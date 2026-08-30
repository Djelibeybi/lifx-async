"""Tests for high-level API discovery helper functions.

This module tests:
- discover() - Async generator for device discovery
- discover_mdns() - Async generator for mDNS-based discovery
- find_by_serial() - Find specific device by serial number
- find_by_ip() - Find device by IP address
- find_by_label() - Find device by exact label match
"""

from __future__ import annotations

import asyncio
from typing import ClassVar
from unittest.mock import patch

import pytest

from lifx.api import discover, discover_mdns, find_by_ip, find_by_label, find_by_serial
from lifx.devices import Light
from lifx.exceptions import LifxTimeoutError
from lifx.network.address import SocketAddress
from lifx.network.discovery import DiscoveredDevice, DiscoveryResponse, discover_devices
from lifx.network.message import create_message
from lifx.network.transport import UdpTransport
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Device as DevicePackets
from lifx.protocol.protocol_types import DeviceService
from tests.conftest import get_free_port


@pytest.mark.emulator
class TestDiscover:
    """Test discover() async generator."""

    async def test_discover_basic(self, emulator_port: int):
        """Test basic discovery with async generator."""
        async for device in discover(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            assert isinstance(device, Light)

    async def test_discover_with_timeout(self, emulator_port: int):
        """Test discovery with custom timeout."""
        async for device in discover(
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            assert device is not None
            break

    async def test_discover_empty_network(self):
        """Test discovery when no devices are present."""
        async for device in discover(
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=get_free_port(),
        ):
            pytest.fail(f"Unexpected yield of {device} from discover.")


@pytest.mark.emulator
class TestFindBySerial:
    """Test find_by_serial() helper function."""

    async def test_find_by_serial_found_string(self, emulator_port: int):
        """Test finding device by serial number (string format)."""
        # First discover a device to get a real serial number
        target_serial = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            target_serial = disc.serial
            break

        assert target_serial is not None

        # Use the first discovered device's serial
        device = await find_by_serial(
            target_serial,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        assert device.serial == target_serial
        assert isinstance(device, Light)

    async def test_find_by_serial_with_colons(self, emulator_port: int):
        """Test finding device by serial with colon separators."""
        # Discover first device
        target_serial = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            target_serial = disc.serial
            break
        assert target_serial is not None

        # Format with colons
        serial_with_colons = ":".join(
            [target_serial[i : i + 2] for i in range(0, 12, 2)]
        )

        device = await find_by_serial(
            serial_with_colons,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        assert device.serial == target_serial

    async def test_find_by_serial_not_found(self, emulator_port: int):
        """Test finding device with non-existent serial."""
        device = await find_by_serial(
            "d073d5999999",
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        # Should return None
        assert device is None

    async def test_find_by_serial_case_insensitive(self, emulator_port: int):
        """Test that serial matching is case-insensitive."""
        # Discover first device
        target_serial = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            target_serial = disc.serial
            break
        assert target_serial is not None

        # Use uppercase version of serial
        uppercase_serial = target_serial.upper()

        device = await find_by_serial(
            uppercase_serial,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        assert device.serial.lower() == target_serial.lower()

    async def test_find_by_serial_timeout(self):
        """Test find_by_serial with empty network (timeout scenario)."""
        # Use a port with no emulator running
        device = await find_by_serial(
            "d073d5999999",
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=get_free_port(),
        )
        assert device is None


@pytest.mark.emulator
class TestFindByIp:
    """Tests for find_by_ip function."""

    async def test_find_by_ip_found(self, emulator_port: int):
        """Test find_by_ip returns device when IP matches."""
        # Emulator devices are all at 127.0.0.1
        device = await find_by_ip(
            "127.0.0.1",
            timeout=1.0,
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        # Should get one of the emulator devices (d073d5000001-d073d5000007)
        assert device.serial.startswith("d073d5")

    async def test_find_by_ip_not_found(self, emulator_port: int):
        """Test find_by_ip returns None when IP doesn't match any device."""
        # Use an IP that's definitely not the emulator (192.168.200.254)
        device = await find_by_ip(
            "192.168.200.254",
            timeout=1.0,
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is None

    async def test_find_by_ip_timeout(self):
        """Test find_by_ip with no emulator running (timeout scenario)."""
        device = await find_by_ip(
            "127.0.0.1",
            timeout=0.5,
            port=get_free_port(),
            idle_timeout_multiplier=0.5,
        )
        assert device is None


@pytest.mark.emulator
class TestFindByLabel:
    """Tests for find_by_label function."""

    async def test_find_by_label_found(self, emulator_port: int):
        """Test find_by_label can find devices by label."""
        # First discover a device and get its label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        # Get the label of the first device
        device = await first_disc.create_device()
        assert device is not None, "Supported emulator product must construct a device"

        async with device:
            device_label = await device.get_label()

        # Now search for that device by label using find_by_label
        found_devices = []
        async for d in find_by_label(
            device_label,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            found_devices.append(d)

        try:
            assert len(found_devices) >= 1
            assert any(d.serial == first_disc.serial for d in found_devices)
        finally:
            # Close all found device connections
            for d in found_devices:
                await d.connection.close()

    async def test_find_by_label_case_insensitive(self, emulator_port: int):
        """Test find_by_label is case-insensitive."""
        # Get a device label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        device = await first_disc.create_device()
        assert device is not None, "Supported emulator product must construct a device"

        async with device:
            device_label = await device.get_label()

        # Search with different case
        found_devices = []
        async for d in find_by_label(
            device_label.upper(),
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            found_devices.append(d)

        try:
            assert len(found_devices) >= 1
            assert any(d.serial == first_disc.serial for d in found_devices)
        finally:
            # Close all found device connections
            for d in found_devices:
                await d.connection.close()

    async def test_find_by_label_not_found(self, emulator_port: int):
        """Test find_by_label returns empty list when label doesn't match any device."""
        # Use a label that definitely doesn't exist
        async for d in find_by_label(
            "Nonexistent Device Label XYZ999",
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            pytest.fail(f"Unexpected yield of {d} from find_by_label()")

    async def test_find_by_label_timeout(self):
        """Test find_by_label with no emulator running (timeout scenario)."""
        async for d in find_by_label(
            "Test Device",
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=get_free_port(),
            idle_timeout_multiplier=0.5,
        ):
            pytest.fail(f"Unexpected yield of {d} from find_by_label()")

    async def test_find_by_label_substring_match(self, emulator_port: int):
        """Test find_by_label substring matching (default behavior)."""
        # Get a device label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        device = await first_disc.create_device()
        assert device is not None, "Supported emulator product must construct a device"

        async with device:
            device_label = await device.get_label()

        # Search with partial label (should match if label contains the substring)
        # E.g., if label is "LIFX Color 000001", search for "Color"
        if len(device_label) > 4:
            partial_label = device_label[5:9]  # Get a middle substring
            async for d in find_by_label(
                partial_label,
                exact_match=False,
                timeout=1.0,
                broadcast_address="127.0.0.1",
                port=emulator_port,
                idle_timeout_multiplier=0.5,
            ):
                assert d is not None
                await d.connection.close()
                break

    async def test_find_by_label_exact_match(self, emulator_port: int):
        """Test find_by_label exact matching."""
        # Get a device label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        device = await first_disc.create_device()
        assert device is not None, "Supported emulator product must construct a device"

        async with device:
            device_label = await device.get_label()

        # Exact match should work
        async for d in find_by_label(
            device_label,
            exact_match=True,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            assert d.serial == first_disc.serial
            await d.connection.close()

        # Partial label with exact_match=True should NOT match
        if len(device_label) > 4:
            partial_label = device_label[5:9]
            async for d in find_by_label(
                partial_label,
                exact_match=True,
                timeout=1.0,
                broadcast_address="127.0.0.1",
                port=emulator_port,
                idle_timeout_multiplier=0.5,
            ):
                pytest.fail(f"Unexpected yield of {d} from find_by_label()")


class TestDiscoveryDelegateLifecycle:
    """Public helpers synchronously close their socket-owning delegates."""

    async def test_discover_skips_unsupported_device(self) -> None:
        """Discovery continues when capability detection rejects a responder."""
        discovered = DiscoveredDevice("d073d5123456", "192.0.2.10")

        async def _discover_devices(*args, **kwargs):
            yield discovered

        async def _create_device(_discovered: DiscoveredDevice) -> None:
            return None

        with (
            patch("lifx.api.discover_devices", side_effect=_discover_devices),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _create_device,
            ),
        ):
            assert [device async for device in discover()] == []

    async def test_discover_close_finalises_device_discovery(self) -> None:
        """Closing ``discover`` immediately closes ``discover_devices``."""
        finalised = False
        discovered = DiscoveredDevice("d073d5123456", "192.0.2.10")
        device = Light("d073d5123456", "192.0.2.10")

        async def _discover_devices(*args, **kwargs):
            nonlocal finalised
            try:
                yield discovered
            finally:
                finalised = True

        async def _create_device(_discovered: DiscoveredDevice) -> Light:
            return device

        with (
            patch("lifx.api.discover_devices", side_effect=_discover_devices),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _create_device,
            ),
        ):
            generator = discover()
            assert await anext(generator) is device
            await generator.aclose()

        assert finalised is True

    async def test_find_by_serial_return_finalises_device_discovery(self) -> None:
        """An early matching return does not leave the delegate suspended."""
        finalised = False
        discovered = DiscoveredDevice("d073d5123456", "192.0.2.10")
        device = Light("d073d5123456", "192.0.2.10")

        async def _discover_devices(*args, **kwargs):
            nonlocal finalised
            try:
                yield discovered
            finally:
                finalised = True

        async def _create_device(_discovered: DiscoveredDevice) -> Light:
            return device

        with (
            patch("lifx.api.discover_devices", side_effect=_discover_devices),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _create_device,
            ),
        ):
            assert await find_by_serial(discovered.serial) is device

        assert finalised is True

    async def test_find_by_label_close_finalises_packet_discovery(self) -> None:
        """A consumer break closes the packet-discovery delegate immediately."""
        finalised = False
        response = DiscoveryResponse(
            serial="d073d5123456",
            ip="192.0.2.10",
            port=56700,
            response_time=0.01,
            response_payload={"label": "Synthetic Light"},
        )
        device = Light(response.serial, response.ip)

        async def _discover_packets(*args, **kwargs):
            nonlocal finalised
            try:
                yield response
            finally:
                finalised = True

        async def _create_device(_discovered: DiscoveredDevice) -> Light:
            return device

        with (
            patch("lifx.api._discover_with_packet", side_effect=_discover_packets),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _create_device,
            ),
        ):
            generator = find_by_label("Synthetic", exact_match=False)
            assert await anext(generator) is device
            await generator.aclose()

        assert finalised is True

    async def test_find_by_label_exact_match_stops_after_first_device(self) -> None:
        """The exact-match contract yields at most one matching device."""
        finalised = False
        responses = [
            DiscoveryResponse(
                serial=f"d073d51234{suffix}",
                ip=f"192.0.2.{index}",
                port=56700,
                response_time=0.01,
                response_payload={"label": "Synthetic Light"},
            )
            for index, suffix in enumerate(("56", "57"), start=10)
        ]

        async def _discover_packets(*args, **kwargs):
            nonlocal finalised
            try:
                for response in responses:
                    yield response
            finally:
                finalised = True

        async def _create_device(discovered: DiscoveredDevice) -> Light:
            return Light(discovered.serial, discovered.ip)

        with (
            patch("lifx.api._discover_with_packet", side_effect=_discover_packets),
            patch.object(DiscoveredDevice, "create_device", _create_device),
        ):
            devices = [
                device
                async for device in find_by_label("Synthetic Light", exact_match=True)
            ]

        assert len(devices) == 1
        assert devices[0].serial == responses[0].serial
        assert finalised is True

    async def test_find_by_label_skips_unsupported_device(self) -> None:
        """A matching label is ignored when its device type is unsupported."""
        response = DiscoveryResponse(
            serial="d073d5123456",
            ip="192.0.2.10",
            port=56700,
            response_time=0.01,
            response_payload={"label": "Synthetic Light"},
        )

        async def _discover_packets(*args, **kwargs):
            yield response

        async def _create_device(_discovered: DiscoveredDevice) -> None:
            return None

        with (
            patch("lifx.api._discover_with_packet", side_effect=_discover_packets),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _create_device,
            ),
        ):
            assert [
                device async for device in find_by_label("Synthetic", exact_match=False)
            ] == []


class TestDiscoverMdns:
    """Tests for discover_mdns() high-level API function."""

    @pytest.mark.asyncio
    async def test_close_synchronously_finalises_device_discovery(self) -> None:
        """Closing the public generator closes its socket-owning delegate."""
        finalised = False
        device = Light("d073d5123456", "192.0.2.10")

        async def mock_discover_devices(*args, **kwargs):
            nonlocal finalised
            try:
                yield device
            finally:
                finalised = True

        with patch(
            "lifx.network.mdns.discovery.discover_devices_mdns",
            side_effect=mock_discover_devices,
        ):
            generator = discover_mdns(timeout=0.1)
            assert await anext(generator) is device
            await generator.aclose()

        assert finalised is True

    @pytest.mark.asyncio
    async def test_discover_mdns_yields_devices(self) -> None:
        """Test that discover_mdns() yields device instances."""
        from lifx.network.mdns.types import _LifxServiceRecord

        mock_record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.0.2.10",
            port=56700,
            product_id=27,  # LIFX A19
            firmware="4.112",
            connectivity="thread",
            service_instance="device._lifx._udp.local",
        )

        async def mock_discover_services(*args, **kwargs):
            yield mock_record

        with patch(
            "lifx.network.mdns.discovery._discover_lifx_services",
            side_effect=mock_discover_services,
        ):
            devices = []
            async for device in discover_mdns(timeout=0.1):
                devices.append(device)

            assert len(devices) == 1
            assert isinstance(devices[0], Light)
            assert devices[0].serial == "d073d5123456"
            assert devices[0].connectivity == "thread"

    @pytest.mark.asyncio
    async def test_discover_mdns_filters_relay_devices(self) -> None:
        """Test that discover_mdns() filters out relay-only devices."""
        from lifx.network.mdns.types import _LifxServiceRecord

        mock_record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=70,  # LIFX Switch - relay only
            firmware="4.112",
            service_instance="device._lifx._udp.local",
        )

        async def mock_discover_services(*args, **kwargs):
            yield mock_record

        with patch(
            "lifx.network.mdns.discovery._discover_lifx_services",
            side_effect=mock_discover_services,
        ):
            devices = []
            async for device in discover_mdns(timeout=0.1):
                devices.append(device)

            # Relay devices should be filtered out
            assert len(devices) == 0

    @pytest.mark.asyncio
    async def test_discover_mdns_empty_network(self) -> None:
        """Test discover_mdns() with no devices."""

        async def mock_discover_services(*args, **kwargs):
            return
            yield  # noqa: B901 - makes this an async generator

        with patch(
            "lifx.network.mdns.discovery._discover_lifx_services",
            side_effect=mock_discover_services,
        ):
            devices = []
            async for device in discover_mdns(timeout=0.1):
                devices.append(device)

            assert len(devices) == 0


class _ObservedNoResponseDiscoveryTransport(UdpTransport):
    """Record a discovery boundary, then cooperatively time out."""

    latest: ClassVar[_ObservedNoResponseDiscoveryTransport | None] = None
    destinations: list[SocketAddress]

    @property
    def ip_address(self) -> str:
        """Expose the configured bind address for boundary assertions."""
        return self._ip_address

    @property
    def broadcast(self) -> bool:
        """Expose the configured broadcast flag for boundary assertions."""
        return self._broadcast

    async def __aenter__(self) -> _ObservedNoResponseDiscoveryTransport:
        self.destinations = []
        _ObservedNoResponseDiscoveryTransport.latest = self
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def send(self, data: bytes, address: SocketAddress) -> None:
        self.destinations.append(address)

    async def receive(self, timeout: float = 2.0) -> tuple[bytes, SocketAddress]:
        await asyncio.sleep(timeout)
        raise LifxTimeoutError("synthetic discovery timeout")


def _build_state_service_packet(source: int) -> bytes:
    """Build one valid response for a clearly synthetic device identity."""
    return create_message(
        DevicePackets.StateService(service=DeviceService.UDP, port=56700),
        source=source,
        target=b"\x02\x00\x00\x00\x00\x01\x00\x00",
        ack_required=False,
        res_required=False,
        sequence=0,
    )


class _SplitScopeResponseDiscoveryTransport(_ObservedNoResponseDiscoveryTransport):
    """Return an IPv6 sockaddr whose numeric scope is separate from its host."""

    _response: bytes | None = None

    async def send(self, data: bytes, address: SocketAddress) -> None:
        await super().send(data, address)
        request_header = LifxHeader.unpack(data[: LifxHeader.HEADER_SIZE])
        self._response = _build_state_service_packet(request_header.source)

    async def receive(self, timeout: float = 2.0) -> tuple[bytes, SocketAddress]:
        if self._response is not None:
            response, self._response = self._response, None
            return response, ("fe80::1", 56700, 0, 7)
        await super().receive(timeout)
        raise AssertionError("the no-response transport should time out")


class _UnicastResponseDiscoveryTransport(_SplitScopeResponseDiscoveryTransport):
    """Return a unicast responder after a multi-responder target was queried."""

    async def receive(self, timeout: float = 2.0) -> tuple[bytes, SocketAddress]:
        if self._response is not None:
            response, self._response = self._response, None
            return response, ("192.0.2.10", 56700)
        await super().receive(timeout)
        raise AssertionError("the no-response transport should time out")


class _FailOnUseDiscoveryTransport:
    """Fail immediately if rejected input reaches transport construction."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("rejected input constructed a discovery transport")


class TestFindByIpAddressGate:
    """Public targeted lookup preserves accepted text at its network boundary."""

    @pytest.mark.parametrize(
        ("literal", "expected_sockaddr"),
        [
            pytest.param(
                "2001:db8::1",
                ("2001:db8::1", 56700, 0, 0),
                id="compressed-representation",
            ),
            pytest.param(
                "2001:0db8:0000:0000:0000:0000:0000:0001",
                ("2001:db8::1", 56700, 0, 0),
                id="expanded-representation",
            ),
            pytest.param("fd00::1", ("fd00::1", 56700, 0, 0), id="ula-representation"),
            pytest.param(
                "2001:db8:1::1",
                ("2001:db8:1::1", 56700, 0, 0),
                id="gua-representation",
            ),
            pytest.param("::1", ("::1", 56700, 0, 0), id="loopback-representation"),
            pytest.param(
                "fe80::1%7",
                ("fe80::1", 56700, 0, 7),
                id="zoned-link-local-representation",
            ),
        ],
    )
    async def test_ipv6_representation_reaches_transport_boundary(
        self, literal: str, expected_sockaddr: tuple[str, int, int, int]
    ) -> None:
        """Every accepted spelling reaches the canonical IPv6 send boundary."""
        _ObservedNoResponseDiscoveryTransport.latest = None

        with patch(
            "lifx.network.discovery.UdpTransport",
            _ObservedNoResponseDiscoveryTransport,
        ):
            result = await find_by_ip(
                literal,
                port=56700,
                timeout=0.05,
                max_response_time=0.01,
                idle_timeout_multiplier=1.0,
            )

        observation = _ObservedNoResponseDiscoveryTransport.latest
        assert observation is not None
        assert result is None
        assert observation.ip_address == "::"
        assert observation.broadcast is False
        assert observation.destinations == [expected_sockaddr]

    async def test_split_response_scope_reaches_product_construction(self) -> None:
        """Discovery reconstructs the responder's zone without caller rewriting."""
        captured: list[DiscoveredDevice] = []

        async def _capture_create_device(discovered: DiscoveredDevice) -> None:
            captured.append(discovered)
            return None

        with (
            patch(
                "lifx.network.discovery.UdpTransport",
                _SplitScopeResponseDiscoveryTransport,
            ),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _capture_create_device,
            ),
        ):
            result = await find_by_ip(
                "fe80::1%11",
                port=56700,
                timeout=0.05,
                max_response_time=0.01,
                idle_timeout_multiplier=1.0,
            )

        assert result is None
        assert len(captured) == 1
        assert captured[0].ip == "fe80::1%7"

    async def test_multi_responder_target_keeps_the_unicast_responder(self) -> None:
        """A broadcast lookup never becomes a Device at the broadcast address."""
        captured: list[DiscoveredDevice] = []

        async def _capture_create_device(discovered: DiscoveredDevice) -> None:
            captured.append(discovered)
            return None

        with (
            patch(
                "lifx.network.discovery.UdpTransport",
                _UnicastResponseDiscoveryTransport,
            ),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _capture_create_device,
            ),
        ):
            result = await find_by_ip(
                "255.255.255.255",
                port=56700,
                timeout=0.05,
                max_response_time=0.01,
                idle_timeout_multiplier=1.0,
            )

        assert result is None
        assert len(captured) == 1
        assert captured[0].ip == "192.0.2.10"

    async def test_unzoned_link_local_discovery_fails_before_transport(self) -> None:
        """Every public discovery entry point shares the immediate address gate."""
        with patch(
            "lifx.network.discovery.UdpTransport",
            _FailOnUseDiscoveryTransport,
        ):
            generator = discover(broadcast_address="fe80::1")
            with pytest.raises(ValueError, match="zone identifier"):
                await anext(generator)

    @pytest.mark.parametrize(
        ("literal", "message"),
        [
            pytest.param("", "No IP address provided", id="empty-representation"),
            pytest.param(
                "definitely-not-an-ip-address",
                "Invalid IP address format",
                id="malformed-representation",
            ),
            pytest.param(
                "fe80::1",
                "zone identifier",
                id="bare-link-local-representation",
            ),
            pytest.param(
                "fe80::1%0",
                "zone identifier",
                id="zero-scope-link-local-representation",
            ),
        ],
    )
    async def test_invalid_representation_fails_before_transport(
        self, literal: str, message: str
    ) -> None:
        """Permanent input errors cannot acquire a discovery transport."""
        with patch(
            "lifx.network.discovery.UdpTransport",
            _FailOnUseDiscoveryTransport,
        ):
            with pytest.raises(ValueError, match=message):
                await find_by_ip(literal)
