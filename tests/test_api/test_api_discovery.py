"""Tests for high-level API discovery helper functions.

This module tests:
- discover() - Async generator for device discovery
- discover_mdns() - Async generator for mDNS-based discovery
- find_by_serial() - Find specific device by serial number
- find_by_ip() - Find device by IP address
- find_by_label() - Find device by exact label match
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from lifx.api import discover, discover_mdns, find_by_ip, find_by_label, find_by_serial
from lifx.devices import Light
from lifx.network.discovery import discover_devices
from tests.conftest import get_free_port


@pytest.mark.emulator
class TestDiscover:
    """Test discover() async generator."""

    async def test_discover_basic(self, emulator_port: int):
        """Test basic discovery with async generator."""
        async for device in discover(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            assert isinstance(device, Light)

    async def test_discover_with_timeout(self, emulator_port: int):
        """Test discovery with custom timeout."""
        async for device in discover(
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            assert device is not None
            break

    async def test_discover_empty_network(self):
        """Test discovery when no devices are present."""
        async for device in discover(
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=get_free_port(),
        ):
            pytest.fail(f"Unexpected yield of {device} from discover.")


@pytest.mark.emulator
class TestFindBySerial:
    """Test find_by_serial() helper function."""

    async def test_find_by_serial_found_string(self, emulator_port: int):
        """Test finding device by serial number (string format)."""
        # First discover a device to get a real serial number
        target_serial = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            target_serial = disc.serial
            break

        assert target_serial is not None

        # Use the first discovered device's serial
        device = await find_by_serial(
            target_serial,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        assert device.serial == target_serial
        assert isinstance(device, Light)

    async def test_find_by_serial_with_colons(self, emulator_port: int):
        """Test finding device by serial with colon separators."""
        # Discover first device
        target_serial = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            target_serial = disc.serial
            break
        assert target_serial is not None

        # Format with colons
        serial_with_colons = ":".join(
            [target_serial[i : i + 2] for i in range(0, 12, 2)]
        )

        device = await find_by_serial(
            serial_with_colons,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        assert device.serial == target_serial

    async def test_find_by_serial_not_found(self, emulator_port: int):
        """Test finding device with non-existent serial."""
        device = await find_by_serial(
            "d073d5999999",
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        # Should return None
        assert device is None

    async def test_find_by_serial_case_insensitive(self, emulator_port: int):
        """Test that serial matching is case-insensitive."""
        # Discover first device
        target_serial = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            target_serial = disc.serial
            break
        assert target_serial is not None

        # Use uppercase version of serial
        uppercase_serial = target_serial.upper()

        device = await find_by_serial(
            uppercase_serial,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        assert device.serial.lower() == target_serial.lower()

    async def test_find_by_serial_timeout(self):
        """Test find_by_serial with empty network (timeout scenario)."""
        # Use a port with no emulator running
        device = await find_by_serial(
            "d073d5999999",
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=get_free_port(),
        )
        assert device is None


@pytest.mark.emulator
class TestFindByIp:
    """Tests for find_by_ip function."""

    async def test_find_by_ip_found(self, emulator_port: int):
        """Test find_by_ip returns device when IP matches."""
        # Emulator devices are all at 127.0.0.1
        device = await find_by_ip(
            "127.0.0.1",
            timeout=1.0,
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        # Should get one of the emulator devices (d073d5000001-d073d5000007)
        assert device.serial.startswith("d073d5")

    async def test_find_by_ip_not_found(self, emulator_port: int):
        """Test find_by_ip returns None when IP doesn't match any device."""
        # Use an IP that's definitely not the emulator (192.168.200.254)
        device = await find_by_ip(
            "192.168.200.254",
            timeout=1.0,
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is None

    async def test_find_by_ip_timeout(self):
        """Test find_by_ip with no emulator running (timeout scenario)."""
        device = await find_by_ip(
            "127.0.0.1",
            timeout=0.5,
            port=get_free_port(),
            idle_timeout_multiplier=0.5,
        )
        assert device is None


@pytest.mark.emulator
class TestFindByLabel:
    """Tests for find_by_label function."""

    async def test_find_by_label_found(self, emulator_port: int):
        """Test find_by_label can find devices by label."""
        # First discover a device and get its label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        # Get the label of the first device
        device = await first_disc.create_device()
        if device is None:
            pytest.skip("Device creation returned None")

        async with device:
            device_label = await device.get_label()

        # Now search for that device by label using find_by_label
        found_devices = []
        async for d in find_by_label(
            device_label,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            found_devices.append(d)

        try:
            assert len(found_devices) >= 1
            assert any(d.serial == first_disc.serial for d in found_devices)
        finally:
            # Close all found device connections
            for d in found_devices:
                await d.connection.close()

    async def test_find_by_label_case_insensitive(self, emulator_port: int):
        """Test find_by_label is case-insensitive."""
        # Get a device label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        device = await first_disc.create_device()
        if device is None:
            pytest.skip("Device creation returned None")

        async with device:
            device_label = await device.get_label()

        # Search with different case
        found_devices = []
        async for d in find_by_label(
            device_label.upper(),
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            found_devices.append(d)

        try:
            assert len(found_devices) >= 1
            assert any(d.serial == first_disc.serial for d in found_devices)
        finally:
            # Close all found device connections
            for d in found_devices:
                await d.connection.close()

    async def test_find_by_label_not_found(self, emulator_port: int):
        """Test find_by_label returns empty list when label doesn't match any device."""
        # Use a label that definitely doesn't exist
        async for d in find_by_label(
            "Nonexistent Device Label XYZ999",
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            pytest.fail(f"Unexpected yield of {d} from find_by_label()")

    async def test_find_by_label_timeout(self):
        """Test find_by_label with no emulator running (timeout scenario)."""
        async for d in find_by_label(
            "Test Device",
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=get_free_port(),
            idle_timeout_multiplier=0.5,
        ):
            pytest.fail(f"Unexpected yield of {d} from find_by_label()")

    async def test_find_by_label_substring_match(self, emulator_port: int):
        """Test find_by_label substring matching (default behavior)."""
        # Get a device label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        device = await first_disc.create_device()
        if device is None:
            pytest.skip("Device creation returned None")

        async with device:
            device_label = await device.get_label()

        # Search with partial label (should match if label contains the substring)
        # E.g., if label is "LIFX Color 000001", search for "Color"
        if len(device_label) > 4:
            partial_label = device_label[5:9]  # Get a middle substring
            async for d in find_by_label(
                partial_label,
                exact_match=False,
                timeout=1.0,
                broadcast_address="127.0.0.1",
                port=emulator_port,
                idle_timeout_multiplier=0.5,
            ):
                assert d is not None
                await d.connection.close()
                break

    async def test_find_by_label_exact_match(self, emulator_port: int):
        """Test find_by_label exact matching."""
        # Get a device label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        device = await first_disc.create_device()
        if device is None:
            pytest.skip("Device creation returned None")

        async with device:
            device_label = await device.get_label()

        # Exact match should work
        async for d in find_by_label(
            device_label,
            exact_match=True,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            assert d.serial == first_disc.serial
            await d.connection.close()

        # Partial label with exact_match=True should NOT match
        if len(device_label) > 4:
            partial_label = device_label[5:9]
            async for d in find_by_label(
                partial_label,
                exact_match=True,
                timeout=1.0,
                broadcast_address="127.0.0.1",
                port=emulator_port,
                idle_timeout_multiplier=0.5,
            ):
                pytest.fail(f"Unexpected yield of {d} from find_by_label()")


class TestDiscoverMdns:
    """Tests for discover_mdns() high-level API function."""

    @pytest.mark.asyncio
    async def test_discover_mdns_yields_devices(self) -> None:
        """Test that discover_mdns() yields device instances."""
        from lifx.network.mdns.types import LifxServiceRecord

        mock_record = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=27,  # LIFX A19
            firmware="4.112",
        )

        async def mock_discover_services(*args, **kwargs):
            yield mock_record

        with patch(
            "lifx.network.mdns.discovery.discover_lifx_services",
            side_effect=mock_discover_services,
        ):
            devices = []
            async for device in discover_mdns(timeout=0.1):
                devices.append(device)

            assert len(devices) == 1
            assert isinstance(devices[0], Light)
            assert devices[0].serial == "d073d5123456"

    @pytest.mark.asyncio
    async def test_discover_mdns_filters_relay_devices(self) -> None:
        """Test that discover_mdns() filters out relay-only devices."""
        from lifx.network.mdns.types import LifxServiceRecord

        mock_record = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=70,  # LIFX Switch - relay only
            firmware="4.112",
        )

        async def mock_discover_services(*args, **kwargs):
            yield mock_record

        with patch(
            "lifx.network.mdns.discovery.discover_lifx_services",
            side_effect=mock_discover_services,
        ):
            devices = []
            async for device in discover_mdns(timeout=0.1):
                devices.append(device)

            # Relay devices should be filtered out
            assert len(devices) == 0

    @pytest.mark.asyncio
    async def test_discover_mdns_empty_network(self) -> None:
        """Test discover_mdns() with no devices."""

        async def mock_discover_services(*args, **kwargs):
            return
            yield  # noqa: B901 - makes this an async generator

        with patch(
            "lifx.network.mdns.discovery.discover_lifx_services",
            side_effect=mock_discover_services,
        ):
            devices = []
            async for device in discover_mdns(timeout=0.1):
                devices.append(device)

            assert len(devices) == 0
