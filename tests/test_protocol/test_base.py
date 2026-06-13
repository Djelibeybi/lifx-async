"""Tests for protocol base module."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, ClassVar
from unittest.mock import patch

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

    def test_unpack_array_of_enums_tolerates_unknown(self) -> None:
        # Two service bytes: UDP(1) known, 5 unknown.
        pkt = _ArrayEnumPacket.unpack(b"\x01\x05")
        assert isinstance(pkt, _ArrayEnumPacket)
        assert pkt.services[0] == DeviceService.UDP
        # Unknown value falls back to the raw int instead of raising.
        assert pkt.services[1] == 5


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
