"""Tests for UDP transport layer."""

import errno
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.exceptions import LifxNetworkError as NetworkError
from lifx.exceptions import LifxTimeoutError as TimeoutError
from lifx.network.transport import UdpTransport


class TestUdpTransport:
    """Test UDP transport."""

    async def test_transport_context_manager(self) -> None:
        """Test transport context manager."""
        async with UdpTransport() as transport:
            assert transport.is_open

        assert not transport.is_open

    async def test_transport_open_close(self) -> None:
        """Test manual open/close."""
        transport = UdpTransport()
        assert not transport.is_open

        await transport.open()
        assert transport.is_open

        await transport.close()
        assert not transport.is_open

    async def test_transport_double_open(self) -> None:
        """Test opening transport twice is safe."""
        transport = UdpTransport()
        await transport.open()
        await transport.open()  # Should not raise
        assert transport.is_open
        await transport.close()

    async def test_send_without_open(self) -> None:
        """Test sending without opening raises error."""
        transport = UdpTransport()
        with pytest.raises(NetworkError):
            await transport.send(b"test", ("127.0.0.1", 56700))

    async def test_receive_without_open(self) -> None:
        """Test receiving without opening raises error."""
        transport = UdpTransport()
        with pytest.raises(NetworkError):
            await transport.receive(timeout=1.0)

    async def test_receive_timeout(self) -> None:
        """Test receive timeout."""
        async with UdpTransport() as transport:
            with pytest.raises(TimeoutError):
                await transport.receive(timeout=0.1)

    async def test_receive_many_timeout(self) -> None:
        """Test receive_many returns empty list on timeout."""
        async with UdpTransport() as transport:
            packets = await transport.receive_many(timeout=0.1)
            assert packets == []

    async def test_broadcast_mode(self) -> None:
        """Test transport with broadcast mode."""
        async with UdpTransport(broadcast=True) as transport:
            assert transport.is_open
            # Just verify it opens successfully with broadcast enabled

    async def test_receive_many_without_open(self) -> None:
        """Test receive_many without opening raises error."""
        transport = UdpTransport()
        with pytest.raises(NetworkError):
            await transport.receive_many(timeout=1.0)

    async def test_double_close(self) -> None:
        """Test closing transport twice is safe."""
        transport = UdpTransport()
        await transport.open()
        await transport.close()
        await transport.close()  # Should not raise
        assert not transport.is_open

    async def test_transport_with_specific_port(self) -> None:
        """Test transport with specific port binding."""
        # Use port 0 for automatic assignment then verify it's assigned
        async with UdpTransport(port=0) as transport:
            assert transport.is_open

    async def test_transport_with_specific_ip(self) -> None:
        """Test transport with specific IP address binding."""
        async with UdpTransport(ip_address="127.0.0.1") as transport:
            assert transport.is_open

    async def test_receive_many_with_max_packets(self) -> None:
        """Test receive_many respects max_packets limit."""
        async with UdpTransport() as transport:
            # With max_packets=0, should return immediately
            packets = await transport.receive_many(timeout=0.5, max_packets=0)
            assert packets == []

    async def test_receive_many_emits_deprecation_warning(self) -> None:
        """receive_many must emit DeprecationWarning naming v6.0 (D-12)."""
        async with UdpTransport() as transport:
            with pytest.warns(DeprecationWarning, match="v6.0"):
                await transport.receive_many(timeout=0.1)


