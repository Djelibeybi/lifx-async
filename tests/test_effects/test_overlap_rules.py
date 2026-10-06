"""Overlap rules between whole-light and light component effects on one light.

A whole-light effect started over light component effects replaces them and
inherits each light component's original prior state. A light component
effect, a light component stop or a caller's light component write during a
whole-light effect moves the whole-light effect onto the other light
component, where it stays, on the canvas it started with.
"""

from __future__ import annotations

import asyncio
import socket
import struct
from collections.abc import Awaitable, Callable, Iterator
from unittest.mock import MagicMock, patch

import pytest

from lifx.color import HSBK
from lifx.devices.ceiling import CeilingLight
from lifx.effects import EffectPulse
from lifx.effects.conductor import Conductor
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.products import get_product
from lifx.protocol import packets
from tests.test_devices import test_component_transitions as transitions

# Set64 colours start after the 36-byte header and the 10-byte payload prefix
# (tile index, length, rect and duration).
_SET64_COLOURS = 36 + 10

FRONT, BACK = 0, 1
BLUE = HSBK.from_protocol(HSBK(240, 1, 0.4, 3500).to_protocol())
GREEN = HSBK.from_protocol(HSBK(120, 1, 0.6, 3500).to_protocol())
AMBER = HSBK.from_protocol(HSBK(40, 0.8, 0.6, 2700).to_protocol())
RED = HSBK.from_protocol(HSBK(0, 1, 1, 3500).to_protocol())
WHITE = HSBK.from_protocol(HSBK(0, 0, 1, 4000).to_protocol())
DIM_BLUE = HSBK.from_protocol(HSBK(240, 1, 0.3, 3500).to_protocol())
VIOLET = HSBK.from_protocol(HSBK(280, 1, 0.8, 3500).to_protocol())

Colour = tuple[int, int, int, int]


class _Zones(FrameEffect):
    """Draws a distinct hue on each zone, recording each frame context."""

    def __init__(self, *, power_on: bool = False) -> None:
        super().__init__(power_on=power_on, fps=50.0)
        self.contexts: list[FrameContext] = []
        self.drawn = asyncio.Event()

    @property
    def name(self) -> str:
        return "zones"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        self.contexts.append(ctx)
        self.drawn.set()
        return [_zone_colour(ctx.device_index, i) for i in range(ctx.pixel_count)]


class _Solid(FrameEffect):
    """Paints every pixel one colour, recording each frame context."""

    def __init__(self, colour: HSBK, *, power_on: bool = False) -> None:
        super().__init__(power_on=power_on, fps=20.0)
        self.colour = colour
        self.contexts: list[FrameContext] = []
        self.drawn = asyncio.Event()

    @property
    def name(self) -> str:
        return "solid"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        self.contexts.append(ctx)
        self.drawn.set()
        return [self.colour] * ctx.pixel_count


class _Counting(FrameEffect):
    """Counts its own frames per participant, drawing the count as a hue."""

    participant_state = ("_count",)

    def __init__(self) -> None:
        super().__init__(power_on=False, fps=20.0)
        self._count = 0
        self.counts: list[int] = []
        self.drawn = asyncio.Event()

    @property
    def name(self) -> str:
        return "counting"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        self._count += 1
        self.counts.append(self._count)
        self.drawn.set()
        return [HSBK(self._count % 360, 1, 0.5, 3500)] * ctx.pixel_count


def _zone_colour(device_index: int, zone: int) -> HSBK:
    return HSBK.from_protocol(
        HSBK(zone * 10 + device_index, 1, 0.5, 3500).to_protocol()
    )


def _zones(device_index: int = 0) -> list[Colour]:
    return [_zone_colour(device_index, k).as_tuple() for k in range(25)]


# Mirror: packet seam and in-memory wire


@pytest.fixture
def udp() -> Iterator[MagicMock]:
    """Capture the Animator's UDP datagrams; no acks ever arrive."""
    with patch.object(socket, "socket") as socket_class:
        sock = MagicMock()
        sock.recvfrom_into.side_effect = BlockingIOError
        socket_class.return_value = sock
        yield sock


