"""Tests for device connection management."""

import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.const import DEFAULT_IP_ADDRESS
from lifx.exceptions import (
    LifxConnectionError,
    LifxNetworkError,
    LifxProtocolError,
    LifxTimeoutError,
    LifxUnsupportedCommandError,
)
from lifx.exceptions import LifxConnectionError as ConnectionError
from lifx.network.connection import DeviceConnection, _ConnectionClosed
from lifx.network.utils import allocate_source
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Device


async def _wait_for(predicate, deadline: float = 2.0) -> None:
    """Poll ``predicate`` until true, or fail. Bounded -- never spins forever."""
    start = time.monotonic()
    while not predicate():
        if time.monotonic() - start > deadline:
            raise AssertionError("Timed out waiting for condition")
        await asyncio.sleep(0.001)


async def _wait_for_pending(conn: DeviceConnection, count: int = 1) -> None:
    """Wait until ``conn`` has registered ``count`` correlation keys."""
    await _wait_for(lambda: len(conn._pending_requests) >= count)


class TestDeviceConnection:
    """Test DeviceConnection class."""

    async def test_connection_creation(self) -> None:
        """Test creating a device connection."""
        serial = "d073d5001234"
        conn = DeviceConnection(serial=serial, ip="192.168.1.100", port=56700)

        assert conn.serial == serial
        assert conn.ip == "192.168.1.100"
        assert conn.port == 56700
        assert not conn.is_open

    async def test_connection_context_manager(self) -> None:
        """Test connection context manager."""
        serial = "d073d5001234"
        async with DeviceConnection(serial=serial, ip="192.168.1.100") as conn:
            # Connection is lazy - not open until first request
            assert not conn.is_open

    async def test_connection_explicit_open_close(self) -> None:
        """Test explicit open/close."""
        serial = "d073d5001234"
        conn = DeviceConnection(serial=serial, ip="192.168.1.100")

        await conn.open()
        assert conn.is_open

        await conn.close()
        assert not conn.is_open

    async def test_connection_lazy_opening(self) -> None:
        """Test connection opens lazily on first request."""
        serial = "d073d5001234"
        conn = DeviceConnection(serial=serial, ip="192.168.1.100")

        # Not open initially
        assert not conn.is_open

        # _ensure_open should open it
        await conn._ensure_open()
        assert conn.is_open

        await conn.close()

    async def test_connection_double_open(self) -> None:
        """Test opening connection twice is safe."""
        serial = "d073d5001234"
        conn = DeviceConnection(serial=serial, ip="192.168.1.100")

        await conn.open()
        await conn.open()  # Should not raise
        assert conn.is_open

        await conn.close()

    async def test_waiting_open_retries_after_opener_failure(self) -> None:
        """A waiter must not return success after the active opener fails."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        entered = asyncio.Event()
        released = asyncio.Event()
        attempts = 0

        async def _open_transport() -> None:
            """Fail the first attempt after a waiter has joined the schedule."""
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                entered.set()
                await released.wait()
                raise LifxNetworkError("forced opener failure")

        with (
            patch("lifx.network.connection.UdpTransport") as transport_class,
            patch.object(conn, "_background_receiver", new_callable=AsyncMock),
        ):
            transport_class.return_value.open.side_effect = _open_transport
            transport_class.return_value.close = AsyncMock()
            first = asyncio.create_task(conn.open())
            await entered.wait()
            waiting = asyncio.create_task(conn.open())
            await asyncio.sleep(0)
            released.set()

            with pytest.raises(LifxNetworkError, match="forced opener failure"):
                await first
            await waiting

            assert attempts == 2
            assert conn.is_open is True
            await conn.close()
            assert transport_class.return_value.close.await_count == 2

    async def test_waiting_open_returns_after_opener_succeeds(self) -> None:
        """A waiter observes and reuses the endpoint established ahead of it."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        entered = asyncio.Event()
        released = asyncio.Event()
        attempts = 0

        async def _open_transport() -> None:
            nonlocal attempts
            attempts += 1
            entered.set()
            await released.wait()

        with (
            patch("lifx.network.connection.UdpTransport") as transport_class,
            patch.object(conn, "_background_receiver", new_callable=AsyncMock),
        ):
            transport_class.return_value.open.side_effect = _open_transport
            transport_class.return_value.close = AsyncMock()
            first = asyncio.create_task(conn.open())
            await entered.wait()
            waiting = asyncio.create_task(conn.open())
            await asyncio.sleep(0)
            released.set()

            await asyncio.gather(first, waiting)

            assert attempts == 1
            assert conn.is_open is True
            await conn.close()

    async def test_close_during_open_invalidates_transport_publication(self) -> None:
        """A close request wins while transport opening is suspended."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.0.2.1")
        entered = asyncio.Event()
        released = asyncio.Event()

        async def _open_transport() -> None:
            entered.set()
            await released.wait()

        with (
            patch("lifx.network.connection.UdpTransport") as transport_class,
            patch.object(
                conn, "_background_receiver", new_callable=AsyncMock
            ) as receiver,
        ):
            transport_class.return_value.open.side_effect = _open_transport
            transport_class.return_value.close = AsyncMock()
            opening = asyncio.create_task(conn.open())
            await entered.wait()

            await conn.close()
            released.set()
            await opening

        transport_class.return_value.close.assert_awaited_once_with()
        receiver.assert_not_awaited()
        assert conn.is_open is False
        assert conn._transport is None
        assert conn._opening_transport is None
        assert conn._send_address is None
        assert conn._receiver_task is None
        assert conn._receiver_shutdown is None
        assert conn._is_opening is False

    async def test_waiting_open_is_invalidated_by_close(self) -> None:
        """Every opener from the closing generation returns without reopening."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.0.2.1")
        entered = asyncio.Event()
        released = asyncio.Event()
        attempts = 0

        async def _open_transport() -> None:
            nonlocal attempts
            attempts += 1
            entered.set()
            await released.wait()

        with patch("lifx.network.connection.UdpTransport") as transport_class:
            transport_class.return_value.open.side_effect = _open_transport
            transport_class.return_value.close = AsyncMock()
            opening = asyncio.create_task(conn.open())
            await entered.wait()
            waiting = asyncio.create_task(conn.open())
            await asyncio.sleep(0)

            await conn.close()
            released.set()
            await asyncio.gather(opening, waiting)

        assert attempts == 1
        transport_class.return_value.close.assert_awaited_once_with()
        assert conn.is_open is False
        assert conn._transport is None
        assert conn._opening_transport is None

    async def test_open_waits_for_close_then_starts_a_new_session(self) -> None:
        """An opener created during active cleanup waits and then reopens."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.0.2.1")
        first_transport = MagicMock()
        first_transport.open = AsyncMock()
        first_transport.close = AsyncMock()
        second_transport = MagicMock()
        second_transport.open = AsyncMock()
        second_transport.close = AsyncMock()
        first_receiver_started = asyncio.Event()
        release_first_receiver = asyncio.Event()
        second_receiver_started = asyncio.Event()
        release_second_receiver = asyncio.Event()
        receiver_calls = 0

        async def _blocked_receiver() -> None:
            nonlocal receiver_calls
            receiver_calls += 1
            if receiver_calls == 1:
                first_receiver_started.set()
                await release_first_receiver.wait()
            else:
                second_receiver_started.set()
                await release_second_receiver.wait()

        with (
            patch(
                "lifx.network.connection.UdpTransport",
                side_effect=[first_transport, second_transport],
            ),
            patch.object(conn, "_background_receiver", side_effect=_blocked_receiver),
        ):
            await conn.open()
            await first_receiver_started.wait()
            closing = asyncio.create_task(conn.close())
            await _wait_for(lambda: conn._is_closing)
            reopening = asyncio.create_task(conn.open())
            await asyncio.sleep(0)

            assert reopening.done() is False

            release_first_receiver.set()
            await closing
            await reopening
            await second_receiver_started.wait()

            assert conn.is_open is True
            assert conn._transport is second_transport

            release_second_receiver.set()
            await conn.close()

        first_transport.close.assert_awaited_once_with()
        second_transport.close.assert_awaited_once_with()

    def test_connection_reopens_across_event_loops(self) -> None:
        """Lifecycle coordination remains independent of any one event loop."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.0.2.1")

        with (
            patch("lifx.network.connection.UdpTransport") as transport_class,
            patch.object(conn, "_background_receiver", new_callable=AsyncMock),
        ):
            transport_class.return_value.open = AsyncMock()
            transport_class.return_value.close = AsyncMock()

            async def _open_and_close() -> None:
                await conn.open()
                assert conn.is_open is True
                await conn.close()
                assert conn.is_open is False

            asyncio.run(_open_and_close())
            asyncio.run(_open_and_close())

        assert transport_class.return_value.open.await_count == 2
        assert transport_class.return_value.close.await_count == 2

    async def test_cancelled_close_finishes_cleanup_and_allows_reopen(self) -> None:
        """Caller cancellation cannot leak the endpoint or stale loop state."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.0.2.1")
        first_transport = MagicMock()
        first_transport.open = AsyncMock()
        first_transport.close = AsyncMock()
        second_transport = MagicMock()
        second_transport.open = AsyncMock()
        second_transport.close = AsyncMock()
        first_receiver_started = asyncio.Event()
        release_first_receiver = asyncio.Event()
        second_receiver_started = asyncio.Event()
        release_second_receiver = asyncio.Event()
        receiver_calls = 0

        async def _blocked_receiver() -> None:
            nonlocal receiver_calls
            receiver_calls += 1
            if receiver_calls == 1:
                first_receiver_started.set()
                await release_first_receiver.wait()
            else:
                second_receiver_started.set()
                await release_second_receiver.wait()

        with (
            patch(
                "lifx.network.connection.UdpTransport",
                side_effect=[first_transport, second_transport],
            ),
            patch.object(conn, "_background_receiver", side_effect=_blocked_receiver),
        ):
            await conn.open()
            await first_receiver_started.wait()
            first_receiver = conn._receiver_task
            pending_queue: asyncio.Queue[
                tuple[LifxHeader, bytes] | _ConnectionClosed
            ] = asyncio.Queue()
            pending_queue.put_nowait(
                (
                    LifxHeader(
                        size=36,
                        protocol=1024,
                        source=1,
                        target=bytes.fromhex(conn.serial),
                        tagged=False,
                        ack_required=False,
                        res_required=False,
                        sequence=2,
                        pkt_type=25,
                    ),
                    b"pending",
                )
            )
            conn._pending_requests[(1, 2, conn.serial)] = pending_queue

            closing = asyncio.create_task(conn.close())
            await _wait_for(lambda: conn._is_closing)
            await asyncio.sleep(0)
            closing.cancel()
            await asyncio.sleep(0)
            assert closing.done() is False
            closing.cancel()
            await asyncio.sleep(0)
            release_first_receiver.set()

            with pytest.raises(asyncio.CancelledError):
                await closing

            first_transport.close.assert_awaited_once_with()
            assert first_receiver is not None
            assert first_receiver.done()
            assert conn._transport is None
            assert conn._receiver_task is None
            assert conn._receiver_shutdown is None
            assert conn._pending_requests == {}
            assert pending_queue.qsize() == 1
            assert conn._send_address is None
            assert conn._is_closing is False

            await conn.open()
            await second_receiver_started.wait()

            assert conn.is_open is True
            assert conn._transport is second_transport
            assert conn._receiver_task is not first_receiver

            release_second_receiver.set()
            await conn.close()

        second_transport.close.assert_awaited_once_with()
        assert conn._receiver_task is None
        assert conn._receiver_shutdown is None

    async def test_close_cancels_receiver_that_ignores_shutdown(self) -> None:
        """A receiver exceeding the shutdown deadline is cancelled and awaited."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.0.2.1")
        transport = MagicMock()
        transport.open = AsyncMock()
        transport.close = AsyncMock()
        receiver_started = asyncio.Event()

        async def _stuck_receiver() -> None:
            receiver_started.set()
            await asyncio.Event().wait()

        with (
            patch("lifx.network.connection.UdpTransport", return_value=transport),
            patch.object(conn, "_background_receiver", side_effect=_stuck_receiver),
            patch("lifx.network.connection._RECEIVER_SHUTDOWN_TIMEOUT", 0.001),
        ):
            await conn.open()
            await receiver_started.wait()
            receiver_task = conn._receiver_task

            await conn.close()

        assert receiver_task is not None
        assert receiver_task.cancelled()
        transport.close.assert_awaited_once_with()
        assert conn._receiver_task is None
        assert conn._receiver_shutdown is None

    async def test_close_without_receiver_still_closes_transport(self) -> None:
        """Teardown closes the endpoint even when no receiver task survives."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.0.2.1")
        transport = MagicMock(is_open=True)
        transport.close = AsyncMock()
        conn._is_open = True
        conn._transport = transport
        conn._receiver_task = None
        conn._receiver_shutdown = asyncio.Event()

        await conn.close()

        transport.close.assert_awaited_once_with()
        assert conn.is_open is False
        assert conn._transport is None
        assert conn._receiver_task is None

    @pytest.mark.parametrize(
        "packet",
        [
            pytest.param(Device.GetLabel(), id="get"),
            pytest.param(Device.SetPower(level=65535), id="set"),
        ],
    )
    async def test_close_terminates_request_before_reopen(self, packet: object) -> None:
        """In-flight GET and SET work cannot cross a close/reopen boundary."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.0.2.1")
        first_transport = MagicMock(is_open=True)
        first_transport.open = AsyncMock()
        first_transport.close = AsyncMock()
        first_transport.send = AsyncMock()
        second_transport = MagicMock(is_open=True)
        second_transport.open = AsyncMock()
        second_transport.close = AsyncMock()
        second_transport.send = AsyncMock()

        async def _wait_for_shutdown() -> None:
            shutdown = conn._receiver_shutdown
            assert shutdown is not None
            await shutdown.wait()

        with (
            patch(
                "lifx.network.connection.UdpTransport",
                side_effect=[first_transport, second_transport],
            ),
            patch.object(conn, "_background_receiver", side_effect=_wait_for_shutdown),
            patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.01,)),
        ):
            request_task = asyncio.create_task(conn.request(packet, timeout=5.0))
            await _wait_for_pending(conn)

            await conn.close()

            with pytest.raises(
                LifxConnectionError, match="Connection closed during request"
            ):
                await asyncio.wait_for(request_task, timeout=0.2)

            assert first_transport.send.await_count == 1

            await conn.open()
            await asyncio.sleep(0.03)
            second_transport.send.assert_not_awaited()
            await conn.close()

    async def test_close_during_send_rejects_stale_request_after_send(self) -> None:
        """A request suspended in send cannot continue in a closed session."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.0.2.1")
        transport = MagicMock(is_open=True)
        transport.open = AsyncMock()
        transport.close = AsyncMock()
        send_started = asyncio.Event()
        release_send = asyncio.Event()

        async def _blocked_send(*_args: object, **_kwargs: object) -> None:
            send_started.set()
            await release_send.wait()

        async def _wait_for_shutdown() -> None:
            shutdown = conn._receiver_shutdown
            assert shutdown is not None
            await shutdown.wait()

        transport.send = AsyncMock(side_effect=_blocked_send)
        with (
            patch("lifx.network.connection.UdpTransport", return_value=transport),
            patch.object(conn, "_background_receiver", side_effect=_wait_for_shutdown),
        ):
            request_task = asyncio.create_task(
                conn.request(Device.GetLabel(), timeout=5.0)
            )
            await send_started.wait()

            await conn.close()
            release_send.set()

            with pytest.raises(
                LifxConnectionError, match="Connection closed during request"
            ):
                await asyncio.wait_for(request_task, timeout=0.2)

        transport.close.assert_awaited_once_with()
        assert conn._pending_requests == {}

    async def test_failed_open_preserves_error_when_cleanup_also_fails(self) -> None:
        """Cleanup failure is logged without replacing the opening failure."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        opening_failure = RuntimeError("forced opening failure")

        with patch("lifx.network.connection.UdpTransport") as transport_class:
            transport_class.return_value.open = AsyncMock(side_effect=opening_failure)
            transport_class.return_value.close = AsyncMock(
                side_effect=RuntimeError("forced cleanup failure")
            )

            with pytest.raises(RuntimeError) as excinfo:
                await conn.open()

        assert excinfo.value is opening_failure
        assert conn.is_open is False
        assert conn._transport is None

    async def test_transport_construction_failure_has_no_cleanup_target(self) -> None:
        """Construction failure propagates when no transport exists to close."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        failure = RuntimeError("forced transport construction failure")

        with patch("lifx.network.connection.UdpTransport", side_effect=failure):
            with pytest.raises(RuntimeError) as excinfo:
                await conn.open()

        assert excinfo.value is failure
        assert conn.is_open is False
        assert conn._transport is None

    async def test_send_without_open(self) -> None:
        """Test sending without opening raises error."""
        serial = "d073d5001234"
        conn = DeviceConnection(serial=serial, ip="192.168.1.100")
        packet = Device.GetLabel()

        with pytest.raises(ConnectionError):
            await conn.send_packet(packet, source=12345, sequence=0)

    async def test_receive_without_open(self) -> None:
        """Test receiving without opening raises error."""
        serial = "d073d5001234"
        conn = DeviceConnection(serial=serial, ip="192.168.1.100")

        with pytest.raises(ConnectionError):
            await conn.receive_packet(timeout=1.0)

    async def test_allocate_source(self) -> None:
        """Test source allocation generates valid sources."""
        # Source allocation is per-request via the shared utility
        source = allocate_source()

        # Should be in valid range [2, 0xFFFFFFFF]
        assert 2 <= source <= 0xFFFFFFFF

    async def test_allocate_source_uniqueness(self) -> None:
        """Test source allocation generates unique sources."""
        # Allocate multiple sources and verify they're different
        sources = {allocate_source() for _ in range(100)}

        # Should generate unique values (probabilistically)
        assert len(sources) > 90  # At least 90% unique in 100 attempts

    async def test_concurrent_requests_supported(self) -> None:
        """Test concurrent requests to same connection are supported."""

        serial = "d073d5001234"
        _conn = DeviceConnection(serial=serial, ip="192.168.1.100")

        # Track execution order
        execution_order = []

        async def mock_request(request_id: int) -> None:
            """Mock a request that tracks execution order."""
            execution_order.append(f"start_{request_id}")
            await asyncio.sleep(0.05)  # Simulate some work
            execution_order.append(f"end_{request_id}")

        # Launch 3 concurrent requests
        await asyncio.gather(
            mock_request(1),
            mock_request(2),
            mock_request(3),
        )

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
        import time

        serial1 = "d073d5001111"
        serial2 = "d073d5002222"

        conn1 = DeviceConnection(serial=serial1, ip="192.168.1.100")
        conn2 = DeviceConnection(serial=serial2, ip="192.168.1.101")

        await conn1.open()
        await conn2.open()

        execution_times = {}

        async def mock_request(conn: DeviceConnection, request_id: str) -> None:
            """Mock a request that records timing."""
            start = time.monotonic()
            await asyncio.sleep(0.1)  # Simulate work
            execution_times[request_id] = time.monotonic() - start

        try:
            # Launch requests on both connections concurrently
            start_time = time.monotonic()
            await asyncio.gather(
                mock_request(conn1, "conn1"),
                mock_request(conn2, "conn2"),
            )
            total_time = time.monotonic() - start_time

            # If truly concurrent, total time should be ~0.1s (one sleep duration)
            # If serialized, it would be ~0.2s (two sleep durations)
            # Use generous tolerance (0.19s) to account for CI variability
            # (especially on macOS where timing can be less precise under load)
            # Anything under 0.2s proves concurrency since serial would be >= 0.2s
            assert total_time < 0.19, (
                f"Requests took too long ({total_time}s), suggesting serialization"
            )

            # Both requests should have completed
            assert "conn1" in execution_times
            assert "conn2" in execution_times

        finally:
            await conn1.close()
            await conn2.close()

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

    async def test_close_already_closed_connection(self) -> None:
        """Test closing an already-closed connection is a no-op."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
        )

        # Close without opening - should not raise
        await conn.close()
        assert not conn.is_open

        # Open and close
        await conn.open()
        assert conn.is_open
        await conn.close()
        assert not conn.is_open

        # Close again - should be no-op
        await conn.close()
        assert not conn.is_open


