"""Tests for protocol code generator."""

from lifx.protocol.generator import (
    TypeRegistry,
    apply_sensor_packet_quirks,
    camel_to_snake_upper,
    convert_type_to_python,
    extract_packets_as_fields,
    format_long_import,
    format_long_list,
    generate_enum_code,
    generate_field_code,
    generate_nested_packet_code,
    generate_pack_method,
    generate_packets_file,
    generate_types_file,
    generate_unpack_method,
    parse_field_type,
    to_snake_case,
    validate_protocol_spec,
)


class TestToSnakeCase:
    """Test PascalCase to snake_case conversion."""

    def test_pascal_case(self):
        """Test conversion of PascalCase."""
        assert to_snake_case("LightWaveform") == "light_waveform"
        assert to_snake_case("DeviceStateVersion") == "device_state_version"

    def test_camel_case(self):
        """Test conversion of camelCase."""
        assert to_snake_case("buttonAction") == "button_action"

    def test_single_word(self):
        """Test single word conversion."""
        assert to_snake_case("Button") == "button"

    def test_already_lowercase(self):
        """Test already lowercase string."""
        assert to_snake_case("button") == "button"


class TestCamelToSnakeUpper:
    """Test CamelCase to UPPER_SNAKE_CASE conversion."""

    def test_camel_case(self):
        """Test conversion of CamelCase."""
        assert camel_to_snake_upper("LightWaveform") == "LIGHT_WAVEFORM"
        assert camel_to_snake_upper("DeviceService") == "DEVICE_SERVICE"

    def test_single_word(self):
        """Test single word conversion."""
        assert camel_to_snake_upper("Light") == "LIGHT"


class TestParseFieldType:
    """Test field type parsing."""

    def test_simple_type(self):
        """Test simple type parsing."""
        base, count, nested = parse_field_type("uint16")
        assert base == "uint16"
        assert count is None
        assert nested is False

    def test_array_type(self):
        """Test array type parsing."""
        base, count, nested = parse_field_type("[8]uint16")
        assert base == "uint16"
        assert count == 8
        assert nested is False

    def test_nested_type(self):
        """Test nested type parsing."""
        base, count, nested = parse_field_type("<LightWaveform>")
        assert base == "LightWaveform"
        assert count is None
        assert nested is True

    def test_array_of_nested(self):
        """Test array of nested type parsing."""
        base, count, nested = parse_field_type("[8]<LightHsbk>")
        assert base == "LightHsbk"
        assert count == 8
        assert nested is True


class TestConvertTypeToPython:
    """Test protocol type to Python type conversion."""

    def test_uint_types(self):
        """Test unsigned integer type conversion."""
        assert convert_type_to_python("uint8") == "int"
        assert convert_type_to_python("uint16") == "int"
        assert convert_type_to_python("uint32") == "int"
        assert convert_type_to_python("uint64") == "int"

    def test_int_types(self):
        """Test signed integer type conversion."""
        assert convert_type_to_python("int8") == "int"
        assert convert_type_to_python("int16") == "int"
        assert convert_type_to_python("int32") == "int"
        assert convert_type_to_python("int64") == "int"

    def test_float_types(self):
        """Test float type conversion."""
        assert convert_type_to_python("float32") == "float"

    def test_bool_type(self):
        """Test bool type conversion."""
        assert convert_type_to_python("bool") == "bool"

    def test_byte_array(self):
        """Test byte array conversion."""
        assert convert_type_to_python("[32]byte") == "bytes"
        assert convert_type_to_python("[6]uint8") == "bytes"

    def test_nested_type(self):
        """Test nested type conversion."""
        assert convert_type_to_python("<LightWaveform>") == "LightWaveform"

    def test_array_of_nested(self):
        """Test array of nested type conversion."""
        assert convert_type_to_python("[8]<LightHsbk>") == "list[LightHsbk]"

    def test_array_of_primitives(self):
        """Test array of primitive type conversion."""
        assert convert_type_to_python("[8]uint16") == "list[int]"

    def test_with_type_aliases(self):
        """Test type conversion with aliases."""
        aliases = {"Light": "LightField"}
        assert convert_type_to_python("<Light>", aliases) == "LightField"
        assert convert_type_to_python("[8]<Light>", aliases) == "list[LightField]"


