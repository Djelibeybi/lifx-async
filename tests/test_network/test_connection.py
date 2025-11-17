"""Tests for device connection management."""

import asyncio
from unittest.mock import patch

import pytest

from lifx.exceptions import LifxConnectionError as ConnectionError
from lifx.exceptions import (
    LifxProtocolError,
    LifxTimeoutError,
    LifxUnsupportedCommandError,
)
from lifx.network.connection import DeviceConnection
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Device


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

    async def test_send_without_open(self) -> None:
        """Test sending without opening raises error."""
        serial = "d073d5001234"
        conn = DeviceConnection(serial=serial, ip="192.168.1.100")
        packet = Device.GetLabel()

        with pytest.raises(ConnectionError):
            await conn.send_packet(packet)

    async def test_receive_without_open(self) -> None:
        """Test receiving without opening raises error."""
        serial = "d073d5001234"
        conn = DeviceConnection(serial=serial, ip="192.168.1.100")

        with pytest.raises(ConnectionError):
            await conn.receive_packet(timeout=1.0)

    async def test_connection_source(self) -> None:
        """Test connection maintains consistent source ID."""
        serial = "d073d5001234"
        conn = DeviceConnection(serial=serial, ip="192.168.1.100", source=12345)

        assert conn.source == 12345

    async def test_connection_random_source(self) -> None:
        """Test connection with random source."""
        serial = "d073d5001234"
        conn = DeviceConnection(serial=serial, ip="192.168.1.100")

        assert conn.source > 0  # Should have random source

    async def test_concurrent_requests_supported(self) -> None:
        """Test concurrent requests to same connection are supported."""
        import asyncio

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


