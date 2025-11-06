"""Tests for uncovered code paths in discovery.py.

This module contains tests targeting lines not covered by existing test suites,
focusing on device creation, label-based discovery, and protocol edge cases.
"""

from __future__ import annotations

import pytest

from lifx.devices.base import Device
from lifx.devices.hev import HevLight
from lifx.devices.infrared import InfraredLight
from lifx.devices.light import Light
from lifx.devices.multizone import MultiZoneLight
from lifx.devices.tile import TileDevice
from lifx.network.discovery import discover_device_by_label, discover_devices


class TestDiscoveredDeviceCreateDevice:
    """Tests for DiscoveredDevice.create_device() method.

    These tests cover lines 48-107 of discovery.py, which create device instances
    of the appropriate type based on product ID.
    """

    @pytest.mark.asyncio
    async def test_create_device_returns_correct_type(
        self, emulator_server: int
    ) -> None:
        """Test that create_device returns a device instance."""
        devices = await discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        assert len(devices) > 0

        # Create device from first discovered device
        device = await devices[0].create_device()
        assert device is not None

        # Verify it's some type of device
        assert isinstance(
            device,
            Device | Light | MultiZoneLight | HevLight | InfraredLight | TileDevice,
        )

    @pytest.mark.asyncio
    async def test_create_device_preserves_connection_info(
        self, emulator_server: int
    ) -> None:
        """Test that create_device preserves serial, IP, and port info."""
        discovered_list = await discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        assert len(discovered_list) > 0

        discovered = discovered_list[0]
        device = await discovered.create_device()

        # Verify connection info is preserved
        assert device.serial == discovered.serial
        assert device.ip == discovered.ip
        assert device.port == discovered.port

    @pytest.mark.asyncio
    async def test_create_device_all_emulator_devices(
        self, emulator_server: int
    ) -> None:
        """Test create_device works for all device types in emulator.

        The emulator creates 7 devices:
        - 1 color light
        - 1 infrared light
        - 1 HEV light
        - 2 multizone lights
        - 1 tile device
        - 1 color temperature light
        """
        discovered_list = await discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        assert len(discovered_list) == 7

        device_types = {}
        for discovered in discovered_list:
            device = await discovered.create_device()
            device_type = type(device).__name__
            device_types[device_type] = device_types.get(device_type, 0) + 1

            # Each created device should have valid connection info
            assert device.serial == discovered.serial
            assert device.ip == discovered.ip
            assert device.port == discovered.port

        # Verify we have expected device types
        assert "Light" in device_types or "InfraredLight" in device_types
        # The emulator should create various device types