class TestUdpProtocol:
    """Test internal _UdpProtocol class."""

    async def test_protocol_datagram_received(self) -> None:
        """Test protocol handles received datagrams."""
        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()
        test_data = b"\x00" * 36  # Minimum valid packet size
        test_addr = ("192.168.1.100", 56700)

        # Simulate receiving a datagram
        protocol.datagram_received(test_data, test_addr)

        # Verify data is in queue
        assert not protocol.queue.empty()
        data, addr = await protocol.queue.get()
        assert data == test_data
        assert addr == test_addr

    async def test_protocol_connection_made(self) -> None:
        """Test protocol connection_made callback."""
        from unittest.mock import MagicMock

        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()
        mock_transport = MagicMock()

        protocol.connection_made(mock_transport)
        assert protocol.transport == mock_transport

    async def test_protocol_connection_lost(self) -> None:
        """Test protocol connection_lost callback."""
        from unittest.mock import MagicMock

        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()
        mock_transport = MagicMock()

        protocol.connection_made(mock_transport)
        assert protocol.transport is not None

        protocol.connection_lost(None)
        assert protocol.transport is None

    async def test_protocol_error_received(self) -> None:
        """Test protocol error_received logs warning."""
        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()

        with patch("lifx.network.transport._LOGGER") as mock_logger:
            protocol.error_received(OSError("test error"))
            mock_logger.warning.assert_called_once()
            log_dict = mock_logger.warning.call_args[0][0]
            assert log_dict["class"] == "_UdpProtocol"
            assert log_dict["method"] == "error_received"
            assert "test error" in log_dict["error"]

    async def test_protocol_queue_full_drops_packet(self) -> None:
        """Test datagram_received drops packets when queue is full."""
        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()
        test_addr = ("192.168.1.100", 56700)
        test_data = b"\x00" * 36

        # Fill the queue to capacity
        for _ in range(protocol._MAX_QUEUE_SIZE):
            protocol.datagram_received(test_data, test_addr)

        assert protocol.queue.full()

        # First drop logs immediately (rate-limited: 1st, then every Nth)
        with patch("lifx.network.transport._LOGGER") as mock_logger:
            protocol.datagram_received(test_data, test_addr)
            mock_logger.warning.assert_called_once()
            log_dict = mock_logger.warning.call_args[0][0]
            assert log_dict["action"] == "packet_dropped"
            assert log_dict["reason"] == "queue_full"
            assert log_dict["total_dropped"] == 1

        # Subsequent drops are rate-limited (no log until interval)
        with patch("lifx.network.transport._LOGGER") as mock_logger:
            protocol.datagram_received(test_data, test_addr)
            mock_logger.warning.assert_not_called()

        # Queue size should remain at max
        assert protocol.queue.qsize() == protocol._MAX_QUEUE_SIZE
        assert protocol._dropped_count == 2


class TestPacketSizeValidation:
    """Test packet size validation in receive methods."""

    async def test_receive_packet_too_large(self) -> None:
        """Test receive rejects packets larger than MAX_PACKET_SIZE."""
        from lifx.exceptions import LifxProtocolError
        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()
        # Create oversized packet (MAX_PACKET_SIZE is 1024)
        oversized_data = b"\x00" * 2000
        protocol.datagram_received(oversized_data, ("127.0.0.1", 56700))

        transport = UdpTransport()
        transport._protocol = protocol

        with pytest.raises(LifxProtocolError, match="Packet too big"):
            await transport.receive(timeout=1.0)

    async def test_receive_packet_too_small(self) -> None:
        """Test receive rejects packets smaller than MIN_PACKET_SIZE."""
        from lifx.exceptions import LifxProtocolError
        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()
        # Create undersized packet (MIN_PACKET_SIZE is 36)
        undersized_data = b"\x00" * 10
        protocol.datagram_received(undersized_data, ("127.0.0.1", 56700))

        transport = UdpTransport()
        transport._protocol = protocol

        with pytest.raises(LifxProtocolError, match="Packet too small"):
            await transport.receive(timeout=1.0)

    async def test_receive_valid_packet_size(self) -> None:
        """Test receive accepts packets within valid size range."""
        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()
        # Create valid packet (exactly MIN_PACKET_SIZE)
        valid_data = b"\x00" * 36
        test_addr = ("127.0.0.1", 56700)
        protocol.datagram_received(valid_data, test_addr)

        transport = UdpTransport()
        transport._protocol = protocol

        data, addr = await transport.receive(timeout=1.0)
        assert data == valid_data
        assert addr == test_addr

    async def test_receive_many_drops_oversized_packets(self) -> None:
        """Test receive_many silently drops oversized packets."""
        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()

        # Add one valid and one oversized packet
        valid_data = b"\x00" * 36
        oversized_data = b"\x00" * 2000
        test_addr = ("127.0.0.1", 56700)

        protocol.datagram_received(valid_data, test_addr)
        protocol.datagram_received(oversized_data, test_addr)

        transport = UdpTransport()
        transport._protocol = protocol

        # Should only get the valid packet (oversized is dropped)
        packets = await transport.receive_many(timeout=0.1)
        assert len(packets) == 1
        assert packets[0][0] == valid_data

    async def test_receive_many_drops_undersized_packets(self) -> None:
        """Test receive_many silently drops undersized packets."""
        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()

        # Add one valid and one undersized packet
        valid_data = b"\x00" * 36
        undersized_data = b"\x00" * 10
        test_addr = ("127.0.0.1", 56700)

        protocol.datagram_received(valid_data, test_addr)
        protocol.datagram_received(undersized_data, test_addr)

        transport = UdpTransport()
        transport._protocol = protocol

        # Should only get the valid packet (undersized is dropped)
        packets = await transport.receive_many(timeout=0.1)
        assert len(packets) == 1
        assert packets[0][0] == valid_data

    async def test_receive_many_max_packets_limit(self) -> None:
        """Test receive_many stops after max_packets."""
        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()

        # Add multiple valid packets
        valid_data = b"\x00" * 36
        test_addr = ("127.0.0.1", 56700)

        for _ in range(5):
            protocol.datagram_received(valid_data, test_addr)

        transport = UdpTransport()
        transport._protocol = protocol

        # Should only get 2 packets
        packets = await transport.receive_many(timeout=1.0, max_packets=2)
        assert len(packets) == 2


