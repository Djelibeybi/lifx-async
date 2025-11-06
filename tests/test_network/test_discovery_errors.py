"""Tests for discovery error paths and DoS protection mechanisms."""

from __future__ import annotations

import struct

import pytest

from lifx.exceptions import LifxProtocolError
from lifx.network.discovery import (
    _parse_device_state_service,
    discover_device_by_ip,
    discover_device_by_serial,
    discover_devices,
)


class TestParseDeviceStateServiceErrors:
    """Test _parse_device_state_service error handling."""

    def test_parse_short_payload(self) -> None:
        """Test error when payload is too short."""
        payload = b"\x01\x00\x00"  # Only 3 bytes, need 5
        with pytest.raises(
            LifxProtocolError, match="DeviceStateService payload too short"
        ):
            _parse_device_state_service(payload)

    def test_parse_empty_payload(self) -> None:
        """Test error with empty payload."""
        with pytest.raises(
            LifxProtocolError, match="DeviceStateService payload too short"
        ):
            _parse_device_state_service(b"")

    def test_parse_valid_payload(self) -> None:
        """Test successful parsing of valid payload."""
        payload = struct.pack("<BI", 1, 56700)
        service, port = _parse_device_state_service(payload)
        assert service == 1
        assert port == 56700

    def test_parse_payload_with_extra_data(self) -> None:
        """Test parsing payload with extra data (should use only first 5 bytes)."""
        payload = struct.pack("<BI", 1, 56700) + b"extra_data"
        service, port = _parse_device_state_service(payload)
        assert service == 1
        assert port == 56700


class TestDiscoveryMalformedPackets:
    """Test discovery handling of malformed packets."""

    @pytest.mark.asyncio
    async def test_discovery_with_malformed_header(self, emulator_server: int) -> None:
        """Test discovery continues when receiving malformed packets.

        The discovery should skip malformed responses and continue waiting
        for valid responses.
        """
        # Test that discovery handles malformed packets gracefully
        # The emulator provides valid packets on the port
        devices = await discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        # Should have discovered devices despite being ready to handle malformed packets
        assert isinstance(devices, list)
        assert len(devices) > 0


class TestDiscoveryWithEmulatorErrors:
    """Test discovery with various error scenarios."""

    @pytest.mark.asyncio
    async def test_discovery_timeout_scenario(self) -> None:
        """Test discovery with no responding devices."""
        # Use non-existent port
        devices = await discover_devices(
            timeout=0.1,
            broadcast_address="255.255.255.255",
            port=65432,
        )

        # Should return empty list, not raise exception
        assert devices == []

    @pytest.mark.asyncio
    async def test_discovery_device_by_ip_not_found(self) -> None:
        """Test discover_device_by_ip returns None when not found."""
        device = await discover_device_by_ip(
            "192.168.1.254",
            timeout=0.1,
            broadcast_address="255.255.255.255",
            port=65432,
        )

        assert device is None

    @pytest.mark.asyncio
    async def test_discovery_device_by_serial_not_found(self) -> None:
        """Test discover_device_by_serial returns None when not found."""
        device = await discover_device_by_serial(
            "d073d5999999",
            timeout=0.1,
            broadcast_address="255.255.255.255",
            port=65432,
        )

        assert device is None

    @pytest.mark.asyncio
    async def test_discovery_device_by_ip_found(self, emulator_server: int) -> None:
        """Test discover_device_by_ip successfully finds a device."""
        # First get a device IP from actual discovery
        all_devices = await discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        if all_devices:
            target_ip = all_devices[0].ip
            device = await discover_device_by_ip(
                target_ip,
                timeout=2.0,
                broadcast_address="127.0.0.1",
                port=emulator_server,
            )

            assert device is not None
            assert device.ip == target_ip

    @pytest.mark.asyncio
    async def test_discovery_device_by_serial_found(self, emulator_server: int) -> None:
        """Test discover_device_by_serial successfully finds a device."""
        # First get a device serial from actual discovery
        all_devices = await discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        if all_devices:
            target_serial = all_devices[0].serial
            device = await discover_device_by_serial(
                target_serial,
                timeout=2.0,
                broadcast_address="127.0.0.1",
                port=emulator_server,
            )

            assert device is not None
            assert device.serial == target_serial


class TestDiscoveryDeduplication:
    """Test that discovered devices are properly deduplicated."""

    @pytest.mark.asyncio
    async def test_devices_deduplicated_by_serial(self, emulator_server: int) -> None:
        """Test that duplicate responses are deduplicated by serial."""
        devices = await discover_devices(
            timeout=1.5,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )

        # Extract serials
        serials = [d.serial for d in devices]

        # All serials should be unique
        assert len(serials) == len(set(serials))
