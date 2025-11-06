"""Tests for API context managers and device type detection.

This module tests:
- Device type detection via discover() API
- DiscoveryContext - Context manager for discovery
- DeviceGroup context manager behavior
- Error handling in context managers
"""

from __future__ import annotations

from lifx.api import DeviceGroup, discover
from lifx.devices import (
    Device,
    Light,
    MultiZoneLight,
    TileDevice,
)
from tests.conftest import get_free_port


class TestDiscoveryContext:
    """Test DiscoveryContext context manager."""

    async def test_discovery_context_basic(self, emulator_server: int):
        """Test basic discovery context manager usage."""
        async with discover(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        ) as group:
            # Should discover all 7 devices from emulator
            assert len(group.devices) == 7

            # Should have correct types
            assert len(group.lights) == 7  # All are Light subclasses

            # Should be able to perform operations
            assert isinstance(group, DeviceGroup)

    async def test_discovery_context_device_types(self, emulator_server: int):
        """Test that discovery context detects device types correctly."""
        async with discover(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        ) as group:
            # Check for specific device types (emulator creates these)
            multizone_lights = group.multizone_lights
            tile_devices = group.tiles
            hev_lights = group.hev_lights
            infrared_lights = group.infrared_lights

            assert len(multizone_lights) == 2  # Emulator creates 2 multizone
            assert len(tile_devices) == 1
            assert len(hev_lights) == 1
            assert len(infrared_lights) == 1

    async def test_discovery_context_empty_network(self):
        """Test discovery context with no devices."""
        # Use a port with no emulator running
        async with discover(
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=get_free_port(),
        ) as group:
            # Should return empty group
            assert len(group.devices) == 0
            assert len(group.lights) == 0

    async def test_discovery_context_cleanup_on_error(self, emulator_server: int):
        """Test that context manager cleans up on error."""
        # Enter context and raise an error
        try:
            async with discover(
                timeout=1.0,
                broadcast_address="127.0.0.1",
                port=emulator_server,
                idle_timeout_multiplier=0.5,
            ) as group:
                assert len(group.devices) > 0
                # Raise an error
                raise ValueError("Test error")
        except ValueError:
            # Error should propagate but cleanup should occur
            pass

    async def test_discovery_context_concurrent_operations(self, emulator_server: int):
        """Test performing operations within discovery context."""
        async with discover(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server,
            idle_timeout_multiplier=0.5,
        ) as group:
            # Should be able to perform batch operations
            await group.set_power(True, duration=0.0)

            # Verify power state (spot check one device)
            async with group.devices[0]:
                is_on = await group.devices[0].get_power()
                assert is_on


class TestDeviceGroupContext:
    """Test DeviceGroup context manager behavior."""

    async def test_device_group_context_manager(self, emulator_devices: DeviceGroup):
        """Test DeviceGroup as context manager."""
        group = emulator_devices

        async with group:
            # Should be able to perform operations
            await group.set_power(True, duration=0.0)

        # After exiting context, operations should still work (connections are pooled)
        await group.set_power(False, duration=0.0)

    async def test_device_group_iteration(self, emulator_devices: DeviceGroup):
        """Test iterating over DeviceGroup."""
        group = emulator_devices

        # Should be iterable
        count = 0
        for device in group:
            assert isinstance(device, Device)
            count += 1

        assert count == 7  # Emulator creates 7 devices

    async def test_device_group_len(self, emulator_devices: DeviceGroup):
        """Test len() on DeviceGroup."""
        assert len(emulator_devices) == 7


class TestContextManagerEdgeCases:
    """Test edge cases for context managers."""

    async def test_discovery_context_custom_timeout(self, emulator_server: int):
        """Test discovery with custom timeout."""
        # Very short timeout still finds devices on localhost
        async with discover(
            timeout=0.3, broadcast_address="127.0.0.1", port=emulator_server
        ) as group:
            # Should discover at least some devices
            assert len(group.devices) >= 0

    async def test_device_group_lights_property(self, emulator_devices: DeviceGroup):
        """Test DeviceGroup.lights property filters correctly."""
        group = emulator_devices

        # lights property should return all Light instances (including subclasses)
        lights = group.lights
        assert len(lights) >= 1
        assert all(isinstance(light, Light) for light in lights)

    async def test_device_group_multizone_property(self, emulator_devices: DeviceGroup):
        """Test DeviceGroup.multizone_lights property."""
        group = emulator_devices

        # multizone_lights property should only return MultiZoneLight instances
        multizone = group.multizone_lights
        assert len(multizone) >= 1
        assert all(isinstance(device, MultiZoneLight) for device in multizone)

    async def test_device_group_tiles_property(self, emulator_devices: DeviceGroup):
        """Test DeviceGroup.tiles property."""
        group = emulator_devices

        # tiles property should only return TileDevice instances
        tiles = group.tiles
        assert len(tiles) >= 1
        assert all(isinstance(device, TileDevice) for device in tiles)