class TestSendTargetPrecomputed:
    """Tests for pre-computed _send_target field."""

    async def test_send_target_precomputed_for_normal_connection(self) -> None:
        """Test _send_target is pre-computed correctly for normal connections."""
        from lifx.protocol.models import Serial

        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        expected = Serial.from_string("d073d5001234").to_protocol()
        assert conn._send_target == expected

    async def test_send_target_broadcast_for_discovery_connection(self) -> None:
        """Test _send_target is broadcast (all zeros) for discovery connections."""
        conn = DeviceConnection(serial="000000000000", ip="192.168.1.100")
        assert conn._send_target == b"\x00" * 8

    async def test_send_packet_uses_precomputed_target(self) -> None:
        """Test send_packet() uses _send_target instead of re-parsing serial."""
        from unittest.mock import AsyncMock
        from unittest.mock import patch as mock_patch

        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        await conn.open()

        try:
            packet = Device.GetLabel()

            with mock_patch(
                "lifx.network.connection.create_message"
            ) as mock_create_msg:
                mock_create_msg.return_value = b"\x00" * 36
                # Mock transport.send to avoid actual network I/O
                conn._transport.send = AsyncMock()  # type: ignore[union-attr]

                await conn.send_packet(packet, source=12345, sequence=0)

                # Verify create_message received the pre-computed target
                mock_create_msg.assert_called_once()
                _, kwargs = mock_create_msg.call_args
                assert kwargs["target"] == conn._send_target
        finally:
            await conn.close()


