"""mDNS transport for multicast UDP communication.

This module provides a UDP transport specifically for mDNS queries,
with multicast group joining and appropriate socket configuration.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
from asyncio import DatagramTransport
from typing import TYPE_CHECKING

from lifx.const import MDNS_ADDRESS, MDNS_PORT
from lifx.exceptions import LifxNetworkError, LifxTimeoutError

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class _MdnsProtocol(asyncio.DatagramProtocol):
    """Asyncio protocol for mDNS UDP communication."""

    def __init__(self) -> None:
        """Initialize the protocol."""
        self.queue: asyncio.Queue[tuple[bytes, tuple[str, int]]] = asyncio.Queue()
        self._transport: DatagramTransport | None = None

    def connection_made(self, transport: DatagramTransport) -> None:  # type: ignore[override]
        """Called when connection is established."""
        self._transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Called when a datagram is received."""
        self.queue.put_nowait((data, addr))

    def error_received(self, exc: Exception) -> None:
        """Called when an error is received."""
        _LOGGER.debug(
            {
                "class": "_MdnsProtocol",
                "method": "error_received",
                "action": "error",
                "error": str(exc),
            }
        )

    def connection_lost(self, exc: Exception | None) -> None:
        """Called when connection is lost."""
        _LOGGER.debug(
            {
                "class": "_MdnsProtocol",
                "method": "connection_lost",
                "action": "lost",
                "error": str(exc) if exc else None,
            }
        )


class MdnsTransport:
    """UDP transport for mDNS multicast communication.

    This transport is specifically designed for mDNS queries and responses,
    with support for multicast group membership and appropriate socket options.

    Example:
        >>> async with MdnsTransport() as transport:
        ...     await transport.send(query, (MDNS_ADDRESS, MDNS_PORT))
        ...     data, addr = await transport.receive(timeout=5.0)
    """

    def __init__(self) -> None:
        """Initialize mDNS transport."""
        self._protocol: _MdnsProtocol | None = None
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
        """Open the mDNS socket with multicast configuration.

        Creates a UDP socket, configures it for mDNS multicast,
        and joins the mDNS multicast group.

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

        try:
            loop = asyncio.get_running_loop()

            # Create and configure socket manually for multicast
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Try to set SO_REUSEPORT if available (Linux/macOS)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass

            # Bind to mDNS port (or ephemeral if busy)
            try:
                sock.bind(("", MDNS_PORT))
                _LOGGER.debug(
                    {
                        "class": "MdnsTransport",
                        "method": "open",
                        "action": "bound_to_mdns_port",
                        "port": MDNS_PORT,
                    }
                )
            except OSError as e:
                _LOGGER.debug(
                    {
                        "class": "MdnsTransport",
                        "method": "open",
                        "action": "mdns_port_busy",
                        "error": str(e),
                    }
                )
                # Fall back to ephemeral port
                sock.bind(("", 0))
                _LOGGER.debug(
                    {
                        "class": "MdnsTransport",
                        "method": "open",
                        "action": "bound_to_ephemeral_port",
                        "port": sock.getsockname()[1],
                    }
                )

            # Join mDNS multicast group
            mreq = struct.pack("4sl", socket.inet_aton(MDNS_ADDRESS), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            _LOGGER.debug(
                {
                    "class": "MdnsTransport",
                    "method": "open",
                    "action": "joined_multicast_group",
                    "group": MDNS_ADDRESS,
                }
            )

            # Set multicast TTL (1 for link-local)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)

            # Make socket non-blocking
            sock.setblocking(False)
            self._socket = sock

            # Create protocol
            protocol = _MdnsProtocol()
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
            async with asyncio.timeout(timeout):
                data, addr = await self._protocol.queue.get()
                return data, addr
        except TimeoutError as e:
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

            # Leave multicast group
            if self._socket is not None:
                try:
                    mreq = struct.pack(
                        "4sl", socket.inet_aton(MDNS_ADDRESS), socket.INADDR_ANY
                    )
                    self._socket.setsockopt(
                        socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq
                    )
                except OSError:
                    pass  # Ignore errors when leaving group

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
