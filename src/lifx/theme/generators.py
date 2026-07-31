"""Color generators for different device types.

This module provides device-specific color distribution strategies for
applying themes to single-zone, multi-zone, and matrix/tile devices.
"""

from __future__ import annotations

from collections.abc import Iterable

from lifx.color import HSBK
from lifx.geometry import TilePlacement, tile_origin_pixels
from lifx.theme.canvas import Canvas
from lifx.theme.theme import Theme


class SingleZoneGenerator:
    """Generator for single-zone light devices.

    Extracts a single color from a theme for simple lights.
    """

    def generate_color(self, theme: Theme) -> HSBK:
        """Get one color from theme.

        Args:
            theme: Theme to extract color from

        Returns:
            Single HSBK color
        """
        return theme.random()


class MultiZoneGenerator:
    """Generator for multi-zone light devices.

    Distributes colors across zones for strips and beams using smooth
    color blending between theme colors. Uses recursive blending to create
    smooth transitions between theme colors.
    """

    def __init__(self) -> None:
        """Create a multi-zone generator."""
        self._colors: list[HSBK] = []

    def add_color(self, color: HSBK) -> None:
        """Add a color to the list of colors to use."""
        self._colors.append(color)

    def apply_to_range(self, this_color: HSBK, next_color: HSBK, length: int) -> None:
        """Recursively add two colors with a blend between them.

        Creates smooth transitions by recursively blending colors.
        This creates the characteristic gradient effect in multizone lights.

        Args:
            this_color: Starting color
            next_color: Ending color
            length: Number of zones to fill between these colors
        """
        if length == 1:
            self.add_color(this_color)

        elif length == 2:
            # Create a blend between the two colors
            second_color = HSBK.average(
                [next_color.limit_distance_to(this_color), this_color]
            )
            self.add_color(this_color)
            self.add_color(second_color)

        else:
            # Recursively divide the range and blend
            average = HSBK.average([next_color, this_color])
            self.apply_to_range(this_color, average, length // 2)
            self.apply_to_range(average, next_color, length - length // 2)

    def build_ranges(self, theme: Theme, zone_count: int) -> None:
        """Build the list of colors in ranges based on multizone count.

        Distributes theme colors across zones with proper blending.

        Args:
            theme: Theme to apply
            zone_count: Number of zones in the device
        """
        index = 0
        location = 0
        zones_per_color = max(1, int(zone_count / max(len(theme) - 1, 1)))

        while location < zone_count:
            length = min(location + zones_per_color, zone_count) - location
            self.apply_to_range(
                theme[index], theme.get_next_bounds_checked(index), length
            )
            index = min(len(theme) - 1, index + 1)
            location += zones_per_color

    def get_theme_colors(self, theme: Theme, num_zones: int) -> list[HSBK]:
        """Generates the list of colors for all zones to create a blended theme.

        Args:
            theme: Theme to apply
            num_zones: Number of zones to generate colors for

        Returns:
            List of HSBK colors, one per zone, with smooth blending
        """
        new_theme = theme.shuffled()
        new_theme.ensure_color()
        self._colors = []
        self.build_ranges(new_theme, num_zones)

        return self._colors


class MatrixGenerator:
    """Generator for matrix/tile devices.

    Distributes colors across all tiles in a chain using Canvas-based rendering
    to create natural color splotches that grow outward.

    Tile geometry is taken from the chain rather than assumed: a Candle is 5x6,
    a Tile is 8x8, and a Ceiling reports its own dimensions.
    """

    def __init__(
        self,
        coords_and_sizes: list[tuple[tuple[int, int], tuple[int, int]]],
    ) -> None:
        """Initialize the matrix generator.

        Args:
            coords_and_sizes: List of ((left_x, top_y), (width, height)) for each
                tile, in pixels. Build these from a device chain with
                :meth:`from_tiles` rather than passing ``user_x``/``user_y``
                directly — those are in tile-position units, not pixels.
        """
        self.coords_and_sizes = coords_and_sizes
        self.tiles: list[list[HSBK]] = []

    @classmethod
    def from_tiles(cls, tiles: Iterable[TilePlacement]) -> MatrixGenerator:
        """Create a generator from a device chain.

        Converts each tile's reported ``user_x``/``user_y`` position into pixel
        coordinates with :func:`lifx.geometry.tile_origin_pixels` and pairs it
        with the tile's real width and height.

        Args:
            tiles: Tiles from a device chain, in chain order

        Returns:
            Generator whose output tiles are in the same order as ``tiles``
        """
        return cls(
            [
                (
                    tile_origin_pixels(tile.user_x, tile.user_y),
                    (tile.width, tile.height),
                )
                for tile in tiles
            ]
        )

    def add_tile(self, colors: list[HSBK]) -> None:
        """Add a list of colors representing one tile."""
        self.tiles.append(colors)

    def add_tiles_from_canvas(self, canvas: Canvas) -> None:
        """Extract tiles from canvas and add them."""
        for (left_x, top_y), (tile_width, tile_height) in self.coords_and_sizes:
            self.add_tile(
                canvas.points_for_tile(
                    (left_x, top_y), width=tile_width, height=tile_height
                )
            )

    def get_theme_colors(self, theme: Theme) -> list[list[HSBK]]:
        """Generate colors for all tiles using Canvas rendering.

        Creates natural color splotches by:
        1. Adding random points from theme on canvas for each tile
        2. Shuffling points to randomize placement
        3. Blurring by distance to create splotches
        4. Filling gaps between points
        5. Final blur for smooth gradients

        Args:
            theme: Theme to apply

        Returns:
            List of color lists, one per tile, each holding ``width * height``
            colours for that tile (64 for an 8x8 Tile, 30 for a 5x6 Candle)
        """
        # Reset accumulated tiles so the generator can be reused, matching
        # MultiZoneGenerator.get_theme_colors(). Without this a second call
        # appends to the list returned by the first one, doubling its length
        # and retroactively mutating the caller's earlier result.
        self.tiles = []

        # Create main canvas and add random points for all tiles
        canvas = Canvas()
        shuffled_theme = theme.shuffled()
        shuffled_theme.ensure_color()

        # Add points for all tiles first
        for (left_x, top_y), (width, height) in self.coords_and_sizes:
            canvas.add_points_for_tile(
                (left_x, top_y), shuffled_theme, width=width, height=height
            )

        # Shuffle and blur ONCE after all points are added
        # (Previously these were inside the loop, causing earlier tiles' points
        # to be shuffled/blurred multiple times, displacing them from their
        # intended positions and losing theme color variety)
        canvas.shuffle_points()
        canvas.blur_by_distance()

        # Create tile canvas and fill gaps
        tile_canvas = Canvas()

        for (left_x, top_y), (tile_width, tile_height) in self.coords_and_sizes:
            tile_canvas.fill_in_points(canvas, left_x, top_y, tile_width, tile_height)

        # Final blur for smoothness
        tile_canvas.blur()

        # Extract tiles from canvas
        self.add_tiles_from_canvas(tile_canvas)

        return self.tiles
