"""Geometry helpers for LIFX matrix tile chains.

Internal module. These helpers exist so that the two places needing the
conversion — :meth:`lifx.theme.generators.MatrixGenerator.from_tiles` and
:meth:`lifx.animation.framebuffer.FrameBuffer._for_multi_tile` — cannot drift
apart again; the bug they fix was the conversion being written inline in both,
differently. Nothing here is re-exported from ``lifx`` or published in the API
docs, and the signatures may change without a major version.

Only chain-capable devices reach this code, which today means the discontinued
LIFX Tile. Every other matrix device is a single fixed panel that is never
arranged, so its reported position is ignored entirely.

LIFX matrix devices report each tile's position in the chain as ``user_x`` and
``user_y`` floats. Those values are **not** pixel coordinates: they are measured
in units of :data:`TILE_POSITION_UNIT_PIXELS` (8) pixels, which is the width of
the original LIFX Tile. The unit is a fixed constant — it is *not* the reporting
tile's own width or height — so a chain of mixed geometry (say an 8x8 Tile beside
a 5x6 Candle) positions correctly only when every tile is scaled by the same 8.

Evidence for the fixed unit, from the reference implementation used by the LIFX
cloud (``photons``):

* ``photons_canvas/points/rearrange.py`` lays parts out side by side with
  ``user_x += part.width / 8`` — a part's own width is divided by 8 to produce
  the position delta, so 1.0 always means 8 pixels.
* ``photons_canvas/points/containers.py`` converts back with
  ``int(user_x * 8)``.
* The arranger app converts a dragged pixel position to a user position with
  ``new_user_x / 8``.

Axis directions differ between the two spaces:

* ``user_x`` grows to the right, matching canvas columns.
* ``user_y`` grows **upwards**, while canvas rows grow downwards. The photons
  arranger renders a part at ``zero_y - user_y * pixel_width`` and treats
  ``bottom = top - height``, both of which confirm the inversion. Callers that
  work in row-major canvas space must therefore negate the converted ``user_y``,
  which is what :func:`tile_origin_pixels` does for them.

Rounding differs deliberately from photons: photons truncates with ``int()``,
this library rounds to nearest, with halves going away from zero (builtin
``round()`` is banker's rounding, which would collapse two tiles placed one
pixel apart onto the same origin). Truncation biases towards zero
and would place a tile a pixel off for positions that are not exact multiples of
an eighth (the LIFX app writes arbitrary floats when a chain is dragged around).
Nothing about this conversion goes on the wire — it only decides which canvas
pixels a tile renders — so the nearest-neighbour result is preferred. For the
values real hardware reports (multiples of 1/8) the two agree exactly.
"""

from __future__ import annotations

import math
from typing import Final, Protocol

__all__ = [
    "TILE_POSITION_UNIT_PIXELS",
    "TilePlacement",
    "tile_origin_pixels",
    "tile_position_to_pixels",
]

# One unit of user_x/user_y equals this many pixels, regardless of the actual
# pixel dimensions of the tile reporting the position.
TILE_POSITION_UNIT_PIXELS: Final[int] = 8


class TilePlacement(Protocol):
    """Structural type for anything that knows where a tile sits and how big it is.

    :class:`lifx.devices.matrix.TileInfo` satisfies this protocol. Using a
    protocol keeps the theme layer's ``MatrixGenerator.from_tiles()`` signature
    free of a dependency on the device layer.

    The members are read-only properties because the helpers only ever read
    them. Declaring them as plain attributes would make writability part of the
    contract, needlessly rejecting frozen dataclasses and NamedTuples.
    """

    @property
    def user_x(self) -> float:
        """Reported horizontal position in tile-position units."""
        ...

    @property
    def user_y(self) -> float:
        """Reported vertical position in tile-position units."""
        ...

    @property
    def width(self) -> int:
        """Tile width in pixels."""
        ...

    @property
    def height(self) -> int:
        """Tile height in pixels."""
        ...


def tile_position_to_pixels(user_position: float) -> int:
    """Convert a single ``user_x``/``user_y`` axis value to pixels.

    Halves round away from zero rather than to even, so two tiles the LIFX app
    placed one pixel apart never collapse onto the same origin. Python's builtin
    ``round()`` is banker's rounding and would map both 1.5 and 2.5 to 2.

    Args:
        user_position: Position in tile-position units (1.0 = 8 pixels)

    Returns:
        The position in pixels, rounded to the nearest whole pixel

    Example:
        ```python
        assert tile_position_to_pixels(0.0) == 0
        assert tile_position_to_pixels(1.0) == 8
        assert tile_position_to_pixels(0.625) == 5  # a 5-pixel-wide tile across
        assert tile_position_to_pixels(0.3125) == 3  # 2.5 px rounds away from 0
        ```
    """
    pixels = user_position * TILE_POSITION_UNIT_PIXELS
    return math.floor(pixels + 0.5) if pixels >= 0 else math.ceil(pixels - 0.5)


def tile_origin_pixels(user_x: float, user_y: float) -> tuple[int, int]:
    """Convert a tile's reported position to its top-left pixel origin.

    The returned origin is in row-major canvas space: x grows to the right and y
    grows downwards. Because ``user_y`` grows upwards, the y axis is inverted
    here so that a tile reported higher in the chain renders higher on the canvas.

    Origins are relative, not absolute: LIFX centres a chain around zero, so
    negative values are normal. Callers that need non-negative canvas indices
    should subtract the minimum origin across the chain.

    Args:
        user_x: Reported horizontal position in tile-position units
        user_y: Reported vertical position in tile-position units

    Returns:
        ``(left_x, top_y)`` in pixels

    Example:
        ```python
        assert tile_origin_pixels(2.0, 0.0) == (16, 0)
        assert tile_origin_pixels(0.0, 1.0) == (0, -8)  # one tile higher up
        ```
    """
    return (tile_position_to_pixels(user_x), -tile_position_to_pixels(user_y))