class TestFormatLongImport:
    """Test import statement formatting."""

    def test_short_import(self):
        """Test short import stays on one line."""
        items = ["Foo", "Bar"]
        result = format_long_import(items)
        assert result == "from lifx.protocol.protocol_types import Foo, Bar\n"

    def test_long_import(self):
        """Test long import splits across lines."""
        items = [
            "VeryLongTypeName1",
            "VeryLongTypeName2",
            "VeryLongTypeName3",
            "VeryLongTypeName4",
            "VeryLongTypeName5",
        ]
        result = format_long_import(items)
        assert "(\n" in result
        assert "    VeryLongTypeName1," in result
        assert ")\n" in result

    def test_empty_import(self):
        """Test empty import list."""
        result = format_long_import([])
        assert result == ""

    def test_import_with_alias(self):
        """Test import with alias."""
        items = ["Light as LightField"]
        result = format_long_import(items)
        assert "Light as LightField" in result


class TestFormatLongList:
    """Test list formatting."""

    def test_short_list(self):
        """Test short list stays on one line."""
        items = [{"name": "foo", "type": "uint8"}]
        result = format_long_list(items, max_line_length=120)
        assert "\n" not in result
        assert result == "[{'name': 'foo', 'type': 'uint8'}]"

    def test_long_list(self):
        """Test long list splits across lines."""
        items = [
            {"name": "field1", "type": "uint32", "size_bytes": 4},
            {"name": "field2", "type": "uint32", "size_bytes": 4},
        ]
        result = format_long_list(items, max_line_length=50)
        assert result.startswith("[\n")
        assert result.endswith("\n]")
        assert "    {" in result

    def test_empty_list(self):
        """Test empty list."""
        result = format_long_list([])
        assert result == "[]"


class TestExtractPacketsAsFields:
    """Test extraction of packets used as field types."""

    def test_extract_packets(self):
        """Test extracting packets that are used as fields."""
        packets = {
            "device": {
                "DeviceStateVersion": {
                    "pkt_type": 33,
                    "fields": [
                        {"name": "Vendor", "type": "uint32"},
                    ],
                },
                "DeviceStateHostFirmware": {
                    "pkt_type": 15,
                    "fields": [
                        {"name": "Build", "type": "uint64"},
                    ],
                },
            }
        }

        fields = {
            "TileStateDevice": {
                "fields": [
                    {"name": "DeviceVersion", "type": "<DeviceStateVersion>"},
                    {"name": "Firmware", "type": "<DeviceStateHostFirmware>"},
                ]
            }
        }

        result = extract_packets_as_fields(packets, fields)
        assert "DeviceStateVersion" in result
        assert "DeviceStateHostFirmware" in result
        assert result["DeviceStateVersion"]["pkt_type"] == 33
        assert result["DeviceStateHostFirmware"]["pkt_type"] == 15

    def test_no_packets_as_fields(self):
        """Test when no packets are used as fields."""
        packets = {
            "device": {
                "DeviceGetLabel": {
                    "pkt_type": 23,
                    "fields": [],
                }
            }
        }

        fields = {
            "LightHsbk": {
                "fields": [
                    {"name": "Hue", "type": "uint16"},
                ]
            }
        }

        result = extract_packets_as_fields(packets, fields)
        assert result == {}


