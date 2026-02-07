"""Tests for FrameBuffer orientation mapping."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.animation.framebuffer import FrameBuffer, TileRegion


class TestFrameBuffer:
    """Tests for FrameBuffer class."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        fb = FrameBuffer(pixel_count=64)
        assert fb.pixel_count == 64
        assert fb.canvas_width == 64
        assert fb.canvas_height == 1

    def test_init_with_canvas_dimensions(self) -> None:
        """Test initialization with canvas dimensions."""
        fb = FrameBuffer(pixel_count=64, canvas_width=8, canvas_height=8)
        assert fb.pixel_count == 64
        assert fb.canvas_width == 8
        assert fb.canvas_height == 8
        assert fb.canvas_size == 64

    def test_init_invalid_pixel_count(self) -> None:
        """Test that negative pixel count raises error."""
        with pytest.raises(ValueError, match="non-negative"):
            FrameBuffer(pixel_count=-1)

    def test_apply_passthrough(self) -> None:
        """Test apply returns copy of data (passthrough mode)."""
        fb = FrameBuffer(pixel_count=4)
        data: list[tuple[int, int, int, int]] = [
            (100, 100, 100, 3500),
            (200, 200, 200, 3500),
            (300, 300, 300, 3500),
            (400, 400, 400, 3500),
        ]

        result = fb.apply(data)

        assert result == data
        assert result is not data  # Should be a copy

    def test_apply_invalid_length(self) -> None:
        """Test that wrong data length raises error."""
        fb = FrameBuffer(pixel_count=64)
        data: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 32

        with pytest.raises(ValueError, match="must match pixel_count"):
            fb.apply(data)


class TestFrameBufferClassMethods:
    """Tests for FrameBuffer class methods."""

    @pytest.mark.asyncio
    async def test_for_matrix_no_chain(self) -> None:
        """Test for_matrix raises error when device has no chain."""
        device = MagicMock()
        device.device_chain = []
        device.get_device_chain = AsyncMock(return_value=[])

        with pytest.raises(ValueError, match="no tiles"):
            await FrameBuffer.for_matrix(device)

    @pytest.mark.asyncio
    async def test_for_matrix_fetches_chain_when_none(self, mock_tile_upright) -> None:
        """Test for_matrix fetches device chain if not already loaded."""
        device = MagicMock()
        device.device_chain = None  # Not loaded yet
        device.capabilities = MagicMock()
        device.capabilities.has_chain = False

        # get_device_chain should be called and populate device_chain
        async def mock_get_device_chain() -> list:
            device.device_chain = [mock_tile_upright]
            return [mock_tile_upright]

        device.get_device_chain = mock_get_device_chain

        fb = await FrameBuffer.for_matrix(device)

        assert fb.pixel_count == 64

    @pytest.mark.asyncio
    async def test_for_matrix_single_tile_with_chain_capability(
        self, mock_tile_upright
    ) -> None:
        """Test for_matrix with single tile and chain capability (LIFX Tile).

        Devices with chain capability support accelerometer-based orientation
        detection, so permutation should be built.
        """
        device = MagicMock()
        device.device_chain = [mock_tile_upright]
        device.get_device_chain = AsyncMock(return_value=[mock_tile_upright])
        # LIFX Tile has chain capability
        device.capabilities = MagicMock()
        device.capabilities.has_chain = True

        fb = await FrameBuffer.for_matrix(device)

        # Multi-tile mode uses tile_regions instead of permutation
        assert fb.canvas_size == 64  # 8x8 canvas
        assert fb.canvas_width == 8
        assert fb.canvas_height == 8
        assert fb.tile_regions is not None
        assert len(fb.tile_regions) == 1

    @pytest.mark.asyncio
    async def test_for_matrix_single_tile_without_chain_capability(
        self, mock_tile_upright
    ) -> None:
        """Test for_matrix with single tile but no chain capability.

        Devices without chain capability don't have accelerometer-based orientation
        detection, so tile_regions should be None (passthrough mode).
        """
        device = MagicMock()
        device.device_chain = [mock_tile_upright]
        device.get_device_chain = AsyncMock(return_value=[mock_tile_upright])
        # Luna, Candle, Path, etc. don't have chain capability
        device.capabilities = MagicMock()
        device.capabilities.has_chain = False

        fb = await FrameBuffer.for_matrix(device)

        assert fb.pixel_count == 64  # 8x8 tile
        assert fb.canvas_width == 8
        assert fb.canvas_height == 8
        assert fb.tile_regions is None  # No tile regions for non-chain devices

    @pytest.mark.asyncio
    async def test_for_matrix_loads_capabilities_when_none(
        self, mock_tile_upright
    ) -> None:
        """Test for_matrix calls _ensure_capabilities when None.

        If capabilities haven't been fetched, we should load them first.
        """
        device = MagicMock()
        device.device_chain = [mock_tile_upright]
        device.get_device_chain = AsyncMock(return_value=[mock_tile_upright])
        device.capabilities = None

        # Mock _ensure_capabilities to set capabilities without has_chain
        async def set_capabilities() -> None:
            device.capabilities = MagicMock()
            device.capabilities.has_chain = False

        device._ensure_capabilities = AsyncMock(side_effect=set_capabilities)

        fb = await FrameBuffer.for_matrix(device)

        # Verify _ensure_capabilities was called
        device._ensure_capabilities.assert_called_once()
        # Without has_chain, should use passthrough mode
        assert fb.pixel_count == 64
        assert fb.tile_regions is None

    @pytest.mark.asyncio
    async def test_for_multizone(self) -> None:
        """Test for_multizone creates correct framebuffer."""
        device = MagicMock()
        device.get_zone_count = AsyncMock(return_value=82)

        fb = await FrameBuffer.for_multizone(device)

        assert fb.pixel_count == 82
        assert fb.canvas_width == 82
        assert fb.canvas_height == 1
        assert fb.tile_regions is None  # No tile regions for multizone


