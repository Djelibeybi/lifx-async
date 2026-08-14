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


@dataclass(frozen=True)
class MirrorComponentLayout:
    """Component layout for LIFX Mirror lights.

    Mirror lights have two logical components, both of which span multiple
    zones, so each one can carry its own gradient, theme or effect:

    - Front: Zones facing the room, for task lighting
    - Back: Zones facing the wall, for indirect backwash lighting

    Each component is a closed ring that traces the capsule-shaped perimeter,
    so its first and last zones are physically adjacent. The two rings run in
    opposite directions: viewed in the default portrait orientation, the front
    ring starts at the lower left and runs clockwise, while the back ring
    starts at the lower left and runs anticlockwise.

    Zone numbering does not match the Set64 buffer order. ``zone_map`` gives
    the zone at each buffer position, and the position tuples give the buffer
    positions in zone order, so callers can gather and scatter component
    colours without re-deriving the mapping.

    Each component also splits into a left and a right side, one matrix column
    each. Unlike the component positions, the side positions are in *buffer*
    order — top of the mirror to bottom — because that is the order a vertical
    gradient wants. The two orders differ: front zone 0 sits near the bottom,
    so ``front_positions[0]`` and ``front_left_positions[0]`` are not the same
    zone.

    The sides are not the same length. The left column carries 13 zones and the
    right carries 12, because the top row has no right-hand zone on either
    component. Left index ``i`` is therefore matrix row ``i``, while right index
    ``i`` is row ``i + 1``.

    Attributes:
        width: Matrix width in zones
        height: Matrix height in zones
        zone_map: Zone index at each buffer position, -1 where unused
        front_positions: Buffer positions of the front zones, in zone order
        back_positions: Buffer positions of the back zones, in zone order
        front_left_positions: Front left column, top to bottom
        front_right_positions: Front right column, top to bottom
        back_left_positions: Back left column, top to bottom
        back_right_positions: Back right column, top to bottom
    """

    width: int
    height: int
    zone_map: tuple[int, ...]
    front_positions: tuple[int, ...]
    back_positions: tuple[int, ...]
    front_left_positions: tuple[int, ...]
    front_right_positions: tuple[int, ...]
    back_left_positions: tuple[int, ...]
    back_right_positions: tuple[int, ...]

    @property
    def zone_count(self) -> int:
        """Total number of addressable zones across both components."""
        return len(self.front_positions) + len(self.back_positions)

    @property
    def buffer_size(self) -> int:
        """Number of Set64 buffer positions, including unused ones."""
        return self.width * self.height


# Zone at each Set64 buffer position for the LIFX Mirror, in row-major order
# across a 4x13 matrix. The buffer holds 52 positions but only 50 zones: the
# two -1 entries are unused. Columns 0-1 carry the front ring (zones 0-24) and
# columns 2-3 carry the back ring (zones 25-49).
MIRROR_ZONE_MAP: tuple[int, ...] = (
    9,
    -1,
    40,
    -1,
    8,
    10,
    41,
    39,
    7,
    11,
    42,
    38,
    6,
    12,
    43,
    37,
    5,
    13,
    44,
    36,
    4,
    14,
    45,
    35,
    3,
    15,
    46,
    34,
    2,
    16,
    47,
    33,
    1,
    17,
    48,
    32,
    0,
    18,
    49,
    31,
    24,
    19,
    25,
    30,
    23,
    20,
    26,
    29,
    22,
    21,
    27,
    28,
)

#: Zones belonging to each Mirror component.
MIRROR_FRONT_ZONES = range(0, 25)
MIRROR_BACK_ZONES = range(25, 50)

#: Matrix column carrying each side of each Mirror component. Every column is
#: exactly one side of one component, which is what makes side addressing a
#: plain column read.
MIRROR_FRONT_LEFT_COLUMN = 0
MIRROR_FRONT_RIGHT_COLUMN = 1
MIRROR_BACK_LEFT_COLUMN = 2
MIRROR_BACK_RIGHT_COLUMN = 3


def _buffer_positions(zone_map: tuple[int, ...], zones: range) -> tuple[int, ...]:
    """Map zone indices to their Set64 buffer positions.

    Args:
        zone_map: Zone index at each buffer position, -1 where unused
        zones: Zone indices to look up, in the order they should be returned

    Returns:
        Buffer positions in the same order as ``zones``

    Raises:
        ValueError: If a zone is missing from the map
    """
    position_of = {zone: position for position, zone in enumerate(zone_map)}

    try:
        return tuple(position_of[zone] for zone in zones)
    except KeyError as e:
        raise ValueError(f"Zone {e.args[0]} is missing from the zone map") from e


def _column_positions(
    zone_map: tuple[int, ...], width: int, column: int
) -> tuple[int, ...]:
    """Collect the used buffer positions of one matrix column.

    Args:
        zone_map: Zone index at each buffer position, -1 where unused
        width: Matrix width, which is the stride between rows
        column: Column index to collect

    Returns:
        Buffer positions in the column, top to bottom, skipping unused entries
    """
    return tuple(
        position
        for position in range(column, len(zone_map), width)
        if zone_map[position] >= 0
    )


# Mirror product component layouts
# Zone map supplied by the LIFX firmware team: a 36x22 capsule, portrait by
# default, driven as a 4x13 matrix. The Matter buttons sit just above the
# bottom half-circle endpoint, between front zones 21 and 22. Matches the
# layout diagram published by LIFX; not yet exercised against hardware.
# TODO: Remove once LIFX adds component layout metadata to products.json
_MIRROR_WIDTH = 4

_MIRROR_LAYOUT = MirrorComponentLayout(
    width=_MIRROR_WIDTH,
    height=13,
    zone_map=MIRROR_ZONE_MAP,
    front_positions=_buffer_positions(MIRROR_ZONE_MAP, MIRROR_FRONT_ZONES),
    back_positions=_buffer_positions(MIRROR_ZONE_MAP, MIRROR_BACK_ZONES),
    front_left_positions=_column_positions(
        MIRROR_ZONE_MAP, _MIRROR_WIDTH, MIRROR_FRONT_LEFT_COLUMN
    ),
    front_right_positions=_column_positions(
        MIRROR_ZONE_MAP, _MIRROR_WIDTH, MIRROR_FRONT_RIGHT_COLUMN
    ),
    back_left_positions=_column_positions(
        MIRROR_ZONE_MAP, _MIRROR_WIDTH, MIRROR_BACK_LEFT_COLUMN
    ),
    back_right_positions=_column_positions(
        MIRROR_ZONE_MAP, _MIRROR_WIDTH, MIRROR_BACK_RIGHT_COLUMN
    ),
)

MIRROR_LAYOUTS: dict[int, MirrorComponentLayout] = {
    267: _MIRROR_LAYOUT,  # Mirror (US)
    268: _MIRROR_LAYOUT,  # Mirror (Intl)
}


def get_mirror_layout(pid: int) -> MirrorComponentLayout | None:
    """Get component layout for a Mirror product.

    Args:
        pid: Product ID

    Returns:
        MirrorComponentLayout if product is a Mirror light, None otherwise
    """
    return MIRROR_LAYOUTS.get(pid)


def is_mirror_product(pid: int) -> bool:
    """Check if product ID is a Mirror light.

    Args:
        pid: Product ID

    Returns:
        True if product is a Mirror light
    """
    return pid in MIRROR_LAYOUTS


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
