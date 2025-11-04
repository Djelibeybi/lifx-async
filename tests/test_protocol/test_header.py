"""Tests for LIFX protocol header."""

import pytest

from lifx.protocol.header import LifxHeader


class TestLifxHeader:
    """Test LIFX header packing and unpacking."""

    def test_create_basic_header(self) -> None:
        """Test creating a basic header."""
        header = LifxHeader.create(
            pkt_type=2,
            source=0x12345678,
            payload_size=0,
        )

        assert header.pkt_type == 2
        assert header.source == 0x12345678
        assert header.size == 36  # Header only, no payload
        assert header.protocol == 1024
        assert header.target == b"\x00" * 8
        assert header.tagged is False
        assert header.res_required is True

    def test_create_with_payload(self) -> None:
        """Test creating a header with payload."""
        header = LifxHeader.create(
            pkt_type=101,
            source=0xABCDEF00,
            payload_size=16,
        )

        assert header.size == 52  # 36 + 16

    def test_create_tagged_header(self) -> None:
        """Test creating a tagged (broadcast) header."""
        header = LifxHeader.create(
            pkt_type=2,
            source=0x12345678,
            tagged=True,
        )

        assert header.tagged is True
        assert header.target == b"\x00" * 8

    def test_create_with_target(self) -> None:
        """Test creating a header with specific target."""
        target = b"\xd0\x73\xd5\x12\x34\x56\x00\x00"
        header = LifxHeader.create(
            pkt_type=101,
            source=0x12345678,
            target=target,
        )

        assert header.target == target
        assert header.tagged is False

    def test_pack_unpack_roundtrip(self) -> None:
        """Test packing and unpacking produces same header."""
        original = LifxHeader.create(
            pkt_type=101,
            source=0x12345678,
            target=b"\xd0\x73\xd5\x12\x34\x56\x00\x00",
            sequence=42,
            ack_required=True,
            res_required=True,
        )

        packed = original.pack()
        assert len(packed) == 36

        unpacked = LifxHeader.unpack(packed)

        assert unpacked.pkt_type == original.pkt_type
        assert unpacked.source == original.source
        assert unpacked.target == original.target
        assert unpacked.sequence == original.sequence
        assert unpacked.ack_required == original.ack_required
        assert unpacked.res_required == original.res_required
        assert unpacked.size == original.size
        assert unpacked.protocol == original.protocol
        assert unpacked.tagged == original.tagged

    def test_pack_size(self) -> None:
        """Test packed header is exactly 36 bytes."""
        header = LifxHeader.create(pkt_type=2, source=1)
        packed = header.pack()
        assert len(packed) == 36

    def test_unpack_short_data_raises(self) -> None:
        """Test unpacking too-short data raises ValueError."""
        with pytest.raises(ValueError, match="at least 36 bytes"):
            LifxHeader.unpack(b"\x00" * 20)

    def test_invalid_target_length_raises(self) -> None:
        """Test creating header with invalid target length raises."""
        with pytest.raises(ValueError, match="Target must be 6 or 8 bytes"):
            LifxHeader.create(
                pkt_type=2,
                source=1,
                target=b"\x00\x00",
            )

    def test_sequence_number(self) -> None:
        """Test sequence number handling."""
        header = LifxHeader.create(
            pkt_type=2,
            source=1,
            sequence=255,
        )

        assert header.sequence == 255

        packed = header.pack()
        unpacked = LifxHeader.unpack(packed)
        assert unpacked.sequence == 255

    def test_sequence_too_large_raises(self) -> None:
        """Test sequence number > 255 raises."""
        with pytest.raises(ValueError, match="Sequence must be 0-255"):
            LifxHeader.create(
                pkt_type=2,
                source=1,
                sequence=256,
            )

    def test_flags(self) -> None:
        """Test flag combinations."""
        test_cases = [
            (True, True),
            (True, False),
            (False, True),
            (False, False),
        ]

        for ack, res in test_cases:
            header = LifxHeader.create(
                pkt_type=2,
                source=1,
                ack_required=ack,
                res_required=res,
            )

            packed = header.pack()
            unpacked = LifxHeader.unpack(packed)

            assert unpacked.ack_required == ack
            assert unpacked.res_required == res

    def test_repr(self) -> None:
        """Test string representation."""
        header = LifxHeader.create(
            pkt_type=101,
            source=0x12345678,
            sequence=5,
        )

        repr_str = repr(header)
        assert "LifxHeader" in repr_str
        assert "type=101" in repr_str
        assert "seq=5" in repr_str