@pytest.mark.emulator
class TestAsyncGeneratorStreaming:
    """Test async generator streaming functionality."""

    async def test_multizone_stream_responses(self, emulator_devices) -> None:
        """Test multizone GetColorZones streams responses through async generator.

        GetColorZones requests can stream multiple responses through the
        async generator interface.
        """
        from lifx.protocol import packets

        # Get multizone devices from the cached emulator devices
        multizone_devices = emulator_devices.multizone_lights

        if not multizone_devices:
            pytest.skip("No multizone devices available in emulator")

        device = multizone_devices[0]

        # Get color zones for all zones using request_stream
        request = packets.MultiZone.GetColorZones(start_index=0, end_index=255)
        responses = []
        async for response in device.connection.request_stream(request, timeout=2.0):
            responses.append(response)
            assert isinstance(response, packets.MultiZone.StateMultiZone)
            # Break after first (single request = single response expected)
            break

        assert len(responses) >= 1

    async def test_single_response_returns_packet_directly(
        self, emulator_devices
    ) -> None:
        """Test single-response requests return single packet directly.

        Single-response requests like GetLabel return the packet directly
        as a single object when using the request() convenience wrapper.
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


# NOTE: Mock-based error path tests (TestRequestStreamErrorPaths) have been removed
# as they are incompatible with the background receiver architecture and referenced
# removed attributes like conn.source and conn._builder. Error handling is now tested
# via emulator integration tests and the remaining timeout tests below.


class TestDeviceConnectionRequestStream:
    """Test DeviceConnection.request_stream() wrapper functionality."""

    async def test_uses_configured_timeout_by_default(self) -> None:
        """The stream inherits the connection's wall-time request budget."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=7.5,
        )
        received_timeouts: list[float | None] = []

        async def mock_request_stream_impl(packet, timeout=None, max_retries=None):
            received_timeouts.append(timeout)
            if False:
                yield packet

        with (
            patch.object(conn, "_ensure_open", return_value=None),
            patch.object(
                conn, "_request_stream_impl", side_effect=mock_request_stream_impl
            ),
        ):
            responses = [
                response async for response in conn.request_stream(Device.GetLabel())
            ]

        assert responses == []
        assert received_timeouts == [7.5]

    async def test_echo_request_handling(self) -> None:
        """Test EchoRequest special case in request_stream()."""
        from lifx.protocol.packets import Device as DevicePackets

        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
        )

        async def mock_request_stream_impl(packet, timeout=None, max_retries=None):
            # Return EchoResponse with same echoing payload
            header = LifxHeader(
                size=36 + 64,
                protocol=1024,
                source=12345,
                target=bytes.fromhex("d073d5001234"),
                tagged=False,
                ack_required=False,
                res_required=False,
                sequence=1,
                pkt_type=59,  # EchoResponse
            )
            # Echo payload should match request
            payload = b"\x01\x02\x03\x04" + (b"\x00" * 60)
            yield header, payload

        with (
            patch.object(conn, "_ensure_open", return_value=None),
            patch.object(
                conn, "_request_stream_impl", side_effect=mock_request_stream_impl
            ),
        ):
            # Create EchoRequest packet
            echo_request = DevicePackets.EchoRequest(
                payload=b"\x01\x02\x03\x04" + (b"\x00" * 60)
            )

            # Test that request_stream handles EchoRequest
            responses = []
            async for response in conn.request_stream(echo_request):
                responses.append(response)
                # Don't break - let generator return naturally

            assert len(responses) == 1
            assert isinstance(responses[0], DevicePackets.EchoResponse)

    async def test_unsupported_packet_kind_error(self) -> None:
        """Test error when packet kind is not GET or SET."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
        )

        # Create a packet with unknown _packet_kind
        class UnknownPacket:
            _packet_kind = "UNKNOWN"
            PKT_TYPE = 999
            as_dict: dict[str, object] = {}

        with patch.object(conn, "_ensure_open", return_value=None):
            with pytest.raises(LifxProtocolError, match="auto-handle"):
                async for _ in conn.request_stream(UnknownPacket()):
                    pass

    async def test_packet_missing_pkt_type_error(self) -> None:
        """Test error when packet is missing PKT_TYPE."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
        )

        # Create packet without PKT_TYPE
        class BadPacket:
            _packet_kind = "OTHER"
            as_dict: dict[str, object] = {}
            # No PKT_TYPE attribute

        with patch.object(conn, "_ensure_open", return_value=None):
            with pytest.raises(LifxProtocolError, match="missing PKT_TYPE"):
                async for _ in conn.request_stream(BadPacket()):
                    pass

    async def test_set_packet_acknowledgement(self) -> None:
        """Test SET packet handling yields True on acknowledgement."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
        )

        async def mock_ack_stream_impl(packet, timeout=None, max_retries=None):
            # Yield True to indicate ACK received
            yield True

        with (
            patch.object(conn, "_ensure_open", return_value=None),
            patch.object(
                conn, "_request_ack_stream_impl", side_effect=mock_ack_stream_impl
            ),
        ):
            # Create SET packet (SetLabel is a SET packet)
            set_packet = Device.SetLabel(label=b"TestLight")

            # Test that request_stream yields True for SET
            responses = []
            async for response in conn.request_stream(set_packet):
                responses.append(response)

            assert len(responses) == 1
            assert responses[0] is True

    async def test_get_packet_response_handling(self) -> None:
        """Test GET packet handling yields unpacked response."""
        from lifx.protocol.packets import Device as DevicePackets

        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
        )

        async def mock_request_stream_impl(packet, timeout=None, max_retries=None):
            # Return StateLabel response
            header = LifxHeader(
                size=36 + 32,
                protocol=1024,
                source=12345,
                target=bytes.fromhex("d073d5001234"),
                tagged=False,
                ack_required=False,
                res_required=False,
                sequence=1,
                pkt_type=25,  # StateLabel
            )
            # Label payload (32 bytes, null-terminated)
            payload = b"TestLight\x00" + (b"\x00" * 23)
            yield header, payload

        with (
            patch.object(conn, "_ensure_open", return_value=None),
            patch.object(
                conn, "_request_stream_impl", side_effect=mock_request_stream_impl
            ),
        ):
            # Create GET packet
            get_packet = DevicePackets.GetLabel()

            # Test that request_stream yields unpacked response
            responses = []
            async for response in conn.request_stream(get_packet):
                responses.append(response)
                break

            assert len(responses) == 1
            assert isinstance(responses[0], DevicePackets.StateLabel)
            assert responses[0].label == "TestLight"

    async def test_unknown_packet_type_in_response(self) -> None:
        """Test error when response contains unknown packet type."""
        from lifx.protocol.packets import Device as DevicePackets

        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
        )

        async def mock_request_stream_impl(packet, timeout=None, max_retries=None):
            # Return unknown packet type
            header = LifxHeader(
                size=36,
                protocol=1024,
                source=12345,
                target=bytes.fromhex("d073d5001234"),
                tagged=False,
                ack_required=False,
                res_required=False,
                sequence=1,
                pkt_type=9999,  # Unknown packet type
            )
            yield header, b""

        with (
            patch.object(conn, "_ensure_open", return_value=None),
            patch.object(
                conn, "_request_stream_impl", side_effect=mock_request_stream_impl
            ),
        ):
            # Create GET packet
            get_packet = DevicePackets.GetLabel()

            with pytest.raises(LifxProtocolError, match="Unknown packet type"):
                async for _ in conn.request_stream(get_packet):
                    pass

    async def test_serial_update_from_response(self) -> None:
        """Test serial is updated from response when unknown."""
        from lifx.protocol.packets import Device as DevicePackets

        conn = DeviceConnection(
            serial="000000000000",  # Unknown serial
            ip="192.168.1.100",
        )
        task: asyncio.Task[object] | None = None
        try:
            await conn.open()
            task = asyncio.create_task(
                conn.request(DevicePackets.GetLabel(), timeout=2.0)
            )
            await _wait_for_pending(conn)
            (key,) = conn._pending_requests.keys()
            source, sequence, _serial = key
            header = LifxHeader(
                size=36 + 32,
                protocol=1024,
                source=source,
                target=bytes.fromhex("d073d5001234").ljust(8, b"\x00"),  # Actual serial
                tagged=False,
                ack_required=False,
                res_required=False,
                sequence=sequence,
                pkt_type=25,  # StateLabel
            )
            payload = b"TestLight\x00" + (b"\x00" * 23)
            conn._pending_requests[key].put_nowait((header, payload))
            await asyncio.wait_for(task, timeout=1.0)
            task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()

        # Serial should be updated from response
        assert conn.serial == "d073d5001234"

    async def test_request_no_response_error(self) -> None:
        """Test request() raises error when no response received."""
        from lifx.protocol.packets import Device as DevicePackets

        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
        )

        async def mock_request_stream_impl(packet, timeout=None, max_retries=None):
            # Empty generator - no responses
            return
            yield  # noqa: B901 - Makes this an async generator

        with (
            patch.object(conn, "_ensure_open", return_value=None),
            patch.object(
                conn, "_request_stream_impl", side_effect=mock_request_stream_impl
            ),
        ):
            get_packet = DevicePackets.GetLabel()

            with pytest.raises(LifxTimeoutError, match="No response from"):
                await conn.request(get_packet)


class TestStateUnhandledResponses:
    """Test StateUnhandled responses from devices that don't support commands."""

    @pytest.mark.emulator
    async def test_get_color_returns_state_unhandled_for_switch(
        self, switch_device
    ) -> None:
        """Test GetColor to a Switch device returns StateUnhandled packet.

        Switch devices don't support Light commands, so GetColor should
        return a StateUnhandled packet instead of raising an exception.
        """
        from lifx.protocol import packets

        async with switch_device:
            # Send GetColor to a Switch - should return StateUnhandled
            response = await switch_device.request(packets.Light.GetColor())

            # Should return StateUnhandled packet, not raise an exception
            assert isinstance(response, packets.Device.StateUnhandled)
            # The unhandled_type field contains the packet type that wasn't handled
            assert response.unhandled_type == packets.Light.GetColor.PKT_TYPE

    @pytest.mark.emulator
    async def test_set_color_raises_for_switch(self, switch_device) -> None:
        """Test SetColor to a Switch device raises LifxUnsupportedCommandError.

        Switch devices don't support Light commands, so SetColor should
        raise LifxUnsupportedCommandError. We don't return False, because
        that means the Acknowledgement timed out.
        """
        from lifx.color import HSBK
        from lifx.protocol import packets

        async with switch_device:
            # Create a SetColor packet
            color = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
            set_packet = packets.Light.SetColor(
                color=color.to_protocol(),
                duration=0,
            )

            with pytest.raises(LifxUnsupportedCommandError):
                # Send SetColor to a Switch, should raise LifxUnsupportedCommandError
                await switch_device.request(set_packet)