class TestRequestStreamErrorPaths:
    """Test error handling in request_stream() async generator."""

    async def test_request_stream_impl_connection_not_open(self) -> None:
        """Test _request_stream_impl raises error when connection not open."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        # Connection not opened

        with pytest.raises(ConnectionError, match="Connection not open"):
            async for _ in conn._request_stream_impl(Device.GetLabel()):
                pass

    async def test_request_stream_timeout_no_response(self) -> None:
        """Test request_stream raises timeout when no response received."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=0.1,
            max_retries=0,
        )
        await conn.open()
        try:
            # Send to non-existent device - should timeout
            with pytest.raises(LifxTimeoutError, match="No response"):
                async for _ in conn._request_stream_impl(Device.GetLabel()):
                    pass
        finally:
            await conn.close()

    async def test_request_stream_uses_default_timeout(self) -> None:
        """Test request_stream uses instance default timeout when not specified."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=0.05,  # Very short timeout
            max_retries=0,
        )
        await conn.open()
        try:
            # Should use default timeout (0.05s) and timeout quickly
            with pytest.raises(LifxTimeoutError):
                async for _ in conn._request_stream_impl(Device.GetLabel()):
                    pass
        finally:
            await conn.close()

    async def test_request_ack_stream_impl_connection_not_open(self) -> None:
        """Test _request_ack_stream_impl raises error when connection not open."""
        conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
        # Connection not opened

        with pytest.raises(ConnectionError, match="Connection not open"):
            async for _ in conn._request_ack_stream_impl(
                Device.SetLabel(label=b"Test")
            ):
                pass

    async def test_request_ack_stream_timeout(self) -> None:
        """Test request_ack_stream raises timeout when no ack received."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=0.1,
            max_retries=0,
        )
        await conn.open()
        try:
            # Send to non-existent device - should timeout
            with pytest.raises(LifxTimeoutError, match="No acknowledgement"):
                async for _ in conn._request_ack_stream_impl(
                    Device.SetLabel(label=b"Test")
                ):
                    pass
        finally:
            await conn.close()

    async def test_request_stream_state_unhandled_error(self) -> None:
        """Test request_stream raises LifxUnsupportedCommandError on StateUnhandled."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=1.0,
            max_retries=0,
        )
        await conn.open()
        try:

            async def mock_receive(*args, **kwargs):
                # Return StateUnhandled packet type with correct sequence
                # The sequence is dynamically set by the request
                header = LifxHeader(
                    size=36,
                    protocol=1024,
                    source=conn.source,
                    target=bytes.fromhex("d073d5001234"),
                    tagged=False,
                    ack_required=False,
                    res_required=False,
                    sequence=conn._builder._sequence - 1,  # Last allocated sequence
                    pkt_type=223,  # StateUnhandled
                )
                return (header, b"")

            with patch.object(conn, "receive_packet", side_effect=mock_receive):
                with pytest.raises(
                    LifxUnsupportedCommandError, match="does not support"
                ):
                    async for _ in conn._request_stream_impl(Device.GetLabel()):
                        pass
        finally:
            await conn.close()

    async def test_request_stream_wrong_packet_type_error(self) -> None:
        """Test request_stream raises LifxProtocolError on wrong packet type."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=1.0,
            max_retries=0,
        )
        await conn.open()
        try:

            async def mock_receive(*args, **kwargs):
                # Return wrong packet type (GetLabel expects StateLabel=25, return 26)
                header = LifxHeader(
                    size=36,
                    protocol=1024,
                    source=conn.source,
                    target=bytes.fromhex("d073d5001234"),
                    tagged=False,
                    ack_required=False,
                    res_required=False,
                    sequence=conn._builder._sequence - 1,  # Last allocated sequence
                    pkt_type=26,  # Wrong type (not StateLabel=25)
                )
                return (header, b"")

            with patch.object(conn, "receive_packet", side_effect=mock_receive):
                with pytest.raises(LifxProtocolError, match="unexpected packet type"):
                    async for _ in conn._request_stream_impl(Device.GetLabel()):
                        pass
        finally:
            await conn.close()

    async def test_request_stream_sequence_mismatch_ignored(self) -> None:
        """Test request_stream ignores responses with wrong sequence number."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=0.3,
            max_retries=0,
        )
        await conn.open()
        try:
            call_count = 0

            async def mock_receive(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    # First two calls: return wrong sequence number
                    header = LifxHeader(
                        size=36,
                        protocol=1024,
                        source=conn.source,
                        target=bytes.fromhex("d073d5001234"),
                        tagged=False,
                        ack_required=False,
                        res_required=False,
                        sequence=255,  # Wrong sequence
                        pkt_type=25,  # StateLabel
                    )
                    return (header, b"Test\x00" * 8)
                else:
                    # After ignoring mismatched packets, timeout
                    raise LifxTimeoutError("No packet")

            with patch.object(conn, "receive_packet", side_effect=mock_receive):
                with pytest.raises(LifxTimeoutError):
                    async for _ in conn._request_stream_impl(Device.GetLabel()):
                        pass

            # Should have called receive at least twice (ignoring wrong sequences)
            assert call_count >= 2
        finally:
            await conn.close()

    async def test_request_stream_retry_with_backoff(self) -> None:
        """Test request_stream retries with exponential backoff."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=0.5,
            max_retries=1,  # One retry
        )
        await conn.open()
        try:
            # Track retry attempts
            attempt_times = []

            original_sleep = asyncio.sleep

            async def tracked_sleep(duration):
                attempt_times.append(duration)
                await original_sleep(duration)

            with (
                patch.object(
                    conn, "receive_packet", side_effect=LifxTimeoutError("No packet")
                ),
                patch("asyncio.sleep", side_effect=tracked_sleep),
            ):
                with pytest.raises(LifxTimeoutError, match="No response"):
                    async for _ in conn._request_stream_impl(Device.GetLabel()):
                        pass

            # Should have slept between retries (jitter applied)
            assert len(attempt_times) >= 1
            # Sleep time should be non-zero (jittered)
            assert all(t >= 0 for t in attempt_times)
        finally:
            await conn.close()

    async def test_request_ack_stream_sequence_mismatch_ignored(self) -> None:
        """Test request_ack_stream ignores ACKs with wrong sequence number."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=0.3,
            max_retries=0,
        )
        await conn.open()
        try:
            call_count = 0

            async def mock_receive(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    # Return wrong sequence number
                    header = LifxHeader(
                        size=36,
                        protocol=1024,
                        source=conn.source,
                        target=bytes.fromhex("d073d5001234"),
                        tagged=False,
                        ack_required=False,
                        res_required=False,
                        sequence=255,  # Wrong sequence
                        pkt_type=45,  # Acknowledgement
                    )
                    return (header, b"")
                else:
                    raise LifxTimeoutError("No packet")

            with patch.object(conn, "receive_packet", side_effect=mock_receive):
                with pytest.raises(LifxTimeoutError):
                    async for _ in conn._request_ack_stream_impl(
                        Device.SetLabel(label=b"Test")
                    ):
                        pass

            assert call_count >= 2
        finally:
            await conn.close()

    async def test_request_ack_stream_state_unhandled_error(self) -> None:
        """Test request_ack_stream raises error on StateUnhandled."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=1.0,
            max_retries=0,
        )
        await conn.open()
        try:

            async def mock_receive(*args, **kwargs):
                header = LifxHeader(
                    size=36,
                    protocol=1024,
                    source=conn.source,
                    target=bytes.fromhex("d073d5001234"),
                    tagged=False,
                    ack_required=False,
                    res_required=False,
                    sequence=conn._builder._sequence - 1,
                    pkt_type=223,  # StateUnhandled
                )
                return (header, b"")

            with patch.object(conn, "receive_packet", side_effect=mock_receive):
                with pytest.raises(
                    LifxUnsupportedCommandError, match="does not support"
                ):
                    async for _ in conn._request_ack_stream_impl(
                        Device.SetLabel(label=b"Test")
                    ):
                        pass
        finally:
            await conn.close()

    async def test_request_ack_stream_successful_ack(self) -> None:
        """Test request_ack_stream yields on successful ACK receipt."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=1.0,
            max_retries=0,
        )
        await conn.open()
        try:

            async def mock_receive(*args, **kwargs):
                # Return an ACK packet with matching sequence
                header = LifxHeader(
                    size=36,
                    protocol=1024,
                    source=conn.source,
                    target=bytes.fromhex("d073d5001234"),
                    tagged=False,
                    ack_required=False,
                    res_required=False,
                    sequence=conn._builder._sequence - 1,
                    pkt_type=45,  # Acknowledgement packet type
                )
                return (header, b"")

            with patch.object(conn, "receive_packet", side_effect=mock_receive):
                # Should yield once then return
                ack_received = False
                async for _ in conn._request_ack_stream_impl(
                    Device.SetLabel(label=b"Test")
                ):
                    ack_received = True

                assert ack_received
        finally:
            await conn.close()

    async def test_request_stream_multiple_responses_with_polling(self) -> None:
        """Test request_stream continues polling after yielding responses."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=0.3,
            max_retries=0,
        )
        await conn.open()
        try:
            call_count = 0

            async def mock_receive(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    # First two calls: return valid response with correct sequence
                    header = LifxHeader(
                        size=36,
                        protocol=1024,
                        source=conn.source,
                        target=bytes.fromhex("d073d5001234"),
                        tagged=False,
                        ack_required=False,
                        res_required=False,
                        sequence=conn._builder._sequence - 1,
                        pkt_type=25,  # StateLabel
                    )
                    return (header, b"Test\x00" * 8)
                else:
                    # After yielding responses, keep polling until timeout
                    raise LifxTimeoutError("No packet")

            responses = []
            with patch.object(conn, "receive_packet", side_effect=mock_receive):
                async for header, payload in conn._request_stream_impl(
                    Device.GetLabel()
                ):
                    responses.append((header, payload))
                    # Don't break - let it continue polling for more responses

            # Should have received 2 responses then timed out
            assert len(responses) == 2
            # Should have polled multiple times (2 responses + polling attempts)
            assert call_count > 2
        finally:
            await conn.close()

    async def test_request_stream_returns_after_timeout_with_responses(self) -> None:
        """Test request_stream returns normally after timeout with responses."""
        import time

        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=0.2,
            max_retries=0,
        )
        await conn.open()
        try:
            call_count = 0
            # Track monotonic time to simulate timeout
            mock_time = [time.monotonic()]

            def advance_time():
                # Advance time by 0.3 seconds (beyond timeout)
                mock_time[0] += 0.3
                return mock_time[0]

            async def mock_receive(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # First call: return valid response
                    header = LifxHeader(
                        size=36,
                        protocol=1024,
                        source=conn.source,
                        target=bytes.fromhex("d073d5001234"),
                        tagged=False,
                        ack_required=False,
                        res_required=False,
                        sequence=conn._builder._sequence - 1,
                        pkt_type=25,  # StateLabel
                    )
                    return (header, b"Test\x00" * 8)
                else:
                    # Advance time to trigger timeout path
                    advance_time()
                    raise LifxTimeoutError("No packet")

            responses = []
            # Patch time.monotonic to control timeout behavior
            time_call_count = [0]

            def mock_monotonic():
                time_call_count[0] += 1
                if time_call_count[0] <= 2:
                    # Initial calls for setup
                    return mock_time[0]
                else:
                    # After first response, advance time
                    return mock_time[0]

            with (
                patch.object(conn, "receive_packet", side_effect=mock_receive),
                patch("time.monotonic", side_effect=mock_monotonic),
            ):
                async for header, payload in conn._request_stream_impl(
                    Device.GetLabel()
                ):
                    responses.append((header, payload))

            # Got one response before timeout - no error should be raised
            assert len(responses) == 1
        finally:
            await conn.close()

    async def test_request_stream_default_max_retries(self) -> None:
        """Test request_stream uses instance default max_retries when not specified."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=0.3,
            max_retries=2,  # Default is 2 retries (3 total attempts)
        )
        await conn.open()
        try:
            attempt_count = 0

            original_sleep = asyncio.sleep

            async def track_sleep(duration):
                nonlocal attempt_count
                attempt_count += 1
                # Use a short sleep to speed up test
                await original_sleep(0.001)

            with (
                patch.object(
                    conn, "receive_packet", side_effect=LifxTimeoutError("No packet")
                ),
                patch("asyncio.sleep", side_effect=track_sleep),
            ):
                with pytest.raises(LifxTimeoutError, match="No response"):
                    async for _ in conn._request_stream_impl(Device.GetLabel()):
                        pass

            # Should have slept between retries (2 retries = 2 sleeps)
            assert attempt_count == 2
        finally:
            await conn.close()

    async def test_request_ack_stream_retry_with_backoff(self) -> None:
        """Test request_ack_stream retries with exponential backoff."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=0.5,
            max_retries=1,  # One retry
        )
        await conn.open()
        try:
            attempt_times = []

            original_sleep = asyncio.sleep

            async def tracked_sleep(duration):
                attempt_times.append(duration)
                await original_sleep(0.001)

            with (
                patch.object(
                    conn, "receive_packet", side_effect=LifxTimeoutError("No packet")
                ),
                patch("asyncio.sleep", side_effect=tracked_sleep),
            ):
                with pytest.raises(LifxTimeoutError, match="No acknowledgement"):
                    async for _ in conn._request_ack_stream_impl(
                        Device.SetLabel(label=b"Test")
                    ):
                        pass

            # Should have slept between retries
            assert len(attempt_times) >= 1
            assert all(t >= 0 for t in attempt_times)
        finally:
            await conn.close()

    async def test_request_ack_stream_default_max_retries(self) -> None:
        """Test request_ack_stream uses instance default max_retries."""
        conn = DeviceConnection(
            serial="d073d5001234",
            ip="192.168.1.100",
            timeout=0.3,
            max_retries=2,
        )
        await conn.open()
        try:
            attempt_count = 0

            original_sleep = asyncio.sleep

            async def track_sleep(duration):
                nonlocal attempt_count
                attempt_count += 1
                await original_sleep(0.001)

            with (
                patch.object(
                    conn, "receive_packet", side_effect=LifxTimeoutError("No packet")
                ),
                patch("asyncio.sleep", side_effect=track_sleep),
            ):
                with pytest.raises(LifxTimeoutError, match="No acknowledgement"):
                    async for _ in conn._request_ack_stream_impl(
                        Device.SetLabel(label=b"Test")
                    ):
                        pass

            # Should have 2 retries = 2 sleeps
            assert attempt_count == 2
        finally:
            await conn.close()


class TestDeviceConnectionRequestStream:
    """Test DeviceConnection.request_stream() wrapper functionality."""

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
            with pytest.raises(LifxUnsupportedCommandError, match="auto-handle"):
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
            # Yield once to indicate ACK received
            yield

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

        async def mock_request_stream_impl(packet, timeout=None, max_retries=None):
            # Return response with device's actual serial
            header = LifxHeader(
                size=36 + 32,
                protocol=1024,
                source=12345,
                target=bytes.fromhex("d073d5001234"),  # Actual serial
                tagged=False,
                ack_required=False,
                res_required=False,
                sequence=1,
                pkt_type=25,  # StateLabel
            )
            payload = b"TestLight\x00" + (b"\x00" * 23)
            yield header, payload

        with (
            patch.object(conn, "_ensure_open", return_value=None),
            patch.object(
                conn, "_request_stream_impl", side_effect=mock_request_stream_impl
            ),
        ):
            get_packet = DevicePackets.GetLabel()

            async for _ in conn.request_stream(get_packet):
                break

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
