"""LIFX Matrix Light Device.

This module provides the MatrixLight class for controlling LIFX devices with matrix
(tile) capabilities. MatrixLight devices have 2D arrays of controllable color zones
arranged in tiles.

Terminology:
- MatrixLight: A light device with matrix capability (has_matrix)
- Tile: A 2D matrix of controllable color zones on the device chain
- Device Chain: Collection of tiles (up to 5 if has_chain capability)
- Common case: Single tile, no chain capability (LIFX Candle, LIFX Path)
- Rare case: Multi-tile chain (discontinued LIFX Tile product only)
"""

from __future__ import annotations

import logging
import time
from dataclasses import InitVar, asdict, dataclass
from typing import TYPE_CHECKING, Any

from lifx.animation.orientation import Orientation, build_orientation_lut
from lifx.color import HSBK
from lifx.const import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    LIFX_UDP_PORT,
    MAX_PALETTE_COLORS,
)
from lifx.devices.light import Light, LightState
from lifx.exceptions import LifxTimeoutError, LifxUnsupportedCommandError
from lifx.products import SKY_EFFECT_MIN_FIRMWARE_MAJOR
from lifx.products import supports_sky_effect as firmware_supports_sky_effect
from lifx.protocol import packets
from lifx.protocol.protocol_types import (
    FirmwareEffect,
    LightHsbk,
    TileBufferRect,
    TileEffectParameter,
    TileEffectSettings,
    TileEffectSkyType,
)
from lifx.protocol.protocol_types import (
    TileStateDevice as LifxProtocolTileDevice,
)

if TYPE_CHECKING:
    from lifx.theme import Theme


_LOGGER = logging.getLogger(__name__)


@dataclass
class TileInfo:
    """Information about a single tile in the device chain.

    Attributes:
        tile_index: Index of this tile in the chain (0-based)
        accel_meas_x: Accelerometer measurement X
        accel_meas_y: Accelerometer measurement Y
        accel_meas_z: Accelerometer measurement Z
        user_x: User-defined X position
        user_y: User-defined Y position
        width: Tile width in zones
        height: Tile height in zones
        supported_frame_buffers: frame buffer count
        device_version_vendor: Device vendor ID
        device_version_product: Device product ID
        device_version_version: Device version
        firmware_build: Firmware build timestamp
        firmware_version_minor: Firmware minor version
        firmware_version_major: Firmware major version
    """

    tile_index: int
    accel_meas_x: int
    accel_meas_y: int
    accel_meas_z: int
    user_x: float
    user_y: float
    width: int
    height: int
    supported_frame_buffers: int
    device_version_vendor: int
    device_version_product: int
    device_version_version: int
    firmware_build: int
    firmware_version_minor: int
    firmware_version_major: int

    @classmethod
    def from_protocol(
        cls, tile_index: int, protocol_tile: LifxProtocolTileDevice
    ) -> TileInfo:
        """Create TileInfo from protocol TileStateDevice.

        Args:
            tile_index: Index of this tile in the chain (0-based)
            protocol_tile: Protocol TileStateDevice object

        Returns:
            TileInfo instance
        """
        return cls(
            tile_index=tile_index,
            accel_meas_x=protocol_tile.accel_meas.x,
            accel_meas_y=protocol_tile.accel_meas.y,
            accel_meas_z=protocol_tile.accel_meas.z,
            user_x=protocol_tile.user_x,
            user_y=protocol_tile.user_y,
            width=protocol_tile.width,
            height=protocol_tile.height,
            supported_frame_buffers=protocol_tile.supported_frame_buffers,
            device_version_vendor=protocol_tile.device_version.vendor,
            device_version_product=protocol_tile.device_version.product,
            device_version_version=0,  # Not available in TileStateDevice
            firmware_build=protocol_tile.firmware.build,
            firmware_version_minor=protocol_tile.firmware.version_minor,
            firmware_version_major=protocol_tile.firmware.version_major,
        )

    @property
    def as_dict(self) -> Any:
        """Return TileInfo as dictionary."""
        return asdict(self)

    @property
    def total_zones(self) -> int:
        """Get total number of zones on this tile."""
        return self.width * self.height

    @property
    def requires_frame_buffer(self) -> bool:
        """Check if tile has more than 64 zones (requires frame buffer strategy)."""
        return self.total_zones > 64

    @property
    def nearest_orientation(self) -> str:
        """Determine the orientation of the tile from accelerometer data."""
        abs_x = abs(self.accel_meas_x)
        abs_y = abs(self.accel_meas_y)
        abs_z = abs(self.accel_meas_z)

        if (
            self.accel_meas_x == -1
            and self.accel_meas_y == -1
            and self.accel_meas_z == -1
        ):
            # Invalid data, assume right-side up.
            return "Upright"

        elif abs_x > abs_y and abs_x > abs_z:
            if self.accel_meas_x > 0:
                return "RotatedRight"
            else:
                return "RotatedLeft"

        elif abs_z > abs_x and abs_z > abs_y:
            if self.accel_meas_z > 0:
                return "FaceDown"
            else:
                return "FaceUp"

        else:
            if self.accel_meas_y > 0:
                return "UpsideDown"
            else:
                return "Upright"


