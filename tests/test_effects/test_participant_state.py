"""Each participant of one frame-effect run keeps its own simulation.

Several effects simulate something over time (embers' heat, Jacob's Ladder's
arcs, a ripple's water). When one run draws on several participants, such as
two lights, each participant must advance its own simulation: drawing
participant B must not change what participant A shows. The two rings of a
whole-light Mirror effect are one participant, so they share one simulation
and show one frame.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.animation.animator import AnimatorStats, AnimatorWriter
from lifx.color import HSBK
from lifx.effects.colorloop import EffectColorloop
from lifx.effects.cylon import EffectCylon
from lifx.effects.embers import EffectEmbers
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.rainbow import EffectRainbow
from lifx.effects.registry import get_effect_registry
from lifx.effects.rule30 import EffectRule30

_TICKS = 40
_SERIAL_A = "d073d5000001"
_SERIAL_B = "d073d5000002"

# Colorloop is left out: it reads each participant's own colour once, at
# setup, and shares one direction across the run by design, so it keeps no
# simulation that a frame advances.
_CASES: list[tuple[str, Callable[[], FrameEffect]]] = [
    *(
        (info.name, cast("Callable[[], FrameEffect]", info.effect_class))
        for info in sorted(get_effect_registry().effects, key=lambda i: i.name)
        if issubclass(info.effect_class, FrameEffect) and info.name != "colorloop"
    ),
    ("rule30-random-seed", lambda: EffectRule30(seed="random")),
]


class _FakeClock:
    """A monotonic clock that only moves when a frame ends."""

    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now


def _writer(
    pixel_count: int,
    frames: list[list[tuple[int, int, int, int]]],
    ring: str | None = None,
) -> MagicMock:
    """A borrowed Animator writer, drawing one ring of a Mirror if ``ring``."""
    if ring is None:
        writer = MagicMock()
    else:
        writer = MagicMock(spec=AnimatorWriter)
        writer.component = ring
        writer.whole_light = True
        writer.shares_tile_with.return_value = False
    writer.pixel_count = pixel_count
    writer.canvas_width = pixel_count
    writer.canvas_height = 1
    writer.wraps = ring is not None
    writer.send_frame.side_effect = frames.append
    return writer


def _light(serial: str) -> MagicMock:
    light = MagicMock()
    light.serial = serial
    light.set_power = AsyncMock()
    return light


async def _frames_of_a(
    effect: FrameEffect,
    b_pixels: int | None,
    monkeypatch: pytest.MonkeyPatch,
    a_first: bool = True,
    rings: bool = False,
) -> list[list[tuple[int, int, int, int]]]:
    """Play the effect and return participant A's frames.

    Every participant's random draws are seeded by its size and tick, so A
    sees the same random numbers whether or not B also draws, and wherever
    A sits in the run. With ``rings``, A and B are the front and back rings
    of one Mirror, as a whole-light Mirror effect draws them.
    """
    clock = _FakeClock()
    monkeypatch.setattr("lifx.effects.frame_effect.time", clock)

    a_frames: list[list[tuple[int, int, int, int]]] = []
    b_frames: list[list[tuple[int, int, int, int]]] = []
    light_a = _light(_SERIAL_A)
    writers = [_writer(16, a_frames, "front" if rings else None)]
    participants = [light_a]
    if b_pixels is not None:
        writers.append(_writer(b_pixels, b_frames, "back" if rings else None))
        participants.append(light_a if rings else _light(_SERIAL_B))
    if not a_first:
        writers.reverse()
        participants.reverse()

    last = writers[-1]
    record = last.send_frame.side_effect
    tick = 0

    def end_frame(frame: list[tuple[int, int, int, int]]) -> None:
        nonlocal tick
        record(frame)
        tick += 1
        clock.now += 1.0 / effect.fps
        if tick >= _TICKS:
            effect.stop()

    last.send_frame.side_effect = end_frame

    generate: Callable[[FrameContext], list[tuple[int, int, int, int]]] = (
        effect.generate_protocol_frame
    )

    def seeded(ctx: FrameContext) -> list[tuple[int, int, int, int]]:
        random.seed(f"{ctx.pixel_count}-{ctx.elapsed_s}")
        return generate(ctx)

    effect.generate_protocol_frame = seeded  # type: ignore[method-assign]
    effect.participants = participants  # type: ignore[assignment]
    effect._animators = writers  # type: ignore[assignment]
    await effect.async_setup(participants)  # type: ignore[arg-type]
    await effect.async_play()
    return a_frames


@pytest.mark.parametrize("a_first", [True, False], ids=["a-first", "a-second"])
@pytest.mark.parametrize("b_pixels", [16, 24], ids=["same-size", "other-size"])
@pytest.mark.parametrize(
    "make_effect", [make for _, make in _CASES], ids=[name for name, _ in _CASES]
)
async def test_a_participant_frames_ignore_other_participants(
    make_effect: Callable[[], FrameEffect],
    b_pixels: int,
    a_first: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Participant A shows the same frames whether or not B also draws."""
    alone = await _frames_of_a(make_effect(), None, monkeypatch)
    together = await _frames_of_a(make_effect(), b_pixels, monkeypatch, a_first=a_first)

    assert len(alone) == _TICKS
    assert together == alone


