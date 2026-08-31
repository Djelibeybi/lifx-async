"""UDP transport layer for LIFX communication."""

from __future__ import annotations

import asyncio
import errno
import logging
import socket
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lifx.const import (
    DEFAULT_IP_ADDRESS,
    MAX_PACKET_SIZE,
    MIN_PACKET_SIZE,
    TIMEOUT_ERRORS,
)
from lifx.exceptions import LifxNetworkError, LifxProtocolError, LifxTimeoutError
from lifx.network.address import (
    SocketAddress,
    family_for,
    family_for_sockaddr,
    sockaddr_for,
)

if TYPE_CHECKING:
    from asyncio import DatagramTransport

_LOGGER = logging.getLogger(__name__)
_socket_factory = socket.socket
_SO_REUSEPORT: int | None = getattr(socket, "SO_REUSEPORT", None)


# Errnos that mean the endpoint itself is gone rather than one datagram
# failing to reach one peer. Everything else reported to error_received --
# EHOSTDOWN, EHOSTUNREACH, ENETUNREACH, ECONNREFUSED, EACCES -- describes the
# destination, not the socket, and must never tear the endpoint down (a device
# asleep or off the network would otherwise cause socket churn).
_FATAL_SOCKET_ERRNOS: frozenset[int] = frozenset({errno.EBADF, errno.ENOTSOCK})


@dataclass
class PeerInfo:
    """Identity of the device a per-device socket talks to.

    Deliberately mutable and shared by reference with the socket's owner: a
    connection opened without a serial (``Device.from_ip()`` and friends)
    learns the real serial from the first reply, long after the transport was
    built. A string snapshot taken at open() time would keep naming the
    ``000000000000`` placeholder for the life of the socket.

    Attributes:
        serial: Device serial as a 12-digit hex string.
        ip: Device IP address.
        port: Device UDP port. Included because two connections to the same
            host on different ports (several emulator devices on localhost, or
            a port-mapped deployment) are otherwise indistinguishable in logs.
    """

    serial: str
    ip: str
    port: int


def _peer_record(
    class_name: str, peer: PeerInfo | None, **fields: object
) -> dict[str, object]:
    """Build a structured log record, tagged with the peer when known.

    Send and receive errors name the errno but never the destination, so
    without this a warning about an unreachable device cannot be traced back
    to which device went away. The peer is emitted as discrete ``serial`` /
    ``ip`` / ``port`` keys to match every other structured log in the library,
    so a log pipeline selecting one device by serial sees transport records too.

    Args:
        class_name: Emitting class, used as the record's ``class`` field.
        peer: Device this socket talks to, or None for the shared broadcast
            socket used by discovery, which has no single peer.
        **fields: Remaining record fields.

    Returns:
        The structured log record.
    """
    record: dict[str, object] = {"class": class_name, **fields}
    if peer is not None:
        record["serial"] = peer.serial
        record["ip"] = peer.ip
        record["port"] = peer.port
    return record