class TestErrorHandling:
    """Test error handling in transport."""

    async def test_open_oserror_raises_network_error(self) -> None:
        """Test OSError during open raises NetworkError."""
        transport = UdpTransport()

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                side_effect=OSError("Address already in use")
            )
            with pytest.raises(NetworkError, match="Failed to open UDP socket"):
                await transport.open()

    async def test_send_oserror_raises_network_error(self) -> None:
        """Test OSError during send raises NetworkError."""
        from lifx.network.transport import _UdpProtocol

        transport = UdpTransport()
        protocol = _UdpProtocol()
        transport._protocol = protocol

        # Create a mock transport that raises OSError on sendto
        mock_transport = MagicMock()
        mock_transport.sendto.side_effect = OSError("Network unreachable")
        transport._transport = mock_transport

        with pytest.raises(NetworkError, match="Failed to send data"):
            await transport.send(b"test", ("127.0.0.1", 56700))

    async def test_receive_oserror_raises_network_error(self) -> None:
        """Test OSError during receive raises NetworkError."""
        import asyncio

        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()
        transport = UdpTransport()
        transport._protocol = protocol

        # Create a custom queue that raises OSError
        class FailingQueue(asyncio.Queue):
            async def get(self):
                raise OSError("Socket closed")

        protocol.queue = FailingQueue()

        with pytest.raises(NetworkError, match="Failed to receive data"):
            await transport.receive(timeout=1.0)

    async def test_broadcast_mode_socket_none(self) -> None:
        """Test broadcast mode when get_extra_info returns None."""
        transport = UdpTransport(broadcast=True)

        # Mock the event loop and transport
        mock_transport = MagicMock()
        mock_transport.get_extra_info.side_effect = lambda key: {
            "sockname": ("0.0.0.0", 12345),
            "socket": None,  # Socket is None - coverage for line 135
        }.get(key)

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                return_value=(mock_transport, MagicMock())
            )
            await transport.open()

        # Should still be open even though socket was None
        assert transport.is_open
        await transport.close()

    async def test_receive_many_oserror_breaks_loop(self) -> None:
        """Test receive_many breaks on OSError during packet receive."""
        import asyncio

        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()
        transport = UdpTransport()
        transport._protocol = protocol

        # Add one valid packet then make queue raise OSError
        valid_data = b"\x00" * 36
        test_addr = ("127.0.0.1", 56700)
        protocol.datagram_received(valid_data, test_addr)

        # Replace queue with one that raises OSError after first get
        original_queue = protocol.queue

        class FailAfterOneQueue(asyncio.Queue):
            def __init__(self):
                super().__init__()
                self._get_count = 0

            async def get(self):
                self._get_count += 1
                if self._get_count == 1:
                    return await original_queue.get()
                raise OSError("Socket error")

        protocol.queue = FailAfterOneQueue()

        # Should get the one valid packet and then break on OSError
        packets = await transport.receive_many(timeout=1.0)
        assert len(packets) == 1
        assert packets[0][0] == valid_data


