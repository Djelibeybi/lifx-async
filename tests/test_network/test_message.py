"""Tests for message protocol."""

import pytest

from lifx.exceptions import LifxProtocolError as ProtocolError
from lifx.network.message import create_message, parse_message
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Device, Light
from lifx.protocol.protocol_types import LightHsbk


class TestPackPacket:
    """Test packet packing."""

    def test_pack_empty_packet(self) -> None:
        """Test packing a packet with no fields."""
        packet = Device.GetService()
        payload = packet.pack()
        assert payload == b""  # Empty packet

    def test_pack_packet_with_int(self) -> None:
        """Test packing a packet with integer field."""
        packet = Device.SetPower(level=65535)
        payload = packet.pack()
        assert len(payload) == 2  # uint16

    def test_pack_packet_with_hsbk(self) -> None:
        """Test packing a packet with HSBK field."""
        color = LightHsbk(hue=32768, saturation=65535, brightness=32768, kelvin=3500)
        packet = Light.SetColor(color=color, duration=1)
        payload = packet.pack()
        # color (8) + duration (4) + reserved = 13 bytes
        assert len(payload) == 13


class TestCreateMessage:
    """Test message creation."""

    def test_create_message_basic(self) -> None:
        """Test creating a basic message."""
        packet = Device.GetService()
        message = create_message(packet, source=12345)

        # Should have header (36 bytes) + empty payload
        assert len(message) == 36

        # Parse and verify header
        header = LifxHeader.unpack(message[:36])
        assert header.pkt_type == Device.GetService.PKT_TYPE
        assert header.source == 12345
        assert header.target == b"\x00" * 8
        assert header.size == 36

    def test_create_message_with_target(self) -> None:
        """Test creating message with specific target."""
        packet = Device.GetLabel()
        target_mac = b"\xd0\x73\xd5\x00\x12\x34\x00\x00"
        message = create_message(packet, source=12345, target=target_mac)

        header = LifxHeader.unpack(message[:36])
        assert header.target == target_mac
        assert not header.tagged  # Not broadcast

    def test_create_message_broadcast(self) -> None:
        """Test creating broadcast message."""
        packet = Device.GetService()
        message = create_message(packet, source=12345, target=b"\x00" * 8)

        header = LifxHeader.unpack(message[:36])
        assert header.tagged  # Broadcast

    def test_create_message_with_payload(self) -> None:
        """Test creating message with payload."""
        packet = Device.SetPower(level=65535)
        message = create_message(packet, source=12345)

        # Header (36) + payload (at least 2 bytes for uint16)
        assert len(message) >= 38

        header = LifxHeader.unpack(message[:36])
        assert header.pkt_type == Device.SetPower.PKT_TYPE
        assert header.size == len(message)

    def test_create_message_sequence(self) -> None:
        """Test creating message with sequence number."""
        packet = Device.GetService()
        message = create_message(packet, source=12345, sequence=42)

        header = LifxHeader.unpack(message[:36])
        assert header.sequence == 42

    def test_create_message_flags(self) -> None:
        """Test creating message with ack/res flags."""
        packet = Device.GetService()
        message = create_message(
            packet, source=12345, ack_required=True, res_required=False
        )

        header = LifxHeader.unpack(message[:36])
        assert header.ack_required
        assert not header.res_required


class TestParseMessage:
    """Test message parsing."""

    def test_parse_valid_message(self) -> None:
        """Test parsing a valid message."""
        # Create a message first
        packet = Device.GetService()
        message = create_message(packet, source=12345)

        # Parse it back
        header, payload = parse_message(message)

        assert header.pkt_type == Device.GetService.PKT_TYPE
        assert header.source == 12345
        assert payload == b""  # Empty payload

    def test_parse_message_with_payload(self) -> None:
        """Test parsing message with payload."""
        packet = Device.SetPower(level=65535)
        message = create_message(packet, source=12345)

        header, payload = parse_message(message)

        assert header.pkt_type == Device.SetPower.PKT_TYPE
        assert len(payload) >= 2  # At least uint16 for level

    def test_parse_message_too_short(self) -> None:
        """Test parsing message that's too short."""
        with pytest.raises(ProtocolError):
            parse_message(b"too short")

    def test_parse_message_invalid_size(self) -> None:
        """Test parsing message with invalid size field."""
        # Create valid message then corrupt size
        packet = Device.GetService()
        message = bytearray(create_message(packet, source=12345))
        # Set size to be larger than actual message
        message[0] = 100
        message[1] = 0

        with pytest.raises(ProtocolError):
            parse_message(bytes(message))
