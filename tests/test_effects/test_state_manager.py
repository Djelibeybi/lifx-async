"""Tests for DeviceStateManager."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.devices.multizone import MultiZoneLight
from lifx.effects.models import PreState
from lifx.effects.state_manager import DeviceStateManager
from lifx.exceptions import LifxTimeoutError
from lifx.protocol.protocol_types import MultiZoneApplicationRequest


@pytest.fixture
def state_manager() -> DeviceStateManager:
    """Create a DeviceStateManager instance."""
    return DeviceStateManager()


@pytest.fixture
def mock_light() -> MagicMock:
    """Create a mock light device."""
    light = MagicMock()
    light.serial = "d073d5123456"
    return light


@pytest.fixture
def mock_multizone_light() -> MagicMock:
    """Create a mock multizone light device."""
    light = MagicMock(spec=MultiZoneLight)
    light.serial = "d073d5abcdef"
    light.capabilities = MagicMock()
    return light


def test_state_manager_initialization(state_manager) -> None:
    """Test DeviceStateManager initialization."""
    assert isinstance(state_manager, DeviceStateManager)


def test_state_manager_repr(state_manager) -> None:
    """Test DeviceStateManager string representation."""
    assert repr(state_manager) == "DeviceStateManager()"


@pytest.mark.asyncio
async def test_capture_state_regular_light(state_manager, mock_light) -> None:
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
async def test_capture_state_powered_off_light(state_manager, mock_light) -> None:
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
async def test_capture_state_multizone_extended(
    state_manager, mock_multizone_light
) -> None:
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
async def test_capture_state_multizone_standard(
    state_manager, mock_multizone_light
) -> None:
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
async def test_capture_state_multizone_failure(
    state_manager, mock_multizone_light
) -> None:
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
async def test_restore_state_regular_light(state_manager, mock_light) -> None:
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
async def test_restore_state_powered_off_light(state_manager, mock_light) -> None:
    """Test restoring powered off state."""
    # Setup mock methods
    mock_light.set_color = AsyncMock()
    mock_light.set_power = AsyncMock()

    mock_light.get_power = AsyncMock(return_value=0)

    # Create powered-off prestate
    color = HSBK(hue=0, saturation=0, brightness=0, kelvin=3500)
    prestate = PreState(power=False, color=color, zone_colors=None)

    # Restore state
    await state_manager.restore_state(mock_light, prestate)

    # Verify power restored to off
    mock_light.set_power.assert_called_once_with(False, duration=0.0)


@pytest.mark.asyncio
async def test_restore_to_off_turns_off_before_writing_colours(
    state_manager, mock_light
) -> None:
    """A light that was off goes dark first, then gets its colours back.

    Writing colours while the light is still on shows them as a flash, and
    real firmware keeps reporting power on for a moment after an
    acknowledged power-off, so the colours wait until it reports off.
    """
    order = MagicMock()
    mock_light.set_power = AsyncMock()
    mock_light.get_power = AsyncMock(side_effect=[65535, 65535, 0])
    mock_light.set_color = AsyncMock()
    order.attach_mock(mock_light.set_power, "set_power")
    order.attach_mock(mock_light.get_power, "get_power")
    order.attach_mock(mock_light.set_color, "set_color")
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)

    await state_manager.restore_state(mock_light, PreState(power=False, color=color))

    names = [c[0] for c in order.mock_calls]
    assert names == ["set_power", "get_power", "get_power", "get_power", "set_color"]
    mock_light.set_power.assert_called_once_with(False, duration=0.0)
    mock_light.set_color.assert_called_once_with(color, duration=0.0)


@pytest.mark.asyncio
@pytest.mark.parametrize("extended", [True, False])
async def test_restore_state_multizone_delegates_to_set_all_color_zones(
    state_manager, mock_multizone_light, extended: bool
) -> None:
    """Test the restore hands the whole list to set_all_color_zones.

    Choosing the packet type and chunking past the 82-color extended limit is
    set_all_color_zones' job, so the restore no longer branches on
    capabilities itself.
    """
    mock_multizone_light.set_all_color_zones = AsyncMock()
    mock_multizone_light.set_color = AsyncMock()
    mock_multizone_light.set_power = AsyncMock()
    mock_multizone_light.capabilities.has_extended_multizone = extended

    color = HSBK(hue=180, saturation=0.8, brightness=0.7, kelvin=4000)
    zone_colors = [
        HSBK(hue=i * 20, saturation=1.0, brightness=0.8, kelvin=3500) for i in range(16)
    ]
    prestate = PreState(power=True, color=color, zone_colors=zone_colors)

    await state_manager.restore_state(mock_multizone_light, prestate)

    mock_multizone_light.set_all_color_zones.assert_awaited_once_with(
        zone_colors,
        duration=0.0,
        apply=MultiZoneApplicationRequest.APPLY,
    )


async def test_restore_state_multizone_chunks_past_the_extended_limit(
    state_manager,
) -> None:
    """Test a strip longer than 82 zones restores instead of raising.

    The old restore called set_extended_color_zones with every captured zone,
    which raised ValueError past 82 colors — swallowed by the broad handler,
    so the strip silently stayed on the effect's last frame.
    """
    light = MultiZoneLight(serial="d073d5abcdef", ip="192.168.1.100")
    light._capabilities = MagicMock()
    light._capabilities.has_extended_multizone = True
    light._zone_count = 128
    light.set_extended_color_zones = AsyncMock()
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()

    color = HSBK(hue=180, saturation=0.8, brightness=0.7, kelvin=4000)
    zone_colors = [
        HSBK(hue=i * 2, saturation=1.0, brightness=0.8, kelvin=3500) for i in range(128)
    ]
    prestate = PreState(power=True, color=color, zone_colors=zone_colors)

    await state_manager.restore_state(light, prestate)

    assert light.set_extended_color_zones.await_count == 2
    assert [
        call.args[0] for call in light.set_extended_color_zones.await_args_list
    ] == [
        0,
        82,
    ]


@pytest.mark.asyncio
async def test_restore_color_failure_handling(state_manager, mock_light) -> None:
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
async def test_restore_power_failure_handling(state_manager, mock_light) -> None:
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
async def test_restore_zones_failure_handling(
    state_manager, mock_multizone_light
) -> None:
    """Test restore handles zone setting failures gracefully."""
    # Setup mock to fail on zones
    mock_multizone_light.set_all_color_zones = AsyncMock(
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


@pytest.mark.parametrize(
    "get_power",
    [
        AsyncMock(return_value=65535),
        AsyncMock(side_effect=LifxTimeoutError("no reply")),
    ],
    ids=["never-reports-off", "power-read-fails"],
)
@pytest.mark.asyncio
async def test_restore_to_off_writes_no_colours_unless_off_is_confirmed(
    state_manager, mock_light, caplog, monkeypatch, get_power
) -> None:
    """Colours written to a light that may still be lit would flash.

    When the light never reports off, or its power cannot be read, the
    colours are left alone and the restore says so.
    """
    monkeypatch.setattr("lifx.devices.light.POWER_OFF_WAIT_SECONDS", 0.05)
    mock_light.set_power = AsyncMock()
    mock_light.get_power = get_power
    mock_light.set_color = AsyncMock()
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)

    await state_manager.restore_state(mock_light, PreState(power=False, color=color))

    mock_light.set_power.assert_called_once_with(False, duration=0.0)
    mock_light.set_color.assert_not_called()
    assert "_wait_until_off" in caplog.text


async def test_restore_state_multizone_keeps_its_zones(state_manager) -> None:
    """Restoring a strip writes its zones and never one colour over them.

    SetColor paints every zone, so a single-colour write after the zones
    would flatten the strip back to one colour.
    """
    light = MultiZoneLight(serial="d073d5abcdef", ip="192.168.1.100")
    light._capabilities = MagicMock()
    light._capabilities.has_extended_multizone = True
    light._zone_count = 4
    zone_colors = [
        HSBK(hue=i * 90, saturation=1.0, brightness=0.8, kelvin=3500) for i in range(4)
    ]
    shown: list[HSBK] = []

    async def set_zones(_index: int, colors: list[HSBK], **_kwargs: object) -> None:
        shown[:] = list(colors)

    async def set_color(color: HSBK, **_kwargs: object) -> None:
        shown[:] = [color] * 4

    light.set_extended_color_zones = AsyncMock(side_effect=set_zones)
    light.set_color = AsyncMock(side_effect=set_color)
    light.set_power = AsyncMock()

    prestate = PreState(power=True, color=zone_colors[0], zone_colors=zone_colors)
    await state_manager.restore_state(light, prestate)

    assert shown == zone_colors
    light.set_color.assert_not_awaited()
