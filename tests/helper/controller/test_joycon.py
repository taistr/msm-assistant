import asyncio
from unittest.mock import AsyncMock

import pytest

from msm_assistant.utils.helper.controller.joycon import (Button, JoyCon,
                                                          JoyConButton, State)


# Fake evdev modules for testing
class FakeEvdev:
    class KeyEvent:
        pass

    @staticmethod
    def list_devices():
        # Simulate finding one device
        return ["/dev/fake"]

    class InputDevice:
        def __init__(self, path):
            # This name matches DEVICE_NAME in _connect()
            self.name = "Nintendo Switch Right Joy-Con"

        async def async_read_loop(self):
            # Yield a single event then exit
            class Event(FakeEvdev.KeyEvent):
                keycode = "BTN_EAST"
                keystate = 1

            yield Event()

    @staticmethod
    def categorize(event):
        # Return the event directly
        return event


# Simulate no devices found
class FakeEvdevNoDevices:
    @staticmethod
    def list_devices():
        return []

    class InputDevice:
        def __init__(self, path):
            pass

    @staticmethod
    def categorize(event):
        return event

    class KeyEvent:
        pass


# --- Tests for pure method ---
@pytest.mark.asyncio
async def test_get_generic_button():
    # Direct mapping
    assert JoyCon._get_generic_button(JoyConButton.A) == Button.PRIMARY
    assert JoyCon._get_generic_button(JoyConButton.B) == Button.SECONDARY
    # Unmapped key returns None
    assert JoyCon._get_generic_button(JoyConButton.X) is None


# --- Tests for _connect() logic ---
@pytest.mark.asyncio
async def test_connect_success():
    # Inject our fake evdev so no real hardware is needed
    joycon = JoyCon(evdev_module=FakeEvdev)
    await joycon._connect()
    # Should have attached the fake device
    assert isinstance(joycon._joy_con, FakeEvdev.InputDevice)
    assert joycon._joy_con.name == "Nintendo Switch Right Joy-Con"


@pytest.mark.asyncio
async def test_connect_failure():
    # max_attempts=0 makes _connect() raise immediately
    joycon = JoyCon(max_attempts=0, evdev_module=FakeEvdevNoDevices)
    with pytest.raises(RuntimeError):
        await joycon._connect()


# --- Tests for listen()/stop() task management ---
@pytest.mark.asyncio
async def test_listen_and_stop():
    joycon = JoyCon(evdev_module=FakeEvdev)
    # Override the actual event loop to avoid side effects
    joycon._read_events = AsyncMock()

    assert joycon._task is None
    await joycon.listen()
    # A task should be scheduled
    assert isinstance(joycon._task, asyncio.Task)

    # Stopping should cancel and clear the task
    await joycon.stop()
    assert joycon._task is None


# --- Test full event loop once triggers listener ---
@pytest.mark.asyncio
async def test_read_events_triggers_listener():
    calls = []

    async def listener(button, state):
        calls.append((button, state))

    joycon = JoyCon(evdev_module=FakeEvdev)
    listener_id = await joycon.add_listener(listener)

    # Run one iteration of _read_events()
    await joycon._read_events()

    # Should have been called exactly once with Button.PRIMARY and State.PRESSED
    assert calls == [(Button.PRIMARY, State.PRESSED)]

    # Clean up listener
    await joycon.remove_listener(listener_id)
    assert joycon._listeners == {}
