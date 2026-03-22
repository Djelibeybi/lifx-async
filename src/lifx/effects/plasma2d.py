"""2D plasma effect -- classic sum-of-sines interference pattern.

Generates a full-color 2D plasma field by summing sine waves at different
frequencies, phases, and orientations. The result is a continuously shifting
interference pattern that fills the entire pixel grid.

The effect produces ``canvas_width * canvas_height`` HSBK values in row-major
order. The combined sine value maps to a blend factor between two colors via
``HSBK.lerp_oklab()`` for perceptually uniform color transitions.

This effect is for MATRIX devices only (e.g., LIFX Tile, Candle, Path).
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Two pi -- full circle in radians.
_TWO_PI: float = 2.0 * math.pi

# Diagonal scale multiplier (larger divisor = smoother diagonal wave).
_DIAGONAL_SCALE: float = 1.5


class EffectPlasma2D(FrameEffect):
    """2D plasma -- sine-wave interference color field for matrix devices.

    Sums four sine waves with different spatial frequencies and directions
    (horizontal, vertical, diagonal, radial) to produce a complex
    interference pattern. The combined value maps to a blend factor between
    two configurable colors using Oklab perceptual interpolation.

    Compatible only with matrix devices (LIFX Tile, Candle, Path).
    Not supported on single lights or multizone strips.

    Attributes:
        speed: Animation speed multiplier
        scale: Spatial scale (larger = coarser pattern)
        hue1: First color hue in degrees (0-360)
        hue2: Second color hue in degrees (0-360)
        brightness: Peak brightness (0.0-1.0)
        kelvin: Color temperature (1500-9000)

    Example:
        ```python
        effect = EffectPlasma2D(speed=1.0, hue1=270, hue2=180)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 1.0,
        scale: float = 1.0,
        hue1: int = 270,
        hue2: int = 180,
        brightness: float = 0.8,
        kelvin: int = 3500,
    ) -> None:
        """Initialize 2D plasma effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Animation speed multiplier, must be > 0 (default 1.0)
            scale: Spatial scale, must be > 0 (default 1.0)
            hue1: First color hue 0-360 degrees (default 270, violet)
            hue2: Second color hue 0-360 degrees (default 180, cyan)
            brightness: Peak brightness 0.0-1.0 (default 0.8)
            kelvin: Color temperature 1500-9000 (default 3500)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if scale <= 0:
            raise ValueError(f"Scale must be positive, got {scale}")
        if not (0 <= hue1 <= 360):
            raise ValueError(f"hue1 must be 0-360, got {hue1}")
        if not (0 <= hue2 <= 360):
            raise ValueError(f"hue2 must be 0-360, got {hue2}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.scale = scale
        self.hue1 = hue1
        self.hue2 = hue2
        self.brightness = brightness
        self.kelvin = kelvin

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "plasma2d"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate one frame of the 2D plasma.

        Evaluates four sine functions per pixel to build a complex
        interference pattern. The combined value maps to a blend factor
        between the two configured colors via Oklab interpolation.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        w: int = ctx.canvas_width
        h: int = ctx.canvas_height
        sc: float = self.scale
        spd: float = self.speed

        # Pre-compute time-varying offsets at different rates.
        t1: float = ctx.elapsed_s * spd
        t2: float = ctx.elapsed_s * spd * 0.7
        t3: float = ctx.elapsed_s * spd * 0.5
        t4: float = ctx.elapsed_s * spd * 0.3

        # Precompute inverse scale to avoid repeated division.
        inv_sc: float = 1.0 / sc
        inv_sc_diag: float = 1.0 / (sc * _DIAGONAL_SCALE)

        # Center point for radial component.
        cx: float = w * 0.5
        cy: float = h * 0.5

        # Precompute the two endpoint colors for lerp.
        color1 = HSBK(
            hue=self.hue1,
            saturation=1.0,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )
        color2 = HSBK(
            hue=self.hue2,
            saturation=1.0,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )

        colors: list[HSBK] = []
        sin = math.sin
        sqrt = math.sqrt

        for y in range(h):
            # Pre-compute y-dependent terms outside inner loop.
            sin_y: float = sin(y * inv_sc + t2)
            dy: float = y - cy
            dy_sq: float = dy * dy

            for x in range(w):
                # Four interference components:
                #   1. Horizontal wave
                #   2. Vertical wave (pre-computed above)
                #   3. Diagonal wave
                #   4. Radial wave (distance from center)
                v: float = sin(x * inv_sc + t1)
                v += sin_y
                v += sin((x + y) * inv_sc_diag + t3)
                dx: float = x - cx
                v += sin(sqrt(dx * dx + dy_sq) * inv_sc + t4)

                # v ranges approximately [-4, +4]. Normalize to [0, 1].
                blend: float = (v + 4.0) * 0.125

                colors.append(color1.lerp_oklab(color2, blend))

        # Pad or trim to exact pixel_count if grid doesn't match.
        if len(colors) < ctx.pixel_count:
            pad_color = colors[-1] if colors else color1
            colors.extend([pad_color] * (ctx.pixel_count - len(colors)))
        elif len(colors) > ctx.pixel_count:
            colors = colors[: ctx.pixel_count]

        return colors

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        Args:
            _light: The device being powered on (unused)

        Returns:
            First plasma color at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=self.hue1,
            saturation=1.0,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with 2D plasma effect.

        Plasma2D requires matrix capability. Not supported on single lights
        or multizone strips.

        Args:
            light: The light device to check

        Returns:
            True if light has matrix support, False otherwise
        """
        if light.capabilities is None:
            await light.ensure_capabilities()
        return light.capabilities.has_matrix if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Plasma2D can inherit prestate from another Plasma2D effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectPlasma2D, False otherwise
        """
        return isinstance(other, EffectPlasma2D)

    def __repr__(self) -> str:
        """String representation of Plasma2D effect."""
        return (
            f"EffectPlasma2D(speed={self.speed}, scale={self.scale}, "
            f"hue1={self.hue1}, hue2={self.hue2}, "
            f"brightness={self.brightness}, kelvin={self.kelvin}, "
            f"power_on={self.power_on})"
        )