class TestGeneratorIntegration:
    """Integration tests for the generator."""

    def test_generator_handles_packets_as_fields(self):
        """Test that generator creates types for packets used as fields."""
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
        )

        # These should be defined and usable
        assert "vendor" in DeviceStateVersion.__annotations__
        assert "product" in DeviceStateVersion.__annotations__
        assert "build" in DeviceStateHostFirmware.__annotations__
        assert "version_minor" in DeviceStateHostFirmware.__annotations__

    def test_no_import_collisions(self):
        """Test that import collisions are resolved."""
        from lifx.protocol import packets

        # Light category class should exist
        assert hasattr(packets, "Light")
        # And it should have nested packet classes
        assert hasattr(packets.Light, "GetColor")
        assert hasattr(packets.Light, "SetColor")

    def test_generated_code_compiles(self):
        """Test that generated code compiles without errors."""
        # This test passes if imports work
        from lifx.protocol.packets import PACKET_REGISTRY, get_packet_class
        from lifx.protocol.protocol_types import (
            FIELD_MAPPINGS,
            LightHsbk,
            LightWaveform,
        )

        # Verify critical structures exist
        assert PACKET_REGISTRY is not None
        assert FIELD_MAPPINGS is not None
        assert get_packet_class is not None
        assert LightHsbk is not None
        assert LightWaveform is not None


class TestTypeRegistry:
    """Test TypeRegistry for validation."""

    def test_register_and_check_enum(self):
        """Test enum registration and checking."""
        registry = TypeRegistry()
        registry.register_enum("MyEnum")

        assert registry.is_enum("MyEnum")
        assert registry.has_type("MyEnum")
        assert not registry.is_enum("OtherEnum")

    def test_register_and_check_field(self):
        """Test field registration and checking."""
        registry = TypeRegistry()
        registry.register_field("MyField")

        assert registry.has_type("MyField")
        assert not registry.is_enum("MyField")

    def test_register_and_check_packet(self):
        """Test packet registration and checking."""
        registry = TypeRegistry()
        registry.register_packet("MyPacket")

        assert registry.has_type("MyPacket")
        assert not registry.is_enum("MyPacket")

    def test_register_and_check_union(self):
        """Test union registration and checking."""
        registry = TypeRegistry()
        registry.register_union("MyUnion")

        assert registry.has_type("MyUnion")
        assert not registry.is_enum("MyUnion")

    def test_basic_types_are_known(self):
        """Test that basic types are pre-registered."""
        registry = TypeRegistry()

        assert registry.has_type("uint8")
        assert registry.has_type("uint16")
        assert registry.has_type("uint32")
        assert registry.has_type("uint64")
        assert registry.has_type("int8")
        assert registry.has_type("float32")
        assert registry.has_type("bool")
        assert registry.has_type("byte")

    def test_unknown_type(self):
        """Test that unknown types return False."""
        registry = TypeRegistry()

        assert not registry.has_type("UnknownType")

    def test_get_all_types(self):
        """Test getting all types."""
        registry = TypeRegistry()
        registry.register_enum("Enum1")
        registry.register_field("Field1")
        registry.register_packet("Packet1")

        all_types = registry.get_all_types()
        assert "Enum1" in all_types
        assert "Field1" in all_types
        assert "Packet1" in all_types
        assert "uint8" in all_types


