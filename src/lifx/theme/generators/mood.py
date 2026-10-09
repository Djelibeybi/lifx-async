"""Paint a theme the way the LIFX app paints a mood.

The app chooses a still image by the theme's ``static_mode`` and fits the
theme's colours to the light with a run-weighted stretch. ``MoodGenerator``
reproduces those recipes with no I/O: a device reads its own geometry and
brightness, asks the generator for colours and writes them.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence

from lifx.color import HSBK
from lifx.const import MAX_PALETTE_COLORS
from lifx.theme.theme import Theme

# Static modes with a recipe. Any other mode, and None, paints as blended,
# as the app does.
_RECIPES = frozenset({"blended", "grid_static", "solid", "solid_loop", "solid_static"})

# An entry at or above this brightness never rescales below it.
_MIN_VISIBLE = 0.01


class MoodGenerator:
    """Turn a theme into the colours the LIFX app paints for it.

    The ``get_*_colors()`` methods paint a still image; ``get_palette()``
    gives the colours an animated mood steps through. Each is rescaled so its
    brightest colour matches the light's brightness.

    Example:
        ```python
        generator = MoodGenerator(get_theme("van_gogh"))
        colors = generator.get_matrix_colors(8, 8, brightness=0.6)
        palette = generator.get_palette(brightness=0.6)
        ```
    """

    def __init__(self, theme: Theme, rng: random.Random | None = None) -> None:
        """Create a generator for one theme.

        Args:
            theme: The theme to paint. Its ``static_mode`` picks the recipe;
                None, or a mode with no recipe, paints as ``blended``.
            rng: Random source for the shuffles, for repeatable output.
        """
        self._colors = list(theme.colors)
        mode = theme.static_mode
        self._mode = mode if mode in _RECIPES else "blended"
        self._rng = rng if rng is not None else random.Random()

    def get_multizone_colors(self, zone_count: int, brightness: float) -> list[HSBK]:
        """Colours for a strip, one per zone.

        Args:
            zone_count: Number of zones to fill
            brightness: The light's current brightness, 0.0 to 1.0

        Returns:
            One colour per zone
        """
        if self._mode == "blended":
            colors = self._gradient(self._shuffled(self._colors), zone_count)
        elif self._mode == "solid":
            colors = self._stretch(
                self._shuffled(self._distinct(self._colors)), zone_count
            )
        else:
            colors = self._stretch(self._colors, zone_count)
        return self._rescale(colors, brightness)

    # Interior cells blend their nearest edge cells, as the app does.
    _NEAREST_EDGE_CELLS = 5

    def get_matrix_colors(
        self, width: int, height: int, brightness: float, *, vertical: bool = False
    ) -> list[HSBK]:
        """Colours for one matrix light, in row-major order.

        Args:
            width: Pixels per row, as the device reports
            height: Rows, as the device reports
            brightness: The light's current brightness, 0.0 to 1.0
            vertical: Paint stripe moods as bands along the long axis, as the
                app does on every Candle, the Tube and the Mirror

        Returns:
            ``width * height`` colours
        """
        return self._rescale(self._paint(width, height, vertical=vertical), brightness)

    def get_chain_colors(
        self, tile_count: int, width: int, height: int, brightness: float
    ) -> list[list[HSBK]]:
        """Colours for a Tile chain, laid out in chain order.

        The app ignores where the tiles sit: one canvas ``width * tile_count``
        wide is painted and sliced per tile. A blended mood paints each tile
        on its own.

        Args:
            tile_count: Tiles in the chain
            width: Pixels per row of one tile
            height: Rows of one tile
            brightness: The light's current brightness, 0.0 to 1.0

        Returns:
            Per tile, ``width * height`` colours in row-major order
        """
        if self._mode == "blended":
            tiles = [
                self._blended_matrix(self._colors, width, height)
                for _ in range(tile_count)
            ]
        else:
            canvas_width = width * tile_count
            canvas = self._paint(canvas_width, height)
            tiles = [
                [
                    canvas[row * canvas_width + tile * width + col]
                    for row in range(height)
                    for col in range(width)
                ]
                for tile in range(tile_count)
            ]
        flat = self._rescale([c for tile in tiles for c in tile], brightness)
        size = width * height
        return [flat[i * size : (i + 1) * size] for i in range(tile_count)]

    def get_bulb_colors(self, brightnesses: Sequence[float]) -> list[HSBK]:
        """Deal the theme's distinct colours, shuffled, one per bulb in turn.

        Args:
            brightnesses: Each bulb's current brightness, in bulb order

        Returns:
            One colour per bulb, rescaled to that bulb's brightness
        """
        deck = self._shuffled(self._distinct(self._colors))
        dealt: list[HSBK] = []
        for index, brightness in enumerate(brightnesses):
            # Rescale the whole deck so each bulb keeps the theme's relative
            # brightness, then take this bulb's card.
            dealt.append(self._rescale(deck, brightness)[index % len(deck)])
        return dealt

    def get_palette(self, brightness: float) -> list[HSBK]:
        """The theme's colours, in order, rescaled to the light's brightness.

        An animated mood steps through these: a bulb's colour loop and a
        matrix light's firmware MORPH, as the app rescales them.

        Args:
            brightness: The light's brightness, 0.0 to 1.0. At 0.0 the
                colours are returned unchanged.

        Returns:
            One colour per theme colour, the brightest at ``brightness``
        """
        return self._rescale(self._colors, brightness)

    @staticmethod
    def morph_palette(colors: Sequence[HSBK]) -> list[HSBK]:
        """Reduce a palette to what firmware MORPH can carry.

        The app's run-weighted reduction: deterministic, so only the order
        the caller shuffles it into varies.

        Args:
            colors: Palette in source order

        Returns:
            The palette unchanged when it fits, else ``MAX_PALETTE_COLORS``
            colours weighted by the area each run covers
        """
        if len(colors) <= MAX_PALETTE_COLORS:
            return list(colors)
        return MoodGenerator._stretch(colors, MAX_PALETTE_COLORS)

    @staticmethod
    def _stretch(colors: Sequence[HSBK], n: int) -> list[HSBK]:
        """Fit a list to ``n`` entries by run weight, as the app does."""
        if len(colors) == n:
            return list(colors)
        run_colors: list[HSBK] = []
        run_lengths: list[int] = []
        for color in colors:
            if run_colors and run_colors[-1] == color:
                run_lengths[-1] += 1
            else:
                run_colors.append(color)
                run_lengths.append(1)
        alloc = [math.ceil(n * length / len(colors)) for length in run_lengths]
        # Each ceil() overshoots by less than one cell, so the total exceeds n
        # by fewer than len(runs) and a single pass trims it from the front.
        for index in range(sum(alloc) - n):
            alloc[index] -= 1
        stretched: list[HSBK] = []
        for color, count in zip(run_colors, alloc):
            stretched.extend([color] * count)
        return stretched

    @staticmethod
    def _rescale(colors: Sequence[HSBK], brightness: float) -> list[HSBK]:
        """Scale so the brightest entry equals the light's brightness."""
        brightest = max((c.brightness for c in colors), default=0.0)
        if brightness <= 0 or brightest <= 0:
            return list(colors)
        factor = brightness / brightest
        rescaled: list[HSBK] = []
        for color in colors:
            value = min(color.brightness * factor, 1.0)
            if color.brightness >= _MIN_VISIBLE:
                value = max(value, _MIN_VISIBLE)
            rescaled.append(
                HSBK(
                    hue=color.hue,
                    saturation=color.saturation,
                    brightness=value,
                    kelvin=color.kelvin,
                )
            )
        return rescaled

    def _gradient(self, colors: Sequence[HSBK], cells: int) -> list[HSBK]:
        """The app's gradient: min(cells, colours - 1) segments, remainder last."""
        if cells <= 0:
            return []
        if len(colors) == 1:
            return [colors[0]] * cells
        segments = min(cells, len(colors) - 1)
        base, extra = divmod(cells, segments)
        out: list[HSBK] = []
        for index in range(segments):
            length = base + (1 if index >= segments - extra else 0)
            start, end = colors[index], colors[index + 1]
            out.extend(
                self._interpolate(start, end, step / length) for step in range(length)
            )
        return out

    @staticmethod
    def _interpolate(start: HSBK, end: HSBK, t: float) -> HSBK:
        """Blend two colours; hue goes the short way and a white has no hue."""
        start_hue = end.hue if start.saturation == 0 else start.hue
        end_hue = start.hue if end.saturation == 0 else end.hue
        delta = ((end_hue - start_hue + 180) % 360) - 180
        return HSBK(
            hue=(start_hue + delta * t) % 360,
            saturation=start.saturation + (end.saturation - start.saturation) * t,
            brightness=start.brightness + (end.brightness - start.brightness) * t,
            kelvin=round(start.kelvin + (end.kelvin - start.kelvin) * t),
        )

    @staticmethod
    def _mix(colors: Sequence[HSBK], weights: Sequence[float]) -> HSBK:
        """Weighted circular mean; whites add no hue."""
        total = sum(weights)
        x = y = 0.0
        for color, weight in zip(colors, weights):
            if color.saturation > 0:
                x += math.cos(math.radians(color.hue)) * weight
                y += math.sin(math.radians(color.hue)) * weight
        hue = math.degrees(math.atan2(y, x)) % 360 if (x or y) else 0.0
        return HSBK(
            hue=hue,
            saturation=sum(c.saturation * w for c, w in zip(colors, weights)) / total,
            brightness=sum(c.brightness * w for c, w in zip(colors, weights)) / total,
            kelvin=round(sum(c.kelvin * w for c, w in zip(colors, weights)) / total),
        )

    @staticmethod
    def _distinct(colors: Sequence[HSBK]) -> list[HSBK]:
        """Distinct colours in the order first seen."""
        return list(dict.fromkeys(colors))

    def _shuffled(self, colors: Sequence[HSBK]) -> list[HSBK]:
        """A shuffled copy, using this generator's random source."""
        copy = list(colors)
        self._rng.shuffle(copy)
        return copy

    def _paint(self, width: int, height: int, *, vertical: bool = False) -> list[HSBK]:
        """The still image for this theme's mode, unscaled."""
        stripes = self._bands if vertical else self._stripes
        if self._mode == "blended":
            return self._blended_matrix(self._colors, width, height)
        if self._mode == "grid_static":
            return self._grid(self._colors, width, height)
        if self._mode == "solid":
            return stripes(self._shuffled(self._distinct(self._colors)), width, height)
        return stripes(self._colors, width, height)

    def _blended_matrix(
        self, colors: Sequence[HSBK], width: int, height: int
    ) -> list[HSBK]:
        """Shuffled gradient round the edge, interior by distance."""
        if width < 2 or height < 2:
            # No edge walk on a single row or column: a gradient along it.
            return self._gradient(self._shuffled(colors), width * height)
        edge = self._edge_cells(width, height)
        ramp = self._gradient(self._shuffled(colors), len(edge))
        painted: dict[tuple[int, int], HSBK] = dict(zip(edge, ramp))
        for row in range(height):
            for col in range(width):
                if (row, col) in painted:
                    continue
                nearest = sorted(
                    ((math.dist((row, col), cell), painted[cell]) for cell in edge),
                    key=lambda pair: pair[0],
                )[: self._NEAREST_EDGE_CELLS]
                total = sum(distance for distance, _ in nearest)
                weights = [math.floor(total / distance) for distance, _ in nearest]
                painted[(row, col)] = self._mix([c for _, c in nearest], weights)
        return [painted[(row, col)] for row in range(height) for col in range(width)]

    @staticmethod
    def _edge_cells(width: int, height: int) -> list[tuple[int, int]]:
        """Top row left to right, both sides row by row, bottom row back."""
        cells = [(0, col) for col in range(width)]
        for row in range(1, height - 1):
            cells.extend([(row, 0), (row, width - 1)])
        cells.extend((height - 1, col) for col in reversed(range(width)))
        return cells

    @staticmethod
    def _grid(colors: Sequence[HSBK], width: int, height: int) -> list[HSBK]:
        """Stretch to every cell, rows laid out serpentine."""
        cells = MoodGenerator._stretch(colors, width * height)
        out: list[HSBK] = []
        for row in range(height):
            run = cells[row * width : (row + 1) * width]
            out.extend(run if row % 2 == 0 else reversed(run))
        return out

    @staticmethod
    def _stripes(colors: Sequence[HSBK], width: int, height: int) -> list[HSBK]:
        """Stretch to one row and repeat it on every row."""
        return MoodGenerator._stretch(colors, width) * height

    @staticmethod
    def _bands(colors: Sequence[HSBK], width: int, height: int) -> list[HSBK]:
        """Stretch to the rows; every row one colour, the first at the bottom."""
        band = MoodGenerator._stretch(colors, height)
        return [band[height - 1 - row] for row in range(height) for _ in range(width)]
