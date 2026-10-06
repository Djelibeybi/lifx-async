"""Shared answers about whether a light suits a kind of software effect.

Each effect still decides through its own ``is_light_compatible()``; the
rules that several effects share live here, so a change to one rule is made
once.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lifx.devices.mirror import MirrorLight

if TYPE_CHECKING:
    from lifx.devices.light import Light


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
