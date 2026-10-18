"""Uplight coordinates flow from products.json to ProductInfo."""

from __future__ import annotations

from typing import Any

import pytest

from lifx.products import ProductRegistry, get_product, is_ceiling_product
from lifx.products.generator import (
    generate_product_definitions,
    parse_uplight_coords,
)

CEILING_8X8 = (176, 177, 265, 266)
CEILING_16X8 = (201, 202)


def _vendor() -> dict[str, Any]:
    return {
        "vid": 1,
        "name": "LIFX",
        # Upstream defaults carry an unset (null) uplight_coords.
        "defaults": {"color": True, "uplight_coords": None},
        "products": [
            {"pid": 1, "name": "Plain", "features": {}},
            {
                "pid": 2,
                "name": "Lit",
                "features": {"matrix": True, "uplight_coords": {"x": 7, "y": 7}},
            },
            {
                "pid": 3,
                "name": "Wide",
                "features": {"uplight_coords": {"x": 15, "y": 7}},
            },
        ],
    }


class TestParseUplightCoords:
    def test_absent_is_none(self) -> None:
        assert parse_uplight_coords({}) is None

    def test_null_is_none(self) -> None:
        assert parse_uplight_coords({"uplight_coords": None}) is None

    def test_coordinates_become_a_pair(self) -> None:
        assert parse_uplight_coords({"uplight_coords": {"x": 15, "y": 7}}) == (15, 7)


class TestGeneratorEmitsUplightCoords:
    def test_file_generator_emits_coordinates(self) -> None:
        namespace: dict[str, Any] = {}
        exec(  # noqa: S102
            "from lifx.products.registry import *\n"
            + generate_product_definitions(_vendor()),
            namespace,
        )
        products = namespace["PRODUCTS"]

        assert products[1].uplight_coords is None
        assert products[2].uplight_coords == (7, 7)
        assert products[3].uplight_coords == (15, 7)

    def test_runtime_loader_reads_coordinates(self) -> None:
        registry = ProductRegistry()
        registry.load_from_dict(_vendor())

        assert registry.get_product(1).uplight_coords is None
        assert registry.get_product(2).uplight_coords == (7, 7)
        assert registry.get_product(3).uplight_coords == (15, 7)


class TestShippedRegistry:
    @pytest.mark.parametrize("pid", CEILING_8X8)
    def test_8x8_ceilings(self, pid: int) -> None:
        assert get_product(pid).uplight_coords == (7, 7)

    @pytest.mark.parametrize("pid", CEILING_16X8)
    def test_16x8_ceilings(self, pid: int) -> None:
        assert get_product(pid).uplight_coords == (15, 7)

    def test_other_products_have_none(self) -> None:
        assert get_product(27).uplight_coords is None


class TestIsCeilingProduct:
    @pytest.mark.parametrize("pid", CEILING_8X8 + CEILING_16X8)
    def test_products_with_uplight_coords(self, pid: int) -> None:
        assert is_ceiling_product(pid)

    @pytest.mark.parametrize("pid", [27, 99999])
    def test_known_and_unknown_non_ceilings(self, pid: int) -> None:
        assert not is_ceiling_product(pid)
