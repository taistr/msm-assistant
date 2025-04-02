from abc import ABC, abstractmethod


class Tool(ABC):
    """Base class for all tools."""

    @classmethod
    @abstractmethod
    def name() -> str:
        """Get the name of the tool."""
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    async def init():
        """Initialize the tool."""
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    async def execute(self, args: dict) -> dict:
        """Execute the tool with the given arguments."""
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    def get_definition(self) -> dict:
        """Get information about the tool."""
        raise NotImplementedError("Subclasses must implement this method.")
