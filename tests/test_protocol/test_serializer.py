"""Tests for binary serializer."""

import pytest

from lifx.protocol.serializer import (
    FieldSerializer,
    get_type_size,
    pack_array,
    pack_bytes,
    pack_reserved,
    pack_string,
    pack_value,
    unpack_array,
    unpack_bytes,
    unpack_string,
    unpack_value,
)


class TestBasicSerialization:
    """Test basic value packing and unpacking."""

    def test_pack_uint8(self) -> None:
        """Test packing uint8."""
        data = pack_value(255, "uint8")
        assert data == b"\xff"
        assert len(data) == 1

    def test_pack_uint16(self) -> None:
        """Test packing uint16."""
        data = pack_value(0x1234, "uint16")
        assert data == b"\x34\x12"  # Little-endian
        assert len(data) == 2

    def test_pack_uint32(self) -> None:
        """Test packing uint32."""
        data = pack_value(0x12345678, "uint32")
        assert data == b"\x78\x56\x34\x12"  # Little-endian
        assert len(data) == 4

    def test_pack_uint64(self) -> None:
        """Test packing uint64."""
        data = pack_value(0x123456789ABCDEF0, "uint64")
        assert len(data) == 8

    def test_pack_float32(self) -> None:
        """Test packing float32."""
        data = pack_value(3.14, "float32")
        assert len(data) == 4

    def test_pack_bool(self) -> None:
        """Test packing bool."""
        true_data = pack_value(True, "bool")
        false_data = pack_value(False, "bool")
        assert len(true_data) == 1
        assert len(false_data) == 1
        assert true_data != false_data

    def test_pack_unknown_type_raises(self) -> None:
        """Test packing unknown type raises."""
        with pytest.raises(ValueError, match="Unknown type"):
            pack_value(42, "unknown_type")

    def test_unpack_uint8(self) -> None:
        """Test unpacking uint8."""
        value, offset = unpack_value(b"\xff\x00", "uint8", 0)
        assert value == 255
        assert offset == 1

    def test_unpack_uint16(self) -> None:
        """Test unpacking uint16."""
        value, offset = unpack_value(b"\x34\x12", "uint16", 0)
        assert value == 0x1234
        assert offset == 2

    def test_unpack_uint32(self) -> None:
        """Test unpacking uint32."""
        value, offset = unpack_value(b"\x78\x56\x34\x12", "uint32", 0)
        assert value == 0x12345678
        assert offset == 4

    def test_unpack_with_offset(self) -> None:
        """Test unpacking with offset."""
        data = b"\x00\x00\xff\x00"
        value, offset = unpack_value(data, "uint8", 2)
        assert value == 255
        assert offset == 3

    def test_unpack_short_data_raises(self) -> None:
        """Test unpacking from too-short data raises."""
        with pytest.raises(ValueError, match="Not enough data"):
            unpack_value(b"\x00", "uint16", 0)

    def test_roundtrip_values(self) -> None:
        """Test pack/unpack roundtrip for various types."""
        test_cases = [
            (123, "uint8"),
            (12345, "uint16"),
            (1234567890, "uint32"),
            (123456789012345, "uint64"),
            (-100, "int16"),
            (3.14159, "float32"),
            (True, "bool"),
            (False, "bool"),
        ]

        for original_value, type_name in test_cases:
            packed = pack_value(original_value, type_name)
            unpacked, _ = unpack_value(packed, type_name, 0)

            if type_name == "float32":
                # Float comparison with tolerance
                assert abs(unpacked - original_value) < 0.0001
            else:
                assert unpacked == original_value


class TestArraySerialization:
    """Test array packing and unpacking."""

    def test_pack_array_uint8(self) -> None:
        """Test packing uint8 array."""
        values = [1, 2, 3, 4, 5]
        data = pack_array(values, "uint8", 5)
        assert data == b"\x01\x02\x03\x04\x05"

    def test_pack_array_uint16(self) -> None:
        """Test packing uint16 array."""
        values = [0x1234, 0x5678]
        data = pack_array(values, "uint16", 2)
        assert data == b"\x34\x12\x78\x56"  # Little-endian

    def test_pack_array_wrong_count_raises(self) -> None:
        """Test packing array with wrong count raises."""
        with pytest.raises(ValueError, match="Expected 3 values, got 2"):
            pack_array([1, 2], "uint8", 3)

    def test_unpack_array_uint8(self) -> None:
        """Test unpacking uint8 array."""
        data = b"\x01\x02\x03\x04\x05"
        values, offset = unpack_array(data, "uint8", 5, 0)
        assert values == [1, 2, 3, 4, 5]
        assert offset == 5

    def test_unpack_array_uint16(self) -> None:
        """Test unpacking uint16 array."""
        data = b"\x34\x12\x78\x56"
        values, offset = unpack_array(data, "uint16", 2, 0)
        assert values == [0x1234, 0x5678]
        assert offset == 4

    def test_unpack_array_with_offset(self) -> None:
        """Test unpacking array with offset."""
        data = b"\xff\xff\x01\x02\x03"
        values, offset = unpack_array(data, "uint8", 3, 2)
        assert values == [1, 2, 3]
        assert offset == 5


