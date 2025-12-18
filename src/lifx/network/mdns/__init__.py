"""mDNS/DNS-SD discovery for LIFX devices.

This module provides mDNS-based discovery using the _lifx._udp.local service type.
It uses only Python stdlib (no external dependencies).

Example:
    Low-level API (raw mDNS records):
    ```python
    async for record in discover_lifx_services():
        print(f"Found: {record.serial} at {record.ip}:{record.port}")
    ```

    High-level API (device instances):
    ```python
    async for device in discover_devices_mdns():
        print(f"Found {type(device).__name__}: {device.serial}")
    ```
"""

from lifx.network.mdns.discovery import (
    create_device_from_record,
    discover_devices_mdns,
    discover_lifx_services,
)
from lifx.network.mdns.dns import (
    DnsHeader,
    DnsResourceRecord,
    ParsedDnsResponse,
    SrvData,
    TxtData,
    build_ptr_query,
    parse_dns_response,
    parse_name,
    parse_txt_record,
)
from lifx.network.mdns.transport import MdnsTransport
from lifx.network.mdns.types import LifxServiceRecord

__all__ = [
    # Types
    "LifxServiceRecord",
    # Discovery functions
    "discover_lifx_services",
    "discover_devices_mdns",
    "create_device_from_record",
    # DNS parsing
    "DnsHeader",
    "DnsResourceRecord",
    "ParsedDnsResponse",
    "SrvData",
    "TxtData",
    "build_ptr_query",
    "parse_dns_response",
    "parse_name",
    "parse_txt_record",
    # Transport
    "MdnsTransport",
]
