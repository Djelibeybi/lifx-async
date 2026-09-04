"""mDNS discovery for LIFX devices.

This module provides discovery functions using mDNS/DNS-SD to find
LIFX devices on the local network.

Example:
    High-level API (device instances):
    ```python
    async for device in discover_devices_mdns():
        async with device:
            print(f"Found: {await device.get_label()}")
    ```
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import struct
import time
from collections import Counter
from collections.abc import AsyncGenerator, Callable, Iterable, Iterator
from contextlib import aclosing, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal, cast

from lifx.const import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DISCOVERY_TIMEOUT,
    IDLE_TIMEOUT_MULTIPLIER,
    LIFX_MDNS_SERVICE,
    MAX_RESPONSE_TIME,
    TIMEOUT_ERRORS,
)
from lifx.devices.base import Device
from lifx.devices.detection import get_device_class_for_product
from lifx.devices.light import Light
from lifx.exceptions import (
    LifxConnectionError,
    LifxNetworkError,
    LifxProtocolError,
    LifxTimeoutError,
    LifxUnsupportedCommandError,
    LifxUnsupportedDeviceError,
)
from lifx.network.address import validate_address, validate_port
from lifx.network.connection import DeviceConnection
from lifx.network.discovery.mdns.dns import (
    DNS_TYPE_A,
    DNS_TYPE_AAAA,
    DNS_TYPE_SRV,
    DNS_TYPE_TXT,
    DnsResourceRecord,
    SrvData,
    TxtData,
    build_address_query,
    build_ptr_query,
    parse_dns_response,
)
from lifx.network.discovery.mdns.transport import MdnsTransport
from lifx.network.discovery.mdns.types import _LifxServiceRecord
from lifx.network.discovery.udp import (
    _current_discovery_observer,
    _DiscoveryObserver,
    _emit_discovery_event,
)
from lifx.network.utils import IdleDeadline
from lifx.products import get_product
from lifx.protocol import packets

_LOGGER = logging.getLogger(__name__)

# Count ceilings bound fixed Python object overhead independently of these
# attacker-controlled variable-payload byte ceilings.
_MAX_RETAINED_PAYLOAD_BYTES_PER_RECORD = 4096
_MAX_RETAINED_PAYLOAD_BYTES_PER_SWEEP = 262144
_MAX_MDNS_LIVENESS_PROBES = 16
_ECHO_LIVENESS_PAYLOAD = bytes(range(64))


@dataclass(frozen=True)
class _MdnsSweepFailure:
    """Bounded sweep failure safe to pass into merged discovery."""

    stage: str
    reason: str
    error_type: str


@dataclass(frozen=True)
class _MdnsCandidateFailure:
    """Bounded candidate failure safe to pass into merged discovery."""

    stage: str
    reason: str
    error_type: str


_MdnsFailure = _MdnsSweepFailure | _MdnsCandidateFailure
_MdnsFailureSink = Callable[[_MdnsFailure], None]


class _MdnsCandidateIdentityError(Exception):
    """A verified connection no longer represents the advertised identity."""


class _MdnsCandidateResponseError(Exception):
    """A correlated candidate response has the wrong type or payload."""


@dataclass(frozen=True)
class _MdnsServiceSourceOverride:
    """Caller-local factory for a hermetic private service-record stream."""

    source_factory: Callable[[], AsyncGenerator[_LifxServiceRecord, None]]


_MDNS_SERVICE_SOURCE_OVERRIDE: ContextVar[_MdnsServiceSourceOverride | None] = (
    ContextVar("lifx_mdns_service_source_override", default=None)
)


@contextmanager
def _override_mdns_service_source(
    source_factory: Callable[[], AsyncGenerator[_LifxServiceRecord, None]],
) -> Iterator[_MdnsServiceSourceOverride]:
    """Use one injected source in this caller context and always reset it."""
    override = _MdnsServiceSourceOverride(source_factory)
    token = _MDNS_SERVICE_SOURCE_OVERRIDE.set(override)
    try:
        yield override
    finally:
        _MDNS_SERVICE_SOURCE_OVERRIDE.reset(token)


def _current_mdns_service_source_override() -> _MdnsServiceSourceOverride | None:
    """Return the private source override selected by this caller context."""
    return _MDNS_SERVICE_SOURCE_OVERRIDE.get()


def _normalise_dns_name(name: str) -> str:
    """Canonicalise a DNS name without changing its label structure."""
    if name.endswith("."):
        name = name[:-1]
    return name.casefold()


_LIFX_MDNS_SERVICE_CANONICAL = _normalise_dns_name(LIFX_MDNS_SERVICE)


def _is_lifx_service_instance(name: str | None) -> bool:
    """Return whether *name* is an exact instance of the LIFX service."""
    if name is None:
        return False
    canonical = _normalise_dns_name(name)
    suffix = f".{_LIFX_MDNS_SERVICE_CANONICAL}"
    return canonical.endswith(suffix) and bool(canonical[: -len(suffix)])


def _connectivity_from_txt(value: str | None) -> Literal["wifi", "thread"]:
    """Map the exact private TXT sentinel to public connectivity metadata."""
    return "thread" if value == "2" else "wifi"


def _validate_txt_id(value: str) -> str | None:
    """Validate an mDNS TXT identity against broadcast serial rules.

    TXT identities deliberately accept less syntax than ``Serial.from_string``:
    discovery data must contain exactly six hexadecimal octets with no
    separators, and the value must identify one unicast device.
    """
    if len(value) != 12:
        return None
    try:
        raw = bytes.fromhex(value)
    except ValueError:
        return None
    if len(raw) != 6 or raw == b"\x00" * 6 or raw == b"\xff" * 6:
        return None
    if raw[0] & 0x01:
        return None
    return value.lower()


_ULA_NETWORK = ipaddress.ip_network("fc00::/7")
_GUA_NETWORK = ipaddress.ip_network("2000::/3")


def _is_usable_mdns_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    """Return whether a syntactically valid candidate can name a route."""
    if address.is_unspecified:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return False
        if address.is_link_local and address.scope_id is None:
            return False
    return True


def _pick_address(addresses: Iterable[str]) -> str | None:
    """Select the lexical address from the best usable class.

    The class order is IPv4, ULA, GUA, then scoped link-local. A syntactically
    valid but unusable address remains useful cache evidence but cannot name a
    route, so it is rejected before candidate ranking. DNS AAAA wire data does
    not carry a zone ID, so scoped link-local is available only to internal or
    synthetic callers that already know the interface scope.
    """
    candidates: list[tuple[int, str]] = []
    for address in addresses:
        parsed = ipaddress.ip_address(address)
        if not _is_usable_mdns_address(parsed):
            continue

        priority: int | None = None
        if isinstance(parsed, ipaddress.IPv4Address):
            priority = 0
        elif parsed in _ULA_NETWORK:
            priority = 1
        elif parsed in _GUA_NETWORK:
            priority = 2
        elif parsed.is_link_local:
            priority = 3

        if priority is not None:
            candidates.append((priority, address))

    return min(candidates)[1] if candidates else None


def _retained_payload_cost(
    name: str,
    rtype: int,
    rdata: bytes,
    parsed_data: object,
) -> int:
    """Return the exact variable payload bytes copied into cache state."""
    parsed_cost = 0
    if rtype == DNS_TYPE_TXT and isinstance(parsed_data, TxtData):
        parsed_cost = sum(len(value.encode()) for value in parsed_data.strings)
    elif rtype == DNS_TYPE_SRV and isinstance(parsed_data, SrvData):
        parsed_cost = len(_normalise_dns_name(parsed_data.target).encode()) + 6
    elif rtype in (DNS_TYPE_A, DNS_TYPE_AAAA) and isinstance(parsed_data, str):
        parsed_cost = len(ipaddress.ip_address(parsed_data).packed)
    return len(name.encode()) + len(rdata) + 4 + parsed_cost


@dataclass
class _CachedResourceRecord:
    """One complete live DNS resource-record identity and its parsed value."""

    name: str
    rtype: int
    rclass: int
    rdata: bytes
    parsed_data: object
    retained_payload_bytes: int
    expires_at: float | None = None

    @property
    def identity(self) -> tuple[str, int, int, bytes]:
        """Return the case-normalised identity used for cache refreshes."""
        return (self.name, self.rtype, self.rclass, self.rdata)


class _LifxRecordCache:
    """Accumulates mDNS records across response packets during discovery.

    Responders may split the records for a service instance across multiple
    packets (e.g. TXT in one packet, the AAAA for its SRV target in a later
    one), and a Thread border router advertises every device on its mesh at
    once. Records are therefore cached for the whole discovery window and
    each instance is emitted as soon as it can be fully resolved.
    """

    # Distinct owner admission remains bounded for the discovery window.
    _MAX_ENTRIES = 1024
    _MAX_TXT_RRS_PER_OWNER = 16
    _MAX_SRV_RRS_PER_OWNER = 16
    _MAX_ADDRESS_RRS_PER_OWNER = 256
    _MAX_ADDRESS_RRS_PER_SWEEP = 1024

    def __init__(self) -> None:
        self._records_by_owner: dict[
            str,
            dict[
                int,
                dict[tuple[str, int, int, bytes], _CachedResourceRecord],
            ],
        ] = {}
        self._construction_owners: set[str] = set()
        self._address_owners: set[str] = set()
        self._fallback_ip_by_instance: dict[str, str] = {}
        self._resolved_instances: set[str] = set()
        self._pending_expiries: dict[tuple[str, int, int, bytes], float] = {}
        self._rejection_counts: Counter[tuple[str, str]] = Counter()
        self._reported_rejections: set[tuple[str, str, str]] = set()
        self._address_rr_count = 0
        self._address_overflowed_owners: set[str] = set()
        self._address_budget_exhausted = False
        self._retained_payload_bytes = 0
        self._byte_incomplete_owner_types: set[tuple[str, int]] = set()
        self._retained_payload_budget_exhausted = False

    @property
    def rejection_counts(self) -> dict[tuple[str, str], int]:
        """Return the privacy-safe aggregate collected for later reporting."""
        return dict(self._rejection_counts)

    def count_rejection(self, reason: str, record_type: str) -> None:
        """Count one observation without retaining packet or address details."""
        self._rejection_counts[(reason, record_type)] += 1

    def records_for(self, owner: str, rtype: int) -> tuple[_CachedResourceRecord, ...]:
        """Return live records for one owner/type in first-learned order."""
        by_type = self._records_by_owner.get(_normalise_dns_name(owner))
        if by_type is None:
            return ()
        return tuple(by_type.get(rtype, {}).values())

    def owners_for(self, rtype: int) -> tuple[str, ...]:
        """Return admitted owners carrying at least one live record of a type."""
        return tuple(
            owner
            for owner, by_type in self._records_by_owner.items()
            if by_type.get(rtype)
        )

    def _addresses_in_order(self, owner: str) -> tuple[str, ...]:
        """Return canonical addresses in first-learned order for selection."""
        values: list[str] = []
        for rtype in (DNS_TYPE_A, DNS_TYPE_AAAA):
            for record in self.records_for(owner, rtype):
                if isinstance(record.parsed_data, str):
                    values.append(record.parsed_data)
        return tuple(values)

    def addresses_for(self, owner: str) -> frozenset[str]:
        """Return immutable unordered advertised-address membership."""
        return frozenset(self._addresses_in_order(owner))

    def selected_address_for(self, owner: str) -> str | None:
        """Select a usable address without exposing same-class ordering."""
        owner = owner.lower()
        if (
            self._retained_payload_budget_exhausted
            or self._address_budget_exhausted
            or owner in self._address_overflowed_owners
            or (owner, DNS_TYPE_A) in self._byte_incomplete_owner_types
            or (owner, DNS_TYPE_AAAA) in self._byte_incomplete_owner_types
        ):
            return None
        return _pick_address(self._addresses_in_order(owner))

    def _admit_owner(self, owner: str, rtype: int) -> bool:
        """Admit one owner within its construction or address budget."""
        owners = (
            self._address_owners
            if rtype in (DNS_TYPE_A, DNS_TYPE_AAAA)
            else self._construction_owners
        )
        if owner in owners:
            return True
        if len(owners) >= self._MAX_ENTRIES:
            return False
        owners.add(owner)
        self._records_by_owner.setdefault(owner, {})
        return True

    @staticmethod
    def _record_type_name(rtype: int) -> str:
        """Return the stable diagnostic type names used by the cache."""
        return {
            DNS_TYPE_A: "A",
            DNS_TYPE_AAAA: "AAAA",
            DNS_TYPE_SRV: "SRV",
            DNS_TYPE_TXT: "TXT",
        }[rtype]

    def _add_record(self, record: DnsResourceRecord) -> bool:
        """Admit or refresh one supported RR by its complete DNS identity."""
        if record.rtype not in (
            DNS_TYPE_TXT,
            DNS_TYPE_SRV,
            DNS_TYPE_A,
            DNS_TYPE_AAAA,
        ):
            return False

        type_name = self._record_type_name(record.rtype)
        if record.cache_flush:
            self._rejection_counts[("unexpected_cache_flush", type_name)] += 1

        name = _normalise_dns_name(record.name)
        parsed_data = record.parsed_data
        if record.rtype in (DNS_TYPE_A, DNS_TYPE_AAAA):
            if not isinstance(parsed_data, str):
                return False
            try:
                parsed_address = ipaddress.ip_address(parsed_data)
            except ValueError:
                self._rejection_counts[("invalid_address", type_name)] += 1
                return False
            if (
                isinstance(parsed_address, ipaddress.IPv6Address)
                and parsed_address.ipv4_mapped is not None
            ):
                parsed_data = f"::ffff:{parsed_address.ipv4_mapped}"
            else:
                parsed_data = str(parsed_address)

        masked_class = record.rclass & 0x7FFF
        identity = (name, record.rtype, masked_class, record.rdata)
        owner_records = self._records_by_owner.get(name)
        by_type = owner_records.get(record.rtype, {}) if owner_records else {}
        existing = by_type.get(identity)

        if record.ttl == 0:
            if existing is None:
                return False
            expires_at = time.monotonic() + 1.0
            existing.expires_at = expires_at
            self._pending_expiries[identity] = expires_at
            return True

        retained_payload_bytes = _retained_payload_cost(
            name,
            record.rtype,
            record.rdata,
            parsed_data,
        )
        if retained_payload_bytes > _MAX_RETAINED_PAYLOAD_BYTES_PER_RECORD:
            self._byte_incomplete_owner_types.add((name, record.rtype))
            self._rejection_counts[("record_byte_capacity", type_name)] += 1
            return False

        previous_payload_bytes = (
            existing.retained_payload_bytes if existing is not None else 0
        )
        prospective_payload_bytes = (
            self._retained_payload_bytes
            - previous_payload_bytes
            + retained_payload_bytes
        )
        if (
            self._retained_payload_budget_exhausted
            or prospective_payload_bytes > _MAX_RETAINED_PAYLOAD_BYTES_PER_SWEEP
        ):
            self._retained_payload_budget_exhausted = True
            self._rejection_counts[("sweep_byte_capacity", type_name)] += 1
            return False

        if existing is not None:
            existing.parsed_data = parsed_data
            existing.retained_payload_bytes = retained_payload_bytes
            existing.expires_at = None
            self._pending_expiries.pop(identity, None)
            self._retained_payload_bytes = prospective_payload_bytes
            return True

        if not self._admit_owner(name, record.rtype):
            if record.rtype in (DNS_TYPE_A, DNS_TYPE_AAAA):
                self._address_budget_exhausted = True
                self._rejection_counts[("address_capacity", type_name)] += 1
            else:
                self._rejection_counts[("owner_capacity", type_name)] += 1
            return False
        by_type = self._records_by_owner[name].setdefault(record.rtype, {})

        if record.rtype in (DNS_TYPE_A, DNS_TYPE_AAAA):
            if (
                self._address_budget_exhausted
                or name in self._address_overflowed_owners
            ):
                self._rejection_counts[("address_capacity", type_name)] += 1
                return False
            address_count_for_owner = sum(
                len(self._records_by_owner[name].get(address_type, {}))
                for address_type in (DNS_TYPE_A, DNS_TYPE_AAAA)
            )
            if address_count_for_owner >= self._MAX_ADDRESS_RRS_PER_OWNER:
                self._address_overflowed_owners.add(name)
                self._rejection_counts[("address_capacity", type_name)] += 1
                return False
            if self._address_rr_count >= self._MAX_ADDRESS_RRS_PER_SWEEP:
                self._address_budget_exhausted = True
                self._address_overflowed_owners.add(name)
                self._rejection_counts[("address_capacity", type_name)] += 1
                return False

        limit: int | None = None
        if record.rtype == DNS_TYPE_TXT:
            limit = self._MAX_TXT_RRS_PER_OWNER
        elif record.rtype == DNS_TYPE_SRV:
            limit = self._MAX_SRV_RRS_PER_OWNER
        if limit is not None and len(by_type) >= limit:
            type_name = self._record_type_name(record.rtype)
            self._rejection_counts[("rr_identity_limit", type_name)] += 1
            return False

        cached = _CachedResourceRecord(
            name=name,
            rtype=record.rtype,
            rclass=masked_class,
            rdata=record.rdata,
            parsed_data=parsed_data,
            retained_payload_bytes=retained_payload_bytes,
        )
        by_type[cached.identity] = cached
        self._retained_payload_bytes = prospective_payload_bytes
        if record.rtype in (DNS_TYPE_A, DNS_TYPE_AAAA):
            self._address_rr_count += 1
        return True

    def next_expiry_delay(self, now: float) -> float | None:
        """Return the delay until the nearest pending goodbye expires."""
        if not self._pending_expiries:
            return None
        return max(min(self._pending_expiries.values()) - now, 0.0)

    def expire(self, now: float) -> int:
        """Remove every exact RR whose one-second goodbye grace has elapsed."""
        due = [
            identity
            for identity, expires_at in self._pending_expiries.items()
            if now >= expires_at
        ]
        expired = 0
        for identity in due:
            self._pending_expiries.pop(identity, None)
            owner, rtype, _rclass, _rdata = identity
            by_owner = self._records_by_owner.get(owner)
            if by_owner is None:
                continue
            by_type = by_owner.get(rtype)
            expired_record = (
                by_type.pop(identity, None) if by_type is not None else None
            )
            if expired_record is None:
                continue
            self._retained_payload_bytes -= expired_record.retained_payload_bytes
            if self._retained_payload_bytes < 0:
                raise RuntimeError("mDNS retained-payload accounting underflow")
            if rtype in (DNS_TYPE_A, DNS_TYPE_AAAA):
                self._address_rr_count -= 1
            expired += 1
            if not by_type:
                by_owner.pop(rtype, None)
        return expired

    def _reject(self, instance: str, reason: str, record_type: str) -> None:
        """Count one stable, privacy-safe rejection reason per instance."""
        rejection = (instance, reason, record_type)
        if rejection in self._reported_rejections:
            return
        self._reported_rejections.add(rejection)
        self._rejection_counts[(reason, record_type)] += 1

    @staticmethod
    def _txt_values(txt_data: TxtData, key: str) -> tuple[str, ...]:
        """Read every raw value for a TXT key without last-wins collapse."""
        values: list[str] = []
        for string in txt_data.strings:
            candidate_key, separator, value = string.partition("=")
            if separator and candidate_key == key:
                values.append(value)
        return tuple(values)

    def _resolve_txt_metadata(
        self, instance: str
    ) -> tuple[str, int, str | None, Literal["wifi", "thread"]] | None:
        """Resolve one unambiguous TXT construction identity for an owner."""
        if (instance, DNS_TYPE_TXT) in self._byte_incomplete_owner_types:
            return None
        serial: str | None = None
        product_id: int | None = None
        firmware: str | None = None
        firmware_seen = False
        connectivity: Literal["wifi", "thread"] | None = None

        for record in self.records_for(instance, DNS_TYPE_TXT):
            if not isinstance(record.parsed_data, TxtData):
                self._reject(instance, "malformed_packet", "TXT")
                return None
            txt_data = record.parsed_data

            candidate_ids = self._txt_values(txt_data, "id")
            if not candidate_ids or any(not value for value in candidate_ids):
                self._reject(instance, "missing_txt_id", "TXT")
                return None
            for candidate_id in candidate_ids:
                candidate_serial = _validate_txt_id(candidate_id)
                if candidate_serial is None:
                    self._reject(instance, "invalid_txt_id", "TXT")
                    return None
                if serial is None:
                    serial = candidate_serial
                elif candidate_serial != serial:
                    self._reject(instance, "conflicting_txt_id", "TXT")
                    return None

            product_values = self._txt_values(txt_data, "p")
            if not product_values or any(not value for value in product_values):
                self._reject(instance, "missing_product_id", "TXT")
                return None
            for product_value in product_values:
                try:
                    candidate_product_id = int(product_value)
                except ValueError:
                    self._reject(instance, "invalid_product_id", "TXT")
                    return None
                if product_id is None:
                    product_id = candidate_product_id
                elif candidate_product_id != product_id:
                    return None

            firmware_values = self._txt_values(txt_data, "fw")
            for candidate_firmware in firmware_values or (None,):
                if not firmware_seen:
                    firmware = candidate_firmware
                    firmware_seen = True
                elif candidate_firmware != firmware:
                    return None

            connectivity_values = self._txt_values(txt_data, "tm")
            for raw_connectivity in connectivity_values or (None,):
                candidate_connectivity = _connectivity_from_txt(raw_connectivity)
                if connectivity is None:
                    connectivity = candidate_connectivity
                elif candidate_connectivity != connectivity:
                    return None

        if serial is None or product_id is None or connectivity is None:
            return None
        return serial, product_id, firmware, connectivity

    def _resolve_srv_endpoint(self, instance: str) -> tuple[str, int] | None:
        """Resolve one target and port when every live SRV RR agrees."""
        if (instance, DNS_TYPE_SRV) in self._byte_incomplete_owner_types:
            return None
        endpoints: set[tuple[str, int]] = set()
        for record in self.records_for(instance, DNS_TYPE_SRV):
            if not isinstance(record.parsed_data, SrvData):
                self._reject(instance, "malformed_packet", "SRV")
                return None
            try:
                validate_port(record.parsed_data.port)
            except ValueError:
                self._reject(instance, "invalid_port", "SRV")
                return None
            endpoints.add(
                (
                    _normalise_dns_name(record.parsed_data.target),
                    record.parsed_data.port,
                )
            )
        if len(endpoints) != 1:
            return None
        return next(iter(endpoints))

    @staticmethod
    def _setdefault(table: dict[str, str], key: str, value: str) -> None:
        """Remember the first value for a key without exceeding the table cap."""
        if key in table:
            return
        if len(table) < _LifxRecordCache._MAX_ENTRIES:
            table[key] = value

    def add_packet(self, records: list, source_ip: str) -> bool:
        """Merge one packet's records into the cache.

        Args:
            records: List of DnsResourceRecord from the response
            source_ip: IP address the packet came from

        Returns:
            True if the packet contained LIFX-related records
        """
        # Only the distinction between one and multiple advertised instances
        # matters for source-address fallback, so retain at most two names.
        packet_instances: set[str] = set()
        has_lifx = False

        packet_address_owners: set[str] = set()
        for record in records:
            name = _normalise_dns_name(record.name)
            is_construction_record = record.rtype in (DNS_TYPE_TXT, DNS_TYPE_SRV)
            if is_construction_record and not _is_lifx_service_instance(name):
                continue

            # Count every TXT owner advertised in this packet before cache
            # admission. A refused goodbye or over-cap record still proves
            # that a proxy may be answering for multiple devices, so its
            # packet source must never be attributed to the sole admitted one.
            if record.rtype == DNS_TYPE_TXT and len(packet_instances) < 2:
                packet_instances.add(name)

            admitted = self._add_record(record)
            if not admitted:
                continue
            if is_construction_record:
                has_lifx = True
            if record.rtype in (DNS_TYPE_A, DNS_TYPE_AAAA):
                packet_address_owners.add(name)

        # Address records are bounded candidates, not construction evidence.
        # They become LIFX activity only when a live SRV from an exact LIFX
        # instance explicitly links its target owner.
        linked_targets = {
            _normalise_dns_name(record.parsed_data.target)
            for instance in self.owners_for(DNS_TYPE_SRV)
            if _is_lifx_service_instance(instance)
            for record in self.records_for(instance, DNS_TYPE_SRV)
            if isinstance(record.parsed_data, SrvData)
        }
        if packet_address_owners & linked_targets:
            has_lifx = True

        # A packet advertising exactly one instance came from the device
        # itself (not an advertising proxy), so its source address can serve
        # as the device address if no A/AAAA record ever resolves.
        if len(packet_instances) == 1:
            instance = next(iter(packet_instances))
            if self.records_for(instance, DNS_TYPE_TXT):
                try:
                    validate_address(source_ip, emit_warnings=False)
                except ValueError:
                    self.count_rejection("invalid_address", "A")
                else:
                    fallback_ip = str(ipaddress.ip_address(source_ip))
                    self._setdefault(
                        self._fallback_ip_by_instance, instance, fallback_ip
                    )

        return has_lifx

    def resolve(self, *, allow_fallback: bool = True) -> list[_LifxServiceRecord]:
        """Return service records for instances that can now be resolved.

        Each instance is returned at most once across the lifetime of the
        cache. A live receive loop can defer packet-source fallback until
        collection ends so a later SRV and advertised address cannot be
        preempted by packet arrival order.
        """
        results: list[_LifxServiceRecord] = []
        if self._retained_payload_budget_exhausted:
            return results

        for instance in self.owners_for(DNS_TYPE_TXT):
            if not _is_lifx_service_instance(instance):
                continue
            if instance in self._resolved_instances:
                continue

            txt_metadata = self._resolve_txt_metadata(instance)
            if txt_metadata is None:
                continue
            serial, product_id, firmware, connectivity = txt_metadata

            if (instance, DNS_TYPE_SRV) in self._byte_incomplete_owner_types:
                continue

            # Get port from SRV record or use default
            srv_records = self.records_for(instance, DNS_TYPE_SRV)
            srv_endpoint = self._resolve_srv_endpoint(instance) if srv_records else None
            if srv_records and srv_endpoint is None:
                continue
            port = srv_endpoint[1] if srv_endpoint else 56700

            # Resolve the instance's SRV target hostname to an address. An
            # instance advertised without any SRV record falls back to the
            # source address of its own single-instance response packet. An
            # instance WITH an SRV record but no address records yet stays
            # pending — its target is reported by pending_targets() for a
            # follow-up query — because guessing the packet's source address
            # would misattribute devices advertised by a border router.
            ip: str | None = None
            addresses = frozenset[str]()
            if srv_endpoint is not None:
                target = srv_endpoint[0]
                addresses = self.addresses_for(target)
                ip = self.selected_address_for(target)
            elif allow_fallback:
                ip = self._fallback_ip_by_instance.get(instance)
            if ip is None:
                continue

            self._resolved_instances.add(instance)
            results.append(
                _LifxServiceRecord(
                    serial=serial,
                    ip=ip,
                    port=port,
                    product_id=product_id,
                    firmware=firmware or "",
                    connectivity=connectivity,
                    addresses=addresses,
                    service_instance=instance,
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
        if self._retained_payload_budget_exhausted:
            return targets

        for instance in self.owners_for(DNS_TYPE_TXT):
            if not _is_lifx_service_instance(instance):
                continue
            if instance in self._resolved_instances:
                continue
            if self._resolve_txt_metadata(instance) is None:
                continue
            if (instance, DNS_TYPE_SRV) in self._byte_incomplete_owner_types:
                continue
            srv_records = self.records_for(instance, DNS_TYPE_SRV)
            if not srv_records:
                continue
            srv_endpoint = self._resolve_srv_endpoint(instance)
            if srv_endpoint is None:
                continue
            target = srv_endpoint[0]
            if (
                self._address_budget_exhausted
                or target in self._address_overflowed_owners
                or (target, DNS_TYPE_A) in self._byte_incomplete_owner_types
                or (target, DNS_TYPE_AAAA) in self._byte_incomplete_owner_types
            ):
                continue
            if self.selected_address_for(target) is not None:
                continue
            targets.append(target)

        return targets


def _create_device_from_record(
    record: _LifxServiceRecord,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Light | None:
    """Create appropriate device class based on product ID from mDNS record.

    Uses the product registry to determine device capabilities and instantiate
    the correct device class (Light, MatrixLight, MultiZoneLight, etc.).

    Args:
        record: Internal mDNS service record
        timeout: Request timeout for the device
        max_retries: Maximum retry attempts for requests

    Returns:
        Device instance of the appropriate type, or None if device should be skipped
        (e.g., relay/button-only devices)

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
        "_emit_input_warnings": False,
    }

    # Priority-based selection matching DiscoveredDevice.create_device(). The
    # record address and port came from the wire and were validated above, so
    # caller-input advisories must not be emitted again by construction.
    device: Light | None
    if is_ceiling_product(record.product_id):
        device = CeilingLight(**kwargs)
    elif product.has_matrix:
        device = MatrixLight(**kwargs)
    elif product.has_multizone:
        device = MultiZoneLight(**kwargs)
    elif product.has_infrared:
        device = InfraredLight(**kwargs)
    elif product.has_hev:
        device = HevLight(**kwargs)
    elif product.has_relays or (product.has_buttons and not product.has_color):
        device = None
    else:
        device = Light(**kwargs)

    if device is not None:
        device._set_connectivity(record.connectivity)
    return device


