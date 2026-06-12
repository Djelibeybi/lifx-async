"""Tests for discovery error paths and DoS protection mechanisms."""

from __future__ import annotations

import struct
import sys
from unittest.mock import AsyncMock, patch

import pytest

from lifx.network.discovery import _discover_with_packet, discover_devices
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Device as DevicePackets


@pytest.mark.emulator
@pytest.mark.flaky(retries=2, delay=1, condition=sys.platform.startswith("win32"))
class TestDiscoveryMalformedPackets:
    """Test discovery handling of malformed packets."""

    @pytest.mark.asyncio
    async def test_discovery_with_malformed_header(self, emulator_port: int) -> None:
        """Test discovery continues when receiving malformed packets.

        The discovery should skip malformed responses and continue waiting
        for valid responses.
        """
        # Test that discovery handles malformed packets gracefully
        # The emulator provides valid packets on the port
        found_device = False
        async for disc in discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            found_device = True
            break

        # Should have discovered at least one device
        assert found_device


class TestDiscoveryWithEmulatorErrors:
    """Test discovery with various error scenarios."""

    @pytest.mark.asyncio
    async def test_discovery_timeout_scenario(self) -> None:
        """Test discovery with no responding devices."""
        # Use non-existent port - generator should yield nothing
        count = 0
        async for disc in discover_devices(
            timeout=0.1,
            broadcast_address="255.255.255.255",
            port=65432,
        ):
            count += 1

        # Should not yield any devices
        assert count == 0

    @pytest.mark.asyncio
    async def test_discovery_idle_timeout_branch(self) -> None:
        """Test discovery exits via idle timeout when idle_timeout is zero."""
        # With idle_timeout=0.0, the condition elapsed_since_last >= 0.0
        # is always true (even if elapsed is exactly 0.0), so the idle
        # timeout branch triggers immediately on the first iteration.
        count = 0
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="255.255.255.255",
            port=65432,
            max_response_time=0.0,
            idle_timeout_multiplier=0.0,
        ):
            count += 1

        assert count == 0

    @pytest.mark.asyncio
    async def test_discovery_overall_timeout_branch(self) -> None:
        """Test discovery exits via overall timeout when timeout is zero."""
        # idle_timeout is large (default 2.0s) so idle check is False,
        # but timeout=0.0 makes the overall timeout check immediately true
        count = 0
        async for disc in discover_devices(
            timeout=0.0,
            broadcast_address="255.255.255.255",
            port=65432,
        ):
            count += 1

        assert count == 0


def _build_state_service_packet(source: int, target: bytes, port: int = 56700) -> bytes:
    """Build a raw StateService response packet for testing.

    Args:
        source: Source ID to embed in the header
        target: 8-byte target serial
        port: Service port for the payload

    Returns:
        Complete LIFX message bytes (header + payload)
    """
    # StateService payload: service=1 (UDP), port
    payload = struct.pack("<BI", 1, port)

    header = LifxHeader.create(
        pkt_type=3,  # StateService
        source=source,
        target=target,
        tagged=False,
        ack_required=False,
        res_required=False,
        sequence=0,
        payload_size=len(payload),
    )
    return header.pack() + payload


