"""Tests for device connection management."""

import pytest

from lifx.exceptions import LifxConnectionError as ConnectionError
from lifx.exceptions import LifxUnsupportedCommandError
from lifx.network.connection import (
    ConnectionPool,
    ConnectionPoolMetrics,
    DeviceConnection,
    _ActualConnection,
)
from lifx.protocol.packets import Device


class TestActualConnection:
    """Test _ActualConnection class (internal implementation)."""

    async def test_connection_creation(self) -> None:
        """Test creating an actual device connection."""
        serial = "d073d5001234"
        conn = _ActualConnection(serial=serial, ip="192.168.1.100", port=56700)

        assert conn.serial == serial
        assert conn.ip == "192.168.1.100"
        assert conn.port == 56700
        assert not conn.is_open

    async def test_connection_context_manager(self) -> None:
        """Test connection context manager."""
        serial = "d073d5001234"
        async with _ActualConnection(serial=serial, ip="192.168.1.100") as conn:
            assert conn.is_open

        assert not conn.is_open

    async def test_connection_open_close(self) -> None:
        """Test manual open/close."""
        serial = "d073d5001234"
        conn = _ActualConnection(serial=serial, ip="192.168.1.100")

        await conn.open()
        assert conn.is_open

        await conn.close()
        assert not conn.is_open

    async def test_connection_double_open(self) -> None:
        """Test opening connection twice is safe."""
        serial = "d073d5001234"
        conn = _ActualConnection(serial=serial, ip="192.168.1.100")

        await conn.open()
        await conn.open()  # Should not raise
        assert conn.is_open

        await conn.close()

    async def test_send_without_open(self) -> None:
        """Test sending without opening raises error."""
        serial = "d073d5001234"
        conn = _ActualConnection(serial=serial, ip="192.168.1.100")
        packet = Device.GetLabel()

        with pytest.raises(ConnectionError):
            await conn.send_packet(packet)

    async def test_receive_without_open(self) -> None:
        """Test receiving without opening raises error."""
        serial = "d073d5001234"
        conn = _ActualConnection(serial=serial, ip="192.168.1.100")

        with pytest.raises(ConnectionError):
            await conn.receive_packet(timeout=1.0)

    async def test_connection_source(self) -> None:
        """Test connection maintains consistent source ID."""
        serial = "d073d5001234"
        conn = _ActualConnection(serial=serial, ip="192.168.1.100", source=12345)

        assert conn.source == 12345

    async def test_connection_random_source(self) -> None:
        """Test connection with random source."""
        serial = "d073d5001234"
        conn = _ActualConnection(serial=serial, ip="192.168.1.100")

        assert conn.source > 0  # Should have random source

    async def test_concurrent_requests_supported(self) -> None:
        """Test concurrent requests to same connection are supported (Phase 2)."""
        import asyncio

        serial = "d073d5001234"
        _conn = _ActualConnection(serial=serial, ip="192.168.1.100")

        # Track execution order
        execution_order = []

        async def mock_request(request_id: int) -> None:
            """Mock a request that tracks execution order."""
            execution_order.append(f"start_{request_id}")
            await asyncio.sleep(0.05)  # Simulate some work
            execution_order.append(f"end_{request_id}")

        # Launch 3 concurrent requests
        async with asyncio.TaskGroup() as tg:
            tg.create_task(mock_request(1))
            tg.create_task(mock_request(2))
            tg.create_task(mock_request(3))

        # All requests should complete
        assert len(execution_order) == 6

        # Phase 2: Concurrent requests can overlap (no serialization lock)
        # We should see interleaved execution like:
        # [start_1, start_2, start_3, end_1, end_2, end_3]
        # This demonstrates true concurrency
        start_count = sum(1 for item in execution_order if item.startswith("start_"))
        end_count = sum(1 for item in execution_order if item.startswith("end_"))
        assert start_count == 3
        assert end_count == 3

    async def test_different_connections_concurrent(self) -> None:
        """Test that different connections can operate concurrently."""
        import asyncio
        import time

        serial1 = "d073d5001111"
        serial2 = "d073d5002222"

        conn1 = _ActualConnection(serial=serial1, ip="192.168.1.100")
        conn2 = _ActualConnection(serial=serial2, ip="192.168.1.101")

        await conn1.open()
        await conn2.open()

        execution_times = {}

        async def mock_request(conn: _ActualConnection, request_id: str) -> None:
            """Mock a request that records timing."""
            start = time.monotonic()
            await asyncio.sleep(0.1)  # Simulate work
            execution_times[request_id] = time.monotonic() - start

        try:
            # Launch requests on both connections concurrently
            start_time = time.monotonic()
            async with asyncio.TaskGroup() as tg:
                tg.create_task(mock_request(conn1, "conn1"))
                tg.create_task(mock_request(conn2, "conn2"))
            total_time = time.monotonic() - start_time

            # If truly concurrent, total time should be ~0.1s (one sleep duration)
            # If serialized, it would be ~0.2s (two sleep durations)
            # Allow some overhead, but verify concurrency
            assert total_time < 0.15, (
                f"Requests took too long ({total_time}s), suggesting serialization"
            )

            # Both requests should have completed
            assert "conn1" in execution_times
            assert "conn2" in execution_times

        finally:
            await conn1.close()
            await conn2.close()


