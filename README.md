# MSM Lab Assistant

The MSM Lab Assistant is a conversational assistant for the Monash Smart Manufacturing Lab. This project provides a voice-driven interface to interact with lab systems, query databases, control devices, and retrieve contextual information. The assistant is configured using a YAML file with multiple configurable parameters.

## Features
- Voice-controlled assistant with support for keyboard and JoyCon input
- Integration with OpenAI for chat, transcription, and speech synthesis
- OPCUA client for industrial device communication
- Knowledge base and weather tool plugins
- Modular tool system for easy extension
- Database and RAG support via Qdrant
- Async architecture for responsive interaction

## Project Structure
```
msm-assistant/
├── config/                # Configuration files (YAML, JSON)
├── src/
│   └── msm_assistant/
│       ├── start_assistant.py      # Main entry point
│       └── utils/
│           ├── assistant.py       # Core assistant logic
│           └── helper/            # Controllers, tools, configuration, etc.
│               ├── controller/
│               ├── message.py
│               ├── configuration.py
│               └── tools/
│                   ├── base.py
│                   ├── knowledge_base.py
│                   ├── opcua_read.py
│                   └── weather.py
├── scripts/              # Data and collection management scripts
│   ├── add_collections.py
│   ├── create_collection.py
│   └── utils/interfaces.py
├── tests/                # Unit tests
├── pyproject.toml        # Poetry/Project configuration
├── makefile
└── README.md
```

## Getting Started

### Prerequisites
- Python 3.12+
- [Poetry](https://python-poetry.org/)
- (Optional) Qdrant vector database
- (Optional) JoyCon controller (Linux only)

### Installation
1. Clone the repository:
   ```sh
   git clone https://github.com/taistr/msm-assistant.git
   cd msm-assistant
   ```
2. Install dependencies:
   ```sh
   poetry install
   ```
3. Copy and edit any configuration file in `config/` as needed to set up a new assistant.

### Running the Assistant
```sh
poetry run python src/msm_assistant/start_assistant.py --config config/<your-config>.yaml
```

#### Optional Flags
- `--joycon-control` : Use JoyCon controller (Linux only)
- `--database-rag`   : Enable database retrieval-augmented generation
- `--opcua-rag`      : Enable OPCUA server for RAG
- `--opcua-state`    : Share assistant state with OPCUA server


## Extending the Assistant
- Add new tools by subclassing `Tool` in `src/msm_assistant/utils/helper/tools/`
- Update configuration files to enable/disable features

## Documentation
- [Poetry Documentation](https://python-poetry.org/docs/)
- [Pytest Documentation](https://docs.pytest.org/en/stable/)
- [OpenAI Python SDK](https://platform.openai.com/docs/libraries/python-library)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [asyncua (OPCUA)](https://github.com/FreeOpcUa/opcua-asyncio)

## License
MIT License