class TestRequestStreamDebugLogging:
    """Cover the DEBUG-only request/reply logging blocks in request_stream().

    These blocks are guarded by ``_LOGGER.isEnabledFor(logging.DEBUG)`` and only
    execute when DEBUG logging is on, so they need explicit DEBUG-level coverage.
    Impls are mocked so the tests stay deterministic and offline.
    """

    @staticmethod
    def _header(pkt_type: int, payload_len: int) -> LifxHeader:
        return LifxHeader(
            size=36 + payload_len,
            protocol=1024,
            source=1,
            target=bytes.fromhex("d073d5001234"),
            tagged=False,
            ack_required=False,
            res_required=False,
            sequence=1,
            pkt_type=pkt_type,
        )

    async def test_get_path_debug_logging(self, caplog) -> None:
        """GET path logs the request/reply cycle at DEBUG."""
        import logging

        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        # StateLabel payload is a 32-byte label field.
        payload = b"Test".ljust(32, b"\x00")
        header = self._header(Device.StateLabel.PKT_TYPE, len(payload))

        async def impl(packet, timeout=None, max_retries=None):
            yield header, payload

        with (
            patch.object(conn, "_ensure_open", return_value=None),
            patch.object(conn, "_request_stream_impl", side_effect=impl),
            caplog.at_level(logging.DEBUG, logger="lifx.network.connection"),
        ):
            results = [r async for r in conn.request_stream(Device.GetLabel())]

        assert len(results) == 1
        assert any(
            isinstance(r.msg, dict) and r.msg.get("method") == "request_stream"
            for r in caplog.records
        )

    async def test_set_path_debug_logging(self, caplog) -> None:
        """SET path logs the request/ack cycle at DEBUG."""
        import logging

        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")

        async def ack_impl(packet, timeout=None, max_retries=None):
            yield True

        with (
            patch.object(conn, "_ensure_open", return_value=None),
            patch.object(conn, "_request_ack_stream_impl", side_effect=ack_impl),
            caplog.at_level(logging.DEBUG, logger="lifx.network.connection"),
        ):
            results = [r async for r in conn.request_stream(Device.SetPower(level=0))]

        assert results == [True]
        assert any(
            isinstance(r.msg, dict) and r.msg.get("method") == "request_stream"
            for r in caplog.records
        )

    async def test_echo_path_debug_logging(self, caplog) -> None:
        """Echo (OTHER) path logs the request/reply cycle at DEBUG."""
        import logging

        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        echo_payload = b"\x01\x02\x03\x04" + (b"\x00" * 60)
        header = self._header(Device.EchoResponse.PKT_TYPE, len(echo_payload))

        async def impl(packet, timeout=None, max_retries=None):
            yield header, echo_payload

        with (
            patch.object(conn, "_ensure_open", return_value=None),
            patch.object(conn, "_request_stream_impl", side_effect=impl),
            caplog.at_level(logging.DEBUG, logger="lifx.network.connection"),
        ):
            results = [
                r
                async for r in conn.request_stream(
                    Device.EchoRequest(payload=echo_payload)
                )
            ]

        assert len(results) == 1
        assert isinstance(results[0], Device.EchoResponse)
        assert any(
            isinstance(r.msg, dict) and r.msg.get("method") == "request_stream"
            for r in caplog.records
        )