async def _discover_lifx_services_sweep(
    record_cache: _LifxRecordCache,
    timeout: float = DISCOVERY_TIMEOUT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    failure_sink: _MdnsFailureSink | None = None,
) -> AsyncGenerator[_LifxServiceRecord, None]:
    """Run one mDNS discovery sweep using invocation-local cache state.

    Sends an mDNS PTR query for _lifx._udp.local and yields service records
    as devices respond. Records are deduplicated by serial number.

    This is the low-level API that provides raw mDNS data. For device instances,
    use discover_devices_mdns() instead.

    Args:
        timeout: Overall discovery timeout in seconds
        max_response_time: Maximum expected response time
        idle_timeout_multiplier: Multiplier for idle timeout

    Yields:
        Internal service record for each discovered device
    """
    seen_serials: set[str] = set()
    queried_targets: set[str] = set()
    query_attempts: dict[str, int] = {}
    start_time = time.monotonic()

    def new_records(*, allow_fallback: bool = False) -> list[_LifxServiceRecord]:
        """Resolve and serial-deduplicate records ready in this sweep."""
        records: list[_LifxServiceRecord] = []
        for record in record_cache.resolve(allow_fallback=allow_fallback):
            if record.serial in seen_serials:
                continue
            seen_serials.add(record.serial)
            found_log: dict[str, object] = {
                "class": "_discover_lifx_services",
                "method": "discover",
                "action": "device_found",
            }
            if failure_sink is None:
                found_log.update(
                    serial=record.serial,
                    ip=record.ip,
                    port=record.port,
                    product_id=record.product_id,
                )
            _LOGGER.debug(found_log)
            records.append(record)
        return records

    transport_context = MdnsTransport(log_failure_details=failure_sink is None)
    try:
        transport = await transport_context.__aenter__()
    except LifxNetworkError as error:
        if failure_sink is None:
            raise
        failure_sink(
            _MdnsSweepFailure(
                stage="open",
                reason="sweep_open_network",
                error_type=type(error).__name__,
            )
        )
        return
    try:
        # Build and send PTR query
        query = build_ptr_query(LIFX_MDNS_SERVICE)

        _LOGGER.debug(
            {
                "class": "_discover_lifx_services",
                "method": "discover",
                "action": "sending_query",
                "service": LIFX_MDNS_SERVICE,
                "timeout": timeout,
            }
        )

        try:
            await transport.send(query)
        except LifxNetworkError as error:
            if failure_sink is None:
                raise
            failure_sink(
                _MdnsSweepFailure(
                    stage="initial_send",
                    reason="sweep_send_network",
                    error_type=type(error).__name__,
                )
            )
            return

        # Per RFC 6762 §5.2, queriers should re-send their query to catch
        # responders whose (randomly delayed) answers were lost or deferred.
        # Responses are deduplicated by serial, so re-answers are harmless.
        retransmit_delays = [1.0, 3.0]

        idle_timeout = max_response_time * idle_timeout_multiplier
        deadline = IdleDeadline(timeout, idle_timeout)

        # Collect responses with dynamic timeout
        while True:
            now = time.monotonic()
            record_cache.expire(now)

            if deadline.idle_expired:
                _LOGGER.debug(
                    {
                        "class": "_discover_lifx_services",
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
                        "class": "_discover_lifx_services",
                        "method": "discover",
                        "action": "overall_timeout",
                        "elapsed": time.monotonic() - deadline._start,
                        "timeout": timeout,
                    }
                )
                break

            # Process every due clock cause in deterministic order: elapsed
            # goodbye expiry first, then a due query retransmission. Deadline
            # expiry always wins over initiating another send.
            elapsed = now - start_time
            if retransmit_delays and elapsed >= retransmit_delays[0]:
                retransmit_delays.pop(0)
                _LOGGER.debug(
                    {
                        "class": "_discover_lifx_services",
                        "method": "discover",
                        "action": "retransmitting_query",
                        "elapsed": elapsed,
                    }
                )
                try:
                    await transport.send(query)
                except LifxNetworkError as error:
                    if failure_sink is None:
                        raise
                    failure_sink(
                        _MdnsSweepFailure(
                            stage="retransmit_send",
                            reason="sweep_send_network",
                            error_type=type(error).__name__,
                        )
                    )
                    return

            ready_records = new_records()
            for record in ready_records:
                yield record
                deadline.mark_response()

            if ready_records:
                # The consumer may have suspended for an arbitrary duration.
                # Re-enter through the deadline and clock checks instead of
                # using timing values captured before the yield.
                continue

            now = time.monotonic()
            elapsed = now - start_time
            remaining = deadline.remaining()
            if remaining <= 0:
                break

            # Clock-only work may shorten this receive, but it never mutates
            # or extends the caller-owned IdleDeadline.
            if retransmit_delays:
                remaining = min(remaining, retransmit_delays[0] - elapsed)
            expiry_delay = record_cache.next_expiry_delay(now)
            if expiry_delay is not None:
                remaining = min(remaining, expiry_delay)

            try:
                data, addr = await transport.receive(timeout=max(remaining, 0.01))
            except LifxTimeoutError:
                if (
                    retransmit_delays
                    or record_cache.next_expiry_delay(time.monotonic()) is not None
                ):
                    # A scheduled retransmission or goodbye expiry still owns
                    # a wake-up inside the unchanged caller deadline.
                    continue
                # Clean end of collection — no more responses within the deadline
                break
            except LifxNetworkError as error:
                if failure_sink is not None:
                    failure_sink(
                        _MdnsSweepFailure(
                            stage="receive",
                            reason="sweep_receive_network",
                            error_type=type(error).__name__,
                        )
                    )
                else:
                    _LOGGER.warning(
                        {
                            "class": "_discover_lifx_services",
                            "action": "network_error",
                            "error": str(error),
                        }
                    )
                break
            except Exception as e:
                _LOGGER.error(
                    {
                        "class": "_discover_lifx_services",
                        "action": "unexpected_error",
                        "error": str(e),
                    },
                    exc_info=True,
                )
                raise

            try:
                response = parse_dns_response(data)
            except (ValueError, IndexError, struct.error):
                record_cache.count_rejection("malformed_packet", "PACKET")
                continue

            # Only process responses (not queries)
            if not response.header.is_response:
                continue

            # Merge every response packet into the cache: a packet
            # carrying only A/AAAA records may complete an instance whose
            # SRV/TXT arrived in an earlier packet. A packet may also
            # advertise multiple instances at once (e.g. a Thread border
            # router answering for its whole mesh).
            had_lifx = record_cache.add_packet(response.records, addr[0])
            extracted = new_records()

            if not had_lifx and not extracted:
                continue

            # Reset idle timer on every valid LIFX response, before the
            # dedup check - repeated mDNS re-announcements from one device
            # must not cause premature idle expiry while slower devices
            # have not yet answered (Pitfall 1 / D-04, mirroring
            # _discover_with_packet).
            deadline.mark_response()

            for record in extracted:
                yield record
                deadline.mark_response()

            if extracted and (deadline.idle_expired or deadline.overall_expired):
                continue

            # Query address records the responses did not include (a
            # single reply packet may not have room for every AAAA
            # record). Admission and retry limits bound traffic even
            # when sends fail persistently.
            for target in record_cache.pending_targets():
                if target in queried_targets:
                    continue

                attempts = query_attempts.get(target)
                if attempts is None:
                    if len(query_attempts) >= 64:
                        continue
                    attempts = 0
                if attempts >= 2:
                    continue

                query_attempts[target] = attempts + 1
                address_log: dict[str, object] = {
                    "class": "_discover_lifx_services",
                    "method": "discover",
                    "action": "querying_addresses",
                    "attempt": attempts + 1,
                }
                if failure_sink is None:
                    address_log["target"] = target
                _LOGGER.debug(address_log)
                try:
                    await transport.send(build_address_query(target))
                except LifxNetworkError as error:
                    if failure_sink is not None:
                        failure_sink(
                            _MdnsSweepFailure(
                                stage="address_followup",
                                reason="sweep_address_followup_network",
                                error_type=type(error).__name__,
                            )
                        )
                    else:
                        _LOGGER.debug(
                            {
                                "class": "_discover_lifx_services",
                                "method": "discover",
                                "action": "address_query_failed",
                                "target": target,
                                "attempt": attempts + 1,
                                "error": str(error),
                            }
                        )
                    continue
                queried_targets.add(target)

        # Packet-source fallback is a last resort. Waiting until collection
        # closes prevents a TXT-only packet from winning over a later SRV and
        # advertised A/AAAA response solely because it arrived first.
        for record in new_records(allow_fallback=True):
            yield record

        _LOGGER.debug(
            {
                "class": "_discover_lifx_services",
                "method": "discover",
                "action": "complete",
                "devices_found": len(seen_serials),
                "elapsed": time.monotonic() - start_time,
            }
        )
    finally:
        await transport_context.__aexit__(None, None, None)


