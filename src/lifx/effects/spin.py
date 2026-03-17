"""Spin (color migration) effect.

Theme colors cycle through zones so hues appear to migrate along the
strip. Each zone is assigned a color from the theme based on its
position plus a time-varying offset. A small per-zone hue shift
(``bulb_offset``) adds shimmer. Interpolation between adjacent theme
colors uses ``HSBK.lerp_oklab()`` for perceptually smooth transitions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import MAX_KELVIN, MIN_KELVIN
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.theme.library import ThemeLibrary
from lifx.theme.theme import Theme

if TYPE_CHECKING:
    from lifx.devices.light import Light


class EffectSpin(FrameEffect):
    """Cycle theme colors through device zones.

    Colors from the theme are spread across the strip and scroll over
    time. Adjacent zones interpolate smoothly via Oklab, and each zone
    receives a tiny hue offset (``bulb_offset``) to add visual shimmer.

    Attributes:
        speed: Seconds per full color rotation
        theme: Theme providing the palette colors
        bulb_offset: Per-zone hue shift in degrees for shimmer
        brightness: Zone brightness 0.0-1.0
        kelvin: Color temperature 1500-9000
        zones_per_bulb: Physical zones per logical bulb

    Example:
        ```python
        effect = EffectSpin(speed=10.0)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 10.0,
        theme: Theme | None = None,
        bulb_offset: float = 5.0,
        brightness: float = 0.8,
        kelvin: int = 3500,
        zones_per_bulb: int = 1,
    ) -> None:
        """Initialize Spin effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Seconds per full color rotation, must be > 0 (default 10.0)
            theme: Theme providing palette colors (defaults to "exciting")
            bulb_offset: Per-zone hue shift in degrees 0-360 (default 5.0)
            brightness: Zone brightness 0.0-1.0 (default 0.8)
            kelvin: Color temperature 1500-9000 (default 3500)
            zones_per_bulb: Physical zones per logical bulb (default 1)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if not (0.0 <= bulb_offset <= 360.0):
            raise ValueError(f"bulb_offset must be 0-360, got {bulb_offset}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.theme = theme if theme is not None else ThemeLibrary.get("exciting")
        self.bulb_offset = bulb_offset
        self.brightness = brightness
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "spin"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of cycling theme colors.

        Each zone's position (0.0-1.0) plus a time offset determines
        which pair of theme colors it falls between. ``HSBK.lerp_oklab``
        interpolates smoothly between those neighbors. A small hue
        shift per zone (``bulb_offset``) adds visual shimmer.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        theme_colors = self.theme.colors
        n_colors = len(theme_colors)

        # Rotation phase: 0.0 to 1.0 over the speed period.
        phase = (ctx.elapsed_s / self.speed) % 1.0

        # Compute logical bulb count
        bulb_count = max(ctx.pixel_count // self.zones_per_bulb, 1)

        bulb_colors: list[HSBK] = []
        for i in range(bulb_count):
            # Normalised position along the strip (0.0 - 1.0)
            position = i / max(bulb_count - 1, 1)

            # Continuous index into the theme palette, scrolling with time
            slot = (position + phase) * n_colors
            slot_mod = slot % n_colors

            idx_a = int(slot_mod)
            idx_b = (idx_a + 1) % n_colors
            frac = slot_mod - idx_a

            # Perceptually smooth interpolation via Oklab
            base_color = theme_colors[idx_a].lerp_oklab(theme_colors[idx_b], frac)

            # Apply per-zone hue shimmer
            shimmer_hue = (base_color.hue + i * self.bulb_offset) % 360

            bulb_colors.append(
                HSBK(
                    hue=round(shimmer_hue),
                    saturation=base_color.saturation,
                    brightness=self.brightness,
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

        Uses the first theme color at zero brightness for a smooth
        fade-in.

        Args:
            _light: The device being powered on (unused)

        Returns:
            First theme color at zero brightness
        """
        first = self.theme.colors[0]
        return HSBK(
            hue=first.hue,
            saturation=first.saturation,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with Spin effect.

        Spin requires color capability to manipulate hue/saturation.

        Args:
            light: The light device to check

        Returns:
            True if light has color support, False otherwise
        """
        if light.capabilities is None:
            await light._ensure_capabilities()
        return light.capabilities.has_color if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Spin can inherit prestate from another Spin effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectSpin, False otherwise
        """
        return isinstance(other, EffectSpin)

    def __repr__(self) -> str:
        """String representation of Spin effect."""
        return (
            f"EffectSpin(speed={self.speed}, theme={self.theme!r}, "
            f"bulb_offset={self.bulb_offset}, brightness={self.brightness}, "
            f"kelvin={self.kelvin}, zones_per_bulb={self.zones_per_bulb}, "
            f"power_on={self.power_on})"
        )
