"""The record of the theme or mood a light was last painted with.

A light remembers, in memory and per device object, the last whole-light paint
that carried a library slug: whether it was painted as a theme or as a mood,
which slug, and exactly what was written. :class:`PaintTracking` turns that
record into the public ``current_theme`` / ``current_mood`` properties and the
``get_current_*()`` verifiers.

The record lives on :class:`~lifx.devices.light.Light` (``_paint_record``)
so every colour write on the class can end it through one hook,
``Light._clear_paint_record()``. A subclass that tracks paints:

- inherits :class:`PaintTracking` ahead of its light base class,
- calls ``_clear_paint_record()`` at the top of every colour or effect write,
- calls ``_record_paint()`` after the write that paints the whole light, and
- implements ``_verify_paint()`` to read the light and call ``_check_paint()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from lifx.color import HSBK

if TYPE_CHECKING:
    from collections.abc import Iterable

    from lifx.theme.theme import Theme

#: One colour as the wire carries it: (hue, saturation, brightness, kelvin).
WireColour = tuple[int, int, int, int]

PaintKind = Literal["theme", "mood"]


def to_wire(colour: HSBK) -> WireColour:
    """Quantise a colour to the uint16 values the light stores.

    Writes and readings both go through this, so a colour that the light
    rounded on its way in compares equal to the colour that was written.
    """
    protocol = colour.to_protocol()
    return protocol.hue, protocol.saturation, protocol.brightness, protocol.kelvin


@dataclass(frozen=True)
class PaintRecord:
    """What a light was last painted with.

    Attributes:
        kind: Whether the theme was painted as a theme or as a mood
        slug: The theme's library slug
        colours: What was written, per zone for a strip, quantised to uint16.
            Later tickets add the fields a matrix light and Morph need beside
            it.
    """

    kind: PaintKind
    slug: str
    colours: tuple[WireColour, ...] = ()

    def matches_zones(self, zones: Iterable[HSBK]) -> bool:
        """Whether every zone still shows what was written."""
        return tuple(to_wire(zone) for zone in zones) == self.colours


class PaintTracking:
    """The public current theme / current mood API for a light that tracks paints.

    Mixed in ahead of the light class. ``_paint_record`` and
    ``_clear_paint_record()`` come from :class:`~lifx.devices.light.Light`.
    """

    _paint_record: PaintRecord | None

    if TYPE_CHECKING:

        def _clear_paint_record(self) -> None: ...

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
        The theme is never identified from the light's colours: a paint this
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

    def _record_paint(
        self,
        kind: PaintKind,
        theme: Theme,
        colours: Iterable[HSBK],
    ) -> None:
        """Remember a whole-light paint, or forget the old one if unslugged."""
        if theme.slug is None:
            self._clear_paint_record()
            return
        self._paint_record = PaintRecord(
            kind=kind, slug=theme.slug, colours=tuple(to_wire(c) for c in colours)
        )

    async def _verify_paint(self) -> None:
        """Read the light and clear the record if it no longer matches."""
        raise NotImplementedError  # pragma: no cover - supplied by the light

    def _check_paint(self, record: PaintRecord | None, zones: Iterable[HSBK]) -> None:
        """Clear ``record`` if ``zones`` differ from it.

        ``record`` is the one the caller held before it read the light. A paint
        made while the read was in flight is a newer record, and a reading
        taken before it says nothing about it.
        """
        if (
            record is not None
            and self._paint_record is record
            and not record.matches_zones(zones)
        ):
            self._clear_paint_record()
