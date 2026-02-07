"""Sunrise and sunset effect implementations.

This module provides EffectSunrise and EffectSunset classes for
simulating sunrise and sunset color transitions on matrix devices.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

from lifx.color import HSBK
from lifx.const import KELVIN_COOL
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect

if TYPE_CHECKING:
    from lifx.devices.light import Light

SunOrigin = Literal["bottom", "center"]
_VALID_ORIGINS: tuple[str, ...] = ("bottom", "center")


def _sun_frame(
    ctx: FrameContext,
    progress: float,
    brightness: float,
    origin: SunOrigin = "bottom",
) -> list[HSBK]:
    """Generate a frame for sun transition effects.

    Uses a radial model centered at a configurable origin point on the
    canvas. The sun emerges from (or retreats to) this point, expanding
    outward through color phase transitions: night, dawn, golden hour,
    morning, daylight. Nearby pixels transition first, creating a radial
    wavefront.

    Args:
        ctx: Frame context with timing and layout info
        progress: Transition progress 0.0 (night) to 1.0 (day)
        brightness: Peak brightness at full day
        origin: Sun origin point — "bottom" (center of bottom row,
            ideal for rectangular tiles) or "center" (middle of canvas,
            ideal for round/oval Ceiling lights)

    Returns:
        List of HSBK colors (length equals ctx.pixel_count)
    """
    progress = max(0.0, min(1.0, progress))

    # Sun center point
    cx = (ctx.canvas_width - 1) / 2.0
    if origin == "center":
        cy = (ctx.canvas_height - 1) / 2.0
    else:  # "bottom"
        cy = ctx.canvas_height - 1  # bottom row (y increases downward)

    # Max distance from sun center to farthest corner (top-left/right)
    max_dist = math.sqrt(cx * cx + cy * cy) if (cx > 0 or cy > 0) else 1.0

    # Spread factor: controls how much radial distance delays the phase.
    # At spread=0.6, the bottom-center leads by ~0.6 worth of progress
    # ahead of the top corners, creating a visible expanding wavefront.
    spread = 0.6

    colors: list[HSBK] = []
    for i in range(ctx.pixel_count):
        x = i % ctx.canvas_width
        y = i // ctx.canvas_width

        # Radial distance from sun center (normalized 0–1)
        dx = x - cx
        dy = y - cy
        dist = math.sqrt(dx * dx + dy * dy)
        norm_dist = dist / max_dist if max_dist > 0 else 0.0

        # Per-pixel progress: center leads, edges lag behind.
        # Scaling by (1 + spread) guarantees all pixels reach 1.0
        # when global progress = 1.0.
        pp = progress * (1.0 + spread) - norm_dist * spread
        pp = max(0.0, min(1.0, pp))

        # Perceptual brightness curve per pixel (gamma 2.2)
        pp_bright = pp**2.2

        # Color phase based on this pixel's effective progress
        if pp < 0.2:
            # Night: deep navy blue
            phase = pp / 0.2
            hue = 240
            saturation = 0.8
            pixel_brightness = brightness * 0.02 * (1 + phase * 2)
            kelvin = 1500
        elif pp < 0.4:
            # Dawn: purple/magenta horizon
            phase = (pp - 0.2) / 0.2
            hue = round(280 + phase * 60)  # 280 → 340
            saturation = 0.7 + 0.2 * (1 - norm_dist)
            pixel_brightness = brightness * (0.06 + 0.14 * phase)
            kelvin = round(1500 + phase * 500)
        elif pp < 0.6:
            # Golden hour: orange/red/gold
            phase = (pp - 0.4) / 0.2
            hue = round(20 + phase * 20)  # 20 → 40
            saturation = 0.8 - 0.2 * phase
            pixel_brightness = brightness * pp_bright
            kelvin = round(2000 + phase * 1000)
        elif pp < 0.8:
            # Morning: yellow/warm white
            phase = (pp - 0.6) / 0.2
            hue = round(50 + phase * 10)  # 50 → 60
            saturation = 0.6 - 0.3 * phase
            pixel_brightness = brightness * pp_bright
            kelvin = round(3000 + phase * 500)
        else:
            # Day: neutral warm white
            phase = (pp - 0.8) / 0.2
            hue = 60
            saturation = max(0.1, 0.3 - 0.2 * phase)
            pixel_brightness = brightness * pp_bright
            kelvin = round(3500 + phase * 500)

        # Radial proximity boost: pixels near center are brighter
        proximity = max(0.0, 1.0 - norm_dist * 1.5)
        pixel_brightness *= 0.5 + 0.5 * proximity

        # Inner pixels are warmer (redder hue, more saturated)
        if norm_dist < 0.5:
            warmth = 1.0 - norm_dist * 2
            hue = max(0, hue - round(warmth * 20))
            saturation = min(1.0, saturation + warmth * 0.2)

        pixel_brightness = max(0.0, min(1.0, pixel_brightness))
        hue = max(0, min(360, hue))

        colors.append(
            HSBK(
                hue=hue,
                saturation=saturation,
                brightness=pixel_brightness,
                kelvin=kelvin,
            )
        )

    return colors


class EffectSunrise(FrameEffect):
    """Sunrise effect transitioning from night to daylight.

    Matrix only — simulates a sunrise with a radial expansion from a
    configurable origin point, progressing through night, dawn, golden
    hour, morning, and daylight. The sun grows outward from the origin,
    with nearby pixels transitioning first.

    Use ``origin="bottom"`` (default) for rectangular tiles where the
    sun rises from the bottom edge, or ``origin="center"`` for round/oval
    Ceiling lights where the sun expands from the middle.

    Attributes:
        brightness: Peak brightness at full daylight
        origin: Sun origin point ("bottom" or "center")

    Example:
        ```python
        # 60-second sunrise from bottom (rectangular tiles)
        effect = EffectSunrise(duration=60)
        await conductor.start(effect, [matrix_light])

        # Sunrise from center (round Ceiling lights)
        effect = EffectSunrise(duration=60, origin="center")
        await conductor.start(effect, [ceiling_light])
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        duration: float = 60.0,
        brightness: float = 1.0,
        origin: SunOrigin = "bottom",
    ) -> None:
        """Initialize sunrise effect.

        Args:
            power_on: Power on devices if off (default True)
            duration: Effect duration in seconds (default 60.0)
            brightness: Peak brightness 0.0-1.0 at full day (default 1.0)
            origin: Sun origin point — "bottom" for center of bottom row
                (rectangular tiles) or "center" for middle of canvas
                (round/oval Ceiling lights). Default "bottom".

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if duration <= 0:
            raise ValueError(f"Duration must be positive, got {duration}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if origin not in _VALID_ORIGINS:
            raise ValueError(f"Origin must be 'bottom' or 'center', got '{origin}'")

        super().__init__(power_on=power_on, fps=20.0, duration=duration)

        self.brightness = brightness
        self.origin: SunOrigin = origin

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "sunrise"

    @property
    def restore_on_complete(self) -> bool:
        """Skip state restoration so light stays at daylight."""
        return False

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of sunrise colors.

        Progress goes from 0 (night) to 1 (day) over the duration.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        progress = ctx.elapsed_s / self._duration if self._duration else 1.0
        return _sun_frame(ctx, progress, self.brightness, self.origin)

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color for sunrise (deep navy).

        Args:
            _light: The device being powered on (unused)

        Returns:
            Deep navy blue at zero brightness
        """
        return HSBK(hue=240, saturation=0.8, brightness=0.0, kelvin=1500)

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with sunrise effect.

        Sunrise requires matrix capability for 2D gradient simulation.

        Args:
            light: The light device to check

        Returns:
            True if light has matrix support, False otherwise
        """
        if light.capabilities is None:
            await light._ensure_capabilities()
        return light.capabilities.has_matrix if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Sunrise can inherit prestate from another sunrise.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectSunrise, False otherwise
        """
        return isinstance(other, EffectSunrise)

    def __repr__(self) -> str:
        """String representation of sunrise effect."""
        return (
            f"EffectSunrise(duration={self._duration}, "
            f"brightness={self.brightness}, origin='{self.origin}', "
            f"power_on={self.power_on})"
        )


class EffectSunset(FrameEffect):
    """Sunset effect transitioning from daylight to night.

    Matrix only — simulates a sunset with a radial contraction toward a
    configurable origin point, progressing from daylight through golden
    hour to night. The sun shrinks inward toward the origin, with
    distant pixels darkening first. Optionally powers off the light
    when complete.

    Use ``origin="bottom"`` (default) for rectangular tiles where the
    sun sets toward the bottom edge, or ``origin="center"`` for
    round/oval Ceiling lights where the sun contracts to the middle.

    Attributes:
        brightness: Starting brightness at daylight
        power_off: Whether to power off lights after sunset completes
        origin: Sun origin point ("bottom" or "center")

    Example:
        ```python
        # 60-second sunset that powers off the light
        effect = EffectSunset(duration=60, power_off=True)
        await conductor.start(effect, [matrix_light])

        # Sunset from center (round Ceiling lights)
        effect = EffectSunset(duration=60, origin="center")
        await conductor.start(effect, [ceiling_light])
        ```
    """

    def __init__(
        self,
        power_on: bool = False,
        duration: float = 60.0,
        brightness: float = 1.0,
        power_off: bool = True,
        origin: SunOrigin = "bottom",
    ) -> None:
        """Initialize sunset effect.

        Args:
            power_on: Power on devices if off (default False)
            duration: Effect duration in seconds (default 60.0)
            brightness: Starting brightness 0.0-1.0 (default 1.0)
            power_off: Power off lights when sunset completes (default True)
            origin: Sun origin point — "bottom" for center of bottom row
                (rectangular tiles) or "center" for middle of canvas
                (round/oval Ceiling lights). Default "bottom".

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if duration <= 0:
            raise ValueError(f"Duration must be positive, got {duration}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if origin not in _VALID_ORIGINS:
            raise ValueError(f"Origin must be 'bottom' or 'center', got '{origin}'")

        super().__init__(power_on=power_on, fps=20.0, duration=duration)

        self.brightness = brightness
        self.power_off = power_off
        self.origin: SunOrigin = origin

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "sunset"

    @property
    def restore_on_complete(self) -> bool:
        """Skip state restoration when sunset powers off lights."""
        return not self.power_off

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of sunset colors.

        Progress goes from 1 (day) to 0 (night) over the duration.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        progress = 1.0 - (ctx.elapsed_s / self._duration if self._duration else 0.0)
        return _sun_frame(ctx, progress, self.brightness, self.origin)

    async def async_play(self) -> None:
        """Run the sunset frame loop, then optionally power off.

        Calls the parent frame loop and, if power_off is True, powers off
        all participant lights after the last frame.
        """
        await super().async_play()

        if self.power_off and self.participants:
            import asyncio

            await asyncio.gather(
                *(light.set_power(False) for light in self.participants)
            )

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color for sunset (warm daylight).

        Args:
            _light: The device being powered on (unused)

        Returns:
            Warm daylight color at configured brightness
        """
        return HSBK(
            hue=60,
            saturation=0.2,
            brightness=self.brightness,
            kelvin=KELVIN_COOL,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with sunset effect.

        Sunset requires matrix capability for 2D gradient simulation.

        Args:
            light: The light device to check

        Returns:
            True if light has matrix support, False otherwise
        """
        if light.capabilities is None:
            await light._ensure_capabilities()
        return light.capabilities.has_matrix if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Sunset can inherit prestate from another sunset.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectSunset, False otherwise
        """
        return isinstance(other, EffectSunset)

    def __repr__(self) -> str:
        """String representation of sunset effect."""
        return (
            f"EffectSunset(duration={self._duration}, "
            f"brightness={self.brightness}, origin='{self.origin}', "
            f"power_off={self.power_off}, power_on={self.power_on})"
        )