async def _discover_lifx_services(
    timeout: float = DISCOVERY_TIMEOUT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    failure_sink: _MdnsFailureSink | None = None,
) -> AsyncGenerator[_LifxServiceRecord, None]:
    """Discover LIFX services and report one bounded rejection aggregate."""
    override = _current_mdns_service_source_override()
    if override is not None:
        source = override.source_factory()
        async with aclosing(source):
            async for record in source:
                yield record
        return

    record_cache = _LifxRecordCache()
    sweep = _discover_lifx_services_sweep(
        record_cache,
        timeout=timeout,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
        failure_sink=failure_sink,
    )
    try:
        async with aclosing(sweep):
            async for record in sweep:
                yield record
    finally:
        _LOGGER.debug(
            {
                "class": "_discover_lifx_services",
                "action": "rejection_summary",
                "rejections": [
                    {"reason": reason, "type": record_type, "count": count}
                    for (reason, record_type), count in sorted(
                        record_cache.rejection_counts.items()
                    )
                ],
            }
        )


def _parse_firmware_components(firmware: str) -> tuple[int | None, int | None]:
    """Parse an exact major.minor firmware pair without retaining raw text."""
    components = firmware.split(".")
    if len(components) != 2 or not all(
        component.isdecimal() for component in components
    ):
        return None, None
    return int(components[0]), int(components[1])


