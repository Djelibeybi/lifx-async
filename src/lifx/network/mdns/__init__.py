"""Compatibility exports for the canonical discovery mDNS package."""

from lifx.network.discovery.mdns import (
    DnsHeader,
    DnsResourceRecord,
    MdnsTransport,
    ParsedDnsResponse,
    SrvData,
    TxtData,
    build_ptr_query,
    discover_devices_mdns,
    parse_dns_response,
    parse_name,
    parse_txt_record,
)

__all__ = [
    "discover_devices_mdns",
    "DnsHeader",
    "DnsResourceRecord",
    "ParsedDnsResponse",
    "SrvData",
    "TxtData",
    "build_ptr_query",
    "parse_dns_response",
    "parse_name",
    "parse_txt_record",
    "MdnsTransport",
]
