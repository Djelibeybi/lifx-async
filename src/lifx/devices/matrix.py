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

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lifx.color import HSBK

if TYPE_CHECKING:
    from lifx.theme import Theme
from lifx.devices.light import Light
from lifx.protocol import packets
from lifx.protocol.protocol_types import (
    LightHsbk,
    TileBufferRect,
    TileEffectParameter,
    TileEffectSettings,
    TileEffectSkyType,
    TileEffectType,
)
from lifx.protocol.protocol_types import (
    TileStateDevice as LifxProtocolTileDevice,
)

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
    device_version_vendor: int
    device_version_product: int
    device_version_version: int
    firmware_build: int
    firmware_version_minor: int
    firmware_version_major: int

    @classmethod
    def from_protocol(
        cls, tile_index: int, protocol_tile: LifxProtocolTileDevice
    ) -> "TileInfo":
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
            device_version_vendor=protocol_tile.device_version.vendor,
            device_version_product=protocol_tile.device_version.product,
            device_version_version=0,  # Not available in TileStateDevice
            firmware_build=protocol_tile.firmware.build,
            firmware_version_minor=protocol_tile.firmware.version_minor,
            firmware_version_major=protocol_tile.firmware.version_major,
        )

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
    """

    effect_type: TileEffectType
    speed: int
    duration: int = 0
    palette: list[HSBK] | None = None
    sky_type: TileEffectSkyType = TileEffectSkyType.SUNRISE
    cloud_saturation_min: int = 0
    cloud_saturation_max: int = 0

    def __post_init__(self) -> None:
        """Initialize defaults and validate fields."""
        # Initialize default palette if not provided
        if self.palette is None:
            # Default palette: single white color
            self.palette = [HSBK(0, 0, 1.0, 3500)]

        # Validate all fields
        # Speed can be 0 only when effect is OFF
        if self.effect_type != TileEffectType.OFF:
            self._validate_speed_active(self.speed)
        elif self.speed < 0:
            raise ValueError(f"Effect speed must be non-negative, got {self.speed}")

        self._validate_duration(self.duration)
        self._validate_palette(self.palette)
        self._validate_saturation(self.cloud_saturation_min, "cloud_saturation_min")
        self._validate_saturation(self.cloud_saturation_max, "cloud_saturation_max")

        # Apply cloud saturation defaults only for CLOUDS sky type
        if (
            self.effect_type == TileEffectType.SKY
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
        if len(value) > 16:
            raise ValueError(
                f"Effect palette can contain at most 16 colors, got {len(value)}"
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
        >>> async with await MatrixLight.from_ip("192.168.1.100") as matrix:
        ...     # Get device chain info
        ...     chain = await matrix.get_device_chain()
        ...     print(f"Device has {len(chain)} tile(s)")
        ...
        ...     # Set colors on first tile (8x8 = 64 zones)
        ...     colors = [HSBK.from_rgb(255, 0, 0)] * 64
        ...     await matrix.set64(tile_index=0, colors=colors, width=8)
    """

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = 56700,
    ) -> None:
        """Initialize MatrixLight device.

        Args:
            serial: Device serial number
            ip: Device IP address
            port: Device port (default: 56700)
        """
        super().__init__(serial, ip, port)
        self._device_chain: list[TileInfo] | None = None
        self._tile_effect: MatrixEffect | None = None

    async def _setup(self) -> None:
        """Setup device by fetching initial state."""
        await super()._setup()
        # Fetch device chain on setup
        await self.get_device_chain()

    async def get_device_chain(self) -> list[TileInfo]:
        """Get device chain details (list of Tile objects).

        This method fetches the device chain information and caches it.

        Returns:
            List of TileInfo objects describing each tile in the chain

        Example:
            >>> chain = await matrix.get_device_chain()
            >>> for tile in chain:
            ...     print(f"Tile {tile.tile_index}: {tile.width}x{tile.height}")
        """
        _LOGGER.debug("Getting device chain for %s", self.label or self.serial)

        response: packets.Tile.StateDeviceChain = await self.connection.request(
            packets.Tile.GetDeviceChain()
        )

        # Parse tiles from response
        tiles = []
        for i, protocol_tile in enumerate(response.tile_devices):
            # Stop at first zero-width tile (indicates end of chain)
            if protocol_tile.width == 0:
                break
            tiles.append(TileInfo.from_protocol(i, protocol_tile))

        self._device_chain = tiles
        _LOGGER.debug("Device chain has %d tile(s)", len(tiles))
        return tiles

    async def set_user_position(
        self, tile_index: int, user_x: float, user_y: float
    ) -> None:
        """Position tiles in the chain (only for devices with has_chain capability).

        Args:
            tile_index: Index of the tile to position (0-based)
            user_x: User-defined X position
            user_y: User-defined Y position

        Note:
            Only applicable for multi-tile devices (has_chain capability).
            Most MatrixLight devices have a single tile and don't need positioning.

        Example:
            >>> # Position second tile at coordinates (1.0, 0.0)
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
        tile_index: int,
        length: int,
        x: int,
        y: int,
        width: int,
        fb_index: int = 0,
    ) -> list[HSBK]:
        """Get up to 64 zones of color state from a tile.

        Args:
            tile_index: Index of the tile (0-based)
            length: Number of tiles to query (usually 1)
            x: X coordinate of the rectangle (0-based)
            y: Y coordinate of the rectangle (0-based)
            width: Width of the rectangle in zones
            fb_index: Frame buffer index (0 for display, 1 for temp buffer)

        Returns:
            List of HSBK colors for the requested zones

        Example:
            >>> # Get colors from 8x8 tile (64 zones)
            >>> colors = await matrix.get64(tile_index=0, length=1, x=0, y=0, width=8)
        """
        # Validate parameters
        if x < 0:
            raise ValueError(f"x coordinate must be non-negative, got {x}")
        if y < 0:
            raise ValueError(f"y coordinate must be non-negative, got {y}")
        if width <= 0:
            raise ValueError(f"width must be positive, got {width}")

        _LOGGER.debug(
            "Getting 64 zones from tile %d (x=%d, y=%d, width=%d, fb=%d) for %s",
            tile_index,
            x,
            y,
            width,
            fb_index,
            self.label or self.serial,
        )

        response: packets.Tile.State64 = await self.connection.request(
            packets.Tile.Get64(
                tile_index=tile_index,
                length=length,
                rect=TileBufferRect(fb_index=fb_index, x=x, y=y, width=width),
            )
        )

        # Convert protocol colors to HSBK
        return [HSBK.from_protocol(proto_color) for proto_color in response.colors]

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
            >>> colors = [HSBK.from_rgb(255, 0, 0)] * 64
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
        proto_colors = []
        for color in colors:
            proto_colors.append(
                LightHsbk(
                    hue=int(color.hue / 360 * 65535),
                    saturation=int(color.saturation * 65535),
                    brightness=int(color.brightness * 65535),
                    kelvin=color.kelvin,
                )
            )

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
        self, tile_index: int, source_fb: int = 1, target_fb: int = 0
    ) -> None:
        """Copy frame buffer (for tiles with >64 zones).

        This is used for tiles with more than 64 zones. After setting colors
        in the temporary buffer (fb=1), copy to the display buffer (fb=0).

        Args:
            tile_index: Index of the tile (0-based)
            source_fb: Source frame buffer index (usually 1)
            target_fb: Target frame buffer index (usually 0)

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
            >>> await matrix.copy_frame_buffer(tile_index=0, source_fb=1, target_fb=0)
        """
        _LOGGER.debug(
            "Copying frame buffer %d -> %d for tile %d on %s",
            source_fb,
            target_fb,
            tile_index,
            self.label or self.serial,
        )

        # Get tile dimensions for the copy operation
        if self._device_chain is None:
            await self.get_device_chain()

        if self._device_chain is None or tile_index >= len(self._device_chain):
            raise ValueError(f"Invalid tile_index {tile_index}")

        tile = self._device_chain[tile_index]

        await self.connection.send_packet(
            packets.Tile.CopyFrameBuffer(
                tile_index=tile_index,
                length=1,
                src_fb_index=source_fb,
                dst_fb_index=target_fb,
                src_x=0,
                src_y=0,
                dst_x=0,
                dst_y=0,
                width=tile.width,
                height=tile.height,
                duration=0,
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
            >>> colors = [HSBK.from_rgb(255, 0, 0)] * 64
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

        # Check if all colors are the same
        first_color = colors[0]
        all_same = all(
            c.hue == first_color.hue
            and c.saturation == first_color.saturation
            and c.brightness == first_color.brightness
            and c.kelvin == first_color.kelvin
            for c in colors
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

    async def get_tile_effect(self) -> MatrixEffect:
        """Get current running tile effect.

        Returns:
            MatrixEffect describing the current effect state

        Example:
            >>> effect = await matrix.get_tile_effect()
            >>> print(f"Effect type: {effect.effect_type}")
        """
        _LOGGER.debug("Getting tile effect for %s", self.label or self.serial)

        response: packets.Tile.StateEffect = await self.connection.request(
            packets.Tile.GetEffect()
        )

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
        )

        self._tile_effect = effect
        return effect

    async def set_tile_effect(
        self,
        effect_type: TileEffectType,
        speed: int = 3000,
        duration: int = 0,
        palette: list[HSBK] | None = None,
        sky_type: TileEffectSkyType = TileEffectSkyType.SUNRISE,
        cloud_saturation_min: int = 0,
        cloud_saturation_max: int = 0,
    ) -> None:
        """Set tile effect with configuration.

        Args:
            effect_type: Type of effect (OFF, MORPH, FLAME, SKY)
            speed: Effect speed in milliseconds (default: 3000)
            duration: Total effect duration in nanoseconds (0 for infinite)
            palette: Color palette for the effect (max 16 colors)
            sky_type: Sky effect type (SUNRISE, SUNSET, CLOUDS)
            cloud_saturation_min: Minimum cloud saturation (0-255, for CLOUDS)
            cloud_saturation_max: Maximum cloud saturation (0-255, for CLOUDS)

        Example:
            >>> # Set MORPH effect with rainbow palette
            >>> rainbow = [
            ...     HSBK(0, 1.0, 1.0, 3500),  # Red
            ...     HSBK(60, 1.0, 1.0, 3500),  # Yellow
            ...     HSBK(120, 1.0, 1.0, 3500),  # Green
            ...     HSBK(240, 1.0, 1.0, 3500),  # Blue
            ... ]
            >>> await matrix.set_tile_effect(
            ...     effect_type=TileEffectType.MORPH,
            ...     speed=5000,
            ...     palette=rainbow,
            ... )
        """
        _LOGGER.debug(
            "Setting tile effect %s (speed=%d) for %s",
            effect_type,
            speed,
            self.label or self.serial,
        )

        # Create and validate MatrixEffect
        effect = MatrixEffect(
            effect_type=effect_type,
            speed=speed,
            duration=duration,
            palette=palette,
            sky_type=sky_type,
            cloud_saturation_min=cloud_saturation_min,
            cloud_saturation_max=cloud_saturation_max,
        )

        # Convert to protocol format
        # Note: palette is guaranteed to be non-None by MatrixEffect.__post_init__
        palette = effect.palette if effect.palette is not None else []
        proto_palette = []
        for color in palette:
            proto_palette.append(
                LightHsbk(
                    hue=int(color.hue / 360 * 65535),
                    saturation=int(color.saturation * 65535),
                    brightness=int(color.brightness * 65535),
                    kelvin=color.kelvin,
                )
            )

        # Pad palette to 16 colors
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
            palette_count=len(palette),
            palette=proto_palette,
        )

        await self.connection.send_packet(packets.Tile.SetEffect(settings=settings))
        self._tile_effect = effect

    async def apply_theme(
        self,
        theme: "Theme",
        power_on: bool = False,
        duration: float = 0.0,
    ) -> None:
        """Apply a theme across matrix tiles using Canvas interpolation.

        Distributes theme colors across the tile matrix with smooth color blending
        using the Canvas API for visually pleasing transitions.

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
        from lifx.theme.canvas import Canvas

        # Get device chain
        tiles = await self.get_device_chain()

        if not tiles:
            return

        # Create canvas and populate with theme colors
        canvas = Canvas()
        for tile in tiles:
            canvas.add_points_for_tile(None, theme)
        canvas.shuffle_points()
        canvas.blur_by_distance()

        # Check if light is on
        is_on = await self.get_power()

        # Apply colors to each tile
        for tile in tiles:
            # Extract tile colors from canvas as 1D list
            colors = canvas.points_for_tile(None, width=tile.width, height=tile.height)

            # Apply with appropriate timing
            if power_on and not is_on:
                await self.set_matrix_colors(tile.tile_index, colors, duration=0)
            else:
                await self.set_matrix_colors(
                    tile.tile_index, colors, duration=int(duration * 1000)
                )

        # Turn on light if requested and currently off
        if power_on and not is_on:
            await self.set_power(True, duration=duration)

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
