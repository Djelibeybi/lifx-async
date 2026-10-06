"""Light component slots on a device's one Animator.

A Ceiling or Mirror has two light components on one tile, and every frame
write replaces the whole tile. The device's Animator therefore keeps one slot
per light component: a software effect on a light component writes frames into
its slot, and the Animator composes every slot into the one tile it sends.

A slot with no effect shows the held tile: the colours the light component had
when the first slot started, retargeted whenever the caller changes that light
component through its existing colour and power methods. The firmware runs
one transition per tile and every frame restarts it, so a fade asked of a held
light component is interpolated here, on the host, across frames.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from lifx.color import HSBK


@dataclass(frozen=True)
class ComponentSlot:
    """Where one light component's frames land on the tile.

    Attributes:
        component: Name of the light component, such as ``"downlight"``
        positions: Buffer positions the light component owns
        sources: For each position, the index in the writer's mapped frame
            that supplies its colour. A cell of the canvas that no position
            reads (the Ceiling downlight's uplight cell) is dropped.
    """

    component: str
    positions: tuple[int, ...]
    sources: tuple[int, ...]


class HeldTile:
    """Colours of the whole tile for light components no effect is drawing."""

    def __init__(self, tile: list[HSBK]) -> None:
        """Hold a tile's current colours, in buffer order."""
        self._target = list(tile)
        self._source = list(tile)
        self._began = 0.0
        self._duration = 0.0
        self._cached: list[tuple[int, int, int, int]] | None = None
        self._version = 0

    @property
    def target(self) -> list[HSBK]:
        """Colours the held tile shows, or is fading towards."""
        return list(self._target)

    @property
    def version(self) -> int:
        """A count that changes whenever the held colours are changed."""
        return self._version

    def remaining(self, now: float) -> float:
        """Seconds left of a fade asked of the held tile, or 0 if none runs."""
        if not self._fading(now):
            return 0.0
        return self._duration - (now - self._began)

    def retarget(self, tile: list[HSBK], duration: float) -> None:
        """Fade from the colours shown now towards a new tile.

        Args:
            tile: New colours for every buffer position
            duration: Fade length in seconds; 0 changes at once
        """
        now = time.monotonic()
        self._source = self._colours_at(now)
        self._target = list(tile)
        self._began = now
        self._duration = max(0.0, duration)
        self._cached = None
        self._version += 1

    def set_cells(self, colours: dict[int, HSBK]) -> None:
        """Show new colours at some positions at once, leaving any fade.

        The other positions keep fading towards their targets over the time
        that remains; only the given positions stop fading.

        Args:
            colours: New colour for each buffer position to change
        """
        for position, colour in colours.items():
            self._source[position] = colour
            self._target[position] = colour
        self._cached = None
        self._version += 1

    def tuples_at(self, now: float) -> list[tuple[int, int, int, int]]:
        """Protocol-ready colours at a moment, part-way through any fade."""
        if self._fading(now):
            return [colour.as_tuple() for colour in self._colours_at(now)]
        if self._cached is None:
            self._cached = [colour.as_tuple() for colour in self._target]
        return list(self._cached)

    def _fading(self, now: float) -> bool:
        return self._duration > 0 and now - self._began < self._duration

    def _colours_at(self, now: float) -> list[HSBK]:
        if not self._fading(now):
            return list(self._target)
        blend = (now - self._began) / self._duration
        return [
            _blend(source, target, blend)
            for source, target in zip(self._source, self._target)
        ]


def _blend(source: HSBK, target: HSBK, blend: float) -> HSBK:
    """Blend hue the short way round, and kelvin as well as H/S/B."""
    if source == target:
        return target
    mixed = source.lerp_hsb(target, blend)
    kelvin = round(source.kelvin + (target.kelvin - source.kelvin) * blend)
    return mixed.with_kelvin(kelvin)
