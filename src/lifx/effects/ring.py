"""Geometry helpers for effects that draw on a ring of pixels.

A Mirror ring is a line of pixels that closes on itself, so the pixel after the
last is pixel 0. These helpers hold the arithmetic that several effects share
for that closing seam, so each rule is written once.
"""

from __future__ import annotations

from typing import TypeVar

_T = TypeVar("_T")
_N = TypeVar("_N", int, float)


def ring_distance(distance: _N, zone_count: int) -> _N:
    """Measure a distance along a ring the short way round.

    Args:
        distance: Non-negative distance in zones along the ring
        zone_count: Number of zones in the ring

    Returns:
        The shorter of the distance and its complement, so a pixel at zone
        ``zone_count - 1`` is one zone from zone 0
    """
    around = distance % zone_count
    return min(around, zone_count - around)


def ring_offset(offset: float, zone_count: int) -> float:
    """Fold a signed distance along the zones onto the short way round a ring.

    Args:
        offset: Signed distance in zones
        zone_count: Number of zones in the ring

    Returns:
        The equivalent offset in the range ``(-zone_count / 2, zone_count / 2]``
    """
    wrapped = offset % zone_count
    if wrapped > zone_count / 2:
        wrapped -= zone_count
    return wrapped


def ring_index(position: float, zone_count: int, wraps: bool) -> int:
    """Turn a position along the zones into a valid zone index.

    Args:
        position: Position in zones, possibly beyond either end
        zone_count: Number of zones
        wraps: Whether the zones form a ring. A ring wraps the position round
            the seam; anything else clamps it to the nearest end zone.

    Returns:
        A zone index in ``range(zone_count)``
    """
    zone = int(position)
    if wraps:
        return zone % zone_count
    return max(0, min(zone_count - 1, zone))


def fold_at_zone_zero(pixels: list[_T]) -> list[_T]:
    """Mirror a ring's pixels about zone 0 so the pattern meets itself.

    Pixel ``i`` takes the value of pixel ``min(i, n - i)``, its ring distance
    from zone 0, so pixel ``i`` equals pixel ``n - i`` and the last pixel sits
    beside a copy of itself rather than beside a jump.

    Args:
        pixels: One value per pixel, indexed from zone 0

    Returns:
        A new list of the same length, symmetric about zone 0
    """
    n = len(pixels)
    return [pixels[min(i, n - i)] for i in range(n)]
