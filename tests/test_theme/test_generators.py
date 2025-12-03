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

    def test_multiple_tiles_use_all_theme_colors(self) -> None:
        """Test that multiple tiles use colors from the entire theme, not just the last.

        Regression test for bug where shuffle_points() and blur_by_distance() were
        called inside the tile loop, causing points from earlier tiles to be displaced
        multiple times, resulting in only the last tile's colors being visible.
        """
        import random

        # Use fixed seed for reproducibility
        random.seed(42)

        # Create a 5-tile chain (like a real LIFX Tile setup)
        coords_and_sizes = [
            ((0, 0), (8, 8)),
            ((8, 0), (8, 8)),
            ((16, 0), (8, 8)),
            ((24, 0), (8, 8)),
            ((32, 0), (8, 8)),
        ]
        gen = MatrixGenerator(coords_and_sizes)

        # Theme with distinctly different colors (high saturation, different hues)
        theme = Theme(
            [Colors.RED, Colors.GREEN, Colors.BLUE, Colors.CYAN, Colors.MAGENTA]
        )

        tiles = gen.get_theme_colors(theme)

        # Collect unique hue values across all tiles (rounded for float precision)
        all_hues: set[int] = set()
        for tile in tiles:
            for color in tile:
                # Round hue to nearest 10 degrees to group similar hues
                rounded_hue = round(color.hue / 10) * 10
                all_hues.add(rounded_hue)

        # With 5 distinct theme colors, we should see variety across the tiles
        # If the bug exists, we'd see very few unique hues (colors would converge)
        # The theme has hues at approximately: 0 (red), 120 (green), 240 (blue),
        # 180 (cyan), 300 (magenta)
        # With blending, we expect to see intermediate hues too
        assert len(all_hues) >= 3, (
            f"Expected at least 3 distinct hue ranges but got {len(all_hues)}: "
            f"{sorted(all_hues)}. This suggests colors are converging to a "
            "single color instead of using the full theme."
        )

    def test_all_theme_colors_represented_in_output(self) -> None:
        """Test that all theme colors are represented in the generated output.

        Regression test for bug where shuffle_points() and blur_by_distance() were
        called inside the tile loop, causing points from earlier tiles to be displaced
        multiple times. This resulted in only some theme colors appearing in the output.
        """
        import random

        from lifx.color import HSBK

        # Use fixed seed for reproducibility
        random.seed(12345)

        # Create tiles that are far apart spatially
        coords_and_sizes = [
            ((0, 0), (8, 8)),
            ((50, 0), (8, 8)),
        ]
        gen = MatrixGenerator(coords_and_sizes)

        # Theme with two distinct, non-wrapping colors (Yellow=60, Cyan=180)
        # These are 120 degrees apart, so we should see hues spanning that range
        theme = Theme(
            [
                HSBK(hue=60, saturation=1.0, brightness=1.0, kelvin=3500),  # Yellow
                HSBK(hue=180, saturation=1.0, brightness=1.0, kelvin=3500),  # Cyan
            ]
        )

        tiles = gen.get_theme_colors(theme)

        # Collect all hues across all tiles
        all_hues = [c.hue for tile in tiles for c in tile]

        # With Yellow (60) and Cyan (180), we expect hues to span from ~60 to ~180
        # If the bug exists, we'd only see hues near one of the colors
        min_hue = min(all_hues)
        max_hue = max(all_hues)
        hue_spread = max_hue - min_hue

        # The spread should be at least 80 degrees (2/3 the distance between colors)
        # if both theme colors are being represented.
        # With the bug, we only see ~66 degree spread (62-128), missing cyan.
        # With the fix, we see spread > 100 degrees as colors approach 60 and 180.
        assert hue_spread >= 80, (
            f"Hue spread is only {hue_spread:.1f} degrees "
            f"(range: {min_hue:.0f}-{max_hue:.0f}). Expected at least 80 degrees "
            "when theme has Yellow(60) and Cyan(180). "
            "This suggests only one theme color is being used."
        )
