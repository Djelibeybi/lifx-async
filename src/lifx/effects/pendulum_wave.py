"""Pendulum wave effect -- a row of pendulums with slightly different periods.

All pendulums start in phase, then drift apart as their slightly different
frequencies create traveling waves, standing waves, and apparent chaos --
before magically realigning after one full cycle.

The math is simple harmonic motion with linearly varying periods:

    displacement_n(t) = sin(2pi * t / T_n)

where T_n = speed / (cycles + n / num_pendulums) so that after ``speed``
seconds the fastest pendulum has completed exactly ``cycles + 1`` full
oscillations and the slowest has completed ``cycles`` -- putting them all
back in phase.

Displacement maps to a color blend between two endpoint colors and to
brightness modulation, producing a mesmerizing visual wave machine.
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

# Full cycle constant for temporal oscillation.
_TWO_PI: float = 2.0 * math.pi

# Brightness split: pendulums at rest (displacement ~ 0) dim to this
# fraction of max, full displacement adds the rest.
# 30% base + 70% displacement-scaled = 100% at full displacement.
_BRI_BASE_FRAC: float = 0.3
_BRI_DISP_FRAC: float = 0.7


class EffectPendulumWave(FrameEffect):
    """Pendulum wave -- a row of pendulums drifting in and out of phase.

    Each zone is a pendulum with a slightly different frequency. Over one
    full cycle (``speed`` seconds) the ensemble passes through traveling
    waves, standing waves, and chaos before all pendulums realign perfectly.

    Displacement maps to a color blend between two hues and to brightness
    modulation -- pendulums at the extremes of their swing are brightest,
    pendulums passing through center are dimmest.

    Attributes:
        speed: Seconds for one full realignment cycle
        cycles: Number of oscillations of the slowest pendulum per cycle
        hue1: Color 1 hue in degrees (0-360, negative displacement)
        hue2: Color 2 hue in degrees (0-360, positive displacement)
        saturation1: Color 1 saturation (0.0-1.0)
        saturation2: Color 2 saturation (0.0-1.0)
        brightness: Overall brightness (0.0-1.0)
        kelvin: Color temperature (1500-9000)
        zones_per_bulb: Number of physical zones per logical bulb

    Example:
        ```python
        effect = EffectPendulumWave(speed=30.0, cycles=8, hue1=0, hue2=240)
        await conductor.start(effect, lights)

        await asyncio.sleep(60)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 30.0,
        cycles: int = 8,
        hue1: int = 0,
        hue2: int = 240,
        saturation1: float = 1.0,
        saturation2: float = 1.0,
        brightness: float = 0.8,
        kelvin: int = 3500,
        zones_per_bulb: int = 1,
    ) -> None:
        """Initialize pendulum wave effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Seconds for full realignment cycle, must be > 0 (default 30.0)
            cycles: Oscillations of slowest pendulum per cycle, must be >= 1 (default 8)
            hue1: Color 1 hue 0-360 degrees (default 0, red)
            hue2: Color 2 hue 0-360 degrees (default 240, blue)
            saturation1: Color 1 saturation 0.0-1.0 (default 1.0)
            saturation2: Color 2 saturation 0.0-1.0 (default 1.0)
            brightness: Overall brightness 0.0-1.0 (default 0.8)
            kelvin: Color temperature 1500-9000 (default 3500)
            zones_per_bulb: Physical zones per logical bulb (default 1)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if cycles < 1:
            raise ValueError(f"Cycles must be >= 1, got {cycles}")
        if not (0 <= hue1 <= 360):
            raise ValueError(f"hue1 must be 0-360, got {hue1}")
        if not (0 <= hue2 <= 360):
            raise ValueError(f"hue2 must be 0-360, got {hue2}")
        if not (0.0 <= saturation1 <= 1.0):
            raise ValueError(f"saturation1 must be 0.0-1.0, got {saturation1}")
        if not (0.0 <= saturation2 <= 1.0):
            raise ValueError(f"saturation2 must be 0.0-1.0, got {saturation2}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.cycles = cycles
        self.hue1 = hue1
        self.hue2 = hue2
        self.saturation1 = saturation1
        self.saturation2 = saturation2
        self.brightness = brightness
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "pendulum_wave"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of the pendulum wave.

        Each zone computes a displacement from its individual pendulum
        frequency, then maps that to a color blend and brightness level.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        # Build endpoint HSBK colors for the two swing extremes.
        color1 = HSBK(
            hue=self.hue1,
            saturation=self.saturation1,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )
        color2 = HSBK(
            hue=self.hue2,
            saturation=self.saturation2,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )

        # Compute logical bulb count
        bulb_count = max(ctx.pixel_count // self.zones_per_bulb, 1)

        # Render to logical bulbs
        bulb_colors: list[HSBK] = []
        for i in range(bulb_count):
            # Each pendulum has a slightly different period.
            # T_n = speed / (cycles + i / bulb_count)
            # At t=speed: pendulum 0 has done exactly `cycles` oscillations,
            # pendulum (bulb_count-1) has done `cycles + (bulb_count-1)/bulb_count`
            # -- nearly one extra. They realign at t = speed.
            freq: float = (
                self.cycles + i / bulb_count if bulb_count > 1 else self.cycles
            )
            period: float = self.speed / freq if freq > 0 else self.speed

            # Simple harmonic motion: displacement in [-1, 1].
            displacement: float = math.sin(_TWO_PI * ctx.elapsed_s / period)

            # Map displacement to color blend factor.
            # -1 = pure color1, 0 = midpoint, +1 = pure color2.
            blend: float = (displacement + 1.0) / 2.0

            # Interpolate through Oklab perceptual color space.
            blended = color1.lerp_oklab(color2, blend)

            # Brightness peaks at extremes (large displacement), dims at
            # center where displacement is near zero. Override the blended
            # brightness with displacement-based modulation.
            disp_abs = abs(displacement)
            bri = self.brightness * (_BRI_BASE_FRAC + _BRI_DISP_FRAC * disp_abs)

            bulb_colors.append(
                HSBK(
                    hue=blended.hue,
                    saturation=blended.saturation,
                    brightness=bri,
                    kelvin=self.kelvin,
                )
            )

        # Expand logical bulbs to physical zones
        if self.zones_per_bulb == 1:
            colors = bulb_colors
        else:
            colors = []
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
            Midpoint color at zero brightness for smooth fade-in
        """
        color1 = HSBK(
            hue=self.hue1,
            saturation=self.saturation1,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )
        color2 = HSBK(
            hue=self.hue2,
            saturation=self.saturation2,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )
        midpoint = color1.lerp_oklab(color2, 0.5)
        return HSBK(
            hue=midpoint.hue,
            saturation=midpoint.saturation,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with pendulum wave effect.

        Pendulum wave requires color capability to manipulate hue/saturation.

        Args:
            light: The light device to check

        Returns:
            True if light has color support, False otherwise
        """
        if light.capabilities is None:
            await light.ensure_capabilities()
        return light.capabilities.has_color if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Pendulum wave can inherit prestate from another PendulumWave effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectPendulumWave, False otherwise
        """
        return isinstance(other, EffectPendulumWave)

    def __repr__(self) -> str:
        """String representation of PendulumWave effect."""
        return (
            f"EffectPendulumWave(speed={self.speed}, cycles={self.cycles}, "
            f"hue1={self.hue1}, hue2={self.hue2}, "
            f"saturation1={self.saturation1}, saturation2={self.saturation2}, "
            f"brightness={self.brightness}, "
            f"kelvin={self.kelvin}, zones_per_bulb={self.zones_per_bulb}, "
            f"power_on={self.power_on})"
        )
