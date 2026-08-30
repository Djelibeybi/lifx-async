"""Tests for UDP transport layer."""

import asyncio
import errno
import logging
import socket
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from lifx.exceptions import LifxNetworkError as NetworkError
from lifx.exceptions import LifxProtocolError
from lifx.exceptions import LifxTimeoutError as TimeoutError
from lifx.network.transport import PeerInfo, UdpTransport, _UdpProtocol


async def _open_mock_transport(
    ip_address: str,
) -> tuple[UdpTransport, MagicMock, MagicMock]:
    """Open against a mocked endpoint without relying on the host IP stack.

    Family-selection tests may need an IPv6 transport on a runner without an
    IPv6 stack. The mocked endpoint keeps assertions focused on transport
    behaviour and exposes both ``sendto`` and socket-factory seams.
    """
    transport = UdpTransport(ip_address=ip_address, port=0)
    raw_socket = MagicMock()
    datagram_transport = MagicMock()
    datagram_transport.get_extra_info.return_value = (ip_address, 49152)

    with (
        patch(
            "lifx.network.transport._socket_factory",
            return_value=raw_socket,
        ) as socket_factory,
        patch("asyncio.get_running_loop") as mock_loop,
    ):
        mock_loop.return_value.create_datagram_endpoint = AsyncMock(
            return_value=(datagram_transport, MagicMock())
        )
        await transport.open()

    return transport, datagram_transport, socket_factory


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

    async def test_broadcast_mode(self) -> None:
        """Test transport with broadcast mode."""
        async with UdpTransport(broadcast=True) as transport:
            assert transport.is_open
            # Just verify it opens successfully with broadcast enabled

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


class TestUdpProtocol:
    """Test internal _UdpProtocol class."""

    async def test_protocol_datagram_received(self) -> None:
        """Test protocol handles received datagrams."""
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

        protocol = _UdpProtocol()
        mock_transport = MagicMock()

        protocol.connection_made(mock_transport)
        assert protocol.transport == mock_transport

    async def test_protocol_connection_lost(self) -> None:
        """Test protocol connection_lost callback."""

        protocol = _UdpProtocol()
        mock_transport = MagicMock()

        protocol.connection_made(mock_transport)
        assert protocol.transport is not None

        protocol.connection_lost(None)
        assert protocol.transport is None

    async def test_protocol_error_received(self) -> None:
        """Test protocol error_received logs warning."""
        protocol = _UdpProtocol()

        with patch("lifx.network.transport._LOGGER") as mock_logger:
            protocol.error_received(OSError("test error"))
            mock_logger.warning.assert_called_once()
            log_dict = mock_logger.warning.call_args[0][0]
            assert log_dict["class"] == "_UdpProtocol"
            assert log_dict["method"] == "error_received"
            assert "test error" in log_dict["error"]
            assert "serial" not in log_dict

    async def test_protocol_error_received_names_the_peer(self) -> None:
        """An unreachable-peer warning identifies which device went away."""
        protocol = _UdpProtocol(peer=PeerInfo("d073d5e00039", "203.0.113.13", 56700))

        with patch("lifx.network.transport._LOGGER") as mock_logger:
            protocol.error_received(OSError(errno.EHOSTDOWN, "Host is down"))
            log_dict = mock_logger.warning.call_args[0][0]
            assert log_dict["serial"] == "d073d5e00039"
            assert log_dict["ip"] == "203.0.113.13"
            assert log_dict["port"] == 56700
            assert log_dict["method"] == "error_received"

    async def test_protocol_log_follows_a_serial_learned_later(self) -> None:
        """A serial learned after open() replaces the placeholder in logs."""
        peer = PeerInfo("000000000000", "203.0.113.13", 56700)
        protocol = _UdpProtocol(peer=peer)

        peer.serial = "d073d5e00039"

        with patch("lifx.network.transport._LOGGER") as mock_logger:
            protocol.error_received(OSError(errno.EHOSTDOWN, "Host is down"))
            log_dict = mock_logger.warning.call_args[0][0]
            assert log_dict["serial"] == "d073d5e00039"

    async def test_protocol_dropped_packet_names_peer_and_sender(self) -> None:
        """A queue-full warning names both the peer and the actual sender."""
        protocol = _UdpProtocol(peer=PeerInfo("d073d5e00039", "203.0.113.13", 56700))
        for _ in range(protocol._MAX_QUEUE_SIZE):
            protocol.datagram_received(b"x", ("203.0.113.13", 56700))

        with patch("lifx.network.transport._LOGGER") as mock_logger:
            # A different host overruns the queue: the peer alone would blame
            # the device that sent nothing.
            protocol.datagram_received(b"x", ("203.0.113.16", 56700))
            log_dict = mock_logger.warning.call_args[0][0]
            assert log_dict["serial"] == "d073d5e00039"
            assert log_dict["sender_ip"] == "203.0.113.16"
            assert log_dict["sender_port"] == 56700
            assert log_dict["action"] == "packet_dropped"

    async def test_transport_passes_peer_to_protocol(self) -> None:
        """UdpTransport hands its peer descriptor to the protocol it creates."""
        peer = PeerInfo("d073d5e00039", "203.0.113.13", 56700)
        transport = UdpTransport(peer=peer)
        await transport.open()
        try:
            assert transport._protocol is not None
            assert transport._protocol._peer is peer
        finally:
            await transport.close()

    async def test_endpoint_lost_warning_names_the_peer(self) -> None:
        """The socket-death warning identifies whose connection was torn down."""
        transport = UdpTransport(peer=PeerInfo("d073d5e00039", "203.0.113.13", 56700))
        await transport.open()
        protocol = transport._protocol
        assert protocol is not None

        with patch("lifx.network.transport._LOGGER") as mock_logger:
            transport._endpoint_lost(protocol, OSError(errno.EBADF, "Bad fd"))
            log_dict = mock_logger.warning.call_args[0][0]
            assert log_dict["class"] == "UdpTransport"
            assert log_dict["action"] == "endpoint_lost"
            assert log_dict["serial"] == "d073d5e00039"
            assert log_dict["ip"] == "203.0.113.13"
            assert log_dict["port"] == 56700

    async def test_protocol_queue_full_drops_packet(self) -> None:
        """Test datagram_received drops packets when queue is full."""
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


