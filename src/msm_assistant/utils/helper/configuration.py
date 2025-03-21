import logging
import sys
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when there is an error with the configuration file"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class Configuration:
    def __init__(self, path: Path):
        config = self._load(path)

        try:
            self._verify(config)
        except ConfigurationError as e:
            logger.error(e)
            sys.exit(1)

        self._config: dict = config
        base: dict = config["base"]
        self.model: str = base["model"]
        self.voice: str = base["voice"]
        self.prompt: str = base["prompt"]

        extra: dict = config["extra"]
        self.database: dict[str, any] | None = extra.get("database")

    @staticmethod
    def _verify(config: dict[str, any]):
        """Verify the configuration file"""
        if "base" not in config:
            raise ConfigurationError(
                "The configuration file must contain a 'base' section"
            )

        if "extra" in config and not isinstance(config["extra"], dict):
            raise ConfigurationError(
                "The 'extra' field must be a dictionary with additional fields"
            )

        REQUIRED_KEYS = ["model", "voice", "prompt"]
        for key in REQUIRED_KEYS:
            if key not in config["base"]:
                raise ConfigurationError(
                    f"Missing required key '{key}' in 'base' section"
                )

        VALID_MODELS = ["gpt-4o-audio-preview", "gpt-4o-mini-audio-preview"]
        if config["base"]["model"] not in VALID_MODELS:
            raise ConfigurationError(
                f"Invalid model '{config['base']['model']}. Models must be one of {VALID_MODELS}"
            )

        VALID_VOICES = [
            "alloy",
            "ash",
            "coral",
            "echo",
            "fable",
            "onyx",
            "nova",
            "sage",
            "shimmer",
        ]
        if config["base"]["voice"] not in VALID_VOICES:
            raise ConfigurationError(
                f"Invalid voice '{config['base']['voice']}. Voices must be one of {VALID_VOICES}"
            )

        if config["base"]["prompt"] == "":
            raise ConfigurationError(
                "The 'prompt' key in the 'base' section cannot be empty"
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
