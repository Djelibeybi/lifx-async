"""Tests for tile orientation remapping."""

from __future__ import annotations

import pytest

from lifx.animation.orientation import (
    LUNA_PRODUCT_IDS,
    TILE_PRODUCT_ID,
    Orientation,
    build_orientation_lut,
    logical_tile_size,
    nearest_orientation,
    orientation_group,
)


class TestOrientation:
    """Tests for Orientation enum."""

    def test_from_string_upright(self) -> None:
        """Test converting 'Upright' string."""
        assert Orientation.from_string("Upright") == Orientation.RIGHT_SIDE_UP

    def test_from_string_rotated_right(self) -> None:
        """Test converting 'RotatedRight' string."""
        assert Orientation.from_string("RotatedRight") == Orientation.ROTATED_90

    def test_from_string_upside_down(self) -> None:
        """Test converting 'UpsideDown' string."""
        assert Orientation.from_string("UpsideDown") == Orientation.ROTATED_180

    def test_from_string_rotated_left(self) -> None:
        """Test converting 'RotatedLeft' string."""
        assert Orientation.from_string("RotatedLeft") == Orientation.ROTATED_270

    def test_from_string_face_up(self) -> None:
        """Test converting 'FaceUp' string."""
        assert Orientation.from_string("FaceUp") == Orientation.FACE_UP

    def test_from_string_face_down(self) -> None:
        """Test converting 'FaceDown' string."""
        assert Orientation.from_string("FaceDown") == Orientation.FACE_DOWN

    def test_from_string_unknown_raises(self) -> None:
        """Test that unknown orientation string raises ValueError."""
        with pytest.raises(ValueError, match="Unknown orientation"):
            Orientation.from_string("InvalidOrientation")


