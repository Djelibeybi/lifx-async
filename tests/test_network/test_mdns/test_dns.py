"""Tests for DNS wire format parser."""

from __future__ import annotations

import struct

import pytest

from lifx.network.mdns.dns import (
    DNS_TYPE_A,
    DNS_TYPE_PTR,
    DNS_TYPE_SRV,
    DNS_TYPE_TXT,
    DnsHeader,
    SrvData,
    TxtData,
    build_ptr_query,
    parse_dns_response,
    parse_name,
    parse_txt_record,
)


class TestDnsHeader:
    """Tests for DnsHeader parsing."""

    def test_parse_query_header(self) -> None:
        """Test parsing a query header."""
        # ID=0x1234, query (no QR bit), 1 question
        data = struct.pack("!HHHHHH", 0x1234, 0x0000, 1, 0, 0, 0)
        header = DnsHeader.parse(data)

        assert header.id == 0x1234
        assert header.is_response is False
        assert header.qd_count == 1
        assert header.an_count == 0

    def test_parse_response_header(self) -> None:
        """Test parsing a response header."""
        # ID=0, response (QR=1, AA=1), 0 questions, 3 answers, 0 auth, 2 additional
        data = struct.pack("!HHHHHH", 0, 0x8400, 0, 3, 0, 2)
        header = DnsHeader.parse(data)

        assert header.id == 0
        assert header.is_response is True
        assert header.qd_count == 0
        assert header.an_count == 3
        assert header.ns_count == 0
        assert header.ar_count == 2

    def test_parse_header_too_short(self) -> None:
        """Test that short data raises ValueError."""
        with pytest.raises(ValueError, match="too short"):
            DnsHeader.parse(b"\x00" * 10)


class TestParseName:
    """Tests for DNS name parsing."""

    def test_parse_simple_name(self) -> None:
        """Test parsing a simple name without compression."""
        # test.local
        data = b"\x04test\x05local\x00"
        name, offset = parse_name(data, 0)

        assert name == "test.local"
        assert offset == len(data)

    def test_parse_name_with_multiple_labels(self) -> None:
        """Test parsing a name with multiple labels."""
        # _lifx._udp.local
        data = b"\x05_lifx\x04_udp\x05local\x00"
        name, offset = parse_name(data, 0)

        assert name == "_lifx._udp.local"
        assert offset == len(data)

    def test_parse_name_with_compression(self) -> None:
        """Test parsing a name with compression pointer."""
        # First name at offset 0: test.local
        # Second name at offset X: foo -> pointer to offset 5 (local)
        data = b"\x04test\x05local\x00\x03foo\xc0\x05"
        #       0-4    5-10   11  12-15 16-17

        # Parse second name starting at offset 12
        name, offset = parse_name(data, 12)

        assert name == "foo.local"
        assert offset == 18  # After the compression pointer

    def test_parse_name_root(self) -> None:
        """Test parsing the root domain (just null byte)."""
        data = b"\x00"
        name, offset = parse_name(data, 0)

        assert name == "."
        assert offset == 1

    def test_parse_name_at_offset(self) -> None:
        """Test parsing a name starting at non-zero offset."""
        # Some prefix data, then test.local
        data = b"\x00\x00\x00\x04test\x05local\x00"
        name, offset = parse_name(data, 3)

        assert name == "test.local"
        assert offset == len(data)

    def test_parse_name_off_end(self) -> None:
        """Test that parsing off the end raises ValueError."""
        data = b"\x04test"  # Incomplete - missing rest of label and null
        with pytest.raises(ValueError):
            parse_name(data, 0)

    def test_parse_name_too_many_jumps(self) -> None:
        """Test that circular compression pointers are detected."""
        # Create circular pointer: points to itself
        data = b"\xc0\x00"  # Pointer at offset 0 pointing to offset 0
        with pytest.raises(ValueError, match="Too many"):
            parse_name(data, 0)

    def test_parse_name_compression_pointer_incomplete(self) -> None:
        """Test that incomplete compression pointer raises ValueError."""
        # Compression pointer prefix without second byte
        data = b"\xc0"  # Pointer prefix but missing second byte
        with pytest.raises(ValueError, match="Compression pointer incomplete"):
            parse_name(data, 0)

    def test_parse_name_label_extends_beyond_data(self) -> None:
        """Test that label extending beyond data raises ValueError."""
        # Label claims length of 10 but data is shorter
        data = b"\x0atest"  # Length 10 but only "test" follows
        with pytest.raises(ValueError, match="Label extends beyond data"):
            parse_name(data, 0)


