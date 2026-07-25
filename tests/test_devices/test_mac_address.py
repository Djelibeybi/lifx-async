"""Tests for MAC address calculation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

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

    async def test_mac_address_version_3_at_offset_boundary(
        self, device: Device
    ) -> None:
        """Test MAC address calculation for firmware 3.70 (the offset boundary).

        The minor version is load-bearing: only 3.70 and above take the offset,
        so lowering it to an earlier 3.x build changes the expected MAC.
        """
        # Mock firmware version 3.70 -- at the offset boundary
        mock_firmware = packets.Device.StateHostFirmware(
            build=1234567890, version_major=3, version_minor=70
        )
        device.connection.request.return_value = mock_firmware

        # Get host firmware to trigger MAC calculation
        await device.get_host_firmware()

        # At/above 3.70, MAC should be serial + 1 on LSB
        # Device serial is "d073d5010203" (from fixture)
        # LSB is 0x03, so MAC should end with 0x04
        expected_mac = "d0:73:d5:01:02:04"
        assert device.mac_address == expected_mac

    @pytest.mark.parametrize(
        ("version_major", "version_minor", "expected_mac"),
        [
            # Below the 3.70 boundary the MAC equals the serial. Verified on
            # real LIFX Tiles running 3.50, whose ARP MAC matched the serial.
            (3, 50, "d0:73:d5:01:02:03"),
            (3, 69, "d0:73:d5:01:02:03"),
            # Minor is compared as an integer, so 9 is below the boundary --
            # a decimal reading of "3.9" would wrongly classify this one.
            (3, 9, "d0:73:d5:01:02:03"),
            # At and above minor 70 the final octet is +1.
            (3, 70, "d0:73:d5:01:02:04"),
            (3, 90, "d0:73:d5:01:02:04"),
            (3, 255, "d0:73:d5:01:02:04"),
            # Major 4 never offsets, even at a minor above the 3.x boundary.
            (4, 90, "d0:73:d5:01:02:03"),
            # Nor does an earlier major.
            (2, 90, "d0:73:d5:01:02:03"),
        ],
    )
    async def test_mac_address_offset_firmware_boundary(
        self,
        device: Device,
        version_major: int,
        version_minor: int,
        expected_mac: str,
    ) -> None:
        """The final-octet offset applies only to 3.70 <= firmware < 4.0."""
        device.connection.request.return_value = packets.Device.StateHostFirmware(
            build=1234567890,
            version_major=version_major,
            version_minor=version_minor,
        )

        await device.get_host_firmware()

        assert device.mac_address == expected_mac

    async def test_mac_address_version_3_wraparound(self) -> None:
        """Test LSB wraparound for firmware in the offset range (3.70 and above).

        Minor 70 is load-bearing here too: an earlier 3.x build takes no offset
        and so exercises no wraparound at all.
        """
        # Create device with serial ending in FF
        device_ff = Device(serial="d073d50102ff", ip="192.168.1.100")
        device_ff.connection = MagicMock()
        device_ff.connection.request = AsyncMock()

        # Mock firmware version 3.70 -- inside the offset range
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
        """Test MAC address defaults to serial outside the 3.70-3.255 offset range."""
        # Mock firmware outside the offset range entirely
        mock_firmware = packets.Device.StateHostFirmware(
            build=1234567890, version_major=5, version_minor=0
        )
        device.connection.request.return_value = mock_firmware

        # Get host firmware to trigger MAC calculation
        await device.get_host_firmware()

        # For unknown version, MAC should default to serial (with colons)
        expected_mac = "d0:73:d5:01:02:03"
        assert device.mac_address == expected_mac

    async def test_mac_address_recomputed_when_firmware_changes(
        self, device: Device
    ) -> None:
        """A firmware change across the boundary must re-derive the cached MAC.

        The rule turns on the minor version, so a device that reports 3.50 and
        later reports 3.90 has a different correct MAC. The cache is keyed on
        the firmware it was derived from rather than on "already computed".
        """
        device.connection.request.return_value = packets.Device.StateHostFirmware(
            build=1234567890, version_major=3, version_minor=50
        )
        await device.get_host_firmware()
        assert device.mac_address == "d0:73:d5:01:02:03"

        device.connection.request.return_value = packets.Device.StateHostFirmware(
            build=1234567891, version_major=3, version_minor=90
        )
        await device.get_host_firmware()

        assert device.mac_address == "d0:73:d5:01:02:04"
        assert await device.get_mac_address() == "d0:73:d5:01:02:04"

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
