"""Tests for uncovered code paths in discovery.py.

This module contains tests targeting lines not covered by existing test suites,
focusing on device creation, label-based discovery, and protocol edge cases.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.devices.base import Device, DeviceVersion, FirmwareInfo
from lifx.devices.hev import HevLight
from lifx.devices.infrared import InfraredLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.network.discovery import (
    DiscoveredDevice,
    DiscoveryResponse,
    discover_devices,
)
from lifx.products.registry import ProductCapability, ProductInfo


class TestDiscoveryGeneratorOwnership:
    """The public discovery generator owns its private packet delegate."""

    @pytest.mark.asyncio
    async def test_close_synchronously_finalises_packet_discovery(self) -> None:
        """Closing device discovery immediately finalises packet discovery."""
        finalised = False

        async def packet_discovery():
            nonlocal finalised
            try:
                yield DiscoveryResponse(
                    serial="d073d5010203",
                    ip="192.0.2.10",
                    port=56700,
                    response_time=0.01,
                    response_payload={"port": 56700},
                )
            finally:
                finalised = True

        with patch(
            "lifx.network.discovery._discover_with_packet",
            return_value=packet_discovery(),
        ):
            generator = discover_devices(timeout=0.1)
            device = await anext(generator)
            assert device.serial == "d073d5010203"
            await generator.aclose()

        assert finalised is True


class TestDiscoveredDeviceValidationBoundary:
    """Malformed responder data is isolated to that response."""

    async def test_constructor_failure_returns_none_without_cleanup(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Failure before a temporary device exists needs no connection cleanup."""
        discovered = DiscoveredDevice(
            serial="d073d5010203",
            ip="192.0.2.10",
        )

        with (
            caplog.at_level(logging.DEBUG, logger="lifx.network.discovery"),
            patch(
                "lifx.devices.base.Device", side_effect=ValueError("invalid address")
            ),
        ):
            assert await discovered.create_device() is None

        record = caplog.records[-1].msg
        assert isinstance(record, dict)
        assert record["action"] == "invalid_device_address"
        assert record["serial"] == discovered.serial
        assert record["reason"] == "invalid address"

    async def test_constructor_programming_error_propagates(self) -> None:
        """A refactor error is not misreported as an unsupported responder."""
        discovered = DiscoveredDevice(
            serial="d073d5010203",
            ip="192.0.2.10",
        )

        with patch(
            "lifx.devices.base.Device", side_effect=TypeError("broken signature")
        ):
            with pytest.raises(TypeError, match="broken signature"):
                await discovered.create_device()

    async def test_invalid_address_returns_none_instead_of_aborting_sweep(self) -> None:
        """Device construction failures stay inside ``create_device``."""
        discovered = DiscoveredDevice(
            serial="d073d5010203",
            ip="fe80::1",
        )

        assert await discovered.create_device() is None

    async def test_missing_capability_metadata_returns_none(self) -> None:
        """A valid responder without version metadata is not constructible."""
        discovered = DiscoveredDevice(
            serial="d073d5010203",
            ip="192.0.2.10",
        )
        temporary_device = MagicMock()
        temporary_device.ensure_capabilities = AsyncMock()
        temporary_device.capabilities = None
        temporary_device.version = None
        temporary_device.connection.close = AsyncMock()

        with patch("lifx.devices.base.Device", return_value=temporary_device):
            assert await discovered.create_device() is None

        temporary_device.connection.close.assert_awaited_once_with()

    async def test_wire_address_warning_stays_suppressed_during_construction(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A responder-controlled loopback address cannot flood warnings."""
        discovered = DiscoveredDevice(
            serial="d073d5010203",
            ip="127.0.0.1",
            port=12345,
        )

        async def fake_ensure(self: Device) -> None:
            self._capabilities = None
            self._version = None

        with (
            caplog.at_level(logging.WARNING),
            patch.object(Device, "ensure_capabilities", fake_ensure),
            patch(
                "lifx.network.connection.DeviceConnection.close",
                new_callable=AsyncMock,
            ),
        ):
            assert await discovered.create_device() is None

        assert caplog.records == []


@pytest.mark.emulator
class TestDiscoveredDeviceCreateDevice:
    """Tests for DiscoveredDevice.create_device() method.

    These tests cover lines 48-107 of discovery.py, which create device instances
    of the appropriate type based on product ID.
    """

    @pytest.mark.asyncio
    async def test_create_device_returns_correct_type(self, emulator_port: int) -> None:
        """Test that create_device returns a device instance."""
        first_disc = None
        async for disc in discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        # Create device from first discovered device
        device = await first_disc.create_device()
        assert device is not None

        # Verify it's some type of device
        assert isinstance(
            device,
            Device | Light | MultiZoneLight | HevLight | InfraredLight | MatrixLight,
        )

    @pytest.mark.asyncio
    async def test_create_device_preserves_connection_info(
        self, emulator_port: int
    ) -> None:
        """Test that create_device preserves serial, IP, and port info."""
        first_disc = None
        async for disc in discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        device = await first_disc.create_device()

        # Verify connection info is preserved
        assert device.serial == first_disc.serial
        assert device.ip == first_disc.ip
        assert device.port == first_disc.port

    @pytest.mark.asyncio
    async def test_create_device_all_emulator_devices(self, emulator_port: int) -> None:
        """Test create_device works for all device types in emulator.

        The emulator creates 7 devices:
        - 1 color light
        - 1 infrared light
        - 1 HEV light
        - 2 multizone lights
        - 1 tile device
        - 1 color temperature light
        """
        device_types: dict[str, int] = {}

        async for disc in discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            device = await disc.create_device()
            if device is not None:
                async with device:
                    device_type = type(device).__name__
                    device_types[device_type] = device_types.get(device_type, 0) + 1

                    # Each created device should have valid connection info
                    assert device.serial == disc.serial
                    assert device.ip == disc.ip
                    assert device.port == disc.port

        # Verify we have expected device types
        assert "Light" in device_types and "InfraredLight" in device_types


@pytest.mark.emulator
class TestDiscoveryEdgeCasesWithEmulator:
    """Additional edge case tests using the emulator server."""

    @pytest.mark.asyncio
    async def test_discover_devices_with_multiple_simultaneous_creates(
        self, emulator_port: int
    ) -> None:
        """Test creating multiple device instances simultaneously.

        This tests that create_device() works correctly when called
        multiple times concurrently.
        """
        import asyncio

        discovered_list = []
        async for disc in discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            discovered_list.append(disc)
            if len(discovered_list) >= 2:
                break

        # Create devices concurrently
        devices = await asyncio.gather(
            *[d.create_device() for d in discovered_list[:2]]
        )

        assert len(devices) == 2
        assert devices[0].serial == discovered_list[0].serial
        assert devices[1].serial == discovered_list[1].serial

    @pytest.mark.asyncio
    async def test_discover_devices_response_time_accuracy(
        self, emulator_port: int
    ) -> None:
        """Test that response_time is accurately calculated."""
        devices = []
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            devices.append(disc)
            if len(devices) >= 2:
                break

        assert len(devices) > 0

        # All response times should be positive and reasonable
        # It is possible for the emulator to respond "instantly"
        for device in devices:
            assert device.response_time >= 0.0
            # Response time should be less than 1 second for localhost
            assert device.response_time < 1.0

    @pytest.mark.asyncio
    async def test_discover_all_devices_have_valid_ports(
        self, emulator_port: int
    ) -> None:
        """Test that all discovered devices have valid port numbers."""
        devices = []
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            devices.append(disc)
            if len(devices) >= 2:
                break

        assert len(devices) > 0

        for device in devices:
            # Port should be valid
            assert 1024 <= device.port <= 65535


class TestCreateDeviceUnsupported:
    """Unit tests for create_device() with unsupported products."""

    @pytest.mark.asyncio
    async def test_create_device_returns_none_for_relay(self) -> None:
        """Test create_device() returns None for relay devices."""
        relay_product = ProductInfo(
            pid=70,
            name="LIFX Switch",
            vendor=1,
            capabilities=ProductCapability.RELAYS,
            temperature_range=None,
            min_ext_mz_firmware=None,
        )

        disc = DiscoveredDevice(
            serial="d073d5010203",
            ip="192.168.1.100",
        )

        async def fake_ensure(self: Device) -> None:
            self._capabilities = relay_product
            self._version = DeviceVersion(vendor=1, product=70)

        with patch.object(Device, "ensure_capabilities", fake_ensure):
            result = await disc.create_device()

        assert result is None

    @pytest.mark.asyncio
    async def test_create_device_preserves_detection_metadata(self) -> None:
        """Metadata fetched for detection is adopted by the concrete device."""
        color_product = ProductInfo(
            pid=27,
            name="LIFX A19",
            vendor=1,
            capabilities=ProductCapability.COLOR,
            temperature_range=None,
            min_ext_mz_firmware=None,
        )
        version = DeviceVersion(vendor=1, product=27)
        firmware = FirmwareInfo(build=123, version_major=3, version_minor=90)
        disc = DiscoveredDevice(serial="d073d5010203", ip="192.168.1.100")

        async def fake_ensure(self: Device) -> None:
            self._capabilities = color_product
            self._version = version
            self._host_firmware = firmware
            self._mac_address = "d0:73:d5:01:02:04"
            self._mac_address_firmware = (3, 90)

        with (
            patch.object(Device, "ensure_capabilities", fake_ensure),
            patch(
                "lifx.network.connection.DeviceConnection.close",
                new_callable=AsyncMock,
            ) as close,
        ):
            result = await disc.create_device()

        assert isinstance(result, Light)
        assert result.version is version
        assert result.host_firmware is firmware
        assert result.capabilities is color_product
        assert result.mac_address == "d0:73:d5:01:02:04"
        close.assert_awaited_once_with()
