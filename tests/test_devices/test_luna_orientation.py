"""A Luna on its side is painted and animated as a 5 wide by 7 high canvas.

The emulator's Luna (product 219) reports a 7x5 tile. Its accelerometer
reading is set here so the device reads as lying on one side or upside down,
and the colors the emulator ends up holding are checked in physical order.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable, Iterator

import pytest
from lifx_emulator import EmulatedLifxServer
from lifx_emulator.factories import create_device
from lifx_emulator.scenarios import HierarchicalScenarioManager

from lifx.animation.orientation import Orientation, build_orientation_lut
from lifx.color import HSBK, Colors
from lifx.devices.matrix import MatrixLight
from lifx.theme import MatrixGenerator, Theme
from tests.conftest import remove_emulated_device
from tests.test_products.test_hidden_cell_support import darkened

LUNA = 219
SERIAL = "d073d5000324"
# Luna axis map: +x UpsideDown, +z RotatedLeft, -z RotatedRight.
SIDES = [
    ((0, 0, -100), Orientation.ROTATED_90),
    ((0, 0, 100), Orientation.ROTATED_270),
]


@pytest.fixture
def make_luna(
    emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
) -> Iterator[Callable[[tuple[int, int, int]], MatrixLight]]:
    port, server, scenario_manager = emulator_server
    if server is None:
        pytest.skip("Cannot add devices to an external emulator")
    added: list[str] = []

    def make(accel: tuple[int, int, int]) -> MatrixLight:
        device = create_device(
            product_id=LUNA, serial=SERIAL, scenario_manager=scenario_manager
        )
        tile = device.state.tile_devices[0]
        tile["accel_meas_x"], tile["accel_meas_y"], tile["accel_meas_z"] = accel
        server.add_device(device)
        added.append(SERIAL)
        return MatrixLight(
            serial=SERIAL, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2
        )

    yield make
    for serial in added:
        remove_emulated_device(server, serial)


def _same(shown: list[HSBK], expected: list[HSBK]) -> None:
    assert len(shown) == len(expected)
    for index, (got, want) in enumerate(zip(shown, expected, strict=True)):
        assert got.brightness == pytest.approx(want.brightness, abs=0.01), index
        if want.brightness:
            assert got.hue == pytest.approx(want.hue, abs=0.1), index
            assert got.saturation == pytest.approx(want.saturation, abs=0.01), index


@pytest.mark.emulator
class TestLunaOnItsSide:
    @pytest.mark.parametrize(("accel", "orientation"), SIDES)
    async def test_theme_paint_is_turned_onto_the_tile(
        self, make_luna, accel: tuple[int, int, int], orientation: Orientation
    ) -> None:
        light = make_luna(accel)
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])
        random.seed(20260801)
        canvas = MatrixGenerator([((0, 0), (5, 7))]).get_theme_colors(theme)[0]
        lut = build_orientation_lut(7, 5, orientation)
        expected = darkened([canvas[src] for src in lut], LUNA)

        random.seed(20260801)
        async with light:
            await light.set_power(True)
            await light.apply_theme(theme)
            shown = (await light.get_all_tile_colors())[0][:35]
            tile = (await light.get_device_chain())[0]

        _same(shown, expected)
        assert shown != canvas
        _same(light._to_logical(tile, shown), light._to_logical(tile, expected))

    async def test_an_upside_down_luna_is_turned_around(self, make_luna) -> None:
        light = make_luna((100, 0, 0))
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])
        random.seed(20260801)
        canvas = MatrixGenerator([((0, 0), (7, 5))]).get_theme_colors(theme)[0]

        random.seed(20260801)
        async with light:
            await light.set_power(True)
            await light.apply_theme(theme)
            shown = (await light.get_all_tile_colors())[0][:35]

        _same(shown, darkened(canvas[::-1], LUNA))

    @pytest.mark.parametrize(("accel", "orientation"), SIDES)
    async def test_animator_frames_are_turned_onto_the_tile(
        self, make_luna, accel: tuple[int, int, int], orientation: Orientation
    ) -> None:
        light = make_luna(accel)
        frame = [(i * 1000, 65535, 65535, 3500) for i in range(35)]
        lut = build_orientation_lut(7, 5, orientation)
        expected = [
            HSBK(
                hue=frame[src][0] / 65535 * 360,
                saturation=1.0,
                brightness=1.0,
                kelvin=3500,
            )
            for src in lut
        ]

        async with light:
            await light.set_power(True)
            animator = await light.animator.prepare()
            assert (animator.canvas_width, animator.canvas_height) == (5, 7)
            animator.send_frame(frame)
            await asyncio.sleep(0.3)
            shown = (await light.get_all_tile_colors())[0][:35]

        _same(shown, darkened(expected, LUNA))
