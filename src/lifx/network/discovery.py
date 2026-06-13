"""Device discovery for LIFX network."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lifx.const import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DISCOVERY_TIMEOUT,
    IDLE_TIMEOUT_MULTIPLIER,
    LIFX_UDP_PORT,
    MAX_RESPONSE_TIME,
)
from lifx.exceptions import LifxProtocolError, LifxTimeoutError
from lifx.network.message import create_message, parse_message
from lifx.network.transport import UdpTransport
from lifx.network.utils import IdleDeadline, allocate_source
from lifx.protocol.base import Packet
from lifx.protocol.models import Serial
from lifx.protocol.packets import Device as DevicePackets
from lifx.protocol.packets import get_packet_class

if TYPE_CHECKING:
    from lifx.devices.base import Device

_LOGGER = logging.getLogger(__name__)
_DEFAULT_SEQUENCE_START: int = 0


@dataclass
class DiscoveredDevice:
    """Information about a discovered LIFX device.

    Attributes:
        serial: Device serial number as 12-digit hex string (e.g., "d073d5123456")
        ip: Device IP address
        port: Device UDP port
        first_seen: Timestamp when device was first discovered
        response_time: Response time in seconds
    """

    serial: str
    ip: str
    port: int = LIFX_UDP_PORT
    timeout: float = DEFAULT_REQUEST_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    first_seen: float = field(default_factory=time.time)
    response_time: float = 0.0

    async def create_device(self) -> Device | None:
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
            LifxDeviceNotFoundError: If device doesn't respond
            LifxTimeoutError: If device query times out
            LifxProtocolError: If device returns invalid data

        Example:
            ```python
            devices = await discover_devices()
            for discovered in devices:
                device = await discovered.create_device()
                print(f"Created {type(device).__name__}: {await device.get_label()}")
            ```
        """
        from lifx.devices.base import Device
        from lifx.devices.detection import get_device_class_for_product
        from lifx.exceptions import LifxUnsupportedDeviceError

        kwargs = {
            "serial": self.serial,
            "ip": self.ip,
            "port": self.port,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }

        # Create temporary device to query version
        temp_device = Device(**kwargs)

        try:
            await temp_device.ensure_capabilities()

            if temp_device.capabilities and temp_device.version:
                device_class = get_device_class_for_product(
                    temp_device.version.product,
                    temp_device.capabilities,
                )
                return device_class(**kwargs)

        except LifxUnsupportedDeviceError:
            return None

        except Exception:
            return None

        finally:
            # Always close the temporary device connection
            await temp_device.connection.close()

        return None

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
        response_time: Response time in seconds
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
) -> AsyncGenerator[DiscoveryResponse]:
    """Generic discovery using any Get* packet.

    Broadcasts the specified packet and collects all State* responses.
    Uses the packet's STATE_TYPE attribute to validate expected responses.

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

    Note:
        The idle timer is reset before each response is yielded, so time the
        consumer spends processing a yielded response counts against the idle
        window. Slow consumers (e.g. performing network round trips per
        response) should pass a larger ``idle_timeout_multiplier``.

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

    async with UdpTransport(port=0, broadcast=True) as transport:
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
        await transport.send(message, (broadcast_address, port))

        idle_timeout = max_response_time * idle_timeout_multiplier
        deadline = IdleDeadline(timeout, idle_timeout)

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

            remaining = deadline.remaining()
            if remaining <= 0:
                break

            try:
                data, addr = await transport.receive(timeout=remaining)
                response_timestamp = time.monotonic()
            except LifxTimeoutError:
                break
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
                # device serial.
                if header.target[0] & 0x01 or header.target == b"\x00" * 8:
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
                    ip=addr[0],
                    port=addr[1],
                    response_time=response_time,
                    response_payload=response_payload,
                )

                # Reset idle timer on every valid protocol response, before dedup
                # check — a duplicate flood must not cause premature idle expiry
                # (Pitfall 1 / D-04).
                deadline.mark_response()

                # First-wins dedup: yield each serial at most once (D-04)
                if device_serial in seen_serials:
                    continue
                seen_serials.add(device_serial)

                yield discovery_resp

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
) -> AsyncGenerator[DiscoveredDevice, None]:
    """Discover LIFX devices on the local network.

    Sends a broadcast DeviceGetService packet and yields devices as they respond.
    Implements DoS protection via timeout, source validation, and serial validation.
    Serial validation and per-serial deduplication are enforced inside
    ``_discover_with_packet``, so every caller of that shared generator benefits.

    Args:
        timeout: Discovery timeout in seconds
        broadcast_address: Broadcast address to use
        port: UDP port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
        device_timeout: Request timeout set on discovered devices
        max_retries: Max retries per request set on discovered devices

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
    async for resp in _discover_with_packet(
        DevicePackets.GetService(),
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    ):
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
