"""Tests for mDNS transport."""

from __future__ import annotations

import asyncio
import errno
import gc
import socket
import warnings
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.const import MDNS_ADDRESS, MDNS_PORT
from lifx.exceptions import LifxNetworkError, LifxTimeoutError
from lifx.network.mdns.transport import MdnsTransport


class _SocketLedger:
    """Tracks the real sockets ``open()`` was handed, and their fate.

    ``live`` is the point of the whole thing: a socket is added when it is
    created and removed when it is closed, so an empty list at the end of a
    failed ``open()`` is a direct assertion that no descriptor was stranded.
    It also matters that nothing else keeps a reference to a leaked socket,
    or CPython can never collect it and the ResourceWarning that would name
    the leak is never emitted.
    """

    def __init__(self) -> None:
        self.created = 0
        self.closed = 0
        self.live: list[socket.socket] = []

    def record_create(self, sock: socket.socket) -> None:
        """Note a socket handed to the code under test."""
        self.created += 1
        self.live.append(sock)

    def record_close(self, sock: socket.socket) -> None:
        """Note that the code under test released a socket."""
        self.closed += 1
        self.live = [held for held in self.live if held is not sock]


class _RecordingSocket(socket.socket):
    """A real UDP socket that reports its own ``close()`` to a ledger.

    A ``MagicMock`` can prove ``open()`` *called* ``close()``, but it owns no
    descriptor, so it can never emit the ResourceWarning that proves one was
    actually released. These tests exist to catch a leaked descriptor, so
    they use the real thing and instrument it, and can fail on cue at each of
    the three steps between ``socket()`` and a working endpoint.
    """

    _ledger: _SocketLedger
    _fail_at: str | None = None

    def bind(self, address: Any) -> None:
        """Bind, or fail on cue."""
        if self._fail_at == "bind":
            raise OSError(errno.EADDRINUSE, "forced bind failure")
        super().bind(address)

    def setsockopt(self, level: int, optname: int, *args: Any) -> None:
        """Set a socket option, or fail on cue.

        Only the multicast TTL option is failed, because it is the one the
        transport sets *after* binding: failing the earlier SO_REUSEADDR call
        would not exercise the bound-but-unusable state this covers.
        """
        if self._fail_at == "setsockopt" and (level, optname) == (
            socket.IPPROTO_IP,
            socket.IP_MULTICAST_TTL,
        ):
            raise OSError(errno.ENOPROTOOPT, "forced setsockopt failure")
        super().setsockopt(level, optname, *args)

    def close(self) -> None:
        """Close, recording that the code under test asked for it."""
        self._ledger.record_close(self)
        super().close()


def _recording_socket_factory(ledger: _SocketLedger, fail_at: str | None = None) -> Any:
    """Return a ``socket.socket`` stand-in producing instrumented sockets."""

    def factory(*args: Any, **kwargs: Any) -> _RecordingSocket:
        sock = _RecordingSocket(*args, **kwargs)
        sock._ledger = ledger
        sock._fail_at = fail_at
        ledger.record_create(sock)
        return sock

    return factory


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
        protocol = MagicMock()
        datagram_transport = MagicMock()
        sock = MagicMock()
        transport._protocol = protocol
        transport._transport = datagram_transport
        transport._socket = sock

        # Should not raise and should return early
        await transport.open()

        assert transport._protocol is protocol
        assert transport._transport is datagram_transport
        assert transport._socket is sock
        await transport.close()

    @pytest.mark.asyncio
    async def test_open_binds_ephemeral_port(self) -> None:
        """Test that open() binds to an ephemeral port (legacy unicast mode).

        Binding to 5353 would share the port with a system mDNS daemon
        (mDNSResponder, Avahi), which steals unicast responses.
        """
        transport = MdnsTransport()

        mock_socket = MagicMock(spec=socket.socket)
        mock_socket.getsockname.return_value = ("", 12345)

        mock_datagram_transport = MagicMock()

        with patch("socket.socket", return_value=mock_socket):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                    return_value=(mock_datagram_transport, None)
                )

                await transport.open()

                # Verify bind was called once, to an ephemeral port
                assert mock_socket.bind.call_count == 1
                assert mock_socket.bind.call_args_list[0][0][0] == ("", 0)

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
    async def test_open_bind_fails(self) -> None:
        """Test that open() raises LifxNetworkError if bind fails."""
        transport = MdnsTransport()

        mock_socket = MagicMock(spec=socket.socket)
        mock_socket.bind.side_effect = OSError("Cannot bind")

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