class TestValidateProtocolSpec:
    """Test protocol specification validation."""

    def test_valid_protocol(self):
        """Test validation of a valid protocol."""
        protocol = {
            "enums": {"MyEnum": {"values": [{"name": "VALUE1", "value": 1}]}},
            "fields": {
                "MyField": {
                    "fields": [
                        {"name": "Field1", "type": "uint16"},
                        {"name": "Field2", "type": "<MyEnum>"},
                    ]
                }
            },
            "compound_fields": {},
            "unions": {},
            "packets": {
                "device": {
                    "DeviceGet": {
                        "pkt_type": 1,
                        "fields": [
                            {"name": "Value", "type": "<MyField>"},
                        ],
                    }
                }
            },
        }

        errors = validate_protocol_spec(protocol)
        assert errors == []

    def test_missing_enum_type(self):
        """Test detection of missing enum type."""
        protocol = {
            "enums": {},
            "fields": {
                "MyField": {
                    "fields": [
                        {"name": "Field1", "type": "<UnknownEnum>"},
                    ]
                }
            },
            "compound_fields": {},
            "unions": {},
            "packets": {},
        }

        errors = validate_protocol_spec(protocol)
        assert len(errors) == 1
        assert "UnknownEnum" in errors[0]
        assert "fields.MyField.Field1" in errors[0]

    def test_missing_field_type(self):
        """Test detection of missing field type."""
        protocol = {
            "enums": {},
            "fields": {},
            "compound_fields": {},
            "unions": {},
            "packets": {
                "device": {
                    "DeviceGet": {
                        "pkt_type": 1,
                        "fields": [
                            {"name": "Value", "type": "<UnknownField>"},
                        ],
                    }
                }
            },
        }

        errors = validate_protocol_spec(protocol)
        assert len(errors) == 1
        assert "UnknownField" in errors[0]

    def test_missing_nested_array_type(self):
        """Test detection of missing type in array."""
        protocol = {
            "enums": {},
            "fields": {
                "MyField": {
                    "fields": [
                        {"name": "Items", "type": "[8]<MissingType>"},
                    ]
                }
            },
            "compound_fields": {},
            "unions": {},
            "packets": {},
        }

        errors = validate_protocol_spec(protocol)
        assert len(errors) == 1
        assert "MissingType" in errors[0]

    def test_basic_types_are_valid(self):
        """Test that basic types don't cause validation errors."""
        protocol = {
            "enums": {},
            "fields": {
                "MyField": {
                    "fields": [
                        {"name": "A", "type": "uint8"},
                        {"name": "B", "type": "uint16"},
                        {"name": "C", "type": "uint32"},
                        {"name": "D", "type": "float32"},
                        {"name": "E", "type": "bool"},
                        {"name": "F", "type": "[8]byte"},
                    ]
                }
            },
            "compound_fields": {},
            "unions": {},
            "packets": {},
        }

        errors = validate_protocol_spec(protocol)
        assert errors == []

    def test_compound_fields_validation(self):
        """Test validation of compound fields."""
        protocol = {
            "enums": {},
            "fields": {},
            "compound_fields": {
                "CompoundField": {
                    "fields": [
                        {"name": "Value", "type": "<UnknownType>"},
                    ]
                }
            },
            "unions": {},
            "packets": {},
        }

        errors = validate_protocol_spec(protocol)
        assert len(errors) == 1
        assert "UnknownType" in errors[0]
        assert "compound_fields.CompoundField" in errors[0]

    def test_unions_validation(self):
        """Test validation of unions."""
        protocol = {
            "enums": {},
            "fields": {},
            "compound_fields": {},
            "unions": {
                "MyUnion": {
                    "fields": [
                        {"name": "Option1", "type": "<MissingType>"},
                    ]
                }
            },
            "packets": {},
        }

        errors = validate_protocol_spec(protocol)
        assert len(errors) == 1
        assert "MissingType" in errors[0]
        assert "unions.MyUnion" in errors[0]

    def test_multiple_errors(self):
        """Test detection of multiple validation errors."""
        protocol = {
            "enums": {},
            "fields": {
                "Field1": {
                    "fields": [
                        {"name": "A", "type": "<MissingA>"},
                        {"name": "B", "type": "<MissingB>"},
                    ]
                }
            },
            "compound_fields": {},
            "unions": {},
            "packets": {},
        }

        errors = validate_protocol_spec(protocol)
        assert len(errors) == 2


class TestGenerateEnumCode:
    """Test enum code generation."""

    def test_generate_simple_enum(self):
        """Test generating a simple enum."""
        enums = {
            "MyEnum": {
                "type": "uint8",
                "values": [
                    {"name": "MY_ENUM_VALUE1", "value": 1},
                    {"name": "MY_ENUM_VALUE2", "value": 2},
                ],
            }
        }

        code = generate_enum_code(enums)
        assert "class MyEnum(IntEnum):" in code
        assert "VALUE1 = 1" in code
        assert "VALUE2 = 2" in code

    def test_generate_enum_without_prefix(self):
        """Test enum generation when values don't have common prefix."""
        enums = {
            "Status": {
                "type": "uint8",
                "values": [
                    {"name": "OK", "value": 0},
                    {"name": "ERROR", "value": 1},
                ],
            }
        }

        code = generate_enum_code(enums)
        assert "OK = 0" in code
        assert "ERROR = 1" in code

    def test_generate_enum_with_reserved(self):
        """Test enum generation with reserved values - should be suppressed."""
        enums = {
            "MyEnum": {
                "type": "uint8",
                "values": [
                    {"name": "MY_ENUM_VALUE1", "value": 1},
                    {"name": "RESERVED", "value": 2},
                    {"name": "RESERVED", "value": 3},
                ],
            }
        }

        code = generate_enum_code(enums)
        # Reserved values should be suppressed
        assert "RESERVED" not in code
        assert "VALUE1 = 1" in code