class TestEndpointLoss:
    """A dead endpoint must report itself dead so it can be reopened.

    asyncio only calls ``connection_lost`` on an unconnected datagram endpoint
    for ``close()``, ``abort()`` and fatal (non-OSError) errors in its
    read/write path; ordinary send and receive errors go to ``error_received``
    and leave the endpoint usable. Both paths are covered here.
    """

    async def test_connection_lost_closes_transport_state(self) -> None:
        """connection_lost clears the transport's own references."""
        transport = UdpTransport()
        await transport.open()
        protocol = transport._protocol
        assert protocol is not None

        protocol.connection_lost(RuntimeError("fatal read error"))

        assert not transport.is_open
        assert transport._transport is None
        assert transport._protocol is None

    async def test_open_after_loss_creates_new_endpoint(self) -> None:
        """open() must build a new endpoint, not early-return "already_open"."""
        transport = UdpTransport()
        await transport.open()
        first_protocol = transport._protocol
        first_transport = transport._transport
        assert first_protocol is not None

        first_protocol.connection_lost(RuntimeError("fatal read error"))
        await transport.open()

        try:
            assert transport.is_open
            assert transport._protocol is not first_protocol
            assert transport._transport is not first_transport
        finally:
            await transport.close()

    async def test_send_raises_after_loss(self) -> None:
        """Sending on a dead endpoint fails loudly instead of being dropped."""
        transport = UdpTransport()
        await transport.open()
        protocol = transport._protocol
        assert protocol is not None
        protocol.connection_lost(None)

        with pytest.raises(NetworkError):
            await transport.send(b"x" * 36, ("127.0.0.1", 56700))

    async def test_stale_loss_does_not_close_replacement(self) -> None:
        """A late callback from a replaced endpoint must not kill the new one."""
        transport = UdpTransport()
        await transport.open()
        old_protocol = transport._protocol
        assert old_protocol is not None
        await transport.close()
        await transport.open()
        new_protocol = transport._protocol

        # asyncio delivers connection_lost after close() has already cleared
        # the references and a replacement endpoint has been opened.
        old_protocol.connection_lost(None)

        try:
            assert transport.is_open
            assert transport._protocol is new_protocol
        finally:
            await transport.close()

    @pytest.mark.parametrize(
        "error_number",
        [errno.EHOSTDOWN, errno.EHOSTUNREACH, errno.ENETUNREACH, errno.ECONNREFUSED],
    )
    async def test_unreachable_peer_errors_keep_endpoint_open(
        self, error_number: int
    ) -> None:
        """Per-datagram ICMP errors describe the peer, not the socket."""
        transport = UdpTransport()
        await transport.open()
        protocol = transport._protocol
        assert protocol is not None

        try:
            for _ in range(50):
                protocol.error_received(OSError(error_number, "peer unreachable"))

            assert transport.is_open
            assert transport._protocol is protocol
        finally:
            await transport.close()

    @pytest.mark.parametrize("error_number", [errno.EBADF, errno.ENOTSOCK])
    async def test_invalid_socket_errors_close_endpoint(
        self, error_number: int
    ) -> None:
        """A structurally invalid socket is endpoint death, not a peer problem.

        asyncio reports these to error_received and never calls
        connection_lost, so without this the transport would claim to be open
        forever while every datagram failed.
        """
        transport = UdpTransport()
        await transport.open()
        protocol = transport._protocol
        assert protocol is not None

        protocol.error_received(OSError(error_number, "Bad file descriptor"))

        assert not transport.is_open

    async def test_error_logging_is_rate_limited(self, caplog) -> None:
        """A sustained error storm must not log once per datagram."""
        transport = UdpTransport()
        await transport.open()
        protocol = transport._protocol
        assert protocol is not None

        try:
            with caplog.at_level(logging.WARNING, logger="lifx.network.transport"):
                for _ in range(250):
                    protocol.error_received(OSError(errno.EHOSTDOWN, "Host is down"))

            records = [
                record
                for record in caplog.records
                if "error_received" in str(record.msg)
            ]
            assert len(records) == 3  # first, 100th, 200th
        finally:
            await transport.close()

    async def test_received_datagram_resets_error_counter(self) -> None:
        """Recovery restarts the rate-limited log for the next burst."""
        transport = UdpTransport()
        await transport.open()
        protocol = transport._protocol
        assert protocol is not None

        try:
            protocol.error_received(OSError(errno.EHOSTDOWN, "Host is down"))
            assert protocol._error_count == 1

            protocol.datagram_received(b"\x00" * 36, ("127.0.0.1", 56700))

            assert protocol._error_count == 0
        finally:
            await transport.close()

    async def test_loss_before_endpoint_is_assigned(self) -> None:
        """Loss reported while the endpoint is still being created is safe."""
        from lifx.network.transport import _UdpProtocol

        transport = UdpTransport()
        protocol = _UdpProtocol(on_endpoint_lost=transport._endpoint_lost)
        # open() assigns _protocol before create_datagram_endpoint() returns.
        transport._protocol = protocol

        protocol.connection_lost(OSError("failed during setup"))

        assert not transport.is_open
        assert transport._transport is None
