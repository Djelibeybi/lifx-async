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

if TYPE_CHECKING:
    from lifx.devices.light import Light

_LOGGER = logging.getLogger(__name__)


class EffectColorloop(LIFXEffect):
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
        super().__init__(power_on=power_on)

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

        self.period = period
        self.change = change
        self.spread = spread
        self.brightness = brightness
        self.saturation_min = saturation_min
        self.saturation_max = saturation_max
        self.transition = transition
        self.synchronized = synchronized

        # Runtime state (set during execution)
        self._running = False
        self._stop_event = asyncio.Event()

    @property
    def name(self) -> str:
        """Return the name of the effect.

        Returns:
            The effect name 'colorloop'
        """
        return "colorloop"

    async def async_play(self) -> None:
        """Execute the colorloop effect continuously."""
        self._running = True
        self._stop_event.clear()

        # Get initial colors for each light
        initial_colors = await self._get_initial_colors()

        # Calculate iteration period based on change amount
        # period is time for full 360° rotation
        # iteration_period is time for each 'change' degree rotation
        iterations_per_cycle = 360.0 / self.change if self.change > 0 else 1
        iteration_period = self.period / iterations_per_cycle

        # Random initial direction for variety
        direction = random.choice([1, -1])  # nosec

        iteration = 0
        while self._running and not self._stop_event.is_set():
            if self.synchronized:
                # Synchronized mode - all lights same color
                await self._update_synchronized(
                    initial_colors, iteration, direction, iteration_period
                )
            else:
                # Spread mode - lights distributed across hue spectrum
                await self._update_spread(
                    initial_colors, iteration, direction, iteration_period
                )

            # Wait for next iteration or stop signal
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=iteration_period
                )
                break  # Stop event was set
            except TimeoutError:
                pass  # Normal - continue to next iteration

            iteration += 1

        # Effect stopped - conductor will restore state

    async def _update_synchronized(
        self,
        initial_colors: list[HSBK],
        iteration: int,
        direction: int,
        iteration_period: float,
    ) -> None:
        """Update all lights with synchronized colors.

        Args:
            initial_colors: Initial colors for each participant
            iteration: Current iteration number
            direction: Direction of hue rotation (1 or -1)
            iteration_period: Time per iteration in seconds
        """
        # Calculate shared hue for all lights
        # Use first light's base hue as reference
        base_hue = initial_colors[0].hue if initial_colors else 0
        hue_offset = (iteration * self.change * direction) % 360
        shared_hue = round((base_hue + hue_offset) % 360)

        # Generate shared saturation (consistent for synchronization)
        shared_saturation = (self.saturation_min + self.saturation_max) / 2

        # Calculate shared brightness (average of all lights)
        if self.brightness is not None:
            shared_brightness = self.brightness
        else:
            # Use average brightness for synchronization
            shared_brightness = sum(c.brightness for c in initial_colors) / len(
                initial_colors
            )

        # Calculate shared kelvin (average of all lights)
        shared_kelvin = int(sum(c.kelvin for c in initial_colors) / len(initial_colors))

        # Determine transition time (consistent for synchronization)
        if self.transition is not None:
            trans_time = self.transition
        else:
            # Use iteration period for smooth transitions
            trans_time = iteration_period

        # Update all devices with same color
        tasks = []
        for light in self.participants:
            # Create color (same for all lights)
            new_color = HSBK(
                hue=shared_hue,
                saturation=shared_saturation,
                brightness=shared_brightness,
                kelvin=shared_kelvin,
            )

            # Apply color
            tasks.append(light.set_color(new_color, duration=trans_time))

        # Apply all color changes concurrently
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            _LOGGER.error(
                {
                    "class": self.__class__.__name__,
                    "method": "_update_synchronized",
                    "action": "change",
                    "error": str(e),
                    "values": {
                        "participant_count": len(self.participants),
                        "iteration": iteration,
                        "period": self.period,
                        "change": self.change,
                    },
                }
            )

    async def _update_spread(
        self,
        initial_colors: list[HSBK],
        iteration: int,
        direction: int,
        iteration_period: float,
    ) -> None:
        """Update all lights with spread colors.

        Args:
            initial_colors: Initial colors for each participant
            iteration: Current iteration number
            direction: Direction of hue rotation (1 or -1)
            iteration_period: Time per iteration in seconds
        """
        # Randomize device order each cycle for visual variety
        device_order = list(enumerate(self.participants))
        random.shuffle(device_order)  # nosec

        # Update all devices
        tasks = []
        for idx, (original_idx, light) in enumerate(device_order):
            # Calculate hue for this device
            base_hue = initial_colors[original_idx].hue
            hue_offset = (iteration * self.change * direction) % 360
            device_spread_offset = (idx * self.spread) % 360
            new_hue = round((base_hue + hue_offset + device_spread_offset) % 360)

            # Get brightness and saturation
            if self.brightness is not None:
                brightness = self.brightness
            else:
                brightness = initial_colors[original_idx].brightness

            # Random saturation within range
            saturation = random.uniform(self.saturation_min, self.saturation_max)  # nosec

            # Use kelvin from initial color
            kelvin = initial_colors[original_idx].kelvin

            # Create new color
            new_color = HSBK(
                hue=new_hue,
                saturation=saturation,
                brightness=brightness,
                kelvin=kelvin,
            )

            # Determine transition time
            if self.transition is not None:
                trans_time = self.transition
            else:
                # Random transition time (0-2x iteration period)
                trans_time = random.uniform(0, iteration_period * 2)  # nosec

            # Apply color
            tasks.append(light.set_color(new_color, duration=trans_time))

        # Apply all color changes concurrently
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            _LOGGER.error(
                {
                    "class": self.__class__.__name__,
                    "method": "_update_spread",
                    "action": "change",
                    "error": str(e),
                    "values": {
                        "participant_count": len(self.participants),
                        "iteration": iteration,
                        "period": self.period,
                        "change": self.change,
                        "spread": self.spread,
                    },
                }
            )

    async def _get_initial_colors(self) -> list[HSBK]:
        """Get initial colors for each participant.

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
        colors: list[HSBK] = [None] * len(self.participants)  # type: ignore

        async with asyncio.TaskGroup() as tg:
            for idx, light in enumerate(self.participants):

                async def fetch_and_store(index: int, device: Light) -> None:
                    colors[index] = await get_color_for_light(device)

                tg.create_task(fetch_and_store(idx, light))

        return colors

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

    def stop(self) -> None:
        """Signal the colorloop to stop.

        This sets an internal flag that will cause async_play() to exit.
        Use conductor.stop() instead for proper state restoration.
        """
        self._running = False
        self._stop_event.set()

    def __repr__(self) -> str:
        """String representation of colorloop effect."""
        return (
            f"EffectColorloop(period={self.period}, change={self.change}, "
            f"spread={self.spread}, brightness={self.brightness}, "
            f"synchronized={self.synchronized}, power_on={self.power_on})"
        )
