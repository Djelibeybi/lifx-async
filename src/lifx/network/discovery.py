"""Device discovery for LIFX network."""

from __future__ import annotations

import logging
import secrets
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
from lifx.protocol.base import Packet
from lifx.protocol.models import Serial
from lifx.protocol.packets import Device as DevicePackets

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
        from lifx.devices.ceiling import CeilingLight
        from lifx.devices.hev import HevLight
        from lifx.devices.infrared import InfraredLight
        from lifx.devices.light import Light
        from lifx.devices.matrix import MatrixLight
        from lifx.devices.multizone import MultiZoneLight
        from lifx.products import is_ceiling_product

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
            await temp_device._ensure_capabilities()

            if temp_device.capabilities:
                # Check for Ceiling products first (before generic MatrixLight)
                if temp_device.version and is_ceiling_product(
                    temp_device.version.product
                ):
                    return CeilingLight(**kwargs)

                if temp_device.capabilities.has_matrix:
                    return MatrixLight(**kwargs)
                if temp_device.capabilities.has_multizone:
                    return MultiZoneLight(**kwargs)
                if temp_device.capabilities.has_infrared:
                    return InfraredLight(**kwargs)
                if temp_device.capabilities.has_hev:
                    return HevLight(**kwargs)
                if temp_device.capabilities.has_relays or (
                    temp_device.capabilities.has_buttons
                    and not temp_device.capabilities.has_color
                ):
                    return None

                return Light(**kwargs)

        except Exception:
            return None

        finally:
            # Always close the temporary device connection to prevent resource leaks
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
        port: Device UDP port
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

    Returns:
        List of DiscoveryResponse objects with unpacked response payloads

    Example:
        ```python
        # Find all devices and their labels
        responses = await _discover_with_packet(DevicePackets.GetLabel())
        for resp in responses:
            print(f"{resp.serial}: {resp.response_payload['Label']}")

        # Find only lights (filter out StateUnhandled)
        responses = await _discover_with_packet(LightPackets.Get())
        lights = [
            r
            for r in responses
            if r.response_payload.get("pkt_type") != StateUnhandled.PKT_TYPE
        ]
        ```
    """
    if not hasattr(packet, "STATE_TYPE"):
        raise ValueError(
            f"Packet {type(packet).__name__} must have STATE_TYPE attribute"
        )

    expected_response_type: int = getattr(packet, "STATE_TYPE")
    responses: dict[str, DiscoveryResponse] = {}
    start_time = time.time()

    async with UdpTransport(port=0, broadcast=True) as transport:
        # Allocate unique source for this discovery session
        discovery_source = secrets.randbelow(0xFFFFFFFF - 1) + 2

        message = create_message(
            packet=packet,
            source=discovery_source,
            sequence=_DEFAULT_SEQUENCE_START,
            target=b"\x00" * 8,  # Broadcast
            res_required=True,
            ack_required=False,
        )

        request_time = time.time()
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
        last_response_time = request_time

        while True:
            elapsed_since_last = time.time() - last_response_time

            if elapsed_since_last >= idle_timeout:
                _LOGGER.debug(
                    {
                        "class": "_discover_with_packet",
                        "action": "idle_timeout",
                        "elapsed": elapsed_since_last,
                    }
                )
                break

            if time.time() - request_time >= timeout:
                _LOGGER.debug(
                    {
                        "class": "_discover_with_packet",
                        "action": "overall_timeout",
                        "elapsed": time.time() - request_time,
                    }
                )
                break

            remaining_idle = idle_timeout - elapsed_since_last
            remaining_overall = timeout - (time.time() - request_time)
            remaining = min(remaining_idle, remaining_overall)

            try:
                data, addr = await transport.receive(timeout=remaining)
                response_timestamp = time.time()
            except LifxTimeoutError:
                break

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

                # Extract serial from header
                device_serial = Serial.from_protocol(header.target).to_string()

                # Dynamically get the response packet class and unpack
                # We need to find the packet class that matches this pkt_type
                from lifx.protocol import packets as all_packets

                response_packet_class = None
                for category_name in dir(all_packets):
                    category = getattr(all_packets, category_name)
                    if not hasattr(category, "__dict__"):
                        continue
                    for packet_name in dir(category):
                        pkt_class = getattr(category, packet_name)
                        if (
                            hasattr(pkt_class, "PKT_TYPE")
                            and pkt_class.PKT_TYPE == header.pkt_type
                        ):
                            response_packet_class = pkt_class
                            break
                    if response_packet_class:
                        break

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

                # Create discovery response
                discovery_resp = DiscoveryResponse(
                    serial=device_serial,
                    ip=addr[0],
                    port=port,
                    response_time=response_time,
                    response_payload=response_payload,
                )

                yield discovery_resp

                responses[device_serial] = discovery_resp
                last_response_time = response_timestamp

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
                    }
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
                "devices_found": len(responses),
                "elapsed": time.time() - start_time,
            }
        )


def _parse_device_state_service(payload: bytes) -> tuple[int, int]:
    """Parse DeviceStateService payload.

    Args:
        payload: Payload bytes (at least 5 bytes)

    Returns:
        Tuple of (service, port)

    Raises:
        ProtocolError: If payload is invalid
    """
    import struct

    if len(payload) < 5:
        raise LifxProtocolError(
            f"DeviceStateService payload too short: {len(payload)} bytes"
        )

    # DeviceStateService structure:
    # - service: uint8 (1 byte)
    # - port: uint32 (4 bytes)
    service, port = struct.unpack("<BI", payload[:5])

    return service, port


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

    Args:
        timeout: Discovery timeout in seconds
        broadcast_address: Broadcast address to use
        port: UDP port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
        device_timeout: request timeout set on discovered devices
        max_retries: max retries per request set on discovered devices

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
    seen_serials: set[str] = set()
    packet_count = 0
    start_time = time.time()

    # Create transport with broadcast enabled
    async with UdpTransport(port=0, broadcast=True) as transport:
        # Allocate unique source for this discovery session
        discovery_source = secrets.randbelow(0xFFFFFFFF - 1) + 2

        # Create discovery message
        discovery_packet = DevicePackets.GetService()
        message = create_message(
            packet=discovery_packet,
            source=discovery_source,
            sequence=_DEFAULT_SEQUENCE_START,
            target=b"\x00" * 8,  # Broadcast
            res_required=True,
            ack_required=False,
        )

        # Send broadcast
        request_time = time.time()
        _LOGGER.debug(
            {
                "class": "discover_devices",
                "method": "discover",
                "action": "broadcast_sent",
                "broadcast_address": broadcast_address,
                "port": port,
                "max_timeout": timeout,
                "request_time": request_time,
            }
        )
        await transport.send(message, (broadcast_address, port))

        # Calculate idle timeout
        idle_timeout = max_response_time * idle_timeout_multiplier
        last_response_time = request_time

        # Collect responses with dynamic timeout
        while True:
            # Calculate elapsed time since last response
            elapsed_since_last = time.time() - last_response_time

            # Stop if we've been idle too long
            if elapsed_since_last >= idle_timeout:
                _LOGGER.debug(
                    {
                        "class": "discover_devices",
                        "method": "discover",
                        "action": "idle_timeout",
                        "idle_time": elapsed_since_last,
                        "idle_timeout": idle_timeout,
                    }
                )
                break

            # Stop if we've exceeded the overall timeout
            if time.time() - request_time >= timeout:
                _LOGGER.debug(
                    {
                        "class": "discover_devices",
                        "method": "discover",
                        "action": "overall_timeout",
                        "elapsed": time.time() - request_time,
                        "timeout": timeout,
                    }
                )
                break

            # Calculate remaining timeout (use the shorter of idle or overall timeout)
            remaining_idle = idle_timeout - elapsed_since_last
            remaining_overall = timeout - (time.time() - request_time)
            remaining = min(remaining_idle, remaining_overall)

            # Try to receive a packet
            try:
                data, addr = await transport.receive(timeout=remaining)
                response_timestamp = time.time()

            except LifxTimeoutError:
                # Timeout means no more responses within the idle period
                _LOGGER.debug(
                    {
                        "class": "discover_devices",
                        "method": "discover",
                        "action": "no_responses",
                    }
                )
                break

            # Increment packet counter for logging
            packet_count += 1

            try:
                # Parse message
                header, payload = parse_message(data)

                # Validate source matches expected source
                if header.source != discovery_source:
                    _LOGGER.debug(
                        {
                            "class": "discover_devices",
                            "method": "discover",
                            "action": "source_mismatch",
                            "expected_source": discovery_source,
                            "received_source": header.source,
                            "source_ip": addr[0],
                        }
                    )
                    continue

                # Check if this is a DeviceStateService response
                if header.pkt_type != DevicePackets.StateService.PKT_TYPE:
                    _LOGGER.debug(
                        {
                            "class": "discover_devices",
                            "method": "discover",
                            "action": "unexpected_packet_type",
                            "pkt_type": header.pkt_type,
                            "expected_type": DevicePackets.StateService.PKT_TYPE,
                            "source_ip": addr[0],
                        }
                    )
                    continue

                # Validate serial is not multicast/broadcast
                if header.target[0] & 0x01 or header.target == b"\xff" * 8:
                    _LOGGER.warning(
                        {
                            "warning": "Invalid serial number in discovery response",
                            "serial": header.target.hex(),
                            "source_ip": addr[0],
                        }
                    )
                    continue

                # Parse service info
                _service, device_port = _parse_device_state_service(payload)

                # Calculate accurate response time from this specific response
                response_time = response_timestamp - request_time

                # Convert 8-byte protocol serial to string
                device_serial = Serial.from_protocol(header.target).to_string()

                # Deduplicate by serial number and yield new devices immediately
                if device_serial not in seen_serials:
                    seen_serials.add(device_serial)

                    # Create device info
                    device = DiscoveredDevice(
                        serial=device_serial,
                        ip=addr[0],
                        port=device_port,
                        response_time=response_time,
                        timeout=device_timeout,
                        max_retries=max_retries,
                    )

                    _LOGGER.debug(
                        {
                            "class": "discover_devices",
                            "method": "discover",
                            "action": "device_found",
                            "serial": device.serial,
                            "ip": device.ip,
                            "port": device.port,
                            "response_time": response_time,
                        }
                    )

                    yield device

                # Update last response time for idle timeout calculation
                last_response_time = response_timestamp

            except LifxProtocolError as e:
                # Log malformed responses
                _LOGGER.warning(
                    {
                        "class": "discover_devices",
                        "method": "discover",
                        "action": "malformed_response",
                        "reason": str(e),
                        "source_ip": addr[0],
                        "packet_size": len(data),
                    },
                    exc_info=True,
                )
                continue
            except Exception as e:
                # Log unexpected errors
                _LOGGER.error(
                    {
                        "class": "discover_devices",
                        "method": "discover",
                        "action": "unexpected_error",
                        "error_details": str(e),
                        "source_ip": addr[0],
                    },
                    exc_info=True,
                )
                continue

        _LOGGER.debug(
            {
                "class": "discover_devices",
                "method": "discover",
                "action": "complete",
                "devices_found": len(seen_serials),
                "packets_processed": packet_count,
                "elapsed": time.time() - start_time,
            }
        )
