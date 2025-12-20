"""Tests for mDNS transport."""

from __future__ import annotations

import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.const import MDNS_ADDRESS, MDNS_PORT
from lifx.exceptions import LifxNetworkError, LifxTimeoutError
from lifx.network.mdns.transport import MdnsTransport, _MdnsProtocol


class TestMdnsTransportInit:
    """Tests for MdnsTransport initialization."""

    def test_initial_state(self) -> None:
        """Test transport initializes in closed state."""
        transport = MdnsTransport()

        assert transport.is_open is False
        assert transport._protocol is None
        assert transport._transport is None
        assert transport._socket is None


class TestMdnsTransportOpen:
    """Tests for MdnsTransport.open() method."""

    @pytest.mark.asyncio
    async def test_open_creates_socket_and_protocol(self) -> None:
        """Test that open() creates socket, protocol, and transport."""
        transport = MdnsTransport()

        # Mock the socket and asyncio loop
        mock_socket = MagicMock(spec=socket.socket)
        mock_socket.getsockname.return_value = ("", MDNS_PORT)

        mock_datagram_transport = MagicMock()

        with patch("socket.socket", return_value=mock_socket):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                    return_value=(mock_datagram_transport, None)
                )

                await transport.open()

                # Verify socket configuration
                assert mock_socket.setsockopt.called
                assert mock_socket.bind.called
                assert mock_socket.setblocking.called

                # Verify transport state
                assert transport.is_open is True
                assert transport._protocol is not None
                assert transport._transport is mock_datagram_transport
                assert transport._socket is mock_socket

        await transport.close()

    @pytest.mark.asyncio
    async def test_open_already_open_does_nothing(self) -> None:
        """Test that open() is idempotent when already open."""
        transport = MdnsTransport()

        # Set up as already open
        transport._protocol = MagicMock()

        # Should not raise and should return early
        await transport.open()

        # Protocol should still be the same mock
        assert transport._protocol is not None

    @pytest.mark.asyncio
    async def test_open_ephemeral_port_fallback(self) -> None:
        """Test that open() falls back to ephemeral port if MDNS_PORT is busy."""
        transport = MdnsTransport()

        mock_socket = MagicMock(spec=socket.socket)
        # First bind fails, second succeeds
        mock_socket.bind.side_effect = [OSError("Address in use"), None]
        mock_socket.getsockname.return_value = ("", 12345)

        mock_datagram_transport = MagicMock()

        with patch("socket.socket", return_value=mock_socket):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                    return_value=(mock_datagram_transport, None)
                )

                await transport.open()

                # Verify bind was called twice (once for MDNS_PORT, once for ephemeral)
                assert mock_socket.bind.call_count == 2
                # First call should be to MDNS_PORT
                assert mock_socket.bind.call_args_list[0][0][0] == ("", MDNS_PORT)
                # Second call should be to ephemeral port
                assert mock_socket.bind.call_args_list[1][0][0] == ("", 0)

                assert transport.is_open is True

        await transport.close()

    @pytest.mark.asyncio
    async def test_open_reuseport_not_available(self) -> None:
        """Test that open() handles SO_REUSEPORT not being available."""
        transport = MdnsTransport()

        mock_socket = MagicMock(spec=socket.socket)

        # Make SO_REUSEPORT fail (common on some systems)
        def mock_setsockopt(level: int, opt: int, value: int) -> None:
            if hasattr(socket, "SO_REUSEPORT") and opt == socket.SO_REUSEPORT:
                raise OSError("Protocol not available")

        mock_socket.setsockopt.side_effect = mock_setsockopt
        mock_socket.getsockname.return_value = ("", MDNS_PORT)

        mock_datagram_transport = MagicMock()

        with patch("socket.socket", return_value=mock_socket):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                    return_value=(mock_datagram_transport, None)
                )

                # Should not raise - SO_REUSEPORT failure is ignored
                await transport.open()
                assert transport.is_open is True

        await transport.close()

    @pytest.mark.asyncio
    async def test_open_socket_creation_fails(self) -> None:
        """Test that open() raises LifxNetworkError on socket failure."""
        transport = MdnsTransport()

        with patch("socket.socket", side_effect=OSError("Socket creation failed")):
            with pytest.raises(LifxNetworkError, match="Failed to open mDNS socket"):
                await transport.open()

        assert transport.is_open is False

    @pytest.mark.asyncio
    async def test_open_multicast_join_fails(self) -> None:
        """Test that open() raises LifxNetworkError if multicast join fails."""
        transport = MdnsTransport()

        mock_socket = MagicMock(spec=socket.socket)
        mock_socket.getsockname.return_value = ("", MDNS_PORT)

        # Make IP_ADD_MEMBERSHIP fail
        def mock_setsockopt(level: int, opt: int, value: object) -> None:
            if level == socket.IPPROTO_IP and opt == socket.IP_ADD_MEMBERSHIP:
                raise OSError("Cannot join multicast group")

        mock_socket.setsockopt.side_effect = mock_setsockopt

        with patch("socket.socket", return_value=mock_socket):
            with pytest.raises(LifxNetworkError, match="Failed to open mDNS socket"):
                await transport.open()

        assert transport.is_open is False


class TestMdnsTransportContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_opens_and_closes(self) -> None:
        """Test that context manager opens on enter and closes on exit."""
        transport = MdnsTransport()

        with patch.object(transport, "open", new_callable=AsyncMock) as mock_open:
            with patch.object(transport, "close", new_callable=AsyncMock) as mock_close:
                async with transport:
                    mock_open.assert_called_once()
                    mock_close.assert_not_called()

                mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_real_open_close(self) -> None:
        """Test context manager with real open/close (mocked socket)."""
        mock_socket = MagicMock(spec=socket.socket)
        mock_socket.getsockname.return_value = ("", MDNS_PORT)
        mock_datagram_transport = MagicMock()

        with patch("socket.socket", return_value=mock_socket):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                    return_value=(mock_datagram_transport, None)
                )

                async with MdnsTransport() as transport:
                    assert transport.is_open is True

                # After exiting, transport should be closed
                assert transport.is_open is False


class TestMdnsTransportSend:
    """Tests for sending data."""

    @pytest.mark.asyncio
    async def test_send_not_open_raises(self) -> None:
        """Test that send raises when socket is not open."""
        transport = MdnsTransport()

        with pytest.raises(LifxNetworkError, match="Socket not open"):
            await transport.send(b"test")

    @pytest.mark.asyncio
    async def test_send_default_address(self) -> None:
        """Test that send uses mDNS multicast address by default."""
        transport = MdnsTransport()
        transport._protocol = MagicMock()
        transport._transport = MagicMock()

        await transport.send(b"test")

        transport._transport.sendto.assert_called_once_with(
            b"test", (MDNS_ADDRESS, MDNS_PORT)
        )

    @pytest.mark.asyncio
    async def test_send_custom_address(self) -> None:
        """Test that send can use a custom address."""
        transport = MdnsTransport()
        transport._protocol = MagicMock()
        transport._transport = MagicMock()

        await transport.send(b"test", ("192.168.1.1", 5353))

        transport._transport.sendto.assert_called_once_with(
            b"test", ("192.168.1.1", 5353)
        )

    @pytest.mark.asyncio
    async def test_send_os_error_raises(self) -> None:
        """Test that OSError is wrapped in LifxNetworkError."""
        transport = MdnsTransport()
        transport._protocol = MagicMock()
        transport._transport = MagicMock()
        transport._transport.sendto.side_effect = OSError("Network error")

        with pytest.raises(LifxNetworkError, match="Failed to send"):
            await transport.send(b"test")


class TestMdnsTransportReceive:
    """Tests for receiving data."""

    @pytest.mark.asyncio
    async def test_receive_not_open_raises(self) -> None:
        """Test that receive raises when socket is not open."""
        transport = MdnsTransport()

        with pytest.raises(LifxNetworkError, match="Socket not open"):
            await transport.receive()

    @pytest.mark.asyncio
    async def test_receive_timeout_raises(self) -> None:
        """Test that receive raises LifxTimeoutError on timeout."""
        import asyncio

        transport = MdnsTransport()
        transport._protocol = MagicMock()
        transport._protocol.queue = asyncio.Queue()

        with pytest.raises(LifxTimeoutError, match="No mDNS data received"):
            await transport.receive(timeout=0.01)

    @pytest.mark.asyncio
    async def test_receive_returns_data(self) -> None:
        """Test that receive returns data from queue."""
        transport = MdnsTransport()
        transport._protocol = MagicMock()
        transport._protocol.queue = asyncio.Queue()

        # Put test data in queue
        test_data = b"test response"
        test_addr = ("192.168.1.1", 5353)
        await transport._protocol.queue.put((test_data, test_addr))

        data, addr = await transport.receive()

        assert data == test_data
        assert addr == test_addr

    @pytest.mark.asyncio
    async def test_receive_os_error_raises(self) -> None:
        """Test that OSError in receive is wrapped in LifxNetworkError."""
        transport = MdnsTransport()
        transport._protocol = MagicMock()

        # Create a queue that raises OSError when getting
        mock_queue = MagicMock()
        mock_queue.get = AsyncMock(side_effect=OSError("Network error"))
        transport._protocol.queue = mock_queue

        with pytest.raises(LifxNetworkError, match="Failed to receive"):
            await transport.receive()


