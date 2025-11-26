"""Tests for EffectColorloop."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.const import KELVIN_NEUTRAL
from lifx.effects.colorloop import EffectColorloop


def test_colorloop_default_parameters():
    """Test EffectColorloop with default parameters."""
    effect = EffectColorloop()

    assert effect.name == "colorloop"
    assert effect.period == 60
    assert effect.change == 20
    assert effect.spread == 30
    assert effect.brightness is None
    assert effect.saturation_min == 0.8
    assert effect.saturation_max == 1.0
    assert effect.transition is None
    assert effect.synchronized is False
    assert effect.power_on is True


def test_colorloop_custom_parameters():
    """Test EffectColorloop with custom parameters."""
    effect = EffectColorloop(
        period=30, change=15, spread=45, brightness=0.7, saturation_min=0.9
    )

    assert effect.period == 30
    assert effect.change == 15
    assert effect.spread == 45
    assert effect.brightness == 0.7
    assert effect.saturation_min == 0.9


def test_colorloop_with_transition():
    """Test EffectColorloop with custom transition time."""
    effect = EffectColorloop(transition=2.5)

    assert effect.transition == 2.5


def test_colorloop_invalid_period():
    """Test EffectColorloop with invalid period raises ValueError."""
    with pytest.raises(ValueError, match="Period must be positive"):
        EffectColorloop(period=0)


def test_colorloop_invalid_change():
    """Test EffectColorloop with invalid change raises ValueError."""
    with pytest.raises(ValueError, match="Change must be 0-360"):
        EffectColorloop(change=400)


def test_colorloop_invalid_spread():
    """Test EffectColorloop with invalid spread raises ValueError."""
    with pytest.raises(ValueError, match="Spread must be 0-360"):
        EffectColorloop(spread=400)


def test_colorloop_invalid_brightness():
    """Test EffectColorloop with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be 0.0-1.0"):
        EffectColorloop(brightness=1.5)


def test_colorloop_invalid_saturation_min():
    """Test EffectColorloop with invalid saturation_min raises ValueError."""
    with pytest.raises(ValueError, match="Saturation_min must be 0.0-1.0"):
        EffectColorloop(saturation_min=1.5)


def test_colorloop_invalid_saturation_max():
    """Test EffectColorloop with invalid saturation_max raises ValueError."""
    with pytest.raises(ValueError, match="Saturation_max must be 0.0-1.0"):
        EffectColorloop(saturation_max=1.5)


def test_colorloop_saturation_min_greater_than_max():
    """Test EffectColorloop with saturation_min > saturation_max raises ValueError."""
    with pytest.raises(ValueError, match="Saturation_min .* must be <="):
        EffectColorloop(saturation_min=0.9, saturation_max=0.5)


def test_colorloop_invalid_transition():
    """Test EffectColorloop with invalid transition raises ValueError."""
    with pytest.raises(ValueError, match="Transition must be non-negative"):
        EffectColorloop(transition=-1.0)


def test_colorloop_synchronized_mode():
    """Test EffectColorloop with synchronized=True."""
    effect = EffectColorloop(synchronized=True)

    assert effect.synchronized is True
    assert effect.period == 60
    assert effect.change == 20


def test_colorloop_synchronized_with_custom_params():
    """Test EffectColorloop with synchronized mode and custom parameters."""
    effect = EffectColorloop(
        period=30, change=15, brightness=0.8, synchronized=True, transition=2.0
    )

    assert effect.synchronized is True
    assert effect.period == 30
    assert effect.change == 15
    assert effect.brightness == 0.8
    assert effect.transition == 2.0


def test_colorloop_inherit_prestate():
    """Test EffectColorloop inherit_prestate method."""
    effect1 = EffectColorloop()
    effect2 = EffectColorloop()
    other_effect = object()

    # Should inherit from another EffectColorloop
    assert effect1.inherit_prestate(effect2) is True

    # Should not inherit from other effect types
    assert effect1.inherit_prestate(other_effect) is False  # type: ignore


