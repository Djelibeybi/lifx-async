#!/usr/bin/env python3
"""mDNS probe script to discover LIFX devices and dump their service records.

This script sends an mDNS query for _lifx._udp.local and displays all
responses including PTR, SRV, TXT, and A records.

When --verify is used, it instantiates actual device classes and queries
them to compare the mDNS 'cnt' field with actual zone/tile counts.

Usage:
    python scripts/mdns_probe.py [--timeout SECONDS] [--verify]

Requires lifx-async to be installed for product registry and device queries.
"""

from __future__ import annotations

import argparse
import asyncio
import socket
import struct
import sys
import time
from dataclasses import dataclass, field
from typing import Any

# Try to import lifx for device instantiation and verification
try:
    from lifx.devices.base import Device
    from lifx.devices.ceiling import CeilingLight
    from lifx.devices.hev import HevLight
    from lifx.devices.infrared import InfraredLight
    from lifx.devices.light import Light
    from lifx.devices.matrix import MatrixLight
    from lifx.devices.multizone import MultiZoneLight
    from lifx.products import get_product, is_ceiling_product

    HAVE_LIFX = True
except ImportError:
    HAVE_LIFX = False
    print(
        "Warning: lifx-async not available - verification disabled",
        file=sys.stderr,
    )

# mDNS constants
MDNS_ADDR = "224.0.0.251"
MDNS_PORT = 5353
LIFX_SERVICE = "_lifx._udp.local"

# DNS record types
DNS_TYPE_A = 1
DNS_TYPE_PTR = 12
DNS_TYPE_TXT = 16
DNS_TYPE_AAAA = 28
DNS_TYPE_SRV = 33
DNS_TYPE_ANY = 255

# DNS classes
DNS_CLASS_IN = 1
DNS_CLASS_UNIQUE = 0x8001  # Cache flush bit set

TYPE_NAMES = {
    DNS_TYPE_A: "A",
    DNS_TYPE_PTR: "PTR",
    DNS_TYPE_TXT: "TXT",
    DNS_TYPE_AAAA: "AAAA",
    DNS_TYPE_SRV: "SRV",
    DNS_TYPE_ANY: "ANY",
}


@dataclass
class DNSHeader:
    """DNS message header (12 bytes)."""

    id: int
    flags: int
    qd_count: int  # Question count
    an_count: int  # Answer count
    ns_count: int  # Authority count
    ar_count: int  # Additional count

    @property
    def is_response(self) -> bool:
        return bool(self.flags & 0x8000)

    @classmethod
    def parse(cls, data: bytes) -> DNSHeader:
        if len(data) < 12:
            raise ValueError(f"DNS header too short: {len(data)} bytes")
        id_, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", data[:12])
        return cls(id_, flags, qd, an, ns, ar)

    def __str__(self) -> str:
        return (
            f"DNSHeader(id=0x{self.id:04x}, "
            f"{'response' if self.is_response else 'query'}, "
            f"questions={self.qd_count}, answers={self.an_count}, "
            f"authority={self.ns_count}, additional={self.ar_count})"
        )


@dataclass
class DNSResourceRecord:
    """DNS resource record."""

    name: str
    rtype: int
    rclass: int
    ttl: int
    rdata: bytes
    parsed_data: Any = None

    @property
    def type_name(self) -> str:
        return TYPE_NAMES.get(self.rtype, f"TYPE{self.rtype}")

    def __str__(self) -> str:
        class_str = (
            "IN" if (self.rclass & 0x7FFF) == DNS_CLASS_IN else f"CLASS{self.rclass}"
        )
        cache_flush = " (cache-flush)" if self.rclass & 0x8000 else ""

        # Format parsed data nicely
        if self.parsed_data is not None:
            data_str = str(self.parsed_data)
        else:
            data_str = self.rdata.hex()

        type_str = self.type_name
        return f"{self.name} {self.ttl}s {class_str}{cache_flush} {type_str} {data_str}"


@dataclass
class SRVData:
    """Parsed SRV record data."""

    priority: int
    weight: int
    port: int
    target: str

    def __str__(self) -> str:
        return (
            f"priority={self.priority} weight={self.weight} "
            f"port={self.port} target={self.target}"
        )


@dataclass
class TXTData:
    """Parsed TXT record data."""

    strings: list[str] = field(default_factory=list)
    pairs: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.pairs:
            return " ".join(f"{k}={v}" for k, v in self.pairs.items())
        return " ".join(repr(s) for s in self.strings)


