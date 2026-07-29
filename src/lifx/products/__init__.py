"""LIFX product registry module.

This module provides product information with capabilities
for LIFX devices.

The product registry is auto-generated from the official LIFX
products.json specification.

To update: run `uv run python -m lifx.products.generator`
"""

from lifx.products.quirks import (
    SKY_EFFECT_MIN_FIRMWARE_MAJOR,
    CeilingComponentLayout,
    get_ceiling_layout,
    is_ceiling_product,
    supports_sky_effect,
)
from lifx.products.registry import (
    ProductCapability,
    ProductInfo,
    ProductRegistry,
    TemperatureRange,
    get_product,
    get_registry,
)

__all__ = [
    "SKY_EFFECT_MIN_FIRMWARE_MAJOR",
    "CeilingComponentLayout",
    "ProductCapability",
    "ProductInfo",
    "ProductRegistry",
    "TemperatureRange",
    "get_ceiling_layout",
    "get_product",
    "get_registry",
    "is_ceiling_product",
    "supports_sky_effect",
]
