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


@lru_cache(maxsize=64)
def build_orientation_lut(
    width: int,
    height: int,
    orientation: Orientation,
) -> tuple[int, ...]:
    """Build a lookup table for remapping pixels based on tile orientation.

    The LUT maps physical tile positions to row-major framebuffer indices.
    For a pixel at physical position i, lut[i] gives the framebuffer index.

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

    for y in range(height):
        for x in range(width):
            # Physical position in row-major order
            physical_idx = y * width + x

            # Calculate source position based on orientation
            if orientation == Orientation.RIGHT_SIDE_UP:
                # No transformation
                src_x, src_y = x, y
            elif orientation == Orientation.ROTATED_90:
                # 90 degrees clockwise: (x, y) -> (height - 1 - y, x)
                # Note: Only valid for square tiles. Non-square tiles would require
                # a source buffer with swapped dimensions (e.g., 5x7 for a 7x5 tile).
                # For non-square tiles, fall back to identity transformation.
                if width == height:
                    src_x = height - 1 - y
                    src_y = x
                else:
                    src_x, src_y = x, y
            elif orientation == Orientation.ROTATED_180:
                # 180 degrees: (x, y) -> (width - 1 - x, height - 1 - y)
                # Works for both square and non-square tiles
                src_x = width - 1 - x
                src_y = height - 1 - y
            elif orientation == Orientation.ROTATED_270:
                # 270 degrees (90 counter-clockwise): (x, y) -> (y, width - 1 - x)
                # Note: Only valid for square tiles. For non-square tiles,
                # fall back to identity transformation.
                if width == height:
                    src_x = y
                    src_y = width - 1 - x
                else:
                    src_x, src_y = x, y
            else:
                # FACE_UP and FACE_DOWN: treat as right-side-up (no x/y rotation)
                # The z-axis orientation doesn't affect 2D pixel mapping
                src_x, src_y = x, y

            # Source index in row-major order
            src_idx = src_y * width + src_x
            lut[physical_idx] = src_idx

    return tuple(lut)
