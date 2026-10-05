"""Start and stop effects directly on a light, without a Conductor."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from lifx import Direction, FirmwareEffect
from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.effects.conductor import Conductor
from lifx.effects.frame_effect import FrameContext, FrameEffect

RED = HSBK.from_protocol(HSBK(0, 1, 1, 3500).to_protocol())
GREEN = HSBK.from_protocol(HSBK(120, 1, 1, 3500).to_protocol())
DIM_BLUE = HSBK.from_protocol(HSBK(240, 1, 0.3, 3500).to_protocol())


class _SolidFrames(FrameEffect):
    """Frame effect painting every pixel one colour."""

    def __init__(self, colour: HSBK) -> None:
        super().__init__(power_on=True, fps=20.0)
        self.colour = colour

    @property
    def name(self) -> str:
        return "solid"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        return [self.colour] * ctx.pixel_count


async def _eventually(check: Callable[[], Awaitable[bool]]) -> None:
    for _ in range(50):
        if await check():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("condition never held")


@pytest.mark.emulator
class TestStartAndStopOnALight:
    async def test_start_effect_shows_frames_and_stop_effect_restores(
        self, emulator_devices
    ):
        light = emulator_devices[0]
        async with light:
            await light.set_power(True)
            await light.set_color(DIM_BLUE)

            await light.start_effect(_SolidFrames(RED))

            async def showing_frames() -> bool:
                return (await light.get_color())[0] == RED

            await _eventually(showing_frames)
            await light.stop_effect()

            colour, power, _ = await light.get_color()
            assert colour == DIM_BLUE
            assert power == 65535

    async def test_a_light_runs_one_effect_after_another(self, emulator_devices):
        light = emulator_devices[0]
        async with light:
            await light.set_power(True)
            await light.set_color(DIM_BLUE)

            for colour in (RED, GREEN):
                await light.start_effect(_SolidFrames(colour))

                async def showing(colour: HSBK = colour) -> bool:
                    return (await light.get_color())[0] == colour

                await _eventually(showing)
                await light.stop_effect()

                assert (await light.get_color())[0] == DIM_BLUE

    async def test_stop_effect_stops_a_matrix_firmware_effect(self, emulator_devices):
        matrix = emulator_devices[6]
        async with matrix:
            await matrix.set_effect(FirmwareEffect.FLAME, speed=3.0)
            assert (await matrix.get_effect()).effect_type == FirmwareEffect.FLAME

            await matrix.stop_effect()

            assert (await matrix.get_effect()).effect_type == FirmwareEffect.OFF

    async def test_stop_effect_stops_a_multizone_firmware_effect(
        self, emulator_devices
    ):
        strip = emulator_devices[4]
        async with strip:
            await strip.set_move_effect(Direction.FORWARD, 5.0)
            assert (await strip.get_effect()).effect_type == FirmwareEffect.MOVE

            await strip.stop_effect()

            assert (await strip.get_effect()).effect_type == FirmwareEffect.OFF

    async def test_stop_effect_leaves_a_multi_light_run(self, emulator_devices):
        first, second = emulator_devices[0], emulator_devices[1]
        async with first, second:
            for light in (first, second):
                await light.set_power(True)
                await light.set_color(DIM_BLUE)
            effect = _SolidFrames(RED)
            conductor = Conductor()
            await conductor.start(effect, [first, second])

            async def both_showing_frames() -> bool:
                colours = [(await light.get_color())[0] for light in (first, second)]
                return colours == [RED, RED]

            await _eventually(both_showing_frames)
            await first.stop_effect()
            effect.colour = GREEN

            async def second_showing_new_frames() -> bool:
                return (await second.get_color())[0] == GREEN

            await _eventually(second_showing_new_frames)
            assert (await first.get_color())[0] == DIM_BLUE
            assert conductor.effect(first) is None
            assert conductor.effect(second) is effect

            await second.stop_effect()

            assert (await second.get_color())[0] == DIM_BLUE
            assert conductor.effect(second) is None

    async def test_stop_effect_on_an_idle_light_restores_nothing(
        self, emulator_devices
    ):
        idle, busy = emulator_devices[0], emulator_devices[1]
        async with idle, busy:
            for light in (idle, busy):
                await light.set_power(True)
                await light.set_color(DIM_BLUE)
            conductor = Conductor()
            await conductor.start(_SolidFrames(RED), [busy])
            await idle.set_color(GREEN)

            await idle.stop_effect()

            assert (await idle.get_color())[0] == GREEN
            assert conductor.effect(busy) is not None
            await conductor.stop([busy])


async def test_start_effect_takes_only_software_effects():
    light = Light(serial="d073d5000001", ip="192.0.2.10")

    with pytest.raises(TypeError, match="software effect"):
        await light.start_effect(FirmwareEffect.MORPH)  # type: ignore[arg-type]


@pytest.mark.emulator
async def test_ceiling_gets_its_components_back_after_stop_effect(ceiling_device):
    ceiling = ceiling_device
    async with ceiling:
        await ceiling.set_power(True)
        await ceiling.set_uplight_color(DIM_BLUE)
        await ceiling.set_downlight_colors([GREEN] * 127)
        await asyncio.sleep(0.6)  # let the pending write settle
        tile = (await ceiling.get_all_tile_colors())[0]

        await ceiling.start_effect(_SolidFrames(RED))

        async def showing_frames() -> bool:
            return (await ceiling.get_all_tile_colors())[0] == [RED] * 128

        await _eventually(showing_frames)
        await ceiling.stop_effect()

        assert (await ceiling.get_all_tile_colors())[0] == tile
        assert await ceiling.get_uplight_color() == DIM_BLUE
        assert await ceiling.get_downlight_colors() == [GREEN] * 127
        assert (await ceiling.get_effect()).effect_type == FirmwareEffect.OFF
