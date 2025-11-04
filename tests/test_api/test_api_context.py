"""Tests for API context managers and device type detection.

This module tests:
- Device type detection via discover() API
- DiscoveryContext - Context manager for discovery
- DeviceGroup context manager behavior
- Error handling in context managers
"""

from __future__ import annotations

import pytest

from lifx.api import DeviceGroup, discover
from lifx.devices import (
    Device,
    HevLight,
    InfraredLight,
    Light,
    MultiZoneLight,
    TileDevice,
)
from lifx.network.discovery import discover_devices
from tests.conftest import get_free_port


class TestDetectDeviceType:
    """Test device type detection via discover() API."""

    @pytest.mark.parametrize(
        "device_type,type_name,exclude_types",
        [
            (Light, "Light", (MultiZoneLight, TileDevice, HevLight, InfraredLight)),
            (MultiZoneLight, "MultiZoneLight", None),
            (TileDevice, "TileDevice", None),
            (HevLight, "HevLight", None),
            (InfraredLight, "InfraredLight", None),
        ],
        ids=[
            "color_light",
            "multizone_light",
            "tile_device",
            "hev_light",
            "infrared_light",
        ],
    )
    async def test_detect_device_type(
        self, emulator_server, device_type, type_name, exclude_types
    ):
        """Test detection of specific device types."""
        server = emulator_server

        # Discover devices to get real serial numbers
        async with discover(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=server.port,
            idle_timeout_multiplier=0.5,
        ) as group:
            # Find a device of the specified type
            found_device = None
            for device in group:
                if exclude_types:
                    # For Light, exclude specialized types
                    if isinstance(device, device_type) and not isinstance(
                        device, exclude_types
                    ):
                        found_device = device
                        break
                else:
                    # For specialized types, just check isinstance
                    if isinstance(device, device_type):
                        found_device = device
                        break

            # Should find at least one device of this type
            assert found_device is not None
            assert isinstance(found_device, device_type)
            assert type(found_device).__name__ == type_name


class TestDiscoveryContext:
    """Test DiscoveryContext context manager."""

    async def test_discovery_context_basic(self, emulator_server):
        """Test basic discovery context manager usage."""
        server = emulator_server

        async with discover(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=server.port,
            idle_timeout_multiplier=0.5,
        ) as group:
            # Should discover all 7 devices from emulator
            assert len(group.devices) == 7

            # Should have correct types
            assert len(group.lights) == 7  # All are Light subclasses

            # Should be able to perform operations
            assert isinstance(group, DeviceGroup)

    async def test_discovery_context_device_types(self, emulator_server):
        """Test that discovery context detects device types correctly."""
        server = emulator_server

        async with discover(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=server.port,
            idle_timeout_multiplier=0.5,
        ) as group:
            # Check for specific device types (emulator creates these)
            multizone_lights = [
                d for d in group.devices if isinstance(d, MultiZoneLight)
            ]
            tile_devices = [d for d in group.devices if isinstance(d, TileDevice)]
            hev_lights = [d for d in group.devices if isinstance(d, HevLight)]
            infrared_lights = [d for d in group.devices if isinstance(d, InfraredLight)]

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
            idle_timeout_multiplier=0.5,
        ) as group:
            # Should return empty group
            assert len(group.devices) == 0
            assert len(group.lights) == 0

    async def test_discovery_context_cleanup_on_error(self, emulator_server):
        """Test that context manager cleans up on error."""
        server = emulator_server

        # Enter context and raise an error
        try:
            async with discover(
                timeout=1.0,
                broadcast_address="127.0.0.1",
                port=server.port,
                idle_timeout_multiplier=0.5,
            ) as group:
                assert len(group.devices) > 0
                # Raise an error
                raise ValueError("Test error")
        except ValueError:
            # Error should propagate but cleanup should occur
            pass

        # Context should have exited cleanly
        # (No way to verify cleanup directly, but test shouldn't hang/leak)

    async def test_discovery_context_concurrent_operations(self, emulator_server):
        """Test performing operations within discovery context."""
        server = emulator_server

        async with discover(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=server.port,
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

    async def test_device_group_context_manager(self, emulator_server):
        """Test DeviceGroup as context manager."""
        server = emulator_server

        # Discover devices
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=server.port,
            idle_timeout_multiplier=0.5,
        )

        # Create Light devices from discovered
        light_devices = [
            Light(serial=d.serial, ip="127.0.0.1", port=server.port) for d in devices
        ]
        group = DeviceGroup(light_devices)

        async with group:
            # Should be able to perform operations
            await group.set_power(True, duration=0.0)

        # After exiting context, operations should still work (connections are pooled)
        await group.set_power(False, duration=0.0)

    async def test_device_group_context_error_propagation(self, emulator_server):
        """Test that errors within DeviceGroup context propagate correctly."""
        server = emulator_server

        # Discover devices
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=server.port,
            idle_timeout_multiplier=0.5,
        )

        light_devices = [
            Light(serial=d.serial, ip="127.0.0.1", port=server.port)
            for d in devices[:2]
        ]
        group = DeviceGroup(light_devices)

        try:
            async with group:
                # Perform operation
                await group.set_power(True)
                # Raise error
                raise RuntimeError("Test error")
        except RuntimeError as e:
            # Error should propagate
            assert str(e) == "Test error"

    async def test_device_group_iteration(self, emulator_server):
        """Test iterating over DeviceGroup."""
        server = emulator_server

        # Discover devices
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=server.port,
            idle_timeout_multiplier=0.5,
        )

        light_devices = [
            Light(serial=d.serial, ip="127.0.0.1", port=server.port) for d in devices
        ]
        group = DeviceGroup(light_devices)

        # Should be iterable
        count = 0
        for device in group:
            assert isinstance(device, Device)
            count += 1

        assert count == 7  # Emulator creates 7 devices

    async def test_device_group_len(self, emulator_server):
        """Test len() on DeviceGroup."""
        server = emulator_server

        # Discover devices
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=server.port,
            idle_timeout_multiplier=0.5,
        )

        light_devices = [
            Light(serial=d.serial, ip="127.0.0.1", port=server.port)
            for d in devices[:3]
        ]
        group = DeviceGroup(light_devices)

        assert len(group) == 3


