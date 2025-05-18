import logging
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class State(Enum):
    PRESSED = 1
    RELEASED = 0


class Button(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


# Controller interface
class Controller(ABC):
    def __init__(self):
        self._listeners: dict[str, Callable[[Button, State], Awaitable[None]]] = {}

    @abstractmethod
    async def listen(self):
        raise NotImplementedError("listen method must be implemented in subclasses")

    @abstractmethod
    async def stop(self):
        raise NotImplementedError("stop method must be implemented in subclasses")

    async def add_listener(
        self, callback: Callable[[Button, State], Awaitable[None]]
    ) -> str:
        """
        Add a listener for button events.
        Args:
            callback (Callable[[Button, State], Awaitable[None]]): The callback function to be called on button events.
        Returns:
            str: A unique identifier for the listener.
        """
        listener_id = str(uuid.uuid4())
        self._listeners[listener_id] = callback
        return listener_id

    async def remove_listener(self, id: str):
        """
        Remove a listener by its unique identifier.
        Args:
            id (str): The unique identifier of the listener to be removed.
        """

        if id in self._listeners.keys():
            self._listeners.pop(id)
