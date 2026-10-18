"""Vendor defaults merge and upstream commit stamps in the product generator."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from lifx._upstream import UpstreamCommit
from lifx.products import ProductCapability, ProductRegistry
from lifx.products.generator import (
    generate_product_definitions,
    generate_registry_file,
    main,
)

STAMP = UpstreamCommit(
    "abc123def456abc123def456abc123def456abcd", "2026-03-04T05:06:07Z"
)


def _vendor() -> dict[str, Any]:
    return {
        "vid": 1,
        "name": "LIFX",
        # Flat defaults, as upstream spells them.
        "defaults": {
            "color": True,
            "hev": False,
            "temperature_range": [2500, 9000],
        },
        "products": [
            {"pid": 1, "name": "Inherits", "features": {"infrared": True}},
            {
                "pid": 2,
                "name": "Overrides",
                "features": {"color": False, "temperature_range": [1500, 4000]},
            },
            {"pid": 3, "name": "Nullable", "features": {"temperature_range": None}},
        ],
    }


class TestFlatDefaultsMerge:
    def test_load_from_dict_inherits_vendor_defaults(self) -> None:
        registry = ProductRegistry()
        registry.load_from_dict(_vendor())

        inherits = registry.get_product(1)
        assert inherits.has_capability(ProductCapability.COLOR)
        assert inherits.has_capability(ProductCapability.INFRARED)
        assert inherits.temperature_range is not None
        assert (inherits.temperature_range.min, inherits.temperature_range.max) == (
            2500,
            9000,
        )

    def test_load_from_dict_product_overrides_defaults(self) -> None:
        registry = ProductRegistry()
        registry.load_from_dict(_vendor())

        overrides = registry.get_product(2)
        assert not overrides.has_capability(ProductCapability.COLOR)
        assert overrides.temperature_range is not None
        assert overrides.temperature_range.max == 4000

    def test_load_from_dict_null_temperature_range_is_none(self) -> None:
        registry = ProductRegistry()
        registry.load_from_dict(_vendor())

        assert registry.get_product(3).temperature_range is None

    def test_file_generator_inherits_vendor_defaults(self) -> None:
        code = generate_product_definitions(_vendor())
        namespace: dict[str, Any] = {}
        exec(  # noqa: S102
            "from lifx.products.registry import *\n" + code, namespace
        )
        products = namespace["PRODUCTS"]

        assert products[1].has_capability(ProductCapability.COLOR)
        assert products[1].temperature_range.max == 9000
        assert not products[2].has_capability(ProductCapability.COLOR)
        assert products[2].temperature_range.max == 4000
        assert products[3].temperature_range is None

    def test_nested_features_defaults_still_merge(self) -> None:
        vendor = _vendor()
        vendor["defaults"] = {"features": {"color": True}}
        registry = ProductRegistry()
        registry.load_from_dict(vendor)

        assert registry.get_product(1).has_capability(ProductCapability.COLOR)


class TestRegistryStamp:
    def test_header_carries_commit_and_timestamp(self) -> None:
        code = generate_registry_file(_vendor(), STAMP)

        assert STAMP.sha in code
        assert STAMP.date in code

    def test_header_unknown_without_a_lookup(self) -> None:
        code = generate_registry_file(_vendor())

        assert "unknown" in code.split('"""', 2)[1]

    def test_main_stamps_registry_with_looked_up_commit(self, tmp_path: Any) -> None:
        captured: dict[str, Any] = {}

        def fake_registry(data: Any, upstream: UpstreamCommit) -> str:
            captured["upstream"] = upstream
            return "x = 1\n"

        with (
            patch("lifx.products.generator.download_products", return_value=_vendor()),
            patch(
                "lifx.products.generator.fetch_upstream_commit", return_value=STAMP
            ) as fetch,
            patch("lifx.products.generator.generate_registry_file", fake_registry),
            patch("lifx.products.generator.format_generated_files"),
            patch("builtins.open", create=True),
        ):
            main()

        assert captured["upstream"] == STAMP
        assert fetch.call_args.args[0] == "LIFX/products"