@pytest.mark.parametrize(
    "make_effect", [make for _, make in _CASES], ids=[name for name, _ in _CASES]
)
async def test_both_rings_of_a_whole_light_mirror_show_one_frame(
    make_effect: Callable[[], FrameEffect],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A whole-light Mirror effect draws its two rings as one participant.

    The effect draws each frame once and both rings show it: they share one
    simulation, which advances once a frame, so a random or stateful effect
    looks as it did on the interim whole-light ring canvas. Every draw gets
    fresh random numbers, as it would on a real run.
    """
    front: list[list[tuple[int, int, int, int]]] = []
    back: list[list[tuple[int, int, int, int]]] = []
    contexts: list[FrameContext] = []
    await _ring_run(
        make_effect(), monkeypatch, front, back, contexts=contexts, seed_calls=True
    )

    assert len(front) == _TICKS
    assert len(contexts) == _TICKS
    assert front == back


async def _ring_run(
    effect: FrameEffect,
    monkeypatch: pytest.MonkeyPatch,
    front: list[list[tuple[int, int, int, int]]],
    back: list[list[tuple[int, int, int, int]]],
    *,
    before: list[list[tuple[int, int, int, int]]] | None = None,
    after: list[list[tuple[int, int, int, int]]] | None = None,
    contexts: list[FrameContext] | None = None,
    move_at: int | None = None,
    seed_calls: bool = False,
) -> None:
    """Play a whole-light Mirror run, optionally between two other lights.

    Random draws are seeded by size and tick, as in ``_frames_of_a()``, or
    with ``seed_calls`` by how many frames the effect has drawn.

    With ``move_at``, the back ring leaves the run at that tick and the front
    ring carries on as a light component, as when an effect starts on the
    back ring.
    """
    clock = _FakeClock()
    monkeypatch.setattr("lifx.effects.frame_effect.time", clock)
    mirror = _light(_SERIAL_A)
    rings = [_writer(16, front, "front"), _writer(16, back, "back")]
    writers: list[MagicMock] = list(rings)
    participants = [mirror, mirror]
    if before is not None:
        writers.insert(0, _writer(16, before))
        participants.insert(0, _light("d073d5000003"))
    if after is not None:
        writers.append(_writer(16, after))
        participants.append(_light(_SERIAL_B))

    last = writers[-1]
    record = last.send_frame.side_effect
    tick = 0

    def end_frame(frame: list[tuple[int, int, int, int]]) -> None:
        nonlocal tick
        record(frame)
        tick += 1
        clock.now += 1.0 / effect.fps
        if tick == move_at:
            idx = effect._animators.index(rings[1])
            del effect._animators[idx]
            del effect.participants[idx]
            rings[0].whole_light = False
            effect._rename_participant(_SERIAL_A, (_SERIAL_A, "front"))
        if tick >= _TICKS:
            effect.stop()

    last.send_frame.side_effect = end_frame

    generate: Callable[[FrameContext], list[tuple[int, int, int, int]]] = (
        effect.generate_protocol_frame
    )
    calls: list[FrameContext] = []

    def seeded(ctx: FrameContext) -> list[tuple[int, int, int, int]]:
        if contexts is not None:
            contexts.append(ctx)
        calls.append(ctx)
        random.seed(len(calls) if seed_calls else f"{ctx.pixel_count}-{ctx.elapsed_s}")
        return generate(ctx)

    effect.generate_protocol_frame = seeded  # type: ignore[method-assign]
    effect.participants = participants  # type: ignore[assignment]
    effect._animators = writers  # type: ignore[assignment]
    await effect.async_setup(participants)  # type: ignore[arg-type]
    await effect.async_play()


async def test_a_whole_light_mirror_takes_one_index_among_other_lights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both rings share the Mirror's index, and later lights keep theirs.

    A spread effect offsets each participant by its index, so the rings match
    and a light after the Mirror is offset as if the Mirror took part once.
    """
    front: list[list[tuple[int, int, int, int]]] = []
    back: list[list[tuple[int, int, int, int]]] = []
    before: list[list[tuple[int, int, int, int]]] = []
    after: list[list[tuple[int, int, int, int]]] = []
    contexts: list[FrameContext] = []
    effect = EffectRainbow(period=10.0, spread=90.0)

    await _ring_run(
        effect, monkeypatch, front, back, before=before, after=after, contexts=contexts
    )

    assert [ctx.device_index for ctx in contexts[:3]] == [0, 1, 2]
    assert len(contexts) == 3 * _TICKS
    assert front == back
    assert front != before
    assert after != front


async def test_unsynchronised_colorloop_paints_both_rings_alike() -> None:
    """Colorloop's spread offsets the Mirror once, not once per ring.

    Both rings share the Mirror's tile, so the front ring stages the step's
    colour and the back ring sends the tile carrying both.
    """
    effect = EffectColorloop(spread=90.0, synchronized=False)
    effect._initial_colors = [HSBK(0, 1, 0.5, 3500), HSBK(0, 1, 0.5, 3500)]
    effect._direction = 1
    staged: list[list[tuple[int, int, int, int]]] = []
    sent: list[list[tuple[int, int, int, int]]] = []
    tile = object()
    front = _writer(25, staged, "front")
    back = _writer(25, sent, "back")
    for ring in (front, back):
        ring.draws_slot = True
        ring.animator = tile
        ring.tile_shared.return_value = False
        ring.slot_deadline.return_value = None
        ring.hold_remaining = 0.0
        ring.hold_version = 0
    front.shares_tile_with.return_value = True
    front.stage.side_effect = lambda frame, settled=False, **_kwargs: (
        staged.append(frame) if settled else None
    )

    def send(frame: list[tuple[int, int, int, int]], **_kwargs: object) -> object:
        sent.append(frame)
        effect.stop()
        return AnimatorStats(packets_sent=1, total_time_ms=0.0)

    back.send_frame.side_effect = send
    mirror = _light(_SERIAL_A)
    effect.participants = [mirror, mirror]
    effect._animators = [front, back]

    await asyncio.wait_for(effect.async_play(), timeout=1.0)

    assert staged[0] == sent[0]


async def test_a_moved_ring_keeps_the_mirror_s_index_and_simulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the back ring leaves, the front ring carries on where it was.

    It keeps the index the Mirror had and the simulation both rings shared,
    so its frames run on as if the run had always drawn that ring alone.
    """
    alone = await _frames_of_a(EffectEmbers(), None, monkeypatch, rings=True)
    front: list[list[tuple[int, int, int, int]]] = []
    back: list[list[tuple[int, int, int, int]]] = []
    after: list[list[tuple[int, int, int, int]]] = []
    contexts: list[FrameContext] = []

    await _ring_run(
        EffectEmbers(),
        monkeypatch,
        front,
        back,
        after=after,
        contexts=contexts,
        move_at=_TICKS // 2,
    )

    assert front == alone
    assert len(back) == _TICKS // 2
    assert [ctx.device_index for ctx in contexts] == [0, 1] * _TICKS


async def test_a_participant_that_rejoins_starts_a_fresh_simulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A participant that leaves a run and joins again keeps no old trail."""
    clock = _FakeClock()
    monkeypatch.setattr("lifx.effects.frame_effect.time", clock)
    effect = EffectCylon(speed=2.0, width=3, trail=0.9)

    a_frames: list[list[tuple[int, int, int, int]]] = []
    b_frames: list[list[tuple[int, int, int, int]]] = []
    c_frames: list[list[tuple[int, int, int, int]]] = []
    a, b, c = _writer(16, a_frames), _writer(16, b_frames), _writer(16, c_frames)
    lights = {a: _light(_SERIAL_A), b: _light(_SERIAL_B), c: _light("d073d5000003")}
    # Ticks 0-9 draw A, C and B; ticks 10-19 only A and B; tick 20 all three.
    # B draws last in every tick, so its frame ends the tick.
    schedule = [[a, c, b]] * 10 + [[a, b]] * 10 + [[a, c, b]]
    tick = 0
    rejoined_at = 0.0

    def end_frame(frame: list[tuple[int, int, int, int]]) -> None:
        nonlocal tick, rejoined_at
        b_frames.append(frame)
        tick += 1
        clock.now += 1.0 / effect.fps
        if tick == len(schedule):
            effect.stop()
            return
        writers = schedule[tick]
        if c in writers:
            rejoined_at = clock.now - 1000.0
        effect._animators = list(writers)  # type: ignore[assignment]
        effect.participants = [lights[w] for w in writers]  # type: ignore[misc]

    b.send_frame.side_effect = end_frame
    effect._animators = list(schedule[0])  # type: ignore[assignment]
    effect.participants = [lights[w] for w in schedule[0]]  # type: ignore[misc]
    await effect.async_play()

    fresh = EffectCylon(speed=2.0, width=3, trail=0.9).generate_protocol_frame(
        FrameContext(
            elapsed_s=rejoined_at,
            device_index=1,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
    )
    assert len(c_frames) == 11
    assert c_frames[-1] == fresh
    assert c_frames[9] != fresh
