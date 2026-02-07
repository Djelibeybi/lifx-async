"""Aurora effect implementation.

This module provides the EffectAurora class for northern lights simulation
with flowing colored bands using palette interpolation and sine waves.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import KELVIN_NEUTRAL
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect

if TYPE_CHECKING:
    from lifx.devices.light import Light

_DEFAULT_PALETTE = [120, 160, 200, 260, 290]


class EffectAurora(FrameEffect):
    """Northern lights effect with flowing colored bands.

    Uses palette interpolation and sine waves to create flowing aurora-like
    patterns. Best on multizone strips and matrix lights where per-pixel
    color variation creates beautiful flowing colored bands.

    Attributes:
        speed: Animation speed multiplier
        brightness: Base brightness level
        spread: Hue degrees offset between devices

    Example:
        ```python
        # Default aurora
        effect = EffectAurora()
        await conductor.start(effect, lights)

        # Custom palette with magenta/pink tones
        effect = EffectAurora(palette=[280, 300, 320, 340])
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 1.0,
        brightness: float = 0.8,
        palette: list[int] | None = None,
        spread: float = 0.0,
    ) -> None:
        """Initialize aurora effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Animation speed multiplier, must be > 0 (default 1.0)
            brightness: Base brightness 0.0-1.0 (default 0.8)
            palette: List of hue values (0-360) defining the aurora colors.
                     Must have >= 2 entries. Defaults to green/cyan/blue/purple.
            spread: Hue degrees offset between devices 0-360 (default 0)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (0.0 <= spread <= 360.0):
            raise ValueError(f"Spread must be 0-360 degrees, got {spread}")

        if palette is not None:
            if len(palette) < 2:
                raise ValueError(
                    f"Palette must have at least 2 entries, got {len(palette)}"
                )
            for h in palette:
                if not (0 <= h <= 360):
                    raise ValueError(f"Palette hue values must be 0-360, got {h}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.brightness = brightness
        self._palette = list(palette) if palette is not None else list(_DEFAULT_PALETTE)
        self.spread = spread

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "aurora"

    def _palette_hue(self, position: float) -> int:
        """Interpolate hue from palette at continuous position.

        Uses shortest-path hue wrapping to avoid going the wrong way
        around the color wheel.

        Args:
            position: Palette position 0.0-1.0

        Returns:
            Interpolated hue value 0-360
        """
        n = len(self._palette)
        scaled = position * n
        idx = int(scaled) % n
        frac = scaled - int(scaled)
        h1 = self._palette[idx]
        h2 = self._palette[(idx + 1) % n]
        diff = h2 - h1
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360
        return round((h1 + frac * diff) % 360)

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of aurora colors for one device.

        Creates flowing colored bands with brightness modulation.
        Matrix devices get a vertical brightness gradient with the
        brightest band in the middle rows.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        t = ctx.elapsed_s * self.speed * 0.05
        device_offset = ctx.device_index * self.spread / 360.0
        is_matrix = ctx.canvas_height > 1

        colors: list[HSBK] = []
        for i in range(ctx.pixel_count):
            position = (i / max(ctx.pixel_count, 1) + t + device_offset) % 1.0
            hue = self._palette_hue(position)

            # Brightness modulation: creates bright "curtain" bands
            brightness_mod = 0.5 + 0.5 * math.sin(
                i / max(ctx.pixel_count, 1) * math.pi * 3 + t * 6
            )

            pixel_brightness = self.brightness * brightness_mod

            # Matrix vertical gradient: brightest in middle rows
            if is_matrix:
                y = i // ctx.canvas_width
                y_norm = y / max(ctx.canvas_height - 1, 1)
                y_factor = math.sin(y_norm * math.pi)
                pixel_brightness *= y_factor

            pixel_brightness = max(0.0, min(1.0, pixel_brightness))

            # Subtle saturation variation
            saturation = 0.7 + 0.3 * math.sin(position * 2 * math.pi)

            colors.append(
                HSBK(
                    hue=hue,
                    saturation=saturation,
                    brightness=pixel_brightness,
                    kelvin=KELVIN_NEUTRAL,
                )
            )

        return colors

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        Args:
            _light: The device being powered on (unused)

        Returns:
            Green aurora color at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=120,
            saturation=0.8,
            brightness=0.0,
            kelvin=KELVIN_NEUTRAL,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with aurora effect.

        Aurora requires color capability to manipulate hue/saturation.

        Args:
            light: The light device to check

        Returns:
            True if light has color support, False otherwise
        """
        if light.capabilities is None:
            await light._ensure_capabilities()
        return light.capabilities.has_color if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Aurora can inherit prestate from another aurora effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectAurora, False otherwise
        """
        return isinstance(other, EffectAurora)

    def __repr__(self) -> str:
        """String representation of aurora effect."""
        return (
            f"EffectAurora(speed={self.speed}, brightness={self.brightness}, "
            f"palette_size={len(self._palette)}, spread={self.spread}, "
            f"power_on={self.power_on})"
        )
