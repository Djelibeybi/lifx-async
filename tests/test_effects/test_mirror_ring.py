"""Whole-light software effects on a Mirror draw on its two rings, which wrap."""

from __future__ import annotations

import asyncio
import socket
import struct
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from lifx.animation.animator import Animator
from lifx.color import HSBK
from lifx.effects.colorloop import EffectColorloop
from lifx.effects.conductor import Conductor
from lifx.effects.cylon import EffectCylon
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.rainbow import EffectRainbow
from lifx.effects.spin import EffectSpin
from lifx.products import get_product
from lifx.protocol import packets
from lifx.protocol.base import Packet
from lifx.theme import Theme
from tests.test_devices import test_component_transitions as transitions
from tests.test_effects.test_ring_helpers import RING, advances_one_zone, ring_ctx

# Set64 colours start after the 36-byte header and the 10-byte payload prefix
# (tile index, length, rect and duration).
_SET64_COLOURS = 36 + 10


@pytest.fixture
def udp() -> Iterator[MagicMock]:
    """Capture the Animator's UDP datagrams; no acks ever arrive."""
    with patch.object(socket, "socket") as socket_class:
        sock = MagicMock()
        sock.recvfrom_into.side_effect = BlockingIOError
        socket_class.return_value = sock
        yield sock


@pytest.fixture
def mirror_rig(monkeypatch) -> transitions.Rig:
    return _rig(267, monkeypatch)


def _rig(product: int, monkeypatch: pytest.MonkeyPatch) -> transitions.Rig:
    # The rig freezes time.monotonic, so settle delays must not use the timer.
    for module in ("state_manager", "base"):
        for name in (
            "COLOR_UPDATE_SETTLE_DELAY",
            "ZONE_UPDATE_SETTLE_DELAY",
            "POWER_ON_SETTLE_DELAY",
        ):
            monkeypatch.setattr(f"lifx.effects.{module}.{name}", 0, raising=False)
    rig = transitions.build_rig(product, monkeypatch)
    rig.light._capabilities = get_product(product)
    return rig


class _Recording(FrameEffect):
    """Frame effect that records its context and draws one hue per zone."""

    def __init__(self, *, power_on: bool = False) -> None:
        super().__init__(power_on=power_on, fps=50.0)
        self.contexts: list[FrameContext] = []
        self.drawn = asyncio.Event()

    @property
    def name(self) -> str:
        return "recording"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        self.contexts.append(ctx)
        self.drawn.set()
        return [HSBK(i * 10, 1, 0.5, 3500) for i in range(ctx.pixel_count)]

    async def from_poweroff_hsbk(self, _light) -> HSBK:
        return HSBK(0, 0, 0, 3500)


async def _one_frame(rig: transitions.Rig) -> _Recording:
    conductor = Conductor()
    effect = _Recording()
    await conductor.start(effect, [rig.light])
    await asyncio.wait_for(effect.drawn.wait(), 1)
    await conductor.stop([rig.light])
    return effect


def _sent_tiles(udp: MagicMock) -> list[list[tuple[int, int, int, int]]]:
    """Decode every Set64 the Animator sent over its UDP socket."""
    tiles = []
    for call in udp.sendto.call_args_list:
        data = bytes(call.args[0])
        pkt_type = struct.unpack_from("<H", data, 32)[0]
        if pkt_type != packets.Tile.Set64.PKT_TYPE:
            continue
        flat = struct.unpack_from("<256H", data, _SET64_COLOURS)
        tiles.append([tuple(flat[i : i + 4]) for i in range(0, 256, 4)])
    return tiles


