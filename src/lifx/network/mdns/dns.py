"""DNS wire format parser for mDNS discovery.

This module provides minimal DNS parsing for mDNS service discovery,
supporting PTR, SRV, A, and TXT record types.

Uses only Python stdlib (struct, socket).
"""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass, field
from typing import Any

# DNS record types
DNS_TYPE_A = 1
DNS_TYPE_PTR = 12
DNS_TYPE_TXT = 16
DNS_TYPE_AAAA = 28
DNS_TYPE_SRV = 33

# DNS classes
DNS_CLASS_IN = 1
DNS_CLASS_UNIQUE = 0x8001  # Cache flush bit set

# Type names for display
_TYPE_NAMES = {
    DNS_TYPE_A: "A",
    DNS_TYPE_PTR: "PTR",
    DNS_TYPE_TXT: "TXT",
    DNS_TYPE_AAAA: "AAAA",
    DNS_TYPE_SRV: "SRV",
}


@dataclass
class DnsHeader:
    """DNS message header (12 bytes).

    Attributes:
        id: Transaction ID (0 for mDNS)
        flags: DNS flags
        qd_count: Question count
        an_count: Answer count
        ns_count: Authority count
        ar_count: Additional count
    """

    id: int
    flags: int
    qd_count: int
    an_count: int
    ns_count: int
    ar_count: int

    @property
    def is_response(self) -> bool:
        """Check if this is a response (QR bit set)."""
        return bool(self.flags & 0x8000)

    @classmethod
    def parse(cls, data: bytes) -> DnsHeader:
        """Parse a DNS header from bytes.

        Args:
            data: At least 12 bytes of DNS header data

        Returns:
            Parsed DnsHeader

        Raises:
            ValueError: If data is too short
        """
        if len(data) < 12:
            raise ValueError(f"DNS header too short: {len(data)} bytes")
        id_, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", data[:12])
        return cls(id_, flags, qd, an, ns, ar)


@dataclass
class SrvData:
    """Parsed SRV record data.

    Attributes:
        priority: Service priority
        weight: Service weight
        port: Service port
        target: Target hostname
    """

    priority: int
    weight: int
    port: int
    target: str


@dataclass
class TxtData:
    """Parsed TXT record data.

    Attributes:
        strings: Raw TXT strings
        pairs: Key-value pairs parsed from strings containing '='
    """

    strings: list[str] = field(default_factory=list)
    pairs: dict[str, str] = field(default_factory=dict)


@dataclass
class DnsResourceRecord:
    """DNS resource record.

    Attributes:
        name: Record name
        rtype: Record type (A, PTR, TXT, SRV, etc.)
        rclass: Record class (usually IN)
        ttl: Time to live in seconds
        rdata: Raw record data bytes
        parsed_data: Parsed record data (type varies by rtype)
    """

    name: str
    rtype: int
    rclass: int
    ttl: int
    rdata: bytes
    parsed_data: Any = None

    @property
    def type_name(self) -> str:
        """Get human-readable record type name."""
        return _TYPE_NAMES.get(self.rtype, f"TYPE{self.rtype}")

    @property
    def cache_flush(self) -> bool:
        """Check if cache flush bit is set (mDNS unique)."""
        return bool(self.rclass & 0x8000)


@dataclass
class ParsedDnsResponse:
    """Parsed DNS response message.

    Attributes:
        header: DNS header
        records: All resource records (answers + authority + additional)
    """

    header: DnsHeader
    records: list[DnsResourceRecord]


def parse_name(data: bytes, offset: int) -> tuple[str, int]:
    """Parse a DNS name with compression pointer support.

    DNS names use length-prefixed labels, with 0xC0 prefix indicating
    compression pointers to earlier positions in the message.

    Args:
        data: Complete DNS message bytes
        offset: Starting offset in data

    Returns:
        Tuple of (parsed name, new offset after the name)

    Raises:
        ValueError: If name parsing fails
    """
    labels: list[str] = []
    original_offset = offset
    jumped = False
    max_jumps = 10  # Prevent infinite loops
    jumps = 0

    while True:
        if offset >= len(data):
            raise ValueError(f"DNS name parsing ran off end of data at offset {offset}")

        length = data[offset]

        # Check for compression pointer (top 2 bits set)
        if (length & 0xC0) == 0xC0:
            if offset + 1 >= len(data):
                raise ValueError("Compression pointer incomplete")
            # Pointer to earlier in message
            pointer = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                original_offset = offset + 2
            jumped = True
            offset = pointer
            jumps += 1
            if jumps > max_jumps:
                raise ValueError("Too many compression pointer jumps")
            continue

        offset += 1

        if length == 0:
            # End of name
            break

        if offset + length > len(data):
            raise ValueError(
                f"Label extends beyond data: offset={offset}, length={length}"
            )

        label = data[offset : offset + length].decode("utf-8", errors="replace")
        labels.append(label)
        offset += length

    name = ".".join(labels) if labels else "."
    final_offset = original_offset if jumped else offset

    return name, final_offset


