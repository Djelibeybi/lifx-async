"""UDP transport layer for LIFX communication."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from lifx.const import DEFAULT_IP_ADDRESS, MAX_PACKET_SIZE, MIN_PACKET_SIZE
from lifx.exceptions import LifxNetworkError
from lifx.exceptions import LifxTimeoutError as LifxTimeoutError

if TYPE_CHECKING:
    from asyncio import DatagramTransport

_LOGGER = logging.getLogger(__name__)


class _UdpProtocol(asyncio.DatagramProtocol):
    """Internal DatagramProtocol implementation for receiving UDP packets."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple[bytes, tuple[str, int]]] = asyncio.Queue()
        self.transport: DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Called when connection is established."""
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Called when a datagram is received."""
        self.queue.put_nowait((data, addr))

    def error_received(self, exc: Exception) -> None:
        """Called when an error is received."""
        # Log error but don't stop receiving
        pass

    def connection_lost(self, exc: Exception | None) -> None:
        """Called when connection is lost."""
        self.transport = None


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
    ) -> None:
        """Initialize UDP transport.

        Args:
            port: Local port to bind to (0 for automatic assignment)
            broadcast: Enable broadcast mode for device discovery
        """
        self._ip_address = ip_address
        self._port = port
        self._broadcast = broadcast
        self._protocol: _UdpProtocol | None = None
        self._transport: DatagramTransport | None = None

    async def __aenter__(self) -> UdpTransport:
        """Enter async context manager."""
        await self.open()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager."""
        await self.close()

    async def open(self) -> None:
        """Open the UDP socket."""
        if self._protocol is not None:
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

        try:
            import socket as stdlib_socket

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
            protocol = _UdpProtocol()
            self._protocol = protocol

            # Create datagram endpoint
            self._transport, _ = await loop.create_datagram_endpoint(
                lambda: protocol,
                local_addr=(self._ip_address, self._port),
                reuse_port=bool(hasattr(stdlib_socket, "SO_REUSEPORT")),
                family=stdlib_socket.AF_INET,
            )

            # Get actual port assigned
            actual_port = self._transport.get_extra_info("sockname")[1]
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
                sock = self._transport.get_extra_info("socket")
                if sock:
                    sock.setsockopt(
                        stdlib_socket.SOL_SOCKET,
                        stdlib_socket.SO_BROADCAST,
                        1,
                    )
                    _LOGGER.debug(
                        {
                            "class": "UdpTransport",
                            "method": "open",
                            "action": "broadcast_enabled",
                        }
                    )

        except OSError as e:
            _LOGGER.debug(
                {
                    "class": "UdpTransport",
                    "method": "open",
                    "action": "failed",
                    "ip_address": self._ip_address,
                    "port": self._port,
                    "reason": str(e),
                }
            )
            raise LifxNetworkError(f"Failed to open UDP socket: {e}") from e

    async def send(self, data: bytes, address: tuple[str, int]) -> None:
        """Send data to a specific address.

        Args:
            data: Bytes to send
            address: Tuple of (host, port)

        Raises:
            NetworkError: If socket is not open or send fails
        """
        if self._transport is None or self._protocol is None:
            raise LifxNetworkError("Socket not open")

        try:
            self._transport.sendto(data, address)
        except OSError as e:
            _LOGGER.debug(
                {
                    "class": "UdpTransport",
                    "method": "send",
                    "action": "failed",
                    "destination": address,
                    "packet_size": len(data),
                    "reason": str(e),
                }
            )
            raise LifxNetworkError(f"Failed to send data: {e}") from e

    async def receive(self, timeout: float = 2.0) -> tuple[bytes, tuple[str, int]]:
        """Receive data from socket with size validation.

        Args:
            timeout: Timeout in seconds

        Returns:
            Tuple of (data, address) where address is (host, port)

        Raises:
            LifxTimeoutError: If no data received within timeout
            NetworkError: If socket is not open or receive fails
            ProtocolError: If packet size is invalid
        """
        if self._protocol is None:
            raise LifxNetworkError("Socket not open")

        try:
            async with asyncio.timeout(timeout):
                data, addr = await self._protocol.queue.get()

                # Validate packet size
                if len(data) > MAX_PACKET_SIZE:
                    from lifx.exceptions import LifxProtocolError

                    _LOGGER.error(
                        {
                            "class": "UdpTransport",
                            "method": "receive",
                            "action": "packet_too_large",
                            "packet_size": len(data),
                            "max_size": MAX_PACKET_SIZE,
                        }
                    )
                    raise LifxProtocolError(
                        f"Packet too big: {len(data)} bytes > {MAX_PACKET_SIZE} bytes"
                    )

                if len(data) < MIN_PACKET_SIZE:
                    from lifx.exceptions import LifxProtocolError

                    _LOGGER.error(
                        {
                            "class": "UdpTransport",
                            "method": "receive",
                            "action": "packet_too_small",
                            "packet_size": len(data),
                            "min_size": MIN_PACKET_SIZE,
                        }
                    )
                    raise LifxProtocolError(
                        f"Packet too small: {len(data)} bytes < {MIN_PACKET_SIZE} bytes"
                    )

                return data, addr
        except TimeoutError as e:
            raise LifxTimeoutError(f"No data received within {timeout}s") from e
        except OSError as e:
            _LOGGER.error(
                {
                    "class": "UdpTransport",
                    "method": "receive",
                    "action": "failed",
                    "reason": str(e),
                }
            )
            raise LifxNetworkError(f"Failed to receive data: {e}") from e

    async def receive_many(
        self, timeout: float = 5.0, max_packets: int | None = None
    ) -> list[tuple[bytes, tuple[str, int]]]:
        """Receive multiple packets within timeout period.

        Args:
            timeout: Total timeout in seconds
            max_packets: Maximum number of packets to receive (None for unlimited)

        Returns:
            List of (data, address) tuples

        Raises:
            NetworkError: If socket is not open
        """
        if self._protocol is None:
            raise LifxNetworkError("Socket not open")

        packets: list[tuple[bytes, tuple[str, int]]] = []

        try:
            async with asyncio.timeout(timeout):
                while True:
                    if max_packets is not None and len(packets) >= max_packets:
                        break

                    try:
                        data, addr = await self._protocol.queue.get()

                        # Validate packet size
                        if len(data) > MAX_PACKET_SIZE:
                            # Drop oversized packet to prevent memory exhaustion DoS
                            continue

                        if len(data) < MIN_PACKET_SIZE:
                            # Drop undersized packet (header is 36 bytes)
                            continue

                        packets.append((data, addr))
                    except OSError:
                        # Ignore individual receive errors
                        break

        except TimeoutError:
            # Timeout is expected - return what we collected
            pass

        return packets

    async def close(self) -> None:
        """Close the UDP socket."""
        if self._transport is not None:
            _LOGGER.debug(
                {
                    "class": "UdpTransport",
                    "method": "close",
                    "action": "closing",
                }
            )
            self._transport.close()
            self._transport = None
            self._protocol = None
            _LOGGER.debug(
                {
                    "class": "UdpTransport",
                    "method": "close",
                    "action": "closed",
                }
            )

    @property
    def is_open(self) -> bool:
        """Check if socket is open."""
        return self._protocol is not None
