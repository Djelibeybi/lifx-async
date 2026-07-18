"""Connection management for LIFX devices."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from typing_extensions import Self

from lifx.const import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    LIFX_UDP_PORT,
    REQUEST_RETRANSMIT_GAPS,
    TIMEOUT_ERRORS,
)
from lifx.exceptions import (
    LifxConnectionError,
    LifxProtocolError,
    LifxTimeoutError,
    LifxUnsupportedCommandError,
)
from lifx.network.message import create_message, parse_message
from lifx.network.transport import UdpTransport
from lifx.network.utils import allocate_source
from lifx.protocol.header import LifxHeader
from lifx.protocol.models import Serial
from lifx.protocol.packets import Device, get_packet_class

_LOGGER = logging.getLogger(__name__)

# Type variable for packet types
T = TypeVar("T")

# Constants for retry logic
_STATE_UNHANDLED_PKT_TYPE: int = 223  # Device.StateUnhandled packet type
# Idle timeout for multi-response streaming: stop streaming if no responses
# arrive for this long after the first response. Read at runtime (not a
# def-time default) inside the helper so tests can patch it for fast
# idle-exit coverage.
_STREAM_IDLE_TIMEOUT: float = 2.0
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
    - Automatic retransmits on an escalating schedule within each request's
      timeout, listening for a reply throughout
    - Response correlation: a background receiver routes each reply to its request,
      so concurrent requests never mix
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
            max_retries: Maximum number of retransmits within the timeout
                (default: 8). Total transmissions are at most
                max_retries + 1; after the cap is reached the request keeps
                listening for a reply until the timeout expires instead of
                failing early. Whichever of the retransmit cap and the
                timeout is reached first wins.
            timeout: Default timeout for requests in seconds (default: 16.0).
                The timeout is an overall limit on the whole request: all
                waiting -- transmissions, retransmit gaps, and the final
                listen window -- counts against it, so a request can never
                take materially longer than the timeout it was given.
        """
        self.serial = serial
        self.ip = ip
        self.port = port
        self.max_retries = max_retries
        self.timeout = timeout

        self._transport: UdpTransport | None = None
        self._is_open = False
        # Flag to prevent concurrent open() calls. Deliberately a plain bool
        # with a poll loop rather than asyncio.Lock: a Lock binds to the event
        # loop that first awaits it, which breaks connections that are closed
        # and reopened under a different loop (e.g. one connection shared
        # across per-test event loops).
        self._is_opening = False

        # Pre-compute serial bytes for fast comparison in background receiver
        self._is_discovery = serial == "000000000000"
        if not self._is_discovery:
            serial_obj = Serial.from_string(serial)
            self._target_bytes: bytes | None = serial_obj.to_protocol()
        else:
            self._target_bytes = None

        # Pre-compute target bytes for send_packet() to avoid
        # re-parsing on every send
        if self._target_bytes is not None:
            self._send_target: bytes = self._target_bytes
        else:
            self._send_target: bytes = b"\x00" * 8

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

        # Prevent concurrent open() calls (see __init__ for why this is a
        # poll loop rather than an asyncio.Lock)
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
            except TIMEOUT_ERRORS:
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
            source = allocate_source()

        message = create_message(
            packet=packet,
            source=source,
            sequence=sequence,
            target=self._send_target,
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
                # For discovery connections, always use "000000000000" for correlation
                # regardless of response serial
                if self._is_discovery:
                    serial = "000000000000"
                else:
                    # Compare target bytes directly to avoid string conversion
                    if (
                        self._target_bytes is not None
                        and header.target == self._target_bytes
                    ):
                        serial = self.serial
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

    async def _transmit_and_listen(
        self,
        request: Any,
        timeout: float | None,
        max_retries: int | None,
        *,
        ack_required: bool,
        res_required: bool,
        timeout_noun: str,
    ) -> AsyncGenerator[tuple[LifxHeader, bytes], None]:
        """Shared wall-deadline retransmit-while-listening engine.

        Both request paths (GET-style multi-response streaming and
        SET-style single-ACK) delegate here. Owns source allocation, the
        shared response queue, the escalating retransmit schedule, the
        single monotonic wall deadline, correlation-key lifecycle, and
        response validation. The two thin wrappers
        (``_request_stream_impl``/``_request_ack_stream_impl``) only add
        their distinct semantics (multi-response idle streaming vs single
        ACK + StateUnhandled handling).

        Schedule: one send at t=0, then retransmits at cumulative offsets
        from ``REQUEST_RETRANSMIT_GAPS`` (read as a module attribute at
        runtime so tests can patch it), repeating the final gap once the
        schedule is exhausted. Retransmits stop the moment a response is
        yielded -- never after (avoids duplicating multi-response sets).

        Deadline: ``timeout`` is a hard deadline computed once from
        ``time.monotonic()``. Every wait folds the deadline, the next
        retransmit time, and (once streaming) the idle window into a
        single ``asyncio.wait_for`` call -- there is no blind
        ``asyncio.sleep()`` anywhere in this loop.

        ``max_retries`` interaction rule: it caps the number of
        *retransmits* after the initial send (total transmissions at most
        ``max_retries + 1``). The deadline caps *time*. Whichever
        binds first wins -- after the retransmit cap is reached the request
        keeps listening until the deadline rather than failing early.

        Correlation contract: one source per logical request, a fresh
        sequence per transmission, all transmissions share ONE response
        queue and are tracked in ``correlation_keys`` so a reply to any
        issued sequence completes the request. All keys are popped
        together in ``finally``; late replies that arrive after cleanup
        fail the ``_pending_requests`` lookup in ``_background_receiver``
        and are silently discarded at DEBUG.

        Args:
            request: Request packet to send
            timeout: Overall time budget for the whole request
            max_retries: Maximum retransmits within the timeout
            ack_required: Value of the ACK-required header flag to send
            res_required: Value of the response-required header flag to send
            timeout_noun: Noun used in the timeout message ("response" or
                "acknowledgement")

        Yields:
            Tuple of (LifxHeader, payload bytes) for each accepted response

        Raises:
            LifxConnectionError: If connection is not open
            LifxProtocolError: If response correlation validation fails
            LifxTimeoutError: If no response is accepted before the deadline
        """
        # Traceability: schedule RETRY-01/D3-01; listen-while-waiting
        # RETRY-02/D3-02; wall-clock budget RETRY-03/D3-03; shared-queue
        # correlation RETRY-04/D3-04; max_retries interaction rule D3-05.
        if not self._is_open or self._transport is None:
            raise LifxConnectionError("Connection not open")  # pragma: no cover

        if timeout is None:
            timeout = self.timeout  # pragma: no cover

        if max_retries is None:
            max_retries = self.max_retries

        # Allocate ONE source for this logical request
        request_source = allocate_source()

        # Create ONE shared queue for ALL transmissions of this request.
        # Responses from any transmission can satisfy the request (D3-04).
        response_queue: asyncio.Queue[tuple[LifxHeader, bytes]] = asyncio.Queue(
            maxsize=100
        )

        # Track all correlation keys for cleanup
        correlation_keys: list[tuple[int, int, str]] = []

        # Photons-shaped retransmit schedule. Read the module attribute at
        # runtime (not a def-time default) so tests can patch
        # lifx.network.connection.REQUEST_RETRANSMIT_GAPS for fast schedules.
        gaps = iter(REQUEST_RETRANSMIT_GAPS)
        last_gap = REQUEST_RETRANSMIT_GAPS[-1]

        start = time.monotonic()
        deadline = start + timeout
        has_yielded = False
        last_response_time = start
        tx_count = 0

        try:
            # Transmission #0 (sequence 0), key registered BEFORE send so a
            # response cannot arrive before its key exists.
            key = (request_source, 0, self.serial)
            self._pending_requests[key] = response_queue
            correlation_keys.append(key)
            await self.send_packet(
                request,
                source=request_source,
                sequence=0,
                ack_required=ack_required,
                res_required=res_required,
            )
            tx_count = 1
            next_tx_at: float | None = (
                time.monotonic() + next(gaps, last_gap) if max_retries > 0 else None
            )

            while True:
                now = time.monotonic()

                # Wall-time budget (RETRY-03): the only exit that can raise.
                if now >= deadline:
                    if has_yielded:
                        return
                    break

                # Idle-streaming exit (only meaningful after the first
                # yield; multi-response stream semantics unchanged).
                if has_yielded:
                    idle_elapsed = now - last_response_time
                    if idle_elapsed >= _STREAM_IDLE_TIMEOUT:
                        _LOGGER.debug(
                            {
                                "class": "DeviceConnection",
                                "method": "_transmit_and_listen",
                                "action": "idle_timeout",
                                "idle_elapsed": idle_elapsed,
                                "responses_received": True,
                            }
                        )
                        return

                # Retransmit due? Never after the first response has been
                # yielded -- retransmitting mid-stream would duplicate a
                # whole multi-response set.
                if next_tx_at is not None and not has_yielded and now >= next_tx_at:
                    sequence = tx_count  # fresh sequence per retransmit
                    key = (request_source, sequence, self.serial)
                    self._pending_requests[key] = response_queue  # SAME queue
                    correlation_keys.append(key)
                    await self.send_packet(
                        request,
                        source=request_source,
                        sequence=sequence,
                        ack_required=ack_required,
                        res_required=res_required,
                    )
                    tx_count += 1
                    next_tx_at = (
                        time.monotonic() + next(gaps, last_gap)
                        if tx_count <= max_retries
                        else None
                    )
                    _LOGGER.debug(
                        {
                            "class": "DeviceConnection",
                            "method": "_transmit_and_listen",
                            "action": "retransmit_sent",
                            "sequence": sequence,
                        }
                    )
                    continue  # re-read monotonic time before computing wait

                # Fold every bound into ONE queue-get timeout (RETRY-02):
                # this replaces the jitter sleep where arrived responses
                # sat unread.
                wait = deadline - now
                if next_tx_at is not None and not has_yielded:
                    wait = min(wait, next_tx_at - now)
                if has_yielded:
                    wait = min(wait, _STREAM_IDLE_TIMEOUT - (now - last_response_time))

                try:
                    header, payload = await asyncio.wait_for(
                        response_queue.get(), timeout=wait
                    )
                except TIMEOUT_ERRORS:
                    continue  # slice ended -- loop top decides why

                # Validate correlation (defense in depth)
                # For discovery connections, skip serial validation
                if not self._is_discovery:
                    if (
                        self._target_bytes is not None
                        and header.target != self._target_bytes
                    ):
                        response_serial = Serial.from_protocol(
                            header.target
                        ).to_string()
                        raise LifxProtocolError(
                            f"Response serial mismatch: "
                            f"expected {self.serial}, got {response_serial}"
                        )

                # Validate source matches (sequence can be from any
                # transmission)
                if header.source != request_source:
                    raise LifxProtocolError(
                        f"Response source mismatch: "
                        f"expected {request_source}, got {header.source}"
                    )

                # Validate sequence is from one of our registered
                # transmissions
                if header.sequence >= len(correlation_keys):
                    max_expected = len(correlation_keys) - 1
                    raise LifxProtocolError(
                        f"Response sequence out of range: "
                        f"got {header.sequence}, max expected {max_expected}"
                    )

                # Yield response (can be from any transmission)
                has_yielded = True
                last_response_time = time.monotonic()
                yield header, payload

                # Continue loop to wait for more responses

        finally:
            # Cleanup: remove ALL correlation keys at once (D3-04 -- late
            # replies then hit _background_receiver's unmatched path, DEBUG
            # logged and silently discarded)
            for key in correlation_keys:
                self._pending_requests.pop(key, None)

        # Wall deadline expired without ever yielding a response
        raise LifxTimeoutError(
            f"No {timeout_noun} from {self.ip} after {tx_count} attempts"
        )

    async def _request_stream_impl(
        self,
        request: Any,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> AsyncGenerator[tuple[LifxHeader, bytes], None]:
        """Internal implementation of request_stream with retry logic.

        Thin wrapper around ``_transmit_and_listen`` for GET-style requests:
        multi-response streaming with ``res_required=True``. Kept as a
        separate async generator with this exact name and signature -- it
        is the mock seam patched by existing tests.

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
        async for header, payload in self._transmit_and_listen(
            request,
            timeout,
            max_retries,
            ack_required=False,
            res_required=True,
            timeout_noun="response",
        ):
            yield header, payload

    async def _request_ack_stream_impl(
        self,
        request: Any,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> AsyncGenerator[bool, None]:
        """Internal implementation of request_ack_stream with retry logic.

        Thin wrapper around ``_transmit_and_listen`` for SET-style requests:
        a single acknowledgement with ``ack_required=True``. Kept as a
        separate async generator with this exact name and signature -- it
        is the mock seam patched by existing tests. StateUnhandled handling
        is ack-specific semantics and stays here (D3-06).

        Args:
            request: Request packet to send
            timeout: Overall timeout for all retry attempts
            max_retries: Maximum retries

        Yields:
            True for successful ACK

        Raises:
            LifxConnectionError: If connection is not open
            LifxUnsupportedCommandError: If device returned StateUnhandled
            LifxTimeoutError: If no ack after all retries
        """
        # The loop body always exits via `return` (ACK accepted) or a raised
        # exception (StateUnhandled, or the delegate raising
        # LifxTimeoutError before ever yielding); it never runs out of items
        # and falls through normally, so the loop's natural-exhaustion arc
        # is structurally unreachable -- pragma below suppresses that one
        # partial branch, not line coverage of the loop itself.
        async for header, _payload in self._transmit_and_listen(  # pragma: no branch
            request,
            timeout,
            max_retries,
            ack_required=True,
            res_required=False,
            timeout_noun="acknowledgement",
        ):
            if header.pkt_type == _STATE_UNHANDLED_PKT_TYPE:
                raise LifxUnsupportedCommandError(
                    "Device does not support this command"
                )
            yield True
            return

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
                if self._is_discovery:
                    serial = Serial(value=header.target_serial).to_string()
                    if serial != self.serial:
                        self.serial = serial
                        # Refresh cached fields now that we know the real serial
                        self._is_discovery = False
                        self._target_bytes = Serial.from_string(serial).to_protocol()
                        self._send_target = self._target_bytes

                # Unpack (labels are automatically decoded by Packet.unpack())
                response_packet = packet_class.unpack(payload)

                # Log the request/reply cycle (as_dict is costly — skip
                # building it unless DEBUG logging is enabled)
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug(
                        {
                            "class": "DeviceConnection",
                            "method": "request_stream",
                            "request": {
                                "packet": type(packet).__name__,
                                "values": packet.as_dict,
                            },
                            "reply": {
                                "packet": type(response_packet).__name__,
                                "values": response_packet.as_dict,
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
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug(
                        {
                            "class": "DeviceConnection",
                            "method": "request_stream",
                            "request": {
                                "packet": type(packet).__name__,
                                "values": packet.as_dict,
                            },
                            "reply": {
                                "packet": "Acknowledgement"
                                if ack_result
                                else "StateUnhandled",
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
                    async for header, payload in self._request_stream_impl(
                        packet, timeout=timeout
                    ):
                        response_packet = Device.EchoResponse.unpack(payload)

                        # Log the request/reply cycle
                        if _LOGGER.isEnabledFor(logging.DEBUG):
                            _LOGGER.debug(
                                {
                                    "class": "DeviceConnection",
                                    "method": "request_stream",
                                    "request": {
                                        "packet": type(packet).__name__,
                                        "values": packet.as_dict,
                                    },
                                    "reply": {
                                        "packet": type(response_packet).__name__,
                                        "values": response_packet.as_dict,
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
