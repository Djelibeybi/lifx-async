"""Tests for LIFX products module."""

from __future__ import annotations

import pytest

from lifx.products import (
    ProductCapability,
    ProductInfo,
    ProductRegistry,
    TemperatureRange,
    get_device_class_name,
    get_registry,
)


@pytest.fixture
def sample_products_data() -> dict:
    """Create sample products data for testing."""
    return {
        "vid": 1,
        "name": "LIFX",
        "defaults": {"features": {}},
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
                    "color": True,
                    "temperature_range": [2500, 9000],
                    "multizone": True,
                },
                "upgrades": [
                    {"major": 2, "minor": 77, "features": {"extended_multizone": True}}
                ],
            },
            {
                "pid": 55,
                "name": "LIFX Tile",
                "features": {
                    "color": True,
                    "temperature_range": [2500, 9000],
                    "chain": True,
                    "matrix": True,
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
                    "color": True,
                    "temperature_range": [2500, 9000],
                    "hev": True,
                },
            },
            {
                "pid": 29,
                "name": "LIFX A19 Night Vision",
                "features": {
                    "color": True,
                    "temperature_range": [2500, 9000],
                    "infrared": True,
                },
            },
            {
                "pid": 10,
                "name": "LIFX White 800",
                "features": {
                    "temperature_range": [2700, 2700],
                },
            },
            {
                "pid": 11,
                "name": "LIFX White to Warm 800",
                "features": {
                    "temperature_range": [2500, 6500],
                },
            },
        ],
    }


@pytest.fixture
def registry(sample_products_data: dict) -> ProductRegistry:
    """Create a registry with sample products."""
    reg = ProductRegistry()
    reg.load_from_dict(sample_products_data)
    return reg


class TestTemperatureRange:
    """Tests for TemperatureRange."""

    def test_create_temperature_range(self) -> None:
        """Test creating temperature range."""
        temp_range = TemperatureRange(min=2500, max=9000)
        assert temp_range.min == 2500
        assert temp_range.max == 9000


class TestProductInfo:
    """Tests for ProductInfo."""

    def test_create_product_info(self) -> None:
        """Test creating product info."""
        product = ProductInfo(
            pid=1,
            name="Test Product",
            vendor=1,
            capabilities=ProductCapability.COLOR | ProductCapability.INFRARED,
            temperature_range=TemperatureRange(min=2500, max=9000),
            min_ext_mz_firmware=None,
        )
        assert product.pid == 1
        assert product.name == "Test Product"
        assert product.vendor == 1

    def test_has_capability(self) -> None:
        """Test capability checking."""
        product = ProductInfo(
            pid=1,
            name="Test",
            vendor=1,
            capabilities=ProductCapability.COLOR | ProductCapability.MULTIZONE,
            temperature_range=None,
            min_ext_mz_firmware=None,
        )
        assert product.has_capability(ProductCapability.COLOR)
        assert product.has_capability(ProductCapability.MULTIZONE)
        assert not product.has_capability(ProductCapability.INFRARED)

    def test_capability_properties(self) -> None:
        """Test capability property helpers."""
        product = ProductInfo(
            pid=1,
            name="Test",
            vendor=1,
            capabilities=(
                ProductCapability.COLOR
                | ProductCapability.MULTIZONE
                | ProductCapability.EXTENDED_MULTIZONE
            ),
            temperature_range=None,
            min_ext_mz_firmware=(2 << 16) | 77,
        )
        assert product.has_color
        assert product.has_multizone
        assert product.has_extended_multizone
        assert not product.has_infrared
        assert not product.has_matrix

    def test_supports_extended_multizone(self) -> None:
        """Test extended multizone firmware check."""
        product = ProductInfo(
            pid=1,
            name="Test",
            vendor=1,
            capabilities=ProductCapability.EXTENDED_MULTIZONE,
            temperature_range=None,
            min_ext_mz_firmware=(2 << 16) | 77,  # v2.77
        )

        # Firmware v2.77 should support it
        assert product.supports_extended_multizone((2 << 16) | 77)

        # Firmware v2.80 should support it
        assert product.supports_extended_multizone((2 << 16) | 80)

        # Firmware v2.70 should not support it
        assert not product.supports_extended_multizone((2 << 16) | 70)

        # No firmware version provided - assume supported
        assert product.supports_extended_multizone(None)


