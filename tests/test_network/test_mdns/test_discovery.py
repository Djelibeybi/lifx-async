"""Tests for mDNS discovery functions."""

from __future__ import annotations

import asyncio
import ipaddress
import struct
from itertools import permutations
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

import lifx
import lifx.network.mdns as mdns
from lifx.devices.ceiling import CeilingLight
from lifx.devices.hev import HevLight
from lifx.devices.infrared import InfraredLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.exceptions import LifxNetworkError, LifxTimeoutError
from lifx.network.mdns.discovery import (
    _create_device_from_record,
    _discover_lifx_services_sweep,
    _LifxRecordCache,
)
from lifx.network.mdns.dns import (
    DnsResourceRecord,
    SrvData,
    TxtData,
    build_address_query,
)
from lifx.network.mdns.types import _LifxServiceRecord


def _txt(
    serial: str = "d073d5123456",
    product: str = "27",
    *,
    connectivity: str | None = None,
    firmware: str | None = "4.112",
    strings: list[str] | None = None,
) -> TxtData:
    if strings is None:
        pairs = {"id": serial, "p": product}
        if firmware is not None:
            pairs["fw"] = firmware
        if connectivity is not None:
            pairs["tm"] = connectivity
        strings = [
            f"{key}={value}" for key, value in pairs.items() if value or key == "tm"
        ]
    else:
        pairs = {}
        for string in strings:
            if "=" in string:
                key, _, value = string.partition("=")
                pairs[key] = value
    return TxtData(
        strings=strings,
        pairs=pairs,
    )


def _txt_record(
    instance: str,
    txt: TxtData | None = None,
    *,
    rclass: int = 1,
    ttl: int = 120,
) -> DnsResourceRecord:
    """Build a TXT RR whose raw identity matches its synthetic strings."""
    parsed = txt if txt is not None else _txt()
    rdata = b"".join(
        bytes([len(string.encode())]) + string.encode() for string in parsed.strings
    )
    return DnsResourceRecord(instance, 16, rclass, ttl, rdata, parsed)


def _srv_record(
    instance: str,
    *,
    target: str = "host.local",
    port: int = 56700,
    identity: bytes | None = None,
    rclass: int = 1,
    ttl: int = 120,
) -> DnsResourceRecord:
    """Build an SRV RR with a stable complete synthetic identity."""
    srv = SrvData(priority=0, weight=0, port=port, target=target)
    rdata = identity if identity is not None else f"{port}:{target.lower()}".encode()
    return DnsResourceRecord(instance, 33, rclass, ttl, rdata, srv)


def _address_record(
    host: str,
    address: str,
    *,
    rclass: int = 1,
    ttl: int = 120,
) -> DnsResourceRecord:
    """Build an A/AAAA RR using the canonical packed address as raw identity."""
    parsed = ipaddress.ip_address(address)
    rtype = 1 if parsed.version == 4 else 28
    return DnsResourceRecord(host, rtype, rclass, ttl, parsed.packed, str(parsed))


def _receive_script(*packets: tuple[bytes, tuple[str, int]]):
    """Build a receive() mock yielding the given packets, then timing out.

    Discovery may call receive() any number of times (query retransmissions
    keep the loop going), so exhaustible side-effect lists are not suitable.
    """
    queue = list(packets)

    async def receive(timeout: float = 5.0) -> tuple[bytes, tuple[str, int]]:
        if queue:
            return queue.pop(0)
        raise LifxTimeoutError("timeout")

    return receive


class TestMdnsPublicSurface:
    """Regression coverage for the deliberately narrow mDNS package API."""

    def test_raw_discovery_symbols_are_not_package_exports(self) -> None:
        """Raw records and generators stay private to their defining modules."""
        removed_names = ("LifxServiceRecord", "discover_lifx_services")
        private_names = ("_LifxServiceRecord", "_discover_lifx_services")

        for name in (*removed_names, *private_names):
            assert name not in lifx.__all__
            assert not hasattr(lifx, name)
            assert name not in mdns.__all__
            assert not hasattr(mdns, name)

    def test_record_to_device_factory_is_not_exported(self) -> None:
        """The private record's conversion helper is private with it."""
        assert "create_device_from_record" not in mdns.__all__
        assert not hasattr(mdns, "create_device_from_record")
        assert "_create_device_from_record" not in mdns.__all__
        assert not hasattr(mdns, "_create_device_from_record")


