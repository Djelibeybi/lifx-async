"""stop_effect() after animate_mood() puts back what the light showed before.

These run the real effect runner and Conductor against simulated lights, so
what is captured, held and restored is the library's own behaviour. The matrix
simulation reports in-flight colours from a tile read taken during a fade, as
hardware does, so a prior state read back after painting would be caught.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.api import DeviceGroup
from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight
from lifx.products import get_product
from lifx.protocol import packets
from lifx.protocol.protocol_types import FirmwareEffect
from lifx.theme import Theme
from tests.test_devices import test_component_transitions as transitions
from tests.test_theme.conftest import make_tile

RED = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
GREEN = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
MOVE = Theme([RED, GREEN], static_mode="solid_static")
MOVE_AGAIN = Theme([GREEN, RED], static_mode="grid_static")
MORPH = Theme([RED, GREEN], static_mode="blended")

# What a tile read reports while a fade is in flight: neither the old image
# nor the new one.
IN_FLIGHT = HSBK(hue=60, saturation=0.5, brightness=0.5, kelvin=3500)


def pattern(count: int, brightness: float = 0.4) -> list[HSBK]:
    return [
        HSBK(hue=(i * 50) % 360, saturation=1.0, brightness=brightness, kelvin=3500)
        for i in range(count)
    ]


@pytest.fixture(autouse=True)
def no_settle_delays(monkeypatch) -> None:
    for module in ("state_manager", "base"):
        for name in (
            "COLOR_UPDATE_SETTLE_DELAY",
            "ZONE_UPDATE_SETTLE_DELAY",
            "POWER_ON_SETTLE_DELAY",
        ):
            monkeypatch.setattr(f"lifx.effects.{module}.{name}", 0, raising=False)


class MatrixSim:
    """One 2x2 tile whose reads report in-flight colours during a fade."""

    def __init__(self, light: MatrixLight, *, on: bool) -> None:
        self.light = light
        self.power = 65535 if on else 0
        self.tiles = [pattern(4)]
        self.fading = False
        self.effect = FirmwareEffect.OFF
        self.log: list[Any] = []
        chain = [make_tile(0, width=2, height=2)]
        light._device_chain = chain
        light.get_device_chain = AsyncMock(return_value=chain)
        light.get_all_tile_colors = AsyncMock(side_effect=self.read)
        light.set_matrix_colors = AsyncMock(side_effect=self.write)
        light.get_color = AsyncMock(
            side_effect=lambda: (self.tiles[0][0], self.power, "")
        )
        light.get_power = AsyncMock(side_effect=lambda: self.power)
        light.set_power = AsyncMock(side_effect=self.set_power)
        light.set_effect = AsyncMock(side_effect=self.set_effect)
        light.get_effect = AsyncMock(
            side_effect=lambda: MagicMock(effect_type=self.effect)
        )

    def read(self) -> list[list[HSBK]]:
        self.log.append("read")
        if self.fading:
            return [[IN_FLIGHT] * 4]
        return [list(tile) for tile in self.tiles]

    def write(self, tile_index: int, colors: list[HSBK], duration: int = 0) -> None:
        self.log.append(("write", duration))
        self.tiles[tile_index] = list(colors)
        self.fading = duration > 0

    def set_power(self, level: bool, duration: float = 0.0) -> None:
        self.log.append(("power", bool(level)))
        self.power = 65535 if level else 0

    def set_effect(self, effect_type: FirmwareEffect, **_kwargs: Any) -> None:
        self.log.append(("effect", effect_type))
        self.effect = effect_type


@pytest.fixture
def matrix(mock_device_factory) -> MatrixSim:
    return MatrixSim(
        mock_device_factory(MatrixLight, serial="d073d5000c01", product=55), on=True
    )


@pytest.fixture
def dark_matrix(mock_device_factory) -> MatrixSim:
    return MatrixSim(
        mock_device_factory(MatrixLight, serial="d073d5000c02", product=55), on=False
    )


class TestMatrixMove:
    async def test_stop_restores_the_image_from_before_the_paint(
        self, matrix: MatrixSim
    ) -> None:
        before = list(matrix.tiles[0])
        await matrix.light.animate_mood(MOVE)
        assert matrix.light._mood_prestate is None
        await matrix.light.stop_effect()
        assert matrix.tiles == [before]
        assert matrix.power == 65535

    async def test_no_tile_is_read_back_after_painting(self, matrix: MatrixSim) -> None:
        await matrix.light.animate_mood(MOVE)
        await matrix.light.stop_effect()
        first_write = next(i for i, e in enumerate(matrix.log) if e[0] == "write")
        assert "read" in matrix.log[:first_write]
        assert "read" not in matrix.log[first_write:]

    async def test_an_off_light_goes_back_off(self, dark_matrix: MatrixSim) -> None:
        before = list(dark_matrix.tiles[0])
        await dark_matrix.light.animate_mood(MOVE)
        assert dark_matrix.power == 65535
        await dark_matrix.light.stop_effect()
        assert dark_matrix.power == 0
        assert dark_matrix.tiles == [before]

    async def test_a_restart_keeps_the_original(self, matrix: MatrixSim) -> None:
        before = list(matrix.tiles[0])
        await matrix.light.animate_mood(MOVE)
        await matrix.light.apply_mood(MOVE_AGAIN)
        await matrix.light.stop_effect()
        assert matrix.tiles == [before]

    async def test_a_second_stop_restores_nothing_more(self, matrix: MatrixSim) -> None:
        await matrix.light.animate_mood(MOVE)
        await matrix.light.stop_effect()
        matrix.log.clear()
        await matrix.light.stop_effect()
        assert matrix.log == [("effect", FirmwareEffect.OFF)]


class TestMatrixMorph:
    async def test_stop_turns_an_off_light_back_off(
        self, dark_matrix: MatrixSim
    ) -> None:
        before = list(dark_matrix.tiles[0])
        await dark_matrix.light.animate_mood(MORPH)
        assert dark_matrix.effect == FirmwareEffect.MORPH
        assert dark_matrix.power == 65535
        await dark_matrix.light.stop_effect()
        assert dark_matrix.effect == FirmwareEffect.OFF
        assert dark_matrix.power == 0
        assert dark_matrix.tiles == [before]

    async def test_firmware_stops_before_the_restore(self, matrix: MatrixSim) -> None:
        await matrix.light.animate_mood(MORPH)
        matrix.log.clear()
        await matrix.light.stop_effect()
        assert matrix.log[0] == ("effect", FirmwareEffect.OFF)
        assert ("write", 0) in matrix.log[1:]

    async def test_morph_then_move_restores_the_original(
        self, dark_matrix: MatrixSim
    ) -> None:
        before = list(dark_matrix.tiles[0])
        await dark_matrix.light.animate_mood(MORPH)
        await dark_matrix.light.animate_mood(MOVE)
        assert dark_matrix.effect == FirmwareEffect.OFF
        await dark_matrix.light.stop_effect()
        assert dark_matrix.power == 0
        assert dark_matrix.tiles == [before]

    async def test_move_then_morph_restores_the_original(
        self, matrix: MatrixSim
    ) -> None:
        before = list(matrix.tiles[0])
        await matrix.light.animate_mood(MOVE)
        await matrix.light.animate_mood(MORPH)
        assert matrix.light._mood_prestate is not None
        await matrix.light.stop_effect()
        assert matrix.tiles == [before]

    async def test_a_second_stop_restores_nothing_more(self, matrix: MatrixSim) -> None:
        await matrix.light.animate_mood(MORPH)
        await matrix.light.stop_effect()
        matrix.log.clear()
        await matrix.light.stop_effect()
        assert matrix.log == [("effect", FirmwareEffect.OFF)]


class StripSim:
    """A strip's zones, power and firmware effect."""

    def __init__(self, light: MultiZoneLight, *, on: bool) -> None:
        self.power = 65535 if on else 0
        self.zones = pattern(4)
        self.effect = FirmwareEffect.OFF
        light.get_zone_count = AsyncMock(return_value=4)
        light.get_extended_color_zones = AsyncMock(
            side_effect=lambda **_: list(self.zones)
        )
        light.get_all_color_zones = AsyncMock(side_effect=lambda: list(self.zones))
        light.set_all_color_zones = AsyncMock(side_effect=self.write)
        # SetColor paints every zone, so a restore must never follow its
        # zones with one.
        light.set_color = AsyncMock(side_effect=self.set_color)
        light.get_color = AsyncMock(side_effect=lambda: (self.zones[0], self.power, ""))
        light.get_power = AsyncMock(side_effect=lambda: self.power)
        light.set_power = AsyncMock(side_effect=self.set_power)
        light.set_effect = AsyncMock(side_effect=self.set_effect)
        light.get_effect = AsyncMock(
            side_effect=lambda: MagicMock(effect_type=self.effect)
        )

    def write(self, colors: list[HSBK], **_kwargs: Any) -> None:
        self.zones = list(colors)

    def set_color(self, color: HSBK, **_kwargs: Any) -> None:
        self.zones = [color] * len(self.zones)

    def set_power(self, level: bool, duration: float = 0.0) -> None:
        self.power = 65535 if level else 0

    def set_effect(self, effect: MultiZoneEffect) -> None:
        self.effect = effect.effect_type


