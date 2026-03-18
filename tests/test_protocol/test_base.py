"""Tests for protocol base module."""

from __future__ import annotations

import logging
from unittest.mock import patch

from lifx.protocol import packets


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