class TestLifxRecordCache:
    """Tests for the _LifxRecordCache mDNS record accumulator."""

    def test_complete_unrelated_service_chain_is_rejected_at_every_boundary(
        self,
    ) -> None:
        """A complete non-LIFX service is never treated as LIFX activity."""
        instance = "printer._ipp._tcp.local"
        cache = _LifxRecordCache()

        assert (
            cache.add_packet(
                [
                    _txt_record(instance),
                    _srv_record(instance, target="printer-host.local"),
                    _address_record("printer-host.local", "192.0.2.40"),
                ],
                "192.0.2.41",
            )
            is False
        )
        assert cache.pending_targets() == []
        assert cache.resolve() == []

    @pytest.mark.parametrize(
        "instance",
        [
            "_lifx._udp.local",
            "prefix_lifx._udp.local",
            "device._lifx._udp.local.extra",
            "device._lifx._udp.local.extra.",
        ],
    )
    def test_lifx_lookalike_suffixes_are_rejected(self, instance: str) -> None:
        """Only an instance immediately beneath the exact service is eligible."""
        cache = _LifxRecordCache()

        assert cache.add_packet([_txt_record(instance)], "192.0.2.42") is False
        assert cache.pending_targets() == []
        assert cache.resolve() == []

    def test_unrelated_records_in_mixed_packet_do_not_gain_lifx_provenance(
        self,
    ) -> None:
        """One valid instance cannot confer eligibility on packet neighbours."""
        lifx_instance = "lamp._lifx._udp.local"
        unrelated_instance = "printer._ipp._tcp.local"
        cache = _LifxRecordCache()

        assert cache.add_packet(
            [
                _txt_record(lifx_instance),
                _srv_record(lifx_instance, target="lamp-host.local"),
                _address_record("lamp-host.local", "192.0.2.43"),
                _txt_record(
                    unrelated_instance,
                    _txt(serial="d073d5aabbcd"),
                ),
                _srv_record(unrelated_instance, target="printer-host.local"),
                _address_record("printer-host.local", "192.0.2.44"),
            ],
            "192.0.2.45",
        )

        records = cache.resolve()
        assert [(record.serial, record.ip) for record in records] == [
            ("d073d5123456", "192.0.2.43")
        ]
        assert records[0].service_instance == lifx_instance
        assert cache.pending_targets() == []

    def test_resolve_with_all_records(self) -> None:
        """Test resolution with TXT, SRV, and A records in one packet."""
        srv_data = SrvData(priority=0, weight=0, port=56700, target="host.local")

        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", _txt()),
            DnsResourceRecord("test._lifx._udp.local", 33, 1, 120, b"", srv_data),
            DnsResourceRecord("host.local", 1, 1, 120, b"", "192.168.1.100"),
        ]

        cache = _LifxRecordCache()
        assert cache.add_packet(records, "192.168.1.50") is True
        results = cache.resolve()

        assert len(results) == 1
        result = results[0]
        assert result.serial == "d073d5123456"
        assert result.ip == "192.168.1.100"  # From A record
        assert result.port == 56700  # From SRV record
        assert result.product_id == 27
        assert result.firmware == "4.112"

    def test_resolve_with_txt_only(self) -> None:
        """Test resolution falls back to source IP with only a TXT record."""
        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", _txt()),
        ]

        cache = _LifxRecordCache()
        cache.add_packet(records, "192.168.1.50")
        results = cache.resolve()

        assert len(results) == 1
        assert results[0].serial == "d073d5123456"
        assert results[0].ip == "192.168.1.50"  # From source IP
        assert results[0].port == 56700  # Default

    def test_refused_second_txt_instance_blocks_packet_source_fallback(self) -> None:
        """Every advertised instance participates in the proxy-packet guard."""
        first = "first._lifx._udp.local"
        second = "second._lifx._udp.local"
        cache = _LifxRecordCache()

        cache.add_packet(
            [
                _txt_record(first),
                _txt_record(
                    second,
                    _txt(serial="d073d5123457"),
                    ttl=0,
                ),
            ],
            "192.0.2.254",
        )

        assert cache.resolve() == []

    def test_resolve_missing_serial(self) -> None:
        """Test resolution fails without serial."""
        txt_data = TxtData(strings=["p=27"], pairs={"p": "27"})
        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", txt_data),
        ]

        cache = _LifxRecordCache()
        cache.add_packet(records, "192.168.1.50")

        assert cache.resolve() == []

    def test_resolve_missing_product_id(self) -> None:
        """Test resolution fails without product ID."""
        txt_data = TxtData(strings=["id=d073d5123456"], pairs={"id": "d073d5123456"})
        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", txt_data),
        ]

        cache = _LifxRecordCache()
        cache.add_packet(records, "192.168.1.50")

        assert cache.resolve() == []

    def test_resolve_invalid_product_id(self) -> None:
        """Test resolution fails with non-numeric product ID."""
        records = [
            DnsResourceRecord(
                "test._lifx._udp.local", 16, 1, 120, b"", _txt(product="abc")
            ),
        ]

        cache = _LifxRecordCache()
        cache.add_packet(records, "192.168.1.50")

        assert cache.resolve() == []

    def test_resolve_no_txt_record(self) -> None:
        """Test resolution fails without TXT record."""
        srv_data = SrvData(priority=0, weight=0, port=56700, target="host.local")
        records = [
            DnsResourceRecord("test._lifx._udp.local", 33, 1, 120, b"", srv_data),
            DnsResourceRecord("host.local", 1, 1, 120, b"", "192.168.1.100"),
        ]

        cache = _LifxRecordCache()
        cache.add_packet(records, "192.168.1.50")

        assert cache.resolve() == []

    def test_resolve_serial_lowercase(self) -> None:
        """Test that serial is lowercased."""
        records = [
            DnsResourceRecord(
                "test._lifx._udp.local", 16, 1, 120, b"", _txt(serial="D073D5AABBCC")
            ),
        ]

        cache = _LifxRecordCache()
        cache.add_packet(records, "192.168.1.50")
        results = cache.resolve()

        assert len(results) == 1
        assert results[0].serial == "d073d5aabbcc"

    @pytest.mark.parametrize("serial", ["d073d5aabbcc", "D073D5AABBCC"])
    def test_txt_id_accepts_exact_unicast_hex_and_normalises_lowercase(
        self, serial: str
    ) -> None:
        """Only the exact broadcast-valid shape produces a serial."""
        cache = _LifxRecordCache()

        cache.add_packet(
            [_txt_record("valid._lifx._udp.local", _txt(serial=serial))],
            "192.0.2.10",
        )

        assert [record.serial for record in cache.resolve()] == ["d073d5aabbcc"]

    @pytest.mark.parametrize(
        "strings",
        [
            ["p=27"],
            ["id=", "p=27"],
            ["id=d0:73:d5:aa:bb:cc", "p=27"],
            ["id=d073d5aabbc", "p=27"],
            ["id=d073d5aabbccd", "p=27"],
            ["id=d073d5aabbcz", "p=27"],
            ["id=000000000000", "p=27"],
            ["id=ffffffffffff", "p=27"],
            ["id=d173d5aabbcc", "p=27"],
        ],
    )
    def test_invalid_txt_id_forms_are_rejected(self, strings: list[str]) -> None:
        """Malformed, broadcast, and group identities fail closed."""
        cache = _LifxRecordCache()

        cache.add_packet(
            [_txt_record("invalid._lifx._udp.local", _txt(strings=strings))],
            "192.0.2.10",
        )

        assert cache.resolve() == []

    @pytest.mark.parametrize(
        "txt_records",
        [
            [
                _txt_record(
                    "conflict._lifx._udp.local",
                    _txt(
                        strings=[
                            "id=d073d5aabbcc",
                            "id=d073d5aabbcd",
                            "p=27",
                        ]
                    ),
                )
            ],
            [
                _txt_record("conflict._lifx._udp.local", _txt(serial="d073d5aabbcc")),
                _txt_record("conflict._lifx._udp.local", _txt(serial="d073d5aabbcd")),
            ],
        ],
    )
    def test_conflicting_txt_ids_are_rejected_in_every_order(
        self, txt_records: list[DnsResourceRecord]
    ) -> None:
        """Neither raw-string last-wins nor RR arrival order selects an ID."""
        for ordered in (txt_records, list(reversed(txt_records))):
            cache = _LifxRecordCache()
            for record in ordered:
                cache.add_packet([record], "192.0.2.10")

            assert cache.resolve() == []

    def test_invalid_instance_does_not_block_later_valid_instance(self) -> None:
        """One malformed owner leaves the remainder of the sweep productive."""
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _txt_record(
                    "invalid._lifx._udp.local",
                    _txt(strings=["id=not-hex", "p=27"]),
                )
            ],
            "192.0.2.10",
        )
        cache.add_packet(
            [_txt_record("valid._lifx._udp.local", _txt(serial="d073d5aabbcc"))],
            "192.0.2.20",
        )

        records = cache.resolve()

        assert [(record.serial, record.ip) for record in records] == [
            ("d073d5aabbcc", "192.0.2.20")
        ]

    @pytest.mark.parametrize(
        "conflicting_strings",
        [
            ["id=d073d5aabbcc", "fw=4.112"],
            ["id=d073d5aabbcc", "p=invalid", "fw=4.112"],
            ["id=d073d5aabbcc", "p=1", "fw=4.112"],
            ["id=d073d5aabbcc", "p=27"],
            ["id=d073d5aabbcc", "p=27", "fw=0.1"],
            ["id=d073d5aabbcc", "p=27", "fw=4.112", "tm=2"],
        ],
    )
    def test_construction_metadata_conflict_is_unresolved_in_every_order(
        self, conflicting_strings: list[str]
    ) -> None:
        """Every live TXT construction candidate must reach one consensus."""
        instance = "construction._lifx._udp.local"
        genuine = _txt_record(instance, _txt(serial="d073d5aabbcc"))
        conflicting = _txt_record(instance, _txt(strings=conflicting_strings))

        for ordered in ((genuine, conflicting), (conflicting, genuine)):
            cache = _LifxRecordCache()
            for record in ordered:
                cache.add_packet([record], "192.0.2.10")

            assert cache.resolve() == []

    def test_construction_metadata_equivalent_txt_records_resolve(self) -> None:
        """Different raw TXT identities with one construction value are safe."""
        instance = "construction._lifx._udp.local"
        candidates = [
            _txt_record(instance, _txt(serial="d073d5aabbcc")),
            _txt_record(
                instance,
                _txt(
                    strings=[
                        "fw=4.112",
                        "p=27",
                        "id=D073D5AABBCC",
                        "tm=1",
                    ]
                ),
            ),
        ]

        for ordered in (candidates, list(reversed(candidates))):
            cache = _LifxRecordCache()
            for record in ordered:
                cache.add_packet([record], "192.0.2.10")

            resolved = cache.resolve()
            assert len(resolved) == 1
            assert resolved[0].serial == "d073d5aabbcc"
            assert resolved[0].product_id == 27
            assert resolved[0].firmware == "4.112"
            assert resolved[0].connectivity == "wifi"

    def test_txt_consensus_constructs_at_most_one_tuple_for_repeated_values(
        self,
    ) -> None:
        """Repeated effective values cannot multiply record construction."""
        instance = "consensus._lifx._udp.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _txt_record(
                    instance,
                    _txt(
                        strings=[
                            "id=d073d5aabbcc",
                            "id=D073D5AABBCC",
                            "p=27",
                            "p=27",
                            "fw=4.112",
                            "fw=4.112",
                            "tm=1",
                            "tm=not-thread",
                        ]
                    ),
                )
            ],
            "192.0.2.10",
        )

        with patch(
            "lifx.network.mdns.discovery._LifxServiceRecord",
            wraps=_LifxServiceRecord,
        ) as record_factory:
            resolved = cache.resolve()

        assert len(resolved) == 1
        assert record_factory.call_count == 1

    def test_txt_consensus_fails_on_second_effective_product_before_later_fields(
        self,
    ) -> None:
        """A product conflict stops consensus before optional-field work."""
        instance = "consensus._lifx._udp.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _txt_record(
                    instance,
                    _txt(
                        strings=[
                            "id=d073d5aabbcc",
                            "p=27",
                            "p=28",
                            "fw=4.112",
                            "tm=2",
                        ]
                    ),
                )
            ],
            "192.0.2.10",
        )

        with patch(
            "lifx.network.mdns.discovery._connectivity_from_txt",
            side_effect=AssertionError("later metadata was processed"),
        ):
            assert cache.resolve() == []

    @pytest.mark.parametrize(
        "strings",
        [
            [
                "id=d073d5aabbcc",
                "p=27",
                "fw=4.112",
                "fw=4.113",
                "tm=1",
            ],
            [
                "id=d073d5aabbcc",
                "p=27",
                "fw=4.112",
                "tm=1",
                "tm=2",
            ],
        ],
        ids=["firmware", "connectivity"],
    )
    def test_txt_consensus_fails_on_conflicting_firmware_or_connectivity(
        self, strings: list[str]
    ) -> None:
        """A second effective optional value prevents record construction."""
        instance = "consensus._lifx._udp.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [_txt_record(instance, _txt(strings=strings))],
            "192.0.2.10",
        )

        with patch(
            "lifx.network.mdns.discovery._LifxServiceRecord",
            wraps=_LifxServiceRecord,
        ) as record_factory:
            assert cache.resolve() == []

        record_factory.assert_not_called()

    def test_txt_consensus_ignores_exact_duplicates_and_malformed_optional_values(
        self,
    ) -> None:
        """Duplicate effective values and valueless optional keys are harmless."""
        instance = "consensus._lifx._udp.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _txt_record(
                    instance,
                    _txt(
                        strings=[
                            "id=d073d5aabbcc",
                            "id=d073d5aabbcc",
                            "p=27",
                            "p=27",
                            "fw=4.112",
                            "fw=4.112",
                            "fw",
                            "tm=1",
                            "tm=not-thread",
                            "tm",
                        ]
                    ),
                )
            ],
            "192.0.2.10",
        )

        resolved = cache.resolve()

        assert len(resolved) == 1
        assert resolved[0].firmware == "4.112"
        assert resolved[0].connectivity == "wifi"

    @pytest.mark.parametrize(
        "conflicting_srv",
        [
            _srv_record(
                "endpoint._lifx._udp.local",
                target="aaa-host.local",
                identity=b"a-target",
            ),
            _srv_record(
                "endpoint._lifx._udp.local",
                target="host.local",
                port=1,
                identity=b"a-port",
            ),
        ],
    )
    def test_srv_conflict_is_unresolved_in_every_order(
        self, conflicting_srv: DnsResourceRecord
    ) -> None:
        """No target or port conflict may become the effective endpoint."""
        instance = "endpoint._lifx._udp.local"
        genuine = _srv_record(
            instance, target="host.local", port=56700, identity=b"z-genuine"
        )
        addresses = [
            _address_record("host.local", "192.0.2.20"),
            _address_record("aaa-host.local", "192.0.2.30"),
        ]

        for ordered in ((genuine, conflicting_srv), (conflicting_srv, genuine)):
            cache = _LifxRecordCache()
            cache.add_packet(
                [_txt_record(instance), *ordered, *addresses], "192.0.2.10"
            )

            assert cache.resolve() == []

    def test_srv_construction_equivalent_records_resolve(self) -> None:
        """Distinct raw SRV identities with one endpoint remain resolvable."""
        instance = "endpoint._lifx._udp.local"
        srv_records = [
            _srv_record(instance, target="Host.Local", identity=b"a-equivalent"),
            _srv_record(instance, target="host.local", identity=b"z-equivalent"),
        ]

        for ordered in (srv_records, list(reversed(srv_records))):
            cache = _LifxRecordCache()
            cache.add_packet(
                [
                    _txt_record(instance),
                    *ordered,
                    _address_record("host.local", "192.0.2.20"),
                ],
                "192.0.2.10",
            )

            resolved = cache.resolve()
            assert len(resolved) == 1
            assert (resolved[0].ip, resolved[0].port) == ("192.0.2.20", 56700)

    def test_resolve_ipv6_aaaa_record(self) -> None:
        """Test resolution via AAAA record (Thread device)."""
        srv_data = SrvData(priority=0, weight=0, port=56700, target="host.local")
        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", _txt()),
            DnsResourceRecord("test._lifx._udp.local", 33, 1, 120, b"", srv_data),
            DnsResourceRecord("host.local", 28, 1, 120, b"", "fd00::1234"),
        ]

        cache = _LifxRecordCache()
        cache.add_packet(records, "192.168.1.50")
        results = cache.resolve()

        assert len(results) == 1
        assert results[0].ip == "fd00::1234"

    def test_resolve_prefers_routable_ipv6_over_link_local(self) -> None:
        """Test that a routable AAAA is preferred over a link-local one."""
        srv_data = SrvData(priority=0, weight=0, port=56700, target="host.local")
        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", _txt()),
            DnsResourceRecord("test._lifx._udp.local", 33, 1, 120, b"", srv_data),
            DnsResourceRecord("host.local", 28, 1, 120, b"", "fe80::1"),
            DnsResourceRecord("host.local", 28, 1, 120, b"", "fd00::1234"),
        ]

        cache = _LifxRecordCache()
        cache.add_packet(records, "192.168.1.50")
        results = cache.resolve()

        assert len(results) == 1
        assert results[0].ip == "fd00::1234"

    def test_resolve_prefers_ipv4_over_ipv6(self) -> None:
        """Test that an A record is preferred over AAAA records."""
        srv_data = SrvData(priority=0, weight=0, port=56700, target="host.local")
        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", _txt()),
            DnsResourceRecord("test._lifx._udp.local", 33, 1, 120, b"", srv_data),
            DnsResourceRecord("host.local", 28, 1, 120, b"", "fd00::1234"),
            DnsResourceRecord("host.local", 1, 1, 120, b"", "192.168.1.100"),
        ]

        cache = _LifxRecordCache()
        cache.add_packet(records, "192.168.1.50")
        results = cache.resolve()

        assert len(results) == 1
        assert results[0].ip == "192.168.1.100"

    def test_resolve_multi_instance_packet(self) -> None:
        """Test a single packet advertising multiple devices (border router)."""
        records = []
        for n in (1, 2):
            instance = f"bulb{n}._lifx._udp.local"
            host = f"host{n}.local"
            records.extend(
                [
                    DnsResourceRecord(
                        instance, 16, 1, 120, b"", _txt(serial=f"d073d500000{n}")
                    ),
                    DnsResourceRecord(
                        instance,
                        33,
                        1,
                        120,
                        b"",
                        SrvData(priority=0, weight=0, port=56700, target=host),
                    ),
                    DnsResourceRecord(host, 28, 1, 120, b"", f"fd00::{n}"),
                ]
            )

        cache = _LifxRecordCache()
        cache.add_packet(records, "192.168.1.1")
        results = {r.serial: r.ip for r in cache.resolve()}

        assert results == {
            "d073d5000001": "fd00::1",
            "d073d5000002": "fd00::2",
        }

    def test_multi_instance_unresolvable_not_misattributed(self) -> None:
        """An instance without address records must not get the proxy's IP."""
        records = []
        for n in (1, 2):
            instance = f"bulb{n}._lifx._udp.local"
            records.extend(
                [
                    DnsResourceRecord(
                        instance, 16, 1, 120, b"", _txt(serial=f"d073d500000{n}")
                    ),
                    DnsResourceRecord(
                        instance,
                        33,
                        1,
                        120,
                        b"",
                        SrvData(
                            priority=0, weight=0, port=56700, target=f"host{n}.local"
                        ),
                    ),
                ]
            )
        # Address record for instance 1 only
        records.append(DnsResourceRecord("host1.local", 28, 1, 120, b"", "fd00::1"))

        cache = _LifxRecordCache()
        cache.add_packet(records, "192.168.1.1")
        results = cache.resolve()

        assert [r.serial for r in results] == ["d073d5000001"]
        # The unresolved instance's target is reported for a follow-up query
        assert cache.pending_targets() == ["host2.local"]

    def test_resolve_across_packets(self) -> None:
        """Records split across packets are joined once the address arrives."""
        instance = "bulb2._lifx._udp.local"
        packet1 = [
            DnsResourceRecord(instance, 16, 1, 120, b"", _txt()),
            DnsResourceRecord(
                instance,
                33,
                1,
                120,
                b"",
                SrvData(priority=0, weight=0, port=56700, target="host2.local"),
            ),
        ]
        packet2 = [
            DnsResourceRecord("host2.local", 28, 1, 120, b"", "fd00::2"),
        ]

        cache = _LifxRecordCache()
        cache.add_packet(packet1, "192.0.2.1")
        assert cache.resolve() == []

        assert cache.add_packet(packet2, "192.0.2.1") is True
        results = cache.resolve()

        assert len(results) == 1
        assert results[0].ip == "fd00::2"

    def test_resolve_emits_each_instance_once(self) -> None:
        """A resolved instance is not returned again by later resolve calls."""
        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", _txt()),
        ]

        cache = _LifxRecordCache()
        cache.add_packet(records, "192.168.1.50")

        assert len(cache.resolve()) == 1
        assert cache.resolve() == []

    def test_split_record_permutations_retain_equal_address_membership(self) -> None:
        """Packet boundaries and arrival order cannot choose cache contents."""
        instance = "synthetic._lifx._udp.local"
        host = "synthetic-host.local"
        packets = (
            [_txt_record(instance)],
            [_srv_record(instance, target=host)],
            [
                _address_record(host, "192.0.2.20"),
                _address_record(host, "fd00::20"),
                _address_record(host, "2001:20::20"),
            ],
        )
        outcomes: set[tuple[str, frozenset[str], int]] = set()

        for packet_order in permutations(packets):
            cache = _LifxRecordCache()
            for packet in packet_order:
                cache.add_packet(packet, "192.0.2.10")
            emitted = cache.resolve()
            assert cache.resolve() == []
            outcomes.add((emitted[0].ip, emitted[0].addresses, len(emitted)))

        assert outcomes == {
            (
                "192.0.2.20",
                frozenset({"192.0.2.20", "fd00::20", "2001:20::20"}),
                1,
            )
        }

    def test_duplicate_replays_collapse_addresses_and_emission(self) -> None:
        """An identical live RR refresh is idempotent for output membership."""
        instance = "synthetic._lifx._udp.local"
        host = "synthetic-host.local"
        records = [
            _txt_record(instance),
            _srv_record(instance, target=host),
            _address_record(host, "192.0.2.20"),
            _address_record(host, "fd00::20"),
        ]
        cache = _LifxRecordCache()

        cache.add_packet(records + records, "192.0.2.10")
        first = cache.resolve()
        cache.add_packet(records, "192.0.2.10")

        assert len(first) == 1
        assert first[0].addresses == frozenset({"192.0.2.20", "fd00::20"})
        assert cache.resolve() == []

    @pytest.mark.parametrize(
        ("addresses", "expected"),
        [
            (
                ["fe80::20%en0", "2001:20::20", "fd00::20", "192.0.2.20"],
                "192.0.2.20",
            ),
            (["fe80::20%en0", "2001:20::20", "fd00::20"], "fd00::20"),
            (["fe80::20%en0", "2001:20::20"], "2001:20::20"),
            (["fe80::20%en0"], "fe80::20%en0"),
        ],
    )
    def test_address_selection_uses_the_locked_class_order(
        self, addresses: list[str], expected: str
    ) -> None:
        """IPv4, ULA, GUA, then scoped link-local is the class order."""
        instance = "synthetic._lifx._udp.local"
        host = "synthetic-host.local"
        cache = _LifxRecordCache()
        records = [_txt_record(instance), _srv_record(instance, target=host)]
        records.extend(_address_record(host, address) for address in addresses)

        cache.add_packet(records, "192.0.2.10")
        result = cache.resolve()

        assert len(result) == 1
        assert result[0].ip == expected
        assert result[0].addresses == frozenset(addresses)

    def test_unscoped_link_local_is_retained_but_not_selected(self) -> None:
        """A bare link-local is useful cache evidence but not a device route."""
        instance = "synthetic._lifx._udp.local"
        host = "synthetic-host.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _txt_record(instance),
                _srv_record(instance, target=host),
                _address_record(host, "fe80::20"),
            ],
            "192.0.2.10",
        )

        assert cache.resolve() == []
        assert cache.addresses_for(host) == frozenset({"fe80::20"})

    def test_pick_address_ignores_unspecified_ipv4_before_valid_ula(self) -> None:
        """An unspecified IPv4 candidate cannot outrank a usable ULA."""
        host = "synthetic-host.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _address_record(host, "0.0.0.0"),
                _address_record(host, "fd00::10"),
            ],
            "192.0.2.10",
        )

        assert cache.addresses_for(host) == frozenset({"0.0.0.0", "fd00::10"})
        assert cache.selected_address_for(host) == "fd00::10"

    def test_pick_address_ignores_ipv4_mapped_ipv6_before_valid_ula(self) -> None:
        """An IPv4-mapped IPv6 candidate cannot outrank a usable ULA."""
        host = "synthetic-host.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _address_record(host, "::ffff:192.0.2.10"),
                _address_record(host, "fd00::10"),
            ],
            "192.0.2.10",
        )

        assert cache.addresses_for(host) == frozenset({"::ffff:192.0.2.10", "fd00::10"})
        assert cache.selected_address_for(host) == "fd00::10"

    def test_pick_address_with_only_unusable_candidates_returns_none(self) -> None:
        """Unusable candidates stay cached without becoming a device route."""
        host = "synthetic-host.local"
        addresses = ["0.0.0.0", "::", "::ffff:192.0.2.10", "fe80::10"]
        cache = _LifxRecordCache()
        cache.add_packet(
            [_address_record(host, address) for address in addresses],
            "192.0.2.10",
        )

        assert cache.addresses_for(host) == frozenset(
            {"0.0.0.0", "::", "::ffff:192.0.2.10", "fe80::10"}
        )
        assert cache.selected_address_for(host) is None

    @pytest.mark.parametrize(
        ("addresses", "expected"),
        [
            (["192.0.2.20", "192.0.2.10", "fd00::10"], "192.0.2.10"),
            (["fd00::20", "fd00::10", "2001:20::10"], "fd00::10"),
            (["2001:db8::10", "fd00::10"], "fd00::10"),
            (["2001:20::20", "2001:20::10", "fe80::10%en0"], "2001:20::10"),
            (["fe80::20%en0", "fe80::10%en0"], "fe80::10%en0"),
        ],
    )
    def test_existing_address_priority_is_unchanged_for_usable_candidates(
        self, addresses: list[str], expected: str
    ) -> None:
        """Usable candidates keep class priority with lexical tie-breaking."""
        host = "synthetic-host.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [_address_record(host, address) for address in addresses],
            "192.0.2.10",
        )

        assert cache.selected_address_for(host) == expected

    def test_packet_source_fallback_is_not_an_advertised_address(self) -> None:
        """Single-instance fallback remains transport evidence only."""
        instance = "synthetic._lifx._udp.local"
        cache = _LifxRecordCache()

        cache.add_packet([_txt_record(instance)], "192.0.2.10")
        result = cache.resolve()

        assert len(result) == 1
        assert result[0].ip == "192.0.2.10"
        assert result[0].addresses == frozenset()


