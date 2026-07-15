"""Tests for mDNS discovery functions."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.devices.ceiling import CeilingLight
from lifx.devices.hev import HevLight
from lifx.devices.infrared import InfraredLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.exceptions import LifxNetworkError, LifxTimeoutError
from lifx.network.mdns.discovery import (
    _LifxRecordCache,
    create_device_from_record,
)
from lifx.network.mdns.dns import DnsResourceRecord, SrvData, TxtData
from lifx.network.mdns.types import LifxServiceRecord


def _txt(serial: str = "d073d5123456", product: str = "27") -> TxtData:
    pairs = {"id": serial, "p": product, "fw": "4.112"}
    return TxtData(
        strings=[f"{k}={v}" for k, v in pairs.items() if v],
        pairs={k: v for k, v in pairs.items() if v},
    )


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


class TestLifxRecordCache:
    """Tests for the _LifxRecordCache mDNS record accumulator."""

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
        cache.add_packet(packet1, "192.168.1.1")
        assert cache.resolve() == []

        assert cache.add_packet(packet2, "192.168.1.1") is False
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


class TestCreateDeviceFromRecord:
    """Tests for create_device_from_record function."""

    def test_create_light_device(self) -> None:
        """Test creating a basic Light device."""
        record = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=27,  # LIFX A19 - basic light
            firmware="4.112",
        )

        device = create_device_from_record(record)

        assert device is not None
        assert isinstance(device, Light)
        assert device.serial == "d073d5123456"
        assert device.ip == "192.168.1.100"
        assert device.port == 56700

    def test_create_multizone_device(self) -> None:
        """Test creating a MultiZoneLight device."""
        record = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=31,  # LIFX Z - multizone
            firmware="4.112",
        )

        device = create_device_from_record(record)

        assert device is not None
        assert isinstance(device, MultiZoneLight)

    def test_create_matrix_device(self) -> None:
        """Test creating a MatrixLight device."""
        record = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=55,  # LIFX Tile - matrix
            firmware="4.112",
        )

        device = create_device_from_record(record)

        assert device is not None
        assert isinstance(device, MatrixLight)

    def test_create_ceiling_device(self) -> None:
        """Test creating a CeilingLight device."""
        record = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=176,  # LIFX Ceiling US
            firmware="4.112",
        )

        device = create_device_from_record(record)

        assert device is not None
        assert isinstance(device, CeilingLight)

    def test_create_infrared_device(self) -> None:
        """Test creating an InfraredLight device."""
        record = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=29,  # LIFX+ A19 - has infrared
            firmware="4.112",
        )

        device = create_device_from_record(record)

        assert device is not None
        assert isinstance(device, InfraredLight)

    def test_create_hev_device(self) -> None:
        """Test creating a HevLight device."""
        record = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=90,  # LIFX Clean - has HEV
            firmware="4.112",
        )

        device = create_device_from_record(record)

        assert device is not None
        assert isinstance(device, HevLight)

    def test_relay_device_returns_none(self) -> None:
        """Test that relay devices return None."""
        record = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=70,  # LIFX Switch - relay only
            firmware="4.112",
        )

        device = create_device_from_record(record)

        assert device is None

    def test_device_timeout_and_retries(self) -> None:
        """Test that timeout and retries are passed to device."""
        record = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=27,
            firmware="4.112",
        )

        device = create_device_from_record(record, timeout=30.0, max_retries=5)

        assert device is not None
        # Check that timeout/retries were passed to the connection
        assert device.connection.timeout == 30.0
        assert device.connection.max_retries == 5


class TestLifxServiceRecord:
    """Tests for LifxServiceRecord dataclass."""

    def test_hash_by_serial(self) -> None:
        """Test that records hash by serial."""
        record1 = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=27,
            firmware="4.112",
        )
        record2 = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.200",  # Different IP
            port=56701,  # Different port
            product_id=28,  # Different product
            firmware="4.113",  # Different firmware
        )

        assert hash(record1) == hash(record2)

    def test_equality_by_serial(self) -> None:
        """Test that records are equal by serial."""
        record1 = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=27,
            firmware="4.112",
        )
        record2 = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.200",
            port=56701,
            product_id=28,
            firmware="4.113",
        )
        record3 = LifxServiceRecord(
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
        record = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=27,
            firmware="4.112",
        )

        with pytest.raises(AttributeError):
            record.serial = "new_serial"  # type: ignore[misc]

    def test_equality_with_non_record(self) -> None:
        """Test that comparing to non-LifxServiceRecord returns False."""
        record = LifxServiceRecord(
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


class TestDiscoverLifxServices:
    """Tests for discover_lifx_services function."""

    @pytest.mark.asyncio
    async def test_discover_yields_records(self) -> None:
        """Test that discovery yields service records."""
        from lifx.network.mdns.discovery import discover_lifx_services

        # Create mock response data
        mock_response_data = b"\x00" * 100  # Placeholder

        # Create mock records
        txt_data = TxtData(
            strings=["id=d073d5123456", "p=27", "fw=4.112"],
            pairs={"id": "d073d5123456", "p": "27", "fw": "4.112"},
        )

        mock_parsed_response = MagicMock()
        mock_parsed_response.header.is_response = True
        mock_parsed_response.records = [
            MagicMock(
                rtype=12, name="_lifx._udp.local", parsed_data="device._lifx._udp.local"
            ),
            MagicMock(rtype=16, parsed_data=txt_data),
        ]

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            mock_transport.receive.side_effect = _receive_script(
                (mock_response_data, ("192.168.1.100", 5353)),
            )

            with patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse:
                mock_parse.return_value = mock_parsed_response

                records = []
                async for record in discover_lifx_services(timeout=0.1):
                    records.append(record)

                assert len(records) == 1
                assert records[0].serial == "d073d5123456"

    @pytest.mark.asyncio
    async def test_discover_idle_timeout(self) -> None:
        """Test that discovery stops on idle timeout."""
        from lifx.network.mdns.discovery import discover_lifx_services

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
            async for record in discover_lifx_services(
                timeout=5.0, max_response_time=0.01, idle_timeout_multiplier=1.0
            ):
                records.append(record)

            assert len(records) == 0

    @pytest.mark.asyncio
    async def test_discover_overall_timeout(self) -> None:
        """Test that discovery stops on overall timeout."""
        from lifx.network.mdns.discovery import discover_lifx_services

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
                async for record in discover_lifx_services(timeout=0.05):
                    records.append(record)

                # Should have discovered at most one device (deduplicated)
                assert len(records) <= 1

    @pytest.mark.asyncio
    async def test_discover_skips_non_response(self) -> None:
        """Test that discovery skips DNS queries (non-responses)."""
        from lifx.network.mdns.discovery import discover_lifx_services

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
                async for record in discover_lifx_services(timeout=0.1):
                    records.append(record)

                # Should have no records since we skipped the query
                assert len(records) == 0

    @pytest.mark.asyncio
    async def test_discover_skips_non_lifx_response(self) -> None:
        """Test that discovery skips non-LIFX mDNS responses."""
        from lifx.network.mdns.discovery import discover_lifx_services

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
                async for record in discover_lifx_services(timeout=0.1):
                    records.append(record)

                assert len(records) == 0

    @pytest.mark.asyncio
    async def test_discover_skips_invalid_record(self) -> None:
        """Test that discovery skips responses that can't be parsed as LIFX records."""
        from lifx.network.mdns.discovery import discover_lifx_services

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
                async for record in discover_lifx_services(timeout=0.1):
                    records.append(record)

                # Should be empty because the TXT record has no id/p fields
                assert len(records) == 0

    @pytest.mark.asyncio
    async def test_discover_handles_parse_error(self) -> None:
        """Test that discovery handles DNS parsing errors gracefully."""
        from lifx.network.mdns.discovery import discover_lifx_services

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
                async for record in discover_lifx_services(timeout=0.1):
                    records.append(record)

                # Should continue despite parse error
                assert len(records) == 0

    @pytest.mark.asyncio
    async def test_discover_with_lifx_txt_but_no_ptr(self) -> None:
        """Test discovery with LIFX TXT record but no PTR record."""
        from lifx.network.mdns.discovery import discover_lifx_services

        # Response with LIFX TXT but no PTR
        txt_data = TxtData(
            strings=["id=d073d5123456", "p=27", "fw=4.112"],
            pairs={"id": "d073d5123456", "p": "27", "fw": "4.112"},
        )
        mock_response = MagicMock()
        mock_response.header.is_response = True
        mock_response.records = [
            MagicMock(rtype=16, name="device.local", parsed_data=txt_data),
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
                async for record in discover_lifx_services(timeout=0.1):
                    records.append(record)

                # Should still discover via TXT record fallback
                assert len(records) == 1
                assert records[0].serial == "d073d5123456"

    @pytest.mark.asyncio
    async def test_discover_deduplicates_by_serial(self) -> None:
        """Test that discovery deduplicates by serial."""
        from lifx.network.mdns.discovery import discover_lifx_services

        txt_data = TxtData(
            strings=["id=d073d5123456", "p=27", "fw=4.112"],
            pairs={"id": "d073d5123456", "p": "27", "fw": "4.112"},
        )

        mock_parsed_response = MagicMock()
        mock_parsed_response.header.is_response = True
        mock_parsed_response.records = [
            MagicMock(
                rtype=12, name="_lifx._udp.local", parsed_data="device._lifx._udp.local"
            ),
            MagicMock(rtype=16, parsed_data=txt_data),
        ]

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            # Return same device twice, then timeout
            mock_transport.receive.side_effect = _receive_script(
                (b"\x00" * 100, ("192.168.1.100", 5353)),
                (b"\x00" * 100, ("192.168.1.100", 5353)),
            )

            with patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse:
                mock_parse.return_value = mock_parsed_response

                records = []
                async for record in discover_lifx_services(timeout=0.1):
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
        from lifx.network.mdns.discovery import discover_lifx_services
        from lifx.network.utils import IdleDeadline

        txt_data = TxtData(
            strings=["id=d073d5123456", "p=27", "fw=4.112"],
            pairs={"id": "d073d5123456", "p": "27", "fw": "4.112"},
        )

        mock_parsed_response = MagicMock()
        mock_parsed_response.header.is_response = True
        mock_parsed_response.records = [
            MagicMock(
                rtype=12, name="_lifx._udp.local", parsed_data="device._lifx._udp.local"
            ),
            MagicMock(rtype=16, parsed_data=txt_data),
        ]

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            # Same device twice (duplicate), then timeout
            mock_transport.receive.side_effect = _receive_script(
                (b"\x00" * 100, ("192.168.1.100", 5353)),
                (b"\x00" * 100, ("192.168.1.100", 5353)),
            )

            with (
                patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse,
                patch.object(IdleDeadline, "mark_response", autospec=True) as mock_mark,
            ):
                mock_parse.return_value = mock_parsed_response

                records = []
                async for record in discover_lifx_services(timeout=0.1):
                    records.append(record)

        # Dedup still yields one record, but BOTH valid responses must have
        # reset the idle deadline.
        assert len(records) == 1
        assert mock_mark.call_count == 2

    @pytest.mark.asyncio
    async def test_discover_network_error_does_not_propagate(self) -> None:
        """Test that LifxNetworkError breaks the loop without propagating (D-08)."""
        from lifx.network.mdns.discovery import discover_lifx_services

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            mock_transport.receive.side_effect = LifxNetworkError("interface down")

            records = []
            # Must not raise — LifxNetworkError causes a clean break with a WARNING log
            async for record in discover_lifx_services(timeout=0.1):
                records.append(record)

            assert len(records) == 0

    @pytest.mark.asyncio
    async def test_discover_unexpected_error_propagates(self) -> None:
        """Test that unexpected receive exceptions are logged and re-raised (D-08)."""
        from lifx.network.mdns.discovery import discover_lifx_services

        with patch("lifx.network.mdns.discovery.MdnsTransport") as mock_transport_cls:
            mock_transport = AsyncMock()
            mock_transport_cls.return_value.__aenter__.return_value = mock_transport

            mock_transport.receive.side_effect = RuntimeError("unexpected socket state")

            with pytest.raises(RuntimeError, match="unexpected socket state"):
                async for _record in discover_lifx_services(timeout=0.1):
                    pass


class TestDiscoverDevicesMdns:
    """Tests for discover_devices_mdns function."""

    @pytest.mark.asyncio
    async def test_discover_yields_device_instances(self) -> None:
        """Test that discovery yields device instances."""
        from lifx.network.mdns.discovery import discover_devices_mdns

        # Create a mock service record
        mock_record = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=27,
            firmware="4.112",
        )

        with patch(
            "lifx.network.mdns.discovery.discover_lifx_services"
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
    async def test_discover_filters_relay_devices(self) -> None:
        """Test that relay devices are filtered out."""
        from lifx.network.mdns.discovery import discover_devices_mdns

        # Create a mock relay device record
        mock_record = LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=70,  # LIFX Switch - relay only
            firmware="4.112",
        )

        with patch(
            "lifx.network.mdns.discovery.discover_lifx_services"
        ) as mock_discover:

            async def mock_generator():
                yield mock_record

            mock_discover.return_value = mock_generator()

            devices = []
            async for device in discover_devices_mdns(timeout=0.1):
                devices.append(device)

            # Relay device should be filtered out
            assert len(devices) == 0


class TestMdnsRemainingNonPositiveGuard:
    """The defensive ``remaining() <= 0`` break terminates the mDNS loop cleanly."""

    @pytest.mark.asyncio
    async def test_remaining_nonpositive_breaks_before_receive(self) -> None:
        from lifx.network.mdns.discovery import discover_lifx_services

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

            records = [r async for r in discover_lifx_services(timeout=0.5)]

        assert records == []
        mock_transport.receive.assert_not_called()

    @pytest.mark.asyncio
    async def test_idle_expired_breaks_with_debug(self) -> None:
        """idle_expired True takes the idle-timeout break (covers the True side)."""
        from lifx.network.mdns.discovery import discover_lifx_services

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

            records = [r async for r in discover_lifx_services(timeout=0.5)]

        assert records == []
        mock_transport.receive.assert_not_called()
