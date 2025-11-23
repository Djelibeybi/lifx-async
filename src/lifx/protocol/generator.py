"""Code generator for LIFX protocol structures.

Downloads the official protocol.yml from the LIFX GitHub repository and
generates Python types and packet classes. The YAML is never stored locally,
only parsed and converted into protocol classes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

import yaml

from lifx.const import PROTOCOL_URL


class TypeRegistry:
    """Registry of all protocol types for validation.

    Tracks all defined types (enums, fields, packets, unions) to validate
    that all type references in the protocol specification are valid.
    """

    def __init__(self) -> None:
        """Initialize empty type registry."""
        self._enums: set[str] = set()
        self._fields: set[str] = set()
        self._packets: set[str] = set()
        self._unions: set[str] = set()
        self._basic_types: set[str] = {
            "uint8",
            "uint16",
            "uint32",
            "uint64",
            "int8",
            "int16",
            "int32",
            "int64",
            "float32",
            "bool",
            "byte",
            "reserved",  # Special type for reserved fields
        }

    def register_enum(self, name: str) -> None:
        """Register an enum type.

        Args:
            name: Enum type name
        """
        self._enums.add(name)

    def register_field(self, name: str) -> None:
        """Register a field structure type.

        Args:
            name: Field structure type name
        """
        self._fields.add(name)

    def register_packet(self, name: str) -> None:
        """Register a packet type.

        Args:
            name: Packet type name
        """
        self._packets.add(name)

    def register_union(self, name: str) -> None:
        """Register a union type.

        Args:
            name: Union type name
        """
        self._unions.add(name)

    def is_enum(self, name: str) -> bool:
        """Check if a type is an enum.

        Args:
            name: Type name to check

        Returns:
            True if the type is an enum
        """
        return name in self._enums

    def has_type(self, name: str) -> bool:
        """Check if a type is defined.

        Args:
            name: Type name to check

        Returns:
            True if the type is defined
        """
        return (
            name in self._enums
            or name in self._fields
            or name in self._packets
            or name in self._unions
            or name in self._basic_types
        )

    def get_all_types(self) -> set[str]:
        """Get all registered types.

        Returns:
            Set of all type names
        """
        return (
            self._enums
            | self._fields
            | self._packets
            | self._unions
            | self._basic_types
        )


def to_snake_case(name: str) -> str:
    """Convert PascalCase or camelCase to snake_case.

    Args:
        name: PascalCase or camelCase string

    Returns:
        snake_case string
    """
    # Insert underscore before uppercase letters (except at start)
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name)
    return snake.lower()


def apply_field_name_quirks(python_name: str) -> str:
    """Apply quirks to field names to avoid Python built-ins and reserved words.

    Args:
        python_name: The Python field name (usually from to_snake_case)

    Returns:
        Quirk-adjusted field name

    Quirks applied:
        - "type" -> "effect_type" (avoids Python built-in)
    """
    if python_name == "type":
        return "effect_type"
    return python_name


def apply_extended_multizone_packet_quirks(
    packet_name: str, category_class: str
) -> str:
    """Apply quirks to extended multizone packet names to follow LIFX naming convention.

    In the LIFX protocol, extended multizone packets should follow the standard naming
    pattern of {Action}{Object} (e.g., GetExtendedColorZones, SetExtendedColorZones).

    Args:
        packet_name: Packet name (after category prefix removal)
        category_class: Category class name (e.g., "MultiZone")

    Returns:
        Quirk-adjusted packet name

    Quirks applied:
        - "ExtendedGetColorZones" -> "GetExtendedColorZones"
        - "ExtendedSetColorZones" -> "SetExtendedColorZones"
        - "ExtendedStateMultiZone" -> "StateExtendedColorZones"
    """
    if category_class == "MultiZone":
        if packet_name == "ExtendedGetColorZones":
            return "GetExtendedColorZones"
        elif packet_name == "ExtendedSetColorZones":
            return "SetExtendedColorZones"
        elif packet_name == "ExtendedStateMultiZone":
            return "StateExtendedColorZones"
    return packet_name


def apply_tile_effect_parameter_quirk(
    fields: dict[str, Any],
) -> dict[str, Any]:
    """Apply local quirk to fix TileEffectParameter structure.

    The upstream protocol.yml doesn't provide enough detail for TileEffectParameter.
    This quirk replaces it with the correct structure:
    - TileEffectSkyType (enum, uint8)
    - 3 reserved bytes
    - cloudSaturationMin (uint8)
    - 3 reserved bytes
    - cloudSaturationMax (uint8)
    - 23 reserved bytes
    Total: 32 bytes

    Args:
        fields: Dictionary of field definitions

    Returns:
        Dictionary with TileEffectParameter quirk applied
    """
    if "TileEffectParameter" in fields:
        fields["TileEffectParameter"] = {
            "size_bytes": 32,
            "fields": [
                {"name": "SkyType", "type": "<TileEffectSkyType>"},
                {"size_bytes": 3},
                {"name": "CloudSaturationMin", "type": "uint8"},
                {"size_bytes": 3},
                {"name": "CloudSaturationMax", "type": "uint8"},
                {"size_bytes": 23},
            ],
        }
    return fields


def apply_tile_state_device_quirk(
    fields: dict[str, Any],
) -> dict[str, Any]:
    """Apply local quirk to add supported_frame_buffers field to TileStateDevice.

    The upstream protocol.yml has a reserved field between height and device_version.
    This quirk replaces that reserved field with supported_frame_buffers (uint8).

    Args:
        fields: Dictionary of field definitions

    Returns:
        Dictionary with TileStateDevice quirk applied
    """
    if "TileStateDevice" in fields:
        tile_def = fields["TileStateDevice"]
        if "fields" in tile_def:
            # Find and replace the reserved field between height and device_version
            fields_list = tile_def["fields"]
            for i, field in enumerate(fields_list):
                # Look for height field
                if field.get("name") == "Height":
                    # Check if next field is reserved (1 byte) and followed by DeviceVersion
                    if (
                        i + 1 < len(fields_list)
                        and i + 2 < len(fields_list)
                        and fields_list[i + 1].get("type") == "reserved"
                        and fields_list[i + 1].get("size_bytes") == 1
                        and fields_list[i + 2].get("name") == "DeviceVersion"
                    ):
                        # Replace the reserved field with supported_frame_buffers
                        fields_list[i + 1] = {
                            "name": "SupportedFrameBuffers",
                            "type": "uint8",
                        }
                        break

    return fields


def apply_sensor_packet_quirks(packets: dict[str, Any]) -> dict[str, Any]:
    """Add undocumented sensor packets for ambient light level reading.

    These packets are not documented in the official protocol.yml but are supported
    by LIFX devices with ambient light sensors.

    Quirks applied:
        - SensorGetAmbientLight (401): Request packet with no parameters
        - SensorStateAmbientLight (402): Response packet with lux field (float)

    Args:
        packets: Dictionary of packet definitions

    Returns:
        Dictionary with sensor packet quirks applied
    """
    # Ensure sensor category exists
    if "sensor" not in packets:
        packets["sensor"] = {}

    # Add SensorGetAmbientLight (401) - request with no parameters
    packets["sensor"]["SensorGetAmbientLight"] = {
        "pkt_type": 401,
        "fields": [],
    }

    # Add SensorStateAmbientLight (402) - response with lux field
    packets["sensor"]["SensorStateAmbientLight"] = {
        "pkt_type": 402,
        "fields": [
            {"name": "Lux", "type": "float32"},
        ],
    }

    return packets


def apply_firmware_effect_enum_quirk(
    enums: dict[str, Any], fields: dict[str, Any], compound_fields: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Merge MultiZoneEffectType and TileEffectType into FirmwareEffect enum.

    Both MultiZone and Tile effects use the same firmware effect protocol values,
    so they should share a single enum. This quirk:
    - Creates FirmwareEffect enum combining values from both
    - Removes MultiZoneEffectType and TileEffectType
    - Updates MultiZoneEffectSettings and TileEffectSettings to use FirmwareEffect
    - Uses clean enum value names (OFF, MOVE, MORPH, FLAME, SKY, RESERVED_*)
    - Also adds DIRECTION enum for move effect parameter

    Args:
        enums: Dictionary of enum definitions
        fields: Dictionary of field definitions
        compound_fields: Dictionary of compound field definitions

    Returns:
        Tuple of (enums, fields, compound_fields) with FirmwareEffect enum quirk applied
    """
    # Create FirmwareEffect enum with clean names manually
    # Based on protocol spec:
    # MultiZone: OFF=0, MOVE=1, reserved=2, reserved=3
    # Tile: OFF=0, reserved=1, MORPH=2, FLAME=3, reserved=4, SKY=5
    # Note: Reserved values are intentionally omitted
    firmware_effect_values = {
        "OFF": 0,
        "MOVE": 1,
        "MORPH": 2,
        "FLAME": 3,
        "SKY": 5,
    }

    # Create FirmwareEffect enum
    enums["FirmwareEffect"] = firmware_effect_values

    # Remove the old separate enums
    enums.pop("MultiZoneEffectType", None)
    enums.pop("TileEffectType", None)

    # Update fields to use FirmwareEffect (check both fields and compound_fields)
    for field_dict in [fields, compound_fields]:
        if "MultiZoneEffectSettings" in field_dict:
            for field in field_dict["MultiZoneEffectSettings"].get("fields", []):
                if field.get("name") == "Type":
                    field["type"] = "<FirmwareEffect>"

        if "TileEffectSettings" in field_dict:
            for field in field_dict["TileEffectSettings"].get("fields", []):
                if field.get("name") == "Type":
                    field["type"] = "<FirmwareEffect>"

    # Add DIRECTION enum for move effect
    enums["Direction"] = {
        "REVERSED": 0,
        "FORWARD": 1,
    }

    return enums, fields, compound_fields


