"""Progress bar effect implementation.

This module provides the EffectProgress class for animated progress bars
on multizone lights. The filled region has a traveling bright spot.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from lifx.color import HSBK, Colors
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect

if TYPE_CHECKING:
    from lifx.devices.light import Light


class EffectProgress(FrameEffect):
    """Animated progress bar for multizone lights.

    Displays a filled/unfilled bar where the filled region has a traveling
    bright spot that animates along it. The user can update the position
    value at any time and the bar grows/shrinks accordingly.

    The foreground can be a single color or a gradient (list of HSBK stops).
    When a gradient is used, each pixel's color is determined by its position
    across the full bar — so the gradient reveals progressively as the bar
    grows, like a thermometer.

    Multizone only — ``is_light_compatible()`` checks for ``has_multizone``.

    Attributes:
        start_value: Start of the value range
        end_value: End of the value range
        position: Current progress position (mutable)
        foreground: Color or gradient of the filled region (mutable)
        background: Color of the unfilled region
        spot_brightness: Peak brightness of the traveling spot
        spot_width: Width of the spot as fraction of filled bar
        spot_speed: Spot oscillation speed in cycles per second

    Example:
        ```python
        # Single color progress bar
        effect = EffectProgress(foreground=Colors.BLUE, end_value=100)
        await conductor.start(effect, [strip])
        effect.position = 45.0

        # Gradient progress bar (blue -> cyan -> green -> yellow -> red)
        gradient = [
            HSBK(hue=240, saturation=1.0, brightness=0.8, kelvin=3500),
            HSBK(hue=180, saturation=1.0, brightness=0.8, kelvin=3500),
            HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),
            HSBK(hue=60, saturation=1.0, brightness=0.8, kelvin=3500),
            HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500),
        ]
        effect = EffectProgress(foreground=gradient, end_value=100)
        await conductor.start(effect, [strip])
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        start_value: float = 0.0,
        end_value: float = 100.0,
        position: float = 0.0,
        foreground: HSBK | list[HSBK] | None = None,
        background: HSBK | None = None,
        spot_brightness: float = 1.0,
        spot_width: float = 0.15,
        spot_speed: float = 1.0,
    ) -> None:
        """Initialize progress effect.

        Args:
            power_on: Power on devices if off (default True)
            start_value: Start of value range (default 0.0)
            end_value: End of value range (default 100.0)
            position: Initial progress position (default 0.0)
            foreground: Color or gradient of filled region. Pass a single
                HSBK for a solid bar, or a list of >= 2 HSBK stops for a
                gradient. Defaults to Colors.GREEN.
            background: Color of unfilled region (default dim neutral)
            spot_brightness: Peak brightness of traveling spot 0.0-1.0 (default 1.0)
            spot_width: Spot width as fraction of bar 0.0-1.0 (default 0.15)
            spot_speed: Spot cycles per second, must be > 0 (default 1.0)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if start_value >= end_value:
            raise ValueError(
                f"start_value ({start_value}) must be < end_value ({end_value})"
            )
        if not (start_value <= position <= end_value):
            raise ValueError(
                f"position ({position}) must be between "
                f"start_value ({start_value}) and end_value ({end_value})"
            )
        if isinstance(foreground, list) and len(foreground) < 2:
            raise ValueError(
                f"Foreground gradient must have at least 2 stops, got {len(foreground)}"
            )
        if not (0.0 <= spot_brightness <= 1.0):
            raise ValueError(f"spot_brightness must be 0.0-1.0, got {spot_brightness}")
        if not (0.0 <= spot_width <= 1.0):
            raise ValueError(f"spot_width must be 0.0-1.0, got {spot_width}")
        if spot_speed <= 0:
            raise ValueError(f"spot_speed must be positive, got {spot_speed}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.start_value = start_value
        self.end_value = end_value
        self.position = position
        self.foreground: HSBK | list[HSBK] = (
            foreground if foreground is not None else Colors.GREEN
        )
        self.background = (
            background
            if background is not None
            else HSBK(hue=0, saturation=0.0, brightness=0.05, kelvin=3500)
        )
        self.spot_brightness = spot_brightness
        self.spot_width = spot_width
        self.spot_speed = spot_speed

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "progress"

    def _gradient_color(self, position: float, stops: list[HSBK]) -> HSBK:
        """Interpolate a color from a gradient at the given position.

        Uses shortest-path hue wrapping and linear interpolation for
        saturation, brightness, and kelvin.

        Args:
            position: Position along the gradient, 0.0 to 1.0.
            stops: List of HSBK color stops (>= 2 entries).

        Returns:
            Interpolated HSBK color.
        """
        position = max(0.0, min(1.0, position))
        n = len(stops) - 1
        scaled = position * n
        idx = min(int(scaled), n - 1)
        frac = scaled - idx

        c1 = stops[idx]
        c2 = stops[idx + 1]

        # Shortest-path hue interpolation
        hue_diff = c2.hue - c1.hue
        if hue_diff > 180:
            hue_diff -= 360
        elif hue_diff < -180:
            hue_diff += 360
        hue = (c1.hue + frac * hue_diff) % 360

        return HSBK(
            hue=round(hue),
            saturation=c1.saturation + frac * (c2.saturation - c1.saturation),
            brightness=c1.brightness + frac * (c2.brightness - c1.brightness),
            kelvin=round(c1.kelvin + frac * (c2.kelvin - c1.kelvin)),
        )

    def _foreground_at(self, position: float) -> HSBK:
        """Return the foreground color at a normalized bar position.

        For a single-color foreground, returns that color directly.
        For a gradient, interpolates based on position across the full bar.

        Args:
            position: Pixel position along the full bar, 0.0 to 1.0.

        Returns:
            HSBK color for this position.
        """
        fg = self.foreground
        if isinstance(fg, list):
            return self._gradient_color(position, fg)
        return fg

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of progress bar colors for one device.

        Divides pixels into filled (foreground) and unfilled (background)
        regions. A bright spot oscillates within the filled region.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        value_range = self.end_value - self.start_value
        fill = (
            (self.position - self.start_value) / value_range if value_range > 0 else 0.0
        )
        fill = max(0.0, min(1.0, fill))
        fill_end = round(fill * ctx.pixel_count)

        colors: list[HSBK] = []

        # Spot position oscillates within the filled region
        if fill_end > 0:
            spot_pos = fill_end * (
                (math.sin(ctx.elapsed_s * self.spot_speed * 2 * math.pi) + 1) / 2
            )
            spot_pixel_width = max(1.0, self.spot_width * fill_end)
        else:
            spot_pos = 0.0
            spot_pixel_width = 1.0

        for i in range(ctx.pixel_count):
            if i < fill_end:
                # Get base color (single color or gradient sample)
                bar_pos = i / max(ctx.pixel_count - 1, 1)
                base = self._foreground_at(bar_pos)

                # Spot brightness boost
                dist = abs(i - spot_pos)
                boost = math.exp(-((dist / spot_pixel_width) ** 2))
                pixel_brightness = base.brightness + boost * (
                    self.spot_brightness - base.brightness
                )
                pixel_brightness = max(0.0, min(1.0, pixel_brightness))
                colors.append(
                    HSBK(
                        hue=base.hue,
                        saturation=base.saturation,
                        brightness=pixel_brightness,
                        kelvin=base.kelvin,
                    )
                )
            else:
                colors.append(self.background)

        return colors

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        Args:
            _light: The device being powered on (unused)

        Returns:
            The background color (bar starts dark)
        """
        return self.background

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with progress effect.

        Progress requires multizone capability for a meaningful bar display.

        Args:
            light: The light device to check

        Returns:
            True if light has multizone support, False otherwise
        """
        if light.capabilities is None:
            await light._ensure_capabilities()
        return light.capabilities.has_multizone if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Progress can inherit prestate from another progress effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectProgress, False otherwise
        """
        return isinstance(other, EffectProgress)

    def __repr__(self) -> str:
        """String representation of progress effect."""
        fg = self.foreground
        fg_repr = f"gradient({len(fg)} stops)" if isinstance(fg, list) else str(fg)
        return (
            f"EffectProgress(position={self.position}, "
            f"start_value={self.start_value}, end_value={self.end_value}, "
            f"foreground={fg_repr}, background={self.background}, "
            f"power_on={self.power_on})"
        )
