"""Software effects on a Mirror's light components, its front and back rings."""

from __future__ import annotations

import asyncio
import socket
import struct
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from lifx.color import HSBK
from lifx.devices.component.participant import LightComponent
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
    # The rig freezes the component clock, so settle delays must not wait on it.
    for module in ("state_manager", "base", "conductor"):
        for name in (
            "COLOR_UPDATE_SETTLE_DELAY",
            "ZONE_UPDATE_SETTLE_DELAY",
            "POWER_ON_SETTLE_DELAY",
            "POWER_ON_TRANSITION_DURATION",
        ):
            monkeypatch.setattr(f"lifx.effects.{module}.{name}", 0, raising=False)
    rig = transitions.build_rig(267, monkeypatch)
    rig.light._capabilities = get_product(267)
    return rig


class _Zones(FrameEffect):
    """Draws a distinct hue on each zone, offset per participant."""

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


def _zone_colour(device_index: int, zone: int) -> HSBK:
    return HSBK.from_protocol(
        HSBK(zone * 10 + device_index, 1, 0.5, 3500).to_protocol()
    )


Colour = tuple[int, int, int, int]


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

    The back ring's zones run anticlockwise, so it is read in reverse, which
    puts back index 24 - k level with front zone k.
    """
    ring = [tile[p] for p in rig.positions[side]]
    if side == BACK:
        return ring[::-1]
    return ring


def _colours(colours: list[HSBK]) -> list[Colour]:
    return [c.as_tuple() for c in colours]


async def _drawn(effect: _Zones) -> None:
    """Wait for the effect's first frame.

    The rig freezes the clock, so the frame loop never wakes for a second one.
    """
    await asyncio.wait_for(effect.drawn.wait(), 1)


async def test_the_rings_are_light_components_with_effect_control(
    rig: transitions.Rig,
):
    mirror = rig.light

    assert isinstance(mirror.front, LightComponent)
    assert isinstance(mirror.back, LightComponent)
    assert mirror.front is mirror.front
    assert mirror.back is not mirror.front
    for ring in (mirror.front, mirror.back):
        assert callable(ring.start_effect)
        assert callable(ring.stop_effect)
        assert ring.animator is mirror.animator


@pytest.mark.parametrize("side", [FRONT, BACK])
async def test_a_ring_effect_draws_its_ring_clockwise_from_zone_0(
    rig: transitions.Rig, udp: MagicMock, side: int
):
    mirror = rig.light
    rig.external(1 - side, BLUE)
    ring = (mirror.front, mirror.back)[side]
    effect = _Zones()

    await ring.start_effect(effect)
    await _drawn(effect)

    ctx = effect.contexts[-1]
    assert (ctx.pixel_count, ctx.canvas_width, ctx.canvas_height) == (25, 25, 1)
    assert ctx.wraps is True
    tile = _sent_tiles(udp)[-1]
    # Zone k of the frame lands on the ring's k-th buffer position.
    assert _ring(tile, rig, side) == _colours([_zone_colour(0, k) for k in range(25)])
    # The other ring keeps its colours.
    assert _ring(tile, rig, 1 - side) == _colours([BLUE] * 25)

    await ring.stop_effect()


async def _next_frame(rig: transitions.Rig, effect: _Zones) -> None:
    """Move the frozen clock on so the frame loop draws one more frame.

    No acks arrive, so the step also outlasts the ack gate's probe expiry.
    """
    effect.drawn.clear()
    rig.clock[0] += 2.0
    await asyncio.wait_for(effect.drawn.wait(), 1)


async def test_the_idle_ring_stays_under_the_callers_control(
    rig: transitions.Rig, udp: MagicMock
):
    mirror = rig.light
    effect = _Zones()
    await mirror.front.start_effect(effect)
    await _drawn(effect)

    await mirror.set_back_colors(GREEN)
    await _next_frame(rig, effect)

    tile = _sent_tiles(udp)[-1]
    assert _ring(tile, rig, BACK) == _colours([GREEN] * 25)
    assert _ring(tile, rig, FRONT) == _colours([_zone_colour(0, k) for k in range(25)])
    # The change survives later frames.
    await _next_frame(rig, effect)
    assert _ring(_sent_tiles(udp)[-1], rig, BACK) == _colours([GREEN] * 25)

    await mirror.front.stop_effect()

    assert [rig.wire.colours[p] for p in rig.positions[BACK]] == [GREEN] * 25
    assert [rig.wire.colours[p] for p in rig.positions[FRONT]] == [transitions.RED] * 25
    assert rig.colours(BACK, "stored_") == [GREEN] * 25
    # The front ring had no stored colours before its effect, and has none now.
    assert rig.colours(FRONT, "stored_") is None


async def test_a_ring_returns_to_its_colours_and_leaves_the_other_ring(
    rig: transitions.Rig, udp: MagicMock
):
    mirror = rig.light
    await mirror.set_front_colors(AMBER)
    await mirror.set_back_colors(BLUE)
    rig.settle()
    effect = _Zones()
    await mirror.back.start_effect(effect)
    await _drawn(effect)

    await mirror.back.stop_effect()

    assert [rig.wire.colours[p] for p in rig.positions[BACK]] == [BLUE] * 25
    assert [rig.wire.colours[p] for p in rig.positions[FRONT]] == [AMBER] * 25
    assert rig.wire.power == 65535
    assert rig.colours(BACK, "stored_") == [BLUE] * 25


async def test_a_ring_dark_before_its_effect_goes_dark_again(
    rig: transitions.Rig, udp: MagicMock
):
    mirror = rig.light
    await mirror.set_back_colors(BLUE)
    await mirror.turn_front_off()
    rig.settle()
    effect = _Zones()
    await mirror.front.start_effect(effect)
    await _drawn(effect)

    await mirror.front.stop_effect()

    assert all(rig.wire.colours[p].brightness == 0 for p in rig.positions[FRONT])
    assert [rig.wire.colours[p] for p in rig.positions[BACK]] == [BLUE] * 25
    assert rig.wire.power == 65535
    assert mirror.front_is_on is False
    assert rig.colours(FRONT, "stored_") == [transitions.RED] * 25


async def test_a_ring_effect_on_a_light_that_is_off_lights_only_that_ring(
    rig: transitions.Rig, udp: MagicMock
):
    mirror = rig.light
    await mirror.set_back_colors(BLUE)
    await mirror.set_power(False)
    rig.settle()
    effect = _Zones(power_on=True)

    await mirror.front.start_effect(effect)
    await _drawn(effect)

    assert rig.wire.power == 65535
    # Brightness inference lit the front from its stored colours, the back is dark.
    assert [rig.wire.colours[p] for p in rig.positions[FRONT]] == [transitions.RED] * 25
    assert all(rig.wire.colours[p].brightness == 0 for p in rig.positions[BACK])
    tile = _sent_tiles(udp)[-1]
    assert all(colour[2] == 0 for colour in _ring(tile, rig, BACK))

    await mirror.front.stop_effect()

    assert rig.wire.power == 0
    assert rig.colours(BACK, "stored_") == [BLUE] * 25


async def test_a_write_to_the_animating_ring_stops_its_effect_first(
    rig: transitions.Rig, udp: MagicMock
):
    mirror = rig.light
    conductor = Conductor()
    effect = _Zones()
    await conductor.start(effect, [mirror.front])
    await _drawn(effect)

    await mirror.set_front_colors(AMBER)

    assert conductor.effect(mirror.front) is None
    assert [rig.wire.colours[p] for p in rig.positions[FRONT]] == [AMBER] * 25
    assert rig.colours(FRONT, "stored_") == [AMBER] * 25


async def test_two_effects_run_one_on_each_ring(rig: transitions.Rig, udp: MagicMock):
    mirror = rig.light
    await mirror.set_front_colors(AMBER)
    rig.settle()
    front, back = _Zones(), _Zones()
    await mirror.front.start_effect(front)
    await _drawn(front)
    await mirror.back.start_effect(back)
    await _drawn(back)

    await mirror.front.stop_effect()
    await _next_frame(rig, back)

    # The back's effect carries on, and its frames carry the restored front.
    tile = _sent_tiles(udp)[-1]
    assert _ring(tile, rig, FRONT) == _colours([AMBER] * 25)
    assert _ring(tile, rig, BACK) == _colours([_zone_colour(0, k) for k in range(25)])
    await mirror.back.stop_effect()
    assert [rig.wire.colours[p] for p in rig.positions[FRONT]] == [AMBER] * 25
    assert [rig.wire.colours[p] for p in rig.positions[BACK]] == [transitions.RED] * 25
