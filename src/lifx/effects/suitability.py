"""Shared answers about whether a light suits a kind of software effect.

Each effect still decides through its own ``is_light_compatible()``; the
rules that several effects share live here, so a change to one rule is made
once.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from lifx.devices.mirror import MirrorLight

if TYPE_CHECKING:
    from lifx.devices.light import Light

_T = TypeVar("_T")


def is_mirror(light: Light) -> bool:
    """Whether a light is a Mirror.

    A Mirror is one matrix tile, but its two rings are one-row canvases, so
    the two-dimensional effects (sunrise, sunset, plasma2d) have no sensible
    look on it.

    Args:
        light: The light to check

    Returns:
        True if the light is a Mirror
    """
    return isinstance(light, MirrorLight)


async def draws_a_line(light: Light) -> bool:
    """Whether a light suits a one-dimensional effect.

    A one-dimensional effect draws a single line of pixels, so it suits a
    light that is one: a multizone strip or beam, or a Mirror, whose rings are
    each a line of 25 pixels. This is the rule behind the compatibility check
    of every effect that draws a line, so a future ring product needs one
    change here rather than one per effect.

    Args:
        light: The light to check. Its capabilities are loaded if the answer
            needs them.

    Returns:
        True if the light has multizone capability or is a Mirror
    """
    if is_mirror(light):
        return True
    if light.capabilities is None:
        await light.ensure_capabilities()
    return light.capabilities.has_multizone if light.capabilities else False


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
