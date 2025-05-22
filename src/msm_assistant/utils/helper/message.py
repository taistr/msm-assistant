from abc import ABC, abstractmethod
from enum import Enum

from openai.types.chat import ChatCompletionMessage


class MessageRole(Enum):
    DEVELOPER = "developer"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(ABC):
    _registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if hasattr(cls, "role"):
            Message._registry[cls.role] = cls

    @abstractmethod
    def to_dict() -> dict:
        pass

    @classmethod
    def create(cls, role: MessageRole, **kwargs):
        if role.value not in cls._registry:
            raise ValueError(f"No message registered for role '{role.value}'")
        return cls._registry[role.value](**kwargs)


class UserMessage(Message):
    role = MessageRole.USER.value

    def __init__(self, content: str):
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class DeveloperMessage(Message):
    role = MessageRole.DEVELOPER.value

    def __init__(self, content: str):
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class AssistantMessage(Message):
    role = MessageRole.ASSISTANT.value

    def __init__(self, content: str):
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class ToolMessage(Message):
    role = MessageRole.TOOL.value

    def __init__(self, tool_call_id: str, content: str):
        self.tool_call_id = tool_call_id
        self.content = content

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "tool_call_id": self.tool_call_id,
            "content": self.content,
        }


class Conversation:
    def __init__(self, prompt: DeveloperMessage):
        self._state: list[Message] = []
        self._prompt = prompt

    def reset(self):
        self._state = []

    def add(self, message: Message | ChatCompletionMessage):
        #! ChatCompletionMessages that contain tool calls need to be preserved as they are in the conversation history
        if isinstance(message, ChatCompletionMessage) and message.tool_calls is None:
            raise ValueError(
                "ChatCompletionMessage instances should only be added for tool calls"
            )

        self._state.append(message)

    def to_messages(self, to_dict: bool = False) -> list[dict]:
        messages = []

        for message in self._state:
            if isinstance(message, Message):
                messages.append(message.to_dict())
            elif isinstance(
                message, ChatCompletionMessage
            ):  #! specifically in the case of a tool call
                message: ChatCompletionMessage
                if to_dict:
                    tool_call_message = {
                        "id": message.tool_calls[0].id,
                        "function_name": message.tool_calls[0].function.name,
                        "arguments": message.tool_calls[0].function.name,
                    }
                    messages.append(tool_call_message)
                else:
                    messages.append(message)
            else:
                raise ValueError(f"Unknown message type: {type(message)}")

        messages.insert(0, self._prompt.to_dict())
        return messages