class TestLifxRecordCacheDefensiveBranches:
    """Cover defensive cache branches exposed by the phase patch gate."""

    @pytest.mark.parametrize("address", ["::", "::1", "::ffff:192.0.2.20"])
    def test_unroutable_ipv6_classes_are_retained_but_not_selected(
        self, address: str
    ) -> None:
        """Unspecified, loopback, and IPv4-mapped values cannot become routes."""
        cache = _LifxRecordCache()
        cache.add_packet(
            [_address_record("synthetic-host.local", address)], "192.0.2.10"
        )

        assert cache.addresses_for("synthetic-host.local") == frozenset({address})
        assert cache.selected_address_for("synthetic-host.local") is None

    @pytest.mark.parametrize("parsed_data", [None, "not-an-address"])
    def test_malformed_address_records_are_rejected(self, parsed_data: object) -> None:
        """Only parsed, syntactically valid address strings enter the cache."""
        cache = _LifxRecordCache()
        record = DnsResourceRecord(
            "synthetic-host.local", 1, 1, 120, b"synthetic", parsed_data
        )

        assert cache._add_record(record) is False
        assert cache.addresses_for("synthetic-host.local") == frozenset()

    def test_address_enumeration_ignores_corrupt_cached_payload(self) -> None:
        """A defensive read cannot expose a non-string cached address value."""
        host = "synthetic-host.local"
        cache = _LifxRecordCache()
        cache.add_packet([_address_record(host, "192.0.2.20")], "192.0.2.10")
        cache.records_for(host, 1)[0].parsed_data = object()

        assert cache.addresses_for(host) == frozenset()
        assert cache.selected_address_for(host) is None

    @pytest.mark.parametrize("missing_part", ["owner", "type", "identity"])
    def test_expiry_tolerates_already_removed_cache_state(
        self, missing_part: Literal["owner", "type", "identity"]
    ) -> None:
        """Stale expiry indexes remain harmless after defensive state removal."""
        host = "synthetic-host.local"
        cache = _LifxRecordCache()
        cache.add_packet([_address_record(host, "192.0.2.20")], "192.0.2.10")
        cached = cache.records_for(host, 1)[0]
        cache._pending_expiries[cached.identity] = 0.0

        if missing_part == "owner":
            cache._records_by_owner.pop(host)
        elif missing_part == "type":
            cache._records_by_owner[host].pop(1)
        else:
            cache._records_by_owner[host][1].pop(cached.identity)

        assert cache.expire(0.0) == 0
        assert cache.next_expiry_delay(0.0) is None

    @pytest.mark.parametrize(
        ("rtype", "parsed_data", "expected_rejection"),
        [
            (16, object(), ("malformed_packet", "TXT")),
            (33, object(), ("malformed_packet", "SRV")),
        ],
    )
    def test_malformed_cached_construction_records_are_rejected(
        self,
        rtype: int,
        parsed_data: object,
        expected_rejection: tuple[str, str],
    ) -> None:
        """Unexpected parsed payload types fail closed with bounded diagnostics."""
        instance = "synthetic._lifx._udp.local"
        cache = _LifxRecordCache()
        records = [
            DnsResourceRecord(instance, rtype, 1, 120, b"malformed", parsed_data)
        ]
        if rtype == 33:
            records.insert(0, _txt_record(instance))
        cache.add_packet(records, "192.0.2.10")

        assert cache.resolve() == []
        assert cache.rejection_counts == {expected_rejection: 1}

    def test_pending_targets_skip_conflicting_srv_endpoints(self) -> None:
        """A conflicted endpoint cannot produce a follow-up address query."""
        instance = "synthetic._lifx._udp.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _txt_record(instance),
                _srv_record(instance, target="first-host.local", identity=b"first"),
                _srv_record(instance, target="second-host.local", identity=b"second"),
            ],
            "192.0.2.10",
        )

        assert cache.pending_targets() == []

    def test_resolution_guards_reject_directly_cached_unrelated_owner(self) -> None:
        """Defence in depth excludes a non-LIFX owner from both consumers."""
        instance = "synthetic._unrelated._udp.local"
        cache = _LifxRecordCache()

        assert cache._add_record(_txt_record(instance)) is True

        assert cache.resolve() == []
        assert cache.pending_targets() == []


class TestPrivateCreateDeviceFromRecord:
    """Tests for _create_device_from_record function."""

    @staticmethod
    def _device_from_connectivity(connectivity: str | None) -> Light:
        """Resolve split records and construct their concrete device."""
        instance = "synthetic._lifx._udp.local"
        target = "synthetic-host.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                DnsResourceRecord(
                    instance,
                    16,
                    1,
                    120,
                    b"",
                    _txt(connectivity=connectivity),
                )
            ],
            "192.0.2.1",
        )
        cache.add_packet(
            [
                DnsResourceRecord(
                    instance,
                    33,
                    1,
                    120,
                    b"",
                    SrvData(priority=0, weight=0, port=56700, target=target),
                )
            ],
            "192.0.2.1",
        )
        cache.add_packet(
            [DnsResourceRecord(target, 1, 1, 120, b"", "192.0.2.10")],
            "192.0.2.1",
        )

        records = cache.resolve()
        assert len(records) == 1
        device = _create_device_from_record(records[0], timeout=7.5, max_retries=4)
        assert device is not None
        return device

    def test_traces_exact_thread_connectivity_from_split_records(self) -> None:
        """Exact private value 2 reaches the public device property."""
        device = self._device_from_connectivity("2")

        assert isinstance(device, Light)
        assert device.connectivity == "thread"

    @pytest.mark.parametrize(
        "connectivity",
        [None, "", "1", " 2", "02", "+2", "0", "3", "-2", "thread"],
    )
    def test_non_exact_thread_connectivity_defaults_to_wifi(
        self, connectivity: str | None
    ) -> None:
        """Every absent or non-exact private value maps to WiFi."""
        device = self._device_from_connectivity(connectivity)

        assert device.connectivity == "wifi"

    def test_connectivity_does_not_change_device_network_configuration(self) -> None:
        """Connectivity metadata remains descriptive and routing-neutral."""
        wifi_device = self._device_from_connectivity("1")
        thread_device = self._device_from_connectivity("2")

        assert type(thread_device) is type(wifi_device)
        assert thread_device.serial == wifi_device.serial
        assert thread_device.ip == wifi_device.ip
        assert thread_device.port == wifi_device.port
        assert thread_device.connection.timeout == wifi_device.connection.timeout
        assert (
            thread_device.connection.max_retries == wifi_device.connection.max_retries
        )
        assert thread_device.connectivity == "thread"
        assert wifi_device.connectivity == "wifi"

    @pytest.mark.parametrize(
        ("product_id", "expected_type"),
        [
            (27, Light),
            (29, InfraredLight),
            (90, HevLight),
            (31, MultiZoneLight),
            (55, MatrixLight),
            (176, CeilingLight),
        ],
    )
    @pytest.mark.parametrize("connectivity", ["wifi", "thread"])
    def test_device_class_lattice_preserves_connectivity(
        self,
        product_id: int,
        expected_type: type[Light],
        connectivity: Literal["wifi", "thread"],
    ) -> None:
        """Every supported class retains transport metadata after conversion."""
        record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.0.2.10",
            port=56700,
            product_id=product_id,
            firmware="4.112",
            connectivity=connectivity,
        )

        device = _create_device_from_record(record)

        assert device is not None
        assert type(device) is expected_type
        assert device.connectivity == connectivity

    def test_create_light_device(self) -> None:
        """Test creating a basic Light device."""
        record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=27,  # LIFX A19 - basic light
            firmware="4.112",
        )

        device = _create_device_from_record(record)

        assert device is not None
        assert isinstance(device, Light)
        assert device.serial == "d073d5123456"
        assert device.ip == "192.168.1.100"
        assert device.port == 56700

    def test_create_multizone_device(self) -> None:
        """Test creating a MultiZoneLight device."""
        record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=31,  # LIFX Z - multizone
            firmware="4.112",
        )

        device = _create_device_from_record(record)

        assert device is not None
        assert isinstance(device, MultiZoneLight)

    def test_create_matrix_device(self) -> None:
        """Test creating a MatrixLight device."""
        record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=55,  # LIFX Tile - matrix
            firmware="4.112",
        )

        device = _create_device_from_record(record)

        assert device is not None
        assert isinstance(device, MatrixLight)

    def test_create_ceiling_device(self) -> None:
        """Test creating a CeilingLight device."""
        record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=176,  # LIFX Ceiling US
            firmware="4.112",
        )

        device = _create_device_from_record(record)

        assert device is not None
        assert isinstance(device, CeilingLight)

    def test_create_infrared_device(self) -> None:
        """Test creating an InfraredLight device."""
        record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=29,  # LIFX+ A19 - has infrared
            firmware="4.112",
        )

        device = _create_device_from_record(record)

        assert device is not None
        assert isinstance(device, InfraredLight)

    def test_create_hev_device(self) -> None:
        """Test creating a HevLight device."""
        record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=90,  # LIFX Clean - has HEV
            firmware="4.112",
        )

        device = _create_device_from_record(record)

        assert device is not None
        assert isinstance(device, HevLight)

    def test_relay_device_returns_none(self) -> None:
        """Test that relay devices return None."""
        record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=70,  # LIFX Switch - relay only
            firmware="4.112",
        )

        device = _create_device_from_record(record)

        assert device is None

    def test_device_timeout_and_retries(self) -> None:
        """Test that timeout and retries are passed to device."""
        record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=27,
            firmware="4.112",
        )

        device = _create_device_from_record(record, timeout=30.0, max_retries=5)

        assert device is not None
        # Check that timeout/retries were passed to the connection
        assert device.connection.timeout == 30.0
        assert device.connection.max_retries == 5

    def test_bare_link_local_address_still_raises(self) -> None:
        """Direct construction keeps the shared link-local validation contract."""
        record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="fe80::1",
            port=56700,
            product_id=27,
            firmware="4.112",
        )

        with pytest.raises(ValueError, match="requires a zone identifier"):
            _create_device_from_record(record)


class TestPrivateLifxServiceRecord:
    """Tests for _LifxServiceRecord dataclass."""

    def test_hash_by_serial(self) -> None:
        """Test that records hash by serial."""
        record1 = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=27,
            firmware="4.112",
        )
        record2 = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.200",  # Different IP
            port=56701,  # Different port
            product_id=28,  # Different product
            firmware="4.113",  # Different firmware
        )

        assert hash(record1) == hash(record2)

    def test_equality_by_serial(self) -> None:
        """Test that records are equal by serial."""
        record1 = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=27,
            firmware="4.112",
        )
        record2 = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.200",
            port=56701,
            product_id=28,
            firmware="4.113",
        )
        record3 = _LifxServiceRecord(
            serial="d073d5654321",  # Different serial
            ip="192.168.1.100",
            port=56700,
            product_id=27,
            firmware="4.112",
        )

        assert record1 == record2
        assert record1 != record3

    def test_immutable(self) -> None:
        """Test that records are immutable (frozen dataclass)."""
        record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=27,
            firmware="4.112",
        )

        with pytest.raises(AttributeError):
            record.serial = "new_serial"  # type: ignore[misc]

    def test_equality_with_non_record(self) -> None:
        """Test that comparing to non-_LifxServiceRecord returns False."""
        record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=27,
            firmware="4.112",
        )

        # Comparison with different types should return False
        assert record != "d073d5123456"
        assert record != 123
        assert record != {"serial": "d073d5123456"}
        assert record != None  # noqa: E711