class TestMdnsTransportIsOpen:
    """Tests for is_open property."""

    def test_is_open_false_when_no_protocol(self) -> None:
        """Test is_open is False when protocol is None."""
        transport = MdnsTransport()
        assert transport.is_open is False

    def test_is_open_true_when_complete_endpoint_set(self) -> None:
        """Test is_open requires one complete, publishable endpoint."""
        transport = MdnsTransport()
        transport._protocol = MagicMock()
        transport._transport = MagicMock()
        transport._socket = MagicMock()
        assert transport.is_open is True


# The mDNS transport shares _UdpProtocol with UdpTransport;
# the protocol class is covered by tests/test_network/test_transport.py.


class TestMdnsTransportOpenFailureIsClean:
    """A partway-failed open() must leave nothing behind (IPV6-04, SPEC R4).

    Two distinct leaks live here. The obvious one is the descriptor: the
    socket is created, bound and configured before ``create_datagram_endpoint``
    is ever awaited, and the original ``except OSError`` block raised without
    closing it, so a retry loop around ``open()`` burned a file descriptor per
    attempt.

    The subtler one is state. A failed or interrupted attempt must not publish
    a partial endpoint or make ``is_open`` true. Closing the descriptor alone
    would still permit incoherent lifecycle state, which is why every case
    here also asserts the object can still be opened.
    """

    @staticmethod
    def _endpoint_for(fail_at: str) -> AsyncMock:
        """Build the mocked ``create_datagram_endpoint`` for a failure case."""
        if fail_at == "endpoint":
            return AsyncMock(
                side_effect=OSError(errno.EADDRNOTAVAIL, "forced endpoint failure")
            )
        # Unreachable for the bind and setsockopt cases, which fail earlier.
        return AsyncMock(return_value=(MagicMock(), MagicMock()))

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fail_at", ["bind", "setsockopt", "endpoint"])
    async def test_failed_open_closes_its_socket_and_resets_state(
        self, fail_at: str
    ) -> None:
        """Each failure step releases the descriptor and clears the state."""
        ledger = _SocketLedger()
        transport = MdnsTransport()

        with warnings.catch_warnings():
            warnings.simplefilter("error", ResourceWarning)

            with patch("socket.socket", _recording_socket_factory(ledger, fail_at)):
                with patch("asyncio.get_running_loop") as mock_loop:
                    mock_loop.return_value.create_datagram_endpoint = (
                        self._endpoint_for(fail_at)
                    )

                    with pytest.raises(
                        LifxNetworkError, match="Failed to open mDNS socket"
                    ) as excinfo:
                        await transport.open()

            # The chained OSError's traceback pins open()'s frame, and that
            # frame holds the socket it created. Nothing can be collected,
            # and so nothing can warn, until that reference is dropped.
            excinfo.value.__traceback__ = None
            excinfo.value.__cause__ = None
            excinfo.value.__context__ = None
            del excinfo
            gc.collect()

        assert ledger.created == 1
        assert ledger.closed == 1
        assert ledger.live == []

        assert transport.is_open is False
        assert transport._socket is None
        assert transport._protocol is None
        assert transport._transport is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fail_at", ["bind", "setsockopt", "endpoint"])
    async def test_transport_is_reusable_after_a_failed_open(
        self, fail_at: str
    ) -> None:
        """A failed open() leaves an object that can still be opened.

        This is the assertion that closing the descriptor alone would not
        satisfy: an endpoint failure that left ``_protocol`` set would make
        the retry below early-return as "already open" and hand back a
        transport with no endpoint at all.
        """
        ledger = _SocketLedger()
        transport = MdnsTransport()

        with patch("socket.socket", _recording_socket_factory(ledger, fail_at)):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.create_datagram_endpoint = self._endpoint_for(
                    fail_at
                )
                with pytest.raises(LifxNetworkError):
                    await transport.open()

        # Retry with nothing forced, exactly as a caller's retry loop would.
        # A MagicMock socket here rather than a real one: this half of the
        # test is about state, and a mock owns no descriptor to strand.
        mock_socket = MagicMock(spec=socket.socket)
        mock_socket.getsockname.return_value = ("", MDNS_PORT)
        datagram_transport = MagicMock()

        with patch("socket.socket", return_value=mock_socket):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                    return_value=(datagram_transport, MagicMock())
                )
                await transport.open()

        assert transport.is_open is True
        assert transport._socket is mock_socket
        assert transport._transport is datagram_transport

        await transport.close()

    @pytest.mark.asyncio
    async def test_cancelled_open_closes_its_socket_and_resets_state(self) -> None:
        """Cancellation releases the descriptor and preserves its exception type."""
        ledger = _SocketLedger()
        transport = MdnsTransport()
        entered = asyncio.Event()
        blocked = asyncio.Event()

        async def _endpoint(protocol_factory: Any, **kwargs: Any) -> None:
            """Suspend endpoint creation until the caller cancels it."""
            entered.set()
            await blocked.wait()

        with patch("socket.socket", _recording_socket_factory(ledger)):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.create_datagram_endpoint = _endpoint
                opening = asyncio.create_task(transport.open())
                await entered.wait()
                opening.cancel()

                with pytest.raises(asyncio.CancelledError):
                    await opening

        assert ledger.created == 1
        assert ledger.closed == 1
        assert ledger.live == []
        assert transport.is_open is False
        assert transport._socket is None
        assert transport._protocol is None
        assert transport._transport is None

        mock_socket = MagicMock(spec=socket.socket)
        mock_socket.getsockname.return_value = ("", MDNS_PORT)
        datagram_transport = MagicMock()
        with patch("socket.socket", return_value=mock_socket):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                    return_value=(datagram_transport, MagicMock())
                )
                await transport.open()

        assert transport.is_open is True
        assert transport._socket is mock_socket
        assert transport._transport is datagram_transport
        await transport.close()

    @pytest.mark.asyncio
    async def test_non_oserror_is_cleaned_up_and_reraised_unchanged(self) -> None:
        """A non-OSError keeps its type and identity after socket cleanup."""
        ledger = _SocketLedger()
        transport = MdnsTransport()
        failure = RuntimeError("forced non-OSError endpoint failure")

        with patch("socket.socket", _recording_socket_factory(ledger)):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                    side_effect=failure
                )
                with pytest.raises(RuntimeError) as excinfo:
                    await transport.open()

        assert excinfo.value is failure
        assert ledger.created == ledger.closed == 1
        assert ledger.live == []
        assert transport.is_open is False
        assert transport._socket is None
        assert transport._protocol is None
        assert transport._transport is None


