"""Tile orientation remapping for LIFX matrix devices.

This module provides utilities for remapping pixel coordinates based on tile
orientation, enabling correct display regardless of how tiles are physically
mounted.

LIFX tiles report their orientation via accelerometer data. This module
converts that orientation into lookup tables for efficient pixel remapping
during animation.

The key insight is that orientation affects how row-major framebuffer indices
map to physical tile positions. By pre-computing lookup tables (LUTs), we
can apply orientation correction with a single array lookup per pixel.

Example:
    ```python
    from lifx.animation.orientation import Orientation, build_orientation_lut

    # Build LUT for a single 8x8 tile rotated 90 degrees
    lut = build_orientation_lut(8, 8, Orientation.ROTATED_90)

    # Apply LUT to remap pixels
    output = [framebuffer[lut[i]] for i in range(len(framebuffer))]
    ```
"""

from __future__ import annotations

from enum import IntEnum
from functools import lru_cache
from typing import NamedTuple


class Orientation(IntEnum):
    """Tile orientation based on accelerometer data.

    These values match the orientation detection in TileInfo.nearest_orientation
    but use integer enum for efficient comparison and caching.

    Physical mounting positions:

        - RIGHT_SIDE_UP: Normal position, no rotation needed
        - ROTATED_90: Rotated 90 degrees clockwise (RotatedRight)
        - ROTATED_180: Upside down (UpsideDown)
        - ROTATED_270: Rotated 90 degrees counter-clockwise (RotatedLeft)
        - FACE_UP: Tile facing ceiling
        - FACE_DOWN: Tile facing floor
    """

    RIGHT_SIDE_UP = 0  # "Upright"
    ROTATED_90 = 1  # "RotatedRight"
    ROTATED_180 = 2  # "UpsideDown"
    ROTATED_270 = 3  # "RotatedLeft"
    FACE_UP = 4  # "FaceUp"
    FACE_DOWN = 5  # "FaceDown"

    @classmethod
    def from_string(cls, orientation_str: str) -> Orientation:
        """Convert TileInfo.nearest_orientation string to Orientation enum.

        Args:
            orientation_str: String from TileInfo.nearest_orientation

        Returns:
            Corresponding Orientation enum value

        Raises:
            ValueError: If orientation string is not recognized
        """
        mapping = {
            "Upright": cls.RIGHT_SIDE_UP,
            "RotatedRight": cls.ROTATED_90,
            "UpsideDown": cls.ROTATED_180,
            "RotatedLeft": cls.ROTATED_270,
            "FaceUp": cls.FACE_UP,
            "FaceDown": cls.FACE_DOWN,
        }
        if orientation_str not in mapping:
            raise ValueError(f"Unknown orientation: {orientation_str}")
        return mapping[orientation_str]


class OrientationAxes(NamedTuple):
    """The orientation each accelerometer axis reads as when it dominates.

    The values are the strings :meth:`Orientation.from_string` accepts.
    """

    x_pos: str
    x_neg: str
    y_pos: str
    y_neg: str
    z_pos: str
    z_neg: str


TILE_PRODUCT_ID = 55
LUNA_PRODUCT_IDS = (219, 220)

#: Axis maps by orientation group. Products in no group have no orientation.
ORIENTATION_GROUPS: dict[str, OrientationAxes] = {
    "Tile": OrientationAxes(
        x_pos="RotatedRight",
        x_neg="RotatedLeft",
        y_pos="UpsideDown",
        y_neg="Upright",
        z_pos="FaceDown",
        z_neg="FaceUp",
    ),
    "Luna": OrientationAxes(
        x_pos="UpsideDown",
        x_neg="Upright",
        y_pos="FaceDown",
        y_neg="FaceUp",
        z_pos="RotatedLeft",
        z_neg="RotatedRight",
    ),
}

#: Which group each product belongs to.
ORIENTATION_GROUP_BY_PRODUCT: dict[int, str] = {
    TILE_PRODUCT_ID: "Tile",
    **dict.fromkeys(LUNA_PRODUCT_IDS, "Luna"),
}

#: Date the Luna axis map was checked on a physical Luna standing upright and
#: lying on each side. "pending" until the maintainer has run that check.
LUNA_AXIS_MAP_VERIFIED = "pending"


