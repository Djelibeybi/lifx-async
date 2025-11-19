"""Code generator for LIFX product registry.

Downloads the official products.json from the LIFX GitHub repository and
generates optimized Python code with pre-built product definitions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from lifx.const import PRODUCTS_URL


def download_products() -> dict[str, Any] | list[dict[str, Any]]:
    """Download and parse products.json from LIFX GitHub repository.

    Returns:
        Parsed products dictionary or list

    Raises:
        URLError: If download fails
        json.JSONDecodeError: If parsing fails
    """
    parsed_url = urlparse(PRODUCTS_URL)
    if parsed_url.scheme == "https" and parsed_url.netloc.startswith(
        "raw.githubusercontent.com"
    ):
        print(f"Downloading products.json from {PRODUCTS_URL}...")
        with urlopen(PRODUCTS_URL) as response:  # nosec B310
            products_data = response.read()

        print("Parsing products specification...")
        products = json.loads(products_data)
        return products


def generate_product_definitions(
    products_data: dict[str, Any] | list[dict[str, Any]],
) -> str:
    """Generate Python code for product definitions.

    Args:
        products_data: Parsed products.json data

    Returns:
        Python code string with ProductInfo instances
    """
    code_lines = []

    # Handle both array and object formats
    all_vendors = []
    if isinstance(products_data, list):
        # Array format - multiple vendors
        all_vendors = products_data
    else:
        # Object format - single vendor
        all_vendors = [products_data]

    # Generate product definitions
    code_lines.append("# Pre-generated product definitions")
    code_lines.append("PRODUCTS: dict[int, ProductInfo] = {")

    product_count = 0
    for vendor_data in all_vendors:
        vendor_id = vendor_data.get("vid", 1)

        # Get default features
        defaults = vendor_data.get("defaults", {})
        default_features = defaults.get("features", {})

        # Process each product
        for product in vendor_data.get("products", []):
            pid = product["pid"]
            name = product["name"]

            # Merge features with defaults
            features = {**default_features, **product.get("features", {})}

            # Build capabilities bitfield
            capabilities = []
            if features.get("color"):
                capabilities.append("ProductCapability.COLOR")
            if features.get("infrared"):
                capabilities.append("ProductCapability.INFRARED")
            if features.get("multizone"):
                capabilities.append("ProductCapability.MULTIZONE")
            if features.get("extended_multizone"):
                capabilities.append("ProductCapability.EXTENDED_MULTIZONE")
            if features.get("chain"):
                capabilities.append("ProductCapability.CHAIN")
            if features.get("matrix"):
                capabilities.append("ProductCapability.MATRIX")
            if features.get("relays"):
                capabilities.append("ProductCapability.RELAYS")
            if features.get("buttons"):
                capabilities.append("ProductCapability.BUTTONS")
            if features.get("hev"):
                capabilities.append("ProductCapability.HEV")

            # Check for extended multizone in upgrades
            min_ext_mz_firmware = None
            for upgrade in product.get("upgrades", []):
                if upgrade.get("features", {}).get("extended_multizone"):
                    capabilities.append("ProductCapability.EXTENDED_MULTIZONE")
                    # Parse firmware version (major.minor format)
                    major = upgrade.get("major", 0)
                    minor = upgrade.get("minor", 0)
                    min_ext_mz_firmware = (major << 16) | minor
                    break

            # Build capabilities expression
            if capabilities:
                capabilities_expr = " | ".join(capabilities)
            else:
                capabilities_expr = "0"

            # Parse temperature range
            temp_range_expr = "None"
            if "temperature_range" in features:
                temp_list = features["temperature_range"]
                if len(temp_list) >= 2:
                    temp_range_expr = (
                        f"TemperatureRange(min={temp_list[0]}, max={temp_list[1]})"
                    )

            # Format firmware version
            min_ext_mz_firmware_expr = (
                str(min_ext_mz_firmware) if min_ext_mz_firmware is not None else "None"
            )

            # Generate ProductInfo instantiation
            code_lines.append(f"    {pid}: ProductInfo(")
            code_lines.append(f"        pid={pid},")
            code_lines.append(f"        name={repr(name)},")
            code_lines.append(f"        vendor={vendor_id},")
            code_lines.append(f"        capabilities={capabilities_expr},")
            code_lines.append(f"        temperature_range={temp_range_expr},")
            code_lines.append(
                f"        min_ext_mz_firmware={min_ext_mz_firmware_expr},"
            )
            code_lines.append("    ),")

            product_count += 1

    code_lines.append("}")
    code_lines.append("")

    print(f"Generated {product_count} product definitions")
    return "\n".join(code_lines)


def generate_registry_file(products_data: dict[str, Any] | list[dict[str, Any]]) -> str:
    """Generate complete registry.py file.

    Args:
        products_data: Parsed products.json data

    Returns:
        Complete Python file content
    """
    header = '''"""LIFX product definitions and capability detection.

