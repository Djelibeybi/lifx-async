"""Tests for the hidden-cell table exposed on ProductInfo."""

from __future__ import annotations

import pytest

from lifx.products import get_product
from lifx.products.hidden_cells import HIDDEN_CELL_FAMILIES, hidden_cell_family
from lifx.products.registry import PRODUCTS

CANDLE_PIDS = (57, 67, 68, 81, 96, 137, 138, 185, 186, 187, 188, 215, 216, 217, 218)
CEILING_8X8 = (145, 146, 176, 177, 265, 266)
CEILING_16X8 = (201, 202)
LUNA = (219, 220)


@pytest.mark.parametrize("pid", CANDLE_PIDS)
def test_candle_hides_three_cells(pid: int) -> None:
    product = get_product(pid)
    assert product is not None
    assert product.hidden_zones == frozenset({2, 3, 4})
    assert product.visible_zone_count == 27


@pytest.mark.parametrize("pid", (176, 177, 265, 266))
def test_ceiling_8x8_hides_corners_and_uplight(pid: int) -> None:
    product = get_product(pid)
    assert product is not None
    assert product.hidden_zones == frozenset({0, 1, 6, 7, 56, 57, 62, 63})
    assert product.visible_zone_count == 56


@pytest.mark.parametrize("pid", (*CANDLE_PIDS, *CEILING_8X8, *CEILING_16X8, *LUNA))
def test_table_covers_ids_the_registry_has_not_listed_yet(pid: int) -> None:
    family = hidden_cell_family(pid)
    assert family is not None
    assert pid in family.pids


@pytest.mark.parametrize("pid", CEILING_16X8)
def test_ceiling_16x8_hides_corners_and_uplight(pid: int) -> None:
    product = get_product(pid)
    assert product is not None
    assert product.hidden_zones == frozenset({0, 1, 14, 15, 112, 113, 126, 127})
    assert product.visible_zone_count == 120


@pytest.mark.parametrize("pid", LUNA)
def test_luna_hides_corners(pid: int) -> None:
    product = get_product(pid)
    assert product is not None
    assert product.hidden_zones == frozenset({0, 6, 28, 34})
    assert product.visible_zone_count == 31


@pytest.mark.parametrize("pid", (1, 22, 32, 55, 143, 267, 268))
def test_other_products_hide_nothing(pid: int) -> None:
    product = get_product(pid)
    assert product is not None
    assert product.hidden_zones == frozenset()
    assert product.visible_zone_count is None


def test_ceiling_mask_keeps_the_uplight_addressable() -> None:
    """The uplight is hidden from the surface but never blacked out."""
    ceiling = get_product(201)
    assert ceiling is not None
    assert 127 in ceiling.hidden_zones
    assert ceiling.masked_zones == frozenset({0, 1, 14, 15, 112, 113, 126})
    candle = get_product(57)
    assert candle is not None
    assert candle.masked_zones == candle.hidden_zones


def test_every_family_is_awaiting_hardware_verification() -> None:
    assert {family.verified for family in HIDDEN_CELL_FAMILIES} == {"pending"}


def test_every_candle_in_the_registry_is_in_the_table() -> None:
    candles = {pid for pid, p in PRODUCTS.items() if "Candle" in p.name}
    assert candles
    assert candles <= set(CANDLE_PIDS)
