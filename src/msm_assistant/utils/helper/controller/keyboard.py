import asyncio
from typing import Awaitable, Callable

from pynput import keyboard

from msm_assistant.utils.helper.controller.base import (Button, Controller,
                                                        State)


class Keyboard(Controller):
    """
    Keyboard controller to handle keyboard events.
    This class listens for keyboard events and triggers the appropriate
    callbacks based on the key pressed or released.
    """

    def __init__(self):
        self._loop = asyncio.get_event_loop()
        self._keyboard = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listeners: dict[
            keyboard.Key, Callable[[Button, State], Awaitable[None]]
        ] = {}

    async def listen(self):
        """
        Start listening to keyboard events.
        """
        self._keyboard.start()

    async def stop(self):
        """
        Stop listening to keyboard events.
        """
        self._keyboard.stop()

    @staticmethod
    def _get_button(key: keyboard.Key) -> Button | None:
        """
        Map the key to a Button enum.

        Args:
            key (keyboard.Key): The key pressed or released.

        Returns:
            The corresponding Button enum or None if not mapped.
        """
        KEYBOARD_MAPPING = {
            "u": Button.PRIMARY,
            "i": Button.SECONDARY,
        }

        if hasattr(key, "char") and key.char in KEYBOARD_MAPPING:
            return KEYBOARD_MAPPING[key.char]
        elif key in KEYBOARD_MAPPING:  # * special key
            return KEYBOARD_MAPPING[key]

    def _on_press(self, key: keyboard.Key) -> bool:
        """
        Handle key press events.

        Args:
            key (keyboard.Key): The key pressed.

        Returns:
            bool: True to continue listening, False to stop.
        """
        button = self._get_button(key)
        if button is None:
            return True

        for callback in self._listeners.values():
            asyncio.run_coroutine_threadsafe(
                callback(button, State.PRESSED), self._loop
            )

    def _on_release(self, key: keyboard.Key) -> bool:
        """
        Handle key release events.

        Args:
            key (keyboard.Key): The key released.

        Returns:
            bool: True to continue listening, False to stop.
        """
        button = self._get_button(key)
        if button is None:
            return True

        for callback in self._listeners.values():
            asyncio.run_coroutine_threadsafe(
                callback(button, State.RELEASED), self._loop
            )