DO NOT EDIT THIS FILE MANUALLY.
Generated from https://github.com/LIFX/products/blob/master/products.json
by products/generator.py

This module provides pre-generated product information for efficient runtime lookups.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class ProductCapability(IntEnum):
    """Product capability flags."""

    COLOR = 1
    INFRARED = 2
    MULTIZONE = 4
    CHAIN = 8
    MATRIX = 16
    RELAYS = 32
    BUTTONS = 64
    HEV = 128
    EXTENDED_MULTIZONE = 256


@dataclass
class TemperatureRange:
    """Color temperature range in Kelvin."""

    min: int
    max: int


@dataclass
class ProductInfo:
    """Information about a LIFX product.

    Attributes:
        pid: Product ID
        name: Product name
        vendor: Vendor ID (always 1 for LIFX)
        capabilities: Bitfield of ProductCapability flags
        temperature_range: Min/max color temperature in Kelvin
        min_ext_mz_firmware: Minimum firmware version for extended multizone
    """

    pid: int
    name: str
    vendor: int
    capabilities: int
    temperature_range: TemperatureRange | None
    min_ext_mz_firmware: int | None

    def has_capability(self, capability: ProductCapability) -> bool:
        """Check if product has a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if product has the capability
        """
        return bool(self.capabilities & capability)

    @property
    def has_color(self) -> bool:
        """Check if product supports color."""
        return self.has_capability(ProductCapability.COLOR)

    @property
    def has_infrared(self) -> bool:
        """Check if product supports infrared."""
        return self.has_capability(ProductCapability.INFRARED)

    @property
    def has_multizone(self) -> bool:
        """Check if product supports multizone."""
        return self.has_capability(ProductCapability.MULTIZONE)

    @property
    def has_chain(self) -> bool:
        """Check if product supports chaining."""
        return self.has_capability(ProductCapability.CHAIN)

    @property
    def has_matrix(self) -> bool:
        """Check if product supports matrix (2D grid)."""
        return self.has_capability(ProductCapability.MATRIX)

    @property
    def has_relays(self) -> bool:
        """Check if product has relays."""
        return self.has_capability(ProductCapability.RELAYS)

    @property
    def has_buttons(self) -> bool:
        """Check if product has buttons."""
        return self.has_capability(ProductCapability.BUTTONS)

    @property
    def has_hev(self) -> bool:
        """Check if product supports HEV."""
        return self.has_capability(ProductCapability.HEV)

    @property
    def has_extended_multizone(self) -> bool:
        """Check if product supports extended multizone."""
        return self.has_capability(ProductCapability.EXTENDED_MULTIZONE)

    def supports_extended_multizone(self, firmware_version: int | None = None) -> bool:
        """Check if extended multizone is supported for given firmware version.

        Args:
            firmware_version: Firmware version to check (optional)

        Returns:
            True if extended multizone is supported
        """
        if not self.has_extended_multizone:
            return False
        if self.min_ext_mz_firmware is None:
            return True
        if firmware_version is None:
            return True
        return firmware_version >= self.min_ext_mz_firmware


'''

    # Generate product definitions
    products_code = generate_product_definitions(products_data)

    # Generate helper functions
    helper_functions = '''

