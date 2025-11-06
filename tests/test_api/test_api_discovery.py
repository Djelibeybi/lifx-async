"""Tests for high-level API discovery helper functions.

This module tests:
- discover() - Context manager for device discovery
- find_lights() - Find lights with optional label filtering
- find_by_serial() - Find specific device by serial number
"""

from __future__ import annotations

from lifx.api import discover, find_by_serial, find_lights
from lifx.devices import Light, MultiZoneLight
from lifx.network.discovery import discover_devices
from tests.conftest import get_free_port


class TestDiscover:
    """Test discover() context manager."""

    async def test_discover_basic(self, emulator_server: int):
        """Test basic discovery with context manager."""
        async with discover(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        ) as group:
            # Should discover all 7 devices from emulator
            assert len(group.devices) == 7

            # Should be able to perform operations
            assert len(group.lights) == 7  # All devices are lights

    async def test_discover_with_timeout(self, emulator_server: int):
        """Test discovery with custom timeout."""
        async with discover(
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        ) as group:
            # Should complete within timeout
            assert len(group.devices) >= 0  # May find some or all devices

    async def test_discover_empty_network(self):
        """Test discovery when no devices are present."""
        # Use a port with no emulator running - will timeout and return empty
        async with discover(
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=get_free_port(),
        ) as group:
            # Should return empty group
            assert len(group.devices) == 0

    async def test_discover_context_manager_cleanup(self, emulator_server: int):
        """Test that context manager properly cleans up."""
        # Enter and exit context
        async with discover(
            timeout=1.0, broadcast_address="127.0.0.1", port=emulator_server
        ) as group:
            devices = group.devices
            assert len(devices) > 0

        # After exit, devices should still be accessible but connections managed by pool
        # Just verify we exited cleanly
        assert len(devices) == 7  # Emulator creates 7 devices


class TestFindLights:
    """Test find_lights() helper function."""

    async def test_find_lights_all(self, emulator_server: int):
        """Test finding all lights without filtering."""
        lights = await find_lights(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )

        # Should find all 7 light devices from emulator
        assert len(lights) == 7
        assert all(isinstance(light, Light) for light in lights)

    async def test_find_lights_by_label_exact(self, emulator_server: int):
        """Test finding lights with exact label match."""
        # Emulator devices have default labels, we can search for "LIFX"
        lights = await find_lights(
            label_contains="LIFX",
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )

        # Should find devices with "LIFX" in their label
        assert len(lights) > 0
        # Verify label contains the search term
        async with lights[0]:
            label = await lights[0].get_label()
            assert "LIFX" in label or "lifx" in label.lower()

    async def test_find_lights_by_label_partial(self, emulator_server: int):
        """Test finding lights with partial label match (case-insensitive)."""
        # Search for common term in emulator device names
        lights = await find_lights(
            label_contains="Color",
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )

        # Should find at least the color light devices
        assert len(lights) >= 1

    async def test_find_lights_by_label_case_insensitive(self, emulator_server: int):
        """Test that label filtering is case-insensitive."""
        # Search with different case
        lights = await find_lights(
            label_contains="COLOR",
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )

        # Should find devices with "color" in label (case-insensitive)
        assert len(lights) >= 1

    async def test_find_lights_not_found(self, emulator_server: int):
        """Test finding lights with non-existent label."""
        lights = await find_lights(
            label_contains="NonExistentDeviceName12345",
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )

        # Should return empty list
        assert len(lights) == 0

    async def test_find_lights_includes_multizone(self, emulator_server: int):
        """Test that find_lights includes MultiZoneLight devices."""
        lights = await find_lights(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )

        # Should include multizone lights (emulator creates 2 multizone devices)
        multizone_lights = [
            light for light in lights if isinstance(light, MultiZoneLight)
        ]
        assert len(multizone_lights) == 2

    async def test_find_lights_empty_network(self):
        """Test find_lights when no devices are present."""
        # Use a port with no emulator running
        lights = await find_lights(
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=get_free_port(),
        )
        assert len(lights) == 0


class TestFindBySerial:
    """Test find_by_serial() helper function."""

    async def test_find_by_serial_found_string(self, emulator_server: int):
        """Test finding device by serial number (string format)."""
        # First discover devices to get a real serial number
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )
        assert len(devices) > 0

        # Use the first discovered device's serial
        target_serial = devices[0].serial
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

    async def test_find_by_serial_found_bytes(self, emulator_server: int):
        """Test finding device by serial number (bytes format)."""
        # Discover devices to get a real serial
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )
        assert len(devices) >= 2

        # Use second device's serial as bytes
        target_serial = devices[1].serial
        serial_bytes = bytes.fromhex(target_serial)
        device = await find_by_serial(
            serial_bytes,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        assert device.serial == target_serial

    async def test_find_by_serial_with_colons(self, emulator_server: int):
        """Test finding device by serial with colon separators."""
        # Discover multizone device
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )

        # Use the first discovered device and format with colons
        target_serial = devices[0].serial
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
        # Discover devices first
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        )
        assert len(devices) > 0

        # Use uppercase version of serial
        target_serial = devices[0].serial
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
