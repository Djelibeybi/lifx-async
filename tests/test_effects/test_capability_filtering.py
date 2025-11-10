"""Tests for effect capability filtering."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.devices.light import Light
from lifx.effects.colorloop import EffectColorloop
from lifx.effects.conductor import Conductor
from lifx.effects.pulse import EffectPulse


@pytest.fixture
def color_light():
    """Create a mock color light."""
    light = MagicMock(spec=Light)
    light.serial = "d073d5000001"
    light.ip = "192.168.1.100"
    light.port = 56700

    # Mock capabilities with color support
    capabilities = MagicMock()
    capabilities.has_color = True
    light.capabilities = capabilities
    light._ensure_capabilities = AsyncMock()

    # Mock methods
    light.get_power = AsyncMock(return_value=True)
    light.get_color = AsyncMock(
        return_value=(
            MagicMock(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),
            0,
            0,
        )
    )
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()

    return light


@pytest.fixture
def white_light():
    """Create a mock white-only light (no color capability)."""
    light = MagicMock(spec=Light)
    light.serial = "d073d5000002"
    light.ip = "192.168.1.101"
    light.port = 56700

    # Mock capabilities without color support
    capabilities = MagicMock()
    capabilities.has_color = False
    light.capabilities = capabilities
    light._ensure_capabilities = AsyncMock()

    # Mock methods
    light.get_power = AsyncMock(return_value=True)
    light.get_color = AsyncMock(
        return_value=(
            MagicMock(hue=0, saturation=0.0, brightness=0.8, kelvin=3500),
            0,
            0,
        )
    )
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()

    return light


async def test_colorloop_filters_non_color_lights(color_light, white_light):
    """Test that colorloop filters out non-color lights."""
    conductor = Conductor()
    effect = EffectColorloop(period=60, change=20)

    # Start effect with mixed lights
    participants = [color_light, white_light]
    await conductor.start(effect, participants)

    # Only color light should be in running effects
    assert color_light.serial in conductor._running
    assert white_light.serial not in conductor._running

    # Clean up
    await conductor.stop([color_light])


async def test_pulse_does_not_filter_lights(color_light, white_light):
    """Test that pulse effect doesn't filter lights (no color requirement)."""
    conductor = Conductor()
    effect = EffectPulse(mode="breathe", cycles=1, period=1.0)

    # Start effect with mixed lights - pulse accepts all
    participants = [color_light, white_light]
    await conductor.start(effect, participants)

    # Both lights should be running (pulse doesn't require color)
    assert color_light.serial in conductor._running
    assert white_light.serial in conductor._running

    # Clean up
    await conductor.stop(participants)


async def test_colorloop_with_all_white_lights_warning(white_light, caplog):
    """Test that colorloop with only white lights logs warning and doesn't run."""
    conductor = Conductor()
    effect = EffectColorloop(period=60, change=20)

    # Start effect with only white light
    participants = [white_light]
    await conductor.start(effect, participants)

    # Effect should not run - no lights in registry
    assert white_light.serial not in conductor._running

    # Should have logged a warning about no compatible lights
    assert any(
        record.levelname == "WARNING"
        and "'compatible_participants': 0" in record.message
        for record in caplog.records
    )


async def test_colorloop_with_all_color_lights(color_light):
    """Test that colorloop with all color lights runs normally."""
    conductor = Conductor()
    effect = EffectColorloop(period=60, change=20)

    # Create a second color light
    color_light2 = MagicMock(spec=Light)
    color_light2.serial = "d073d5000003"
    color_light2.ip = "192.168.1.102"
    color_light2.port = 56700
    capabilities = MagicMock()
    capabilities.has_color = True
    color_light2.capabilities = capabilities
    color_light2._ensure_capabilities = AsyncMock()
    color_light2.get_power = AsyncMock(return_value=True)
    color_light2.get_color = AsyncMock(
        return_value=(
            MagicMock(hue=240, saturation=1.0, brightness=0.8, kelvin=3500),
            0,
            0,
        )
    )
    color_light2.set_color = AsyncMock()
    color_light2.set_power = AsyncMock()

    # Start effect with all color lights
    participants = [color_light, color_light2]
    await conductor.start(effect, participants)

    # Both lights should be running
    assert color_light.serial in conductor._running
    assert color_light2.serial in conductor._running

    # Clean up
    await conductor.stop(participants)


async def test_colorloop_with_light_without_cached_capabilities():
    """Test colorloop compatibility check when light capabilities need to be loaded."""
    conductor = Conductor()
    effect = EffectColorloop(period=60, change=20)

    # Create light without cached capabilities
    light = MagicMock(spec=Light)
    light.serial = "d073d5000004"
    light.ip = "192.168.1.103"
    light.port = 56700

    # Initially no capabilities cached
    light.capabilities = None

    # Mock _ensure_capabilities to set capabilities
    async def ensure_caps():
        caps = MagicMock()
        caps.has_color = True
        light.capabilities = caps

    light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)
    light.get_power = AsyncMock(return_value=True)
    light.get_color = AsyncMock(
        return_value=(
            MagicMock(hue=180, saturation=1.0, brightness=0.8, kelvin=3500),
            0,
            0,
        )
    )
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()

    # Start effect - should load capabilities and accept light
    await conductor.start(effect, [light])

    # Capabilities should have been loaded
    light._ensure_capabilities.assert_called_once()

    # Light should be running
    assert light.serial in conductor._running

    # Clean up
    await conductor.stop([light])
