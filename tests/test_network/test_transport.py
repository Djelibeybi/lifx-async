"""Tests for UDP transport layer."""

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
        """Test protocol error_received callback doesn't crash."""
        from lifx.network.transport import _UdpProtocol

        protocol = _UdpProtocol()
        # Should not raise - errors are silently ignored
        protocol.error_received(OSError("test error"))


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