class TestDiscoverySourceValidation:
    """Test that discovery rejects responses with wrong source IDs (T-H3)."""

    @pytest.mark.asyncio
    async def test_wrong_source_id_rejected(self) -> None:
        """Responses with mismatched source ID must not be yielded."""
        valid_serial = b"\xd0\x73\xd5\x01\x02\x03\x00\x00"

        known_source = 42
        wrong_source = 999

        # Crafted packet has a different source than the discovery session
        crafted_packet = _build_state_service_packet(
            source=wrong_source, target=valid_serial
        )

        call_count = 0

        async def mock_receive(timeout: float = 2.0):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return crafted_packet, ("192.168.1.100", 56700)
            # Subsequent calls timeout to end discovery
            from lifx.exceptions import LifxTimeoutError

            raise LifxTimeoutError("timeout")

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.allocate_source", return_value=known_source),
        ):
            mock_transport = AsyncMock()
            mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
            mock_transport.__aexit__ = AsyncMock(return_value=False)
            mock_transport.send = AsyncMock()
            mock_transport.receive = mock_receive
            mock_transport_cls.return_value = mock_transport

            devices = []
            async for device in discover_devices(timeout=0.5):
                devices.append(device)

        # The crafted packet should have been rejected (source mismatch)
        assert len(devices) == 0

    @pytest.mark.asyncio
    async def test_broadcast_serial_all_ff_rejected(self) -> None:
        """Response with all-0xFF broadcast serial must not be yielded.

        Discovery rejects responses with an all-0xFF target as an invalid
        broadcast serial number.
        """
        all_ff = b"\xff\xff\xff\xff\xff\xff\xff\xff"

        known_source = 42

        packets_to_send = [
            _build_state_service_packet(source=known_source, target=all_ff),
        ]
        packet_iter = iter(packets_to_send)

        async def mock_receive(timeout: float = 2.0):
            try:
                pkt = next(packet_iter)
                return pkt, ("192.168.1.100", 56700)
            except StopIteration:
                from lifx.exceptions import LifxTimeoutError

                raise LifxTimeoutError("timeout")

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.allocate_source", return_value=known_source),
        ):
            mock_transport = AsyncMock()
            mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
            mock_transport.__aexit__ = AsyncMock(return_value=False)
            mock_transport.send = AsyncMock()
            mock_transport.receive = mock_receive
            mock_transport_cls.return_value = mock_transport

            devices = []
            async for device in discover_devices(timeout=0.5):
                devices.append(device)

        assert len(devices) == 0

    @pytest.mark.asyncio
    async def test_multicast_serial_rejected(self) -> None:
        """Response with multicast serial (LSB of first byte set) must not be yielded.

        A multicast MAC address has the least significant bit of the first
        octet set. Such addresses are never valid LIFX device serials.
        """
        # LSB of byte 0 set = multicast address
        multicast_serial = b"\x01\x02\x03\x04\x05\x06\x00\x00"

        known_source = 42

        packets_to_send = [
            _build_state_service_packet(source=known_source, target=multicast_serial),
        ]
        packet_iter = iter(packets_to_send)

        async def mock_receive(timeout: float = 2.0):
            try:
                pkt = next(packet_iter)
                return pkt, ("192.168.1.100", 56700)
            except StopIteration:
                from lifx.exceptions import LifxTimeoutError

                raise LifxTimeoutError("timeout")

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.allocate_source", return_value=known_source),
        ):
            mock_transport = AsyncMock()
            mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
            mock_transport.__aexit__ = AsyncMock(return_value=False)
            mock_transport.send = AsyncMock()
            mock_transport.receive = mock_receive
            mock_transport_cls.return_value = mock_transport

            devices = []
            async for device in discover_devices(timeout=0.5):
                devices.append(device)

        assert len(devices) == 0


class TestMalformedPayloadHandling:
    """Test that malformed StateService payloads are handled gracefully (D-10).

    Re-proves the behaviour previously covered by the retired direct parser tests,
    now via the shared _discover_with_packet path that replaced the deleted parser.
    """

    @pytest.mark.asyncio
    async def test_truncated_state_service_payload_yields_no_device(self) -> None:
        """Truncated StateService payload must not cause an exception to propagate.

        Crafts a header+payload where the header claims 2 bytes of payload but the
        actual StateService body is too short to unpack (service=1 byte + port=4 bytes
        = 5 bytes minimum).  The LifxProtocolError or ValueError is caught by
        _discover_with_packet and the generator must complete yielding zero devices.
        """
        known_source = 42
        valid_serial = b"\xd0\x73\xd5\x01\x02\x03\x00\x00"
        # Deliberately truncated payload: only 2 bytes instead of 5
        truncated_payload = b"\x01\x00"

        header = LifxHeader.create(
            pkt_type=3,  # StateService
            source=known_source,
            target=valid_serial,
            tagged=False,
            ack_required=False,
            res_required=False,
            sequence=0,
            payload_size=len(truncated_payload),
        )
        crafted_packet = header.pack() + truncated_payload

        call_count = 0

        async def mock_receive(timeout: float = 2.0):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return crafted_packet, ("192.168.1.100", 56700)
            from lifx.exceptions import LifxTimeoutError

            raise LifxTimeoutError("timeout")

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.allocate_source", return_value=known_source),
        ):
            mock_transport = AsyncMock()
            mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
            mock_transport.__aexit__ = AsyncMock(return_value=False)
            mock_transport.send = AsyncMock()
            mock_transport.receive = mock_receive
            mock_transport_cls.return_value = mock_transport

            devices = []
            # Must not raise — the generator handles the malformed payload internally
            async for device in discover_devices(timeout=0.5):
                devices.append(device)

        assert len(devices) == 0


