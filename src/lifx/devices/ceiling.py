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
from typing import TYPE_CHECKING, Any, cast

from lifx.color import HSBK
from lifx.devices.matrix import MatrixLight, MatrixLightState
from lifx.exceptions import LifxError
from lifx.products import get_ceiling_layout, is_ceiling_product

if TYPE_CHECKING:
    pass

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

        # Get ceiling component colors
        uplight_color = await self.get_uplight_color()
        downlight_colors = await self.get_downlight_colors()

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

        # Get ceiling component colors
        uplight_color = await self.get_uplight_color()
        downlight_colors = await self.get_downlight_colors()

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
            downlight_colors = [colors] * len(range(*self.downlight_zones.indices(256)))
        else:
            if all(c.brightness == 0 for c in colors):
                raise ValueError(
                    "Cannot set downlight colors with brightness=0. "
                    "Use turn_downlight_off() instead."
                )

            expected_count = len(range(*self.downlight_zones.indices(256)))
            if len(colors) != expected_count:
                raise ValueError(
                    f"Expected {expected_count} colors for downlight, got {len(colors)}"
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
        if color is not None:
            if color.brightness == 0:
                raise ValueError("Cannot turn on uplight with brightness=0")
            await self.set_uplight_color(color, duration)
        else:
            # Determine color using priority logic
            determined_color = await self._determine_uplight_brightness()
            await self.set_uplight_color(determined_color, duration)

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
        if color is not None:
            if color.brightness == 0:
                raise ValueError(
                    "Provided color cannot have brightness=0. "
                    "Omit the parameter to use current color."
                )
            # Store the provided color
            self._stored_uplight_state = color
        else:
            # Get and store current color
            current_color = await self.get_uplight_color()
            self._stored_uplight_state = current_color

        # Create color with brightness=0 for device
        off_color = HSBK(
            hue=self._stored_uplight_state.hue,
            saturation=self._stored_uplight_state.saturation,
            brightness=0.0,
            kelvin=self._stored_uplight_state.kelvin,
        )

        # Get all colors and update uplight zone
        all_colors = await self.get_all_tile_colors()
        tile_colors = all_colors[0]
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
        if colors is not None:
            await self.set_downlight_colors(colors, duration)
        else:
            # Determine colors using priority logic
            determined_colors = await self._determine_downlight_brightness()
            await self.set_downlight_colors(determined_colors, duration)

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
        expected_count = len(range(*self.downlight_zones.indices(256)))

        if colors is not None:
            # Validate and normalize provided colors
            if isinstance(colors, HSBK):
                if colors.brightness == 0:
                    raise ValueError(
                        "Provided color cannot have brightness=0. "
                        "Omit the parameter to use current colors."
                    )
                colors_to_store = [colors] * expected_count
            else:
                if all(c.brightness == 0 for c in colors):
                    raise ValueError(
                        "Provided colors cannot have brightness=0. "
                        "Omit the parameter to use current colors."
                    )
                if len(colors) != expected_count:
                    raise ValueError(
                        f"Expected {expected_count} colors for downlight, "
                        f"got {len(colors)}"
                    )
                colors_to_store = colors

            self._stored_downlight_state = colors_to_store
        else:
            # Get and store current colors
            current_colors = await self.get_downlight_colors()
            self._stored_downlight_state = current_colors

        # Create colors with brightness=0 for device
        off_colors = [
            HSBK(
                hue=c.hue,
                saturation=c.saturation,
                brightness=0.0,
                kelvin=c.kelvin,
            )
            for c in self._stored_downlight_state
        ]

        # Get all colors and update downlight zones
        all_colors = await self.get_all_tile_colors()
        tile_colors = all_colors[0]
        tile_colors[self.downlight_zones] = off_colors
        await self.set_matrix_colors(0, tile_colors, duration=int(duration * 1000))

        # Update cache
        self._last_downlight_colors = off_colors

        # Persist if enabled
        if self._state_file:
            self._save_state_to_file()

    async def _determine_uplight_brightness(self) -> HSBK:
        """Determine uplight brightness using priority logic.

        Priority order:
        1. Stored state (if available)
        2. Infer from downlight average brightness
        3. Hardcoded default (0.8)

        Returns:
            HSBK color for uplight
        """
        # 1. Stored state
        if self._stored_uplight_state is not None:
            return self._stored_uplight_state

        # Get current uplight color for H, S, K
        current_uplight = await self.get_uplight_color()

        # 2. Infer from downlight average brightness
        try:
            downlight_colors = await self.get_downlight_colors()
            avg_brightness = sum(c.brightness for c in downlight_colors) / len(
                downlight_colors
            )

            # Only use inferred brightness if it's > 0
            # If all downlights are off (brightness=0), skip to default
            if avg_brightness > 0:
                return HSBK(
                    hue=current_uplight.hue,
                    saturation=current_uplight.saturation,
                    brightness=avg_brightness,
                    kelvin=current_uplight.kelvin,
                )
        except Exception:  # nosec B110
            # If inference fails, fall through to default
            pass

        # 3. Hardcoded default (0.8)
        return HSBK(
            hue=current_uplight.hue,
            saturation=current_uplight.saturation,
            brightness=0.8,
            kelvin=current_uplight.kelvin,
        )

    async def _determine_downlight_brightness(self) -> list[HSBK]:
        """Determine downlight brightness using priority logic.

        Priority order:
        1. Stored state (if available)
        2. Infer from uplight brightness
        3. Hardcoded default (0.8)

        Returns:
            List of HSBK colors for downlight zones
        """
        # 1. Stored state
        if self._stored_downlight_state is not None:
            return self._stored_downlight_state

        # Get current downlight colors for H, S, K
        current_downlight = await self.get_downlight_colors()

        # 2. Infer from uplight brightness
        try:
            uplight_color = await self.get_uplight_color()

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
                    for c in current_downlight
                ]
        except Exception:  # nosec B110
            # If inference fails, fall through to default
            pass

        # 3. Hardcoded default (0.8)
        return [
            HSBK(
                hue=c.hue,
                saturation=c.saturation,
                brightness=0.8,
                kelvin=c.kelvin,
            )
            for c in current_downlight
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
