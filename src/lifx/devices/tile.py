"""Tile device class for LIFX Tile products."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.protocol import packets
from lifx.protocol.protocol_types import (
    TileBufferRect,
    TileEffectParameter,
    TileEffectSettings,
    TileEffectSkyType,
    TileEffectType,
)
from lifx.protocol.protocol_types import TileStateDevice as LifxProtocolTileDevice

if TYPE_CHECKING:
    from lifx.theme import Theme

_LOGGER = logging.getLogger(__name__)


@dataclass
class TileInfo:
    """Information about a single tile in the chain.

    Attributes:
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
    def from_protocol(cls, protocol_tile: LifxProtocolTileDevice) -> TileInfo:
        """Create TileInfo from protocol TileStateDevice."""
        return cls(
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


@dataclass
class TileEffect:
    """Tile effect configuration.

    Attributes:
        effect_type: Type of effect (OFF, MORPH, FLAME)
        speed: Effect speed in milliseconds
        duration: Total effect duration in nanoseconds (0 for infinite)
        palette: Color palette for the effect (max 16 colors)
        parameters: Effect-specific parameters (sky_type, cloud_saturation_min,
                    cloud_saturation_max)
    """

    effect_type: TileEffectType
    speed: int
    duration: int = 0
    palette: list[HSBK] | None = None
    parameters: list[int] | None = None

    def __post_init__(self) -> None:
        """Initialize defaults and validate fields."""
        # Initialize default palette and parameters if not provided
        if self.palette is None:
            # Default palette: single white color
            self.palette = [HSBK(0, 0, 1.0, 3500)]
        if self.parameters is None:
            self.parameters = [0] * 3

        # Validate all fields
        self._validate_speed(self.speed)
        self._validate_duration(self.duration)
        self._validate_palette(self.palette)
        self._validate_parameters(self.parameters)

    @staticmethod
    def _validate_speed(value: int) -> None:
        """Validate effect speed is non-negative.

        Args:
            value: Speed value in milliseconds

        Raises:
            ValueError: If speed is negative
        """
        if value < 0:
            raise ValueError(f"Effect speed must be non-negative, got {value}")

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
    def _validate_parameters(value: list[int]) -> None:
        """Validate effect parameters list.

        Args:
            value: sky_type, cloud_saturation_min, cloud_saturation_max

        Raises:
            ValueError: If parameters list is invalid
        """
        if len(value) != 3:
            raise ValueError(
                f"Effect parameters must be a list of 3 values, got {len(value)}"
            )
        for i, param in enumerate(value):
            if not (0 <= param < 256):
                raise ValueError(f"Parameter {i} must be a uint8 (0-255), got {param}")


@dataclass
class TileColors:
    """Color data for a single tile.

    Attributes:
        colors: Flat list of HSBK colors in row-major order
        width: Tile width in zones
        height: Tile height in zones
    """

    colors: list[HSBK]
    width: int
    height: int

    def get_color(self, x: int, y: int) -> HSBK:
        """Get color at specific coordinate.

        Args:
            x: X coordinate (0-based)
            y: Y coordinate (0-based)

        Returns:
            HSBK color at that position
        """
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            raise ValueError(
                f"Coordinates ({x}, {y}) out of bounds for"
                f"{self.width}x{self.height} tile"
            )
        index = y * self.width + x
        return self.colors[index]

    def set_color(self, x: int, y: int, color: HSBK) -> None:
        """Set color at specific coordinate.

        Args:
            x: X coordinate (0-based)
            y: Y coordinate (0-based)
            color: HSBK color to set
        """
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            raise ValueError(
                f"Coordinates ({x}, {y}) out of bounds for"
                f"{self.width}x{self.height} tile"
            )
        index = y * self.width + x
        self.colors[index] = color

    def to_2d(self) -> list[list[HSBK]]:
        """Convert flat color list to 2D array.

        Returns:
            2D list of colors [row][col]
        """
        result = []
        for row_idx in range(self.height):
            row = []
            for col_idx in range(self.width):
                index = row_idx * self.width + col_idx
                row.append(self.colors[index])
            result.append(row)
        return result

    @classmethod
    def from_2d(cls, colors_2d: list[list[HSBK]]) -> TileColors:
        """Create TileColors from 2D array.

        Args:
            colors_2d: 2D list of colors [row][col]

        Returns:
            TileColors instance
        """
        if not colors_2d or not colors_2d[0]:
            raise ValueError("2D colors array cannot be empty")
        height = len(colors_2d)
        width = len(colors_2d[0])
        # Flatten to 1D
        colors_flat = []
        for row in colors_2d:
            if len(row) != width:
                raise ValueError("All rows must have the same width")
            colors_flat.extend(row)
        return cls(colors=colors_flat, width=width, height=height)


@dataclass
class TileRect:
    """Rectangle area on a tile.

    Attributes:
        x: X coordinate (0-based)
        y: Y coordinate (0-based)
        width: Rectangle width in zones
        height: Rectangle height in zones
    """

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        """Validate all rectangle fields."""
        self._validate_coordinate(self.x, "x")
        self._validate_coordinate(self.y, "y")
        self._validate_dimension(self.width, "width")
        self._validate_dimension(self.height, "height")

    @staticmethod
    def _validate_coordinate(value: int, name: str) -> None:
        """Validate coordinate is non-negative.

        Args:
            value: Coordinate value to validate
            name: Name of the coordinate (for error messages)

        Raises:
            ValueError: If coordinate is negative
        """
        if value < 0:
            raise ValueError(
                f"Rectangle {name} coordinate must be non-negative, got {value}"
            )

    @staticmethod
    def _validate_dimension(value: int, name: str) -> None:
        """Validate dimension is positive.

        Args:
            value: Dimension value to validate
            name: Name of the dimension (for error messages)

        Raises:
            ValueError: If dimension is not positive
        """
        if value <= 0:
            raise ValueError(f"Rectangle {name} must be positive, got {value}")

    @property
    def pixel_count(self) -> int:
        """Get total number of zones in rectangle."""
        return self.width * self.height

    def contains_point(self, x: int, y: int) -> bool:
        """Check if point is within rectangle."""
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height


class TileDevice(Light):
    """LIFX Tile device with grid control.

    Extends the Light class with tile-specific functionality:
    - Tile chain discovery and information
    - Individual tile grid color control
    - Tile effects (morph, flame, sky)

    Example:
        ```python
        tile = TileDevice(serial="d073d5123456", ip="192.168.1.100")

        async with tile:
            # Get tile chain information
            chain = await tile.get_tile_chain()
            print(f"Device has {len(chain)} tiles")

            # Get colors from first tile
            colors = await tile.get_tile_colors(tile_index=0)

            # Set entire first tile to red
            red = HSBK.from_rgb(255, 0, 0)
            await tile.set_tile_colors(
                tile_index=0, colors=[[red] * 8 for _ in range(8)]
            )

            # Apply a flame effect
            await tile.set_flame_effect(speed=5.0)
        ```

        Using the simplified connect method:
        ```python
        async with await TileDevice.from_ip(ip="192.168.1.100") as light:
            await tile.set_flame_effect(speed=5.0)
        ```
    """

    def __init__(self, *args, **kwargs) -> None:
        """Initialize TileDevice with additional state attributes."""
        super().__init__(*args, **kwargs)
        # Tile-specific state storage
        self._tile_chain: tuple[list[TileInfo], float] | None = None
        self._tile_effect: tuple[TileEffect | None, float] | None = None
        # Tile colors: dict indexed by tile_index with TileColors for each tile
        # Structure: dict[tile_index] -> TileColors(colors, width, height)
        self._tile_colors: tuple[dict[int, TileColors], float] | None = None

    async def _setup(self) -> None:
        """Populate Tile light capabilities, state and metadata."""
        await super()._setup()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.get_tile_chain())
            tg.create_task(self.get_tile_effect())
        async with asyncio.TaskGroup() as tg:
            if self.tile_count is not None:
                tile_count, _ = self.tile_count
            else:
                tile_count = await self.get_tile_count()
            [tg.create_task(self.get_tile_colors(i)) for i in range(tile_count)]

    async def get_tile_chain(self) -> list[TileInfo]:
        """Get information about all tiles in the chain.

        Always fetches from device.
        Use the `tile_chain` property to access stored value.

        Returns:
            List of TileInfo objects, one per tile

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
            chain = await tile.get_tile_chain()
            for i, tile_info in enumerate(chain):
                print(f"Tile {i}: {tile_info.width}x{tile_info.height}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Tile.GetDeviceChain())

        # Convert protocol TileDevice objects to TileInfo
        tiles = [
            TileInfo.from_protocol(tile_device)
            for tile_device in state.tile_devices[: state.tile_devices_count]
        ]

        import time

        self._tile_chain = (tiles, time.time())

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_tile_chain",
                "action": "query",
                "reply": {
                    "tile_devices_count": state.tile_devices_count,
                    "tiles": [
                        {
                            "width": tile.width,
                            "height": tile.height,
                            "device_version_vendor": tile.device_version_vendor,
                            "device_version_product": tile.device_version_product,
                            "firmware_version_major": tile.firmware_version_major,
                            "firmware_version_minor": tile.firmware_version_minor,
                        }
                        for tile in tiles
                    ],
                },
            }
        )

        return tiles

    async def get_tile_count(self) -> int:
        """Get the number of tiles in the chain.

        Always fetches from device.
        Use the `tile_count` property to access stored value.

        Returns:
            Number of tiles

        Example:
            ```python
            count = await tile.get_tile_count()
            print(f"Device has {count} tiles")
            ```
        """
        chain = await self.get_tile_chain()
        count = len(chain)

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_tile_count",
                "action": "query",
                "reply": {
                    "count": count,
                },
            }
        )

        return count

    async def get_tile_colors(
        self,
        tile_index: int,
        x: int = 0,
        y: int = 0,
        width: int | None = None,
        height: int | None = None,
    ) -> list[list[HSBK]]:
        """Get colors from a tile.

        Always fetches from device.
        Use the `tile_colors` property to access stored value.

        Returns a 2D array of colors representing the zones.
        For tiles with >64 zones, multiple Get64 requests are sent sequentially.

        Args:
            tile_index: Index of tile in chain (0-based)
            x: Starting X coordinate (default 0)
            y: Starting Y coordinate (default 0)
            width: Rectangle width in zones (default: tile width)
            height: Rectangle height in zones (default: tile height)

        Returns:
            2D list of HSBK colors

        Raises:
            ValueError: If tile_index or dimensions are invalid
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
            # Get all colors from first tile
            colors = await tile.get_tile_colors(0)
            print(f"Top-left zone: {colors[0][0]}")

            # Get colors from specific rectangle
            colors = await tile.get_tile_colors(0, x=2, y=2, width=4, height=4)
            ```
        """
        if tile_index < 0:
            raise ValueError(f"Invalid tile index: {tile_index}")
        if x < 0 or y < 0:
            raise ValueError(f"Invalid coordinates: x={x}, y={y}")

        # Get tile info to determine dimensions
        chain = await self.get_tile_chain()
        if tile_index >= len(chain):
            raise ValueError(
                f"Tile index {tile_index} out of range (chain has {len(chain)} tiles)"
            )

        tile_info = chain[tile_index]

        # Default to full tile if dimensions not specified
        if width is None:
            width = tile_info.width - x
        if height is None:
            height = tile_info.height - y

        # Validate dimensions
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid dimensions: width={width}, height={height}")
        if x + width > tile_info.width or y + height > tile_info.height:
            raise ValueError(
                f"Rectangle exceeds tile dimensions ({x},{y},{width},{height}) "
                f"vs ({tile_info.width}x{tile_info.height})"
            )

        total_zones = width * height

        if total_zones <= 64:
            # Single Get64 request sufficient
            state = await self.connection.request(
                packets.Tile.Get64(
                    tile_index=tile_index,
                    length=1,
                    rect=TileBufferRect(fb_index=0, x=x, y=y, width=width),
                ),
            )

            # Convert colors from protocol HSBK to HSBK
            colors_flat = [
                HSBK.from_protocol(color) for color in state.colors[:total_zones]
            ]
        else:
            # Multiple Get64 requests needed
            # Split into chunks by rows, taking as many rows as fit in 64 zones
            colors_flat: list[HSBK] = []
            current_y = y

            while current_y < y + height:
                # Calculate how many rows we can fetch in this chunk (max 64 zones)
                rows_in_chunk = min((64 // width), (y + height - current_y))
                if rows_in_chunk == 0:
                    rows_in_chunk = 1  # Always fetch at least 1 row

                # Send Get64 request for this chunk
                state = await self.connection.request(
                    packets.Tile.Get64(
                        tile_index=tile_index,
                        length=1,
                        rect=TileBufferRect(fb_index=0, x=x, y=current_y, width=width),
                    ),
                )

                # Extract colors for this chunk
                zones_in_chunk = width * rows_in_chunk
                chunk_colors = [
                    HSBK.from_protocol(color) for color in state.colors[:zones_in_chunk]
                ]
                colors_flat.extend(chunk_colors)

                current_y += rows_in_chunk

        # Convert flat list to 2D array [y][x]
        colors_2d: list[list[HSBK]] = []
        for row_idx in range(height):
            row: list[HSBK] = []
            for col_idx in range(width):
                index = row_idx * width + col_idx
                if index < len(colors_flat):
                    row.append(colors_flat[index])
                else:
                    # Pad with black if we don't have enough colors
                    row.append(HSBK(0, 0, 0, 3500))
            colors_2d.append(row)

        # Update tile colors with fetched data
        import time

        timestamp = time.time()

        # Get tile chain to know dimensions
        if self._tile_chain is None:
            chain = await self.get_tile_chain()
        else:
            chain, _ = self._tile_chain

        # Get tile info for this specific tile
        tile_info = chain[tile_index]

        # Initialize or get existing colors dict
        if self._tile_colors is None:
            tiles_colors_dict = {}
        else:
            tiles_colors_dict, _ = self._tile_colors

        # Get or create TileColors for this tile
        if tile_index not in tiles_colors_dict:
            # Create new TileColors with default black colors
            num_zones = tile_info.width * tile_info.height
            default_colors = [HSBK(0, 0, 0, 3500)] * num_zones
            tiles_colors_dict[tile_index] = TileColors(
                colors=default_colors, width=tile_info.width, height=tile_info.height
            )

        tile_colors = tiles_colors_dict[tile_index]

        # Update the specific tile region with fetched colors
        for row_idx in range(height):
            for col_idx in range(width):
                tile_x = x + col_idx
                tile_y = y + row_idx
                if tile_y < tile_colors.height and tile_x < tile_colors.width:
                    tile_colors.set_color(tile_x, tile_y, colors_2d[row_idx][col_idx])

        # Store updated colors with new timestamp
        self._tile_colors = (tiles_colors_dict, timestamp)

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_tile_colors",
                "action": "query",
                "reply": {
                    "tile_index": tile_index,
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "total_zones": total_zones,
                },
            }
        )

        return colors_2d

    async def set_tile_colors(
        self,
        tile_index: int,
        colors: list[list[HSBK]],
        x: int = 0,
        y: int = 0,
        duration: float = 0.0,
    ) -> None:
        """Set colors on a tile.

        For tiles with >64 zones, multiple Set64 requests are sent to frame buffer 1,
        then CopyFrameBuffer is used to atomically copy to frame buffer 0 with the
        specified duration. This eliminates flicker during multi-packet updates.

        If the device is powered off, colors are set instantly (duration=0) and then
        the device is powered on with the specified duration for a smooth visual effect.

        Args:
            tile_index: Index of tile in chain (0-based)
            colors: 2D list of HSBK colors
            x: Starting X coordinate on tile (default 0)
            y: Starting Y coordinate on tile (default 0)
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If parameters are invalid
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

        Example:
            ```python
            # Set entire 8x8 tile to red
            red = HSBK.from_rgb(255, 0, 0)
            colors = [[red] * 8 for _ in range(8)]
            await tile.set_tile_colors(0, colors)

            # Set a 4x4 area starting at (2, 2) with transition
            blue = HSBK.from_rgb(0, 0, 255)
            colors = [[blue] * 4 for _ in range(4)]
            await tile.set_tile_colors(0, colors, x=2, y=2, duration=1.0)

            # Set entire 16x8 wide tile with smooth transition
            colors = [[HSBK.from_rgb(255, 0, 0)] * 16 for _ in range(8)]
            await tile.set_tile_colors(0, colors, duration=2.0)
            ```
        """
        if tile_index < 0:
            raise ValueError(f"Invalid tile index: {tile_index}")
        if x < 0 or y < 0:
            raise ValueError(f"Invalid coordinates: x={x}, y={y}")
        if not colors or not colors[0]:
            raise ValueError("Colors array cannot be empty")

        height = len(colors)
        width = len(colors[0])

        # Validate that all rows have the same width
        for row in colors:
            if len(row) != width:
                raise ValueError("All rows in colors array must have the same width")

        # Flatten colors to 1D array
        colors_flat: list[HSBK] = []
        for row in colors:
            colors_flat.extend(row)

        total_zones = width * height

        # Check power state to optimize duration handling
        # If device is off, set colors instantly then power on with duration
        # Use stored power state if available, otherwise fetch
        power_tuple = self.power
        if power_tuple is not None:
            is_powered_on, _ = power_tuple
        else:
            is_powered_on = await self.get_power()

        # Convert duration to milliseconds
        duration_ms = int(duration * 1000)

        # Apply duration to colors only if device is already on
        color_duration_ms = duration_ms if is_powered_on else 0

        if total_zones <= 64:
            # Single Set64 request sufficient - write directly to visible frame buffer 0
            # Pad to 64 colors
            protocol_colors = [color.to_protocol() for color in colors_flat]
            while len(protocol_colors) < 64:
                protocol_colors.append(HSBK(0, 0, 0, 3500).to_protocol())

            await self.connection.request(
                packets.Tile.Set64(
                    tile_index=tile_index,
                    length=1,
                    rect=TileBufferRect(fb_index=0, x=x, y=y, width=width),
                    duration=color_duration_ms,
                    colors=protocol_colors,
                ),
            )
        else:
            # Multiple Set64 requests needed for >64 zones
            # Write to buffer 1, then copy to buffer 0 atomically
            current_y = y
            flat_index = 0

            while flat_index < len(colors_flat):
                # Calculate how many rows we can write in this chunk (max 64 zones)
                rows_in_chunk = min((64 // width), (y + height - current_y))
                if rows_in_chunk == 0:
                    rows_in_chunk = 1  # Always write at least 1 row

                # Extract colors for this chunk
                zones_in_chunk = width * rows_in_chunk
                chunk_colors = colors_flat[flat_index : flat_index + zones_in_chunk]

                # Pad to 64 colors
                protocol_colors = [color.to_protocol() for color in chunk_colors]
                while len(protocol_colors) < 64:
                    protocol_colors.append(HSBK(0, 0, 0, 3500).to_protocol())

                # Write to frame buffer 1 (invisible) with no duration
                await self.connection.request(
                    packets.Tile.Set64(
                        tile_index=tile_index,
                        length=1,
                        rect=TileBufferRect(fb_index=1, x=x, y=current_y, width=width),
                        duration=0,
                        colors=protocol_colors,
                    ),
                )

                flat_index += zones_in_chunk
                current_y += rows_in_chunk

            # Copy from buffer 1 to buffer 0 with transition duration
            copy_duration = duration if is_powered_on else 0.0
            await self.copy_frame_buffer(
                tile_index=tile_index,
                src_fb_index=1,
                dst_fb_index=0,
                src_x=x,
                src_y=y,
                dst_x=x,
                dst_y=y,
                width=width,
                height=height,
                duration=copy_duration,
            )

        # Update tile colors with the values we just set
        import time

        timestamp = time.time()

        # Get tile chain to know dimensions
        if self._tile_chain is None:
            chain = await self.get_tile_chain()
        else:
            chain, _ = self._tile_chain

        # Get tile info for this specific tile
        tile_info = chain[tile_index]

        # Initialize or get existing colors dict
        if self._tile_colors is None:
            tiles_colors_dict = {}
        else:
            tiles_colors_dict, _ = self._tile_colors

        # Get or create TileColors for this tile
        if tile_index not in tiles_colors_dict:
            # Create new TileColors with default black colors
            num_zones = tile_info.width * tile_info.height
            default_colors = [HSBK(0, 0, 0, 3500)] * num_zones
            tiles_colors_dict[tile_index] = TileColors(
                colors=default_colors, width=tile_info.width, height=tile_info.height
            )

        tile_colors = tiles_colors_dict[tile_index]

        # Update the specific tile region with colors we just set
        for row_idx in range(height):
            for col_idx in range(width):
                tile_x = x + col_idx
                tile_y = y + row_idx
                if tile_y < tile_colors.height and tile_x < tile_colors.width:
                    tile_colors.set_color(tile_x, tile_y, colors[row_idx][col_idx])

        # Store updated colors with new timestamp
        self._tile_colors = (tiles_colors_dict, timestamp)

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_tile_colors",
                "action": "change",
                "values": {
                    "tile_index": tile_index,
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "total_zones": total_zones,
                    "duration": duration,
                },
            }
        )

        # If device was off, power it on with the specified duration
        if not is_powered_on and duration > 0:
            await self.set_power(True, duration=duration)

    async def get_tile_effect(self) -> TileEffect | None:
        """Get current tile effect.

        Always fetches from device.
        Use the `tile_effect` property to access stored value.

        Returns:
            TileEffect if an effect is active, None if no effect

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
            effect = await tile.get_tile_effect()
            if effect:
                print(f"Effect: {effect.effect_type}, Speed: {effect.speed}ms")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Tile.GetEffect())

        settings = state.settings
        effect_type = settings.effect_type

        # Extract parameters from the settings parameter field
        parameters = [
            int(settings.parameter.sky_type),
            settings.parameter.cloud_saturation_min,
            settings.parameter.cloud_saturation_max,
        ]

        # Convert palette from protocol HSBK to HSBK
        palette = [
            HSBK.from_protocol(color)
            for color in settings.palette[: settings.palette_count]
        ]

        if effect_type == TileEffectType.OFF:
            result = None
        else:
            result = TileEffect(
                effect_type=effect_type,
                speed=settings.speed,
                duration=settings.duration,
                palette=palette,
                parameters=parameters,
            )

        import time

        self._tile_effect = (result, time.time())

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_tile_effect",
                "action": "query",
                "reply": {
                    "effect_type": effect_type.name,
                    "speed": settings.speed,
                    "duration": settings.duration,
                    "palette_count": settings.palette_count,
                    "parameters": parameters,
                },
            }
        )

        return result

    async def set_tile_effect(self, effect: TileEffect) -> None:
        """Set tile effect.

        Args:
            effect: Tile effect configuration

        Raises:
            ValueError: If palette has too many colors
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

        Example:
            ```python
            # Apply a morph effect with rainbow palette
            palette = [
                HSBK(0, 1.0, 1.0, 3500),  # Red
                HSBK(60, 1.0, 1.0, 3500),  # Yellow
                HSBK(120, 1.0, 1.0, 3500),  # Green
                HSBK(240, 1.0, 1.0, 3500),  # Blue
            ]
            effect = TileEffect(
                effect_type=TileEffectType.MORPH,
                speed=5000,
                palette=palette,
            )
            await tile.set_tile_effect(effect)
            ```
        """
        palette = effect.palette or [HSBK(0, 0, 1.0, 3500)]
        if len(palette) > 16:
            raise ValueError(f"Palette too large: {len(palette)} colors (max 16)")

        # Convert palette to protocol HSBK and pad to 16
        protocol_palette = [color.to_protocol() for color in palette]

        while len(protocol_palette) < 16:
            protocol_palette.append(HSBK(0, 0, 0, 3500).to_protocol())

        # Ensure parameters list is 3 elements (sky_type, cloud_sat_min, cloud_sat_max)
        parameters = effect.parameters or [0] * 3
        if len(parameters) < 3:
            parameters.extend([0] * (3 - len(parameters)))
        parameters = parameters[:3]

        # Request automatically handles acknowledgement
        await self.connection.request(
            packets.Tile.SetEffect(
                settings=TileEffectSettings(
                    instanceid=0,  # 0 for new effect
                    effect_type=effect.effect_type,
                    speed=effect.speed,
                    duration=effect.duration,
                    parameter=TileEffectParameter(
                        sky_type=TileEffectSkyType(value=parameters[0]),
                        cloud_saturation_min=parameters[1],
                        cloud_saturation_max=parameters[2],
                    ),
                    palette_count=len(palette),
                    palette=protocol_palette,
                ),
            ),
        )

        # Update state attribute
        import time

        result = effect if effect.effect_type != TileEffectType.OFF else None
        self._tile_effect = (result, time.time())

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_tile_effect",
                "action": "change",
                "values": {
                    "effect_type": effect.effect_type.name,
                    "speed": effect.speed,
                    "duration": effect.duration,
                    "palette_count": len(palette),
                    "parameters": parameters,
                },
            }
        )

    async def stop_effect(self) -> None:
        """Stop any running tile effect.

        Example:
            ```python
            await tile.stop_effect()
            ```
        """
        await self.set_tile_effect(
            TileEffect(
                effect_type=TileEffectType.OFF,
                speed=0,
                duration=0,
            )
        )

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "stop_effect",
                "action": "change",
                "values": {},
            }
        )

    async def copy_frame_buffer(
        self,
        tile_index: int,
        src_fb_index: int = 0,
        dst_fb_index: int = 0,
        src_x: int = 0,
        src_y: int = 0,
        dst_x: int = 0,
        dst_y: int = 0,
        width: int = 8,
        height: int = 8,
        duration: float = 0.0,
    ) -> None:
        """Copy a rectangular region from one frame buffer to another.

        This allows copying pixel data between frame buffers or within the same
        frame buffer on a tile. Useful for double-buffering effects or moving
        pixel regions.

        Args:
            tile_index: Index of tile in chain (0-based)
            src_fb_index: Source frame buffer index (default 0)
            dst_fb_index: Destination frame buffer index (default 0)
            src_x: Source rectangle X coordinate (default 0)
            src_y: Source rectangle Y coordinate (default 0)
            dst_x: Destination rectangle X coordinate (default 0)
            dst_y: Destination rectangle Y coordinate (default 0)
            width: Rectangle width in zones (default 8)
            height: Rectangle height in zones (default 8)
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If parameters are invalid or out of range
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

        Example:
            ```python
            # Copy entire tile from frame buffer 0 to frame buffer 1
            await tile.copy_frame_buffer(tile_index=0, src_fb_index=0, dst_fb_index=1)

            # Copy a 4x4 region from (0,0) to (2,2) within same buffer with transition
            await tile.copy_frame_buffer(
                tile_index=0,
                src_x=0,
                src_y=0,
                dst_x=2,
                dst_y=2,
                width=4,
                height=4,
                duration=1.0,
            )
            ```
        """
        if tile_index < 0:
            raise ValueError(f"Invalid tile index: {tile_index}")
        if src_fb_index < 0 or dst_fb_index < 0:
            raise ValueError(
                f"Invalid frame buffer indices: src={src_fb_index}, dst={dst_fb_index}"
            )
        if src_x < 0 or src_y < 0 or dst_x < 0 or dst_y < 0:
            raise ValueError(
                f"Invalid coordinates: src=({src_x},{src_y}), dst=({dst_x},{dst_y})"
            )
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid dimensions: {width}x{height}")

        # Get tile info to validate dimensions
        chain = await self.get_tile_chain()
        if tile_index >= len(chain):
            raise ValueError(
                f"Tile index {tile_index} out of range (chain has {len(chain)} tiles)"
            )

        tile_info = chain[tile_index]

        # Validate source rectangle
        if src_x + width > tile_info.width or src_y + height > tile_info.height:
            raise ValueError(
                f"Source rectangle ({src_x},{src_y},{width},{height}) "
                f"exceeds tile dimensions ({tile_info.width}x{tile_info.height})"
            )

        # Validate destination rectangle
        if dst_x + width > tile_info.width or dst_y + height > tile_info.height:
            raise ValueError(
                f"Destination rectangle ({dst_x},{dst_y},{width},{height}) "
                f"exceeds tile dimensions ({tile_info.width}x{tile_info.height})"
            )

        # Convert duration to milliseconds
        duration_ms = int(duration * 1000)

        # Send copy command
        await self.connection.request(
            packets.Tile.CopyFrameBuffer(
                tile_index=tile_index,
                length=1,
                src_fb_index=src_fb_index,
                dst_fb_index=dst_fb_index,
                src_x=src_x,
                src_y=src_y,
                dst_x=dst_x,
                dst_y=dst_y,
                width=width,
                height=height,
                duration=duration_ms,
            ),
        )

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "copy_frame_buffer",
                "action": "change",
                "values": {
                    "tile_index": tile_index,
                    "src_fb_index": src_fb_index,
                    "dst_fb_index": dst_fb_index,
                    "src_x": src_x,
                    "src_y": src_y,
                    "dst_x": dst_x,
                    "dst_y": dst_y,
                    "width": width,
                    "height": height,
                    "duration": duration_ms,
                },
            }
        )

    async def set_morph_effect(
        self,
        palette: list[HSBK],
        speed: float = 5.0,
        duration: float = 0.0,
    ) -> None:
        """Apply a morph effect that transitions through a color palette.

        Args:
            palette: List of colors to morph between (2-16 colors)
            speed: Speed in seconds per cycle (default 5.0)
            duration: Total duration in seconds (0 for infinite, default 0.0)

        Raises:
            ValueError: If palette is invalid

        Example:
            ```python
            # Morph between red, green, and blue
            palette = [
                HSBK.from_rgb(255, 0, 0),
                HSBK.from_rgb(0, 255, 0),
                HSBK.from_rgb(0, 0, 255),
            ]
            await tile.set_morph_effect(palette, speed=5.0)
            ```
        """
        if len(palette) < 2:
            raise ValueError("Palette must have at least 2 colors")
        if len(palette) > 16:
            raise ValueError(f"Palette too large: {len(palette)} colors (max 16)")

        # Convert speed to milliseconds
        speed_ms = int(speed * 1000)

        # Convert duration to nanoseconds
        duration_ns = int(duration * 1_000_000_000)

        await self.set_tile_effect(
            TileEffect(
                effect_type=TileEffectType.MORPH,
                speed=speed_ms,
                duration=duration_ns,
                palette=palette,
            )
        )

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_morph_effect",
                "action": "change",
                "values": {
                    "palette_count": len(palette),
                    "speed": speed,
                    "duration": duration,
                },
            }
        )

    async def set_flame_effect(
        self,
        speed: float = 5.0,
        duration: float = 0.0,
        palette: list[HSBK] | None = None,
    ) -> None:
        """Apply a flame effect.

        Args:
            speed: Effect speed in seconds per cycle (default 5.0)
            duration: Total duration in seconds (0 for infinite, default 0.0)
            palette: Optional color palette (default: fire colors)

        Example:
            ```python
            # Apply default flame effect
            await tile.set_flame_effect()

            # Custom flame colors
            palette = [
                HSBK.from_rgb(255, 0, 0),  # Red
                HSBK.from_rgb(255, 100, 0),  # Orange
                HSBK.from_rgb(255, 200, 0),  # Yellow
            ]
            await tile.set_flame_effect(speed=3.0, palette=palette)
            ```
        """
        if palette is None:
            # Default fire palette
            palette = [
                HSBK(0, 1.0, 1.0, 3500),  # Red
                HSBK(30, 1.0, 1.0, 3500),  # Orange
                HSBK(45, 1.0, 0.8, 3500),  # Yellow-orange
            ]

        # Convert speed to milliseconds
        speed_ms = int(speed * 1000)

        # Convert duration to nanoseconds
        duration_ns = int(duration * 1_000_000_000)

        await self.set_tile_effect(
            TileEffect(
                effect_type=TileEffectType.FLAME,
                speed=speed_ms,
                duration=duration_ns,
                palette=palette,
            )
        )

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_flame_effect",
                "action": "change",
                "values": {
                    "palette_count": len(palette),
                    "speed": speed,
                    "duration": duration,
                },
            }
        )

    # Stored value properties
    @property
    def tile_chain(self) -> tuple[list[TileInfo], float] | None:
        """Get stored tile chain if available.

        Returns:
            Stored tile chain (use get_tile_chain() for fresh data)
        """
        return self._tile_chain

    @property
    def tile_count(self) -> tuple[int, float] | None:
        """Get stored tile count with timestamp if available.

        Returns:
            Tuple of (tile_count, timestamp) or None if never fetched.
            Derived from tile_chain property.
        """
        if self._tile_chain is not None:
            chain, timestamp = self._tile_chain
            return (len(chain), timestamp)
        return None

    @property
    def tile_effect(self) -> tuple[TileEffect | None, float] | None:
        """Get stored tile effect if available.

        Returns:
            Stored tile effect (use get_tile_effect() for fresh data)
        """
        return self._tile_effect

    @property
    def tile_colors(self) -> tuple[dict[int, TileColors], float] | None:
        """Get stored tile colors with timestamp if available.

        Returns:
            Tuple of (tile_colors_dict, timestamp) or None if never fetched.
            The dict maps tile_index -> TileColors(colors, width, height).
            Each TileColors contains a flat list of colors and dimensions.
            Use get_tile_colors() to fetch from device.

        Example:
            ```python
            if tile.tile_colors:
                colors_dict, timestamp = tile.tile_colors
                tile_0 = colors_dict[0]
                # Access flat list: tile_0.colors
                # Get dimensions: tile_0.width, tile_0.height
                # Get 2D array: tile_0.to_2d()
                # Get specific color: tile_0.get_color(x, y)
            ```
        """
        return self._tile_colors

    async def apply_theme(
        self,
        theme: Theme,
        power_on: bool = False,
        duration: float = 0.0,
    ) -> None:
        """Apply a theme to this tile device.

        Distributes theme colors across all tiles in the chain using Canvas-based
        rendering to create natural color splotches that grow outward.

        Args:
            theme: Theme to apply
            power_on: Turn on the device
            duration: Transition duration in seconds

        Example:
            ```python
            from lifx.theme import get_theme

            theme = get_theme("sunset")
            await tile.apply_theme(theme, power_on=True, duration=2.0)
            ```
        """
        from lifx.theme.generators import MatrixGenerator

        # Get tile dimensions
        tiles = await self.get_tile_chain()
        if not tiles:
            _LOGGER.warning("No tiles available, skipping theme application")
            return

        # Build coords_and_sizes for all tiles
        left_x = 0
        coords_and_sizes = []
        for tile in tiles:
            coords_and_sizes.append(((left_x, 0), (tile.width, tile.height)))
            left_x += tile.width

        # Create generator with all tile coordinates
        generator = MatrixGenerator(coords_and_sizes)

        # Generate colors for all tiles at once
        tile_colors_list = generator.get_theme_colors(theme)

        # Check if device is on
        is_on = await self.get_power()

        # Determine duration for color setting
        color_duration = 0 if (power_on and not is_on) else duration

        # Apply colors to each tile
        for tile_idx, colors_flat in enumerate(tile_colors_list):
            tile_info = tiles[tile_idx]

            # Convert to 2D grid for set_tile_colors
            colors_2d = []
            for y in range(tile_info.height):
                row = []
                for x in range(tile_info.width):
                    idx = y * tile_info.width + x
                    if idx < len(colors_flat):
                        row.append(colors_flat[idx])
                    else:
                        row.append(HSBK(0, 0, 1.0, 3500))  # White fallback
                colors_2d.append(row)

            # Apply colors to tile
            await self.set_tile_colors(tile_idx, colors_2d, duration=color_duration)

        # Turn on if requested
        if power_on and not is_on:
            await self.set_power(True, duration=duration)

    def __repr__(self) -> str:
        """String representation of tile device."""
        return f"TileDevice(serial={self.serial}, ip={self.ip}, port={self.port})"
