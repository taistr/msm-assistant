import asyncio
import logging
import uuid
from enum import Enum
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

try:
    import evdev
except ImportError:
    logger.warning("JoyCon control is only supported on linux")


class JoyConButton(Enum):
    A = "BTN_EAST"
    B = "BTN_SOUTH"
    X = "BTN_NORTH"
    Y = "BTN_WEST"
    START = "BTN_START"
    HOME = "BTN_MODE"
    R = "BTN_TR"
    ZR = "BTN_TR2"
    SL = "BTN_TL"
    SR = "BTN_TL2"


JOYCON_BUTTONS = [member.value for member in JoyConButton]


class JoyConButtonState(Enum):
    PRESSED = 1
    RELEASED = 0


class JoyCon:
    def __init__(self, max_attempts: int = 5):
        # ! will only work on Linux due to use of evdev
        self._device_name = ["Nintendo Switch Right Joy-Con", "Joy-Con (R)"]
        self._max_attempts = max_attempts

        self._joy_con = None
        self._task = None
        self._listeners: dict[
            str, Callable[[JoyConButton, JoyConButtonState], Awaitable[None]]
        ] = {}

    async def _connect(self) -> None:
        SLEEP_TIME = 1  # seconds

        attempts = 0
        while attempts < self._max_attempts:
            for path in evdev.list_devices():
                device = evdev.InputDevice(path)
                if device.name in self._device_name:
                    logger.info(f"Connected to JoyCon: {device.name} at {path}")
                    self._joy_con = device
                    return

            # * could not find a device matching the JoyCon device name
            attempts += 1
            logger.warning("JoyCon not found, retrying ...")
            await asyncio.sleep(SLEEP_TIME)

        raise RuntimeError("Failed connec to JoyCon after several attempts")

    async def listen(self):
        self._task = asyncio.create_task(self._read_events())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None

    async def add_listener(
        self, callback: Callable[[JoyConButton, JoyConButtonState], Awaitable[None]]
    ) -> str:
        listener_id = str(uuid.uuid4())
        self._listeners[listener_id] = callback
        return listener_id

    async def remove_listener(self, id: str):
        if id in self._listeners.keys():
            self._listeners.pop(id)

    async def _read_events(self):
        """Main async input loop. Call once to keep reading events and dispatching to listeners."""
        if not self._joy_con:
            await self._connect()

        async for event in self._joy_con.async_read_loop():
            parsed = evdev.categorize(event)
            if not isinstance(parsed, evdev.KeyEvent):
                continue

            keycodes = (
                list(parsed.keycode)
                if isinstance(parsed.keycode, tuple)
                else [parsed.keycode]
            )

            common_keycode = set(keycodes) & set(JOYCON_BUTTONS)
            if common_keycode:
                button = JoyConButton(next(iter(common_keycode)))
                state = JoyConButtonState(parsed.keystate)

                for callback in self._listeners.values():
                    await callback(button, state)


async def joycon_listener(button: JoyConButton, state: JoyConButtonState):
    """Example listener that prints the received button and state."""
    print(f"JoyCon event: {button.name} - {state.name}")


async def main():
    # Create JoyCon instance (this will start connecting asynchronously)
    joycon = JoyCon(max_attempts=5)

    print("JoyCon listen starting. Waiting for input events... (Press Ctrl+C to exit)")
    try:
        await joycon.listen()

        # Register our listener callback
        while True:
            listener_id = await joycon.add_listener(joycon_listener)
            print("Added listener")

            await asyncio.sleep(5)

            await joycon.remove_listener(listener_id)
            print("Removed listener")

            await asyncio.sleep(5)

    except KeyboardInterrupt:
        print("Keyboard interrupt detected.")
    finally:
        # Ensure the JoyCon listener is stopped before exiting
        await joycon.stop()
        print("JoyCon listener stopped. Exiting")


if __name__ == "__main__":
    asyncio.run(main())
