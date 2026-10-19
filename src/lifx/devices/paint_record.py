"""The record of the theme or mood a light was last painted with.

A light remembers, in memory and per device object, the last whole-light paint
that carried a library slug: whether it was painted as a theme or as a mood,
which slug, and exactly what was written. :class:`PaintTracking` turns that
record into the public ``current_theme`` / ``current_mood`` properties and the
``get_current_*()`` verifiers.

The record lives on :class:`~lifx.devices.light.Light` (``_paint_record``)
so every color write on the class can end it through one hook,
``Light._clear_paint_record()``. A subclass that tracks paints:

- inherits :class:`PaintTracking` ahead of its light base class,
- ends the record after every color or effect write that succeeds, which
  ``Light._zones_changed()`` does through ``_clear_paint_record()`` (a write
  that raises leaves the record for verification to catch),
- calls the matching ``_record_*()`` after the write that paints the whole
  light, so the new record is set once the write has ended the old one, and
- implements ``_verify_paint()`` to read the light and call ``_check_paint()``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from lifx.color import HSBK

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from lifx.effects.base import LIFXEffect
    from lifx.theme.theme import Theme

#: One color as the wire carries it: (hue, saturation, brightness, kelvin).
WireColor = tuple[int, int, int, int]

PaintKind = Literal["theme", "mood"]


def to_wire(color: HSBK) -> WireColor:
    """Quantize a color to the uint16 values the light stores.

    Writes and readings both go through this, so a color that the light
    rounded on its way in compares equal to the color that was written.
    """
    protocol = color.to_protocol()
    return protocol.hue, protocol.saturation, protocol.brightness, protocol.kelvin


@dataclass(frozen=True)
class PaintRecord:
    """What a light was last painted with.

    Attributes:
        kind: Whether the theme was painted as a theme or as a mood
        slug: The theme's library slug
        colors: What was written, per zone for a strip, quantized to uint16.
            Empty for a matrix light.
        tiles: What was written, per tile for a matrix light: each tile's
            pixels in the order the light stores them (after any orientation
            remapping), quantized to uint16. Empty for a strip.

        morph: The palette sent to firmware Morph, quantized to uint16 and
            sorted, so it compares as a multiset. ``None`` unless the record
            is a Morph one.
        run: The software effect running the mood, for a record kept alive by
            a run rather than by colors. ``None`` unless the record is a
            software-run one.
        settles_at: When the paint's fade ends, on ``time.monotonic()``. A
            paint written with a duration is still fading when the write
            returns, and the light reports the in-flight colors until the
            fade ends, as firmware does. A reading taken before this instant
            says nothing about whether the paint still shows. ``0.0`` for a
            paint that landed at once.
    """

    kind: PaintKind
    slug: str
    colors: tuple[WireColor, ...] = ()
    tiles: tuple[tuple[WireColor, ...], ...] = ()
    morph: tuple[WireColor, ...] | None = None
    run: LIFXEffect | None = None
    settles_at: float = 0.0

    def matches_zones(self, zones: Iterable[HSBK]) -> bool:
        """Whether every zone still shows what was written."""
        return tuple(to_wire(zone) for zone in zones) == self.colors

    def matches_tiles(self, tiles: Iterable[Iterable[HSBK]]) -> bool:
        """Whether every pixel of every tile still shows what was written."""
        return tuple(tuple(to_wire(c) for c in tile) for tile in tiles) == self.tiles

    def matches_morph(self, palette: Iterable[HSBK]) -> bool:
        """Whether a Morph palette holds the colors that were sent, in any order."""
        return tuple(sorted(to_wire(c) for c in palette)) == self.morph


class PaintTracking:
    """The public current theme / current mood API for a light that tracks paints.

    Mixed in ahead of the light class. ``_paint_record`` and
    ``_clear_paint_record()`` come from :class:`~lifx.devices.light.Light`.
    """

    _paint_record: PaintRecord | None

    if TYPE_CHECKING:

        def _clear_paint_record(self) -> None: ...

        async def _verify_paint(self) -> None:
            """Read the light and clear the record if it no longer matches."""

    @property
    def current_theme(self) -> str | None:
        """The slug of the theme this light was last painted with as a theme.

        ``None`` when the light was never painted by this object, was painted
        with a theme that has no slug, was painted as a mood, or has been
        written to since. Reads the in-memory record, with no I/O; use
        :meth:`get_current_theme` to confirm the light still shows it.
        """
        record = self._paint_record
        return record.slug if record is not None and record.kind == "theme" else None

    @property
    def current_mood(self) -> str | None:
        """The slug of the theme this light was last painted with as a mood.

        See :attr:`current_theme`.
        """
        record = self._paint_record
        return record.slug if record is not None and record.kind == "mood" else None

    async def get_current_theme(self) -> str | None:
        """Read the light, then return the current theme if it still shows it.

        Every zone must still equal what was painted (uint16 rounding
        allowed). A light that no longer matches has its record cleared.
        The theme is never identified from the light's colors: a paint this
        object did not make reads as ``None``.

        Returns:
            The theme's slug, or ``None``
        """
        await self._verify_paint()
        return self.current_theme

    async def get_current_mood(self) -> str | None:
        """Read the light, then return the current mood if it still shows it.

        See :meth:`get_current_theme`.

        Returns:
            The mood's slug, or ``None``
        """
        await self._verify_paint()
        return self.current_mood

    def _remember(self, kind: PaintKind, theme: Theme, **shape: Any) -> None:
        """Remember a paint, or forget the old one if the theme has no slug."""
        if theme.slug is None:
            self._clear_paint_record()
            return
        self._paint_record = PaintRecord(kind=kind, slug=theme.slug, **shape)

    @staticmethod
    def _settles_at(duration: float) -> float:
        """When a paint written with ``duration`` seconds of fade has landed.

        Taken after the write returns, so the device started its fade no later
        than this and has finished by the instant returned.
        """
        return time.monotonic() + duration if duration > 0 else 0.0

    def _record_paint(
        self,
        kind: PaintKind,
        theme: Theme,
        colors: Iterable[HSBK],
        duration: float = 0.0,
    ) -> None:
        """Remember a whole-light paint, or forget the old one if unslugged.

        ``duration`` is the fade the colors were written with, in seconds.
        """
        self._remember(
            kind,
            theme,
            colors=tuple(to_wire(c) for c in colors),
            settles_at=self._settles_at(duration),
        )

    def _record_tile_paint(
        self,
        kind: PaintKind,
        theme: Theme,
        tiles: Iterable[Iterable[HSBK]],
        duration: float = 0.0,
    ) -> None:
        """Remember a whole-light matrix paint, or forget the old one if unslugged.

        ``tiles`` holds each tile's pixels as the light stores them, and
        ``duration`` is the fade they were written with, in seconds.
        """
        self._remember(
            kind,
            theme,
            tiles=tuple(tuple(to_wire(c) for c in t) for t in tiles),
            settles_at=self._settles_at(duration),
        )

    def _record_morph(
        self, kind: PaintKind, theme: Theme, palette: Iterable[HSBK]
    ) -> None:
        """Remember a firmware Morph started from a theme.

        ``palette`` is the palette actually sent (rescaled to brightness and
        reduced to what Morph carries), never the theme's raw colors.
        """
        self._remember(kind, theme, morph=tuple(sorted(to_wire(c) for c in palette)))

    def _record_run(self, kind: PaintKind, theme: Theme, run: LIFXEffect) -> None:
        """Remember a mood a software effect run is animating.

        The record holds only while ``run`` is the effect running on the light.
        """
        self._remember(kind, theme, run=run)

    def _check_paint(
        self, record: PaintRecord | None, holds: Callable[[PaintRecord], bool]
    ) -> None:
        """Clear ``record`` unless ``holds`` says the light still shows it.

        ``record`` is the one the caller held before it read the light. A paint
        made while the read was in flight is a newer record, and a reading
        taken before it says nothing about it.
        """
        if record is not None and self._paint_record is record and not holds(record):
            self._clear_paint_record()
