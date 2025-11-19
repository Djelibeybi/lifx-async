"""Comprehensive tests for LIFX product registry generator.

Tests cover:
- Product data download and parsing
- Python code generation from product definitions
- Registry file generation
- Edge cases and error handling
- Feature capability encoding
- Temperature range parsing
- Extended multizone firmware version handling
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, mock_open, patch

import pytest

from lifx.products.generator import (
    download_products,
    generate_product_definitions,
    generate_registry_file,
    main,
)

# ============================================================================
# Fixtures for test data
# ============================================================================


@pytest.fixture
def minimal_products_data() -> dict[str, Any]:
    """Minimal valid products.json data structure."""
    return {
        "vid": 1,
        "name": "LIFX",
        "defaults": {"features": {}},
        "products": [
            {
                "pid": 1,
                "name": "Test Light",
                "features": {},
            }
        ],
    }


@pytest.fixture
def full_featured_product_data() -> dict[str, Any]:
    """Comprehensive products.json with all feature types."""
    return {
        "vid": 1,
        "name": "LIFX",
        "defaults": {"features": {"color": True}},
        "products": [
            {
                "pid": 1,
                "name": "LIFX Original 1000",
                "features": {
                    "color": True,
                    "temperature_range": [2500, 9000],
                },
            },
            {
                "pid": 31,
                "name": "LIFX Z",
                "features": {
                    "multizone": True,
                    "temperature_range": [2500, 9000],
                },
                "upgrades": [
                    {
                        "major": 2,
                        "minor": 77,
                        "features": {"extended_multizone": True},
                    }
                ],
            },
            {
                "pid": 55,
                "name": "LIFX Tile",
                "features": {
                    "matrix": True,
                    "chain": True,
                    "temperature_range": [2500, 9000],
                },
            },
            {
                "pid": 89,
                "name": "LIFX Switch",
                "features": {
                    "relays": True,
                    "buttons": True,
                },
            },
            {
                "pid": 90,
                "name": "LIFX Clean",
                "features": {
                    "hev": True,
                    "temperature_range": [2500, 9000],
                },
            },
            {
                "pid": 29,
                "name": "LIFX A19 Night Vision",
                "features": {
                    "infrared": True,
                    "temperature_range": [2500, 9000],
                },
            },
        ],
    }


@pytest.fixture
def array_format_products_data() -> list[dict[str, Any]]:
    """Products data in array format (multiple vendors)."""
    return [
        {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {"color": True}},
            "products": [
                {
                    "pid": 1,
                    "name": "LIFX Light",
                    "features": {"temperature_range": [2500, 9000]},
                }
            ],
        },
        {
            "vid": 2,
            "name": "Other Vendor",
            "defaults": {"features": {}},
            "products": [
                {
                    "pid": 100,
                    "name": "Other Light",
                    "features": {"color": True},
                }
            ],
        },
    ]


# ============================================================================
# Tests for download_products()
# ============================================================================


class TestDownloadProducts:
    """Tests for the download_products function."""

    def test_download_products_success(self, full_featured_product_data: dict) -> None:
        """Test successful products.json download and parsing."""
        json_str = json.dumps(full_featured_product_data)

        with patch("lifx.products.generator.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=None)
            mock_response.read = Mock(return_value=json_str.encode())
            mock_urlopen.return_value = mock_response

            result = download_products()

            assert isinstance(result, dict)
            assert result["vid"] == 1
            assert result["name"] == "LIFX"
            assert len(result["products"]) == 6

    def test_download_products_invalid_json(self) -> None:
        """Test handling of invalid JSON from download."""
        invalid_json = b"{ invalid json }"

        with patch("lifx.products.generator.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=None)
            mock_response.read = Mock(return_value=invalid_json)
            mock_urlopen.return_value = mock_response

            with pytest.raises(json.JSONDecodeError):
                download_products()

    def test_download_products_invalid_url_scheme(self) -> None:
        """Test rejection of non-HTTPS URLs."""
        with patch(
            "lifx.products.generator.PRODUCTS_URL", "http://example.com/products.json"
        ):
            result = download_products()
            assert result is None

    def test_download_products_invalid_domain(self) -> None:
        """Test rejection of non-GitHub URLs."""
        with patch(
            "lifx.products.generator.PRODUCTS_URL", "https://example.com/products.json"
        ):
            result = download_products()
            assert result is None

    def test_download_products_network_error(self) -> None:
        """Test handling of network errors during download."""
        with patch("lifx.products.generator.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = OSError("Network error")

            with pytest.raises(OSError):
                download_products()


# ============================================================================
# Tests for generate_product_definitions()
# ============================================================================


class TestGenerateProductDefinitions:
    """Tests for the generate_product_definitions function."""

    def test_generate_basic_product_definitions(
        self, minimal_products_data: dict
    ) -> None:
        """Test generating Python code for basic product."""
        code = generate_product_definitions(minimal_products_data)

        assert "# Pre-generated product definitions" in code
        assert "PRODUCTS: dict[int, ProductInfo] = {" in code
        assert "ProductInfo(" in code
        assert "1: ProductInfo(" in code
        assert "Test Light" in code
        assert "}" in code

    def test_generate_product_with_color_capability(
        self, minimal_products_data: dict
    ) -> None:
        """Test generating product with color capability."""
        minimal_products_data["products"][0]["features"]["color"] = True
        code = generate_product_definitions(minimal_products_data)

        assert "ProductCapability.COLOR" in code

    def test_generate_product_with_all_capabilities(
        self, full_featured_product_data: dict
    ) -> None:
        """Test generating product with all capabilities."""
        code = generate_product_definitions(full_featured_product_data)

        assert "ProductCapability.COLOR" in code
        assert "ProductCapability.MULTIZONE" in code
        assert "ProductCapability.MATRIX" in code
        assert "ProductCapability.CHAIN" in code
        assert "ProductCapability.RELAYS" in code
        assert "ProductCapability.BUTTONS" in code
        assert "ProductCapability.HEV" in code
        assert "ProductCapability.INFRARED" in code
        assert "ProductCapability.EXTENDED_MULTIZONE" in code

    def test_generate_product_no_capabilities(
        self, minimal_products_data: dict
    ) -> None:
        """Test generating product with no capabilities."""
        code = generate_product_definitions(minimal_products_data)

        # Should have capabilities = 0 for a product with no features
        assert "capabilities=0" in code

    def test_generate_temperature_range(self, minimal_products_data: dict) -> None:
        """Test temperature range code generation."""
        minimal_products_data["products"][0]["features"]["temperature_range"] = [
            2500,
            9000,
        ]
        code = generate_product_definitions(minimal_products_data)

        assert "TemperatureRange(min=2500, max=9000)" in code

    def test_generate_temperature_range_incomplete(
        self, minimal_products_data: dict
    ) -> None:
        """Test temperature range with incomplete data."""
        minimal_products_data["products"][0]["features"]["temperature_range"] = [2500]
        code = generate_product_definitions(minimal_products_data)

        assert "temperature_range=None" in code

    def test_generate_extended_multizone_firmware(
        self, full_featured_product_data: dict
    ) -> None:
        """Test extended multizone firmware version encoding."""
        code = generate_product_definitions(full_featured_product_data)

        # v2.77 = (2 << 16) | 77 = 131149
        assert "min_ext_mz_firmware=131149" in code

    def test_generate_multiple_products(self, full_featured_product_data: dict) -> None:
        """Test generating multiple products."""
        code = generate_product_definitions(full_featured_product_data)

        # Check all product IDs are present
        assert "1: ProductInfo(" in code
        assert "31: ProductInfo(" in code
        assert "55: ProductInfo(" in code
        assert "89: ProductInfo(" in code
        assert "90: ProductInfo(" in code
        assert "29: ProductInfo(" in code

    def test_generate_array_format_products(
        self, array_format_products_data: list
    ) -> None:
        """Test generating products from array format."""
        code = generate_product_definitions(array_format_products_data)

        assert "1: ProductInfo(" in code
        assert "100: ProductInfo(" in code
        assert code.count("ProductInfo(") == 2

    def test_generate_default_features_inheritance(self) -> None:
        """Test that product features inherit from defaults."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {
                "features": {"color": True, "temperature_range": [2500, 9000]}
            },
            "products": [
                {
                    "pid": 1,
                    "name": "Light",
                    "features": {
                        "infrared": True
                    },  # Overrides, should have both color and infrared
                }
            ],
        }

        code = generate_product_definitions(data)

        # Should have both color (from default) and infrared (from product)
        assert "ProductCapability.COLOR" in code
        assert "ProductCapability.INFRARED" in code

    def test_generate_feature_override(self) -> None:
        """Test that product features override defaults."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {
                "features": {
                    "color": True,
                    "temperature_range": [2500, 9000],
                }
            },
            "products": [
                {
                    "pid": 1,
                    "name": "Light",
                    "features": {
                        "temperature_range": [3000, 6500],  # Override default range
                    },
                }
            ],
        }

        code = generate_product_definitions(data)

        assert "TemperatureRange(min=3000, max=6500)" in code

    def test_generate_no_products(self) -> None:
        """Test generating when no products defined."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [],
        }

        code = generate_product_definitions(data)

        assert "PRODUCTS: dict[int, ProductInfo] = {" in code
        assert "}" in code
        assert code.count("ProductInfo(") == 0

    def test_firmware_version_calculation(self) -> None:
        """Test firmware version encoding as (major << 16) | minor."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [
                {
                    "pid": 1,
                    "name": "Light",
                    "features": {},
                    "upgrades": [
                        {
                            "major": 3,
                            "minor": 42,
                            "features": {"extended_multizone": True},
                        }
                    ],
                }
            ],
        }

        code = generate_product_definitions(data)

        # (3 << 16) | 42 = 196650
        assert "min_ext_mz_firmware=196650" in code

    def test_product_name_escaping(self) -> None:
        """Test proper escaping of product names with special characters."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [
                {
                    "pid": 1,
                    "name": 'LIFX "Color" A19',
                    "features": {},
                }
            ],
        }

        code = generate_product_definitions(data)

        # Should properly escape quotes
        assert (
            "name='LIFX \"Color\" A19'" in code or 'name="LIFX \\"Color\\" A19"' in code
        )


