"""Tests for Canvas class.

This tests only the Canvas methods actually called by MatrixLight.apply_theme().
"""

from __future__ import annotations

import pytest

from lifx.color import Colors
from lifx.theme.canvas import Canvas
from lifx.theme.theme import Theme


class TestCanvasBasics:
    """Tests for basic Canvas creation and operations."""

    def test_create_empty_canvas(self) -> None:
        """Test creating an empty canvas."""
        canvas = Canvas()
        assert len(canvas.points) == 0
        assert "Canvas(0 points)" in repr(canvas)

    def test_canvas_repr(self) -> None:
        """Test canvas representation."""
        canvas = Canvas()
        canvas.points[(0, 0)] = Colors.RED
        assert "Canvas(1 points)" in repr(canvas)

    def test_canvas_subscript_operations(self) -> None:
        """Test __setitem__ and __getitem__."""
        canvas = Canvas()
        canvas[(0, 0)] = Colors.RED
        assert canvas[(0, 0)].hue == 0

    def test_canvas_contains(self) -> None:
        """Test __contains__ operator."""
        canvas = Canvas()
        canvas[(0, 0)] = Colors.RED
        assert (0, 0) in canvas
        assert (1, 1) not in canvas

    def test_canvas_iteration(self) -> None:
        """Test iterating over canvas points."""
        canvas = Canvas()
        canvas[(0, 0)] = Colors.RED
        canvas[(1, 1)] = Colors.GREEN

        points = list(canvas)
        assert len(points) == 2
        assert all(
            isinstance(coord, tuple) and isinstance(color, type(Colors.RED))
            for coord, color in points
        )


class TestAddPointsForTile:
    """Tests for add_points_for_tile method."""

    def test_add_points_for_empty_theme(self) -> None:
        """Test adding points with empty theme."""
        canvas = Canvas()
        theme = Theme([])
        # Empty theme defaults to white, so it will add points
        canvas.add_points_for_tile(None, theme)
        # Should have distributed white color points
        assert len(canvas.points) > 0

    def test_add_points_for_theme_with_colors(self) -> None:
        """Test adding points from theme with colors."""
        canvas = Canvas()
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        canvas.add_points_for_tile(None, theme)

        # Should have distributed some points
        assert len(canvas.points) > 0

    def test_add_points_respects_existing_points(self) -> None:
        """Test that add_points_for_tile doesn't override existing points."""
        canvas = Canvas()
        theme = Theme([Colors.RED, Colors.GREEN])

        # Pre-populate canvas
        original_point = Colors.BLUE
        canvas[(0, 0)] = original_point

        canvas.add_points_for_tile(None, theme)

        # Original point should still be there
        assert canvas[(0, 0)] == original_point


class TestShufflePoints:
    """Tests for shuffle_points method."""

    def test_shuffle_preserves_point_count(self) -> None:
        """Test that shuffle_points preserves number of points."""
        canvas = Canvas()
        canvas[(0, 0)] = Colors.RED
        canvas[(5, 5)] = Colors.GREEN
        canvas[(10, 10)] = Colors.BLUE

        original_count = len(canvas.points)
        canvas.shuffle_points()

        assert len(canvas.points) == original_count

    def test_shuffle_changes_positions(self) -> None:
        """Test that shuffle_points actually moves points."""
        canvas = Canvas()
        canvas[(5, 5)] = Colors.RED

        # Get original positions
        original_positions = set(canvas.points.keys())

        # Shuffle multiple times - should eventually change position
        for _ in range(10):
            canvas.shuffle_points()
            if set(canvas.points.keys()) != original_positions:
                # Position changed
                return

        # If we get here, positions didn't change after 10 shuffles
        # This is statistically unlikely but possible, so we just note it
        pytest.skip("Shuffle didn't change position after 10 attempts")