class TestStringSerialization:
    """Test string packing and unpacking."""

    def test_pack_string_short(self) -> None:
        """Test packing string shorter than fixed length."""
        data = pack_string("hello", 10)
        assert len(data) == 10
        assert data.startswith(b"hello")
        assert data.endswith(b"\x00" * 5)  # Null-padded

    def test_pack_string_exact(self) -> None:
        """Test packing string exactly at fixed length."""
        data = pack_string("hello", 5)
        assert len(data) == 5
        assert data == b"hello"

    def test_pack_string_long(self) -> None:
        """Test packing string longer than fixed length."""
        data = pack_string("hello world", 5)
        assert len(data) == 5
        assert data == b"hello"  # Truncated

    def test_unpack_string(self) -> None:
        """Test unpacking string."""
        data = b"hello\x00\x00\x00\x00\x00"
        string, offset = unpack_string(data, 10, 0)
        assert string == "hello"
        assert offset == 10

    def test_unpack_string_no_null(self) -> None:
        """Test unpacking string without null terminator."""
        data = b"hello"
        string, offset = unpack_string(data, 5, 0)
        assert string == "hello"
        assert offset == 5

    def test_unpack_string_with_offset(self) -> None:
        """Test unpacking string with offset."""
        data = b"\xff\xff" + b"test\x00\x00"
        string, offset = unpack_string(data, 6, 2)
        assert string == "test"
        assert offset == 8


class TestReserved:
    """Test reserved field handling."""

    def test_pack_reserved(self) -> None:
        """Test packing reserved bytes."""
        data = pack_reserved(10)
        assert len(data) == 10
        assert data == b"\x00" * 10


class TestFieldSerializer:
    """Test structured field serialization."""

    def test_pack_field(self) -> None:
        """Test packing a structured field."""
        field_defs = {
            "HSBK": {
                "hue": "uint16",
                "saturation": "uint16",
                "brightness": "uint16",
                "kelvin": "uint16",
            }
        }

        serializer = FieldSerializer(field_defs)

        field_data = {
            "hue": 0x8000,
            "saturation": 0xFFFF,
            "brightness": 0x8000,
            "kelvin": 3500,
        }

        packed = serializer.pack_field(field_data, "HSBK")
        assert len(packed) == 8  # 4 × uint16

    def test_unpack_field(self) -> None:
        """Test unpacking a structured field."""
        field_defs = {
            "HSBK": {
                "hue": "uint16",
                "saturation": "uint16",
                "brightness": "uint16",
                "kelvin": "uint16",
            }
        }

        serializer = FieldSerializer(field_defs)

        # Pack then unpack
        field_data = {
            "hue": 0x8000,
            "saturation": 0xFFFF,
            "brightness": 0x8000,
            "kelvin": 3500,
        }

        packed = serializer.pack_field(field_data, "HSBK")
        unpacked, offset = serializer.unpack_field(packed, "HSBK", 0)

        assert unpacked == field_data
        assert offset == 8

    def test_get_field_size(self) -> None:
        """Test getting field size."""
        field_defs = {
            "HSBK": {
                "hue": "uint16",
                "saturation": "uint16",
                "brightness": "uint16",
                "kelvin": "uint16",
            }
        }

        serializer = FieldSerializer(field_defs)
        size = serializer.get_field_size("HSBK")
        assert size == 8

    def test_unknown_field_raises(self) -> None:
        """Test unknown field raises."""
        serializer = FieldSerializer({})

        with pytest.raises(ValueError, match="Unknown field"):
            serializer.pack_field({}, "UnknownField")

        with pytest.raises(ValueError, match="Unknown field"):
            serializer.unpack_field(b"", "UnknownField", 0)

        with pytest.raises(ValueError, match="Unknown field"):
            serializer.get_field_size("UnknownField")


