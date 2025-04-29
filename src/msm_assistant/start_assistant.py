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
        "--joycon-control",
        action="store_true",
        help="Use a JoyCon controller (default: False)",
    )

    parser.add_argument(
        "--database-rag",
        action="store_true",
        help="Use a database for RAG (default: False)",
    )

    parser.add_argument(
        "--opcua-rag",
        action="store_true",
        help="Use the OPCUA server for RAG (default: False)",
    )

    parser.add_argument(
        "--opcua-state",
        action="store_true",
        help="Share the assistant's state with the OPCUA server (default: False)",
    )

    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_arguments()

    config = Configuration(Path(args.config))

    if not sys.platform == "linux" and args.joycon_control:
        logger.warning(
            "JoyCon support is only implemented on linux. Use keyboard for controls"
        )
        use_joycon = False
    else:
        use_joycon = args.joycon_control

    config.add("use_joycon", use_joycon)
    config.add("use_database_rag", args.database_rag)
    config.add("use_opcua_rag", args.opcua_rag)
    config.add("share_state", args.opcua_state)

    asyncio.run(run(config))


if __name__ == "__main__":
    main()
