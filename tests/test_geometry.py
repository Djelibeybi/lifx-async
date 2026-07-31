"""Tests for tile position geometry helpers.

These pin the user_x/user_y -> pixel conversion so it cannot silently drift back
to the tile's own width, which is the bug this module was written to kill.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import pytest

from lifx.geometry import (
    TILE_POSITION_UNIT_PIXELS,
    TilePlacement,
    tile_origin_pixels,
    tile_position_to_pixels,
)


class TestTilePositionUnit:
    """Tests for the tile position unit constant."""

    def test_unit_is_eight_pixels(self) -> None:
        """Test the unit is a fixed 8 pixels.

        Photons — the reference implementation — lays parts out with
        ``user_x += part.width / 8`` and converts back with ``int(user_x * 8)``,
        so 1.0 is always 8 pixels regardless of the tile reporting it.
        """
        assert TILE_POSITION_UNIT_PIXELS == 8


class TestTilePositionToPixels:
    """Tests for tile_position_to_pixels."""

    @pytest.mark.parametrize(
        ("user_position", "expected"),
        [
            (0.0, 0),
            (1.0, 8),
            (2.0, 16),
            (4.0, 32),
            (-1.0, -8),
            (-2.5, -20),
            (0.5, 4),
            (0.625, 5),  # a 5-pixel-wide tile advances the position by 5/8
            (0.75, 6),
        ],
    )
    def test_conversion(self, user_position: float, expected: int) -> None:
        """Test conversion of positions to pixels."""
        assert tile_position_to_pixels(user_position) == expected

    def test_unit_is_independent_of_tile_size(self) -> None:
        """Test that a 5x6 Candle still uses the 8 pixel unit.

        Scaling by the tile's own width would put this tile at 5 pixels.
        """
        assert tile_position_to_pixels(1.0) == 8

    def test_rounds_to_nearest_pixel(self) -> None:
        """Test fractional positions round rather than truncate.

        Photons truncates (``int``); this library rounds because the value only
        decides which canvas pixel a tile renders at and never goes on the wire.
        """
        assert tile_position_to_pixels(0.8) == 6  # 6.4
        assert tile_position_to_pixels(0.85) == 7  # 6.8, int() would give 6
        assert tile_position_to_pixels(-0.85) == -7  # int() would give -6


class TestTileOriginPixels:
    """Tests for tile_origin_pixels."""

    def test_origin_at_zero(self) -> None:
        """Test the chain origin maps to the canvas origin."""
        assert tile_origin_pixels(0.0, 0.0) == (0, 0)

    def test_horizontal_chain_is_eight_pixels_apart(self) -> None:
        """Test consecutive tiles in a chain sit one tile width apart."""
        origins = [tile_origin_pixels(float(i), 0.0) for i in range(5)]

        assert origins == [(0, 0), (8, 0), (16, 0), (24, 0), (32, 0)]

    def test_user_y_is_inverted(self) -> None:
        """Test a tile higher in the chain gets a smaller canvas row.

        user_y grows upwards while canvas rows grow downwards.
        """
        assert tile_origin_pixels(0.0, 1.0) == (0, -8)
        assert tile_origin_pixels(0.0, -1.0) == (0, 8)

    def test_negative_positions(self) -> None:
        """Test centred chains, which report negative positions, convert."""
        assert tile_origin_pixels(-1.5, 0.5) == (-12, -4)


class TestHalfPixelRounding:
    """Tests for how half-pixel positions round.

    Builtin ``round()`` is banker's rounding, which maps both 1.5 and 2.5 to 2
    and would collapse two tiles the LIFX app placed one pixel apart onto the
    same canvas origin.
    """

    @pytest.mark.parametrize(
        ("user_position", "expected"),
        [
            (0.0625, 1),  # 0.5 px
            (0.1875, 2),  # 1.5 px
            (0.3125, 3),  # 2.5 px
            (0.5625, 5),  # 4.5 px
            (-0.1875, -2),  # -1.5 px
            (-0.3125, -3),  # -2.5 px
        ],
    )
    def test_halves_round_away_from_zero(
        self, user_position: float, expected: int
    ) -> None:
        """Test halves round away from zero, not to even."""
        assert tile_position_to_pixels(user_position) == expected

    def test_adjacent_half_pixel_tiles_keep_distinct_origins(self) -> None:
        """Test two tiles a pixel apart do not share one canvas origin."""
        first = tile_origin_pixels(0.1875, 0.0)
        second = tile_origin_pixels(0.3125, 0.0)

        assert first != second
        assert second[0] - first[0] == 1


class TestTilePlacementProtocol:
    """Tests that read-only tile models satisfy the TilePlacement protocol.

    The protocol is internal, so this is not a compatibility promise: it pins
    that the protocol does not demand writability it never uses.
    """

    def test_frozen_dataclass_is_accepted(self) -> None:
        """Test a frozen dataclass satisfies the protocol."""

        @dataclass(frozen=True)
        class FrozenTile:
            user_x: float
            user_y: float
            width: int
            height: int

        placement: TilePlacement = FrozenTile(user_x=1.0, user_y=0.0, width=8, height=8)

        assert tile_origin_pixels(placement.user_x, placement.user_y) == (8, 0)

    def test_named_tuple_is_accepted(self) -> None:
        """Test a NamedTuple satisfies the protocol."""

        class TupleTile(NamedTuple):
            user_x: float
            user_y: float
            width: int
            height: int

        placement: TilePlacement = TupleTile(user_x=0.0, user_y=1.0, width=5, height=6)

        assert tile_origin_pixels(placement.user_x, placement.user_y) == (0, -8)