class TestErrorHandling:
    """Test error handling in transport."""

    async def test_open_oserror_raises_network_error(self) -> None:
        """An endpoint OSError resets state and permits a successful retry."""
        transport = UdpTransport()
        datagram_transport = MagicMock()

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                side_effect=[
                    OSError("Address already in use"),
                    (datagram_transport, MagicMock()),
                ]
            )
            with pytest.raises(NetworkError, match="Failed to open UDP socket"):
                await transport.open()

            assert transport._protocol is None
            assert transport._transport is None
            assert transport._family is None
            assert transport.is_open is False

            await transport.open()

        await transport.send(b"test", ("127.0.0.1", 56700))
        datagram_transport.sendto.assert_called_once_with(b"test", ("127.0.0.1", 56700))
        await transport.close()

    async def test_cancelled_open_resets_state_and_permits_retry(self) -> None:
        """Cancellation propagates unchanged and leaves a reusable object."""
        transport = UdpTransport()
        entered = asyncio.Event()
        blocked = asyncio.Event()

        async def _blocked_endpoint(*args: Any, **kwargs: Any) -> None:
            """Suspend endpoint creation until the opening task is cancelled."""
            entered.set()
            await blocked.wait()

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = _blocked_endpoint
            opening = asyncio.create_task(transport.open())
            await entered.wait()
            opening.cancel()

            with pytest.raises(asyncio.CancelledError):
                await opening

        assert transport._protocol is None
        assert transport._transport is None
        assert transport._family is None
        assert transport.is_open is False

        datagram_transport = MagicMock()
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                return_value=(datagram_transport, MagicMock())
            )
            await transport.open()

        await transport.send(b"test", ("127.0.0.1", 56700))
        datagram_transport.sendto.assert_called_once_with(b"test", ("127.0.0.1", 56700))
        await transport.close()

    async def test_queued_open_invalidated_by_close_returns_closed(self) -> None:
        """A close invalidates an opener queued before it acquired the lock."""
        transport = UdpTransport()
        await transport._state_lock.acquire()
        opening = asyncio.create_task(transport.open())
        await asyncio.sleep(0)

        await transport.close()
        transport._state_lock.release()
        await opening

        assert transport.is_open is False
        assert transport._protocol is None
        assert transport._transport is None
        assert transport._family is None

    async def test_close_racing_successful_open_wins_and_allows_reopen(self) -> None:
        """close() invalidates a UDP endpoint that completes after it returns."""
        transport = UdpTransport()
        entered = asyncio.Event()
        released = asyncio.Event()
        attempts = 0
        endpoints: list[MagicMock] = []

        async def _endpoint(*args: Any, **kwargs: Any) -> tuple[MagicMock, Any]:
            """Suspend only the endpoint racing the close."""
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                entered.set()
                await released.wait()
            datagram_transport = MagicMock()
            datagram_transport.get_extra_info.return_value = ("127.0.0.1", 12345)
            endpoints.append(datagram_transport)
            return datagram_transport, args[0]()

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = _endpoint
            opening = asyncio.create_task(transport.open())
            await entered.wait()

            assert transport.is_open is False
            await transport.close()
            released.set()
            await opening

            endpoints[0].close.assert_called_once_with()
            assert transport.is_open is False
            assert transport._protocol is None
            assert transport._transport is None
            assert transport._family is None

            await transport.open()
            assert attempts == 2
            assert transport.is_open is True
            await transport.close()

    async def test_failure_after_endpoint_assignment_closes_endpoint(self) -> None:
        """A later setup failure closes the endpoint before resetting state."""
        transport = UdpTransport()
        datagram_transport = MagicMock()
        datagram_transport.get_extra_info.side_effect = OSError(
            "Cannot inspect endpoint"
        )

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                return_value=(datagram_transport, MagicMock())
            )
            with pytest.raises(NetworkError, match="Failed to open UDP socket"):
                await transport.open()

        datagram_transport.close.assert_called_once_with()
        assert transport._protocol is None
        assert transport._transport is None
        assert transport._family is None
        assert transport.is_open is False

    async def test_non_oserror_open_failure_is_reraised_unchanged(self) -> None:
        """Non-OSError endpoint failures retain their original identity."""
        transport = UdpTransport()
        failure = RuntimeError("forced endpoint failure")

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                side_effect=failure
            )
            with pytest.raises(RuntimeError) as excinfo:
                await transport.open()

        assert excinfo.value is failure
        assert transport._protocol is None
        assert transport._transport is None
        assert transport._family is None
        assert transport.is_open is False

    async def test_ipv6_endpoint_failure_closes_raw_socket(self) -> None:
        """A failed endpoint hand-off does not leak its raw IPv6 socket."""
        transport = UdpTransport(ip_address="::")
        raw_socket = MagicMock()
        failure = RuntimeError("forced IPv6 endpoint failure")

        with (
            patch("lifx.network.transport._socket_factory", return_value=raw_socket),
            patch("asyncio.get_running_loop") as mock_loop,
        ):
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                side_effect=failure
            )
            with pytest.raises(RuntimeError) as excinfo:
                await transport.open()

        assert excinfo.value is failure
        raw_socket.close.assert_called_once_with()
        assert transport._protocol is None
        assert transport._transport is None
        assert transport._family is None
        assert transport.is_open is False

    async def test_send_oserror_raises_network_error(self) -> None:
        """Test OSError during send raises NetworkError."""
        transport = UdpTransport()
        protocol = _UdpProtocol()
        transport._protocol = protocol
        # open() records the socket family for send()'s pre-send check, so a
        # hand-assembled transport has to record it too or the send is
        # rejected as "not open" before it can reach sendto.
        transport._family = socket.AF_INET

        # Create a mock transport that raises OSError on sendto
        mock_transport = MagicMock()
        mock_transport.sendto.side_effect = OSError("Network unreachable")
        transport._transport = mock_transport

        with pytest.raises(NetworkError, match="Failed to send data"):
            await transport.send(b"test", ("127.0.0.1", 56700))

    async def test_receive_oserror_raises_network_error(self) -> None:
        """Test OSError during receive raises NetworkError."""

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
        transport = UdpTransport()
        protocol = _UdpProtocol(on_endpoint_lost=transport._endpoint_lost)
        # open() assigns _protocol before create_datagram_endpoint() returns.
        transport._protocol = protocol

        protocol.connection_lost(OSError("failed during setup"))

        assert not transport.is_open
        assert transport._transport is None


