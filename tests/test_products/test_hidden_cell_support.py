"""Test helper: what a tile looks like once its hidden cells are sent dark."""

from __future__ import annotations

from typing import TypeVar

from lifx.color import HSBK
from lifx.products import get_product

T = TypeVar("T", tuple[int, int, int, int], HSBK)


def darkened(tile: list[T], pid: int) -> list[T]:
    """Return ``tile`` with the product's masked cells at brightness 0.

    Accepts protocol tuples or HSBK values and keeps hue, saturation and kelvin.
    """
    product = get_product(pid)
    assert product is not None
    out = list(tile)
    for index in product.masked_zones:
        cell = out[index]
        if isinstance(cell, HSBK):
            out[index] = HSBK(cell.hue, cell.saturation, 0.0, cell.kelvin)  # type: ignore[assignment]
        else:
            out[index] = (cell[0], cell[1], 0, cell[3])  # type: ignore[assignment]
    return out
