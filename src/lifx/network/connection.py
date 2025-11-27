"""Connection management for LIFX devices."""

from __future__ import annotations

import asyncio
import logging
import random
import secrets
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from typing import Self

from lifx.const import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    LIFX_UDP_PORT,
)
from lifx.exceptions import (
    LifxConnectionError,
    LifxProtocolError,
    LifxTimeoutError,
    LifxUnsupportedCommandError,
)
from lifx.network.message import create_message, parse_message
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
_RECEIVER_SHUTDOWN_TIMEOUT: float = (
    2.0  # How long to wait for the receiver to shutdown gracefully
)
_RECEIVER_POLL_TIMEOUT: float = 0.1  # How often the background receiver will sleep


class DeviceConnection:
    """Connection to a LIFX device.

    This class manages the UDP transport and request/response lifecycle for
    a single device. Connections are opened lazily on first request and
    remain open until explicitly closed.

    Features:
    - Lazy connection opening (no context manager required)
    - Async generator-based request/response streaming
    - Retry logic with exponential backoff and jitter
    - Request serialization to prevent response mixing
    - Automatic sequence number management

    Example:
        ```python
        conn = DeviceConnection(serial="d073d5123456", ip="192.168.1.100")

        # Connection opens automatically on first request
        state = await conn.request(packets.Light.GetColor())
        # state.label is already decoded to string
        # state.color is LightHsbk instance

        # Optionally close when done
        await conn.close()
        ```

    With context manager (recommended for cleanup):
        ```python
        async with DeviceConnection(...) as conn:
            state = await conn.request(packets.Light.GetColor())
        # Connection automatically closed on exit
        ```
    """

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = LIFX_UDP_PORT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        """Initialize device connection.

        This is lightweight - doesn't actually create a connection.
        Connection is opened lazily on first request.

        Args:
            serial: Device serial number as 12-digit hex string (e.g., 'd073d5123456')
            ip: Device IP address
            port: Device UDP port (default LIFX_UDP_PORT)
            max_retries: Maximum number of retry attempts (default: 8)
            timeout: Default timeout for requests in seconds (default: 8.0)
        """
        self.serial = serial
        self.ip = ip
        self.port = port
        self.max_retries = max_retries
        self.timeout = timeout

        self._transport: UdpTransport | None = None
        self._is_open = False
        self._is_opening = False  # Flag to prevent concurrent open() calls

        # Background receiver task infrastructure
        # Key: (source, sequence, serial) → Queue of (header, payload) tuples
        self._pending_requests: dict[
            tuple[int, int, str], asyncio.Queue[tuple[LifxHeader, bytes]]
        ] = {}
        self._receiver_task: asyncio.Task[None] | None = None
        self._receiver_shutdown: asyncio.Event | None = None

    async def __aenter__(self) -> Self:
        """Enter async context manager."""
        # Don't open connection here - it will open lazily on first request
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
        Called automatically on first request if not already open.
        """
        if self._is_open:
            return

        # Prevent concurrent open() calls
        if self._is_opening:
            # Another task is already opening, wait for it
            while self._is_opening:
                await asyncio.sleep(0.001)
            return

        self._is_opening = True
        try:
            # Double-check after setting flag
            if self._is_open:  # pragma: no cover
                return

            # Create shutdown event for receiver task
            self._receiver_shutdown = asyncio.Event()

            # Open transport
            self._transport = UdpTransport(port=0, broadcast=False)
            await self._transport.open()
            self._is_open = True

            # Start background receiver task
            self._receiver_task = asyncio.create_task(self._background_receiver())

            _LOGGER.debug(
                {
                    "class": "DeviceConnection",
                    "method": "open",
                    "serial": self.serial,
                    "ip": self.ip,
                    "port": self.port,
                }
            )
        finally:
            self._is_opening = False

    async def close(self) -> None:
        """Close connection to device."""
        if not self._is_open:
            return

        self._is_open = False

        # Signal shutdown to receiver task
        if self._receiver_shutdown:
            self._receiver_shutdown.set()

        # Wait for receiver to stop (with timeout)
        if self._receiver_task:
            try:
                await asyncio.wait_for(
                    self._receiver_task, timeout=_RECEIVER_SHUTDOWN_TIMEOUT
                )
            except TimeoutError:
                self._receiver_task.cancel()
                try:
                    await self._receiver_task
                except asyncio.CancelledError:
                    pass

        # Cancel all pending request queues
        for queue in self._pending_requests.values():
            # Drain queue
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
        self._pending_requests.clear()

        # Close transport
        if self._transport is not None:
            await self._transport.close()

        _LOGGER.debug(
            {
                "class": "DeviceConnection",
                "method": "close",
                "serial": self.serial,
                "ip": self.ip,
            }
        )
        self._transport = None

    async def _ensure_open(self) -> None:
        """Ensure connection is open, opening it if necessary.

        Note: This relies on open() being idempotent. In rare race conditions,
        multiple concurrent calls might attempt to open, but open() checks
        _is_open at the start and returns early if already open.
        """
        if not self._is_open:
            await self.open()

    async def send_packet(
        self,
        packet: Any,
        source: int | None = None,
        sequence: int = 0,
        ack_required: bool = False,
        res_required: bool = False,
    ) -> None:
        """Send a packet to the device.

        Args:
            packet: Packet dataclass instance
            source: Client source identifier (optional, allocated if None)
            sequence: Sequence number (default: 0)
            ack_required: Request acknowledgement
            res_required: Request response

        Raises:
            ConnectionError: If connection is not open or send fails
        """
        if not self._is_open or self._transport is None:
            raise LifxConnectionError("Connection not open")

        # Allocate source if not provided
        if source is None:
            source = self._allocate_source()

        target = Serial.from_string(self.serial).to_protocol()
        message = create_message(
            packet=packet,
            source=source,
            sequence=sequence,
            target=target,
            ack_required=ack_required,
            res_required=res_required,
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

    @staticmethod
    def _allocate_source() -> int:
        """Allocate unique source identifier for a request.

        LIFX protocol defines source as Uint32, with 0 and 1 reserved.
        We generate values in range [2, 0xFFFFFFFF].

        Returns:
            Unique source identifier (range: 2 to 4294967295)
        """
        return secrets.randbelow(0xFFFFFFFF - 1) + 2

    async def _background_receiver(self) -> None:
        """Background task to receive and route packets.

        Continuously receives packets and routes them to waiting requests
        by correlation key (source, sequence, serial). Unmatched responses
        are logged and discarded.

        The timeout in receive_packet() does NOT add latency to packet handling
        because packets are queued immediately by the UDP protocol's
        datagram_received() callback. The timeout is only for checking the
        shutdown flag.
        """
        while self._receiver_shutdown is None or not self._receiver_shutdown.is_set():
            try:
                # Poll with timeout to allow periodic shutdown checks
                # Note: This timeout does NOT delay packet handling!
                # Packets are queued immediately when they arrive.
                header, payload = await self.receive_packet(
                    timeout=_RECEIVER_POLL_TIMEOUT
                )

                # Compute correlation key (includes serial for defense-in-depth)
                # For discovery connections (self.serial == "000000000000"), always use
                # "000000000000" for correlation regardless of response serial
                if self.serial == "000000000000":
                    serial = "000000000000"
                else:
                    serial = Serial.from_protocol(header.target).to_string()
                key = (header.source, header.sequence, serial)

                # Route to waiting request
                if key in self._pending_requests:
                    queue = self._pending_requests[key]
                    try:
                        # Put in queue for request coroutine to consume
                        queue.put_nowait((header, payload))
                    except asyncio.QueueFull:
                        _LOGGER.warning(
                            {
                                "class": "DeviceConnection",
                                "method": "_background_receiver",
                                "action": "queue_full",
                                "source": header.source,
                                "sequence": header.sequence,
                                "serial": serial,
                            }
                        )
                else:
                    # Unmatched response - log and discard
                    _LOGGER.debug(
                        {
                            "class": "DeviceConnection",
                            "method": "_background_receiver",
                            "action": "unmatched_response",
                            "source": header.source,
                            "sequence": header.sequence,
                            "serial": serial,
                            "pkt_type": header.pkt_type,
                        }
                    )

            except LifxTimeoutError:
                # No packet available, continue loop (allows shutdown check)
                continue

            except Exception as e:
                if self._is_open:
                    _LOGGER.error(
                        {
                            "class": "DeviceConnection",
                            "method": "_background_receiver",
                            "action": "error",
                            "error": str(e),
                        },
                        exc_info=True,
                    )
                break

    async def _request_stream_impl(
        self,
        request: Any,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> AsyncGenerator[tuple[LifxHeader, bytes], None]:
        """Internal implementation of request_stream with retry logic.

        This is an async generator that sends a request and yields each response
        as it arrives. Uses queue-based correlation for multi-response support.

        All correlation keys (one per retry attempt) are kept registered until
        the entire request completes or all retries are exhausted. This allows
        late responses from earlier attempts to be accepted, preventing spurious
        "unmatched response" logs.

        Args:
            request: Request packet to send
            timeout: Overall timeout for all retry attempts
            max_retries: Maximum retries

        Yields:
            Tuple of (LifxHeader, payload bytes)

        Raises:
            LifxConnectionError: If connection is not open
            LifxProtocolError: If response correlation validation fails
            LifxTimeoutError: If no response after all retries
        """
        if not self._is_open or self._transport is None:
            raise LifxConnectionError("Connection not open")  # pragma: no cover

        if timeout is None:
            timeout = self.timeout  # pragma: no cover

        if max_retries is None:
            max_retries = self.max_retries

        # Allocate ONE source for this logical request
        request_source = self._allocate_source()

        # Create ONE shared queue for ALL retry attempts
        # Responses from any attempt can satisfy the request
        response_queue: asyncio.Queue[tuple[LifxHeader, bytes]] = asyncio.Queue(
            maxsize=100
        )

        # Track all correlation keys for cleanup
        correlation_keys: list[tuple[int, int, str]] = []

        # Calculate per-attempt timeouts with exponential backoff
        # Use proper exponential backoff distribution: timeout / (2^(n+1) - 1)
        # This ensures total of all attempt timeouts equals the overall timeout budget
        total_weight = (2 ** (max_retries + 1)) - 1
        base_timeout = timeout / total_weight

        # Idle timeout for multi-response protocols
        # Stop streaming if no responses for this long after first response
        idle_timeout = 2.0

        last_error: Exception | None = None
        has_yielded = False
        overall_start = time.monotonic()
        total_sleep_time = 0.0  # Track sleep time to exclude from timeout budget

        try:
            for attempt in range(max_retries + 1):
                # Calculate current attempt timeout with exponential backoff
                # Exclude sleep time from elapsed time to preserve timeout budget
                elapsed_response_time = (
                    time.monotonic() - overall_start - total_sleep_time
                )
                ideal_timeout = base_timeout * (2**attempt)
                current_timeout = min(ideal_timeout, timeout - elapsed_response_time)

                # Check if we've exceeded overall timeout budget
                if current_timeout <= 0:
                    break

                # Sequence increments per retry
                sequence = attempt  # 0, 1, 2, 3, ...

                # Correlation key: (source, sequence, serial)
                key = (request_source, sequence, self.serial)

                # Register correlation key with SHARED queue
                # All attempts share the same queue so any response can be consumed
                self._pending_requests[key] = response_queue
                correlation_keys.append(key)

                try:
                    # Send request
                    await self.send_packet(
                        request,
                        source=request_source,
                        sequence=sequence,
                        ack_required=False,
                        res_required=True,
                    )

                    attempt_start = time.monotonic()
                    attempt_deadline = attempt_start + current_timeout
                    last_response_time = attempt_start

                    # Stream responses from queue until timeout or idle timeout
                    while True:
                        remaining_time = attempt_deadline - time.monotonic()
                        if remaining_time <= 0:
                            if not has_yielded:
                                # No responses this attempt, retry
                                raise TimeoutError(
                                    f"No response within {current_timeout:.3f}s "
                                    f"(attempt {attempt + 1}/{max_retries + 1})"
                                )
                            # Had responses, stream complete
                            return

                        # Check idle timeout (only after first response)
                        if has_yielded:
                            idle_elapsed = time.monotonic() - last_response_time
                            if idle_elapsed >= idle_timeout:
                                # No more responses coming, done
                                _LOGGER.debug(
                                    {
                                        "class": "DeviceConnection",
                                        "method": "_request_stream_impl",
                                        "action": "idle_timeout",
                                        "idle_elapsed": idle_elapsed,
                                        "responses_received": True,
                                    }
                                )
                                return

                            # Adjust remaining time for idle timeout
                            remaining_time = min(
                                remaining_time, idle_timeout - idle_elapsed
                            )

                        # Wait for next response from queue
                        # Can come from ANY registered correlation key
                        try:
                            header, payload = await asyncio.wait_for(
                                response_queue.get(), timeout=remaining_time
                            )
                        except TimeoutError:
                            if not has_yielded:
                                # No response this attempt, retry
                                raise TimeoutError(
                                    f"No response within {current_timeout:.3f}s "
                                    f"(attempt {attempt + 1}/{max_retries + 1})"
                                )
                            # Had responses, done
                            return

                        # Validate correlation (defense in depth)
                        # For discovery connections, skip serial validation
                        if self.serial != "000000000000":
                            response_serial = Serial.from_protocol(
                                header.target
                            ).to_string()
                            if response_serial != self.serial:
                                raise LifxProtocolError(
                                    f"Response serial mismatch: "
                                    f"expected {self.serial}, got {response_serial}"
                                )

                        # Validate source matches (sequence can be from any attempt)
                        if header.source != request_source:
                            raise LifxProtocolError(
                                f"Response source mismatch: "
                                f"expected {request_source}, got {header.source}"
                            )

                        # Validate sequence is from one of our registered attempts
                        if header.sequence >= len(correlation_keys):
                            max_expected = len(correlation_keys) - 1
                            raise LifxProtocolError(
                                f"Response sequence out of range: "
                                f"got {header.sequence}, max expected {max_expected}"
                            )

                        # Yield response (can be from any retry attempt)
                        has_yielded = True
                        last_response_time = time.monotonic()
                        yield header, payload

                        # Continue loop to wait for more responses

                except TimeoutError as e:
                    last_error = LifxTimeoutError(str(e))
                    if attempt < max_retries:
                        # Sleep with jitter before retry
                        sleep_time = self._calculate_retry_sleep_with_jitter(attempt)
                        await asyncio.sleep(sleep_time)
                        total_sleep_time += (
                            sleep_time  # Track sleep to exclude from timeout
                        )
                        continue
                    else:
                        # All retries exhausted
                        break

        finally:
            # Cleanup: remove ALL correlation keys at once
            for key in correlation_keys:
                self._pending_requests.pop(key, None)

        # All retries exhausted without yielding any response
        if not has_yielded:
            raise LifxTimeoutError(
                f"No response from {self.ip} after {max_retries + 1} attempts"
            ) from last_error

    async def _request_ack_stream_impl(
        self,
        request: Any,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> AsyncGenerator[bool, None]:
        """Internal implementation of request_ack_stream with retry logic.

        This is an async generator that sends a request requiring acknowledgement
        and yields once when the ACK is received.

        Args:
            request: Request packet to send
            timeout: Overall timeout for all retry attempts
            max_retries: Maximum retries

        Yields:
            True for successful ACK, False if device returned StateUnhandled

        Raises:
            LifxConnectionError: If connection is not open
            LifxTimeoutError: If no ack after all retries
        """
        if not self._is_open or self._transport is None:
            raise LifxConnectionError("Connection not open")  # pragma: no cover

        if timeout is None:
            timeout = self.timeout  # pragma: no cover

        if max_retries is None:
            max_retries = self.max_retries

        # Allocate ONE source for this logical request
        request_source = self._allocate_source()

        # Calculate timeouts with exponential backoff
        total_weight = (2 ** (max_retries + 1)) - 1
        base_timeout = timeout / total_weight

        last_error: Exception | None = None
        total_sleep_time = 0.0  # Track sleep time to exclude from timeout budget
        overall_start = time.monotonic()

        for attempt in range(max_retries + 1):
            # Calculate timeout with budget remaining after excluding sleep time
            elapsed_response_time = time.monotonic() - overall_start - total_sleep_time
            ideal_timeout = base_timeout * (2**attempt)
            current_timeout = min(ideal_timeout, timeout - elapsed_response_time)
            sequence = attempt

            # Correlation key: (source, sequence, serial)
            key = (request_source, sequence, self.serial)

            # Create queue for ACK (bounded, though only expect 1 response)
            response_queue: asyncio.Queue[tuple[LifxHeader, bytes]] = asyncio.Queue(
                maxsize=10
            )
            self._pending_requests[key] = response_queue

            try:
                # Send request with ACK required
                await self.send_packet(
                    request,
                    source=request_source,
                    sequence=sequence,
                    ack_required=True,
                    res_required=False,
                )

                # Wait for single ACK response
                try:
                    header, _payload = await asyncio.wait_for(
                        response_queue.get(), timeout=current_timeout
                    )
                except TimeoutError:
                    raise TimeoutError(
                        f"No acknowledgement within {current_timeout:.3f}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )

                # Validate correlation
                if (
                    header.source != request_source
                    or header.sequence != sequence
                    or Serial.from_protocol(header.target).to_string() != self.serial
                ):
                    raise LifxProtocolError(
                        f"ACK correlation mismatch: "
                        f"expected ({request_source}, {sequence}, {self.serial}), "
                        f"got ({header.source}, {header.sequence}, "
                        f"{Serial.from_protocol(header.target).to_string()})"
                    )

                # Check for StateUnhandled - return False to indicate unsupported
                if header.pkt_type == _STATE_UNHANDLED_PKT_TYPE:
                    raise LifxUnsupportedCommandError(
                        "Device does not support this command"
                    )

                # ACK received successfully
                yield True
                return

            except TimeoutError as e:
                last_error = LifxTimeoutError(str(e))
                if attempt < max_retries:
                    # Sleep with jitter before retry
                    sleep_time = self._calculate_retry_sleep_with_jitter(attempt)
                    await asyncio.sleep(sleep_time)
                    total_sleep_time += (
                        sleep_time  # Track sleep to exclude from timeout
                    )
                    continue
                else:
                    break

            finally:
                self._pending_requests.pop(key, None)

        # All retries exhausted
        raise LifxTimeoutError(
            f"No acknowledgement from {self.ip} after {max_retries + 1} attempts"
        ) from last_error

    @property
    def is_open(self) -> bool:
        """Check if connection is open."""
        return self._is_open

    async def request_stream(
        self,
        packet: Any,
        timeout: float | None = None,
    ) -> AsyncGenerator[Any, None]:
        """Send request and yield unpacked responses.

        This is an async generator that handles the complete request/response
        cycle including packet type detection, response unpacking, and label
        decoding. Connection is opened automatically if not already open.

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
            Unpacked response packet instances (including StateUnhandled if device
            doesn't support the command)
            For SET packets: yields True (acknowledgement) or False (StateUnhandled)

        Raises:
            LifxTimeoutError: If request times out
            LifxProtocolError: If response invalid
            LifxConnectionError: If connection fails

        Example:
            ```python
            # GET request yields unpacked packets
            async for state in conn.request_stream(packets.Light.GetColor()):
                color = HSBK.from_protocol(state.color)
                label = state.label  # Already decoded to string
                break

            # SET request yields True (acknowledgement) or False (StateUnhandled)
            async for result in conn.request_stream(
                packets.Light.SetColor(color=hsbk, duration=1000)
            ):
                if result:
                    # Acknowledgement received
                    pass
                else:
                    # Device doesn't support this command
                    pass
                break

            # Multi-response GET - stream all responses
            async for state in conn.request_stream(
                packets.MultiZone.GetExtendedColorZones()
            ):
                # Process each zone state
                pass
            ```
        """
        # Ensure connection is open (lazy opening)
        await self._ensure_open()

        if timeout is None:
            timeout = self.timeout

        # Get packet metadata
        packet_kind = getattr(packet, "_packet_kind", "OTHER")

        if packet_kind == "GET":
            # Use PACKET_REGISTRY to find the appropriate packet class
            from lifx.protocol.packets import get_packet_class

            # Stream responses and unpack each
            async for header, payload in self._request_stream_impl(
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
            async for ack_result in self._request_ack_stream_impl(
                packet, timeout=timeout
            ):
                # Log the request/ack cycle
                request_values = packet.as_dict
                reply_packet = "Acknowledgement" if ack_result else "StateUnhandled"
                _LOGGER.debug(
                    {
                        "class": "DeviceConnection",
                        "method": "request_stream",
                        "request": {
                            "packet": type(packet).__name__,
                            "values": request_values,
                        },
                        "reply": {
                            "packet": reply_packet,
                            "values": {},
                        },
                        "serial": self.serial,
                        "ip": self.ip,
                    }
                )

                yield ack_result
                return

        else:
            # Handle special cases
            if hasattr(packet, "PKT_TYPE"):
                pkt_type = packet.PKT_TYPE
                # EchoRequest/EchoResponse (58/59)
                if pkt_type == 58:  # EchoRequest
                    from lifx.protocol.packets import Device

                    async for header, payload in self._request_stream_impl(
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
                    raise LifxProtocolError(
                        f"Cannot auto-handle packet kind: {packet_kind}"
                    )
            else:
                raise LifxProtocolError(
                    f"Packet missing PKT_TYPE: {type(packet).__name__}"
                )

    async def request(self, packet: Any, timeout: float | None = None) -> Any:
        """Send request and get single response (convenience wrapper).

        This is a convenience method that returns the first response from
        request_stream(). It's equivalent to:
            await anext(conn.request_stream(packet))

        Most device operations use this method since they expect a single response.
        Connection is opened automatically if not already open.

        Args:
            packet: Packet instance to send
            timeout: Request timeout in seconds

        Returns:
            Single unpacked response packet (including StateUnhandled if device
            doesn't support the command)
            For SET packets: True (acknowledgement) or False (StateUnhandled)

        Raises:
            LifxTimeoutError: If no response within timeout
            LifxProtocolError: If response invalid
            LifxConnectionError: If connection fails

        Example:
            ```python
            # GET request returns unpacked packet
            state = await conn.request(packets.Light.GetColor())
            color = HSBK.from_protocol(state.color)
            label = state.label  # Already decoded to string

            # SET request returns True or False
            success = await conn.request(
                packets.Light.SetColor(color=hsbk, duration=1000)
            )
            if not success:
                # Device doesn't support this command (returned StateUnhandled)
                pass
            ```
        """
        async for response in self.request_stream(packet, timeout):
            return response
        raise LifxTimeoutError(f"No response from {self.ip}")
