"""Hidden cells are sent dark by paints and frames, and read back whole."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator

import pytest
from lifx_emulator import EmulatedLifxServer
from lifx_emulator.factories import create_device
from lifx_emulator.scenarios import HierarchicalScenarioManager

from lifx.color import HSBK
from lifx.const import MOOD_FADE_SECONDS
from lifx.devices.ceiling import CeilingLight
from lifx.devices.matrix import MatrixLight
from lifx.devices.mirror import MirrorLight
from lifx.effects.state_manager import DeviceStateManager
from lifx.products import get_product
from lifx.theme import get_theme
from tests.conftest import remove_emulated_device

# (label, product id, serial, device class)
FAMILIES = [
    ("candle", 57, "d073d5000321", MatrixLight),
    ("ceiling", 201, "d073d5000322", CeilingLight),
    ("luna", 219, "d073d5000323", MatrixLight),
]

BRIGHT = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)


@pytest.fixture
def make_light(
    emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
) -> Iterator[Callable[[int, str, type], MatrixLight]]:
    port, server, scenario_manager = emulator_server
    if server is None:
        pytest.skip("Cannot add devices to an external emulator")
    added: list[str] = []

    def make(pid: int, serial: str, cls: type) -> MatrixLight:
        server.add_device(
            create_device(
                product_id=pid, serial=serial, scenario_manager=scenario_manager
            )
        )
        added.append(serial)
        return cls(serial=serial, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2)

    yield make
    for serial in added:
        remove_emulated_device(server, serial)


def _dark(colors: list[HSBK], hidden: frozenset[int]) -> None:
    for index, color in enumerate(colors):
        if index in hidden:
            assert color.brightness == 0, index
        else:
            assert color.brightness > 0, index


@pytest.mark.emulator
@pytest.mark.parametrize(("label", "pid", "serial", "cls"), FAMILIES)
class TestHiddenCellsOnPaintAndFrames:
    async def test_theme_paint_sends_hidden_cells_dark(
        self, make_light, label, pid, serial, cls
    ) -> None:
        light = make_light(pid, serial, cls)
        masked = get_product(pid).masked_zones
        async with light:
            await light.set_power(True)
            await light.apply_theme(get_theme("evening"), power_on=True)
            tile = (await light.get_all_tile_colors())[0]
            if cls is CeilingLight:
                tile = tile[:-1]  # the uplight is not masked
            for index, color in enumerate(tile):
                assert (color.brightness == 0) == (index in masked), index

    async def test_mood_paint_sends_hidden_cells_dark(
        self, make_light, label, pid, serial, cls
    ) -> None:
        light = make_light(pid, serial, cls)
        masked = get_product(pid).masked_zones
        async with light:
            await light.apply_mood(get_theme("evening"))
            await asyncio.sleep(MOOD_FADE_SECONDS)  # the mood fades in
            tile = (await light.get_all_tile_colors())[0]
            for index in masked:
                assert tile[index].brightness == 0, index

    async def test_effect_frame_sends_hidden_cells_dark(
        self, make_light, label, pid, serial, cls
    ) -> None:
        light = make_light(pid, serial, cls)
        masked = get_product(pid).masked_zones
        async with light:
            animator = await light.animator.prepare()
            size = animator.pixel_count
            animator.send_frame([(21845, 65535, 65535, 3500)] * size)
            await asyncio.sleep(0.3)
            tile = (await light.get_all_tile_colors())[0]
            if cls is CeilingLight:
                tile = tile[:-1]
            for index, color in enumerate(tile):
                assert (color.brightness == 0) == (index in masked), index

    async def test_capture_and_restore_round_trip_every_cell(
        self, make_light, label, pid, serial, cls
    ) -> None:
        light = make_light(pid, serial, cls)
        async with light:
            size = len((await light.get_all_tile_colors())[0])
            await light.set_matrix_colors(0, [BRIGHT] * size, duration=0)
            manager = DeviceStateManager(settle_window=0)
            prestate = await manager.capture_state(light)
            await light.set_matrix_colors(0, [HSBK(0, 1.0, 0.5, 3500)] * size, 0)
            await manager.restore_state(light, prestate)
            restored = (await light.get_all_tile_colors())[0]
            assert len(restored) == size
            assert all(color.brightness > 0.9 for color in restored)


@pytest.mark.emulator
async def test_ceiling_component_shapes_are_unchanged(make_light) -> None:
    light = make_light(201, "d073d5000324", CeilingLight)
    async with light:
        assert light.downlight_zone_count == 127
        await light.set_uplight_color(BRIGHT)
        await light.set_downlight_colors([BRIGHT] * 127)
        assert len(await light.get_downlight_colors()) == 127
        assert (await light.get_uplight_color()).brightness > 0.9
        # Component writes are caller writes: no cell is blacked out.
        tile = (await light.get_all_tile_colors())[0]
        assert all(color.brightness > 0.9 for color in tile)


@pytest.mark.emulator
async def test_mirror_is_not_masked(make_light) -> None:
    light = make_light(267, "d073d5000325", MirrorLight)
    async with light:
        animator = await light.animator.prepare()
        animator.send_frame([(21845, 65535, 65535, 3500)] * animator.pixel_count)
        await asyncio.sleep(0.3)
        tile = (await light.get_all_tile_colors())[0]
        lit = [i for i, c in enumerate(tile) if c.brightness > 0]
        assert len(lit) >= 50
