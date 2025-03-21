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

        self._config = config
        self.openai_api_key = config["base"]["openai_api_key"]
        self.model = config["base"]["model"]
        self.voice = config["base"]["voice"]
        self.prompt = config["base"]["prompt"]

    @staticmethod
    def _verify(config: dict[str, any]):
        """Verify the configuration file"""
        if "base" not in config:
            raise ConfigurationError(
                "The configuration file must contain a 'base' section"
            )

        required_keys = ["openai_api_key", "model", "voice", "prompt"]
        for key in required_keys:
            if key not in config["base"]:
                raise ConfigurationError(
                    f"Missing required key '{key}' in 'base' section"
                )

        valid_models = ["gpt-4o-audio-preview", "gpt-4o-mini-audio-preview"]
        if config["base"]["model"] not in valid_models:
            raise ConfigurationError(
                f"Invalid model '{config['base']['model']}. Models must be one of {valid_models}"
            )

        valid_voices = [
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
        if config["base"]["voice"] not in valid_voices:
            raise ConfigurationError(
                f"Invalid voice '{config['base']['voice']}. Voices must be one of {valid_voices}"
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
