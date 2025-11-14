"""Tests for MAC address calculation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from lifx.devices.base import Device
from lifx.protocol import packets


class TestMacAddress:
    """Tests for MAC address calculation."""

    async def test_mac_address_version_2(self, device: Device) -> None:
        """Test MAC address calculation for firmware version 2."""
        # Mock firmware version 2
        mock_firmware = packets.Device.StateHostFirmware(
            build=1234567890, version_major=2, version_minor=77
        )
        device.connection.request.return_value = mock_firmware

        # Get host firmware to trigger MAC calculation
        await device.get_host_firmware()

        # For version 2, MAC should match serial (with colons)
        # Device serial is "d073d5010203" (from fixture)
        expected_mac = "d0:73:d5:01:02:03"
        assert device.mac_address == expected_mac

    async def test_mac_address_version_4(self, device: Device) -> None:
        """Test MAC address calculation for firmware version 4."""
        # Mock firmware version 4
        mock_firmware = packets.Device.StateHostFirmware(
            build=1234567890, version_major=4, version_minor=0
        )
        device.connection.request.return_value = mock_firmware

        # Get host firmware to trigger MAC calculation
        await device.get_host_firmware()

        # For version 4, MAC should match serial (with colons)
        expected_mac = "d0:73:d5:01:02:03"
        assert device.mac_address == expected_mac

    async def test_mac_address_version_3(self, device: Device) -> None:
        """Test MAC address calculation for firmware version 3."""
        # Mock firmware version 3
        mock_firmware = packets.Device.StateHostFirmware(
            build=1234567890, version_major=3, version_minor=70
        )
        device.connection.request.return_value = mock_firmware

        # Get host firmware to trigger MAC calculation
        await device.get_host_firmware()

        # For version 3, MAC should be serial + 1 on LSB
        # Device serial is "d073d5010203" (from fixture)
        # LSB is 0x03, so MAC should end with 0x04
        expected_mac = "d0:73:d5:01:02:04"
        assert device.mac_address == expected_mac

    async def test_mac_address_version_3_wraparound(self) -> None:
        """Test MAC address calculation for firmware version 3 with LSB wraparound."""
        # Create device with serial ending in FF
        device_ff = Device(serial="d073d50102ff", ip="192.168.1.100")
        device_ff.connection = MagicMock()
        device_ff.connection.request = AsyncMock()

        # Mock firmware version 3
        mock_firmware = packets.Device.StateHostFirmware(
            build=1234567890, version_major=3, version_minor=70
        )
        device_ff.connection.request.return_value = mock_firmware

        # Get host firmware to trigger MAC calculation
        await device_ff.get_host_firmware()

        # For version 3 with LSB=0xff, MAC should wrap around to 0x00
        expected_mac = "d0:73:d5:01:02:00"
        assert device_ff.mac_address == expected_mac

    async def test_mac_address_none_before_firmware_fetch(self, device: Device) -> None:
        """Test MAC address is None before firmware is fetched."""
        # MAC address should be None initially
        assert device.mac_address is None

    async def test_mac_address_unknown_version(self, device: Device) -> None:
        """Test MAC address defaults to serial for unknown firmware version."""
        # Mock firmware with unknown version (not 2, 3, or 4)
        mock_firmware = packets.Device.StateHostFirmware(
            build=1234567890, version_major=5, version_minor=0
        )
        device.connection.request.return_value = mock_firmware

        # Get host firmware to trigger MAC calculation
        await device.get_host_firmware()

        # For unknown version, MAC should default to serial (with colons)
        expected_mac = "d0:73:d5:01:02:03"
        assert device.mac_address == expected_mac

    async def test_mac_address_format(self, device: Device) -> None:
        """Test MAC address is formatted with colons."""
        # Mock firmware version 2
        mock_firmware = packets.Device.StateHostFirmware(
            build=1234567890, version_major=2, version_minor=77
        )
        device.connection.request.return_value = mock_firmware

        # Get host firmware to trigger MAC calculation
        await device.get_host_firmware()

        # Verify format with colons
        assert device.mac_address is not None
        assert ":" in device.mac_address
        # Should have 5 colons (6 octets)
        assert device.mac_address.count(":") == 5
        # Should be lowercase hex
        assert device.mac_address == device.mac_address.lower()