# ============================================================================
# Tests for generate_registry_file()
# ============================================================================


class TestGenerateRegistryFile:
    """Tests for the generate_registry_file function."""

    def test_generate_registry_file_structure(
        self, minimal_products_data: dict
    ) -> None:
        """Test that generated registry file has correct structure."""
        code = generate_registry_file(minimal_products_data)

        # Check header
        assert '"""LIFX product definitions' in code
        assert "DO NOT EDIT THIS FILE MANUALLY" in code
        assert "from __future__ import annotations" in code

        # Check imports
        assert "from dataclasses import dataclass" in code
        assert "from enum import IntEnum" in code

        # Check ProductCapability enum
        assert "class ProductCapability(IntEnum):" in code
        assert "COLOR = 1" in code
        assert "INFRARED = 2" in code
        assert "MULTIZONE = 4" in code
        assert "HEV = 128" in code
        assert "EXTENDED_MULTIZONE = 256" in code

        # Check TemperatureRange dataclass
        assert "class TemperatureRange:" in code
        assert "min: int" in code
        assert "max: int" in code

        # Check ProductInfo dataclass
        assert "class ProductInfo:" in code
        assert "pid: int" in code
        assert "name: str" in code
        assert "vendor: int" in code
        assert "capabilities: int" in code

        # Check ProductRegistry class
        assert "class ProductRegistry:" in code
        assert "def __init__" in code
        assert "def load_from_dict" in code
        assert "def get_product" in code

        # Check product definitions
        assert "PRODUCTS: dict[int, ProductInfo]" in code

        # Check helper functions
        assert "def get_registry()" in code
        assert "def get_product(pid: int)" in code

    def test_registry_file_has_product_info_methods(
        self, minimal_products_data: dict
    ) -> None:
        """Test that generated registry includes ProductInfo methods."""
        code = generate_registry_file(minimal_products_data)

        # Check capability check methods
        assert "def has_capability(self, capability: ProductCapability)" in code
        assert "def has_color(self) -> bool:" in code
        assert "def has_infrared(self) -> bool:" in code
        assert "def has_multizone(self) -> bool:" in code
        assert "def has_chain(self) -> bool:" in code
        assert "def has_matrix(self) -> bool:" in code
        assert "def has_relays(self) -> bool:" in code
        assert "def has_buttons(self) -> bool:" in code
        assert "def has_hev(self) -> bool:" in code
        assert "def has_extended_multizone(self) -> bool:" in code
        assert "def supports_extended_multizone(self, firmware_version:" in code

    def test_registry_file_has_registry_methods(
        self, minimal_products_data: dict
    ) -> None:
        """Test that generated registry includes ProductRegistry methods."""
        code = generate_registry_file(minimal_products_data)

        # Check registry methods
        assert "def is_loaded(self) -> bool:" in code
        assert "def get_product(self, pid: int)" in code
        assert "def __len__(self)" in code
        assert "def __contains__(self, pid: int)" in code

    def test_registry_file_valid_python_syntax(
        self, minimal_products_data: dict
    ) -> None:
        """Test that generated code is valid Python."""
        code = generate_registry_file(minimal_products_data)

        # Should be compilable Python
        compile(code, "<generated>", "exec")

    def test_registry_file_array_format(self, array_format_products_data: list) -> None:
        """Test registry file generation from array format."""
        code = generate_registry_file(array_format_products_data)

        assert "PRODUCTS: dict[int, ProductInfo]" in code
        assert "class ProductRegistry:" in code