class TestTypeSizes:
    """Test type size helpers."""

    def test_get_type_size(self) -> None:
        """Test getting type sizes."""
        assert get_type_size("uint8") == 1
        assert get_type_size("uint16") == 2
        assert get_type_size("uint32") == 4
        assert get_type_size("uint64") == 8
        assert get_type_size("float32") == 4
        assert get_type_size("bool") == 1

    def test_get_unknown_type_size_raises(self) -> None:
        """Test getting unknown type size raises."""
        with pytest.raises(ValueError, match="Unknown type"):
            get_type_size("unknown")


class TestUnpackValueErrors:
    """Test unpack_value error handling."""

    def test_unpack_unknown_type_raises(self) -> None:
        """Test unpacking unknown type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown type"):
            unpack_value(b"\x00\x00\x00\x00", "unknown_type", 0)


class TestBytesSerialization:
    """Test bytes packing and unpacking."""

    def test_pack_bytes_exact_length(self) -> None:
        """Test packing bytes with exact length."""
        data = pack_bytes(b"\x01\x02\x03\x04\x05", 5)
        assert data == b"\x01\x02\x03\x04\x05"
        assert len(data) == 5

    def test_pack_bytes_shorter_than_length(self) -> None:
        """Test packing bytes shorter than fixed length (padded with nulls)."""
        data = pack_bytes(b"\x01\x02\x03", 6)
        assert data == b"\x01\x02\x03\x00\x00\x00"
        assert len(data) == 6

    def test_pack_bytes_longer_than_length(self) -> None:
        """Test packing bytes longer than fixed length (truncated)."""
        data = pack_bytes(b"\x01\x02\x03\x04\x05\x06\x07\x08", 5)
        assert data == b"\x01\x02\x03\x04\x05"
        assert len(data) == 5

    def test_pack_bytes_empty(self) -> None:
        """Test packing empty bytes."""
        data = pack_bytes(b"", 4)
        assert data == b"\x00\x00\x00\x00"
        assert len(data) == 4

    def test_unpack_bytes(self) -> None:
        """Test unpacking bytes."""
        data = b"\x01\x02\x03\x04\x05\x06"
        result, offset = unpack_bytes(data, 4, 0)
        assert result == b"\x01\x02\x03\x04"
        assert offset == 4

    def test_unpack_bytes_with_offset(self) -> None:
        """Test unpacking bytes with offset."""
        data = b"\xff\xff\x01\x02\x03\x04"
        result, offset = unpack_bytes(data, 4, 2)
        assert result == b"\x01\x02\x03\x04"
        assert offset == 6

    def test_unpack_bytes_short_data_raises(self) -> None:
        """Test unpacking bytes from too-short data raises."""
        with pytest.raises(ValueError, match="Bytes: need 6 bytes, got 4"):
            unpack_bytes(b"\x01\x02\x03\x04", 4, 2)

    def test_bytes_roundtrip(self) -> None:
        """Test pack/unpack roundtrip for bytes."""
        original = b"\x01\x02\x03\x04\x05"
        packed = pack_bytes(original, 5)
        unpacked, _ = unpack_bytes(packed, 5, 0)
        assert unpacked == original


class TestStringEdgeCases:
    """Test string serialization edge cases."""

    def test_pack_string_utf8_truncation_at_boundary(self) -> None:
        """Test packing string truncates at UTF-8 character boundary."""
        # Multi-byte UTF-8 character: emoji (4 bytes)
        # If we truncate mid-character, it should back off to safe boundary
        emoji_string = "test\U0001f600"  # test + grinning face emoji
        # "test" is 4 bytes, emoji is 4 bytes = 8 total
        # If we truncate to 6 bytes, it should only include "test" (4 bytes)
        # because including partial emoji bytes would be invalid UTF-8
        data = pack_string(emoji_string, 6)
        assert len(data) == 6
        # Should be "test" + 2 null bytes (emoji is not included)
        assert data[:4] == b"test"

    def test_pack_string_utf8_multi_byte_characters(self) -> None:
        """Test packing string with multi-byte UTF-8 characters."""
        # 2-byte character: é
        string_with_accent = "café"  # c(1) + a(1) + f(1) + é(2) = 5 bytes
        data = pack_string(string_with_accent, 10)
        assert len(data) == 10
        # First 5 bytes should be the encoded string
        assert data[:5] == "café".encode()

    def test_pack_string_utf8_truncation_mid_character(self) -> None:
        """Test packing string that would truncate mid-character."""
        # String with 3-byte character at the end: Japanese character
        japanese_string = "AB\u3042"  # A(1) + B(1) + あ(3) = 5 bytes
        # Truncate to 4 bytes - should only include "AB" (2 bytes) + padding
        # because あ takes 3 bytes and would be incomplete
        data = pack_string(japanese_string, 4)
        assert len(data) == 4
        # Should safely truncate to avoid invalid UTF-8
        assert data[:2] == b"AB"

    def test_unpack_string_short_data_raises(self) -> None:
        """Test unpacking string from too-short data raises."""
        with pytest.raises(ValueError, match="String: need 10 bytes, got 5"):
            unpack_string(b"hello", 10, 0)

    def test_unpack_string_with_invalid_utf8(self) -> None:
        """Test unpacking string with invalid UTF-8 uses replacement characters."""
        # Create data with invalid UTF-8 sequence
        invalid_utf8 = b"\xff\xfe\x00\x00"
        string, offset = unpack_string(invalid_utf8, 4, 0)
        # Should use replacement characters for invalid bytes
        assert offset == 4
        # The result should be a valid Python string (with replacement chars)
        assert isinstance(string, str)


class TestArrayEdgeCases:
    """Test array serialization edge cases."""

    def test_unpack_array_short_data_raises(self) -> None:
        """Test unpacking array from too-short data raises."""
        # uint16 array of 5 elements needs 10 bytes
        with pytest.raises(ValueError, match="Array: need 10 bytes, got 6"):
            unpack_array(b"\x00\x00\x00\x00\x00\x00", "uint16", 5, 0)

    def test_pack_array_int_types(self) -> None:
        """Test packing array with signed integer types."""
        values = [-1, -100, 100, 127]
        data = pack_array(values, "int8", 4)
        assert len(data) == 4

        # Verify roundtrip
        unpacked, _ = unpack_array(data, "int8", 4, 0)
        assert unpacked == values

    def test_pack_array_int16(self) -> None:
        """Test packing array with int16 type."""
        values = [-1000, 0, 1000]
        data = pack_array(values, "int16", 3)
        assert len(data) == 6

        unpacked, _ = unpack_array(data, "int16", 3, 0)
        assert unpacked == values


class TestFieldSerializerEdgeCases:
    """Test FieldSerializer edge cases."""

    def test_pack_field_missing_attribute_raises(self) -> None:
        """Test packing field with missing attribute raises."""
        field_defs = {
            "TestField": {
                "attr1": "uint16",
                "attr2": "uint32",
            }
        }

        serializer = FieldSerializer(field_defs)

        # Missing attr2
        incomplete_data = {"attr1": 100}

        with pytest.raises(ValueError, match="Missing attribute attr2"):
            serializer.pack_field(incomplete_data, "TestField")

    def test_unpack_field_with_offset(self) -> None:
        """Test unpacking field with non-zero offset."""
        field_defs = {
            "Point": {
                "x": "uint16",
                "y": "uint16",
            }
        }

        serializer = FieldSerializer(field_defs)

        # Create data with padding before the field
        field_data = {"x": 100, "y": 200}
        packed_field = serializer.pack_field(field_data, "Point")
        padded_data = b"\xff\xff" + packed_field

        unpacked, offset = serializer.unpack_field(padded_data, "Point", 2)
        assert unpacked == field_data
        assert offset == 6  # 2 (initial offset) + 4 (field size)

    def test_field_serializer_multiple_fields(self) -> None:
        """Test FieldSerializer with multiple field definitions."""
        field_defs = {
            "HSBK": {
                "hue": "uint16",
                "saturation": "uint16",
                "brightness": "uint16",
                "kelvin": "uint16",
            },
            "Point": {
                "x": "int32",
                "y": "int32",
            },
        }

        serializer = FieldSerializer(field_defs)

        assert serializer.get_field_size("HSBK") == 8
        assert serializer.get_field_size("Point") == 8

        # Test both fields work
        hsbk_data = {"hue": 100, "saturation": 200, "brightness": 300, "kelvin": 400}
        point_data = {"x": -100, "y": 200}

        hsbk_packed = serializer.pack_field(hsbk_data, "HSBK")
        point_packed = serializer.pack_field(point_data, "Point")

        assert len(hsbk_packed) == 8
        assert len(point_packed) == 8

        # Verify roundtrip
        hsbk_unpacked, _ = serializer.unpack_field(hsbk_packed, "HSBK", 0)
        point_unpacked, _ = serializer.unpack_field(point_packed, "Point", 0)

        assert hsbk_unpacked == hsbk_data
        assert point_unpacked == point_data