@dataclass
class MatrixEffect:
    """Matrix effect configuration.

    Attributes:
        effect_type: Type of effect (OFF, MORPH, FLAME, SKY)
        speed: Effect speed in milliseconds
        duration: Total effect duration in nanoseconds (0 for infinite)
        palette: Color palette for the effect (max 16 colors)
        sky_type: Sky effect type (SUNRISE, SUNSET, CLOUDS)
        cloud_saturation_min: Minimum cloud saturation (0-255, for CLOUDS sky type)
        cloud_saturation_max: Maximum cloud saturation (0-255, for CLOUDS sky type)
        from_device: Set when building this object from a device response. The
            validation and default-filling below are rules for values the
            caller is about to send: applying them to values the firmware
            reported would reject legitimate device state, or silently rewrite
            it to something the device never reported.
    """

    effect_type: FirmwareEffect
    speed: int
    duration: int = 0
    palette: list[HSBK] | None = None
    sky_type: TileEffectSkyType = TileEffectSkyType.SUNRISE
    cloud_saturation_min: int = 0
    cloud_saturation_max: int = 0
    from_device: InitVar[bool] = False

    def __post_init__(self, from_device: bool) -> None:
        """Initialize defaults and validate fields."""
        if from_device:
            return

        # Validate all fields
        # Speed can be 0 only when effect is OFF
        if self.effect_type != FirmwareEffect.OFF:
            self._validate_speed_active(self.speed)
        elif self.speed < 0:
            raise ValueError(f"Effect speed must be non-negative, got {self.speed}")

        self._validate_duration(self.duration)

        # Only validate palette if provided
        if self.palette is not None:
            self._validate_palette(self.palette)

        self._validate_saturation(self.cloud_saturation_min, "cloud_saturation_min")
        self._validate_saturation(self.cloud_saturation_max, "cloud_saturation_max")

        # Apply cloud saturation defaults only for CLOUDS sky type
        if (
            self.effect_type == FirmwareEffect.SKY
            and self.sky_type == TileEffectSkyType.CLOUDS
        ):
            # Apply sensible defaults for cloud saturation if not specified
            if self.cloud_saturation_max == 0:
                self.cloud_saturation_max = 180
            if self.cloud_saturation_min == 0:
                self.cloud_saturation_min = 50

    @staticmethod
    def _validate_speed_active(value: int) -> None:
        """Validate effect speed for active effects (non-OFF).

        Args:
            value: Speed value in milliseconds

        Raises:
            ValueError: If speed is not positive
        """
        if value <= 0:
            raise ValueError(
                f"Effect speed must be positive for active effects, got {value}"
            )

    @staticmethod
    def _validate_duration(value: int) -> None:
        """Validate effect duration is non-negative.

        Args:
            value: Duration value in nanoseconds (0 for infinite)

        Raises:
            ValueError: If duration is negative
        """
        if value < 0:
            raise ValueError(f"Effect duration must be non-negative, got {value}")

    @staticmethod
    def _validate_palette(value: list[HSBK]) -> None:
        """Validate color palette.

        Args:
            value: List of HSBK colors (max 16)

        Raises:
            ValueError: If palette is invalid
        """
        if not value:
            raise ValueError("Effect palette must contain at least one color")
        if len(value) > MAX_PALETTE_COLORS:
            raise ValueError(
                f"Effect palette can contain at most {MAX_PALETTE_COLORS} colors, "
                f"got {len(value)}"
            )

    @staticmethod
    def _validate_saturation(value: int, name: str) -> None:
        """Validate saturation value is in range 0-255.

        Args:
            value: Saturation value to validate
            name: Name of the field (for error messages)

        Raises:
            ValueError: If saturation is out of range
        """
        if not (0 <= value <= 255):
            raise ValueError(f"{name} must be in range 0-255, got {value}")


@dataclass
class MatrixLightState(LightState):
    """Matrix light device state with tile-based control.

    Attributes:
        tiles: List of tile information for each tile in the chain
        tile_colors: List of HSBK colors for all pixels across all tiles
        tile_count: Total number of tiles in chain
        effect: Current matrix effect configuration
    """

    chain: list[TileInfo]
    tile_orientations: dict[int, str]
    tile_colors: list[HSBK]
    tile_count: int
    effect: FirmwareEffect

    @property
    def as_dict(self) -> Any:
        """Return MatrixLightState as dict.

        ``tile_orientations`` is keyed by tile index. JSON object keys are
        always strings, so the keys are stringified here rather than letting
        ``json.dumps`` coerce them and break lookups after a round trip.
        """
        state = super().as_dict
        state["chain"] = [tile.as_dict for tile in self.chain]
        state["tile_orientations"] = {
            str(index): orientation
            for index, orientation in self.tile_orientations.items()
        }
        state["tile_colors"] = [color.as_dict for color in self.tile_colors]
        state["tile_count"] = self.tile_count
        state["effect"] = self.effect
        return state

    @classmethod
    def from_light_state(
        cls,
        light_state: LightState,
        chain: list[TileInfo],
        tile_orientations: dict[int, str],
        tile_colors: list[HSBK],
        effect: FirmwareEffect,
    ) -> MatrixLightState:
        """Create MatrixLightState from LightState."""
        return cls(
            model=light_state.model,
            label=light_state.label,
            serial=light_state.serial,
            mac_address=light_state.mac_address,
            power=light_state.power,
            capabilities=light_state.capabilities,
            host_firmware=light_state.host_firmware,
            wifi_firmware=light_state.wifi_firmware,
            wifi_info=light_state.wifi_info,
            location=light_state.location,
            group=light_state.group,
            color=light_state.color,
            ambient_light=light_state.ambient_light,
            chain=chain,
            tile_orientations=tile_orientations,
            tile_colors=tile_colors,
            tile_count=len(chain),
            effect=effect,
            last_updated=time.time(),
        )