@pytest.fixture
def rig(monkeypatch: pytest.MonkeyPatch) -> transitions.Rig:
    return _frozen_rig(267, monkeypatch)


def _frozen_rig(product: int, monkeypatch: pytest.MonkeyPatch) -> transitions.Rig:
    # The rig freezes the component clock, so settle delays must not wait on it.
    for module in ("state_manager", "base", "conductor"):
        for name in (
            "COLOR_UPDATE_SETTLE_DELAY",
            "ZONE_UPDATE_SETTLE_DELAY",
            "POWER_ON_SETTLE_DELAY",
            "POWER_ON_TRANSITION_DURATION",
        ):
            monkeypatch.setattr(f"lifx.effects.{module}.{name}", 0, raising=False)
    rig = transitions.build_rig(product, monkeypatch)
    rig.light._capabilities = get_product(product)
    return rig


def _sent_tiles(udp: MagicMock) -> list[list[Colour]]:
    """Decode every Set64 the Animator sent over its UDP socket."""
    tiles = []
    for call in udp.sendto.call_args_list:
        data = bytes(call.args[0])
        if struct.unpack_from("<H", data, 32)[0] != packets.Tile.Set64.PKT_TYPE:
            continue
        flat = struct.unpack_from("<256H", data, _SET64_COLOURS)
        tiles.append([tuple(flat[i : i + 4]) for i in range(0, 256, 4)])
    return tiles


def _ring(tile: list[Colour], rig: transitions.Rig, side: int) -> list[Colour]:
    """A ring as an effect draws it: clockwise from zone 0, viewed from the front.

    The back ring's zones run anticlockwise, so it is read in reverse from zone 0.
    """
    ring = [tile[p] for p in rig.positions[side]]
    if side == BACK:
        return [ring[-k % len(ring)] for k in range(len(ring))]
    return ring


def _on_wire(rig: transitions.Rig, side: int) -> list[HSBK]:
    return [rig.wire.colours[p] for p in rig.positions[side]]


async def _drawn(effect: _Zones | _Solid) -> None:
    """Wait for the effect's next frame.

    The rig freezes the clock, so the frame loop only wakes when it moves.
    """
    await asyncio.wait_for(effect.drawn.wait(), 1)


async def _next_frame(rig: transitions.Rig, effect: _Zones | _Solid) -> None:
    """Move the frozen clock on so the frame loop draws one more frame.

    No acks arrive, so the step also outlasts the ack gate's probe expiry.
    """
    effect.drawn.clear()
    rig.clock[0] += 2.0
    await _drawn(effect)


async def _amber_front_blue_back(rig: transitions.Rig) -> None:
    await rig.light.set_front_colors(AMBER)
    await rig.light.set_back_colors(BLUE)
    rig.settle()


