"""Device class detection from product capabilities.

Shared helper used by both Device.connect() and
DiscoveredDevice.create_device() to determine the appropriate device
class for a given product.
"""

from __future__ import annotations

from lifx.devices.ceiling import CeilingLight
from lifx.devices.hev import HevLight
from lifx.devices.infrared import InfraredLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight
from lifx.exceptions import LifxUnsupportedDeviceError
from lifx.products import is_ceiling_product, is_mirror_product
from lifx.products.registry import ProductInfo


def get_device_class_for_product(
    product_id: int,
    product_info: ProductInfo,
) -> type[Light]:
    """Determine the correct device class for a product.

    Detection order (first match wins):
    1. Ceiling product ID → CeilingLight
    2. Mirror product ID → MirrorLight
    3. Matrix capability → MatrixLight
    4. Multizone capability → MultiZoneLight
    5. Infrared capability → InfraredLight
    6. HEV capability → HevLight
    7. Relay-only or button-only (no colour) → raises
    8. Default → Light (covers colour, CCT, and brightness-only)

    Args:
        product_id: Product ID from device version response.
        product_info: Product capabilities from the registry.

    Returns:
        The appropriate Device subclass.

    Raises:
        LifxUnsupportedDeviceError: If device is a relay-only or
            button-only product not supported by this library.
    """
    if is_ceiling_product(product_id):
        return CeilingLight
    if is_mirror_product(product_id):
        return MirrorLight
    if product_info.has_matrix:
        return MatrixLight
    if product_info.has_multizone:
        return MultiZoneLight
    if product_info.has_infrared:
        return InfraredLight
    if product_info.has_hev:
        return HevLight
    if product_info.has_relays or (
        product_info.has_buttons and not product_info.has_color
    ):
        raise LifxUnsupportedDeviceError(
            f"Relay/button-only device (product {product_id}) is not a supported light"
        )

    return Light
