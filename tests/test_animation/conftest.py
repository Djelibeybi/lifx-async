"""Shared fixtures for animation module tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    pass


@dataclass
class MockTileInfo:
    """Mock TileInfo for testing without device dependency."""

    tile_index: int
    width: int
    height: int
    accel_meas_x: int = 0
    accel_meas_y: int = -100  # Default: right-side up
    accel_meas_z: int = 0
    user_x: float = 0.0
    user_y: float = 0.0
    supported_frame_buffers: int = 2
    device_version_vendor: int = 1
    device_version_product: int = 55
    device_version_version: int = 0
    firmware_build: int = 0
    firmware_version_minor: int = 0
    firmware_version_major: int = 3

    @property
    def total_zones(self) -> int:
        """Get total number of zones on this tile."""
        return self.width * self.height

    @property
    def requires_frame_buffer(self) -> bool:
        """Check if tile has more than 64 zones."""
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


@pytest.fixture
def mock_tile_upright() -> MockTileInfo:
    """Create a mock 8x8 tile in upright orientation."""
    return MockTileInfo(
        tile_index=0,
        width=8,
        height=8,
        accel_meas_x=0,
        accel_meas_y=-100,
        accel_meas_z=0,
    )


@pytest.fixture
def mock_tile_rotated_90() -> MockTileInfo:
    """Create a mock 8x8 tile rotated 90 degrees (RotatedRight)."""
    return MockTileInfo(
        tile_index=0,
        width=8,
        height=8,
        accel_meas_x=100,  # Positive X = RotatedRight
        accel_meas_y=0,
        accel_meas_z=0,
    )


@pytest.fixture
def mock_tile_rotated_180() -> MockTileInfo:
    """Create a mock 8x8 tile rotated 180 degrees (UpsideDown)."""
    return MockTileInfo(
        tile_index=0,
        width=8,
        height=8,
        accel_meas_x=0,
        accel_meas_y=100,  # Positive Y = UpsideDown
        accel_meas_z=0,
    )


@pytest.fixture
def mock_tile_rotated_270() -> MockTileInfo:
    """Create a mock 8x8 tile rotated 270 degrees (RotatedLeft)."""
    return MockTileInfo(
        tile_index=0,
        width=8,
        height=8,
        accel_meas_x=-100,  # Negative X = RotatedLeft
        accel_meas_y=0,
        accel_meas_z=0,
    )


@pytest.fixture
def mock_tile_chain() -> list[MockTileInfo]:
    """Create a mock chain of 3 tiles with different orientations."""
    return [
        MockTileInfo(
            tile_index=0,
            width=8,
            height=8,
            accel_meas_x=0,
            accel_meas_y=-100,  # Upright
            accel_meas_z=0,
        ),
        MockTileInfo(
            tile_index=1,
            width=8,
            height=8,
            accel_meas_x=100,  # RotatedRight
            accel_meas_y=0,
            accel_meas_z=0,
        ),
        MockTileInfo(
            tile_index=2,
            width=8,
            height=8,
            accel_meas_x=0,
            accel_meas_y=100,  # UpsideDown
            accel_meas_z=0,
        ),
    ]


@pytest.fixture
def mock_multizone_device() -> MagicMock:
    """Create a mock MultiZoneLight device."""
    device = MagicMock()
    device.capabilities = MagicMock()
    device.capabilities.has_extended_multizone = True
    device._zone_count = 82
    return device


@pytest.fixture
def mock_matrix_device() -> MagicMock:
    """Create a mock MatrixLight device."""
    device = MagicMock()
    device._device_chain = [
        MockTileInfo(tile_index=0, width=8, height=8),
    ]
    return device
