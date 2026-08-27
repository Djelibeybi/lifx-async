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
        if self._protocol is not None:
            _LOGGER.debug(
                {
                    "class": "MdnsTransport",
                    "method": "open",
                    "action": "already_open",
                }
            )
            return

        sock: socket.socket | None = None

        try:
            loop = asyncio.get_running_loop()

            # Create and configure the socket by hand, so the ephemeral bind
            # below is ours to choose rather than asyncio's.
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
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
            self._socket = sock

            # Create protocol. Shared with UdpTransport, whose bounded queue
            # and drop logging guard against multicast floods.
            protocol = _UdpProtocol()
            self._protocol = protocol

            # Create datagram endpoint using our configured socket
            self._transport, _ = await loop.create_datagram_endpoint(
                lambda: protocol,
                sock=sock,
            )

            _LOGGER.debug(
                {
                    "class": "MdnsTransport",
                    "method": "open",
                    "action": "opened",
                }
            )

        except OSError as e:
            # Two things are stranded by a failure partway through, and the
            # descriptor is only the obvious one. `_socket` and `_protocol`
            # are assigned before the endpoint is awaited, and `is_open` is
            # `_protocol is not None`, so an endpoint failure would otherwise
            # leave the object claiming to be open while the early return at
            # the top of this method refused to build a replacement:
            # descriptor-clean, and permanently unusable. Put the object back
            # to exactly the state close() leaves it in, so a caller's retry
            # loop gets a working transport instead of a phantom.
            #
            # close() is a no-op on an already-closed socket, so this is safe
            # whether or not create_datagram_endpoint took ownership first.
            if sock is not None:
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
            raise LifxNetworkError(f"Failed to open mDNS socket: {e}") from e

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
        if self._transport is not None:
            _LOGGER.debug(
                {
                    "class": "MdnsTransport",
                    "method": "close",
                    "action": "closing",
                }
            )

            self._transport.close()
            self._transport = None
            self._protocol = None
            self._socket = None

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
        return self._protocol is not None
