from unittest.mock import AsyncMock, MagicMock

import pytest

from msm_assistant.utils.helper.controller.base import Button, State
from msm_assistant.utils.helper.controller.keyboard import Keyboard


@pytest.mark.asyncio
async def test_keyboard_listen():
    """
    Test the initialization of the Keyboard class.
    """
    # Arrange
    keyboard = Keyboard()
    keyboard._keyboard = MagicMock()

    # Act
    await keyboard.listen()

    # Assert
    keyboard._keyboard.start.assert_called_once()


@pytest.mark.asyncio
async def test_keyboard_stop():
    """
    Test the stop method of the Keyboard class.
    """
    # Arrange
    keyboard = Keyboard()
    keyboard._keyboard = MagicMock()

    # Act
    await keyboard.stop()

    # Assert
    keyboard._keyboard.stop.assert_called_once()


@pytest.mark.asyncio
async def test_keyboard_get_button():
    """
    Test the _get_button method to ensure it returns the correct Button enum.
    """
    # Arrange
    keyboard = Keyboard()

    # Act
    button_primary = keyboard._get_button(MagicMock(char="u"))
    button_secondary = keyboard._get_button(MagicMock(char="i"))
    button_special = keyboard._get_button(MagicMock(name="k"))

    # Assert
    assert button_primary == Button.PRIMARY
    assert button_secondary == Button.SECONDARY
    assert button_special is None


@pytest.mark.asyncio
async def test_keyboard_triggers_callback():
    """
    Test that the keyboard event triggers the correct callback.
    """
    # Arrange
    keyboard = Keyboard()

    callback = AsyncMock()
    await keyboard.add_listener(callback)

    # Act
    keyboard._on_press(MagicMock(char="u"))
    keyboard._on_release(MagicMock(char="u"))
    keyboard._on_press(MagicMock(char="i"))
    keyboard._on_release(MagicMock(char="i"))

    # Assert
    callback.assert_any_call(Button.PRIMARY, State.PRESSED)
    callback.assert_any_call(Button.PRIMARY, State.RELEASED)
    callback.assert_any_call(Button.SECONDARY, State.PRESSED)
    callback.assert_any_call(Button.SECONDARY, State.RELEASED)


@pytest.mark.asyncio
async def test_keyboard_doesnt_trigger_callback():
    """
    Test that the keyboard event does not trigger the callback for unrecognized keys.
    """
    # Arrange
    keyboard = Keyboard()

    callback = AsyncMock()
    await keyboard.add_listener(callback)

    # Act
    keyboard._on_press(MagicMock(char="x"))
    keyboard._on_release(MagicMock(char="x"))

    # Assert
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_keyboard_add_listener():
    """
    Test adding a listener to the keyboard.
    """
    # Arrange
    keyboard = Keyboard()

    callback = AsyncMock()

    # Act
    listener_id = await keyboard.add_listener(callback)

    # Assert
    assert listener_id in keyboard._listeners
    assert keyboard._listeners[listener_id] == callback


@pytest.mark.asyncio
async def test_keyboard_remove_listener():
    """
    Test removing a listener from the keyboard.
    """
    # Arrange
    keyboard = Keyboard()

    callback = AsyncMock()
    listener_id = await keyboard.add_listener(callback)

    # Act
    await keyboard.remove_listener(listener_id)

    # Assert
    assert listener_id not in keyboard._listeners
