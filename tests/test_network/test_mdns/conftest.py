"""Test fixtures for mDNS tests."""

from __future__ import annotations

import struct

import pytest


@pytest.fixture
def sample_ptr_query() -> bytes:
    """Sample PTR query for _lifx._udp.local."""
    # Build a PTR query for _lifx._udp.local
    # Header: ID=0, standard query (flags=0), 1 question
    header = struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)

    # Question: _lifx._udp.local PTR IN
    question = (
        b"\x05_lifx"  # 5 bytes: "_lifx"
        b"\x04_udp"  # 4 bytes: "_udp"
        b"\x05local"  # 5 bytes: "local"
        b"\x00"  # Root label
        b"\x00\x0c"  # Type PTR (12)
        b"\x00\x01"  # Class IN (1)
    )
    return header + question


@pytest.fixture
def sample_txt_data() -> bytes:
    """Sample TXT record data in LIFX format."""
    # TXT data format: length-prefixed strings
    txt_strings = [
        "tm=1",
        "cm=0",
        "cnt=5",
        "ts=1753699325000000000",
        "fw=4.112",
        "p=222",
        "v=1",
        "id=d073d5882c19",
    ]

    data = b""
    for s in txt_strings:
        encoded = s.encode("utf-8")
        data += bytes([len(encoded)]) + encoded
    return data


@pytest.fixture
def sample_a_record_data() -> bytes:
    """Sample A record data for 192.168.19.185."""
    return bytes([192, 168, 19, 185])


@pytest.fixture
def sample_srv_data() -> bytes:
    """Sample SRV record data: priority=0, weight=0, port=56700, target=host.local."""
    # Priority, weight, port
    header = struct.pack("!HHH", 0, 0, 56700)
    # Target: host.local (compressed or not - for simplicity, uncompressed)
    target = b"\x04host\x05local\x00"
    return header + target


@pytest.fixture
def simple_dns_response() -> bytes:
    """A simple DNS response with one A record.

    This is a minimal valid mDNS response.
    """
    # Header: ID=0, response (0x8400), 0 questions, 1 answer
    header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)

    # Answer: test.local A 192.168.1.1
    name = b"\x04test\x05local\x00"  # "test.local"
    rr_header = struct.pack(
        "!HHIH",
        1,  # Type A
        1,  # Class IN
        120,  # TTL
        4,  # RDLength
    )
    rdata = bytes([192, 168, 1, 1])

    return header + name + rr_header + rdata


@pytest.fixture
def lifx_dns_response() -> bytes:
    """A realistic LIFX mDNS response with PTR, SRV, TXT, and A records.

    Simulates what a LIFX device would send in response to a PTR query.
    """
    # Header: ID=0, response (0x8400), 0 questions, 3 answers, 0 authority, 1 additional
    header = struct.pack("!HHHHHH", 0, 0x8400, 0, 3, 0, 1)

    # Build the message body
    body = b""

    # Answer 1: PTR record - _lifx._udp.local -> D073D5882C19._lifx._udp.local
    # Name: _lifx._udp.local (offset will be 12)
    body += b"\x05_lifx\x04_udp\x05local\x00"  # offset 12, ends at ~27
    ptr_name_offset = 12
    body += struct.pack("!HHIH", 12, 1, 4500, 0)  # PTR, IN, TTL, placeholder rdlength

    # PTR target: D073D5882C19._lifx._udp.local
    ptr_target = b"\x0cD073D5882C19"  # 12 chars
    # Use compression pointer to _lifx._udp.local
    ptr_target += struct.pack("!H", 0xC000 | ptr_name_offset)
    # Update rdlength
    body = body[:-2] + struct.pack("!H", len(ptr_target)) + ptr_target

    # Answer 2: SRV record - D073D5882C19._lifx._udp.local -> D073D5882C19.local
    # Build without compression for simplicity in test
    srv_name = b"\x0cD073D5882C19\x05_lifx\x04_udp\x05local\x00"
    body += srv_name
    body += struct.pack(
        "!HHIH", 33, 0x8001, 120, 0
    )  # SRV, cache-flush, TTL, placeholder
    srv_target = b"\x0cD073D5882C19\x05local\x00"
    srv_rdata = struct.pack("!HHH", 0, 0, 56700) + srv_target
    body = body[:-2] + struct.pack("!H", len(srv_rdata)) + srv_rdata

    # Answer 3: TXT record
    txt_name = b"\x0cD073D5882C19\x05_lifx\x04_udp\x05local\x00"
    body += txt_name
    txt_strings = [
        "tm=1",
        "cm=0",
        "cnt=5",
        "ts=1753699325000000000",
        "fw=4.112",
        "p=222",
        "v=1",
        "id=d073d5882c19",
    ]
    txt_rdata = b""
    for s in txt_strings:
        encoded = s.encode("utf-8")
        txt_rdata += bytes([len(encoded)]) + encoded
    body += struct.pack("!HHIH", 16, 0x8001, 4500, len(txt_rdata))  # TXT
    body += txt_rdata

    # Additional: A record - D073D5882C19.local -> 192.168.19.185
    a_name = b"\x0cD073D5882C19\x05local\x00"
    body += a_name
    body += struct.pack("!HHIH", 1, 0x8001, 120, 4)  # A record
    body += bytes([192, 168, 19, 185])

    return header + body
