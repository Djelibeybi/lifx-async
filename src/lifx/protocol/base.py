"""Base packet class for LIFX protocol.

Provides generic pack/unpack functionality for all packet types.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, ClassVar

_LOGGER = logging.getLogger(__name__)


@dataclass
class Packet:
    """Base class for all LIFX protocol packets.

    Each packet subclass defines:
    - PKT_TYPE: ClassVar[int] - The packet type number
    - _fields: ClassVar[list[dict]] - Field metadata from protocol.yml
    - Actual field attributes as dataclass fields
    """

    PKT_TYPE: ClassVar[int]
    _fields: ClassVar[list[dict[str, Any]]]
    _field_info: ClassVar[list[tuple[str, str, int]] | None] = None

    @property
    def as_dict(self) -> dict[str, Any]:
        """Return packet as dictionary."""
        return asdict(self)

    def pack(self) -> bytes:
        """Pack packet to bytes using field metadata.

        Returns:
            Packed bytes ready to send in a LIFX message payload
        """
        from lifx.protocol import serializer

        result = b""

        for field_item in self._fields:
            # Handle reserved fields (no name)
            if "name" not in field_item:
                size_bytes = field_item.get("size_bytes", 0)
                result += serializer.pack_reserved(size_bytes)
                continue

            # Get field value from instance
            field_name = self._protocol_to_python_name(field_item["name"])
            value = getattr(self, field_name)

            # Pack based on type
            field_type = field_item["type"]
            size_bytes = field_item.get("size_bytes", 0)
            result += self._pack_field_value(value, field_type, size_bytes)

        return result

    @classmethod
    def unpack(cls, data: bytes, offset: int = 0) -> Packet:
        """Unpack packet from bytes using field metadata.

        Args:
            data: Bytes to unpack from
            offset: Offset in bytes to start unpacking

        Returns:
            Packet instance with label fields decoded to strings
        """
        packet, _ = cls._unpack_internal(data, offset)

        # Decode label fields from bytes to string in-place
        # This ensures all State packets have human-readable labels
        cls._decode_labels_inplace(packet)

        # Log packet values after unpacking and decoding labels
        packet_values = asdict(packet)
        _LOGGER.debug(
            {
                "class": "Packet",
                "method": "unpack",
                "packet_type": type(packet).__name__,
                "values": packet_values,
            }
        )

        return packet

    @classmethod
    def _compute_field_info(cls) -> list[tuple[str, str, int]]:
        """Pre-compute parsed field metadata for faster unpacking.

        This optimization caches the parsing of field metadata to avoid
        repeated dictionary lookups and name conversions during unpacking.

        Returns:
            List of tuples: (field_name, field_type, size_bytes)
            Reserved fields have empty string as field_name
        """
        info: list[tuple[str, str, int]] = []

        for field_item in cls._fields:
            size_bytes = field_item.get("size_bytes", 0)

            # Handle reserved fields (no name)
            if "name" not in field_item:
                info.append(("", "", size_bytes))
                continue

            # Regular field
            field_name = cls._protocol_to_python_name(field_item["name"])
            field_type = field_item["type"]
            info.append((field_name, field_type, size_bytes))

        return info

    @classmethod
    def _unpack_internal(cls, data: bytes, offset: int) -> tuple[Packet, int]:
        """Internal method for unpacking packets with offset tracking.

        This method handles the recursion needed for nested structures.

        Args:
            data: Bytes to unpack from
            offset: Offset in bytes to start unpacking

        Returns:
            Tuple of (packet_instance, new_offset)
        """
        # Pre-compute field info on first use (lazy initialization)
        if cls._field_info is None:
            cls._field_info = cls._compute_field_info()

        current_offset = offset
        field_values: dict[str, Any] = {}

        for field_name, field_type, size_bytes in cls._field_info:
            # Handle reserved fields (empty name)
            if not field_name:
                current_offset += size_bytes
                continue

            # Unpack field value
            value, current_offset = cls._unpack_field_value(
                data, field_type, size_bytes, current_offset
            )
            field_values[field_name] = value

        return cls(**field_values), current_offset

    @staticmethod
    def _protocol_to_python_name(name: str) -> str:
        """Convert protocol name (PascalCase) to Python name (snake_case)."""
        import re

        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name)
        return snake.lower()

    def _pack_field_value(self, value: Any, field_type: str, size_bytes: int) -> bytes:
        """Pack a single field value based on its type."""
        from lifx.protocol import serializer

        # Parse field type
        base_type, array_count, is_nested = self._parse_field_type(field_type)

        # Check if it's an enum (Button/Relay enums excluded)
        enum_types = {
            "DeviceService",
            "LightLastHevCycleResult",
            "LightWaveform",
            "MultiZoneApplicationRequest",
            "FirmwareEffect",
        }
        is_enum = is_nested and base_type in enum_types

        # Handle different field types
        if array_count:
            if is_enum:
                # Array of enums
                result = b""
                for item in value:
                    result += serializer.pack_value(int(item), "uint8")
                return result
            elif is_nested:
                # Array of nested structures
                result = b""
                for item in value:
                    result += item.pack()
                return result
            elif base_type in ("uint8", "byte"):
                # Byte array
                return serializer.pack_bytes(value, size_bytes)
            else:
                # Array of primitives
                return serializer.pack_array(value, base_type, array_count)
        elif is_enum:
            # Single enum
            return serializer.pack_value(int(value), "uint8")
        elif is_nested:
            # Nested structure
            return value.pack()
        else:
            # Primitive type
            return serializer.pack_value(value, base_type)

    @classmethod
    def _unpack_field_value(
        cls, data: bytes, field_type: str, size_bytes: int, offset: int
    ) -> tuple[Any, int]:
        """Unpack a single field value based on its type."""
        from lifx.protocol import serializer
        from lifx.protocol.protocol_types import (
            DeviceService,
            FirmwareEffect,
            LightLastHevCycleResult,
            LightWaveform,
            MultiZoneApplicationRequest,
        )

        # Parse field type
        base_type, array_count, is_nested = cls._parse_field_type(field_type)

        # Check if it's an enum (Button/Relay enums excluded)
        enum_types = {
            "DeviceService": DeviceService,
            "LightLastHevCycleResult": LightLastHevCycleResult,
            "LightWaveform": LightWaveform,
            "MultiZoneApplicationRequest": MultiZoneApplicationRequest,
            "FirmwareEffect": FirmwareEffect,
        }
        is_enum = is_nested and base_type in enum_types

        # Handle different field types
        if array_count:
            if is_enum:
                # Array of enums
                result = []
                current_offset = offset
                enum_class = enum_types[base_type]
                for _ in range(array_count):
                    item_raw, current_offset = serializer.unpack_value(
                        data, "uint8", current_offset
                    )
                    result.append(enum_class(item_raw))
                return result, current_offset
            elif is_nested:
                # Array of nested structures - need to import dynamically
                from lifx.protocol import protocol_types

                struct_class = getattr(protocol_types, base_type)
                result = []
                current_offset = offset
                for _ in range(array_count):
                    # Check if it's a Packet subclass or protocol_types class
                    if issubclass(struct_class, cls):
                        item, current_offset = struct_class._unpack_internal(
                            data, current_offset
                        )
                    else:
                        # struct_class returns tuple[T, int]
                        item, current_offset = struct_class.unpack(data, current_offset)  # type: ignore[misc]
                    result.append(item)
                return result, current_offset
            elif base_type in ("uint8", "byte"):
                # Byte array
                return serializer.unpack_bytes(data, size_bytes, offset)
            else:
                # Array of primitives
                return serializer.unpack_array(data, base_type, array_count, offset)
        elif is_enum:
            # Single enum
            enum_class = enum_types[base_type]
            value_raw, new_offset = serializer.unpack_value(data, "uint8", offset)
            return enum_class(value_raw), new_offset
        elif is_nested:
            # Nested structure - import dynamically
            from lifx.protocol import protocol_types

            struct_class = getattr(protocol_types, base_type)
            # Check if it's a Packet subclass or protocol_types class
            if issubclass(struct_class, cls):
                return struct_class._unpack_internal(data, offset)
            else:
                return struct_class.unpack(data, offset)
        else:
            # Primitive type
            return serializer.unpack_value(data, base_type, offset)

    @staticmethod
    def _decode_labels_inplace(packet: object) -> None:
        """Decode label fields from bytes to string in-place.

        Automatically finds and decodes any field named 'label' or ending with '_label'
        for all State packets. This ensures human-readable labels in all contexts.

        Args:
            packet: Packet instance to process (modified in-place)
        """
        from dataclasses import fields, is_dataclass

        if not is_dataclass(packet):
            return

        for field_info in fields(packet):
            # Check if this looks like a label field
            if field_info.name == "label" or field_info.name.endswith("_label"):
                value = getattr(packet, field_info.name)
                if isinstance(value, bytes):
                    # Decode: strip null terminator, decode UTF-8
                    decoded = value.rstrip(b"\x00").decode("utf-8")
                    # Use object.__setattr__ to bypass frozen dataclass if needed
                    object.__setattr__(packet, field_info.name, decoded)

    @staticmethod
    def _parse_field_type(field_type: str) -> tuple[str, int | None, bool]:
        """Parse a field type string.

        Args:
            field_type: Field type (e.g., 'uint16', '[32]uint8', '<HSBK>')

        Returns:
            Tuple of (base_type, array_count, is_nested)
        """
        import re

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
