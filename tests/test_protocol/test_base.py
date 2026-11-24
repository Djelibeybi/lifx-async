"""Tests for protocol base module."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, ClassVar
from unittest.mock import patch

import pytest

from lifx.protocol import packets
from lifx.protocol.base import Packet
from lifx.protocol.protocol_types import DeviceService


@dataclass
class _ArrayEnumPacket(Packet):
    """Synthetic packet with an array-of-enums field.

    No real LIFX packet currently carries an enum array, so this exercises the
    array-enum branch of the deserialiser directly — including its tolerance of
    values outside the known enum (newer firmware).
    """

    PKT_TYPE: ClassVar[int] = 60001
    _fields: ClassVar[list[dict[str, Any]]] = [
        {"name": "Services", "type": "[2]<DeviceService>", "size_bytes": 1},
    ]

    services: list[Any] = None  # type: ignore[assignment]


class TestArrayEnumDeserialisation:
    """Array-of-enums fields tolerate values outside the known enum."""

    def test_unpack_array_of_enums_tolerates_unknown(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Two service bytes: UDP(1) known, and 5, which the protocol reserves
        # and bulbs advertise in every StateService reply.
        with caplog.at_level(logging.DEBUG, logger="lifx.protocol.base"):
            pkt = _ArrayEnumPacket.unpack(b"\x01\x05")
        assert isinstance(pkt, _ArrayEnumPacket)
        assert pkt.services[0] == DeviceService.UDP
        # DeviceService is open: the value becomes a pseudo-member silently
        assert pkt.services[1] == 5
        assert isinstance(pkt.services[1], DeviceService)
        assert "Unknown" not in caplog.text


class TestPacketUnpackDebugGuard:
    """Tests for debug logging guard in Packet.unpack()."""

    def test_asdict_not_called_when_debug_disabled(self) -> None:
        """Verify asdict() is skipped when debug logging is disabled.

        The asdict() call deep-copies the entire packet for debug logging.
        When DEBUG is disabled (the common case), this overhead should be
        avoided entirely.
        """
        # LightGetPower has no fields — simplest packet to unpack
        packed = b""

        with patch("lifx.protocol.base.asdict") as mock_asdict:
            # Ensure DEBUG is disabled
            logger = logging.getLogger("lifx.protocol.base")
            original_level = logger.level
            logger.setLevel(logging.WARNING)
            try:
                packets.Light.GetPower.unpack(packed)
                mock_asdict.assert_not_called()
            finally:
                logger.setLevel(original_level)

    def test_asdict_called_when_debug_enabled(self) -> None:
        """Verify asdict() IS called when debug logging is enabled."""
        packed = b""

        with patch("lifx.protocol.base.asdict") as mock_asdict:
            mock_asdict.return_value = {}
            logger = logging.getLogger("lifx.protocol.base")
            original_level = logger.level
            logger.setLevel(logging.DEBUG)
            try:
                packets.Light.GetPower.unpack(packed)
                mock_asdict.assert_called_once()
            finally:
                logger.setLevel(original_level)


class TestPacketUnpackLogsNonSensitiveValues:
    """Packets without sensitive fields log their values unchanged."""

    def test_values_logged_verbatim(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="lifx.protocol.base"):
            packets.Device.SetLabel.unpack(b"kitchen".ljust(32, b"\0"))

        assert "kitchen" in caplog.text
        assert "<redacted>" not in caplog.text


class TestLabelFieldPacking:
    """State packets type labels as ``str``, so ``pack()`` must accept one."""

    def test_state_label_str_round_trips(self) -> None:
        packed = packets.Device.StateLabel(label="Kitchen").pack()

        assert packed == b"Kitchen".ljust(32, b"\x00")
        assert packets.Device.StateLabel.unpack(packed).label == "Kitchen"

    def test_state_group_str_round_trips(self) -> None:
        group = bytes(range(16))
        packed = packets.Device.StateGroup(
            group=group, label="Upstairs", updated_at=42
        ).pack()

        unpacked = packets.Device.StateGroup.unpack(packed)
        assert unpacked.group == group
        assert unpacked.label == "Upstairs"
        assert unpacked.updated_at == 42

    def test_state_color_str_round_trips(self) -> None:
        color = packets.Light.StateColor.unpack(bytes(52))
        color.label = "Desk"

        assert packets.Light.StateColor.unpack(color.pack()).label == "Desk"

    def test_set_label_still_accepts_bytes(self) -> None:
        packed = packets.Device.SetLabel(label=b"Hall").pack()

        assert packed == b"Hall".ljust(32, b"\x00")

    def test_str_label_is_encoded_as_utf8(self) -> None:
        packed = packets.Device.StateLabel(label="Café").pack()

        assert packed[:5] == "Café".encode()

    def test_overlong_str_label_truncates_on_a_character_boundary(self) -> None:
        # 31 ASCII bytes then a 2-byte character: a byte cut at 32 would
        # split the character and the label could no longer be decoded.
        label = "a" * 31 + "é"
        packed = packets.Device.StateLabel(label=label).pack()

        assert len(packed) == 32
        assert packets.Device.StateLabel.unpack(packed).label == "a" * 31
