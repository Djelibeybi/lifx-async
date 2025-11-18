"""Shared fixtures for device tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.devices.base import Device, FirmwareInfo
from lifx.devices.hev import HevLight
from lifx.devices.infrared import InfraredLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.products.registry import ProductCapability, ProductInfo, TemperatureRange


@pytest.fixture
def mock_device_factory():
    """Factory for creating devices with mocked connections.

    Usage:
        def test_something(mock_device_factory):
            device = mock_device_factory(Light)
            # or with custom params:
            device = mock_device_factory(Light, serial="d073d5abcdef")
    """

    def _create_device(
        device_class: type[Device],
        serial: str = "d073d5010203",
        ip: str = "192.168.1.100",
        port: int = 56700,
    ) -> Device:
        device = device_class(serial=serial, ip=ip, port=port)
        # Replace device's connection with mock
        mock_conn = MagicMock()
        mock_conn.request = AsyncMock()
        mock_conn.request_ack = AsyncMock()
        device.connection = mock_conn
        return device

    return _create_device


@pytest.fixture
def device(mock_device_factory) -> Device:
    """Create a test device with mocked connection."""
    return mock_device_factory(Device)


@pytest.fixture
def light(mock_device_factory) -> Light:
    """Create a test light with mocked connection."""
    return mock_device_factory(Light)


@pytest.fixture
def multizone_light(mock_device_factory) -> MultiZoneLight:
    """Create a test multizone light with mocked connection."""
    return mock_device_factory(MultiZoneLight)


@pytest.fixture
def matrix_light(mock_device_factory) -> MatrixLight:
    """Create a test matrix light with mocked connection."""
    return mock_device_factory(MatrixLight)


@pytest.fixture
def hev_light(mock_device_factory) -> HevLight:
    """Create a test HEV light with mocked connection."""
    return mock_device_factory(HevLight)


@pytest.fixture
def infrared_light(mock_device_factory) -> InfraredLight:
    """Create a test infrared light with mocked connection."""
    return mock_device_factory(InfraredLight)


@pytest.fixture
def mock_product_info():
    """Factory for creating mock ProductInfo objects.

    Usage:
        def test_something(mock_product_info):
            info = mock_product_info(has_multizone=True, has_extended_multizone=True)
    """

    def _create_product_info(
        pid: int = 32,
        name: str = "Test LIFX Device",
        vendor: int = 1,
        has_color: bool = True,
        has_multizone: bool = True,
        has_extended_multizone: bool = False,
        min_ext_mz_firmware: int | None = None,
        has_matrix: bool = False,
        has_infrared: bool = False,
        has_hev: bool = False,
    ) -> ProductInfo:
        """Create a mock ProductInfo with specified capabilities."""
        capabilities = 0
        if has_color:
            capabilities |= ProductCapability.COLOR
        if has_multizone:
            capabilities |= ProductCapability.MULTIZONE
        if has_extended_multizone:
            capabilities |= ProductCapability.EXTENDED_MULTIZONE
        if has_matrix:
            capabilities |= ProductCapability.MATRIX
        if has_infrared:
            capabilities |= ProductCapability.INFRARED
        if has_hev:
            capabilities |= ProductCapability.HEV

        return ProductInfo(
            pid=pid,
            name=name,
            vendor=vendor,
            capabilities=capabilities,
            temperature_range=TemperatureRange(min=1500, max=9000),
            min_ext_mz_firmware=min_ext_mz_firmware,
        )

    return _create_product_info


@pytest.fixture
def mock_firmware_info():
    """Factory for creating mock FirmwareInfo objects.

    Usage:
        def test_something(mock_firmware_info):
            firmware = mock_firmware_info(major=2, minor=80)
    """

    def _create_firmware_info(
        version_major: int = 2,
        version_minor: int = 80,
        build: int = 1514213314000000000,
    ) -> FirmwareInfo:
        """Create a mock FirmwareInfo with specified version."""
        return FirmwareInfo(
            build=build,
            version_major=version_major,
            version_minor=version_minor,
        )

    return _create_firmware_info