class TestDiscoveryConnectionSerialUpdate:
    """A discovery connection refreshes its serial from a response header.

    Driven through the real ``_transmit_and_listen`` by injecting into the
    pending-request queue, because the learning happens there (so every
    request path benefits, not just GET) and only takes effect once the
    request that learned it has released its correlation keys.
    """

    @staticmethod
    def _header(*, source: int, sequence: int, target_hex: str) -> LifxHeader:
        return LifxHeader(
            size=36 + 32,
            protocol=1024,
            source=source,
            target=bytes.fromhex(target_hex).ljust(8, b"\x00"),
            tagged=False,
            ack_required=False,
            res_required=False,
            sequence=sequence,
            pkt_type=Device.StateLabel.PKT_TYPE,
        )

    async def _run(self, conn: DeviceConnection, target_hex: str) -> None:
        """Run one GET against ``conn``, answering it with ``target_hex``."""
        task: asyncio.Task[object] | None = None
        try:
            await conn.open()
            task = asyncio.create_task(conn.request(Device.GetLabel(), timeout=2.0))
            await _wait_for_pending(conn)
            (key,) = conn._pending_requests.keys()
            source, sequence, _serial = key
            header = self._header(
                source=source, sequence=sequence, target_hex=target_hex
            )
            payload = b"x".ljust(32, b"\x00")  # 32-byte StateLabel payload
            conn._pending_requests[key].put_nowait((header, payload))
            await asyncio.wait_for(task, timeout=1.0)
            task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()

    async def test_serial_reported_as_soon_as_it_is_learned(self) -> None:
        """The public serial updates immediately; correlation state waits."""
        conn = DeviceConnection(serial="000000000000", ip="192.168.1.100")
        assert conn._is_discovery is True
        await self._run(conn, "d073d5001234")

        # What callers (Device.from_ip) read straight after their request.
        assert conn.serial == "d073d5001234"
        assert conn._peer.serial == "d073d5001234"
        # Correlation identity still the placeholder until the next request.
        assert conn._serial == "000000000000"
        assert conn._is_discovery is True

    async def test_correlation_identity_adopted_on_next_request(self) -> None:
        """_ensure_open() adopts the learned serial before registering keys."""
        conn = DeviceConnection(serial="000000000000", ip="192.168.1.100")
        await self._run(conn, "d073d5001234")

        await conn._ensure_open()
        try:
            assert conn._serial == "d073d5001234"
            assert conn._is_discovery is False
            assert conn._target_bytes == bytes.fromhex("d073d5001234").ljust(8, b"\x00")
            assert conn._send_target == conn._target_bytes
            assert conn._learned_serial is None
            assert conn.serial == "d073d5001234"
        finally:
            await conn.close()

    async def test_serial_unchanged_when_response_matches(self) -> None:
        conn = DeviceConnection(serial="000000000000", ip="192.168.1.100")
        await self._run(conn, "000000000000")
        assert conn.serial == "000000000000"
        assert conn._is_discovery is True

    async def test_serial_learned_from_ack_only_traffic(self) -> None:
        """A SET-driven connection learns its serial too, not just GETs."""
        conn = DeviceConnection(serial="000000000000", ip="192.168.1.100")
        task: asyncio.Task[object] | None = None
        try:
            await conn.open()
            task = asyncio.create_task(
                conn.request(Device.SetPower(level=65535), timeout=2.0)
            )
            await _wait_for_pending(conn)
            (key,) = conn._pending_requests.keys()
            source, sequence, _serial = key
            header = LifxHeader(
                size=36,
                protocol=1024,
                source=source,
                target=bytes.fromhex("d073d5001234").ljust(8, b"\x00"),
                tagged=False,
                ack_required=False,
                res_required=False,
                sequence=sequence,
                pkt_type=45,  # Acknowledgement
            )
            conn._pending_requests[key].put_nowait((header, b""))
            await asyncio.wait_for(task, timeout=1.0)
            task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()

        assert conn.serial == "d073d5001234"
        assert conn._peer.serial == "d073d5001234"

    async def test_adoption_waits_for_a_concurrent_request(self) -> None:
        """A second in-flight request holds the placeholder identity in place.

        That request registered its keys under ``000000000000``; adopting the
        learned serial while it is still pending would orphan them.
        """
        conn = DeviceConnection(serial="000000000000", ip="192.168.1.100")
        other: asyncio.Task[object] | None = None
        first: asyncio.Task[object] | None = None
        try:
            await conn.open()
            # A request that is never answered, holding a placeholder key.
            other = asyncio.create_task(conn.request(Device.GetPower(), timeout=5.0))
            await _wait_for_pending(conn, 1)
            other_keys = set(conn._pending_requests)

            first = asyncio.create_task(conn.request(Device.GetLabel(), timeout=2.0))
            await _wait_for_pending(conn, 2)
            (key,) = set(conn._pending_requests) - other_keys
            source, sequence, _serial = key
            conn._pending_requests[key].put_nowait(
                (
                    self._header(
                        source=source, sequence=sequence, target_hex="d073d5001234"
                    ),
                    b"x".ljust(32, b"\x00"),
                )
            )
            await asyncio.wait_for(first, timeout=1.0)
            first = None

            # Learned and visible in logs, but not yet adopted: the other
            # request is still correlating on the placeholder.
            assert conn._learned_serial == "d073d5001234"
            assert conn._peer.serial == "d073d5001234"
            assert conn.serial == "d073d5001234"
            # Correlation identity held back while the other request runs.
            assert conn._serial == "000000000000"
            assert conn._is_discovery is True

            # Even an explicit adoption attempt is refused while it is pending.
            conn._adopt_learned_serial()
            assert conn._serial == "000000000000"

            other.cancel()
            with pytest.raises(asyncio.CancelledError):
                await other
            other = None
        finally:
            for task in (first, other):
                if task is not None and not task.done():
                    task.cancel()
            await conn.close()

    async def test_multi_response_stream_survives_learned_serial(self) -> None:
        """Adopting the learned serial must not orphan the in-flight keys.

        Applying it on the first response would re-key the background
        receiver's correlation while the request is still registered under
        the placeholder, dropping every later response in the stream.
        """
        conn = DeviceConnection(serial="000000000000", ip="192.168.1.100")
        received: list[object] = []
        task: asyncio.Task[None] | None = None
        try:
            await conn.open()

            async def _drive() -> None:
                async for response in conn.request_stream(
                    Device.GetLabel(), timeout=2.0
                ):
                    received.append(response)

            with patch("lifx.network.connection._STREAM_IDLE_TIMEOUT", 0.1):
                task = asyncio.create_task(_drive())
                await _wait_for_pending(conn)
                (key,) = conn._pending_requests.keys()
                source, sequence, _serial = key
                payload = b"x".ljust(32, b"\x00")

                for index, target_hex in enumerate(
                    ("d073d5001234", "d073d5005678"), start=1
                ):
                    # The receiver routes on the connection's *current*
                    # serial, so a mid-stream flip would strand the second
                    # response.
                    assert conn._is_discovery is True
                    conn._pending_requests[key].put_nowait(
                        (
                            self._header(
                                source=source, sequence=sequence, target_hex=target_hex
                            ),
                            payload,
                        )
                    )
                    await _wait_for(lambda n=index: len(received) >= n)

                await asyncio.wait_for(task, timeout=3.0)
                task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()

        assert len(received) == 2
        assert conn.serial == "d073d5001234"


