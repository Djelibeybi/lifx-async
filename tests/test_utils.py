"""Tests for Serial number utilities."""

from __future__ import annotations

import pytest

from lifx.protocol.models import Serial


class TestSerialFromString:
    """Test Serial.from_string() method."""

    def test_serial_from_string_basic(self):
        """Test creating Serial from basic string."""
        serial = Serial.from_string("d073d5123456")
        assert serial.value == b"\xd0\x73\xd5\x12\x34\x56"
        assert len(serial.value) == 6

    def test_serial_from_string_uppercase(self):
        """Test creating Serial from uppercase string."""
        serial = Serial.from_string("D073D5123456")
        assert serial.value == b"\xd0\x73\xd5\x12\x34\x56"

    def test_serial_from_string_with_colons(self):
        """Test creating Serial with colon separators."""
        serial = Serial.from_string("d0:73:d5:12:34:56")
        assert serial.value == b"\xd0\x73\xd5\x12\x34\x56"

    def test_serial_from_string_with_hyphens(self):
        """Test creating Serial with hyphen separators."""
        serial = Serial.from_string("d0-73-d5-12-34-56")
        assert serial.value == b"\xd0\x73\xd5\x12\x34\x56"

    def test_serial_from_string_with_spaces(self):
        """Test creating Serial with space separators."""
        serial = Serial.from_string("d0 73 d5 12 34 56")
        assert serial.value == b"\xd0\x73\xd5\x12\x34\x56"

    def test_serial_from_string_invalid_type(self):
        """Test that non-string raises TypeError."""
        with pytest.raises(TypeError, match="Serial must be a string"):
            Serial.from_string(123456)  # type: ignore

    def test_serial_from_string_wrong_length(self):
        """Test that wrong length raises ValueError."""
        with pytest.raises(ValueError, match="must be 12 hex characters"):
            Serial.from_string("d073d5")  # Too short

    def test_serial_from_string_invalid_hex(self):
        """Test that invalid hex characters raise ValueError."""
        with pytest.raises(ValueError, match="Invalid serial number format"):
            Serial.from_string("zzzzzzzzzzzz")


class TestSerialFromProtocol:
    """Test Serial.from_protocol() method."""

    def test_serial_from_protocol_basic(self):
        """Test creating Serial from protocol format."""
        serial = Serial.from_protocol(b"\xd0\x73\xd5\x12\x34\x56\x00\x00")
        assert serial.value == b"\xd0\x73\xd5\x12\x34\x56"
        assert len(serial.value) == 6

    def test_serial_from_protocol_wrong_length(self):
        """Test that wrong length raises ValueError."""
        with pytest.raises(ValueError, match="must be 8 bytes"):
            Serial.from_protocol(b"\xd0\x73\xd5\x12\x34\x56")  # Only 6 bytes


class TestSerialToString:
    """Test Serial.to_string() method."""

    def test_serial_to_string(self):
        """Test converting Serial to string."""
        serial = Serial(value=b"\xd0\x73\xd5\x12\x34\x56")
        assert serial.to_string() == "d073d5123456"

    def test_serial_to_string_from_protocol(self):
        """Test converting Serial from protocol to string."""
        serial = Serial.from_protocol(b"\xd0\x73\xd5\x12\x34\x56\x00\x00")
        assert serial.to_string() == "d073d5123456"


class TestSerialToProtocol:
    """Test Serial.to_protocol() method."""

    def test_serial_to_protocol(self):
        """Test converting Serial to protocol format."""
        serial = Serial.from_string("d073d5123456")
        result = serial.to_protocol()
        assert result == b"\xd0\x73\xd5\x12\x34\x56\x00\x00"
        assert len(result) == 8


class TestSerialStringRepresentation:
    """Test Serial string representations."""

    def test_serial_str(self):
        """Test __str__ returns hex string."""
        serial = Serial.from_string("d073d5123456")
        assert str(serial) == "d073d5123456"

    def test_serial_repr(self):
        """Test __repr__ returns detailed representation."""
        serial = Serial.from_string("d073d5123456")
        assert repr(serial) == "Serial('d073d5123456')"


class TestSerialValidation:
    """Test Serial validation."""

    def test_serial_invalid_type(self):
        """Test that non-bytes value raises TypeError."""
        with pytest.raises(TypeError, match="Serial value must be bytes"):
            Serial(value="d073d5123456")  # type: ignore

    def test_serial_wrong_length(self):
        """Test that wrong length raises ValueError."""
        with pytest.raises(ValueError, match="must be 6 bytes"):
            Serial(value=b"\xd0\x73\xd5")  # Only 3 bytes


class TestSerialRoundTrip:
    """Test round-trip conversions."""

    def test_from_string_to_string_roundtrip(self):
        """Test that from_string -> to_string is a roundtrip."""
        original = "d073d5123456"
        serial = Serial.from_string(original)
        back = serial.to_string()
        assert back == original.lower()

    def test_protocol_roundtrip(self):
        """Test that to_protocol -> from_protocol is a roundtrip."""
        original = "d073d5123456"
        serial1 = Serial.from_string(original)
        protocol = serial1.to_protocol()
        serial2 = Serial.from_protocol(protocol)
        assert serial2.to_string() == original.lower()

    def test_full_roundtrip(self):
        """Test full roundtrip: string -> Serial -> protocol -> Serial -> string."""
        original = "d073d5ABCDEF"

        # Create Serial from string
        serial1 = Serial.from_string(original)
        assert len(serial1.value) == 6

        # Convert to protocol format
        protocol = serial1.to_protocol()
        assert len(protocol) == 8

        # Create Serial from protocol
        serial2 = Serial.from_protocol(protocol)
        assert len(serial2.value) == 6

        # Convert back to string
        back_str = serial2.to_string()
        assert back_str == original.lower()


class TestSerialImmutability:
    """Test that Serial is immutable (frozen=True)."""

    def test_serial_is_frozen(self):
        """Test that Serial cannot be modified after creation."""
        serial = Serial.from_string("d073d5123456")
        with pytest.raises(Exception):  # FrozenInstanceError in Python 3.10+
            serial.value = b"\x00" * 6  # type: ignore