class TestMirrorOverlapRules:
    async def test_a_whole_light_effect_replaces_ring_effects(
        self, rig: transitions.Rig, udp: MagicMock
    ):
        mirror = rig.light
        await _amber_front_blue_back(rig)
        stored = (rig.colours(FRONT, "stored_"), rig.colours(BACK, "stored_"))
        rings = Conductor()
        front, back = _Solid(GREEN), _Solid(VIOLET)
        await rings.start(front, [mirror.front])
        await _drawn(front)
        await rings.start(back, [mirror.back])
        await _drawn(back)

        whole = _Zones()
        conductor = Conductor()
        await conductor.start(whole, [mirror])
        await _drawn(whole)

        assert rings.effect(mirror.front) is None
        assert rings.effect(mirror.back) is None
        assert conductor.effect(mirror) is whole
        await _next_frame(rig, whole)
        tile = _sent_tiles(udp)[-1]
        # Both rings are the Mirror's one participant, so they match.
        assert _ring(tile, rig, FRONT) == _zones(0)
        assert _ring(tile, rig, BACK) == _zones(0)

        # Stopping it restores what was there before any effect started.
        await conductor.stop([mirror])

        assert _on_wire(rig, FRONT) == [AMBER] * 25
        assert _on_wire(rig, BACK) == [BLUE] * 25
        assert rig.wire.power == 65535
        assert (rig.colours(FRONT, "stored_"), rig.colours(BACK, "stored_")) == stored

    async def test_a_ring_effect_moves_a_whole_light_effect_onto_the_other_ring(
        self, rig: transitions.Rig, udp: MagicMock
    ):
        mirror = rig.light
        await _amber_front_blue_back(rig)
        whole = _Zones()
        conductor = Conductor()
        await conductor.start(whole, [mirror])
        await _drawn(whole)

        back = _Solid(GREEN)
        await mirror.back.start_effect(back)
        await _drawn(back)

        assert conductor.effect(mirror) is None
        assert conductor.effect(mirror.front) is whole
        await _next_frame(rig, whole)
        tile = _sent_tiles(udp)[-1]
        assert _ring(tile, rig, FRONT) == _zones(0)
        assert _ring(tile, rig, BACK) == [GREEN.as_tuple()] * 25
        ctx = whole.contexts[-1]
        assert (ctx.pixel_count, ctx.canvas_width, ctx.wraps) == (25, 25, True)
        assert conductor.get_last_frame(mirror.front) == [
            _zone_colour(0, k) for k in range(25)
        ]

        # The moved effect restores its ring's colours from before it started.
        await mirror.front.stop_effect()

        assert conductor.effect(mirror.front) is None
        assert _on_wire(rig, FRONT) == [AMBER] * 25
        # The back's effect inherited its ring's original prior state too.
        await mirror.back.stop_effect()
        assert _on_wire(rig, BACK) == [BLUE] * 25
        assert _on_wire(rig, FRONT) == [AMBER] * 25

    async def test_a_moved_effect_stays_on_its_ring(
        self, rig: transitions.Rig, udp: MagicMock
    ):
        mirror = rig.light
        await _amber_front_blue_back(rig)
        whole = _Zones()
        conductor = Conductor()
        await conductor.start(whole, [mirror])
        await _drawn(whole)
        front = _Solid(GREEN)
        await mirror.front.start_effect(front)
        await _drawn(front)

        await mirror.front.stop_effect()
        await _next_frame(rig, whole)

        assert conductor.effect(mirror) is None
        assert conductor.effect(mirror.back) is whole
        tile = _sent_tiles(udp)[-1]
        assert _ring(tile, rig, FRONT) == [AMBER.as_tuple()] * 25
        # The back ring keeps the index the Mirror had.
        assert _ring(tile, rig, BACK) == _zones(0)
        assert whole.contexts[-1].pixel_count == 25

        await mirror.back.stop_effect()
        assert _on_wire(rig, BACK) == [BLUE] * 25

    async def test_stopping_a_ring_leaves_the_whole_light_effect_on_the_other(
        self, rig: transitions.Rig, udp: MagicMock
    ):
        mirror = rig.light
        await _amber_front_blue_back(rig)
        whole = _Zones()
        conductor = Conductor()
        await conductor.start(whole, [mirror])
        await _drawn(whole)

        await mirror.front.stop_effect()

        assert conductor.effect(mirror.back) is whole
        assert _on_wire(rig, FRONT) == [AMBER] * 25
        await _next_frame(rig, whole)
        tile = _sent_tiles(udp)[-1]
        assert _ring(tile, rig, FRONT) == [AMBER.as_tuple()] * 25
        # The back ring keeps the index the Mirror had.
        assert _ring(tile, rig, BACK) == _zones(0)

        await conductor.stop([mirror.back])
        assert _on_wire(rig, BACK) == [BLUE] * 25

    async def test_a_ring_write_moves_the_whole_light_effect_onto_the_other_ring(
        self, rig: transitions.Rig, udp: MagicMock
    ):
        mirror = rig.light
        await _amber_front_blue_back(rig)
        whole = _Zones()
        conductor = Conductor()
        await conductor.start(whole, [mirror])
        await _drawn(whole)

        await mirror.set_front_colors(GREEN)
        await _next_frame(rig, whole)

        assert conductor.effect(mirror.back) is whole
        tile = _sent_tiles(udp)[-1]
        assert _ring(tile, rig, FRONT) == [GREEN.as_tuple()] * 25
        assert _ring(tile, rig, BACK) == _zones(0)
        assert rig.colours(FRONT, "stored_") == [GREEN] * 25

        await mirror.back.stop_effect()
        assert _on_wire(rig, BACK) == [BLUE] * 25
        assert _on_wire(rig, FRONT) == [GREEN] * 25

    async def test_a_moved_ring_keeps_its_simulation(
        self, rig: transitions.Rig, udp: MagicMock
    ):
        mirror = rig.light
        await _amber_front_blue_back(rig)
        whole = _Counting()
        conductor = Conductor()
        await conductor.start(whole, [mirror])
        for _ in range(3):
            await _next_frame(rig, whole)
        # Both rings show one count, drawn once a frame.
        front_count = whole.counts[-1]
        assert whole.counts[-3:] == [front_count - 2, front_count - 1, front_count]

        await mirror.back.start_effect(_Solid(GREEN))
        await _next_frame(rig, whole)

        # The front ring carries on counting rather than starting again.
        assert whole.counts[-1] == front_count + 1
        await mirror.front.stop_effect()
        await mirror.back.stop_effect()