class MatrixLight(Light):
    """LIFX Matrix Light Device.

    MatrixLight devices have 2D arrays of controllable color zones arranged in tiles.
    Most MatrixLight devices (LIFX Candle, LIFX Path) have a single tile. The
    discontinued LIFX Tile product supported up to 5 tiles in a chain (has_chain).

    Zone Addressing:

    - Colors are applied row-by-row starting at top-left (0,0)
    - For tiles ≤64 zones: Single set64() call to frame buffer 0
    - For tiles >64 zones (e.g., 16x8 = 128 zones):

      1. First set64(): rect=(0,0), 64 colors, frame buffer 1
      2. Second set64(): rect=(0,4), 64 colors, frame buffer 1
      3. copy_frame_buffer(): Copy buffer 1 → buffer 0

    Example:
        >>> async with await Device.connect("192.168.1.100") as matrix:
        ...     assert isinstance(matrix, MatrixLight)
        ...     # Get device chain info
        ...     chain = await matrix.get_device_chain()
        ...     print(f"Device has {len(chain)} tile(s)")
        ...
        ...     # Set colors on first tile (8x8 = 64 zones)
        ...     colors = [HSBK.from_rgb(1.0, 0.0, 0.0)] * 64
        ...     await matrix.set64(tile_index=0, colors=colors, width=8)
    """

    _state: MatrixLightState

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = LIFX_UDP_PORT,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        *,
        fetch_wifi_info: bool = False,
        fetch_ambient_light: bool = False,
    ) -> None:
        """Initialize MatrixLight device.

        See :class:`~lifx.devices.base.Device` for parameter documentation. The
        signature is spelled out rather than forwarded as ``*args, **kwargs`` so
        callers get the same type checking the base class offers.
        """
        super().__init__(
            serial,
            ip,
            port,
            timeout,
            max_retries,
            fetch_wifi_info=fetch_wifi_info,
            fetch_ambient_light=fetch_ambient_light,
        )
        # Matrix specific properties
        self._device_chain: list[TileInfo] | None = None
        self._tile_effect: MatrixEffect | None = None

    @property
    def state(self) -> MatrixLightState:
        """Get matrix light state (guaranteed when using Device.connect()).

        Returns:
            MatrixLightState with current matrix light state

        Raises:
            RuntimeError: If accessed before state initialization
        """
        if self._state is None:
            raise RuntimeError("State not found.")
        return self._state

    async def get_device_chain(self) -> list[TileInfo]:
        """Get device chain details (list of Tile objects).

        This method fetches the device chain information and caches it.

        Returns:
            List of TileInfo objects describing each tile in the chain

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            >>> chain = await matrix.get_device_chain()
            >>> for tile in chain:
            ...     print(f"Tile {tile.tile_index}: {tile.width}x{tile.height}")
        """
        _LOGGER.debug("Getting device chain for %s", self.label or self.serial)

        response: packets.Tile.StateDeviceChain = await self.connection.request(
            packets.Tile.GetDeviceChain()
        )
        self._raise_if_unhandled(response)

        # Parse tiles from response
        tiles = []
        for i, protocol_tile in enumerate(response.tile_devices):
            # Stop at first zero-width tile (indicates end of chain)
            if protocol_tile.width == 0:
                break
            tiles.append(TileInfo.from_protocol(i, protocol_tile))

        self._device_chain = tiles

        # Update state if it exists
        if self._state is not None and hasattr(self._state, "chain"):
            self._state.chain = tiles
            self._state.tile_count = len(tiles)
            self._state.last_updated = time.time()

        _LOGGER.debug("Device chain has %d tile(s)", len(tiles))
        return tiles

    async def set_user_position(
        self, tile_index: int, user_x: float, user_y: float
    ) -> None:
        """Position tiles in the chain (only for devices with has_chain capability).

        Positions are in tile-position units, **not pixels**: 1.0 is always 8
        pixels, regardless of this tile's own width or height. ``user_x`` grows
        to the right and ``user_y`` grows **upwards**. To move a tile a given
        number of pixels, divide by 8 — moving one 8x8 tile's width to the right
        is ``user_x += 1.0``, and a 5x6 Candle's width is ``user_x += 5 / 8``.

        Args:
            tile_index: Index of the tile to position (0-based)
            user_x: Horizontal position in tile-position units (1.0 = 8 pixels,
                growing right)
            user_y: Vertical position in tile-position units (1.0 = 8 pixels,
                growing up)

        Note:
            Only applicable for multi-tile devices (has_chain capability).
            Most MatrixLight devices have a single tile and don't need positioning.

        Example:
            >>> # Place the second tile one 8-pixel tile-width to the right
            >>> await matrix.set_user_position(tile_index=1, user_x=1.0, user_y=0.0)
        """
        _LOGGER.debug(
            "Setting tile %d position to (%f, %f) for %s",
            tile_index,
            user_x,
            user_y,
            self.label or self.serial,
        )

        await self.connection.send_packet(
            packets.Tile.SetUserPosition(
                tile_index=tile_index,
                user_x=user_x,
                user_y=user_y,
            )
        )

    async def get64(
        self,
        tile_index: int = 0,
        length: int = 1,
        x: int = 0,
        y: int = 0,
        width: int | None = None,
    ) -> list[HSBK]:
        """Get up to 64 zones of color state from a tile.

        For devices with ≤64 zones, returns all zones. For devices with >64 zones,
        returns up to 64 zones due to protocol limitations.

        Args:
            tile_index: Index of the tile (0-based). Defaults to 0.
            length: Number of tiles to query (usually 1). Defaults to 1.
            x: X coordinate of the rectangle (0-based). Defaults to 0.
            y: Y coordinate of the rectangle (0-based). Defaults to 0.
            width: Width of the rectangle in zones. Defaults to tile width.

        Returns:
            List of HSBK colors for the requested zones. For tiles with ≤64 zones,
            returns the actual zone count (e.g., 64 for 8x8, 16 for 4x4). For tiles
            with >64 zones (e.g., 128 for 16x8 Ceiling), returns 64 (protocol limit).

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            >>> # Get all colors from first tile (no parameters needed)
            >>> colors = await matrix.get64()
            >>>
            >>> # Get colors from specific region
            >>> colors = await matrix.get64(y=4)  # Start at row 4
        """
        # Validate parameters
        if x < 0:
            raise ValueError(f"x coordinate must be non-negative, got {x}")
        if y < 0:
            raise ValueError(f"y coordinate must be non-negative, got {y}")
        if width is not None and width <= 0:
            raise ValueError(f"width must be positive, got {width}")

        if self._device_chain is None:
            device_chain = await self.get_device_chain()
        else:
            device_chain = self._device_chain

        if width is None:
            width = device_chain[0].width

        _LOGGER.debug(
            "Getting 64 zones from tile %d (x=%d, y=%d, width=%d) for %s",
            tile_index,
            x,
            y,
            width,
            self.label or self.serial,
        )

        response: packets.Tile.State64 = await self.connection.request(
            packets.Tile.Get64(
                tile_index=tile_index,
                length=length,
                rect=TileBufferRect(fb_index=0, x=x, y=y, width=width),
            )
        )
        self._raise_if_unhandled(response)

        max_colors = device_chain[0].width * device_chain[0].height

        # Convert protocol colors to HSBK
        result = [
            HSBK.from_protocol(proto_color)
            for proto_color in response.colors[:max_colors]
        ]

        # Update state if it exists and we fetched all colors from tile 0
        if self._state is not None and hasattr(self._state, "tile_colors"):
            if tile_index == 0 and x == 0 and y == 0 and len(result) == max_colors:
                self._state.tile_colors = result
                self._state.last_updated = time.time()

        return result

    async def get_all_tile_colors(self) -> list[list[HSBK]]:
        """Get colors for all tiles in the chain.

        Fetches colors from each tile in the device chain and returns them
        as a list of color lists (one per tile). This is the matrix equivalent
        of MultiZoneLight's get_all_color_zones().

        A chain of uniform tiles of 64 zones or fewer is read with a single
        Get64 carrying ``length`` equal to the chain length, which the device
        answers with one State64 per tile — one round trip instead of one per
        tile. Everything else (single-tile devices, and tiles over 64 zones such
        as a 16x8 Ceiling) is queried a tile at a time, sequentially, to avoid
        overwhelming the device with concurrent requests.

        Always fetches from device.

        Returns:
            List of color lists, one per tile. Each inner list contains
            all colors for that tile (64 for 8x8 tiles, 128 for 16x8 Ceiling).

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Get colors for all tiles
            all_colors = await matrix.get_all_tile_colors()
            print(f"Device has {len(all_colors)} tiles")
            for i, tile_colors in enumerate(all_colors):
                print(f"Tile {i}: {len(tile_colors)} colors")

            # Flatten to single list if needed
            flat_colors = [c for tile in all_colors for c in tile]
            ```
        """
        # Get device chain (use cached if available)
        if self._device_chain is None:
            device_chain = await self.get_device_chain()
        else:
            device_chain = self._device_chain

        if self._can_batch_chain_fetch(device_chain):
            all_colors = await self._get_chain_colors_batched(device_chain)
        else:
            all_colors = await self._get_chain_colors_per_tile(device_chain)

        # Update state if it exists (flatten for state storage)
        if self._state is not None and hasattr(self._state, "tile_colors"):
            flat_colors = [c for tile_colors in all_colors for c in tile_colors]
            self._state.tile_colors = flat_colors
            self._state.last_updated = time.time()

        return all_colors

    @staticmethod
    def _can_batch_chain_fetch(device_chain: list[TileInfo]) -> bool:
        """Return whether the whole chain can be read with one Get64.

        Get64 carries a ``length`` field: one request starting at tile 0 makes
        the device answer with one State64 per tile, saving a round trip per
        tile on a chain. That only works when a single 64-colour response
        covers a whole tile and one rect describes every tile, so it is limited
        to multi-tile chains of uniform tiles of 64 zones or fewer. In practice
        that is the LIFX Tile, the only chain-capable product.

        Args:
            device_chain: Tiles reported by the device

        Returns:
            True if the batched path applies
        """
        if len(device_chain) < 2:
            return False

        first = device_chain[0]
        return all(
            tile.width == first.width and tile.width * tile.height <= 64
            for tile in device_chain
        )

    async def _get_chain_colors_batched(
        self, device_chain: list[TileInfo]
    ) -> list[list[HSBK]]:
        """Read every tile in the chain with a single Get64 request.

        Responses are keyed by their reported ``tile_index`` rather than by
        arrival order. Any tile the device does not answer for is fetched
        individually afterwards, so a dropped datagram costs one extra request
        rather than the whole read.

        Args:
            device_chain: Tiles reported by the device

        Returns:
            List of color lists, one per tile, in chain order
        """
        expected = len(device_chain)
        colors_by_index: dict[int, list[HSBK]] = {}

        _LOGGER.debug(
            "Getting all zones from %d tiles in one request for %s",
            expected,
            self.label or self.serial,
        )

        async for response in self.connection.request_stream(
            packets.Tile.Get64(
                tile_index=0,
                length=expected,
                rect=TileBufferRect(fb_index=0, x=0, y=0, width=device_chain[0].width),
            )
        ):
            self._raise_if_unhandled(response)

            index = response.tile_index
            if not 0 <= index < expected or index in colors_by_index:
                # Out of range or a duplicate: neither can be placed in the
                # result, and counting it would end the stream early.
                continue

            tile = device_chain[index]
            colors_by_index[index] = [
                HSBK.from_protocol(proto_color)
                for proto_color in response.colors[: tile.width * tile.height]
            ]

            if len(colors_by_index) == expected:
                break

        missing = [index for index in range(expected) if index not in colors_by_index]
        if missing:
            _LOGGER.debug(
                "Batched read missed tiles %s for %s, fetching them individually",
                missing,
                self.label or self.serial,
            )
            for index in missing:
                colors_by_index[index] = await self.get64(tile_index=index)

        return [colors_by_index[index] for index in range(expected)]

    async def _get_chain_colors_per_tile(
        self, device_chain: list[TileInfo]
    ) -> list[list[HSBK]]:
        """Read each tile with its own request, chunking tiles over 64 zones.

        Used for single-tile devices and for tiles too large for one Set64-sized
        response (a 16x8 Ceiling needs two). Tiles are queried sequentially to
        avoid overwhelming the device with concurrent requests.

        Args:
            device_chain: Tiles reported by the device

        Returns:
            List of color lists, one per tile, in chain order
        """
        all_colors: list[list[HSBK]] = []

        for tile in device_chain:
            tile_zone_count = tile.width * tile.height

            if tile_zone_count <= 64:
                # Single request for tiles with ≤64 zones
                all_colors.append(await self.get64(tile_index=tile.tile_index))
            else:
                # Multiple requests for tiles with >64 zones (e.g., 16x8 Ceiling)
                # Split into multiple 64-zone requests by row
                tile_colors: list[HSBK] = []
                rows_per_request = 64 // tile.width  # e.g., 64/16 = 4 rows

                for y_offset in range(0, tile.height, rows_per_request):
                    chunk = await self.get64(
                        tile_index=tile.tile_index,
                        x=0,
                        y=y_offset,
                        width=tile.width,
                    )
                    tile_colors.extend(chunk)

                all_colors.append(tile_colors)

        return all_colors

    async def set64(
        self,
        tile_index: int,
        length: int,
        x: int,
        y: int,
        width: int,
        duration: int,
        colors: list[HSBK],
        fb_index: int = 0,
    ) -> None:
        """Set up to 64 zones of color on a tile.

        Colors are applied row-by-row starting at position (x, y).
        For tiles >64 zones, use multiple set64() calls with copy_frame_buffer().

        Args:
            tile_index: Index of the tile (0-based)
            length: Number of tiles to update (usually 1)
            x: X coordinate of the rectangle (0-based)
            y: Y coordinate of the rectangle (0-based)
            width: Width of the rectangle in zones
            duration: Transition duration in milliseconds
            colors: List of HSBK colors (up to 64)
            fb_index: Frame buffer index (0 for display, 1 for temp buffer)

        Example:
            >>> # Set 8x8 tile to red
            >>> colors = [HSBK.from_rgb(1.0, 0.0, 0.0)] * 64
            >>> await matrix.set64(
            ...     tile_index=0, length=1, x=0, y=0, width=8, duration=0, colors=colors
            ... )
        """
        # Validate parameters
        if x < 0:
            raise ValueError(f"x coordinate must be non-negative, got {x}")
        if y < 0:
            raise ValueError(f"y coordinate must be non-negative, got {y}")
        if width <= 0:
            raise ValueError(f"width must be positive, got {width}")

        _LOGGER.debug(
            "Setting 64 zones on tile %d (x=%d, y=%d, width=%d, fb=%d, "
            "duration=%d) for %s",
            tile_index,
            x,
            y,
            width,
            fb_index,
            duration,
            self.label or self.serial,
        )

        # Convert HSBK colors to protocol format
        proto_colors = [color.to_protocol() for color in colors]

        # Pad to 64 colors if needed
        while len(proto_colors) < 64:
            proto_colors.append(LightHsbk(0, 0, 0, 3500))

        await self.connection.send_packet(
            packets.Tile.Set64(
                tile_index=tile_index,
                length=length,
                rect=TileBufferRect(fb_index=fb_index, x=x, y=y, width=width),
                duration=duration,
                colors=proto_colors,
            )
        )

    async def copy_frame_buffer(
        self,
        tile_index: int,
        source_fb: int = 1,
        target_fb: int = 0,
        duration: float = 0.0,
        length: int = 1,
    ) -> None:
        """Copy frame buffer (for tiles with >64 zones).

        This is used for tiles with more than 64 zones. After setting colors
        in the temporary buffer (fb=1), copy to the display buffer (fb=0).

        Args:
            tile_index: Index of the tile (0-based)
            source_fb: Source frame buffer index (usually 1)
            target_fb: Target frame buffer index (usually 0)
            duration: time in seconds to transition if target_fb is 0
            length: Number of tiles to update starting from tile_index (default 1)

        Example:
            >>> # For 16x8 tile (128 zones):
            >>> # 1. Set first 64 zones to buffer 1
            >>> await matrix.set64(
            ...     tile_index=0,
            ...     length=1,
            ...     x=0,
            ...     y=0,
            ...     width=16,
            ...     duration=0,
            ...     colors=colors[:64],
            ...     fb_index=1,
            ... )
            >>> # 2. Set second 64 zones to buffer 1
            >>> await matrix.set64(
            ...     tile_index=0,
            ...     length=1,
            ...     x=0,
            ...     y=4,
            ...     width=16,
            ...     duration=0,
            ...     colors=colors[64:],
            ...     fb_index=1,
            ... )
            >>> # 3. Copy buffer 1 to buffer 0 (display)
            >>> await matrix.copy_frame_buffer(
            ...     tile_index=0, source_fb=1, target_fb=0, duration=2.0
            ... )

            >>> # For a chain of 5 tiles, update all simultaneously:
            >>> await matrix.copy_frame_buffer(
            ...     tile_index=0, source_fb=1, target_fb=0, length=5
            ... )
        """
        _LOGGER.debug(
            "Copying frame buffer %d -> %d for tile %d (length=%d) on %s",
            source_fb,
            target_fb,
            tile_index,
            length,
            self.label or self.serial,
        )

        # Get tile dimensions for the copy operation
        if self._device_chain is None:
            await self.get_device_chain()

        if self._device_chain is None or tile_index >= len(self._device_chain):
            raise ValueError(f"Invalid tile_index {tile_index}")

        tile = self._device_chain[tile_index]
        duration_ms = round(duration * 1000 if duration else 0)

        await self.connection.send_packet(
            packets.Tile.CopyFrameBuffer(
                tile_index=tile_index,
                length=length,
                src_fb_index=source_fb,
                dst_fb_index=target_fb,
                src_x=0,
                src_y=0,
                dst_x=0,
                dst_y=0,
                width=tile.width,
                height=tile.height,
                duration=duration_ms,
            )
        )

    async def set_matrix_colors(
        self, tile_index: int, colors: list[HSBK], duration: int = 0
    ) -> None:
        """Convenience method to set all colors on a tile.

        If all colors are the same, uses SetColor() packet which sets all zones
        across all tiles. Otherwise, automatically handles tiles with >64 zones
        using frame buffer strategy.

        Args:
            tile_index: Index of the tile (0-based)
            colors: List of HSBK colors (length must match tile total_zones)
            duration: Transition duration in milliseconds

        Example:
            >>> # Set entire tile to solid red (uses SetColor packet)
            >>> colors = [HSBK.from_rgb(1.0, 0.0, 0.0)] * 64
            >>> await matrix.set_matrix_colors(tile_index=0, colors=colors)

            >>> # Set 8x8 tile to gradient (uses set64 with zones)
            >>> colors = [HSBK(i * 360 / 64, 1.0, 1.0, 3500) for i in range(64)]
            >>> await matrix.set_matrix_colors(tile_index=0, colors=colors)
        """
        # Get device chain to determine tile dimensions
        if self._device_chain is None:
            await self.get_device_chain()

        if not self._device_chain or tile_index >= len(self._device_chain):
            raise ValueError(f"Invalid tile_index: {tile_index}")

        tile = self._device_chain[tile_index]

        if len(colors) != tile.total_zones:
            raise ValueError(
                f"Color count mismatch: expected {tile.total_zones}, got {len(colors)}"
            )

        # Check if all colors are the same (uint16 wire equality). The shortcut
        # below sends a device-wide SetColor, so it is only safe when the device
        # has a single tile — on a chain it would repaint every other tile too.
        first_color = colors[0]
        all_same = len(self._device_chain) == 1 and all(
            c == first_color for c in colors
        )

        if all_same:
            # All zones same color - use SetColor packet (much faster!)
            _LOGGER.debug(
                "All zones same color, using SetColor packet for tile %d",
                tile_index,
            )
            await self.set_color(first_color, duration=duration / 1000.0)
            return

        if tile.requires_frame_buffer:
            # Tile has >64 zones, use frame buffer strategy
            _LOGGER.debug(
                "Using frame buffer strategy for tile %d (%dx%d = %d zones)",
                tile_index,
                tile.width,
                tile.height,
                tile.total_zones,
            )

            # Calculate rows per batch (64 zones / width)
            rows_per_batch = 64 // tile.width
            total_batches = (tile.height + rows_per_batch - 1) // rows_per_batch

            for batch in range(total_batches):
                start_row = batch * rows_per_batch
                end_row = min(start_row + rows_per_batch, tile.height)

                # Extract colors for this batch
                start_idx = start_row * tile.width
                end_idx = end_row * tile.width
                batch_colors = colors[start_idx:end_idx]

                # Set colors to frame buffer 1
                await self.set64(
                    tile_index=tile_index,
                    length=1,
                    x=0,
                    y=start_row,
                    width=tile.width,
                    duration=duration if batch == total_batches - 1 else 0,
                    colors=batch_colors,
                    fb_index=1,
                )

            # Copy frame buffer 1 to 0 (display)
            await self.copy_frame_buffer(
                tile_index=tile_index, source_fb=1, target_fb=0
            )
        else:
            # Tile has ≤64 zones, single set64() call
            await self.set64(
                tile_index=tile_index,
                length=1,
                x=0,
                y=0,
                width=tile.width,
                duration=duration,
                colors=colors,
            )

    async def get_effect(self) -> MatrixEffect:
        """Get current running matrix effect.

        Returns:
            MatrixEffect describing the current effect state

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            >>> effect = await matrix.get_effect()
            >>> print(f"Effect type: {effect.effect_type}")
        """
        _LOGGER.debug("Getting matrix effect for %s", self.label or self.serial)

        response: packets.Tile.StateEffect = await self.connection.request(
            packets.Tile.GetEffect()
        )
        self._raise_if_unhandled(response)

        # Convert protocol effect to MatrixEffect
        palette = [
            HSBK.from_protocol(proto_color)
            for proto_color in response.settings.palette[
                : response.settings.palette_count
            ]
        ]

        effect = MatrixEffect(
            effect_type=response.settings.effect_type,
            speed=response.settings.speed,
            duration=response.settings.duration,
            palette=palette if palette else None,
            sky_type=response.settings.parameter.sky_type,
            cloud_saturation_min=response.settings.parameter.cloud_saturation_min,
            cloud_saturation_max=response.settings.parameter.cloud_saturation_max,
            from_device=True,
        )

        self._tile_effect = effect

        # Update state if it exists
        if self._state is not None and hasattr(self._state, "effect"):
            self._state.effect = effect.effect_type
            self._state.last_updated = time.time()

        return effect

    async def _resolve_sky_support(self) -> tuple[bool, str | None]:
        """Resolve SKY support and the reason when it is unsupported.

        Returns:
            Tuple of (supported, reason). `reason` is None when supported, and
            otherwise describes why the device cannot run the effect.

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
        """
        # connect(), discovery and __aenter__ all populate capabilities and
        # host firmware, so any device that got here through a supported path
        # has both. Anything built without them fails closed.
        capabilities = self.capabilities
        has_matrix = capabilities is not None and capabilities.has_matrix

        if not has_matrix:
            return False, "it is not a matrix device"

        firmware = self._host_firmware or await self.get_host_firmware()

        if firmware_supports_sky_effect(has_matrix, firmware.version_major):
            return True, None

        return False, (
            f"it is running firmware "
            f"{firmware.version_major}.{firmware.version_minor} and the "
            f"SKY effect needs firmware "
            f"{SKY_EFFECT_MIN_FIRMWARE_MAJOR}.0 or later"
        )

    async def supports_sky_effect(self) -> bool:
        """Check whether this device can run the SKY firmware effect.

        SKY requires both the matrix capability and a host firmware major
        version of at least `SKY_EFFECT_MIN_FIRMWARE_MAJOR`: matrix devices on
        earlier firmware reject or ignore it. See `lifx.products.quirks` for
        the products this has been confirmed on.

        Products missing from the bundled registry snapshot have no known
        capabilities, so they are reported as unsupported.

        Returns:
            True if the device has matrix capability and its host firmware
            supports the SKY effect

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

        Example:
            ```python
            if await matrix.supports_sky_effect():
                await matrix.set_effect(FirmwareEffect.SKY)
            ```
        """
        supported, _ = await self._resolve_sky_support()
        return supported

    async def set_effect(
        self,
        effect_type: FirmwareEffect,
        speed: float = 3.0,
        duration: int = 0,
        palette: list[HSBK] | None = None,
        sky_type: TileEffectSkyType = TileEffectSkyType.SUNRISE,
        cloud_saturation_min: int = 0,
        cloud_saturation_max: int = 0,
    ) -> None:
        """Set matrix effect with configuration.

        Args:
            effect_type: Type of effect (OFF, MORPH, FLAME, SKY)
            speed: Effect speed in seconds (default: 3)
            duration: Total effect duration in nanoseconds (0 for infinite)
            palette: Color palette for the effect (max 16 colors, None for no palette)
            sky_type: Sky effect type (SUNRISE, SUNSET, CLOUDS)
            cloud_saturation_min: Minimum cloud saturation (0-255, for CLOUDS)
            cloud_saturation_max: Maximum cloud saturation (0-255, for CLOUDS)

        Raises:
            LifxUnsupportedCommandError: If SKY is requested on a device that
                is known not to support it, either because it lacks the matrix
                capability or because its host firmware is too old

        Example:
            >>> # Set MORPH effect with rainbow palette
            >>> rainbow = [
            ...     HSBK(0, 1.0, 1.0, 3500),  # Red
            ...     HSBK(60, 1.0, 1.0, 3500),  # Yellow
            ...     HSBK(120, 1.0, 1.0, 3500),  # Green
            ...     HSBK(240, 1.0, 1.0, 3500),  # Blue
            ... ]
            >>> await matrix.set_effect(
            ...     effect_type=FirmwareEffect.MORPH,
            ...     speed=5.0,
            ...     palette=rainbow,
            ... )

            >>> # Set effect without a palette
            >>> await matrix.set_effect(
            ...     effect_type=FirmwareEffect.FLAME,
            ...     speed=3.0,
            ... )
        """
        if effect_type == FirmwareEffect.SKY:
            try:
                supported, reason = await self._resolve_sky_support()
            except LifxTimeoutError:
                # The support probe is best-effort. A device that fails to
                # answer is not evidence of missing support, and refusing here
                # would turn a fire-and-forget send into a hard failure.
                _LOGGER.debug(
                    "SKY support probe timed out for %s, sending the effect anyway",
                    self.label or self.serial,
                )
            else:
                if not supported:
                    raise LifxUnsupportedCommandError(
                        f"{self.label or self.serial} does not support the SKY"
                        f" effect: {reason}"
                    )

        _LOGGER.debug(
            "Setting matrix effect %s (speed=%d) for %s",
            effect_type,
            speed,
            self.label or self.serial,
        )
        speed_ms = round(speed * 1000) if speed else 3000

        # Create and validate MatrixEffect
        effect = MatrixEffect(
            effect_type=effect_type,
            speed=speed_ms,
            duration=duration,
            palette=palette,
            sky_type=sky_type,
            cloud_saturation_min=cloud_saturation_min,
            cloud_saturation_max=cloud_saturation_max,
        )

        # Convert to protocol format
        proto_palette = []
        palette_count = 0

        if effect.palette is not None:
            palette_count = len(effect.palette)
            proto_palette = [color.to_protocol() for color in effect.palette]

        # Pad palette to 16 colors (protocol requirement)
        while len(proto_palette) < 16:
            proto_palette.append(LightHsbk(0, 0, 0, 3500))

        settings = TileEffectSettings(
            instanceid=0,
            effect_type=effect.effect_type,
            speed=effect.speed,
            duration=effect.duration,
            parameter=TileEffectParameter(
                sky_type=effect.sky_type,
                cloud_saturation_min=effect.cloud_saturation_min,
                cloud_saturation_max=effect.cloud_saturation_max,
            ),
            palette_count=palette_count,
            palette=proto_palette,
        )

        await self.connection.send_packet(packets.Tile.SetEffect(settings=settings))
        self._tile_effect = effect

    async def apply_theme(
        self,
        theme: Theme,
        power_on: bool = False,
        duration: float = 0.0,
    ) -> None:
        """Apply a theme across matrix tiles using Canvas interpolation.

        Distributes theme colors across the tile matrix with smooth color blending
        using the Canvas API for visually pleasing transitions.

        Every device is rendered at its own reported pixel geometry, so non-8x8
        products (Candle 5x6, Ceiling 16x8) get the right number of colours.

        Position and orientation are used only on a chain-capable device — the
        LIFX Tile, the sole product that is arranged into a layout and the sole
        product with an accelerometer. There, each tile is placed on the canvas
        with :func:`lifx.geometry.tile_origin_pixels` so it gets a distinct slice
        of the theme, and a physically rotated panel is remapped to match. Every
        other matrix device is a single fixed panel, so it renders at the canvas
        origin and is never remapped.

        Args:
            theme: Theme to apply
            power_on: Turn on the light
            duration: Transition duration in seconds

        Example:
            ```python
            from lifx.theme import get_theme

            theme = get_theme("evening")
            await matrix.apply_theme(theme, power_on=True, duration=0.5)
            ```
        """
        from lifx.theme.generators import MatrixGenerator

        # Get device chain
        tiles = await self.get_device_chain()

        if not tiles:
            return

        # The LIFX Tile is the only chain-capable product, and the only one with
        # an accelerometer. Every other matrix device is a single fixed panel: it
        # is never arranged relative to anything, and it returns whatever its
        # firmware leaves in the position and accel fields. Reading those as a
        # layout or a rotation would scatter and scramble the theme, so both are
        # used only for a chain. FrameBuffer.for_matrix() gates the same way.
        await self.ensure_capabilities()
        has_chain = bool(self.capabilities and self.capabilities.has_chain)

        # Render the theme across the whole chain in one pass
        if has_chain:
            generator = MatrixGenerator.from_tiles(tiles)
        else:
            generator = MatrixGenerator([((0, 0), (t.width, t.height)) for t in tiles])
        tile_colors = generator.get_theme_colors(theme)

        # Check if light is on
        is_on = await self.get_power()

        # Apply colors to each tile
        for tile, colors in zip(tiles, tile_colors, strict=True):
            # The canvas renders in row-major screen order, so a physically
            # rotated tile needs the same orientation remapping the animation
            # layer applies in FrameBuffer._for_multi_tile().
            oriented = self._orient_tile_colors(tile, colors) if has_chain else colors

            # Apply with appropriate timing
            if power_on and not is_on:
                await self.set_matrix_colors(tile.tile_index, oriented, duration=0)
            else:
                await self.set_matrix_colors(
                    tile.tile_index, oriented, duration=int(duration * 1000)
                )

        # Turn on light if requested and currently off
        if power_on and not is_on:
            await self.set_power(True, duration=duration)

    @staticmethod
    def _orient_tile_colors(tile: TileInfo, colors: list[HSBK]) -> list[HSBK]:
        """Remap row-major canvas colours into the tile's physical orientation.

        Only meaningful for chain-capable devices: the LIFX Tile is the sole
        product with an accelerometer, so it is the only one whose reported
        orientation is real. Callers must gate on ``has_chain``.

        Args:
            tile: Tile the colours are destined for
            colors: Colours in row-major screen order

        Returns:
            The colours reordered for the tile's reported orientation, or the
            input unchanged when the tile is upright or the count does not match
            the tile's pixel grid.
        """
        orientation = Orientation.from_string(tile.nearest_orientation)
        if orientation == Orientation.RIGHT_SIDE_UP:
            return colors

        if len(colors) != tile.width * tile.height:  # pragma: no cover
            return colors

        lut = build_orientation_lut(tile.width, tile.height, orientation)
        return [colors[src_idx] for src_idx in lut]

    @property
    def device_chain(self) -> list[TileInfo] | None:
        """Get cached device chain.

        Returns None if not yet fetched. Use get_device_chain() to fetch.
        """
        return self._device_chain

    @property
    def tile_count(self) -> int | None:
        """Get number of tiles in the chain.

        Returns None if device chain not yet fetched.
        """
        if self._device_chain is None:
            return None
        return len(self._device_chain)

    @property
    def tile_effect(self) -> MatrixEffect | None:
        """Get cached tile effect.

        Returns None if not yet fetched. Use get_tile_effect() to fetch.
        """
        return self._tile_effect

    def __repr__(self) -> str:
        """Return string representation of MatrixLight."""
        return (
            f"MatrixLight(label={self.label!r}, serial={self.serial!r}, ip={self.ip!r})"
        )

    async def refresh_state(self) -> None:
        """Refresh matrix light state from hardware.

        Fetches color, tiles, tile colors for all tiles, and effect.

        Raises:
            LifxTimeoutError: If device does not respond
            LifxDeviceNotFoundError: If device cannot be reached
        """
        await super().refresh_state()

        # Fetch all matrix light state sequentially to avoid overwhelming device
        all_tile_colors = await self.get_all_tile_colors()
        effect = await self.get_effect()

        # Flatten tile colors for state storage
        self._state.tile_colors = [c for tile in all_tile_colors for c in tile]
        self._state.effect = effect.effect_type

    async def _initialize_state(self) -> MatrixLightState:
        """Initialize matrix light state transactionally.

        Extends Light implementation to fetch tiles and effect.

        Raises:
            LifxTimeoutError: If device does not respond within timeout
            LifxDeviceNotFoundError: If device cannot be reached
            LifxProtocolError: If responses are invalid
        """
        light_state = await super()._initialize_state()

        # Fetch matrix-specific state sequentially to avoid overwhelming device
        chain = await self.get_device_chain()
        tile_orientations = {
            index: tile.nearest_orientation for index, tile in enumerate(chain)
        }
        # get_all_tile_colors uses cached chain from above
        all_tile_colors = await self.get_all_tile_colors()
        effect = await self.get_effect()

        # Flatten tile colors for state storage
        flat_tile_colors = [c for tile in all_tile_colors for c in tile]

        # Create state instance with matrix fields
        self._state = MatrixLightState.from_light_state(
            light_state,
            chain=chain,
            tile_orientations=tile_orientations,
            tile_colors=flat_tile_colors,
            effect=effect.effect_type,
        )

        return self._state
