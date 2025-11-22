"""Device state management for effects framework.

This module provides the DeviceStateManager class that handles capturing
and restoring device state (power, color, zones) during effects.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from lifx.devices.multizone import MultiZoneLight
from lifx.effects.const import COLOR_UPDATE_SETTLE_DELAY, ZONE_UPDATE_SETTLE_DELAY
from lifx.effects.models import PreState
from lifx.protocol.protocol_types import (
    MultiZoneApplicationRequest,
)

if TYPE_CHECKING:
    from lifx.color import HSBK
    from lifx.devices.light import Light

_LOGGER = logging.getLogger(__name__)


class DeviceStateManager:
    """Manages device state capture and restoration for effects.

    Handles capturing device state before effects and restoring it afterward,
    including power state, color, and multizone configurations.

    Example:
        ```python
        state_manager = DeviceStateManager()

        # Capture state before effect
        prestate = await state_manager.capture_state(light)

        # Run effect...

        # Restore state after effect
        await state_manager.restore_state(light, prestate)
        ```
    """

    async def capture_state(self, light: Light) -> PreState:
        """Capture current device state.

        Captures power state, color, and zone colors (for multizone devices)
        to enable restoration after effects complete.

        Args:
            light: Light device to capture state from

        Returns:
            PreState with captured power, color, and zone information

        Raises:
            Exception: If state capture fails (logged as warning)

        Example:
            ```python
            prestate = await state_manager.capture_state(light)
            print(f"Captured: {prestate}")
            ```
        """
        # Get power and color states
        color, power, _ = await light.get_color()

        # Get zone colors for multizone devices
        zone_colors = None
        if isinstance(light, MultiZoneLight):
            zone_colors = await self._capture_zones(light)

        return PreState(power=bool(power > 0), color=color, zone_colors=zone_colors)

    async def restore_state(self, light: Light, prestate: PreState) -> None:
        """Restore device to pre-effect state.

        Restores power, color, and zones (for multizone devices) in the
        correct order to ensure smooth transitions.

        Args:
            light: Light device to restore
            prestate: PreState to restore

        Example:
            ```python
            # After effect completes
            await state_manager.restore_state(light, prestate)
            ```
        """
        # Restore in order: zones -> color -> power
        if isinstance(light, MultiZoneLight) and prestate.zone_colors:
            await self._restore_zones(light, prestate.zone_colors)

        await self._restore_color(light, prestate.color)
        await self._restore_power(light, prestate.power)

    async def _capture_zones(self, light: MultiZoneLight) -> list[HSBK] | None:
        """Capture zone colors from multizone device.

        Args:
            light: MultiZoneLight device to capture zones from

        Returns:
            List of zone colors, or None if capture fails
        """
        try:
            zone_count = await light.get_zone_count()

            # Use extended multizone if available (more efficient)
            if light.capabilities and light.capabilities.has_extended_multizone:
                zone_colors = await light.get_extended_color_zones(
                    start=0, end=zone_count - 1
                )
            else:
                # Fall back to standard multizone
                zone_colors = await light.get_color_zones(start=0, end=zone_count - 1)

            _LOGGER.debug(
                {
                    "class": self.__class__.__name__,
                    "method": "_capture_zones",
                    "action": "capture",
                    "values": {
                        "serial": light.serial,
                        "zone_count": len(zone_colors),
                        "extended_multizone": light.capabilities
                        and light.capabilities.has_extended_multizone,
                    },
                }
            )
            return zone_colors
        except Exception as e:
            _LOGGER.warning(
                {
                    "class": self.__class__.__name__,
                    "method": "_capture_zones",
                    "action": "capture",
                    "error": str(e),
                    "values": {"serial": light.serial},
                }
            )
            return None

    async def _restore_zones(
        self, light: MultiZoneLight, zone_colors: list[HSBK]
    ) -> None:
        """Restore multizone colors.

        Args:
            light: MultiZoneLight device to restore zones to
            zone_colors: List of zone colors to restore
        """
        try:
            _LOGGER.debug(
                {
                    "class": self.__class__.__name__,
                    "method": "_restore_zones",
                    "action": "restore",
                    "values": {
                        "serial": light.serial,
                        "zone_count": len(zone_colors),
                        "extended_multizone": light.capabilities
                        and light.capabilities.has_extended_multizone,
                    },
                }
            )

            # Use extended multizone if available (more efficient)
            if light.capabilities and light.capabilities.has_extended_multizone:
                await light.set_extended_color_zones(
                    zone_index=0,
                    colors=zone_colors,
                    duration=0.0,
                    apply=MultiZoneApplicationRequest.APPLY,
                )
            else:
                # Restore zones individually, applying only on last update
                for i, color in enumerate(zone_colors):
                    is_last = i == len(zone_colors) - 1
                    apply = (
                        MultiZoneApplicationRequest.APPLY
                        if is_last
                        else MultiZoneApplicationRequest.NO_APPLY
                    )
                    await light.set_color_zones(
                        start=i,
                        end=i,
                        color=color,
                        duration=0.0,
                        apply=apply,
                    )

            # Small delay to let zones update
            await asyncio.sleep(ZONE_UPDATE_SETTLE_DELAY)
        except Exception as e:
            _LOGGER.warning(
                {
                    "class": self.__class__.__name__,
                    "method": "_restore_zones",
                    "action": "restore",
                    "error": str(e),
                    "values": {"serial": light.serial, "zone_count": len(zone_colors)},
                }
            )

    async def _restore_color(self, light: Light, color: HSBK) -> None:
        """Restore device color.

        Args:
            light: Light device to restore color to
            color: HSBK color to restore
        """
        try:
            await light.set_color(color, duration=0.0)
            await asyncio.sleep(COLOR_UPDATE_SETTLE_DELAY)  # Let color update
        except Exception as e:
            _LOGGER.warning(
                {
                    "class": self.__class__.__name__,
                    "method": "_restore_color",
                    "action": "restore",
                    "error": str(e),
                    "values": {
                        "serial": light.serial,
                        "color": {
                            "hue": color.hue,
                            "saturation": color.saturation,
                            "brightness": color.brightness,
                            "kelvin": color.kelvin,
                        },
                    },
                }
            )

    async def _restore_power(self, light: Light, power: bool) -> None:
        """Restore power state.

        Args:
            light: Light device to restore power to
            power: Power state to restore (True=on, False=off)
        """
        try:
            await light.set_power(power, duration=0.0)
        except Exception as e:
            _LOGGER.warning(
                {
                    "class": self.__class__.__name__,
                    "method": "_restore_power",
                    "action": "restore",
                    "error": str(e),
                    "values": {"serial": light.serial, "power": power},
                }
            )

    def __repr__(self) -> str:
        """String representation of DeviceStateManager."""
        return "DeviceStateManager()"
