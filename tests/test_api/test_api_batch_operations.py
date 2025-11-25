"""Tests for DeviceGroup batch operations.

This module tests batch operations on multiple devices:
- set_power() - Set power on all devices
- set_color() - Set color on all devices
- set_brightness() - Set brightness on all devices
- pulse() - Pulse effect on all devices
"""

from __future__ import annotations

import asyncio

import pytest

from lifx.api import DeviceGroup
from lifx.color import HSBK


@pytest.mark.emulator
class TestDeviceGroupBatchOperations:
    """Test DeviceGroup batch operations."""

    async def test_batch_set_power(self, emulator_devices: DeviceGroup):
        """Test setting power on all devices."""
        group = emulator_devices

        async with group:
            await group.set_power(True, duration=0.0)

            # Verify power is on (spot check one device)
            await asyncio.sleep(0.1)  # Give time for updates
            device = group.devices[0]
            power = await device.get_power()
            assert power == 65535

    async def test_batch_set_color(self, emulator_devices: DeviceGroup):
        """Test setting color on all devices."""
        group = emulator_devices

        async with group:
            color = HSBK(hue=180, saturation=1.0, brightness=0.5, kelvin=3500)
            await group.set_color(color, duration=0.0)

            # Verify color was set (check one device)
            await asyncio.sleep(0.1)
            device = group.devices[0]
            light_color, _, _ = await device.get_color()
            # Color should be approximately what we set
            assert abs(light_color.hue - 180) < 5

    async def test_batch_set_brightness(self, emulator_devices: DeviceGroup):
        """Test setting brightness on all devices."""
        group = emulator_devices

        async with group:
            await group.set_brightness(0.25, duration=0.0)

            # Verify brightness was set
            await asyncio.sleep(0.1)
            device = group.devices[0]
            color, _, _ = await device.get_color()
            # Brightness should be approximately 0.25
            assert abs(color.brightness - 0.25) < 0.05

    async def test_batch_pulse(self, emulator_devices: DeviceGroup):
        """Test pulse effect on all devices."""
        group = emulator_devices

        async with group:
            color = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
            # Just verify the method doesn't raise
            await group.pulse(color, period=0.5, cycles=1)

    async def test_empty_device_group(self):
        """Test device group with no devices."""
        group = DeviceGroup([])

        assert len(group) == 0
        assert group.lights == []
        assert group.multizone_lights == []
        assert group.matrix_lights == []

        # Batch operations should not raise on empty group
        async with group:
            await group.set_power(True)
            await group.set_color(HSBK(hue=0, saturation=1, brightness=1, kelvin=3500))
            await group.set_brightness(0.5)
            await group.pulse(HSBK(hue=180, saturation=1, brightness=1, kelvin=3500))

    async def test_mixed_device_types(self, emulator_devices: DeviceGroup):
        """Test batch operations with heterogeneous device types."""
        group = emulator_devices

        # Should have mix of device types
        assert len(group.lights) > 0
        assert len(group.multizone_lights) > 0
        assert len(group.matrix_lights) > 0

        # Test batch operation works on mixed types
        await group.set_power(True, duration=0.0)

        # Verify operation succeeded on at least one device
        device = group.lights[0]
        is_on = await device.get_power()
        assert is_on