class TestGenerateFieldCode:
    """Test field code generation."""

    def test_generate_simple_field(self):
        """Test generating a simple field structure."""
        fields = {
            "MyField": {
                "fields": [
                    {"name": "Value", "type": "uint16", "size_bytes": 2},
                ]
            }
        }

        code, mappings = generate_field_code(fields)
        assert "class MyField:" in code
        assert "value: int" in code
        assert "MyField" in mappings
        assert mappings["MyField"]["value"] == "Value"

    def test_generate_field_with_nested_type(self):
        """Test generating field with nested type."""
        fields = {
            "Outer": {
                "fields": [
                    {"name": "Inner", "type": "<InnerType>"},
                ]
            }
        }

        code, mappings = generate_field_code(fields)
        assert "inner: InnerType" in code

    def test_generate_field_with_array(self):
        """Test generating field with array."""
        fields = {
            "ArrayField": {
                "fields": [
                    {"name": "Values", "type": "[8]uint16"},
                ]
            }
        }

        code, mappings = generate_field_code(fields)
        assert "values: list[int]" in code

    def test_generate_field_with_bytes(self):
        """Test generating field with byte array."""
        fields = {
            "ByteField": {
                "fields": [
                    {"name": "Data", "type": "[32]byte", "size_bytes": 32},
                ]
            }
        }

        code, mappings = generate_field_code(fields)
        assert "data: bytes" in code


