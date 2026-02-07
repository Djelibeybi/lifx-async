"""Rainbow effect implementation.

This module provides the EffectRainbow class for animated rainbow effects
that spread colors across device pixels.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import KELVIN_NEUTRAL
from lifx.effects.frame_effect import FrameContext, FrameEffect

if TYPE_CHECKING:
    from lifx.devices.light import Light


class EffectRainbow(FrameEffect):
    """Animated rainbow effect that spreads colors across device pixels.

    For multizone strips and matrix lights, displays a full 360-degree
    rainbow spread across all pixels that scrolls over time. For single
    lights, cycles through the hue spectrum (similar to colorloop but
    simpler).

    Attributes:
        period: Seconds per full rainbow scroll (default 10)
        brightness: Fixed brightness (default 0.8)
        saturation: Fixed saturation (default 1.0)
        spread: Hue degrees offset between devices (default 0)

    Example:
        ```python
        # Rainbow on a multizone strip — scrolls every 10 seconds
        effect = EffectRainbow(period=10)
        await conductor.start(effect, lights)

        # Fast rainbow with lower brightness
        effect = EffectRainbow(period=3, brightness=0.5)
        await conductor.start(effect, lights)

        # Multiple devices offset by 90 degrees
        effect = EffectRainbow(period=10, spread=90)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        period: float = 10.0,
        brightness: float = 0.8,
        saturation: float = 1.0,
        spread: float = 0.0,
    ) -> None:
        """Initialize rainbow effect.

        Args:
            power_on: Power on devices if off (default True)
            period: Seconds per full rainbow scroll (default 10.0)
            brightness: Fixed brightness 0.0-1.0 (default 0.8)
            saturation: Fixed saturation 0.0-1.0 (default 1.0)
            spread: Hue degrees offset between devices (default 0).
                    When running on multiple devices, each device's rainbow
                    is offset by this many degrees.

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if period <= 0:
            raise ValueError(f"Period must be positive, got {period}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (0.0 <= saturation <= 1.0):
            raise ValueError(f"Saturation must be 0.0-1.0, got {saturation}")
        if not (0.0 <= spread <= 360.0):
            raise ValueError(f"Spread must be 0-360 degrees, got {spread}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.period = period
        self.brightness = brightness
        self.saturation = saturation
        self.spread = spread

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "rainbow"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of rainbow colors for one device.

        For multi-pixel devices, spreads a full 360-degree rainbow across
        all pixels. The entire pattern scrolls as time passes. For single
        lights, cycles through hues over time.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        # How far the rainbow has scrolled (degrees)
        degrees_scrolled = (ctx.elapsed_s / self.period) * 360.0

        # Inter-device offset for multi-device setups
        device_offset = (ctx.device_index * self.spread) % 360

        colors: list[HSBK] = []
        for i in range(ctx.pixel_count):
            # Spread full 360° rainbow across pixels
            pixel_offset = (i / ctx.pixel_count) * 360.0
            hue = round((degrees_scrolled + device_offset + pixel_offset) % 360)
            colors.append(
                HSBK(
                    hue=hue,
                    saturation=self.saturation,
                    brightness=self.brightness,
                    kelvin=KELVIN_NEUTRAL,
                )
            )

        return colors

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        Args:
            _light: The device being powered on (unused)

        Returns:
            HSBK color to use as startup color
        """
        return HSBK(
            hue=0,
            saturation=self.saturation,
            brightness=self.brightness,
            kelvin=KELVIN_NEUTRAL,
        )

    def __repr__(self) -> str:
        """String representation of rainbow effect."""
        return (
            f"EffectRainbow(period={self.period}, "
            f"brightness={self.brightness}, "
            f"saturation={self.saturation}, "
            f"spread={self.spread}, power_on={self.power_on})"
        )