async def test_whole_light_effect_on_a_mirror_runs_as_two_ring_participants(
    mirror_rig: transitions.Rig, udp: MagicMock
):
    rig = mirror_rig
    conductor = Conductor()
    effect = _Recording()

    await conductor.start(effect, [rig.light])
    await asyncio.wait_for(effect.drawn.wait(), 1)

    # Each ring is drawn by a writer of its own on 25 pixels clockwise from
    # zone 0 that wrap, but both rings are the Mirror's one participant: the effect
    # draws one frame, at the Mirror's index, and both rings show it.
    (ctx,) = effect.contexts
    assert ctx.device_index == 0
    assert (ctx.pixel_count, ctx.canvas_width, ctx.canvas_height) == (25, 25, 1)
    assert ctx.wraps is True
    assert [w.component for w in effect._animators] == ["front", "back"]

    # One tile per frame carries the frame on each ring's positions, and the
    # two chipless positions stay dark, as on the interim ring canvas.
    (sent,) = _sent_tiles(udp)
    frame = [HSBK(i * 10, 1, 0.5, 3500).as_tuple() for i in range(25)]
    front, back = rig.positions
    assert [sent[p] for p in front] == frame
    # The back ring's zones run the other way round, so it takes the frame
    # reversed (pixel k on back index 24 - k, level with front zone k) and both
    # rings turn clockwise together.
    assert [sent[back[24 - k]] for k in range(25)] == frame
    chipless = set(range(52)) - set(front) - set(back)
    assert len(chipless) == 2
    assert all(rig.wire.colours[p].brightness > 0 for p in chipless)
    assert all(sent[p][2] == 0 for p in chipless)

    # It is still one whole-light run.
    assert conductor.effect(rig.light) is effect
    assert conductor.effect(rig.light.front) is None
    last = conductor.get_last_frame(rig.light)
    assert last is not None
    assert [c.as_tuple() for c in last] == frame + frame

    await conductor.stop([rig.light])

    assert conductor.effect(rig.light) is None


async def test_a_whole_light_mirror_effect_restores_the_whole_tile(
    mirror_rig: transitions.Rig, udp: MagicMock
):
    rig = mirror_rig
    mirror = rig.light
    await mirror.set_front_colors(transitions.GREEN)
    await mirror.set_back_colors(transitions.BLUE)
    await mirror.set_power(False)
    rig.settle()
    tile = list(rig.wire.colours)
    stored = (rig.colours(0, "stored_"), rig.colours(1, "stored_"))
    conductor = Conductor()
    effect = _Recording(power_on=True)

    rig.wire.packets.clear()

    async def take_turns(_packet: Packet) -> None:
        # Real replies take time, so concurrent requests interleave.
        await asyncio.sleep(0)

    rig.wire.before = take_turns
    await conductor.start(effect, [mirror])
    await asyncio.wait_for(effect.drawn.wait(), 1)
    # The light powers on once, with no colour written first.
    assert rig.wire.power == 65535
    sent = [type(packet) for packet in rig.wire.packets]
    assert sent.count(packets.Light.SetPower) == 1
    assert packets.Light.SetColor not in sent
    assert packets.Tile.Set64 not in sent
    await conductor.stop([mirror])

    assert rig.wire.colours == tile
    assert rig.wire.power == 0
    assert (rig.colours(0, "stored_"), rig.colours(1, "stored_")) == stored


async def test_a_mirror_leaving_a_run_takes_both_rings_with_it(
    mirror_rig: transitions.Rig, monkeypatch: pytest.MonkeyPatch, udp: MagicMock
):
    rig = mirror_rig
    other = _rig(267, monkeypatch)
    other.light.serial = "d073d5000002"
    conductor = Conductor()
    effect = _Recording()
    await conductor.start(effect, [rig.light, other.light])
    await asyncio.wait_for(effect.drawn.wait(), 1)
    assert len(effect._animators) == 4

    await conductor.remove_lights([rig.light])

    assert effect.participants == [other.light, other.light]
    assert [w.component for w in effect._animators] == ["front", "back"]
    assert conductor.effect(other.light) is effect
    await conductor.stop([other.light])


async def test_whole_light_effect_on_a_ceiling_does_not_wrap(
    monkeypatch: pytest.MonkeyPatch, udp: MagicMock
):
    rig = _rig(201, monkeypatch)
    effect = await _one_frame(rig)

    ctx = effect.contexts[0]
    assert (ctx.canvas_width, ctx.canvas_height) == (16, 8)
    assert ctx.wraps is False


# Ring-aware effects. A ring has no ends: zone 24 sits next to zone 0, so a
# pattern that circulates must look the same one zone further on, and the
# step from zone 24 to zone 0 must be no bigger than any other step.


