"""Orientation mapping for LIFX matrix device animations.

This module provides the FrameBuffer class, which handles pixel coordinate
remapping for matrix devices based on tile orientation. For animations,
every frame is assumed to change all pixels, so no diff tracking is performed.

Multi-Tile Canvas Support:
    For devices with multiple tiles (e.g., original LIFX Tile with 5 tiles),
    the FrameBuffer creates a unified canvas based on tile positions (user_x,
    user_y). The user provides colors for the entire canvas, and the FrameBuffer
    extracts the appropriate region for each tile.

    Example with 5 tiles arranged horizontally:
        - Canvas dimensions: 40x8 (5 tiles * 8 pixels wide)
        - User provides 320 HSBK tuples (40*8)
        - FrameBuffer extracts 64 pixels for each tile based on position

Design Philosophy:
    Colors are "protocol-ready" HSBK tuples - uint16 values matching the LIFX
    protocol (0-65535 for H/S/B, 1500-9000 for K).

Example:
    ```python
    from lifx.animation.framebuffer import FrameBuffer

    # Create framebuffer for a matrix device
    fb = await FrameBuffer.for_matrix(matrix_device)

    # For multi-tile devices, check canvas dimensions
    print(f"Canvas: {fb.canvas_width}x{fb.canvas_height}")  # e.g., 40x8

    # Provide colors for the entire canvas
    canvas_colors = [(65535, 65535, 65535, 3500)] * (fb.canvas_width * fb.canvas_height)
    device_order_data = fb.apply(canvas_colors)
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lifx.devices.matrix import MatrixLight, TileInfo
    from lifx.devices.multizone import MultiZoneLight


@dataclass(frozen=True)
class TileRegion:
    """Region of a tile within the canvas.

    Attributes:
        x: X offset in canvas coordinates
        y: Y offset in canvas coordinates
        width: Tile width in pixels
        height: Tile height in pixels
        orientation_lut: Lookup table for orientation remapping (optional)
    """

    x: int
    y: int
    width: int
    height: int
    orientation_lut: tuple[int, ...] | None = None


class FrameBuffer:
    """Orientation mapping for matrix device animations.

    For matrix devices with tile orientation (like the original LIFX Tile),
    this class remaps pixel coordinates from user-space (logical layout) to
    device-space (physical tile order accounting for rotation).

    For multi-tile devices, the FrameBuffer creates a unified canvas where
    each tile's position (user_x, user_y) determines which region of the
    canvas it displays. This allows animations to span across all tiles
    instead of being mirrored.

    For multizone devices and matrix devices without orientation, this is
    essentially a passthrough.

    Attributes:
        pixel_count: Total number of device pixels
        canvas_width: Width of the logical canvas in pixels
        canvas_height: Height of the logical canvas in pixels
        tile_regions: List of tile regions with positions and orientations

    Example:
        ```python
        # Create for a device
        fb = await FrameBuffer.for_matrix(matrix_device)

        # Check canvas dimensions
        print(f"Canvas: {fb.canvas_width}x{fb.canvas_height}")

        # Provide canvas-sized input
        canvas = [(0, 0, 65535, 3500)] * (fb.canvas_width * fb.canvas_height)
        device_data = fb.apply(canvas)
        ```
    """

    def __init__(
        self,
        pixel_count: int,
        canvas_width: int = 0,
        canvas_height: int = 0,
        tile_regions: list[TileRegion] | None = None,
    ) -> None:
        """Initialize framebuffer.

        Args:
            pixel_count: Total number of device pixels
            canvas_width: Width of the logical canvas (0 = same as pixel_count)
            canvas_height: Height of the logical canvas (0 = 1 for linear)
            tile_regions: List of tile regions with positions and orientations.
                         If provided, input is interpreted as a 2D canvas.
        """
        if pixel_count < 0:
            raise ValueError(f"pixel_count must be non-negative, got {pixel_count}")

        self._pixel_count = pixel_count
        self._tile_regions = tile_regions

        # Canvas dimensions
        if tile_regions:
            # Calculate from tile regions
            self._canvas_width = canvas_width
            self._canvas_height = canvas_height
        else:
            # Linear (multizone) or single tile
            self._canvas_width = canvas_width if canvas_width > 0 else pixel_count
            self._canvas_height = canvas_height if canvas_height > 0 else 1

    @classmethod
    async def for_matrix(
        cls,
        device: MatrixLight,
    ) -> FrameBuffer:
        """Create a FrameBuffer configured for a MatrixLight device.

        Automatically determines pixel count from device chain and creates
        appropriate mapping for tile orientations and positions.

        For multi-tile devices (has_chain capability), creates a unified canvas
        based on tile positions (user_x, user_y). Each tile's position determines
        which region of the canvas it displays, allowing animations to span
        across all tiles.

        Args:
            device: MatrixLight device (must be connected)

        Returns:
            Configured FrameBuffer instance

        Example:
            ```python
            async with await MatrixLight.from_ip("192.168.1.100") as matrix:
                fb = await FrameBuffer.for_matrix(matrix)
                print(f"Canvas: {fb.canvas_width}x{fb.canvas_height}")
            ```
        """
        # Ensure device chain is loaded
        if device.device_chain is None:
            await device.get_device_chain()

        tiles = device.device_chain
        if not tiles:
            raise ValueError("Device has no tiles")

        # Calculate total device pixels
        pixel_count = sum(t.width * t.height for t in tiles)

        # Only build canvas mapping for devices with chain capability.
        # The original LIFX Tile is the only matrix device with accelerometer-based
        # orientation detection and multi-tile positioning. Other matrix devices
        # (Ceiling, Luna, Candle, Path, etc.) have fixed positions.
        if device.capabilities and device.capabilities.has_chain:
            return cls._for_multi_tile(tiles, pixel_count)
        else:
            # Single tile device - simple passthrough
            first_tile = tiles[0]
            return cls(
                pixel_count=pixel_count,
                canvas_width=first_tile.width,
                canvas_height=first_tile.height,
            )

    @classmethod
    def _for_multi_tile(
        cls,
        tiles: list[TileInfo],
        pixel_count: int,
    ) -> FrameBuffer:
        """Create FrameBuffer for multi-tile device with canvas positioning.

        Uses user_x/user_y to determine where each tile sits in the canvas.
        Coordinates are in tile-width units (1.0 = one tile width) and
        represent the center of each tile.
        """
        from lifx.animation.orientation import Orientation, build_orientation_lut

        if not tiles:  # pragma: no cover
            raise ValueError("No tiles provided")

        first_tile = tiles[0]
        tile_width = first_tile.width
        tile_height = first_tile.height

        # Convert tile center positions to pixel coordinates
        # user_x/user_y are in "tile width" units, representing tile centers
        tile_centers = [
            (int(round(t.user_x * tile_width)), int(round(t.user_y * tile_height)))
            for t in tiles
        ]

        # Calculate bounding box of all tile centers
        min_cx = min(c[0] for c in tile_centers)
        max_cx = max(c[0] for c in tile_centers)
        min_cy = min(c[1] for c in tile_centers)
        max_cy = max(c[1] for c in tile_centers)

        # Canvas extends from leftmost tile left edge to rightmost tile right edge
        # Since centers are at tile_width/2 from edges:
        # - Left edge of leftmost tile: min_cx - tile_width/2
        # - Right edge of rightmost tile: max_cx + tile_width/2
        # Total width = (max_cx - min_cx) + tile_width
        canvas_width = (max_cx - min_cx) + tile_width
        canvas_height = (max_cy - min_cy) + tile_height

        # Origin offset (to convert tile centers to top-left positions)
        origin_x = min_cx - tile_width // 2
        origin_y = min_cy - tile_height // 2

        # Build tile regions with canvas-relative positions
        tile_regions: list[TileRegion] = []
        for tile, (cx, cy) in zip(tiles, tile_centers, strict=True):
            # Convert center to top-left, relative to canvas origin
            x = cx - tile_width // 2 - origin_x
            y = cy - tile_height // 2 - origin_y

            # Build orientation LUT for this tile
            orientation = Orientation.from_string(tile.nearest_orientation)
            lut = build_orientation_lut(tile_width, tile_height, orientation)

            tile_regions.append(
                TileRegion(
                    x=x,
                    y=y,
                    width=tile_width,
                    height=tile_height,
                    orientation_lut=lut,
                )
            )

        return cls(
            pixel_count=pixel_count,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            tile_regions=tile_regions,
        )

    @classmethod
    async def for_multizone(
        cls,
        device: MultiZoneLight,
    ) -> FrameBuffer:
        """Create a FrameBuffer configured for a MultiZoneLight device.

        Automatically determines pixel count from zone count.
        Multizone devices don't need permutation (zones are linear).

        Args:
            device: MultiZoneLight device (must be connected)

        Returns:
            Configured FrameBuffer instance

        Example:
            ```python
            async with await MultiZoneLight.from_ip("192.168.1.100") as strip:
                fb = await FrameBuffer.for_multizone(strip)
            ```
        """
        # Get zone count (fetches from device if not cached)
        zone_count = await device.get_zone_count()

        return cls(pixel_count=zone_count)

    @property
    def pixel_count(self) -> int:
        """Get total number of device pixels."""
        return self._pixel_count

    @property
    def canvas_width(self) -> int:
        """Get width of the logical canvas in pixels."""
        return self._canvas_width

    @property
    def canvas_height(self) -> int:
        """Get height of the logical canvas in pixels."""
        return self._canvas_height

    @property
    def canvas_size(self) -> int:
        """Get total number of canvas pixels (width * height)."""
        return self._canvas_width * self._canvas_height

    @property
    def tile_regions(self) -> list[TileRegion] | None:
        """Get tile regions if configured."""
        return self._tile_regions

    def apply(
        self, hsbk: list[tuple[int, int, int, int]]
    ) -> list[tuple[int, int, int, int]]:
        """Apply orientation mapping to frame data.

        For multi-tile devices, the input is interpreted as a row-major 2D
        canvas of size (canvas_width x canvas_height). Each tile extracts
        its region from the canvas based on its position.

        For single-tile or multizone devices, this is a passthrough.

        Args:
            hsbk: List of protocol-ready HSBK tuples.
                  - For multi-tile: length must match canvas_size
                  - For single-tile/multizone: length must match pixel_count
                  Each tuple is (hue, sat, brightness, kelvin) where
                  H/S/B are 0-65535 and K is 1500-9000.

        Returns:
            Remapped HSBK data in device order

        Raises:
            ValueError: If hsbk length doesn't match expected size
        """
        # Multi-tile canvas mode
        if self._tile_regions:
            expected_size = self._canvas_width * self._canvas_height
            if len(hsbk) != expected_size:
                raise ValueError(
                    f"HSBK length ({len(hsbk)}) must match "
                    f"canvas_size ({expected_size})"
                )
            return self._apply_canvas(hsbk)

        # Single-tile or multizone mode (passthrough)
        if len(hsbk) != self._pixel_count:
            raise ValueError(
                f"HSBK length ({len(hsbk)}) must match "
                f"pixel_count ({self._pixel_count})"
            )

        return list(hsbk)

    def _apply_canvas(
        self, hsbk: list[tuple[int, int, int, int]]
    ) -> list[tuple[int, int, int, int]]:
        """Extract tile regions from canvas and apply orientation.

        Args:
            hsbk: Row-major canvas data (canvas_width x canvas_height)

        Returns:
            Device-ordered pixels (concatenated tiles)
        """
        result: list[tuple[int, int, int, int]] = []
        canvas_width = self._canvas_width

        for region in self._tile_regions:  # type: ignore[union-attr]
            # Extract pixels for this tile from the canvas
            tile_pixels: list[tuple[int, int, int, int]] = []

            for row in range(region.height):
                canvas_y = region.y + row
                for col in range(region.width):
                    canvas_x = region.x + col
                    canvas_idx = canvas_y * canvas_width + canvas_x
                    tile_pixels.append(hsbk[canvas_idx])

            # Apply orientation remapping for this tile
            if region.orientation_lut:
                tile_pixels = [
                    tile_pixels[region.orientation_lut[i]]
                    for i in range(len(tile_pixels))
                ]

            result.extend(tile_pixels)

        return result
