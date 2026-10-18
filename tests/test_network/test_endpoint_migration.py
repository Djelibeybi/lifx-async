"""Endpoint migration: a device that moves keeps working through its object.

The connection owns the mechanism (address epoch, send address, stale-reply
rejection) and the device owns the public hook, ``Device.update_address()``.
Both are driven here against the embedded emulator restarted on a new port with
the same serial, plus a raw UDP socket standing in for the address a device
moved away from.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from lifx_emulator import EmulatedLifxServer
from lifx_emulator.devices import DeviceManager
from lifx_emulator.factories import create_color_light
from lifx_emulator.repositories import DeviceRepository
from lifx_emulator.scenarios import HierarchicalScenarioManager

from lifx.color import HSBK
from lifx.devices import Light
from lifx.devices.base import Connectivity
from lifx.exceptions import LifxConnectionError
from lifx.network.connection import DeviceConnection
from lifx.network.message import create_message
from lifx.protocol import packets
from lifx.protocol.header import LifxHeader
from lifx.protocol.models import Serial
from tests.conftest import IPV6_DEVICE_SERIAL, EmulatorRunner, get_free_port

SERIAL = "d073d5000a01"
LOOPBACK = "127.0.0.1"


@contextmanager
def _emulator_on_new_port(serial: str = SERIAL) -> Iterator[int]:
    """Run one emulated colour light on a fresh port and yield that port."""
    scenario_manager = HierarchicalScenarioManager()
    port = get_free_port()
    server = EmulatedLifxServer(
        devices=[create_color_light(serial=serial, scenario_manager=scenario_manager)],
        device_manager=DeviceManager(DeviceRepository()),
        bind_address=LOOPBACK,
        port=port,
        scenario_manager=scenario_manager,
    )
    runner = EmulatorRunner(server)
    runner.start()
    try:
        yield port
    finally:
        runner.stop()


@contextmanager
def _silent_socket() -> Iterator[socket.socket]:
    """A UDP socket on loopback that receives requests and never answers."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LOOPBACK, 0))
    sock.setblocking(False)
    try:
        yield sock
    finally:
        sock.close()


async def _receive(sock: socket.socket) -> tuple[bytes, tuple[str, int]]:
    """Receive one datagram without the 3.11-only ``loop.sock_recvfrom``.

    The socket is read from a worker thread with a socket timeout, which
    works on every supported Python version and event loop.
    """
    loop = asyncio.get_running_loop()
    sock.settimeout(5.0)
    return await loop.run_in_executor(None, sock.recvfrom, 2048)


def _send(sock: socket.socket, data: bytes, client: tuple[str, int]) -> None:
    """Send one datagram; UDP ``sendto`` never blocks on loopback."""
    sock.sendto(data, client)


def _state_label(request: bytes, label: str) -> bytes:
    """Craft a StateLabel reply that correlates with ``request``."""
    header = LifxHeader.unpack(request)
    return create_message(
        packet=packets.Device.StateLabel(label=label.encode()),
        source=header.source,
        sequence=header.sequence,
        target=Serial.from_string(SERIAL).to_protocol(),
    )


@pytest.fixture
async def migrated_light() -> AsyncIterator[tuple[Light, int, int]]:
    """A connected light whose emulator is replaced by one on another port."""
    with _emulator_on_new_port() as first_port:
        light = Light(serial=SERIAL, ip=LOOPBACK, port=first_port, timeout=2.0)
        async with light:
            await light.get_label()
            await light.get_version()
            await light.get_host_firmware()
            await light.get_location()
            await light.get_group()
        second_port = get_free_port()
        while second_port == first_port:  # pragma: no cover
            second_port = get_free_port()
    yield light, first_port, second_port


