import asyncio
import logging
from enum import Enum
from typing import Awaitable, Callable

from .base import Button, Controller, State

logger = logging.getLogger(__name__)
try:
    import evdev as _evdev
except ImportError:
    _evdev = None
    logger.warning("JoyCon control is only supported on linux")


# Joycon controller
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


class JoyCon(Controller):
    def __init__(self, max_attempts: int = 5, evdev_module=None):
        self._evdev = evdev_module or _evdev

        # ! will only work on Linux due to use of evdev
        self._max_attempts = max_attempts

        self._joy_con = None
        self._task = None
        self._listeners: dict[str, Callable[[Button, State], Awaitable[None]]] = {}

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

    async def _connect(self) -> None:
        DEVICE_NAME = ["Nintendo Switch Right Joy-Con", "Joy-Con (R)"]
        SLEEP_TIME = 1  # seconds

        attempts = 0
        while attempts < self._max_attempts:
            for path in self._evdev.list_devices():
                device = self._evdev.InputDevice(path)
                if device.name in DEVICE_NAME:
                    logger.info(f"Connected to JoyCon: {device.name} at {path}")
                    self._joy_con = device
                    return

            # * could not find a device matching the JoyCon device name
            attempts += 1
            logger.warning("JoyCon not found, retrying ...")
            await asyncio.sleep(SLEEP_TIME)

        raise RuntimeError("Failed connec to JoyCon after several attempts")

    @staticmethod
    def _get_generic_button(key: JoyConButton) -> Button | None:
        JOYCON_MAPPING = {
            JoyConButton.A: Button.PRIMARY,
            JoyConButton.B: Button.SECONDARY,
        }

        if key in JOYCON_MAPPING:
            return JOYCON_MAPPING[key]

    async def _read_events(self):
        """Main async input loop. Call once to keep reading events and dispatching to listeners."""
        if not self._joy_con:
            await self._connect()

        async for event in self._joy_con.async_read_loop():
            parsed = self._evdev.categorize(event)
            if not isinstance(parsed, self._evdev.KeyEvent):
                continue

            keycodes = (
                list(parsed.keycode)
                if isinstance(parsed.keycode, tuple)
                else [parsed.keycode]
            )

            common_keycode = set(keycodes) & set(JOYCON_BUTTONS)
            if common_keycode:
                joycon_button = JoyConButton(next(iter(common_keycode)))
                state = State(parsed.keystate)

                button = self._get_generic_button(joycon_button)
                if button is None:
                    continue

                for callback in self._listeners.values():
                    await callback(button, state)