class TestBuildOrientationLut:
    """Tests for build_orientation_lut function."""

    def test_right_side_up_identity(self) -> None:
        """Test that RIGHT_SIDE_UP produces identity mapping."""
        lut = build_orientation_lut(4, 4, Orientation.RIGHT_SIDE_UP)
        # Should be 0, 1, 2, 3, 4, 5, ... 15
        assert lut == tuple(range(16))

    def test_rotated_180_reverses(self) -> None:
        """Test that ROTATED_180 reverses the pixel order."""
        lut = build_orientation_lut(4, 4, Orientation.ROTATED_180)
        # First physical position should map to last framebuffer index
        assert lut[0] == 15
        # Last physical position should map to first framebuffer index
        assert lut[15] == 0

    def test_rotated_90_corners(self) -> None:
        """Test ROTATED_90 corner mappings for 4x4 grid."""
        lut = build_orientation_lut(4, 4, Orientation.ROTATED_90)
        # For 90 degree clockwise rotation:
        # Physical (0,0) -> Source (3,0) = index 3
        assert lut[0] == 3
        # Physical (3,0) -> Source (3,3) = index 15
        assert lut[3] == 15
        # Physical (0,3) -> Source (0,0) = index 0
        assert lut[12] == 0
        # Physical (3,3) -> Source (0,3) = index 12
        assert lut[15] == 12

    def test_rotated_270_corners(self) -> None:
        """Test ROTATED_270 corner mappings for 4x4 grid."""
        lut = build_orientation_lut(4, 4, Orientation.ROTATED_270)
        # For 270 degree (90 counter-clockwise) rotation:
        # Physical (0,0) -> Source (0,3) = index 12
        assert lut[0] == 12
        # Physical (3,0) -> Source (0,0) = index 0
        assert lut[3] == 0
        # Physical (0,3) -> Source (3,3) = index 15
        assert lut[12] == 15
        # Physical (3,3) -> Source (3,0) = index 3
        assert lut[15] == 3

    def test_face_up_same_as_upright(self) -> None:
        """Test that FACE_UP is treated same as RIGHT_SIDE_UP."""
        lut_face_up = build_orientation_lut(4, 4, Orientation.FACE_UP)
        lut_upright = build_orientation_lut(4, 4, Orientation.RIGHT_SIDE_UP)
        assert lut_face_up == lut_upright

    def test_face_down_same_as_upright(self) -> None:
        """Test that FACE_DOWN is treated same as RIGHT_SIDE_UP."""
        lut_face_down = build_orientation_lut(4, 4, Orientation.FACE_DOWN)
        lut_upright = build_orientation_lut(4, 4, Orientation.RIGHT_SIDE_UP)
        assert lut_face_down == lut_upright

    def test_8x8_tile_size(self) -> None:
        """Test LUT for standard 8x8 tile."""
        lut = build_orientation_lut(8, 8, Orientation.RIGHT_SIDE_UP)
        assert len(lut) == 64

    def test_rectangular_tile(self) -> None:
        """Test LUT for non-square tile (16x8)."""
        lut = build_orientation_lut(16, 8, Orientation.RIGHT_SIDE_UP)
        assert len(lut) == 128

    def test_lru_cache_works(self) -> None:
        """Test that repeated calls return cached results."""
        # Call twice with same args
        lut1 = build_orientation_lut(8, 8, Orientation.RIGHT_SIDE_UP)
        lut2 = build_orientation_lut(8, 8, Orientation.RIGHT_SIDE_UP)
        # Should be the exact same object (cached)
        assert lut1 is lut2

    def test_lru_cache_different_args(self) -> None:
        """Test that different args return different results."""
        lut1 = build_orientation_lut(8, 8, Orientation.RIGHT_SIDE_UP)
        lut2 = build_orientation_lut(8, 8, Orientation.ROTATED_180)
        # Should be different objects
        assert lut1 is not lut2
        assert lut1 != lut2

    def test_bijective_mapping(self) -> None:
        """Test that LUT is a bijection (one-to-one mapping)."""
        for orientation in Orientation:
            lut = build_orientation_lut(8, 8, orientation)
            # All indices should be unique (bijective)
            assert len(set(lut)) == 64
            # All indices should be in valid range
            assert all(0 <= i < 64 for i in lut)

    def test_rotated_90_non_square_reads_a_swapped_canvas(self) -> None:
        """Test a 7x5 tile on its right side shows a 5 wide by 7 high canvas.

        Physical (x, y) reads logical (height - 1 - y, x) on a canvas whose
        width is the tile's height, so the logical top row lands on the
        physical left column.
        """
        lut = build_orientation_lut(7, 5, Orientation.ROTATED_90)
        assert len(lut) == 35
        assert sorted(lut) == list(range(35))
        # Physical left column, top to bottom, reads the logical top row
        # from its right end to its left.
        assert [lut[y * 7] for y in range(5)] == [4, 3, 2, 1, 0]
        # Physical bottom-right corner reads the logical bottom-left corner.
        assert lut[34] == 30

    def test_rotated_270_non_square_reads_a_swapped_canvas(self) -> None:
        """Test a 7x5 tile on its left side shows a 5 wide by 7 high canvas."""
        lut = build_orientation_lut(7, 5, Orientation.ROTATED_270)
        assert len(lut) == 35
        assert sorted(lut) == list(range(35))
        # Physical top-left corner reads the logical bottom-left corner.
        assert lut[0] == 30
        # Physical right column, top to bottom, reads the logical top row.
        assert [lut[y * 7 + 6] for y in range(5)] == [0, 1, 2, 3, 4]

    def test_quarter_turns_undo_each_other_on_a_non_square_tile(self) -> None:
        """Test a side rotation applied through the LUT is undone by its inverse."""
        canvas = list(range(35))
        for orientation in (Orientation.ROTATED_90, Orientation.ROTATED_270):
            lut = build_orientation_lut(7, 5, orientation)
            physical = [canvas[src] for src in lut]
            logical = [0] * 35
            for dst, src in enumerate(lut):
                logical[src] = physical[dst]
            assert logical == canvas

    def test_square_quarter_turns_are_unchanged(self) -> None:
        """Test the 8x8 LUT still reads the square formula pixel for pixel."""
        lut = build_orientation_lut(8, 8, Orientation.ROTATED_90)
        assert lut == tuple((7 - y) + x * 8 for y in range(8) for x in range(8))
        lut = build_orientation_lut(8, 8, Orientation.ROTATED_270)
        assert lut == tuple(y + (7 - x) * 8 for y in range(8) for x in range(8))

    def test_rotated_180_works_for_non_square(self) -> None:
        """Test ROTATED_180 works correctly for non-square tiles.

        180 degree rotation is valid for any tile dimensions.
        """
        lut = build_orientation_lut(4, 2, Orientation.ROTATED_180)
        # 4x2 = 8 pixels, reversed
        assert len(lut) == 8
        # First physical position maps to last framebuffer index
        assert lut[0] == 7
        # Last physical position maps to first framebuffer index
        assert lut[7] == 0


