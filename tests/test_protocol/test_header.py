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


class TestThreadConnectionFlag:
    """Test the frame address thread_connection bit (byte 22, bit 3).

    LIFX documents byte 22 of the packet (byte 14 of the frame address) as
    res_required (bit 0), ack_required (bit 1), one reserved bit (bit 2),
    thread_connection (bit 3), then four reserved bits (bits 4-7).

    thread_connection is set by the device to report that the message was
    sent over a Thread connection, so it is an inbound-only observation:
    create() does not expose it and a client never asserts it.
    """

    FLAGS_OFFSET = 22
    THREAD_BIT = 0b1000

    def test_defaults_false(self) -> None:
        """A header built by create() never claims a Thread connection."""
        header = LifxHeader.create(pkt_type=2, source=1)

        assert header.thread_connection is False
        assert not (header.pack()[self.FLAGS_OFFSET] & self.THREAD_BIT)

    def test_unpack_reads_thread_bit(self) -> None:
        """An inbound packet with bit 3 set is reported as Thread-sent."""
        packed = bytearray(LifxHeader.create(pkt_type=2, source=1).pack())
        packed[self.FLAGS_OFFSET] |= self.THREAD_BIT

        assert LifxHeader.unpack(bytes(packed)).thread_connection is True

    def test_unpack_absent_thread_bit(self) -> None:
        """An inbound packet without bit 3 is not reported as Thread-sent."""
        packed = LifxHeader.create(pkt_type=2, source=1).pack()

        assert LifxHeader.unpack(packed).thread_connection is False

    def test_roundtrip_preserves_thread_connection(self) -> None:
        """pack() re-emits an observed thread_connection unchanged."""
        for thread_connection in (True, False):
            header = LifxHeader(
                size=LifxHeader.HEADER_SIZE,
                protocol=LifxHeader.PROTOCOL_NUMBER,
                source=1,
                target=b"\x00" * 6,
                tagged=False,
                ack_required=True,
                res_required=True,
                sequence=7,
                pkt_type=2,
                thread_connection=thread_connection,
            )

            unpacked = LifxHeader.unpack(header.pack())

            assert unpacked.thread_connection is thread_connection
            assert unpacked.ack_required is True
            assert unpacked.res_required is True

    def test_thread_bit_independent_of_other_flags(self) -> None:
        """thread_connection does not disturb res_required or ack_required."""
        for ack, res, thread in [
            (a, r, t)
            for a in (True, False)
            for r in (True, False)
            for t in (True, False)
        ]:
            header = LifxHeader(
                size=LifxHeader.HEADER_SIZE,
                protocol=LifxHeader.PROTOCOL_NUMBER,
                source=1,
                target=b"\x00" * 6,
                tagged=False,
                ack_required=ack,
                res_required=res,
                sequence=0,
                pkt_type=2,
                thread_connection=thread,
            )

            unpacked = LifxHeader.unpack(header.pack())

            assert unpacked.ack_required is ack
            assert unpacked.res_required is res
            assert unpacked.thread_connection is thread

    def test_reserved_bits_are_not_emitted(self) -> None:
        """pack() leaves reserved bits 2 and 4-7 of the flags byte zero."""
        header = LifxHeader(
            size=LifxHeader.HEADER_SIZE,
            protocol=LifxHeader.PROTOCOL_NUMBER,
            source=1,
            target=b"\x00" * 6,
            tagged=False,
            ack_required=True,
            res_required=True,
            sequence=0,
            pkt_type=2,
            thread_connection=True,
        )

        assert header.pack()[self.FLAGS_OFFSET] == 0b1011

    def test_reserved_bits_are_ignored_on_unpack(self) -> None:
        """Reserved bits set by a peer do not corrupt the parsed flags."""
        packed = bytearray(LifxHeader.create(pkt_type=2, source=1).pack())
        packed[self.FLAGS_OFFSET] |= 0b1111_0100

        unpacked = LifxHeader.unpack(bytes(packed))

        assert unpacked.res_required is True
        assert unpacked.ack_required is False
        assert unpacked.thread_connection is False

    def test_repr_reports_thread_connection(self) -> None:
        """The header repr surfaces the Thread observation for debugging."""
        packed = bytearray(LifxHeader.create(pkt_type=2, source=1).pack())
        packed[self.FLAGS_OFFSET] |= self.THREAD_BIT

        assert "thread=True" in repr(LifxHeader.unpack(bytes(packed)))


class TestHeaderValidation:
    """Test the header's rejection of malformed frames."""

    def _valid_header(self) -> LifxHeader:
        return LifxHeader.create(pkt_type=2, source=1)

    def test_wrong_protocol_number_raises(self) -> None:
        """A header must carry the LIFX protocol number."""
        with pytest.raises(ValueError, match="Protocol must be 1024"):
            LifxHeader(
                size=LifxHeader.HEADER_SIZE,
                protocol=1023,
                source=1,
                target=b"\x00" * 6,
                tagged=False,
                ack_required=False,
                res_required=True,
                sequence=0,
                pkt_type=2,
            )

    def test_nonzero_origin_raises(self) -> None:
        """The origin bits (14-15 of the protocol field) must be zero."""
        packed = bytearray(self._valid_header().pack())
        packed[3] |= 0b0100_0000  # set origin bit 14

        with pytest.raises(ValueError, match="Invalid origin"):
            LifxHeader.unpack(bytes(packed))

    def test_unset_addressable_bit_raises(self) -> None:
        """The addressable bit (12 of the protocol field) must be set."""
        packed = bytearray(self._valid_header().pack())
        packed[3] &= ~0b0001_0000 & 0xFF  # clear addressable bit 12

        with pytest.raises(ValueError, match="Addressable bit must be set"):
            LifxHeader.unpack(bytes(packed))
