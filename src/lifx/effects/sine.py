"""Traveling ease wave effect -- bright humps roll along the strip.

A wave travels smoothly from one end to the other using cubic
ease-in-ease-out interpolation. Each zone's normalized phase
(0 to 1) is mapped through the smoothstep function

    f(x) = 3x^2 - 2x^3

which has zero derivative at both endpoints -- brightness ramps
up gently from the floor, peaks, and ramps back down without any
perceptible flicker or quiver at the transitions.
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

# Full sine cycle constant.
_TWO_PI: float = 2.0 * math.pi


def _smoothstep(x: float) -> float:
    """Cubic ease-in-ease-out: 3x^2 - 2x^3.

    Input and output are both in [0, 1]. First and second
    derivatives are zero at x=0 and x=1, producing silky-smooth
    brightness transitions with no perceptible flicker.

    Args:
        x: Normalized input, clamped to [0, 1].

    Returns:
        Eased output in [0, 1].
    """
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


class EffectSine(FrameEffect):
    """Traveling ease wave -- bright humps roll along the strip.

    Each zone computes a traveling wave phase, then the positive
    half-cycle is remapped through cubic ease-in-ease-out (smoothstep).
    The negative half-cycle shows floor brightness, creating distinct
    bright humps separated by dim gaps that scroll continuously.

    Attributes:
        speed: Seconds per full wave cycle (travel speed)
        wavelength: Wavelength as fraction of strip length
        hue: Wave color hue in degrees (0-360)
        saturation: Wave color saturation (0.0-1.0)
        brightness: Peak brightness (0.0-1.0)
        floor: Minimum brightness (0.0-1.0, must be < brightness)
        hue2: Optional second hue for gradient along the wave (None = disabled)
        kelvin: Color temperature (1500-9000)
        zones_per_bulb: Number of physical zones per logical bulb
        reverse: Reverse wave travel direction

    Example:
        ```python
        effect = EffectSine(speed=4.0, hue=200, wavelength=0.5)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 4.0,
        wavelength: float = 0.5,
        hue: int = 200,
        saturation: float = 1.0,
        brightness: float = 0.8,
        floor: float = 0.02,
        hue2: int | None = None,
        kelvin: int = 3500,
        zones_per_bulb: int = 1,
        reverse: bool = False,
    ) -> None:
        """Initialize traveling ease wave effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Seconds per full wave cycle, must be > 0 (default 4.0)
            wavelength: Wavelength as fraction of strip length,
                must be > 0 (default 0.5)
            hue: Wave color hue 0-360 degrees (default 200)
            saturation: Wave color saturation 0.0-1.0 (default 1.0)
            brightness: Peak brightness 0.0-1.0 (default 0.8)
            floor: Minimum brightness 0.0-1.0, must be < brightness (default 0.02)
            hue2: Optional second hue 0-360 for gradient (default None, disabled)
            kelvin: Color temperature 1500-9000 (default 3500)
            zones_per_bulb: Physical zones per logical bulb (default 1)
            reverse: Reverse wave direction (default False)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if wavelength <= 0:
            raise ValueError(f"Wavelength must be positive, got {wavelength}")
        if not (0 <= hue <= 360):
            raise ValueError(f"Hue must be 0-360, got {hue}")
        if not (0.0 <= saturation <= 1.0):
            raise ValueError(f"Saturation must be 0.0-1.0, got {saturation}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (0.0 <= floor <= 1.0):
            raise ValueError(f"Floor must be 0.0-1.0, got {floor}")
        if floor >= brightness:
            raise ValueError(
                f"Floor must be less than brightness, "
                f"got floor={floor} >= brightness={brightness}"
            )
        if hue2 is not None and not (0 <= hue2 <= 360):
            raise ValueError(f"hue2 must be 0-360, got {hue2}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.wavelength = wavelength
        self.hue = hue
        self.saturation = saturation
        self.brightness = brightness
        self.floor = floor
        self.hue2 = hue2
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb
        self.reverse = reverse

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "sine"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of the traveling ease wave.

        Each zone computes a traveling-wave phase. The positive
        half-cycle is remapped through smoothstep for flicker-free
        brightness; the negative half-cycle holds at floor brightness.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        bri_range = self.brightness - self.floor

        # Build base color for the wave crest.
        base_color = HSBK(
            hue=self.hue,
            saturation=self.saturation,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )

        # Optional second color for gradient along the wave crest.
        use_gradient = self.hue2 is not None
        end_color = base_color
        if use_gradient:
            end_color = HSBK(
                hue=self.hue2,  # type: ignore[arg-type]
                saturation=self.saturation,
                brightness=self.brightness,
                kelvin=self.kelvin,
            )

        # Direction multiplier.
        direction: float = -1.0 if self.reverse else 1.0

        zpb = self.zones_per_bulb
        bulb_count = max(ctx.pixel_count // zpb, 1)

        bulb_colors: list[HSBK] = []
        for i in range(bulb_count):
            # Polychrome-aware: all zones within one bulb share position.
            bulb_index = i

            # Normalized position along the strip (0.0 to 1.0).
            x: float = bulb_index / bulb_count if bulb_count > 0 else 0.0

            # Traveling wave: sin(2pi * (x/wavelength - t/speed))
            phase = _TWO_PI * (
                x / self.wavelength - direction * ctx.elapsed_s / self.speed
            )
            displacement = math.sin(phase)

            if displacement <= 0.0:
                # Negative half-cycle: hold at floor brightness.
                bulb_colors.append(
                    HSBK(
                        hue=self.hue,
                        saturation=self.saturation,
                        brightness=self.floor,
                        kelvin=self.kelvin,
                    )
                )
            else:
                # Positive half-cycle: remap through cubic ease-in-ease-out.
                eased = _smoothstep(displacement)
                bri = self.floor + bri_range * eased

                if use_gradient:
                    blended = base_color.lerp_oklab(end_color, x)
                    bulb_colors.append(
                        HSBK(
                            hue=blended.hue,
                            saturation=blended.saturation,
                            brightness=bri,
                            kelvin=self.kelvin,
                        )
                    )
                else:
                    bulb_colors.append(
                        HSBK(
                            hue=self.hue,
                            saturation=self.saturation,
                            brightness=bri,
                            kelvin=self.kelvin,
                        )
                    )

        # Expand logical bulbs to physical zones
        if zpb == 1:
            return bulb_colors

        colors: list[HSBK] = []
        for color in bulb_colors:
            colors.extend([color] * zpb)

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
            Wave color at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=self.hue,
            saturation=self.saturation,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with sine effect.

        Sine requires color capability to manipulate hue/saturation.

        Args:
            light: The light device to check

        Returns:
            True if light has color support, False otherwise
        """
        if light.capabilities is None:
            await light.ensure_capabilities()
        return light.capabilities.has_color if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Sine can inherit prestate from another Sine effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectSine, False otherwise
        """
        return isinstance(other, EffectSine)

    def __repr__(self) -> str:
        """String representation of Sine effect."""
        return (
            f"EffectSine(speed={self.speed}, wavelength={self.wavelength}, "
            f"hue={self.hue}, saturation={self.saturation}, "
            f"brightness={self.brightness}, floor={self.floor}, "
            f"hue2={self.hue2}, kelvin={self.kelvin}, "
            f"zones_per_bulb={self.zones_per_bulb}, reverse={self.reverse}, "
            f"power_on={self.power_on})"
        )
