import logging
import sys
from pathlib import Path
from typing import List

import yaml

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when there is an error with the configuration file"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class TranscriptionConfig:
    def __init__(self, config: dict):
        self._verify(config)

        self.model: str = config["model"]

    def _verify(self, config: dict):
        if "model" not in config:
            raise ConfigurationError(
                "The transcription configuration needs to contain a 'model' field."
            )

        VALID_MODELS = [
            "whisper-1",
            "gpt-4o-mini-transcribe",
            "gpt-4o-transcribe",
        ]
        if config["model"] not in VALID_MODELS:
            raise ConfigurationError(
                f"The transcription model must be one of {VALID_MODELS}"
            )


class ChatConfig:
    def __init__(self, config: dict):
        self._verify(config)

        self.model: str = config["model"]
        self.prompt: str = config["prompt"]

    def _verify(self, config: dict):
        if "model" not in config:
            raise ConfigurationError(
                "The chat configuration needs to contain a 'model' field."
            )

        if "prompt" not in config:
            raise ConfigurationError(
                "The chat configuration needs to contain a 'prompt' field."
            )

        VALID_MODELS = [
            "o3-mini",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
        ]
        if config["model"] not in VALID_MODELS:
            raise ConfigurationError(f"The chat model must be one of {VALID_MODELS}")


class SpeechConfig:
    def __init__(self, config: dict):
        self._verify(config)

        self.model: str = config["model"]
        self.voice: str = config["voice"]
        self.instructions: str = config["instructions"]

    def _verify(self, config: dict):
        if "model" not in config:
            raise ConfigurationError(
                "The speech configuration needs to contain a 'model' field."
            )

        if "voice" not in config:
            raise ConfigurationError(
                "The speech configuration needs to contain a 'voice' field."
            )

        if "instructions" not in config:
            raise ConfigurationError(
                "The speech configuration needs to contain a 'instructions' field."
            )

        VALID_VOICES = [
            "alloy",
            "ash",
            "ballad",
            "coral",
            "echo",
            "fable",
            "onyx",
            "nova",
            "sage",
            "shimmer",
            "verse",
        ]

        VALID_MODELS = [
            "gpt-4o-mini-tts",
        ]

        if config["model"] not in VALID_MODELS:
            raise ConfigurationError(f"The speech model must be one of {VALID_MODELS}")

        if config["voice"] not in VALID_VOICES:
            raise ConfigurationError(f"The speech voice must be one of {VALID_VOICES}")


class DatabaseConfig:
    def __init__(self, config: dict):
        self._verify(config)

        self.url: str = config["url"]
        self.collection: str = config["collection"]

    def _verify(self, config: dict):
        if "url" not in config:
            raise ConfigurationError(
                "The database configuration needs to contain a 'url' field."
            )

        if "collection" not in config:
            raise ConfigurationError(
                "The database configuration needs to contain a 'collection' field."
            )


class CategoryConfig:
    def __init__(self, config: dict):
        self._verify(config)

        self.category_name: str = config["category_name"]
        self.description: str = config["description"]
        self.nodes: List[str] = config["nodes"]

    def _verify(self, config: dict):
        REQUIRED_KEYS = [
            "category_name",
            "description",
            "nodes",
        ]
        for key in REQUIRED_KEYS:
            if key not in config:
                raise ConfigurationError(
                    f"Missing required key '{key}' in the OPCUARead configuration."
                )

        if len(config["nodes"]) == 0:
            raise ConfigurationError(
                "The OPCUARead configuration needs to contain at least one node."
            )

        REQUIRED_NODE_KEYS = [
            "node_id",
            "alias",
        ]
        if not self.all_dicts_have_keys(config["nodes"], REQUIRED_NODE_KEYS):
            raise ConfigurationError(
                "Each node in the OPCUARead configuration needs to contain 'node_id' and 'alias' fields."
            )

    @staticmethod
    def all_dicts_have_keys(dict_list, required_keys):
        return all(all(key in d for key in required_keys) for d in dict_list)


class OPCUAConfig:
    def __init__(self, config: dict):
        self._verify(config)

        self.url: str = config["url"]
        self.state_node_id: str = config["state_node_id"]
        self.conversation_node_id: str = config["conversation_node_id"]
        self.categories: List[CategoryConfig] = [
            CategoryConfig(category_dict)
            for category_dict in config.get("categories", [])
        ]

    def _verify(self, config: dict):
        REQUIRED_KEYS = [
            "url",
            "conversation_node_id",
            "state_node_id",
        ]
        for key in REQUIRED_KEYS:
            if key not in config:
                raise ConfigurationError(
                    f"Missing required key '{key}' in the OPCUA configuration."
                )


class Configuration:
    def __init__(self, path: Path):
        config = self._load(path)

        try:
            self._verify(config)
        except ConfigurationError as e:
            logger.error(e)
            sys.exit(1)

        self._config: dict = config

        self.transcription: TranscriptionConfig = TranscriptionConfig(
            config["transcription"]
        )
        self.chat: ChatConfig = ChatConfig(config["chat"])
        self.speech: SpeechConfig = SpeechConfig(config["speech"])
        self.database: DatabaseConfig = DatabaseConfig(config["database"])
        self.opcua: OPCUAConfig = OPCUAConfig(config["opcua"])

        self.additional: dict[str, any] = {}

    def add(self, key: str, value: any):
        """Add a new configuration key-value pair"""
        self.additional[key] = value

    @staticmethod
    def _verify(config: dict[str, any]):
        """Verify the configuration file"""

        REQUIRED_KEYS = ["transcription", "chat", "speech", "database", "opcua"]
        for key in REQUIRED_KEYS:
            if key not in config:
                raise ConfigurationError(
                    f"Missing required key '{key}' in the configuration file."
                )

    @staticmethod
    def _load(path: Path) -> dict:
        """Load a YAML configuration file"""
        try:
            with open(path, "r") as file:
                config = yaml.safe_load(file)
            return config
        except FileNotFoundError:
            logger.error(f"The file '{path}' could not be found")
            sys.exit(1)
        except yaml.YAMLError as e:
            logger.error(f"Unable to parse the provided YAML file. {e}")
            sys.exit(1)