class TestParseTxtRecord:
    """Tests for TXT record parsing."""

    def test_parse_lifx_txt(self, sample_txt_data: bytes) -> None:
        """Test parsing LIFX TXT record format."""
        result = parse_txt_record(sample_txt_data)

        assert isinstance(result, TxtData)
        assert "p=222" in result.strings
        assert "id=d073d5882c19" in result.strings
        assert result.pairs["p"] == "222"
        assert result.pairs["id"] == "d073d5882c19"
        assert result.pairs["fw"] == "4.112"
        assert result.pairs["cnt"] == "5"

    def test_parse_empty_txt(self) -> None:
        """Test parsing empty TXT data."""
        result = parse_txt_record(b"")
        assert result.strings == []
        assert result.pairs == {}

    def test_parse_single_string(self) -> None:
        """Test parsing TXT with single string."""
        data = b"\x05hello"
        result = parse_txt_record(data)

        assert result.strings == ["hello"]
        assert result.pairs == {}

    def test_parse_key_value_pair(self) -> None:
        """Test parsing TXT with key=value format."""
        data = b"\x09foo=hello"
        result = parse_txt_record(data)

        assert result.strings == ["foo=hello"]
        assert result.pairs["foo"] == "hello"

    def test_parse_empty_value(self) -> None:
        """Test parsing key with empty value."""
        data = b"\x04foo="
        result = parse_txt_record(data)

        assert result.pairs["foo"] == ""

    def test_parse_truncated_txt_data(self) -> None:
        """Test parsing TXT with truncated data (length exceeds available bytes)."""
        # Length says 10 but only 3 bytes follow
        data = b"\x0afoo"
        result = parse_txt_record(data)

        # Should handle gracefully by breaking early
        assert result.strings == []


class TestBuildPtrQuery:
    """Tests for building PTR queries."""

    def test_build_lifx_query(self) -> None:
        """Test building a query for _lifx._udp.local."""
        query = build_ptr_query("_lifx._udp.local")

        # Should be a valid DNS query
        header = DnsHeader.parse(query)
        assert header.id == 0  # mDNS uses ID=0
        assert header.is_response is False
        assert header.qd_count == 1

        # Parse the question
        name, offset = parse_name(query, 12)
        assert name == "_lifx._udp.local"

        # Check QTYPE and QCLASS
        qtype, qclass = struct.unpack("!HH", query[offset : offset + 4])
        assert qtype == DNS_TYPE_PTR
        assert qclass == 1  # IN

    def test_build_custom_service_query(self) -> None:
        """Test building a query for a custom service."""
        query = build_ptr_query("_http._tcp.local")

        name, _ = parse_name(query, 12)
        assert name == "_http._tcp.local"


class TestParseDnsResponse:
    """Tests for complete DNS response parsing."""

    def test_parse_simple_response(self, simple_dns_response: bytes) -> None:
        """Test parsing a simple DNS response with one A record."""
        result = parse_dns_response(simple_dns_response)

        assert result.header.is_response is True
        assert result.header.an_count == 1
        assert len(result.records) == 1

        record = result.records[0]
        assert record.name == "test.local"
        assert record.rtype == DNS_TYPE_A
        assert record.parsed_data == "192.168.1.1"

    def test_parse_lifx_response(self, lifx_dns_response: bytes) -> None:
        """Test parsing a realistic LIFX mDNS response."""
        result = parse_dns_response(lifx_dns_response)

        assert result.header.is_response is True
        # Should have PTR, SRV, TXT in answers + A in additional
        assert len(result.records) == 4

        # Find specific records by type
        ptr_records = [r for r in result.records if r.rtype == DNS_TYPE_PTR]
        srv_records = [r for r in result.records if r.rtype == DNS_TYPE_SRV]
        txt_records = [r for r in result.records if r.rtype == DNS_TYPE_TXT]
        a_records = [r for r in result.records if r.rtype == DNS_TYPE_A]

        assert len(ptr_records) == 1
        assert len(srv_records) == 1
        assert len(txt_records) == 1
        assert len(a_records) == 1

        # Check PTR record
        ptr = ptr_records[0]
        assert "_lifx._udp.local" in ptr.name
        assert "D073D5882C19" in ptr.parsed_data

        # Check SRV record
        srv = srv_records[0]
        assert isinstance(srv.parsed_data, SrvData)
        assert srv.parsed_data.port == 56700
        assert "D073D5882C19" in srv.parsed_data.target

        # Check TXT record
        txt = txt_records[0]
        assert isinstance(txt.parsed_data, TxtData)
        assert txt.parsed_data.pairs["p"] == "222"
        assert txt.parsed_data.pairs["id"] == "d073d5882c19"
        assert txt.parsed_data.pairs["fw"] == "4.112"

        # Check A record
        a = a_records[0]
        assert a.parsed_data == "192.168.19.185"

    def test_parse_response_header_only(self) -> None:
        """Test parsing a response with no records."""
        # Header only, 0 records
        data = struct.pack("!HHHHHH", 0, 0x8400, 0, 0, 0, 0)
        result = parse_dns_response(data)

        assert result.header.is_response is True
        assert len(result.records) == 0

    def test_cache_flush_bit(self, simple_dns_response: bytes) -> None:
        """Test that cache flush bit is correctly detected."""
        # Modify the simple response to set cache-flush bit
        # Class field is at offset after name + 2 bytes (type)
        # name "test.local\0" = 12 bytes, then type(2) + class(2)
        header_len = 12
        name_len = 12  # \x04test\x05local\x00
        class_offset = header_len + name_len + 2

        # Set cache-flush bit (0x8001 instead of 0x0001)
        modified = bytearray(simple_dns_response)
        modified[class_offset : class_offset + 2] = struct.pack("!H", 0x8001)

        result = parse_dns_response(bytes(modified))
        assert result.records[0].cache_flush is True


