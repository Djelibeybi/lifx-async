"""Tests for concurrent request handling with DeviceConnection.

This module tests concurrent request/response handling through the
user-facing DeviceConnection API.
"""

from __future__ import annotations

import asyncio

import pytest

from lifx.exceptions import LifxTimeoutError
from lifx.protocol.packets import Device


class TestConcurrentRequests:
    """Test concurrent request/response handling with DeviceConnection."""

    async def test_timeout_behavior(self):
        """Test that timeout raises LifxTimeoutError with no server response."""
        from lifx.network.connection import DeviceConnection

        conn = DeviceConnection(
            serial="d073d5000001", ip="192.168.1.100", timeout=0.1, max_retries=0
        )

        # Request should timeout when no server is available
        with pytest.raises(LifxTimeoutError):
            await conn.request(Device.GetPower(), timeout=0.1)


class TestErrorHandling:
    """Test error handling in concurrent scenarios using DeviceConnection."""

    async def test_timeout_when_server_drops_packets(
        self, emulator_server_with_scenarios
    ):
        """Test handling timeout when server drops packets (simulating no response)."""
        # Create a scenario that drops Device.GetPower packets (pkt_type 20)
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={
                "drop_packets": {
                    "20": 1.0  # Drop 100% of GetPower responses (pkt_type 20)
                }
            },
        )

        from lifx.network.connection import DeviceConnection

        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=0.5,
            max_retries=0,  # No retries for faster test
        )

        # This should timeout since server drops all GetPower packets
        with pytest.raises(LifxTimeoutError):
            await conn.request(Device.GetPower(), timeout=0.5)

    async def test_concurrent_requests_with_one_timing_out(
        self, emulator_server_with_scenarios
    ):
        """Test timeout isolation between concurrent requests."""
        # Create a scenario that drops ONLY GetPower packets
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={
                "drop_packets": {
                    "20": 1.0  # Drop 100% of GetPower responses (pkt_type 20)
                }
            },
        )

        from lifx.network.connection import DeviceConnection

        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=1.0,
            max_retries=2,
        )

        # Create multiple concurrent requests where one will timeout
        async def get_power():
            """This will timeout."""
            try:
                await conn.request(Device.GetPower(), timeout=0.3)
                return "power_success"
            except LifxTimeoutError:
                return "power_timeout"

        async def get_label():
            """This should succeed."""
            try:
                await conn.request(Device.GetLabel(), timeout=1.0)
                return "label_success"
            except LifxTimeoutError:
                return "label_timeout"

        # Run both concurrently
        results = await asyncio.gather(get_power(), get_label())

        # Power request should timeout, label should succeed
        assert results[0] == "power_timeout"
        assert results[1] == "label_success"


class TestAsyncGeneratorRequests:
    """Test async generator-based request streaming."""

    async def test_request_stream_single_response(self, emulator_server_with_scenarios):
        """Test request_stream with single response exits immediately after break."""
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={},
        )

        from lifx.network.connection import DeviceConnection

        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=2.0,
            max_retries=2,
        )

        # Stream should yield single response
        received = []
        async for response in conn.request_stream(Device.GetLabel()):
            received.append(response)
            break  # Exit immediately after first response

        assert len(received) == 1
        assert hasattr(received[0], "label")

    async def test_request_stream_convenience_wrapper(
        self, emulator_server_with_scenarios
    ):
        """Test that request() convenience wrapper works correctly."""
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={},
        )

        from lifx.network.connection import DeviceConnection

        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=2.0,
            max_retries=2,
        )

        # request() should return single response directly
        response = await conn.request(Device.GetLabel())
        assert hasattr(response, "label")

    async def test_early_exit_no_resource_leak(self, emulator_server_with_scenarios):
        """Test that breaking early doesn't leak resources."""
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={},
        )

        from lifx.network.connection import DeviceConnection

        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=2.0,
            max_retries=2,
        )

        try:
            # Stream and break early
            async for _response in conn.request_stream(Device.GetLabel()):
                break

            # Verify connection is still functional
            assert conn.is_open

            # Make another request to verify no leak
            response = await conn.request(Device.GetPower())
            assert hasattr(response, "level")
        finally:
            await conn.close()
