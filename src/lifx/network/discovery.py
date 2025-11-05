"""Device discovery for LIFX network."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lifx.const import (
    DISCOVERY_TIMEOUT,
    IDLE_TIMEOUT_MULTIPLIER,
    LIFX_UDP_PORT,
    MAX_RESPONSE_TIME,
)
from lifx.exceptions import LifxProtocolError, LifxTimeoutError
from lifx.network.message import MessageBuilder, parse_message
from lifx.network.transport import UdpTransport
from lifx.protocol.models import Serial
from lifx.protocol.packets import Device as DevicePackets

if TYPE_CHECKING:
    from lifx.devices.base import Device

_LOGGER = logging.getLogger(__name__)


@dataclass
class DiscoveredDevice:
    """Information about a discovered LIFX device.

    Attributes:
        serial: Device serial number as 12-digit hex string (e.g., "d073d5123456")
        ip: Device IP address
        port: Device UDP port
        service: Service type (typically UDP=1)
        first_seen: Timestamp when device was first discovered
        response_time: Response time in seconds
    """

    serial: str
    ip: str
    port: int
    service: int
    first_seen: float = field(default_factory=time.time)
    response_time: float = 0.0

    async def create_device(self) -> Device:
        """Create appropriate device instance based on product capabilities.

        Queries the device for its product ID and firmware version, then
        instantiates the appropriate device class (Device, Light, MultiZoneLight,
        or TileDevice) based on the product capabilities.

        Returns:
            Device instance of the appropriate type

        Raises:
            DeviceNotFoundError: If device doesn't respond
            TimeoutError: If device query times out

        Example:
            ```python
            devices = await discover_devices()
            for discovered in devices:
                device = await discovered.create_device()
                print(f"Created {type(device).__name__}: {await device.get_label()}")
            ```
        """
        from lifx.devices.base import Device
        from lifx.devices.hev import HevLight
        from lifx.devices.infrared import InfraredLight
        from lifx.devices.light import Light
        from lifx.devices.multizone import MultiZoneLight
        from lifx.devices.tile import TileDevice
        from lifx.products import get_device_class_name

        # Create temporary device to query version (registry is always pre-loaded)
        temp_device = Device(serial=self.serial, ip=self.ip, port=self.port)

        try:
            version = await temp_device.get_version()
            pid = version.product

            # Get appropriate class name
            class_name = get_device_class_name(pid)

            # Instantiate the correct class
            if class_name == "TileDevice":
                device = TileDevice(serial=self.serial, ip=self.ip, port=self.port)
            elif class_name == "MultiZoneLight":
                device = MultiZoneLight(serial=self.serial, ip=self.ip, port=self.port)
            elif class_name == "HevLight":
                device = HevLight(serial=self.serial, ip=self.ip, port=self.port)
            elif class_name == "InfraredLight":
                device = InfraredLight(serial=self.serial, ip=self.ip, port=self.port)
            elif class_name == "Light":
                device = Light(serial=self.serial, ip=self.ip, port=self.port)
            else:
                device = temp_device

            return device

        except Exception:
            # If version query fails, default to Light
            device = Light(serial=self.serial, ip=self.ip, port=self.port)
            return device

    def __hash__(self) -> int:
        """Hash based on serial number for deduplication."""
        return hash(self.serial)

    def __eq__(self, other: object) -> bool:
        """Equality based on serial number."""
        if not isinstance(other, DiscoveredDevice):
            return False
        return self.serial == other.serial


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
) -> list[DiscoveredDevice]:
    """Discover LIFX devices on the local network.

    Sends a broadcast DeviceGetService packet and collects responses.
    Implements DoS protection via timeout, source validation, and serial validation.

    Args:
        timeout: Discovery timeout in seconds
        broadcast_address: Broadcast address to use
        port: UDP port to use (default LIFX_UDP_PORT)

    Returns:
        List of discovered devices (deduplicated by serial number)

    Example:
        ```python
        devices = await discover_devices(timeout=5.0)
        for device in devices:
            print(f"Found device: {device.serial} at {device.ip}:{device.port}")
        ```
    """
    devices: dict[str, DiscoveredDevice] = {}
    packet_count = 0
    start_time = time.time()

    # Create transport with broadcast enabled
    async with UdpTransport(port=0, broadcast=True) as transport:
        # Create discovery message
        builder = MessageBuilder()
        discovery_packet = DevicePackets.GetService()
        message = builder.create_message(
            packet=discovery_packet,
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
                if header.source != builder.source:
                    _LOGGER.debug(
                        {
                            "class": "discover_devices",
                            "method": "discover",
                            "action": "source_mismatch",
                            "expected_source": builder.source,
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
                service, device_port = _parse_device_state_service(payload)

                # Calculate accurate response time from this specific response
                response_time = response_timestamp - request_time

                # Convert 8-byte protocol serial to string
                device_serial = Serial.from_protocol(header.target).to_string()

                # Create device info
                device = DiscoveredDevice(
                    serial=device_serial,
                    ip=addr[0],
                    port=device_port,
                    service=service,
                    response_time=response_time,
                )

                # Deduplicate by serial number
                devices[device.serial] = device

                # Update last response time for idle timeout calculation
                last_response_time = response_timestamp

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
                "devices_found": len(devices),
                "packets_processed": packet_count,
                "elapsed": time.time() - start_time,
            }
        )

    return list(devices.values())


async def discover_device_by_ip(
    target_ip: str,
    timeout: float = 5.0,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
) -> DiscoveredDevice | None:
    """Discover a specific LIFX device by IP address.

    Args:
        target_ip: Target device IP address (IPv4 only)
        timeout: Discovery timeout in seconds
        broadcast_address: Broadcast address to use
        port: UDP port to use (default LIFX_UDP_PORT)

    Returns:
        DiscoveredDevice if found, None otherwise

    Example:
        ```python
        ip = "192.168.1.100"
        device = await discover_device_by_ip(ip, timeout=5.0)
        if device:
            print(f"Found device at {device.ip}:{device.port})
        ```
    """
    devices = await discover_devices(
        timeout=timeout, broadcast_address=broadcast_address, port=port
    )

    for device in devices:
        if device.ip == target_ip:
            return device

    return None


async def discover_device_by_serial(
    target_serial: str,
    timeout: float = 5.0,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
) -> DiscoveredDevice | None:
    """Discover a specific LIFX device by serial number.

    Args:
        target_serial: Target device serial number (string)
        timeout: Discovery timeout in seconds
        broadcast_address: Broadcast address to use
        port: UDP port to use (default LIFX_UDP_PORT)

    Returns:
        DiscoveredDevice if found, None otherwise

    Example:
        ```python
        serial = "d073d5123456"
        device = await discover_device_by_serial(serial, timeout=5.0)
        if device:
            print(f"Found device at {device.ip}:{device.port}")
        ```
    """
    devices = await discover_devices(
        timeout=timeout, broadcast_address=broadcast_address, port=port
    )

    for device in devices:
        if device.serial == target_serial:
            return device

    return None


# Deprecated alias for backward compatibility
async def discover_device_by_label(
    label: str,
    timeout: float = 5.0,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
) -> DiscoveredDevice | None:
    """Discover a LIFX device by label (name).

    Note: This requires querying all devices for their labels,
    so it may take longer than serial-based discovery.

    Args:
        label: Device label to search for
        timeout: Discovery timeout in seconds
        broadcast_address: Broadcast address to use
        port: UDP port to use (default LIFX_UDP_PORT)

    Returns:
        DiscoveredDevice if found, None otherwise

    Example:
        ```python
        device = await discover_device_by_label("Living Room", timeout=5.0)
        if device:
            print(f"Found device at {device.ip}:{device.port}")
        ```
    """
    from lifx.devices.base import Device
    from lifx.exceptions import LifxError

    # First discover all devices
    devices = await discover_devices(
        timeout=timeout, broadcast_address=broadcast_address, port=port
    )

    # Query each device for its label
    for discovered_device in devices:
        try:
            # Create a temporary device connection to query the label
            device = Device(
                serial=discovered_device.serial,
                ip=discovered_device.ip,
                port=discovered_device.port,
            )

            async with device:
                # Match label (case-insensitive)
                if device.label is not None:
                    if device.label[0].lower() == label.lower():
                        return discovered_device

        except (LifxError, TimeoutError):
            # Skip devices that don't respond or error out
            continue

    return None