class TestParseResourceRecord:
    """Tests for _parse_resource_record edge cases."""

    def test_resource_record_header_incomplete(self) -> None:
        """Test parsing resource record with incomplete header."""
        from lifx.network.mdns.dns import _parse_resource_record

        # Name followed by incomplete header (less than 10 bytes)
        data = b"\x04test\x05local\x00" + b"\x00\x01"  # Only type, missing rest
        with pytest.raises(ValueError, match="Resource record header incomplete"):
            _parse_resource_record(data, 0)

    def test_resource_record_data_incomplete(self) -> None:
        """Test parsing resource record with incomplete rdata."""
        from lifx.network.mdns.dns import _parse_resource_record

        # Name + complete header + incomplete rdata
        name = b"\x04test\x05local\x00"
        # Type=A, Class=IN, TTL=120, RDLength=10 (but only 4 bytes available)
        rr_header = struct.pack("!HHIH", 1, 1, 120, 10)
        rdata = b"\xc0\xa8\x01\x01"  # Only 4 bytes, but rdlength says 10

        data = name + rr_header + rdata
        with pytest.raises(ValueError, match="Resource record data incomplete"):
            _parse_resource_record(data, 0)

    def test_aaaa_record_parsing(self) -> None:
        """Test parsing AAAA (IPv6) record."""
        from lifx.network.mdns.dns import DNS_TYPE_AAAA, _parse_resource_record

        # Build an AAAA record for ::1 (loopback)
        name = b"\x04test\x05local\x00"
        # Type=AAAA (28), Class=IN, TTL=120, RDLength=16
        rr_header = struct.pack("!HHIH", DNS_TYPE_AAAA, 1, 120, 16)
        # IPv6 loopback address ::1
        rdata = b"\x00" * 15 + b"\x01"

        data = name + rr_header + rdata
        record, offset = _parse_resource_record(data, 0)

        assert record.rtype == DNS_TYPE_AAAA
        assert record.parsed_data == "::1"


class TestParseDnsResponseQuestions:
    """Tests for parse_dns_response with questions."""

    def test_parse_response_with_questions(self) -> None:
        """Test parsing DNS response that includes questions."""
        # Header: ID=0, response, 1 question, 1 answer
        header = struct.pack("!HHHHHH", 0, 0x8400, 1, 1, 0, 0)

        # Question: test.local PTR IN
        question = b"\x04test\x05local\x00"
        question += struct.pack("!HH", DNS_TYPE_PTR, 1)

        # Answer: A record
        answer_name = b"\x04host\x05local\x00"
        answer_rr = struct.pack("!HHIH", 1, 1, 120, 4)
        answer_rdata = bytes([192, 168, 1, 1])

        data = header + question + answer_name + answer_rr + answer_rdata
        result = parse_dns_response(data)

        # Questions should be skipped, only answers in records
        assert result.header.qd_count == 1
        assert result.header.an_count == 1
        assert len(result.records) == 1
        assert result.records[0].rtype == 1  # A record


class TestDnsResourceRecord:
    """Tests for DnsResourceRecord properties."""

    def test_type_name_known(self) -> None:
        """Test type_name for known types."""
        from lifx.network.mdns.dns import DnsResourceRecord

        record = DnsResourceRecord("test.local", DNS_TYPE_A, 1, 120, b"")
        assert record.type_name == "A"

        record = DnsResourceRecord("test.local", DNS_TYPE_PTR, 1, 120, b"")
        assert record.type_name == "PTR"

        record = DnsResourceRecord("test.local", DNS_TYPE_TXT, 1, 120, b"")
        assert record.type_name == "TXT"

        record = DnsResourceRecord("test.local", DNS_TYPE_SRV, 1, 120, b"")
        assert record.type_name == "SRV"

    def test_type_name_unknown(self) -> None:
        """Test type_name for unknown types."""
        from lifx.network.mdns.dns import DnsResourceRecord

        record = DnsResourceRecord("test.local", 999, 1, 120, b"")
        assert record.type_name == "TYPE999"
