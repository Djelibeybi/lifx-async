"""Each participant of one frame-effect run keeps its own simulation.

Several effects simulate something over time (embers' heat, Jacob's Ladder's
arcs, a ripple's water). When one run draws on several participants, such as
two lights or the two rings of a whole-light Mirror effect, each participant
must advance its own simulation: drawing participant B must not change what
participant A shows.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.animation.animator import AnimatorWriter
from lifx.effects.cylon import EffectCylon
from lifx.effects.frame_effect import FrameContext, FrameEffect
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
        writer._shares_tile_with.return_value = False
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


@pytest.mark.parametrize("a_first", [True, False], ids=["front-first", "back-first"])
@pytest.mark.parametrize(
    "make_effect", [make for _, make in _CASES], ids=[name for name, _ in _CASES]
)
async def test_a_mirror_ring_frames_ignore_the_other_ring(
    make_effect: Callable[[], FrameEffect],
    a_first: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A whole-light Mirror effect draws each ring as if it drew that ring alone.

    Both rings belong to one light, so each ring's simulation is keyed by its
    light component as well as the light.
    """
    alone = await _frames_of_a(make_effect(), None, monkeypatch, rings=True)
    together = await _frames_of_a(
        make_effect(), 16, monkeypatch, a_first=a_first, rings=True
    )

    assert len(alone) == _TICKS
    assert together == alone


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