class TestDiscoverPrivateLifxServices:
    """Tests for _discover_lifx_services function."""

    @pytest.mark.asyncio
    async def test_discover_yields_records(self) -> None:
        """Test that discovery yields service records."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        # Create mock response data
        mock_response_data = b"\x00" * 100  # Synthetic response bytes

        # Create mock records
        txt_data = TxtData(
            strings=["id=d073d5123456", "p=27", "fw=4.112"],
            pairs={"id": "d073d5123456", "p": "27", "fw": "4.112"},
        )

        mock_parsed_response = MagicMock()
        mock_parsed_response.header.is_response = True
        mock_parsed_response.records = [
            DnsResourceRecord(
                "_lifx._udp.local",
                12,
                1,
                120,
                b"device._lifx._udp.local",
                "device._lifx._udp.local",
            ),
            _txt_record("device._lifx._udp.local", txt_data),
        ]

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            mock_transport.receive.side_effect = _receive_script(
                (mock_response_data, ("192.0.2.100", 5353)),
            )

            with patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse:
                mock_parse.return_value = mock_parsed_response

                records = []
                # This test exercises record assembly, not deadline precision. Leave
                # enough wall-clock headroom for a loaded full-suite event loop.
                async for record in _discover_lifx_services(timeout=1.0):
                    records.append(record)

                assert len(records) == 1
                assert records[0].serial == "d073d5123456"

    @pytest.mark.asyncio
    async def test_discover_idle_timeout(self) -> None:
        """Test that discovery stops on idle timeout."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            call_count = 0

            async def slow_receive(
                timeout: float = 5.0,
            ) -> tuple[bytes, tuple[str, int]]:
                nonlocal call_count
                call_count += 1
                # First call sleeps past the idle timeout, then raises LifxTimeoutError
                if call_count == 1:
                    await asyncio.sleep(0.02)
                    raise LifxTimeoutError("No data")
                raise LifxTimeoutError("timeout")

            mock_transport.receive.side_effect = slow_receive

            records = []
            # Use very short idle timeout
            async for record in _discover_lifx_services(
                timeout=5.0, max_response_time=0.01, idle_timeout_multiplier=1.0
            ):
                records.append(record)

            assert len(records) == 0

    @pytest.mark.asyncio
    async def test_discover_overall_timeout(self) -> None:
        """Test that discovery stops on overall timeout."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            # Keep returning data until timeout
            txt_data = TxtData(
                strings=["id=d073d5123456", "p=27"],
                pairs={"id": "d073d5123456", "p": "27"},
            )
            mock_parsed_response = MagicMock()
            mock_parsed_response.header.is_response = True
            mock_parsed_response.records = [
                MagicMock(rtype=12, name="_lifx._udp.local", parsed_data="dev"),
                MagicMock(rtype=16, parsed_data=txt_data),
            ]

            call_count = 0

            async def receive_with_delay(
                timeout: float = 5.0,
            ) -> tuple[bytes, tuple[str, int]]:
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.01)  # Small delay each time
                return (b"\x00" * 50, ("192.168.1.100", 5353))

            mock_transport.receive.side_effect = receive_with_delay

            with patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse:
                mock_parse.return_value = mock_parsed_response

                records = []
                # Very short overall timeout
                async for record in _discover_lifx_services(timeout=0.05):
                    records.append(record)

                # Should have discovered at most one device (deduplicated)
                assert len(records) <= 1

    @pytest.mark.asyncio
    async def test_discover_skips_non_response(self) -> None:
        """Test that discovery skips DNS queries (non-responses)."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        mock_query_response = MagicMock()
        mock_query_response.header.is_response = False  # This is a query, not response

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            mock_transport.receive.side_effect = _receive_script(
                (b"\x00" * 50, ("192.168.1.100", 5353)),
            )

            with patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse:
                mock_parse.return_value = mock_query_response

                records = []
                async for record in _discover_lifx_services(timeout=0.1):
                    records.append(record)

                # Should have no records since we skipped the query
                assert len(records) == 0

    @pytest.mark.asyncio
    async def test_discover_skips_non_lifx_response(self) -> None:
        """Test that discovery skips non-LIFX mDNS responses."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        # Response without LIFX PTR or TXT records
        mock_response = MagicMock()
        mock_response.header.is_response = True
        mock_response.records = [
            MagicMock(rtype=1, name="some.other.local", parsed_data="192.168.1.1"),
        ]

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            mock_transport.receive.side_effect = _receive_script(
                (b"\x00" * 50, ("192.168.1.100", 5353)),
            )

            with patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse:
                mock_parse.return_value = mock_response

                records = []
                async for record in _discover_lifx_services(timeout=0.1):
                    records.append(record)

                assert len(records) == 0

    @pytest.mark.asyncio
    async def test_discover_skips_invalid_record(self) -> None:
        """Test that discovery skips responses that can't be parsed as LIFX records."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        # Response with LIFX PTR but invalid TXT data (missing required fields)
        txt_data = TxtData(
            strings=["some=other"],
            pairs={"some": "other"},  # Missing 'id' and 'p'
        )
        mock_response = MagicMock()
        mock_response.header.is_response = True
        mock_response.records = [
            MagicMock(
                rtype=12, name="_lifx._udp.local", parsed_data="dev._lifx._udp.local"
            ),
            MagicMock(rtype=16, parsed_data=txt_data),
        ]

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            mock_transport.receive.side_effect = _receive_script(
                (b"\x00" * 50, ("192.168.1.100", 5353)),
            )

            with patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse:
                mock_parse.return_value = mock_response

                records = []
                async for record in _discover_lifx_services(timeout=0.1):
                    records.append(record)

                # Should be empty because the TXT record has no id/p fields
                assert len(records) == 0

    @pytest.mark.asyncio
    async def test_discover_handles_parse_error(self) -> None:
        """Test that discovery handles DNS parsing errors gracefully."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            mock_transport.receive.side_effect = _receive_script(
                (b"\x00" * 50, ("192.168.1.100", 5353)),
            )

            with patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse:
                # Parsing fails with an exception
                mock_parse.side_effect = ValueError("Invalid DNS data")

                records = []
                async for record in _discover_lifx_services(timeout=0.1):
                    records.append(record)

                # Should continue despite parse error
                assert len(records) == 0

    @pytest.mark.asyncio
    async def test_discover_with_lifx_txt_but_no_ptr(self) -> None:
        """Test discovery with LIFX TXT record but no PTR record."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        # Response with LIFX TXT but no PTR
        txt_data = TxtData(
            strings=["id=d073d5123456", "p=27", "fw=4.112"],
            pairs={"id": "d073d5123456", "p": "27", "fw": "4.112"},
        )
        mock_response = MagicMock()
        mock_response.header.is_response = True
        mock_response.records = [
            _txt_record("device._lifx._udp.local", txt_data),
        ]

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            mock_transport.receive.side_effect = _receive_script(
                (b"\x00" * 50, ("192.0.2.100", 5353)),
            )

            with patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse:
                mock_parse.return_value = mock_response

                records = []
                async for record in _discover_lifx_services(timeout=0.1):
                    records.append(record)

                # Should still discover via TXT record fallback
                assert len(records) == 1
                assert records[0].serial == "d073d5123456"

    @pytest.mark.asyncio
    async def test_discover_deduplicates_by_serial(self) -> None:
        """Test that discovery deduplicates by serial."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        txt_data = TxtData(
            strings=["id=d073d5123456", "p=27", "fw=4.112"],
            pairs={"id": "d073d5123456", "p": "27", "fw": "4.112"},
        )

        mock_parsed_response = MagicMock()
        mock_parsed_response.header.is_response = True
        mock_parsed_response.records = [
            DnsResourceRecord(
                "_lifx._udp.local",
                12,
                1,
                120,
                b"device._lifx._udp.local",
                "device._lifx._udp.local",
            ),
            _txt_record("device._lifx._udp.local", txt_data),
        ]

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            # Return same device twice, then timeout
            mock_transport.receive.side_effect = _receive_script(
                (b"\x00" * 100, ("192.0.2.100", 5353)),
                (b"\x00" * 100, ("192.0.2.100", 5353)),
            )

            with patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse:
                mock_parse.return_value = mock_parsed_response

                records = []
                async for record in _discover_lifx_services(timeout=0.1):
                    records.append(record)

                # Should only get one record despite two responses
                assert len(records) == 1

    @pytest.mark.asyncio
    async def test_duplicate_responses_reset_idle_deadline(self) -> None:
        """Duplicate announcements must reset the idle timer before dedup (D-04).

        mark_response() must be called for every valid LIFX response —
        including duplicates of an already-seen serial — so a re-announcement
        flood from one device cannot cause premature idle expiry while slower
        devices have not yet answered.
        """
        from lifx.network.mdns.discovery import _discover_lifx_services
        from lifx.network.utils import IdleDeadline

        txt_data = TxtData(
            strings=["id=d073d5123456", "p=27", "fw=4.112"],
            pairs={"id": "d073d5123456", "p": "27", "fw": "4.112"},
        )

        mock_parsed_response = MagicMock()
        mock_parsed_response.header.is_response = True
        mock_parsed_response.records = [
            DnsResourceRecord(
                "_lifx._udp.local",
                12,
                1,
                120,
                b"device._lifx._udp.local",
                "device._lifx._udp.local",
            ),
            _txt_record("device._lifx._udp.local", txt_data),
        ]

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            # Same device twice (duplicate), then timeout
            mock_transport.receive.side_effect = _receive_script(
                (b"\x00" * 100, ("192.0.2.100", 5353)),
                (b"\x00" * 100, ("192.0.2.100", 5353)),
            )

            with (
                patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse,
                patch.object(IdleDeadline, "mark_response", autospec=True) as mock_mark,
            ):
                mock_parse.return_value = mock_parsed_response

                records = []
                async for record in _discover_lifx_services(timeout=0.1):
                    records.append(record)

        # Dedup still yields one record, but BOTH valid responses must have
        # reset the idle deadline.
        assert len(records) == 1
        assert mock_mark.call_count == 2

    @pytest.mark.asyncio
    async def test_discover_network_error_does_not_propagate(self) -> None:
        """Test that LifxNetworkError breaks the loop without propagating (D-08)."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            mock_transport.receive.side_effect = LifxNetworkError("interface down")

            records = []
            # Must not raise — LifxNetworkError causes a clean break with a WARNING log
            async for record in _discover_lifx_services(timeout=0.1):
                records.append(record)

            assert len(records) == 0

    @pytest.mark.asyncio
    async def test_discover_unexpected_error_propagates(self) -> None:
        """Test that unexpected receive exceptions are logged and re-raised (D-08)."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            mock_transport.receive.side_effect = RuntimeError("unexpected socket state")

            with pytest.raises(RuntimeError, match="unexpected socket state"):
                async for _record in _discover_lifx_services(timeout=0.1):
                    pass


class TestMdnsRejectionDiagnostics:
    """One bounded rejection aggregate closes every discovery sweep."""

    @staticmethod
    def _response(records: list[DnsResourceRecord]) -> MagicMock:
        response = MagicMock()
        response.header.is_response = True
        response.records = records
        return response

    @staticmethod
    def _summaries(caplog) -> list[dict]:
        return [
            record.msg
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("action") == "rejection_summary"
        ]

    @pytest.mark.asyncio
    async def test_diagnostic_summary_is_emitted_once_when_empty(self, caplog) -> None:
        """Normal timeout finalises one stable zero-count event."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        transport = _fake_transport()
        transport.receive = AsyncMock(side_effect=LifxTimeoutError("timeout"))

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"),
        ):
            assert [
                record async for record in _discover_lifx_services(timeout=0.1)
            ] == []

        assert self._summaries(caplog) == [
            {
                "class": "_discover_lifx_services",
                "action": "rejection_summary",
                "rejections": [],
            }
        ]

    @pytest.mark.asyncio
    async def test_diagnostic_summary_is_ordered_and_privacy_safe(self, caplog) -> None:
        """Only fixed reason, type, and integer count scalars are retained."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        instance = "private-device._lifx._udp.local"
        invalid = _txt_record(
            instance,
            _txt(strings=["id=not-valid", "p=27"]),
            rclass=0x8001,
        )
        response = self._response([invalid])
        transport = _fake_transport()
        transport.receive = _receive_script((b"private-packet", ("192.0.2.44", 5353)))

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response", return_value=response
            ),
            caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"),
        ):
            assert [
                record async for record in _discover_lifx_services(timeout=0.1)
            ] == []

        summaries = self._summaries(caplog)
        assert len(summaries) == 1
        assert set(summaries[0]) == {"class", "action", "rejections"}
        assert summaries[0]["rejections"] == [
            {"reason": "invalid_txt_id", "type": "TXT", "count": 1},
            {"reason": "unexpected_cache_flush", "type": "TXT", "count": 1},
        ]
        assert all(
            set(entry) == {"reason", "type", "count"}
            and isinstance(entry["count"], int)
            for entry in summaries[0]["rejections"]
        )
        rendered = repr(summaries[0])
        for private_value in (
            "private-device",
            "192.0.2.44",
            "not-valid",
            "private-packet",
        ):
            assert private_value not in rendered

    @pytest.mark.asyncio
    async def test_cache_flush_is_counted_without_replacing_a_usable_rr(
        self, caplog
    ) -> None:
        """The legacy-unicast high class bit has no cache semantics."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        response = self._response(
            [_txt_record("device._lifx._udp.local", rclass=0x8001)]
        )
        transport = _fake_transport()
        transport.receive = _receive_script((b"packet", ("192.0.2.10", 5353)))

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response", return_value=response
            ),
            caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"),
        ):
            found = [record async for record in _discover_lifx_services(timeout=0.1)]

        assert [record.serial for record in found] == ["d073d5123456"]
        assert self._summaries(caplog)[0]["rejections"] == [
            {"reason": "unexpected_cache_flush", "type": "TXT", "count": 1}
        ]

    @pytest.mark.asyncio
    async def test_invalid_srv_port_does_not_abort_later_device(self, caplog) -> None:
        """One invalid endpoint is aggregated while unrelated discovery continues."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        invalid_instance = "invalid._lifx._udp.local"
        valid_instance = "valid._lifx._udp.local"
        invalid_response = self._response(
            [
                _txt_record(invalid_instance, _txt(serial="d073d5000001")),
                _srv_record(invalid_instance, target="invalid-host.local", port=53),
                _address_record("invalid-host.local", "192.0.2.1"),
            ]
        )
        valid_response = self._response(
            [
                _txt_record(valid_instance, _txt(serial="d073d5000002")),
                _srv_record(valid_instance, target="valid-host.local"),
                _address_record("valid-host.local", "192.0.2.2"),
            ]
        )
        transport = _fake_transport()
        transport.receive = _receive_script(
            (b"invalid", ("192.0.2.10", 5353)),
            (b"valid", ("192.0.2.20", 5353)),
        )

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response",
                side_effect=[invalid_response, valid_response],
            ),
            caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"),
        ):
            found = [record async for record in _discover_lifx_services(timeout=0.1)]

        assert [record.serial for record in found] == ["d073d5000002"]
        assert self._summaries(caplog)[0]["rejections"] == [
            {"reason": "invalid_port", "type": "SRV", "count": 1}
        ]

    @pytest.mark.parametrize(
        "error",
        [
            ValueError("invalid data"),
            IndexError("truncated data"),
            struct.error("short buffer"),
        ],
        ids=["value", "index", "struct"],
    )
    @pytest.mark.asyncio
    async def test_malformed_packet_uses_the_exact_recoverable_boundary(
        self, error: Exception, caplog
    ) -> None:
        """Parser wire failures aggregate without exception text or source."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        transport = _fake_transport()
        transport.receive = _receive_script((b"bad", ("192.0.2.10", 5353)))

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch("lifx.network.mdns.discovery.parse_dns_response", side_effect=error),
            caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"),
        ):
            assert [
                record async for record in _discover_lifx_services(timeout=0.1)
            ] == []

        assert self._summaries(caplog)[0]["rejections"] == [
            {"reason": "malformed_packet", "type": "PACKET", "count": 1}
        ]
        assert str(error) not in repr(self._summaries(caplog)[0])

    @pytest.mark.asyncio
    async def test_connectivity_fallback_has_no_diagnostic(self, caplog) -> None:
        """Non-2 private connectivity values are valid WiFi outcomes."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        response = self._response(
            [
                _txt_record(
                    "device._lifx._udp.local",
                    _txt(connectivity="not-thread"),
                )
            ]
        )
        transport = _fake_transport()
        transport.receive = _receive_script((b"packet", ("192.0.2.10", 5353)))

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response", return_value=response
            ),
            caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"),
        ):
            found = [record async for record in _discover_lifx_services(timeout=0.1)]

        assert found[0].connectivity == "wifi"
        assert self._summaries(caplog)[0]["rejections"] == []

    @pytest.mark.asyncio
    async def test_concurrent_diagnostic_summaries_are_isolated(self, caplog) -> None:
        """Two calls cannot share reason counts or cache-flush observations."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        invalid = self._response(
            [
                _txt_record(
                    "invalid._lifx._udp.local",
                    _txt(strings=["id=invalid", "p=27"]),
                )
            ]
        )
        flushed = self._response(
            [_txt_record("flushed._lifx._udp.local", rclass=0x8001)]
        )
        first = _fake_transport()
        first.receive = _receive_script((b"first", ("192.0.2.10", 5353)))
        second = _fake_transport()
        second.receive = _receive_script((b"second", ("192.0.2.20", 5353)))

        def parse(data: bytes) -> MagicMock:
            return invalid if data == b"first" else flushed

        async def collect() -> list[_LifxServiceRecord]:
            return [record async for record in _discover_lifx_services(timeout=0.1)]

        with (
            patch(
                "lifx.network.mdns.discovery.MdnsTransport",
                side_effect=[first, second],
            ),
            patch("lifx.network.mdns.discovery.parse_dns_response", side_effect=parse),
            caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"),
        ):
            results = await asyncio.gather(collect(), collect())

        assert [len(result) for result in results] == [0, 1]
        entries = [summary["rejections"] for summary in self._summaries(caplog)]
        assert entries == [
            [{"reason": "invalid_txt_id", "type": "TXT", "count": 1}],
            [{"reason": "unexpected_cache_flush", "type": "TXT", "count": 1}],
        ]

    @pytest.mark.asyncio
    async def test_early_generator_close_emits_summary_once(self, caplog) -> None:
        """GeneratorExit runs the synchronous final summary path."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        response = self._response([_txt_record("device._lifx._udp.local")])
        transport = _fake_transport()
        transport.receive = _receive_script((b"packet", ("192.0.2.10", 5353)))

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response", return_value=response
            ),
            caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"),
        ):
            generator = _discover_lifx_services(timeout=0.1)
            await anext(generator)
            await generator.aclose()

        assert len(self._summaries(caplog)) == 1

    @pytest.mark.asyncio
    async def test_unexpected_cache_failure_propagates_after_summary(
        self, caplog
    ) -> None:
        """Implementation defects are never relabelled as malformed input."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        response = self._response([_txt_record("device._lifx._udp.local")])
        transport = _fake_transport()
        transport.receive = _receive_script((b"packet", ("192.0.2.10", 5353)))

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response", return_value=response
            ),
            patch.object(
                _LifxRecordCache,
                "add_packet",
                side_effect=RuntimeError("cache defect"),
            ),
            caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"),
            pytest.raises(RuntimeError, match="cache defect"),
        ):
            async for _record in _discover_lifx_services(timeout=0.1):
                pass

        assert len(self._summaries(caplog)) == 1
        assert self._summaries(caplog)[0]["rejections"] == []

    @pytest.mark.asyncio
    async def test_replayed_over_cap_identity_counts_each_observation(
        self, caplog
    ) -> None:
        """Rejected replay changes count magnitude, never key cardinality."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        instance = "device._lifx._udp.local"
        records = [
            _txt_record(instance, _txt(product=str(index + 1)))
            for index in range(_LifxRecordCache._MAX_TXT_RRS_PER_OWNER + 1)
        ]
        response = self._response([*records, records[-1]])
        transport = _fake_transport()
        transport.receive = _receive_script((b"packet", ("192.0.2.10", 5353)))

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response", return_value=response
            ),
            caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"),
        ):
            assert [
                record async for record in _discover_lifx_services(timeout=0.1)
            ] == []

        assert self._summaries(caplog)[0]["rejections"] == [
            {"reason": "rr_identity_limit", "type": "TXT", "count": 2}
        ]

    @pytest.mark.asyncio
    async def test_invalid_packet_source_fallback_is_aggregated(self, caplog) -> None:
        """A malformed fallback never reaches record or device construction."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        response = self._response([_txt_record("device._lifx._udp.local")])
        transport = _fake_transport()
        transport.receive = _receive_script((b"packet", ("not-an-address", 5353)))

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response", return_value=response
            ),
            caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"),
        ):
            assert [
                record async for record in _discover_lifx_services(timeout=0.1)
            ] == []

        assert self._summaries(caplog)[0]["rejections"] == [
            {"reason": "invalid_address", "type": "A", "count": 1}
        ]