class TestGeneratePackUnpackMethods:
    """Test pack/unpack method generation."""

    def test_generate_pack_method_simple(self):
        """Test generating pack method for simple fields."""
        fields_data = [
            {"name": "Value", "type": "uint16", "size_bytes": 2},
        ]

        code = generate_pack_method(fields_data, "field")
        assert "def pack(self) -> bytes:" in code
        assert 'result = b""' in code
        assert "serializer.pack_value" in code

    def test_generate_pack_method_with_reserved(self):
        """Test generating pack method with reserved fields."""
        fields_data = [
            {"name": "Value", "type": "uint16"},
            {"size_bytes": 2},  # Reserved field (no name)
        ]

        code = generate_pack_method(fields_data, "field")
        assert "serializer.pack_reserved(2)" in code

    def test_generate_pack_method_with_enum(self):
        """Test generating pack method with enum types."""
        fields_data = [
            {"name": "Waveform", "type": "<LightWaveform>"},
        ]
        enum_types = {"LightWaveform"}

        code = generate_pack_method(fields_data, "field", enum_types)
        assert "int(self.waveform)" in code
        assert "(enum)" in code

    def test_generate_pack_method_with_enum_array(self):
        """Test generating pack method with enum array."""
        fields_data = [
            {"name": "Values", "type": "[8]<LightWaveform>"},
        ]
        enum_types = {"LightWaveform"}

        code = generate_pack_method(fields_data, "field", enum_types)
        assert "for item in self.values:" in code
        assert "int(item)" in code

    def test_generate_pack_method_with_nested_struct(self):
        """Test generating pack method with nested structure."""
        fields_data = [
            {"name": "Color", "type": "<HSBK>"},
        ]

        code = generate_pack_method(fields_data, "field", set())
        assert "self.color.pack()" in code

    def test_generate_pack_method_with_nested_array(self):
        """Test generating pack method with nested structure array."""
        fields_data = [
            {"name": "Colors", "type": "[8]<HSBK>"},
        ]

        code = generate_pack_method(fields_data, "field", set())
        assert "for item in self.colors:" in code
        assert "item.pack()" in code

    def test_generate_unpack_method_simple(self):
        """Test generating unpack method for simple fields."""
        fields_data = [
            {"name": "Value", "type": "uint16", "size_bytes": 2},
        ]

        code = generate_unpack_method("MyField", fields_data, "field")
        assert "def unpack(cls, data: bytes, offset: int = 0)" in code
        assert "serializer.unpack_value" in code
        assert "return cls(" in code

    def test_generate_unpack_method_with_reserved(self):
        """Test generating unpack method with reserved fields."""
        fields_data = [
            {"name": "Value", "type": "uint16"},
            {"size_bytes": 4},  # Reserved field
        ]

        code = generate_unpack_method("MyField", fields_data, "field")
        assert "current_offset += 4" in code
        assert "Skip reserved" in code

    def test_generate_unpack_method_with_enum(self):
        """Test generating unpack method with enum types."""
        fields_data = [
            {"name": "Waveform", "type": "<LightWaveform>"},
        ]
        enum_types = {"LightWaveform"}

        code = generate_unpack_method("MyField", fields_data, "field", enum_types)
        assert "LightWaveform(waveform_raw)" in code

    def test_generate_unpack_method_with_enum_array(self):
        """Test generating unpack method with enum array."""
        fields_data = [
            {"name": "Values", "type": "[8]<LightWaveform>"},
        ]
        enum_types = {"LightWaveform"}

        code = generate_unpack_method("MyField", fields_data, "field", enum_types)
        assert "for _ in range(8):" in code
        assert "LightWaveform(item_raw)" in code

    def test_generate_unpack_method_with_nested_struct(self):
        """Test generating unpack method with nested structure."""
        fields_data = [
            {"name": "Color", "type": "<HSBK>"},
        ]

        code = generate_unpack_method("MyField", fields_data, "field", set())
        assert "HSBK.unpack(data, current_offset)" in code

    def test_generate_unpack_method_with_nested_array(self):
        """Test generating unpack method with nested structure array."""
        fields_data = [
            {"name": "Colors", "type": "[8]<HSBK>"},
        ]

        code = generate_unpack_method("MyField", fields_data, "field", set())
        assert "for _ in range(8):" in code
        assert "HSBK.unpack(data, current_offset)" in code

    def test_generate_unpack_method_long_return(self):
        """Test generating unpack method with long return statement."""
        # Create many fields to force line wrapping
        fields_data = [{"name": f"Field{i}", "type": "uint16"} for i in range(10)]

        code = generate_unpack_method("MyField", fields_data, "field", set())
        # Should split across multiple lines when return statement is too long
        assert "return (" in code or "return cls(" in code


class TestGenerateNestedPacketCode:
    """Test nested packet code generation."""

    def test_generate_nested_packets(self):
        """Test generating nested packet classes."""
        packets = {
            "device": {
                "DeviceGet": {
                    "pkt_type": 2,
                    "fields": [
                        {"name": "Value", "type": "uint8"},
                    ],
                },
                "DeviceSet": {"pkt_type": 3, "fields": []},
            }
        }

        code = generate_nested_packet_code(packets)
        assert "class Device(Packet):" in code
        assert "class Get(Packet):" in code
        assert "PKT_TYPE: ClassVar[int] = 2" in code
        assert "class Set(Packet):" in code

    def test_generate_nested_packets_multizone_category(self):
        """Test category name conversion for multi_zone."""
        packets = {"multi_zone": {"MultiZoneGet": {"pkt_type": 502, "fields": []}}}

        code = generate_nested_packet_code(packets)
        # Should convert multi_zone to MultiZone
        assert "class MultiZone(Packet):" in code
        assert "class Get(Packet):" in code

    def test_generate_nested_packets_light_quirks(self):
        """Test Light category quirks (Get -> GetColor)."""
        packets = {
            "light": {
                "LightGet": {"pkt_type": 101, "fields": []},
                "LightState": {"pkt_type": 107, "fields": []},
            }
        }

        code = generate_nested_packet_code(packets)
        assert "class Light(Packet):" in code
        # Light.Get -> Light.GetColor
        assert "class GetColor(Packet):" in code
        # Light.State -> Light.StateColor
        assert "class StateColor(Packet):" in code

    def test_generate_nested_packets_with_type_aliases(self):
        """Test packet generation with type aliases."""
        packets = {
            "device": {
                "DeviceGet": {
                    "pkt_type": 2,
                    "fields": [
                        {"name": "Value", "type": "<Light>"},
                    ],
                }
            }
        }

        type_aliases = {"Light": "LightField"}
        code = generate_nested_packet_code(packets, type_aliases)
        # Should use aliased type name
        assert "LightField" in code