class TestConnectionAddressUpdate:
    """DeviceConnection.update_address(): the connection-level operation."""

    def test_epoch_starts_at_zero_and_counts_moves(self) -> None:
        conn = DeviceConnection(SERIAL, "192.0.2.10", 56700)
        assert conn.address_epoch == 0
        assert conn.update_address("192.0.2.11", 56700) is True
        assert conn.address_epoch == 1
        assert (conn.ip, conn.port) == ("192.0.2.11", 56700)
        assert conn.update_address("192.0.2.11", 56701) is True
        assert conn.address_epoch == 2
        assert (conn.ip, conn.port) == ("192.0.2.11", 56701)

    def test_same_address_is_a_noop(self, caplog: pytest.LogCaptureFixture) -> None:
        conn = DeviceConnection(SERIAL, "192.0.2.10", 56700)
        with caplog.at_level(logging.DEBUG):
            assert conn.update_address("192.0.2.10", 56700) is False
        assert conn.address_epoch == 0
        assert caplog.records == []

    def test_invalid_address_raises_and_changes_nothing(self) -> None:
        conn = DeviceConnection(SERIAL, "192.0.2.10", 56700)
        with pytest.raises(ValueError):
            conn.update_address("not-an-ip", 56700)
        with pytest.raises(ValueError):
            conn.update_address("192.0.2.11", 80)
        assert conn.address_epoch == 0
        assert (conn.ip, conn.port) == ("192.0.2.10", 56700)

    def test_ipv6_zone_change_is_a_move(self) -> None:
        conn = DeviceConnection(SERIAL, "fe80::1%1", 56700)
        assert conn.update_address("fe80::1%1", 56700) is False
        assert conn.update_address("fe80::1%2", 56700) is True
        assert conn.address_epoch == 1
        assert conn.ip == "fe80::1%2"

    def test_zone_spelled_differently_is_the_same_address(self) -> None:
        conn = DeviceConnection(SERIAL, "fe80::1%1", 56700)
        assert conn.update_address("FE80:0::1%1", 56700) is False
        assert conn.address_epoch == 0

    def test_observed_transport_survives(self) -> None:
        conn = DeviceConnection(SERIAL, "192.0.2.10", 56700)
        conn._thread_connection = True
        conn.update_address("192.0.2.11", 56700)
        assert conn.thread_connection is True


