"""LIFX Ceiling Light Device.

This module provides the CeilingLight class for controlling LIFX Ceiling lights with
independent uplight and downlight component control.

Terminology:
- Zone: Individual HSBK pixel in the matrix (indexed 0-63 or 0-127)
- Component: Logical grouping of zones:
  - Uplight Component: Single zone for ambient lighting (zone 63 or 127)
  - Downlight Component: Multiple zones for main illumination (zones 0-62 or 0-126)

Product IDs:
- 176: Ceiling (US) - 8x8 matrix
- 177: Ceiling (Intl) - 8x8 matrix
- 201: Ceiling Capsule (US) - 16x8 matrix
- 202: Ceiling Capsule (Intl) - 16x8 matrix
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from lifx.color import HSBK
from lifx.devices.matrix import MatrixLight, MatrixLightState
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
    """

    uplight_color: HSBK
    downlight_colors: list[HSBK]
    uplight_is_on: bool
    downlight_is_on: bool
    uplight_zone: int
    downlight_zones: slice

    @property
    def as_dict(self) -> Any:
        """Return CeilingLightState as dict."""
        return asdict(self)

    @classmethod
    def from_matrix_state(
        cls,
        matrix_state: MatrixLightState,
        uplight_color: HSBK,
        downlight_colors: list[HSBK],
        uplight_zone: int,
        downlight_zones: slice,
    ) -> CeilingLightState:
        """Create CeilingLightState from MatrixLightState.

        Args:
            matrix_state: Base MatrixLightState to extend
            uplight_color: Current uplight zone color
            downlight_colors: Current downlight zone colors
            uplight_zone: Zone index for uplight component
            downlight_zones: Slice representing downlight component zones

        Returns:
            CeilingLightState with all matrix state plus ceiling components
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
            location=matrix_state.location,
            group=matrix_state.group,
            color=matrix_state.color,
            chain=matrix_state.chain,
            tile_orientations=matrix_state.tile_orientations,
            tile_colors=matrix_state.tile_colors,
            tile_count=matrix_state.tile_count,
            effect=matrix_state.effect,
            uplight_color=uplight_color,
            downlight_colors=downlight_colors,
            uplight_is_on=uplight_color.brightness > 0,
            downlight_is_on=any(c.brightness > 0 for c in downlight_colors),
            uplight_zone=uplight_zone,
            downlight_zones=downlight_zones,
            last_updated=time.time(),
        )


class CeilingLight(MatrixLight):
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

        async with await CeilingLight.from_ip("192.168.1.100") as ceiling:
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

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = 56700,  # LIFX_UDP_PORT
        timeout: float = 0.5,  # DEFAULT_REQUEST_TIMEOUT
        max_retries: int = 3,  # DEFAULT_MAX_RETRIES
        state_file: str | None = None,
    ):
        """Initialize CeilingLight.

        Args:
            serial: Device serial number
            ip: Device IP address
            port: Device UDP port (default: 56700)
            timeout: Overall timeout for network requests in seconds
                (default: 0.5)
            max_retries: Maximum number of retry attempts for network requests
                (default: 3)
            state_file: Optional path to JSON file for state persistence

        Raises:
            LifxError: If device is not a supported Ceiling product
        """
        super().__init__(serial, ip, port, timeout, max_retries)
        self._state_file = state_file
        self._stored_uplight_state: HSBK | None = None
        self._stored_downlight_state: list[HSBK] | None = None
        self._last_uplight_color: HSBK | None = None
        self._last_downlight_colors: list[HSBK] | None = None

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
            self._load_state_from_file()

        return self

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

        # Cache for is_on properties
        self._last_uplight_color = uplight_color
        self._last_downlight_colors = downlight_colors

        # Create ceiling state from matrix state
        ceiling_state = CeilingLightState.from_matrix_state(
            matrix_state=matrix_state,
            uplight_color=uplight_color,
            downlight_colors=downlight_colors,
            uplight_zone=self.uplight_zone,
            downlight_zones=self.downlight_zones,
        )

        # Store in _state - cast is used in state property to access ceiling fields
        self._state = ceiling_state

        return ceiling_state

    async def refresh_state(self) -> None:
        """Refresh ceiling light state from hardware.

        Fetches color, tiles, tile colors, effect, and ceiling component state.

        Raises:
            RuntimeError: If state has not been initialized
            LifxTimeoutError: If device does not respond
            LifxDeviceNotFoundError: If device cannot be reached
        """
        await super().refresh_state()

        # Extract ceiling component colors from already-fetched tile_colors
        # (parent refresh_state already called get_all_tile_colors)
        tile_colors = self._state.tile_colors
        uplight_color = tile_colors[self.uplight_zone]
        downlight_colors = list(tile_colors[self.downlight_zones])

        # Cache for is_on properties
        self._last_uplight_color = uplight_color
        self._last_downlight_colors = downlight_colors

        # Update ceiling-specific state fields
        state = cast(CeilingLightState, self._state)
        state.uplight_color = uplight_color
        state.downlight_colors = downlight_colors
        state.uplight_is_on = bool(
            self.state.power > 0 and uplight_color.brightness > 0
        )
        state.downlight_is_on = bool(
            self.state.power > 0 and any(c.brightness > 0 for c in downlight_colors)
        )

    @classmethod
    async def from_ip(
        cls,
        ip: str,
        port: int = 56700,  # LIFX_UDP_PORT
        serial: str | None = None,
        timeout: float = 0.5,  # DEFAULT_REQUEST_TIMEOUT
        max_retries: int = 3,  # DEFAULT_MAX_RETRIES
        *,
        state_file: str | None = None,
    ) -> CeilingLight:
        """Create CeilingLight from IP address.

        Args:
            ip: Device IP address
            port: Port number (default LIFX_UDP_PORT)
            serial: Serial number as 12-digit hex string
            timeout: Request timeout for this device instance
            max_retries: Maximum number of retries for requests
            state_file: Optional path to JSON file for state persistence

        Returns:
            CeilingLight instance

        Raises:
            LifxDeviceNotFoundError: Device not found at IP
            LifxTimeoutError: Device did not respond
            LifxError: Device is not a supported Ceiling product
        """
        # Use parent class factory method
        device = await super().from_ip(ip, port, serial, timeout, max_retries)
        # Type cast to CeilingLight and set state_file
        ceiling = CeilingLight(device.serial, device.ip)
        ceiling._state_file = state_file
        ceiling.connection = device.connection
        return ceiling

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
            Requires recent data from device. Call get_uplight_color() or
            get_power() to refresh cached values before checking this property.

        Returns:
            True if uplight component is on, False otherwise
        """
        if self._state is None or self._state.power == 0:
            return False

        if self._last_uplight_color is None:
            return False

        return self._last_uplight_color.brightness > 0

    @property
    def downlight_is_on(self) -> bool:
        """True if downlight component is currently on.

        Calculated as: power_level > 0 AND NOT all downlight zones have brightness == 0

        Note:
            Requires recent data from device. Call get_downlight_colors() or
            get_power() to refresh cached values before checking this property.

        Returns:
            True if downlight component is on, False otherwise
        """
        if self._state is None or self._state.power == 0:
            return False

        if self._last_downlight_colors is None:
            return False

        # Downlight is on if any downlight zone has a brightness > 0
        return any(c.brightness > 0 for c in self._last_downlight_colors)

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

        # Cache for is_on property
        self._last_uplight_color = uplight_color

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

        # Cache for is_on property
        self._last_downlight_colors = downlight_colors

        return downlight_colors

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
        if color.brightness == 0:
            raise ValueError(
                "Cannot set uplight color with brightness=0. "
                "Use turn_uplight_off() instead."
            )

        # Get current colors for all zones
        all_colors = await self.get_all_tile_colors()
        tile_colors = all_colors[0]

        # Update uplight zone
        tile_colors[self.uplight_zone] = color

        # Set all colors back (duration in milliseconds for set_matrix_colors)
        await self.set_matrix_colors(0, tile_colors, duration=int(duration * 1000))

        # Store state
        self._stored_uplight_state = color
        self._last_uplight_color = color

        # Persist if enabled
        if self._state_file:
            self._save_state_to_file()

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
        # Validate and normalize colors
        if isinstance(colors, HSBK):
            if colors.brightness == 0:
                raise ValueError(
                    "Cannot set downlight color with brightness=0. "
                    "Use turn_downlight_off() instead."
                )
            downlight_colors = [colors] * self.downlight_zone_count
        else:
            if all(c.brightness == 0 for c in colors):
                raise ValueError(
                    "Cannot set downlight colors with brightness=0. "
                    "Use turn_downlight_off() instead."
                )

            if len(colors) != self.downlight_zone_count:
                raise ValueError(
                    f"Expected {self.downlight_zone_count} colors for downlight, "
                    f"got {len(colors)}"
                )
            downlight_colors = colors

        # Get current colors for all zones
        all_colors = await self.get_all_tile_colors()
        tile_colors = all_colors[0]

        # Update downlight zones
        tile_colors[self.downlight_zones] = downlight_colors

        # Set all colors back
        await self.set_matrix_colors(0, tile_colors, duration=int(duration * 1000))

        # Store state
        self._stored_downlight_state = downlight_colors
        self._last_downlight_colors = downlight_colors

        # Persist if enabled
        if self._state_file:
            self._save_state_to_file()

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
        # Validate provided color early
        if color is not None and color.brightness == 0:
            raise ValueError("Cannot turn on uplight with brightness=0")

        # Check if light is off first to determine which path to take
        if await self.get_power() == 0:
            # Light is off - single fetch for both determining color and modification
            all_colors = await self.get_all_tile_colors()
            tile_colors = all_colors[0]

            # Determine target color (pass pre-fetched colors to avoid extra fetch)
            if color is not None:
                target_color = color
            else:
                target_color = await self._determine_uplight_brightness(tile_colors)

            # Store current downlight colors BEFORE zeroing them out
            # This allows turn_downlight_on() to restore them later
            downlight_colors = tile_colors[self.downlight_zones]
            self._stored_downlight_state = list(downlight_colors)

            # Set uplight zone to target color
            tile_colors[self.uplight_zone] = target_color

            # Zero out downlight zones so they stay off when power turns on
            for i in range(*self.downlight_zones.indices(len(tile_colors))):
                tile_colors[i] = HSBK(
                    hue=tile_colors[i].hue,
                    saturation=tile_colors[i].saturation,
                    brightness=0.0,
                    kelvin=tile_colors[i].kelvin,
                )

            # Set all colors instantly (duration=0) while light is off
            await self.set_matrix_colors(0, tile_colors, duration=0)

            # Update stored state for uplight
            self._stored_uplight_state = target_color
            self._last_uplight_color = target_color

            # Turn on with the requested duration - light fades on to target color
            await super().set_power(True, duration)

            # Persist AFTER device operations complete
            if self._state_file:
                self._save_state_to_file()
        else:
            # Light is already on - determine target color first, then set
            if color is not None:
                target_color = color
            else:
                target_color = await self._determine_uplight_brightness()

            # set_uplight_color will fetch and modify (single fetch in that method)
            await self.set_uplight_color(target_color, duration)

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
        """
        if color is not None and color.brightness == 0:
            raise ValueError(
                "Provided color cannot have brightness=0. "
                "Omit the parameter to use current color."
            )

        # Fetch current state once and reuse to calculate brightness
        all_colors = await self.get_all_tile_colors()
        tile_colors = all_colors[0]

        # Determine which color to store
        if color is not None:
            stored_color = color
        else:
            stored_color = tile_colors[self.uplight_zone]
            self._last_uplight_color = stored_color

        # Store for future restoration
        self._stored_uplight_state = stored_color

        # Create color with brightness=0 for device
        off_color = HSBK(
            hue=stored_color.hue,
            saturation=stored_color.saturation,
            brightness=0.0,
            kelvin=stored_color.kelvin,
        )

        # Update uplight zone and send immediately
        tile_colors[self.uplight_zone] = off_color
        await self.set_matrix_colors(0, tile_colors, duration=int(duration * 1000))

        # Update cache
        self._last_uplight_color = off_color

        # Persist if enabled
        if self._state_file:
            self._save_state_to_file()

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
        # Validate provided colors early
        if colors is not None:
            if isinstance(colors, HSBK):
                if colors.brightness == 0:
                    raise ValueError("Cannot turn on downlight with brightness=0")
            else:
                if all(c.brightness == 0 for c in colors):
                    raise ValueError("Cannot turn on downlight with brightness=0")
                if len(colors) != self.downlight_zone_count:
                    raise ValueError(
                        f"Expected {self.downlight_zone_count} colors for downlight, "
                        f"got {len(colors)}"
                    )

        # Check if light is off first to determine which path to take
        if await self.get_power() == 0:
            # Light is off - single fetch for both determining colors and modification
            all_colors = await self.get_all_tile_colors()
            tile_colors = all_colors[0]

            # Determine target colors (pass pre-fetched colors to avoid extra fetch)
            if colors is not None:
                if isinstance(colors, HSBK):
                    target_colors = [colors] * self.downlight_zone_count
                else:
                    target_colors = list(colors)
            else:
                target_colors = await self._determine_downlight_brightness(tile_colors)

            # Store current uplight color BEFORE zeroing it out
            # This allows turn_uplight_on() to restore it later
            self._stored_uplight_state = tile_colors[self.uplight_zone]

            # Set downlight zones to target colors
            tile_colors[self.downlight_zones] = target_colors

            # Zero out uplight zone so it stays off when power turns on
            uplight_color = tile_colors[self.uplight_zone]
            tile_colors[self.uplight_zone] = HSBK(
                hue=uplight_color.hue,
                saturation=uplight_color.saturation,
                brightness=0.0,
                kelvin=uplight_color.kelvin,
            )

            # Set all colors instantly (duration=0) while light is off
            await self.set_matrix_colors(0, tile_colors, duration=0)

            # Update stored state for downlight
            self._stored_downlight_state = target_colors
            self._last_downlight_colors = target_colors

            # Turn on with the requested duration - light fades on to target colors
            await super().set_power(True, duration)

            # Persist AFTER device operations complete
            if self._state_file:
                self._save_state_to_file()
        else:
            # Light is already on - determine target colors first, then set
            if colors is not None:
                if isinstance(colors, HSBK):
                    target_colors = [colors] * self.downlight_zone_count
                else:
                    target_colors = list(colors)
            else:
                target_colors = await self._determine_downlight_brightness()

            # set_downlight_colors will fetch and modify (single fetch in that method)
            await self.set_downlight_colors(target_colors, duration)

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
        # Determine if we're turning off
        if isinstance(level, bool):
            turning_off = not level
        elif isinstance(level, int):
            if level not in (0, 65535):
                raise ValueError(f"Power level must be 0 or 65535, got {level}")
            turning_off = level == 0
        else:
            raise TypeError(f"Expected bool or int, got {type(level).__name__}")

        # If turning off, capture current colors for both components with single fetch
        if turning_off:
            # Single fetch to capture both uplight and downlight colors
            all_colors = await self.get_all_tile_colors()
            tile_colors = all_colors[0]

            # Extract and store both component colors
            self._stored_uplight_state = tile_colors[self.uplight_zone]
            self._stored_downlight_state = list(tile_colors[self.downlight_zones])

            # Also update cache for is_on properties
            self._last_uplight_color = self._stored_uplight_state
            self._last_downlight_colors = self._stored_downlight_state

        # Call parent to perform actual power change
        await super().set_power(level, duration)

        # Persist AFTER device operation completes
        if turning_off and self._state_file:
            self._save_state_to_file()

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
        # Call parent to perform actual color change
        await super().set_color(color, duration)

        # Update cached component colors - all zones now have the same color
        self._last_uplight_color = color
        self._last_downlight_colors = [color] * self.downlight_zone_count

        # Also update stored state for restoration
        self._stored_uplight_state = color
        self._stored_downlight_state = [color] * self.downlight_zone_count

        # Persist if enabled
        if self._state_file:
            self._save_state_to_file()

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
        """
        # Validate provided colors early (before fetching)
        stored_colors: list[HSBK] | None = None
        if colors is not None:
            if isinstance(colors, HSBK):
                if colors.brightness == 0:
                    raise ValueError(
                        "Provided color cannot have brightness=0. "
                        "Omit the parameter to use current colors."
                    )
                stored_colors = [colors] * self.downlight_zone_count
            else:
                if all(c.brightness == 0 for c in colors):
                    raise ValueError(
                        "Provided colors cannot have brightness=0. "
                        "Omit the parameter to use current colors."
                    )
                if len(colors) != self.downlight_zone_count:
                    raise ValueError(
                        f"Expected {self.downlight_zone_count} colors for downlight, "
                        f"got {len(colors)}"
                    )
                stored_colors = list(colors)

        # Fetch current state once and reuse to calculate brightness
        all_colors = await self.get_all_tile_colors()
        tile_colors = all_colors[0]

        # If colors not provided, extract from fetched data
        if stored_colors is None:
            stored_colors = list(tile_colors[self.downlight_zones])
            self._last_downlight_colors = stored_colors

        # Store for future restoration
        self._stored_downlight_state = stored_colors

        # Create colors with brightness=0 for device
        off_colors = [
            HSBK(
                hue=c.hue,
                saturation=c.saturation,
                brightness=0.0,
                kelvin=c.kelvin,
            )
            for c in stored_colors
        ]

        # Update downlight zones and send immediately
        tile_colors[self.downlight_zones] = off_colors
        await self.set_matrix_colors(0, tile_colors, duration=int(duration * 1000))

        # Update cache
        self._last_downlight_colors = off_colors

        # Persist if enabled
        if self._state_file:
            self._save_state_to_file()

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
        # 1. Stored state (only if brightness > 0)
        if (
            self._stored_uplight_state is not None
            and self._stored_uplight_state.brightness > 0
        ):
            return self._stored_uplight_state

        # Get current colors (use pre-fetched if available)
        if tile_colors is None:
            all_colors = await self.get_all_tile_colors()
            tile_colors = all_colors[0]

        current_uplight = tile_colors[self.uplight_zone]
        downlight_colors = tile_colors[self.downlight_zones]

        # Cache for is_on properties
        self._last_uplight_color = current_uplight
        self._last_downlight_colors = list(downlight_colors)

        # Determine which color source to use for H, S, K
        source_color = self._stored_uplight_state or current_uplight

        # 2. Infer from downlight average brightness
        avg_brightness = sum(c.brightness for c in downlight_colors) / len(
            downlight_colors
        )

        # Only use inferred brightness if it's > 0
        # If all downlights are off (brightness=0), skip to default
        if avg_brightness > 0:
            return HSBK(
                hue=source_color.hue,
                saturation=source_color.saturation,
                brightness=avg_brightness,
                kelvin=source_color.kelvin,
            )

        # 3. Hardcoded default (0.8)
        return HSBK(
            hue=source_color.hue,
            saturation=source_color.saturation,
            brightness=0.8,
            kelvin=source_color.kelvin,
        )

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
        # 1. Stored state (only if any color has brightness > 0)
        if self._stored_downlight_state is not None:
            if any(c.brightness > 0 for c in self._stored_downlight_state):
                return self._stored_downlight_state

        # Get current colors (use pre-fetched if available)
        if tile_colors is None:
            all_colors = await self.get_all_tile_colors()
            tile_colors = all_colors[0]

        current_downlight = list(tile_colors[self.downlight_zones])
        uplight_color = tile_colors[self.uplight_zone]

        # Cache for is_on properties
        self._last_downlight_colors = current_downlight
        self._last_uplight_color = uplight_color

        # Prefer stored H, S, K if available, otherwise use current
        source_colors: list[HSBK] = (
            self._stored_downlight_state
            if self._stored_downlight_state is not None
            else current_downlight
        )

        # 2. Infer from uplight brightness
        # Only use inferred brightness if it's > 0
        # If uplight is off (brightness=0), skip to default
        if uplight_color.brightness > 0:
            return [
                HSBK(
                    hue=c.hue,
                    saturation=c.saturation,
                    brightness=uplight_color.brightness,
                    kelvin=c.kelvin,
                )
                for c in source_colors
            ]

        # 3. Hardcoded default (0.8)
        return [
            HSBK(
                hue=c.hue,
                saturation=c.saturation,
                brightness=0.8,
                kelvin=c.kelvin,
            )
            for c in source_colors
        ]

    def _is_stored_state_valid(
        self, component: str, current: HSBK | list[HSBK]
    ) -> bool:
        """Check if stored state matches current (ignoring brightness).

        Args:
            component: Either "uplight" or "downlight"
            current: Current color(s) from device

        Returns:
            True if stored state matches current (H, S, K), False otherwise
        """
        if component == "uplight":
            if self._stored_uplight_state is None or not isinstance(current, HSBK):
                return False

            stored = self._stored_uplight_state
            return (
                stored.hue == current.hue
                and stored.saturation == current.saturation
                and stored.kelvin == current.kelvin
            )

        if component == "downlight":
            if self._stored_downlight_state is None or not isinstance(current, list):
                return False

            if len(self._stored_downlight_state) != len(current):
                return False

            # Check if all zones match (H, S, K)
            return all(
                s.hue == c.hue and s.saturation == c.saturation and s.kelvin == c.kelvin
                for s, c in zip(self._stored_downlight_state, current)
            )

        return False

    def _load_state_from_file(self) -> None:
        """Load state from JSON file.

        Handles file not found and JSON errors gracefully.
        """
        if not self._state_file:
            return

        try:
            state_path = Path(self._state_file).expanduser()
            if not state_path.exists():
                _LOGGER.debug("State file does not exist: %s", state_path)
                return

            with state_path.open("r") as f:
                data = json.load(f)

            # Get state for this device
            device_state = data.get(self.serial)
            if not device_state:
                _LOGGER.debug("No state found for device %s", self.serial)
                return

            # Load uplight state
            if "uplight" in device_state:
                uplight_data = device_state["uplight"]
                self._stored_uplight_state = HSBK(
                    hue=uplight_data["hue"],
                    saturation=uplight_data["saturation"],
                    brightness=uplight_data["brightness"],
                    kelvin=uplight_data["kelvin"],
                )

            # Load downlight state
            if "downlight" in device_state:
                downlight_data = device_state["downlight"]
                self._stored_downlight_state = [
                    HSBK(
                        hue=c["hue"],
                        saturation=c["saturation"],
                        brightness=c["brightness"],
                        kelvin=c["kelvin"],
                    )
                    for c in downlight_data
                ]

            _LOGGER.debug("Loaded state from %s for device %s", state_path, self.serial)

        except Exception as e:
            _LOGGER.warning("Failed to load state from %s: %s", self._state_file, e)

    def _save_state_to_file(self) -> None:
        """Save state to JSON file.

        Handles file I/O errors gracefully.
        """
        if not self._state_file:
            return

        try:
            state_path = Path(self._state_file).expanduser()

            # Load existing data or create new
            if state_path.exists():
                with state_path.open("r") as f:
                    data = json.load(f)
            else:
                data = {}

            # Update state for this device
            device_state = {}

            if self._stored_uplight_state:
                device_state["uplight"] = {
                    "hue": self._stored_uplight_state.hue,
                    "saturation": self._stored_uplight_state.saturation,
                    "brightness": self._stored_uplight_state.brightness,
                    "kelvin": self._stored_uplight_state.kelvin,
                }

            if self._stored_downlight_state:
                device_state["downlight"] = [
                    {
                        "hue": c.hue,
                        "saturation": c.saturation,
                        "brightness": c.brightness,
                        "kelvin": c.kelvin,
                    }
                    for c in self._stored_downlight_state
                ]

            data[self.serial] = device_state

            # Ensure directory exists
            state_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to file
            with state_path.open("w") as f:
                json.dump(data, f, indent=2)

            _LOGGER.debug("Saved state to %s for device %s", state_path, self.serial)

        except Exception as e:
            _LOGGER.warning("Failed to save state to %s: %s", self._state_file, e)
