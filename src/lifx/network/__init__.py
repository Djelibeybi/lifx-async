"""Network layer for LIFX device communication."""

from lifx.network.connection import ConnectionPool, DeviceConnection
from lifx.network.discovery import (
    DiscoveredDevice,
    discover_device_by_ip,
    discover_device_by_label,
    discover_device_by_serial,
    discover_devices,
)
from lifx.network.message import MessageBuilder, create_message, parse_message
from lifx.network.transport import UdpTransport

__all__ = [
    # Transport
    "UdpTransport",
    # Message
    "MessageBuilder",
    "create_message",
    "parse_message",
    # Discovery
    "DiscoveredDevice",
    "discover_devices",
    "discover_device_by_ip",
    "discover_device_by_serial",
    "discover_device_by_label",
    # Connection
    "DeviceConnection",
    "ConnectionPool",
]