class TestStrip:
    async def test_stop_after_the_mood_ended_elsewhere_keeps_the_light(
        self, mock_device_factory
    ) -> None:
        light = mock_device_factory(MultiZoneLight, serial="d073d5000c03", product=32)
        strip = StripSim(light, on=True)
        await light.animate_mood(MOVE)
        strip.effect = FirmwareEffect.OFF  # stopped by another app
        since = pattern(4, brightness=0.9)
        strip.zones = list(since)
        await light.stop_effect()
        assert strip.zones == since
        assert light._mood_prestate is None

    @pytest.mark.parametrize("on", [True, False])
    async def test_stop_restores_zones_and_power(self, mock_device_factory, on) -> None:
        light = mock_device_factory(MultiZoneLight, serial="d073d5000c03", product=32)
        strip = StripSim(light, on=on)
        before = list(strip.zones)
        await light.animate_mood(MOVE)
        assert strip.effect == FirmwareEffect.MOVE
        assert strip.power == 65535
        await light.apply_mood(MOVE_AGAIN)  # a restart
        await light.stop_effect()
        assert strip.effect == FirmwareEffect.OFF
        assert strip.zones == before
        assert strip.power == (65535 if on else 0)


async def _bulb_state(bulb: Light) -> tuple[HSBK, int]:
    color, power, _ = await bulb.get_color()
    return color, power


