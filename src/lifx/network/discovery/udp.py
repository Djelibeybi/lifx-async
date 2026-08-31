"""Device discovery for LIFX network."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import aclosing
from dataclasses import dataclass, field
from itertools import accumulate
from typing import Any, cast

from lifx.const import (
    DEFAULT_IP_ADDRESS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DISCOVERY_REBROADCAST_GAPS,
    DISCOVERY_TIMEOUT,
    IDLE_TIMEOUT_MULTIPLIER,
    LIFX_UDP_PORT,
    MAX_RESPONSE_TIME,
)
from lifx.exceptions import (
    LifxError,
    LifxNetworkError,
    LifxProtocolError,
    LifxTimeoutError,
    LifxUnsupportedDeviceError,
)
from lifx.network.address import (
    host_from_sockaddr,
    sockaddr_for,
    validate_address,
    validate_port,
    wildcard_for,
)
from lifx.network.connection import DeviceConnection
from lifx.network.discovery.coordinator import _UdpSweepKey, subscribe_udp_sweep
from lifx.network.message import create_message, parse_message
from lifx.network.transport import UdpTransport
from lifx.network.utils import IdleDeadline, allocate_source
from lifx.protocol.base import Packet
from lifx.protocol.models import Serial
from lifx.protocol.packets import Device as DevicePackets
from lifx.protocol.packets import get_packet_class
from lifx.protocol.protocol_types import DeviceService

_LOGGER = logging.getLogger(__name__)
_DEFAULT_SEQUENCE_START: int = 0
_DISCOVERY_OBSERVER_TASK_ATTRIBUTE = "_lifx_discovery_observer"
_DiscoveryObserver = Callable[[str, str, str, int | None, int | None, str | None], None]


def _current_discovery_observer() -> _DiscoveryObserver | None:
    """Return the repository harness callback attached to the current task."""
    try:
        task = asyncio.current_task()
    except RuntimeError:
        return None
    return cast(
        _DiscoveryObserver | None,
        getattr(task, _DISCOVERY_OBSERVER_TASK_ATTRIBUTE, None),
    )


def _emit_discovery_event(
    observer: _DiscoveryObserver | None,
    *,
    source: str,
    stage: str,
    raw_identity: str,
    firmware_major: int | None = None,
    firmware_minor: int | None = None,
    connectivity: str | None = None,
) -> None:
    """Call an explicitly injected repository observer when one is present."""
    if observer is not None:
        observer(
            source,
            stage,
            raw_identity,
            firmware_major,
            firmware_minor,
            connectivity,
        )


@dataclass
class DiscoveredDevice:
    """Information about a discovered LIFX device.

    Attributes:
        serial: Device serial number as 12-digit hex string (e.g., "d073d5123456")
        ip: Device IP address
        port: Device UDP port
        first_seen: Timestamp when device was first discovered
        response_time: Response time in seconds, anchored at the first
            broadcast (time since discovery began). A device answering a
            later re-broadcast reports a proportionally larger value.
    """

    serial: str
    ip: str
    port: int = LIFX_UDP_PORT
    timeout: float = DEFAULT_REQUEST_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    first_seen: float = field(default_factory=time.time)
    response_time: float = 0.0
    _construction_connections: dict[asyncio.Task[Any], DeviceConnection] = field(
        default_factory=dict,
        init=False,
        repr=False,
        compare=False,
    )

    # Pyright infers the concrete device union from the local factory imports.
    # A module-level Device import would create a devices.base -> network cycle.
    async def create_device(self):
        """Create appropriate device instance based on product capabilities.

        Queries the device for its product ID and uses the product registry
        to instantiate the appropriate device class (Device, Light, HevLight,
        InfraredLight, MultiZoneLight, MatrixLight, or CeilingLight) based on
        the product capabilities.

        This is the single source of truth for device type detection and
        instantiation across the library.

        Returns:
            Device instance of the appropriate type

        Raises:
            TypeError: If a concrete device constructor no longer accepts the
                shared discovery arguments.
            AttributeError: If an internal device capability or metadata
                contract is broken.

        Example:
            ```python
            async for discovered in discover_devices():
                device = await discovered.create_device()
                if device is None:
                    continue  # unsupported product or transient failure
                print(f"Created {type(device).__name__}: {await device.get_label()}")
            ```
        """
        # Intentional local imports preserve the documented layer direction.
        # Importing the device layer while this network module initialises
        # creates a cycle when callers reach ``lifx.devices`` before the
        # top-level package has already populated ``lifx.network``.
        from lifx.devices.base import Device
        from lifx.devices.detection import get_device_class_for_product

        try:
            # Create temporary device to query version. Address validation can
            # fail here, before a connection exists, so keep construction
            # inside the same failure boundary as capability detection.
            temp_device = Device(
                serial=self.serial,
                ip=self.ip,
                port=self.port,
                timeout=self.timeout,
                max_retries=self.max_retries,
                _emit_input_warnings=False,
            )
            construction_task = asyncio.current_task()
            if construction_task is not None:
                self._construction_connections[construction_task] = (
                    temp_device.connection
                )

        except ValueError as error:
            _LOGGER.debug(
                {
                    "class": "DiscoveredDevice",
                    "method": "create_device",
                    "action": "invalid_device_address",
                    "serial": self.serial,
                    "ip": self.ip,
                    "reason": str(error),
                }
            )
            return None

        try:
            await temp_device.ensure_capabilities()
        except LifxError as error:
            _LOGGER.debug(
                {
                    "class": "DiscoveredDevice",
                    "method": "create_device",
                    "action": "capability_detection_failed",
                    "error_type": type(error).__name__,
                }
            )
            return None
        finally:
            # Always close the temporary device connection
            try:
                await temp_device.connection.close()
            finally:
                if construction_task is not None:
                    self._construction_connections.pop(construction_task, None)

        if not temp_device.capabilities or not temp_device.version:
            return None

        try:
            device_class = get_device_class_for_product(
                temp_device.version.product,
                temp_device.capabilities,
            )
        except LifxUnsupportedDeviceError:
            return None

        # Keep typed-device construction outside the transient network failure
        # boundary. A missing constructor pass-through is a programming error,
        # and must fail visibly instead of silently removing that product from
        # discovery.
        device = device_class(
            serial=self.serial,
            ip=self.ip,
            port=self.port,
            timeout=self.timeout,
            max_retries=self.max_retries,
            _emit_input_warnings=False,
        )

        # Capability detection already fetched and derived this metadata.
        # Preserve it on the correctly typed instance so callers do not
        # immediately repeat the same network work.
        device.adopt_cached_metadata(temp_device)
        return device

    def _force_close_construction(self, task: asyncio.Task[Any]) -> None:
        """Force-close temporary discovery resources owned by ``task``."""
        connection = self._construction_connections.get(task)
        if connection is not None:
            connection._force_close()

    def __hash__(self) -> int:
        """Hash based on serial number for deduplication."""
        return hash(self.serial)

    def __eq__(self, other: object) -> bool:
        """Equality based on serial number."""
        if not isinstance(other, DiscoveredDevice):
            return False
        return self.serial == other.serial


@dataclass
class DiscoveryResponse:
    """Response from a discovery broadcast using a custom packet.

    Attributes:
        serial: Device serial number
        ip: Device IP address
        port: UDP source port the device responded from (``addr[1]``), not a
            device-reported service port. For GetService discovery the
            authoritative service port is in ``response_payload["port"]``.
        response_time: Response time in seconds, anchored at the first
            broadcast (time since discovery began). A device answering a
            later re-broadcast reports a proportionally larger value.
        response_payload: Unpacked State packet fields as key/value dict
    """

    serial: str
    ip: str
    port: int
    response_time: float
    response_payload: dict[str, Any]


async def _discover_with_packet(
    packet: Packet,
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    *,
    _address_is_prevalidated: bool = False,
    _observer: _DiscoveryObserver | None = None,
) -> AsyncGenerator[DiscoveryResponse]:
    """Generic discovery using any Get* packet.

    Broadcasts the specified packet and collects all State* responses.
    Uses the packet's STATE_TYPE attribute to validate expected responses.
    The packet is re-broadcast on an escalating Photons-shaped schedule
    (``DISCOVERY_REBROADCAST_GAPS``, cumulative offsets 0.6, 1.8, 3.6, 5.6,
    7.6 s from the first send), capped by the discovery window, so devices
    behind a lossy access point that miss the first broadcast are still
    found within a single discovery call.

    This is a powerful protocol trick that allows targeted discovery:
    - GetLabel: Find devices by label
    - GetColor: Find only lights (non-lights return StateUnhandled)
    - GetGroup/GetLocation: Find devices by group/location

    Args:
        packet: Any Get* packet to broadcast (must have STATE_TYPE attribute)
        timeout: Discovery timeout in seconds
        broadcast_address: Broadcast address or specific IP
        port: UDP port
        max_response_time: Max response time
        idle_timeout_multiplier: Idle timeout multiplier
        _address_is_prevalidated: Suppress caller advisories when a public
            entry point already validated the same destination
        _observer: Explicit caller-owned measurement observer. The
            repository harness selector is captured by ``discover_devices`` and is
            never consulted inside this wire producer.

    Note:
        The idle timer is reset both before a response is yielded and again
        once the consumer resumes the generator, so time the consumer spends
        processing a response does not count against the *idle* window. A
        consumer that performs network round trips per response (as
        ``discover()`` does, constructing a Device each time) therefore does
        not expire the idle window.

        The overall ``timeout`` is unaffected and remains the real bound. With
        the default constants a single stalled request
        (``DEFAULT_REQUEST_TIMEOUT``, 16 s) outlasts the whole discovery window
        (``DISCOVERY_TIMEOUT``, 15 s), so one unreachable device can still end
        the sweep early -- via the overall deadline rather than the idle one.
        Raise ``timeout`` if per-device consumer work can approach the request
        timeout.

        Re-broadcast offsets that fall due while the consumer holds the
        generator are all sent when it resumes (see
        ``test_multiple_sends_due_in_one_loop_pass``), so a long stall
        compresses the remaining schedule rather than deferring it.

    Yields:
        DiscoveryResponse objects with unpacked response payloads, one per
        unique serial (first response wins). ``response_payload`` keys are the
        snake_case Python field names of the State packet (e.g. ``label``,
        ``port``). Responses whose packet type does not match the request's
        ``STATE_TYPE`` (e.g. StateUnhandled from non-lights) are skipped, not
        yielded.

    Example:
        ```python
        # Find all devices and their labels
        async for resp in _discover_with_packet(DevicePackets.GetLabel()):
            print(f"{resp.serial}: {resp.response_payload['label']}")
        ```
    """
    if not hasattr(packet, "STATE_TYPE"):
        raise ValueError(
            f"Packet {type(packet).__name__} must have STATE_TYPE attribute"
        )

    expected_response_type: int = getattr(packet, "STATE_TYPE")
    seen_serials: set[str] = set()
    start_time = time.monotonic()

    validate_address(broadcast_address, emit_warnings=not _address_is_prevalidated)
    local_bind = wildcard_for(broadcast_address)
    try:
        send_address = sockaddr_for((broadcast_address, port))
    except ValueError as error:
        raise LifxNetworkError(
            f"Invalid destination {broadcast_address!r}: {error}"
        ) from error
    async with UdpTransport(
        ip_address=local_bind,
        port=0,
        broadcast=local_bind == DEFAULT_IP_ADDRESS,
    ) as transport:
        # Allocate unique source for this discovery session
        discovery_source = allocate_source()

        message = create_message(
            packet=packet,
            source=discovery_source,
            sequence=_DEFAULT_SEQUENCE_START,
            target=b"\x00" * 8,  # Broadcast
            res_required=True,
            ack_required=False,
        )

        request_time = time.monotonic()
        _LOGGER.debug(
            {
                "class": "_discover_with_packet",
                "method": "discover",
                "action": "broadcast_sent",
                "broadcast_address": broadcast_address,
                "port": port,
                "packet_type": type(packet).__name__,
                "expected_response": expected_response_type,
            }
        )
        await transport.send(message, send_address)

        idle_timeout = max_response_time * idle_timeout_multiplier
        deadline = IdleDeadline(timeout, idle_timeout)

        # Escalating re-broadcast schedule (DISC-01, D2-01): cumulative
        # offsets from request_time at which the same message is re-sent.
        # Read the module constant at runtime (not as a def-time default)
        # so tests can patch it for fast schedule-exhaustion coverage.
        tx_offsets = accumulate(DISCOVERY_REBROADCAST_GAPS)
        next_tx: float | None = next(tx_offsets, None)

        while True:
            if deadline.idle_expired:
                _LOGGER.debug(
                    {
                        "class": "_discover_with_packet",
                        "action": "idle_timeout",
                        "elapsed": time.monotonic() - deadline._last_response,
                    }
                )
                break

            if deadline.overall_expired:
                _LOGGER.debug(
                    {
                        "class": "_discover_with_packet",
                        "action": "overall_timeout",
                        "elapsed": time.monotonic() - deadline._start,
                    }
                )
                break

            now = time.monotonic()
            while next_tx is not None and now - request_time >= next_tx:
                _LOGGER.debug(
                    {
                        "class": "_discover_with_packet",
                        "method": "discover",
                        "action": "rebroadcast_sent",
                        "offset": next_tx,
                        "broadcast_address": broadcast_address,
                        "port": port,
                    }
                )
                await transport.send(message, send_address)
                next_tx = next(tx_offsets, None)
                now = time.monotonic()

            remaining = deadline.remaining()
            if remaining <= 0:
                break

            if next_tx is not None:
                remaining = min(remaining, request_time + next_tx - now)

            try:
                data, addr = await transport.receive(timeout=remaining)
                response_timestamp = time.monotonic()
            except LifxTimeoutError:
                continue
            except LifxProtocolError as e:
                # Size-invalid datagram from a hostile or broken sender — skip
                # it, never abort discovery (DoS protection contract). DEBUG
                # level only: per-packet WARNING logging on a hostile network
                # would itself be a flooding vector (D-02 rationale), and the
                # transport already logs the size violation.
                _LOGGER.debug(
                    {
                        "class": "_discover_with_packet",
                        "action": "invalid_packet_size",
                        "reason": str(e),
                    }
                )
                continue

            try:
                header, payload = parse_message(data)

                # Validate source
                if header.source != discovery_source:
                    continue

                # Check for expected response type
                if header.pkt_type != expected_response_type:
                    _LOGGER.debug(
                        {
                            "class": "_discover_with_packet",
                            "action": "unexpected_packet_type",
                            "expected": expected_response_type,
                            "received": header.pkt_type,
                        }
                    )
                    continue

                # Reject broadcast/multicast serials (D-01, D-02). The
                # multicast bit check also covers the all-0xff broadcast
                # target; the all-zeros target is the LIFX broadcast address
                # used by the discovery request itself and is never a valid
                # device serial. The two trailing bytes of the 8-byte target
                # are protocol padding and MUST be zero — Serial.from_protocol
                # silently drops target[6:], so a malformed/spoofed response
                # with non-zero padding would otherwise normalise to a clean
                # serial and could win the per-serial dedup race against the
                # real device.
                if (
                    header.target[0] & 0x01
                    or header.target == b"\x00" * 8
                    or header.target[6:] != b"\x00\x00"
                ):
                    _LOGGER.debug(
                        {
                            "class": "_discover_with_packet",
                            "action": "invalid_serial",
                            "serial": header.target.hex(),
                            "source_ip": addr[0],
                        }
                    )
                    continue

                # Extract serial from header
                device_serial = Serial.from_protocol(header.target).to_string()

                # Look up the response packet class by type (O(1) registry lookup)
                response_packet_class = get_packet_class(header.pkt_type)

                if not response_packet_class:
                    _LOGGER.warning(
                        {
                            "class": "_discover_with_packet",
                            "action": "unknown_packet_type",
                            "pkt_type": header.pkt_type,
                        }
                    )
                    continue

                # Unpack the response packet
                response_packet = response_packet_class.unpack(payload)

                # A valid protocol response proves the network is active even
                # when its service or responder address is unusable. Reset the
                # idle window before those filtering decisions.
                deadline.mark_response()

                # GetService discovery: a device advertises one StateService per
                # service it supports, but only UDP carries an address we can
                # talk to. Ignore the others so they neither claim the serial
                # (first-wins dedup) nor supply a non-UDP port. The deserialiser
                # tolerates service values from newer firmware (falls back to a
                # raw int), so the comparison stays correct for unknown values.
                if isinstance(response_packet, DevicePackets.StateService):
                    if response_packet.service != DeviceService.UDP:
                        _LOGGER.debug(
                            {
                                "class": "_discover_with_packet",
                                "action": "ignored_non_udp_service",
                                "serial": device_serial,
                                "service": int(response_packet.service),
                            }
                        )
                        continue
                    endpoint_port = response_packet.port
                else:
                    # State packets without an advertised service port expose
                    # the datagram's source port to callers such as
                    # find_by_label(). Validate it before first-wins dedup so
                    # a malformed response cannot hide a later valid endpoint.
                    endpoint_port = addr[1]

                try:
                    validate_port(endpoint_port)
                except ValueError:
                    _LOGGER.debug(
                        {
                            "class": "_discover_with_packet",
                            "action": "ignored_invalid_endpoint_port",
                            "serial": device_serial,
                            "port": endpoint_port,
                        }
                    )
                    continue

                try:
                    responder_ip = host_from_sockaddr(
                        addr, fallback_ip=broadcast_address
                    )
                    validate_address(responder_ip, emit_warnings=False)
                except ValueError as error:
                    _LOGGER.debug(
                        {
                            "class": "_discover_with_packet",
                            "action": "ignored_invalid_responder_address",
                            "serial": device_serial,
                            "reason": str(error),
                        }
                    )
                    continue

                # Extract all fields into a dict
                response_payload = response_packet.as_dict

                # Calculate response time
                response_time = response_timestamp - request_time

                # Create discovery response. port is the device's actual source
                # port (addr[1]), not the broadcast destination parameter — this
                # is the only truthful port for State responses without a service
                # port field (e.g. StateLabel via find_by_label). WR-04.
                discovery_resp = DiscoveryResponse(
                    serial=device_serial,
                    ip=responder_ip,
                    port=addr[1],
                    response_time=response_time,
                    response_payload=response_payload,
                )

                # First-wins dedup: yield each serial at most once (D-04)
                if device_serial in seen_serials:
                    continue
                seen_serials.add(device_serial)

                _emit_discovery_event(
                    _observer,
                    source="udp",
                    stage="accepted",
                    raw_identity=device_serial,
                )

                yield discovery_resp

                # Control has come back from the consumer. Reset the idle timer
                # again so the consumer's own work does not count against the
                # idle window: api.discover() constructs a Device per yielded
                # response, and those requests carry a wall deadline several
                # times the idle window, so one slow or dead device would
                # otherwise expire discovery before later re-broadcast
                # responses are read.
                #
                # This is the second non-receive trigger for a reset (sends are
                # deliberately NOT one -- see the module's re-broadcast
                # rationale and test_send_does_not_reset_idle_window). The
                # invariant is "time we spend, not time the network spends,
                # never counts against the idle window".
                #
                # The overall deadline is untouched, and it -- not the idle
                # window -- is what bounds a slow consumer. Note that with the
                # default constants a single stalled request
                # (DEFAULT_REQUEST_TIMEOUT, 16 s) outlasts the whole discovery
                # window (DISCOVERY_TIMEOUT, 15 s), so a consumer that blocks
                # for a full request timeout still ends the sweep -- via the
                # overall deadline. Callers whose per-device work can approach
                # the request timeout should raise ``timeout`` accordingly.
                deadline.mark_response()

                _LOGGER.debug(
                    {
                        "class": "_discover_with_packet",
                        "action": "device_found",
                        "serial": device_serial,
                        "ip": addr[0],
                        "payload_keys": list(response_payload.keys()),
                    }
                )

            except LifxProtocolError as e:
                _LOGGER.warning(
                    {
                        "class": "_discover_with_packet",
                        "action": "malformed_response",
                        "reason": str(e),
                        "source_ip": addr[0],
                    },
                    exc_info=True,
                )
                continue
            except Exception as e:
                _LOGGER.error(
                    {
                        "class": "_discover_with_packet",
                        "action": "unexpected_error",
                        "error": str(e),
                        "source_ip": addr[0],
                    },
                    exc_info=True,
                )
                continue

        _LOGGER.debug(
            {
                "class": "_discover_with_packet",
                "action": "complete",
                "devices_found": len(seen_serials),
                "elapsed": time.monotonic() - start_time,
            }
        )


async def discover_devices(
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    *,
    _address_is_prevalidated: bool = False,
) -> AsyncGenerator[DiscoveredDevice, None]:
    """Discover LIFX devices on the local network.

    Sends a broadcast DeviceGetService packet and yields devices as they respond.
    The packet is re-broadcast several times on an escalating schedule within
    the discovery window, so devices behind a lossy access point that miss
    the first broadcast are still found. Implements DoS protection via
    timeout, source validation, and serial validation. Serial validation and
    per-serial deduplication are enforced inside ``_discover_with_packet``,
    so every caller of that shared generator benefits.

    Note:
        On a populated network, generator *completion* now typically takes
        longer than a single broadcast alone would: re-broadcasts continue
        for several seconds into the window, and the generator then waits
        out the ~4 s idle window (``max_response_time`` ×
        ``idle_timeout_multiplier``) after the last response -- still well
        inside ``DISCOVERY_TIMEOUT`` (15 s). Streaming consumers
        (``async for``) see the first devices at unchanged latency; only
        overall completion moves later, because later re-broadcasts
        legitimately keep finding new devices and resetting the idle
        window.

        The idle window measures network silence, not elapsed wall time:
        time the consumer spends inside the ``async for`` body is excluded,
        so a slow consumer no longer shortens the sweep. ``timeout``
        (default 15 s) is the bound that still applies to it.

    Args:
        timeout: Discovery timeout in seconds
        broadcast_address: Broadcast address to use
        port: UDP port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
        device_timeout: Request timeout set on discovered devices
        max_retries: Max retries per request set on discovered devices
        _address_is_prevalidated: Internal signal that caller advisories were
            already emitted for ``broadcast_address``

    Yields:
        DiscoveredDevice instances as they are discovered
        (deduplicated by serial number)

    Example:
        ```python
        # Process devices as they're discovered
        async for device in discover_devices(timeout=5.0):
            print(f"Found device: {device.serial} at {device.ip}:{device.port}")

        # Or collect all devices first
        devices = []
        async for device in discover_devices():
            devices.append(device)
        ```
    """
    observer = _current_discovery_observer()
    responses = _discover_with_packet(
        DevicePackets.GetService(),
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
        _address_is_prevalidated=_address_is_prevalidated,
        _observer=observer,
    )
    async with aclosing(responses):
        async for resp in responses:
            # Device's authoritative service port comes from the StateService
            # payload (D-05). resp.port is only the device's source port (addr[1]) —
            # prefer the reported service port here (Pitfall 2).
            device_port: int = resp.response_payload["port"]
            yield DiscoveredDevice(
                serial=resp.serial,
                ip=resp.ip,
                port=device_port,
                response_time=resp.response_time,
                timeout=device_timeout,
                max_retries=max_retries,
            )


async def discover_devices_shared(
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    *,
    _address_is_prevalidated: bool = False,
    _caller_deadline: float | None = None,
    _observer: _DiscoveryObserver | None = None,
) -> AsyncGenerator[DiscoveredDevice, None]:
    """Share one compatible active UDP sweep across enumeration callers.

    The coordinator eagerly drains the validated raw producer, so consumer
    pacing cannot shift its re-broadcast schedule or consume its idle window.
    A late compatible caller receives the producer's accepted prefix followed
    by its suffix, but never extends the producer-origin wire deadline. Its own
    caller-origin ``timeout`` independently bounds registration, replay,
    construction, and delivery.

    ``device_timeout`` and ``max_retries`` remain caller-specific. They are
    applied only after raw fan-out and therefore do not split a compatible wire
    sweep or leak one subscriber's settings into another.
    """
    validate_address(broadcast_address, emit_warnings=not _address_is_prevalidated)
    validate_port(port)
    caller_deadline = (
        time.monotonic() + max(0.0, timeout)
        if _caller_deadline is None
        else _caller_deadline
    )
    observer = _current_discovery_observer() if _observer is None else _observer
    key = _UdpSweepKey(
        broadcast_address=broadcast_address,
        port=port,
        timeout=timeout,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    )

    def _producer() -> AsyncGenerator[DiscoveryResponse, None]:
        return _discover_with_packet(
            DevicePackets.GetService(),
            timeout=timeout,
            broadcast_address=broadcast_address,
            port=port,
            max_response_time=max_response_time,
            idle_timeout_multiplier=idle_timeout_multiplier,
            _address_is_prevalidated=True,
            _observer=None,
        )

    responses = subscribe_udp_sweep(
        key,
        _producer,
        caller_deadline=caller_deadline,
        observer=observer,
    )
    async with aclosing(responses):
        async for resp in responses:
            if time.monotonic() >= caller_deadline:
                return
            device_port: int = resp.response_payload["port"]
            discovered = DiscoveredDevice(
                serial=resp.serial,
                ip=resp.ip,
                port=device_port,
                response_time=resp.response_time,
                timeout=device_timeout,
                max_retries=max_retries,
            )
            if time.monotonic() >= caller_deadline:
                return
            yield discovered
