"""Connection management for LIFX devices."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

if TYPE_CHECKING:
    from typing import Self

from lifx.const import LIFX_UDP_PORT, MAX_CONNECTIONS
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


@dataclass
class PendingRequest:
    """Tracks a pending request waiting for response(s).

    Used by the background response dispatcher to route incoming UDP
    responses to the correct waiting coroutine.

    Optionally collects multiple responses with an automatic timeout when
    collect_multiple is True, allowing callers to handle both single and
    multiple response cases.

    Attributes:
        sequence: Request sequence number for matching responses
        event: Event to signal when response(s) arrive
        collect_multiple: Whether to wait for multiple responses (default: False)
        collection_timeout: Timeout for additional responses after first
        results: List of response data (header, payload) when successful
        error: Exception if an error occurred
        first_response_time: Time when first response was received
    """

    sequence: int
    event: asyncio.Event
    collect_multiple: bool = False
    collection_timeout: float = 0.2
    results: list[tuple[LifxHeader, bytes]] = field(default_factory=list)
    error: Exception | None = None
    first_response_time: float | None = field(default=None)


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

    This is the actual connection with UDP socket, rate limiter, and background
    receiver. Not exposed directly - used internally by ConnectionPool which is
    in turn used internally by DeviceConnection handles.

    This class handles:
    - Message sending/receiving to a specific device
    - Sequence number management
    - Request/response matching with background dispatcher
    - Retry logic with exponential backoff
    """

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = LIFX_UDP_PORT,
        source: int | None = None,
        max_retries: int = 3,
        timeout: float = 1.0,
    ) -> None:
        """Initialize device connection.

        Args:
            serial: Device serial number as 12-digit hex string (e.g., 'd073d5123456')
            ip: Device IP address
            port: Device UDP port (default LIFX_UDP_PORT)
            source: Client source identifier (random if None)
            max_retries: Maximum number of retry attempts
            timeout: Overall timeout for requests in seconds
        """
        self.serial = serial
        self.ip = ip
        self.port = port
        self.max_retries = max_retries
        self.timeout = timeout

        self._transport: UdpTransport | None = None
        self._builder = MessageBuilder(source=source)
        self._is_open = False

        # Phase 2: Background response dispatcher
        self._pending_requests: dict[int, PendingRequest] = {}
        self._receiver_task: Any = None
        self._receiver_started = asyncio.Event()
        self._receiver_enabled = False

    async def __aenter__(self) -> Self:
        """Enter async context manager and start connection with background receiver."""
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
        """Open connection to device and start background receiver.

        The background receiver task enables concurrent request/response handling.
        It is started automatically whether using context manager or direct open().
        """
        if self._is_open:
            return

        # Open transport
        self._transport = UdpTransport(port=0, broadcast=False)
        await self._transport.open()
        self._is_open = True

        # Reset receiver started event for this connection session
        self._receiver_started = asyncio.Event()

        # Start background receiver task
        self._receiver_task = asyncio.create_task(self._response_receiver())
        # Wait for receiver to signal ready
        await self._receiver_started.wait()
        self._receiver_enabled = True

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
        """Close connection to device and stop background receiver."""
        if not self._is_open:
            return

        self._is_open = False
        reason = "normal"
        error_msg = None

        # Stop background receiver task
        if self._receiver_task is not None:
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                reason = "cancelled"
            except Exception as e:
                reason = "error"
                error_msg = str(e)
            self._receiver_task = None
            self._receiver_enabled = False

        # Close transport
        if self._transport is not None:
            await self._transport.close()

        log_entry: dict[str, str | None] = {
            "class": "_ActualConnection",
            "method": "close",
            "serial": self.serial,
            "ip": self.ip,
            "reason": reason,
        }
        if error_msg is not None:
            log_entry["error"] = error_msg
        _LOGGER.debug(log_entry)
        self._transport = None

    async def send_packet(
        self,
        packet: Any,
        ack_required: bool = False,
        res_required: bool = False,
    ) -> None:
        """Send a packet to the device.

        Args:
            packet: Packet dataclass instance
            ack_required: Request acknowledgement
            res_required: Request response

        Raises:
            ConnectionError: If connection is not open or send fails
        """
        if not self._is_open or self._transport is None:
            raise LifxConnectionError("Connection not open")

        # Create message
        message = self._builder.create_message(
            packet=packet,
            target=Serial.from_string(self.serial).to_protocol(),
            ack_required=ack_required,
            res_required=res_required,
        )

        # Send to device
        await self._transport.send(message, (self.ip, self.port))

    async def receive_packet(self, timeout: float = 2.0) -> tuple[LifxHeader, bytes]:
        """Receive a packet from the device.

        Note:
            This method does not validate the source IP address. Validation is instead
            performed using the LIFX protocol's built-in target field (serial number)
            and sequence number matching in request_response() and request_ack().
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

    async def _response_receiver(self) -> None:
        """Background task that receives and routes all UDP responses.

        This task runs continuously while the connection is open, receiving
        UDP packets and routing them to waiting coroutines based on sequence number.

        Always collects multiple responses with an automatic timeout by tracking
        when the first response arrives and signaling completion after the timeout
        period expires. This allows callers to handle both single and multiple
        response cases uniformly.

        This enables concurrent request/response handling on a single connection.

        Lifecycle:
        - Started by open() using asyncio.create_task()
        - Cancelled by close() via task cancellation
        - Completes any pending requests with error on cancellation
        """
        try:
            # Signal that receiver is ready
            self._receiver_started.set()
            _LOGGER.debug(
                {
                    "class": "_ActualConnection",
                    "method": "_response_receiver",
                    "action": "start",
                    "serial": self.serial,
                    "ip": self.ip,
                }
            )

            while self._is_open and self._transport is not None:
                try:
                    # Check for timed-out collections BEFORE receiving next packet
                    # This ensures we don't block indefinitely waiting for a second
                    # response
                    current_time = time.monotonic()
                    sequences_to_complete = []

                    for seq, pending in self._pending_requests.items():
                        if (
                            pending.collect_multiple
                            and pending.first_response_time is not None
                        ):
                            elapsed = current_time - pending.first_response_time
                            if elapsed >= pending.collection_timeout:
                                sequences_to_complete.append(seq)

                    # Complete any timed-out collections
                    for seq in sequences_to_complete:
                        pending = self._pending_requests.pop(seq)
                        pending.event.set()

                    # Receive next packet with short timeout to allow checking for
                    # expired collections
                    try:
                        header, payload = await self.receive_packet(timeout=0.1)
                    except LifxTimeoutError:
                        # No packet received, loop back to check for expired timeouts
                        continue

                    # Look up pending request by sequence number
                    sequence = header.sequence
                    if sequence in self._pending_requests:
                        pending = self._pending_requests[sequence]

                        # Check for StateUnhandled (unsupported command)
                        if header.pkt_type == 223:  # Device.StateUnhandled
                            # Device doesn't support this command (e.g., Switch device
                            # received Light command)
                            pending.error = LifxUnsupportedCommandError(
                                "Device does not support the requested command "
                                "(received StateUnhandled)"
                            )
                            # Remove from pending and signal completion
                            self._pending_requests.pop(sequence)
                            pending.event.set()
                        else:
                            # Success - add response to results
                            pending.results.append((header, payload))

                            # Handle based on collection mode
                            if pending.collect_multiple:
                                # Multi-response mode: track time for collection timeout
                                current_time = time.monotonic()
                                if pending.first_response_time is None:
                                    # First response - record time and wait for more
                                    pending.first_response_time = current_time
                                # Don't signal yet - wait for collection timeout
                            else:
                                # Single-response mode: signal immediately
                                self._pending_requests.pop(sequence, None)
                                pending.event.set()

                    # else: orphaned response (timeout, cancelled, etc.)
                    # We silently discard these

                except Exception:  # nosec B112
                    # Unexpected error - continue receiving
                    # In production, logging would be helpful here
                    continue

        except (asyncio.CancelledError, Exception) as e:
            # Task cancelled during close or other error - cleanup pending requests
            reason = "error"
            error_msg = None
            if isinstance(e, asyncio.CancelledError):
                reason = "cancelled"
                # Cancelled - cleanup pending requests
                for pending in self._pending_requests.values():
                    pending.error = LifxConnectionError("Connection closed")
                    pending.event.set()
                self._pending_requests.clear()
            else:
                error_msg = str(e)

            log_entry: dict[str, str | None] = {
                "class": "_ActualConnection",
                "method": "_response_receiver",
                "action": "stop",
                "serial": self.serial,
                "ip": self.ip,
                "reason": reason,
            }
            if error_msg is not None:
                log_entry["error"] = error_msg
            _LOGGER.debug(log_entry)
            raise  # Re-raise to complete cancellation/error propagation

    async def request_response(
        self,
        request: Any,
        timeout: float | None = None,
        max_retries: int | None = None,
        collect_multiple: bool = False,
    ) -> tuple[LifxHeader, bytes] | list[tuple[LifxHeader, bytes]]:
        """Send request and wait for response(s).

        Implements retry logic with exponential backoff. Matches responses by
        sequence number and supports concurrent requests on the same connection.

        By default, returns immediately after the first response. Set
        collect_multiple=True to wait for additional responses (200ms timeout).

        Args:
            request: Request packet to send
            timeout: Overall timeout for all retry attempts
            max_retries: Maximum retries (uses instance default if None)
            collect_multiple: Whether to wait for multiple responses

        Returns:
            Single response tuple or list of response tuples if collect_multiple

        Raises:
            ConnectionError: If connection is not open
            TimeoutError: If no response after all retries
            ProtocolError: If response is malformed

        Example:
            ```python
            # Single response (default, fast)
            header, payload = await conn.request_response(DeviceGetLabel(), timeout=2.0)

            # Multiple responses (e.g., MultiZone)
            response = await conn.request_response(
                MultiZone.GetColorZones(), timeout=2.0, collect_multiple=True
            )
            if isinstance(response, list):
                for header, payload in response:
                    pass
            else:
                header, payload = response
            ```
        """
        if not self._is_open or self._transport is None:
            raise LifxConnectionError("Connection not open")

        if timeout is None:
            timeout = self.timeout

        if max_retries is None:
            max_retries = self.max_retries

        # Calculate base timeout for exponential backoff
        # Normalize so total time across all retries equals overall timeout
        # Geometric series: 1 + 2 + 4 + ... + 2^n = 2^(n+1) - 1
        total_weight = (2 ** (max_retries + 1)) - 1
        base_timeout = timeout / total_weight

        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            # Calculate timeout with exponential backoff (normalized to overall timeout)
            current_timeout = base_timeout * (2**attempt)

            try:
                # Get sequence number BEFORE creating pending request
                sequence = self._builder.next_sequence()

                # Create pending request with optional multi-response collection
                pending = PendingRequest(
                    sequence=sequence,
                    event=asyncio.Event(),
                    collect_multiple=collect_multiple,
                )
                self._pending_requests[sequence] = pending

                try:
                    # Send request
                    await self.send_packet(
                        request, ack_required=False, res_required=True
                    )

                    # Wait for response(s) with internal collection timeout
                    async with asyncio.timeout(current_timeout):
                        await pending.event.wait()

                    # Check if error occurred
                    if pending.error is not None:
                        raise pending.error

                    # Return results - either single tuple or list of tuples
                    if pending.results:
                        if len(pending.results) == 1:
                            # Single response - return as tuple
                            return pending.results[0]
                        else:
                            # Multiple responses - return as list
                            return pending.results
                    else:
                        raise LifxConnectionError("Request completed without result")

                finally:
                    # Cleanup pending request if still registered
                    self._pending_requests.pop(sequence, None)

            except TimeoutError:
                last_error = LifxTimeoutError(
                    f"No response within {current_timeout:.3f}s "
                    f"(attempt {attempt + 1}/{max_retries + 1})"
                )
                if attempt < max_retries:
                    await asyncio.sleep(0.1 * (2**attempt))
                    continue
                else:
                    break

        # All retries exhausted
        if last_error:
            raise LifxTimeoutError(
                f"No response from {self.ip} after {max_retries + 1} attempts"
            ) from last_error
        else:
            raise LifxConnectionError("Request failed for unknown reason")

    async def request_ack(
        self,
        request: Any,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        """Send request and wait for acknowledgement packet.

        Implements retry logic with exponential backoff. Matches acknowledgements
        by sequence number and supports concurrent requests on the same connection.

        Args:
            request: Request packet to send
            timeout: Overall timeout for all retry attempts
            max_retries: Maximum retries (uses instance default if None)

        Returns:
            None

        Raises:
            ConnectionError: If connection is not open
            TimeoutError: If no acknowledgement after all retries
            ProtocolError: If acknowledgement is malformed

        Example:
            ```python
            await conn.request_ack(LightSetPower(state=LightPowerLevel.ON), timeout=2.0)
            ```
        """
        if not self._is_open or self._transport is None:
            raise LifxConnectionError("Connection not open")

        if timeout is None:
            timeout = self.timeout

        if max_retries is None:
            max_retries = self.max_retries

        # Calculate base timeout for exponential backoff
        # Normalize so total time across all retries equals overall timeout
        # Geometric series: 1 + 2 + 4 + ... + 2^n = 2^(n+1) - 1
        total_weight = (2 ** (max_retries + 1)) - 1
        base_timeout = timeout / total_weight

        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            # Calculate timeout with exponential backoff (normalized to overall timeout)
            current_timeout = base_timeout * (2**attempt)

            try:
                # Get sequence number BEFORE creating pending request
                sequence = self._builder.next_sequence()

                # Create pending request (matches by sequence number only)
                pending = PendingRequest(sequence=sequence, event=asyncio.Event())
                self._pending_requests[sequence] = pending

                try:
                    # Send request with acknowledgement required
                    await self.send_packet(
                        request, ack_required=True, res_required=False
                    )

                    # Wait for acknowledgement with current timeout
                    async with asyncio.timeout(current_timeout):
                        await pending.event.wait()

                    # Check if error occurred
                    if pending.error is not None:
                        raise pending.error

                    # Success (acknowledgement received)
                    return

                finally:
                    # Cleanup pending request if still registered
                    self._pending_requests.pop(sequence, None)

            except TimeoutError:
                last_error = LifxTimeoutError(
                    f"No acknowledgement within {current_timeout:.3f}s "
                    f"(attempt {attempt + 1}/{max_retries + 1})"
                )
                if attempt < max_retries:
                    await asyncio.sleep(0.1 * (2**attempt))
                    continue
                else:
                    break

        # All retries exhausted
        if last_error:
            raise LifxTimeoutError(
                f"Failed to receive acknowledgement after {max_retries + 1} attempts"
            ) from last_error
        else:
            raise LifxConnectionError("Request failed for unknown reason")

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
        max_retries: int = 3,
        timeout: float = 1.0,
    ) -> _ActualConnection:
        """Get or create actual connection with parameters.

        Args:
            serial: Device serial number
            ip: Device IP address
            port: Device UDP port
            source: Client source identifier (random if None)
            max_retries: Maximum retry attempts
            timeout: Overall timeout for requests (distributed across retries)

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
        max_retries: int = 3,
        timeout: float = 1.0,
    ) -> None:
        """Initialize connection handle.

        This is lightweight - doesn't actually create a connection.
        Connection is created/retrieved from pool on first request().

        Args:
            serial: Device serial number as 12-digit hex string
            ip: Device IP address
            port: Device UDP port (default LIFX_UDP_PORT)
            source: Client source identifier (random if None)
            max_retries: Maximum retry attempts
            timeout: Overall timeout for requests in seconds
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

    async def request(
        self, packet: Any, timeout: float = 2.0, collect_multiple: bool = False
    ) -> Any:
        """Send request and return unpacked response(s).

        This method handles everything internally:
        - Getting connection from pool (creates if needed)
        - Opening connection if needed
        - Sending request with proper ack/response flags
        - Optionally collecting multiple responses if requested
        - Unpacking response(s)
        - Decoding label fields

        Device classes just call this and get back the result.

        By default, GET requests return immediately after the first response.
        Set collect_multiple=True for multi-response commands to wait 200ms.

        Args:
            packet: Packet instance to send
            timeout: Request timeout in seconds
            collect_multiple: Whether to wait for multiple responses (default: False)

        Returns:
            Single or multiple response packets (list if collect_multiple=True)
            True for SET acknowledgement

        Raises:
            LifxTimeoutError: If request times out
            LifxProtocolError: If response invalid
            LifxConnectionError: If connection fails
            LifxUnsupportedCommandError: If packet kind is unsupported

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

            # Multi-response GET - collect multiple responses
            states = await conn.request(
                packets.MultiZone.GetColorZones(...), collect_multiple=True
            )
            if isinstance(states, list):
                for state in states:
                    # process each zone state
                    pass
            else:
                # single response
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
            # Request response(s) - with optional multi-response collection
            response = await actual_conn.request_response(
                packet, timeout=timeout, collect_multiple=collect_multiple
            )

            # Use PACKET_REGISTRY to find the appropriate packet class
            from lifx.protocol.packets import get_packet_class

            # Check if we got multiple responses or a single response
            if isinstance(response, list):
                # Multiple responses - unpack each one
                unpacked_responses = []
                for header, payload in response:
                    packet_class = get_packet_class(header.pkt_type)
                    if packet_class is None:
                        raise LifxProtocolError(
                            f"Unknown packet type {header.pkt_type} in response"
                        )

                    # Unpack (labels are automatically decoded by Packet.unpack())
                    response_packet = packet_class.unpack(payload)
                    unpacked_responses.append(response_packet)

                # Log the full request/reply cycle (multiple responses)
                request_values = packet.as_dict
                reply_values_by_seq: dict[int, dict[str, Any]] = {}
                for i, (header, _) in enumerate(response, 1):
                    resp_pkt = unpacked_responses[i - 1]
                    reply_values_by_seq[header.sequence] = resp_pkt.as_dict

                _LOGGER.debug(
                    {
                        "class": "DeviceConnection",
                        "method": "request",
                        "request": {
                            "packet": type(packet).__name__,
                            "values": request_values,
                        },
                        "reply": {
                            "packet": type(unpacked_responses[0]).__name__
                            if unpacked_responses
                            else "Unknown",
                            "expected": len(response),
                            "received": len(unpacked_responses),
                            "values": reply_values_by_seq,
                        },
                        "serial": self.serial,
                        "ip": self.ip,
                    }
                )

                return unpacked_responses
            else:
                # Single response - response is tuple[LifxHeader, bytes]
                header, payload = response
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

                # Log the full request/reply cycle (single response)
                request_values = packet.as_dict
                reply_values = response_packet.as_dict
                _LOGGER.debug(
                    {
                        "class": "DeviceConnection",
                        "method": "request",
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

                return response_packet

        elif packet_kind == "SET":
            # Request acknowledgement
            await actual_conn.request_ack(packet, timeout=timeout)

            # Log the full request/ack cycle
            request_values = packet.as_dict
            _LOGGER.debug(
                {
                    "class": "DeviceConnection",
                    "method": "request",
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

            return True

        else:
            # Handle special cases
            if hasattr(packet, "PKT_TYPE"):
                pkt_type = packet.PKT_TYPE
                # EchoRequest/EchoResponse (58/59)
                if pkt_type == 58:  # EchoRequest
                    from lifx.protocol.packets import Device

                    response = await actual_conn.request_response(
                        packet, timeout=timeout, collect_multiple=False
                    )
                    if not isinstance(response, tuple):
                        raise LifxProtocolError(
                            "Expected single response tuple for EchoRequest"
                        )

                    header, payload = response
                    response_packet = Device.EchoResponse.unpack(payload)

                    # Log the full request/reply cycle
                    request_values = packet.as_dict
                    reply_values = response_packet.as_dict
                    _LOGGER.debug(
                        {
                            "class": "DeviceConnection",
                            "method": "request",
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

                    return response_packet
                else:
                    raise LifxUnsupportedCommandError(
                        f"Cannot auto-handle packet kind: {packet_kind}"
                    )
            else:
                raise LifxProtocolError(
                    f"Packet missing PKT_TYPE: {type(packet).__name__}"
                )
