"""Spectrum Sweep -- three-phase sine waves drive color across zones.

Three sine waves, 120 degrees out of phase, sweep through the zones
at a configurable rate.  Each wave controls one of the three primary
hue regions (red, green, blue), producing a continuously shifting
color pattern that travels along the strip.

Designed to look like a frequency sweep across a spectrum analyzer.
No audio input needed -- the waves are synthetic.  Uses Oklab
interpolation for perceptually smooth color blending.
"""

# Originally derived from https://github.com/pkivolowitz/lifx
#
# MIT License
#
# Copyright (c) 2026 Perry Kivolowitz
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import MAX_KELVIN, MIN_KELVIN
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect

if TYPE_CHECKING:
    from lifx.devices.light import Light

# Full circle in radians.
_TWO_PI: float = 2.0 * math.pi

# Phase offset between waves (120 degrees = 2pi/3).
_PHASE_OFFSET: float = _TWO_PI / 3.0

# Number of sine-wave phases.
_NUM_PHASES: int = 3

# Hue anchors for the three phases in degrees: red, green, blue.
_PHASE_HUES: list[int] = [0, 120, 240]


class EffectSpectrumSweep(FrameEffect):
    """Three-phase sine sweep across zones -- synthetic spectrum analyzer.

    Three sine waves at 120-degree phase separation travel along the strip.
    Each wave's amplitude controls brightness at its hue anchor.
    Where waves overlap, colors blend through Oklab for perceptually smooth
    transitions.  The result is a smooth, continuously shifting rainbow that
    wraps and travels.

    Attributes:
        speed: Seconds per full sweep cycle
        waves: Number of wave periods across the strip
        brightness: Peak brightness (0.0-1.0)
        kelvin: Color temperature (1500-9000)
        zones_per_bulb: Number of physical zones per logical bulb

    Example:
        ```python
        effect = EffectSpectrumSweep(speed=6.0, waves=1.0)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 6.0,
        waves: float = 1.0,
        brightness: float = 0.8,
        kelvin: int = 3500,
        zones_per_bulb: int = 1,
    ) -> None:
        """Initialize Spectrum Sweep effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Seconds per full sweep cycle, must be > 0 (default 6.0)
            waves: Number of wave periods across the strip, must be > 0 (default 1.0)
            brightness: Peak brightness 0.0-1.0 (default 0.8)
            kelvin: Color temperature 1500-9000 (default 3500)
            zones_per_bulb: Physical zones per logical bulb (default 1)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if waves <= 0:
            raise ValueError(f"Waves must be positive, got {waves}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.waves = waves
        self.brightness = brightness
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "spectrum_sweep"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of the spectrum sweep.

        For each zone, compute three sine wave amplitudes (120 degrees apart),
        use them as brightness weights for red, green, blue hue anchors, and
        blend the dominant two through Oklab interpolation.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        # Compute logical bulb count
        bulb_count = max(ctx.pixel_count // self.zones_per_bulb, 1)

        # Temporal phase -- sweeps the pattern along the strip.
        time_phase = _TWO_PI * ctx.elapsed_s / self.speed

        bulb_colors: list[HSBK] = []
        for z in range(bulb_count):
            # Spatial position along the strip (0 to 1).
            pos = z / max(bulb_count - 1, 1)

            # Spatial frequency -- how many wave periods fit on the strip.
            spatial = _TWO_PI * self.waves * pos

            # Three sine waves, 120 degrees apart.
            # Map sine (-1..+1) to amplitude (0..1).
            amps: list[float] = []
            for i in range(_NUM_PHASES):
                phase = i * _PHASE_OFFSET
                s = math.sin(spatial - time_phase + phase)
                amp = (s + 1.0) / 2.0
                amps.append(amp)

            # Build HSBK colors at the phase hues, weighted by amplitude.
            phase_colors: list[HSBK] = []
            for i in range(_NUM_PHASES):
                phase_colors.append(
                    HSBK(
                        hue=_PHASE_HUES[i],
                        saturation=1.0,
                        brightness=amps[i] * self.brightness,
                        kelvin=self.kelvin,
                    )
                )

            # Blend: find the dominant wave and blend toward second via Oklab.
            # Sort by amplitude -- strongest first.
            ranked = sorted(
                zip(amps, phase_colors),
                key=lambda x: -x[0],
            )

            a1 = ranked[0][0]
            a2 = ranked[1][0]
            total = a1 + a2
            blend = a2 / total if total > 0.0 else 0.0

            color = ranked[0][1].lerp_oklab(ranked[1][1], blend)

            # Override brightness with the max amplitude.
            max_amp = max(amps)
            final_bri = max_amp * self.brightness

            color = HSBK(
                hue=color.hue,
                saturation=color.saturation,
                brightness=final_bri,
                kelvin=color.kelvin,
            )

            bulb_colors.append(color)

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
            Red at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=0,
            saturation=1.0,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with Spectrum Sweep effect.

        Spectrum Sweep requires color capability to manipulate hue/saturation.

        Args:
            light: The light device to check

        Returns:
            True if light has color support, False otherwise
        """
        if light.capabilities is None:
            await light.ensure_capabilities()
        return light.capabilities.has_color if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Spectrum Sweep can inherit prestate from another Spectrum Sweep.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectSpectrumSweep, False otherwise
        """
        return isinstance(other, EffectSpectrumSweep)

    def __repr__(self) -> str:
        """String representation of Spectrum Sweep effect."""
        return (
            f"EffectSpectrumSweep(speed={self.speed}, waves={self.waves}, "
            f"brightness={self.brightness}, kelvin={self.kelvin}, "
            f"zones_per_bulb={self.zones_per_bulb}, power_on={self.power_on})"
        )