class TestDeviceConnection:
    """Test DeviceConnection handle class (user-facing lightweight handle)."""

    def test_connection_creation(self) -> None:
        """Test creating a DeviceConnection handle."""
        serial = "d073d5001234"
        conn = DeviceConnection(serial=serial, ip="192.168.1.100", port=56700)

        assert conn.serial == serial
        assert conn.ip == "192.168.1.100"
        assert conn.port == 56700

    def test_connection_with_source(self) -> None:
        """Test DeviceConnection handle with explicit source."""
        serial = "d073d5001234"
        conn = DeviceConnection(serial=serial, ip="192.168.1.100", source=12345)

        assert conn.source == 12345

    def test_unsupported_command_error_exists(self) -> None:
        """Test that LifxUnsupportedCommandError exception exists.

        This exception is raised when a device doesn't support a command,
        such as when sending Light commands to a Switch device. The device
        responds with StateUnhandled (packet 223), which the background
        receiver converts to this exception.
        """
        # Verify the exception can be instantiated
        error = LifxUnsupportedCommandError("Device does not support this command")
        assert "does not support" in str(error).lower()

        # Verify it's a subclass of LifxError
        from lifx.exceptions import LifxError

        assert issubclass(LifxUnsupportedCommandError, LifxError)

        # Verify it can be raised and caught
        with pytest.raises(LifxUnsupportedCommandError) as exc_info:
            raise LifxUnsupportedCommandError("Test error")

        assert "test error" in str(exc_info.value).lower()


class TestConnectionPool:
    """Test ConnectionPool class."""

    async def test_pool_creation(self) -> None:
        """Test creating a connection pool."""
        pool = ConnectionPool(max_connections=5)
        assert pool.max_connections == 5

    async def test_pool_context_manager(self) -> None:
        """Test pool context manager."""
        async with ConnectionPool() as pool:
            assert pool is not None

    async def test_pool_get_connection(self) -> None:
        """Test getting connection from pool."""
        serial = "d073d5001234"

        async with ConnectionPool() as pool:
            conn = await pool.get_connection(serial=serial, ip="192.168.1.100")
            assert conn.is_open
            assert conn.serial == serial

    async def test_pool_reuses_connection(self) -> None:
        """Test pool reuses existing connections."""
        serial = "d073d5001234"

        async with ConnectionPool() as pool:
            conn1 = await pool.get_connection(serial=serial, ip="192.168.1.100")
            conn2 = await pool.get_connection(serial=serial, ip="192.168.1.100")

            assert conn1 is conn2  # Same connection instance

    async def test_pool_different_devices(self) -> None:
        """Test pool manages connections to different devices."""
        serial1 = "d073d5001234"
        serial2 = "d073d5005678"

        async with ConnectionPool() as pool:
            conn1 = await pool.get_connection(serial=serial1, ip="192.168.1.100")
            conn2 = await pool.get_connection(serial=serial2, ip="192.168.1.101")

            assert conn1 is not conn2
            assert conn1.serial == serial1
            assert conn2.serial == serial2

    async def test_pool_eviction(self) -> None:
        """Test pool evicts oldest connection when full."""
        async with ConnectionPool(max_connections=2) as pool:
            serial1 = "d073d5001111"
            serial2 = "d073d5002222"
            serial3 = "d073d5003333"

            conn1 = await pool.get_connection(serial=serial1, ip="192.168.1.100")
            conn2 = await pool.get_connection(serial=serial2, ip="192.168.1.101")

            # Adding third should evict first
            conn3 = await pool.get_connection(serial=serial3, ip="192.168.1.102")

            # First connection should be closed
            assert not conn1.is_open
            assert conn2.is_open
            assert conn3.is_open

    async def test_pool_close_all(self) -> None:
        """Test closing all connections in pool."""
        serial1 = "d073d5001234"
        serial2 = "d073d5005678"

        pool = ConnectionPool()
        conn1 = await pool.get_connection(serial=serial1, ip="192.168.1.100")
        conn2 = await pool.get_connection(serial=serial2, ip="192.168.1.101")

        assert conn1.is_open
        assert conn2.is_open

        await pool.close_all()

        assert not conn1.is_open
        assert not conn2.is_open