class TestDeviceMigration:
    """Device.update_address() and the stale-reply rules, on a real socket."""

    async def test_restarted_emulator_on_new_port_is_reached(
        self, migrated_light: tuple[Light, int, int]
    ) -> None:
        light, _, _ = migrated_light
        with _emulator_on_new_port() as new_port:
            assert light.update_address(LOOPBACK, new_port) is True
            assert (light.ip, light.port) == (LOOPBACK, new_port)
            async with light:
                await light.set_color(
                    HSBK(hue=120, saturation=1, brightness=0.5, kelvin=3500)
                )
                color, _power, _label = await light.get_color()
            assert color.hue == pytest.approx(120, abs=1)

    async def test_open_connection_follows_the_move(self) -> None:
        with _emulator_on_new_port() as first, _emulator_on_new_port() as second:
            async with Light(
                serial=SERIAL, ip=LOOPBACK, port=first, timeout=2.0
            ) as light:
                await light.get_label()
                assert light.update_address(LOOPBACK, second) is True
                await light.set_color(
                    HSBK(hue=240, saturation=1, brightness=0.5, kelvin=3500)
                )
                color, _power, _label = await light.get_color()
                assert color.hue == pytest.approx(240, abs=1)

    async def test_same_address_changes_nothing(
        self, migrated_light: tuple[Light, int, int], caplog: pytest.LogCaptureFixture
    ) -> None:
        light, first, _ = migrated_light
        with caplog.at_level(logging.DEBUG):
            assert light.update_address(LOOPBACK, first) is False
        assert light.connection.address_epoch == 0
        assert not [r for r in caplog.records if "address_updated" in str(r.msg)]

    async def test_cached_values_survive_the_move(
        self, migrated_light: tuple[Light, int, int]
    ) -> None:
        light, _, second = migrated_light
        label, version, firmware = light._label, light._version, light._host_firmware
        location, group = light._location, light._group
        connectivity = light.connectivity
        light.connection._thread_connection = False
        light.update_address(LOOPBACK, second)
        assert light._label == label is not None
        assert light._version is version is not None
        assert light._host_firmware is firmware is not None
        assert light._location is location is not None
        assert light._group is group is not None
        assert light.connectivity == connectivity == Connectivity.WIFI
        assert light.connection.thread_connection is False

    async def test_move_triggers_no_traffic(self) -> None:
        with _silent_socket() as old, _silent_socket() as new:
            light = Light(serial=SERIAL, ip=LOOPBACK, port=old.getsockname()[1])
            try:
                await light.connection.open()
                light.update_address(LOOPBACK, new.getsockname()[1])
                await asyncio.sleep(0.3)
            finally:
                await light.connection.close()
            with pytest.raises(BlockingIOError):
                old.recvfrom(2048)
            with pytest.raises(BlockingIOError):
                new.recvfrom(2048)

    async def test_request_started_before_the_move_completes_after_it(
        self,
    ) -> None:
        with (
            patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.05,)),
            _silent_socket() as old,
            _emulator_on_new_port() as new_port,
        ):
            conn = DeviceConnection(SERIAL, LOOPBACK, old.getsockname()[1])
            try:
                request = asyncio.create_task(
                    conn.request(packets.Device.GetLabel(), timeout=5.0)
                )
                await _receive(old)  # the request is in flight at the old address
                conn.update_address(LOOPBACK, new_port)
                state = await asyncio.wait_for(request, timeout=5.0)
                assert state.label
            finally:
                await conn.close()

    async def test_reply_from_the_old_address_is_dropped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with (
            patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.3,)),
            _silent_socket() as old,
            _emulator_on_new_port() as new_port,
            caplog.at_level(logging.DEBUG, logger="lifx.network.connection"),
        ):
            conn = DeviceConnection(SERIAL, LOOPBACK, old.getsockname()[1])
            try:
                request = asyncio.create_task(
                    conn.request(packets.Device.GetLabel(), timeout=5.0)
                )
                data, client = await _receive(old)
                conn.update_address(LOOPBACK, new_port)
                # A late reply from the address the device moved away from.
                _send(old, _state_label(data, "stale"), client)
                state = await asyncio.wait_for(request, timeout=5.0)
                assert state.label != "stale"
                assert any(
                    "stale_epoch_response" in str(record.msg)
                    for record in caplog.records
                )
            finally:
                await conn.close()

    async def test_old_address_is_accepted_again_when_the_device_returns(
        self,
    ) -> None:
        with _silent_socket() as old, _emulator_on_new_port() as other:
            conn = DeviceConnection(SERIAL, LOOPBACK, old.getsockname()[1])
            try:
                request = asyncio.create_task(
                    conn.request(packets.Device.GetLabel(), timeout=5.0)
                )
                data, client = await _receive(old)
                conn.update_address(LOOPBACK, other)
                conn.update_address(LOOPBACK, old.getsockname()[1])
                _send(old, _state_label(data, "back"), client)
                state = await asyncio.wait_for(request, timeout=5.0)
                assert state.label == "back"
            finally:
                await conn.close()

    async def test_unrelated_sources_keep_their_existing_handling(self) -> None:
        # Before any move nothing is filtered by source: the serial and
        # sequence correlation stays the only gate.
        with _silent_socket() as old:
            conn = DeviceConnection(SERIAL, LOOPBACK, old.getsockname()[1])
            try:
                request = asyncio.create_task(
                    conn.request(packets.Device.GetLabel(), timeout=5.0)
                )
                data, client = await _receive(old)
                _send(old, _state_label(data, "ok"), client)
                assert (await request).label == "ok"
            finally:
                await conn.close()

    async def test_ipv4_to_ipv6_move_rebinds_the_socket(
        self, emulator_server_ipv6: tuple[int, EmulatedLifxServer]
    ) -> None:
        port6, _ = emulator_server_ipv6
        with _emulator_on_new_port(IPV6_DEVICE_SERIAL) as port4:
            async with Light(
                serial=IPV6_DEVICE_SERIAL, ip=LOOPBACK, port=port4, timeout=3.0
            ) as light:
                await light.get_label()
                assert light.update_address("::1", port6) is True
                await light.get_label()
                assert light.update_address(LOOPBACK, port4) is True
                await light.get_label()

    async def test_a_flapping_device_keeps_bounded_memory(self) -> None:
        conn = DeviceConnection(SERIAL, "192.0.2.10", 56700)
        for index in range(40):
            conn.update_address("192.0.2.11", 56701 + index)
        assert conn.address_epoch == 40
        assert len(conn._retired_endpoints) == 16

    async def test_unresolvable_original_endpoint_can_be_replaced(self) -> None:
        conn = DeviceConnection(SERIAL, "not-an-ip", 56700)
        assert conn.update_address("192.0.2.11", 56700) is True
        assert conn.address_epoch == 1
        assert len(conn._retired_endpoints) == 0

    async def test_close_during_rebind_fails_the_send(self) -> None:
        with _emulator_on_new_port() as port:
            conn = DeviceConnection(SERIAL, LOOPBACK, port)
            await conn.open()
            real_rebind = conn._rebind_transport

            async def close_then_rebind(address):
                await conn.close()
                await real_rebind(address)

            try:
                conn.update_address("::1", port)
                with (
                    patch.object(conn, "_rebind_transport", close_then_rebind),
                    pytest.raises(LifxConnectionError),
                ):
                    await conn.send_packet(packets.Device.GetLabel())
            finally:
                await conn.close()

    async def test_concurrent_senders_rebind_once(self) -> None:
        with _emulator_on_new_port() as port:
            conn = DeviceConnection(SERIAL, LOOPBACK, port)
            await conn.open()
            try:
                conn.update_address("::1", port)
                first = conn._transport
                await asyncio.gather(
                    conn.send_packet(packets.Device.GetLabel()),
                    conn.send_packet(packets.Device.GetLabel()),
                )
                assert conn._transport is not first
                assert conn._transport_family == socket.AF_INET6
            finally:
                await conn.close()

    async def test_move_while_opening_uses_the_new_endpoint(self) -> None:
        with _emulator_on_new_port() as port:
            conn = DeviceConnection(SERIAL, "192.0.2.10", 56700)
            opening = asyncio.create_task(conn.open())
            await asyncio.sleep(0)
            conn.update_address(LOOPBACK, port)
            await opening
            try:
                assert (await conn.request(packets.Device.GetLabel())).label
            finally:
                await conn.close()
