"""Cylon / Larson scanner effect.

A bright "eye" sweeps back and forth across the strip with a smooth
cosine-shaped brightness falloff. Classic Battlestar Galactica / Knight
Rider look. The eye position follows a sinusoidal easing curve so
direction reversals at the edges look natural rather than abrupt.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import MAX_KELVIN, MIN_KELVIN
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect

if TYPE_CHECKING:
    from lifx.devices.light import Light

# Minimum travel distance to prevent division by zero on single-zone devices.
_MIN_TRAVEL: int = 1

# Divisor for the cosine eye shape -- splits the eye width in half.
_COSINE_DIVISOR: float = 2.0

# Sinusoidal easing uses a full cycle (2pi) mapped across one sweep period.
_FULL_CYCLE: float = 2.0 * math.pi


class EffectCylon(FrameEffect):
    """Larson scanner -- a bright eye sweeps back and forth.

    The eye has a cosine-shaped brightness profile so it tapers smoothly
    on both sides. Eye width, color, speed, and trail are all tunable.

    Attributes:
        speed: Seconds per full sweep (there and back)
        width: Width of the eye in logical bulbs
        hue: Eye color hue in degrees (0-360)
        brightness: Peak eye brightness (0.0-1.0)
        background_brightness: Background brightness (0.0-1.0)
        trail: Trail decay factor (0.0=no trail, 1.0=max trail)
        kelvin: Color temperature (1500-9000)
        zones_per_bulb: Number of physical zones per logical bulb

    Example:
        ```python
        effect = EffectCylon(speed=2.0, hue=0, width=3)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 2.0,
        width: int = 3,
        hue: int = 0,
        brightness: float = 0.8,
        background_brightness: float = 0.0,
        trail: float = 0.5,
        kelvin: int = 3500,
        zones_per_bulb: int = 1,
    ) -> None:
        """Initialize Cylon scanner effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Seconds per full sweep, must be > 0 (default 2.0)
            width: Width of the eye in logical bulbs, must be >= 1 (default 3)
            hue: Eye color hue 0-360 degrees (default 0, red)
            brightness: Peak eye brightness 0.0-1.0 (default 0.8)
            background_brightness: Background brightness 0.0-1.0 (default 0.0)
            trail: Trail decay factor 0.0-1.0 (default 0.5)
            kelvin: Color temperature 1500-9000 (default 3500)
            zones_per_bulb: Physical zones per logical bulb (default 1)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if width < 1:
            raise ValueError(f"Width must be >= 1, got {width}")
        if not (0 <= hue <= 360):
            raise ValueError(f"Hue must be 0-360, got {hue}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (0.0 <= background_brightness <= 1.0):
            raise ValueError(
                f"Background brightness must be 0.0-1.0, got {background_brightness}"
            )
        if not (0.0 <= trail <= 1.0):
            raise ValueError(f"Trail must be 0.0-1.0, got {trail}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.width = width
        self.hue = hue
        self.brightness = brightness
        self.background_brightness = background_brightness
        self.trail = trail
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "cylon"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of the Cylon scanner.

        The eye position is computed via sinusoidal easing across the
        zone range. Each zone's brightness is the cosine falloff from
        the eye center, floored at the background brightness.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        # Compute logical bulb count
        bulb_count = max(ctx.pixel_count // self.zones_per_bulb, 1)

        half = self.width / _COSINE_DIVISOR

        # Travel distance is the number of inter-bulb gaps the eye crosses.
        travel = max(bulb_count - 1, _MIN_TRAVEL)

        # Phase within the current sweep cycle (0.0 to 1.0).
        phase = (ctx.elapsed_s % self.speed) / self.speed

        # Sinusoidal easing: cos maps [0..2pi] to [1..-1..1], scaled to
        # [0..travel..0] for a smooth bounce at both ends.
        position = travel * (1 - math.cos(phase * _FULL_CYCLE)) / _COSINE_DIVISOR

        # Render to logical bulbs
        bulb_colors: list[HSBK] = []
        for i in range(bulb_count):
            dist = abs(i - position)

            if dist < half:
                # Cosine falloff: full brightness at center, tapering to zero
                # at the eye edges for a smooth, rounded profile.
                t_norm = dist / half
                eye_bri = (
                    self.brightness * (math.cos(t_norm * math.pi) + 1) / _COSINE_DIVISOR
                )
                zone_bri = max(eye_bri, self.background_brightness)
            else:
                zone_bri = self.background_brightness

            zone_bri = max(0.0, min(1.0, zone_bri))

            bulb_colors.append(
                HSBK(
                    hue=self.hue,
                    saturation=1.0,
                    brightness=zone_bri,
                    kelvin=self.kelvin,
                )
            )

        # Expand logical bulbs to physical zones
        if self.zones_per_bulb == 1:
            return bulb_colors

        colors: list[HSBK] = []
        for color in bulb_colors:
            colors.extend([color] * self.zones_per_bulb)

        # Trim or pad to exact pixel_count
        if len(colors) < ctx.pixel_count:
            colors.extend([colors[-1]] * (ctx.pixel_count - len(colors)))
        elif len(colors) > ctx.pixel_count:
            colors = colors[: ctx.pixel_count]

        return colors

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        Args:
            _light: The device being powered on (unused)

        Returns:
            Eye color at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=self.hue,
            saturation=1.0,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with Cylon effect.

        Cylon requires color capability to manipulate hue/saturation.

        Args:
            light: The light device to check

        Returns:
            True if light has color support, False otherwise
        """
        if light.capabilities is None:
            await light._ensure_capabilities()
        return light.capabilities.has_color if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Cylon can inherit prestate from another Cylon effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectCylon, False otherwise
        """
        return isinstance(other, EffectCylon)

    def __repr__(self) -> str:
        """String representation of Cylon effect."""
        return (
            f"EffectCylon(speed={self.speed}, width={self.width}, "
            f"hue={self.hue}, brightness={self.brightness}, "
            f"background_brightness={self.background_brightness}, "
            f"trail={self.trail}, kelvin={self.kelvin}, "
            f"zones_per_bulb={self.zones_per_bulb}, power_on={self.power_on})"
        )
