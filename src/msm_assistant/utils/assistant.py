import base64
import logging
import tempfile
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from openai import OpenAI

from .helper.configuration import Configuration
from .helper.message import Audio, Conversation, Message, MessageRole

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Assistant:
    def __init__(self, config: Configuration, directory: Path):
        self._config = config
        self._working_directory = directory

        self._openai_client = OpenAI()
        self._conversation = Conversation(
            Message.create(MessageRole.DEVELOPER, content=self._config.prompt)
        )

    def _record_audio(
        self,
    ) -> (
        Path | None
    ):  # TODO: modify this to allow starting and stopping of recording at will
        AUDIO_FILE_NAME = "user.wav"
        SAMPLE_RATE = 44100
        CHANNELS = 1

        chunks = []

        # start the stream
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=np.int16
        )

        # accumulate audio samples
        print("Recording... Press Ctrl+C to stop.")
        try:
            with stream:
                while True:  # Run until interrupted
                    audio_chunk, overflowed = stream.read(SAMPLE_RATE // 10)
                    if overflowed:
                        logger.warning("Warning: Audio buffer overflowed")
                    chunks.append(audio_chunk)
        except KeyboardInterrupt:
            logger.info("Recording finished.")

        # store audio samples
        if chunks:
            audio_array = np.concatenate(chunks)

            file_path = self._working_directory / AUDIO_FILE_NAME
            with wave.open(str(file_path), "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)  # * we are using int16 values - 2 bytes
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_array.tobytes())

            logger.info(f"Audio saved to {file_path}")
            return file_path
        else:
            logger.warning("No audio was recorded")
            return None

    def _transcribe_audio(self, audio_file_path: Path) -> str:
        with open(audio_file_path, "rb") as file:  # TODO: implement exception handling
            transcription = self._openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=file,
                response_format="text",
            )

        return transcription

    def _create_response(self) -> tuple[Path, dict]:
        AUDIO_FILE_NAME = "assistant.wav"

        completion = self._openai_client.chat.completions.create(
            model=self._config.model,
            modalities=["text", "audio"],
            audio={"voice": self._config.voice, "format": "wav"},
            messages=self._conversation.to_messages(),
        )

        wav_bytes = base64.b64decode(completion.choices[0].message.audio.data)
        file_path = self._working_directory / AUDIO_FILE_NAME
        with open(file_path, "wb") as f:
            f.write(wav_bytes)

        return [file_path, completion.choices[0].message.audio.id]

    def _play_audio(self, filepath: Path):
        try:
            audio_data, fs = sf.read(filepath, dtype="float32")
            sd.play(audio_data, fs)
            sd.wait()
        except Exception as e:
            print(f"Error playing audio: {e}")

    def turn(self):
        # Record audio
        user_recording_path = self._record_audio()

        if user_recording_path:
            transcription = self._transcribe_audio(user_recording_path)
            logger.info(f"User said: {transcription}")
        else:
            return

        # Update the convo
        self._conversation.add(Message.create(MessageRole.USER, content=transcription))

        # Create response
        model_output_path, audio_id = self._create_response()

        # Update conversation state
        self._conversation.add(
            Message.create(MessageRole.ASSISTANT, audio=Audio(id=audio_id))
        )

        # Play response
        self._play_audio(model_output_path)


def run(config: dict):
    # Define a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logger.info(f"Temporary directory created: {temp_path}")
        assistant = Assistant(config, temp_path)

        try:
            while True:
                assistant.turn()
        except KeyboardInterrupt:
            logger.info("\nConversation ended by user")
