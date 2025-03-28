import base64
import enum
import logging
import tempfile
import threading
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from openai import OpenAI
from transitions import Machine

from .helper.configuration import Configuration
from .helper.controller import JoyCon, JoyConButton, JoyConButtonState
from .helper.message import Audio, Conversation, Message, MessageRole

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Arguments:
    user_recording_path: Path | None
    model_output_path: Path | None


class States(enum.Enum):
    ERROR = "error"
    RESET = "reset"
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class Assistant:
    states = [state.value for state in States]

    def __init__(self, config: Configuration, directory: Path):
        self._config = config
        self._working_directory = directory

        self._openai_client = OpenAI()
        self._conversation = Conversation(
            Message.create(MessageRole.DEVELOPER, content=self._config.prompt)
        )

        self._controller = JoyCon()

        self._args = Arguments(user_recording_path=None, model_output_path=None)
        self._machine = Machine(
            model=self, states=Assistant.states, initial=States.IDLE.value
        )
        self._machine.add_transition(
            source=States.IDLE.value,
            dest=States.LISTENING.value,
            trigger="start_listening",
        )
        self._machine.add_transition(
            source=States.LISTENING.value,
            dest=States.PROCESSING.value,
            trigger="start_processing",
        )
        self._machine.add_transition(
            source=States.PROCESSING.value,
            dest=States.SPEAKING.value,
            trigger="start_speaking",
        )
        self._machine.add_transition(
            source=States.SPEAKING.value, dest=States.IDLE.value, trigger="start_idle"
        )
        self._machine.add_transition(
            source="*", dest=States.ERROR.value, trigger="start_error"
        )

    def on_enter_idle(self):
        logger.info("Entered IDLE state")
        logger.info("Press A to start recording")

        while True:
            button = self._controller.listen(JoyConButtonState.PRESSED)
            if button == JoyConButton.A:
                break

        self.start_listening()

    def on_enter_listening(self):
        logger.info("Entered LISTENING state")

        self._args.user_recording_path = self._record_audio()

        self.start_processing()
        return

    def on_enter_processing(self):
        logger.info("Entered PROCESSING state")

        user_recording_path = self._args.user_recording_path
        if user_recording_path:
            transcription = self._transcribe_audio(user_recording_path)
            logger.info(f"User said: {transcription}")
        else:
            self.start_error()
            return

        # Update the convo
        self._conversation.add(Message.create(MessageRole.USER, content=transcription))

        # Create response
        model_output_path, audio_id = self._create_response()
        self._args.model_output_path = model_output_path

        # Update conversation state
        self._conversation.add(
            Message.create(MessageRole.ASSISTANT, audio=Audio(id=audio_id))
        )

        self.start_speaking()
        return

    def on_enter_speaking(self):
        logger.info("Entered SPEAKING state")

        model_output_path = self._args.model_output_path
        self._play_audio(model_output_path)

        self.start_idle()
        return

    def _record_audio(
        self, file_name: str = "user.wav", sample_rate: int = 44100, channels: int = 1
    ):
        FRAME_DIVISOR = 10
        SAMPLE_CONFIG = {"type": np.int16, "byte_width": 2}

        chunks = []
        stop_event = threading.Event()

        def button_listener():
            while not stop_event.is_set():
                button = self._controller.listen(JoyConButtonState.PRESSED)
                if button == JoyConButton.A:
                    stop_event.set()

        listener_thread = threading.Thread(target=button_listener, daemon=True)

        # start the stream
        stream = sd.InputStream(
            samplerate=sample_rate, channels=channels, dtype=SAMPLE_CONFIG["type"]
        )

        # accumulate audio samples
        print("Recording... Press A to stop.")
        try:
            listener_thread.start()

            with stream:
                while not stop_event.is_set():  # Run until interrupted
                    audio_chunk, overflowed = stream.read(sample_rate // FRAME_DIVISOR)
                    if overflowed:
                        logger.warning("Warning: Audio buffer overflowed")
                    chunks.append(audio_chunk)
        except (
            Exception
        ) as e:  #! if an exception occurs here then the controller thread lives on!
            # TODO: fix threads staying alive
            logger.error(f"Error occurred during recording: {e}")
        finally:
            stop_event.set()
            listener_thread.join()

        # store audio samples
        if chunks:
            audio_array = np.concatenate(chunks)

            file_path = self._working_directory / file_name
            with wave.open(str(file_path), "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(
                    SAMPLE_CONFIG["byte_width"]
                )  # * we are using int16 values - 2 bytes
                wf.setframerate(sample_rate)
                wf.writeframes(audio_array.tobytes())

            logger.info(f"Audio saved to {file_path}")
            return file_path
        else:
            logger.warning("No audio was recorded")
            return None

    def _transcribe_audio(self, file_path: Path) -> str:
        with open(file_path, "rb") as file:  # TODO: implement exception handling
            transcription = self._openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=file,
                response_format="text",
            )

        return transcription

    def _create_response(self, file_name: str = "assistant.wav") -> tuple[Path, dict]:
        completion = self._openai_client.chat.completions.create(
            model=self._config.model,
            modalities=["text", "audio"],
            audio={"voice": self._config.voice, "format": "wav"},
            messages=self._conversation.to_messages(),
        )

        wav_bytes = base64.b64decode(completion.choices[0].message.audio.data)
        file_path = self._working_directory / file_name
        with open(file_path, "wb") as f:
            f.write(wav_bytes)

        return [file_path, completion.choices[0].message.audio.id]

    def _play_audio(self, file_path: Path):
        try:
            audio_data, fs = sf.read(file_path, dtype="float32")
            sd.play(audio_data, fs)
            sd.wait()
        except Exception as e:
            print(f"Error playing audio: {e}")


def run(config: dict):
    # Define a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path("/home/msm_assistant_test/Documents/msm-assistant/temp")
        logger.info(f"Temporary directory created: {temp_path}")
        assistant = Assistant(config, temp_path)

        try:
            assistant.on_enter_idle()
        except KeyboardInterrupt:
            logger.info("Conversation ended by user")