async def test_a_moved_ceiling_keeps_its_simulation_beside_other_lights(
    monkeypatch: pytest.MonkeyPatch, udp: MagicMock
):
    first = _frozen_rig(201, monkeypatch)
    # The second rig's clock is the one both lights' frames run on.
    second = _frozen_rig(201, monkeypatch)
    second.light.serial = "d073d5000002"
    conductor = Conductor()
    whole = _Counting()
    await conductor.start(whole, [first.light, second.light])
    for _ in range(3):
        await _next_frame(second, whole)
    # Each light counts its own frames; the second light draws last.
    first_count, second_count = whole.counts[-2:]

    await first.light.downlight.start_effect(_Solid(RED))
    await _next_frame(second, whole)

    # The first light, now on its uplight, and the second carry on counting.
    assert whole.counts[-2:] == [first_count + 1, second_count + 1]
    assert conductor.effect(first.light.uplight) is whole
    await conductor.stop([first.light, second.light])
    await first.light.downlight.stop_effect()


# Ceiling: the embedded emulator

UPLIGHT = 127
DOWNLIGHT = 127  # zones 0-126 of the 16x8 tile


async def _eventually(check: Callable[[], Awaitable[bool]]) -> None:
    for _ in range(50):
        if await check():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("condition never held")


async def _tile(ceiling: CeilingLight) -> list[HSBK]:
    return (await ceiling.get_all_tile_colors())[0]


async def _prepare(ceiling: CeilingLight) -> None:
    """Both components lit in known colours, settled."""
    await ceiling.stop_effect()
    await ceiling.set_power(True)
    await ceiling.set_uplight_color(DIM_BLUE)
    await ceiling.set_downlight_colors([GREEN] * DOWNLIGHT)
    await asyncio.sleep(0.6)  # let the pending write settle


async def _shows(ceiling: CeilingLight, uplight: HSBK, downlight: HSBK) -> None:
    async def check() -> bool:
        tile = await _tile(ceiling)
        return tile[UPLIGHT] == uplight and tile[:DOWNLIGHT] == [downlight] * DOWNLIGHT

    await _eventually(check)


def _counted(effect: _Counting, frames: int) -> Callable[[], Awaitable[bool]]:
    async def check() -> bool:
        return len(effect.counts) >= frames

    return check


