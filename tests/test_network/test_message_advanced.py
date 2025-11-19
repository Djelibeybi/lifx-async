"""Advanced tests for message module covering error paths and edge cases."""

from __future__ import annotations

import pytest

from lifx.exceptions import LifxProtocolError
from lifx.network.message import create_message
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Device


class TestCreateMessageErrors:
    """Test create_message error handling."""

    def test_create_message_no_pkt_type(self) -> None:
        """Test error when packet has no PKT_TYPE."""

        class InvalidPacket:
            pass

        with pytest.raises(LifxProtocolError, match="PKT_TYPE"):
            create_message(InvalidPacket(), source=12345)

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
