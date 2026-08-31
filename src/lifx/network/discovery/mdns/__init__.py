"""mDNS/DNS-SD discovery for LIFX devices.

This module provides mDNS-based discovery using the _lifx._udp.local service type.
It uses only Python stdlib (no external dependencies).

Example:
    High-level API (device instances):
    ```python
    async for device in discover_devices_mdns():
        print(f"Found {type(device).__name__}: {device.serial}")
    ```
"""

from lifx.network.discovery.mdns.discovery import discover_devices_mdns
from lifx.network.discovery.mdns.dns import (
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
from lifx.network.discovery.mdns.transport import MdnsTransport

__all__ = [
    # Discovery functions
    "discover_devices_mdns",
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