class _UdpProtocol(asyncio.DatagramProtocol):
    """Internal DatagramProtocol implementation for receiving UDP packets."""

    _MAX_QUEUE_SIZE = 1000
    _DROP_LOG_INTERVAL = 100  # Log every Nth dropped packet
    _ERROR_LOG_INTERVAL = 100  # Log every Nth per-datagram error

    def __init__(
        self,
        on_endpoint_lost: Callable[[_UdpProtocol, Exception | None], None]
        | None = None,
        peer: PeerInfo | None = None,
    ) -> None:
        """Initialize the protocol.

        Args:
            on_endpoint_lost: Called once when the endpoint dies, with this
                protocol instance and the causing exception (None when the
                endpoint was closed rather than failed). The owner uses it to
                drop its references to a socket that can no longer send or
                receive.
            peer: Device this socket talks to, included in warning logs. Held
                by reference so a serial learned after open() shows up in
                later records. A per-device socket knows its peer; the
                broadcast socket used for discovery does not, so it is
                optional and omitted from the log when unset.
        """
        self._peer = peer
        self.queue: asyncio.Queue[tuple[bytes, SocketAddress]] = asyncio.Queue(
            maxsize=self._MAX_QUEUE_SIZE
        )
        self.transport: DatagramTransport | None = None
        self._dropped_count: int = 0
        self._error_count: int = 0
        self._on_endpoint_lost = on_endpoint_lost
        self._lost = False

    def _log(self, **fields: object) -> dict[str, object]:
        """Build a structured log record, tagged with the peer when known."""
        return _peer_record("_UdpProtocol", self._peer, **fields)

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Called when connection is established."""
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: SocketAddress) -> None:
        """Called when a datagram is received."""
        # A received datagram proves the socket still works, so the
        # rate-limited error log starts fresh on the next failure burst.
        self._error_count = 0
        try:
            self.queue.put_nowait((data, addr))
        except asyncio.QueueFull:
            self._dropped_count += 1
            if (
                self._dropped_count == 1
                or self._dropped_count % self._DROP_LOG_INTERVAL == 0
            ):
                _LOGGER.warning(
                    self._log(
                        method="datagram_received",
                        action="packet_dropped",
                        reason="queue_full",
                        # The socket accepts datagrams from any host, so the
                        # sender is not necessarily the configured peer: a
                        # stray broadcaster can overrun the queue and the peer
                        # alone would blame a device that sent nothing. Split
                        # into discrete keys for the same reason the peer is:
                        # a tuple JSON-encodes to a positional array no log
                        # pipeline can filter on by host.
                        sender_ip=addr[0],
                        sender_port=addr[1],
                        total_dropped=self._dropped_count,
                    )
                )

    def error_received(self, exc: Exception) -> None:
        """Called when a datagram could not be sent or received.

        On an unconnected UDP socket asyncio reports every OSError from
        ``sendto``/``recvfrom`` here, including the ICMP-derived errors seen
        when a device drops off the network (EHOSTDOWN, EHOSTUNREACH,
        ENETUNREACH). Those are per-datagram and routine: a sleeping or
        unreachable device produces a sustained stream of them and must not be
        treated as the endpoint dying, so they are logged (rate-limited) and
        nothing else. Only errnos that mean the socket itself is invalid --
        ``_FATAL_SOCKET_ERRNOS`` -- signal endpoint death, because asyncio
        never calls ``connection_lost`` for them: a socket closed underneath
        the loop keeps reporting EBADF here forever while the transport still
        claims to be open.
        """
        self._error_count += 1
        if self._error_count == 1 or self._error_count % self._ERROR_LOG_INTERVAL == 0:
            _LOGGER.warning(
                self._log(
                    method="error_received",
                    error=str(exc),
                    total_errors=self._error_count,
                )
            )

        if isinstance(exc, OSError) and exc.errno in _FATAL_SOCKET_ERRNOS:
            self._notify_lost(exc)

    def connection_lost(self, exc: Exception | None) -> None:
        """Called when the endpoint is closed or fails fatally.

        For an unconnected datagram endpoint this fires on ``close()``,
        ``abort()``, and fatal (non-OSError) errors in asyncio's read/write
        path -- not on ordinary send or receive errors, which go to
        :meth:`error_received`.
        """
        self.transport = None
        self._notify_lost(exc)

    def _notify_lost(self, exc: Exception | None) -> None:
        """Report endpoint death to the owner exactly once."""
        if self._lost:
            return
        self._lost = True
        self.transport = None
        if self._on_endpoint_lost is not None:
            self._on_endpoint_lost(self, exc)


class UdpTransport:
    """UDP transport for sending and receiving LIFX packets.

    This class provides a simple interface for UDP communication with LIFX devices.
    It uses asyncio for async I/O operations.
    """

    def __init__(
        self,
        ip_address: str = DEFAULT_IP_ADDRESS,
        port: int = 0,
        broadcast: bool = False,
        peer: PeerInfo | None = None,
    ) -> None:
        """Initialize UDP transport.

        Args:
            port: Local port to bind to (0 for automatic assignment)
            broadcast: Enable broadcast mode for device discovery
            peer: Device this socket talks to, included in warning logs so an
                unreachable-peer error names the device. Held by reference, so
                a serial learned after open() shows up in later records. Left
                unset for the shared broadcast socket, which has no single
                peer.
        """
        self._ip_address = ip_address
        self._port = port
        self._broadcast = broadcast
        self._peer = peer
        self._protocol: _UdpProtocol | None = None
        self._transport: DatagramTransport | None = None
        # Recorded by open() so send() can compare a destination against it
        # without asking asyncio for the socket on every datagram. None means
        # no endpoint has been built yet, which send() reports as "not open".
        self._family: socket.AddressFamily | None = None
        self._state_lock = asyncio.Lock()
        self._state_generation = 0

    def _log(self, **fields: object) -> dict[str, object]:
        """Build a structured log record, tagged with the peer when known."""
        return _peer_record("UdpTransport", self._peer, **fields)

    async def __aenter__(self) -> UdpTransport:
        """Enter async context manager."""
        await self.open()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager."""
        await self.close()

    async def open(self) -> None:
        """Open the UDP socket."""
        generation = self._state_generation
        async with self._state_lock:
            if generation != self._state_generation:
                return

            if self.is_open:
                _LOGGER.debug(
                    {
                        "class": "UdpTransport",
                        "method": "open",
                        "action": "already_open",
                        "ip_address": self._ip_address,
                        "port": self._port,
                    }
                )
                return

            datagram_transport: DatagramTransport | None = None
            raw_socket: socket.socket | None = None
            try:
                loop = asyncio.get_running_loop()

                _LOGGER.debug(
                    {
                        "class": "UdpTransport",
                        "method": "open",
                        "action": "opening_socket",
                        "ip_address": self._ip_address,
                        "port": self._port,
                        "broadcast": self._broadcast,
                    }
                )

                # Create protocol
                protocol = _UdpProtocol(
                    on_endpoint_lost=self._endpoint_lost, peer=self._peer
                )

                # Create datagram endpoint. The socket family follows the local
                # bind address, derived by the one shared rule in
                # lifx.network.address, which is what lets this transport reach
                # Thread devices that have no IPv4 address.
                family = family_for(self._ip_address)
                bind_address = sockaddr_for(
                    (self._ip_address, self._port), require_routable=False
                )
                if family is socket.AF_INET6:
                    raw_socket = _socket_factory(socket.AF_INET6, socket.SOCK_DGRAM)
                    raw_socket.setsockopt(
                        socket.IPPROTO_IPV6,
                        socket.IPV6_V6ONLY,
                        1,
                    )
                    if _SO_REUSEPORT is not None:
                        raw_socket.setsockopt(
                            socket.SOL_SOCKET,
                            _SO_REUSEPORT,
                            1,
                        )
                    raw_socket.bind(bind_address)
                    raw_socket.setblocking(False)
                    datagram_transport, _ = await loop.create_datagram_endpoint(
                        lambda: protocol,
                        sock=raw_socket,
                    )
                    raw_socket = None  # asyncio owns the descriptor now
                else:
                    assert len(bind_address) == 2
                    datagram_transport, _ = await loop.create_datagram_endpoint(
                        lambda: protocol,
                        local_addr=bind_address,
                        reuse_port=_SO_REUSEPORT is not None,
                        family=family,
                    )

                # Get actual port assigned
                actual_port = datagram_transport.get_extra_info("sockname")[1]
                _LOGGER.debug(
                    {
                        "class": "UdpTransport",
                        "method": "open",
                        "action": "socket_opened",
                        "assigned_port": actual_port,
                        "broadcast": self._broadcast,
                    }
                )

                # Enable broadcast if requested
                if self._broadcast:
                    sock = datagram_transport.get_extra_info("socket")
                    if sock:
                        sock.setsockopt(
                            socket.SOL_SOCKET,
                            socket.SO_BROADCAST,
                            1,
                        )
                        _LOGGER.debug(
                            {
                                "class": "UdpTransport",
                                "method": "open",
                                "action": "broadcast_enabled",
                            }
                        )

                if generation != self._state_generation:
                    datagram_transport.close()
                    return

                self._protocol = protocol
                self._transport = datagram_transport
                self._family = family

            except BaseException as e:
                if datagram_transport is not None:
                    datagram_transport.close()
                if raw_socket is not None:
                    raw_socket.close()
                self._transport = None
                self._protocol = None
                self._family = None

                _LOGGER.debug(
                    self._log(
                        method="open",
                        action="failed",
                        bind_address=self._ip_address,
                        bind_port=self._port,
                        reason=str(e),
                    )
                )
                if isinstance(e, (OSError, ValueError)):
                    raise LifxNetworkError(f"Failed to open UDP socket: {e}") from e
                raise

    def _endpoint_lost(self, protocol: _UdpProtocol, exc: Exception | None) -> None:
        """Drop references to an endpoint that has died.

        Without this the asyncio transport can be closed while
        ``_transport``/``_protocol`` stay populated: :attr:`is_open` keeps
        returning True, :meth:`open` early-returns "already_open", and
        :meth:`send` calls ``sendto`` on a dead transport, which asyncio logs
        and drops rather than raising. Clearing both references makes
        :attr:`is_open` report the truth and lets :meth:`open` build a genuinely
        new endpoint.

        Args:
            protocol: Protocol reporting the loss.
            exc: Exception that killed the endpoint, if any.
        """
        if protocol is not self._protocol:
            # Stale notification from an endpoint that has already been
            # replaced (close() clears the references before asyncio delivers
            # connection_lost). Resetting here would tear down the live one.
            return

        # The local bind values are deliberately left out: callers use a
        # family-appropriate wildcard on an ephemeral port, so the values name
        # no device. The peer is what identifies whose socket just died.
        _LOGGER.warning(
            self._log(
                method="_endpoint_lost",
                action="endpoint_lost",
                reason=str(exc) if exc is not None else "closed",
            )
        )

        transport, self._transport = self._transport, None
        self._protocol = None
        self._family = None

        if transport is not None:
            try:
                transport.close()
            except OSError as e:  # pragma: no cover - defensive
                _LOGGER.debug(
                    {
                        "class": "UdpTransport",
                        "method": "_endpoint_lost",
                        "action": "close_failed",
                        "reason": str(e),
                    }
                )

    async def send(self, data: bytes, address: SocketAddress) -> None:
        """Send data to a specific address.

        The destination's address family is checked against the socket's
        before the datagram is handed to asyncio. A mismatch is a permanent
        configuration error, but the socket reports it as a ``gaierror``,
        an ``OSError`` subclass that :meth:`_UdpProtocol.error_received`
        deliberately swallows along with every genuine peer error. Without
        this check an unreachable-by-construction address is
        indistinguishable from a sleeping device: the caller waits out the
        full retry schedule and is told only that it timed out. Checking
        first costs one parse and names the actual problem.

        This is a pre-send guard and nothing more. The routing of errors
        that arrive from the network is untouched: EHOSTUNREACH, EHOSTDOWN
        and ENETUNREACH still reach ``error_received`` and still leave the
        endpoint alive.

        Args:
            data: Bytes to send
            address: Tuple of (host, port)

        Raises:
            LifxNetworkError: If the socket is not open, the destination's
                address family does not match the socket's, an IPv6 zone
                identifier cannot be resolved, or the send fails.
        """
        if self._transport is None or self._protocol is None or self._family is None:
            raise LifxNetworkError("Socket not open")

        try:
            send_address = sockaddr_for(address)
        except ValueError as error:
            _LOGGER.debug(
                self._log(
                    method="send",
                    action="invalid_destination",
                    destination_ip=address[0],
                    destination_port=address[1],
                    reason=str(error),
                )
            )
            raise LifxNetworkError(
                f"Invalid destination {address[0]!r}: {error}"
            ) from error

        destination_family = family_for_sockaddr(send_address)
        if destination_family is not self._family:
            _LOGGER.debug(
                self._log(
                    method="send",
                    action="family_mismatch",
                    destination_ip=address[0],
                    destination_port=address[1],
                    destination_family=destination_family.name,
                    socket_family=self._family.name,
                )
            )
            raise LifxNetworkError(
                f"Destination {address[0]} requires {destination_family.name} "
                f"but the socket family is {self._family.name}"
            )

        try:
            self._transport.sendto(data, send_address)
        except OSError as e:
            _LOGGER.debug(
                self._log(
                    method="send",
                    action="failed",
                    destination_ip=address[0],
                    destination_port=address[1],
                    packet_size=len(data),
                    reason=str(e),
                )
            )
            raise LifxNetworkError(f"Failed to send data: {e}") from e

    async def receive(self, timeout: float = 2.0) -> tuple[bytes, SocketAddress]:
        """Receive data from socket with size validation.

        Args:
            timeout: Timeout in seconds

        Returns:
            Tuple of (data, address) where address is (host, port)

        Raises:
            LifxTimeoutError: If no data received within timeout
            LifxNetworkError: If socket is not open or receive fails
            LifxProtocolError: If packet size is invalid
        """
        if self._protocol is None:
            raise LifxNetworkError("Socket not open")

        try:
            data, addr = await asyncio.wait_for(
                self._protocol.queue.get(), timeout=timeout
            )
        except TIMEOUT_ERRORS as e:
            raise LifxTimeoutError(f"No data received within {timeout}s") from e
        except OSError as e:
            _LOGGER.error(self._log(method="receive", action="failed", reason=str(e)))
            raise LifxNetworkError(f"Failed to receive data: {e}") from e

        # Validate packet size
        if len(data) > MAX_PACKET_SIZE:
            _LOGGER.error(
                self._log(
                    method="receive",
                    action="packet_too_large",
                    sender_ip=addr[0],
                    sender_port=addr[1],
                    packet_size=len(data),
                    max_size=MAX_PACKET_SIZE,
                )
            )
            raise LifxProtocolError(
                f"Packet too big: {len(data)} bytes > {MAX_PACKET_SIZE} bytes"
            )

        if len(data) < MIN_PACKET_SIZE:
            _LOGGER.error(
                self._log(
                    method="receive",
                    action="packet_too_small",
                    sender_ip=addr[0],
                    sender_port=addr[1],
                    packet_size=len(data),
                    min_size=MIN_PACKET_SIZE,
                )
            )
            raise LifxProtocolError(
                f"Packet too small: {len(data)} bytes < {MIN_PACKET_SIZE} bytes"
            )

        return data, addr

    def _close_immediately(self) -> None:
        """Synchronously invalidate and close the owned asyncio endpoint."""
        self._state_generation += 1
        transport, self._transport = self._transport, None
        self._protocol = None
        self._family = None

        if transport is not None:
            _LOGGER.debug(
                {
                    "class": "UdpTransport",
                    "method": "close",
                    "action": "closing",
                }
            )
            transport.close()
            _LOGGER.debug(
                {
                    "class": "UdpTransport",
                    "method": "close",
                    "action": "closed",
                }
            )

    async def close(self) -> None:
        """Close the UDP socket."""
        self._close_immediately()

    @property
    def is_open(self) -> bool:
        """Check if socket is open."""
        return (
            self._protocol is not None
            and self._transport is not None
            and self._family is not None
        )
