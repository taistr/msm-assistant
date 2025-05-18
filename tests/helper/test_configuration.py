import sys

import pytest
import yaml

from msm_assistant.utils.helper.configuration import (CategoryConfig,
                                                      ChatConfig,
                                                      Configuration,
                                                      ConfigurationError,
                                                      DatabaseConfig,
                                                      OPCUAConfig,
                                                      SpeechConfig,
                                                      TranscriptionConfig)


# --- TranscriptionConfig ---
@pytest.mark.parametrize(
    "config, error_msg",
    [
        ({}, "needs to contain a 'model' field"),
        ({"model": "invalid-model"}, "The transcription model must be one of"),
    ],
)
def test_transcription_config_invalid(config, error_msg):
    with pytest.raises(ConfigurationError) as exc:
        TranscriptionConfig(config)
    assert error_msg in str(exc.value)


def test_transcription_config_valid():
    cfg = TranscriptionConfig({"model": "whisper-1"})
    assert cfg.model == "whisper-1"


# --- ChatConfig ---
@pytest.mark.parametrize(
    "config, error_msg",
    [
        ({}, "needs to contain a 'model' field"),
        ({"model": "o3-mini"}, "needs to contain a 'prompt' field"),
        ({"model": "invalid", "prompt": "hi"}, "The chat model must be one of"),
    ],
)
def test_chat_config_invalid(config, error_msg):
    with pytest.raises(ConfigurationError) as exc:
        ChatConfig(config)
    assert error_msg in str(exc.value)


def test_chat_config_valid():
    cfg = ChatConfig({"model": "gpt-4", "prompt": "Hello"})
    assert cfg.model == "gpt-4"
    assert cfg.prompt == "Hello"


# --- SpeechConfig ---
@pytest.mark.parametrize(
    "config, error_msg",
    [
        ({}, "needs to contain a 'model' field"),
        ({"model": "gpt-4o-mini-tts"}, "needs to contain a 'voice' field"),
        (
            {"model": "gpt-4o-mini-tts", "voice": "alloy"},
            "needs to contain a 'instructions' field",
        ),
        (
            {"model": "invalid", "voice": "alloy", "instructions": "x"},
            "speech model must be one of",
        ),
        (
            {"model": "gpt-4o-mini-tts", "voice": "invalid", "instructions": "x"},
            "speech voice must be one of",
        ),
    ],
)
def test_speech_config_invalid(config, error_msg):
    with pytest.raises(ConfigurationError) as exc:
        SpeechConfig(config)
    assert error_msg in str(exc.value)


def test_speech_config_valid():
    cfg = SpeechConfig(
        {"model": "gpt-4o-mini-tts", "voice": "alloy", "instructions": "Speak clearly"}
    )
    assert cfg.model == "gpt-4o-mini-tts"
    assert cfg.voice == "alloy"
    assert cfg.instructions == "Speak clearly"


# --- DatabaseConfig ---
@pytest.mark.parametrize(
    "config, error_msg",
    [
        ({}, "needs to contain a 'url' field"),
        ({"url": "http://db"}, "needs to contain a 'collection' field"),
    ],
)
def test_database_config_invalid(config, error_msg):
    with pytest.raises(ConfigurationError) as exc:
        DatabaseConfig(config)
    assert error_msg in str(exc.value)


def test_database_config_valid():
    cfg = DatabaseConfig({"url": "http://db", "collection": "col"})
    assert cfg.url == "http://db"
    assert cfg.collection == "col"


# --- CategoryConfig ---
@pytest.mark.parametrize(
    "config, error_msg",
    [
        ({}, "Missing required key 'category_name'"),
        ({"category_name": "cat"}, "Missing required key 'description'"),
        (
            {"category_name": "cat", "description": "desc"},
            "Missing required key 'nodes'",
        ),
        (
            {"category_name": "cat", "description": "desc", "nodes": []},
            "at least one node",
        ),
        (
            {
                "category_name": "cat",
                "description": "desc",
                "nodes": [{"node_id": "1"}],
            },
            "needs to contain 'node_id' and 'alias' fields",
        ),
    ],
)
def test_category_config_invalid(config, error_msg):
    with pytest.raises(ConfigurationError) as exc:
        CategoryConfig(config)
    assert error_msg in str(exc.value)


