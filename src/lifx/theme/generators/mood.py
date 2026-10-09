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

    Example:
        ```python
        generator = MoodGenerator(get_theme("van_gogh"))
        colors = generator.get_matrix_colors(8, 8, brightness=0.6)
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
        """Colours for a strip, or for one Mirror ring.

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