class TestSocketFamilySelection:
    """The socket family follows the local bind address (IPV6-03, B9).

    ``open()`` no longer decides this for itself: it asks
    :func:`lifx.network.address.family_for`, the one shared rule. Both arms
    are asserted here because only the IPv4 arm runs in the rest of the
    suite, which would leave the IPv6 side of the seam unproven.
    """

    @staticmethod
    async def _family_used(ip_address: str) -> socket.AddressFamily:
        """Open a transport against a mocked loop and report the family."""
        transport, _, socket_factory = await _open_mock_transport(ip_address)

        family = transport._family
        assert family is not None
        if family is socket.AF_INET6:
            socket_factory.assert_called_once_with(socket.AF_INET6, socket.SOCK_DGRAM)
        else:
            socket_factory.assert_not_called()
        await transport.close()
        return family

    async def test_ipv4_bind_address_opens_an_af_inet_endpoint(self) -> None:
        """The default wildcard bind stays IPv4."""
        assert await self._family_used("0.0.0.0") == socket.AF_INET

    async def test_ipv6_bind_address_opens_an_af_inet6_endpoint(self) -> None:
        """The IPv6 wildcard bind is what reaches a Thread device."""
        assert await self._family_used("::") == socket.AF_INET6

    async def test_zoned_link_local_bind_opens_an_af_inet6_endpoint(self) -> None:
        """A zoned literal parses, so the family still follows the address."""
        assert await self._family_used("fe80::1%1") == socket.AF_INET6

    async def test_unscoped_link_local_bind_reaches_the_operating_system(self) -> None:
        """Destination routing rules do not reject a local bind literal."""
        transport = UdpTransport(ip_address="fe80::1", port=56700)
        raw_socket = MagicMock()
        datagram_transport = MagicMock()
        datagram_transport.get_extra_info.return_value = (
            "fe80::1",
            56700,
            0,
            0,
        )

        with (
            patch("lifx.network.transport._socket_factory", return_value=raw_socket),
            patch("asyncio.get_running_loop") as mock_loop,
        ):
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                return_value=(datagram_transport, MagicMock())
            )
            await transport.open()

        raw_socket.bind.assert_called_once_with(("fe80::1", 56700, 0, 0))
        await transport.close()

    async def test_ipv6_endpoint_is_explicitly_v6_only(self) -> None:
        """Platform defaults cannot admit IPv4-mapped datagrams."""
        transport = UdpTransport(ip_address="::", port=0)
        raw_socket = MagicMock()
        raw_socket.getsockname.return_value = ("::", 49152, 0, 0)
        endpoint = MagicMock()
        endpoint.get_extra_info.side_effect = lambda name: {
            "sockname": ("::", 49152, 0, 0),
            "socket": raw_socket,
        }.get(name)

        with (
            patch("lifx.network.transport._socket_factory", return_value=raw_socket),
            patch("asyncio.get_running_loop") as mock_loop,
        ):
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                return_value=(endpoint, MagicMock())
            )
            await transport.open()

        raw_socket.setsockopt.assert_any_call(
            socket.IPPROTO_IPV6,
            socket.IPV6_V6ONLY,
            1,
        )
        assert raw_socket.method_calls.index(
            call.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        ) < raw_socket.method_calls.index(call.bind(("::", 0, 0, 0)))
        await transport.close()

    async def test_ipv6_endpoint_without_reuse_port_support(self) -> None:
        """IPv6 setup works when the platform omits ``SO_REUSEPORT``."""
        transport = UdpTransport(ip_address="::", port=0)
        raw_socket = MagicMock()
        datagram_transport = MagicMock()
        datagram_transport.get_extra_info.return_value = ("::", 49152, 0, 0)

        with (
            patch("lifx.network.transport._SO_REUSEPORT", None),
            patch("lifx.network.transport._socket_factory", return_value=raw_socket),
            patch("asyncio.get_running_loop") as mock_loop,
        ):
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                return_value=(datagram_transport, MagicMock())
            )
            await transport.open()

        raw_socket.setsockopt.assert_called_once_with(
            socket.IPPROTO_IPV6,
            socket.IPV6_V6ONLY,
            1,
        )
        assert raw_socket.method_calls.index(
            call.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        ) < raw_socket.method_calls.index(call.bind(("::", 0, 0, 0)))
        await transport.close()

    async def test_zoned_ipv6_bind_uses_canonical_native_sockaddr(self) -> None:
        """A textual interface zone becomes the bind tuple's scope field."""
        transport = UdpTransport(ip_address="fe80::1%test0", port=56700)
        raw_socket = MagicMock()
        datagram_transport = MagicMock()
        datagram_transport.get_extra_info.return_value = (
            "fe80::1",
            56700,
            0,
            7,
        )

        with (
            patch("lifx.network.address.socket.if_nametoindex", return_value=7),
            patch("lifx.network.transport._socket_factory", return_value=raw_socket),
            patch("asyncio.get_running_loop") as mock_loop,
        ):
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                return_value=(datagram_transport, MagicMock())
            )
            await transport.open()

        raw_socket.bind.assert_called_once_with(("fe80::1", 56700, 0, 7))
        await transport.close()


