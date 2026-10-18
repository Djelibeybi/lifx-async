"""Capability resolution for products the registry does not list.

A product newer than the bundled registry still has to work on the day it
ships. Its shape is inferred from two queries: a matrix chain query that is
answered makes it a matrix light, an extended color zones query that is
answered makes it a multizone light, and neither makes it a plain light.

Ceiling and Mirror are never inferred here, because telling them apart needs a
product id the registry has never seen.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from lifx.const import (
    UNKNOWN_RANGE_MAX_KELVIN,
    UNKNOWN_RANGE_MIN_KELVIN,
)
from lifx.exceptions import LifxTimeoutError
from lifx.products.registry import (
    ProductCapability,
    ProductInfo,
    TemperatureRange,
    get_product,
    get_registry,
)
from lifx.protocol import packets

if TYPE_CHECKING:
    from lifx.network.connection import DeviceConnection

#: Seconds a probe waits for an answer. A device that does not support the
#: query normally replies with ``StateUnhandled`` at once; this bounds the
#: devices that stay silent instead.
PROBE_TIMEOUT: float = 2.0


def is_known_product(product_id: int) -> bool:
    """Return True if the product registry lists ``product_id``."""
    return get_registry().get_product(product_id) is not None


async def _answered(
    connection: DeviceConnection, packet: Any, state_type: type
) -> bool:
    """Send a probe and report whether the device answered it with its state."""
    try:
        response = await connection.request(packet, timeout=PROBE_TIMEOUT)
    except LifxTimeoutError:
        return False
    return isinstance(response, state_type)


async def probe_unknown_product(
    connection: DeviceConnection, product_id: int
) -> ProductInfo:
    """Infer the capabilities of a product the registry does not list.

    Args:
        connection: Connection to the device
        product_id: Product ID the device reported

    Returns:
        A synthetic ``ProductInfo`` named ``Unknown product <id>``. Color is
        assumed and the temperature range is the library's default.
    """
    is_matrix, is_multizone = await asyncio.gather(
        _answered(
            connection, packets.Tile.GetDeviceChain(), packets.Tile.StateDeviceChain
        ),
        _answered(
            connection,
            packets.MultiZone.GetExtendedColorZones(),
            packets.MultiZone.StateExtendedColorZones,
        ),
    )

    capabilities = ProductCapability.COLOR
    if is_matrix:
        capabilities |= ProductCapability.MATRIX
    elif is_multizone:
        capabilities |= (
            ProductCapability.MULTIZONE | ProductCapability.EXTENDED_MULTIZONE
        )

    return ProductInfo(
        pid=product_id,
        name=f"Unknown product {product_id}",
        vendor=1,
        capabilities=capabilities,
        temperature_range=TemperatureRange(
            min=UNKNOWN_RANGE_MIN_KELVIN, max=UNKNOWN_RANGE_MAX_KELVIN
        ),
        min_ext_mz_firmware=None,
    )


async def resolve_product_info(
    connection: DeviceConnection, product_id: int
) -> ProductInfo:
    """Return the registry entry for a product, probing the device if absent.

    This is the one place both ``Device.connect()`` and discovery construction
    learn what a product can do.
    """
    if is_known_product(product_id):
        return get_product(product_id)
    return await probe_unknown_product(connection, product_id)
