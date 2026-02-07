"""ColorLoop effect implementation.

This module provides the EffectColorloop class for continuous hue rotation.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import KELVIN_NEUTRAL
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect

if TYPE_CHECKING:
    from lifx.devices.light import Light

_LOGGER = logging.getLogger(__name__)


class EffectColorloop(FrameEffect):
    """Continuous color rotation effect cycling through hue spectrum.

    Perpetually cycles through hues with configurable speed, spread,
    and color constraints. Continues until stopped.

    Attributes:
        period: Seconds per full cycle (default 60)
        change: Hue degrees to shift per iteration (default 20)
        spread: Hue degrees spread across devices (default 30)
        brightness: Fixed brightness, or None to preserve (default None)
        saturation_min: Minimum saturation (0.0-1.0, default 0.8)
        saturation_max: Maximum saturation (0.0-1.0, default 1.0)
        transition: Color transition time in seconds, or None for random
        synchronized: If True, all lights show same color simultaneously (default False)

    Example:
        ```python
        # Rainbow effect with spread
        effect = EffectColorloop(period=30, change=30, spread=60)
        await conductor.start(effect, lights)

        # Synchronized colorloop - all lights same color
        effect = EffectColorloop(period=30, change=30, synchronized=True)
        await conductor.start(effect, lights)

        # Wait then stop
        await asyncio.sleep(120)
        await conductor.stop(lights)

        # Colorloop with fixed brightness
        effect = EffectColorloop(
            period=20, change=15, brightness=0.7, saturation_min=0.9
        )
        await conductor.start(effect, lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        period: float = 60,
        change: float = 20,
        spread: float = 30,
        brightness: float | None = None,
        saturation_min: float = 0.8,
        saturation_max: float = 1.0,
        transition: float | None = None,
        synchronized: bool = False,
    ) -> None:
        """Initialize colorloop effect.

        Args:
            power_on: Power on devices if off (default True)
            period: Seconds per full cycle (default 60)
            change: Hue degrees to shift per iteration (default 20)
            spread: Hue degrees spread across devices (default 30).
                    Ignored if synchronized=True.
            brightness: Fixed brightness, or None to preserve (default None)
            saturation_min: Minimum saturation (0.0-1.0, default 0.8)
            saturation_max: Maximum saturation (0.0-1.0, default 1.0)
            transition: Color transition time in seconds, or None for
                        random per device (default None). When synchronized=True
                        and transition=None, uses iteration_period as transition.
            synchronized: If True, all lights display the same color
                         simultaneously with consistent transitions. When False,
                         lights are spread across the hue spectrum based on
                         'spread' parameter (default False).

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if period <= 0:
            raise ValueError(f"Period must be positive, got {period}")
        if not (0 <= change <= 360):
            raise ValueError(f"Change must be 0-360 degrees, got {change}")
        if not (0 <= spread <= 360):
            raise ValueError(f"Spread must be 0-360 degrees, got {spread}")
        if brightness is not None and not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (0.0 <= saturation_min <= 1.0):
            raise ValueError(f"Saturation_min must be 0.0-1.0, got {saturation_min}")
        if not (0.0 <= saturation_max <= 1.0):
            raise ValueError(f"Saturation_max must be 0.0-1.0, got {saturation_max}")
        if saturation_min > saturation_max:
            raise ValueError(
                f"Saturation_min ({saturation_min}) must be <= "
                f"saturation_max ({saturation_max})"
            )
        if transition is not None and transition < 0:
            raise ValueError(f"Transition must be non-negative, got {transition}")

        # Calculate FPS from period and change
        # iterations_per_cycle = 360 / change (how many steps for a full rotation)
        # fps = iterations_per_cycle / period (steps per second)
        # Minimum 20 FPS ensures smooth animation on multizone/matrix devices.
        # For single lights, the firmware interpolates between frames using
        # duration_ms, so extra frames are harmless.
        fps = max(20.0, (360.0 / change) / period) if change > 0 else 20.0

        super().__init__(power_on=power_on, fps=fps, duration=None)

        self.period = period
        self.change = change
        self.spread = spread
        self.brightness = brightness
        self.saturation_min = saturation_min
        self.saturation_max = saturation_max
        self.transition = transition
        self.synchronized = synchronized

        # Runtime state (set during async_setup)
        self._initial_colors: list[HSBK] = []
        self._direction: int = 1

    @property
    def name(self) -> str:
        """Return the name of the effect.

        Returns:
            The effect name 'colorloop'
        """
        return "colorloop"

    async def async_setup(self, participants: list[Light]) -> None:
        """Fetch initial colors and pick rotation direction.

        Args:
            participants: List of lights participating in the effect
        """
        self._initial_colors = await self._get_initial_colors(participants)
        self._direction = random.choice([1, -1])  # nosec

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of colors for one device.

        All pixels on a device receive the same color. For multizone/matrix
        devices that need per-pixel rainbow effects, use EffectRainbow instead.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        if not self._initial_colors:
            # Fallback if setup hasn't run yet
            return [
                HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500)
            ] * ctx.pixel_count

        # Calculate hue rotation from elapsed time
        # degrees_rotated = (elapsed / period) * 360 * direction
        degrees_rotated = (ctx.elapsed_s / self.period) * 360.0 * self._direction

        if self.synchronized:
            color = self._generate_synchronized_color(degrees_rotated)
        else:
            color = self._generate_spread_color(degrees_rotated, ctx.device_index)

        return [color] * ctx.pixel_count

    def _generate_synchronized_color(self, degrees_rotated: float) -> HSBK:
        """Generate color for synchronized mode.

        All devices get the same color based on the first light's initial hue.

        Args:
            degrees_rotated: Total degrees of hue rotation

        Returns:
            HSBK color for this frame
        """
        base_hue = self._initial_colors[0].hue if self._initial_colors else 0
        new_hue = round((base_hue + degrees_rotated) % 360)

        # Consistent saturation for synchronization
        shared_saturation = (self.saturation_min + self.saturation_max) / 2

        # Calculate shared brightness
        if self.brightness is not None:
            shared_brightness = self.brightness
        else:
            shared_brightness = sum(c.brightness for c in self._initial_colors) / len(
                self._initial_colors
            )

        # Calculate shared kelvin
        shared_kelvin = int(
            sum(c.kelvin for c in self._initial_colors) / len(self._initial_colors)
        )

        return HSBK(
            hue=new_hue,
            saturation=shared_saturation,
            brightness=shared_brightness,
            kelvin=shared_kelvin,
        )

    def _generate_spread_color(self, degrees_rotated: float, device_index: int) -> HSBK:
        """Generate color for spread mode.

        Each device gets a hue offset by device_index * spread.

        Args:
            degrees_rotated: Total degrees of hue rotation
            device_index: Index of this device in participants list

        Returns:
            HSBK color for this device's frame
        """
        # Clamp device_index to available initial colors
        color_index = min(device_index, len(self._initial_colors) - 1)

        base_hue = self._initial_colors[color_index].hue
        device_spread_offset = (device_index * self.spread) % 360
        new_hue = round((base_hue + degrees_rotated + device_spread_offset) % 360)

        # Get brightness
        if self.brightness is not None:
            brightness = self.brightness
        else:
            brightness = self._initial_colors[color_index].brightness

        # Use consistent saturation for smooth animation
        saturation = (self.saturation_min + self.saturation_max) / 2

        # Use kelvin from initial color
        kelvin = self._initial_colors[color_index].kelvin

        return HSBK(
            hue=new_hue,
            saturation=saturation,
            brightness=brightness,
            kelvin=kelvin,
        )

    async def _get_initial_colors(self, participants: list[Light]) -> list[HSBK]:
        """Get initial colors for each participant.

        Args:
            participants: List of lights to get colors from

        Returns:
            List of HSBK colors, one per participant
        """

        async def get_color_for_light(light: Light) -> HSBK:
            """Get color for a single light."""
            # Determine fallback brightness based on effect configuration
            fallback_brightness = (
                self.brightness if self.brightness is not None else 0.8
            )

            # Use base class method for consistent color fetching with brightness safety
            return await self.fetch_light_color(
                light, fallback_brightness=fallback_brightness
            )

        # Fetch colors for all lights concurrently
        colors = await asyncio.gather(
            *(get_color_for_light(light) for light in participants)
        )

        return list(colors)

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        For colorloop, start with random hue and target brightness.

        Args:
            _light: The device being powered on (unused)

        Returns:
            HSBK color to use as startup color
        """
        return HSBK(
            hue=random.randint(0, 360),  # nosec
            saturation=random.uniform(self.saturation_min, self.saturation_max),  # nosec
            brightness=self.brightness if self.brightness is not None else 0.8,
            kelvin=KELVIN_NEUTRAL,
        )

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Colorloop can run without reset if switching to another colorloop.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectColorloop, False otherwise
        """
        return isinstance(other, EffectColorloop)

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with colorloop effect.

        Colorloop requires color capability to manipulate hue/saturation.

        Args:
            light: The light device to check

        Returns:
            True if light has color support, False otherwise
        """
        # Ensure capabilities are loaded
        if light.capabilities is None:
            await light._ensure_capabilities()

        # Check if light has color support
        return light.capabilities.has_color if light.capabilities else False

    def __repr__(self) -> str:
        """String representation of colorloop effect."""
        return (
            f"EffectColorloop(period={self.period}, change={self.change}, "
            f"spread={self.spread}, brightness={self.brightness}, "
            f"synchronized={self.synchronized}, power_on={self.power_on})"
        )
