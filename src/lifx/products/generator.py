"""Code generator for LIFX product registry.

Downloads the official products.json from the LIFX GitHub repository and
generates optimized Python code with pre-built product definitions.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from lifx._upstream import UpstreamCommit, fetch_upstream_commit
from lifx.const import PRODUCTS_URL


def format_generated_files(*paths: Path) -> None:
    """Run `ruff format` and `ruff check --fix` over the generated files.

    The generator emits valid but unformatted Python: string quoting and line
    wrapping differ from the repository style, so an unformatted regeneration
    shows up as a large spurious diff. This mirrors the "Format and lint
    generated files" step in the CI generated-files job.

    Args:
        paths: Files to format in place.

    Raises:
        RuntimeError: If ruff cannot format or lint the generated files.
    """
    print("Formatting generated code with ruff...")
    targets = [str(path) for path in paths]

    for command in (["format"], ["check", "--fix"]):
        result = subprocess.run(  # nosec B603
            [sys.executable, "-m", "ruff", *command, *targets],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # ruff writes diagnostics to stdout and internal errors to stderr,
            # so both are needed to explain the failure. `ruff format` only
            # fails on unparsable Python, which means the generator emitted
            # broken code: never let that pass as a successful generation.
            diagnostics = "\n".join(
                stream.strip()
                for stream in (result.stdout, result.stderr)
                if stream.strip()
            )
            raise RuntimeError(
                f"ruff {command[0]} failed on the generated files:\n{diagnostics}"
            )


def download_products() -> dict[str, Any] | list[dict[str, Any]] | None:
    """Download and parse products.json from LIFX GitHub repository.

    Returns:
        Parsed products dictionary or list

    Raises:
        URLError: If download fails
        json.JSONDecodeError: If parsing fails
    """
    parsed_url = urlparse(PRODUCTS_URL)
    if (
        parsed_url.scheme == "https"
        and parsed_url.netloc == "raw.githubusercontent.com"
        and parsed_url.path.startswith("/LIFX/")
    ):
        print(f"Downloading products.json from {parsed_url.geturl()}...")
        with urlopen(parsed_url.geturl()) as response:  # nosec B310
            products_data = response.read()

        print("Parsing products specification...")
        products = json.loads(products_data)
        return products


def parse_temperature_range_upgrades(
    product: dict[str, Any],
) -> list[tuple[int, tuple[int, int]]]:
    """Extract a product's firmware-dependent temperature ranges.

    Args:
        product: One product entry from products.json

    Returns:
        (min_firmware, (min_kelvin, max_kelvin)) pairs ordered by firmware,
        where min_firmware is encoded as ``(major << 16) | minor``
    """
    upgrades = []
    for upgrade in product.get("upgrades", []):
        temp_list = upgrade.get("features", {}).get("temperature_range")
        if temp_list is None or len(temp_list) < 2:
            continue
        min_firmware = (upgrade.get("major", 0) << 16) | upgrade.get("minor", 0)
        upgrades.append((min_firmware, (temp_list[0], temp_list[1])))
    return sorted(upgrades)


def vendor_default_features(vendor_data: dict[str, Any]) -> dict[str, Any]:
    """Return a vendor's default feature values.

    Upstream spells ``defaults`` flat (feature keys at the top level). A
    nested ``features`` object is also accepted. Keys with a null value, such
    as an unset ``temperature_range``, are dropped so they read as absent.

    Args:
        vendor_data: One vendor entry from products.json

    Returns:
        Feature name to default value
    """
    defaults = vendor_data.get("defaults", {})
    merged = {**defaults, **defaults.get("features", {})}
    merged.pop("features", None)
    return {key: value for key, value in merged.items() if value is not None}


def parse_uplight_coords(features: dict[str, Any]) -> tuple[int, int] | None:
    """Return a product's uplight position as ``(x, y)``, or None.

    Args:
        features: Product features with vendor defaults merged beneath them

    Returns:
        The uplight cell coordinates, None when absent or null
    """
    coords = features.get("uplight_coords")
    if coords is None:
        return None
    return (int(coords["x"]), int(coords["y"]))


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
        default_features = vendor_default_features(vendor_data)

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
            temp_list = features.get("temperature_range")
            if temp_list is not None:
                if len(temp_list) >= 2:
                    temp_range_expr = (
                        f"TemperatureRange(min={temp_list[0]}, max={temp_list[1]})"
                    )

            # Parse firmware-dependent temperature ranges
            temp_upgrade_exprs = [
                f"TemperatureRangeUpgrade(min_firmware={min_firmware}, "
                f"temperature_range=TemperatureRange(min={low}, max={high}))"
                for min_firmware, (low, high) in parse_temperature_range_upgrades(
                    product
                )
            ]

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
            uplight_coords = parse_uplight_coords(features)
            if uplight_coords is not None:
                code_lines.append(f"        uplight_coords={uplight_coords!r},")
            if temp_upgrade_exprs:
                code_lines.append("        temperature_range_upgrades=(")
                for expr in temp_upgrade_exprs:
                    code_lines.append(f"            {expr},")
                code_lines.append("        ),")
            code_lines.append("    ),")

            product_count += 1

    code_lines.append("}")
    code_lines.append("")

    print(f"Generated {product_count} product definitions")
    return "\n".join(code_lines)


def generate_registry_file(
    products_data: dict[str, Any] | list[dict[str, Any]],
    upstream: UpstreamCommit = UpstreamCommit(),
) -> str:
    """Generate complete registry.py file.

    Args:
        products_data: Parsed products.json data
        upstream: Upstream commit the data came from, recorded in the header

    Returns:
        Complete Python file content
    """
    header = '''"""LIFX product definitions and capability detection.

