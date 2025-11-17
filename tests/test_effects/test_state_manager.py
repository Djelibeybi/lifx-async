"""Tests for DeviceStateManager."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.devices.multizone import MultiZoneLight
from lifx.effects.models import PreState
from lifx.effects.state_manager import DeviceStateManager


@pytest.fixture
def state_manager():
    """Create a DeviceStateManager instance."""
    return DeviceStateManager()


@pytest.fixture
def mock_light():
    """Create a mock light device."""
    light = MagicMock()
    light.serial = "d073d5123456"
    return light


@pytest.fixture
def mock_multizone_light():
    """Create a mock multizone light device."""
    light = MagicMock(spec=MultiZoneLight)
    light.serial = "d073d5abcdef"
    light.capabilities = MagicMock()
    return light


def test_state_manager_initialization(state_manager):
    """Test DeviceStateManager initialization."""
    assert isinstance(state_manager, DeviceStateManager)


def test_state_manager_repr(state_manager):
    """Test DeviceStateManager string representation."""
    assert repr(state_manager) == "DeviceStateManager()"


@pytest.mark.asyncio
async def test_capture_state_regular_light(state_manager, mock_light):
    """Test capturing state from a regular light."""
    # Setup mock responses
    mock_light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    mock_light.get_color = AsyncMock(return_value=(color, 100, 200))

    # Capture state
    prestate = await state_manager.capture_state(mock_light)

    # Verify captured state
    assert isinstance(prestate, PreState)
    assert prestate.power is True
    assert prestate.color == color
    assert prestate.zone_colors is None  # Not a multizone device


@pytest.mark.asyncio
async def test_capture_state_powered_off_light(state_manager, mock_light):
    """Test capturing state from a powered off light."""
    # Setup mock responses for powered off light
    mock_light.get_power = AsyncMock(return_value=0)
    color = HSBK(hue=0, saturation=0, brightness=0, kelvin=3500)
    mock_light.get_color = AsyncMock(return_value=(color, 0, 200))

    # Capture state
    prestate = await state_manager.capture_state(mock_light)

    # Verify captured state
    assert prestate.power is False
    assert prestate.color.brightness == 0


@pytest.mark.asyncio
async def test_capture_state_multizone_extended(state_manager, mock_multizone_light):
    """Test capturing state from multizone light with extended support."""
    # Setup mock responses
    mock_multizone_light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=180, saturation=0.8, brightness=0.7, kelvin=4000)
    mock_multizone_light.get_color = AsyncMock(return_value=(color, 100, 200))

    # Setup extended multizone
    mock_multizone_light.capabilities.has_extended_multizone = True
    mock_multizone_light.get_zone_count = AsyncMock(return_value=16)
    zone_colors = [
        HSBK(hue=i * 20, saturation=1.0, brightness=0.8, kelvin=3500) for i in range(16)
    ]
    mock_multizone_light.get_extended_color_zones = AsyncMock(return_value=zone_colors)

    # Capture state
    prestate = await state_manager.capture_state(mock_multizone_light)

    # Verify captured state
    assert prestate.power is True
    assert prestate.color == color
    assert prestate.zone_colors == zone_colors
    assert len(prestate.zone_colors) == 16
    mock_multizone_light.get_extended_color_zones.assert_called_once_with(
        start=0, end=15
    )


@pytest.mark.asyncio
async def test_capture_state_multizone_standard(state_manager, mock_multizone_light):
    """Test capturing state from multizone light without extended support."""
    # Setup mock responses
    mock_multizone_light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=240, saturation=0.9, brightness=0.6, kelvin=2700)
    mock_multizone_light.get_color = AsyncMock(return_value=(color, 100, 200))

    # Setup standard multizone
    mock_multizone_light.capabilities.has_extended_multizone = False
    mock_multizone_light.get_zone_count = AsyncMock(return_value=8)
    zone_colors = [
        HSBK(hue=i * 45, saturation=1.0, brightness=0.8, kelvin=3500) for i in range(8)
    ]
    mock_multizone_light.get_color_zones = AsyncMock(return_value=zone_colors)

    # Capture state
    prestate = await state_manager.capture_state(mock_multizone_light)

    # Verify captured state
    assert prestate.zone_colors == zone_colors
    assert len(prestate.zone_colors) == 8
    mock_multizone_light.get_color_zones.assert_called_once_with(start=0, end=7)


@pytest.mark.asyncio
async def test_capture_state_multizone_failure(state_manager, mock_multizone_light):
    """Test capturing state when zone capture fails."""
    # Setup mock responses
    mock_multizone_light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=300, saturation=0.7, brightness=0.5, kelvin=3000)
    mock_multizone_light.get_color = AsyncMock(return_value=(color, 100, 200))

    # Setup zone capture to fail
    mock_multizone_light.capabilities.has_extended_multizone = True
    mock_multizone_light.get_zone_count = AsyncMock(
        side_effect=Exception("Network error")
    )

    # Capture state should handle exception gracefully
    prestate = await state_manager.capture_state(mock_multizone_light)

    # Verify captured state (zones should be None)
    assert prestate.power is True
    assert prestate.color == color
    assert prestate.zone_colors is None


@pytest.mark.asyncio
async def test_restore_state_regular_light(state_manager, mock_light):
    """Test restoring state to a regular light."""
    # Setup mock methods
    mock_light.set_color = AsyncMock()
    mock_light.set_power = AsyncMock()

    # Create prestate
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    prestate = PreState(power=True, color=color, zone_colors=None)

    # Restore state
    await state_manager.restore_state(mock_light, prestate)

    # Verify restoration
    mock_light.set_color.assert_called_once_with(color, duration=0.0)
    mock_light.set_power.assert_called_once_with(True, duration=0.0)


@pytest.mark.asyncio
async def test_restore_state_powered_off_light(state_manager, mock_light):
    """Test restoring powered off state."""
    # Setup mock methods
    mock_light.set_color = AsyncMock()
    mock_light.set_power = AsyncMock()

    # Create powered-off prestate
    color = HSBK(hue=0, saturation=0, brightness=0, kelvin=3500)
    prestate = PreState(power=False, color=color, zone_colors=None)

    # Restore state
    await state_manager.restore_state(mock_light, prestate)

    # Verify power restored to off
    mock_light.set_power.assert_called_once_with(False, duration=0.0)


@pytest.mark.asyncio
async def test_restore_state_multizone_extended(state_manager, mock_multizone_light):
    """Test restoring state to multizone light with extended support."""
    # Setup mock methods
    mock_multizone_light.set_extended_color_zones = AsyncMock()
    mock_multizone_light.set_color = AsyncMock()
    mock_multizone_light.set_power = AsyncMock()

    # Setup extended multizone
    mock_multizone_light.capabilities.has_extended_multizone = True

    # Create multizone prestate
    color = HSBK(hue=180, saturation=0.8, brightness=0.7, kelvin=4000)
    zone_colors = [
        HSBK(hue=i * 20, saturation=1.0, brightness=0.8, kelvin=3500) for i in range(16)
    ]
    prestate = PreState(power=True, color=color, zone_colors=zone_colors)

    # Restore state
    await state_manager.restore_state(mock_multizone_light, prestate)

    # Verify zones restored
    mock_multizone_light.set_extended_color_zones.assert_called_once()
    call_kwargs = mock_multizone_light.set_extended_color_zones.call_args.kwargs
    assert call_kwargs["zone_index"] == 0
    assert call_kwargs["colors"] == zone_colors
    assert call_kwargs["duration"] == 0.0


@pytest.mark.asyncio
async def test_restore_state_multizone_standard(state_manager, mock_multizone_light):
    """Test restoring state to multizone light without extended support."""
    # Setup mock methods
    mock_multizone_light.set_color_zones = AsyncMock()
    mock_multizone_light.set_color = AsyncMock()
    mock_multizone_light.set_power = AsyncMock()

    # Setup standard multizone
    mock_multizone_light.capabilities.has_extended_multizone = False

    # Create multizone prestate with fewer zones
    color = HSBK(hue=240, saturation=0.9, brightness=0.6, kelvin=2700)
    zone_colors = [
        HSBK(hue=i * 45, saturation=1.0, brightness=0.8, kelvin=3500) for i in range(8)
    ]
    prestate = PreState(power=True, color=color, zone_colors=zone_colors)

    # Restore state
    await state_manager.restore_state(mock_multizone_light, prestate)

    # Verify zones restored individually
    assert mock_multizone_light.set_color_zones.call_count == 8


@pytest.mark.asyncio
async def test_restore_color_failure_handling(state_manager, mock_light):
    """Test restore handles color setting failures gracefully."""
    # Setup mock to fail
    mock_light.set_color = AsyncMock(side_effect=Exception("Network error"))
    mock_light.set_power = AsyncMock()

    # Create prestate
    color = HSBK(hue=60, saturation=0.5, brightness=0.4, kelvin=3200)
    prestate = PreState(power=True, color=color, zone_colors=None)

    # Restore should not raise exception
    await state_manager.restore_state(mock_light, prestate)

    # Power should still be restored despite color failure
    mock_light.set_power.assert_called_once()


@pytest.mark.asyncio
async def test_restore_power_failure_handling(state_manager, mock_light):
    """Test restore handles power setting failures gracefully."""
    # Setup mock to fail on power
    mock_light.set_color = AsyncMock()
    mock_light.set_power = AsyncMock(side_effect=Exception("Device offline"))

    # Create prestate
    color = HSBK(hue=90, saturation=0.7, brightness=0.9, kelvin=5000)
    prestate = PreState(power=True, color=color, zone_colors=None)

    # Restore should not raise exception
    await state_manager.restore_state(mock_light, prestate)

    # Color should have been restored before power failure
    mock_light.set_color.assert_called_once()


@pytest.mark.asyncio
async def test_restore_zones_failure_handling(state_manager, mock_multizone_light):
    """Test restore handles zone setting failures gracefully."""
    # Setup mock to fail on zones
    mock_multizone_light.set_extended_color_zones = AsyncMock(
        side_effect=Exception("Zone error")
    )
    mock_multizone_light.set_color = AsyncMock()
    mock_multizone_light.set_power = AsyncMock()
    mock_multizone_light.capabilities.has_extended_multizone = True

    # Create multizone prestate
    color = HSBK(hue=210, saturation=0.6, brightness=0.5, kelvin=3800)
    zone_colors = [
        HSBK(hue=i * 30, saturation=1.0, brightness=0.8, kelvin=3500) for i in range(8)
    ]
    prestate = PreState(power=True, color=color, zone_colors=zone_colors)

    # Restore should not raise exception
    await state_manager.restore_state(mock_multizone_light, prestate)

    # Color and power should still be restored despite zone failure
    mock_multizone_light.set_color.assert_called_once()
    mock_multizone_light.set_power.assert_called_once()
