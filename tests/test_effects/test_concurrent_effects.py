"""Concurrent software effects on the light components of one Ceiling."""

from __future__ import annotations

import asyncio

import pytest

from lifx.color import HSBK
from lifx.devices.ceiling import CeilingLight
from lifx.devices.light import Light
from lifx.devices.multizone import MultiZoneLight
from lifx.effects.colorloop import EffectColorloop
from lifx.effects.conductor import Conductor, own_conductor
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.plasma2d import EffectPlasma2D
from tests.test_effects.test_component_effects import (
    AMBER,
    DIM_BLUE,
    DOWNLIGHT,
    GREEN,
    RED,
    UPLIGHT,
    WHITE,
    _eventually,
    _prepare,
    _SolidFrames,
    _tile,
)

BLUE = HSBK.from_protocol(HSBK(240, 1, 1, 3500).to_protocol())


class _Alternating(FrameEffect):
    """Alternates two colours every frame, a different effect at its own rate."""

    def __init__(self, first: HSBK, second: HSBK) -> None:
        super().__init__(power_on=True, fps=7.0)
        self.first = first
        self.second = second
        self.frames = 0

    @property
    def name(self) -> str:
        return "alternating"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        self.frames += 1
        colour = self.first if self.frames % 2 else self.second
        return [colour] * ctx.pixel_count


async def _sample(
    ceiling: CeilingLight,
) -> tuple[set[tuple[HSBK, ...]], set[HSBK]]:
    """The distinct downlights and uplight colours seen over about two seconds."""
    downlights: set[tuple[HSBK, ...]] = set()
    uplights: set[HSBK] = set()
    for _ in range(20):
        tile = await _tile(ceiling)
        downlights.add(tuple(tile[:DOWNLIGHT]))
        uplights.add(tile[UPLIGHT])
        await asyncio.sleep(0.1)
    return downlights, uplights