class TestDiscoverDevicesMdns:
    """Tests for discover_devices_mdns function."""

    @pytest.mark.asyncio
    async def test_close_synchronously_finalises_service_discovery(self) -> None:
        """Closing device discovery closes its service-record delegate."""
        from lifx.network.mdns.discovery import discover_devices_mdns

        finalised = False
        record = _LifxServiceRecord(
            "d073d5123456",
            "192.0.2.10",
            56700,
            27,
            "4.112",
            service_instance="device._lifx._udp.local",
        )

        async def mock_generator():
            nonlocal finalised
            try:
                yield record
            finally:
                finalised = True

        with patch(
            "lifx.network.mdns.discovery._discover_lifx_services",
            return_value=mock_generator(),
        ):
            generator = discover_devices_mdns(timeout=0.1)
            device = await anext(generator)
            assert device.serial == record.serial
            await generator.aclose()

        assert finalised is True

    @pytest.mark.asyncio
    async def test_discover_yields_device_instances(self) -> None:
        """Test that discovery yields device instances."""
        from lifx.network.mdns.discovery import discover_devices_mdns

        # Create a mock service record
        mock_record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.0.2.100",
            port=56700,
            product_id=27,
            firmware="4.112",
            service_instance="device._lifx._udp.local",
        )

        with patch(
            "lifx.network.mdns.discovery._discover_lifx_services"
        ) as mock_discover:

            async def mock_generator():
                yield mock_record

            mock_discover.return_value = mock_generator()

            devices = []
            async for device in discover_devices_mdns(timeout=0.1):
                devices.append(device)

            assert len(devices) == 1
            assert isinstance(devices[0], Light)
            assert devices[0].serial == "d073d5123456"

    @pytest.mark.asyncio
    async def test_mixed_unusable_ipv4_and_valid_ula_yields_thread_device(
        self,
    ) -> None:
        """A valid ULA survives an earlier unspecified IPv4 advertisement."""
        from lifx.network.mdns.discovery import discover_devices_mdns

        instance = "device._lifx._udp.local"
        host = "synthetic-host.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _txt_record(instance, _txt(connectivity="2")),
                _srv_record(instance, target=host),
                _address_record(host, "0.0.0.0"),
                _address_record(host, "fd00::10"),
            ],
            "192.0.2.10",
        )
        records = cache.resolve()

        async def mock_generator():
            for record in records:
                yield record

        with patch(
            "lifx.network.mdns.discovery._discover_lifx_services",
            return_value=mock_generator(),
        ):
            devices = [device async for device in discover_devices_mdns(timeout=0.1)]

        assert len(devices) == 1
        assert devices[0].ip == "fd00::10"
        assert devices[0].connectivity == "thread"

    @pytest.mark.asyncio
    async def test_unusable_only_cache_yields_no_public_device(self) -> None:
        """An unusable-only address set cannot escape through public discovery."""
        from lifx.network.mdns.discovery import discover_devices_mdns

        instance = "device._lifx._udp.local"
        host = "synthetic-host.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _txt_record(instance),
                _srv_record(instance, target=host),
                _address_record(host, "0.0.0.0"),
                _address_record(host, "::"),
                _address_record(host, "::ffff:192.0.2.10"),
                _address_record(host, "fe80::10"),
            ],
            "192.0.2.10",
        )
        records = cache.resolve()

        async def mock_generator():
            for record in records:
                yield record

        with (
            patch(
                "lifx.network.mdns.discovery._discover_lifx_services",
                return_value=mock_generator(),
            ),
            patch(
                "lifx.network.mdns.discovery._create_device_from_record"
            ) as mock_create,
        ):
            devices = [device async for device in discover_devices_mdns(timeout=0.1)]

        assert records == []
        assert devices == []
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_discover_filters_relay_devices(self) -> None:
        """Test that relay devices are filtered out."""
        from lifx.network.mdns.discovery import discover_devices_mdns

        # Create a mock relay device record
        mock_record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.0.2.100",
            port=56700,
            product_id=70,  # LIFX Switch - relay only
            firmware="4.112",
            service_instance="device._lifx._udp.local",
        )

        with patch(
            "lifx.network.mdns.discovery._discover_lifx_services"
        ) as mock_discover:

            async def mock_generator():
                yield mock_record

            mock_discover.return_value = mock_generator()

            devices = []
            async for device in discover_devices_mdns(timeout=0.1):
                devices.append(device)

            # Relay device should be filtered out
            assert len(devices) == 0

    @pytest.mark.asyncio
    async def test_invalid_address_does_not_end_device_sweep(self, caplog) -> None:
        """A bare link-local record is skipped while later records are yielded."""
        from lifx.network.mdns.discovery import discover_devices_mdns

        records = (
            _LifxServiceRecord(
                "d073d5000001",
                "fe80::1",
                56700,
                27,
                "4.112",
                service_instance="device-1._lifx._udp.local",
            ),
            _LifxServiceRecord(
                "d073d5000002",
                "192.0.2.2",
                56700,
                27,
                "4.112",
                service_instance="device-2._lifx._udp.local",
            ),
        )

        async def mock_generator():
            for record in records:
                yield record

        with patch(
            "lifx.network.mdns.discovery._discover_lifx_services",
            return_value=mock_generator(),
        ):
            with caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"):
                devices = [
                    device async for device in discover_devices_mdns(timeout=0.1)
                ]

        assert [device.serial for device in devices] == ["d073d5000002"]
        assert not any(
            record.msg.get("action") == "invalid_address"
            for record in caplog.records
            if isinstance(record.msg, dict)
        )

    @pytest.mark.asyncio
    async def test_invalid_address_adjacent_to_relay_filters_both(self) -> None:
        """Invalid addresses do not interfere with normal relay filtering."""
        from lifx.network.mdns.discovery import discover_devices_mdns

        records = (
            _LifxServiceRecord(
                "d073d5000001",
                "fe80::1",
                56700,
                27,
                "4.112",
                service_instance="device-1._lifx._udp.local",
            ),
            _LifxServiceRecord(
                "d073d5000002",
                "192.0.2.2",
                56700,
                70,
                "4.112",
                service_instance="device-2._lifx._udp.local",
            ),
        )

        async def mock_generator():
            for record in records:
                yield record

        with patch(
            "lifx.network.mdns.discovery._discover_lifx_services",
            return_value=mock_generator(),
        ):
            devices = [device async for device in discover_devices_mdns(timeout=0.1)]

        assert devices == []

    @pytest.mark.asyncio
    async def test_constructor_value_error_propagates(self) -> None:
        """Only address-validation errors degrade; constructor defects propagate."""
        from lifx.network.mdns.discovery import discover_devices_mdns

        record = _LifxServiceRecord(
            "d073d5000001",
            "192.0.2.2",
            56700,
            27,
            "4.112",
            service_instance="device._lifx._udp.local",
        )

        async def mock_generator():
            yield record

        with (
            patch(
                "lifx.network.mdns.discovery._discover_lifx_services",
                return_value=mock_generator(),
            ),
            patch(
                "lifx.network.mdns.discovery._create_device_from_record",
                side_effect=ValueError("constructor defect"),
            ),
            pytest.raises(ValueError, match="constructor defect"),
        ):
            async for _device in discover_devices_mdns(timeout=0.1):
                pass

    @pytest.mark.asyncio
    async def test_exact_case_insensitive_lifx_instance_reaches_public_generator(
        self,
    ) -> None:
        """Mixed-case exact service provenance survives the complete boundary."""
        from lifx.network.mdns.discovery import discover_devices_mdns

        instance = "Synthetic._LiFx._UdP.LoCaL."
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _txt_record(instance),
                _srv_record(instance, target="synthetic-host.local"),
                _address_record("synthetic-host.local", "192.0.2.46"),
            ],
            "192.0.2.47",
        )
        records = cache.resolve()
        assert len(records) == 1

        async def mock_generator():
            yield records[0]

        with patch(
            "lifx.network.mdns.discovery._discover_lifx_services",
            return_value=mock_generator(),
        ):
            devices = [device async for device in discover_devices_mdns(timeout=0.1)]

        assert [(device.serial, device.ip) for device in devices] == [
            ("d073d5123456", "192.0.2.46")
        ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "service_instance",
        [None, "printer._ipp._tcp.local"],
    )
    async def test_public_generator_rejects_record_without_exact_service_provenance(
        self, service_instance: str | None
    ) -> None:
        """Forged or legacy private records cannot cross the public boundary."""
        from lifx.network.mdns.discovery import discover_devices_mdns

        record = _LifxServiceRecord(
            "d073d5000001",
            "192.0.2.48",
            56700,
            27,
            "4.112",
            service_instance=service_instance,
        )

        async def mock_generator():
            yield record

        with (
            patch(
                "lifx.network.mdns.discovery._discover_lifx_services",
                return_value=mock_generator(),
            ),
            patch(
                "lifx.network.mdns.discovery._create_device_from_record"
            ) as converter,
        ):
            devices = [device async for device in discover_devices_mdns(timeout=0.1)]

        assert devices == []
        converter.assert_not_called()


class TestMdnsRemainingNonPositiveGuard:
    """The defensive ``remaining() <= 0`` break terminates the mDNS loop cleanly."""

    @pytest.mark.asyncio
    async def test_remaining_nonpositive_breaks_before_receive(self) -> None:
        from lifx.network.mdns.discovery import _discover_lifx_services

        fake = MagicMock()
        fake.idle_expired = False
        fake.overall_expired = False
        fake.remaining.return_value = -1.0
        fake._start = 0.0
        fake._last_response = 0.0

        with (
            patch("lifx.network.mdns.discovery.IdleDeadline", return_value=fake),
            patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls,
        ):
            mock_transport = AsyncMock()
            mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
            mock_transport.__aexit__ = AsyncMock(return_value=False)
            mock_transport.send = AsyncMock()
            mock_transport.receive = AsyncMock()
            mock_transport_cls.return_value = mock_transport

            records = [r async for r in _discover_lifx_services(timeout=0.5)]

        assert records == []
        mock_transport.receive.assert_not_called()

    @pytest.mark.asyncio
    async def test_idle_expired_breaks_with_debug(self) -> None:
        """idle_expired True takes the idle-timeout break (covers the True side)."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        fake = MagicMock()
        fake.idle_expired = True
        fake._start = 0.0
        fake._last_response = 0.0

        with (
            patch("lifx.network.mdns.discovery.IdleDeadline", return_value=fake),
            patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls,
        ):
            mock_transport = AsyncMock()
            mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
            mock_transport.__aexit__ = AsyncMock(return_value=False)
            mock_transport.send = AsyncMock()
            mock_transport.receive = AsyncMock()
            mock_transport_cls.return_value = mock_transport

            records = [r async for r in _discover_lifx_services(timeout=0.5)]

        assert records == []
        mock_transport.receive.assert_not_called()


class TestLifxRecordCacheBounds:
    """The cache's tables are bounded against a multicast flood.

    Discovery holds every record it sees for the whole window, so an
    unbounded cache is a memory-growth lever for anything that can put
    packets on the local link. Each bound is asserted from both sides: the
    entry below the cap is kept, the one at it is refused.
    """

    def test_a_full_table_refuses_a_key_it_does_not_hold(self) -> None:
        """At _MAX_ENTRIES, a genuinely new owner is dropped."""
        cache = _LifxRecordCache()

        cache.add_packet(
            [
                _srv_record(f"bulb{n}._lifx._udp.local")
                for n in range(_LifxRecordCache._MAX_ENTRIES)
            ],
            "192.0.2.10",
        )
        assert len(cache._records_by_owner) == _LifxRecordCache._MAX_ENTRIES
        assert cache.records_for("bulb0._lifx._udp.local", 33)

        cache.add_packet(
            [_srv_record("overflow._lifx._udp.local")],
            "192.0.2.10",
        )

        assert len(cache._records_by_owner) == _LifxRecordCache._MAX_ENTRIES
        assert cache.records_for("overflow._lifx._udp.local", 33) == ()

    def test_address_owner_exhaustion_preserves_construction_capacity(self) -> None:
        """Unrelated address owners cannot consume every LIFX instance slot."""
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _address_record(f"junk-{n}.local", f"fd00::{n:x}")
                for n in range(_LifxRecordCache._MAX_ENTRIES)
            ],
            "192.0.2.1",
        )

        cache.add_packet(
            [_txt_record("genuine._lifx._udp.local")],
            "192.0.2.10",
        )

        assert [(record.serial, record.ip) for record in cache.resolve()] == [
            ("d073d5123456", "192.0.2.10")
        ]

    def test_construction_owner_exhaustion_is_reported(self) -> None:
        """A refused LIFX owner contributes to the bounded rejection summary."""
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _srv_record(f"bulb{n}._lifx._udp.local")
                for n in range(_LifxRecordCache._MAX_ENTRIES + 1)
            ],
            "192.0.2.10",
        )

        assert cache.rejection_counts == {("owner_capacity", "SRV"): 1}

    def test_a_full_table_still_updates_a_key_it_already_holds(self) -> None:
        """The bound must not freeze out a re-announcement from a known device.

        Once an owner is admitted, new RR identities for it remain eligible
        even when no additional owner can be admitted.
        """
        cache = _LifxRecordCache()

        cache.add_packet(
            [
                _srv_record(f"bulb{n}._lifx._udp.local")
                for n in range(_LifxRecordCache._MAX_ENTRIES)
            ],
            "192.0.2.10",
        )

        cache.add_packet(
            [_srv_record("bulb0._lifx._udp.local", target="moved.local", port=1234)],
            "192.0.2.10",
        )

        records = cache.records_for("bulb0._lifx._udp.local", 33)
        srv_values = [
            record.parsed_data
            for record in records
            if isinstance(record.parsed_data, SrvData)
        ]
        assert len(cache._records_by_owner) == _LifxRecordCache._MAX_ENTRIES
        assert {srv.port for srv in srv_values} == {56700, 1234}

    def test_a_repeated_aaaa_is_not_stored_twice_for_one_host(self) -> None:
        """Re-announcements must not grow a host's address list without end."""
        cache = _LifxRecordCache()
        record = _address_record("host.local", "fd00::1")

        cache.add_packet([record, record, record], "192.0.2.10")

        assert cache.addresses_for("host.local") == frozenset({"fd00::1"})
        assert len(cache.records_for("host.local", 28)) == 1

    def test_a_seventeenth_address_for_one_host_is_retained(self) -> None:
        """The owner bound never becomes an address-cardinality cap."""
        cache = _LifxRecordCache()

        cache.add_packet(
            [_address_record("host.local", f"fd00::{n:x}") for n in range(1, 18)],
            "192.0.2.10",
        )

        addrs = cache.addresses_for("host.local")
        assert len(addrs) == 17
        assert "fd00::10" in addrs
        assert "fd00::11" in addrs

    def test_aaaa_owner_limit_exhaustion_fails_closed_for_the_sweep(self) -> None:
        """An incomplete sweep cannot later select from retained addresses."""
        cache = _LifxRecordCache()

        cache.add_packet(
            [
                _address_record(f"host{n}.local", f"fd00::{n:x}")
                for n in range(_LifxRecordCache._MAX_ENTRIES)
            ],
            "192.0.2.1",
        )
        cache.add_packet(
            [
                _address_record("overflow.local", "fd00::ffff"),
                _address_record("host0.local", "fd00::abcd"),
            ],
            "192.0.2.1",
        )

        assert len(cache._records_by_owner) == _LifxRecordCache._MAX_ENTRIES
        assert cache.records_for("overflow.local", 28) == ()
        assert cache.addresses_for("host0.local") == frozenset({"fd00::"})
        assert cache.selected_address_for("host0.local") is None
        assert cache.rejection_counts == {("address_capacity", "AAAA"): 2}

    def test_fallback_addresses_are_bounded_by_the_instance_limit(self) -> None:
        """Single-instance replies cannot grow the fallback map past the cap."""
        cache = _LifxRecordCache()

        for n in range(_LifxRecordCache._MAX_ENTRIES + 1):
            instance = f"bulb{n}._lifx._udp.local"
            cache.add_packet(
                [
                    DnsResourceRecord(
                        instance,
                        16,
                        1,
                        120,
                        b"",
                        _txt(serial=f"d073{n:08x}"),
                    )
                ],
                "192.0.2.1",
            )

        overflow = f"bulb{_LifxRecordCache._MAX_ENTRIES}._lifx._udp.local"
        assert len(cache._fallback_ip_by_instance) == _LifxRecordCache._MAX_ENTRIES
        assert overflow not in cache._fallback_ip_by_instance

    def test_fallback_address_keeps_the_first_source_for_an_instance(self) -> None:
        """A re-announcement cannot replace the source first tied to an instance."""
        cache = _LifxRecordCache()
        record = DnsResourceRecord("bulb._lifx._udp.local", 16, 1, 120, b"", _txt())

        cache.add_packet([record], "192.0.2.1")
        cache.add_packet([record], "192.0.2.2")

        assert cache._fallback_ip_by_instance == {"bulb._lifx._udp.local": "192.0.2.1"}

    def test_duplicate_txt_records_keep_single_instance_fallback(self) -> None:
        """Duplicate TXT records still describe one fallback-eligible device."""
        cache = _LifxRecordCache()
        record = DnsResourceRecord("bulb._lifx._udp.local", 16, 1, 120, b"", _txt())

        cache.add_packet([record, record], "192.0.2.1")

        resolved = cache.resolve()
        assert len(resolved) == 1
        assert resolved[0].ip == "192.0.2.1"

    def test_full_fallback_map_rejects_an_admitted_txt_instance(self) -> None:
        """The fallback map retains its own cap if cache tables diverge."""
        cache = _LifxRecordCache()
        cache._fallback_ip_by_instance = {
            f"existing{n}._lifx._udp.local": "192.0.2.1"
            for n in range(_LifxRecordCache._MAX_ENTRIES)
        }
        instance = "new._lifx._udp.local"

        cache.add_packet(
            [DnsResourceRecord(instance, 16, 1, 120, b"", _txt())],
            "192.0.2.2",
        )

        assert cache.records_for(instance, 16)
        assert instance not in cache._fallback_ip_by_instance
        assert len(cache._fallback_ip_by_instance) == _LifxRecordCache._MAX_ENTRIES

    def test_resolved_instances_are_directly_bounded(self) -> None:
        """Resolution cannot exceed the distinct-owner admission bound."""
        cache = _LifxRecordCache()

        for n in range(_LifxRecordCache._MAX_ENTRIES + 1):
            instance = f"bulb{n}._lifx._udp.local"
            cache.add_packet(
                [_txt_record(instance, _txt(serial=f"d073{n:08x}"))],
                "192.0.2.1",
            )

        results = cache.resolve()
        overflow = f"bulb{_LifxRecordCache._MAX_ENTRIES}._lifx._udp.local"

        assert len(results) == _LifxRecordCache._MAX_ENTRIES
        assert len(cache._resolved_instances) == _LifxRecordCache._MAX_ENTRIES
        assert overflow not in cache._resolved_instances

    @pytest.mark.parametrize(
        ("rtype", "type_name", "limit_name"),
        [
            (16, "TXT", "_MAX_TXT_RRS_PER_OWNER"),
            (33, "SRV", "_MAX_SRV_RRS_PER_OWNER"),
        ],
    )
    def test_txt_and_srv_identity_limits_never_evict_first_admitted_records(
        self, rtype: int, type_name: str, limit_name: str
    ) -> None:
        """Each hostile identity after the ceiling is rejected and counted."""
        cache = _LifxRecordCache()
        instance = "synthetic._lifx._udp.local"
        limit = getattr(_LifxRecordCache, limit_name)
        if rtype == 16:
            records = [
                _txt_record(instance, _txt(product=str(index + 1)))
                for index in range(limit + 1)
            ]
        else:
            records = [
                _srv_record(
                    instance,
                    target=f"host-{index}.local",
                    identity=f"srv-{index}".encode(),
                )
                for index in range(limit + 1)
            ]

        cache.add_packet(records, "192.0.2.10")
        cache.add_packet([records[-1]], "192.0.2.10")

        retained = cache.records_for(instance, rtype)
        assert len(retained) == limit
        assert records[0].rdata in {record.rdata for record in retained}
        assert records[-1].rdata not in {record.rdata for record in retained}
        assert cache.rejection_counts == {("rr_identity_limit", type_name): 2}

    def test_refreshes_do_not_consume_identity_capacity_or_report_a_limit(self) -> None:
        """An exact admitted RR identity refreshes in place at the ceiling."""
        cache = _LifxRecordCache()
        instance = "synthetic._lifx._udp.local"
        records = [
            _txt_record(instance, _txt(product=str(index + 1)))
            for index in range(_LifxRecordCache._MAX_TXT_RRS_PER_OWNER)
        ]

        cache.add_packet(records, "192.0.2.10")
        cache.add_packet([records[0], records[0]], "192.0.2.10")

        assert len(cache.records_for(instance, 16)) == len(records)
        assert cache.rejection_counts == {}

    def test_address_owner_overflow_fails_closed_without_selecting_a_subset(
        self,
    ) -> None:
        """One owner cannot force selection from a truncated address set."""
        cache = _LifxRecordCache()
        instance = "synthetic._lifx._udp.local"
        records = [
            _address_record("host.local", f"fd00::{index:x}")
            for index in range(1, _LifxRecordCache._MAX_ADDRESS_RRS_PER_OWNER + 2)
        ]

        cache.add_packet(records, "192.0.2.10")
        cache.add_packet(
            [_txt_record(instance), _srv_record(instance, target="host.local")],
            "192.0.2.10",
        )
        with patch("lifx.network.mdns.discovery.time.monotonic", return_value=50.0):
            cache.add_packet(
                [_address_record("host.local", "fd00::1", ttl=0)],
                "192.0.2.10",
            )
        assert cache.expire(51.0) == 1
        cache.add_packet(
            [_address_record("host.local", "fd00::ffff")],
            "192.0.2.10",
        )

        assert len(cache.addresses_for("host.local")) == (
            _LifxRecordCache._MAX_ADDRESS_RRS_PER_OWNER - 1
        )
        assert cache.selected_address_for("host.local") is None
        assert cache.resolve() == []
        assert cache.pending_targets() == []
        assert cache.rejection_counts == {("address_capacity", "AAAA"): 2}

    def test_sweep_address_budget_cannot_be_bypassed_across_owners(self) -> None:
        """Unrelated owners share one hard address-record budget."""
        cache = _LifxRecordCache()
        per_owner = _LifxRecordCache._MAX_ADDRESS_RRS_PER_OWNER
        owner_count = _LifxRecordCache._MAX_ADDRESS_RRS_PER_SWEEP // per_owner

        for owner_index in range(owner_count):
            cache.add_packet(
                [
                    _address_record(
                        f"host-{owner_index}.local",
                        f"fd{owner_index:02x}::{address_index:x}",
                    )
                    for address_index in range(1, per_owner + 1)
                ],
                "192.0.2.10",
            )

        cache.add_packet(
            [_address_record("overflow.local", "fdff::1")],
            "192.0.2.10",
        )

        retained = sum(
            len(cache.records_for(owner, rtype))
            for owner in cache._records_by_owner
            for rtype in (1, 28)
        )
        assert retained == _LifxRecordCache._MAX_ADDRESS_RRS_PER_SWEEP
        assert cache.addresses_for("overflow.local") == frozenset()
        assert cache.selected_address_for("host-0.local") is None
        assert cache.rejection_counts == {("address_capacity", "AAAA"): 1}


