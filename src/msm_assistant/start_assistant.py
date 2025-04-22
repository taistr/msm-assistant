#!/usr/bin/env python3
import argparse
import asyncio
import logging
import sys
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

    parser.add_argument(
        "--joycon",
        action="store_true",
        help="Use a JoyCon controller (default: False)",
    )

    parser.add_argument(
        "--database",
        action="store_true",
        help="Use a database for RAG (default: False)",
    )

    parser.add_argument(
        "--opcua",
        action="store_true",
        help="Use OPCUA for RAG and state (default: False)",
    )

    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_arguments()

    config = Configuration(Path(args.config))

    if not sys.platform == "linux" and args.joycon:
        logger.warning(
            "JoyCon support is only implemented on linux. Use keyboard for controls"
        )
        use_joycon = False
    else:
        use_joycon = args.joycon

    config.add("use_joycon", use_joycon)
    config.add("use_database", args.database)
    config.add("use_opcua", args.opcua)

    asyncio.run(run(config))


if __name__ == "__main__":
    main()
