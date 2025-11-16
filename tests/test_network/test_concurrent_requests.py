"""Tests for concurrent request handling with DeviceConnection.

This module tests concurrent request/response handling through the
user-facing DeviceConnection API.
"""

from __future__ import annotations

import asyncio

import pytest

from lifx.const import MULTI_RESPONSE_COLLECTION_TIMEOUT
from lifx.exceptions import LifxProtocolError, LifxTimeoutError
from lifx.network.connection import PendingRequest
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Device


class TestPendingRequest:
    """Test PendingRequest dataclass."""

    def test_pending_request_initialization(self):
        """Test creating a PendingRequest."""
        event = asyncio.Event()
        pending = PendingRequest(sequence=42, event=event)

        assert pending.sequence == 42
        assert pending.event is event
        assert pending.results == []  # Empty list for collecting responses
        assert pending.error is None
        # Default uses MULTI_RESPONSE_COLLECTION_TIMEOUT from const.py
        assert pending.collection_timeout == MULTI_RESPONSE_COLLECTION_TIMEOUT
        assert (
            pending.first_response_time is None
        )  # No response time until first response

    def test_pending_request_with_result(self):
        """Test PendingRequest with result."""
        event = asyncio.Event()
        pending = PendingRequest(sequence=42, event=event)

        # Simulate receiving response
        header = LifxHeader.create(
            pkt_type=Device.StatePower.PKT_TYPE,
            sequence=42,
            target=b"\x00" * 6,
            source=12345,
        )
        payload = b"\x00\x01"  # Sample payload
        pending.results = [(header, payload)]
        pending.event.set()

        assert pending.results[0] == (header, payload)
        assert pending.error is None

    def test_pending_request_with_error(self):
        """Test PendingRequest with error."""
        event = asyncio.Event()
        pending = PendingRequest(sequence=42, event=event)

        # Simulate error
        pending.error = LifxProtocolError("Type mismatch")
        pending.event.set()

        assert len(pending.results) == 0
        assert isinstance(pending.error, LifxProtocolError)


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


class TestConnectionPoolWithPhase2:
    """Test that ConnectionPool works with Phase 2 changes."""

    async def test_connection_pool_basic_operation(self):
        """Test that connection pool still works with Phase 2."""
        from lifx.network.connection import ConnectionPool

        pool = ConnectionPool(max_connections=2)

        async with pool:
            conn1 = await pool.get_connection(serial="d073d5000001", ip="192.168.1.100")
            assert conn1.is_open

            conn2 = await pool.get_connection(serial="d073d5000002", ip="192.168.1.101")
            assert conn2.is_open

            # Getting same connection should return cached instance
            conn1_again = await pool.get_connection(
                serial="d073d5000001", ip="192.168.1.100"
            )
            assert conn1_again is conn1