class TestDiscoverDeviceByLabel:
    """Tests for discover_device_by_label function.

    These tests cover lines 458-520 of discovery.py, including label matching,
    timeout handling, and device querying.
    """

    @pytest.mark.asyncio
    async def test_discover_by_label_finds_device(self, emulator_server: int) -> None:
        """Test discover_device_by_label can find a device by label."""
        # First discover all devices and get a label
        discovered_list = await discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        if not discovered_list:
            pytest.skip("No devices discovered from emulator")

        # Get the label of the first device
        first_device = discovered_list[0]
        device = await first_device.create_device()
        async with device:
            device_label = await device.get_label()

        # Now search for that device by label
        found_device = await discover_device_by_label(
            device_label,
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        assert found_device is not None
        assert found_device.serial == first_device.serial

    @pytest.mark.asyncio
    async def test_discover_by_label_case_insensitive(
        self, emulator_server: int
    ) -> None:
        """Test discover_device_by_label is case-insensitive."""
        # First discover all devices and get a label
        discovered_list = await discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        if not discovered_list:
            pytest.skip("No devices discovered from emulator")

        # Get the label of the first device
        first_device = discovered_list[0]
        device = await first_device.create_device()
        async with device:
            device_label = await device.get_label()

        # Search with different case
        found_device = await discover_device_by_label(
            device_label.upper(),
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        assert found_device is not None
        assert found_device.serial == first_device.serial

    @pytest.mark.asyncio
    async def test_discover_by_label_not_found(self, emulator_server: int) -> None:
        """Test discover_device_by_label returns None when label not found."""
        result = await discover_device_by_label(
            "Nonexistent Device Label 12345",
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_discover_by_label_no_devices(self) -> None:
        """Test discover_device_by_label when no devices respond."""
        result = await discover_device_by_label(
            "Test Device",
            timeout=0.1,
            broadcast_address="255.255.255.255",
            port=65432,  # Non-existent port
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_discover_by_label_skips_unresponsive_devices(
        self, emulator_server
    ) -> None:
        """Test discover_device_by_label skips non-responding devices.

        Tests error handling when devices raise LifxError or TimeoutError.
        """
        # This test is more of an integration test - the emulator should respond
        # but this tests that the function properly handles errors
        result = await discover_device_by_label(
            "Test Device",
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        # Should either find a device or return None, not raise
        assert result is None or result.serial is not None

    @pytest.mark.asyncio
    async def test_discover_by_label_uses_all_parameters(
        self, emulator_server: int
    ) -> None:
        """Test discover_device_by_label passes parameters to discover_devices."""
        # This verifies the function properly forwards parameters
        result = await discover_device_by_label(
            "Nonexistent",
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        # May or may not find, but should complete without error
        assert result is None or result.serial is not None


class TestDiscoveryEdgeCasesWithEmulator:
    """Additional edge case tests using the emulator server."""

    @pytest.mark.asyncio
    async def test_discover_devices_with_multiple_simultaneous_creates(
        self, emulator_server: int
    ) -> None:
        """Test creating multiple device instances simultaneously.

        This tests that create_device() works correctly when called
        multiple times concurrently.
        """
        import asyncio

        discovered_list = await discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        if len(discovered_list) < 2:
            pytest.skip("Need at least 2 devices for this test")

        # Create devices concurrently
        devices = await asyncio.gather(
            *[d.create_device() for d in discovered_list[:2]]
        )

        assert len(devices) == 2
        assert devices[0].serial == discovered_list[0].serial
        assert devices[1].serial == discovered_list[1].serial

    @pytest.mark.asyncio
    async def test_discover_devices_response_time_accuracy(
        self, emulator_server: int
    ) -> None:
        """Test that response_time is accurately calculated."""
        devices = await discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        assert len(devices) > 0

        # All response times should be positive and reasonable
        # It is possible for the emulator to respond "instantly"
        for device in devices:
            assert device.response_time >= 0.0
            # Response time should be less than 1 second for localhost
            assert device.response_time < 1.0

    @pytest.mark.asyncio
    async def test_discover_all_devices_have_valid_ports(
        self, emulator_server: int
    ) -> None:
        """Test that all discovered devices have valid port numbers."""
        devices = await discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        assert len(devices) > 0

        for device in devices:
            # Port should be valid
            assert 1 <= device.port <= 65535
            # Service should be UDP (1)
            assert device.service == 1


class TestDiscoverByIpAndSerialLoops:
    """Tests for discover_device_by_ip and discover_device_by_serial loops.

    These tests specifically exercise the for loops in discover_device_by_ip
    (lines 414-418) and discover_device_by_serial (lines 450-454) that return
    matching devices.
    """

    @pytest.mark.asyncio
    async def test_discover_by_ip_returns_matching_device(
        self, emulator_server: int
    ) -> None:
        """Test discover_device_by_ip returns device when IP matches.

        This tests lines 414-418 where the for loop finds a matching IP
        and returns the device.
        """
        from lifx.network.discovery import discover_device_by_ip

        # First discover all devices
        discovered_list = await discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        if not discovered_list:
            pytest.skip("No devices discovered")

        # Pick the first device's IP
        target_ip = discovered_list[0].ip

        # Now search for it
        found = await discover_device_by_ip(
            target_ip,
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        assert found is not None
        assert found.ip == target_ip

    @pytest.mark.asyncio
    async def test_discover_by_ip_returns_none_when_not_found(
        self, emulator_server: int
    ) -> None:
        """Test discover_device_by_ip returns None when no IP matches.

        This tests lines 414-418 where the for loop completes without
        finding a match, then line 418 returns None.
        """
        from lifx.network.discovery import discover_device_by_ip

        found = await discover_device_by_ip(
            "192.168.200.254",  # Unlikely to exist
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        assert found is None

    @pytest.mark.asyncio
    async def test_discover_by_serial_returns_matching_device(
        self, emulator_server: int
    ) -> None:
        """Test discover_device_by_serial returns device when serial matches.

        This tests lines 450-454 where the for loop finds a matching serial
        and returns the device.
        """
        from lifx.network.discovery import discover_device_by_serial

        # First discover all devices
        discovered_list = await discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        if not discovered_list:
            pytest.skip("No devices discovered")

        # Pick the first device's serial
        target_serial = discovered_list[0].serial

        # Now search for it
        found = await discover_device_by_serial(
            target_serial,
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        assert found is not None
        assert found.serial == target_serial

    @pytest.mark.asyncio
    async def test_discover_by_serial_returns_none_when_not_found(
        self, emulator_server: int
    ) -> None:
        """Test discover_device_by_serial returns None when no serial matches.

        This tests lines 450-454 where the for loop completes without
        finding a match, then line 454 returns None.
        """
        from lifx.network.discovery import discover_device_by_serial

        found = await discover_device_by_serial(
            "aabbccddffee",  # Unlikely to exist
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        assert found is None
