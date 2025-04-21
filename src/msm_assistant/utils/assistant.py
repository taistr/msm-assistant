import asyncio
import enum
import json
import logging
import tempfile
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
from asyncua import Client, ua
from openai import AsyncOpenAI
from transitions.extensions.asyncio import AsyncMachine

from .helper.configuration import Configuration
from .helper.controller.base import Button, State
from .helper.controller.joycon import JoyCon
from .helper.controller.keyboard import Keyboard
from .helper.message import Conversation, Message, MessageRole
from .helper.tools.base import Tool
from .helper.tools.knowledge_base import KnowledgeBase
from .helper.tools.weather import Weather

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
            Keyboard() if self._config.additional.get("use_keyboard") else JoyCon()
        )
        logger.info(f"Using {self._controller.__class__.__name__} controller")

        self._openai_client = AsyncOpenAI()
        self._conversation = Conversation(
            Message.create(MessageRole.DEVELOPER, content=self._config.chat.prompt)
        )
        self._opcua_client = Client(
            url=self._config.opcua.url
        )  # TODO: make the use of this configurable

        self._tools: dict[str, Tool] = {
            Weather.name(): Weather(),
        }
        if self._config.additional.get("use_database"):
            self._tools[KnowledgeBase.name()] = (
                KnowledgeBase(  # TODO: make the name of the knowledge base function call more domain specific
                    url=self._config.database.url,
                    collection=self._config.database.collection,
                )
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

        # initialise the tools
        for tool in self._tools.values():
            await tool.init()
            logger.info(f"Tool {tool.name()} initialized")

        # initialise the opcua client
        await self._opcua_client.connect()
        asyncio.create_task(self._update_state())
        logger.info("Connected to OPCUA server")

        # transition to idle
        await self.start_idle()

    async def on_enter_reset(self):
        logger.info("Resetting conversation...")
        self._conversation.reset()
        self._args.user_recording_path = None
        self._args.model_response = None

        self.start_idle()

    async def on_enter_idle(self):
        # await on controller input
        event = asyncio.Event()
        to_reset = False

        async def listener(button: Button, state: State):
            nonlocal to_reset
            if state == State.PRESSED:
                if button == Button.PRIMARY:
                    event.set()
                if button == Button.SECONDARY:
                    to_reset = True
                    event.set()

        listener_id = await self._controller.add_listener(listener)
        logger.info(
            f"Press {Button.PRIMARY} to start recording or {Button.SECONDARY} to reset..."
        )
        await event.wait()
        await self._controller.remove_listener(listener_id)

        # transition to either start recording or reset conversation
        if to_reset:
            await self.start_reset()
        else:
            await self.start_listening()

    async def on_enter_listening(self):
        # wait for a button press
        stop_flag = threading.Event()
        to_idle = False

        async def listener(button: Button, state: State):
            nonlocal to_idle
            if state == State.PRESSED:
                if button == Button.PRIMARY:
                    stop_flag.set()
                elif button == Button.SECONDARY:
                    stop_flag.set()
                    to_idle = True

        listener_id = await self._controller.add_listener(listener)
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
        messages = await self._generate_response(self._conversation)
        for message in messages:
            self._conversation.add(message)

        self._args.model_response = messages[-1].content
        logger.info(f"Assistant: {self._args.model_response}")

        # transition to speech (only if the last 4 operations were successful)
        await self.start_speaking()

    async def on_enter_speaking(self):
        event = asyncio.Event()

        async def listener(button: Button, state: State):
            if state == State.PRESSED:
                if button == Button.SECONDARY:
                    event.set()

        # stream the audio while checking for interruptions
        logger.info(f"Generating speech... Press {Button.SECONDARY} to interrupt")
        listener_id = await self._controller.add_listener(listener)
        await self._generate_speech(self._args.model_response, event)
        await self._controller.remove_listener(listener_id)

        # transition to idle (either through interruption or finishing)
        await self.start_idle()

    async def _update_state(self):
        POLLING_PERIOD = 0.2  # seconds
        state_node = self._opcua_client.get_node(self._config.opcua.state_node_id)
        conversation_node = self._opcua_client.get_node(
            self._config.opcua.conversation_node_id
        )

        while True:
            await state_node.write_value(
                ua.Variant(
                    self.state,
                    ua.VariantType.String,
                )
            )
            await conversation_node.write_value(
                ua.Variant(
                    json.dumps(self._conversation.to_messages()),
                    ua.VariantType.String,
                )
            )
            await asyncio.sleep(POLLING_PERIOD)

    async def _generate_speech(self, text: str, stop_flag: asyncio.Event):
        SAMPLE_RATE = 24000  # OpenAI's TTS default rate

        async with self._openai_client.audio.speech.with_streaming_response.create(
            model=self._config.speech.model,
            voice=self._config.speech.voice,
            input=text,
            instructions=self._config.speech.instructions,
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

    async def _generate_response(
        self, conversation: Conversation
    ) -> list[Message]:  #! return all messages in the conversation
        tools = [tool.get_definition() for tool in self._tools.values()]
        completion = await self._openai_client.chat.completions.create(
            model=self._config.chat.model,
            messages=conversation.to_messages(),
            tools=tools,
        )

        # handle tool calls
        messages = []
        if completion.choices[0].finish_reason == "tool_calls":
            messages.append(
                completion.choices[0].message
            )  # append model's function call message

            # execute the tool calls
            tool_calls = completion.choices[0].message.tool_calls
            for tool_call in tool_calls:
                args = json.loads(tool_call.function.arguments)
                result = await self._tools[tool_call.function.name].execute(args)
                messages.append(
                    Message.create(
                        MessageRole.TOOL,
                        tool_call_id=tool_call.id,
                        content=str(result),
                    )
                )

            # generate another response
            completion_alt = await self._openai_client.chat.completions.create(
                model=self._config.chat.model,
                messages=conversation.to_messages()
                + [message.to_dict() for message in messages],
            )  #! this needs to be more robust later
            content = completion_alt.choices[0].message.content
            messages.append(
                Message.create(
                    MessageRole.ASSISTANT,
                    content=content,
                )
            )
        elif completion.choices[0].finish_reason == "stop":
            messages.append(
                Message.create(
                    MessageRole.ASSISTANT,
                    content=completion.choices[0].message.content,
                )
            )
        else:
            raise ValueError(
                f"Encountered unhandled finish reason: {completion.choices[0].finish_reason}"
            )

        return messages

    async def _transcribe_audio(self, file_path: Path) -> str:
        with open(
            file_path, "rb"
        ) as file:  # TODO: add exception handling/retries if not inbuilt
            # Assuming the async API method is called acreate:
            transcription = await self._openai_client.audio.transcriptions.create(
                model=self._config.transcription.model,
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

        logger.info(
            f"Recording... Press {Button.PRIMARY} to stop or {Button.SECONDARY} to cancel."
        )
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


async def run(config: Configuration):
    # Define a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logger.info(f"Temporary directory created: {temp_path}")

        assistant = Assistant(config, temp_path)

        try:
            await assistant.on_enter_initial()
        except KeyboardInterrupt:
            logger.info("Conversation ended by user")
