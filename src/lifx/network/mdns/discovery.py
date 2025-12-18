"""mDNS discovery for LIFX devices.

This module provides discovery functions using mDNS/DNS-SD to find
LIFX devices on the local network.

Example:
    Low-level API (raw service records):
    ```python
    async for record in discover_lifx_services():
        print(f"Found: {record.serial} at {record.ip}:{record.port}")
    ```

    High-level API (device instances):
    ```python
    async for device in discover_devices_mdns():
        async with device:
            print(f"Found: {await device.get_label()}")
    ```
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from lifx.const import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DISCOVERY_TIMEOUT,
    IDLE_TIMEOUT_MULTIPLIER,
    LIFX_MDNS_SERVICE,
    MAX_RESPONSE_TIME,
)
from lifx.network.mdns.dns import (
    DNS_TYPE_A,
    DNS_TYPE_PTR,
    DNS_TYPE_SRV,
    DNS_TYPE_TXT,
    SrvData,
    TxtData,
    build_ptr_query,
    parse_dns_response,
)
from lifx.network.mdns.transport import MdnsTransport
from lifx.network.mdns.types import LifxServiceRecord

if TYPE_CHECKING:
    from lifx.devices.light import Light

_LOGGER = logging.getLogger(__name__)


def _extract_lifx_info(
    records: list,
    source_ip: str,
) -> LifxServiceRecord | None:
    """Extract LIFX device info from mDNS records.

    Args:
        records: List of DnsResourceRecord from the response
        source_ip: IP address the response came from

    Returns:
        LifxServiceRecord if valid LIFX device info found, None otherwise
    """
    # Find records of each type
    srv_data: SrvData | None = None
    txt_data: TxtData | None = None
    a_record_ip: str | None = None

    for record in records:
        if record.rtype == DNS_TYPE_SRV and isinstance(record.parsed_data, SrvData):
            srv_data = record.parsed_data
        elif record.rtype == DNS_TYPE_TXT and isinstance(record.parsed_data, TxtData):
            txt_data = record.parsed_data
        elif record.rtype == DNS_TYPE_A and isinstance(record.parsed_data, str):
            a_record_ip = record.parsed_data

    # Need at least TXT record to identify the device
    if txt_data is None:
        return None

    # Extract required fields from TXT record
    serial = txt_data.pairs.get("id", "").lower()
    product_id_str = txt_data.pairs.get("p", "")
    firmware = txt_data.pairs.get("fw", "")

    # Validate required fields
    if not serial or not product_id_str:
        return None

    try:
        product_id = int(product_id_str)
    except ValueError:
        return None

    # Get port from SRV record or use default
    port = srv_data.port if srv_data else 56700

    # Get IP from A record or use source IP
    ip = a_record_ip if a_record_ip else source_ip

    return LifxServiceRecord(
        serial=serial,
        ip=ip,
        port=port,
        product_id=product_id,
        firmware=firmware,
    )


def create_device_from_record(
    record: LifxServiceRecord,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Light | None:
    """Create appropriate device class based on product ID from mDNS record.

    Uses the product registry to determine device capabilities and instantiate
    the correct device class (Light, MatrixLight, MultiZoneLight, etc.).

    Args:
        record: LifxServiceRecord from mDNS discovery
        timeout: Request timeout for the device
        max_retries: Maximum retry attempts for requests

    Returns:
        Device instance of the appropriate type, or None if device should be skipped
        (e.g., relay/button-only devices)

    Example:
        ```python
        async for record in discover_lifx_services():
            device = create_device_from_record(record)
            if device:
                async with device:
                    print(f"Device: {await device.get_label()}")
        ```
    """
    from lifx.devices.ceiling import CeilingLight
    from lifx.devices.hev import HevLight
    from lifx.devices.infrared import InfraredLight
    from lifx.devices.light import Light
    from lifx.devices.matrix import MatrixLight
    from lifx.devices.multizone import MultiZoneLight
    from lifx.products import get_product, is_ceiling_product

    product = get_product(record.product_id)
    kwargs = {
        "serial": record.serial,
        "ip": record.ip,
        "port": record.port,
        "timeout": timeout,
        "max_retries": max_retries,
    }

    # Priority-based selection matching DiscoveredDevice.create_device()
    if is_ceiling_product(record.product_id):
        return CeilingLight(**kwargs)
    if product.has_matrix:
        return MatrixLight(**kwargs)
    if product.has_multizone:
        return MultiZoneLight(**kwargs)
    if product.has_infrared:
        return InfraredLight(**kwargs)
    if product.has_hev:
        return HevLight(**kwargs)
    if product.has_relays or (product.has_buttons and not product.has_color):
        return None
    return Light(**kwargs)


async def discover_lifx_services(
    timeout: float = DISCOVERY_TIMEOUT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
) -> AsyncGenerator[LifxServiceRecord, None]:
    """Discover LIFX devices via mDNS and yield service records.

    Sends an mDNS PTR query for _lifx._udp.local and yields service records
    as devices respond. Records are deduplicated by serial number.

    This is the low-level API that provides raw mDNS data. For device instances,
    use discover_devices_mdns() instead.

    Args:
        timeout: Overall discovery timeout in seconds
        max_response_time: Maximum expected response time
        idle_timeout_multiplier: Multiplier for idle timeout

    Yields:
        LifxServiceRecord for each discovered device

    Example:
        ```python
        async for record in discover_lifx_services(timeout=10.0):
            print(f"Found: {record.serial} (product {record.product_id})")
            print(f"  IP: {record.ip}:{record.port}")
            print(f"  Firmware: {record.firmware}")
        ```
    """
    seen_serials: set[str] = set()
    start_time = time.time()

    async with MdnsTransport() as transport:
        # Build and send PTR query
        query = build_ptr_query(LIFX_MDNS_SERVICE)
        request_time = time.time()

        _LOGGER.debug(
            {
                "class": "discover_lifx_services",
                "method": "discover",
                "action": "sending_query",
                "service": LIFX_MDNS_SERVICE,
                "timeout": timeout,
            }
        )

        await transport.send(query)

        # Calculate idle timeout
        idle_timeout = max_response_time * idle_timeout_multiplier
        last_response_time = request_time

        # Collect responses with dynamic timeout
        while True:
            # Calculate elapsed time since last response
            elapsed_since_last = time.time() - last_response_time

            # Stop if we've been idle too long
            if elapsed_since_last >= idle_timeout:
                _LOGGER.debug(
                    {
                        "class": "discover_lifx_services",
                        "method": "discover",
                        "action": "idle_timeout",
                        "idle_time": elapsed_since_last,
                        "idle_timeout": idle_timeout,
                    }
                )
                break

            # Stop if we've exceeded the overall timeout
            if time.time() - request_time >= timeout:
                _LOGGER.debug(
                    {
                        "class": "discover_lifx_services",
                        "method": "discover",
                        "action": "overall_timeout",
                        "elapsed": time.time() - request_time,
                        "timeout": timeout,
                    }
                )
                break

            # Calculate remaining timeout
            remaining_idle = idle_timeout - elapsed_since_last
            remaining_overall = timeout - (time.time() - request_time)
            remaining = min(remaining_idle, remaining_overall)

            try:
                data, addr = await transport.receive(timeout=remaining)
                response_timestamp = time.time()

            except Exception:
                # Timeout or error - stop collecting
                _LOGGER.debug(
                    {
                        "class": "discover_lifx_services",
                        "method": "discover",
                        "action": "no_responses",
                    }
                )
                break

            try:
                # Parse DNS response
                response = parse_dns_response(data)

                # Only process responses (not queries)
                if not response.header.is_response:
                    continue

                # Check if this is a LIFX response (has PTR for _lifx._udp.local)
                has_lifx_ptr = any(
                    r.rtype == DNS_TYPE_PTR and LIFX_MDNS_SERVICE in r.name
                    for r in response.records
                )

                if not has_lifx_ptr:
                    # Might still be a LIFX device responding without PTR
                    # Check TXT records for LIFX format
                    has_lifx_txt = any(
                        r.rtype == DNS_TYPE_TXT
                        and isinstance(r.parsed_data, TxtData)
                        and "id" in r.parsed_data.pairs
                        and "p" in r.parsed_data.pairs
                        for r in response.records
                    )
                    if not has_lifx_txt:
                        continue

                # Extract device info from records
                record = _extract_lifx_info(response.records, addr[0])

                if record is None:
                    continue

                # Deduplicate by serial
                if record.serial in seen_serials:
                    continue

                seen_serials.add(record.serial)

                _LOGGER.debug(
                    {
                        "class": "discover_lifx_services",
                        "method": "discover",
                        "action": "device_found",
                        "serial": record.serial,
                        "ip": record.ip,
                        "port": record.port,
                        "product_id": record.product_id,
                    }
                )

                yield record

                # Update last response time for idle timeout
                last_response_time = response_timestamp

            except Exception as e:
                _LOGGER.debug(
                    {
                        "class": "discover_lifx_services",
                        "method": "discover",
                        "action": "parse_error",
                        "error": str(e),
                        "source_ip": addr[0],
                    }
                )
                continue

        _LOGGER.debug(
            {
                "class": "discover_lifx_services",
                "method": "discover",
                "action": "complete",
                "devices_found": len(seen_serials),
                "elapsed": time.time() - start_time,
            }
        )


async def discover_devices_mdns(
    timeout: float = DISCOVERY_TIMEOUT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AsyncGenerator[Light, None]:
    """Discover LIFX devices via mDNS and yield device instances.

    This is the high-level API that yields fully-typed device instances
    (Light, MatrixLight, MultiZoneLight, etc.) based on product capabilities.

    Devices that are not lights (relays, buttons without color) are automatically
    filtered out and not yielded.

    Args:
        timeout: Overall discovery timeout in seconds
        max_response_time: Maximum expected response time
        idle_timeout_multiplier: Multiplier for idle timeout
        device_timeout: Request timeout for created devices
        max_retries: Maximum retry attempts for device requests

    Yields:
        Device instances (Light, MatrixLight, etc.) as they are discovered

    Example:
        ```python
        async for device in discover_devices_mdns(timeout=10.0):
            async with device:
                label = await device.get_label()
                print(f"{type(device).__name__}: {label} at {device.ip}")
        ```
    """
    async for record in discover_lifx_services(
        timeout=timeout,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    ):
        device = create_device_from_record(
            record,
            timeout=device_timeout,
            max_retries=max_retries,
        )

        if device is not None:
            yield device
