"""Binary serialization for LIFX protocol packets.

Handles packing and unpacking of protocol structures using struct module.
All multi-byte values use little-endian byte order per LIFX specification.
"""

from __future__ import annotations

import struct
from typing import Any

# Type format mapping for struct module (little-endian)
TYPE_FORMATS: dict[str, str] = {
    "uint8": "B",
    "uint16": "H",
    "uint32": "I",
    "uint64": "Q",
    "int8": "b",
    "int16": "h",
    "int32": "i",
    "int64": "q",
    "float32": "f",
    "bool": "?",
}

# Type sizes in bytes
TYPE_SIZES: dict[str, int] = {
    "uint8": 1,
    "uint16": 2,
    "uint32": 4,
    "uint64": 8,
    "int8": 1,
    "int16": 2,
    "int32": 4,
    "int64": 8,
    "float32": 4,
    "bool": 1,
}

# Pre-compiled struct.Struct objects for faster pack/unpack (optimization)
_STRUCT_CACHE: dict[str, struct.Struct] = {
    "uint8": struct.Struct("<B"),
    "uint16": struct.Struct("<H"),
    "uint32": struct.Struct("<I"),
    "uint64": struct.Struct("<Q"),
    "int8": struct.Struct("<b"),
    "int16": struct.Struct("<h"),
    "int32": struct.Struct("<i"),
    "int64": struct.Struct("<q"),
    "float32": struct.Struct("<f"),
    "bool": struct.Struct("<?"),
}


def get_type_size(type_name: str) -> int:
    """Get the size in bytes of a type.

    Args:
        type_name: Type name (e.g., 'uint16', 'float32')

    Returns:
        Size in bytes

    Raises:
        ValueError: If type is unknown
    """
    if type_name not in TYPE_SIZES:
        raise ValueError(f"Unknown type: {type_name}")
    return TYPE_SIZES[type_name]


def pack_value(value: Any, type_name: str) -> bytes:
    """Pack a single value into bytes.

    Args:
        value: Value to pack
        type_name: Type name (e.g., 'uint16', 'float32')

    Returns:
        Packed bytes

    Raises:
        ValueError: If type is unknown
        struct.error: If value doesn't match type
    """
    if type_name not in _STRUCT_CACHE:
        raise ValueError(f"Unknown type: {type_name}")

    return _STRUCT_CACHE[type_name].pack(value)


def unpack_value(data: bytes, type_name: str, offset: int = 0) -> tuple[Any, int]:
    """Unpack a single value from bytes.

    Args:
        data: Bytes to unpack from
        type_name: Type name (e.g., 'uint16', 'float32')
        offset: Offset in bytes to start unpacking

    Returns:
        Tuple of (unpacked_value, new_offset)

    Raises:
        ValueError: If type is unknown or data is too short
        struct.error: If data format is invalid
    """
    if type_name not in _STRUCT_CACHE:
        raise ValueError(f"Unknown type: {type_name}")

    size = TYPE_SIZES[type_name]

    if len(data) < offset + size:
        raise ValueError(
            f"Not enough data: need {offset + size} bytes, got {len(data)}"
        )

    value = _STRUCT_CACHE[type_name].unpack_from(data, offset)[0]
    return value, offset + size


def pack_array(values: list[Any], element_type: str, count: int) -> bytes:
    """Pack an array of values into bytes.

    Args:
        values: List of values to pack
        element_type: Type of each element (e.g., 'uint8', 'uint16')
        count: Expected number of elements

    Returns:
        Packed bytes

    Raises:
        ValueError: If values length doesn't match count or type is unknown
    """
    if len(values) != count:
        raise ValueError(f"Expected {count} values, got {len(values)}")

    # Optimization: Pack entire primitive array at once with single struct call
    if element_type in TYPE_FORMATS:
        format_str = f"<{count}{TYPE_FORMATS[element_type]}"
        return struct.pack(format_str, *values)

    # Fall back to element-by-element for complex types
    result = b""
    for value in values:
        result += pack_value(value, element_type)
    return result


def unpack_array(
    data: bytes, element_type: str, count: int, offset: int = 0
) -> tuple[list[Any], int]:
    """Unpack an array of values from bytes.

    Args:
        data: Bytes to unpack from
        element_type: Type of each element
        count: Number of elements to unpack
        offset: Offset in bytes to start unpacking

    Returns:
        Tuple of (list_of_values, new_offset)
    """
    # Optimization: Unpack entire primitive array at once with single struct call
    if element_type in TYPE_FORMATS:
        format_str = f"<{count}{TYPE_FORMATS[element_type]}"
        size = TYPE_SIZES[element_type] * count

        if len(data) < offset + size:
            raise ValueError(f"Array: need {offset + size} bytes, got {len(data)}")

        values = list(struct.unpack_from(format_str, data, offset))
        return values, offset + size

    # Fall back to element-by-element for complex types
    values = []
    current_offset = offset

    for _ in range(count):
        value, current_offset = unpack_value(data, element_type, current_offset)
        values.append(value)

    return values, current_offset


def pack_string(value: str, length: int) -> bytes:
    """Pack a string into fixed-length byte array.

    Safely truncates at UTF-8 character boundaries to avoid creating
    invalid UTF-8 sequences that could crash device firmware

    Args:
        value: String to pack
        length: Fixed length in bytes

    Returns:
        Packed bytes (null-padded if necessary)
    """
    encoded = value.encode("utf-8")

    # Safe truncation at character boundary
    if len(encoded) > length:
        # Decode and re-encode to find safe truncation point
        truncated = encoded[:length]
        # Find valid UTF-8 boundary by trying to decode
        while truncated:
            try:
                truncated.decode("utf-8")
                break
            except UnicodeDecodeError:
                # Remove last byte and try again
                truncated = truncated[:-1]
        encoded = truncated

    return encoded.ljust(length, b"\x00")


def unpack_string(data: bytes, length: int, offset: int = 0) -> tuple[str, int]:
    """Unpack a fixed-length string from bytes.

    Args:
        data: Bytes to unpack from
        length: Length in bytes to read
        offset: Offset in bytes to start unpacking

    Returns:
        Tuple of (string, new_offset)
    """
    if len(data) < offset + length:
        raise ValueError(f"String: need {offset + length} bytes, got {len(data)}")

    raw_bytes = data[offset : offset + length]
    # Strip null bytes and decode
    string = raw_bytes.rstrip(b"\x00").decode("utf-8", errors="replace")
    return string, offset + length


def pack_reserved(size: int) -> bytes:
    """Pack reserved (zero) bytes.

    Args:
        size: Number of bytes

    Returns:
        Zero bytes
    """
    return b"\x00" * size


def pack_bytes(data: bytes, length: int) -> bytes:
    """Pack bytes into fixed-length byte array.

    Args:
        data: Bytes to pack
        length: Fixed length in bytes

    Returns:
        Packed bytes (null-padded or truncated if necessary)
    """
    if len(data) >= length:
        return data[:length]
    return data + b"\x00" * (length - len(data))


def unpack_bytes(data: bytes, length: int, offset: int = 0) -> tuple[bytes, int]:
    """Unpack fixed-length byte array from bytes.

    Args:
        data: Bytes to unpack from
        length: Length in bytes to read
        offset: Offset in bytes to start unpacking

    Returns:
        Tuple of (bytes, new_offset)

    Raises:
        ValueError: If data is too short
    """
    if len(data) < offset + length:
        raise ValueError(f"Bytes: need {offset + length} bytes, got {len(data)}")

    raw_bytes = data[offset : offset + length]
    return raw_bytes, offset + length
