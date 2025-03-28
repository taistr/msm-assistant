import asyncio
import enum
import logging
import tempfile
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf
from openai import AsyncOpenAI, OpenAI
from openai.helpers import LocalAudioPlayer
from transitions.extensions.asyncio import AsyncMachine

from .helper.configuration import Configuration
from .helper.controller import JoyCon, JoyConButton, JoyConButtonState
from .helper.message import Conversation, Message, MessageRole

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Arguments:
    user_recording_path: Path | None
    model_response: str


class States(enum.Enum):
    ERROR = "error"
    RESET = "reset"
    INITIAL = "initial"
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class Assistant:
    states = [state.value for state in States]

    def __init__(self, config: Configuration, directory: Path):
        self._config = config
        self._working_directory = directory

        self._args = Arguments(
            user_recording_path=None,
            model_response=None,  # TODO: this should come from the conversation later
        )

        self._controller = (
            JoyCon()
        )  # TODO: make this a child class of a parent "controller" class with generic listen, add_listener and remove_listener methods
        self._openai_client = AsyncOpenAI()
        self._conversation = Conversation(
            Message.create(MessageRole.DEVELOPER, content=self._config.prompt)
        )

        self._machine = AsyncMachine(
            model=self,
            states=Assistant.states,
            initial=States.INITIAL.value,
        )
        self._populate_machine()

    def _populate_machine(self) -> None:
        if not self._machine:
            raise ValueError("Cannot populate machine transitions")
        self._machine.add_transition(  # * listening: receive inputs
            source=[States.IDLE.value, States.SPEAKING.value],
            dest=States.LISTENING.value,
            trigger="start_listening",
        )
        self._machine.add_transition(  # * processing
            source=States.LISTENING.value,
            dest=States.PROCESSING.value,
            trigger="start_processing",
        )
        self._machine.add_transition(  # * speaking
            source=States.PROCESSING.value,
            dest=States.SPEAKING.value,
            trigger="start_speaking",
        )
        self._machine.add_transition(  # * idle
            source=[
                States.INITIAL.value,
                States.SPEAKING.value,
                States.LISTENING.value,
            ],
            dest=States.IDLE.value,
            trigger="start_idle",
        )
        self._machine.add_transition(  # * error
            source="*",
            dest=States.ERROR.value,
            trigger="start_error",
        )
        self._machine.add_transition(  # * reset
            source=States.IDLE.value, dest=States.RESET.value, trigger="start_reset"
        )

    async def on_enter_initial(self):
        # initialise the controller listen
        await self._controller.listen()
        logger.info("Started controller listener")

        # transition to idle
        await self.start_idle()

    async def on_enter_idle(self):
        # await on controller input
        event = asyncio.Event()

        async def joycon_listener(button: JoyConButton, state: JoyConButtonState):
            if state == JoyConButtonState.PRESSED:
                if button == JoyConButton.A:
                    event.set()

        listener_id = await self._controller.add_listener(joycon_listener)
        logger.info("Press A to start recording...")
        await event.wait()
        await self._controller.remove_listener(listener_id)

        # TODO: add transition to reset
        # transition to either start recording or reset conversation
        await self.start_listening()

    async def on_enter_listening(self):
        # wait for a button press
        stop_flag = threading.Event()
        to_idle = False

        async def joycon_listener(button: JoyConButton, state: JoyConButtonState):
            nonlocal to_idle
            if state == JoyConButtonState.PRESSED:
                if button == JoyConButton.A:
                    stop_flag.set()
                elif button == JoyConButton.B:
                    stop_flag.set()
                    to_idle = True

        listener_id = await self._controller.add_listener(joycon_listener)
        self._args.user_recording_path = await asyncio.to_thread(
            self._record_audio, stop_flag
        )
        await self._controller.remove_listener(listener_id)

        # transition to processing or idle
        if to_idle:
            await self.start_idle()
        else:
            await self.start_processing()

    async def on_enter_processing(self):
        # transcribe speech
        user_text = await self._transcribe_audio(self._args.user_recording_path)
        logger.info(f"User: {user_text}")
        self._conversation.add(Message.create(MessageRole.USER, content=user_text))

        # generate response
        self._args.model_response = await self._generate_response(self._conversation)
        logger.info(f"Assistant: {self._args.model_response}")
        self._conversation.add(
            Message.create(MessageRole.ASSISTANT, content=self._args.model_response)
        )

        # transition to speech (only if the last 4 operations were successful)
        await self.start_speaking()

    async def on_enter_speaking(self):
        event = asyncio.Event()

        async def joycon_listener(button: JoyConButton, state: JoyConButtonState):
            if state == JoyConButtonState.PRESSED:
                if button == JoyConButton.B:
                    event.set()

        # stream the audio while checking for interruptions
        logger.info("Generating speech... Press B to interrupt")
        listener_id = await self._controller.add_listener(joycon_listener)
        await self._generate_speech(self._args.model_response, event)
        await self._controller.remove_listener(listener_id)

        # transition to idle (either through interruption or finishing)
        await self.start_idle()

    async def _generate_speech(self, text: str, stop_flag: asyncio.Event):
        SAMPLE_RATE = 24000  # OpenAI's TTS default rate
        INSTRUCTIONS = """Voice: Gruff, fast-talking, and a little worn-out, like a New York cabbie who's seen it all but still keeps things moving.\n\nTone: Slightly exasperated but still functional, with a mix of sarcasm and no-nonsense efficiency.\n\nDialect: Strong New York accent, with dropped \"r\"s, sharp consonants, and classic phrases like whaddaya and lemme guess.\n\nPronunciation: Quick and clipped, with a rhythm that mimics the natural hustle of a busy city conversation.\n\nFeatures: Uses informal, straight-to-the-point language, throws in some dry humor, and keeps the energy just on the edge of impatience but still helpful."""

        async with self._openai_client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",  # TODO: make all sthis configurable
            voice="coral",
            input=text,
            instructions=INSTRUCTIONS,
            response_format="pcm",
        ) as response:
            with sd.OutputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="int16"
            ) as stream:
                async for chunk in response.iter_bytes(chunk_size=1024):
                    if stop_flag.is_set():
                        print("Playback interrupted!")
                        break

                    audio_array = np.frombuffer(chunk, dtype=np.int16)
                    stream.write(audio_array)

    async def _generate_response(self, conversation: Conversation) -> str:
        completion = await self._openai_client.chat.completions.create(
            model="gpt-4o-mini",  # TODO: make this configurable
            messages=conversation.to_messages(),
        )
        # TODO: handle tool calls

        return completion.choices[0].message.content

    async def _transcribe_audio(self, file_path: Path) -> str:
        with open(
            file_path, "rb"
        ) as file:  # TODO: add exception handling/retries if not inbuilt
            # Assuming the async API method is called acreate:
            transcription = await self._openai_client.audio.transcriptions.create(
                model="whisper-1",  # TODO: make this configurable
                file=file,
                response_format="text",
            )
        return transcription

    def _record_audio(
        self,
        stop_flag: asyncio.Event,
        file_name: str = "user.wav",
        sample_rate: int = 44100,
        channels: int = 1,
    ) -> Optional[Path]:
        FRAME_DIVISOR = 10
        SAMPLE_CONFIG = {"type": np.int16, "byte_width": 2}

        chunks = []
        stream = sd.InputStream(
            samplerate=sample_rate, channels=channels, dtype=SAMPLE_CONFIG["type"]
        )

        logger.info("Recording... Press A to stop or B to cancel.")
        try:
            with stream:
                while not stop_flag.is_set():
                    audio_chunk, overflowed = stream.read(sample_rate // FRAME_DIVISOR)
                    if overflowed:
                        logger.warning("Warning: audio buffer overflowed")
                    chunks.append(audio_chunk)
        except Exception as e:
            logger.error(f"Error during recording: {e}")
            return
        logger.info("Finished recording.")

        # Store audio samples to file if any chunks were recorded
        if chunks:
            audio_array = np.concatenate(chunks)
            file_path = self._working_directory / file_name
            with wave.open(str(file_path), "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(SAMPLE_CONFIG["byte_width"])  # int16 = 2 bytes
                wf.setframerate(sample_rate)
                wf.writeframes(audio_array.tobytes())
            logger.info(f"Audio saved to {file_path}")
            return file_path
        else:
            logger.warning("No audio was recorded")
            return None


async def run(config: dict):
    # Define a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path("/home/msm_assistant_test/Documents/msm-assistant/temp")
        logger.info(f"Temporary directory created: {temp_path}")
        assistant = Assistant(config, temp_path)

        try:
            await assistant.on_enter_initial()
        except KeyboardInterrupt:
            logger.info("Conversation ended by user")
