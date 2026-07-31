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
        canvas.add_points_for_tile(None, theme, width=8, height=8)
        # Should have distributed white color points
        assert len(canvas.points) > 0

    def test_add_points_for_theme_with_colors(self) -> None:
        """Test adding points from theme with colors."""
        canvas = Canvas()
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        canvas.add_points_for_tile(None, theme, width=8, height=8)

        # Should have distributed some points
        assert len(canvas.points) > 0

    def test_add_points_respects_existing_points(self) -> None:
        """Test that add_points_for_tile doesn't override existing points."""
        canvas = Canvas()
        theme = Theme([Colors.RED, Colors.GREEN])

        # Pre-populate canvas
        original_point = Colors.BLUE
        canvas[(0, 0)] = original_point

        canvas.add_points_for_tile(None, theme, width=8, height=8)

        # Original point should still be there
        assert canvas[(0, 0)] == original_point

    def test_add_points_skips_existing_points_in_tile_area(self) -> None:
        """Test that add_points_for_tile skips points already in the tile area.

        This covers the branch 87->91 where (i, j) IS in self.points,
        so we skip the inner if block and continue to the next iteration.
        """
        canvas = Canvas()
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        # Pre-populate canvas with many points in the tile area
        # The tile area for None (default) with width=8 spans roughly -12 to 12
        # We fill multiple points to ensure the branch is hit
        for x in range(-5, 6):
            for y in range(-5, 6):
                canvas[(x, y)] = Colors.BLUE

        # Call add_points_for_tile - it should skip existing points
        canvas.add_points_for_tile(None, theme, width=8, height=8)

        # Check that original points are preserved
        for x in range(-5, 6):
            for y in range(-5, 6):
                # Original points should still be blue
                assert canvas[(x, y)] == Colors.BLUE

    def test_add_points_requires_tile_geometry(self) -> None:
        """Test that the tile's real size must be supplied.

        Pins the removal of the 8x8 defaults: silently assuming 8x8 gave a
        Candle (5x6) the wrong seed scale.
        """
        canvas = Canvas()
        theme = Theme([Colors.RED])

        with pytest.raises(TypeError, match="width"):
            canvas.add_points_for_tile(None, theme)  # type: ignore[call-arg]

    def test_add_points_seed_area_scales_with_tile_size(self) -> None:
        """Test that the seeded area is three times the tile's own geometry.

        A 5x6 Candle must seed a smaller area than an 8x8 Tile, otherwise its
        theme point density and splotch size are wrong.
        """
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        candle = Canvas()
        candle.add_points_for_tile((0, 0), theme, width=5, height=6)

        tile = Canvas()
        tile.add_points_for_tile((0, 0), theme, width=8, height=8)

        # int(0 - 5 * 1.5) == -7 and int(0 + 5 * 1.5) == 7 (exclusive)
        assert all(-7 <= i < 7 for i, _ in candle.points)
        assert all(-9 <= j < 9 for _, j in candle.points)

        # The 8x8 tile seeds the wider -12..12 area on both axes
        assert all(-12 <= i < 12 for i, _ in tile.points)
        assert max(i for i, _ in tile.points) > max(i for i, _ in candle.points)

    def test_add_points_seed_area_follows_tile_origin(self) -> None:
        """Test that the seeded area moves with the tile's pixel origin."""
        theme = Theme([Colors.RED, Colors.GREEN])

        canvas = Canvas()
        canvas.add_points_for_tile((32, 16), theme, width=8, height=8)

        assert all(20 <= i < 44 for i, _ in canvas.points)
        assert all(4 <= j < 28 for _, j in canvas.points)


class TestShufflePoints:
    """Tests for shuffle_points method."""

    def test_shuffle_preserves_point_count(self) -> None:
        """Test that shuffle_points preserves number of points."""
        canvas = Canvas()
        # Use points spaced far apart (10 units) to avoid collision after shuffle.
        # shuffle_point() moves each point by ±3, so points 7+ apart can't collide.
        canvas[(0, 0)] = Colors.RED
        canvas[(10, 10)] = Colors.GREEN
        canvas[(20, 20)] = Colors.BLUE

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

    def test_blur_by_distance_single_point_at_origin(self) -> None:
        """Test blur_by_distance keeps a lone point.

        When a point queries itself as the only closest point, distance is 0 and
        so is greatest_distance. Weighting by distance would then yield nothing
        and delete the point, emptying the canvas — which later crashes
        color_weighting with `max() iterable argument is empty`. All-zero
        distances therefore keep every candidate at equal weight.
        """
        canvas = Canvas()
        canvas[(0, 0)] = Colors.RED

        canvas.blur_by_distance()

        assert list(canvas.points) == [(0, 0)]
        assert canvas[(0, 0)] == Colors.RED

    def test_blur_by_distance_keeps_coincident_points(self) -> None:
        """Test that points sharing a position survive weighting.

        shuffle_points() can collapse several points onto one key, and a tiny
        tile (a 3x1 Spot) can seed only two or three points to begin with. The
        canvas must not empty itself in that case.
        """
        canvas = Canvas()
        canvas[(0, 0)] = Colors.RED
        canvas[(0, 1)] = Colors.BLUE

        canvas.blur_by_distance()

        assert len(canvas.points) == 2


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

    def test_fill_in_points_single_source_point_at_query_location(self) -> None:
        """Test fill_in_points when the only source point is the query pixel.

        Distance is 0 and so is greatest_distance, so weighting by distance
        would drop the colour. The point is kept instead — a 1x1 tile must
        still render its theme colour rather than a gap.
        """
        source_canvas = Canvas()
        source_canvas[(0, 0)] = Colors.RED

        target_canvas = Canvas()
        # Query a 1x1 tile at exactly (0, 0) where the source point is
        target_canvas.fill_in_points(source_canvas, 0, 0, 1, 1)

        assert target_canvas[(0, 0)] == Colors.RED

    def test_fill_in_points_empty_source_canvas(self) -> None:
        """Test fill_in_points against an empty source canvas.

        closest_points returns nothing, so color_weighting must yield nothing
        rather than calling max() on an empty sequence.
        """
        target_canvas = Canvas()
        target_canvas.fill_in_points(Canvas(), 0, 0, 2, 2)

        assert target_canvas.points == {}


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

    def test_points_for_tile_requires_geometry(self) -> None:
        """Test that width and height are required, with no 8x8 fallback."""
        canvas = Canvas()

        with pytest.raises(TypeError, match="width"):
            canvas.points_for_tile(None)  # type: ignore[call-arg]

    def test_points_for_tile_candle_geometry(self) -> None:
        """Test a 5x6 Candle returns 30 colours, not 64."""
        canvas = Canvas()
        grid = canvas.points_for_tile(None, width=5, height=6)

        assert len(grid) == 30

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