class TestFrameBufferMultiTileCanvas:
    """Tests for multi-tile canvas functionality."""

    def test_tile_region_dataclass(self) -> None:
        """Test TileRegion dataclass."""
        lut = tuple(range(64))
        region = TileRegion(x=8, y=0, width=8, height=8, orientation_lut=lut)

        assert region.x == 8
        assert region.y == 0
        assert region.width == 8
        assert region.height == 8
        assert region.orientation_lut == lut

    def test_init_with_tile_regions(self) -> None:
        """Test initialization with tile regions."""
        regions = [
            TileRegion(x=0, y=0, width=8, height=8),
            TileRegion(x=8, y=0, width=8, height=8),
        ]
        fb = FrameBuffer(
            pixel_count=128,  # 2 tiles * 64 pixels
            canvas_width=16,
            canvas_height=8,
            tile_regions=regions,
        )

        assert fb.canvas_width == 16
        assert fb.canvas_height == 8
        assert fb.canvas_size == 128
        assert fb.tile_regions == regions

    def test_apply_canvas_two_tiles_horizontal(self) -> None:
        """Test applying canvas to two horizontally arranged tiles."""
        # Two 4x2 tiles arranged horizontally
        # Tile 0: canvas[0:4, 0:2]
        # Tile 1: canvas[4:8, 0:2]
        regions = [
            TileRegion(x=0, y=0, width=4, height=2),
            TileRegion(x=4, y=0, width=4, height=2),
        ]
        fb = FrameBuffer(
            pixel_count=16,  # 2 tiles * 8 pixels
            canvas_width=8,
            canvas_height=2,
            tile_regions=regions,
        )

        # Canvas: 8x2 grid, row-major
        # Row 0: 0 1 2 3 | 4 5 6 7
        # Row 1: 8 9 10 11 | 12 13 14 15
        canvas: list[tuple[int, int, int, int]] = [
            (i * 1000, 0, 0, 3500) for i in range(16)
        ]

        result = fb.apply(canvas)

        # Expected: Tile 0 gets [0,1,2,3,8,9,10,11], Tile 1 gets [4,5,6,7,12,13,14,15]
        assert len(result) == 16

        # Tile 0 (first 8 pixels)
        assert result[0] == (0, 0, 0, 3500)  # canvas[0,0]
        assert result[1] == (1000, 0, 0, 3500)  # canvas[1,0]
        assert result[2] == (2000, 0, 0, 3500)  # canvas[2,0]
        assert result[3] == (3000, 0, 0, 3500)  # canvas[3,0]
        assert result[4] == (8000, 0, 0, 3500)  # canvas[0,1]
        assert result[5] == (9000, 0, 0, 3500)  # canvas[1,1]
        assert result[6] == (10000, 0, 0, 3500)  # canvas[2,1]
        assert result[7] == (11000, 0, 0, 3500)  # canvas[3,1]

        # Tile 1 (next 8 pixels)
        assert result[8] == (4000, 0, 0, 3500)  # canvas[4,0]
        assert result[9] == (5000, 0, 0, 3500)  # canvas[5,0]
        assert result[10] == (6000, 0, 0, 3500)  # canvas[6,0]
        assert result[11] == (7000, 0, 0, 3500)  # canvas[7,0]
        assert result[12] == (12000, 0, 0, 3500)  # canvas[4,1]
        assert result[13] == (13000, 0, 0, 3500)  # canvas[5,1]
        assert result[14] == (14000, 0, 0, 3500)  # canvas[6,1]
        assert result[15] == (15000, 0, 0, 3500)  # canvas[7,1]

    def test_apply_canvas_with_orientation(self) -> None:
        """Test applying canvas with tile orientation."""
        # Single 2x2 tile with 180 degree rotation
        # LUT for 180 rotation: [3, 2, 1, 0]
        lut = (3, 2, 1, 0)
        regions = [TileRegion(x=0, y=0, width=2, height=2, orientation_lut=lut)]
        fb = FrameBuffer(
            pixel_count=4,
            canvas_width=2,
            canvas_height=2,
            tile_regions=regions,
        )

        # Canvas:
        # 0 1
        # 2 3
        canvas: list[tuple[int, int, int, int]] = [
            (0, 0, 0, 3500),
            (1000, 0, 0, 3500),
            (2000, 0, 0, 3500),
            (3000, 0, 0, 3500),
        ]

        result = fb.apply(canvas)

        # After 180 rotation, output should be:
        # Position 0 gets canvas[lut[0]] = canvas[3]
        # Position 1 gets canvas[lut[1]] = canvas[2]
        # etc.
        assert result[0] == (3000, 0, 0, 3500)
        assert result[1] == (2000, 0, 0, 3500)
        assert result[2] == (1000, 0, 0, 3500)
        assert result[3] == (0, 0, 0, 3500)

    def test_apply_canvas_wrong_length_raises(self) -> None:
        """Test that wrong canvas length raises error."""
        regions = [TileRegion(x=0, y=0, width=8, height=8)]
        fb = FrameBuffer(
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
            tile_regions=regions,
        )

        wrong_length: list[tuple[int, int, int, int]] = [(0, 0, 0, 3500)] * 32

        with pytest.raises(ValueError, match="must match canvas_size"):
            fb.apply(wrong_length)

    @pytest.mark.asyncio
    async def test_for_matrix_multi_tile_chain(self) -> None:
        """Test for_matrix with multiple tiles creates canvas."""
        # Create 3 tiles arranged horizontally
        tile1 = MagicMock()
        tile1.width = 8
        tile1.height = 8
        tile1.user_x = 0.0
        tile1.user_y = 0.0
        tile1.nearest_orientation = "Upright"

        tile2 = MagicMock()
        tile2.width = 8
        tile2.height = 8
        tile2.user_x = 1.0  # 1 tile width to the right
        tile2.user_y = 0.0
        tile2.nearest_orientation = "Upright"

        tile3 = MagicMock()
        tile3.width = 8
        tile3.height = 8
        tile3.user_x = 2.0  # 2 tile widths to the right
        tile3.user_y = 0.0
        tile3.nearest_orientation = "Upright"

        device = MagicMock()
        device.device_chain = [tile1, tile2, tile3]
        device.get_device_chain = AsyncMock(return_value=[tile1, tile2, tile3])
        device.capabilities = MagicMock()
        device.capabilities.has_chain = True

        fb = await FrameBuffer.for_matrix(device)

        # Canvas should span all 3 tiles horizontally
        assert fb.canvas_width == 24  # 3 * 8
        assert fb.canvas_height == 8
        assert fb.canvas_size == 192  # 24 * 8
        assert fb.tile_regions is not None
        assert len(fb.tile_regions) == 3

        # Check tile positions
        assert fb.tile_regions[0].x == 0
        assert fb.tile_regions[1].x == 8
        assert fb.tile_regions[2].x == 16

    @pytest.mark.asyncio
    async def test_for_matrix_five_tile_chain(self) -> None:
        """Test for_matrix with 5 tiles (original LIFX Tile configuration)."""
        tiles = []
        for i in range(5):
            tile = MagicMock()
            tile.width = 8
            tile.height = 8
            tile.user_x = float(i)  # 0.0, 1.0, 2.0, 3.0, 4.0
            tile.user_y = 0.0
            tile.nearest_orientation = "Upright"
            tiles.append(tile)

        device = MagicMock()
        device.device_chain = tiles
        device.get_device_chain = AsyncMock(return_value=tiles)
        device.capabilities = MagicMock()
        device.capabilities.has_chain = True

        fb = await FrameBuffer.for_matrix(device)

        assert fb.canvas_width == 40  # 5 * 8
        assert fb.canvas_height == 8
        assert fb.canvas_size == 320  # 40 * 8
        assert fb.tile_regions is not None
        assert len(fb.tile_regions) == 5


class TestFrameBufferForLight:
    """Tests for FrameBuffer.for_light() factory method."""

    def test_for_light_pixel_count(self) -> None:
        """Test for_light creates framebuffer with pixel_count=1."""
        device = MagicMock()
        fb = FrameBuffer.for_light(device)
        assert fb.pixel_count == 1

    def test_for_light_canvas_dimensions(self) -> None:
        """Test for_light creates 1x1 canvas."""
        device = MagicMock()
        fb = FrameBuffer.for_light(device)
        assert fb.canvas_width == 1
        assert fb.canvas_height == 1
        assert fb.canvas_size == 1

    def test_for_light_no_tile_regions(self) -> None:
        """Test for_light has no tile regions (passthrough)."""
        device = MagicMock()
        fb = FrameBuffer.for_light(device)
        assert fb.tile_regions is None

    def test_for_light_apply_passthrough(self) -> None:
        """Test for_light apply is passthrough for single pixel."""
        device = MagicMock()
        fb = FrameBuffer.for_light(device)
        data: list[tuple[int, int, int, int]] = [(65535, 32768, 16384, 3500)]
        result = fb.apply(data)
        assert result == data
