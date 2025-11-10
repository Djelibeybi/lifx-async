"""Tests for concurrent request handling with DeviceConnection.

This module tests concurrent request/response handling through the
user-facing DeviceConnection API.
"""

from __future__ import annotations

import asyncio

import pytest

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
        assert pending.collection_timeout == 0.2  # Default collection timeout
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


class TestSequenceNumberHandling:
    """Test sequence number wraparound and edge cases."""

    async def test_sequence_number_uniqueness(self):
        """Test that create_message increments sequence numbers."""
        from lifx.network.message import MessageBuilder

        builder = MessageBuilder()

        # Create messages and extract sequence numbers from them
        msg1 = builder.create_message(
            Device.GetPower(),
            target=b"\xd0\x73\xd5\x00\x00\x01\x00\x00",
            ack_required=False,
            res_required=True,
        )
        msg2 = builder.create_message(
            Device.GetPower(),
            target=b"\xd0\x73\xd5\x00\x00\x01\x00\x00",
            ack_required=False,
            res_required=True,
        )
        msg3 = builder.create_message(
            Device.GetPower(),
            target=b"\xd0\x73\xd5\x00\x00\x01\x00\x00",
            ack_required=False,
            res_required=True,
        )

        # Parse headers to get sequence numbers
        from lifx.network.message import parse_message

        header1, _ = parse_message(msg1)
        header2, _ = parse_message(msg2)
        header3, _ = parse_message(msg3)

        # Verify sequence numbers are unique and incrementing
        assert header1.sequence == 0
        assert header2.sequence == 1
        assert header3.sequence == 2

    async def test_next_sequence_returns_current(self):
        """Test that next_sequence returns the current sequence number."""
        from lifx.network.message import MessageBuilder

        builder = MessageBuilder()

        # next_sequence() should return the value that will be used next
        seq = builder.next_sequence()
        assert seq == 0

        # Create a message - it should use sequence 0
        msg = builder.create_message(
            Device.GetPower(),
            target=b"\xd0\x73\xd5\x00\x00\x01\x00\x00",
        )

        from lifx.network.message import parse_message

        header, _ = parse_message(msg)
        assert header.sequence == 0

        # Now next_sequence() should return 1
        seq = builder.next_sequence()
        assert seq == 1

    async def test_sequence_number_wraparound(self):
        """Test that sequence numbers wrap around at 256."""
        from lifx.network.message import MessageBuilder

        builder = MessageBuilder()
        builder._sequence = 255

        # Create message at 255
        msg1 = builder.create_message(
            Device.GetPower(),
            target=b"\xd0\x73\xd5\x00\x00\x01\x00\x00",
        )

        from lifx.network.message import parse_message

        header1, _ = parse_message(msg1)
        assert header1.sequence == 255

        # Next message should wrap to 0
        msg2 = builder.create_message(
            Device.GetPower(),
            target=b"\xd0\x73\xd5\x00\x00\x01\x00\x00",
        )
        header2, _ = parse_message(msg2)
        assert header2.sequence == 0


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

        conn = DeviceConnection(serial="d073d5000001", ip="127.0.0.1", port=server.port)

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
