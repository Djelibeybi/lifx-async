"""Shared helpers for the tests that drive a software effect on a Mirror ring.

A ring is a one-row canvas of 25 pixels that wraps, so each test drives an
effect's ``generate_frame()`` with a ``FrameContext`` built here, once for a
ring and once for a strip of the same length.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from lifx.color import HSBK
from lifx.effects.frame_effect import FrameContext, FrameEffect

RING = 25
FPS = 20


def ring_ctx(elapsed_s: float, wraps: bool = True, pixels: int = RING) -> FrameContext:
    """Context for a one-row canvas of ``pixels`` pixels that may wrap."""
    return FrameContext(
        elapsed_s=elapsed_s,
        device_index=0,
        pixel_count=pixels,
        canvas_width=pixels,
        canvas_height=1,
        wraps=wraps,
    )


def draw_frames(
    effect: FrameEffect, count: int, wraps: bool, pixels: int = RING
) -> list[list[HSBK]]:
    """Frames drawn at ``FPS`` frames a second."""
    return [
        effect.generate_frame(ring_ctx(f / FPS, wraps, pixels)) for f in range(count)
    ]


def as_tuples(frame: list[HSBK]) -> list[tuple[float, float, float, int]]:
    """A frame as plain ``(hue, saturation, brightness, kelvin)`` tuples."""
    return [(c.hue, c.saturation, c.brightness, c.kelvin) for c in frame]


def tuple_frames(
    effect: FrameEffect, wraps: bool, count: int = 60, pixels: int = RING
) -> list[list[tuple[float, float, float, int]]]:
    """Frames drawn at ``FPS`` frames a second, as plain tuples."""
    return [as_tuples(frame) for frame in draw_frames(effect, count, wraps, pixels)]


def brightness(drawn: list[list[HSBK]]) -> list[list[float]]:
    """The brightness of every pixel of every frame."""
    return [[c.brightness for c in frame] for frame in drawn]


def strip_digest(effect: FrameEffect, count: int) -> str:
    """SHA-256 of ``count`` frames drawn on a non-wrapping strip.

    It hashes the protocol values each frame puts on the wire, not the raw
    floats, because the platform maths library can differ in the last bit of a
    float, which would change a float digest without changing what a light shows.
    """
    digest = hashlib.sha256()
    for frame in draw_frames(effect, count, wraps=False):
        digest.update(repr([colour.as_tuple() for colour in frame]).encode())
    return digest.hexdigest()


def advances_one_zone(
    before: list[HSBK],
    after: list[HSBK],
    step: int,
    same: Callable[[HSBK, HSBK], bool],
) -> bool:
    """True if ``after`` is ``before`` moved ``step`` zones round the ring.

    ``same`` decides when two pixels count as the same colour.
    """
    n = len(before)
    return all(same(after[i], before[(i - step) % n]) for i in range(n))
