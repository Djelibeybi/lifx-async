"""Canvas for 2D color interpolation on matrix/tile devices.

This module provides the Canvas class for handling 2D color grids used
in tile and matrix devices.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Iterator

from lifx.color import HSBK
from lifx.theme.theme import Theme


def color_weighting(distances: list[tuple[int, HSBK]]) -> Iterable[HSBK]:
    """Return an array of colors where there is more of a color the closer it is."""
    if not distances:
        return

    greatest_distance = max(dist for dist, _ in distances)

    if greatest_distance == 0:
        # Every candidate sits on the point itself. Weighting by distance would
        # yield nothing at all and silently delete the point, which empties the
        # canvas when a small tile seeds only one or two points.
        for _, color in distances:
            yield color
        return

    for dist, color in distances:
        if dist == 0:
            for _ in range(int(greatest_distance)):
                yield color
        else:
            for _ in range(int(greatest_distance / dist)):
                yield color


def shuffle_point(i: int, j: int) -> tuple[int, int]:
    """Return a new (i, j) value that is the current (i, j) value +/- ~3."""
    new_x = random.randint(i - 3, i + 3)
    new_y = random.randint(j - 3, j + 3)
    return new_x, new_y


def surrounding_points(i: int, j: int) -> list[tuple[int, int]]:
    """Return the points that surround the specified point."""
    return [
        (i - 1, j + 1),
        (i, j + 1),
        (i + 1, j + 1),
        (i - 1, j),
        (i + 1, j),
        (i - 1, j - 1),
        (i, j - 1),
        (i + 1, j - 1),
    ]


class Canvas:
    """A Canvas is a collection of points with methods for interacting with those points

    The points are stored as (i, j) in a dictionary. The value for each point is an HSBK
    color.
    """

    def __init__(self) -> None:
        """Initialize the canvas."""
        self.points: dict[tuple[int, int], HSBK] = {}

    def add_points_for_tile(
        self, tile: tuple[int, int] | None, theme: Theme, width: int, height: int
    ) -> None:
        """Create points on the canvas around where a tile is.

        We seed an area three times the tile's width and height, centred on the
        tile's origin, so that the splotches the theme grows from extend well
        past the tile itself. We also spread the points out in a random manner
        and try to avoid having points next to each other.

        The area scales with the tile's real geometry, so a 5x6 Candle gets a
        proportionally smaller seed area than an 8x8 Tile and ends up with a
        comparable density of theme colours.

        Multiple calls to this function will not override existing points on the canvas.

        Args:
            tile: Top-left pixel coordinates (x, y) of the tile, or None for (0, 0).
                Convert a device's ``user_x``/``user_y`` with
                :func:`lifx.geometry.tile_origin_pixels` — they are not pixels.
            theme: Theme containing colors to distribute
            width: Tile width in pixels
            height: Tile height in pixels
        """
        tile_x, tile_y = tile if tile else (0, 0)

        from_x = int(tile_x - width * 1.5)
        to_x = int(tile_x + width * 1.5)
        from_y = int(tile_y - height * 1.5)
        to_y = int(tile_y + height * 1.5)

        i = from_x
        while i < to_x:
            j = from_y
            while j < to_y:
                if (i, j) not in self.points:
                    if not self.has_neighbour(i, j):
                        random_color = theme.random()
                        self[(i, j)] = random_color
                j += random.choice([1, 2, 3])
            i += random.choice([1, 2, 3])

    def surrounding_colors(self, i: int, j: int) -> list[HSBK]:
        """Return the colors that surround this (i, j) point.

        This will only return points that exist.
        """
        return [self[(x, y)] for x, y in surrounding_points(i, j) if (x, y) in self]

    def has_neighbour(self, i: int, j: int) -> bool:
        """Return whether there are any points around this (i, j) position."""
        return any(self.surrounding_colors(i, j))

    def shuffle_points(self) -> None:
        """Take all the points and move them around a random amount."""
        new_points = {}
        for (i, j), color in self:
            new_points[shuffle_point(i, j)] = color

        self.points = new_points

    def blur(self) -> None:
        """
        For each point, find the average colour of that point plus all surrounding
        points.
        """
        new_points = {}
        for (i, j), original in self:
            colors = [original for _ in range(2)]
            for color in self.surrounding_colors(i, j):
                colors.append(color)
            new_points[(i, j)] = HSBK.average(colors)
        self.points = new_points

    def blur_by_distance(self) -> None:
        """Similar to blur but will find the 8 closest points as opposed to the 8
        surrounding points."""
        new_points = {}
        for (i, j), _ in self:
            # closest_points always returns the point itself, and
            # color_weighting keeps every candidate when they are all at
            # distance zero, so the average is never taken over an empty list.
            distances = self.closest_points(i, j, 8)
            new_points[(i, j)] = HSBK.average(list(color_weighting(distances)))
        self.points = new_points

    def points_for_tile(
        self, tile: tuple[int, int] | None, width: int, height: int
    ) -> list[HSBK]:
        """Return a list of HSBK values for this tile.

        For any point on the tile that doesn't have a corresponding point on the
        canvas return a grey value. This is useful for when we tell the applier
        to not fill in the gaps.

        Args:
            tile: Top-left pixel coordinates (x, y) of the tile, or None for (0, 0).
                Convert a device's ``user_x``/``user_y`` with
                :func:`lifx.geometry.tile_origin_pixels` — they are not pixels.
            width: Grid width in pixels (8 for a Tile, 5 for a Candle)
            height: Grid height in pixels (8 for a Tile, 6 for a Candle)

        Returns:
            List of HSBK colors in row-major order
        """
        tile_x, tile_y = tile if tile else (0, 0)
        result = []
        grey = HSBK(hue=0, saturation=0, brightness=0.3, kelvin=3500)

        for j in range(tile_y, tile_y + height):
            for i in range(tile_x, tile_x + width):
                if (i, j) in self.points:
                    result.append(self.points[(i, j)])
                else:
                    result.append(grey)

        return result

    def fill_in_points(
        self, canvas: Canvas, left_x: int, top_y: int, tile_width: int, tile_height: int
    ) -> None:
        """Fill in the gaps on this canvas by blurring the points on the provided canvas

        We blur by finding the 4 closest points for each point on our tile and
        averaging them.

        Args:
            canvas: Source canvas to interpolate from
            left_x: Left x pixel coordinate of tile
            top_y: Top y pixel coordinate of tile
            tile_width: Width of tile in pixels
            tile_height: Height of tile in pixels
        """
        for j in range(top_y, top_y + tile_height):
            for i in range(left_x, left_x + tile_width):
                distances = canvas.closest_points(i, j, 4)
                weighted = list(color_weighting(distances))
                if weighted:
                    self[(i, j)] = HSBK.average(weighted)

    def closest_points(self, i: int, j: int, consider: int) -> list[tuple[int, HSBK]]:
        """Return [(distance, color), ...] for the closest consider amount of
        points to (i, j)."""
        distances: list[tuple[int, HSBK]] = []

        for (x, y), color in self:
            distances.append(((x - i) ** 2 + (y - j) ** 2, color))

        def get_key(
            dc: tuple[int, HSBK],
        ) -> tuple[int, tuple[float, float, float, int]]:
            return (
                dc[0],
                (dc[1].hue, dc[1].saturation, dc[1].brightness, dc[1].kelvin),
            )

        distances = sorted(distances, key=get_key)
        return distances[:consider]

    def __iter__(self) -> Iterator[tuple[tuple[int, int], HSBK]]:
        """Yield ((i, j), color) pairs for all our points."""
        yield from self.points.items()

    def __getitem__(self, point: tuple[int, int]) -> HSBK:
        """Return the color at point where point is (i, j)."""
        return self.points[point]

    def __setitem__(self, key: tuple[int, int], color: HSBK) -> None:
        """Set the color at point where point is (i, j)."""
        self.points[key] = color

    def __contains__(self, point: tuple[int, int]) -> bool:
        """Return whether this point has a color where point is (i, j)."""
        return point in self.points

    def __repr__(self) -> str:
        """Return string representation."""
        return f"Canvas({len(self.points)} points)"