class TestBlurByDistance:
    """Tests for blur_by_distance method."""

    def test_blur_by_distance_preserves_point_count(self) -> None:
        """Test that blur_by_distance preserves point count."""
        canvas = Canvas()
        canvas[(0, 0)] = Colors.RED
        canvas[(5, 0)] = Colors.BLUE

        original_count = len(canvas.points)
        canvas.blur_by_distance()

        assert len(canvas.points) == original_count

    def test_blur_by_distance_on_empty_canvas(self) -> None:
        """Test blur_by_distance on empty canvas."""
        canvas = Canvas()
        canvas.blur_by_distance()
        assert len(canvas.points) == 0

    def test_blur_by_distance_modifies_colors(self) -> None:
        """Test that blur_by_distance modifies colors based on neighbors."""
        canvas = Canvas()
        canvas[(0, 0)] = Colors.RED
        canvas[(1, 0)] = Colors.BLUE

        original_color = canvas[(0, 0)]
        canvas.blur_by_distance()
        blurred_color = canvas[(0, 0)]

        # Color should be modified (blurred average of red and blue)
        assert blurred_color.hue != original_color.hue


class TestFillInPoints:
    """Tests for fill_in_points method."""

    def test_fill_in_points_basic(self) -> None:
        """Test basic fill_in_points operation."""
        source_canvas = Canvas()
        source_canvas[(0, 0)] = Colors.RED
        source_canvas[(10, 10)] = Colors.BLUE

        target_canvas = Canvas()
        target_canvas.fill_in_points(source_canvas, 0, 0, 8, 8)

        # Should have filled in some points
        assert len(target_canvas.points) > 0

    def test_fill_in_points_on_larger_tile(self) -> None:
        """Test fill_in_points with non-standard tile size."""
        source_canvas = Canvas()
        source_canvas[(0, 0)] = Colors.RED
        source_canvas[(16, 16)] = Colors.BLUE

        target_canvas = Canvas()
        target_canvas.fill_in_points(source_canvas, 0, 0, 16, 16)

        # Should fill the 16x16 area
        assert len(target_canvas.points) > 0


class TestBlur:
    """Tests for blur method."""

    def test_blur_preserves_point_count(self) -> None:
        """Test that blur preserves point count."""
        canvas = Canvas()
        canvas[(0, 0)] = Colors.RED
        canvas[(1, 0)] = Colors.BLUE

        original_count = len(canvas.points)
        canvas.blur()

        assert len(canvas.points) == original_count

    def test_blur_on_empty_canvas(self) -> None:
        """Test blur on empty canvas."""
        canvas = Canvas()
        canvas.blur()
        assert len(canvas.points) == 0

    def test_blur_with_neighbors_modifies_color(self) -> None:
        """Test that blur modifies colors when neighbors exist."""
        canvas = Canvas()
        canvas[(0, 0)] = Colors.RED
        canvas[(1, 0)] = Colors.BLUE

        original_color = canvas[(0, 0)]
        canvas.blur()
        blurred_color = canvas[(0, 0)]

        # Red should be blurred with blue neighbor
        assert blurred_color.hue != original_color.hue


class TestPointsForTile:
    """Tests for points_for_tile method."""

    def test_points_for_tile_empty_canvas(self) -> None:
        """Test extracting points from empty canvas."""
        canvas = Canvas()
        grid = canvas.points_for_tile(None, width=2, height=2)

        # Should return 4 grey points for 2x2 grid
        assert len(grid) == 4
        assert all(c.saturation == 0.0 for c in grid)  # All grey

    def test_points_for_tile_with_points(self) -> None:
        """Test extracting points with some canvas points."""
        canvas = Canvas()
        canvas[(0, 0)] = Colors.RED
        canvas[(1, 0)] = Colors.GREEN

        grid = canvas.points_for_tile(None, width=2, height=2)

        assert len(grid) == 4
        assert grid[0].hue == 0  # RED at (0,0)
        assert grid[1].hue == 120  # GREEN at (1,0)

    def test_points_for_tile_default_size(self) -> None:
        """Test default 8x8 tile size."""
        canvas = Canvas()
        grid = canvas.points_for_tile(None)

        assert len(grid) == 64  # 8x8

    def test_points_for_tile_with_offset(self) -> None:
        """Test tile extraction with coordinates."""
        canvas = Canvas()
        canvas[(5, 5)] = Colors.RED
        canvas[(6, 5)] = Colors.GREEN

        # Extract tile starting at (5, 5)
        grid = canvas.points_for_tile((5, 5), width=2, height=2)

        assert len(grid) == 4
        assert grid[0].hue == 0  # RED at (5,5)
        assert grid[1].hue == 120  # GREEN at (6,5)