class TestLifxRecordCacheByteBounds:
    """Retained variable payload has exact, lifetime-aware byte ceilings."""

    _RECORD_LIMIT = 4096
    _SWEEP_LIMIT = 262144

    @staticmethod
    def _srv_with_retained_cost(
        owner: str,
        cost: int,
        *,
        target: str = "host.example",
        marker: bytes = b"x",
        ttl: int = 120,
    ) -> DnsResourceRecord:
        """Build an SRV RR with the plan-defined exact retained byte cost."""
        raw_length = (
            cost
            - len(owner.casefold().encode())
            - 4
            - len(target.casefold().encode())
            - 6
        )
        assert raw_length >= len(marker)
        rdata = marker + (b"x" * (raw_length - len(marker)))
        return _srv_record(
            owner,
            target=target,
            identity=rdata,
            ttl=ttl,
        )

    @staticmethod
    def _txt_with_retained_cost(
        owner: str,
        cost: int,
    ) -> DnsResourceRecord:
        """Build a valid TXT RR with the plan-defined exact retained byte cost."""
        required = ("id=d073d5123456", "p=27")
        required_length = sum(len(value.encode()) for value in required)
        for filler_count in range(1, 32):
            string_count = len(required) + filler_count
            payload_bytes = cost - len(owner.casefold().encode()) - 4
            if (payload_bytes - string_count) % 2:
                continue
            total_string_length = (payload_bytes - string_count) // 2
            filler_length = total_string_length - required_length
            if filler_count <= filler_length <= filler_count * 255:
                lengths = [1] * filler_count
                for index in range(filler_count):
                    added = min(254, filler_length - sum(lengths))
                    lengths[index] += added
                strings = [*required, *("x" * length for length in lengths)]
                return _txt_record(owner, _txt(strings=list(strings)))
        raise AssertionError(f"cannot construct TXT retained cost {cost}")

    @pytest.mark.parametrize("record_type", ["TXT", "SRV"])
    def test_retained_payload_at_4096_byte_record_limit_is_accepted(
        self,
        record_type: str,
    ) -> None:
        """Valid TXT and SRV identities at the exact limit remain usable."""
        instance = "limit._lifx._udp.local"
        cache = _LifxRecordCache()
        if record_type == "TXT":
            record = self._txt_with_retained_cost(instance, self._RECORD_LIMIT)
            records = [record]
            expected_ip = "192.0.2.61"
        else:
            record = self._srv_with_retained_cost(instance, self._RECORD_LIMIT)
            records = [
                _txt_record(instance),
                record,
                _address_record("host.example", "192.0.2.60"),
            ]
            expected_ip = "192.0.2.60"

        cache.add_packet(records, "192.0.2.61")

        assert cache.records_for(instance, record.rtype)
        assert [(item.serial, item.ip) for item in cache.resolve()] == [
            ("d073d5123456", expected_ip)
        ]

    @pytest.mark.parametrize("record_type", ["TXT", "SRV"])
    def test_retained_payload_above_4096_byte_record_limit_fails_owner_closed(
        self,
        record_type: str,
    ) -> None:
        """One extra retained byte rejects either variable-payload identity."""
        instance = "over-limit._lifx._udp.local"
        cache = _LifxRecordCache()
        if record_type == "TXT":
            record = self._txt_with_retained_cost(instance, self._RECORD_LIMIT + 1)
            records = [record]
        else:
            record = self._srv_with_retained_cost(instance, self._RECORD_LIMIT + 1)
            records = [
                _txt_record(instance),
                record,
                _address_record("host.example", "192.0.2.62"),
            ]

        cache.add_packet(records, "192.0.2.63")

        assert cache.records_for(instance, record.rtype) == ()
        assert cache.resolve() == []
        assert cache.rejection_counts == {("record_byte_capacity", record_type): 1}

    def test_byte_incomplete_txt_owner_fails_resolution_closed(self) -> None:
        """A retained TXT followed by an oversized sibling stays unusable."""
        instance = "txt-over-limit._lifx._udp.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _txt_record(instance),
                self._txt_with_retained_cost(instance, self._RECORD_LIMIT + 1),
            ],
            "192.0.2.63",
        )

        assert cache.resolve() == []
        assert cache.rejection_counts == {("record_byte_capacity", "TXT"): 1}

    def test_byte_incomplete_srv_owner_fails_all_endpoint_consumers_closed(
        self,
    ) -> None:
        """An oversized SRV cannot resolve or trigger a follow-up query."""
        instance = "srv-over-limit._lifx._udp.local"
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                _txt_record(instance),
                self._srv_with_retained_cost(
                    instance,
                    self._RECORD_LIMIT + 1,
                ),
            ],
            "192.0.2.63",
        )

        assert cache._resolve_srv_endpoint(instance) is None
        assert cache.pending_targets() == []
        assert cache.rejection_counts == {("record_byte_capacity", "SRV"): 1}

    def test_sweep_retained_payload_at_262144_bytes_is_accepted(self) -> None:
        """Exactly 64 maximum-size records fill, but do not exceed, the sweep."""
        cache = _LifxRecordCache()

        for owner_index in range(4):
            owner = f"owner-{owner_index}._lifx._udp.local"
            cache.add_packet(
                [
                    self._srv_with_retained_cost(
                        owner,
                        self._RECORD_LIMIT,
                        marker=index.to_bytes(2, "big"),
                    )
                    for index in range(16)
                ],
                "192.0.2.64",
            )

        assert cache._retained_payload_bytes == self._SWEEP_LIMIT
        assert (
            sum(len(cache.records_for(owner, 33)) for owner in cache._records_by_owner)
            == 64
        )
        assert cache.rejection_counts == {}

    def test_sweep_retained_payload_above_262144_bytes_fails_sweep_closed(
        self,
    ) -> None:
        """The first over-limit RR disables construction without eviction."""
        cache = _LifxRecordCache()
        for owner_index in range(4):
            owner = f"owner-{owner_index}._lifx._udp.local"
            cache.add_packet(
                [
                    self._srv_with_retained_cost(
                        owner,
                        self._RECORD_LIMIT,
                        marker=index.to_bytes(2, "big"),
                    )
                    for index in range(16)
                ],
                "192.0.2.65",
            )

        cache.add_packet(
            [_address_record("overflow.example", "192.0.2.66")],
            "192.0.2.67",
        )
        cache.add_packet(
            [_txt_record("later._lifx._udp.local")],
            "192.0.2.68",
        )

        assert cache._retained_payload_bytes == self._SWEEP_LIMIT
        assert cache.records_for("overflow.example", 1) == ()
        assert cache.records_for("later._lifx._udp.local", 16) == ()
        assert cache.resolve() == []
        assert cache.pending_targets() == []
        assert cache.rejection_counts == {
            ("sweep_byte_capacity", "A"): 1,
            ("sweep_byte_capacity", "TXT"): 1,
        }

    def test_duplicate_refresh_does_not_double_charge_retained_bytes(self) -> None:
        """Exact identity refreshes retain one stored cost."""
        instance = "refresh._lifx._udp.local"
        record = self._srv_with_retained_cost(instance, 1024)
        cache = _LifxRecordCache()

        cache.add_packet([record, record, record], "192.0.2.69")
        retained = cache._retained_payload_bytes
        cache.add_packet([record], "192.0.2.69")

        assert retained == 1024
        assert cache._retained_payload_bytes == retained
        assert len(cache.records_for(instance, 33)) == 1

    def test_positive_ttl_record_retains_charge_for_the_sweep(self) -> None:
        """Advertised TTL does not release positive records inside one sweep."""
        instance = "positive._lifx._udp.local"
        record = self._srv_with_retained_cost(instance, 1024, ttl=1)
        cache = _LifxRecordCache()

        cache.add_packet([record], "192.0.2.70")

        assert cache.expire(10000.0) == 0
        assert cache._retained_payload_bytes == 1024
        assert cache.records_for(instance, 33)

    def test_goodbye_grace_retains_charge_until_expire_removes_record(self) -> None:
        """TTL-zero grace keeps the charge until exact expiry removal."""
        instance = "goodbye._lifx._udp.local"
        record = self._srv_with_retained_cost(instance, 1024)
        goodbye = self._srv_with_retained_cost(instance, 1024, ttl=0)
        cache = _LifxRecordCache()

        with patch("lifx.network.mdns.discovery.time.monotonic", return_value=10.0):
            cache.add_packet([record, goodbye], "192.0.2.71")

        assert cache._retained_payload_bytes == 1024
        assert cache.expire(10.999) == 0
        assert cache._retained_payload_bytes == 1024
        assert cache.expire(11.0) == 1
        assert cache._retained_payload_bytes == 0
        assert cache.expire(12.0) == 0
        assert cache._retained_payload_bytes == 0

    def test_goodbye_expiry_detects_retained_payload_underflow(self) -> None:
        """Corrupt accounting raises instead of silently wrapping negative."""
        instance = "underflow._lifx._udp.local"
        record = self._srv_with_retained_cost(instance, 1024)
        goodbye = self._srv_with_retained_cost(instance, 1024, ttl=0)
        cache = _LifxRecordCache()

        with patch("lifx.network.mdns.discovery.time.monotonic", return_value=10.0):
            cache.add_packet([record, goodbye], "192.0.2.71")
        cache.records_for(instance, 33)[0].retained_payload_bytes += 1

        with pytest.raises(
            RuntimeError,
            match="mDNS retained-payload accounting underflow",
        ):
            cache.expire(11.0)

    def test_positive_reannouncement_rescues_goodbye_without_recharging(self) -> None:
        """An identical rescue clears expiry while preserving one exact charge."""
        instance = "rescue._lifx._udp.local"
        record = self._srv_with_retained_cost(instance, 1024)
        goodbye = self._srv_with_retained_cost(instance, 1024, ttl=0)
        cache = _LifxRecordCache()

        with patch("lifx.network.mdns.discovery.time.monotonic", return_value=20.0):
            cache.add_packet([record, goodbye, record], "192.0.2.72")

        assert cache._retained_payload_bytes == 1024
        assert cache.next_expiry_delay(20.0) is None
        assert cache.expire(21.0) == 0
        assert cache._retained_payload_bytes == 1024
        assert cache.records_for(instance, 33)

    def test_byte_limits_do_not_change_address_identity_limits(self) -> None:
        """D-15 count ceilings remain independent of retained-byte pressure."""
        owner_cache = _LifxRecordCache()
        owner_cache.add_packet(
            [
                _address_record("owner.example", f"fd00::{index:x}")
                for index in range(
                    1,
                    _LifxRecordCache._MAX_ADDRESS_RRS_PER_OWNER + 2,
                )
            ],
            "192.0.2.73",
        )

        sweep_cache = _LifxRecordCache()
        for owner_index in range(4):
            sweep_cache.add_packet(
                [
                    _address_record(
                        f"owner-{owner_index}.example",
                        f"fd{owner_index:02x}::{address_index:x}",
                    )
                    for address_index in range(
                        1,
                        _LifxRecordCache._MAX_ADDRESS_RRS_PER_OWNER + 1,
                    )
                ],
                "192.0.2.74",
            )
        sweep_cache.add_packet(
            [_address_record("overflow.example", "fdff::1")],
            "192.0.2.75",
        )

        assert _LifxRecordCache._MAX_ADDRESS_RRS_PER_OWNER == 256
        assert _LifxRecordCache._MAX_ADDRESS_RRS_PER_SWEEP == 1024
        assert len(owner_cache.addresses_for("owner.example")) == 256
        assert owner_cache.rejection_counts == {("address_capacity", "AAAA"): 1}
        assert sweep_cache._address_rr_count == 1024
        assert sweep_cache.rejection_counts == {("address_capacity", "AAAA"): 1}