# ============================================================================
# Tests for main() and integration
# ============================================================================


class TestMain:
    """Tests for the main generator entry point."""

    def test_main_success(self, tmp_path: Path, minimal_products_data: dict) -> None:
        """Test successful main execution."""
        json.dumps(minimal_products_data)

        # Mock the download and file system operations
        with patch("lifx.products.generator.download_products") as mock_download:
            with patch("lifx.products.generator.Path") as mock_path_class:
                mock_download.return_value = minimal_products_data

                # Mock file writing
                mock_file = mock_open()
                with patch("builtins.open", mock_file):
                    # Create a mock path instance
                    mock_path_instance = Mock()
                    mock_path_instance.parent = tmp_path
                    mock_path_class.return_value = mock_path_instance

                    # Should not raise
                    main()

                # Verify file was written
                mock_file.assert_called()

    def test_main_download_failure(self) -> None:
        """Test main handles download failures gracefully."""
        with patch("lifx.products.generator.download_products") as mock_download:
            mock_download.side_effect = Exception("Download failed")

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

    def test_main_prints_progress(
        self, capsys, tmp_path: Path, minimal_products_data: dict
    ) -> None:
        """Test that main prints progress messages."""
        with patch("lifx.products.generator.download_products") as mock_download:
            with patch("lifx.products.generator.Path") as mock_path_class:
                mock_download.return_value = minimal_products_data

                mock_file = mock_open()
                with patch("builtins.open", mock_file):
                    mock_path_instance = Mock()
                    mock_path_instance.parent = tmp_path
                    mock_path_class.return_value = mock_path_instance

                    main()

                captured = capsys.readouterr()
                # Should have progress messages
                assert (
                    "Downloading" in captured.out
                    or "Parsing" in captured.out
                    or "Generated" in captured.out
                )


