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

import ipaddress
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
from lifx.exceptions import LifxNetworkError, LifxTimeoutError
from lifx.network.mdns.dns import (
    DNS_TYPE_A,
    DNS_TYPE_AAAA,
    DNS_TYPE_SRV,
    DNS_TYPE_TXT,
    SrvData,
    TxtData,
    build_address_query,
    build_ptr_query,
    parse_dns_response,
)
from lifx.network.mdns.transport import MdnsTransport
from lifx.network.mdns.types import LifxServiceRecord
from lifx.network.utils import IdleDeadline

if TYPE_CHECKING:
    from lifx.devices.light import Light

_LOGGER = logging.getLogger(__name__)


def _pick_address(a_ip: str | None, aaaa_ips: list[str]) -> str | None:
    """Pick the best address for a host from its A and AAAA records.

    Prefers an IPv4 A record, then an IPv6 AAAA record (Thread devices are
    IPv6-only). Among AAAA records, routable addresses (ULA/GUA) are
    preferred over link-local, which would need a zone/scope ID to be
    reachable.
    """
    if a_ip is not None:
        return a_ip
    if aaaa_ips:
        routable = [
            addr for addr in aaaa_ips if not ipaddress.ip_address(addr).is_link_local
        ]
        return routable[0] if routable else aaaa_ips[0]
    return None


