"""Device state management for effects framework.

This module provides the DeviceStateManager class that handles capturing
and restoring device state (power, color, zones) during effects.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from lifx.devices.component.effect_support import (
    reinstate_stored_colors,
    restore_component,
    stored_colors_snapshot,
)
from lifx.devices.component.light import ComponentMatrixLight
from lifx.devices.light import wait_until_off
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects.const import COLOR_UPDATE_SETTLE_DELAY, ZONE_UPDATE_SETTLE_DELAY
from lifx.effects.models import PreState
from lifx.protocol.protocol_types import (
    MultiZoneApplicationRequest,
)

if TYPE_CHECKING:
    from lifx.color import HSBK
    from lifx.devices.component.participant import ComponentName
    from lifx.devices.light import Light
    from lifx.devices.paint_record import PaintRecord

_LOGGER = logging.getLogger(__name__)

# Seconds after a restore during which a capture returns the restored prestate.
DEFAULT_SETTLE_WINDOW = 5.0


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

    def __init__(
        self,
        settle_window: float = DEFAULT_SETTLE_WINDOW,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize the state manager.

        Args:
            settle_window: Seconds after a restore during which a capture
                returns the prestate that was restored instead of reading the
                device, which is still mid-fade and would report colors the
                effect painted. 0 disables the window.
            clock: Monotonic clock in seconds, replaceable for tests

        Raises:
            ValueError: If settle_window is negative
        """
        if settle_window < 0:
            raise ValueError("settle_window must not be negative")
        self._settle_window = settle_window
        self._clock = clock
        # Per serial: when the last restore began, and what it restored.
        # A caller write since then ends the window, as the device no longer
        # shows what was restored; the write count at the restore's end tells.
        self._restored: dict[str, tuple[float, int, PreState]] = {}

    @property
    def settle_window(self) -> float:
        """Seconds after a restore during which captures reuse its prestate."""
        return self._settle_window

    async def capture_state(self, light: Light) -> PreState:
        """Capture current device state.

        A capture within the settle window of the light's last restore returns
        the prestate that restore wrote, without reading the device. Only a
        restore whose every write landed opens the window; after one that
        failed or skipped a write, the device is read.

        Captures power state, colour, zone colours (for multizone devices) and
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
        restored = self._restored.get(light.serial)
        if restored is not None:
            restored_at, writes, restored_prestate = restored
            if (
                self._clock() - restored_at < self._settle_window
                and light._state_writes == writes
            ):
                return restored_prestate
            del self._restored[light.serial]

        # A paint still fading would be captured mid-fade, and restoring that
        # would put back colors the light never settled on.
        await light._await_paint_settled()
        # Taken first, to compare once the reads finish: a write while the
        # state is read replaces or ends the record.
        paint_record = light._paint_record

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
            stored_colors = stored_colors_snapshot(light)

        return PreState(
            power=bool(power > 0),
            color=color,
            zone_colors=zone_colors,
            tile_colors=tile_colors,
            stored_colors=stored_colors,
            _paint_record=self._record_still_true(
                light, paint_record, zone_colors, tile_colors
            ),
        )

    @staticmethod
    def _record_still_true(
        light: Light,
        record: PaintRecord | None,
        zone_colors: list[HSBK] | None,
        tile_colors: list[list[HSBK]] | None,
    ) -> PaintRecord | None:
        """Keep a paint record only if the captured colors still match it.

        The record must still be the light's current one, so a write that
        landed during the capture drops it. It must be a painted record, as
        restoring still colors does not resume a Morph or a software run. And
        what it recorded must equal the captured zones or tiles, as the light
        stores them.

        Args:
            light: The light the state was captured from
            record: The light's record before the reads began
            zone_colors: The captured zones, for a strip
            tile_colors: The captured tiles, for a matrix light

        Returns:
            The record, or None if it cannot be trusted
        """
        if record is None or light._paint_record is not record:
            return None
        if record.morph is not None or record.run is not None:
            return None
        if isinstance(light, MatrixLight):
            return (
                record
                if tile_colors is not None
                and record.matches_tiles(light._shown_read(tile_colors))
                else None
            )
        # Any other light captures no zones, so it cannot match a painted record.
        return (
            record
            if zone_colors is not None and record.matches_zones(zone_colors)
            else None
        )

    async def restore_state(self, light: Light, prestate: PreState) -> None:
        """Restore device to pre-effect state.

        Restores power, colour, zones (for multizone devices) and whole tiles
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
        # A light that was on gets its colours back, then power. One that was
        # off goes dark first and gets its colours back once it reports off,
        # so they never show as a flash; if it never reports off, they are
        # not written at all.
        # ``complete`` stays True only while every write the restore needs
        # has landed: a failed or skipped write, or a fallback to one color,
        # leaves the light showing something other than the prestate.
        write_colours = True
        exact = False
        complete = True
        if not prestate.power:
            complete = await self._restore_power(light, prestate.power)
            write_colours = await self._wait_until_off(light)
            complete = complete and write_colours

        if write_colours:
            # SetColor paints every zone, so it must never follow zones or
            # tiles it would flatten; it is only the fallback for a strip
            # whose zones could not be written.
            if isinstance(light, MultiZoneLight) and prestate.zone_colors:
                exact = await self._restore_zones(light, prestate.zone_colors)
                if not exact:
                    await self._restore_color(light, prestate.color)
                complete = complete and exact
            elif isinstance(light, MatrixLight) and prestate.tile_colors:
                exact = await self._restore_tiles(light, prestate.tile_colors)
                complete = complete and exact
            else:
                written = await self._restore_color(light, prestate.color)
                complete = complete and written

        if prestate.power:
            powered = await self._restore_power(light, prestate.power)
            complete = complete and powered

        # The zones or tiles are back exactly, so the light shows what the
        # record described. After a failed or skipped write, a fallback to one
        # color, or a single-color restore, it is not known to.
        light._adopt_paint_record(prestate._paint_record if exact else None)

        # Ceiling and Mirror: an effect never changes either component's
        # stored colours, whatever the restore writes above remembered.
        if isinstance(light, ComponentMatrixLight) and prestate.stored_colors:
            await reinstate_stored_colors(light, prestate.stored_colors)

        # Stamped once the writes are done, so the count includes them and only
        # a later caller write ends the window. Only a complete restore is
        # stamped: after a failed or skipped write the light may still show
        # the effect or a fallback color, so the next capture must read it,
        # and an entry from an earlier restore no longer describes it either.
        if self._settle_window > 0 and complete:
            self._restored[light.serial] = (
                self._clock(),
                light._state_writes,
                prestate,
            )
        else:
            self._restored.pop(light.serial, None)

    async def restore_component(
        self, light: ComponentMatrixLight, component: ComponentName, prestate: PreState
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
        try:
            await restore_component(
                light,
                component,
                prestate.tile_colors[0] if prestate.tile_colors else None,
                prestate.power,
                prestate.stored_colors,
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
    ) -> bool:
        """Restore multizone colors.

        Args:
            light: MultiZoneLight device to restore zones to
            zone_colors: List of zone colors to restore

        Returns:
            Whether the zones were written
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
                light._clamp_colors(zone_colors),
                duration=0.0,
                apply=MultiZoneApplicationRequest.APPLY,
            )

            # Small delay to let zones update
            await asyncio.sleep(ZONE_UPDATE_SETTLE_DELAY)
            return True
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
            return False

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
    ) -> bool:
        """Write every captured tile back to a matrix light.

        Args:
            light: MatrixLight device to restore tiles to
            tile_colors: One list of colours per tile

        Returns:
            Whether every tile was written
        """
        try:
            for tile_index, colors in enumerate(tile_colors):
                await light.set_matrix_colors(
                    tile_index, light._clamp_colors(colors), duration=0
                )
            await asyncio.sleep(ZONE_UPDATE_SETTLE_DELAY)
            return True
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
            return False

    async def _restore_color(self, light: Light, color: HSBK) -> bool:
        """Restore device color.

        Args:
            light: Light device to restore color to
            color: HSBK color to restore

        Returns:
            Whether the color was written
        """
        try:
            await light.set_color(light._clamp_color(color), duration=0.0)
            await asyncio.sleep(COLOR_UPDATE_SETTLE_DELAY)  # Let color update
            return True
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
            return False

    async def _wait_until_off(self, light: Light) -> bool:
        """Wait for a power-off to take effect before colours are written.

        Args:
            light: Light device that was just turned off

        Returns:
            True once the light reports off; False, with a warning, if it
            still reports on when the wait runs out or its power cannot be
            read, in which case no colours should be written
        """
        try:
            if await wait_until_off(light):
                return True
            error = "the light did not report off in time"
        except Exception as e:
            error = str(e)
        _LOGGER.warning(
            {
                "class": self.__class__.__name__,
                "method": "_wait_until_off",
                "action": "skip_colours",
                "error": error,
                "values": {"serial": light.serial},
            }
        )
        return False

    async def _restore_power(self, light: Light, power: bool) -> bool:
        """Restore power state.

        Args:
            light: Light device to restore power to
            power: Power state to restore (True=on, False=off)

        Returns:
            Whether the power was written
        """
        try:
            await light.set_power(power, duration=0.0)
            return True
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
            return False

    def __repr__(self) -> str:
        """String representation of DeviceStateManager."""
        return "DeviceStateManager()"
