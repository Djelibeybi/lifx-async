"""Tests for mDNS transport."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.const import MDNS_ADDRESS, MDNS_PORT
from lifx.exceptions import LifxNetworkError, LifxTimeoutError
from lifx.network.mdns.transport import MdnsTransport


class TestMdnsTransportInit:
    """Tests for MdnsTransport initialization."""

    def test_initial_state(self) -> None:
        """Test transport initializes in closed state."""
        transport = MdnsTransport()

        assert transport.is_open is False
        assert transport._protocol is None
        assert transport._transport is None
        assert transport._socket is None


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
        import asyncio

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
        import socket

        transport = MdnsTransport()
        transport._protocol = MagicMock()
        transport._transport = MagicMock()
        mock_socket = MagicMock(spec=socket.socket)
        transport._socket = mock_socket

        await transport.close()

        # Should have called setsockopt to drop membership
        mock_socket.setsockopt.assert_called()


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

        from lifx.network.mdns.transport import _MdnsProtocol

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
        from lifx.network.mdns.transport import _MdnsProtocol

        protocol = _MdnsProtocol()
        mock_transport = MagicMock()

        protocol.connection_made(mock_transport)

        assert protocol._transport is mock_transport

    def test_error_received_does_not_raise(self) -> None:
        """Test that error_received handles errors gracefully."""
        from lifx.network.mdns.transport import _MdnsProtocol

        protocol = _MdnsProtocol()

        # Should not raise
        protocol.error_received(OSError("Test error"))

    def test_connection_lost_does_not_raise(self) -> None:
        """Test that connection_lost handles disconnection gracefully."""
        from lifx.network.mdns.transport import _MdnsProtocol

        protocol = _MdnsProtocol()

        # Should not raise
        protocol.connection_lost(None)
        protocol.connection_lost(OSError("Disconnected"))
