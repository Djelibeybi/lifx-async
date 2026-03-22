"""Double slit interference effect -- two coherent wave sources.

Two point sources emit sinusoidal waves that propagate along the strip.
Where the waves meet, constructive interference produces bright zones and
destructive interference produces dark zones -- the classic Young's double
slit fringe pattern rendered on a 1D LED strip.

    wave_1(x, t) = sin(k * |x - s1| - omega * t)
    wave_2(x, t) = sin(k * |x - s2| - omega * t)
    amplitude(x, t) = (wave_1 + wave_2) / 2

Slowly varying the wavelength makes the fringe pattern breathe and shift.
Color encodes the sign of the combined displacement: positive maps toward
hue1, negative maps toward hue2, with brightness proportional to
|amplitude|.
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

# Full cycle constant.
_TWO_PI: float = 2.0 * math.pi

# Floor brightness fraction -- avoids LIFX hardware flicker at true black.
_FLOOR_FRAC: float = 0.02

# Modulation depth for wavelength breathing.  The wavelength oscillates
# between wavelength * (1 - DEPTH) and wavelength * (1 + DEPTH).
_BREATH_DEPTH: float = 0.3


class EffectDoubleSlit(FrameEffect):
    """Double slit interference -- two coherent wave sources.

    Two point sources at configurable positions emit sinusoidal waves.
    The combined amplitude at each zone determines brightness and color:
    constructive interference is bright, destructive is dark.  An optional
    breathe parameter modulates wavelength over time, making the fringe
    pattern shift and evolve.

    Attributes:
        speed: Wave propagation period in seconds
        wavelength: Base wavelength as fraction of strip length (0.0-1.0)
        separation: Source separation as fraction of strip length (0.0-1.0)
        breathe: Wavelength modulation period in seconds (0 = off)
        hue1: Color for positive displacement (0-360 degrees)
        hue2: Color for negative displacement (0-360 degrees)
        saturation: Wave color saturation (0.0-1.0)
        brightness: Peak brightness (0.0-1.0)
        kelvin: Color temperature (1500-9000)
        zones_per_bulb: Number of physical zones per logical bulb

    Example:
        ```python
        effect = EffectDoubleSlit(speed=4.0, wavelength=0.3, separation=0.2)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 4.0,
        wavelength: float = 0.3,
        separation: float = 0.2,
        breathe: float = 0.0,
        hue1: int = 0,
        hue2: int = 240,
        saturation: float = 1.0,
        brightness: float = 0.8,
        kelvin: int = 3500,
        zones_per_bulb: int = 1,
    ) -> None:
        """Initialize double slit interference effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Wave propagation period in seconds, must be > 0 (default 4.0)
            wavelength: Base wavelength as fraction of strip length, 0.05-2.0
                (default 0.3)
            separation: Source separation as fraction of strip length, 0.05-0.9
                (default 0.2)
            breathe: Wavelength modulation period in seconds, 0 = off (default 0.0)
            hue1: Color 1 hue 0-360 degrees (default 0, red)
            hue2: Color 2 hue 0-360 degrees (default 240, blue)
            saturation: Wave color saturation 0.0-1.0 (default 1.0)
            brightness: Peak brightness 0.0-1.0 (default 0.8)
            kelvin: Color temperature 1500-9000 (default 3500)
            zones_per_bulb: Physical zones per logical bulb (default 1)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if not (0.05 <= wavelength <= 2.0):
            raise ValueError(f"Wavelength must be 0.05-2.0, got {wavelength}")
        if not (0.05 <= separation <= 0.9):
            raise ValueError(f"Separation must be 0.05-0.9, got {separation}")
        if breathe < 0:
            raise ValueError(f"Breathe must be >= 0, got {breathe}")
        if not (0 <= hue1 <= 360):
            raise ValueError(f"hue1 must be 0-360, got {hue1}")
        if not (0 <= hue2 <= 360):
            raise ValueError(f"hue2 must be 0-360, got {hue2}")
        if not (0.0 <= saturation <= 1.0):
            raise ValueError(f"Saturation must be 0.0-1.0, got {saturation}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.wavelength = wavelength
        self.separation = separation
        self.breathe = breathe
        self.hue1 = hue1
        self.hue2 = hue2
        self.saturation = saturation
        self.brightness = brightness
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "double_slit"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of double slit interference.

        Two sinusoidal waves propagate from point sources.  Their sum
        creates an interference pattern that shifts as the wavelength
        breathes.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        zpb = self.zones_per_bulb
        bulb_count = max(ctx.pixel_count // zpb, 1)

        # Source positions (symmetric about center).
        center: float = 0.5
        half_sep: float = self.separation / 2.0
        s1: float = center - half_sep  # normalized [0, 1]
        s2: float = center + half_sep

        # Wavelength with optional breathing modulation.
        wl: float = self.wavelength
        if self.breathe > 0.0:
            breath_phase: float = math.sin(_TWO_PI * ctx.elapsed_s / self.breathe)
            wl *= 1.0 + _BREATH_DEPTH * breath_phase

        # Wave number: k = 2pi / (wavelength_in_zones).
        wl_zones: float = wl * bulb_count if bulb_count > 0 else 1.0
        k: float = _TWO_PI / wl_zones if wl_zones > 0 else _TWO_PI

        # Angular frequency: omega = 2pi / speed.
        omega: float = _TWO_PI / self.speed if self.speed > 0 else _TWO_PI

        # Brightness floor and range.
        max_bri: float = self.brightness
        min_bri: float = max_bri * _FLOOR_FRAC
        bri_range: float = max_bri - min_bri

        # Build endpoint colors for blending.
        color_pos = HSBK(
            hue=self.hue1,
            saturation=self.saturation,
            brightness=max_bri,
            kelvin=self.kelvin,
        )
        color_neg = HSBK(
            hue=self.hue2,
            saturation=self.saturation,
            brightness=max_bri,
            kelvin=self.kelvin,
        )

        # Render to logical bulbs.
        bulb_colors: list[HSBK] = []
        for i in range(bulb_count):
            # Normalized position along the strip.
            x: float = i / bulb_count if bulb_count > 0 else 0.5

            # Distance from each source (in zone units for wave number).
            d1: float = abs(x - s1) * bulb_count
            d2: float = abs(x - s2) * bulb_count

            # Superposition of two coherent waves.
            wave1: float = math.sin(k * d1 - omega * ctx.elapsed_s)
            wave2: float = math.sin(k * d2 - omega * ctx.elapsed_s)
            amplitude: float = (wave1 + wave2) / 2.0  # normalize to [-1, 1]

            # Brightness from |amplitude|.
            bri: float = min_bri + bri_range * abs(amplitude)

            # Color from sign of amplitude via Oklab interpolation.
            # Map amplitude [-1, 1] to blend factor [0, 1].
            blend: float = (amplitude + 1.0) / 2.0
            blended = color_neg.lerp_oklab(color_pos, blend)

            bulb_colors.append(
                HSBK(
                    hue=blended.hue,
                    saturation=blended.saturation,
                    brightness=bri,
                    kelvin=self.kelvin,
                )
            )

        # Expand logical bulbs to physical zones.
        if zpb == 1:
            return bulb_colors

        colors: list[HSBK] = []
        for color in bulb_colors:
            colors.extend([color] * zpb)

        # Trim or pad to exact pixel_count.
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
            saturation=self.saturation,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )
        color2 = HSBK(
            hue=self.hue2,
            saturation=self.saturation,
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
        """Check if light is compatible with double slit effect.

        Double slit requires color capability to manipulate hue/saturation.

        Args:
            light: The light device to check

        Returns:
            True if light has color support, False otherwise
        """
        if light.capabilities is None:
            await light.ensure_capabilities()
        return light.capabilities.has_color if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Double slit can inherit prestate from another DoubleSlit effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectDoubleSlit, False otherwise
        """
        return isinstance(other, EffectDoubleSlit)

    def __repr__(self) -> str:
        """String representation of DoubleSlit effect."""
        return (
            f"EffectDoubleSlit(speed={self.speed}, wavelength={self.wavelength}, "
            f"separation={self.separation}, breathe={self.breathe}, "
            f"hue1={self.hue1}, hue2={self.hue2}, "
            f"saturation={self.saturation}, brightness={self.brightness}, "
            f"kelvin={self.kelvin}, zones_per_bulb={self.zones_per_bulb}, "
            f"power_on={self.power_on})"
        )
