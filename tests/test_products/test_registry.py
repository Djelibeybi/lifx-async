"""Tests for LIFX products module."""

from __future__ import annotations

import pytest

from lifx.products import (
    ProductCapability,
    ProductInfo,
    ProductRegistry,
    TemperatureRange,
    TemperatureRangeUpgrade,
    get_product,
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


class TestProductInfoForFirmware:
    """Resolving a product's firmware-dependent capabilities."""

    @staticmethod
    def _upgraded_light() -> ProductInfo:
        return ProductInfo(
            pid=219,
            name="Test Luna",
            vendor=1,
            capabilities=ProductCapability.COLOR | ProductCapability.MATRIX,
            temperature_range=TemperatureRange(min=1500, max=9000),
            min_ext_mz_firmware=None,
            temperature_range_upgrades=(
                TemperatureRangeUpgrade(
                    min_firmware=(4 << 16) | 148,
                    temperature_range=TemperatureRange(min=1000, max=10000),
                ),
            ),
        )

    def test_firmware_below_upgrade_keeps_base_range(self) -> None:
        resolved = self._upgraded_light().for_firmware((4 << 16) | 147)
        assert resolved.temperature_range == TemperatureRange(min=1500, max=9000)

    def test_firmware_at_upgrade_gets_upgraded_range(self) -> None:
        resolved = self._upgraded_light().for_firmware((4 << 16) | 148)
        assert resolved.temperature_range == TemperatureRange(min=1000, max=10000)

    def test_newer_major_gets_upgraded_range(self) -> None:
        """4.148 is below 5.0 even though 148 > 0: versions compare as integers."""
        resolved = self._upgraded_light().for_firmware(5 << 16)
        assert resolved.temperature_range == TemperatureRange(min=1000, max=10000)

    def test_later_upgrade_wins(self) -> None:
        product = ProductInfo(
            pid=1,
            name="Test",
            vendor=1,
            capabilities=ProductCapability.COLOR,
            temperature_range=TemperatureRange(min=2500, max=9000),
            min_ext_mz_firmware=None,
            temperature_range_upgrades=(
                TemperatureRangeUpgrade(
                    min_firmware=(2 << 16) | 80,
                    temperature_range=TemperatureRange(min=1500, max=9000),
                ),
                TemperatureRangeUpgrade(
                    min_firmware=(4 << 16) | 148,
                    temperature_range=TemperatureRange(min=1000, max=10000),
                ),
            ),
        )
        assert product.for_firmware((2 << 16) | 79).temperature_range == (
            TemperatureRange(min=2500, max=9000)
        )
        assert product.for_firmware((3 << 16) | 70).temperature_range == (
            TemperatureRange(min=1500, max=9000)
        )
        assert product.for_firmware((4 << 16) | 200).temperature_range == (
            TemperatureRange(min=1000, max=10000)
        )

    def test_highest_reached_upgrade_wins_in_any_order(self) -> None:
        product = ProductInfo(
            pid=1,
            name="Test",
            vendor=1,
            capabilities=ProductCapability.COLOR,
            temperature_range=TemperatureRange(min=2500, max=9000),
            min_ext_mz_firmware=None,
            temperature_range_upgrades=(
                TemperatureRangeUpgrade(
                    min_firmware=(4 << 16) | 148,
                    temperature_range=TemperatureRange(min=1000, max=10000),
                ),
                TemperatureRangeUpgrade(
                    min_firmware=(2 << 16) | 80,
                    temperature_range=TemperatureRange(min=1500, max=9000),
                ),
            ),
        )
        assert product.for_firmware((4 << 16) | 148).temperature_range == (
            TemperatureRange(min=1000, max=10000)
        )

    def test_old_firmware_drops_extended_multizone(self) -> None:
        product = ProductInfo(
            pid=32,
            name="Test Strip",
            vendor=1,
            capabilities=ProductCapability.MULTIZONE
            | ProductCapability.EXTENDED_MULTIZONE,
            temperature_range=None,
            min_ext_mz_firmware=(2 << 16) | 77,
        )
        assert not product.for_firmware((2 << 16) | 76).has_extended_multizone
        assert product.for_firmware((2 << 16) | 77).has_extended_multizone

    def test_does_not_mutate_the_registry_entry(self) -> None:
        product = self._upgraded_light()
        product.for_firmware((4 << 16) | 148)
        assert product.temperature_range == TemperatureRange(min=1500, max=9000)

    def test_mirror_upgrades_from_4_200(self) -> None:
        mirror = get_product(267)
        assert mirror.for_firmware((4 << 16) | 199).temperature_range == (
            mirror.temperature_range
        )
        assert mirror.for_firmware((4 << 16) | 200).temperature_range == (
            TemperatureRange(min=1000, max=10000)
        )

    def test_luna_upgrades_from_4_148(self) -> None:
        luna = get_product(219)
        assert luna.for_firmware((4 << 16) | 148).temperature_range == (
            TemperatureRange(min=1000, max=10000)
        )


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
