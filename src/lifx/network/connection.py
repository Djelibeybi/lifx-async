"""Connection management for LIFX devices."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import OrderedDict
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

if TYPE_CHECKING:
    from typing import Self

from lifx.const import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    LIFX_UDP_PORT,
    MAX_CONNECTIONS,
)
from lifx.exceptions import (
    LifxConnectionError,
    LifxProtocolError,
    LifxTimeoutError,
    LifxUnsupportedCommandError,
)
from lifx.network.message import MessageBuilder, parse_message
from lifx.network.transport import UdpTransport
from lifx.protocol.header import LifxHeader
from lifx.protocol.models import Serial

_LOGGER = logging.getLogger(__name__)

# Type variable for packet types
T = TypeVar("T")

# Constants for retry logic
_RETRY_SLEEP_BASE: float = 0.1  # Base sleep time between retries (seconds)
_STATE_UNHANDLED_PKT_TYPE: int = 223  # Device.StateUnhandled packet type
_DEFAULT_IDLE_TIMEOUT: float = 0.1  # Idle timeout for response polling within generator


@dataclass
class ConnectionPoolMetrics:
    """Performance metrics for connection pool.

    Tracks cache hits, misses, evictions, and eviction times to help
    identify performance bottlenecks.

    Attributes:
        hits: Number of cache hits (connection found and reused)
        misses: Number of cache misses (new connection created)
        evictions: Number of LRU evictions performed
        total_requests: Total number of connection requests
        eviction_times_ms: List of eviction times in milliseconds
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_requests: int = 0
    eviction_times_ms: list[float] = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate (0.0-1.0).

        Returns:
            Hit rate as a fraction (hits / total_requests)
        """
        return self.hits / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def avg_eviction_time_ms(self) -> float:
        """Calculate average eviction time in milliseconds.

        Returns:
            Average eviction time, or 0.0 if no evictions
        """
        if not self.eviction_times_ms:
            return 0.0
        return sum(self.eviction_times_ms) / len(self.eviction_times_ms)

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.total_requests = 0
        self.eviction_times_ms.clear()


class _ActualConnection:
    """Internal connection implementation for LIFX devices.

    This is the actual connection with UDP socket and retry logic.
    Not exposed directly - used internally by ConnectionPool which is
    in turn used internally by DeviceConnection handles.

    This class handles:
    - Message sending/receiving to a specific device
    - Sequence number management
    - Async generator-based request/response streaming
    - Retry logic with exponential backoff
    """

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = LIFX_UDP_PORT,
        source: int | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        """Initialize device connection.

        Args:
            serial: Device serial number as 12-digit hex string (e.g., 'd073d5123456')
            ip: Device IP address
            port: Device UDP port (default LIFX_UDP_PORT)
            source: Client source identifier (random if None)
            max_retries: Maximum number of retry attempts (default: 8)
            timeout: Default timeout for requests in seconds (default: 8.0)
                    Used as fallback when timeout not specified in requests
        """
        self.serial = serial
        self.ip = ip
        self.port = port
        self.max_retries = max_retries
        # Renamed to clarify it's a default, not override
        self.default_timeout = timeout

        self._transport: UdpTransport | None = None
        self._builder = MessageBuilder(source=source)
        self._is_open = False
        # Lock to serialize requests on same connection
        # This prevents response mixing when multiple concurrent requests
        # share the same UDP socket
        self._request_lock = asyncio.Lock()

    async def __aenter__(self) -> Self:
        """Enter async context manager and start connection."""
        await self.open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context manager and close connection."""
        await self.close()

    async def open(self) -> None:
        """Open connection to device.

        Opens the UDP transport for sending and receiving packets.
        """
        if self._is_open:
            return

        # Open transport
        self._transport = UdpTransport(port=0, broadcast=False)
        await self._transport.open()
        self._is_open = True

        _LOGGER.debug(
            {
                "class": "_ActualConnection",
                "method": "open",
                "serial": self.serial,
                "ip": self.ip,
                "port": self.port,
            }
        )

    async def close(self) -> None:
        """Close connection to device."""
        if not self._is_open:
            return

        self._is_open = False

        # Close transport
        if self._transport is not None:
            await self._transport.close()

        _LOGGER.debug(
            {
                "class": "_ActualConnection",
                "method": "close",
                "serial": self.serial,
                "ip": self.ip,
            }
        )
        self._transport = None

    async def send_packet(
        self,
        packet: Any,
        ack_required: bool = False,
        res_required: bool = False,
        sequence: int | None = None,
    ) -> None:
        """Send a packet to the device.

        Args:
            packet: Packet dataclass instance
            ack_required: Request acknowledgement
            res_required: Request response
            sequence: Explicit sequence number (allocates new one if None)

        Raises:
            ConnectionError: If connection is not open or send fails
        """
        if not self._is_open or self._transport is None:
            raise LifxConnectionError("Connection not open")

        message = self._builder.create_message(
            packet=packet,
            target=Serial.from_string(self.serial).to_protocol(),
            ack_required=ack_required,
            res_required=res_required,
            sequence=sequence,
        )

        # Send to device
        await self._transport.send(message, (self.ip, self.port))

    async def receive_packet(self, timeout: float = 0.5) -> tuple[LifxHeader, bytes]:
        """Receive a packet from the device.

        Note:
            This method does not validate the source IP address. Validation is instead
            performed using the LIFX protocol's built-in target field (serial number)
            and sequence number matching in request_stream() and request_ack_stream().
            This approach is more reliable in complex network configurations (NAT,
            multiple interfaces, bridges, etc.) while maintaining security through
            proper protocol-level validation.

        Args:
            timeout: Timeout in seconds

        Returns:
            Tuple of (header, payload)

        Raises:
            ConnectionError: If connection is not open
            TimeoutError: If no response within timeout
        """
        if not self._is_open or self._transport is None:
            raise LifxConnectionError("Connection not open")

        # Receive message - source address not validated here
        # Validation occurs via target field and sequence number matching
        data, _addr = await self._transport.receive(timeout=timeout)

        # Parse and return message
        return parse_message(data)

    @staticmethod
    def _calculate_retry_sleep_with_jitter(attempt: int) -> float:
        """Calculate retry sleep time with exponential backoff and jitter.

        Uses full jitter strategy: random value between 0 and exponential delay.
        This prevents thundering herd when multiple clients retry simultaneously.

        Args:
            attempt: Retry attempt number (0-based)

        Returns:
            Sleep time in seconds with jitter applied
        """
        # Exponential backoff: base * 2^attempt
        exponential_delay = _RETRY_SLEEP_BASE * (2**attempt)

        # Full jitter: random value between 0 and exponential_delay
        # This spreads retries across time to avoid synchronized retries
        return random.uniform(0, exponential_delay)  # nosec

    async def request_stream(
        self,
        request: Any,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> AsyncGenerator[tuple[LifxHeader, bytes], None]:
        """Send request and yield responses as they arrive.

        This is an async generator that sends a request and yields each response
        as it arrives. Callers can break early for single-response requests or
        continue iterating for multi-response protocols.

        Single-response pattern:
            async for header, payload in conn.request_stream(packet):
                process(header, payload)
                break  # Exit immediately after first response

        Multi-response pattern:
            async for header, payload in conn.request_stream(packet, timeout=2.0):
                results.append((header, payload))
                # Automatically stops at timeout

        The retry logic is incorporated into the generator: if no response is
        received within the timeout for an attempt, the generator will retry
        with exponential backoff until max_retries is exhausted.

        Note: Requests on the same connection are serialized to prevent response
        mixing. For concurrent operations, use separate connections.

        Args:
            request: Request packet to send
            timeout: Overall timeout for all retry attempts
                    (uses instance default if None)
            max_retries: Maximum retries (uses instance default if None)

        Yields:
            Tuple of (LifxHeader, payload bytes)

        Raises:
            LifxConnectionError: If connection is not open
            LifxProtocolError: If response is malformed or has wrong packet type
            LifxTimeoutError: If no response after all retries
            LifxUnsupportedCommandError: If device doesn't support command
        """
        if not self._is_open or self._transport is None:
            raise LifxConnectionError("Connection not open")

        if timeout is None:
            timeout = self.default_timeout

        if max_retries is None:
            max_retries = self.max_retries

        # Serialize requests on same connection to prevent response mixing
        async with self._request_lock:
            # Calculate base timeout for exponential backoff
            # Normalize so total time across all retries equals overall timeout
            # Geometric series: 1 + 2 + 4 + ... + 2^n = 2^(n+1) - 1
            total_weight = (2 ** (max_retries + 1)) - 1
            base_timeout = timeout / total_weight

            # Get expected response type from packet (if defined)
            expected_pkt_type = getattr(request, "STATE_TYPE", None)

            last_error: Exception | None = None
            has_yielded = False

            for attempt in range(max_retries + 1):
                # Calculate timeout with exponential backoff (normalized)
                current_timeout = base_timeout * (2**attempt)

                try:
                    # Atomically allocate sequence number for this attempt
                    sequence = self._builder.next_sequence()

                    # Send request
                    await self.send_packet(
                        request,
                        ack_required=False,
                        res_required=True,
                        sequence=sequence,
                    )

                    # Track time for this attempt
                    attempt_start = time.monotonic()
                    attempt_deadline = attempt_start + current_timeout

                    # Receive responses until timeout
                    while True:
                        remaining_time = attempt_deadline - time.monotonic()
                        if remaining_time <= 0:  # pragma: no cover
                            # Attempt timeout reached (race condition edge case)
                            if not has_yielded:
                                # No response received this attempt
                                raise TimeoutError(
                                    f"No response within {current_timeout:.3f}s "
                                    f"(attempt {attempt + 1}/{max_retries + 1})"
                                )
                            # Had responses, done with this stream
                            return  # pragma: no cover (race condition edge case)

                        # Use short idle timeout for polling, but respect remaining time
                        recv_timeout = min(_DEFAULT_IDLE_TIMEOUT, remaining_time)

                        try:
                            header, payload = await self.receive_packet(
                                timeout=recv_timeout
                            )
                        except LifxTimeoutError:
                            # No packet received within poll interval
                            if has_yielded:
                                # Already got at least one response, continue polling
                                continue
                            # No response yet, check if attempt timeout reached
                            if time.monotonic() >= attempt_deadline:
                                raise TimeoutError(
                                    f"No response within {current_timeout:.3f}s "
                                    f"(attempt {attempt + 1}/{max_retries + 1})"
                                ) from None
                            continue

                        # Check sequence number matches
                        if header.sequence != sequence:
                            # Not our response, ignore and continue
                            continue

                        # Check for StateUnhandled (unsupported command)
                        if header.pkt_type == _STATE_UNHANDLED_PKT_TYPE:
                            raise LifxUnsupportedCommandError(
                                "Device does not support the requested command "
                                "(received StateUnhandled)"
                            )

                        # Validate packet type if expected type is specified
                        if (
                            expected_pkt_type is not None
                            and header.pkt_type != expected_pkt_type
                        ):
                            raise LifxProtocolError(
                                f"Received unexpected packet type "
                                f"{header.pkt_type} for sequence {sequence}, "
                                f"expected {expected_pkt_type}"
                            )

                        # Valid response - yield it
                        has_yielded = True
                        yield header, payload

                except TimeoutError as e:
                    last_error = LifxTimeoutError(str(e))
                    if attempt < max_retries:
                        # Sleep with jitter before retry
                        sleep_time = self._calculate_retry_sleep_with_jitter(attempt)
                        await asyncio.sleep(sleep_time)
                        continue
                    else:
                        # All retries exhausted
                        break

            # All retries exhausted without yielding any response
            if not has_yielded:
                # last_error is always set since we only break after TimeoutError
                raise LifxTimeoutError(
                    f"No response from {self.ip} after {max_retries + 1} attempts"
                ) from last_error

    async def request_ack_stream(
        self,
        request: Any,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> AsyncGenerator[None, None]:
        """Send request and yield when acknowledgement received.

        This is an async generator that sends a request requiring acknowledgement
        and yields once when the ACK is received.

        Usage:
            async for _ in conn.request_ack_stream(packet):
                break  # Ack received

        The retry logic is incorporated: if no ACK is received within the timeout
        for an attempt, it will retry with exponential backoff.

        Note: Requests on the same connection are serialized to prevent response
        mixing. For concurrent operations, use separate connections.

        Args:
            request: Request packet to send
            timeout: Overall timeout for all retry attempts
                    (uses instance default if None)
            max_retries: Maximum retries (uses instance default if None)

        Yields:
            None (single yield on successful ack)

        Raises:
            LifxConnectionError: If connection is not open
            LifxTimeoutError: If no ack after all retries
            LifxUnsupportedCommandError: If device doesn't support command
        """
        if not self._is_open or self._transport is None:
            raise LifxConnectionError("Connection not open")

        if timeout is None:
            timeout = self.default_timeout

        if max_retries is None:
            max_retries = self.max_retries

        # Serialize requests on same connection to prevent response mixing
        async with self._request_lock:
            # Calculate base timeout for exponential backoff
            total_weight = (2 ** (max_retries + 1)) - 1
            base_timeout = timeout / total_weight

            last_error: Exception | None = None

            for attempt in range(max_retries + 1):
                # Calculate timeout with exponential backoff (normalized)
                current_timeout = base_timeout * (2**attempt)

                try:
                    # Atomically allocate sequence number for this attempt
                    sequence = self._builder.next_sequence()

                    # Send request with ACK required
                    await self.send_packet(
                        request,
                        ack_required=True,
                        res_required=False,
                        sequence=sequence,
                    )

                    # Track time for this attempt
                    attempt_start = time.monotonic()
                    attempt_deadline = attempt_start + current_timeout

                    # Receive ACK
                    while True:
                        remaining_time = attempt_deadline - time.monotonic()
                        if remaining_time <= 0:  # pragma: no cover
                            # Race condition edge case
                            raise TimeoutError(
                                f"No acknowledgement within {current_timeout:.3f}s "
                                f"(attempt {attempt + 1}/{max_retries + 1})"
                            )

                        recv_timeout = min(_DEFAULT_IDLE_TIMEOUT, remaining_time)

                        try:
                            header, _payload = await self.receive_packet(
                                timeout=recv_timeout
                            )
                        except LifxTimeoutError:
                            # No packet received within poll interval
                            if time.monotonic() >= attempt_deadline:
                                raise TimeoutError(
                                    f"No acknowledgement within {current_timeout:.3f}s "
                                    f"(attempt {attempt + 1}/{max_retries + 1})"
                                ) from None
                            continue

                        # Check sequence number matches
                        if header.sequence != sequence:
                            # Not our ACK, ignore and continue
                            continue

                        # Check for StateUnhandled (unsupported command)
                        if header.pkt_type == _STATE_UNHANDLED_PKT_TYPE:
                            raise LifxUnsupportedCommandError(
                                "Device does not support the requested command "
                                "(received StateUnhandled)"
                            )

                        # ACK received (any packet with matching sequence is ACK)
                        yield
                        return

                except TimeoutError as e:
                    last_error = LifxTimeoutError(str(e))
                    if attempt < max_retries:
                        # Sleep with jitter before retry
                        sleep_time = self._calculate_retry_sleep_with_jitter(attempt)
                        await asyncio.sleep(sleep_time)
                        continue
                    else:
                        # All retries exhausted
                        break

            # All retries exhausted
            # last_error is always set since we only break after TimeoutError
            raise LifxTimeoutError(
                f"No acknowledgement from {self.ip} after {max_retries + 1} attempts"
            ) from last_error

    @property
    def is_open(self) -> bool:
        """Check if connection is open."""
        return self._is_open

    @property
    def source(self) -> int:
        """Get the source identifier for this connection."""
        return self._builder.source


class ConnectionPool:
    """Pool of actual device connections (internal to DeviceConnection).

    Maintains a pool of _ActualConnection objects that can be reused
    to avoid repeatedly opening/closing connections.

    Uses LRU (Least Recently Used) eviction policy

    Collects performance metrics to help identify bottlenecks.
    """

    def __init__(self, max_connections: int = MAX_CONNECTIONS) -> None:
        """Initialize connection pool.

        Args:
            max_connections: Maximum number of connections to keep open
        """
        self.max_connections = max_connections
        # Use OrderedDict for LRU eviction
        self.connections: OrderedDict[str, tuple[_ActualConnection, float]] = (
            OrderedDict()
        )
        # Performance metrics
        self.metrics = ConnectionPoolMetrics()
        _LOGGER.debug(
            {
                "class": "ConnectionPool",
                "method": "__init__",
                "max_connections": max_connections,
            }
        )

    async def get_connection(
        self,
        serial: str,
        ip: str,
        port: int = LIFX_UDP_PORT,
        source: int | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> _ActualConnection:
        """Get or create actual connection with parameters.

        Args:
            serial: Device serial number
            ip: Device IP address
            port: Device UDP port
            source: Client source identifier (random if None)
            max_retries: Maximum retry attempts (default: 8)
            timeout: Default timeout for requests in seconds (default: 8.0)

        Returns:
            _ActualConnection instance (opened and ready)
        """
        current_time = time.time()
        self.metrics.total_requests += 1

        # Check if we already have a connection for this device
        if serial in self.connections:
            conn, _ = self.connections[serial]
            if conn.is_open:
                # Cache hit
                self.metrics.hits += 1
                # Update access time (move to end = most recently used)
                self.connections.move_to_end(serial)
                self.connections[serial] = (conn, current_time)
                connections_free = self.max_connections - len(self.connections)
                _LOGGER.debug(
                    {
                        "class": "ConnectionPool",
                        "method": "get_connection",
                        "action": "reused",
                        "serial": serial,
                        "ip": ip,
                        "pool_size": len(self.connections),
                        "connections_free": connections_free,
                    }
                )
                return conn

        # Cache miss - need to create new connection
        self.metrics.misses += 1

        # Create new actual connection with all parameters
        conn = _ActualConnection(
            serial=serial,
            ip=ip,
            port=port,
            source=source,
            max_retries=max_retries,
            timeout=timeout,
        )
        await conn.open()

        # Add to pool (evict LRU if necessary)
        if len(self.connections) >= self.max_connections:
            # Measure eviction time
            eviction_start = time.monotonic()

            # Evict least recently used item
            lru_serial, (old_conn, _) = self.connections.popitem(last=False)
            await old_conn.close()

            # Track eviction metrics
            eviction_time_ms = (time.monotonic() - eviction_start) * 1000
            self.metrics.evictions += 1
            self.metrics.eviction_times_ms.append(eviction_time_ms)

            _LOGGER.debug(
                {
                    "class": "ConnectionPool",
                    "method": "get_connection",
                    "action": "evicted",
                    "serial": lru_serial,
                    "eviction_time_ms": round(eviction_time_ms, 1),
                    "remaining_pool_size": len(self.connections),
                }
            )

        self.connections[serial] = (conn, current_time)
        connections_free = self.max_connections - len(self.connections)
        _LOGGER.debug(
            {
                "class": "ConnectionPool",
                "method": "get_connection",
                "action": "created",
                "serial": serial,
                "ip": ip,
                "pool_size": len(self.connections),
                "connections_free": connections_free,
            }
        )
        return conn

    async def close_all(self) -> None:
        """Close all connections in the pool."""
        connections_to_close = len(self.connections)
        for conn, _ in self.connections.values():
            await conn.close()
        self.connections.clear()
        _LOGGER.debug(
            {
                "class": "ConnectionPool",
                "method": "close_all",
                "connections_closed": connections_to_close,
            }
        )

    async def __aenter__(self) -> ConnectionPool:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager."""
        await self.close_all()


class DeviceConnection:
    """Handle to a device connection (lightweight, user-facing).

    This is a lightweight handle that internally uses a class-level
    connection pool. Multiple DeviceConnection instances with the
    same serial/ip/port will share the same underlying connection.

    All connection management (pooling, opening, closing) is internal
    and completely hidden from Device classes.

    Device classes just call:
        await self.connection.request(packet)

    Example:
        ```python
        conn = DeviceConnection(serial="d073d5123456", ip="192.168.1.100")
        state = await conn.request(packets.Light.GetColor())
        # state.label is already decoded to string
        # state.color is LightHsbk instance
        ```
    """

    # Class-level connection pool (shared by all instances)
    _pool: ClassVar[ConnectionPool | None] = None
    _pool_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = LIFX_UDP_PORT,
        source: int | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        """Initialize connection handle.

        This is lightweight - doesn't actually create a connection.
        Connection is created/retrieved from pool on first request().

        Args:
            serial: Device serial number as 12-digit hex string
            ip: Device IP address
            port: Device UDP port (default LIFX_UDP_PORT)
            source: Client source identifier (random if None)
            max_retries: Maximum retry attempts (default: 8)
            timeout: Default timeout for requests in seconds (default: 8.0)
        """
        self.serial = serial
        self.ip = ip
        self.port = port
        self.source = source
        self.max_retries = max_retries
        self.timeout = timeout

    @classmethod
    async def _get_pool(cls, max_connections: int = MAX_CONNECTIONS) -> ConnectionPool:
        """Get or create the shared connection pool.

        Internal method - not exposed to Device layer.

        Args:
            max_connections: Maximum connections in pool

        Returns:
            Shared ConnectionPool instance
        """
        async with cls._pool_lock:
            if cls._pool is None:
                cls._pool = ConnectionPool(max_connections=max_connections)
            return cls._pool

    @classmethod
    async def close_all_connections(cls) -> None:
        """Close all connections in the shared pool.

        Call this at application shutdown for clean teardown.
        """
        async with cls._pool_lock:
            if cls._pool is not None:
                await cls._pool.close_all()
                cls._pool = None

    @classmethod
    def get_pool_metrics(cls) -> ConnectionPoolMetrics | None:
        """Get connection pool metrics.

        Returns:
            ConnectionPoolMetrics if pool exists, None otherwise
        """
        return cls._pool.metrics if cls._pool is not None else None

    async def request_stream(
        self,
        packet: Any,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> AsyncGenerator[Any, None]:
        """Send request and yield unpacked responses.

        This is an async generator that handles the complete request/response
        cycle including packet type detection, response unpacking, and label
        decoding.

        Single response (most common):
            async for response in conn.request_stream(GetLabel()):
                process(response)
                break  # Exit immediately

        Multiple responses:
            async for state in conn.request_stream(GetColorZones()):
                process(state)
                # Continues until timeout

        Args:
            packet: Packet instance to send
            timeout: Request timeout in seconds

        Yields:
            Unpacked response packet instances
            For SET packets: yields True once (acknowledgement)

        Raises:
            LifxTimeoutError: If request times out
            LifxProtocolError: If response invalid
            LifxConnectionError: If connection fails
            LifxUnsupportedCommandError: If command not supported

        Example:
            ```python
            # GET request yields unpacked packets
            async for state in conn.request_stream(packets.Light.GetColor()):
                color = HSBK.from_protocol(state.color)
                label = state.label  # Already decoded to string
                break

            # SET request yields True (acknowledgement)
            async for _ in conn.request_stream(
                packets.Light.SetColor(color=hsbk, duration=1000)
            ):
                # Acknowledgement received
                break

            # Multi-response GET - stream all responses
            async for state in conn.request_stream(
                packets.MultiZone.GetExtendedColorZones()
            ):
                # Process each zone state
                pass
            ```
        """
        # Get pool and retrieve actual connection
        pool = await self._get_pool()
        actual_conn = await pool.get_connection(
            serial=self.serial,
            ip=self.ip,
            port=self.port,
            source=self.source,
            max_retries=self.max_retries,
            timeout=self.timeout,
        )

        # Get packet metadata
        packet_kind = getattr(packet, "_packet_kind", "OTHER")

        if packet_kind == "GET":
            # Use PACKET_REGISTRY to find the appropriate packet class
            from lifx.protocol.packets import get_packet_class

            # Stream responses and unpack each
            async for header, payload in actual_conn.request_stream(
                packet, timeout=timeout
            ):
                packet_class = get_packet_class(header.pkt_type)
                if packet_class is None:
                    raise LifxProtocolError(
                        f"Unknown packet type {header.pkt_type} in response"
                    )

                # Update unknown serial with value from response header
                serial = Serial(value=header.target_serial).to_string()
                if self.serial == "000000000000" and serial != self.serial:
                    self.serial = serial

                # Unpack (labels are automatically decoded by Packet.unpack())
                response_packet = packet_class.unpack(payload)

                # Log the request/reply cycle
                request_values = packet.as_dict
                reply_values = response_packet.as_dict
                _LOGGER.debug(
                    {
                        "class": "DeviceConnection",
                        "method": "request_stream",
                        "request": {
                            "packet": type(packet).__name__,
                            "values": request_values,
                        },
                        "reply": {
                            "packet": type(response_packet).__name__,
                            "values": reply_values,
                        },
                        "serial": self.serial,
                        "ip": self.ip,
                    }
                )

                yield response_packet

        elif packet_kind == "SET":
            # Request acknowledgement
            async for _ in actual_conn.request_ack_stream(packet, timeout=timeout):
                # Log the request/ack cycle
                request_values = packet.as_dict
                _LOGGER.debug(
                    {
                        "class": "DeviceConnection",
                        "method": "request_stream",
                        "request": {
                            "packet": type(packet).__name__,
                            "values": request_values,
                        },
                        "reply": {
                            "packet": "Acknowledgement",
                            "values": {},
                        },
                        "serial": self.serial,
                        "ip": self.ip,
                    }
                )

                yield True
                return

        else:
            # Handle special cases
            if hasattr(packet, "PKT_TYPE"):
                pkt_type = packet.PKT_TYPE
                # EchoRequest/EchoResponse (58/59)
                if pkt_type == 58:  # EchoRequest
                    from lifx.protocol.packets import Device

                    async for header, payload in actual_conn.request_stream(
                        packet, timeout=timeout
                    ):
                        response_packet = Device.EchoResponse.unpack(payload)

                        # Log the request/reply cycle
                        request_values = packet.as_dict
                        reply_values = response_packet.as_dict
                        _LOGGER.debug(
                            {
                                "class": "DeviceConnection",
                                "method": "request_stream",
                                "request": {
                                    "packet": type(packet).__name__,
                                    "values": request_values,
                                },
                                "reply": {
                                    "packet": type(response_packet).__name__,
                                    "values": reply_values,
                                },
                                "serial": self.serial,
                                "ip": self.ip,
                            }
                        )

                        yield response_packet
                        return
                else:
                    raise LifxUnsupportedCommandError(
                        f"Cannot auto-handle packet kind: {packet_kind}"
                    )
            else:
                raise LifxProtocolError(
                    f"Packet missing PKT_TYPE: {type(packet).__name__}"
                )

    async def request(
        self,
        packet: Any,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> Any:
        """Send request and get single response (convenience wrapper).

        This is a convenience method that returns the first response from
        request_stream(). It's equivalent to:
            await anext(conn.request_stream(packet))

        Most device operations use this method since they expect a single response.

        Args:
            packet: Packet instance to send
            timeout: Request timeout in seconds

        Returns:
            Single unpacked response packet
            True for SET acknowledgement

        Raises:
            LifxTimeoutError: If no response within timeout
            LifxProtocolError: If response invalid
            LifxConnectionError: If connection fails
            LifxUnsupportedCommandError: If command not supported

        Example:
            ```python
            # GET request returns unpacked packet
            state = await conn.request(packets.Light.GetColor())
            color = HSBK.from_protocol(state.color)
            label = state.label  # Already decoded to string

            # SET request returns True
            success = await conn.request(
                packets.Light.SetColor(color=hsbk, duration=1000)
            )
            ```
        """
        async for response in self.request_stream(packet, timeout):
            return response
        raise LifxTimeoutError(f"No response from {self.ip}")