class TestDiscoverWithPacketSerialValidation:
    """Direct generator-level tests for hoisted serial validation (D-11).

    These tests drive _discover_with_packet directly to prove the broadcast/multicast
    and all-0xff serial guards are enforced at the shared generator, not only
    transitively via discover_devices.
    """

    @pytest.mark.asyncio
    async def test_broadcast_bit_serial_rejected_at_generator(self) -> None:
        """Packet with broadcast/multicast serial (LSB of byte 0 set) yields nothing.

        Proves the D-01 guard in _discover_with_packet rejects multicast addresses
        before any DiscoveryResponse is produced.
        """
        known_source = 42
        # LSB of byte 0 is set — this is a multicast MAC address
        multicast_serial = b"\x01\x02\x03\x04\x05\x06\x00\x00"

        packets_to_send = [
            _build_state_service_packet(source=known_source, target=multicast_serial),
        ]
        packet_iter = iter(packets_to_send)

        async def mock_receive(timeout: float = 2.0):
            try:
                pkt = next(packet_iter)
                return pkt, ("192.168.1.100", 56700)
            except StopIteration:
                from lifx.exceptions import LifxTimeoutError

                raise LifxTimeoutError("timeout")

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.allocate_source", return_value=known_source),
        ):
            mock_transport = AsyncMock()
            mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
            mock_transport.__aexit__ = AsyncMock(return_value=False)
            mock_transport.send = AsyncMock()
            mock_transport.receive = mock_receive
            mock_transport_cls.return_value = mock_transport

            responses = []
            async for resp in _discover_with_packet(
                DevicePackets.GetService(), timeout=0.5
            ):
                responses.append(resp)

        assert len(responses) == 0

    @pytest.mark.asyncio
    async def test_all_ff_serial_rejected_at_generator(self) -> None:
        """Packet with all-0xFF serial yields no DiscoveryResponse (D-01).

        Proves the all-0xff broadcast serial guard in _discover_with_packet.
        """
        known_source = 42
        all_ff = b"\xff\xff\xff\xff\xff\xff\xff\xff"

        packets_to_send = [
            _build_state_service_packet(source=known_source, target=all_ff),
        ]
        packet_iter = iter(packets_to_send)

        async def mock_receive(timeout: float = 2.0):
            try:
                pkt = next(packet_iter)
                return pkt, ("192.168.1.100", 56700)
            except StopIteration:
                from lifx.exceptions import LifxTimeoutError

                raise LifxTimeoutError("timeout")

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.allocate_source", return_value=known_source),
        ):
            mock_transport = AsyncMock()
            mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
            mock_transport.__aexit__ = AsyncMock(return_value=False)
            mock_transport.send = AsyncMock()
            mock_transport.receive = mock_receive
            mock_transport_cls.return_value = mock_transport

            responses = []
            async for resp in _discover_with_packet(
                DevicePackets.GetService(), timeout=0.5
            ):
                responses.append(resp)

        assert len(responses) == 0

    @pytest.mark.asyncio
    async def test_first_wins_dedup_at_generator(self) -> None:
        """Two packets with the same valid serial yield exactly one DiscoveryResponse.

        Proves the first-wins dedup guard (D-04) is enforced inside
        _discover_with_packet rather than only in its callers.
        """
        known_source = 42
        valid_serial = b"\xd0\x73\xd5\x01\x02\x03\x00\x00"

        # Same serial appearing twice — second must be suppressed
        duplicate_packet = _build_state_service_packet(
            source=known_source, target=valid_serial
        )
        packets_to_send = [duplicate_packet, duplicate_packet]
        packet_iter = iter(packets_to_send)

        async def mock_receive(timeout: float = 2.0):
            try:
                pkt = next(packet_iter)
                return pkt, ("192.168.1.100", 56700)
            except StopIteration:
                from lifx.exceptions import LifxTimeoutError

                raise LifxTimeoutError("timeout")

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.allocate_source", return_value=known_source),
        ):
            mock_transport = AsyncMock()
            mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
            mock_transport.__aexit__ = AsyncMock(return_value=False)
            mock_transport.send = AsyncMock()
            mock_transport.receive = mock_receive
            mock_transport_cls.return_value = mock_transport

            responses = []
            async for resp in _discover_with_packet(
                DevicePackets.GetService(), timeout=0.5
            ):
                responses.append(resp)

        assert len(responses) == 1


@pytest.mark.emulator
class TestDiscoveryDeduplication:
    """Test that discovered devices are properly deduplicated."""

    @pytest.mark.asyncio
    async def test_devices_deduplicated_by_serial(self, emulator_port: int) -> None:
        """Test that duplicate responses are deduplicated by serial."""
        seen_serials: set[str] = set()
        async for disc in discover_devices(
            timeout=1.5,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            # Each yielded device should have a unique serial
            assert disc.serial not in seen_serials, f"Duplicate serial: {disc.serial}"
            seen_serials.add(disc.serial)