DO NOT EDIT THIS FILE MANUALLY.
Generated from https://github.com/LIFX/products/blob/master/products.json
by products/generator.py
__UPSTREAM_HEADER__

This module provides pre-generated product information for efficient runtime lookups.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum

from lifx.products.hidden_cells import hidden_cell_family


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


@dataclass(frozen=True)
class TemperatureRangeUpgrade:
    """A color temperature range a product gains from a firmware version on.

    Attributes:
        min_firmware: First firmware version with this range, encoded as
            ``(major << 16) | minor``
        temperature_range: Min/max color temperature in Kelvin from that version
    """

    min_firmware: int
    temperature_range: TemperatureRange


@dataclass
class ProductInfo:
    """Information about a LIFX product.

    Attributes:
        pid: Product ID
        name: Product name
        vendor: Vendor ID (always 1 for LIFX)
        capabilities: Bitfield of ProductCapability flags
        temperature_range: Min/max color temperature in Kelvin. On a registry
            entry this is the range of the earliest firmware; a device's own
            capabilities hold the range of the firmware it runs
        min_ext_mz_firmware: Minimum firmware version for extended multizone
        temperature_range_upgrades: Wider temperature ranges later firmware
            versions support
        uplight_coords: Cell ``(x, y)`` of the uplight on a Ceiling product's
            tile, None for every other product
    """

    pid: int
    name: str
    vendor: int
    capabilities: int
    temperature_range: TemperatureRange | None
    min_ext_mz_firmware: int | None
    temperature_range_upgrades: tuple[TemperatureRangeUpgrade, ...] = ()
    uplight_coords: tuple[int, int] | None = None

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

    @property
    def hidden_zones(self) -> frozenset[int]:
        """Zones with no LED, empty for a product with none.

        Rendering still covers the full rectangle; these cells are sent dark.
        On a Ceiling the uplight zone is included, though the uplight
        component still addresses it.
        """
        family = hidden_cell_family(self.pid)
        return family.zones if family else frozenset()

    @property
    def masked_zones(self) -> frozenset[int]:
        """Hidden zones a frame sends dark: ``hidden_zones`` less the uplight."""
        family = hidden_cell_family(self.pid)
        return family.masked_zones if family else frozenset()

    @property
    def visible_zone_count(self) -> int | None:
        """Cells that have an LED, or None when the registry knows no size.

        Only the products with hidden cells have a registry size; for every
        other product the count is whatever the device reports.
        """
        family = hidden_cell_family(self.pid)
        return family.visible_zone_count if family else None

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

    def for_firmware(self, firmware_version: int) -> ProductInfo:
        """Resolve the capabilities a device running this firmware has.

        Returns a copy, so the shared registry entry is never modified:
        extended multizone is dropped when the firmware predates it, and the
        temperature range is the one from the newest upgrade the firmware
        has reached.

        Args:
            firmware_version: Host firmware version, ``(major << 16) | minor``

        Returns:
            A new ProductInfo describing the device on that firmware
        """
        capabilities = self.capabilities
        if not self.supports_extended_multizone(firmware_version):
            capabilities &= ~ProductCapability.EXTENDED_MULTIZONE

        temperature_range = self.temperature_range
        reached = [
            upgrade
            for upgrade in self.temperature_range_upgrades
            if firmware_version >= upgrade.min_firmware
        ]
        if reached:
            newest = max(reached, key=lambda upgrade: upgrade.min_firmware)
            temperature_range = newest.temperature_range

        return replace(
            self, capabilities=capabilities, temperature_range=temperature_range
        )


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
            # Upstream spells the vendor defaults flat; a nested "features"
            # object is accepted too. Null defaults read as absent.
            defaults = vendor_data.get("defaults", {})
            default_features: dict[str, Any] = {
                key: value
                for key, value in {**defaults, **defaults.get("features", {})}.items()
                if key != "features" and value is not None
            }

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
                temp_list = features.get("temperature_range")
                if temp_list is not None:
                    if len(temp_list) >= 2:
                        temp_range = TemperatureRange(min=temp_list[0], max=temp_list[1])

                # Parse firmware-dependent temperature ranges
                temp_upgrades = []
                for upgrade in product.get("upgrades", []):
                    upgrade_list = upgrade.get("features", {}).get("temperature_range")
                    if upgrade_list is None or len(upgrade_list) < 2:
                        continue
                    temp_upgrades.append(
                        TemperatureRangeUpgrade(
                            min_firmware=(upgrade.get("major", 0) << 16)
                            | upgrade.get("minor", 0),
                            temperature_range=TemperatureRange(
                                min=upgrade_list[0], max=upgrade_list[1]
                            ),
                        )
                    )
                temp_upgrades.sort(key=lambda upgrade: upgrade.min_firmware)

                # Parse uplight position (Ceiling products only)
                uplight_coords = None
                coords = features.get("uplight_coords")
                if coords is not None:
                    uplight_coords = (int(coords["x"]), int(coords["y"]))

                product_info = ProductInfo(
                    pid=pid,
                    name=name,
                    vendor=vendor_id,
                    capabilities=capabilities,
                    temperature_range=temp_range,
                    min_ext_mz_firmware=min_ext_mz_firmware,
                    temperature_range_upgrades=tuple(temp_upgrades),
                    uplight_coords=uplight_coords,
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

    header = header.replace("__UPSTREAM_HEADER__", upstream.header_lines())
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
    upstream = fetch_upstream_commit("LIFX/products", "master", "products.json")
    registry_code = generate_registry_file(products_data, upstream)

    # Determine output path
    output_path = Path(__file__).parent / "registry.py"

    with open(output_path, "w") as f:
        f.write(registry_code)

    print(f"Generated {output_path}")

    format_generated_files(output_path)

    print("✓ Generation complete!")


if __name__ == "__main__":
    main()
