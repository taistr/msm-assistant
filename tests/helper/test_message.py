import sys
import types
from enum import Enum

import pytest

# --- Setup fake openai.types.chat module before importing message module ---
chat_module = types.ModuleType("openai.types.chat")


class ChatCompletionMessage:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls


chat_module.ChatCompletionMessage = ChatCompletionMessage

types_module = types.ModuleType("openai.types")
types_module.chat = chat_module
openai_module = types.ModuleType("openai")
openai_module.types = types_module

sys.modules["openai"] = openai_module
sys.modules["openai.types"] = types_module
sys.modules["openai.types.chat"] = chat_module

from openai.types.chat import ChatCompletionMessage  # noqa: E402

# --- Import module under test ---
from msm_assistant.utils.helper.message import AssistantMessage  # noqa: E402
from msm_assistant.utils.helper.message import Conversation  # noqa: E402
from msm_assistant.utils.helper.message import (DeveloperMessage, Message, # noqa: E402
                                                MessageRole, ToolMessage,
                                                UserMessage)

# --- Tests for Message registry and factory ---


def test_registry_populated():
    registry = Message._registry
    assert registry[MessageRole.USER.value] is UserMessage
    assert registry[MessageRole.DEVELOPER.value] is DeveloperMessage
    assert registry[MessageRole.ASSISTANT.value] is AssistantMessage
    assert registry[MessageRole.TOOL.value] is ToolMessage


def test_create_valid():
    user_msg = Message.create(MessageRole.USER, content="hello")
    assert isinstance(user_msg, UserMessage)
    assert user_msg.content == "hello"

    dev_msg = Message.create(MessageRole.DEVELOPER, content="dev-content")
    assert isinstance(dev_msg, DeveloperMessage)
    assert dev_msg.content == "dev-content"


def test_create_invalid_role():
    class FakeRole(Enum):
        UNKNOWN = "unknown"

    with pytest.raises(ValueError) as exc:
        Message.create(FakeRole.UNKNOWN, content="x")
    assert "No message registered for role" in str(exc.value)


# --- Tests for to_dict methods on each Message subclass ---


def test_to_dict_user_message():
    um = UserMessage("u")
    assert um.to_dict() == {"role": MessageRole.USER.value, "content": "u"}


def test_to_dict_developer_message():
    dm = DeveloperMessage("d")
    assert dm.to_dict() == {"role": MessageRole.DEVELOPER.value, "content": "d"}


def test_to_dict_assistant_message():
    am = AssistantMessage("a")
    assert am.to_dict() == {"role": MessageRole.ASSISTANT.value, "content": "a"}


def test_to_dict_tool_message():
    tm = ToolMessage(tool_call_id="123", content="output")
    assert tm.to_dict() == {
        "role": MessageRole.TOOL.value,
        "tool_call_id": "123",
        "content": "output",
    }


# --- Tests for Conversation ---


def test_conversation_initial_state_only_prompt():
    prompt = DeveloperMessage("start")
    conv = Conversation(prompt)
    msgs = conv.to_messages()
    assert msgs == [prompt.to_dict()]


def test_conversation_add_and_to_messages():
    prompt = DeveloperMessage("start")
    conv = Conversation(prompt)
    conv.add(UserMessage("hey"))
    conv.add(AssistantMessage("reply"))
    msgs = conv.to_messages()
    assert msgs == [
        prompt.to_dict(),
        {"role": MessageRole.USER.value, "content": "hey"},
        {"role": MessageRole.ASSISTANT.value, "content": "reply"},
    ]


def test_conversation_reset():
    prompt = DeveloperMessage("init")
    conv = Conversation(prompt)
    conv.add(UserMessage("u"))
    conv.reset()
    msgs = conv.to_messages()
    assert msgs == [prompt.to_dict()]


def test_add_chat_message_without_tool_calls_raises():
    prompt = DeveloperMessage("p")
    conv = Conversation(prompt)
    cc = ChatCompletionMessage(tool_calls=None)
    with pytest.raises(ValueError) as exc:
        conv.add(cc)
    assert "ChatCompletionMessage instances should only be added for tool calls" in str(
        exc.value
    )


def test_conversation_with_tool_call_messages():
    # Create dummy tool_call
    from types import SimpleNamespace

    tool_call = SimpleNamespace(
        id="call1",
        function=SimpleNamespace(name="fn", arguments="args"),
    )
    cc = ChatCompletionMessage(tool_calls=[tool_call])

    prompt = DeveloperMessage("prompt")
    conv = Conversation(prompt)
    conv.add(cc)

    # to_dict=False (default): message object preserved
    msgs_obj = conv.to_messages()
    assert msgs_obj[0] == prompt.to_dict()
    assert isinstance(msgs_obj[1], ChatCompletionMessage)

    # to_dict=True: convert tool call to dict
    msgs_dict = conv.to_messages(to_dict=True)
    assert msgs_dict == [
        prompt.to_dict(),
        {"id": "call1", "function_name": "fn", "arguments": "fn"},
    ]


def test_to_messages_unknown_message_type_raises():
    prompt = DeveloperMessage("p")
    conv = Conversation(prompt)
    # Append an unsupported type
    conv._state.append(42)
    with pytest.raises(ValueError) as exc:
        conv.to_messages()
    assert "Unknown message type" in str(exc.value)
