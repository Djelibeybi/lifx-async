"""Device state management for effects framework.

This module provides the DeviceStateManager class that handles capturing
and restoring device state (power, color, zones) during effects.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from lifx.devices.component.light import ComponentMatrixLight
from lifx.devices.matrix import MatrixLight
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

        Captures power state, color, zone colors (for multizone devices) and
        the colours of every tile (for matrix lights) to enable restoration
        after effects complete.

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

        tile_colors = None
        if isinstance(light, MatrixLight):
            tile_colors = await self._capture_tiles(light)

        # Taken after the tile read so the read's own observations count.
        stored_colors = None
        if isinstance(light, ComponentMatrixLight):
            stored_colors = light._stored_colors_snapshot()

        return PreState(
            power=bool(power > 0),
            color=color,
            zone_colors=zone_colors,
            tile_colors=tile_colors,
            stored_colors=stored_colors,
        )

    async def restore_state(self, light: Light, prestate: PreState) -> None:
        """Restore device to pre-effect state.

        Restores power, color, zones (for multizone devices) and whole tiles
        (for matrix lights) in the correct order to ensure smooth transitions.
        A matrix light gets back every tile it showed, not one colour.

        Args:
            light: Light device to restore
            prestate: PreState to restore

        Example:
            ```python
            # After effect completes
            await state_manager.restore_state(light, prestate)
            ```
        """
        # Restore in order: zones -> tiles or color -> power
        if isinstance(light, MultiZoneLight) and prestate.zone_colors:
            await self._restore_zones(light, prestate.zone_colors)

        if isinstance(light, MatrixLight) and prestate.tile_colors:
            await self._restore_tiles(light, prestate.tile_colors)
        else:
            await self._restore_color(light, prestate.color)
        await self._restore_power(light, prestate.power)

        # Ceiling and Mirror: an effect never changes either component's
        # stored colours, whatever the restore writes above remembered.
        if isinstance(light, ComponentMatrixLight) and prestate.stored_colors:
            await light._reinstate_stored_colors(prestate.stored_colors)

    async def restore_component(
        self, light: ComponentMatrixLight, component: str, prestate: PreState
    ) -> None:
        """Restore one light component after its software effect.

        A light component that was lit gets back its colours from the tile
        captured before the effect; one that was dark, or whose light was
        off, is turned off again, powering the light off if the other light
        component is dark too. The other light component is left as it is
        now, including any change its caller made meanwhile, and the light
        component's stored colours are those from before the effect.

        Args:
            light: The Ceiling or Mirror light the light component belongs to
            component: The light component's name
            prestate: State captured from the light before the effect
        """
        stored = (prestate.stored_colors or {}).get(component)
        try:
            await light._restore_component(
                component,
                prestate.tile_colors[0] if prestate.tile_colors else None,
                prestate.power,
                stored,
            )
        except Exception as e:
            _LOGGER.warning(
                {
                    "class": self.__class__.__name__,
                    "method": "restore_component",
                    "action": "restore",
                    "error": str(e),
                    "values": {"serial": light.serial, "component": component},
                }
            )

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

            # set_all_color_zones picks the extended or legacy packet based on
            # capabilities and chunks past the 82-color extended limit, so a
            # strip longer than that restores instead of raising ValueError.
            await light.set_all_color_zones(
                zone_colors,
                duration=0.0,
                apply=MultiZoneApplicationRequest.APPLY,
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

    async def _capture_tiles(self, light: MatrixLight) -> list[list[HSBK]] | None:
        """Capture the colours of every tile of a matrix light.

        Args:
            light: MatrixLight device to capture tiles from

        Returns:
            One list of colours per tile, or None if capture fails
        """
        try:
            return [list(tile) for tile in await light.get_all_tile_colors()]
        except Exception as e:
            _LOGGER.warning(
                {
                    "class": self.__class__.__name__,
                    "method": "_capture_tiles",
                    "action": "capture",
                    "error": str(e),
                    "values": {"serial": light.serial},
                }
            )
            return None

    async def _restore_tiles(
        self, light: MatrixLight, tile_colors: list[list[HSBK]]
    ) -> None:
        """Write every captured tile back to a matrix light.

        Args:
            light: MatrixLight device to restore tiles to
            tile_colors: One list of colours per tile
        """
        try:
            for tile_index, colors in enumerate(tile_colors):
                await light.set_matrix_colors(tile_index, colors, duration=0)
            await asyncio.sleep(ZONE_UPDATE_SETTLE_DELAY)
        except Exception as e:
            _LOGGER.warning(
                {
                    "class": self.__class__.__name__,
                    "method": "_restore_tiles",
                    "action": "restore",
                    "error": str(e),
                    "values": {"serial": light.serial, "tiles": len(tile_colors)},
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
