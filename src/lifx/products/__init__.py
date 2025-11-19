"""LIFX product registry module.

This module provides product information with capabilities
for LIFX devices.

The product registry is auto-generated from the official LIFX
products.json specification.

To update: run `uv run python -m lifx.products.generator`
"""

from lifx.products.registry import (
    ProductCapability,
    ProductInfo,
    ProductRegistry,
    TemperatureRange,
    get_product,
    get_registry,
)

__all__ = [
    "ProductCapability",
    "ProductInfo",
    "ProductRegistry",
    "TemperatureRange",
    "get_product",
    "get_registry",
]
