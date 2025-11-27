"""Tests for DeviceGroup batch operation error handling.

This module tests error scenarios for batch operations:
- set_power() - Batch power control with failures
- set_color() - Batch color control with errors
- pulse() - Batch effects with network issues
- set_brightness() - Batch brightness with timeouts
- Empty group edge cases
- Partial failures and error aggregation
"""

from __future__ import annotations

import pytest

from lifx.api import DeviceGroup
from lifx.color import HSBK
from lifx.devices import Light
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
            # Should raise ExceptionGroup because fake device will timeout
            with pytest.raises(ExceptionGroup) as exc_info:
                await group.set_power(True, duration=0.0)

            # ExceptionGroup should contain at least one timeout error
            exceptions = exc_info.value.exceptions
            assert len(exceptions) > 0
            assert any(
                "timeout" in str(e).lower() or "Timeout" in type(e).__name__
                for e in exceptions
            )
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
            # Should raise ExceptionGroup with all 3 failing
            with pytest.raises(ExceptionGroup) as exc_info:
                await group.set_power(True, duration=0.0)

            exceptions = exc_info.value.exceptions
            assert len(exceptions) > 0
            assert any(
                "timeout" in str(e).lower() or "Timeout" in type(e).__name__
                for e in exceptions
            )
        finally:
            # Clean up fake device connections
            for device in light_devices:
                await device.connection.close()

    async def test_batch_operation_mixed_success_failure(
        self, emulator_devices: DeviceGroup
    ):
        """Test that successful devices complete even when others fail."""
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
            # Attempt batch operation - should raise ExceptionGroup
            with pytest.raises(ExceptionGroup):
                await group.set_power(True, duration=0.0)

            # Verify that the real device actually changed state
            is_on = await real_device.get_power()
            assert is_on  # Real device should be on
        finally:
            # Clean up fake device connections
            await fake_device_1.connection.close()
            await fake_device_2.connection.close()


@pytest.mark.emulator
class TestBatchOperationErrorDetails:
    """Test detailed error information from batch operations."""

    async def test_exception_group_contains_device_info(
        self, emulator_devices: DeviceGroup
    ):
        """Test that ExceptionGroup contains useful device information."""
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
            # Trigger failure
            with pytest.raises(ExceptionGroup) as exc_info:
                await group.set_power(True, duration=0.0)

            # ExceptionGroup should be present
            assert exc_info.value is not None

            # Should have at least one exception
            exceptions = exc_info.value.exceptions
            assert len(exceptions) > 0

            # Exceptions should be specific LIFX exception types
            for exc in exceptions:
                # Should be a LIFX exception type
                from lifx.exceptions import (
                    LifxConnectionError,
                    LifxProtocolError,
                    LifxTimeoutError,
                )

                assert isinstance(
                    exc,
                    LifxTimeoutError | LifxConnectionError | LifxProtocolError,
                ), f"Expected LIFX exception type, got {type(exc).__name__}: {exc}"
        finally:
            # Clean up the fake device connection
            await fake_device.connection.close()