def parse_txt_record(rdata: bytes) -> TxtData:
    """Parse TXT record data.

    TXT records contain one or more length-prefixed strings.
    LIFX uses key=value format in these strings.

    Args:
        rdata: TXT record data bytes

    Returns:
        Parsed TxtData with strings and key-value pairs
    """
    txt_data = TxtData()
    offset = 0

    while offset < len(rdata):
        str_len = rdata[offset]
        offset += 1
        if offset + str_len > len(rdata):
            break
        txt_str = rdata[offset : offset + str_len].decode("utf-8", errors="replace")
        txt_data.strings.append(txt_str)
        # Try to parse as key=value
        if "=" in txt_str:
            key, _, value = txt_str.partition("=")
            txt_data.pairs[key] = value
        offset += str_len

    return txt_data


def _parse_resource_record(data: bytes, offset: int) -> tuple[DnsResourceRecord, int]:
    """Parse a single DNS resource record.

    Args:
        data: Complete DNS message bytes
        offset: Starting offset of the record

    Returns:
        Tuple of (parsed record, new offset after the record)

    Raises:
        ValueError: If record parsing fails
    """
    name, offset = parse_name(data, offset)

    if offset + 10 > len(data):
        raise ValueError(f"Resource record header incomplete at offset {offset}")

    rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[offset : offset + 10])
    offset += 10

    if offset + rdlength > len(data):
        available = len(data) - offset
        raise ValueError(
            f"Resource record data incomplete: need {rdlength}, have {available}"
        )

    rdata = data[offset : offset + rdlength]
    offset += rdlength

    # Parse specific record types
    parsed_data: Any = None

    if rtype == DNS_TYPE_A and rdlength == 4:
        parsed_data = socket.inet_ntoa(rdata)

    elif rtype == DNS_TYPE_AAAA and rdlength == 16:
        parsed_data = socket.inet_ntop(socket.AF_INET6, rdata)

    elif rtype == DNS_TYPE_PTR:
        parsed_data, _ = parse_name(data, offset - rdlength)

    elif rtype == DNS_TYPE_SRV and rdlength >= 6:
        priority, weight, port = struct.unpack("!HHH", rdata[:6])
        target, _ = parse_name(data, offset - rdlength + 6)
        parsed_data = SrvData(priority, weight, port, target)

    elif rtype == DNS_TYPE_TXT:
        parsed_data = parse_txt_record(rdata)

    return DnsResourceRecord(name, rtype, rclass, ttl, rdata, parsed_data), offset


def parse_dns_response(data: bytes) -> ParsedDnsResponse:
    """Parse a complete DNS response message.

    Args:
        data: Complete DNS message bytes

    Returns:
        ParsedDnsResponse containing header and all records

    Raises:
        ValueError: If message parsing fails
    """
    header = DnsHeader.parse(data)
    offset = 12
    records: list[DnsResourceRecord] = []

    # Skip questions (we don't need them for responses)
    for _ in range(header.qd_count):
        _, offset = parse_name(data, offset)
        offset += 4  # QTYPE + QCLASS

    # Parse all resource records (answers, authority, additional)
    total_records = header.an_count + header.ns_count + header.ar_count
    for _ in range(total_records):
        record, offset = _parse_resource_record(data, offset)
        records.append(record)

    return ParsedDnsResponse(header, records)


def build_ptr_query(service: str) -> bytes:
    """Build an mDNS PTR query for a service type.

    Args:
        service: Service name (e.g., "_lifx._udp.local")

    Returns:
        DNS query packet bytes ready to send

    Example:
        >>> query = build_ptr_query("_lifx._udp.local")
        >>> # Send to 224.0.0.251:5353
    """
    # Header: ID=0 (mDNS), standard query, 1 question
    header = struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)

    # Question: service name, PTR type, IN class
    question = b""
    for label in service.split("."):
        question += bytes([len(label)]) + label.encode("utf-8")
    question += b"\x00"  # Root label
    question += struct.pack("!HH", DNS_TYPE_PTR, DNS_CLASS_IN)

    return header + question
