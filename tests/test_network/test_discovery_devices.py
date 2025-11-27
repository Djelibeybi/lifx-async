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
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.network.discovery import discover_devices


class TestDiscoveredDeviceCreateDevice:
    """Tests for DiscoveredDevice.create_device() method.

    These tests cover lines 48-107 of discovery.py, which create device instances
    of the appropriate type based on product ID.
    """

    @pytest.mark.asyncio
    async def test_create_device_returns_correct_type(self, emulator_port: int) -> None:
        """Test that create_device returns a device instance."""
        first_disc = None
        async for disc in discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        # Create device from first discovered device
        device = await first_disc.create_device()
        assert device is not None

        # Verify it's some type of device
        assert isinstance(
            device,
            Device | Light | MultiZoneLight | HevLight | InfraredLight | MatrixLight,
        )

    @pytest.mark.asyncio
    async def test_create_device_preserves_connection_info(
        self, emulator_port: int
    ) -> None:
        """Test that create_device preserves serial, IP, and port info."""
        first_disc = None
        async for disc in discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        device = await first_disc.create_device()

        # Verify connection info is preserved
        assert device.serial == first_disc.serial
        assert device.ip == first_disc.ip
        assert device.port == first_disc.port

    @pytest.mark.asyncio
    async def test_create_device_all_emulator_devices(self, emulator_port: int) -> None:
        """Test create_device works for all device types in emulator.

        The emulator creates 7 devices:
        - 1 color light
        - 1 infrared light
        - 1 HEV light
        - 2 multizone lights
        - 1 tile device
        - 1 color temperature light
        """
        device_types: dict[str, int] = {}

        async for disc in discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            device = await disc.create_device()
            if device is not None:
                async with device:
                    device_type = type(device).__name__
                    device_types[device_type] = device_types.get(device_type, 0) + 1

                    # Each created device should have valid connection info
                    assert device.serial == disc.serial
                    assert device.ip == disc.ip
                    assert device.port == disc.port

        # Verify we have expected device types
        assert "Light" in device_types and "InfraredLight" in device_types


class TestDiscoveryEdgeCasesWithEmulator:
    """Additional edge case tests using the emulator server."""

    @pytest.mark.asyncio
    async def test_discover_devices_with_multiple_simultaneous_creates(
        self, emulator_port: int
    ) -> None:
        """Test creating multiple device instances simultaneously.

        This tests that create_device() works correctly when called
        multiple times concurrently.
        """
        import asyncio

        discovered_list = []
        async for disc in discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            discovered_list.append(disc)
            if len(discovered_list) >= 2:
                break

        # Create devices concurrently
        devices = await asyncio.gather(
            *[d.create_device() for d in discovered_list[:2]]
        )

        assert len(devices) == 2
        assert devices[0].serial == discovered_list[0].serial
        assert devices[1].serial == discovered_list[1].serial

    @pytest.mark.asyncio
    async def test_discover_devices_response_time_accuracy(
        self, emulator_port: int
    ) -> None:
        """Test that response_time is accurately calculated."""
        devices = []
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            devices.append(disc)
            if len(devices) >= 2:
                break

        assert len(devices) > 0

        # All response times should be positive and reasonable
        # It is possible for the emulator to respond "instantly"
        for device in devices:
            assert device.response_time >= 0.0
            # Response time should be less than 1 second for localhost
            assert device.response_time < 1.0

    @pytest.mark.asyncio
    async def test_discover_all_devices_have_valid_ports(
        self, emulator_port: int
    ) -> None:
        """Test that all discovered devices have valid port numbers."""
        devices = []
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            devices.append(disc)
            if len(devices) >= 2:
                break

        assert len(devices) > 0

        for device in devices:
            # Port should be valid
            assert 1024 <= device.port <= 65535
