"""mDNS transport for LIFX service discovery.

A UDP socket bound to an ephemeral port, which is what makes every query it
sends a legacy unicast query under RFC 6762 section 6.7: responders answer
straight back to that port instead of broadcasting the reply. Queries
themselves still go to the well-known mDNS address
(:data:`lifx.const.MDNS_ADDRESS`, 224.0.0.251) on port 5353, so only the
replies are unicast.

Binding 5353 instead would share the port with whatever system mDNS daemon
is already running (mDNSResponder on macOS, Avahi on Linux), which silently
takes the unicast responses and causes devices to be missed. The ephemeral
bind is what keeps this transport's answers its own.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from asyncio import DatagramTransport

from lifx.const import MDNS_ADDRESS, MDNS_PORT, TIMEOUT_ERRORS
from lifx.exceptions import LifxNetworkError, LifxTimeoutError
from lifx.network.transport import _UdpProtocol

_LOGGER = logging.getLogger(__name__)


class MdnsTransport:
    """UDP transport for mDNS queries and their unicast replies.

    Sends to the well-known mDNS address from a socket bound to an ephemeral
    port. Under RFC 6762 section 6.7 that makes each query a legacy unicast
    query, which a responder answers directly to this socket rather than to
    5353, so no system mDNS daemon is competing for the reply.

    Example:
        >>> async with MdnsTransport() as transport:
        ...     await transport.send(query, (MDNS_ADDRESS, MDNS_PORT))
        ...     data, addr = await transport.receive(timeout=5.0)
    """

    def __init__(self) -> None:
        """Initialize mDNS transport."""
        self._protocol: _UdpProtocol | None = None
        self._transport: DatagramTransport | None = None
        self._socket: socket.socket | None = None
        self._state_lock = asyncio.Lock()
        self._state_generation = 0

    async def __aenter__(self) -> MdnsTransport:
        """Enter async context manager."""
        await self.open()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager."""
        await self.close()

    async def open(self) -> None:
        """Open the mDNS socket.

        Creates a UDP socket, sets the multicast TTL to 1 so queries stay on
        the local link, and binds an ephemeral port so that responders reply
        directly to it (RFC 6762 section 6.7).

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

                # Create and configure the socket by hand, so the ephemeral bind
                # below is ours to choose rather than asyncio's.
                sock = socket.socket(
                    socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
                )
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

                # Bind to an ephemeral port: per RFC 6762 §6.7, queries sent from
                # a port other than 5353 are "legacy unicast" queries and
                # responders reply directly to our port. Binding to 5353 instead
                # would share the port (via SO_REUSEPORT) with any system mDNS
                # daemon (mDNSResponder, Avahi), which silently steals unicast
                # responses and causes devices to be missed.
                sock.bind(("", 0))
                _LOGGER.debug(
                    {
                        "class": "MdnsTransport",
                        "method": "open",
                        "action": "bound_to_ephemeral_port",
                        "port": sock.getsockname()[1],
                    }
                )

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

                _LOGGER.debug(
                    {
                        "class": "MdnsTransport",
                        "method": "open",
                        "action": "failed",
                        "error": str(e),
                    }
                )
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
            _LOGGER.debug(
                {
                    "class": "MdnsTransport",
                    "method": "send",
                    "action": "sent",
                    "size": len(data),
                    "destination": address,
                }
            )
        except OSError as e:
            _LOGGER.debug(
                {
                    "class": "MdnsTransport",
                    "method": "send",
                    "action": "failed",
                    "destination": address,
                    "error": str(e),
                }
            )
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
            return data, addr
        except TIMEOUT_ERRORS as e:
            raise LifxTimeoutError(f"No mDNS data received within {timeout}s") from e
        except OSError as e:
            _LOGGER.debug(
                {
                    "class": "MdnsTransport",
                    "method": "receive",
                    "action": "failed",
                    "error": str(e),
                }
            )
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
