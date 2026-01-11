"""Tests for DeviceGroup batch operation error handling.

This module tests error scenarios for batch operations:
- set_power() - Batch power control with failures
- set_color() - Batch color control with errors
- pulse() - Batch effects with network issues
- set_brightness() - Batch brightness with timeouts
- Empty group edge cases
- Partial failures and error propagation

Note: With asyncio.gather() (used for Python 3.10 compatibility), the first
exception is raised immediately rather than collecting all exceptions into
an ExceptionGroup like TaskGroup does. Tests reflect this behavior.
"""

from __future__ import annotations

import pytest

from lifx.api import DeviceGroup
from lifx.color import HSBK
from lifx.devices import Light
from lifx.exceptions import LifxTimeoutError
from tests.conftest import get_free_port


@pytest.mark.emulator
class TestBatchOperationPartialFailures:
    """Test batch operations with partial failures."""

    async def test_batch_operation_nonexistent_device_fails(
        self, emulator_devices: DeviceGroup
    ):
        """Test batch operation when one device doesn't exist."""
        # Use the first two devices from the emulator, plus add a fake device
        real_devices = list(emulator_devices.devices[:2])

        # Add a device that doesn't exist (will timeout)
        fake_device = Light(
            serial="d073d5999999",
            ip="127.0.0.1",
            port=get_free_port(),
            timeout=0.5,
            max_retries=0,
        )
        real_devices.append(fake_device)

        group = DeviceGroup(real_devices)

        try:
            # Should raise LifxTimeoutError because fake device will timeout
            # (asyncio.gather raises the first exception immediately)
            with pytest.raises(LifxTimeoutError):
                await group.set_power(True, duration=0.0)
        finally:
            # Clean up fake device connection
            await fake_device.connection.close()


@pytest.mark.emulator
class TestBatchOperationScalability:
    """Test batch operations with large numbers of devices."""

    async def test_batch_operation_all_devices(self, emulator_devices: DeviceGroup):
        """Test batch operation with all devices from emulator."""
        assert len(emulator_devices.devices) == 7  # Emulator creates 7 devices
        group = emulator_devices

        # Should handle all 7 devices concurrently
        await group.set_power(True, duration=0.0)

        # Verify devices are on (spot check a few)
        device = group.devices[0]
        is_on = await device.get_power()
        assert is_on


@pytest.mark.emulator
class TestBatchOperationConcurrency:
    """Test batch operation concurrent execution."""

    async def test_batch_operation_concurrent_execution(
        self, emulator_devices: DeviceGroup
    ):
        """Test that batch operations execute requests concurrently."""
        assert len(emulator_devices.devices) >= 5

        # Use first 5 devices from emulator
        devices = list(emulator_devices.devices[:5])
        group = DeviceGroup(devices)

        # Batch operation should complete successfully
        await group.set_power(True, duration=0.0)

        # Verify all devices received the command
        for i, light in enumerate(group.devices):
            is_on = await light.get_power()
            assert is_on, f"Device {i} should be on"


@pytest.mark.emulator
class TestBatchOperationEdgeCases:
    """Test edge cases for batch operations."""

    async def test_batch_empty_device_group(self):
        """Test batch operation on empty DeviceGroup."""
        empty_group = DeviceGroup([])

        # Should complete successfully (no-op)
        await empty_group.set_power(True)
        await empty_group.set_color(HSBK(0, 0, 0.5, 3500))
        await empty_group.set_brightness(0.5)
        await empty_group.pulse(HSBK(120, 1.0, 1.0, 3500))

        # All should succeed with no errors
        assert len(empty_group.devices) == 0

    async def test_batch_operation_all_devices_fail(self):
        """Test batch operation when all devices fail (non-existent devices)."""
        # Create 3 devices that don't exist (will all timeout)
        light_devices = [
            Light(
                serial=f"d073d500{i:04x}",
                ip="127.0.0.1",
                port=get_free_port(),
                timeout=0.1,
                max_retries=0,
            )
            for i in range(3)
        ]
        group = DeviceGroup(light_devices)

        try:
            # Should raise LifxTimeoutError (first exception from gather)
            with pytest.raises(LifxTimeoutError):
                await group.set_power(True, duration=0.0)
        finally:
            # Clean up fake device connections
            for device in light_devices:
                await device.connection.close()

    async def test_batch_operation_mixed_success_failure(
        self, emulator_devices: DeviceGroup
    ):
        """Test that an exception is raised when some devices fail.

        Note: With asyncio.gather, the first exception is raised immediately.
        Some devices may complete successfully before the exception is raised,
        but this is not guaranteed due to concurrent execution.
        """
        # Use one real device from emulator and add fake ones
        real_device = emulator_devices.devices[0]

        # Create fake devices that will fail
        fake_device_1 = Light(
            serial="d073d5999998",
            ip="127.0.0.1",
            port=get_free_port(),
            timeout=0.1,
            max_retries=0,
        )
        fake_device_2 = Light(
            serial="d073d5999999",
            ip="127.0.0.1",
            port=get_free_port(),
            timeout=0.1,
            max_retries=0,
        )

        # Create group with real device and fake ones
        light_devices = [real_device, fake_device_1, fake_device_2]
        group = DeviceGroup(light_devices)

        try:
            # Attempt batch operation - should raise LifxTimeoutError
            with pytest.raises(LifxTimeoutError):
                await group.set_power(True, duration=0.0)
        finally:
            # Clean up fake device connections
            await fake_device_1.connection.close()
            await fake_device_2.connection.close()


@pytest.mark.emulator
class TestBatchOperationErrorDetails:
    """Test detailed error information from batch operations."""

    async def test_exception_contains_device_info(self, emulator_devices: DeviceGroup):
        """Test that exception contains useful device information."""
        # Use one real device from emulator and add a fake device
        real_device = emulator_devices.devices[0]

        # Create fake device that will timeout
        fake_device = Light(
            serial="d073d5999999",
            ip="127.0.0.1",
            port=get_free_port(),
            timeout=0.5,
            max_retries=0,
        )

        # Create group with real and fake devices
        light_devices = [real_device, fake_device]
        group = DeviceGroup(light_devices)

        try:
            # Trigger failure - asyncio.gather raises first exception
            with pytest.raises(LifxTimeoutError) as exc_info:
                await group.set_power(True, duration=0.0)

            # Exception should contain useful info
            exc = exc_info.value
            assert exc is not None
            # Exception message should mention timeout or device info
            assert (
                "timeout" in str(exc).lower() or "acknowledgement" in str(exc).lower()
            )
        finally:
            # Clean up the fake device connection
            await fake_device.connection.close()
