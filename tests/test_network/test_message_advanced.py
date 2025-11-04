"""Advanced tests for message module covering error paths and edge cases."""

from __future__ import annotations

import pytest

from lifx.exceptions import LifxProtocolError
from lifx.network.message import (
    MessageBuilder,
    create_message,
)
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Device


class TestMessageBuilderSequence:
    """Test MessageBuilder sequence handling."""

    def test_message_builder_sequence_increment(self) -> None:
        """Test that sequence increments properly."""
        builder = MessageBuilder(source=12345)

        assert builder.next_sequence() == 0

        builder.create_message(Device.GetService())
        assert builder.next_sequence() == 1

        builder.create_message(Device.GetService())
        assert builder.next_sequence() == 2

    def test_message_builder_sequence_wraparound(self) -> None:
        """Test sequence number wraps at 256."""
        builder = MessageBuilder(source=12345)
        builder._sequence = 255

        assert builder.next_sequence() == 255

        builder.create_message(Device.GetService())
        # Should wrap to 0
        assert builder.next_sequence() == 0

    def test_message_builder_sequence_in_header(self) -> None:
        """Test that sequence is correctly placed in header."""
        builder = MessageBuilder(source=12345)
        builder._sequence = 42

        message = builder.create_message(Device.GetService())
        header = LifxHeader.unpack(message[:36])

        assert header.sequence == 42

    def test_message_builder_custom_source(self) -> None:
        """Test MessageBuilder with custom source."""
        builder = MessageBuilder(source=99999)
        message = builder.create_message(Device.GetService())

        header = LifxHeader.unpack(message[:36])
        assert header.source == 99999

    def test_message_builder_random_source(self) -> None:
        """Test MessageBuilder generates random source."""
        builder1 = MessageBuilder()
        builder2 = MessageBuilder()

        # Should have different sources (extremely unlikely to be same)
        assert builder1.source != builder2.source


class TestCreateMessageErrors:
    """Test create_message error handling."""

    def test_create_message_no_pkt_type(self) -> None:
        """Test error when packet has no PKT_TYPE."""

        class InvalidPacket:
            pass

        with pytest.raises(LifxProtocolError, match="PKT_TYPE"):
            create_message(InvalidPacket())

    def test_create_message_with_ack_required(self) -> None:
        """Test creating message with ack_required flag."""
        packet = Device.GetService()
        message = create_message(packet, source=12345, ack_required=True)

        header = LifxHeader.unpack(message[:36])
        assert header.ack_required is True

    def test_create_message_without_ack_required(self) -> None:
        """Test creating message without ack_required flag."""
        packet = Device.GetService()
        message = create_message(packet, source=12345, ack_required=False)

        header = LifxHeader.unpack(message[:36])
        assert header.ack_required is False

    def test_create_message_with_res_required(self) -> None:
        """Test creating message with res_required flag."""
        packet = Device.GetService()
        message = create_message(packet, source=12345, res_required=True)

        header = LifxHeader.unpack(message[:36])
        assert header.res_required is True

    def test_create_message_without_res_required(self) -> None:
        """Test creating message without res_required flag."""
        packet = Device.GetService()
        message = create_message(packet, source=12345, res_required=False)

        header = LifxHeader.unpack(message[:36])
        assert header.res_required is False