async def _turns_on(bulb: Light) -> None:
    """The colour loop powers a bulb on from its own task."""
    for _ in range(50):
        if await bulb.get_power() > 0:
            return
        await asyncio.sleep(0.02)
    raise AssertionError("the bulb never turned on")


@pytest.mark.emulator
class TestBulbs:
    async def test_stop_restores_colour_and_power(self, emulator_devices) -> None:
        bulb = emulator_devices[0]
        async with bulb:
            await bulb.set_color(HSBK(200, 0.5, 0.3, 3500))
            await bulb.set_power(False)
            before = await _bulb_state(bulb)
            await bulb.animate_mood(MORPH)
            await bulb.apply_mood(MOVE)  # a restart
            await _turns_on(bulb)
            await bulb.stop_effect()
            assert await _bulb_state(bulb) == before

    @pytest.mark.parametrize("restart", [False, True], ids=["once", "restarted"])
    async def test_group_bulbs_each_get_their_own_state_back(
        self, emulator_devices, restart: bool
    ) -> None:
        a, b = emulator_devices[0], emulator_devices[1]
        async with a, b:
            await a.set_color(HSBK(30, 1.0, 0.2, 3500))
            await a.set_power(False)
            await b.set_color(HSBK(250, 1.0, 0.6, 3500))
            await b.set_power(True)
            before = [await _bulb_state(a), await _bulb_state(b)]
            await DeviceGroup([a, b]).animate_mood(MORPH)
            # animate_mood turns on an off light beside one that is on.
            await _turns_on(a)
            if restart:
                # The restarted loop keeps each bulb's state from before.
                await DeviceGroup([a, b]).animate_mood(MOVE)
            await a.stop_effect()
            await b.stop_effect()
            assert [await _bulb_state(a), await _bulb_state(b)] == before


class TestComponentLight:
    @pytest.fixture(params=[176, 267], ids=["ceiling", "mirror"])
    def rig(self, request, monkeypatch) -> transitions.Rig:
        rig = transitions.build_rig(request.param, monkeypatch)
        rig.light._capabilities = get_product(request.param)
        rig.light.get_device_chain = AsyncMock(  # type: ignore[method-assign]
            return_value=rig.light._device_chain
        )
        exchange = rig.wire.exchange
        effect = {"type": FirmwareEffect.OFF}

        async def with_effects(packet, **kwargs):
            if isinstance(packet, packets.Tile.SetEffect):
                rig.wire.packets.append(packet)
                effect["type"] = packet.settings.effect_type
                return packets.Device.Acknowledgement()
            return await exchange(packet, **kwargs)

        rig.light.connection.request.side_effect = with_effects
        rig.light.get_effect = AsyncMock(  # type: ignore[method-assign]
            side_effect=lambda: MagicMock(effect_type=effect["type"])
        )
        return rig

    @pytest.mark.parametrize("on", [True, False])
    @pytest.mark.parametrize("theme", [MOVE, MORPH])
    async def test_stop_restores_the_tile_and_power(
        self, rig: transitions.Rig, theme: Theme, on: bool
    ) -> None:
        rig.wire.colours[:] = [transitions.GREEN] * len(rig.wire.colours)
        await rig.read(0)
        await rig.read(1)
        if not on:
            await rig.light.set_power(False)
            rig.settle()
        tile = list(rig.wire.colours)
        await rig.light.animate_mood(theme)
        rig.settle(2.0)
        assert rig.wire.power == 65535
        await rig.light.stop_effect()
        rig.settle()
        assert rig.wire.colours == tile
        assert rig.wire.power == (65535 if on else 0)