@pytest.mark.emulator
class TestCeilingOverlapRules:
    async def test_a_whole_light_effect_replaces_component_effects(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            components = Conductor()
            await components.start(_Solid(RED), [ceiling.uplight])
            await components.start(_Solid(WHITE), [ceiling.downlight])
            await _shows(ceiling, RED, WHITE)

            conductor = Conductor()
            whole = _Solid(VIOLET)
            await conductor.start(whole, [ceiling])

            assert components.effect(ceiling.uplight) is None
            assert components.effect(ceiling.downlight) is None
            await _shows(ceiling, VIOLET, VIOLET)
            for _ in range(5):  # no component effect draws over it
                assert await _tile(ceiling) == [VIOLET] * 128
                await asyncio.sleep(0.05)

            await conductor.stop([ceiling])

            assert await ceiling.get_uplight_color() == DIM_BLUE
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT
            assert ceiling.state.stored_uplight_color == DIM_BLUE
            assert ceiling.state.stored_downlight_colors == [GREEN] * DOWNLIGHT

    async def test_a_whole_light_effect_inherits_a_component_s_dark_light(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.set_power(False)
            await ceiling.uplight.start_effect(_Solid(RED, power_on=True))

            async def uplight_red() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == RED

            await _eventually(uplight_red)
            assert await ceiling.get_power() == 65535

            await ceiling.start_effect(_Solid(VIOLET))
            await _shows(ceiling, VIOLET, VIOLET)
            await ceiling.stop_effect()

            # The light was off before any effect started.
            assert await ceiling.get_power() == 0

    async def test_a_downlight_effect_moves_a_whole_light_effect_to_the_uplight(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            conductor = Conductor()
            whole = _Solid(VIOLET)
            await conductor.start(whole, [ceiling])
            await _shows(ceiling, VIOLET, VIOLET)

            await ceiling.downlight.start_effect(_Solid(RED))

            assert conductor.effect(ceiling) is None
            assert conductor.effect(ceiling.uplight) is whole
            await _shows(ceiling, VIOLET, RED)
            # Its canvas keeps the size it started with.
            ctx = whole.contexts[-1]
            assert (ctx.pixel_count, ctx.canvas_width, ctx.canvas_height) == (
                128,
                16,
                8,
            )

            # Stopping the moved effect restores the uplight's original colour.
            await ceiling.uplight.stop_effect()
            await _shows(ceiling, DIM_BLUE, RED)
            assert await ceiling.get_uplight_color() == DIM_BLUE

            # The downlight effect inherited its original prior state.
            await ceiling.downlight.stop_effect()
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT

    async def test_an_uplight_effect_moves_a_whole_light_effect_to_the_downlight(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            conductor = Conductor()
            whole = _Solid(VIOLET)
            await conductor.start(whole, [ceiling])
            await _shows(ceiling, VIOLET, VIOLET)

            uplight = _Solid(RED)
            await ceiling.uplight.start_effect(uplight)
            await _shows(ceiling, RED, VIOLET)
            assert conductor.effect(ceiling.downlight) is whole

            # The moved effect stays on the downlight after the uplight stops.
            await ceiling.uplight.stop_effect()
            await _shows(ceiling, DIM_BLUE, VIOLET)
            assert conductor.effect(ceiling.downlight) is whole
            assert conductor.effect(ceiling) is None
            ctx = whole.contexts[-1]
            assert (ctx.canvas_width, ctx.canvas_height) == (16, 8)

            await conductor.stop([ceiling.downlight])
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT
            assert await ceiling.get_uplight_color() == DIM_BLUE

    async def test_a_moved_effect_from_a_light_that_was_off_turns_off_again(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.set_power(False)
            conductor = Conductor()
            whole = _Solid(VIOLET, power_on=True)
            await conductor.start(whole, [ceiling])
            await _shows(ceiling, VIOLET, VIOLET)

            await ceiling.uplight.start_effect(_Solid(RED))
            await _shows(ceiling, RED, VIOLET)

            await ceiling.downlight.stop_effect()
            assert not ceiling.downlight_is_on
            assert await ceiling.get_power() == 65535
            await ceiling.uplight.stop_effect()
            assert await ceiling.get_power() == 0

    async def test_stopping_a_component_leaves_the_whole_light_effect_on_the_other(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            conductor = Conductor()
            whole = _Solid(VIOLET)
            await conductor.start(whole, [ceiling])
            await _shows(ceiling, VIOLET, VIOLET)

            await ceiling.downlight.stop_effect()

            assert conductor.effect(ceiling.uplight) is whole
            await _shows(ceiling, VIOLET, GREEN)
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT

            await ceiling.stop_effect()
            assert await ceiling.get_uplight_color() == DIM_BLUE

    async def test_a_component_write_moves_the_whole_light_effect(self, ceiling_device):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            conductor = Conductor()
            whole = _Solid(VIOLET)
            await conductor.start(whole, [ceiling])
            await _shows(ceiling, VIOLET, VIOLET)

            await ceiling.set_uplight_color(AMBER)

            assert conductor.effect(ceiling.downlight) is whole
            await _shows(ceiling, AMBER, VIOLET)
            for _ in range(5):  # later frames keep the write
                assert (await _tile(ceiling))[UPLIGHT] == AMBER
                await asyncio.sleep(0.05)

            await ceiling.stop_effect()
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT
            assert await ceiling.get_uplight_color() == AMBER

    async def test_a_moved_effect_keeps_its_simulation(self, ceiling_device):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            conductor = Conductor()
            whole = _Counting()
            await conductor.start(whole, [ceiling])
            await _eventually(_counted(whole, 3))
            before = whole.counts[-1]

            await ceiling.downlight.start_effect(_Solid(RED))
            whole.drawn.clear()
            await asyncio.wait_for(whole.drawn.wait(), 2)

            # The uplight's frames continue the count rather than restart it.
            assert whole.counts[-1] > before
            await ceiling.stop_effect()

    async def test_stopping_the_light_stops_a_moved_effect(self, ceiling_device):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            conductor = Conductor()
            whole = _Solid(VIOLET)
            await conductor.start(whole, [ceiling])
            await _shows(ceiling, VIOLET, VIOLET)
            downlight = _Solid(RED)
            await conductor.start(downlight, [ceiling.downlight])
            await _shows(ceiling, VIOLET, RED)

            await conductor.stop([ceiling])

            assert conductor.effect(ceiling.uplight) is None
            assert conductor.effect(ceiling.downlight) is None
            assert await ceiling.get_uplight_color() == DIM_BLUE
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT
            for _ in range(5):  # no effect draws on any more
                assert (await _tile(ceiling))[UPLIGHT] == DIM_BLUE
                await asyncio.sleep(0.05)

    async def test_removing_the_light_removes_a_moved_effect(self, ceiling_device):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            conductor = Conductor()
            whole = _Solid(VIOLET)
            await conductor.start(whole, [ceiling])
            await _shows(ceiling, VIOLET, VIOLET)
            await ceiling.set_downlight_colors(WHITE)
            await _shows(ceiling, VIOLET, WHITE)

            await conductor.remove_lights([ceiling])

            assert conductor.effect(ceiling.uplight) is None
            assert await ceiling.get_uplight_color() == DIM_BLUE
            assert await ceiling.get_downlight_colors() == [WHITE] * DOWNLIGHT

    async def test_a_component_effect_takes_the_light_from_a_waveform_effect(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            conductor = Conductor()
            pulse = EffectPulse(mode="breathe", period=5.0, cycles=10)
            await conductor.start(pulse, [ceiling])

            # A caller's write to a light component leaves a waveform alone.
            await ceiling.set_uplight_color(AMBER)
            assert conductor.effect(ceiling) is pulse

            # An effect on a light component cannot share the light with it.
            await ceiling.downlight.start_effect(_Solid(RED))
            assert conductor.effect(ceiling) is None
            assert conductor.effect(ceiling.uplight) is None

            await ceiling.stop_effect()
