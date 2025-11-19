"""Shared fixtures for theme tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.devices.base import DeviceVersion
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight


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
    ):
        device = device_class(serial=serial, ip=ip, port=port)
        # Replace device's connection with mock
        mock_conn = MagicMock()
        mock_conn.request = AsyncMock()
        mock_conn.request_ack = AsyncMock()
        device.connection = mock_conn
        device._version = DeviceVersion(vendor=1, product=27)
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
    """Create a test multizone light with mocked theme methods."""
    light = mock_device_factory(MultiZoneLight)
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
