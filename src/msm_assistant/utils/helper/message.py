from abc import ABC, abstractmethod
from enum import Enum


class MessageRole(Enum):
    DEVELOPER = "developer"
    USER = "user"
    ASSISTANT = "assistant"


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


# * User message
class UserMessage(Message):
    role = MessageRole.USER.value

    def __init__(self, content: str):
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


# * Developer message
class DeveloperMessage(Message):
    role = MessageRole.DEVELOPER.value

    def __init__(self, content: str):
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


# * Assistant message
class Audio:
    def __init__(self, id: str):
        self._id = id

    def to_dict(self) -> dict:
        return {"id": self._id}


class AssistantMessage(Message):
    role = MessageRole.ASSISTANT.value

    def __init__(self, audio: Audio):
        self.audio = audio

    def to_dict(self) -> dict:
        return {"role": self.role, "audio": self.audio.to_dict()}


class Conversation:
    def __init__(self, prompt: DeveloperMessage):
        self._state: list[Message] = []
        self._prompt = prompt

    def reset(self):
        self._state = []

    def add(self, message: Message):
        self._state.append(message)

    def to_messages(self) -> list[dict]:
        messages = [message.to_dict() for message in self._state]
        messages.insert(0, self._prompt.to_dict())
        return messages


if __name__ == "__main__":
    user_msg = Message.create("user", content="Hello there!")
    print(user_msg.to_dict())

    dev_msg = Message.create("developer", content="System update available.")
    print(dev_msg.to_dict())

    assistant_msg = Message.create("assistant", audio=Audio("audio123"))
    print(assistant_msg.to_dict())
