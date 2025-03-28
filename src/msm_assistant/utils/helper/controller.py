import logging
import platform
import time
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import evdev
except ImportError:
    logger.warning("JoyCon control is only supported on linux")

JOYCON_DEVICE_NAMES = ["Nintendo Switch Right Joy-Con", "Joy-Con (R)"]


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
    RELEASED = 2


class JoyConError(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)


class JoyCon:
    """A class that listens for an input from a JoyCon controller and returns the input"""

    def __init__(self, max_attempts: int = 5):
        if platform.system() != "Linux":
            raise OSError("JoyCon control is only supported on Linux")
        self._max_attempts = max_attempts

        self._joy_con = None
        self._connect()

    def listen(self, state: JoyConButtonState):
        SLEEP_TIME_S = 0.1

        if not self._joy_con:
            logger.warning("Could not find a Joy-Con - attempting to reconnect")
            self._connect()

        self._flush_events(self._joy_con)
        logger.info("Started listening for Joy-Con inputs")
        valid_buttons = set(JOYCON_BUTTONS)

        while True:
            event = self._joy_con.read_one()
            if event is None:
                time.sleep(SLEEP_TIME_S)
                continue

            parsed_event = evdev.categorize(event)
            if not isinstance(parsed_event, evdev.KeyEvent):
                continue

            keycodes = (
                list(parsed_event.keycode)
                if isinstance(parsed_event.keycode, tuple)
                else [parsed_event.keycode]
            )
            if parsed_event.keystate != state.value:
                continue

            common_buttons = set(keycodes) & valid_buttons
            if common_buttons:
                button_string = next(iter(common_buttons))
                return JoyConButton(button_string)

    def _connect(self):
        SLEEP_TIME_S = 1

        attempts = 0
        while attempts < self._max_attempts:
            try:
                device_file = self._find_joycon()

                if device_file:
                    self._joy_con = evdev.InputDevice(device_file)
                    return
            except JoyConError:
                time.sleep(SLEEP_TIME_S)
                attempts += 1

        raise JoyConError(
            f"Failed to connect to a Joy-Con after {self._max_attempts} attempts"
        )

    def _find_joycon(self) -> Path | None:
        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            if dev.name in JOYCON_DEVICE_NAMES:
                logger.info(f"Using {dev.name} at: {path}")
                return Path(path)

        raise JoyConError("Could not find a Joy-Con device")

    @staticmethod
    def _flush_events(device: evdev.InputDevice):
        """Read and discard any pending events."""
        while True:
            event = device.read_one()  # non-blocking read
            if event is None:
                break


def main():
    logging.basicConfig(level=logging.INFO)

    try:
        joycon = JoyCon()
        print("Waiting for a Joy-Con button press...")
        while True:
            button = joycon.listen(JoyConButtonState.PRESSED)
            print(f"Detected Joy-Con button press: {button.name} ({button.value})")
    except OSError as e:
        print(f"Platform error: {e}")
    except JoyConError as e:
        print(f"JoyCon error: {e}")
    except KeyboardInterrupt:
        print("\nExiting gracefully.")


if __name__ == "__main__":
    main()
