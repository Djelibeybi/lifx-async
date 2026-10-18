"""Cells of a matrix product that have no LED.

Candle, Ceiling and Luna firmware accepts a full rectangle of cells, but some
cells have nothing behind them. This hand-maintained table, taken from the
reference lifxlan-go library, lists them per product family. It is not in
products.json.

A hidden cell is a mask, not a reshape: rendering keeps the full rectangle and
the cells are sent as off (brightness 0) when a frame is assembled. Reads and
state restore still cover every cell.

Each family records the date it was verified on the test fleet, by painting a
single bright color and confirming the listed cells show nothing. ``"pending"``
marks a family whose hardware check has not been run yet.

This module must not import the product registry: ``ProductInfo`` imports it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HiddenCellFamily:
    """Hidden cells shared by a family of products.

    Attributes:
        name: Family name
        pids: Product IDs in the family
        width: Cells per row of the family's tile
        height: Rows of the family's tile
        zones: Zone indexes with no LED, in Set64 buffer order
        verified: ISO date of the hardware check, or ``"pending"``
        uplight_zone: Zone index of a Ceiling's uplight, which stays
            addressable, or None
    """

    name: str
    pids: frozenset[int]
    width: int
    height: int
    zones: frozenset[int]
    verified: str
    uplight_zone: int | None = None

    @property
    def visible_zone_count(self) -> int:
        """Cells that have an LED."""
        return self.width * self.height - len(self.zones)

    @property
    def masked_zones(self) -> frozenset[int]:
        """Hidden cells that are sent dark: the hidden set less the uplight."""
        if self.uplight_zone is None:
            return self.zones
        return self.zones - {self.uplight_zone}


HIDDEN_CELL_FAMILIES: tuple[HiddenCellFamily, ...] = (
    HiddenCellFamily(
        name="Candle",
        pids=frozenset(
            {57, 67, 68, 81, 96, 137, 138, 185, 186, 187, 188, 215, 216, 217, 218}
        ),
        width=5,
        height=6,
        zones=frozenset({2, 3, 4}),
        verified="pending",  # filled by the single-bright-color check
    ),
    HiddenCellFamily(
        name="Ceiling 8x8",
        pids=frozenset({145, 146, 176, 177, 265, 266}),
        width=8,
        height=8,
        zones=frozenset({0, 1, 6, 7, 56, 57, 62, 63}),
        verified="pending",  # filled by the single-bright-color check
        uplight_zone=63,
    ),
    HiddenCellFamily(
        name="Ceiling 16x8",
        pids=frozenset({201, 202}),
        width=16,
        height=8,
        zones=frozenset({0, 1, 14, 15, 112, 113, 126, 127}),
        verified="pending",  # filled by the single-bright-color check
        uplight_zone=127,
    ),
    HiddenCellFamily(
        name="Luna",
        pids=frozenset({219, 220}),
        width=7,
        height=5,
        zones=frozenset({0, 6, 28, 34}),
        verified="pending",  # filled by the single-bright-color check
    ),
)

_BY_PID: dict[int, HiddenCellFamily] = {
    pid: family for family in HIDDEN_CELL_FAMILIES for pid in family.pids
}


def hidden_cell_family(pid: int) -> HiddenCellFamily | None:
    """Return the hidden-cell family of a product, or None."""
    return _BY_PID.get(pid)