class TestLogicalTileSize:
    """logical_tile_size(): the canvas a tile presents in its orientation."""

    @pytest.mark.parametrize(
        ("orientation", "expected"),
        [
            (Orientation.RIGHT_SIDE_UP, (7, 5)),
            (Orientation.ROTATED_90, (5, 7)),
            (Orientation.ROTATED_180, (7, 5)),
            (Orientation.ROTATED_270, (5, 7)),
            (Orientation.FACE_UP, (7, 5)),
            (Orientation.FACE_DOWN, (7, 5)),
        ],
    )
    def test_quarter_turns_swap_the_sides(
        self, orientation: Orientation, expected: tuple[int, int]
    ) -> None:
        assert logical_tile_size(7, 5, orientation) == expected

    def test_a_square_tile_keeps_its_size(self) -> None:
        assert logical_tile_size(8, 8, Orientation.ROTATED_90) == (8, 8)


class TestOrientationGroups:
    """Tests for the per-product accelerometer axis maps."""

    def test_groups_by_product(self) -> None:
        """Test Tile and Luna products find their group, others none."""
        assert orientation_group(TILE_PRODUCT_ID) == "Tile"
        assert LUNA_PRODUCT_IDS == (219, 220)
        assert all(orientation_group(pid) == "Luna" for pid in LUNA_PRODUCT_IDS)
        assert orientation_group(57) is None  # Candle

    def test_negative_x_differs_between_luna_and_tile(self) -> None:
        """Test the same reading means different things on each product."""
        assert nearest_orientation(219, -100, 0, 0) == "Upright"
        assert nearest_orientation(TILE_PRODUCT_ID, -100, 0, 0) == "RotatedLeft"

    @pytest.mark.parametrize(
        ("reading", "expected"),
        [
            ((100, 0, 0), "UpsideDown"),
            ((-100, 0, 0), "Upright"),
            ((0, 100, 0), "FaceDown"),
            ((0, -100, 0), "FaceUp"),
            ((0, 0, 100), "RotatedLeft"),
            ((0, 0, -100), "RotatedRight"),
        ],
    )
    @pytest.mark.parametrize("pid", LUNA_PRODUCT_IDS)
    def test_luna_map(
        self, pid: int, reading: tuple[int, int, int], expected: str
    ) -> None:
        """Test each dominant Luna axis."""
        assert nearest_orientation(pid, *reading) == expected

    @pytest.mark.parametrize(
        ("reading", "expected"),
        [
            ((100, 0, 0), "RotatedRight"),
            ((-100, 0, 0), "RotatedLeft"),
            ((0, 100, 0), "UpsideDown"),
            ((0, -100, 0), "Upright"),
            ((0, 0, 100), "FaceDown"),
            ((0, 0, -100), "FaceUp"),
        ],
    )
    def test_tile_map(self, reading: tuple[int, int, int], expected: str) -> None:
        """Test each dominant Tile axis."""
        assert nearest_orientation(TILE_PRODUCT_ID, *reading) == expected

    def test_invalid_reading_is_upright(self) -> None:
        """Test the all -1 sentinel reads as upright on both groups."""
        assert nearest_orientation(219, -1, -1, -1) == "Upright"
        assert nearest_orientation(TILE_PRODUCT_ID, -1, -1, -1) == "Upright"

    def test_ties_fall_back_to_y_axis(self) -> None:
        """Test a tie with no dominant axis is decided by the sign of Y."""
        assert nearest_orientation(219, 5, 5, 5) == "FaceDown"
        assert nearest_orientation(219, 5, -5, 5) == "FaceUp"

    def test_product_in_neither_group_has_no_orientation(self) -> None:
        """Test a Candle is never given an orientation, whatever it reports."""
        assert nearest_orientation(57, 100, 0, 0) is None
        assert nearest_orientation(57, -1, -1, -1) is None
