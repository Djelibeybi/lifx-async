"""Adversarial tests for the DNS wire format parser.

These tests verify the parser fails safely on attacker-controlled input.
The mDNS DNS parser processes raw bytes received over multicast UDP from
any device on the LAN, making it a security-sensitive attack surface.
"""

from __future__ import annotations

import struct

import pytest

from lifx.network.mdns.dns import (
    _parse_resource_record,
    parse_dns_response,
    parse_name,
)


class TestMdnsParserAdversarial:
    """Adversarial input tests for the DNS parser."""

    def test_empty_packet_raises(self) -> None:
        """Empty packet (0 bytes) must raise ValueError or struct.error (T-H2)."""
        with pytest.raises((ValueError, struct.error)):
            parse_dns_response(b"")

    def test_truncated_header_raises(self) -> None:
        """Truncated header (<12 bytes) must raise cleanly (T-H2)."""
        for length in range(1, 12):
            with pytest.raises(ValueError, match="too short"):
                parse_dns_response(b"\x00" * length)

    def test_inflated_record_count_raises(self) -> None:
        """Header claims 65535 answers but only 12 bytes total (SEC-M2).

        Must raise ValueError before exhausting memory — the parser should
        fail on the first record parse attempt, not try to allocate 65535 records.
        """
        # Header: response flag, 0 questions, 65535 answers
        data = struct.pack("!HHHHHH", 0, 0x8400, 0, 0xFFFF, 0, 0)
        with pytest.raises(ValueError):
            parse_dns_response(data)

    def test_oversized_rdlength_raises(self) -> None:
        """Resource record claims rdlength=65535 but only 4 bytes follow (T-H2).

        Must raise ValueError about incomplete data.
        """
        # Build a minimal response with one record that has oversized rdlength
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
        name = b"\x04test\x05local\x00"
        # Type=A, Class=IN, TTL=120, RDLength=65535
        rr_header = struct.pack("!HHIH", 1, 1, 120, 0xFFFF)
        rdata = b"\xc0\xa8\x01\x01"  # Only 4 bytes

        data = header + name + rr_header + rdata
        with pytest.raises(ValueError, match="Resource record data incomplete"):
            parse_dns_response(data)

    def test_compression_pointer_chain_at_max_jumps(self) -> None:
        """Compression pointer chain at exactly max_jumps=10 resolves (T-H2).

        Builds a chain: ptr[0]->ptr[1]->...->ptr[9]->label, which is
        10 jumps. The parser allows up to 10 jumps, so this should succeed.
        """
        # Build a chain of 10 pointers, each pointing to the next
        # Final destination is a real label
        # Layout: [ptr0][ptr1]...[ptr9][label "ok" + null]
        # Each pointer is 2 bytes: 0xC0 | high_offset, low_offset
        chain_length = 10
        ptr_size = 2
        label = b"\x02ok\x00"  # "ok" label + null terminator

        # Calculate offsets: ptr[i] at offset i*2, label at offset chain_length*2
        data = bytearray()
        for i in range(chain_length):
            next_offset = (i + 1) * ptr_size
            data += struct.pack("!H", 0xC000 | next_offset)
        data += label

        name, _ = parse_name(bytes(data), 0)
        assert name == "ok"

    def test_compression_pointer_chain_exceeds_max_jumps(self) -> None:
        """Compression pointer chain at max_jumps+1=11 raises ValueError (T-H2)."""
        # Build a chain of 11 pointers — one more than allowed
        chain_length = 11
        ptr_size = 2
        label = b"\x02ok\x00"

        data = bytearray()
        for i in range(chain_length):
            next_offset = (i + 1) * ptr_size
            data += struct.pack("!H", 0xC000 | next_offset)
        data += label

        with pytest.raises(ValueError, match="Too many compression pointer jumps"):
            parse_name(bytes(data), 0)

    def test_circular_compression_pointer(self) -> None:
        """Circular compression pointer (points to itself) raises within limit (T-H2).

        Must not loop infinitely — should raise ValueError after max_jumps.
        """
        # Pointer at offset 0 pointing to offset 0
        data = b"\xc0\x00"
        with pytest.raises(ValueError, match="Too many"):
            parse_name(data, 0)

    def test_mutual_circular_pointers(self) -> None:
        """Two pointers pointing to each other must raise, not loop.

        Pointer at offset 0 -> offset 2, pointer at offset 2 -> offset 0.
        """
        data = b"\xc0\x02\xc0\x00"
        with pytest.raises(ValueError, match="Too many"):
            parse_name(data, 0)

    def test_malformed_utf8_in_label(self) -> None:
        """Malformed UTF-8 bytes in DNS label must not crash (T-H2).

        Parser should use errors='replace' and return a string with
        replacement characters instead of raising UnicodeDecodeError.
        """
        # Build a label with invalid UTF-8 bytes (0xFE, 0xFF are never valid)
        invalid_utf8 = bytes([0xFE, 0xFF, 0x80, 0x81])
        # Length-prefixed label: 4 bytes of invalid UTF-8
        data = bytes([len(invalid_utf8)]) + invalid_utf8 + b"\x00"

        name, offset = parse_name(data, 0)

        # Should not crash — name should contain replacement characters
        assert "\ufffd" in name  # Unicode replacement character
        assert offset == len(data)

    def test_forward_compression_pointer(self) -> None:
        """Compression pointer pointing forward in packet (SEC-L3).

        Forward pointers (pointing beyond current offset) are unusual but
        the parser should handle them without crash as long as they point
        within the data and don't exceed max_jumps.
        """
        # Layout: [ptr at 0 -> offset 2][label "fwd" at offset 2]
        label = b"\x03fwd\x00"
        ptr = struct.pack("!H", 0xC000 | 2)
        data = ptr + label

        name, _ = parse_name(data, 0)
        assert name == "fwd"

    def test_forward_pointer_beyond_data_raises(self) -> None:
        """Compression pointer pointing beyond data length must raise."""
        # Pointer to offset 100, but data is only 2 bytes
        data = struct.pack("!H", 0xC000 | 100)
        with pytest.raises(ValueError):
            parse_name(data, 0)

    def test_resource_record_with_zero_rdlength(self) -> None:
        """Resource record with rdlength=0 should parse without error.

        Some record types legitimately have zero-length rdata.
        """
        name = b"\x04test\x05local\x00"
        # Type=unknown(999), Class=IN, TTL=120, RDLength=0
        rr_header = struct.pack("!HHIH", 999, 1, 120, 0)
        data = name + rr_header

        record, end_offset = _parse_resource_record(data, 0)
        assert record.rdata == b""
        assert end_offset == len(data)

    def test_many_questions_with_no_answers(self) -> None:
        """Header claims many questions but no answers — should not crash.

        The parser skips questions by parsing their names. With valid
        question data this should succeed; with truncated data it should raise.
        """
        # Header: 2 questions, 0 answers
        header = struct.pack("!HHHHHH", 0, 0x8400, 2, 0, 0, 0)
        # Two valid questions
        q1 = b"\x04test\x05local\x00" + struct.pack("!HH", 1, 1)
        q2 = b"\x03foo\x05local\x00" + struct.pack("!HH", 1, 1)

        data = header + q1 + q2
        result = parse_dns_response(data)
        assert len(result.records) == 0
