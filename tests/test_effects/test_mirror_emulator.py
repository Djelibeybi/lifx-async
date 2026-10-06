"""Software effects on a Mirror, checked against what the emulated Mirror reports.

The Mirror is one 4x13 tile carrying two 25-zone rings. Every assertion reads
the light back over the wire: the rings through ``get_front_colors()`` and
``get_back_colors()``, the whole tile through Get64, and the power level.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from lifx.color import HSBK
from lifx.devices.mirror import MirrorLight
from lifx.effects import EffectCylon, EffectRainbow, EffectTwinkle
from lifx.effects.conductor import Conductor
from lifx.effects.frame_effect import FrameContext, FrameEffect

RED = HSBK.from_protocol(HSBK(0, 1, 1, 3500).to_protocol())
GREEN = HSBK.from_protocol(HSBK(120, 1, 0.6, 3500).to_protocol())
WHITE = HSBK.from_protocol(HSBK(0, 0, 1, 4000).to_protocol())
BLUE = HSBK.from_protocol(HSBK(240, 1, 0.4, 3500).to_protocol())
AMBER = HSBK.from_protocol(HSBK(40, 0.8, 0.6, 2700).to_protocol())
VIOLET = HSBK.from_protocol(HSBK(280, 1, 0.8, 3500).to_protocol())

RING = 25


class _Solid(FrameEffect):
    """Paints every pixel one colour, recording each frame context."""

    def __init__(self, colour: HSBK, *, power_on: bool = True) -> None:
        super().__init__(power_on=power_on, fps=20.0)
        self.colour = colour
        self.contexts: list[FrameContext] = []

    @property
    def name(self) -> str:
        return "solid"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        self.contexts.append(ctx)
        return [self.colour] * ctx.pixel_count


class _Zones(FrameEffect):
    """Draws a distinct hue on each pixel, so zone order is visible."""

    def __init__(self) -> None:
        super().__init__(power_on=True, fps=20.0)
        self.contexts: list[FrameContext] = []

    @property
    def name(self) -> str:
        return "zones"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        self.contexts.append(ctx)
        return [_zone_colour(k) for k in range(ctx.pixel_count)]


def _zone_colour(zone: int) -> HSBK:
    return HSBK.from_protocol(HSBK(zone * 10, 1, 0.5, 3500).to_protocol())


ZONES = [_zone_colour(k) for k in range(RING)]
# The same frame on the back ring, whose zones run the other way round: it is
# drawn clockwise, so back index k shows frame pixel RING - 1 - k, which puts it
# level with front zone RING - 1 - k.
BACK_ZONES = [ZONES[RING - 1 - k] for k in range(RING)]


async def _eventually(check: Callable[[], Awaitable[bool]]) -> None:
    for _ in range(50):
        if await check():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("condition never held")


async def _tile(mirror: MirrorLight) -> list[HSBK]:
    return (await mirror.get_all_tile_colors())[0]


async def _rings(mirror: MirrorLight) -> tuple[list[HSBK], list[HSBK]]:
    """The front and back rings as the tile reports them, in zone order."""
    tile = await _tile(mirror)
    return (
        [tile[p] for p in mirror.front_positions],
        [tile[p] for p in mirror.back_positions],
    )


async def _shows(
    mirror: MirrorLight, front: HSBK | list[HSBK], back: HSBK | list[HSBK]
) -> None:
    want_front = front if isinstance(front, list) else [front] * RING
    want_back = back if isinstance(back, list) else [back] * RING

    async def check() -> bool:
        return await _rings(mirror) == (want_front, want_back)

    await _eventually(check)


async def _holds(
    mirror: MirrorLight, front: HSBK | list[HSBK], back: HSBK | list[HSBK]
) -> None:
    """Later frames keep showing the same picture."""
    want_front = front if isinstance(front, list) else [front] * RING
    want_back = back if isinstance(back, list) else [back] * RING
    for _ in range(5):
        assert await _rings(mirror) == (want_front, want_back)
        await asyncio.sleep(0.05)


def _dark(colours: list[HSBK]) -> bool:
    return all(colour.brightness == 0 for colour in colours)


async def _prepare(mirror: MirrorLight) -> None:
    """Both rings lit in known colours, settled.

    These tests are about ring behaviour, not placement, so frame pixel k lands
    on front zone k.
    """
    mirror.ring_origin = 0
    await mirror.stop_effect()
    await mirror.set_power(True)
    await mirror.set_front_colors(AMBER)
    await mirror.set_back_colors(BLUE)
    await asyncio.sleep(0.6)  # let the pending write settle


@pytest.mark.emulator
class TestMirrorRingEffects:
    async def test_the_emulator_reports_a_mirror(self, mirror_device):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)

            assert mirror.version is not None
            assert mirror.version.product == 267
            assert await mirror.get_front_colors() == [AMBER] * RING
            assert await mirror.get_back_colors() == [BLUE] * RING
            assert await _rings(mirror) == ([AMBER] * RING, [BLUE] * RING)

    async def test_a_whole_light_effect_restores_the_tile_and_both_rings(
        self, mirror_device
    ):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)
            before = await _tile(mirror)
            stored = (mirror.state.stored_front_colors, mirror.state.stored_back_colors)
            effect = _Zones()

            await mirror.start_effect(effect)

            # Both rings are one participant, drawn clockwise round each.
            await _shows(mirror, ZONES, BACK_ZONES)
            ctx = effect.contexts[-1]
            assert (ctx.pixel_count, ctx.canvas_width, ctx.canvas_height) == (
                RING,
                RING,
                1,
            )
            assert ctx.wraps

            await mirror.stop_effect()

            assert await _tile(mirror) == before
            assert await mirror.get_front_colors() == [AMBER] * RING
            assert await mirror.get_back_colors() == [BLUE] * RING
            assert await mirror.get_power() == 65535
            assert (
                mirror.state.stored_front_colors,
                mirror.state.stored_back_colors,
            ) == stored

    async def test_a_front_effect_leaves_the_back_under_the_callers_control(
        self, mirror_device
    ):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)
            effect = _Zones()

            await mirror.front.start_effect(effect)
            await _shows(mirror, ZONES, BLUE)
            ctx = effect.contexts[-1]
            assert (ctx.pixel_count, ctx.canvas_width, ctx.canvas_height) == (
                RING,
                RING,
                1,
            )

            await mirror.set_back_colors(GREEN)
            await _shows(mirror, ZONES, GREEN)
            await _holds(mirror, ZONES, GREEN)

            await mirror.turn_back_off()

            async def back_dark() -> bool:
                return _dark((await _rings(mirror))[1])

            await _eventually(back_dark)
            assert not mirror.back_is_on
            assert await mirror.get_power() == 65535
            assert (await _rings(mirror))[0] == ZONES

            await mirror.turn_back_on()
            await _shows(mirror, ZONES, GREEN)

            await mirror.front.stop_effect()

            assert await mirror.get_front_colors() == [AMBER] * RING
            assert await mirror.get_back_colors() == [GREEN] * RING
            assert mirror.state.stored_back_colors == [GREEN] * RING

    async def test_each_ring_runs_its_own_effect_and_stops_alone(self, mirror_device):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)

            await mirror.front.start_effect(_Solid(RED))
            await mirror.back.start_effect(_Solid(WHITE))
            await _shows(mirror, RED, WHITE)
            await _holds(mirror, RED, WHITE)

            await mirror.back.stop_effect()

            # Only the back returns; the front effect carries on.
            await _shows(mirror, RED, BLUE)
            await _holds(mirror, RED, BLUE)
            assert await mirror.get_back_colors() == [BLUE] * RING

            await mirror.front.stop_effect()

            assert await mirror.get_front_colors() == [AMBER] * RING
            assert await mirror.get_back_colors() == [BLUE] * RING
            assert await mirror.get_power() == 65535

    async def test_a_conductor_stopping_one_ring_leaves_the_other_drawing(
        self, mirror_device
    ):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)
            conductor = Conductor()
            effect = _Solid(RED)
            await conductor.start(effect, [mirror.front, mirror.back])
            try:
                await _shows(mirror, RED, RED)

                await conductor.stop([mirror.front])

                assert conductor.effect(mirror.front) is None
                assert conductor.effect(mirror.back) is effect
                await _shows(mirror, AMBER, RED)
                await _holds(mirror, AMBER, RED)
            finally:
                # Leave nothing running for the next test on this Mirror.
                await conductor.stop([mirror])

            assert await mirror.get_front_colors() == [AMBER] * RING
            assert await mirror.get_back_colors() == [BLUE] * RING

    async def test_a_chain_of_replaced_effects_restores_the_starting_picture(
        self, mirror_device
    ):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)
            for effect in (EffectCylon(), EffectRainbow(), EffectTwinkle()):
                # Each whole-light effect replaces the one before it.
                await mirror.start_effect(effect)
                await asyncio.sleep(0.5)

            await mirror.stop_effect()

            assert await mirror.get_front_colors() == [AMBER] * RING
            assert await mirror.get_back_colors() == [BLUE] * RING
            assert mirror.state.stored_front_colors == [AMBER] * RING
            assert mirror.state.stored_back_colors == [BLUE] * RING

    async def test_a_ring_dark_before_its_effect_goes_dark_again(self, mirror_device):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)
            await mirror.turn_back_off()
            await mirror.back.start_effect(_Solid(RED))
            await _shows(mirror, AMBER, RED)

            await mirror.back.stop_effect()

            front, back = await _rings(mirror)
            assert _dark(back)
            assert front == [AMBER] * RING
            assert not mirror.back_is_on
            assert mirror.front_is_on
            assert await mirror.get_power() == 65535
            assert mirror.state.stored_back_colors == [BLUE] * RING

            await mirror.turn_back_on()

            assert await mirror.get_back_colors() == [BLUE] * RING

    async def test_a_ring_effect_on_a_light_that_is_off_lights_only_that_ring(
        self, mirror_device
    ):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)
            await mirror.set_power(False)

            await mirror.front.start_effect(_Solid(RED))

            assert await mirror.get_power() == 65535
            assert mirror.front_is_on
            assert not mirror.back_is_on

            async def front_red() -> bool:
                return (await _rings(mirror))[0] == [RED] * RING

            await _eventually(front_red)
            for _ in range(5):  # the back stays dark under the frames
                assert _dark((await _rings(mirror))[1])
                await asyncio.sleep(0.05)

            await mirror.front.stop_effect()

            assert await mirror.get_power() == 0
            assert not mirror.front_is_on
            assert not mirror.back_is_on
            assert mirror.state.stored_front_colors == [AMBER] * RING
            assert mirror.state.stored_back_colors == [BLUE] * RING

            # Powering the light on shows the whole picture from before the
            # effect: the back ring the effect's turn-on darkened comes back too.
            await mirror.set_power(True)

            assert await _rings(mirror) == ([AMBER] * RING, [BLUE] * RING)
            assert mirror.state.stored_front_colors == [AMBER] * RING
            assert mirror.state.stored_back_colors == [BLUE] * RING

    async def test_a_write_to_the_animating_ring_stops_its_effect_first(
        self, mirror_device
    ):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)
            conductor = Conductor()
            await conductor.start(_Solid(RED), [mirror.front])
            await _shows(mirror, RED, BLUE)

            await mirror.set_front_colors(WHITE)

            assert conductor.effect(mirror.front) is None
            await _holds(mirror, WHITE, BLUE)  # no later frame overwrites it
            assert await mirror.get_front_colors() == [WHITE] * RING
            assert mirror.state.stored_front_colors == [WHITE] * RING


@pytest.mark.emulator
class TestMirrorOverlapRules:
    async def test_a_whole_light_effect_replaces_ring_effects(self, mirror_device):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)
            rings = Conductor()
            await rings.start(_Solid(RED), [mirror.front])
            await rings.start(_Solid(WHITE), [mirror.back])
            await _shows(mirror, RED, WHITE)

            conductor = Conductor()
            whole = _Solid(VIOLET)
            await conductor.start(whole, [mirror])

            assert rings.effect(mirror.front) is None
            assert rings.effect(mirror.back) is None
            assert conductor.effect(mirror) is whole
            await _shows(mirror, VIOLET, VIOLET)
            await _holds(mirror, VIOLET, VIOLET)  # no ring effect draws over it

            await conductor.stop([mirror])

            # It restores what was there before any effect started.
            assert await mirror.get_front_colors() == [AMBER] * RING
            assert await mirror.get_back_colors() == [BLUE] * RING
            assert await mirror.get_power() == 65535
            assert mirror.state.stored_front_colors == [AMBER] * RING
            assert mirror.state.stored_back_colors == [BLUE] * RING

    async def test_a_back_effect_moves_a_whole_light_effect_onto_the_front(
        self, mirror_device
    ):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)
            conductor = Conductor()
            whole = _Zones()
            await conductor.start(whole, [mirror])
            await _shows(mirror, ZONES, BACK_ZONES)

            await mirror.back.start_effect(_Solid(RED))

            assert conductor.effect(mirror) is None
            assert conductor.effect(mirror.front) is whole
            await _shows(mirror, ZONES, RED)
            await _holds(mirror, ZONES, RED)
            ctx = whole.contexts[-1]
            assert (ctx.pixel_count, ctx.canvas_width, ctx.wraps) == (RING, RING, True)

            # The moved effect restores its ring's colours from before it started.
            await mirror.front.stop_effect()
            await _shows(mirror, AMBER, RED)

            # The back's effect inherited its ring's original prior state too.
            await mirror.back.stop_effect()
            assert await mirror.get_front_colors() == [AMBER] * RING
            assert await mirror.get_back_colors() == [BLUE] * RING

    async def test_a_front_effect_moves_a_whole_light_effect_onto_the_back(
        self, mirror_device
    ):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)
            conductor = Conductor()
            whole = _Solid(VIOLET)
            await conductor.start(whole, [mirror])
            await _shows(mirror, VIOLET, VIOLET)

            await mirror.front.start_effect(_Solid(RED))
            await _shows(mirror, RED, VIOLET)
            assert conductor.effect(mirror.back) is whole

            # The moved effect stays on the back after the front stops.
            await mirror.front.stop_effect()
            await _shows(mirror, AMBER, VIOLET)
            await _holds(mirror, AMBER, VIOLET)
            assert conductor.effect(mirror.back) is whole
            assert conductor.effect(mirror) is None

            await conductor.stop([mirror.back])
            assert await mirror.get_back_colors() == [BLUE] * RING
            assert await mirror.get_front_colors() == [AMBER] * RING

    async def test_a_ring_write_moves_a_whole_light_effect_onto_the_other_ring(
        self, mirror_device
    ):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)
            conductor = Conductor()
            whole = _Solid(VIOLET)
            await conductor.start(whole, [mirror])
            await _shows(mirror, VIOLET, VIOLET)

            await mirror.set_front_colors(GREEN)

            assert conductor.effect(mirror.back) is whole
            await _shows(mirror, GREEN, VIOLET)
            await _holds(mirror, GREEN, VIOLET)
            assert mirror.state.stored_front_colors == [GREEN] * RING

            await mirror.back.stop_effect()
            assert await mirror.get_back_colors() == [BLUE] * RING
            assert await mirror.get_front_colors() == [GREEN] * RING

    async def test_a_moved_effect_from_a_light_that_was_off_turns_off_again(
        self, mirror_device
    ):
        mirror = mirror_device
        async with mirror:
            await _prepare(mirror)
            await mirror.set_power(False)
            conductor = Conductor()
            await conductor.start(_Solid(VIOLET), [mirror])
            await _shows(mirror, VIOLET, VIOLET)
            assert await mirror.get_power() == 65535

            await mirror.front.start_effect(_Solid(RED))
            await _shows(mirror, RED, VIOLET)

            await mirror.back.stop_effect()
            assert not mirror.back_is_on
            assert await mirror.get_power() == 65535
            await mirror.front.stop_effect()
            assert await mirror.get_power() == 0