class TestMdnsTransportClose:
    """Tests for closing transport."""

    @pytest.mark.asyncio
    async def test_close_when_not_open(self) -> None:
        """Test that close does nothing when not open."""
        transport = MdnsTransport()

        # Should not raise
        await transport.close()

        assert transport.is_open is False

    @pytest.mark.asyncio
    async def test_close_clears_state(self) -> None:
        """Test that close clears internal state."""
        import socket

        transport = MdnsTransport()
        transport._protocol = MagicMock()
        transport._transport = MagicMock()
        transport._socket = MagicMock(spec=socket.socket)

        await transport.close()

        assert transport._protocol is None
        assert transport._transport is None
        assert transport._socket is None
        assert transport.is_open is False

    @pytest.mark.asyncio
    async def test_close_leaves_multicast_group(self) -> None:
        """Test that close leaves the multicast group."""
        transport = MdnsTransport()
        transport._protocol = MagicMock()
        transport._transport = MagicMock()
        mock_socket = MagicMock(spec=socket.socket)
        transport._socket = mock_socket

        await transport.close()

        # Should have called setsockopt to drop membership
        mock_socket.setsockopt.assert_called()

    @pytest.mark.asyncio
    async def test_close_ignores_multicast_leave_error(self) -> None:
        """Test that close ignores errors when leaving multicast group."""
        transport = MdnsTransport()
        transport._protocol = MagicMock()
        transport._transport = MagicMock()
        mock_socket = MagicMock(spec=socket.socket)
        # Make leaving multicast group fail
        mock_socket.setsockopt.side_effect = OSError("Cannot leave group")
        transport._socket = mock_socket

        # Should not raise despite OSError
        await transport.close()

        # Transport should still be closed
        assert transport.is_open is False
        assert transport._socket is None


class TestMdnsTransportIsOpen:
    """Tests for is_open property."""

    def test_is_open_false_when_no_protocol(self) -> None:
        """Test is_open is False when protocol is None."""
        transport = MdnsTransport()
        assert transport.is_open is False

    def test_is_open_true_when_protocol_set(self) -> None:
        """Test is_open is True when protocol is set."""
        transport = MdnsTransport()
        transport._protocol = MagicMock()
        assert transport.is_open is True


class TestMdnsProtocol:
    """Tests for the internal _MdnsProtocol class."""

    def test_datagram_received_queues_data(self) -> None:
        """Test that received datagrams are queued."""

        protocol = _MdnsProtocol()

        # Simulate receiving a datagram
        test_data = b"test data"
        test_addr = ("192.168.1.1", 5353)
        protocol.datagram_received(test_data, test_addr)

        # Check data is in queue
        assert not protocol.queue.empty()
        data, addr = protocol.queue.get_nowait()
        assert data == test_data
        assert addr == test_addr

    def test_connection_made_stores_transport(self) -> None:
        """Test that connection_made stores the transport."""

        protocol = _MdnsProtocol()
        mock_transport = MagicMock()

        protocol.connection_made(mock_transport)

        assert protocol._transport is mock_transport

    def test_error_received_does_not_raise(self) -> None:
        """Test that error_received handles errors gracefully."""

        protocol = _MdnsProtocol()

        # Should not raise
        protocol.error_received(OSError("Test error"))

    def test_connection_lost_does_not_raise(self) -> None:
        """Test that connection_lost handles disconnection gracefully."""

        protocol = _MdnsProtocol()

        # Should not raise
        protocol.connection_lost(None)
        protocol.connection_lost(OSError("Disconnected"))
