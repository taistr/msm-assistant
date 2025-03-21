#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from msm_assistant.utils.assistant import Configuration, run

logger = logging.getLogger(__name__)


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="Monash Automation Assistant",
        description="A conversational assistant that can be verbally queried",
    )

    parser.add_argument(
        "--config", "-c", required=True, help="Path to the configuration YAML file"
    )

    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_arguments()

    config = Configuration(Path(args.config))
    run(config)


if __name__ == "__main__":
    main()