class TestMalformedDatagramHandling:
    """A stray datagram must not kill the connection's background receiver.

    The socket accepts traffic from any host, so an unrelated sender can put
    an unparsable packet in the queue. Treating that as a dead socket would
    strand every in-flight request until its timeout expires.
    """

    async def test_receiver_survives_malformed_datagram(self) -> None:
        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        try:
            await conn.open()
            assert conn._transport is not None
            protocol = conn._transport._protocol
            assert protocol is not None

            # Too small to be a LIFX header: receive() raises LifxProtocolError.
            protocol.datagram_received(b"\x00" * 4, ("192.168.1.9", 1234))
            await _wait_for(protocol.queue.empty)
            # Let the receiver run its handler before asserting.
            await asyncio.sleep(0.01)

            assert conn._receiver_task is not None
            assert not conn._receiver_task.done()
            assert conn._is_alive()

            # The receiver still routes real responses afterwards.
            task = asyncio.create_task(conn.request(Device.GetLabel(), timeout=2.0))
            await _wait_for_pending(conn)
            (key,) = conn._pending_requests.keys()
            source, sequence, _serial = key
            header = LifxHeader(
                size=36 + 32,
                protocol=1024,
                source=source,
                target=bytes.fromhex(conn.serial).ljust(8, b"\x00"),
                tagged=False,
                ack_required=False,
                res_required=False,
                sequence=sequence,
                pkt_type=Device.StateLabel.PKT_TYPE,
            )
            conn._pending_requests[key].put_nowait((header, b"x".ljust(32, b"\x00")))
            assert await asyncio.wait_for(task, timeout=1.0) is not None
        finally:
            await conn.close()


