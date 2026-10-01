"""Tests for refresh_state(extended=False) across the device classes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from lifx.devices.ceiling import CeilingLight
from lifx.devices.hev import HevLight
from lifx.devices.infrared import InfraredLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight

EXTENDED_GETTERS = (
    "get_all_color_zones",
    "get_all_tile_colors",
    "get_effect",
    "get_hev_cycle",
    "get_last_hev_result",
    "get_infrared",
)


@pytest.mark.parametrize(
    "device_class",
    [
        pytest.param(MultiZoneLight, id="multizone"),
        pytest.param(MatrixLight, id="matrix"),
        pytest.param(CeilingLight, id="ceiling"),
        pytest.param(MirrorLight, id="mirror"),
        pytest.param(HevLight, id="hev"),
        pytest.param(InfraredLight, id="infrared"),
    ],
)
async def test_refresh_state_without_extended_reads_only_the_colour_batch(
    device_class: type[Light],
) -> None:
    """extended=False stops after the colour batch, leaving extended state alone."""
    device = device_class(serial="d073d5000001", ip="192.0.2.1")
    state = SimpleNamespace()
    device._state = state
    getters = {
        name: AsyncMock() for name in EXTENDED_GETTERS if hasattr(device_class, name)
    }
    core_refresh = AsyncMock()

    with patch.object(Light, "refresh_state", core_refresh):
        for name, getter in getters.items():
            setattr(device, name, getter)
        await device.refresh_state(extended=False)

    core_refresh.assert_awaited_once_with(extended=False)
    for name, getter in getters.items():
        assert not getter.await_count, f"{name} was read"
    # Component colours are derived from tile colours, so they must not be
    # rewritten from a tile buffer this refresh never read
    assert vars(state) == {}