def parse_dns_name(data: bytes, offset: int) -> tuple[str, int]:
    """Parse a DNS name with compression pointer support.

    Returns (name, new_offset).
    """
    labels = []
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


def parse_resource_record(data: bytes, offset: int) -> tuple[DNSResourceRecord, int]:
    """Parse a DNS resource record.

    Returns (record, new_offset).
    """
    name, offset = parse_dns_name(data, offset)

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
    parsed_data = None

    if rtype == DNS_TYPE_A and rdlength == 4:
        parsed_data = socket.inet_ntoa(rdata)

    elif rtype == DNS_TYPE_AAAA and rdlength == 16:
        parsed_data = socket.inet_ntop(socket.AF_INET6, rdata)

    elif rtype == DNS_TYPE_PTR:
        parsed_data, _ = parse_dns_name(data, offset - rdlength)

    elif rtype == DNS_TYPE_SRV and rdlength >= 6:
        priority, weight, port = struct.unpack("!HHH", rdata[:6])
        target, _ = parse_dns_name(data, offset - rdlength + 6)
        parsed_data = SRVData(priority, weight, port, target)

    elif rtype == DNS_TYPE_TXT:
        txt_data = TXTData()
        txt_offset = 0
        while txt_offset < len(rdata):
            str_len = rdata[txt_offset]
            txt_offset += 1
            if txt_offset + str_len > len(rdata):
                break
            txt_str = rdata[txt_offset : txt_offset + str_len].decode(
                "utf-8", errors="replace"
            )
            txt_data.strings.append(txt_str)
            # Try to parse as key=value
            if "=" in txt_str:
                key, _, value = txt_str.partition("=")
                txt_data.pairs[key] = value
            txt_offset += str_len
        parsed_data = txt_data

    return DNSResourceRecord(name, rtype, rclass, ttl, rdata, parsed_data), offset


def parse_dns_message(data: bytes) -> tuple[DNSHeader, list[DNSResourceRecord]]:
    """Parse a complete DNS message.

    Returns (header, list of all resource records).
    """
    header = DNSHeader.parse(data)
    offset = 12
    records = []

    # Skip questions (we don't need them for responses)
    for _ in range(header.qd_count):
        _, offset = parse_dns_name(data, offset)
        offset += 4  # QTYPE + QCLASS

    # Parse all resource records (answers, authority, additional)
    total_records = header.an_count + header.ns_count + header.ar_count
    for _ in range(total_records):
        try:
            record, offset = parse_resource_record(data, offset)
            records.append(record)
        except ValueError as e:
            print(f"  Warning: Failed to parse record: {e}", file=sys.stderr)
            break

    return header, records


def build_mdns_query(service: str) -> bytes:
    """Build an mDNS PTR query for a service type."""
    # Header: ID=0 (mDNS), standard query, 1 question
    header = struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)

    # Question: service name, PTR type, IN class
    question = b""
    for label in service.split("."):
        question += bytes([len(label)]) + label.encode("utf-8")
    question += b"\x00"  # Root label
    question += struct.pack("!HH", DNS_TYPE_PTR, DNS_CLASS_IN)

    return header + question


def create_device_from_product_id(
    serial: str,
    ip: str,
    port: int,
    product_id: int,
) -> Device | None:
    """Create appropriate device class based on product ID."""
    if not HAVE_LIFX:
        return None

    product = get_product(product_id)
    kwargs = {"serial": serial, "ip": ip, "port": port}

    # Priority-based selection matching DiscoveredDevice.create_device()
    if is_ceiling_product(product_id):
        return CeilingLight(**kwargs)
    if product.has_matrix:
        return MatrixLight(**kwargs)
    if product.has_multizone:
        return MultiZoneLight(**kwargs)
    if product.has_infrared:
        return InfraredLight(**kwargs)
    if product.has_hev:
        return HevLight(**kwargs)
    if product.has_relays or (product.has_buttons and not product.has_color):
        return None
    return Light(**kwargs)