def _emit_candidate_failure(
    failure_sink: _MdnsFailureSink | None,
    *,
    stage: str,
    reason: str,
    error: BaseException,
) -> None:
    """Emit one value-suppressed candidate failure when requested."""
    if failure_sink is None:
        return
    failure_sink(
        _MdnsCandidateFailure(
            stage=stage,
            reason=reason,
            error_type=type(error).__name__,
        )
    )


async def _verify_mdns_candidate(
    record: _LifxServiceRecord,
    *,
    deadline: float,
    device_timeout: float,
    max_retries: int,
    failure_sink: _MdnsFailureSink | None = None,
) -> Device | None:
    """Verify one advertisement with a current correlated LIFX response."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        _emit_candidate_failure(
            failure_sink,
            stage="queue",
            reason="candidate_timeout",
            error=LifxTimeoutError(),
        )
        return None

    try:
        validate_address(record.ip, emit_warnings=False)
        validate_port(record.port)
    except ValueError:
        error = _MdnsCandidateResponseError()
        _emit_candidate_failure(
            failure_sink,
            stage="record",
            reason="candidate_response",
            error=error,
        )
        return None

    product = get_product(record.product_id)
    try:
        device_class = cast(
            type[Device],
            get_device_class_for_product(record.product_id, product),
        )
    except LifxUnsupportedDeviceError as error:
        _emit_candidate_failure(
            failure_sink,
            stage="classify",
            reason="candidate_unsupported",
            error=error,
        )
        return None

    connection = DeviceConnection(
        serial=record.serial,
        ip=record.ip,
        port=record.port,
        timeout=device_timeout,
        max_retries=max_retries,
    )
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LifxTimeoutError()
        request_timeout = min(device_timeout, remaining)

        if issubclass(device_class, Light):
            request: object = packets.Light.GetColor()
        else:
            request = packets.Device.EchoRequest(payload=_ECHO_LIVENESS_PAYLOAD)

        response = await asyncio.wait_for(
            connection.request(request, timeout=request_timeout),
            timeout=remaining,
        )

        if isinstance(response, packets.Device.StateUnhandled):
            raise LifxUnsupportedCommandError()
        if connection.serial != record.serial:
            raise _MdnsCandidateIdentityError()

        if issubclass(device_class, Light):
            if not isinstance(response, packets.Light.StateColor):
                raise _MdnsCandidateResponseError()
        elif not isinstance(response, packets.Device.EchoResponse) or (
            response.payload != _ECHO_LIVENESS_PAYLOAD
        ):
            raise _MdnsCandidateResponseError()

        device = device_class(
            serial=record.serial,
            ip=record.ip,
            port=record.port,
            timeout=device_timeout,
            max_retries=max_retries,
            _emit_input_warnings=False,
        )
        device._set_connectivity(record.connectivity)
        # The liveness probe already elicited a correlated response, so the
        # device's own report supersedes the advertised TXT sentinel without
        # the caller issuing a request of their own.
        device.connection._adopt_thread_connection(connection.thread_connection)
        if isinstance(device, Light):
            device._adopt_state_color(cast(packets.Light.StateColor, response))
        return device
    except (LifxTimeoutError, *TIMEOUT_ERRORS) as error:
        _emit_candidate_failure(
            failure_sink,
            stage="request",
            reason="candidate_timeout",
            error=error,
        )
    except (LifxConnectionError, LifxNetworkError) as error:
        _emit_candidate_failure(
            failure_sink,
            stage="request",
            reason="candidate_connect",
            error=error,
        )
    except LifxProtocolError as error:
        _emit_candidate_failure(
            failure_sink,
            stage="request",
            reason="candidate_protocol",
            error=error,
        )
    except LifxUnsupportedCommandError as error:
        _emit_candidate_failure(
            failure_sink,
            stage="request",
            reason="candidate_unsupported",
            error=error,
        )
    except _MdnsCandidateIdentityError as error:
        _emit_candidate_failure(
            failure_sink,
            stage="response",
            reason="candidate_identity",
            error=error,
        )
    except _MdnsCandidateResponseError as error:
        _emit_candidate_failure(
            failure_sink,
            stage="response",
            reason="candidate_response",
            error=error,
        )
    finally:
        await connection.close()
    return None


async def _discover_verified_devices_mdns(
    timeout: float = DISCOVERY_TIMEOUT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    failure_sink: _MdnsFailureSink | None = None,
    *,
    _deadline: float | None = None,
    _observer: _DiscoveryObserver | None = None,
) -> AsyncGenerator[Device, None]:
    """Yield only currently answering mDNS candidates under one deadline."""
    deadline = time.monotonic() + timeout if _deadline is None else _deadline
    observer = _current_discovery_observer() if _observer is None else _observer
    candidate_queue: asyncio.Queue[_LifxServiceRecord | None] = asyncio.Queue()
    result_queue: asyncio.Queue[tuple[str, object | None]] = asyncio.Queue()
    worker_count = max(1, _MAX_MDNS_LIVENESS_PROBES)
    deadline_reached = asyncio.Event()

    records = _discover_lifx_services(
        timeout=timeout,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
        failure_sink=failure_sink,
    )

    async def expire() -> None:
        """Stop queued verification at the invocation's original deadline."""
        await asyncio.sleep(max(0.0, deadline - time.monotonic()))
        deadline_reached.set()
        await result_queue.put(("deadline", None))

    async def produce() -> None:
        """Read one invocation-local record stream and queue candidates."""
        try:
            async with aclosing(records):
                async for record in records:
                    firmware_major, firmware_minor = _parse_firmware_components(
                        record.firmware
                    )
                    _emit_discovery_event(
                        observer,
                        source="mdns",
                        stage="accepted",
                        raw_identity=record.serial,
                        firmware_major=firmware_major,
                        firmware_minor=firmware_minor,
                        connectivity=record.connectivity,
                    )
                    await candidate_queue.put(record)
        except BaseException as error:
            await result_queue.put(("error", error))
        finally:
            for _ in range(worker_count):
                await candidate_queue.put(None)

    async def verify() -> None:
        """Verify queued records serially; the fixed pool owns the cap."""
        try:
            while True:
                record = await candidate_queue.get()
                if record is None:
                    return
                if deadline_reached.is_set():
                    return
                try:
                    device = await _verify_mdns_candidate(
                        record,
                        deadline=deadline,
                        device_timeout=device_timeout,
                        max_retries=max_retries,
                        failure_sink=failure_sink,
                    )
                except BaseException as error:
                    await result_queue.put(("error", error))
                    return
                if device is not None:
                    await result_queue.put(("device", device))
        finally:
            await result_queue.put(("worker_done", None))

    deadline_task = asyncio.create_task(expire())
    producer_task = asyncio.create_task(produce())
    worker_tasks = [asyncio.create_task(verify()) for _ in range(worker_count)]
    tasks = [deadline_task, producer_task, *worker_tasks]
    workers_done = 0
    try:
        while workers_done < worker_count:
            kind, value = await result_queue.get()
            if kind == "worker_done":
                workers_done += 1
            elif kind == "deadline":
                return
            elif kind == "error":
                assert isinstance(value, BaseException)
                raise value
            else:
                assert isinstance(value, Device)
                yield value
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


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
    records = _discover_lifx_services(
        timeout=timeout,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    )
    async with aclosing(records):
        async for record in records:
            if not _is_lifx_service_instance(record.service_instance):
                continue
            try:
                validate_address(record.ip, emit_warnings=False)
            except ValueError:
                continue

            device = _create_device_from_record(
                record,
                timeout=device_timeout,
                max_retries=max_retries,
            )

            if device is not None:
                yield device