class TestMdnsTransportOpenConcurrency:
    """Concurrent lifecycle operations preserve one coherent state (SPEC R4)."""

    @pytest.mark.asyncio
    async def test_concurrent_opens_build_exactly_one_endpoint(self) -> None:
        """Two tasks opening at once must produce one endpoint, not two."""
        ledger = _SocketLedger()
        transport = MdnsTransport()
        entered = asyncio.Event()
        released = asyncio.Event()
        endpoints: list[MagicMock] = []

        async def _endpoint(
            protocol_factory: Any, **kwargs: Any
        ) -> tuple[MagicMock, Any]:
            """Hold the first caller inside the await until released."""
            entered.set()
            await released.wait()
            datagram_transport = MagicMock()
            endpoints.append(datagram_transport)
            return datagram_transport, protocol_factory()

        try:
            with patch("socket.socket", _recording_socket_factory(ledger)):
                with patch("asyncio.get_running_loop") as mock_loop:
                    mock_loop.return_value.create_datagram_endpoint = _endpoint

                    first = asyncio.ensure_future(transport.open())
                    second = asyncio.ensure_future(transport.open())

                    # Deterministic interleaving: the first task is parked
                    # inside create_datagram_endpoint, and the short sleep
                    # lets the second reach its own decision point while the
                    # first is still in flight.
                    await entered.wait()
                    await asyncio.sleep(0.01)
                    released.set()
                    await asyncio.gather(first, second)

            assert len(endpoints) == 1
            assert ledger.created == 1
            # Created equals closed plus still-live: one socket, none closed,
            # one held by the single live endpoint.
            assert ledger.created == ledger.closed + len(ledger.live)
            assert transport.is_open is True
        finally:
            for sock in list(ledger.live):
                sock.close()

    @pytest.mark.asyncio
    async def test_queued_open_invalidated_by_close_returns_closed(self) -> None:
        """A close invalidates an opener queued before it acquired the lock."""
        transport = MdnsTransport()
        await transport._state_lock.acquire()
        opening = asyncio.create_task(transport.open())
        await asyncio.sleep(0)

        await transport.close()
        transport._state_lock.release()
        await opening

        assert transport.is_open is False
        assert transport._socket is None
        assert transport._protocol is None
        assert transport._transport is None

    @pytest.mark.asyncio
    async def test_failure_after_endpoint_creation_closes_endpoint(self) -> None:
        """A failure after endpoint creation closes it before clearing state."""
        transport = MdnsTransport()
        sock = MagicMock(spec=socket.socket)
        datagram_transport = MagicMock()
        failure = RuntimeError("forced post-endpoint failure")

        with (
            patch("socket.socket", return_value=sock),
            patch("asyncio.get_running_loop") as mock_loop,
            patch(
                "lifx.network.mdns.transport._LOGGER.debug",
                side_effect=[None, failure, None],
            ),
        ):
            mock_loop.return_value.create_datagram_endpoint = AsyncMock(
                return_value=(datagram_transport, MagicMock())
            )
            with pytest.raises(RuntimeError) as excinfo:
                await transport.open()

        assert excinfo.value is failure
        datagram_transport.close.assert_called_once_with()
        assert transport.is_open is False

    @pytest.mark.asyncio
    async def test_close_releases_unpublished_socket(self) -> None:
        """Close releases a socket even when no endpoint owns it yet."""
        transport = MdnsTransport()
        sock = MagicMock(spec=socket.socket)
        transport._socket = sock

        await transport.close()

        sock.close.assert_called_once_with()
        assert transport.is_open is False

    @pytest.mark.asyncio
    async def test_close_racing_successful_open_wins_and_allows_reopen(self) -> None:
        """close() invalidates an endpoint that completes after close returns."""
        ledger = _SocketLedger()
        transport = MdnsTransport()
        entered = asyncio.Event()
        released = asyncio.Event()
        attempts = 0
        endpoints: list[MagicMock] = []

        async def _endpoint(
            protocol_factory: Any, **kwargs: Any
        ) -> tuple[MagicMock, Any]:
            """Suspend only the endpoint racing the close."""
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                entered.set()
                await released.wait()
            datagram_transport = MagicMock()
            datagram_transport.close.side_effect = kwargs["sock"].close
            endpoints.append(datagram_transport)
            return datagram_transport, protocol_factory()

        with patch("socket.socket", _recording_socket_factory(ledger)):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.create_datagram_endpoint = _endpoint
                opening = asyncio.create_task(transport.open())
                await entered.wait()

                assert transport.is_open is False
                await transport.close()
                released.set()
                await opening

                assert endpoints[0].close.call_count == 1
                assert ledger.created == ledger.closed == 1
                assert transport.is_open is False
                assert transport._socket is None
                assert transport._protocol is None
                assert transport._transport is None

                await transport.open()
                assert attempts == 2
                assert transport.is_open is True
                await transport.close()

        assert ledger.created == ledger.closed == 2
        assert ledger.live == []

    @pytest.mark.asyncio
    async def test_close_racing_a_failing_open_strands_nothing(self) -> None:
        """close() landing mid-open must not leave the failure path stranded."""
        ledger = _SocketLedger()
        transport = MdnsTransport()
        entered = asyncio.Event()
        released = asyncio.Event()

        async def _endpoint(protocol_factory: Any, **kwargs: Any) -> None:
            """Fail, but only once the racing close() has happened."""
            entered.set()
            await released.wait()
            raise OSError(errno.EADDRNOTAVAIL, "forced endpoint failure")

        try:
            with patch("socket.socket", _recording_socket_factory(ledger)):
                with patch("asyncio.get_running_loop") as mock_loop:
                    mock_loop.return_value.create_datagram_endpoint = _endpoint

                    opening = asyncio.ensure_future(transport.open())
                    await entered.wait()

                    # close() lands while open() is still inside its await.
                    await transport.close()

                    released.set()
                    with pytest.raises(LifxNetworkError):
                        await opening

            assert ledger.created == 1
            assert ledger.closed == 1
            assert ledger.live == []
            assert transport.is_open is False
            assert transport._socket is None
            assert transport._transport is None
        finally:
            for sock in list(ledger.live):
                sock.close()

    @pytest.mark.asyncio
    async def test_cancelled_open_allows_waiting_open_to_establish_endpoint(
        self,
    ) -> None:
        """A concurrent opener waits out cancellation and builds a replacement."""
        ledger = _SocketLedger()
        transport = MdnsTransport()
        first_entered = asyncio.Event()
        hold_first = asyncio.Event()
        attempts = 0

        async def _endpoint(
            protocol_factory: Any, **kwargs: Any
        ) -> tuple[MagicMock, Any]:
            """Block only the first endpoint attempt."""
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                first_entered.set()
                await hold_first.wait()
            datagram_transport = MagicMock()
            datagram_transport.close.side_effect = kwargs["sock"].close
            return datagram_transport, protocol_factory()

        with patch("socket.socket", _recording_socket_factory(ledger)):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.create_datagram_endpoint = _endpoint
                first = asyncio.create_task(transport.open())
                await first_entered.wait()
                second = asyncio.create_task(transport.open())

                first.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await first
                await second

                assert attempts == 2
                assert ledger.created == 2
                assert ledger.closed == 1
                assert len(ledger.live) == 1
                assert transport.is_open is True

                await transport.close()

        assert ledger.created == ledger.closed == 2
        assert ledger.live == []
        assert transport.is_open is False

    @pytest.mark.asyncio
    async def test_close_racing_cancelled_open_finishes_closed_and_reopens(
        self,
    ) -> None:
        """A racing close wins after cancellation without leaking the socket."""
        ledger = _SocketLedger()
        transport = MdnsTransport()
        first_entered = asyncio.Event()
        hold_first = asyncio.Event()
        close_started = asyncio.Event()
        attempts = 0

        async def _endpoint(
            protocol_factory: Any, **kwargs: Any
        ) -> tuple[MagicMock, Any]:
            """Block the cancelled endpoint and complete the later retry."""
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                first_entered.set()
                await hold_first.wait()
            datagram_transport = MagicMock()
            datagram_transport.close.side_effect = kwargs["sock"].close
            return datagram_transport, protocol_factory()

        async def _close() -> None:
            """Expose when close has begun racing the in-flight open."""
            close_started.set()
            await transport.close()

        with patch("socket.socket", _recording_socket_factory(ledger)):
            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value.create_datagram_endpoint = _endpoint
                opening = asyncio.create_task(transport.open())
                await first_entered.wait()
                closing = asyncio.create_task(_close())
                await close_started.wait()

                opening.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await opening
                await closing

                assert ledger.created == ledger.closed == 1
                assert ledger.live == []
                assert transport.is_open is False
                assert transport._socket is None
                assert transport._protocol is None
                assert transport._transport is None

                await transport.open()
                assert attempts == 2
                assert transport.is_open is True
                await transport.close()

        assert ledger.created == ledger.closed == 2
        assert ledger.live == []
        assert transport.is_open is False
