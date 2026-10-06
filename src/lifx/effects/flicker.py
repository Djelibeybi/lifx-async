"""Flicker effect implementation.

This module provides the EffectFlicker class for fire/candle flicker effects
using layered sine waves for organic brightness variation.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import KELVIN_AMBER, MAX_KELVIN, MIN_KELVIN
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect

if TYPE_CHECKING:
    from lifx.devices.light import Light

# Radians of spatial phase each flicker wave advances across the whole canvas.
_SPATIAL: tuple[float, float, float] = (17.1, 31.7, 53.3)

# A ring needs a whole number of cycles to close on itself, so each wave holds
# the nearest whole number of cycles to the one above (about 3, 5 and 8).
_RING_SPATIAL: tuple[float, float, float] = (
    6.0 * math.pi,
    10.0 * math.pi,
    16.0 * math.pi,
)


class EffectFlicker(FrameEffect):
    """Fire/candle flicker effect using layered sine waves.

    Creates organic brightness variation with warm colors ranging from
    deep red to yellow. On matrix devices, applies vertical brightness
    falloff so bottom rows are hotter.

    On a Mirror ring (``FrameContext.wraps``) each flicker wave holds a whole
    number of cycles round the ring, so zone 0 flickers in step with the last
    zone and there is no seam.

    Attributes:
        intensity: Flicker intensity 0.0-1.0 (higher = more variation)
        speed: Animation speed multiplier (higher = faster flicker)
        kelvin_min: Minimum color temperature
        kelvin_max: Maximum color temperature
        brightness: Base brightness level

    Example:
        ```python
        # Default candle flicker
        effect = EffectFlicker()
        await conductor.start(effect, lights)

        # Intense fast fire
        effect = EffectFlicker(intensity=1.0, speed=2.0, brightness=1.0)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        intensity: float = 0.7,
        speed: float = 1.0,
        kelvin_min: int = 1500,
        kelvin_max: int = 2500,
        brightness: float = 0.8,
    ) -> None:
        """Initialize flicker effect.

        Args:
            power_on: Power on devices if off (default True)
            intensity: Flicker intensity 0.0-1.0 (default 0.7)
            speed: Animation speed multiplier, must be > 0 (default 1.0)
            kelvin_min: Minimum color temperature (default 1500)
            kelvin_max: Maximum color temperature (default 2500)
            brightness: Base brightness 0.0-1.0 (default 0.8)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if not (0.0 <= intensity <= 1.0):
            raise ValueError(f"Intensity must be 0.0-1.0, got {intensity}")
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if kelvin_min < MIN_KELVIN:
            raise ValueError(f"kelvin_min must be >= {MIN_KELVIN}, got {kelvin_min}")
        if kelvin_max > MAX_KELVIN:
            raise ValueError(f"kelvin_max must be <= {MAX_KELVIN}, got {kelvin_max}")
        if kelvin_min > kelvin_max:
            raise ValueError(
                f"kelvin_min ({kelvin_min}) must be <= kelvin_max ({kelvin_max})"
            )
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.intensity = intensity
        self.speed = speed
        self.kelvin_min = kelvin_min
        self.kelvin_max = kelvin_max
        self.brightness = brightness

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "flicker"

    def _flicker(self, t: float, seed: float, ring: bool = False) -> float:
        """Return 0.0-1.0 flicker value from layered sine waves.

        Uses three sine waves with prime-ish frequency ratios for
        organic, non-repeating variation.

        Args:
            t: Time value (elapsed_s * speed)
            seed: Spatial seed (pixel position / pixel_count)
            ring: True on a canvas that wraps. Each wave then holds a whole
                number of cycles round the ring, so zone 0 carries on from the
                last zone with no jump.

        Returns:
            Flicker intensity between 0.0 and 1.0
        """
        k1, k2, k3 = _RING_SPATIAL if ring else _SPATIAL
        v1 = math.sin(t * 3.7 + seed * k1) * 0.5 + 0.5
        v2 = math.sin(t * 7.3 + seed * k2) * 0.25 + 0.5
        v3 = math.sin(t * 13.1 + seed * k3) * 0.125 + 0.5
        return (v1 + v2 + v3) / 3.0

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of flicker colors for one device.

        Each pixel gets a unique flicker pattern based on its spatial
        position. Matrix devices get vertical brightness falloff.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        t = ctx.elapsed_s * self.speed
        is_matrix = ctx.canvas_height > 1
        kelvin_range = self.kelvin_max - self.kelvin_min

        colors: list[HSBK] = []
        for i in range(ctx.pixel_count):
            seed = i / max(ctx.pixel_count, 1)
            flicker = self._flicker(t, seed, ctx.wraps)

            # Brightness: base * (1 - intensity + intensity * flicker)
            pixel_brightness = self.brightness * (
                1.0 - self.intensity + self.intensity * flicker
            )

            # Matrix vertical falloff: bottom rows hotter
            if is_matrix:
                y = i // ctx.canvas_width
                y_factor = 1.0 - (y / ctx.canvas_height) ** 0.7
                pixel_brightness *= y_factor

            pixel_brightness = max(0.0, min(1.0, pixel_brightness))

            # Hue: 0 (red) at low flicker, 40 (yellow) at high flicker
            hue = round(flicker * 40)

            # Saturation: high warmth
            saturation = 0.85 + 0.15 * (1.0 - flicker)

            # Kelvin: interpolate based on flicker
            kelvin = round(self.kelvin_min + flicker * kelvin_range)

            colors.append(
                HSBK(
                    hue=hue,
                    saturation=saturation,
                    brightness=pixel_brightness,
                    kelvin=kelvin,
                )
            )

        return colors

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        Args:
            _light: The device being powered on (unused)

        Returns:
            Warm amber color at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=20,
            saturation=1.0,
            brightness=0.0,
            kelvin=KELVIN_AMBER,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with flicker effect.

        Flicker requires color capability to manipulate hue/saturation.

        Args:
            light: The light device to check

        Returns:
            True if light has color support, False otherwise
        """
        if light.capabilities is None:
            await light.ensure_capabilities()
        return light.capabilities.has_color if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Flicker can inherit prestate from another flicker effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectFlicker, False otherwise
        """
        return isinstance(other, EffectFlicker)

    def __repr__(self) -> str:
        """String representation of flicker effect."""
        return (
            f"EffectFlicker(intensity={self.intensity}, speed={self.speed}, "
            f"kelvin_min={self.kelvin_min}, kelvin_max={self.kelvin_max}, "
            f"brightness={self.brightness}, power_on={self.power_on})"
        )