def test_colorloop_repr():
    """Test EffectColorloop string representation."""
    effect = EffectColorloop(period=30, change=15, spread=45, brightness=0.7)
    repr_str = repr(effect)

    assert "EffectColorloop" in repr_str
    assert "period=30" in repr_str
    assert "change=15" in repr_str
    assert "spread=45" in repr_str
    assert "brightness=0.7" in repr_str
    assert "synchronized=False" in repr_str


def test_colorloop_repr_synchronized():
    """Test EffectColorloop string representation with synchronized mode."""
    effect = EffectColorloop(synchronized=True)
    repr_str = repr(effect)

    assert "EffectColorloop" in repr_str
    assert "synchronized=True" in repr_str


@pytest.mark.asyncio
async def test_colorloop_stop_method():
    """Test colorloop stop() method."""
    effect = EffectColorloop(period=0.2, change=30)

    # Create mock light
    light = MagicMock()
    light.serial = "d073d5test789"
    light.capabilities = MagicMock()
    light.capabilities.has_color = True
    light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    light.color = (color, 100)
    light.set_color = AsyncMock()

    # Set participants
    effect.participants = [light]
    effect._running = True

    # Run async_play in background
    play_task = asyncio.create_task(effect.async_play())

    # Let it run briefly
    await asyncio.sleep(0.05)

    # Stop the effect
    effect.stop()

    # Wait for task to complete
    await asyncio.wait_for(play_task, timeout=1.0)

    # Verify stop flags are set
    assert not effect._running
    assert effect._stop_event.is_set()


@pytest.mark.asyncio
async def test_colorloop_synchronized_with_fixed_brightness():
    """Test colorloop synchronized mode with fixed brightness."""
    effect = EffectColorloop(period=0.2, change=30, synchronized=True, brightness=0.5)

    # Create mock lights
    lights = []
    for i in range(2):
        light = MagicMock()
        light.serial = f"d073d5sync{i}"
        light.capabilities = MagicMock()
        light.capabilities.has_color = True
        light.get_power = AsyncMock(return_value=True)
        color = HSBK(hue=i * 60, saturation=1.0, brightness=0.8, kelvin=3500)
        light.color = (color, 100)
        light.set_color = AsyncMock()
        lights.append(light)

    effect.participants = lights
    effect._running = True

    # Run one iteration
    play_task = asyncio.create_task(effect.async_play())

    await asyncio.sleep(0.05)
    effect.stop()
    await asyncio.wait_for(play_task, timeout=1.0)

    # Verify set_color was called
    assert lights[0].set_color.called


@pytest.mark.asyncio
async def test_colorloop_synchronized_with_fixed_transition():
    """Test colorloop synchronized mode with fixed transition time."""
    effect = EffectColorloop(period=0.2, change=30, synchronized=True, transition=0.05)

    # Create mock lights
    lights = []
    for i in range(2):
        light = MagicMock()
        light.serial = f"d073d5trans{i}"
        light.capabilities = MagicMock()
        light.capabilities.has_color = True
        light.get_power = AsyncMock(return_value=True)
        color = HSBK(hue=i * 60, saturation=1.0, brightness=0.8, kelvin=3500)
        light.color = (color, 100)
        light.set_color = AsyncMock()
        lights.append(light)

    effect.participants = lights
    effect._running = True

    # Run one iteration
    play_task = asyncio.create_task(effect.async_play())

    await asyncio.sleep(0.05)
    effect.stop()
    await asyncio.wait_for(play_task, timeout=1.0)

    # Verify set_color was called with transition time
    assert lights[0].set_color.called


@pytest.mark.asyncio
async def test_colorloop_synchronized_exception_handling():
    """Test colorloop synchronized mode handles exceptions gracefully."""
    effect = EffectColorloop(period=0.2, change=30, synchronized=True)

    # Create mock lights where one fails
    lights = []
    for i in range(2):
        light = MagicMock()
        light.serial = f"d073d5fail{i}"
        light.capabilities = MagicMock()
        light.capabilities.has_color = True
        light.get_power = AsyncMock(return_value=True)
        color = HSBK(hue=i * 60, saturation=1.0, brightness=0.8, kelvin=3500)
        light.color = (color, 100)
        if i == 0:
            light.set_color = AsyncMock(side_effect=Exception("Device offline"))
        else:
            light.set_color = AsyncMock()
        lights.append(light)

    effect.participants = lights
    effect._running = True

    # Should not raise exception
    play_task = asyncio.create_task(effect.async_play())

    await asyncio.sleep(0.05)
    effect.stop()
    await asyncio.wait_for(play_task, timeout=1.0)


