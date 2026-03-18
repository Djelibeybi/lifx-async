"""Twinkle effect -- random pixels sparkle and fade like Christmas lights.

Each pixel independently triggers a sparkle at random intervals. Sparkles
flash bright (white or a chosen hue) then decay smoothly back to the
background color via quadratic falloff. Multiple sparkles overlap naturally.

This is a stateful effect: per-pixel sparkle timers persist across frames.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import MAX_KELVIN, MIN_KELVIN
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect

if TYPE_CHECKING:
    from lifx.devices.light import Light

# Sparkle trigger rate multiplier. The per-frame probability is
# ``density * dt * SPARKLE_RATE``, tuned so density ~ 0.05 gives a
# pleasant twinkling rate at ~20 fps.
SPARKLE_RATE: float = 20.0

# Intensity threshold: above this the sparkle keeps its own hue;
# below it the hue snaps to the background.
HUE_BLEND_THRESHOLD: float = 0.5


class EffectTwinkle(FrameEffect):
    """Random pixels sparkle and fade like Christmas lights.

    Each pixel maintains an independent sparkle timer. When it triggers,
    the pixel flashes to peak brightness then decays via quadratic falloff
    (fast flash, slow tail) back to the background color.

    Attributes:
        speed: Sparkle fade duration in seconds
        density: Probability a pixel sparks per frame (0.0-1.0)
        hue: Sparkle hue in degrees (0-360)
        saturation: Sparkle saturation (0.0-1.0, 0.0=white sparkle)
        brightness: Peak sparkle brightness (0.0-1.0)
        background_hue: Background hue in degrees (0-360)
        background_saturation: Background saturation (0.0-1.0)
        background_brightness: Background brightness (0.0-1.0)
        kelvin: Color temperature (1500-9000)

    Example:
        ```python
        # White sparkles on dark background
        effect = EffectTwinkle()
        await conductor.start(effect, lights)

        # Colored sparkles on blue background
        effect = EffectTwinkle(
            hue=60,
            saturation=1.0,
            brightness=1.0,
            background_hue=240,
            background_saturation=0.8,
            background_brightness=0.1,
        )
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 1.0,
        density: float = 0.05,
        hue: int = 0,
        saturation: float = 0.0,
        brightness: float = 1.0,
        background_hue: int = 0,
        background_saturation: float = 0.0,
        background_brightness: float = 0.0,
        kelvin: int = 3500,
    ) -> None:
        """Initialize Twinkle effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Sparkle fade duration in seconds, must be > 0 (default 1.0)
            density: Per-frame sparkle probability 0.0-1.0 (default 0.05)
            hue: Sparkle hue 0-360 degrees (default 0)
            saturation: Sparkle saturation 0.0-1.0 (default 0.0, white)
            brightness: Peak sparkle brightness 0.0-1.0 (default 1.0)
            background_hue: Background hue 0-360 degrees (default 0)
            background_saturation: Background saturation 0.0-1.0 (default 0.0)
            background_brightness: Background brightness 0.0-1.0 (default 0.0)
            kelvin: Color temperature 1500-9000 (default 3500)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if not (0.0 <= density <= 1.0):
            raise ValueError(f"Density must be 0.0-1.0, got {density}")
        if not (0 <= hue <= 360):
            raise ValueError(f"Hue must be 0-360, got {hue}")
        if not (0.0 <= saturation <= 1.0):
            raise ValueError(f"Saturation must be 0.0-1.0, got {saturation}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (0 <= background_hue <= 360):
            raise ValueError(f"Background hue must be 0-360, got {background_hue}")
        if not (0.0 <= background_saturation <= 1.0):
            raise ValueError(
                f"Background saturation must be 0.0-1.0, got {background_saturation}"
            )
        if not (0.0 <= background_brightness <= 1.0):
            raise ValueError(
                f"Background brightness must be 0.0-1.0, got {background_brightness}"
            )
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.density = density
        self.hue = hue
        self.saturation = saturation
        self.brightness = brightness
        self.background_hue = background_hue
        self.background_saturation = background_saturation
        self.background_brightness = background_brightness
        self.kelvin = kelvin

        # Per-pixel sparkle state: time remaining in current sparkle (0 = idle).
        # Initialized lazily on first generate_frame call when pixel_count is known.
        self._sparkle_timers: list[float] | None = None
        # Previous elapsed_s for computing delta-time between frames.
        self._last_elapsed_s: float | None = None

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "twinkle"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of twinkling sparkles.

        On each frame, every pixel has a random chance of triggering a
        new sparkle. Active sparkles decay quadratically toward the
        background color.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        # Lazy initialization or reinitialize if pixel count changed.
        if self._sparkle_timers is None or len(self._sparkle_timers) != ctx.pixel_count:
            self._sparkle_timers = [0.0] * ctx.pixel_count
            self._last_elapsed_s = ctx.elapsed_s

        # Compute delta-time; clamp to zero on backwards jumps.
        dt = max(ctx.elapsed_s - (self._last_elapsed_s or 0.0), 0.0)
        self._last_elapsed_s = ctx.elapsed_s

        colors: list[HSBK] = []
        for i in range(ctx.pixel_count):
            # Decay existing sparkle timers.
            if self._sparkle_timers[i] > 0:
                self._sparkle_timers[i] -= dt
                if self._sparkle_timers[i] < 0:
                    self._sparkle_timers[i] = 0.0

            # Random chance to trigger a new sparkle on an idle pixel.
            trigger_chance = self.density * dt * SPARKLE_RATE
            if self._sparkle_timers[i] <= 0 and random.random() < trigger_chance:
                self._sparkle_timers[i] = self.speed

            if self._sparkle_timers[i] > 0:
                # Fraction of sparkle remaining: 1.0 at trigger, 0.0 at end.
                frac = self._sparkle_timers[i] / self.speed

                # Quadratic decay: fast flash then slow tail.
                intensity = frac * frac

                # Interpolate brightness between background and peak.
                pixel_brightness = (
                    self.background_brightness
                    + (self.brightness - self.background_brightness) * intensity
                )

                # Hold sparkle hue while bright; snap to background hue as it fades.
                if intensity > HUE_BLEND_THRESHOLD:
                    pixel_hue = self.hue
                else:
                    pixel_hue = self.background_hue

                # Blend saturation from sparkle toward background as intensity drops.
                pixel_saturation = self.saturation + (
                    self.background_saturation - self.saturation
                ) * (1.0 - intensity)

                colors.append(
                    HSBK(
                        hue=pixel_hue,
                        saturation=max(0.0, min(1.0, pixel_saturation)),
                        brightness=max(0.0, min(1.0, pixel_brightness)),
                        kelvin=self.kelvin,
                    )
                )
            else:
                colors.append(
                    HSBK(
                        hue=self.background_hue,
                        saturation=self.background_saturation,
                        brightness=self.background_brightness,
                        kelvin=self.kelvin,
                    )
                )

        return colors

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        Args:
            _light: The device being powered on (unused)

        Returns:
            Background color at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=self.background_hue,
            saturation=self.background_saturation,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with Twinkle effect.

        Twinkle works with any light that has color capability.

        Args:
            light: The light device to check

        Returns:
            True if light has color support, False otherwise
        """
        if light.capabilities is None:
            await light.ensure_capabilities()
        return light.capabilities.has_color if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Twinkle can inherit prestate from another Twinkle effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectTwinkle, False otherwise
        """
        return isinstance(other, EffectTwinkle)

    def __repr__(self) -> str:
        """String representation of Twinkle effect."""
        return (
            f"EffectTwinkle(speed={self.speed}, density={self.density}, "
            f"hue={self.hue}, saturation={self.saturation}, "
            f"brightness={self.brightness}, "
            f"background_hue={self.background_hue}, "
            f"background_saturation={self.background_saturation}, "
            f"background_brightness={self.background_brightness}, "
            f"kelvin={self.kelvin}, power_on={self.power_on})"
        )
