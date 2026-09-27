"""LIFX Ceiling Light Device.

This module provides the CeilingLight class for controlling LIFX Ceiling lights with
independent uplight and downlight component control.

Terminology:
- Zone: Individual HSBK pixel in the matrix (indexed 0-63 or 0-127)
- Component: Logical grouping of zones:
  - Uplight Component: Single zone for ambient lighting (zone 63 or 127)
  - Downlight Component: Multiple zones for main illumination (zones 0-62 or 0-126)

Product IDs:
- 176: Ceiling              - 8x8 matrix
- 177: Ceiling Intl         - 8x8 matrix
- 201: Ceiling 13x26        - 16x8 matrix
- 202: Ceiling 13x26 Intl   - 16x8 matrix
- 265: Ceiling 13".         - 8x8 matrix
- 266: Ceiling 13" Intl     - 8x8 matrix
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, cast

from lifx.color import HSBK
from lifx.const import DEFAULT_MAX_RETRIES, DEFAULT_REQUEST_TIMEOUT, LIFX_UDP_PORT
from lifx.devices.component.light import ComponentMatrixLight, _ComponentFields
from lifx.devices.component.state import (
    color_as_dict,
    colors_as_dict,
    decode_color,
    encode_color,
    read_state_file,
    write_state_file,
    zones_as_dict,
)
from lifx.devices.matrix import MatrixLightState
from lifx.exceptions import LifxError
from lifx.products import get_ceiling_layout, is_ceiling_product

_LOGGER = logging.getLogger(__name__)


@dataclass
class CeilingLightState(MatrixLightState):
    """Ceiling light device state with uplight/downlight component control.

    Extends MatrixLightState with ceiling-specific component information.

    Attributes:
        uplight_color: Current HSBK color of the uplight component
        downlight_colors: List of HSBK colors for each downlight zone
        uplight_is_on: Whether uplight component is on (brightness > 0)
        downlight_is_on: Whether downlight component is on (any zone brightness > 0)
        uplight_zone: Zone index for the uplight component
        downlight_zones: Slice representing downlight component zones
        stored_uplight_color: Stored uplight color for restoration
            after turning off
        stored_downlight_colors: Stored downlight colors for restoration
            after turning off
        last_uplight_color: Last known uplight color, updated after
            every operation
        last_downlight_colors: Last known downlight colors, updated
            after every operation
    """

    uplight_color: HSBK
    downlight_colors: list[HSBK]
    uplight_is_on: bool
    downlight_is_on: bool
    uplight_zone: int
    downlight_zones: slice
    stored_uplight_color: HSBK | None = field(default=None)
    stored_downlight_colors: list[HSBK] | None = field(default=None)
    last_uplight_color: HSBK | None = field(default=None)
    last_downlight_colors: list[HSBK] | None = field(default=None)

    @property
    def as_dict(self) -> Any:
        """Return CeilingLightState as dict.

        ``downlight_zones`` is expanded from a :class:`slice` into a
        ``{"start": ..., "stop": ..., "step": ...}`` mapping so the result is
        serialisable.

        Ceiling layouts define the zones as ``slice(0, N)``, which leaves
        ``slice.step`` set to None even though it steps by one, so the step is
        normalised to 1 here.

        The uplight/downlight colors are expanded via :attr:`HSBK.as_dict`;
        the stored and last-known fields stay None when unset.
        """
        state = super().as_dict
        state["downlight_zones"] = zones_as_dict(self.downlight_zones)
        state["uplight_is_on"] = self.uplight_is_on
        state["downlight_is_on"] = self.downlight_is_on
        state["uplight_zone"] = self.uplight_zone
        state["uplight_color"] = self.uplight_color.as_dict
        state["downlight_colors"] = colors_as_dict(self.downlight_colors)
        state["stored_uplight_color"] = color_as_dict(self.stored_uplight_color)
        state["stored_downlight_colors"] = colors_as_dict(self.stored_downlight_colors)
        state["last_uplight_color"] = color_as_dict(self.last_uplight_color)
        state["last_downlight_colors"] = colors_as_dict(self.last_downlight_colors)
        return state

    @classmethod
    def from_matrix_state(
        cls,
        matrix_state: MatrixLightState,
        uplight_color: HSBK,
        downlight_colors: list[HSBK],
        uplight_zone: int,
        downlight_zones: slice,
        *,
        stored_uplight_color: HSBK | None = None,
        stored_downlight_colors: list[HSBK] | None = None,
    ) -> CeilingLightState:
        """Create CeilingLightState from MatrixLightState.

        Args:
            matrix_state: Base MatrixLightState to extend
            uplight_color: Current uplight zone color
            downlight_colors: Current downlight zone colors
            uplight_zone: Zone index for uplight component
            downlight_zones: Slice representing downlight component zones
            stored_uplight_color: Stored uplight color for restoration
            stored_downlight_colors: Stored downlight colors for
                restoration

        Returns:
            CeilingLightState with all matrix state plus ceiling
            components
        """
        return cls(
            model=matrix_state.model,
            label=matrix_state.label,
            serial=matrix_state.serial,
            mac_address=matrix_state.mac_address,
            power=matrix_state.power,
            capabilities=matrix_state.capabilities,
            host_firmware=matrix_state.host_firmware,
            wifi_firmware=matrix_state.wifi_firmware,
            wifi_info=matrix_state.wifi_info,
            thread_info=matrix_state.thread_info,
            location=matrix_state.location,
            group=matrix_state.group,
            color=matrix_state.color,
            ambient_light=matrix_state.ambient_light,
            chain=matrix_state.chain,
            tile_orientations=matrix_state.tile_orientations,
            tile_colors=matrix_state.tile_colors,
            tile_count=matrix_state.tile_count,
            effect=matrix_state.effect,
            uplight_color=uplight_color,
            downlight_colors=downlight_colors,
            uplight_is_on=matrix_state.power > 0 and uplight_color.brightness > 0,
            downlight_is_on=matrix_state.power > 0
            and any(c.brightness > 0 for c in downlight_colors),
            uplight_zone=uplight_zone,
            downlight_zones=downlight_zones,
            stored_uplight_color=stored_uplight_color,
            stored_downlight_colors=stored_downlight_colors,
            last_uplight_color=uplight_color,
            last_downlight_colors=list(downlight_colors),
            last_updated=time.time(),
        )


class CeilingLight(ComponentMatrixLight):
    """LIFX Ceiling Light with independent uplight and downlight control.

    CeilingLight extends MatrixLight to provide semantic control over uplight and
    downlight components while maintaining full backward compatibility with the
    MatrixLight API.

    The uplight component is the last zone in the matrix, and the downlight component
    consists of all other zones.

    Example:
        ```python
        from lifx.devices import CeilingLight
        from lifx.color import HSBK

        async with await Device.connect("192.168.1.100") as ceiling:
            assert isinstance(ceiling, CeilingLight)
            # Independent component control
            await ceiling.set_downlight_colors(HSBK(hue=0, sat=0, bri=1.0, kelvin=3500))
            await ceiling.set_uplight_color(HSBK(hue=30, sat=0.2, bri=0.3, kelvin=2700))

            # Turn components on/off
            await ceiling.turn_downlight_on()
            await ceiling.turn_uplight_off()

            # Check component state
            if ceiling.uplight_is_on:
                print("Uplight is on")
        ```
    """

    _component_fields = (
        _ComponentFields("uplight", "uplight_color", scalar=True),
        _ComponentFields("downlight", "downlight_colors"),
    )

    def _component_positions(self, component: str) -> tuple[int, ...]:
        """Map named Ceiling regions into the shared tile."""
        if component == "uplight":
            return (self.uplight_zone,)
        return tuple(range(self.downlight_zone_count))

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = LIFX_UDP_PORT,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        state_file: str | None = None,
        *,
        fetch_wifi_info: bool = False,
        fetch_thread_info: bool = False,
        fetch_radio_info: bool = False,
        fetch_ambient_light: bool = False,
    ):
        """Initialize CeilingLight.

        ``state_file`` keeps its original position: inserting a parameter ahead
        of it would silently rebind existing positional callers. New options are
        keyword-only for the same reason.

        Args:
            serial: Device serial number
            ip: Device IP address
            port: Device UDP port (default: 56700)
            timeout: Overall timeout for network requests in seconds
            max_retries: Maximum number of retry attempts for network requests
            state_file: Optional path to JSON file for state persistence
            fetch_wifi_info: Query WiFi signal strength during state initialization
            fetch_thread_info: Query Thread mesh information during state
                initialization
            fetch_radio_info: Query whichever radio matches the device's
                evidenced connectivity during state initialization
            fetch_ambient_light: Query the ambient light sensor during state
                initialization

        Raises:
            LifxError: If device is not a supported Ceiling product
        """
        super().__init__(
            serial,
            ip,
            port,
            timeout,
            max_retries,
            fetch_wifi_info=fetch_wifi_info,
            fetch_thread_info=fetch_thread_info,
            fetch_radio_info=fetch_radio_info,
            fetch_ambient_light=fetch_ambient_light,
        )
        self._state_file = state_file

    async def __aenter__(self) -> CeilingLight:
        """Async context manager entry."""
        await super().__aenter__()

        # Validate product ID after version is fetched
        if self.version and not is_ceiling_product(self.version.product):
            raise LifxError(
                f"Product ID {self.version.product} is not a supported Ceiling light."
            )

        # Load state from disk if state_file is provided
        if self._state_file:
            await self._load_state_from_file()

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context manager, saving state to file before closing.

        Saves the current in-memory state to ``state_file`` (when set) before
        delegating to the parent ``close()`` via ``super().__aexit__()``.
        ``_save_state_to_file()`` does its file I/O in a worker thread so it
        never blocks the event loop, and logs ordinary I/O failures as a
        WARNING rather than raising.  The ``except Exception`` here is a
        belt-and-braces guard: anything the save does not handle would
        otherwise escape ``__aexit__`` and replace the body's exception.  The
        save is wrapped in ``try/finally`` so the parent cleanup always runs —
        even if cancellation (``asyncio.CancelledError``, a ``BaseException``
        that neither handler catches) lands while the save is pending.  The
        original body exception (if any) is never replaced or suppressed.
        """
        try:
            if self._state_file:
                try:
                    await self._save_state_to_file()
                except Exception as e:
                    _LOGGER.warning(
                        "Failed to save state on __aexit__ for %s: %s",
                        self.serial,
                        e,
                    )
        finally:
            await super().__aexit__(exc_type, exc_val, exc_tb)

    async def _initialize_state(self) -> CeilingLightState:
        """Initialize ceiling light state transactionally.

        Extends MatrixLight implementation to add ceiling-specific component state.

        Returns:
            CeilingLightState instance with all device, light, matrix,
            and ceiling component information.

        Raises:
            LifxTimeoutError: If device does not respond within timeout
            LifxDeviceNotFoundError: If device cannot be reached
            LifxProtocolError: If responses are invalid
        """
        matrix_state = await super()._initialize_state()

        # Extract ceiling component colors from already-fetched tile_colors
        # (parent _initialize_state already called get_all_tile_colors)
        tile_colors = matrix_state.tile_colors
        uplight_color = tile_colors[self.uplight_zone]
        downlight_colors = list(tile_colors[self.downlight_zones])

        # Create ceiling state from matrix state
        # (from_matrix_state sets last_uplight_color and
        # last_downlight_colors automatically)
        ceiling_state = CeilingLightState.from_matrix_state(
            matrix_state=matrix_state,
            uplight_color=uplight_color,
            downlight_colors=downlight_colors,
            uplight_zone=self.uplight_zone,
            downlight_zones=self.downlight_zones,
        )

        # Store in _state - cast is used in state property
        self._state = ceiling_state

        return ceiling_state

    async def refresh_state(self) -> None:
        """Refresh ceiling light state from hardware.

        Fetches color, tiles, tile colors, effect, and ceiling component state.

        Raises:
            LifxTimeoutError: If device does not respond
            LifxDeviceNotFoundError: If device cannot be reached
        """
        await super().refresh_state()

        # Extract ceiling component colors from already-fetched tile_colors
        # (parent refresh_state already called get_all_tile_colors)
        tile_colors = self._state.tile_colors
        uplight_color = tile_colors[self.uplight_zone]
        downlight_colors = list(tile_colors[self.downlight_zones])

        # Update ceiling-specific state fields
        state = cast(CeilingLightState, self._state)
        state.uplight_color = uplight_color
        state.downlight_colors = list(downlight_colors)
        state.last_uplight_color = uplight_color
        state.last_downlight_colors = list(downlight_colors)
        state.uplight_is_on = bool(state.power > 0 and uplight_color.brightness > 0)
        state.downlight_is_on = bool(
            state.power > 0 and any(c.brightness > 0 for c in downlight_colors)
        )

    @classmethod
    async def from_ip(
        cls,
        ip: str,
        port: int = LIFX_UDP_PORT,
        serial: str | None = None,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        *,
        fetch_wifi_info: bool = False,
        fetch_thread_info: bool = False,
        fetch_radio_info: bool = False,
        fetch_ambient_light: bool = False,
        state_file: str | None = None,
    ) -> CeilingLight:
        """Create CeilingLight from IP address.

        Args:
            ip: Device IP address
            port: Port number (default LIFX_UDP_PORT)
            serial: Serial number as 12-digit hex string
            timeout: Request timeout for this device instance
            max_retries: Maximum number of retries for requests
            fetch_wifi_info: Query WiFi signal strength during state initialization
            fetch_thread_info: Query Thread mesh information during state
                initialization
            fetch_radio_info: Query whichever radio matches the device's
                evidenced connectivity during state initialization
            fetch_ambient_light: Query the ambient light sensor during state
                initialization
            state_file: Optional path to JSON file for state persistence

        Returns:
            CeilingLight instance

        Raises:
            LifxDeviceNotFoundError: Device not found at IP
            LifxTimeoutError: Device did not respond
            LifxError: Device is not a supported Ceiling product
        """
        # Parent factory constructs via cls(...), so this is already a fully
        # configured CeilingLight — only state_file needs setting
        device = await super().from_ip(
            ip,
            port,
            serial,
            timeout,
            max_retries,
            fetch_wifi_info=fetch_wifi_info,
            fetch_thread_info=fetch_thread_info,
            fetch_radio_info=fetch_radio_info,
            fetch_ambient_light=fetch_ambient_light,
        )
        device._state_file = state_file
        return device

    @property
    def state(self) -> CeilingLightState:
        """Get Ceiling light state.

        Returns:
            CeilingLightState with current state information.

        Raises:
            RuntimeError: If accessed before state initialization.
        """
        if self._state is None:
            raise RuntimeError("State not found.")
        return cast(CeilingLightState, self._state)

    @property
    def uplight_zone(self) -> int:
        """Zone index of the uplight component.

        Returns:
            Zone index (63 for standard Ceiling, 127 for Capsule)

        Raises:
            LifxError: If device version is not available or not a Ceiling product
        """
        if not self.version:
            raise LifxError("Device version not available. Use async context manager.")

        layout = get_ceiling_layout(self.version.product)
        if not layout:
            raise LifxError(f"Product ID {self.version.product} is not a Ceiling light")

        return layout.uplight_zone

    @property
    def downlight_zones(self) -> slice:
        """Slice representing the downlight component zones.

        Returns:
            Slice object (slice(0, 63) for standard, slice(0, 127) for Capsule)

        Raises:
            LifxError: If device version is not available or not a Ceiling product
        """
        if not self.version:
            raise LifxError("Device version not available. Use async context manager.")

        layout = get_ceiling_layout(self.version.product)
        if not layout:
            raise LifxError(f"Product ID {self.version.product} is not a Ceiling light")

        return layout.downlight_zones

    @property
    def downlight_zone_count(self) -> int:
        """Number of downlight zones.

        Returns:
            Zone count (63 for standard 8x8, 127 for Capsule 16x8)

        Raises:
            LifxError: If device version is not available or not a Ceiling product
        """
        # downlight_zones is slice(0, N), so stop equals the count
        stop = self.downlight_zones.stop
        if stop is None:
            raise LifxError("Invalid downlight zones configuration")
        return stop

    @property
    def uplight_is_on(self) -> bool:
        """True if uplight component is currently on.

        Calculated as: power_level > 0 AND uplight brightness > 0

        Note:
            Requires recent data from device. Call refresh_state()
            to update cached values before checking this property.

        Returns:
            True if uplight component is on, False otherwise
        """
        if self._state is None or self._state.power == 0:
            return False

        state = cast(CeilingLightState, self._state)
        if state.last_uplight_color is None:
            return False

        return state.last_uplight_color.brightness > 0

    @property
    def downlight_is_on(self) -> bool:
        """True if downlight component is currently on.

        Calculated as: power_level > 0 AND NOT all downlight zones
        have brightness == 0

        Note:
            Requires recent data from device. Call refresh_state()
            to update cached values before checking this property.

        Returns:
            True if downlight component is on, False otherwise
        """
        if self._state is None or self._state.power == 0:
            return False

        state = cast(CeilingLightState, self._state)
        if state.last_downlight_colors is None:
            return False

        return any(c.brightness > 0 for c in state.last_downlight_colors)

    async def get_uplight_color(self) -> HSBK:
        """Get current uplight component color from device.

        Returns:
            HSBK color of uplight zone

        Raises:
            LifxTimeoutError: Device did not respond
        """
        # Get all colors from tile
        all_colors = await self.get_all_tile_colors()
        tile_colors = all_colors[0]  # First tile

        # Extract uplight zone
        uplight_color = tile_colors[self.uplight_zone]

        return uplight_color

    async def get_downlight_colors(self) -> list[HSBK]:
        """Get current downlight component colors from device.

        Returns:
            List of HSBK colors for each downlight zone (63 or 127 zones)

        Raises:
            LifxTimeoutError: Device did not respond
        """
        # Get all colors from tile
        all_colors = await self.get_all_tile_colors()
        tile_colors = all_colors[0]  # First tile

        # Extract downlight zones
        downlight_colors = tile_colors[self.downlight_zones]

        return list(downlight_colors)

    async def set_uplight_color(self, color: HSBK, duration: float = 0.0) -> None:
        """Set uplight component color.

        Args:
            color: HSBK color to set
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If color.brightness == 0 (use turn_uplight_off instead)
            LifxTimeoutError: Device did not respond

        Note:
            Also updates stored state for future restoration.
        """
        await self._set_component_colors("uplight", color, duration)

    async def set_downlight_colors(
        self, colors: HSBK | list[HSBK], duration: float = 0.0
    ) -> None:
        """Set downlight component colors.

        Args:
            colors: Either:

                - Single HSBK: sets all downlight zones to same color
                - List[HSBK]: sets each zone individually (must match zone count)
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If any color.brightness == 0 (use turn_downlight_off instead)
            ValueError: If list length doesn't match downlight zone count
            LifxTimeoutError: Device did not respond

        Note:
            Also updates stored state for future restoration.
        """
        await self._set_component_colors("downlight", colors, duration)

    async def turn_uplight_on(
        self, color: HSBK | None = None, duration: float = 0.0
    ) -> None:
        """Turn uplight component on.

        If the entire light is off, this will set the color instantly and then
        turn on the light with the specified duration, so the light fades to
        the target color instead of flashing to its previous state.

        Args:
            color: Optional HSBK color. If provided:

                - Uses this color immediately
                - Updates stored state

                If None, uses brightness determination logic
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If color.brightness == 0
            LifxTimeoutError: Device did not respond
        """
        await self._turn_component_on("uplight", color, duration)

    async def turn_uplight_off(
        self, color: HSBK | None = None, duration: float = 0.0
    ) -> None:
        """Turn uplight component off.

        Args:
            color: Optional HSBK color to store for future turn_on.
                If provided, stores this color (with brightness=0 on the device).
                If None, stores current color from device before turning off.
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If color.brightness == 0
            LifxTimeoutError: Device did not respond

        Note:
            Sets uplight zone brightness to 0 on device while preserving H, S, K.
            If the downlight component is already off, the entire device is
            powered off instead and the uplight zone keeps its brightness, so
            a later set_power(True) brings the uplight back rather than turning
            on a light with every zone at zero brightness.
        """
        await self._turn_component_off("uplight", color, duration)

    async def turn_downlight_on(
        self, colors: HSBK | list[HSBK] | None = None, duration: float = 0.0
    ) -> None:
        """Turn downlight component on.

        If the entire light is off, this will set the colors instantly and then
        turn on the light with the specified duration, so the light fades to
        the target colors instead of flashing to its previous state.

        Args:
            colors: Optional colors. Can be:

                - None: uses brightness determination logic
                - Single HSBK: sets all downlight zones to same color
                - List[HSBK]: sets each zone individually (must match zone count)

                If provided, updates stored state.
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If any color.brightness == 0
            ValueError: If list length doesn't match downlight zone count
            LifxTimeoutError: Device did not respond
        """
        await self._turn_component_on("downlight", colors, duration)

    async def set_power(self, level: bool | int, duration: float = 0.0) -> None:
        """Set light power state, capturing component colors before turning off.

        Overrides Light.set_power() to capture the current uplight and downlight
        colors before turning off the entire light. This allows subsequent calls
        to turn_uplight_on() or turn_downlight_on() to restore the colors that
        were active just before the light was turned off.

        The captured colors preserve hue, saturation, and kelvin values even if
        a component was already off (brightness=0). The brightness will be
        determined at turn-on time using the standard brightness inference logic.

        Args:
            level: True/65535 to turn on, False/0 to turn off
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If integer value is not 0 or 65535
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Turn off entire ceiling light (captures colors for later)
            await ceiling.set_power(False)

            # Later, turn on just the uplight with its previous color
            await ceiling.turn_uplight_on()

            # Or turn on just the downlight with its previous colors
            await ceiling.turn_downlight_on()
            ```
        """
        await super().set_power(level, duration)

    async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
        """Set light color, updating component state tracking.

        Overrides Light.set_color() to track the color change in the ceiling
        light's component state. When set_color() is called, all zones (uplight
        and downlight) are set to the same color. This override ensures that
        the cached component colors stay in sync so that subsequent component
        control methods (like turn_uplight_on or turn_downlight_on) use the
        correct color values.

        Args:
            color: HSBK color to set for the entire light
            duration: Transition duration in seconds (default 0.0)

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            from lifx.color import HSBK

            # Set entire ceiling light to warm white
            await ceiling.set_color(
                HSBK(hue=0, saturation=0, brightness=1.0, kelvin=2700)
            )

            # Later component control will use this color
            await ceiling.turn_uplight_off()  # Uplight off
            await ceiling.turn_uplight_on()  # Restores to warm white
            ```
        """
        await super().set_color(color, duration)

    async def turn_downlight_off(
        self, colors: HSBK | list[HSBK] | None = None, duration: float = 0.0
    ) -> None:
        """Turn downlight component off.

        Args:
            colors: Optional colors to store for future turn_on. Can be:

                - None: stores current colors from device
                - Single HSBK: stores this color for all zones
                - List[HSBK]: stores individual colors (must match zone count)

                If provided, stores these colors (with brightness=0 on device).
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If any color.brightness == 0
            ValueError: If list length doesn't match downlight zone count
            LifxTimeoutError: Device did not respond

        Note:
            Sets all downlight zone brightness to 0 on device while preserving H, S, K.
            If the uplight component is already off, the entire device is
            powered off instead and the downlight zones keep their brightness,
            so a later set_power(True) brings the downlight back rather than
            turning on a light with every zone at zero brightness.
        """
        await self._turn_component_off("downlight", colors, duration)

    async def _determine_uplight_brightness(
        self, tile_colors: list[HSBK] | None = None
    ) -> HSBK:
        """Determine uplight brightness using priority logic.

        Priority order:
        1. Stored state (if available AND brightness > 0)
        2. Infer from downlight average brightness (using stored H, S, K if available)
        3. Hardcoded default (0.8)

        Args:
            tile_colors: Optional pre-fetched tile colors to avoid redundant fetch.
                If None, will fetch from device.

        Returns:
            HSBK color for uplight
        """
        return (await self._determine_component_brightness("uplight", tile_colors))[0]

    async def _determine_downlight_brightness(
        self, tile_colors: list[HSBK] | None = None
    ) -> list[HSBK]:
        """Determine downlight brightness using priority logic.

        Priority order:
        1. Stored state (if available AND any brightness > 0)
        2. Infer from uplight brightness
        3. Hardcoded default (0.8)

        Args:
            tile_colors: Optional pre-fetched tile colors to avoid redundant fetch.
                If None, will fetch from device.

        Returns:
            List of HSBK colors for downlight zones
        """
        return await self._determine_component_brightness("downlight", tile_colors)

    async def _load_state_from_file(self) -> None:
        """Load state from JSON file.

        The read runs in a worker thread via ``asyncio.to_thread`` so the file
        I/O never blocks the event loop; the parsed data is applied to state
        back on the loop. Handles a missing file, malformed contents and JSON
        errors gracefully.
        """
        if not self._state_file:
            return

        try:
            exists, data = await asyncio.to_thread(read_state_file, self._state_file)

            if not exists:
                _LOGGER.debug("State file does not exist: %s", self._state_file)
                return

            if not isinstance(data, dict):
                # A file that parses but is not an object (``null`` after a
                # truncated write, a bare list) is corruption, not absence
                _LOGGER.warning(
                    "State file %s does not contain a JSON object (found %s)",
                    self._state_file,
                    type(data).__name__,
                )
                return

            # Get state for this device
            device_state = data.get(self.serial)
            if not device_state:
                _LOGGER.debug("No state found for device %s", self.serial)
                return

            # Load uplight state
            state = self.state
            if "uplight" in device_state:
                state.stored_uplight_color = decode_color(device_state["uplight"])

            # Load downlight state (validate zone count if version is available)
            if "downlight" in device_state:
                loaded_colors = [decode_color(c) for c in device_state["downlight"]]
                try:
                    expected = self.downlight_zone_count
                except LifxError:
                    # Version not yet available — accept loaded data
                    state.stored_downlight_colors = loaded_colors
                else:
                    if len(loaded_colors) == expected:
                        state.stored_downlight_colors = loaded_colors
                    else:
                        _LOGGER.warning(
                            "Ignoring stored downlight state:"
                            " expected %d zones, got %d",
                            expected,
                            len(loaded_colors),
                        )

            _LOGGER.debug(
                "Loaded state from %s for device %s", self._state_file, self.serial
            )

        except Exception as e:
            _LOGGER.warning("Failed to load state from %s: %s", self._state_file, e)

    async def _save_state_to_file(self) -> None:
        """Save state to JSON file.

        The read-merge-write cycle runs in a worker thread via
        ``asyncio.to_thread`` so the file I/O never blocks the event loop. The
        thread holds the state file's lock for the whole cycle, so devices
        sharing a file within this process cannot drop each other's entries —
        and cancelling this coroutine cannot free the lock mid-write. Handles
        file I/O errors gracefully.
        """
        if not self._state_file:
            return

        try:
            # Build this device's entry; write_state_file merges it into any
            # existing on-disk entry
            device_state: dict[str, Any] = {}
            state = self.state

            if state.stored_uplight_color:
                device_state["uplight"] = encode_color(state.stored_uplight_color)

            if state.stored_downlight_colors:
                device_state["downlight"] = [
                    encode_color(c) for c in state.stored_downlight_colors
                ]

            await asyncio.to_thread(
                write_state_file, self._state_file, self.serial, device_state
            )

            _LOGGER.debug(
                "Saved state to %s for device %s", self._state_file, self.serial
            )

        except Exception as e:
            _LOGGER.warning("Failed to save state to %s: %s", self._state_file, e)
