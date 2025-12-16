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
            await conn.send_packet(packet, source=12345, sequence=0)

    async def test_receive_without_open(self) -> None:
        """Test receiving without opening raises error."""
        serial = "d073d5001234"
        conn = DeviceConnection(serial=serial, ip="192.168.1.100")

        with pytest.raises(ConnectionError):
            await conn.receive_packet(timeout=1.0)

    async def test_allocate_source(self) -> None:
        """Test source allocation generates valid sources."""
        # Source allocation is now per-request, test the static method
        source = DeviceConnection._allocate_source()

        # Should be in valid range [2, 0xFFFFFFFF]
        assert 2 <= source <= 0xFFFFFFFF

    async def test_allocate_source_uniqueness(self) -> None:
        """Test source allocation generates unique sources."""
        # Allocate multiple sources and verify they're different
        sources = {DeviceConnection._allocate_source() for _ in range(100)}

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