async def verify_device(
    device: Device,
    mdns_cnt: int,
) -> dict[str, Any]:
    """Query device to get actual zone/tile counts and compare with mDNS cnt."""
    result: dict[str, Any] = {
        "device_class": type(device).__name__,
        "mdns_cnt": mdns_cnt,
        "actual_count": None,
        "count_type": None,
        "match": None,
        "label": None,
    }

    try:
        async with device:
            # Get label
            result["label"] = await device.get_label()

            # Get zone/tile count based on device type
            # Check CeilingLight first (extends MatrixLight)
            if isinstance(device, CeilingLight):
                result["count_type"] = "tiles"
                chain = await device.get_device_chain()
                result["actual_count"] = len(chain)
            elif isinstance(device, MatrixLight):
                result["count_type"] = "tiles"
                chain = await device.get_device_chain()
                result["actual_count"] = len(chain)
            elif isinstance(device, MultiZoneLight):
                result["count_type"] = "zones"
                result["actual_count"] = await device.get_zone_count()
            else:
                result["count_type"] = "n/a (single zone)"
                result["actual_count"] = 1

            result["match"] = result["actual_count"] == mdns_cnt

    except Exception as e:
        result["error"] = str(e)

    return result


def create_mdns_socket() -> socket.socket:
    """Create a socket suitable for mDNS queries."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Try to set SO_REUSEPORT if available (Linux/macOS)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except (AttributeError, OSError):
        pass

    # Bind to mDNS port to receive responses
    try:
        sock.bind(("", MDNS_PORT))
    except OSError as e:
        print(f"Warning: Could not bind to port {MDNS_PORT}: {e}", file=sys.stderr)
        print(
            "Binding to ephemeral port instead (may miss some responses)",
            file=sys.stderr,
        )
        sock.bind(("", 0))

    # Join multicast group (bind to all interfaces for multicast reception)
    local_addr = socket.inet_aton("0.0.0.0")  # nosec B104
    mreq = struct.pack("4s4s", socket.inet_aton(MDNS_ADDR), local_addr)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    # Set multicast TTL
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)

    # Enable receiving our own multicast (useful for testing)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)

    sock.setblocking(False)

    return sock


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe for LIFX devices via mDNS and dump service records"
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=10.0,
        help="Discovery timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--service",
        "-s",
        type=str,
        default=LIFX_SERVICE,
        help=f"Service to query (default: {LIFX_SERVICE})",
    )
    parser.add_argument("--raw", action="store_true", help="Also dump raw packet hex")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Query devices to verify cnt field matches actual zone/tile count",
    )
    args = parser.parse_args()

    if args.verify and not HAVE_LIFX:
        print("Error: --verify requires lifx-async to be installed", file=sys.stderr)
        sys.exit(1)

    print(f"mDNS Probe for {args.service}")
    print(f"Timeout: {args.timeout}s")
    if args.verify:
        print("Verification: ENABLED")
    print("=" * 60)

    # Create socket
    sock = create_mdns_socket()

    # Build and send query
    query = build_mdns_query(args.service)
    print(f"\nSending PTR query for {args.service}...")
    if args.raw:
        print(f"Query packet ({len(query)} bytes): {query.hex()}")

    sock.sendto(query, (MDNS_ADDR, MDNS_PORT))

    # Collect responses
    print("\nListening for responses...\n")

    start_time = time.time()
    seen_sources: set[str] = set()
    response_count = 0

    # Collect device info for verification
    devices_to_verify: list[dict[str, Any]] = []

    while time.time() - start_time < args.timeout:
        remaining = args.timeout - (time.time() - start_time)
        if remaining <= 0:
            break

        try:
            sock.settimeout(min(remaining, 1.0))
            data, addr = sock.recvfrom(4096)
        except TimeoutError:
            continue
        except BlockingIOError:
            time.sleep(0.1)
            continue

        source = f"{addr[0]}:{addr[1]}"

        # Skip if we've seen this exact response (dedup)
        response_key = f"{source}:{data.hex()}"
        if response_key in seen_sources:
            continue
        seen_sources.add(response_key)

        try:
            header, records = parse_dns_message(data)

            # Only show responses (not our own query)
            if not header.is_response:
                continue

            # Filter for LIFX-related records
            lifx_records = [
                r
                for r in records
                if "lifx" in r.name.lower()
                or (r.parsed_data and "lifx" in str(r.parsed_data).lower())
            ]

            if not lifx_records and args.service in [LIFX_SERVICE]:
                # Also check if any record matches our service
                lifx_records = [
                    r for r in records if args.service.split(".")[0] in r.name.lower()
                ]

            if not lifx_records:
                continue

            response_count += 1
            print(f"Response #{response_count} from {source}")
            print(f"  {header}")

            if args.raw:
                print(f"  Raw ({len(data)} bytes): {data.hex()}")

            # Extract device info from records
            device_info: dict[str, Any] = {"ip": addr[0]}
            for record in records:
                if record.rtype == DNS_TYPE_SRV and record.parsed_data:
                    device_info["port"] = record.parsed_data.port
                elif record.rtype == DNS_TYPE_TXT and record.parsed_data:
                    txt = record.parsed_data
                    if hasattr(txt, "pairs"):
                        if "id" in txt.pairs:
                            device_info["serial"] = txt.pairs["id"]
                        if "p" in txt.pairs:
                            device_info["product_id"] = int(txt.pairs["p"])
                        if "cnt" in txt.pairs:
                            device_info["cnt"] = int(txt.pairs["cnt"])
                        if "fw" in txt.pairs:
                            device_info["firmware"] = txt.pairs["fw"]

            # Add product name if we have registry
            if HAVE_LIFX and "product_id" in device_info:
                product = get_product(device_info["product_id"])
                device_info["product_name"] = product.name
                device_info["has_multizone"] = product.has_multizone
                device_info["has_matrix"] = product.has_matrix

            # Print records
            print(
                f"  Records ({len(records)} total, {len(lifx_records)} LIFX-related):"
            )
            for record in records:
                prefix = "  >>> " if record in lifx_records else "      "
                print(f"{prefix}{record}")

            # Show extracted device info
            if device_info.get("product_name"):
                print(f"  Device: {device_info['product_name']}")
                print(f"    Serial: {device_info.get('serial', 'N/A')}")
                print(f"    Firmware: {device_info.get('firmware', 'N/A')}")
                print(f"    mDNS cnt: {device_info.get('cnt', 'N/A')}")
                if device_info.get("has_multizone"):
                    print("    Type: MultiZone (zones expected)")
                elif device_info.get("has_matrix"):
                    print("    Type: Matrix (tiles expected)")
                else:
                    print("    Type: Single zone light")

            # Store for verification
            if args.verify and all(
                k in device_info for k in ["serial", "ip", "port", "product_id", "cnt"]
            ):
                devices_to_verify.append(device_info)

            print()

        except Exception as e:
            print(f"Failed to parse response from {source}: {e}", file=sys.stderr)
            if args.raw:
                print(f"  Raw ({len(data)} bytes): {data.hex()}", file=sys.stderr)
            continue

    sock.close()

    print("=" * 60)
    print(f"Discovery complete. Found {response_count} LIFX-related response(s).")

    if response_count == 0:
        print("\nNo LIFX devices responded. Possible reasons:")
        print("  - No LIFX devices on the network")
        print("  - Devices don't support mDNS (older firmware)")
        print("  - Firewall blocking mDNS (UDP port 5353)")
        print("  - Network doesn't allow multicast")
        print("\nTry:")
        print("  - Power cycling a LIFX device (triggers announcement)")
        print("  - Running with --timeout 30 for longer wait")
        print("  - Checking firewall settings")

    # Run verification if requested
    if args.verify and devices_to_verify:
        print("\n" + "=" * 60)
        print("VERIFICATION: Querying devices to compare cnt with actual counts")
        print("=" * 60 + "\n")

        async def run_verification() -> None:
            for info in devices_to_verify:
                device = create_device_from_product_id(
                    serial=info["serial"],
                    ip=info["ip"],
                    port=info["port"],
                    product_id=info["product_id"],
                )
                if device is None:
                    print(f"  {info['serial']}: Skipped (relay/button device)")
                    continue

                result = await verify_device(device, info["cnt"])

                # Format output
                status = ""
                if result.get("error"):
                    status = f"ERROR: {result['error']}"
                elif result["match"]:
                    status = "MATCH"
                else:
                    status = "MISMATCH"

                print(f"  {info['serial']} ({info.get('product_name', 'Unknown')}):")
                print(f"    Label: {result.get('label', 'N/A')}")
                print(f"    Device class: {result['device_class']}")
                print(f"    mDNS cnt: {result['mdns_cnt']}")
                print(f"    Actual {result['count_type']}: {result['actual_count']}")
                print(f"    Status: {status}")
                print()

        asyncio.run(run_verification())

        print("=" * 60)
        print("Verification complete.")


if __name__ == "__main__":
    main()