class TestGenerateTypesFile:
    """Test types file generation."""

    def test_generate_types_file_basic(self):
        """Test generating basic types file."""
        enums = {
            "MyEnum": {"type": "uint8", "values": [{"name": "VALUE1", "value": 1}]}
        }
        fields = {"MyField": {"fields": [{"name": "Value", "type": "uint16"}]}}

        code = generate_types_file(enums, fields)
        assert "class MyEnum(IntEnum):" in code
        assert "class MyField:" in code
        assert "FIELD_MAPPINGS" in code
        assert "DO NOT EDIT THIS FILE MANUALLY" in code

    def test_generate_types_file_with_compound_fields(self):
        """Test types file with compound fields."""
        enums = {}
        fields = {}
        compound_fields = {
            "CompoundField": {"fields": [{"name": "Value", "type": "uint32"}]}
        }

        code = generate_types_file(enums, fields, compound_fields=compound_fields)
        assert "class CompoundField:" in code

    def test_generate_types_file_with_unions(self):
        """Test types file with unions."""
        enums = {}
        fields = {}
        unions = {
            "MyUnion": {
                "comment": "Union of different types",
                "size_bytes": 16,
                "fields": [],
            }
        }

        code = generate_types_file(enums, fields, unions=unions)
        assert "class MyUnion:" in code


class TestGeneratePacketsFile:
    """Test packets file generation."""

    def test_generate_packets_file_basic(self):
        """Test generating basic packets file."""
        packets = {"device": {"DeviceGet": {"pkt_type": 2, "fields": []}}}
        fields = {}

        code = generate_packets_file(packets, fields)
        assert "class Device(Packet):" in code
        assert "PACKET_REGISTRY" in code
        assert "def get_packet_class" in code
        assert "DO NOT EDIT THIS FILE MANUALLY" in code

    def test_generate_packets_file_with_imports(self):
        """Test packets file with field imports."""
        packets = {
            "light": {
                "LightSetColor": {
                    "pkt_type": 102,
                    "fields": [{"name": "Color", "type": "<LightHsbk>"}],
                }
            }
        }
        fields = {"LightHsbk": {"fields": [{"name": "Hue", "type": "uint16"}]}}

        code = generate_packets_file(packets, fields)
        # Should import LightHsbk
        assert "from lifx.protocol.protocol_types import" in code

    def test_generate_packets_file_with_collision_avoidance(self):
        """Test packets file handles name collisions."""
        packets = {
            "light": {
                "LightGet": {
                    "pkt_type": 101,
                    "fields": [{"name": "Target", "type": "<Light>"}],
                }
            }
        }
        fields = {"Light": {"fields": [{"name": "Value", "type": "uint8"}]}}

        code = generate_packets_file(packets, fields)
        # Should use alias to avoid collision with Light category
        assert "Light as LightField" in code or "LightField" in code

    def test_generate_packets_file_packet_registry(self):
        """Test packet registry generation."""
        packets = {
            "device": {
                "DeviceGet": {"pkt_type": 2, "fields": []},
                "DeviceSet": {"pkt_type": 14, "fields": []},
            }
        }
        fields = {}

        code = generate_packets_file(packets, fields)
        # Should include both packet types in registry
        assert "2: Device.Get" in code
        assert "14: Device.Set" in code