def apply_multizone_application_request_quirk(
    enums: dict[str, Any], packets: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Suppress MultiZoneExtendedApplicationRequest enum.

    Both MultiZoneApplicationRequest and MultiZoneExtendedApplicationRequest have
    identical values (NO_APPLY=0, APPLY=1, APPLY_ONLY=2), so we suppress the
    extended version and use the standard one for both SetColorZones and
    SetExtendedColorZones packets.

    Args:
        enums: Dictionary of enum definitions
        packets: Dictionary of packet definitions

    Returns:
        Tuple of (enums, packets) with MultiZoneExtendedApplicationRequest removed
        and packets updated to use MultiZoneApplicationRequest
    """
    # Remove the duplicate enum
    enums.pop("MultiZoneExtendedApplicationRequest", None)

    # Update packets in multi_zone category to use MultiZoneApplicationRequest
    if "multi_zone" in packets:
        for packet_name, packet_def in packets["multi_zone"].items():
            if "fields" in packet_def:
                for field in packet_def["fields"]:
                    if (
                        isinstance(field, dict)
                        and field.get("type") == "<MultiZoneExtendedApplicationRequest>"
                    ):
                        field["type"] = "<MultiZoneApplicationRequest>"

    return enums, packets


def format_long_import(
    items: list[str], prefix: str = "from lifx.protocol.protocol_types import "
) -> str:
    """Format a long import statement across multiple lines.

    Args:
        items: List of import items (e.g., ["Foo", "Bar as BazAlias"])
        prefix: Import prefix

    Returns:
        Formatted import string with line breaks if needed
    """
    if not items:
        return ""

    # Try single line first
    single_line = prefix + ", ".join(items)
    if len(single_line) <= 120:
        return single_line + "\n"

    # Multi-line format
    lines = [prefix + "("]
    for i, item in enumerate(items):
        if i < len(items) - 1:
            lines.append(f"    {item},")
        else:
            lines.append(f"    {item},")
    lines.append(")")
    return "\n".join(lines) + "\n"


def format_long_list(items: list[dict[str, Any]], max_line_length: int = 120) -> str:
    """Format a long list across multiple lines.

    Args:
        items: List of dict items to format
        max_line_length: Maximum line length before wrapping

    Returns:
        Formatted list string
    """
    if not items:
        return "[]"

    # Try single line first
    single_line = repr(items)
    if len(single_line) <= max_line_length:
        return single_line

    # Multi-line format with one item per line
    lines = ["["]
    for i, item in enumerate(items):
        item_str = repr(item)
        if i < len(items) - 1:
            lines.append(f"    {item_str},")
        else:
            lines.append(f"    {item_str},")
    lines.append("]")
    return "\n".join(lines)


def parse_field_type(field_type: str) -> tuple[str, int | None, bool]:
    """Parse a field type string.

    Args:
        field_type: Field type (e.g., 'uint16', '[32]uint8', '<HSBK>')

    Returns:
        Tuple of (base_type, array_count, is_nested)
        - base_type: The base type name
        - array_count: Number of elements if array, None otherwise
        - is_nested: True if it's a nested structure (<Type>)
    """
    # Check for array: [N]type
    array_match = re.match(r"\[(\d+)\](.+)", field_type)
    if array_match:
        count = int(array_match.group(1))
        inner_type = array_match.group(2)
        # Check if inner type is nested
        if inner_type.startswith("<") and inner_type.endswith(">"):
            return inner_type[1:-1], count, True
        return inner_type, count, False

    # Check for nested structure: <Type>
    if field_type.startswith("<") and field_type.endswith(">"):
        return field_type[1:-1], None, True

    # Simple type
    return field_type, None, False


def camel_to_snake_upper(name: str) -> str:
    """Convert CamelCase to UPPER_SNAKE_CASE.

    Args:
        name: CamelCase string

    Returns:
        UPPER_SNAKE_CASE string
    """
    # Insert underscore before uppercase letters (except at start)
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name)
    return snake.upper()


def generate_enum_code(enums: dict[str, Any]) -> str:
    """Generate Python Enum definitions with shortened names.

    Args:
        enums: Dictionary of enum definitions

    Returns:
        Python code string
    """
    code: list[str] = []

    for enum_name, enum_def in sorted(enums.items()):
        code.append(f"class {enum_name}(IntEnum):")
        code.append('    """Auto-generated enum."""')
        code.append("")

        # Handle both old format (dict) and new format (list of dicts)
        if isinstance(enum_def, dict) and "values" in enum_def:
            # New format: {type: "uint16", values: [{name: "X", value: 1}, ...]}
            values = enum_def["values"]

            # Check if all values share a common prefix (enum name)
            expected_prefix = camel_to_snake_upper(enum_name) + "_"
            non_reserved = [
                item["name"] for item in values if item["name"].lower() != "reserved"
            ]
            has_common_prefix = non_reserved and all(
                name.startswith(expected_prefix) for name in non_reserved
            )

            for item in sorted(values, key=lambda x: x["value"]):
                protocol_name = item["name"]
                member_value = item["value"]

                # Skip reserved fields entirely
                if protocol_name.lower() == "reserved":
                    continue

                # Remove redundant prefix for cleaner Python names
                if has_common_prefix and protocol_name.startswith(expected_prefix):
                    member_name = protocol_name[len(expected_prefix) :]
                else:
                    member_name = protocol_name

                code.append(f"    {member_name} = {member_value}")
        else:
            # Old format: {MEMBER: value, ...}
            for member_name, member_value in sorted(
                enum_def.items(), key=lambda x: x[1]
            ):
                code.append(f"    {member_name} = {member_value}")

        code.append("")
        code.append("")

    return "\n".join(code)


def convert_type_to_python(
    field_type: str, type_aliases: dict[str, str] | None = None
) -> str:
    """Convert a protocol field type to Python type annotation.

    Args:
        field_type: Protocol field type string
        type_aliases: Optional dict for type name aliases

    Returns:
        Python type annotation string
    """
    if type_aliases is None:
        type_aliases = {}

    base_type, array_count, is_nested = parse_field_type(field_type)

    if array_count:
        if is_nested:
            # Use alias if one exists
            type_name = type_aliases.get(base_type, base_type)
            return f"list[{type_name}]"
        elif base_type in ("uint8", "byte"):
            # Special case: byte arrays
            return "bytes"
        else:
            return "list[int]"
    elif is_nested:
        # Use alias if one exists
        return type_aliases.get(base_type, base_type)
    elif base_type in ("uint8", "uint16", "uint32", "uint64"):
        return "int"
    elif base_type in ("int8", "int16", "int32", "int64"):
        return "int"
    elif base_type == "float32":
        return "float"
    elif base_type == "bool":
        return "bool"
    else:
        return "Any"


def generate_pack_method(
    fields_data: list[dict[str, Any]],
    class_type: str = "field",
    enum_types: set[str] | None = None,
) -> str:
    """Generate pack() method code for a field structure or packet.

    Args:
        fields_data: List of field definitions
        class_type: Either "field" or "packet"
        enum_types: Set of enum type names for detection

    Returns:
        Python method code string
    """
    if enum_types is None:
        enum_types = set()

    code = []
    code.append("    def pack(self) -> bytes:")
    code.append('        """Pack to bytes."""')
    code.append("        from lifx.protocol import serializer")
    code.append('        result = b""')
    code.append("")

    for field_item in fields_data:
        # Handle reserved fields (no name)
        if "name" not in field_item:
            size_bytes = field_item.get("size_bytes", 0)
            code.append(f"        # Reserved {size_bytes} bytes")
            code.append(f"        result += serializer.pack_reserved({size_bytes})")
            continue

        protocol_name = field_item["name"]
        field_type = field_item["type"]
        size_bytes = field_item.get("size_bytes", 0)
        python_name = apply_field_name_quirks(to_snake_case(protocol_name))

        base_type, array_count, is_nested = parse_field_type(field_type)

        # Check if this is an enum (nested but in enum_types)
        is_enum = is_nested and base_type in enum_types

        # Handle different field types
        if array_count:
            if is_enum:
                # Array of enums - pack as array of ints
                code.append(f"        # {python_name}: list[{base_type}] (enum array)")
                code.append(f"        for item in self.{python_name}:")
                code.append(
                    "            result += serializer.pack_value(int(item), 'uint8')"
                )
            elif is_nested:
                # Array of nested structures
                code.append(f"        # {python_name}: list[{base_type}]")
                code.append(f"        for item in self.{python_name}:")
                code.append("            result += item.pack()")
            elif base_type in ("uint8", "byte"):
                # Byte array
                code.append(f"        # {python_name}: bytes ({size_bytes} bytes)")
                code.append(
                    f"        result += "
                    f"serializer.pack_bytes(self.{python_name}, {size_bytes})"
                )
            else:
                # Array of primitives
                code.append(f"        # {python_name}: list[{base_type}]")
                code.append(
                    f"        result += "
                    f"serializer.pack_array(self.{python_name}, '{base_type}', {array_count})"
                )
        elif is_enum:
            # Enum - pack as int
            code.append(f"        # {python_name}: {base_type} (enum)")
            code.append(
                f"        result += "
                f"serializer.pack_value(int(self.{python_name}), 'uint8')"
            )
        elif is_nested:
            # Nested structure
            code.append(f"        # {python_name}: {base_type}")
            code.append(f"        result += self.{python_name}.pack()")
        else:
            # Primitive type
            code.append(f"        # {python_name}: {base_type}")
            code.append(
                f"        result += "
                f"serializer.pack_value(self.{python_name}, '{base_type}')"
            )

    code.append("")
    code.append("        return result")

    return "\n".join(code)


def generate_unpack_method(
    class_name: str,
    fields_data: list[dict[str, Any]],
    class_type: str = "field",
    enum_types: set[str] | None = None,
) -> str:
    """Generate unpack() classmethod code for a field structure or packet.

    Args:
        class_name: Name of the class
        fields_data: List of field definitions
        class_type: Either "field" or "packet"
        enum_types: Set of enum type names for detection

    Returns:
        Python method code string
    """
    if enum_types is None:
        enum_types = set()

    code = []
    code.append("    @classmethod")
    code.append(
        f"    def unpack(cls, data: bytes, offset: int = 0) -> tuple[{class_name}, int]:"
    )
    code.append('        """Unpack from bytes."""')
    code.append("        from lifx.protocol import serializer")
    code.append("        current_offset = offset")

    # Store field values
    field_vars = []

    for field_item in fields_data:
        # Handle reserved fields (no name)
        if "name" not in field_item:
            size_bytes = field_item.get("size_bytes", 0)
            code.append(f"        # Skip reserved {size_bytes} bytes")
            code.append(f"        current_offset += {size_bytes}")
            continue

        protocol_name = field_item["name"]
        field_type = field_item["type"]
        size_bytes = field_item.get("size_bytes", 0)
        python_name = apply_field_name_quirks(to_snake_case(protocol_name))
        field_vars.append(python_name)

        base_type, array_count, is_nested = parse_field_type(field_type)

        # Check if this is an enum (nested but in enum_types)
        is_enum = is_nested and base_type in enum_types

        # Handle different field types
        if array_count:
            if is_enum:
                # Array of enums
                code.append(f"        # {python_name}: list[{base_type}] (enum array)")
                code.append(f"        {python_name} = []")
                code.append(f"        for _ in range({array_count}):")
                code.append(
                    "            item_raw, current_offset = serializer.unpack_value(data, 'uint8', current_offset)"
                )
                code.append(f"            {python_name}.append({base_type}(item_raw))")
            elif is_nested:
                # Array of nested structures
                code.append(f"        # {python_name}: list[{base_type}]")
                code.append(f"        {python_name} = []")
                code.append(f"        for _ in range({array_count}):")
                code.append(
                    f"            item, current_offset = {base_type}.unpack(data, current_offset)"
                )
                code.append(f"            {python_name}.append(item)")
            elif base_type in ("uint8", "byte"):
                # Byte array
                code.append(f"        # {python_name}: bytes ({size_bytes} bytes)")
                code.append(
                    f"        {python_name}, current_offset = serializer.unpack_bytes("
                )
                code.append(f"            data, {size_bytes}, current_offset")
                code.append("        )")
            else:
                # Array of primitives
                code.append(f"        # {python_name}: list[{base_type}]")
                code.append(
                    f"        {python_name}, current_offset = serializer.unpack_array("
                )
                code.append(
                    f"            data, '{base_type}', {array_count}, current_offset"
                )
                code.append("        )")
        elif is_enum:
            # Enum - unpack as int then convert
            code.append(f"        # {python_name}: {base_type} (enum)")
            code.append(
                f"        {python_name}_raw, current_offset = serializer.unpack_value(data, 'uint8', current_offset)"
            )
            code.append(f"        {python_name} = {base_type}({python_name}_raw)")
        elif is_nested:
            # Nested structure
            code.append(f"        # {python_name}: {base_type}")
            code.append(
                f"        {python_name}, current_offset = {base_type}.unpack(data, current_offset)"
            )
        else:
            # Primitive type
            code.append(f"        # {python_name}: {base_type}")
            code.append(
                f"        {python_name}, current_offset = serializer.unpack_value(data, '{base_type}', current_offset)"
            )

    code.append("")
    # Create instance - format long return statements
    field_args = ", ".join([f"{name}={name}" for name in field_vars])
    return_stmt = f"        return cls({field_args}), current_offset"

    # If too long, break across multiple lines
    if len(return_stmt) > 120:
        code.append("        return (")
        code.append("            cls(")
        for i, name in enumerate(field_vars):
            if i < len(field_vars) - 1:
                code.append(f"                {name}={name},")
            else:
                code.append(f"                {name}={name},")
        code.append("            ),")
        code.append("            current_offset,")
        code.append("        )")
    else:
        code.append(return_stmt)

    return "\n".join(code)


def generate_field_code(
    fields: dict[str, Any],
    compound_fields: dict[str, Any] | None = None,
    unions: dict[str, Any] | None = None,
    packets_as_fields: dict[str, Any] | None = None,
    enum_types: set[str] | None = None,
) -> tuple[str, dict[str, dict[str, str]]]:
    """Generate Python dataclass definitions for field structures.

    Args:
        fields: Dictionary of field definitions
        compound_fields: Dictionary of compound field definitions
        unions: Dictionary of union definitions (treated as fields)
        packets_as_fields: Dictionary of packets that are also used as field types
        enum_types: Set of enum type names

    Returns:
        Tuple of (code string, field mappings dict)
        Field mappings: {ClassName: {python_name: protocol_name}}
    """
    if enum_types is None:
        enum_types = set()

    code = []
    field_mappings: dict[str, dict[str, str]] = {}
    all_fields = {**fields}
    if compound_fields:
        all_fields.update(compound_fields)
    if unions:
        all_fields.update(unions)
    if packets_as_fields:
        all_fields.update(packets_as_fields)

    for field_name, field_def in sorted(all_fields.items()):
        code.append("@dataclass")
        code.append(f"class {field_name}:")

        # Check if this is a union (has comment indicating it's a union)
        is_union = isinstance(field_def, dict) and "comment" in field_def
        if is_union:
            code.append(
                f'    """Auto-generated union structure. {field_def.get("comment", "")}"""'
            )
        else:
            code.append('    """Auto-generated field structure."""')
        code.append("")

        field_map: dict[str, str] = {}
        fields_data = []

        # Handle both old format (dict) and new format (list of dicts)
        if isinstance(field_def, dict) and "fields" in field_def:
            # New format: {size_bytes: N, fields: [{name: "X", type: "uint16"}, ...]}
            field_list = field_def["fields"]

            # For unions, treat as a raw bytes field (they overlay, so just store raw data)
            if is_union:
                size_bytes = field_def.get("size_bytes", 16)
                code.append(f"    data: bytes  # Union of {size_bytes} bytes")
                field_map["data"] = "data"
                # For pack/unpack, use bytes field
                fields_data = [
                    {
                        "name": "data",
                        "type": f"[{size_bytes}]byte",
                        "size_bytes": size_bytes,
                    }
                ]
            else:
                # Normal field structure - process all fields
                fields_data = field_list  # Save for pack/unpack generation
                for field_item in field_list:
                    # Skip reserved fields without names (they won't be in dataclass)
                    if "name" not in field_item:
                        continue
                    protocol_name = field_item["name"]
                    attr_type = field_item["type"]
                    python_name = apply_field_name_quirks(to_snake_case(protocol_name))
                    python_type = convert_type_to_python(attr_type)

                    code.append(f"    {python_name}: {python_type}")
                    field_map[python_name] = protocol_name
        else:
            # Old format: {attr_name: type, ...}
            # Convert to new format for pack/unpack generation
            for protocol_name, attr_type in field_def.items():
                python_name = apply_field_name_quirks(to_snake_case(protocol_name))
                python_type = convert_type_to_python(attr_type)
                code.append(f"    {python_name}: {python_type}")
                field_map[python_name] = protocol_name
                # Build fields_data for old format
                fields_data.append({"name": protocol_name, "type": attr_type})

        field_mappings[field_name] = field_map

        # Add pack/unpack methods
        if fields_data:
            code.append("")
            code.append(generate_pack_method(fields_data, "field", enum_types))
            code.append("")
            code.append(
                generate_unpack_method(field_name, fields_data, "field", enum_types)
            )

        code.append("")
        code.append("")

    return "\n".join(code), field_mappings


def generate_nested_packet_code(
    packets: dict[str, Any], type_aliases: dict[str, str] | None = None
) -> str:
    """Generate nested Python packet class definitions.

    Args:
        packets: Dictionary of packet definitions (grouped by category)
        type_aliases: Optional dict mapping type names to their aliases (for collision resolution)

    Returns:
        Python code string with nested packet classes
    """
    if type_aliases is None:
        type_aliases = {}

    code = []

    # Flatten packets if they're grouped by category
    flat_packets: list[tuple[str, str, dict[str, Any]]] = []

    # Check if packets are grouped by category (new format)
    sample_key = next(iter(packets.keys())) if packets else None
    if sample_key and isinstance(packets[sample_key], dict):
        sample_value = packets[sample_key]
        # Check if this is a category grouping (contains nested packet dicts)
        if any(isinstance(v, dict) and "pkt_type" in v for v in sample_value.values()):
            # New format: grouped by category
            for category, category_packets in packets.items():
                for packet_name, packet_def in category_packets.items():
                    flat_packets.append((category, packet_name, packet_def))
        else:
            # Old format: flat packets with category field
            for packet_name, packet_def in packets.items():
                category = packet_def.get("category", "misc")
                flat_packets.append((category, packet_name, packet_def))

    # Group by category
    categories: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for category, packet_name, packet_def in flat_packets:
        if category not in categories:
            categories[category] = []
        categories[category].append((packet_name, packet_def))

    # Build lookup table for request-to-response mapping
    # Maps (category, short_name) -> pkt_type
    packet_lookup: dict[tuple[str, str], int] = {}
    for category, packets_list in categories.items():
        parts = category.split("_")
        category_class = "".join(part.capitalize() for part in parts)
        for packet_name, packet_def in packets_list:
            short_name = packet_name
            if packet_name.lower().startswith(category_class.lower()):
                short_name = packet_name[len(category_class) :]
            if category_class == "Light":
                if short_name == "Get":
                    short_name = "GetColor"
                elif short_name == "State":
                    short_name = "StateColor"
            short_name = apply_extended_multizone_packet_quirks(
                short_name, category_class
            )
            packet_lookup[(category, short_name)] = packet_def["pkt_type"]

    # Generate category classes with nested packet classes
    for category in sorted(categories.keys()):
        # Generate category class
        # Quirk: Convert category names to proper camel case (multi_zone -> MultiZone)
        # Split on underscores, capitalize each part, then join
        parts = category.split("_")
        category_class = "".join(part.capitalize() for part in parts)
        code.append("")
        code.append(f"class {category_class}(Packet):")
        code.append(f'    """{category_class} category packets."""')
        code.append("")

        # Generate nested packet classes
        for packet_name, packet_def in sorted(categories[category]):
            pkt_type = packet_def["pkt_type"]
            fields_data = packet_def.get("fields", [])

            # Remove category prefix from packet name (e.g., DeviceGetLabel -> GetLabel)
            # The packet name format is: CategoryActionTarget (e.g., DeviceGetLabel, LightSetColor)
            # Use case-insensitive matching to handle multi_zone -> Multizone -> MultiZone
            short_name = packet_name
            if packet_name.lower().startswith(category_class.lower()):
                short_name = packet_name[len(category_class) :]

            # Quirk: Rename Light.Get/Set/State to Light.GetColor/SetColor/StateColor
            # for better clarity (Set and SetColor are different packets)
            if category_class == "Light":
                if short_name == "Get":
                    short_name = "GetColor"
                elif short_name == "State":
                    short_name = "StateColor"

            # Quirk: Rename extended multizone packets to follow standard naming convention
            short_name = apply_extended_multizone_packet_quirks(
                short_name, category_class
            )

            code.append("    @dataclass")
            code.append(f"    class {short_name}(Packet):")
            code.append(f'        """Packet type {pkt_type}."""')
            code.append("")
            code.append(f"        PKT_TYPE: ClassVar[int] = {pkt_type}")

            # Add STATE_TYPE for Get*/Request packets (expected response packet type)
            state_pkt_type = None
            if short_name.startswith("Get"):
                # Special case: GetColorZones → StateMultiZone (not StateColorZones)
                if category_class == "MultiZone" and short_name == "GetColorZones":
                    state_pkt_type = packet_lookup.get((category, "StateMultiZone"))
                else:
                    # Standard naming: GetXxx → StateXxx
                    state_name = short_name.replace("Get", "State", 1)
                    state_pkt_type = packet_lookup.get((category, state_name))
            elif short_name.endswith("Request"):
                # XxxRequest → XxxResponse
                response_name = short_name.replace("Request", "Response")
                state_pkt_type = packet_lookup.get((category, response_name))

            if state_pkt_type is not None:
                code.append(f"        STATE_TYPE: ClassVar[int] = {state_pkt_type}")

            # Format fields_data - split long lists across multiple lines
            # Account for the prefix "        _fields: ClassVar[list[dict[str, Any]]] = " which is ~50 chars
            fields_repr = format_long_list(fields_data, max_line_length=70)
            if "\n" in fields_repr:
                # Multi-line format - indent properly
                code.append("        _fields: ClassVar[list[dict[str, Any]]] = (")
                for line in fields_repr.split("\n"):
                    if line.strip():
                        code.append(f"        {line}")
                code.append("        )")
            else:
                code.append(
                    f"        _fields: ClassVar[list[dict[str, Any]]] = {fields_repr}"
                )

            # Add packet metadata for smart request handling
            # Classify packet by name pattern: Get*, Set*, State*, or OTHER
            packet_kind = "OTHER"
            if short_name.startswith("Get"):
                packet_kind = "GET"
            elif short_name.startswith("Set"):
                packet_kind = "SET"
            elif short_name.startswith("State"):
                packet_kind = "STATE"

            # Quirk: CopyFrameBuffer is semantically a SET operation
            # It modifies device state without returning data
            if category_class == "Tile" and short_name == "CopyFrameBuffer":
                packet_kind = "SET"

            code.append("")
            code.append("        # Packet metadata for automatic handling")
            code.append(f"        _packet_kind: ClassVar[str] = {repr(packet_kind)}")

            # Requires acknowledgement/response based on packet kind
            # GET requests: ack_required=False, res_required=False (device responds anyway)
            # SET requests: ack_required=True, res_required=False (need acknowledgement)
            requires_ack = packet_kind == "SET"
            requires_response = False
            code.append(f"        _requires_ack: ClassVar[bool] = {requires_ack}")
            code.append(
                f"        _requires_response: ClassVar[bool] = {requires_response}"
            )
            code.append("")

            # Generate dataclass fields (only non-reserved)
            has_fields = False
            if isinstance(fields_data, list):
                for field_item in fields_data:
                    # Skip reserved fields
                    if "name" not in field_item:
                        continue
                    protocol_name = field_item["name"]
                    field_type = field_item["type"]
                    python_name = apply_field_name_quirks(to_snake_case(protocol_name))
                    python_type = convert_type_to_python(field_type, type_aliases)
                    code.append(f"        {python_name}: {python_type}")
                    has_fields = True

            if not has_fields:
                code.append("        pass")

            code.append("")

        code.append("")

    return "\n".join(code)


def generate_types_file(
    enums: dict[str, Any],
    fields: dict[str, Any],
    compound_fields: dict[str, Any] | None = None,
    unions: dict[str, Any] | None = None,
    packets_as_fields: dict[str, Any] | None = None,
) -> str:
    """Generate complete types.py file.

    Args:
        enums: Enum definitions
        fields: Field structure definitions
        compound_fields: Compound field definitions
        unions: Union definitions
        packets_as_fields: Packets that are also used as field types

    Returns:
        Complete Python file content
    """
    header = '''"""Auto-generated LIFX protocol types.

DO NOT EDIT THIS FILE MANUALLY.
Generated from https://github.com/LIFX/public-protocol/blob/main/protocol.yml
by protocol/generator.py

Uses Pythonic naming conventions (snake_case fields, shortened enums) while
maintaining compatibility with the official LIFX protocol through mappings.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


'''

    code = header
    code += generate_enum_code(enums)
    code += "\n"

    # Extract enum names for pack/unpack generation
    enum_names = set(enums.keys())

    field_code, field_mappings = generate_field_code(
        fields, compound_fields, unions, packets_as_fields, enum_names
    )
    code += field_code
    code += "\n"

    # Add type aliases for common names
    code += "# Type aliases for convenience\n"
    all_field_names = {
        **fields,
        **(compound_fields or {}),
        **(unions or {}),
        **(packets_as_fields or {}),
    }
    if "TileStateDevice" in all_field_names:
        code += "TileDevice = TileStateDevice  # Pythonic alias\n"
    code += "\n"

    # Add field name mappings as module-level constant (formatted for readability)
    code += "# Field name mappings: Python name -> Protocol name\n"
    code += "# Used by serializer to translate between conventions\n"
    code += "FIELD_MAPPINGS: dict[str, dict[str, str]] = {\n"
    for class_name in sorted(field_mappings.keys()):
        mappings = field_mappings[class_name]
        # Format each class mapping - if too long, break it into multiple lines
        mappings_str = repr(mappings)
        line = f"    {repr(class_name)}: {mappings_str},"
        if len(line) > 120:
            # Multi-line format
            code += f"    {repr(class_name)}: {{\n"
            for py_name, proto_name in sorted(mappings.items()):
                code += f"        {repr(py_name)}: {repr(proto_name)},\n"
            code += "    },\n"
        else:
            code += line + "\n"
    code += "}\n"
    code += "\n"

    return code


def generate_packets_file(
    packets: dict[str, Any],
    fields: dict[str, Any],
    compound_fields: dict[str, Any] | None = None,
    unions: dict[str, Any] | None = None,
    packets_as_fields: dict[str, Any] | None = None,
    enums: dict[str, Any] | None = None,
) -> str:
    """Generate complete packets.py file.

    Args:
        packets: Packet definitions
        fields: Field definitions (for imports)
        compound_fields: Compound field definitions (for imports)
        unions: Union definitions (for imports)
        packets_as_fields: Packets that are also used as field types (for imports)
        enums: Enum definitions for detecting enum types

    Returns:
        Complete Python file content
    """
    # Extract enum names for pack/unpack generation
    enum_names = set(enums.keys()) if enums else set()

    # Collect all field types and enum types used in packets
    used_fields = set()
    used_enums = set()
    all_fields = {**fields}
    if compound_fields:
        all_fields.update(compound_fields)
    if unions:
        all_fields.update(unions)
    if packets_as_fields:
        all_fields.update(packets_as_fields)

    # Flatten packets to scan for used field types
    flat_packets: list[dict[str, Any]] = []
    for value in packets.values():
        if isinstance(value, dict):
            # Check if this is a category grouping
            if any(isinstance(v, dict) and "pkt_type" in v for v in value.values()):
                # New format: grouped by category
                for packet_def in value.values():
                    flat_packets.append(packet_def)
            elif "pkt_type" in value:
                # Old format: direct packet
                flat_packets.append(value)

    for packet_def in flat_packets:
        fields_data = packet_def.get("fields", [])
        # Handle both list and dict formats
        if isinstance(fields_data, list):
            for field_item in fields_data:
                if "type" in field_item:
                    field_type = field_item["type"]
                    base_type, _, is_nested = parse_field_type(field_type)
                    if is_nested:
                        if base_type in all_fields:
                            used_fields.add(base_type)
                        elif base_type in enum_names:
                            used_enums.add(base_type)
        elif isinstance(fields_data, dict):
            for field_type in fields_data.values():
                base_type, _, is_nested = parse_field_type(field_type)
                if is_nested:
                    if base_type in all_fields:
                        used_fields.add(base_type)
                    elif base_type in enum_names:
                        used_enums.add(base_type)

    # Generate imports with collision detection
    imports = ""
    all_imports = sorted(used_fields | used_enums)
    if all_imports:
        # Detect name collisions with packet category names
        category_names = set()
        for category in packets.keys():
            if isinstance(packets[category], dict):
                # Convert category name to class name (same as in generate_nested_packet_code)
                parts = category.split("_")
                category_class = "".join(part.capitalize() for part in parts)
                category_names.add(category_class)

        # Generate import list with aliases for collisions
        import_items = []
        type_aliases = {}  # Map original name to aliased name
        for name in all_imports:
            if name in category_names:
                # Use alias to avoid collision
                aliased_name = f"{name}Field"
                import_items.append(f"{name} as {aliased_name}")
                type_aliases[name] = aliased_name
            else:
                import_items.append(name)

        imports = format_long_import(import_items) + "\n"
    else:
        type_aliases = {}
        imports = ""

    header = f'''"""Auto-generated LIFX protocol packets.

DO NOT EDIT THIS FILE MANUALLY.
Generated from https://github.com/LIFX/public-protocol/blob/main/protocol.yml
by protocol/generator.py

Uses nested packet classes organized by category (Device, Light, etc.).
Each packet inherits from base Packet class which provides generic pack/unpack.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from lifx.protocol.base import Packet
{imports}
'''

    code = header
    packet_code = generate_nested_packet_code(packets, type_aliases)
    code += packet_code

    # Generate packet registry for nested classes
    code += "\n\n"
    code += "# Packet Registry - maps packet type to nested packet class\n"
    code += "PACKET_REGISTRY: dict[int, type[Packet]] = {\n"

    # Build registry with nested class paths
    registry_items = []
    for category, value in packets.items():
        if isinstance(value, dict):
            # Check if this is a category grouping
            if any(isinstance(v, dict) and "pkt_type" in v for v in value.values()):
                # New format: grouped by category
                # Quirk: Convert category names to proper camel case (multi_zone -> MultiZone)
                parts = category.split("_")
                category_class = "".join(part.capitalize() for part in parts)
                for packet_name, packet_def in value.items():
                    pkt_type = packet_def.get("pkt_type")
                    if pkt_type is not None:
                        # Remove category prefix to get short name
                        # Use case-insensitive matching to handle multi_zone -> Multizone -> MultiZone
                        short_name = packet_name
                        if packet_name.lower().startswith(category_class.lower()):
                            short_name = packet_name[len(category_class) :]

                        # Quirk: Rename Light.Get/Set/State to Light.GetColor/SetColor/StateColor
                        if category_class == "Light":
                            if short_name == "Get":
                                short_name = "GetColor"
                            elif short_name == "State":
                                short_name = "StateColor"

                        # Quirk: Rename extended multizone packets to follow standard naming convention
                        short_name = apply_extended_multizone_packet_quirks(
                            short_name, category_class
                        )

                        # Full path: Category.ShortName
                        full_path = f"{category_class}.{short_name}"
                        registry_items.append((pkt_type, full_path))

    # Sort by packet type for readability
    for pkt_type, full_path in sorted(registry_items):
        code += f"    {pkt_type}: {full_path},\n"

    code += "}\n"
    code += "\n\n"
    code += "def get_packet_class(pkt_type: int) -> type[Packet] | None:\n"
    code += '    """Get packet class for a given packet type.\n'
    code += "\n"
    code += "    Args:\n"
    code += "        pkt_type: Packet type number\n"
    code += "\n"
    code += "    Returns:\n"
    code += "        Nested packet class, or None if unknown\n"
    code += '    """\n'
    code += "    return PACKET_REGISTRY.get(pkt_type)\n"

    return code


def download_protocol() -> dict[str, Any]:
    """Download and parse protocol.yml from LIFX GitHub repository.

    Returns:
        Parsed protocol dictionary

    Raises:
        URLError: If download fails
        yaml.YAMLError: If parsing fails
    """
    parsed_url = urlparse(PROTOCOL_URL)
    if parsed_url.scheme == "https" and parsed_url.netloc.startswith(
        "raw.githubusercontent.com"
    ):
        print(f"Downloading protocol.yml from {PROTOCOL_URL}...")
        with urlopen(PROTOCOL_URL) as response:  # nosec B310
            protocol_data = response.read()

        print("Parsing protocol specification...")
        protocol = yaml.safe_load(protocol_data)
        return protocol


def validate_protocol_spec(protocol: dict[str, Any]) -> list[str]:
    """Validate protocol specification for missing type references.

    Args:
        protocol: Parsed protocol dictionary

    Returns:
        List of error messages (empty if validation passes)
    """
    errors: list[str] = []
    registry = TypeRegistry()

    # Register all types
    enums = protocol.get("enums", {})
    fields = protocol.get("fields", {})
    compound_fields = protocol.get("compound_fields", {})
    unions = protocol.get("unions", {})
    packets = protocol.get("packets", {})

    # Register enums
    for enum_name in enums.keys():
        registry.register_enum(enum_name)

    # Register field structures
    for field_name in fields.keys():
        registry.register_field(field_name)

    # Register compound fields
    for field_name in compound_fields.keys():
        registry.register_field(field_name)

    # Register unions
    for union_name in unions.keys():
        registry.register_union(union_name)

    # Register packets (flatten by category)
    for category_packets in packets.values():
        if isinstance(category_packets, dict):
            for packet_name in category_packets.keys():
                registry.register_packet(packet_name)

    # Validate field type references
    def validate_field_types(struct_name: str, struct_def: dict[str, Any]) -> None:
        """Validate all field types in a structure."""
        if isinstance(struct_def, dict) and "fields" in struct_def:
            for field_item in struct_def["fields"]:
                if "type" in field_item:
                    field_type = field_item["type"]
                    field_name = field_item.get("name", "reserved")
                    base_type, _, _ = parse_field_type(field_type)

                    # Check if type is defined
                    if not registry.has_type(base_type):
                        errors.append(
                            f"{struct_name}.{field_name}: Unknown type '{base_type}' in field type '{field_type}'"
                        )

    # Validate fields
    for field_name, field_def in fields.items():
        validate_field_types(f"fields.{field_name}", field_def)

    # Validate compound fields
    for field_name, field_def in compound_fields.items():
        validate_field_types(f"compound_fields.{field_name}", field_def)

    # Validate unions
    for union_name, union_def in unions.items():
        validate_field_types(f"unions.{union_name}", union_def)

    # Validate packets
    for category, category_packets in packets.items():
        if isinstance(category_packets, dict):
            for packet_name, packet_def in category_packets.items():
                if isinstance(packet_def, dict):
                    validate_field_types(
                        f"packets.{category}.{packet_name}", packet_def
                    )

    return errors


def should_skip_button_relay(name: str) -> bool:
    """Check if a name should be skipped (Button or Relay related).

    Args:
        name: Type name to check (enum, field, union, packet, or category)

    Returns:
        True if the name starts with Button or Relay, False otherwise
    """
    return name.startswith("Button") or name.startswith("Relay")


def filter_button_relay_items(items: dict[str, Any]) -> dict[str, Any]:
    """Filter out Button and Relay items from a dictionary.

    Args:
        items: Dictionary of items to filter

    Returns:
        Filtered dictionary without Button/Relay items
    """
    return {
        name: value
        for name, value in items.items()
        if not should_skip_button_relay(name)
    }


def filter_button_relay_packets(packets: dict[str, Any]) -> dict[str, Any]:
    """Filter out button and relay category packets.

    Args:
        packets: Dictionary of packet definitions (grouped by category)

    Returns:
        Filtered dictionary without button/relay categories
    """
    return {
        category: category_packets
        for category, category_packets in packets.items()
        if category not in ("button", "relay")
    }


def extract_packets_as_fields(
    packets: dict[str, Any], fields: dict[str, Any]
) -> dict[str, Any]:
    """Extract packets that are used as field types in other structures.

    Args:
        packets: Dictionary of packet definitions
        fields: Dictionary of field definitions to scan

    Returns:
        Dictionary of packet definitions that are referenced as field types
    """
    packets_as_fields = {}

    # Flatten packets first
    flat_packets = {}
    for category, category_packets in packets.items():
        if isinstance(category_packets, dict):
            for packet_name, packet_def in category_packets.items():
                if isinstance(packet_def, dict) and "pkt_type" in packet_def:
                    flat_packets[packet_name] = packet_def

    # Scan all fields for references to packet types
    all_structures = {**fields}

    for struct_def in all_structures.values():
        if isinstance(struct_def, dict) and "fields" in struct_def:
            for field_item in struct_def["fields"]:
                if "type" in field_item:
                    field_type = field_item["type"]
                    base_type, _, is_nested = parse_field_type(field_type)

                    # Check if this references a packet
                    if is_nested and base_type in flat_packets:
                        packets_as_fields[base_type] = flat_packets[base_type]

    return packets_as_fields


def main() -> None:
    """Main generator entry point."""
    try:
        # Download and parse protocol from GitHub
        protocol = download_protocol()
    except Exception as e:
        print(f"Error: Failed to download protocol.yml: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract sections
    enums = protocol.get("enums", {})
    fields = protocol.get("fields", {})
    compound_fields = protocol.get("compound_fields", {})
    unions = protocol.get("unions", {})
    packets = protocol.get("packets", {})

    # Filter out Button and Relay items (not relevant for light control)
    print("Filtering out Button and Relay items...")
    enums = filter_button_relay_items(enums)
    fields = filter_button_relay_items(fields)
    compound_fields = filter_button_relay_items(compound_fields)
    unions = filter_button_relay_items(unions)
    packets = filter_button_relay_packets(packets)

    # Apply local quirks to fix protocol issues
    print("Applying local protocol quirks...")
    enums, fields, compound_fields = apply_firmware_effect_enum_quirk(
        enums, fields, compound_fields
    )
    enums, packets = apply_multizone_application_request_quirk(enums, packets)
    fields = apply_tile_effect_parameter_quirk(fields)
    fields = apply_tile_state_device_quirk(fields)
    packets = apply_sensor_packet_quirks(packets)

    # Rebuild protocol dict with filtered items for validation
    filtered_protocol = {
        **protocol,
        "enums": enums,
        "fields": fields,
        "compound_fields": compound_fields,
        "unions": unions,
        "packets": packets,
    }

    # Validate filtered protocol specification
    print("Validating protocol specification...")
    validation_errors = validate_protocol_spec(filtered_protocol)
    if validation_errors:
        print("Validation failed with the following errors:", file=sys.stderr)
        for error in validation_errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)
    print("Validation passed!")

    # Extract packets that are used as field types (e.g., DeviceStateVersion)
    packets_as_fields = extract_packets_as_fields(packets, fields)

    print(f"Found {len(unions)} unions")
    print(
        f"Found {len(packets_as_fields)} packets used as field types: {list(packets_as_fields.keys())}"
    )

    # Determine output directory
    project_root = Path(__file__).parent.parent.parent.parent
    protocol_dir = project_root / "src" / "lifx" / "protocol"

    # Generate protocol_types.py (avoid conflict with Python's types module)
    types_code = generate_types_file(
        enums, fields, compound_fields, unions, packets_as_fields
    )
    types_file = protocol_dir / "protocol_types.py"
    with open(types_file, "w") as f:
        f.write(types_code)
    print(f"Generated {types_file}")

    # Generate packets.py
    packets_code = generate_packets_file(
        packets, fields, compound_fields, unions, packets_as_fields, enums
    )
    packets_file = protocol_dir / "packets.py"
    with open(packets_file, "w") as f:
        f.write(packets_code)
    print(f"Generated {packets_file}")


if __name__ == "__main__":
    main()
