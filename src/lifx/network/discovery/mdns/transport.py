"""mDNS transport for LIFX service discovery.

An IPv4 UDP socket bound to one route-selected interface and an ephemeral port,
which is what makes every query it sends a legacy unicast query under RFC 6762
section 6.7: responders answer straight back to that port instead of
broadcasting the reply. Queries themselves still go to the well-known mDNS address
(:data:`lifx.const.MDNS_ADDRESS`, 224.0.0.251) on port 5353, so only the
replies are unicast.

Binding 5353 instead would share the port with whatever system mDNS daemon
is already running (mDNSResponder on macOS, Avahi on Linux), which silently
takes the unicast responses and causes devices to be missed. The ephemeral
bind gives this transport a per-call socket queue instead.

The implemented path sends an IPv4 multicast query from an ephemeral source port
and accepts legacy-unicast replies addressed directly to that socket. It
does not join the multicast group and does not receive unsolicited announcements.
It does not authenticate or correlate responders with the outstanding queries.
Because cache-flush semantics do not apply to these replies, the discovery-layer
cache state is scoped to one discovery call.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from asyncio import DatagramTransport
from ipaddress import AddressValueError, IPv4Address

from lifx.const import MDNS_ADDRESS, MDNS_PORT, TIMEOUT_ERRORS
from lifx.exceptions import LifxNetworkError, LifxTimeoutError
from lifx.network.transport import _UdpProtocol

_LOGGER = logging.getLogger(__name__)


def _select_mdns_ipv4_address() -> str:
    """Return the concrete IPv4 source selected for the mDNS multicast route."""
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
        socket.IPPROTO_UDP,
    ) as probe:
        # Connecting a UDP socket sends no packet. It asks the OS routing table
        # which source address would be used for the actual mDNS destination.
        probe.connect((MDNS_ADDRESS, MDNS_PORT))
        selected_address = probe.getsockname()[0]

    if not isinstance(selected_address, str):
        raise OSError("No concrete IPv4 mDNS interface is available")

    try:
        parsed_address = IPv4Address(selected_address)
    except AddressValueError as error:
        raise OSError("No concrete IPv4 mDNS interface is available") from error

    if parsed_address.is_unspecified:
        raise OSError("No concrete IPv4 mDNS interface is available")

    return str(parsed_address)


class MdnsTransport:
    """IPv4 UDP transport for multicast mDNS queries and direct replies.

    Sends to the well-known mDNS address from a socket bound to one concrete
    outbound interface and an ephemeral port. Under RFC 6762 section 6.7 that
    makes each query a legacy unicast query, which a responder answers directly
    to this socket rather than to 5353, so no system mDNS daemon is competing
    for the reply.

    Example:
        >>> async with MdnsTransport() as transport:
        ...     await transport.send(query, (MDNS_ADDRESS, MDNS_PORT))
        ...     data, addr = await transport.receive(timeout=5.0)
    """

    def __init__(self, *, log_failure_details: bool = True) -> None:
        """Initialize mDNS transport.

        Args:
            log_failure_details: Include exception text and destinations in
                low-level logs. The private merged-discovery path disables
                these details because it emits bounded typed failure events.
        """
        self._protocol: _UdpProtocol | None = None
        self._transport: DatagramTransport | None = None
        self._socket: socket.socket | None = None
        self._state_lock = asyncio.Lock()
        self._state_generation = 0
        self._log_failure_details = log_failure_details

    async def __aenter__(self) -> MdnsTransport:
        """Enter async context manager."""
        await self.open()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager."""
        await self.close()

    async def open(self) -> None:
        """Open the mDNS socket.

        Selects the concrete IPv4 interface for the mDNS route, creates a UDP
        socket, sets the multicast TTL to 1 so queries stay on the local link,
        and binds an ephemeral port so responders reply directly to it
        (RFC 6762 section 6.7).

        Raises:
            LifxNetworkError: If socket creation or configuration fails
        """
        generation = self._state_generation
        async with self._state_lock:
            # A close that began after this open call invalidates the attempt,
            # including callers queued behind another opener.
            if generation != self._state_generation:
                return

            if self.is_open:
                _LOGGER.debug(
                    {
                        "class": "MdnsTransport",
                        "method": "open",
                        "action": "already_open",
                    }
                )
                return

            sock: socket.socket | None = None
            datagram_transport: DatagramTransport | None = None

            try:
                loop = asyncio.get_running_loop()
                local_address = _select_mdns_ipv4_address()

                # Create and configure the socket by hand, so the ephemeral bind
                # below is ours to choose rather than asyncio's.
                sock = socket.socket(
                    socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
                )
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

                # Bind only the interface selected for the mDNS route. Port zero
                # retains the RFC 6762 §6.7 legacy-unicast behaviour without
                # exposing the reply listener on every IPv4 interface.
                sock.bind((local_address, 0))
                sock.setsockopt(
                    socket.IPPROTO_IP,
                    socket.IP_MULTICAST_IF,
                    socket.inet_aton(local_address),
                )
                bound_log: dict[str, str | int] = {
                    "class": "MdnsTransport",
                    "method": "open",
                    "action": "bound_to_ephemeral_port",
                }
                if self._log_failure_details:
                    bound_log["port"] = sock.getsockname()[1]
                _LOGGER.debug(bound_log)

                # Set multicast TTL (1 for link-local)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)

                # Make socket non-blocking
                sock.setblocking(False)
                # Create protocol. Shared with UdpTransport, whose bounded queue
                # and drop logging guard against multicast floods.
                protocol = _UdpProtocol()

                # Create datagram endpoint using our configured socket
                datagram_transport, _ = await loop.create_datagram_endpoint(
                    lambda: protocol,
                    sock=sock,
                )

                # close() deliberately does not wait for endpoint creation. If
                # it landed during the await, it wins and this late endpoint is
                # closed without ever becoming observable as open.
                if generation != self._state_generation:
                    datagram_transport.close()
                    return

                self._socket = sock
                self._protocol = protocol
                self._transport = datagram_transport

                _LOGGER.debug(
                    {
                        "class": "MdnsTransport",
                        "method": "open",
                        "action": "opened",
                    }
                )

            except BaseException as e:
                if datagram_transport is not None:
                    datagram_transport.close()
                elif sock is not None:
                    sock.close()
                self._socket = None
                self._protocol = None
                self._transport = None

                failure_log = {
                    "class": "MdnsTransport",
                    "method": "open",
                    "action": "failed",
                    "error_type": type(e).__name__,
                }
                if self._log_failure_details:
                    failure_log["error"] = str(e)
                _LOGGER.debug(failure_log)
                if isinstance(e, OSError):
                    raise LifxNetworkError(f"Failed to open mDNS socket: {e}") from e
                raise

    async def send(self, data: bytes, address: tuple[str, int] | None = None) -> None:
        """Send data to mDNS multicast address.

        Args:
            data: Bytes to send
            address: Target address (defaults to mDNS multicast address)

        Raises:
            LifxNetworkError: If socket is not open or send fails
        """
        if self._transport is None or self._protocol is None:
            raise LifxNetworkError("Socket not open")

        if address is None:
            address = (MDNS_ADDRESS, MDNS_PORT)

        try:
            self._transport.sendto(data, address)
            sent_log: dict[str, object] = {
                "class": "MdnsTransport",
                "method": "send",
                "action": "sent",
                "size": len(data),
            }
            if self._log_failure_details:
                sent_log["destination"] = address
            _LOGGER.debug(sent_log)
        except OSError as e:
            failure_log: dict[str, object] = {
                "class": "MdnsTransport",
                "method": "send",
                "action": "failed",
                "error_type": type(e).__name__,
            }
            if self._log_failure_details:
                failure_log["destination"] = address
                failure_log["error"] = str(e)
            _LOGGER.debug(failure_log)
            raise LifxNetworkError(f"Failed to send mDNS data: {e}") from e

    async def receive(self, timeout: float = 5.0) -> tuple[bytes, tuple[str, int]]:
        """Receive data from socket.

        Args:
            timeout: Timeout in seconds

        Returns:
            Tuple of (data, address) where address is (host, port)

        Raises:
            LifxTimeoutError: If no data received within timeout
            LifxNetworkError: If socket is not open or receive fails
        """
        if self._protocol is None:
            raise LifxNetworkError("Socket not open")

        try:
            data, addr = await asyncio.wait_for(
                self._protocol.queue.get(), timeout=timeout
            )
            # MdnsTransport always opens an AF_INET endpoint. Narrow the
            # shared UDP protocol's dual-family sockaddr type at this IPv4-only
            # boundary instead of leaking an impossible four-tuple downstream.
            return data, (addr[0], addr[1])
        except TIMEOUT_ERRORS as e:
            raise LifxTimeoutError(f"No mDNS data received within {timeout}s") from e
        except OSError as e:
            failure_log = {
                "class": "MdnsTransport",
                "method": "receive",
                "action": "failed",
                "error_type": type(e).__name__,
            }
            if self._log_failure_details:
                failure_log["error"] = str(e)
            _LOGGER.debug(failure_log)
            raise LifxNetworkError(f"Failed to receive mDNS data: {e}") from e

    async def close(self) -> None:
        """Close the mDNS socket."""
        self._state_generation += 1
        transport, self._transport = self._transport, None
        sock, self._socket = self._socket, None
        self._protocol = None

        if transport is not None or sock is not None:
            _LOGGER.debug(
                {
                    "class": "MdnsTransport",
                    "method": "close",
                    "action": "closing",
                }
            )

            if transport is not None:
                transport.close()
            else:
                assert sock is not None
                sock.close()

            _LOGGER.debug(
                {
                    "class": "MdnsTransport",
                    "method": "close",
                    "action": "closed",
                }
            )

    @property
    def is_open(self) -> bool:
        """Check if socket is open."""
        return (
            self._socket is not None
            and self._protocol is not None
            and self._transport is not None
        )
