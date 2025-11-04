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
from lifx.network.discovery import discover_devices
from tests.conftest import EmulatorServer, get_free_port


class TestBatchOperationPartialFailures:
    """Test batch operations with partial failures."""

    async def test_batch_operation_nonexistent_device_fails(
        self, emulator_server: EmulatorServer
    ):
        """Test batch operation when one device doesn't exist."""
        # Discover real devices
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server.port,
            idle_timeout_multiplier=0.5,
        )
        assert len(devices) > 0

        # Create a group with real devices and one fake device
        light_devices: list[Light] = [
            Light(serial=d.serial, ip="127.0.0.1", port=emulator_server.port)
            for d in devices[:2]
        ]
        # Add a device that doesn't exist (will timeout)
        fake_device = Light(
            serial="d073d5999999", ip="127.0.0.1", port=emulator_server.port
        )
        light_devices.append(fake_device)

        group = DeviceGroup(light_devices)

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


class TestBatchOperationScalability:
    """Test batch operations with large numbers of devices."""

    async def test_batch_operation_all_devices(self, emulator_server):
        """Test batch operation with all devices from emulator."""
        # Discover all devices
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server.port,
            idle_timeout_multiplier=0.5,
        )
        assert len(devices) == 7  # Emulator creates 7 devices

        # Create Light objects
        light_devices = [
            Light(serial=d.serial, ip="127.0.0.1", port=emulator_server.port)
            for d in devices
        ]
        group = DeviceGroup(light_devices)

        # Should handle all 7 devices concurrently
        await group.set_power(True, duration=0.0)

        # Verify devices are on (spot check a few)
        async with light_devices[0]:
            is_on = await light_devices[0].get_power()
            assert is_on


class TestBatchOperationConcurrency:
    """Test batch operation concurrent execution."""

    async def test_batch_operation_concurrent_execution(self, emulator_server):
        """Test that batch operations execute requests concurrently."""
        # Discover devices
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server.port,
            idle_timeout_multiplier=0.5,
        )
        assert len(devices) >= 5

        light_devices = [
            Light(serial=d.serial, ip="127.0.0.1", port=emulator_server.port)
            for d in devices[:5]
        ]
        group = DeviceGroup(light_devices)

        # Batch operation should complete successfully
        await group.set_power(True, duration=0.0)

        # Verify all devices received the command
        for i, light in enumerate(light_devices):
            async with light:
                is_on = await light.get_power()
                assert is_on, f"Device {i} should be on"


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
            Light(serial=f"d073d500{i:04x}", ip="127.0.0.1", port=get_free_port())
            for i in range(3)
        ]
        group = DeviceGroup(light_devices)

        # Should raise ExceptionGroup with all 3 failing
        with pytest.raises(ExceptionGroup) as exc_info:
            await group.set_power(True, duration=0.0)

        assert len(exc_info.value.exceptions) == 3

    async def test_batch_operation_mixed_success_failure(self, emulator_server):
        """Test that successful devices complete even when others fail."""
        # Get one real device
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server.port,
            idle_timeout_multiplier=0.5,
        )
        assert len(devices) > 0

        # Create group with real device and fake ones
        light_devices = [
            Light(
                serial=devices[0].serial, ip="127.0.0.1", port=emulator_server.port
            ),  # Real
            Light(
                serial="d073d5999998", ip="127.0.0.1", port=get_free_port()
            ),  # Fake (will fail)
            Light(
                serial="d073d5999999", ip="127.0.0.1", port=get_free_port()
            ),  # Fake (will fail)
        ]
        group = DeviceGroup(light_devices)

        # Attempt batch operation - should raise ExceptionGroup
        with pytest.raises(ExceptionGroup):
            await group.set_power(True, duration=0.0)

        # Verify that the real device actually changed state
        async with light_devices[0]:
            is_on = await light_devices[0].get_power()
            assert is_on  # Real device should be on


class TestBatchOperationErrorDetails:
    """Test detailed error information from batch operations."""

    async def test_exception_group_contains_device_info(self, emulator_server):
        """Test that ExceptionGroup contains useful device information."""
        # Get one real device
        devices = await discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_server.port,
            idle_timeout_multiplier=0.5,
        )

        # Create group with real and fake devices
        light_devices = [
            Light(serial=devices[0].serial, ip="127.0.0.1", port=emulator_server.port),
            Light(serial="d073d5999999", ip="127.0.0.1", port=get_free_port()),
        ]
        group = DeviceGroup(light_devices)

        # Trigger failure
        with pytest.raises(ExceptionGroup) as exc_info:
            await group.set_power(True, duration=0.0)

        # ExceptionGroup should be present
        assert exc_info.value is not None

        # Should have at least one exception
        exceptions = exc_info.value.exceptions
        assert len(exceptions) > 0

        # Exceptions should be informative
        for exc in exceptions:
            # Should contain keywords indicating failure
            exc_str = str(exc).lower()
            assert any(
                keyword in exc_str
                for keyword in [
                    "timeout",
                    "connection",
                    "error",
                    "failed",
                    "acknowledgement",
                ]
            )