def _hue_gap(a: float, b: float) -> float:
    gap = abs(a - b) % 360
    return min(gap, 360 - gap)


def _visibly_same(a: HSBK, b: HSBK) -> bool:
    return (
        _hue_gap(a.hue, b.hue) <= 1
        and abs(a.saturation - b.saturation) < 0.01
        and abs(a.brightness - b.brightness) < 0.01
        and a.kelvin == b.kelvin
    )


THEME = Theme([HSBK(0, 1, 0.8, 3500), HSBK(120, 1, 0.8, 3500), HSBK(240, 1, 0.8, 3500)])


def test_spin_circulates_round_a_ring_without_a_seam():
    effect = EffectSpin(speed=10.0, theme=THEME, bulb_offset=0.0)
    before = effect.generate_frame(ring_ctx(1.0))
    after = effect.generate_frame(ring_ctx(1.0 + 10.0 / RING))

    # Palette position rises with the zone, so the frame one zone-time later
    # is the frame moved one zone back.
    assert advances_one_zone(before, after, -1, _visibly_same)


def test_spin_shimmer_has_no_jump_where_the_ring_closes():
    effect = EffectSpin(theme=Theme([HSBK(0, 1, 0.8, 3500)]), bulb_offset=5.0)
    frame = effect.generate_frame(ring_ctx(0.0))

    gaps = [_hue_gap(frame[i].hue, frame[(i + 1) % RING].hue) for i in range(RING)]
    assert max(gaps) <= 5 + 1


def test_spin_on_a_strip_is_unchanged():
    effect = EffectSpin(theme=Theme([HSBK(0, 1, 0.8, 3500)]), bulb_offset=5.0)
    frame = effect.generate_frame(ring_ctx(0.0, wraps=False))

    # The shimmer climbs 5 degrees a zone from one end to the other.
    assert [round(c.hue) for c in frame] == [i * 5 for i in range(RING)]


def test_cylon_eye_bounces_on_a_ring_as_on_a_strip():
    ring = EffectCylon(speed=2.0, width=3, trail=0.6)
    strip = EffectCylon(speed=2.0, width=3, trail=0.6)
    for f in range(80):
        t = f / 20
        assert ring.generate_frame(ring_ctx(t)) == strip.generate_frame(
            ring_ctx(t, wraps=False)
        )


def test_cylon_eye_turns_at_zone_0_on_a_ring():
    effect = EffectCylon(speed=2.0, width=3, trail=0.0)
    frame = effect.generate_frame(ring_ctx(0.0))

    # The eye starts on zone 0 and lights nothing across the seam.
    assert frame[0].brightness == pytest.approx(0.8)
    assert frame[1].brightness > 0
    assert frame[RING - 1].brightness == 0


def test_cylon_on_a_strip_still_bounces_off_the_ends():
    effect = EffectCylon(speed=2.0, width=3, trail=0.0)
    start = effect.generate_frame(ring_ctx(0.0, wraps=False))
    middle = effect.generate_frame(ring_ctx(1.0, wraps=False))

    assert start[0].brightness == pytest.approx(0.8)
    assert start[RING - 1].brightness == 0
    assert middle[RING - 1].brightness == pytest.approx(0.8)


def test_rainbow_circulates_round_a_ring_without_a_seam():
    effect = EffectRainbow(period=10.0)
    before = effect.generate_frame(ring_ctx(1.0))
    after = effect.generate_frame(ring_ctx(1.0 + 10.0 / RING))

    assert advances_one_zone(before, after, -1, _visibly_same)
    # The step from the last zone back to the first matches every other step.
    gaps = [_hue_gap(before[i].hue, before[(i + 1) % RING].hue) for i in range(RING)]
    assert max(gaps) - min(gaps) <= 1
    assert effect.generate_frame(ring_ctx(1.0, wraps=False)) == before


async def test_colorloop_paints_the_whole_ring_one_colour(
    mirror_rig: transitions.Rig,
):
    effect = EffectColorloop(period=10.0)
    await effect.async_setup([mirror_rig.light])
    frame = effect.generate_frame(ring_ctx(2.0))

    assert len(frame) == RING
    assert len(set(frame)) == 1
    assert effect.generate_frame(ring_ctx(2.0, wraps=False)) == frame