# ============================================================================
# Tests for capability bitfield encoding
# ============================================================================


class TestCapabilityEncoding:
    """Tests for correct encoding of capability bitfields."""

    def test_single_capability(self) -> None:
        """Test single capability encoding."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [{"pid": 1, "name": "Light", "features": {"color": True}}],
        }

        code = generate_product_definitions(data)
        assert "capabilities=ProductCapability.COLOR" in code

    def test_multiple_capabilities_bitwise_or(self) -> None:
        """Test multiple capabilities use bitwise OR."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [
                {
                    "pid": 1,
                    "name": "Light",
                    "features": {"color": True, "infrared": True, "multizone": True},
                }
            ],
        }

        code = generate_product_definitions(data)
        # Should use | operator
        assert " | " in code
        assert "ProductCapability.COLOR" in code
        assert "ProductCapability.INFRARED" in code
        assert "ProductCapability.MULTIZONE" in code

    def test_all_capabilities_combination(
        self, full_featured_product_data: dict
    ) -> None:
        """Test all capability types in single product."""
        # Add all features to one product
        full_featured_product_data["products"][0].update(
            {
                "features": {
                    "color": True,
                    "infrared": True,
                    "multizone": True,
                    "chain": True,
                    "matrix": True,
                    "relays": True,
                    "buttons": True,
                    "hev": True,
                    "temperature_range": [2500, 9000],
                },
                "upgrades": [
                    {
                        "major": 2,
                        "minor": 77,
                        "features": {"extended_multizone": True},
                    }
                ],
            }
        )

        code = generate_product_definitions(full_featured_product_data)

        # Count how many capabilities are in the OR expression
        line_with_capabilities = [
            line for line in code.split("\n") if "ProductCapability" in line
        ][0]

        # Should have multiple capabilities joined by |
        assert line_with_capabilities.count("|") >= 8


