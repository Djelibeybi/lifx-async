"""Start and stop effects directly on a light, without a Conductor."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from lifx import Direction, FirmwareEffect
from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.effects.base import LIFXEffect
from lifx.effects.conductor import Conductor
from lifx.effects.frame_effect import FrameContext, FrameEffect

RED = HSBK.from_protocol(HSBK(0, 1, 1, 3500).to_protocol())
GREEN = HSBK.from_protocol(HSBK(120, 1, 1, 3500).to_protocol())
WHITE = HSBK.from_protocol(HSBK(0, 0, 1, 4000).to_protocol())
DIM_BLUE = HSBK.from_protocol(HSBK(240, 1, 0.3, 3500).to_protocol())


class _SolidFrames(FrameEffect):
    """Frame effect painting every pixel one colour."""

    def __init__(self, colour: HSBK) -> None:
        super().__init__(power_on=True, fps=20.0)
        self.colour = colour
        self.frames = 0

    @property
    def name(self) -> str:
        return "solid"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        self.frames += 1
        return [self.colour] * ctx.pixel_count


async def _stopped_drawing(effect: _SolidFrames) -> bool:
    """True if the effect draws no frame over a few frame intervals."""
    frames = effect.frames
    await asyncio.sleep(0.3)
    return effect.frames == frames


class _FollowOnFrames(_SolidFrames):
    """Solid frames that take over another solid run's prior state."""

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        return isinstance(other, _SolidFrames)


async def _shows(light: Light, colour: HSBK) -> bool:
    return (await light.get_color())[0] == colour


async def _keeps_showing(light: Light, colour: HSBK) -> None:
    """Fail if any read over about half a second shows another colour.

    The reads are spaced out of step with the 20 fps frames, so a second
    writer cannot hide between them.
    """
    for _ in range(30):
        assert (await light.get_color())[0] == colour
        await asyncio.sleep(0.017)


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

    async def test_a_new_effect_replaces_the_running_one(self, emulator_devices):
        light = emulator_devices[0]
        async with light:
            await light.set_power(True)
            await light.set_color(DIM_BLUE)
            first = _SolidFrames(RED)
            await light.start_effect(first)
            await _eventually(lambda: _shows(light, RED))

            await light.start_effect(_FollowOnFrames(GREEN))

            assert await _stopped_drawing(first)
            await _eventually(lambda: _shows(light, GREEN))
            await _keeps_showing(light, GREEN)
            await light.stop_effect()
            assert (await light.get_color())[0] == DIM_BLUE
            await asyncio.sleep(0.3)
            assert (await light.get_color())[0] == DIM_BLUE

    async def test_a_replacement_that_does_not_inherit_still_replaces(
        self, emulator_devices
    ):
        light = emulator_devices[0]
        async with light:
            await light.set_power(True)
            await light.set_color(DIM_BLUE)
            conductor = Conductor()
            first = _SolidFrames(RED)
            await conductor.start(first, [light])
            await _eventually(lambda: _shows(light, RED))

            await conductor.start(_SolidFrames(GREEN), [light])

            assert await _stopped_drawing(first)
            await _eventually(lambda: _shows(light, GREEN))
            await _keeps_showing(light, GREEN)
            await conductor.stop([light])

    async def test_start_effect_takes_one_light_out_of_a_shared_run(
        self, emulator_devices
    ):
        first, second = emulator_devices[0], emulator_devices[1]
        async with first, second:
            for light in (first, second):
                await light.set_power(True)
                await light.set_color(DIM_BLUE)
            shared = _SolidFrames(RED)
            conductor = Conductor()
            await conductor.start(shared, [first, second])
            await _eventually(lambda: _shows(first, RED))

            await first.start_effect(_FollowOnFrames(GREEN))
            shared.colour = WHITE

            await _eventually(lambda: _shows(first, GREEN))
            await _eventually(lambda: _shows(second, WHITE))
            await _keeps_showing(first, GREEN)
            assert conductor.effect(first) is None
            assert conductor.effect(second) is shared

            await first.stop_effect()
            assert (await first.get_color())[0] == DIM_BLUE
            await _eventually(lambda: _shows(second, WHITE))
            await conductor.stop([second])
            assert (await second.get_color())[0] == DIM_BLUE

    async def test_add_lights_takes_a_light_out_of_its_old_run(self, emulator_devices):
        first, second = emulator_devices[0], emulator_devices[1]
        async with first, second:
            for light in (first, second):
                await light.set_power(True)
                await light.set_color(DIM_BLUE)
            old = _SolidFrames(RED)
            await second.start_effect(old)
            shared = _FollowOnFrames(GREEN)
            conductor = Conductor()
            await conductor.start(shared, [first])
            await _eventually(lambda: _shows(second, RED))

            await conductor.add_lights(shared, [first, second])

            assert await _stopped_drawing(old)
            await _eventually(lambda: _shows(second, GREEN))
            assert conductor.effect(first) is shared
            assert conductor.effect(second) is shared

            await conductor.stop([first, second])
            for light in (first, second):
                assert (await light.get_color())[0] == DIM_BLUE

    async def test_add_lights_to_an_effect_that_is_not_running_changes_nothing(
        self, emulator_devices
    ):
        light = emulator_devices[0]
        async with light:
            await light.set_power(True)
            await light.set_color(DIM_BLUE)
            old = _SolidFrames(RED)
            await light.start_effect(old)

            await Conductor().add_lights(_FollowOnFrames(GREEN), [light])

            assert not await _stopped_drawing(old)
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