@pytest.mark.asyncio
async def test_colorloop_spread_with_fixed_transition():
    """Test colorloop spread mode with fixed transition time."""
    effect = EffectColorloop(period=0.2, change=30, transition=0.05)

    # Create mock lights
    lights = []
    for i in range(2):
        light = MagicMock()
        light.serial = f"d073d5spread{i}"
        light.capabilities = MagicMock()
        light.capabilities.has_color = True
        light.get_power = AsyncMock(return_value=True)
        color = HSBK(hue=i * 60, saturation=1.0, brightness=0.8, kelvin=3500)
        light.color = (color, 100)
        light.set_color = AsyncMock()
        lights.append(light)

    effect.participants = lights
    effect._running = True

    # Run one iteration
    play_task = asyncio.create_task(effect.async_play())

    await asyncio.sleep(0.05)
    effect.stop()
    await asyncio.wait_for(play_task, timeout=1.0)

    # Verify set_color was called
    assert lights[0].set_color.called


@pytest.mark.asyncio
async def test_colorloop_spread_with_fixed_brightness():
    """Test colorloop spread mode with fixed brightness.

    This covers line 288 in _update_spread where self.brightness is not None
    and we use the fixed brightness value.
    """
    effect = EffectColorloop(period=0.2, change=30, brightness=0.7, synchronized=False)

    # Create mock lights
    lights = []
    for i in range(2):
        light = MagicMock()
        light.serial = f"d073d5fixbr{i}"
        light.capabilities = MagicMock()
        light.capabilities.has_color = True
        light.get_power = AsyncMock(return_value=True)
        color = HSBK(hue=i * 60, saturation=1.0, brightness=0.5, kelvin=3500)
        light.color = (color, 100)
        light.set_color = AsyncMock()
        lights.append(light)

    effect.participants = lights
    effect._running = True

    # Run one iteration
    play_task = asyncio.create_task(effect.async_play())

    await asyncio.sleep(0.05)
    effect.stop()
    await asyncio.wait_for(play_task, timeout=1.0)

    # Verify set_color was called with the fixed brightness
    assert lights[0].set_color.called


@pytest.mark.asyncio
async def test_colorloop_spread_exception_handling():
    """Test colorloop spread mode handles exceptions gracefully."""
    effect = EffectColorloop(period=0.2, change=30)

    # Create mock lights where one fails
    lights = []
    for i in range(2):
        light = MagicMock()
        light.serial = f"d073d5spread_err{i}"
        light.capabilities = MagicMock()
        light.capabilities.has_color = True
        light.get_power = AsyncMock(return_value=True)
        color = HSBK(hue=i * 60, saturation=1.0, brightness=0.8, kelvin=3500)
        light.color = (color, 100)
        if i == 0:
            light.set_color = AsyncMock(side_effect=Exception("Network error"))
        else:
            light.set_color = AsyncMock()
        lights.append(light)

    effect.participants = lights
    effect._running = True

    # Should not raise exception
    play_task = asyncio.create_task(effect.async_play())

    await asyncio.sleep(0.05)
    effect.stop()
    await asyncio.wait_for(play_task, timeout=1.0)


@pytest.mark.asyncio
async def test_colorloop_from_poweroff_with_custom_brightness():
    """Test from_poweroff_hsbk with custom brightness specified."""
    effect = EffectColorloop(brightness=0.6)

    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    # Should return random hue with custom brightness
    assert 0 <= result.hue <= 360
    assert result.brightness == 0.6
    assert result.kelvin == KELVIN_NEUTRAL