class TestLifxRecordCacheGoodbyeExpiry:
    """RFC 6762 goodbye grace is exact, bounded, and rescueable."""

    @pytest.mark.parametrize(
        "record",
        [
            _txt_record("device._lifx._udp.local"),
            _srv_record("device._lifx._udp.local"),
            _address_record("host.local", "192.0.2.20"),
            _address_record("host.local", "fd00::20"),
        ],
        ids=["TXT", "SRV", "A", "AAAA"],
    )
    def test_goodbye_marks_only_an_identical_live_rr_for_one_second(
        self, record: DnsResourceRecord
    ) -> None:
        """TTL zero never creates state and schedules one exact live identity."""
        goodbye = DnsResourceRecord(
            record.name,
            record.rtype,
            record.rclass,
            0,
            record.rdata,
            record.parsed_data,
        )
        cache = _LifxRecordCache()

        with patch("lifx.network.mdns.discovery.time.monotonic", return_value=10.0):
            cache.add_packet([goodbye], "192.0.2.10")
            assert cache.records_for(record.name, record.rtype) == ()
            assert cache.next_expiry_delay(10.0) is None

            cache.add_packet([record], "192.0.2.10")
            cache.add_packet([goodbye], "192.0.2.10")

        cached = cache.records_for(record.name, record.rtype)
        assert len(cached) == 1
        assert cached[0].expires_at == 11.0
        assert cache.next_expiry_delay(10.25) == pytest.approx(0.75)
        assert cache.expire(10.999) == 0
        assert cache.expire(11.0) == 1
        assert cache.records_for(record.name, record.rtype) == ()
        assert cache.next_expiry_delay(11.0) is None

    def test_rescue_clears_only_the_identical_pending_goodbye(self) -> None:
        """A positive refresh rescues its identity without touching a sibling."""
        first = _address_record("host.local", "192.0.2.20")
        second = _address_record("host.local", "192.0.2.21")
        goodbye = _address_record("host.local", "192.0.2.20", ttl=0)
        cache = _LifxRecordCache()

        with patch("lifx.network.mdns.discovery.time.monotonic", return_value=4.0):
            cache.add_packet([first, second, goodbye], "192.0.2.10")
        assert cache.next_expiry_delay(4.5) == pytest.approx(0.5)

        cache.add_packet([first], "192.0.2.10")

        assert cache.next_expiry_delay(5.0) is None
        assert cache.expire(6.0) == 0
        assert cache.addresses_for("host.local") == frozenset(
            {"192.0.2.20", "192.0.2.21"}
        )

    @pytest.mark.parametrize(
        "conflicting",
        [
            _txt_record(
                "device._lifx._udp.local",
                _txt(serial="d073d5aabbcd"),
            ),
            _txt_record(
                "device._lifx._udp.local",
                _txt(product="28"),
            ),
            _txt_record(
                "device._lifx._udp.local",
                _txt(firmware="4.113"),
            ),
            _txt_record(
                "device._lifx._udp.local",
                _txt(connectivity="2"),
            ),
        ],
        ids=["serial", "product", "firmware", "connectivity"],
    )
    def test_txt_conflict_recovers_only_after_goodbye_expiry(
        self, conflicting: DnsResourceRecord
    ) -> None:
        """Live construction conflicts remain fail closed during grace."""
        instance = "device._lifx._udp.local"
        genuine = _txt_record(instance)
        goodbye = DnsResourceRecord(
            conflicting.name,
            conflicting.rtype,
            conflicting.rclass,
            0,
            conflicting.rdata,
            conflicting.parsed_data,
        )
        cache = _LifxRecordCache()

        with patch("lifx.network.mdns.discovery.time.monotonic", return_value=20.0):
            cache.add_packet([genuine, conflicting, goodbye], "192.0.2.10")

        assert cache.resolve() == []
        assert cache.expire(20.999) == 0
        assert cache.resolve() == []
        assert cache.expire(21.0) == 1
        assert [record.serial for record in cache.resolve()] == ["d073d5123456"]

    @pytest.mark.parametrize(
        "conflicting",
        [
            _srv_record(
                "device._lifx._udp.local",
                target="aaa-host.local",
                identity=b"a-target",
            ),
            _srv_record(
                "device._lifx._udp.local",
                port=1,
                identity=b"a-port",
            ),
        ],
        ids=["target", "port"],
    )
    def test_srv_conflict_recovers_only_after_goodbye_expiry(
        self, conflicting: DnsResourceRecord
    ) -> None:
        """Arrival and lexicographic order cannot choose a live endpoint."""
        instance = "device._lifx._udp.local"
        genuine = _srv_record(instance, identity=b"z-genuine")
        goodbye = DnsResourceRecord(
            conflicting.name,
            conflicting.rtype,
            conflicting.rclass,
            0,
            conflicting.rdata,
            conflicting.parsed_data,
        )
        cache = _LifxRecordCache()

        with patch("lifx.network.mdns.discovery.time.monotonic", return_value=30.0):
            cache.add_packet(
                [
                    _txt_record(instance),
                    genuine,
                    conflicting,
                    _address_record("host.local", "192.0.2.20"),
                    _address_record("aaa-host.local", "192.0.2.30"),
                    goodbye,
                ],
                "192.0.2.10",
            )

        assert cache.resolve() == []
        assert cache.expire(31.0) == 1
        resolved = cache.resolve()
        assert [(record.ip, record.port) for record in resolved] == [
            ("192.0.2.20", 56700)
        ]

    def test_goodbye_expiry_never_re_emits_an_already_resolved_instance(self) -> None:
        """The immutable generator result has no retraction or re-emission path."""
        instance = "device._lifx._udp.local"
        record = _txt_record(instance)
        cache = _LifxRecordCache()
        cache.add_packet([record], "192.0.2.10")
        assert len(cache.resolve()) == 1

        with patch("lifx.network.mdns.discovery.time.monotonic", return_value=40.0):
            cache.add_packet(
                [
                    DnsResourceRecord(
                        record.name,
                        record.rtype,
                        record.rclass,
                        0,
                        record.rdata,
                        record.parsed_data,
                    )
                ],
                "192.0.2.10",
            )
        assert cache.expire(41.0) == 1
        cache.add_packet([record], "192.0.2.10")

        assert cache.resolve() == []

    @pytest.mark.parametrize(
        ("rtype", "limit_name"),
        [(16, "_MAX_TXT_RRS_PER_OWNER"), (33, "_MAX_SRV_RRS_PER_OWNER")],
    )
    def test_expiry_releases_one_live_identity_slot(
        self, rtype: int, limit_name: str
    ) -> None:
        """A pending goodbye consumes capacity until its deadline fires."""
        instance = "device._lifx._udp.local"
        limit = getattr(_LifxRecordCache, limit_name)
        if rtype == 16:
            records = [
                _txt_record(instance, _txt(product=str(index + 1)))
                for index in range(limit + 1)
            ]
        else:
            records = [
                _srv_record(
                    instance,
                    target=f"host-{index}.local",
                    identity=f"srv-{index}".encode(),
                )
                for index in range(limit + 1)
            ]
        goodbye = DnsResourceRecord(
            records[0].name,
            records[0].rtype,
            records[0].rclass,
            0,
            records[0].rdata,
            records[0].parsed_data,
        )
        cache = _LifxRecordCache()

        with patch("lifx.network.mdns.discovery.time.monotonic", return_value=50.0):
            cache.add_packet([*records[:limit], goodbye], "192.0.2.10")
            cache.add_packet([records[-1]], "192.0.2.10")
        assert records[-1].rdata not in {
            item.rdata for item in cache.records_for(instance, rtype)
        }

        assert cache.expire(51.0) == 1
        cache.add_packet([records[-1]], "192.0.2.10")

        assert records[-1].rdata in {
            item.rdata for item in cache.records_for(instance, rtype)
        }

    def test_expiry_scheduler_indexes_only_pending_goodbyes(self) -> None:
        """Ordinary lossless address retention is outside timer traversal."""
        cache = _LifxRecordCache()
        addresses = [
            _address_record("host.local", f"fd00::{index:x}") for index in range(1, 257)
        ]
        goodbye = _address_record("host.local", "fd00::1", ttl=0)

        with patch("lifx.network.mdns.discovery.time.monotonic", return_value=60.0):
            cache.add_packet([*addresses, goodbye], "192.0.2.10")

        assert len(cache.addresses_for("host.local")) == 256
        assert len(cache._pending_expiries) == 1
        assert cache.next_expiry_delay(60.5) == pytest.approx(0.5)
        assert cache.expire(61.0) == 1
        assert len(cache.addresses_for("host.local")) == 255
        assert cache._pending_expiries == {}


class TestLifxRecordCachePendingTargets:
    """Which SRV targets still need a follow-up address query.

    A responder that answers for a whole Thread mesh can run out of room in
    one packet and send every instance's TXT and SRV records but only some of
    their AAAA records. Those instances are pending: their target hostname is
    known, its address is not.
    """

    @staticmethod
    def _instance_records(target: str = "host.local") -> list[DnsResourceRecord]:
        """TXT plus SRV for one instance, with no address record."""
        return [
            DnsResourceRecord("bulb._lifx._udp.local", 16, 1, 120, b"", _txt()),
            DnsResourceRecord(
                "bulb._lifx._udp.local",
                33,
                1,
                120,
                b"",
                SrvData(priority=0, weight=0, port=56700, target=target),
            ),
        ]

    def test_an_instance_missing_its_address_records_is_pending(self) -> None:
        """The case the follow-up query exists for."""
        cache = _LifxRecordCache()
        cache.add_packet(self._instance_records(), "192.168.1.50")

        assert cache.pending_targets() == ["host.local"]

    def test_an_instance_with_no_srv_record_is_not_pending(self) -> None:
        """Without an SRV record there is no hostname to ask about.

        Such an instance resolves from the source address of its own
        single-instance packet instead, so querying would be pointless.
        """
        cache = _LifxRecordCache()
        cache.add_packet(
            [DnsResourceRecord("bulb._lifx._udp.local", 16, 1, 120, b"", _txt())],
            "192.168.1.50",
        )

        assert cache.pending_targets() == []

    def test_an_instance_whose_target_address_is_known_is_not_pending(self) -> None:
        """An A record for the target answers the question already."""
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                *self._instance_records(),
                DnsResourceRecord("host.local", 1, 1, 120, b"", "192.168.1.100"),
            ],
            "192.168.1.50",
        )

        assert cache.pending_targets() == []

    def test_an_ipv6_only_target_is_not_pending_either(self) -> None:
        """A Thread device has an AAAA record and no A record at all."""
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                *self._instance_records(),
                DnsResourceRecord("host.local", 28, 1, 120, b"", "fd00::1"),
            ],
            "192.168.1.50",
        )

        assert cache.pending_targets() == []

    def test_an_instance_with_only_unusable_addresses_remains_pending(self) -> None:
        """Cached address evidence cannot suppress a query for a usable route."""
        cache = _LifxRecordCache()
        cache.add_packet(
            [
                *self._instance_records(),
                DnsResourceRecord("host.local", 28, 1, 120, b"", "fe80::20"),
            ],
            "192.168.1.50",
        )

        assert cache.addresses_for("host.local") == frozenset({"fe80::20"})
        assert cache.pending_targets() == ["host.local"]


def _fake_deadline() -> MagicMock:
    """An IdleDeadline stand-in that never expires on its own."""
    deadline = MagicMock()
    deadline.idle_expired = False
    deadline.overall_expired = False
    deadline.remaining.return_value = 5.0
    deadline._start = 0.0
    deadline._last_response = 0.0
    return deadline


def _fake_transport() -> AsyncMock:
    """An MdnsTransport stand-in usable as its own async context manager."""
    transport = AsyncMock()
    transport.__aenter__ = AsyncMock(return_value=transport)
    transport.__aexit__ = AsyncMock(return_value=False)
    transport.send = AsyncMock()
    return transport


class _FakeMonotonicClock:
    """Explicitly advanced monotonic clock for receive-loop timing tests."""

    def __init__(self, current: float = 0.0) -> None:
        self.current = current

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