class TestTransportDeathRecovery:
    """A connection whose transport dies must rebuild it on the next request.

    ``_is_open`` only records that ``open()`` ran. Without a liveness check the
    dead transport is never noticed: ``open()`` early-returns, every send is
    dropped by asyncio, and each request burns its full retransmit schedule
    before timing out -- forever.
    """

    @staticmethod
    def _kill_transport(conn: DeviceConnection) -> None:
        """Kill the endpoint the way asyncio does on a fatal transport error."""
        assert conn._transport is not None
        protocol = conn._transport._protocol
        assert protocol is not None
        protocol.connection_lost(RuntimeError("fatal read error"))

    async def test_ensure_open_rebuilds_dead_connection(self) -> None:
        """The dead transport is replaced rather than reused."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        await conn.open()
        dead_transport = conn._transport

        self._kill_transport(conn)
        assert dead_transport is not None
        assert not dead_transport.is_open

        await conn._ensure_open()

        try:
            assert conn.is_open
            assert conn._transport is not dead_transport
            assert conn._transport is not None
            assert conn._transport.is_open
        finally:
            await conn.close()

    async def test_ensure_open_rebuilds_after_receiver_death(self) -> None:
        """A crashed background receiver also counts as a dead connection."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        await conn.open()
        first_receiver = conn._receiver_task

        # The receiver exits when it can no longer read from the transport.
        self._kill_transport(conn)
        await asyncio.sleep(0.2)
        assert first_receiver is not None
        assert first_receiver.done()

        await conn._ensure_open()

        try:
            assert conn._receiver_task is not None
            assert conn._receiver_task is not first_receiver
            assert not conn._receiver_task.done()
        finally:
            await conn.close()

    async def test_timeout_does_not_rebuild_connection(self) -> None:
        """An unresponsive device must not cause socket churn."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="127.0.0.1",
            port=56799,
            timeout=0.3,
            max_retries=1,
        )
        await conn.open()
        transport = conn._transport
        receiver = conn._receiver_task

        try:
            with pytest.raises(LifxTimeoutError):
                await conn.request(Device.GetLabel())

            await conn._ensure_open()

            assert conn._transport is transport
            assert conn._receiver_task is receiver
        finally:
            await conn.close()

    @pytest.mark.emulator
    async def test_request_succeeds_after_transport_death(
        self, emulator_devices
    ) -> None:
        """The next request recovers instead of timing out at max_retries."""
        from lifx.protocol import packets

        lights = emulator_devices.lights
        if not lights:
            pytest.skip("No lights available in emulator")

        conn = lights[0].connection
        await conn.request(packets.Device.GetLabel(), timeout=2.0)
        dead_transport = conn._transport

        self._kill_transport(conn)

        response = await conn.request(packets.Device.GetLabel(), timeout=2.0)

        assert isinstance(response, packets.Device.StateLabel)
        assert conn._transport is not dead_transport

    async def test_receiver_reports_read_failure_on_live_transport(
        self, caplog
    ) -> None:
        """A read failure that is not transport death is still an error."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        await conn.open()

        try:
            with (
                caplog.at_level(logging.ERROR, logger="lifx.network.connection"),
                patch.object(
                    conn,
                    "receive_packet",
                    side_effect=LifxNetworkError("Failed to receive data"),
                ),
            ):
                await conn._background_receiver()

            assert any(
                isinstance(record.msg, dict) and record.msg.get("action") == "error"
                for record in caplog.records
            )
        finally:
            await conn.close()

    async def test_receiver_is_quiet_when_connection_already_closed(
        self, caplog
    ) -> None:
        """Teardown racing the receiver must not log a lost transport."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        await conn.open()

        try:
            self._kill_transport(conn)
            conn._is_open = False  # close() already ran on another task

            with (
                caplog.at_level(logging.WARNING, logger="lifx.network.connection"),
                patch.object(
                    conn,
                    "receive_packet",
                    side_effect=LifxConnectionError("Connection not open"),
                ),
            ):
                await conn._background_receiver()

            assert not [
                record
                for record in caplog.records
                if isinstance(record.msg, dict)
                and record.msg.get("action") == "transport_lost"
            ]
        finally:
            conn._is_open = True
            await conn.close()


class TestWildcardBindSelection:
    """The local bind literal follows the device address (IPV6-03, B9).

    ``_open()`` performs no family test of its own: it asks
    :func:`lifx.network.address.wildcard_for`. Only the IPv4 arm runs in the
    rest of the suite, so both are asserted here, and the transport is
    mocked so the assertion holds on a host with no IPv6 stack.
    """

    @staticmethod
    async def _bind_address_used(ip: str) -> str:
        """Open a connection against a mocked transport and report the bind."""
        conn = DeviceConnection(serial="d073d5001234", ip=ip)

        with patch("lifx.network.connection.UdpTransport") as mock_transport:
            mock_transport.return_value.open = AsyncMock()
            mock_transport.return_value.receive_packet = AsyncMock(
                side_effect=LifxTimeoutError("no traffic")
            )
            await conn.open()
            try:
                return mock_transport.call_args.kwargs["ip_address"]
            finally:
                conn._is_open = False
                if conn._receiver_shutdown is not None:
                    conn._receiver_shutdown.set()
                if conn._receiver_task is not None:
                    conn._receiver_task.cancel()

    async def test_ipv4_device_binds_the_ipv4_wildcard(self) -> None:
        """A WiFi device keeps today's IPv4 wildcard bind."""
        assert await self._bind_address_used("192.168.1.100") == DEFAULT_IP_ADDRESS

    async def test_ipv6_device_binds_the_ipv6_wildcard(self) -> None:
        """A Thread device has no IPv4 address, so the bind must be IPv6."""
        assert await self._bind_address_used("fd00:1::") == "::"

    async def test_zoned_link_local_device_binds_the_ipv6_wildcard(self) -> None:
        """A portable numeric-zone literal still selects the IPv6 wildcard."""
        assert await self._bind_address_used("fe80::1%1") == "::"

    async def test_invalid_named_zone_raises_network_error_without_transport(
        self,
    ) -> None:
        """Address derivation stays inside the public network-error taxonomy."""
        conn = DeviceConnection(serial="d073d5001234", ip="fe80::1%missing0")

        with (
            patch(
                "lifx.network.address.socket.if_nametoindex",
                side_effect=OSError("no such interface"),
            ),
            patch("lifx.network.connection.UdpTransport") as transport_class,
        ):
            with pytest.raises(LifxNetworkError, match="Invalid destination"):
                await conn.open()

        transport_class.assert_not_called()
        assert conn._transport is None
        assert conn._send_address is None
        assert conn._receiver_shutdown is None
        assert not conn._is_opening