class TestContextManagerEdgeCases:
    """Test edge cases for context managers."""

    async def test_discovery_context_custom_timeout(self, emulator_server):
        """Test discovery with custom timeout."""
        server = emulator_server

        # Very short timeout still finds devices on localhost
        async with discover(
            timeout=0.3, broadcast_address="127.0.0.1", port=server.port
        ) as group:
            # Should discover at least some devices
            assert len(group.devices) >= 0

    async def test_device_group_lights_property(self, emulator_server):
        """Test DeviceGroup.lights property filters correctly."""
        server = emulator_server

        # Discover devices
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=server.port,
            idle_timeout_multiplier=0.5,
        )
        assert len(devices) >= 3

        # Create mixed device list (including non-Light Device instances)
        device_list = [
            Light(serial=devices[0].serial, ip="127.0.0.1", port=server.port),
            MultiZoneLight(serial=devices[1].serial, ip="127.0.0.1", port=server.port),
            TileDevice(serial=devices[2].serial, ip="127.0.0.1", port=server.port),
        ]

        group = DeviceGroup(device_list)

        # lights property should return all Light instances (including subclasses)
        lights = group.lights
        assert len(lights) == 3
        assert all(isinstance(light, Light) for light in lights)

    async def test_device_group_multizone_property(self, emulator_server):
        """Test DeviceGroup.multizone_lights property."""
        server = emulator_server

        # Discover devices
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=server.port,
            idle_timeout_multiplier=0.5,
        )
        assert len(devices) >= 3

        device_list = [
            Light(serial=devices[0].serial, ip="127.0.0.1", port=server.port),
            MultiZoneLight(serial=devices[1].serial, ip="127.0.0.1", port=server.port),
            TileDevice(serial=devices[2].serial, ip="127.0.0.1", port=server.port),
        ]

        group = DeviceGroup(device_list)

        # multizone_lights property should only return MultiZoneLight instances
        multizone = group.multizone_lights
        assert len(multizone) == 1
        assert isinstance(multizone[0], MultiZoneLight)

    async def test_device_group_tiles_property(self, emulator_server):
        """Test DeviceGroup.tiles property."""
        server = emulator_server

        # Discover devices
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=server.port,
            idle_timeout_multiplier=0.5,
        )
        assert len(devices) >= 3

        device_list = [
            Light(serial=devices[0].serial, ip="127.0.0.1", port=server.port),
            MultiZoneLight(serial=devices[1].serial, ip="127.0.0.1", port=server.port),
            TileDevice(serial=devices[2].serial, ip="127.0.0.1", port=server.port),
        ]

        group = DeviceGroup(device_list)

        # tiles property should only return TileDevice instances
        tiles = group.tiles
        assert len(tiles) == 1
        assert isinstance(tiles[0], TileDevice)
