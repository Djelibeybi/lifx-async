"""Tests for color generators."""

from __future__ import annotations

from lifx.color import Colors
from lifx.theme.generators import (
    MatrixGenerator,
    MultiZoneGenerator,
    SingleZoneGenerator,
)
from lifx.theme.theme import Theme


class TestSingleZoneGenerator:
    """Tests for SingleZoneGenerator."""

    def test_create_generator(self) -> None:
        """Test creating a single-zone generator."""
        gen = SingleZoneGenerator()
        assert gen is not None

    def test_generate_color(self) -> None:
        """Test random color generation."""
        gen = SingleZoneGenerator()
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        color = gen.generate_color(theme)

        # Should be one of the theme colors
        assert color in theme


class TestMultiZoneGenerator:
    """Tests for MultiZoneGenerator."""

    def test_create_generator(self) -> None:
        """Test creating a multi-zone generator."""
        gen = MultiZoneGenerator()
        assert gen is not None

    def test_get_theme_colors_basic(self) -> None:
        """Test basic color generation for zones."""
        gen = MultiZoneGenerator()
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        colors = gen.get_theme_colors(theme, num_zones=6)

        assert len(colors) == 6
        # All colors should be HSBK instances
        assert all(hasattr(c, "hue") for c in colors)

    def test_get_theme_colors_single_zone(self) -> None:
        """Test generating color for single zone."""
        gen = MultiZoneGenerator()
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        colors = gen.get_theme_colors(theme, num_zones=1)

        assert len(colors) == 1

    def test_get_theme_colors_many_zones(self) -> None:
        """Test generating many zones."""
        gen = MultiZoneGenerator()
        theme = Theme([Colors.RED])

        colors = gen.get_theme_colors(theme, num_zones=80)

        assert len(colors) == 80

    def test_get_theme_colors_more_zones_than_theme(self) -> None:
        """Test generating more zones than theme colors."""
        gen = MultiZoneGenerator()
        theme = Theme([Colors.RED])

        colors = gen.get_theme_colors(theme, num_zones=10)

        assert len(colors) == 10

    def test_get_theme_colors_fewer_zones_than_theme(self) -> None:
        """Test generating fewer zones than theme colors."""
        gen = MultiZoneGenerator()
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        colors = gen.get_theme_colors(theme, num_zones=2)

        assert len(colors) == 2

    def test_blending_creates_smooth_transitions(self) -> None:
        """Test that blending creates intermediate colors."""
        gen = MultiZoneGenerator()
        # Create theme with red and blue
        theme = Theme([Colors.RED, Colors.BLUE])

        colors = gen.get_theme_colors(theme, num_zones=4)

        assert len(colors) == 4
        # Should have intermediate colors due to blending
        # First color should be red-ish, last should be blue-ish


class TestMatrixGenerator:
    """Tests for MatrixGenerator."""

    def test_create_generator_single_tile(self) -> None:
        """Test creating a matrix generator for single tile."""
        coords_and_sizes = [((0, 0), (8, 8))]
        gen = MatrixGenerator(coords_and_sizes)
        assert gen is not None

    def test_generate_for_single_tile_default(self) -> None:
        """Test generating colors for default 8x8 tile."""
        coords_and_sizes = [((0, 0), (8, 8))]
        gen = MatrixGenerator(coords_and_sizes)
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        tiles = gen.get_theme_colors(theme)

        assert len(tiles) == 1
        assert len(tiles[0]) == 64

    def test_generate_for_single_tile_custom_size(self) -> None:
        """Test tile generation with custom size."""
        coords_and_sizes = [((0, 0), (4, 4))]
        gen = MatrixGenerator(coords_and_sizes)
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        tiles = gen.get_theme_colors(theme)

        assert len(tiles) == 1
        assert len(tiles[0]) == 16

    def test_generate_for_multiple_tiles(self) -> None:
        """Test tile generation with multiple tiles."""
        coords_and_sizes = [((0, 0), (8, 8)), ((8, 0), (8, 8))]
        gen = MatrixGenerator(coords_and_sizes)
        theme = Theme([Colors.RED, Colors.GREEN])

        tiles = gen.get_theme_colors(theme)

        assert len(tiles) == 2
        assert len(tiles[0]) == 64
        assert len(tiles[1]) == 64

    def test_generate_for_tiles_with_coordinates(self) -> None:
        """Test tile generation with different tile coordinates."""
        coords_and_sizes = [((0, 0), (8, 8)), ((8, 8), (8, 8))]
        gen = MatrixGenerator(coords_and_sizes)
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        tiles = gen.get_theme_colors(theme)

        assert len(tiles) == 2

    def test_generate_for_single_color_theme(self) -> None:
        """Test tile generation with single color theme."""
        coords_and_sizes = [((0, 0), (8, 8))]
        gen = MatrixGenerator(coords_and_sizes)
        theme = Theme([Colors.RED])

        tiles = gen.get_theme_colors(theme)

        assert len(tiles) == 1
        assert len(tiles[0]) == 64

    def test_generate_for_large_tile(self) -> None:
        """Test tile generation with larger size."""
        coords_and_sizes = [((0, 0), (16, 16))]
        gen = MatrixGenerator(coords_and_sizes)
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        tiles = gen.get_theme_colors(theme)

        assert len(tiles) == 1
        assert len(tiles[0]) == 256
