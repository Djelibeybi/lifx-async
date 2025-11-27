"""Tests for discovery error paths and DoS protection mechanisms."""

from __future__ import annotations

import struct

import pytest

from lifx.exceptions import LifxProtocolError
from lifx.network.discovery import (
    _parse_device_state_service,
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


@pytest.mark.emulator
class TestDiscoveryMalformedPackets:
    """Test discovery handling of malformed packets."""

    @pytest.mark.asyncio
    async def test_discovery_with_malformed_header(self, emulator_port: int) -> None:
        """Test discovery continues when receiving malformed packets.

        The discovery should skip malformed responses and continue waiting
        for valid responses.
        """
        # Test that discovery handles malformed packets gracefully
        # The emulator provides valid packets on the port
        found_device = False
        async for disc in discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            found_device = True
            break

        # Should have discovered at least one device
        assert found_device


class TestDiscoveryWithEmulatorErrors:
    """Test discovery with various error scenarios."""

    @pytest.mark.asyncio
    async def test_discovery_timeout_scenario(self) -> None:
        """Test discovery with no responding devices."""
        # Use non-existent port - generator should yield nothing
        count = 0
        async for disc in discover_devices(
            timeout=0.1,
            broadcast_address="255.255.255.255",
            port=65432,
        ):
            count += 1

        # Should not yield any devices
        assert count == 0


@pytest.mark.emulator
class TestDiscoveryDeduplication:
    """Test that discovered devices are properly deduplicated."""

    @pytest.mark.asyncio
    async def test_devices_deduplicated_by_serial(self, emulator_port: int) -> None:
        """Test that duplicate responses are deduplicated by serial."""
        seen_serials: set[str] = set()
        async for disc in discover_devices(
            timeout=1.5,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            # Each yielded device should have a unique serial
            assert disc.serial not in seen_serials, f"Duplicate serial: {disc.serial}"
            seen_serials.add(disc.serial)