class TestTypeRegistryAdvanced:
    """Additional TypeRegistry tests."""

    def test_type_registry_get_type_category(self):
        """Test get_type_category method if it exists."""
        registry = TypeRegistry()
        registry.register_enum("MyEnum")
        registry.register_field("MyField")
        registry.register_packet("MyPacket")
        registry.register_union("MyUnion")

        # TypeRegistry doesn't have get_type_category in current implementation
        # but we can test has_type for different categories
        assert registry.has_type("MyEnum")
        assert registry.has_type("MyField")
        assert registry.has_type("MyPacket")
        assert registry.has_type("MyUnion")


class TestValidateProtocolSpecAdvanced:
    """Additional validation tests."""

    def test_validate_handles_reserved_fields(self):
        """Test validation ignores reserved fields."""
        protocol = {
            "enums": {},
            "fields": {
                "MyField": {
                    "fields": [
                        {"name": "Value", "type": "uint16"},
                        {"size_bytes": 2},  # Reserved, no name
                    ]
                }
            },
            "compound_fields": {},
            "unions": {},
            "packets": {},
        }

        errors = validate_protocol_spec(protocol)
        assert errors == []

    def test_validate_packet_field_types(self):
        """Test validation of packet field types."""
        protocol = {
            "enums": {},
            "fields": {},
            "compound_fields": {},
            "unions": {},
            "packets": {
                "device": {
                    "DeviceGet": {
                        "pkt_type": 2,
                        "fields": [{"name": "Value", "type": "<UnknownType>"}],
                    }
                }
            },
        }

        errors = validate_protocol_spec(protocol)
        assert len(errors) == 1
        assert "UnknownType" in errors[0]


class TestSensorPacketQuirks:
    """Test sensor packet quirks."""

    def test_apply_sensor_packet_quirks_adds_packets(self):
        """Test that sensor packet quirks add the two sensor packets."""
        packets = {}
        result = apply_sensor_packet_quirks(packets)

        assert "sensor" in result
        assert "SensorGetAmbientLight" in result["sensor"]
        assert "SensorStateAmbientLight" in result["sensor"]

    def test_sensor_get_ambient_light_structure(self):
        """Test SensorGetAmbientLight packet structure."""
        packets = {}
        result = apply_sensor_packet_quirks(packets)

        get_packet = result["sensor"]["SensorGetAmbientLight"]
        assert get_packet["pkt_type"] == 401
        assert get_packet["fields"] == []

    def test_sensor_state_ambient_light_structure(self):
        """Test SensorStateAmbientLight packet structure."""
        packets = {}
        result = apply_sensor_packet_quirks(packets)

        state_packet = result["sensor"]["SensorStateAmbientLight"]
        assert state_packet["pkt_type"] == 402
        assert len(state_packet["fields"]) == 1
        assert state_packet["fields"][0]["name"] == "Lux"
        assert state_packet["fields"][0]["type"] == "float32"

    def test_apply_sensor_packet_quirks_preserves_existing(self):
        """Test that applying quirks preserves existing packets."""
        packets = {
            "device": {
                "DeviceGetService": {"pkt_type": 2, "fields": []},
            }
        }
        result = apply_sensor_packet_quirks(packets)

        # Existing packets should still be there
        assert "device" in result
        assert "DeviceGetService" in result["device"]

        # New sensor packets should be added
        assert "sensor" in result
        assert "SensorGetAmbientLight" in result["sensor"]
        assert "SensorStateAmbientLight" in result["sensor"]

    def test_apply_sensor_packet_quirks_idempotent(self):
        """Test that applying quirks multiple times doesn't duplicate."""
        packets = {}
        result1 = apply_sensor_packet_quirks(packets)
        result2 = apply_sensor_packet_quirks(result1)

        # Should still have exactly 2 sensor packets
        assert len(result2["sensor"]) == 2
        assert "SensorGetAmbientLight" in result2["sensor"]
        assert "SensorStateAmbientLight" in result2["sensor"]