class TestProductRegistry:
    """Tests for ProductRegistry."""

    def test_create_registry(self) -> None:
        """Test creating registry (pre-loaded with generated products)."""
        reg = ProductRegistry()
        # Registry is always pre-loaded with generated products
        assert reg.is_loaded
        assert len(reg) > 0  # Contains all generated products

    def test_load_from_dict(self, registry: ProductRegistry) -> None:
        """Test loading from dict."""
        assert registry.is_loaded
        assert (
            len(registry) == 8
        )  # Updated: includes HEV, Infrared, White, and White-to-Warm products

    def test_get_product(self, registry: ProductRegistry) -> None:
        """Test getting product by ID."""
        product = registry.get_product(1)
        assert product is not None
        assert product.name == "LIFX Original 1000"
        assert product.has_color
        assert not product.has_multizone

    def test_get_product_not_found(self, registry: ProductRegistry) -> None:
        """Test getting non-existent product."""
        product = registry.get_product(999)
        assert product is None

    def test_contains(self, registry: ProductRegistry) -> None:
        """Test __contains__ operator."""
        assert 1 in registry
        assert 31 in registry
        assert 999 not in registry

    def test_get_device_class_name_tile(self, registry: ProductRegistry) -> None:
        """Test device class for tile products."""
        class_name = registry.get_device_class_name(55)  # LIFX Tile
        assert class_name == "TileDevice"

    def test_get_device_class_name_multizone(self, registry: ProductRegistry) -> None:
        """Test device class for multizone products."""
        class_name = registry.get_device_class_name(31)  # LIFX Z
        assert class_name == "MultiZoneLight"

    def test_get_device_class_name_hev(self, registry: ProductRegistry) -> None:
        """Test device class for HEV products."""
        class_name = registry.get_device_class_name(90)  # LIFX Clean
        assert class_name == "HevLight"

    def test_get_device_class_name_infrared(self, registry: ProductRegistry) -> None:
        """Test device class for infrared products."""
        class_name = registry.get_device_class_name(29)  # LIFX A19 Night Vision
        assert class_name == "InfraredLight"

    def test_get_device_class_name_light(self, registry: ProductRegistry) -> None:
        """Test device class for color lights."""
        class_name = registry.get_device_class_name(1)  # LIFX Original
        assert class_name == "Light"

    def test_get_device_class_name_white_light(self, registry: ProductRegistry) -> None:
        """Test device class for basic white lights (brightness-only)."""
        class_name = registry.get_device_class_name(10)  # LIFX White 800
        assert class_name == "Light"

    def test_get_device_class_name_white_to_warm(
        self, registry: ProductRegistry
    ) -> None:
        """Test device class for white-to-warm lights (brightness + temperature)."""
        class_name = registry.get_device_class_name(11)  # LIFX White to Warm 800
        assert class_name == "Light"

    def test_get_device_class_name_device(self, registry: ProductRegistry) -> None:
        """Test device class for non-light products (switches)."""
        class_name = registry.get_device_class_name(89)  # LIFX Switch
        assert class_name == "Device"

    def test_get_device_class_name_unknown(self, registry: ProductRegistry) -> None:
        """Test device class for unknown product."""
        class_name = registry.get_device_class_name(999)
        assert class_name == "Light"  # Default to Light

    def test_load_array_format(self) -> None:
        """Test loading array format (multiple vendors)."""
        data = [
            {
                "vid": 1,
                "name": "LIFX",
                "products": [
                    {"pid": 1, "name": "Product 1", "features": {"color": True}},
                ],
            },
            {
                "vid": 2,
                "name": "Other",
                "products": [
                    {"pid": 100, "name": "Product 2", "features": {"color": True}},
                ],
            },
        ]

        reg = ProductRegistry()
        reg.load_from_dict(data)

        assert len(reg) == 2
        assert reg.get_product(1) is not None
        assert reg.get_product(100) is not None

    def test_temperature_range_parsing(self, registry: ProductRegistry) -> None:
        """Test temperature range is parsed correctly."""
        product = registry.get_product(1)
        assert product is not None
        assert product.temperature_range is not None
        assert product.temperature_range.min == 2500
        assert product.temperature_range.max == 9000

    def test_extended_multizone_upgrade(self, registry: ProductRegistry) -> None:
        """Test extended multizone upgrade parsing."""
        product = registry.get_product(31)  # LIFX Z
        assert product is not None
        assert product.has_extended_multizone
        assert product.min_ext_mz_firmware is not None
        # v2.77 = (2 << 16) | 77 = 131149
        assert product.min_ext_mz_firmware == (2 << 16) | 77


class TestGlobalFunctions:
    """Tests for global functions."""

    def test_get_registry(self) -> None:
        """Test getting global registry."""
        reg = get_registry()
        assert isinstance(reg, ProductRegistry)

    def test_get_device_class_name_with_registry(
        self, registry: ProductRegistry
    ) -> None:
        """Test get_device_class_name function with test registry."""
        # Test with the sample registry fixture
        assert registry.get_device_class_name(55) == "TileDevice"
        assert registry.get_device_class_name(31) == "MultiZoneLight"
        assert registry.get_device_class_name(90) == "HevLight"
        assert registry.get_device_class_name(29) == "InfraredLight"
        assert registry.get_device_class_name(1) == "Light"
        assert registry.get_device_class_name(10) == "Light"  # White (brightness-only)
        assert registry.get_device_class_name(11) == "Light"  # White to Warm
        assert registry.get_device_class_name(89) == "Device"

    def test_get_device_class_name_global(self) -> None:
        """Test global get_device_class_name function uses pre-loaded registry."""
        # The global registry should be pre-loaded
        reg = get_registry()
        assert reg.is_loaded
        assert len(reg) > 0

        # Test that function works (using actual product IDs from generated registry)
        # We can't predict exact PIDs, but we can verify it returns valid class names
        valid_classes = {
            "TileDevice",
            "MultiZoneLight",
            "HevLight",
            "InfraredLight",
            "Light",
            "Device",
        }
        for pid in [1, 10, 27, 31, 55]:  # Common LIFX product IDs
            class_name = get_device_class_name(pid)
            assert class_name in valid_classes
