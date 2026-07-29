"""Product-specific quirks and metadata not available in products.json.

This module provides additional metadata for LIFX products that is not included
in the official products.json specification. These quirks are manually maintained
and should be updated as needed when new products are released or when LIFX adds
this information to products.json.

Note:
    If LIFX adds any of this information to products.json in the future,
    the generator should be updated to include it in the auto-generated registry,
    and the corresponding quirk should be removed from this module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CeilingComponentLayout:
    """Component layout for LIFX Ceiling lights.

    Ceiling lights have two logical components:
    - Uplight: Single zone for ambient/indirect lighting
    - Downlight: Multiple zones for main illumination

    Attributes:
        width: Matrix width in zones
        height: Matrix height in zones
        uplight_zone: Zone index for the uplight component
        downlight_zones: Slice representing downlight component zones
    """

    width: int
    height: int
    uplight_zone: int
    downlight_zones: slice


# Ceiling product component layouts
# TODO: Remove once LIFX adds component layout metadata to products.json
CEILING_LAYOUTS: dict[int, CeilingComponentLayout] = {
    176: CeilingComponentLayout(  # Ceiling (US)
        width=8,
        height=8,
        uplight_zone=63,
        downlight_zones=slice(0, 63),
    ),
    177: CeilingComponentLayout(  # Ceiling (Intl)
        width=8,
        height=8,
        uplight_zone=63,
        downlight_zones=slice(0, 63),
    ),
    201: CeilingComponentLayout(  # Ceiling Capsule (US)
        width=16,
        height=8,
        uplight_zone=127,
        downlight_zones=slice(0, 127),
    ),
    202: CeilingComponentLayout(  # Ceiling Capsule (Intl)
        width=16,
        height=8,
        uplight_zone=127,
        downlight_zones=slice(0, 127),
    ),
    265: CeilingComponentLayout(  # Ceiling 13" (US)
        width=8,
        height=8,
        uplight_zone=63,
        downlight_zones=slice(0, 63),
    ),
    266: CeilingComponentLayout(  # Ceiling 13" (Intl)
        width=8,
        height=8,
        uplight_zone=63,
        downlight_zones=slice(0, 63),
    ),
}


# Minimum host firmware major version that implements the SKY tile effect.
# SKY requires the matrix capability plus firmware 4.x: matrix devices still on
# firmware 3.x and earlier reject or ignore it. Confirmed on Ceiling, Luna,
# Tube, Path and the E26 Candle, and assumed on Spot. Support on the LIFX
# Mirror is unconfirmed pending an answer from LIFX. The discontinued LIFX Tile
# is permanently excluded: its terminal firmware is 3.50.
# TODO: Remove once LIFX publishes per-effect support in products.json
SKY_EFFECT_MIN_FIRMWARE_MAJOR = 4


def supports_sky_effect(has_matrix: bool, firmware_major: int) -> bool:
    """Check whether a device can run the SKY tile effect.

    Args:
        has_matrix: Whether the product has the matrix capability
        firmware_major: Host firmware major version number

    Returns:
        True if the device supports the SKY tile effect
    """
    return has_matrix and firmware_major >= SKY_EFFECT_MIN_FIRMWARE_MAJOR


def get_ceiling_layout(pid: int) -> CeilingComponentLayout | None:
    """Get component layout for a Ceiling product.

    Args:
        pid: Product ID

    Returns:
        CeilingComponentLayout if product is a Ceiling light, None otherwise
    """
    return CEILING_LAYOUTS.get(pid)


def is_ceiling_product(pid: int) -> bool:
    """Check if product ID is a Ceiling light.

    Args:
        pid: Product ID

    Returns:
        True if product is a Ceiling light
    """
    return pid in CEILING_LAYOUTS