class TestMdnsQueryRetransmission:
    """The PTR query is re-sent at its scheduled slots (RFC 6762 section 5.2).

    Responders delay their answers randomly, and those answers can be lost.
    Re-sending catches the ones that were missed; responses are deduplicated
    by serial, so the re-answers cost nothing. The clock is faked rather than
    waited out, since the first slot is a whole second away.
    """

    @pytest.mark.asyncio
    async def test_each_slot_re_sends_the_query_once(self) -> None:
        """Crossing both slots sends the query twice more, then stops."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        clock = MagicMock()
        # start_time, loop timing, freshly recomputed pre-receive timing, and
        # timeout handling. The loop readings at 1.5 and 4.0 cross the two
        # retransmission slots; the repeated values keep each local snapshot
        # internally consistent.
        clock.monotonic.side_effect = [0.0, 1.5, 3.5, 4.0, 4.0, 4.0, 4.0]

        transport = _fake_transport()
        transport.receive = AsyncMock(side_effect=LifxTimeoutError("timeout"))

        with (
            patch(
                "lifx.network.mdns.discovery.IdleDeadline",
                return_value=_fake_deadline(),
            ),
            patch("lifx.network.mdns.discovery.time", clock),
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
        ):
            records = [r async for r in _discover_lifx_services(timeout=5.0)]

        assert records == []
        # The initial query plus one re-send per slot.
        assert transport.send.await_count == 3

    @pytest.mark.asyncio
    async def test_a_timeout_with_slots_left_loops_instead_of_ending(self) -> None:
        """A receive timeout before the last slot is not the end of collection.

        The receive timeout is clamped to the next retransmission, so timing
        out means "the slot arrived", not "nothing more is coming". Ending
        there would drop every responder that had not yet answered.
        """
        from lifx.network.mdns.discovery import _discover_lifx_services

        clock = MagicMock()
        # Never reaches a slot, so the schedule stays non-empty and every
        # timeout has to loop rather than break.
        clock.monotonic.side_effect = [0.0] + [0.1] * 10

        deadline = _fake_deadline()
        # Expire on the third pass, so the loop can only end by the deadline.
        type(deadline).overall_expired = PropertyMock(side_effect=[False, False, True])

        transport = _fake_transport()
        transport.receive = AsyncMock(side_effect=LifxTimeoutError("timeout"))

        with (
            patch("lifx.network.mdns.discovery.IdleDeadline", return_value=deadline),
            patch("lifx.network.mdns.discovery.time", clock),
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
        ):
            records = [r async for r in _discover_lifx_services(timeout=5.0)]

        assert records == []
        assert transport.receive.await_count == 2
        # No slot was crossed, so the query was sent exactly once.
        assert transport.send.await_count == 1

    @pytest.mark.asyncio
    async def test_due_retransmit_is_not_sent_after_the_overall_deadline(self) -> None:
        """Deadline expiry wins over a retransmission that became overdue."""
        clock = _FakeMonotonicClock()
        deadline = _fake_deadline()
        deadline.overall_expired = True
        transport = _fake_transport()

        async def send(_data: bytes) -> None:
            clock.advance(1.1)

        transport.send.side_effect = send

        with (
            patch("lifx.network.mdns.discovery.time.monotonic", new=clock),
            patch("lifx.network.mdns.discovery.IdleDeadline", return_value=deadline),
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
        ):
            records = [
                record
                async for record in _discover_lifx_services_sweep(
                    _LifxRecordCache(), timeout=1.0
                )
            ]

        assert records == []
        assert transport.send.await_count == 1


class TestMdnsConsumerYieldTiming:
    """Consumer work is excluded from the mDNS idle receive window."""

    @staticmethod
    def _ready_cache() -> _LifxRecordCache:
        cache = _LifxRecordCache()
        instance = "ready._lifx._udp.local"
        cache.add_packet(
            [
                _txt_record(instance),
                _srv_record(instance, target="ready-host.local"),
                _address_record("ready-host.local", "192.0.2.20"),
            ],
            "192.0.2.10",
        )
        return cache

    @pytest.mark.asyncio
    async def test_resuming_after_a_yield_resets_the_idle_window(self) -> None:
        """A yielded record marks consumer resumption before collection continues."""
        deadline = _fake_deadline()
        transport = _fake_transport()
        transport.receive = AsyncMock(side_effect=LifxNetworkError("stop"))

        with (
            patch("lifx.network.mdns.discovery.IdleDeadline", return_value=deadline),
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
        ):
            records = [
                record
                async for record in _discover_lifx_services_sweep(
                    self._ready_cache(), timeout=10.0
                )
            ]

        assert len(records) == 1
        deadline.mark_response.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_receive_timeout_is_recomputed_after_consumer_resumes(self) -> None:
        """A pre-yield remaining value cannot bound a post-yield receive."""
        clock = _FakeMonotonicClock()
        transport = _fake_transport()
        receive_timeouts: list[float] = []

        async def receive(timeout: float) -> tuple[bytes, tuple[str, int]]:
            receive_timeouts.append(timeout)
            raise LifxTimeoutError("timeout")

        transport.receive = receive

        with (
            patch("lifx.network.mdns.discovery.time.monotonic", new=clock),
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
        ):
            generator = _discover_lifx_services_sweep(
                self._ready_cache(),
                timeout=10.0,
                max_response_time=2.0,
                idle_timeout_multiplier=2.0,
            )
            record = await anext(generator)
            clock.advance(3.5)
            with pytest.raises(StopAsyncIteration):
                await anext(generator)

        assert record.serial == "d073d5123456"
        assert receive_timeouts[-1] == pytest.approx(4.0)

    @pytest.mark.asyncio
    async def test_deadline_expiry_during_yield_blocks_address_follow_up(self) -> None:
        """Consumer delay cannot permit a follow-up send past the deadline."""
        ready_instance = "ready._lifx._udp.local"
        pending_instance = "pending._lifx._udp.local"
        response = MagicMock()
        response.header.is_response = True
        response.records = [
            _txt_record(ready_instance),
            _srv_record(ready_instance, target="ready-host.local"),
            _address_record("ready-host.local", "192.0.2.20"),
            _txt_record(pending_instance, _txt(serial="d073d5123457")),
            _srv_record(pending_instance, target="pending-host.local"),
        ]
        deadline = _fake_deadline()
        transport = _fake_transport()
        transport.receive = _receive_script((b"response", ("192.0.2.10", 5353)))

        with (
            patch("lifx.network.mdns.discovery.IdleDeadline", return_value=deadline),
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response",
                return_value=response,
            ),
        ):
            generator = _discover_lifx_services_sweep(_LifxRecordCache(), timeout=10.0)
            record = await anext(generator)
            deadline.idle_expired = True
            with pytest.raises(StopAsyncIteration):
                await anext(generator)

        assert record.serial == "d073d5123456"
        assert transport.send.await_count == 1


class TestMdnsGoodbyeExpiryScheduling:
    """Goodbye timer wakes stay within the caller-owned deadlines."""

    @pytest.mark.asyncio
    async def test_expiry_wake_precedes_due_retransmit_without_marking_response(
        self,
    ) -> None:
        """One timeout processes expiry then retransmit at the same instant."""
        from lifx.network.mdns.discovery import (
            _discover_lifx_services,
            _LifxRecordCache,
        )

        clock = _FakeMonotonicClock()
        deadline = _fake_deadline()
        transport = _fake_transport()
        events: list[str] = []
        receive_timeouts: list[float] = []
        instance = "device._lifx._udp.local"
        genuine = _txt_record(instance)
        conflicting = _txt_record(instance, _txt(serial="d073d5aabbcd"))
        goodbye = _txt_record(
            instance,
            _txt(serial="d073d5aabbcd"),
            ttl=0,
        )

        positive_response = MagicMock()
        positive_response.header.is_response = True
        positive_response.records = [
            genuine,
            conflicting,
            _srv_record(instance, target="device-host.local"),
            _address_record("device-host.local", "192.0.2.20"),
        ]
        goodbye_response = MagicMock()
        goodbye_response.header.is_response = True
        goodbye_response.records = [goodbye]

        receive_count = 0

        async def receive(timeout: float) -> tuple[bytes, tuple[str, int]]:
            nonlocal receive_count
            receive_count += 1
            receive_timeouts.append(timeout)
            if receive_count == 1:
                return b"conflict", ("192.0.2.10", 5353)
            if receive_count == 2:
                return b"goodbye", ("192.0.2.10", 5353)
            clock.advance(1.0)
            await asyncio.sleep(0)
            raise LifxTimeoutError("scheduled wake")

        transport.receive = receive

        async def send(_data: bytes) -> None:
            events.append("send")

        transport.send.side_effect = send
        original_expire = _LifxRecordCache.expire

        def tracked_expire(cache: _LifxRecordCache, now: float) -> int:
            events.append("expire")
            return original_expire(cache, now)

        with (
            patch("lifx.network.mdns.discovery.time.monotonic", new=clock),
            patch("lifx.network.mdns.discovery.IdleDeadline", return_value=deadline),
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response",
                side_effect=[positive_response, goodbye_response],
            ),
            patch.object(_LifxRecordCache, "expire", new=tracked_expire),
        ):
            generator = _discover_lifx_services(timeout=5.0)
            record = await anext(generator)
            await generator.aclose()

        assert record.serial == "d073d5123456"
        assert receive_timeouts[-1] == pytest.approx(1.0)
        assert events[-2:] == ["expire", "send"]
        assert deadline.mark_response.call_count == 2


class TestMdnsFollowUpAddressQueries:
    """Addresses a responder left out are asked for directly."""

    @staticmethod
    def _pending_records(count: int) -> list[DnsResourceRecord]:
        """TXT and SRV for `count` instances, with no address records."""
        records: list[DnsResourceRecord] = []
        for n in range(count):
            instance = f"bulb{n}._lifx._udp.local"
            records.append(
                DnsResourceRecord(
                    instance, 16, 1, 120, b"", _txt(serial=f"d073d5{n:06x}")
                )
            )
            records.append(
                DnsResourceRecord(
                    instance,
                    33,
                    1,
                    120,
                    b"",
                    SrvData(priority=0, weight=0, port=56700, target=f"host{n}.local"),
                )
            )
        return records

    @staticmethod
    def _response_for(records: list[DnsResourceRecord]) -> MagicMock:
        """A parsed response carrying the given records."""
        response = MagicMock()
        response.header.is_response = True
        response.records = records
        return response

    @pytest.mark.asyncio
    async def test_generator_packet_permutations_yield_one_equal_record(
        self,
    ) -> None:
        """TXT/SRV/A/AAAA packet order, empties, and replay cannot choose output."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        instance = "synthetic._lifx._udp.local"
        target = "synthetic-host.local"
        packet_records = {
            b"txt": [_txt_record(instance)],
            b"srv": [_srv_record(instance, target=target)],
            b"addresses": [
                _address_record(target, "192.0.2.20"),
                _address_record(target, "fd00::20"),
            ],
            b"empty": [],
        }
        expected = (
            "d073d5123456",
            "192.0.2.20",
            56700,
            frozenset({"192.0.2.20", "fd00::20"}),
        )

        for packet_order in permutations((b"txt", b"srv", b"addresses")):
            sequence = [packet_order[0], b"empty", *packet_order[1:], packet_order[-1]]
            transport = _fake_transport()
            transport.receive = _receive_script(
                *((packet, ("192.0.2.10", 5353)) for packet in sequence)
            )

            def parse(packet: bytes) -> MagicMock:
                return self._response_for(packet_records[packet])

            with (
                patch(
                    "lifx.network.mdns.discovery.MdnsTransport",
                    return_value=transport,
                ),
                patch(
                    "lifx.network.mdns.discovery.parse_dns_response",
                    side_effect=parse,
                ),
            ):
                found = [
                    record async for record in _discover_lifx_services(timeout=0.1)
                ]

            assert len(found) == 1
            assert isinstance(found[0], _LifxServiceRecord)
            assert (
                found[0].serial,
                found[0].ip,
                found[0].port,
                found[0].addresses,
            ) == expected

    @pytest.mark.asyncio
    async def test_concurrent_generators_cannot_complete_each_others_instances(
        self, caplog
    ) -> None:
        """Every cache, target ledger, serial set, and summary belongs to one call."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        first_instance = "first._lifx._udp.local"
        second_instance = "second._lifx._udp.local"
        first_pending = self._response_for(
            [
                _txt_record(first_instance, _txt(serial="d073d5000001")),
                _srv_record(first_instance, target="first-host.local"),
            ]
        )
        first_address = self._response_for(
            [_address_record("first-host.local", "192.0.2.11")]
        )
        second_pending = self._response_for(
            [
                _txt_record(second_instance, _txt(serial="d073d5000002")),
                _srv_record(second_instance, target="second-host.local"),
            ]
        )
        second_address = self._response_for(
            [_address_record("second-host.local", "fd00::12")]
        )
        first_transport = _fake_transport()
        first_transport.receive = _receive_script(
            (b"first-pending", ("192.0.2.1", 5353)),
            (b"first-address", ("192.0.2.1", 5353)),
        )
        second_transport = _fake_transport()
        second_transport.receive = _receive_script(
            (b"second-pending", ("192.0.2.2", 5353)),
            (b"second-address", ("192.0.2.2", 5353)),
        )
        responses = {
            b"first-pending": first_pending,
            b"first-address": first_address,
            b"second-pending": second_pending,
            b"second-address": second_address,
        }

        async def collect() -> list[_LifxServiceRecord]:
            return [record async for record in _discover_lifx_services(timeout=0.1)]

        with (
            patch(
                "lifx.network.mdns.discovery.MdnsTransport",
                side_effect=[first_transport, second_transport],
            ),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response",
                side_effect=lambda packet: responses[packet],
            ),
            caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"),
        ):
            first, second = await asyncio.gather(collect(), collect())

        assert [(record.serial, record.ip) for record in first] == [
            ("d073d5000001", "192.0.2.11")
        ]
        assert [(record.serial, record.ip) for record in second] == [
            ("d073d5000002", "fd00::12")
        ]
        summaries = [
            record.msg
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("action") == "rejection_summary"
        ]
        assert [summary["rejections"] for summary in summaries] == [[], []]
        assert first_transport.send.await_args_list[1].args[0] == build_address_query(
            "first-host.local"
        )
        assert second_transport.send.await_args_list[1].args[0] == build_address_query(
            "second-host.local"
        )

    @pytest.mark.parametrize(
        ("address_record", "expected_ip"),
        [
            (_address_record("host0.local", "192.0.2.20"), "192.0.2.20"),
            (_address_record("host0.local", "fd00::20"), "fd00::20"),
        ],
        ids=["a", "aaaa"],
    )
    @pytest.mark.asyncio
    async def test_later_address_response_completes_exact_follow_up(
        self,
        address_record: DnsResourceRecord,
        expected_ip: str,
    ) -> None:
        """The combined A/AAAA query bytes precede later target completion."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        pending = self._response_for(self._pending_records(1))
        address = self._response_for([address_record])
        transport = _fake_transport()
        transport.receive = _receive_script(
            (b"pending", ("192.0.2.10", 5353)),
            (b"address", ("192.0.2.10", 5353)),
        )

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response",
                side_effect=[pending, address],
            ),
        ):
            found = [record async for record in _discover_lifx_services(timeout=0.1)]

        assert [(record.serial, record.ip) for record in found] == [
            ("d073d5000000", expected_ip)
        ]
        assert transport.send.await_args_list[1].args[0] == build_address_query(
            "host0.local"
        )

    @pytest.mark.asyncio
    async def test_unusable_address_triggers_follow_up_then_usable_address_resolves(
        self,
    ) -> None:
        """An unusable cached AAAA cannot deny the direct address query."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        pending = self._response_for(
            [
                *self._pending_records(1),
                _address_record("host0.local", "fe80::20"),
            ]
        )
        address = self._response_for([_address_record("host0.local", "fd00::20")])
        transport = _fake_transport()
        transport.receive = _receive_script(
            (b"unusable", ("192.0.2.10", 5353)),
            (b"usable", ("192.0.2.10", 5353)),
        )

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response",
                side_effect=[pending, address],
            ),
        ):
            found = [record async for record in _discover_lifx_services(timeout=0.1)]

        assert [(record.serial, record.ip) for record in found] == [
            ("d073d5000000", "fd00::20")
        ]
        assert transport.send.await_args_list[1].args[0] == build_address_query(
            "host0.local"
        )

    @pytest.mark.asyncio
    async def test_a_target_with_no_address_record_is_queried_directly(self) -> None:
        """The instance stays unresolved, so its host is asked about."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        transport = _fake_transport()
        transport.receive = _receive_script((b"\x00" * 100, ("192.168.1.100", 5353)))

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response",
                return_value=self._response_for(self._pending_records(1)),
            ),
        ):
            records = [r async for r in _discover_lifx_services(timeout=0.1)]

        # No address ever arrived, so nothing resolved.
        assert records == []

        sent = [call.args[0] for call in transport.send.await_args_list]
        assert build_address_query("host0.local") in sent
        # Asked once, however many times the packet is re-examined: the
        # target is remembered, not re-queried on every pass of the loop.
        assert sent.count(build_address_query("host0.local")) == 1

    @pytest.mark.asyncio
    async def test_follow_up_queries_stop_at_sixty_four_targets(self) -> None:
        """A hostile responder cannot turn one reply into unbounded traffic."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        transport = _fake_transport()
        transport.receive = _receive_script((b"\x00" * 100, ("192.168.1.100", 5353)))

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response",
                return_value=self._response_for(self._pending_records(65)),
            ),
        ):
            records = [r async for r in _discover_lifx_services(timeout=0.1)]

        assert records == []

        sent = [call.args[0] for call in transport.send.await_args_list]
        # The initial PTR query, then the cap's worth of address queries and
        # not one more, even though 65 targets are pending.
        assert len(sent) == 1 + 64
        assert build_address_query("host64.local") not in sent

    @pytest.mark.asyncio
    async def test_resolved_record_survives_unrelated_query_failure(
        self, caplog
    ) -> None:
        """Resolved records are delivered before a pending target's send fails."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        records = [
            *self._pending_records(2),
            DnsResourceRecord("host0.local", 1, 1, 120, b"", "192.168.1.100"),
        ]
        response = self._response_for(records)
        transport = _fake_transport()
        transport.receive = _receive_script(
            (b"first", ("192.168.1.1", 5353)),
            (b"duplicate", ("192.168.1.1", 5353)),
        )
        transport.send.side_effect = [
            None,
            LifxNetworkError("query failed"),
            LifxNetworkError("query failed again"),
        ]

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response",
                return_value=response,
            ),
            caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"),
        ):
            found = [record async for record in _discover_lifx_services(timeout=0.1)]

        assert [record.serial for record in found] == ["d073d5000000"]
        actions = [
            record.msg.get("action")
            for record in caplog.records
            if isinstance(record.msg, dict)
        ]
        assert actions.count("address_query_failed") == 2
        assert "parse_error" not in actions
        summaries = [
            record.msg
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("action") == "rejection_summary"
        ]
        assert len(summaries) == 1
        assert summaries[0]["rejections"] == []

    @pytest.mark.asyncio
    async def test_transient_query_failure_retries_once_then_stops(self) -> None:
        """A failed target retries once and a successful retry is final."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        response = self._response_for(self._pending_records(1))
        transport = _fake_transport()
        transport.receive = _receive_script(
            (b"first", ("192.168.1.1", 5353)),
            (b"second", ("192.168.1.1", 5353)),
            (b"third", ("192.168.1.1", 5353)),
        )
        transport.send.side_effect = [None, LifxNetworkError("transient"), None]

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response",
                return_value=response,
            ),
        ):
            found = [record async for record in _discover_lifx_services(timeout=0.1)]

        assert found == []
        sent = [call.args[0] for call in transport.send.await_args_list]
        assert sent.count(build_address_query("host0.local")) == 2

    @pytest.mark.asyncio
    async def test_persistent_query_failure_stops_after_two_attempts(self) -> None:
        """Duplicate packets cannot generate more than two failed sends per target."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        response = self._response_for(self._pending_records(1))
        transport = _fake_transport()
        transport.receive = _receive_script(
            *((b"duplicate", ("192.168.1.1", 5353)) for _ in range(4))
        )
        transport.send.side_effect = [
            None,
            LifxNetworkError("first"),
            LifxNetworkError("second"),
        ]

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response",
                return_value=response,
            ),
        ):
            found = [record async for record in _discover_lifx_services(timeout=0.1)]

        assert found == []
        sent = [call.args[0] for call in transport.send.await_args_list]
        assert sent.count(build_address_query("host0.local")) == 2

    @pytest.mark.asyncio
    async def test_failed_targets_still_count_towards_sixty_four_cap(self) -> None:
        """The distinct-target cap applies before sends can succeed."""
        from lifx.network.mdns.discovery import _discover_lifx_services

        transport = _fake_transport()
        transport.receive = _receive_script((b"packet", ("192.168.1.1", 5353)))

        async def fail_address_queries(_data: bytes) -> None:
            if transport.send.await_count == 1:
                return
            raise LifxNetworkError("blocked")

        transport.send.side_effect = fail_address_queries

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response",
                return_value=self._response_for(self._pending_records(65)),
            ),
        ):
            found = [record async for record in _discover_lifx_services(timeout=0.1)]

        assert found == []
        sent = [call.args[0] for call in transport.send.await_args_list]
        assert len(sent) == 1 + 64
        assert build_address_query("host64.local") not in sent


class TestMdnsSerialDeduplication:
    """One device answering under two instance names is still one device."""

    @pytest.mark.asyncio
    async def test_two_instances_sharing_a_serial_yield_one_record(self) -> None:
        """The dedupe is by serial, not by instance name.

        The cache already emits each *instance* once, so this only bites when
        a device is advertised twice under different names, which is what a
        border router re-advertising a device that also answers for itself
        looks like on the wire.
        """
        from lifx.network.mdns.discovery import _discover_lifx_services

        serial = "d073d5123456"
        records = []
        for label, host, ip in (
            ("bulb-a", "hosta.local", "192.168.1.100"),
            ("bulb-b", "hostb.local", "192.168.1.101"),
        ):
            instance = f"{label}._lifx._udp.local"
            records.append(
                DnsResourceRecord(instance, 16, 1, 120, b"", _txt(serial=serial))
            )
            records.append(
                DnsResourceRecord(
                    instance,
                    33,
                    1,
                    120,
                    b"",
                    SrvData(priority=0, weight=0, port=56700, target=host),
                )
            )
            records.append(DnsResourceRecord(host, 1, 1, 120, b"", ip))

        response = MagicMock()
        response.header.is_response = True
        response.records = records

        transport = _fake_transport()
        transport.receive = _receive_script((b"\x00" * 100, ("192.168.1.100", 5353)))

        with (
            patch("lifx.network.mdns.discovery.MdnsTransport", return_value=transport),
            patch(
                "lifx.network.mdns.discovery.parse_dns_response",
                return_value=response,
            ),
        ):
            found = [r async for r in _discover_lifx_services(timeout=0.1)]

        assert len(found) == 1
        assert found[0].serial == serial
        assert found[0].ip == "192.168.1.100"