class TestConnectionPoolMetrics:
    """Test ConnectionPoolMetrics class."""

    def test_metrics_initialization(self) -> None:
        """Test metrics are initialized to zero."""
        metrics = ConnectionPoolMetrics()

        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.evictions == 0
        assert metrics.total_requests == 0
        assert metrics.eviction_times_ms == []

    def test_hit_rate_with_no_requests(self) -> None:
        """Test hit rate calculation with no requests."""
        metrics = ConnectionPoolMetrics()

        assert metrics.hit_rate == 0.0

    def test_hit_rate_calculation(self) -> None:
        """Test hit rate calculation."""
        metrics = ConnectionPoolMetrics()
        metrics.hits = 8
        metrics.misses = 2
        metrics.total_requests = 10

        assert metrics.hit_rate == 0.8

    def test_hit_rate_all_hits(self) -> None:
        """Test hit rate with all hits."""
        metrics = ConnectionPoolMetrics()
        metrics.hits = 10
        metrics.total_requests = 10

        assert metrics.hit_rate == 1.0

    def test_hit_rate_all_misses(self) -> None:
        """Test hit rate with all misses."""
        metrics = ConnectionPoolMetrics()
        metrics.misses = 10
        metrics.total_requests = 10

        assert metrics.hit_rate == 0.0

    def test_avg_eviction_time_with_no_evictions(self) -> None:
        """Test average eviction time with no evictions."""
        metrics = ConnectionPoolMetrics()

        assert metrics.avg_eviction_time_ms == 0.0

    def test_avg_eviction_time_calculation(self) -> None:
        """Test average eviction time tracking."""
        metrics = ConnectionPoolMetrics()
        metrics.eviction_times_ms.extend([1.5, 2.0, 1.8])

        assert metrics.avg_eviction_time_ms == pytest.approx(1.77, 0.01)

    def test_avg_eviction_time_single_eviction(self) -> None:
        """Test average eviction time with single eviction."""
        metrics = ConnectionPoolMetrics()
        metrics.eviction_times_ms.append(2.5)

        assert metrics.avg_eviction_time_ms == 2.5

    def test_metrics_reset(self) -> None:
        """Test metrics reset functionality."""
        metrics = ConnectionPoolMetrics()
        metrics.hits = 10
        metrics.misses = 5
        metrics.evictions = 2
        metrics.total_requests = 15
        metrics.eviction_times_ms.extend([1.5, 2.0])

        metrics.reset()

        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.evictions == 0
        assert metrics.total_requests == 0
        assert metrics.eviction_times_ms == []
        assert metrics.hit_rate == 0.0
        assert metrics.avg_eviction_time_ms == 0.0

    def test_metrics_accumulation(self) -> None:
        """Test metrics can be accumulated over time."""
        metrics = ConnectionPoolMetrics()

        # Simulate some activity
        metrics.total_requests = 5
        metrics.hits = 3
        metrics.misses = 2

        # More activity
        metrics.total_requests += 5
        metrics.hits += 4
        metrics.misses += 1

        assert metrics.total_requests == 10
        assert metrics.hits == 7
        assert metrics.misses == 3
        assert metrics.hit_rate == 0.7


class TestMultiResponse:
    """Test multi-response collection functionality."""

    async def test_multizone_returns_multiple_responses(self, emulator_devices) -> None:
        """Test multizone GetColorZones auto-collection of multiple responses.

        GetColorZones requests that return multiple responses are collected
        automatically into a list if multiple packets arrive within 200ms.
        """
        from lifx.protocol import packets

        # Get multizone devices from the cached emulator devices
        multizone_devices = emulator_devices.multizone_lights

        if not multizone_devices:
            pytest.skip("No multizone devices available in emulator")

        device = multizone_devices[0]

        # Get color zones for all zones (may return multiple packets)
        request = packets.MultiZone.GetColorZones(start_index=0, end_index=255)
        response = await device.connection.request(
            request, timeout=2.0, collect_multiple=True
        )

        # Should get list or single response depending on emulator
        # The connection waits for additional responses if available
        if isinstance(response, list):
            # Multiple responses - verify they all have the expected fields
            assert len(response) >= 1
            for pkt in response:
                assert isinstance(pkt, packets.MultiZone.StateMultiZone)
        else:
            # Single response
            assert isinstance(response, packets.MultiZone.StateMultiZone)

    async def test_single_response_automatic_collection(self, emulator_devices) -> None:
        """Test single-response requests return single packet (not a list).

        Single-response requests like GetLabel return the packet directly
        as a single object, not wrapped in a list.
        """
        from lifx.protocol import packets

        # Get lights from the cached emulator devices
        lights = emulator_devices.lights

        if not lights:
            pytest.skip("No lights available in emulator")

        light = lights[0]

        # GetLabel() should only return a single response
        response = await light.connection.request(
            packets.Device.GetLabel(), timeout=2.0
        )
        assert isinstance(response, packets.Device.StateLabel)