class TestSendFamilyAssertion:
    """A destination of the wrong family must fail loudly, not silently (B1).

    Sending an IPv6 literal down an ``AF_INET`` socket raises
    :class:`socket.gaierror`, an ``OSError`` subclass, which asyncio hands to
    ``error_received``. That handler deliberately swallows everything it is
    given, so before this guard existed an address-shaped configuration error
    was indistinguishable from a dead device: the caller waited out the whole
    retry schedule and got a timeout naming nothing. The pre-send check turns
    it into a typed, immediate, self-describing failure.
    """

    #: Generous enough to survive a loaded CI runner, tight enough that a
    #: swallowed error waiting out the retry schedule could never pass.
    _FAST_FAILURE_SECONDS = 0.1

    async def test_ipv6_destination_on_an_ipv4_socket_raises_immediately(self) -> None:
        """The B1 case: an IPv6 target reached through the IPv4 seam."""
        transport, datagram_transport, _ = await _open_mock_transport("0.0.0.0")

        started = time.perf_counter()
        with pytest.raises(NetworkError) as excinfo:
            await transport.send(b"x" * 36, ("::1", 56700))
        elapsed = time.perf_counter() - started

        assert elapsed < self._FAST_FAILURE_SECONDS
        assert str(excinfo.value) == (
            "Destination ::1 requires AF_INET6 but the socket family is AF_INET"
        )
        datagram_transport.sendto.assert_not_called()

    async def test_ipv4_destination_on_an_ipv6_socket_raises_immediately(self) -> None:
        """The mirror case, so the guard is not one-directional."""
        transport, datagram_transport, _ = await _open_mock_transport("::")

        started = time.perf_counter()
        with pytest.raises(NetworkError) as excinfo:
            await transport.send(b"x" * 36, ("127.0.0.1", 56700))
        elapsed = time.perf_counter() - started

        assert elapsed < self._FAST_FAILURE_SECONDS
        assert str(excinfo.value) == (
            "Destination 127.0.0.1 requires AF_INET but the socket family is AF_INET6"
        )
        datagram_transport.sendto.assert_not_called()

    async def test_matching_ipv4_destination_still_sends(self) -> None:
        """The happy path is untouched: a matching family reaches sendto."""
        transport, datagram_transport, _ = await _open_mock_transport("0.0.0.0")

        await transport.send(b"x" * 36, ("127.0.0.1", 56700))

        datagram_transport.sendto.assert_called_once_with(
            b"x" * 36, ("127.0.0.1", 56700)
        )

    async def test_matching_ipv6_destination_uses_canonical_sockaddr(self) -> None:
        """IPv6 sends use the four-field sockaddr required by Windows."""
        transport, datagram_transport, _ = await _open_mock_transport("::")

        await transport.send(b"x" * 36, ("fd00:1::", 56700))

        datagram_transport.sendto.assert_called_once_with(
            b"x" * 36, ("fd00:1::", 56700, 0, 0)
        )

    async def test_existing_ipv6_sockaddr_preserves_flowinfo_and_scope(self) -> None:
        """A received IPv6 sockaddr can be sent back without losing routing."""
        transport, datagram_transport, _ = await _open_mock_transport("::")

        await transport.send(b"x" * 36, ("fe80::1", 56700, 3, 7))

        datagram_transport.sendto.assert_called_once_with(
            b"x" * 36, ("fe80::1", 56700, 3, 7)
        )

    async def test_numeric_zoned_ipv6_destination_uses_scope_id(self) -> None:
        """A numeric zone becomes the native sockaddr scope identifier."""
        transport, datagram_transport, _ = await _open_mock_transport("::")

        with patch("lifx.network.address.socket.if_nametoindex") as if_nametoindex:
            await transport.send(b"x" * 36, ("fe80::1%7", 56700))

        if_nametoindex.assert_not_called()
        datagram_transport.sendto.assert_called_once_with(
            b"x" * 36, ("fe80::1", 56700, 0, 7)
        )

    async def test_named_zoned_ipv6_destination_resolves_scope_id(self) -> None:
        """A named zone is resolved once before the datagram is sent."""
        transport, datagram_transport, _ = await _open_mock_transport("::")

        with patch(
            "lifx.network.address.socket.if_nametoindex", return_value=11
        ) as if_nametoindex:
            await transport.send(b"x" * 36, ("fe80::1%test0", 56700))

        if_nametoindex.assert_called_once_with("test0")
        datagram_transport.sendto.assert_called_once_with(
            b"x" * 36, ("fe80::1", 56700, 0, 11)
        )

    async def test_unknown_named_ipv6_zone_raises_immediately(self) -> None:
        """An unknown interface is a typed pre-send configuration failure."""
        transport, datagram_transport, _ = await _open_mock_transport("::")
        protocol = transport._protocol
        assert protocol is not None

        started = time.perf_counter()
        with (
            patch(
                "lifx.network.address.socket.if_nametoindex",
                side_effect=OSError("synthetic interface is unavailable"),
            ) as if_nametoindex,
            pytest.raises(NetworkError, match="IPv6 zone identifier") as excinfo,
        ):
            await transport.send(b"x" * 36, ("fe80::1%missing0", 56700))
        elapsed = time.perf_counter() - started

        assert elapsed < self._FAST_FAILURE_SECONDS
        assert isinstance(excinfo.value.__cause__, ValueError)
        assert isinstance(excinfo.value.__cause__.__cause__, OSError)
        if_nametoindex.assert_called_once_with("missing0")
        datagram_transport.sendto.assert_not_called()
        assert transport.is_open
        assert transport._protocol is protocol

        await transport.send(b"x" * 36, ("fd00:1::", 56700))
        datagram_transport.sendto.assert_called_once_with(
            b"x" * 36, ("fd00:1::", 56700, 0, 0)
        )

    async def test_malformed_named_zone_is_wrapped_with_destination_context(
        self,
    ) -> None:
        """Socket and codec failures stay inside the Lifx exception hierarchy."""
        transport, datagram_transport, _ = await _open_mock_transport("::")

        with pytest.raises(NetworkError, match="destination.*zone identifier"):
            await transport.send(b"x" * 36, ("fe80::1%a\x00b", 56700))

        datagram_transport.sendto.assert_not_called()

    async def test_out_of_range_numeric_ipv6_zone_raises_immediately(self) -> None:
        """A scope outside the native unsigned 32-bit range fails pre-send."""
        transport, datagram_transport, _ = await _open_mock_transport("::")
        protocol = transport._protocol
        assert protocol is not None

        started = time.perf_counter()
        with (
            patch("lifx.network.address.socket.if_nametoindex") as if_nametoindex,
            pytest.raises(NetworkError, match="IPv6 zone identifier"),
        ):
            await transport.send(b"x" * 36, (f"fe80::1%{2**32}", 56700))
        elapsed = time.perf_counter() - started

        assert elapsed < self._FAST_FAILURE_SECONDS
        if_nametoindex.assert_not_called()
        datagram_transport.sendto.assert_not_called()
        assert transport.is_open
        assert transport._protocol is protocol

    async def test_zero_numeric_ipv6_zone_raises_immediately(self) -> None:
        """An explicit zero scope cannot become an unscoped link-local send."""
        transport, datagram_transport, _ = await _open_mock_transport("::")
        protocol = transport._protocol
        assert protocol is not None

        started = time.perf_counter()
        with (
            patch("lifx.network.address.socket.if_nametoindex") as if_nametoindex,
            pytest.raises(NetworkError, match="IPv6 zone identifier"),
        ):
            await transport.send(b"x" * 36, ("fe80::1%0", 56700))
        elapsed = time.perf_counter() - started

        assert elapsed < self._FAST_FAILURE_SECONDS
        if_nametoindex.assert_not_called()
        datagram_transport.sendto.assert_not_called()
        assert transport.is_open
        assert transport._protocol is protocol

    async def test_ipv4_broadcast_destination_still_sends(self) -> None:
        """Discovery broadcasts to a literal no device owns; it must pass."""
        transport, datagram_transport, _ = await _open_mock_transport("0.0.0.0")

        await transport.send(b"x" * 36, ("255.255.255.255", 56700))

        datagram_transport.sendto.assert_called_once_with(
            b"x" * 36, ("255.255.255.255", 56700)
        )

    @pytest.mark.parametrize(
        "error_number",
        [errno.EHOSTUNREACH, errno.EHOSTDOWN, errno.ENETUNREACH],
    )
    async def test_peer_errors_are_still_swallowed_after_a_send(
        self, error_number: int
    ) -> None:
        """The guard must not reclassify a peer problem as a socket problem.

        This is the regression the family assertion most easily breaks: a
        sleeping device produces a sustained stream of these, and converting
        any of them into a raise, or into endpoint death, would tear down
        healthy request flows across the whole fleet.
        """
        transport = UdpTransport()
        await transport.open()
        protocol = transport._protocol
        assert protocol is not None

        try:
            await transport.send(b"x" * 36, ("127.0.0.1", 56700))

            # asyncio delivers the ICMP-derived failure after sendto returned.
            for _ in range(50):
                protocol.error_received(OSError(error_number, "peer unreachable"))

            assert transport.is_open
            assert transport._protocol is protocol
            assert transport._transport is not None
        finally:
            await transport.close()

    async def test_send_on_a_dead_endpoint_raises_the_typed_error(self) -> None:
        """A dead endpoint is reported as such, never as an AttributeError.

        The family check needs the socket family recorded at open time, so a
        transport whose endpoint has since died must still take the "Socket
        not open" path rather than dereferencing what open() left behind.
        """
        transport = UdpTransport()
        await transport.open()
        protocol = transport._protocol
        assert protocol is not None

        protocol.error_received(OSError(errno.EBADF, "Bad file descriptor"))
        assert not transport.is_open

        with pytest.raises(NetworkError) as excinfo:
            await transport.send(b"x" * 36, ("::1", 56700))

        assert str(excinfo.value) == "Socket not open"
