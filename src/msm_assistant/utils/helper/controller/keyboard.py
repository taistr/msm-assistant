import asyncio
from typing import Awaitable, Callable

from pynput import keyboard

from msm_assistant.utils.helper.controller.base import (Button, Controller,
                                                        State)


class Keyboard(Controller):
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
        self._keyboard.start()

    async def stop(self):
        self._keyboard.stop()

    @staticmethod
    def _get_button(key: keyboard.Key) -> Button | None:
        KEYBOARD_MAPPING = {
            "u": Button.PRIMARY,
            "i": Button.SECONDARY,
        }

        if hasattr(key, "char") and key.char in KEYBOARD_MAPPING:
            return KEYBOARD_MAPPING[key.char]
        elif key in KEYBOARD_MAPPING:  # * special key
            return KEYBOARD_MAPPING[key]

    def _on_press(self, key: keyboard.Key) -> bool:
        button = self._get_button(key)
        if button is None:
            return True

        for callback in self._listeners.values():
            asyncio.run_coroutine_threadsafe(
                callback(button, State.PRESSED), self._loop
            )

    def _on_release(self, key: keyboard.Key) -> bool:
        button = self._get_button(key)
        if button is None:
            return True

        for callback in self._listeners.values():
            asyncio.run_coroutine_threadsafe(
                callback(button, State.RELEASED), self._loop
            )


async def main():
    async def keyboard_listener(button: Button, state: State):
        print(f"Keyboard event: {button} - {state.name}")

    # Create Keyboard instance
    keyboard_controller = Keyboard()

    print(
        "Keyboard listen starting. Waiting for input events... (Press Ctrl+C to exit)"
    )
    try:
        await keyboard_controller.listen()

        # Register our listener callback; assuming these methods exist on your Controller base class.
        while True:
            listener_id = await keyboard_controller.add_listener(keyboard_listener)
            print("Added keyboard listener")

            await asyncio.sleep(5)

            await keyboard_controller.remove_listener(listener_id)
            print("Removed keyboard listener")

            await asyncio.sleep(5)

    except KeyboardInterrupt:
        print("Keyboard interrupt detected.")
    finally:
        await keyboard_controller.stop()
        print("Keyboard listener stopped. Exiting")


if __name__ == "__main__":
    asyncio.run(main())
