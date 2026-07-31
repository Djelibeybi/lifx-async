"""Shared fixtures for theme tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.devices.base import DeviceVersion
from lifx.devices.ceiling import CeilingLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight, TileInfo
from lifx.devices.multizone import MultiZoneLight
from lifx.products import get_product


def make_tile(
    tile_index: int = 0,
    *,
    user_x: float = 0.0,
    user_y: float = 0.0,
    width: int = 8,
    height: int = 8,
    accel: tuple[int, int, int] = (0, 0, 0),
) -> TileInfo:
    """Build a TileInfo with the geometry fields that matter for theming.

    Args:
        tile_index: Index of the tile in the chain
        user_x: Reported horizontal position, in tile-position units
        user_y: Reported vertical position, in tile-position units
        width: Tile width in pixels
        height: Tile height in pixels
        accel: Accelerometer reading (x, y, z), which decides
            ``nearest_orientation``. The default reads as Upright;
            ``(1, 0, 0)`` reads as RotatedRight.
    """
    return TileInfo(
        tile_index=tile_index,
        accel_meas_x=accel[0],
        accel_meas_y=accel[1],
        accel_meas_z=accel[2],
        user_x=user_x,
        user_y=user_y,
        width=width,
        height=height,
        supported_frame_buffers=2,
        device_version_vendor=1,
        device_version_product=27,
        device_version_version=0,
        firmware_build=1234567890,
        firmware_version_minor=50,
        firmware_version_major=3,
    )


@pytest.fixture
def mock_device_factory():
    """Factory for creating devices with mocked connections.

    This is imported from test_devices but redefined here to avoid
    pytest_plugins duplication issues.
    """

    def _create_device(
        device_class: type,
        serial: str = "d073d5010203",
        ip: str = "192.168.1.100",
        port: int = 56700,
        product: int = 27,
    ):
        device = device_class(serial=serial, ip=ip, port=port)
        # Replace device's connection with mock
        mock_conn = MagicMock()
        mock_conn.request = AsyncMock()
        mock_conn.request_ack = AsyncMock()
        device.connection = mock_conn
        device._version = DeviceVersion(vendor=1, product=product)
        # A connected device populates this from the registry during setup;
        # set it directly so capability checks do not hit the mocked connection.
        device._capabilities = get_product(product)
        return device

    return _create_device


@pytest.fixture
def light(mock_device_factory) -> Light:
    """Create a test light with mocked theme methods."""
    light = mock_device_factory(Light)
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()
    light.get_power = AsyncMock(return_value=False)
    return light


@pytest.fixture
def multizone_light(mock_device_factory) -> MultiZoneLight:
    """Create a test multizone light with mocked theme methods.

    Product 32 is a LIFX Z with extended multizone, so apply_theme takes the
    SetExtendedColorZones path.
    """
    light = mock_device_factory(MultiZoneLight, product=32)
    light.set_color = AsyncMock()
    light.set_extended_color_zones = AsyncMock()
    light.set_power = AsyncMock()
    light.get_power = AsyncMock(return_value=False)
    light.get_zone_count = AsyncMock(return_value=8)
    return light


@pytest.fixture
def matrix_light(mock_device_factory) -> MatrixLight:
    """Create a test matrix light with mocked theme methods."""
    device = mock_device_factory(MatrixLight)
    device.set_color = AsyncMock()
    device.set_matrix_colors = AsyncMock()
    device.set_power = AsyncMock()
    device.get_power = AsyncMock(return_value=False)
    device.get_device_chain = AsyncMock(return_value=[])
    return device


@pytest.fixture
def tile_light(mock_device_factory) -> MatrixLight:
    """Create a test LIFX Tile with mocked theme methods.

    Product 55 is the only chain-capable product and the only one with an
    accelerometer, so it is the only device whose reported orientation is real.
    """
    device = mock_device_factory(MatrixLight, product=55)
    device.set_color = AsyncMock()
    device.set_matrix_colors = AsyncMock()
    device.set_power = AsyncMock()
    device.get_power = AsyncMock(return_value=False)
    device.get_device_chain = AsyncMock(return_value=[])
    return device


@pytest.fixture
def ceiling_light(mock_device_factory) -> CeilingLight:
    """Create a test ceiling light with mocked theme methods.

    Product 201 is a LIFX Ceiling, which reports a single 16x8 tile covering
    both the downlight pixels and the uplight zone.
    """
    device = mock_device_factory(CeilingLight, product=201)
    device.set_color = AsyncMock()
    device.set_matrix_colors = AsyncMock()
    device.set_power = AsyncMock()
    device.get_power = AsyncMock(return_value=False)
    device.get_device_chain = AsyncMock(return_value=[])
    return device
