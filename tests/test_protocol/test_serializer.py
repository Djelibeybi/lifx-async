"""Tests for binary serializer."""

import pytest

from lifx.protocol.serializer import (
    FieldSerializer,
    get_type_size,
    pack_array,
    pack_reserved,
    pack_string,
    pack_value,
    unpack_array,
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