# ============================================================================
# Tests for edge cases and error handling
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_product_with_zero_pid(self) -> None:
        """Test handling of product with pid=0."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [{"pid": 0, "name": "Test", "features": {}}],
        }

        code = generate_product_definitions(data)
        assert "0: ProductInfo(" in code

    def test_product_with_negative_firmware_version(self) -> None:
        """Test handling of negative firmware versions."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [
                {
                    "pid": 1,
                    "name": "Light",
                    "features": {},
                    "upgrades": [
                        {
                            "major": 255,
                            "minor": 255,
                            "features": {"extended_multizone": True},
                        }
                    ],
                }
            ],
        }

        code = generate_product_definitions(data)
        # (255 << 16) | 255 should work correctly
        assert "min_ext_mz_firmware=" in code

    def test_product_with_empty_features_dict(self) -> None:
        """Test product with empty features dict."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [{"pid": 1, "name": "Light", "features": {}}],
        }

        code = generate_product_definitions(data)
        assert "capabilities=0" in code

    def test_product_with_missing_name(self) -> None:
        """Test that missing product name field raises KeyError."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [
                {"pid": 1}  # Missing name
            ],
        }

        with pytest.raises(KeyError):
            generate_product_definitions(data)

    def test_product_with_missing_pid(self) -> None:
        """Test that missing product pid field raises KeyError."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [
                {"name": "Light"}  # Missing pid
            ],
        }

        with pytest.raises(KeyError):
            generate_product_definitions(data)

    def test_vendor_missing_default_vid(self) -> None:
        """Test default vendor ID when not specified."""
        data = {
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [{"pid": 1, "name": "Light", "features": {}}],
        }

        code = generate_product_definitions(data)
        # Should use default vid=1
        assert "vendor=1" in code

    def test_multiple_upgrades_first_extended_multizone_wins(self) -> None:
        """Test that first upgrade with extended_multizone is used."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [
                {
                    "pid": 1,
                    "name": "Light",
                    "features": {},
                    "upgrades": [
                        {
                            "major": 1,
                            "minor": 0,
                            "features": {"extended_multizone": True},
                        },
                        {
                            "major": 2,
                            "minor": 0,
                            "features": {"extended_multizone": True},
                        },
                    ],
                }
            ],
        }

        code = generate_product_definitions(data)
        # (1 << 16) | 0 = 65536
        assert "min_ext_mz_firmware=65536" in code

    def test_large_product_id(self) -> None:
        """Test handling of large product IDs."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [{"pid": 999999, "name": "Light", "features": {}}],
        }

        code = generate_product_definitions(data)
        assert "999999: ProductInfo(" in code

    def test_temperature_range_with_extra_values(self) -> None:
        """Test temperature range with extra values in list."""
        data = {
            "vid": 1,
            "name": "LIFX",
            "defaults": {"features": {}},
            "products": [
                {
                    "pid": 1,
                    "name": "Light",
                    "features": {
                        "temperature_range": [2500, 9000, 6500]
                    },  # Extra value
                }
            ],
        }

        code = generate_product_definitions(data)
        # Should use first two values
        assert "TemperatureRange(min=2500, max=9000)" in code

    def test_empty_array_format_data(self) -> None:
        """Test generating from empty array."""
        data = []

        code = generate_product_definitions(data)
        assert "PRODUCTS: dict[int, ProductInfo] = {" in code
        assert code.count("ProductInfo(") == 0


# ============================================================================
# Tests for code generation quality
# ============================================================================


class TestCodeQuality:
    """Tests for quality of generated code."""

    def test_generated_code_is_properly_formatted(
        self, minimal_products_data: dict
    ) -> None:
        """Test that generated code has proper indentation and formatting."""
        code = generate_product_definitions(minimal_products_data)

        # Should have proper indentation
        lines = code.split("\n")
        for line in lines:
            if line and not line.startswith("#"):
                # Check leading spaces are consistent (0, 4, 8, etc. for 4-space indent)
                leading_spaces = len(line) - len(line.lstrip())
                assert leading_spaces % 4 == 0, f"Bad indentation: {repr(line)}"

    def test_generated_code_has_type_hints(self, minimal_products_data: dict) -> None:
        """Test that generated ProductInfo instances have proper structure."""
        code = generate_registry_file(minimal_products_data)

        # Should have type annotations in registry
        assert "pid: int" in code
        assert "name: str" in code
        assert "vendor: int" in code
        assert "capabilities: int" in code
        assert "temperature_range: TemperatureRange | None" in code
        assert "min_ext_mz_firmware: int | None" in code

    def test_generated_code_has_docstrings(self, minimal_products_data: dict) -> None:
        """Test that generated code includes docstrings."""
        code = generate_registry_file(minimal_products_data)

        # Should have module docstring
        assert '"""LIFX product definitions' in code

        # Should have class docstrings
        assert "class ProductCapability" in code
        assert "class TemperatureRange" in code
        assert "class ProductInfo" in code
        assert "class ProductRegistry" in code


# ============================================================================
# Tests for consistency and correctness
# ============================================================================


class TestConsistency:
    """Tests for consistency across generation runs."""

    def test_same_input_produces_same_output(
        self, full_featured_product_data: dict
    ) -> None:
        """Test that same input produces identical output."""
        code1 = generate_registry_file(full_featured_product_data)
        code2 = generate_registry_file(full_featured_product_data)

        assert code1 == code2

    def test_array_and_dict_formats_equivalent(
        self, full_featured_product_data: dict, array_format_products_data: list
    ) -> None:
        """Test that array and dict formats produce equivalent results."""
        # Convert dict to array format for comparison
        array_version = [full_featured_product_data]

        code_dict = generate_product_definitions(full_featured_product_data)
        code_array = generate_product_definitions(array_version)

        # Both should have same products
        assert code_dict.count("ProductInfo(") == code_array.count("ProductInfo(")
