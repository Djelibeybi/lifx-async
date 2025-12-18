"""Tests for mDNS discovery functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.devices.ceiling import CeilingLight
from lifx.devices.hev import HevLight
from lifx.devices.infrared import InfraredLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.network.mdns.discovery import (
    _extract_lifx_info,
    create_device_from_record,
)
from lifx.network.mdns.dns import DnsResourceRecord, SrvData, TxtData
from lifx.network.mdns.types import LifxServiceRecord


class TestExtractLifxInfo:
    """Tests for _extract_lifx_info helper function."""

    def test_extract_with_all_records(self) -> None:
        """Test extraction with TXT, SRV, and A records."""
        txt_data = TxtData(
            strings=["id=d073d5123456", "p=27", "fw=4.112"],
            pairs={"id": "d073d5123456", "p": "27", "fw": "4.112"},
        )
        srv_data = SrvData(priority=0, weight=0, port=56700, target="host.local")

        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", txt_data),
            DnsResourceRecord("test._lifx._udp.local", 33, 1, 120, b"", srv_data),
            DnsResourceRecord("host.local", 1, 1, 120, b"", "192.168.1.100"),
        ]

        result = _extract_lifx_info(records, "192.168.1.50")

        assert result is not None
        assert result.serial == "d073d5123456"
        assert result.ip == "192.168.1.100"  # From A record
        assert result.port == 56700  # From SRV record
        assert result.product_id == 27
        assert result.firmware == "4.112"

    def test_extract_with_txt_only(self) -> None:
        """Test extraction with only TXT record."""
        txt_data = TxtData(
            strings=["id=d073d5123456", "p=27", "fw=4.112"],
            pairs={"id": "d073d5123456", "p": "27", "fw": "4.112"},
        )

        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", txt_data),
        ]

        result = _extract_lifx_info(records, "192.168.1.50")

        assert result is not None
        assert result.serial == "d073d5123456"
        assert result.ip == "192.168.1.50"  # From source IP
        assert result.port == 56700  # Default
        assert result.product_id == 27

    def test_extract_missing_serial(self) -> None:
        """Test extraction fails without serial."""
        txt_data = TxtData(
            strings=["p=27", "fw=4.112"],
            pairs={"p": "27", "fw": "4.112"},
        )

        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", txt_data),
        ]

        result = _extract_lifx_info(records, "192.168.1.50")

        assert result is None

    def test_extract_missing_product_id(self) -> None:
        """Test extraction fails without product ID."""
        txt_data = TxtData(
            strings=["id=d073d5123456", "fw=4.112"],
            pairs={"id": "d073d5123456", "fw": "4.112"},
        )

        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", txt_data),
        ]

        result = _extract_lifx_info(records, "192.168.1.50")

        assert result is None

    def test_extract_invalid_product_id(self) -> None:
        """Test extraction fails with non-numeric product ID."""
        txt_data = TxtData(
            strings=["id=d073d5123456", "p=abc", "fw=4.112"],
            pairs={"id": "d073d5123456", "p": "abc", "fw": "4.112"},
        )

        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", txt_data),
        ]

        result = _extract_lifx_info(records, "192.168.1.50")

        assert result is None

    def test_extract_no_txt_record(self) -> None:
        """Test extraction fails without TXT record."""
        srv_data = SrvData(priority=0, weight=0, port=56700, target="host.local")

        records = [
            DnsResourceRecord("test._lifx._udp.local", 33, 1, 120, b"", srv_data),
            DnsResourceRecord("host.local", 1, 1, 120, b"", "192.168.1.100"),
        ]

        result = _extract_lifx_info(records, "192.168.1.50")

        assert result is None

    def test_extract_serial_lowercase(self) -> None:
        """Test that serial is lowercased."""
        txt_data = TxtData(
            strings=["id=D073D5AABBCC", "p=27"],
            pairs={"id": "D073D5AABBCC", "p": "27"},
        )

        records = [
            DnsResourceRecord("test._lifx._udp.local", 16, 1, 120, b"", txt_data),
        ]

        result = _extract_lifx_info(records, "192.168.1.50")

        assert result is not None
        assert result.serial == "d073d5aabbcc"


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

            # First receive returns data, second raises timeout
            mock_transport.receive.side_effect = [
                (mock_response_data, ("192.168.1.100", 5353)),
                Exception("timeout"),
            ]

            with patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse:
                mock_parse.return_value = mock_parsed_response

                records = []
                async for record in discover_lifx_services(timeout=0.1):
                    records.append(record)

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
            mock_transport.receive.side_effect = [
                (b"\x00" * 100, ("192.168.1.100", 5353)),
                (b"\x00" * 100, ("192.168.1.100", 5353)),
                Exception("timeout"),
            ]

            with patch("lifx.network.mdns.discovery.parse_dns_response") as mock_parse:
                mock_parse.return_value = mock_parsed_response

                records = []
                async for record in discover_lifx_services(timeout=0.1):
                    records.append(record)

                # Should only get one record despite two responses
                assert len(records) == 1


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