@pytest.mark.asyncio
async def test_colorloop_spread_with_brightness_none():
    """Test colorloop spread mode with brightness=None (uses initial brightness).

    This covers the else branch in _update_spread where self.brightness is None
    and we use initial_colors brightness instead.
    """
    effect = EffectColorloop(period=0.2, change=30, brightness=None)

    # Create mock lights
    lights = []
    for i in range(2):
        light = MagicMock()
        light.serial = f"d073d5bright{i}"
        light.capabilities = MagicMock()
        light.capabilities.has_color = True
        light.get_power = AsyncMock(return_value=True)
        # Each light has different brightness
        color = HSBK(hue=i * 60, saturation=1.0, brightness=0.5 + i * 0.2, kelvin=3500)
        light.color = (color, 100)
        light.set_color = AsyncMock()
        lights.append(light)

    effect.participants = lights
    effect._running = True

    # Run one iteration
    play_task = asyncio.create_task(effect.async_play())

    await asyncio.sleep(0.05)
    effect.stop()
    await asyncio.wait_for(play_task, timeout=1.0)

    # Verify set_color was called (using initial brightness)
    assert lights[0].set_color.called


@pytest.mark.asyncio
async def test_colorloop_is_light_compatible_with_none_capabilities():
    """Test is_light_compatible when light.capabilities is None.

    This covers the branch where capabilities need to be loaded first.
    """
    effect = EffectColorloop()

    light = MagicMock()
    light.capabilities = None
    light._ensure_capabilities = AsyncMock()

    # After ensure_capabilities is called, capabilities should be set
    async def set_capabilities():
        light.capabilities = MagicMock()
        light.capabilities.has_color = True

    light._ensure_capabilities.side_effect = set_capabilities

    result = await effect.is_light_compatible(light)

    # Should have called _ensure_capabilities
    light._ensure_capabilities.assert_called_once()
    assert result is True


@pytest.mark.asyncio
async def test_colorloop_is_light_compatible_capabilities_still_none():
    """Test is_light_compatible when capabilities remain None after loading."""
    effect = EffectColorloop()

    light = MagicMock()
    light.capabilities = None
    light._ensure_capabilities = AsyncMock()
    # Capabilities remain None after ensure_capabilities

    result = await effect.is_light_compatible(light)

    # Should return False when capabilities is None
    assert result is False


@pytest.mark.asyncio
async def test_colorloop_is_light_compatible_capabilities_already_loaded():
    """Test is_light_compatible when capabilities are already loaded.

    This covers the branch 409->413 where capabilities is not None,
    so we skip the _ensure_capabilities() call.
    """
    effect = EffectColorloop()

    light = MagicMock()
    # Capabilities already loaded (not None)
    light.capabilities = MagicMock()
    light.capabilities.has_color = True
    light._ensure_capabilities = AsyncMock()

    result = await effect.is_light_compatible(light)

    # Should NOT call _ensure_capabilities since capabilities is already set
    light._ensure_capabilities.assert_not_called()
    assert result is True


@pytest.mark.asyncio
async def test_colorloop_is_light_compatible_no_color_support():
    """Test is_light_compatible when light doesn't support color."""
    effect = EffectColorloop()

    light = MagicMock()
    light.capabilities = MagicMock()
    light.capabilities.has_color = False

    result = await effect.is_light_compatible(light)

    assert result is False


@pytest.mark.asyncio
async def test_colorloop_stop_before_loop_starts():
    """Test colorloop when stop() is called during initialization.

    This covers the branch where the while loop condition is False at the start
    because stop_event was set during _get_initial_colors().
    """
    effect = EffectColorloop(period=0.2, change=30)

    # Create mock light with slow get_color
    light = MagicMock()
    light.serial = "d073d5slow1"
    light.capabilities = MagicMock()
    light.capabilities.has_color = True
    light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    light.color = (color, 100)
    light.set_color = AsyncMock()

    effect.participants = [light]

    # Start the play task
    play_task = asyncio.create_task(effect.async_play())

    # Stop immediately (before the while loop can run)
    await asyncio.sleep(0)  # Yield to let play_task start
    effect.stop()

    # Wait for task to complete
    await asyncio.wait_for(play_task, timeout=1.0)

    # Verify effect stopped
    assert not effect._running
    assert effect._stop_event.is_set()
