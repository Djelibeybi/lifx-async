"""Abstract base class for LIFX effects.

This module provides the LIFXEffect base class that all effects should inherit from.
"""

from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import KELVIN_NEUTRAL
from lifx.effects.const import (
    DEFAULT_BRIGHTNESS,
    MIN_VISIBLE_BRIGHTNESS,
    POWER_ON_SETTLE_DELAY,
    POWER_ON_TRANSITION_DURATION,
)

if TYPE_CHECKING:
    from lifx.devices.light import Light
    from lifx.effects.conductor import Conductor

import logging

_LOGGER = logging.getLogger(__name__)


class LIFXEffect(ABC):
    """Abstract base class for light effects.

    Subclass this to create custom effects. Implement async_play() with
    your effect logic. The conductor will handle state management.

    Attributes:
        power_on: Whether to power on devices during effect
        conductor: Conductor instance managing this effect (set by conductor)
        participants: List of lights participating in effect (set by conductor)

    Example:
        ```python
        class MyEffect(LIFXEffect):
            async def async_play(self) -> None:
                # Custom effect logic
                for light in self.participants:
                    await light.set_color(HSBK.from_rgb(255, 0, 0))
        ```
    """

    def __init__(self, power_on: bool = True) -> None:
        """Initialize the effect.

        Args:
            power_on: Whether to power on devices during effect (default True)
        """
        self.power_on = power_on
        self.conductor: Conductor | None = None
        self.participants: list[Light] = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the effect.

        Returns:
            The effect name as a string
        """
        raise NotImplementedError("Subclasses must implement name property")

    async def async_perform(self, participants: list[Light]) -> None:
        """Perform common setup and play the effect.

        Called by conductor. Sets participants, powers on lights if needed,
        then calls async_play(). Subclasses should override async_play(),
        not this method.

        Args:
            participants: List of lights to apply effect to
        """
        self.participants = participants

        # Power on lights if requested and they're off
        if self.power_on:
            needs_power_on = False

            async def power_on_if_needed(light: Light) -> None:
                """Power on a single light if it's currently off."""
                nonlocal needs_power_on
                is_on = await light.get_power()
                if not is_on:
                    needs_power_on = True
                    # Get startup color for this light
                    startup_color = await self.from_poweroff_hsbk(light)
                    # Set color immediately, then power on
                    await light.set_color(startup_color, duration=0)
                    await light.set_power(True, duration=POWER_ON_TRANSITION_DURATION)

            # Power on all lights concurrently
            async with asyncio.TaskGroup() as tg:
                for light in self.participants:
                    tg.create_task(power_on_if_needed(light))

            # Wait for power transition to complete if any lights were powered on
            if needs_power_on:
                await asyncio.sleep(POWER_ON_SETTLE_DELAY)

        # Call subclass implementation
        await self.async_play()

    @abstractmethod
    async def async_play(self) -> None:
        """Play the effect logic. Override this in subclasses.

        This method is called after setup (power on, etc). Implement your
        effect logic here. Access self.participants for the light list,
        self.conductor for state management.

        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        raise NotImplementedError("Subclasses must implement async_play()")

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        Called when powering on a light for effect. By default returns
        random hue, full saturation, zero brightness, neutral white.

        Args:
            _light: The device being powered on (unused in base implementation)

        Returns:
            HSBK color to use as startup color

        Example:
            ```python
            # Override for custom startup color
            async def from_poweroff_hsbk(self, light: Light) -> HSBK:
                return HSBK.from_rgb(255, 0, 0)  # Always start with red
            ```
        """
        return HSBK(
            hue=random.randint(0, 360),  # nosec
            saturation=1.0,
            brightness=0.0,
            kelvin=KELVIN_NEUTRAL,
        )

    def inherit_prestate(self, _other: LIFXEffect) -> bool:
        """Whether this effect can skip device state restoration.

        Optimization allowing consecutive compatible effects to avoid
        resetting device state. Return True if the given effect type
        can run without requiring state restoration first.

        Args:
            _other: The incoming effect (unused in base implementation)

        Returns:
            True if state restoration can be skipped, False otherwise

        Example:
            ```python
            # ColorLoop effects can inherit from other ColorLoop effects
            def inherit_prestate(self, other: LIFXEffect) -> bool:
                return isinstance(other, EffectColorloop)
            ```
        """
        return False

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if a specific light is compatible with this effect.

        Effects can override this to implement custom compatibility logic.
        The default implementation accepts all lights.

        Args:
            light: The light device to check compatibility for

        Returns:
            True if the light is compatible with this effect, False otherwise

        Example:
            ```python
            # Effect that requires color capability
            async def is_light_compatible(self, light: Light) -> bool:
                if light.capabilities is None:
                    await light._ensure_capabilities()
                return light.capabilities.has_color if light.capabilities else False


            # Effect that requires multizone capability
            async def is_light_compatible(self, light: Light) -> bool:
                if light.capabilities is None:
                    await light._ensure_capabilities()
                return light.capabilities.has_multizone if light.capabilities else False
            ```
        """
        # Default: all lights are compatible
        return True

    async def fetch_light_color(
        self,
        light: Light,
        fallback_brightness: float = DEFAULT_BRIGHTNESS,
        min_brightness: float = MIN_VISIBLE_BRIGHTNESS,
    ) -> HSBK:
        """Fetch current color with brightness safety check.

        Gets the current color from the light, with automatic brightness
        adjustment to ensure visibility. If brightness is below the minimum
        threshold, it's boosted to the fallback brightness.

        Args:
            light: Light to fetch color from
            fallback_brightness: Brightness to use if current is too low (default: 0.8)
            min_brightness: Minimum acceptable brightness (default: 0.1)

        Returns:
            Current HSBK color with brightness safety applied

        Example:
            ```python
            # Get color with default brightness safety
            color = await self.fetch_light_color(light)

            # Get color with custom fallback
            color = await self.fetch_light_color(light, fallback_brightness=0.5)
            ```
        """
        try:
            # Fetch current color from device
            current_color, _, _ = await light.get_color()

            # Safety check: boost brightness if too low
            if current_color.brightness < min_brightness:
                _LOGGER.debug(
                    {
                        "class": self.__class__.__name__,
                        "method": "fetch_light_color",
                        "action": "request",
                        "values": {
                            "serial": light.serial,
                            "original_brightness": current_color.brightness,
                            "fallback_brightness": fallback_brightness,
                            "min_brightness": min_brightness,
                        },
                    }
                )
                current_color = HSBK(
                    hue=current_color.hue,
                    saturation=current_color.saturation,
                    brightness=fallback_brightness,
                    kelvin=current_color.kelvin,
                )

            return current_color
        except Exception as e:
            _LOGGER.warning(
                {
                    "class": self.__class__.__name__,
                    "method": "fetch_light_color",
                    "action": "request",
                    "error": str(e),
                    "values": {
                        "serial": light.serial,
                        "fallback_brightness": fallback_brightness,
                    },
                }
            )
            return self._get_fallback_color(fallback_brightness)

    def _get_fallback_color(self, brightness: float = DEFAULT_BRIGHTNESS) -> HSBK:
        """Get fallback color when fetch fails.

        Args:
            brightness: Brightness for fallback color (default: 0.8)

        Returns:
            HSBK color with random hue, full saturation, specified brightness
        """
        return HSBK(
            hue=random.randint(0, 360),  # nosec
            saturation=1.0,
            brightness=brightness,
            kelvin=KELVIN_NEUTRAL,
        )

    def __repr__(self) -> str:
        """String representation of effect."""
        return f"{self.__class__.__name__}(power_on={self.power_on})"