@pytest.mark.emulator
class TestConcurrentComponentEffects:
    async def test_two_different_effects_run_on_the_uplight_and_downlight(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            flicker = _Alternating(RED, AMBER)
            solid = _SolidFrames(WHITE)

            await ceiling.uplight.start_effect(flicker)
            await ceiling.downlight.start_effect(solid)

            conductor = own_conductor(ceiling)
            assert conductor.effect(ceiling.uplight) is flicker
            assert conductor.effect(ceiling.downlight) is solid

            async def both_drawn() -> bool:
                tile = await _tile(ceiling)
                return (
                    tile[UPLIGHT] in (RED, AMBER)
                    and tile[:DOWNLIGHT] == [WHITE] * DOWNLIGHT
                )

            await _eventually(both_drawn)
            seen = {(await _tile(ceiling))[UPLIGHT]}
            for _ in range(20):
                seen.add((await _tile(ceiling))[UPLIGHT])
                await asyncio.sleep(0.05)
            assert seen == {RED, AMBER}

            await ceiling.stop_effect()

            assert await ceiling.get_uplight_color() == DIM_BLUE
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT

    async def test_stopping_one_component_leaves_the_others_effect_running(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            flicker = _Alternating(RED, AMBER)
            solid = _SolidFrames(WHITE)
            await ceiling.uplight.start_effect(flicker)
            await ceiling.downlight.start_effect(solid)

            async def downlight_white() -> bool:
                return (await _tile(ceiling))[:DOWNLIGHT] == [WHITE] * DOWNLIGHT

            await _eventually(downlight_white)

            await ceiling.uplight.stop_effect()

            conductor = own_conductor(ceiling)
            assert conductor.effect(ceiling.uplight) is None
            assert conductor.effect(ceiling.downlight) is solid

            async def uplight_back() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == DIM_BLUE

            await _eventually(uplight_back)
            frames = solid.contexts[-1]
            for _ in range(5):  # the downlight effect keeps drawing
                tile = await _tile(ceiling)
                assert tile[UPLIGHT] == DIM_BLUE
                assert tile[:DOWNLIGHT] == [WHITE] * DOWNLIGHT
                await asyncio.sleep(0.05)
            assert solid.contexts[-1] is not frames

            await ceiling.downlight.stop_effect()

            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT

    async def test_plasma2d_on_the_downlight_beside_colour_loop_on_the_uplight(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            plasma = EffectPlasma2D(speed=4.0)
            loop = EffectColorloop(period=3, change=60)

            await ceiling.downlight.start_effect(plasma)
            await ceiling.uplight.start_effect(loop)

            conductor = own_conductor(ceiling)
            assert conductor.effect(ceiling.downlight) is plasma
            assert conductor.effect(ceiling.uplight) is loop

            async def both_drawn() -> bool:
                tile = await _tile(ceiling)
                return GREEN not in tile[:DOWNLIGHT] and tile[UPLIGHT] != DIM_BLUE

            await _eventually(both_drawn)
            downlights, uplights = await _sample(ceiling)
            assert len(downlights) > 1  # the plasma moves
            assert all(len(set(frame)) > 1 for frame in downlights)  # and varies
            assert len(uplights) > 1  # colour loop steps while plasma holds the tile

            await ceiling.downlight.stop_effect()

            assert conductor.effect(ceiling.uplight) is loop

            # The restore rides on colour loop's next write to the held tile.
            async def downlight_back() -> bool:
                return await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT

            await _eventually(downlight_back)
            downlights, uplights = await _sample(ceiling)
            assert downlights == {(GREEN,) * DOWNLIGHT}
            assert len(uplights) > 1  # colour loop carries on with the tile alone

            await ceiling.uplight.stop_effect()

            assert await ceiling.get_uplight_color() == DIM_BLUE
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT

    async def test_stopping_colour_loop_on_the_uplight_leaves_plasma2d_running(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            plasma = EffectPlasma2D(speed=4.0)
            loop = EffectColorloop(period=3, change=60)
            await ceiling.downlight.start_effect(plasma)
            await ceiling.uplight.start_effect(loop)

            async def both_drawn() -> bool:
                tile = await _tile(ceiling)
                return GREEN not in tile[:DOWNLIGHT] and tile[UPLIGHT] != DIM_BLUE

            await _eventually(both_drawn)

            await ceiling.uplight.stop_effect()

            conductor = own_conductor(ceiling)
            assert conductor.effect(ceiling.uplight) is None
            assert conductor.effect(ceiling.downlight) is plasma

            async def uplight_back() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == DIM_BLUE

            await _eventually(uplight_back)
            downlights, uplights = await _sample(ceiling)
            assert uplights == {DIM_BLUE}
            assert len(downlights) > 1  # the plasma keeps moving

            await ceiling.downlight.stop_effect()

            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT
            assert await ceiling.get_uplight_color() == DIM_BLUE

    async def test_both_components_share_one_effects_clock(self, ceiling_device):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            conductor = Conductor()
            effect = _SolidFrames(RED)

            await conductor.start(effect, [ceiling.uplight, ceiling.downlight])

            async def all_red() -> bool:
                return (await _tile(ceiling)) == [RED] * 128

            await _eventually(all_red)
            contexts = list(effect.contexts)
            pairs = list(zip(contexts[::2], contexts[1::2]))
            assert pairs
            for uplight, downlight in pairs:
                assert (uplight.device_index, downlight.device_index) == (0, 1)
                assert uplight.elapsed_s == downlight.elapsed_s
                assert uplight.pixel_count == 1
                assert downlight.pixel_count == 128

            await conductor.stop([ceiling.uplight, ceiling.downlight])

            assert await ceiling.get_uplight_color() == DIM_BLUE
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT

    async def test_one_effect_mixes_a_component_with_whole_lights(
        self, ceiling_device, emulator_devices
    ):
        ceiling = ceiling_device
        bulb = emulator_devices[0]
        strip = emulator_devices[4]
        assert isinstance(bulb, Light)
        assert isinstance(strip, MultiZoneLight)
        async with ceiling:
            await _prepare(ceiling)
            await bulb.set_power(True)
            await bulb.set_color(GREEN)
            await strip.set_power(True)
            await strip.set_color(GREEN)
            conductor = Conductor()
            effect = _SolidFrames(BLUE)

            await conductor.start(effect, [ceiling.downlight, strip, bulb])

            assert conductor.effect(ceiling.downlight) is effect
            assert conductor.effect(strip) is effect
            assert conductor.effect(bulb) is effect
            assert conductor.effect(ceiling.uplight) is None

            async def all_blue() -> bool:
                tile = await _tile(ceiling)
                zones = await strip.get_all_color_zones()
                colour, _, _ = await bulb.get_color()
                return (
                    tile[:DOWNLIGHT] == [BLUE] * DOWNLIGHT
                    and all(zone == BLUE for zone in zones)
                    and colour == BLUE
                )

            await _eventually(all_blue)
            assert (await _tile(ceiling))[UPLIGHT] == DIM_BLUE
            indices = {ctx.device_index for ctx in effect.contexts}
            assert indices == {0, 1, 2}

            await conductor.remove_lights([ceiling.downlight])

            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT
            assert conductor.effect(strip) is effect

            await conductor.stop([strip, bulb])

            colour, _, _ = await bulb.get_color()
            assert colour == GREEN
            assert await ceiling.get_uplight_color() == DIM_BLUE