class _LifxRecordCache:
    """Accumulates mDNS records across response packets during discovery.

    Responders may split the records for a service instance across multiple
    packets (e.g. TXT in one packet, the AAAA for its SRV target in a later
    one), and a Thread border router advertises every device on its mesh at
    once. Records are therefore cached for the whole discovery window and
    each instance is emitted as soon as it can be fully resolved.
    """

    # Bound on entries per record table — guards against multicast floods
    # filling memory during the discovery window
    _MAX_ENTRIES = 1024

    def __init__(self) -> None:
        self._srv_by_instance: dict[str, SrvData] = {}
        self._txt_by_instance: dict[str, TxtData] = {}
        self._a_by_host: dict[str, str] = {}
        self._aaaa_by_host: dict[str, list[str]] = {}
        self._fallback_ip_by_instance: dict[str, str] = {}
        self._resolved_instances: set[str] = set()

    @staticmethod
    def _add(table: dict, key: str, value: object) -> None:
        if len(table) < _LifxRecordCache._MAX_ENTRIES or key in table:
            table[key] = value

    def add_packet(self, records: list, source_ip: str) -> bool:
        """Merge one packet's records into the cache.

        Args:
            records: List of DnsResourceRecord from the response
            source_ip: IP address the packet came from

        Returns:
            True if the packet contained LIFX-related records
        """
        packet_instances: list[str] = []
        has_lifx = False

        for record in records:
            name = record.name.lower()
            if LIFX_MDNS_SERVICE in name:
                has_lifx = True
            if record.rtype == DNS_TYPE_SRV and isinstance(record.parsed_data, SrvData):
                self._add(self._srv_by_instance, name, record.parsed_data)
            elif record.rtype == DNS_TYPE_TXT and isinstance(
                record.parsed_data, TxtData
            ):
                self._add(self._txt_by_instance, name, record.parsed_data)
                packet_instances.append(name)
                # A TXT record in LIFX format marks the packet as LIFX even
                # without a service name match, so that duplicate
                # re-announcements keep resetting the caller's idle deadline
                if "id" in record.parsed_data.pairs and "p" in record.parsed_data.pairs:
                    has_lifx = True
            elif record.rtype == DNS_TYPE_A and isinstance(record.parsed_data, str):
                self._add(self._a_by_host, name, record.parsed_data)
            elif record.rtype == DNS_TYPE_AAAA and isinstance(record.parsed_data, str):
                addrs = self._aaaa_by_host.setdefault(name, [])
                if record.parsed_data not in addrs and len(addrs) < 16:
                    addrs.append(record.parsed_data)

        # A packet advertising exactly one instance came from the device
        # itself (not an advertising proxy), so its source address can serve
        # as the device address if no A/AAAA record ever resolves.
        if len(packet_instances) == 1:
            self._fallback_ip_by_instance.setdefault(packet_instances[0], source_ip)

        return has_lifx

    def resolve(self) -> list[LifxServiceRecord]:
        """Return service records for instances that can now be resolved.

        Each instance is returned at most once across the lifetime of the
        cache.
        """
        results: list[LifxServiceRecord] = []

        for instance, txt_data in self._txt_by_instance.items():
            if instance in self._resolved_instances:
                continue

            # Extract required fields from TXT record
            serial = txt_data.pairs.get("id", "").lower()
            product_id_str = txt_data.pairs.get("p", "")
            firmware = txt_data.pairs.get("fw", "")

            # Validate required fields
            if not serial or not product_id_str:
                continue

            try:
                product_id = int(product_id_str)
            except ValueError:
                continue

            # Get port from SRV record or use default
            srv_data = self._srv_by_instance.get(instance)
            port = srv_data.port if srv_data else 56700

            # Resolve the instance's SRV target hostname to an address. An
            # instance advertised without any SRV record falls back to the
            # source address of its own single-instance response packet. An
            # instance WITH an SRV record but no address records yet stays
            # pending — its target is reported by pending_targets() for a
            # follow-up query — because guessing the packet's source address
            # would misattribute devices advertised by a border router.
            ip: str | None = None
            if srv_data is not None:
                target = srv_data.target.lower()
                ip = _pick_address(
                    self._a_by_host.get(target), self._aaaa_by_host.get(target, [])
                )
            else:
                ip = self._fallback_ip_by_instance.get(instance)
            if ip is None:
                continue

            self._resolved_instances.add(instance)
            results.append(
                LifxServiceRecord(
                    serial=serial,
                    ip=ip,
                    port=port,
                    product_id=product_id,
                    firmware=firmware,
                )
            )

        return results

    def pending_targets(self) -> list[str]:
        """Return SRV target hostnames still needed to resolve instances.

        These are hostnames of valid LIFX instances whose address records
        have not been seen — e.g. when a border router's single reply packet
        had room for every instance's TXT/SRV records but not all of their
        AAAA records. The caller can query these hosts directly.
        """
        targets: list[str] = []

        for instance, txt_data in self._txt_by_instance.items():
            if instance in self._resolved_instances:
                continue
            if not txt_data.pairs.get("id") or not txt_data.pairs.get("p"):
                continue
            srv_data = self._srv_by_instance.get(instance)
            if srv_data is None:
                continue
            target = srv_data.target.lower()
            if target in self._a_by_host or target in self._aaaa_by_host:
                continue
            targets.append(target)

        return targets


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
    record_cache = _LifxRecordCache()
    queried_targets: set[str] = set()
    start_time = time.monotonic()

    async with MdnsTransport() as transport:
        # Build and send PTR query
        query = build_ptr_query(LIFX_MDNS_SERVICE)

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

        # Per RFC 6762 §5.2, queriers should re-send their query to catch
        # responders whose (randomly delayed) answers were lost or deferred.
        # Responses are deduplicated by serial, so re-answers are harmless.
        retransmit_delays = [1.0, 3.0]

        idle_timeout = max_response_time * idle_timeout_multiplier
        deadline = IdleDeadline(timeout, idle_timeout)

        # Collect responses with dynamic timeout
        while True:
            if deadline.idle_expired:
                _LOGGER.debug(
                    {
                        "class": "discover_lifx_services",
                        "method": "discover",
                        "action": "idle_timeout",
                        "idle_time": time.monotonic() - deadline._last_response,
                        "idle_timeout": idle_timeout,
                    }
                )
                break

            if deadline.overall_expired:
                _LOGGER.debug(
                    {
                        "class": "discover_lifx_services",
                        "method": "discover",
                        "action": "overall_timeout",
                        "elapsed": time.monotonic() - deadline._start,
                        "timeout": timeout,
                    }
                )
                break

            remaining = deadline.remaining()
            if remaining <= 0:
                break

            # Cap the receive timeout at the next scheduled retransmission
            elapsed = time.monotonic() - start_time
            if retransmit_delays and elapsed >= retransmit_delays[0]:
                retransmit_delays.pop(0)
                _LOGGER.debug(
                    {
                        "class": "discover_lifx_services",
                        "method": "discover",
                        "action": "retransmitting_query",
                        "elapsed": elapsed,
                    }
                )
                await transport.send(query)
            if retransmit_delays:
                remaining = min(remaining, retransmit_delays[0] - elapsed)

            try:
                data, addr = await transport.receive(timeout=max(remaining, 0.01))
            except LifxTimeoutError:
                if retransmit_delays:
                    # Timed out waiting for the retransmission slot, not the
                    # deadline — loop to re-send the query
                    continue
                # Clean end of collection — no more responses within the deadline
                break
            except LifxNetworkError as e:
                _LOGGER.warning(
                    {
                        "class": "discover_lifx_services",
                        "action": "network_error",
                        "error": str(e),
                    }
                )
                break
            except Exception as e:
                _LOGGER.error(
                    {
                        "class": "discover_lifx_services",
                        "action": "unexpected_error",
                        "error": str(e),
                    },
                    exc_info=True,
                )
                raise

            try:
                # Parse DNS response
                response = parse_dns_response(data)

                # Only process responses (not queries)
                if not response.header.is_response:
                    continue

                # Merge every response packet into the cache: a packet
                # carrying only A/AAAA records may complete an instance whose
                # SRV/TXT arrived in an earlier packet. A packet may also
                # advertise multiple instances at once (e.g. a Thread border
                # router answering for its whole mesh).
                had_lifx = record_cache.add_packet(response.records, addr[0])
                extracted = record_cache.resolve()

                # Query address records the responses did not include (a
                # single reply packet may not have room for every AAAA
                # record). Capped to bound traffic on hostile networks.
                for target in record_cache.pending_targets():
                    if target in queried_targets or len(queried_targets) >= 64:
                        continue
                    queried_targets.add(target)
                    _LOGGER.debug(
                        {
                            "class": "discover_lifx_services",
                            "method": "discover",
                            "action": "querying_addresses",
                            "target": target,
                        }
                    )
                    await transport.send(build_address_query(target))

                if not had_lifx and not extracted:
                    continue

                # Reset idle timer on every valid LIFX response, before the
                # dedup check — repeated mDNS re-announcements from one device
                # must not cause premature idle expiry while slower devices
                # have not yet answered (Pitfall 1 / D-04, mirroring
                # _discover_with_packet).
                deadline.mark_response()

                for record in extracted:
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
                "elapsed": time.monotonic() - start_time,
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
