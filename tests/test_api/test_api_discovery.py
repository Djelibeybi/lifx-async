"""Tests for high-level API discovery helper functions.

This module tests:
- discover() - Async generator for device discovery
- find_by_serial() - Find specific device by serial number
- find_by_ip() - Find device by IP address
- find_by_label() - Find device by exact label match
"""

from __future__ import annotations

import pytest

from lifx.api import discover, find_by_ip, find_by_label, find_by_serial
from lifx.devices import Light
from lifx.network.discovery import discover_devices
from tests.conftest import get_free_port


class TestDiscover:
    """Test discover() async generator."""

    async def test_discover_basic(self, emulator_server: int):
        """Test basic discovery with async generator."""
        async for device in discover(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        ):
            assert isinstance(device, Light)

    async def test_discover_with_timeout(self, emulator_server: int):
        """Test discovery with custom timeout."""
        async for device in discover(
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=emulator_server,
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


class TestFindBySerial:
    """Test find_by_serial() helper function."""

    async def test_find_by_serial_found_string(self, emulator_server: int):
        """Test finding device by serial number (string format)."""
        # First discover a device to get a real serial number
        target_serial = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
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
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        assert device.serial == target_serial
        assert isinstance(device, Light)

    async def test_find_by_serial_with_colons(self, emulator_server: int):
        """Test finding device by serial with colon separators."""
        # Discover first device
        target_serial = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
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
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        assert device.serial == target_serial

    async def test_find_by_serial_not_found(self, emulator_server: int):
        """Test finding device with non-existent serial."""
        device = await find_by_serial(
            "d073d5999999",
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )

        # Should return None
        assert device is None

    async def test_find_by_serial_case_insensitive(self, emulator_server: int):
        """Test that serial matching is case-insensitive."""
        # Discover first device
        target_serial = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
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
            port=emulator_server,
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


class TestFindByIp:
    """Tests for find_by_ip function."""

    async def test_find_by_ip_found(self, emulator_server: int):
        """Test find_by_ip returns device when IP matches."""
        # Emulator devices are all at 127.0.0.1
        device = await find_by_ip(
            "127.0.0.1",
            timeout=1.0,
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        # Should get one of the emulator devices (d073d5000001-d073d5000007)
        assert device.serial.startswith("d073d5")

    async def test_find_by_ip_not_found(self, emulator_server: int):
        """Test find_by_ip returns None when IP doesn't match any device."""
        # Use an IP that's definitely not the emulator (192.168.200.254)
        device = await find_by_ip(
            "192.168.200.254",
            timeout=1.0,
            port=emulator_server,
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


class TestFindByLabel:
    """Tests for find_by_label function."""

    async def test_find_by_label_found(self, emulator_server: int):
        """Test find_by_label can find devices by label."""
        # First discover a device and get its label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        # Get the label of the first device
        device = await first_disc.create_device()
        if device is None:
            pytest.skip("Device creation returned None")

        device_label = await device.get_label()

        # Now search for that device by label using find_by_label
        found_devices = []
        async for d in find_by_label(
            device_label,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        ):
            found_devices.append(d)

        assert len(found_devices) >= 1
        assert any(d.serial == first_disc.serial for d in found_devices)

    async def test_find_by_label_case_insensitive(self, emulator_server: int):
        """Test find_by_label is case-insensitive."""
        # Get a device label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
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
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        ):
            found_devices.append(d)

        assert len(found_devices) >= 1
        assert any(d.serial == first_disc.serial for d in found_devices)

    async def test_find_by_label_not_found(self, emulator_server: int):
        """Test find_by_label returns empty list when label doesn't match any device."""
        # Use a label that definitely doesn't exist
        async for d in find_by_label(
            "Nonexistent Device Label XYZ999",
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
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

    async def test_find_by_label_substring_match(self, emulator_server: int):
        """Test find_by_label substring matching (default behavior)."""
        # Get a device label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        device = await first_disc.create_device()
        if device is None:
            pytest.skip("Device creation returned None")

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
                port=emulator_server,
                idle_timeout_multiplier=0.5,
            ):
                assert d is not None
                break

    async def test_find_by_label_exact_match(self, emulator_server: int):
        """Test find_by_label exact matching."""
        # Get a device label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        device = await first_disc.create_device()
        if device is None:
            pytest.skip("Device creation returned None")

        device_label = await device.get_label()

        # Exact match should work
        async for d in find_by_label(
            device_label,
            exact_match=True,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        ):
            assert d.serial == first_disc.serial

        # Partial label with exact_match=True should NOT match
        if len(device_label) > 4:
            partial_label = device_label[5:9]
            async for d in find_by_label(
                partial_label,
                exact_match=True,
                timeout=1.0,
                broadcast_address="127.0.0.1",
                port=emulator_server,
                idle_timeout_multiplier=0.5,
            ):
                pytest.fail(f"Unexpected yield of {d} from find_by_label()")