def orientation_group(product_id: int) -> str | None:
    """Return the orientation group a product belongs to, or None."""
    return ORIENTATION_GROUP_BY_PRODUCT.get(product_id)


def nearest_orientation(product_id: int, x: int, y: int, z: int) -> str | None:
    """Read an accelerometer vector on the product's own axes.

    Args:
        product_id: LIFX product ID, which picks the axis map
        x: Accelerometer X reading
        y: Accelerometer Y reading
        z: Accelerometer Z reading

    Returns:
        A string for :meth:`Orientation.from_string`, or None when the product
        is in no orientation group and so has no orientation to apply.
    """
    group = orientation_group(product_id)
    if group is None:
        return None
    axes = ORIENTATION_GROUPS[group]
    abs_x, abs_y, abs_z = abs(x), abs(y), abs(z)

    if x == -1 and y == -1 and z == -1:
        # Invalid data, assume right-side up.
        return "Upright"
    if abs_x > abs_y and abs_x > abs_z:
        return axes.x_pos if x > 0 else axes.x_neg
    if abs_z > abs_x and abs_z > abs_y:
        return axes.z_pos if z > 0 else axes.z_neg
    return axes.y_pos if y > 0 else axes.y_neg


def logical_tile_size(
    width: int, height: int, orientation: Orientation
) -> tuple[int, int]:
    """The canvas a tile presents in its orientation, as (width, height).

    A tile on its side (ROTATED_90 or ROTATED_270) shows its height across
    and its width down, so a 7x5 Luna lying on a side is drawn as 5 wide by
    7 high. Every other orientation keeps the tile's own size.
    """
    if orientation in (Orientation.ROTATED_90, Orientation.ROTATED_270):
        return height, width
    return width, height


@lru_cache(maxsize=64)
def build_orientation_lut(
    width: int,
    height: int,
    orientation: Orientation,
) -> tuple[int, ...]:
    """Build a lookup table for remapping pixels based on tile orientation.

    The LUT maps physical tile positions to row-major framebuffer indices.
    For a pixel at physical position i, lut[i] gives the framebuffer index.
    The framebuffer is the logical canvas of :func:`logical_tile_size`: for
    a quarter turn of a non-square tile its rows are ``height`` wide, so a
    7x5 tile on its side reads a 5 wide by 7 high canvas. A square tile's
    canvas has the tile's own shape in every orientation.

    This is LRU-cached because tiles typically have standard dimensions (8x8)
    and there are only 6 orientations, so the cache will be highly effective.

    Args:
        width: Tile width in pixels
        height: Tile height in pixels
        orientation: Tile orientation

    Returns:
        Tuple of indices mapping physical position to framebuffer position.
        Tuple is used instead of list for hashability in caches.

    Example:
        >>> lut = build_orientation_lut(8, 8, Orientation.RIGHT_SIDE_UP)
        >>> len(lut)
        64
        >>> lut[0]  # First pixel maps to index 0
        0
        >>> lut = build_orientation_lut(8, 8, Orientation.ROTATED_180)
        >>> lut[0]  # First physical position maps to last framebuffer index
        63
    """
    size = width * height
    lut: list[int] = [0] * size
    canvas_width, _ = logical_tile_size(width, height, orientation)

    for y in range(height):
        for x in range(width):
            # Physical position in row-major order
            physical_idx = y * width + x

            # Calculate source position on the logical canvas
            if orientation == Orientation.ROTATED_90:
                # 90 degrees clockwise: (x, y) -> (height - 1 - y, x), so the
                # canvas top row lands on the physical left column
                src_x = height - 1 - y
                src_y = x
            elif orientation == Orientation.ROTATED_180:
                # 180 degrees: (x, y) -> (width - 1 - x, height - 1 - y)
                src_x = width - 1 - x
                src_y = height - 1 - y
            elif orientation == Orientation.ROTATED_270:
                # 270 degrees (90 counter-clockwise): (x, y) -> (y, width - 1 - x),
                # so the canvas top row lands on the physical right column
                src_x = y
                src_y = width - 1 - x
            else:
                # RIGHT_SIDE_UP, FACE_UP and FACE_DOWN: no x/y rotation. The
                # z-axis orientation doesn't affect 2D pixel mapping
                src_x, src_y = x, y

            # Source index in row-major order on the logical canvas
            src_idx = src_y * canvas_width + src_x
            lut[physical_idx] = src_idx

    return tuple(lut)