async def test_an_effect_borrows_the_light_s_own_animator(
    mirror_rig: transitions.Rig, udp: MagicMock
):
    rig = mirror_rig
    with pytest.warns(DeprecationWarning):
        ledfx = await Animator.for_matrix(rig.light)
    conductor = Conductor()
    effect = _Recording()

    await conductor.start(effect, [rig.light])
    await asyncio.wait_for(effect.drawn.wait(), 1)
    writers = list(effect._animators)
    await conductor.stop([rig.light])

    # One Animator and one ack gate: both rings drew through LedFx's Animator,
    # which still exposes the raw tile and stays open after the effect.
    assert len(writers) == 2
    assert all(writer.animator is ledfx is rig.light.animator for writer in writers)
    assert ledfx.pixel_count == 52
    assert udp.close.call_count == 0


async def test_a_mirror_added_to_a_run_joins_as_both_rings(
    mirror_rig: transitions.Rig, monkeypatch: pytest.MonkeyPatch, udp: MagicMock
):
    rig = mirror_rig
    other = _rig(267, monkeypatch)
    other.light.serial = "d073d5000002"
    conductor = Conductor()
    effect = _Recording()
    await conductor.start(effect, [other.light])
    await asyncio.wait_for(effect.drawn.wait(), 1)

    await conductor.add_lights(effect, [rig.light])

    assert effect.participants == [other.light] * 2 + [rig.light] * 2
    assert [w.component for w in effect._animators] == ["front", "back"] * 2
    assert conductor.effect(rig.light) is effect
    await conductor.stop([other.light, rig.light])


async def test_each_whole_light_mirror_takes_one_index_in_a_run(
    mirror_rig: transitions.Rig, monkeypatch: pytest.MonkeyPatch, udp: MagicMock
):
    """Two Mirrors in one run are participants 0 and 1, not 0 to 3."""
    rig = mirror_rig
    other = _rig(267, monkeypatch)
    other.light.serial = "d073d5000002"
    conductor = Conductor()
    effect = _Recording()

    await conductor.start(effect, [other.light, rig.light])
    await asyncio.wait_for(effect.drawn.wait(), 1)
    await conductor.stop([other.light, rig.light])

    assert [ctx.device_index for ctx in effect.contexts[:2]] == [0, 1]


async def test_colorloop_sets_up_each_whole_light_mirror_once(
    mirror_rig: transitions.Rig, monkeypatch: pytest.MonkeyPatch, udp: MagicMock
):
    """Setup sees each participant once, so its colours line up with indices."""
    rig = mirror_rig
    other = _rig(267, monkeypatch)
    other.light.serial = "d073d5000002"
    conductor = Conductor()
    effect = EffectColorloop(spread=90.0, synchronized=False)
    seen: list[list[object]] = []
    setup = effect.async_setup

    async def record_setup(participants) -> None:
        seen.append(list(participants))
        await setup(participants)

    effect.async_setup = record_setup  # type: ignore[method-assign]
    await conductor.start(effect, [other.light, rig.light])
    await conductor.stop([other.light, rig.light])

    assert seen == [[other.light, rig.light]]
    assert len(effect._initial_colors) == 2


class _Protocol(_Recording):
    """Draws protocol tuples directly, so it keeps no HSBK frames."""

    def generate_protocol_frame(self, ctx: FrameContext) -> list[tuple[int, ...]]:
        self.drawn.set()
        return [(0, 0, 0, 3500)] * ctx.pixel_count


async def test_a_mirror_has_no_last_frame_from_an_effect_that_keeps_none(
    mirror_rig: transitions.Rig, udp: MagicMock
):
    rig = mirror_rig
    conductor = Conductor()
    effect = _Protocol()
    await conductor.start(effect, [rig.light])
    await asyncio.wait_for(effect.drawn.wait(), 1)

    assert conductor.get_last_frame(rig.light) is None
    await conductor.stop([rig.light])