class ProductRegistry:
    """Registry of LIFX products and their capabilities."""

    def __init__(self) -> None:
        """Initialize product registry with pre-generated data."""
        self._products = PRODUCTS.copy()  # Copy to allow test overrides
        self._loaded = True  # Always loaded in generated registry

    def load_from_dict(self, data: dict | list) -> None:
        """Load products from parsed JSON data (for testing).

        Args:
            data: Parsed products.json dictionary or array
        """
        from typing import Any

        # Clear existing products
        self._products.clear()

        # Handle both array and object formats
        all_vendors = []
        if isinstance(data, list):
            all_vendors = data
        else:
            all_vendors = [data]

        # Process each vendor
        for vendor_data in all_vendors:
            vendor_id = vendor_data.get("vid", 1)
            defaults = vendor_data.get("defaults", {})
            default_features = defaults.get("features", {})

            # Parse each product
            for product in vendor_data.get("products", []):
                pid = product["pid"]
                name = product["name"]

                # Merge features with defaults
                features: dict[str, Any] = {**default_features, **product.get("features", {})}

                # Build capabilities bitfield
                capabilities = 0
                if features.get("color"):
                    capabilities |= ProductCapability.COLOR
                if features.get("infrared"):
                    capabilities |= ProductCapability.INFRARED
                if features.get("multizone"):
                    capabilities |= ProductCapability.MULTIZONE
                if features.get("chain"):
                    capabilities |= ProductCapability.CHAIN
                if features.get("matrix"):
                    capabilities |= ProductCapability.MATRIX
                if features.get("relays"):
                    capabilities |= ProductCapability.RELAYS
                if features.get("buttons"):
                    capabilities |= ProductCapability.BUTTONS
                if features.get("hev"):
                    capabilities |= ProductCapability.HEV

                # Check for extended multizone in upgrades
                min_ext_mz_firmware = None
                for upgrade in product.get("upgrades", []):
                    if upgrade.get("features", {}).get("extended_multizone"):
                        capabilities |= ProductCapability.EXTENDED_MULTIZONE
                        # Parse firmware version (major.minor format)
                        major = upgrade.get("major", 0)
                        minor = upgrade.get("minor", 0)
                        min_ext_mz_firmware = (major << 16) | minor
                        break

                # Parse temperature range
                temp_range = None
                if "temperature_range" in features:
                    temp_list = features["temperature_range"]
                    if len(temp_list) >= 2:
                        temp_range = TemperatureRange(min=temp_list[0], max=temp_list[1])

                product_info = ProductInfo(
                    pid=pid,
                    name=name,
                    vendor=vendor_id,
                    capabilities=capabilities,
                    temperature_range=temp_range,
                    min_ext_mz_firmware=min_ext_mz_firmware,
                )

                self._products[pid] = product_info

        self._loaded = True

    @property
    def is_loaded(self) -> bool:
        """Check if registry has been loaded."""
        return self._loaded

    def get_product(self, pid: int) -> ProductInfo | None:
        """Get product info by product ID.

        Args:
            pid: Product ID

        Returns:
            ProductInfo if found, None otherwise
        """
        return self._products.get(pid)

    def __len__(self) -> int:
        """Get number of products in registry."""
        return len(self._products)

    def __contains__(self, pid: int) -> bool:
        """Check if product ID exists in registry."""
        return pid in self._products


# Global registry instance
_registry = ProductRegistry()


def get_registry() -> ProductRegistry:
    """Get the global product registry.

    Returns:
        Global ProductRegistry instance
    """
    return _registry


def get_product(pid: int) -> ProductInfo:
    """Get product info by product ID.

    Args:
        pid: Product ID

    Returns:
        ProductInfo if found, otherwise a default ProductInfo with no capabilities
    """
    product = _registry.get_product(pid)
    if product is None:
        # Return default product with no capabilities for unknown products
        return ProductInfo(
            pid=0,
            name="LIFX Light",
            vendor=1,
            capabilities=0,
            temperature_range=None,
            min_ext_mz_firmware=None,
        )
    return product
'''

    return header + products_code + helper_functions


def main() -> None:
    """Main generator entry point."""
    try:
        # Download and parse products from GitHub
        products_data = download_products()
    except Exception as e:
        print(f"Error: Failed to download products.json: {e}", file=sys.stderr)
        sys.exit(1)

    # Count products for summary
    if isinstance(products_data, list):
        all_products = []
        for vendor in products_data:
            all_products.extend(vendor.get("products", []))
    else:
        all_products = products_data.get("products", [])

    print(f"Found {len(all_products)} products")

    # Generate registry.py
    registry_code = generate_registry_file(products_data)

    # Determine output path
    output_path = Path(__file__).parent / "registry.py"

    with open(output_path, "w") as f:
        f.write(registry_code)

    print(f"Generated {output_path}")
    print("✓ Generation complete!")


if __name__ == "__main__":
    main()