def test_category_config_valid():
    nodes = [{"node_id": "1", "alias": "a"}]
    cfg = CategoryConfig(
        {"category_name": "cat", "description": "desc", "nodes": nodes}
    )
    assert cfg.category_name == "cat"
    assert cfg.description == "desc"
    assert cfg.nodes == nodes


# --- OPCUAConfig ---
@pytest.mark.parametrize(
    "config, error_msg",
    [
        ({}, "Missing required key 'url'"),
        ({"url": "u"}, "Missing required key 'conversation_node_id'"),
        (
            {"url": "u", "conversation_node_id": "c"},
            "Missing required key 'state_node_id'",
        ),
    ],
)
def test_opcua_config_invalid(config, error_msg):
    with pytest.raises(ConfigurationError) as exc:
        OPCUAConfig(config)
    assert error_msg in str(exc.value)


def test_opcua_config_valid():
    # include categories too
    config = {
        "url": "u",
        "conversation_node_id": "c",
        "state_node_id": "s",
        "categories": [
            {
                "category_name": "cat",
                "description": "desc",
                "nodes": [{"node_id": "1", "alias": "a"}],
            }
        ],
    }
    cfg = OPCUAConfig(config)
    assert cfg.url == "u"
    assert cfg.state_node_id == "s"
    assert len(cfg.categories) == 1
    assert isinstance(cfg.categories[0], CategoryConfig)


# --- Configuration class ---
def make_full_config_dict():
    return {
        "transcription": {"model": "whisper-1"},
        "chat": {"model": "gpt-4", "prompt": "hi"},
        "speech": {"model": "gpt-4o-mini-tts", "voice": "alloy", "instructions": "x"},
        "database": {"url": "u", "collection": "col"},
        "opcua": {
            "url": "u",
            "conversation_node_id": "c",
            "state_node_id": "s",
            "categories": [],
        },
    }


@pytest.mark.asyncio
async def test_configuration_valid(tmp_path):
    config_dict = make_full_config_dict()
    file = tmp_path / "conf.yaml"
    file.write_text(yaml.safe_dump(config_dict))

    cfg = Configuration(path=file)
    # Check nested attributes
    assert cfg.transcription.model == "whisper-1"
    assert cfg.chat.prompt == "hi"
    # Test add method
    cfg.add("extra", 123)
    assert cfg.additional["extra"] == 123


@pytest.mark.parametrize(
    "missing_key", ["transcription", "chat", "speech", "database", "opcua"]
)
def test_configuration_missing_top_level(monkeypatch, tmp_path, missing_key):
    config = make_full_config_dict()
    del config[missing_key]
    file = tmp_path / "conf.yaml"
    file.write_text(yaml.safe_dump(config))

    monkeypatch.setattr(
        sys, "exit", lambda code: (_ for _ in ()).throw(SystemExit(code))
    )
    with pytest.raises(SystemExit) as exc:
        Configuration(path=file)
    assert exc.value.code == 1


def test_load_yaml_error(monkeypatch, tmp_path):
    # Create a bad YAML file
    file = tmp_path / "bad.yaml"
    file.write_text("invalid: [unclosed")

    # Patch safe_load to throw
    monkeypatch.setitem(
        sys.modules["msm_assistant.utils.helper.configuration"].__dict__, "yaml", yaml
    )
    # Actually monkeypatch yaml.safe_load
    import msm_assistant.utils.helper.configuration as cfg_mod

    monkeypatch.setattr(
        cfg_mod.yaml,
        "safe_load",
        lambda f: (_ for _ in ()).throw(yaml.YAMLError("err")),
    )
    monkeypatch.setattr(
        sys, "exit", lambda code: (_ for _ in ()).throw(SystemExit(code))
    )

    with pytest.raises(SystemExit) as exc:
        Configuration(path=file)
    assert exc.value.code == 1
