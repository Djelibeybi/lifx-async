"""Discovery applies endpoint migration to device objects the caller holds."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest

from lifx.api import discover, discover_mdns, discover_udp, find_by_serial
from lifx.devices import Light
from lifx.network.discovery.mdns.discovery import _override_mdns_service_source
from tests.conftest import get_free_port
from tests.test_network.test_endpoint_migration import (
    LOOPBACK,
    SERIAL,
    _emulator_on_new_port,
)


@pytest.fixture(autouse=True)
def _no_ambient_mdns() -> Iterator[None]:
    """Keep the merged and serial lookups independent of real multicast."""

    async def empty_source():
        return
        yield  # noqa: B901 - retain the async-generator ownership shape

    with _override_mdns_service_source(empty_source):
        yield


@pytest.fixture
async def moved() -> AsyncIterator[tuple[Light, int]]:
    """A light first seen on one port, with its emulator now on another."""
    with _emulator_on_new_port() as first:
        light = Light(serial=SERIAL, ip=LOOPBACK, port=first, timeout=2.0)
        async with light:
            await light.get_label()
    with _emulator_on_new_port() as second:
        yield light, second


async def _first(generator) -> Light:
    async for device in generator:
        assert isinstance(device, Light)
        return device
    raise AssertionError("nothing discovered")


class TestDiscoveryMigration:
    async def test_discover_udp_moves_the_existing_object(
        self, moved: tuple[Light, int]
    ) -> None:
        light, port = moved
        found = await _first(
            discover_udp(
                timeout=2.0,
                broadcast_address=LOOPBACK,
                port=port,
                idle_timeout_multiplier=0.5,
                known_devices=[light],
            )
        )
        assert found is light
        assert light.port == port
        async with light:
            await light.get_color()

    async def test_discover_moves_the_existing_object(
        self, moved: tuple[Light, int]
    ) -> None:
        light, port = moved
        found = await _first(
            discover(
                timeout=2.0,
                broadcast_address=LOOPBACK,
                port=port,
                idle_timeout_multiplier=0.5,
                known_devices=[light],
            )
        )
        assert found is light
        assert light.port == port

    async def test_find_by_serial_moves_the_existing_object(
        self, moved: tuple[Light, int]
    ) -> None:
        light, port = moved
        found = await find_by_serial(
            SERIAL,
            timeout=2.0,
            broadcast_address=LOOPBACK,
            port=port,
            idle_timeout_multiplier=0.5,
            device=light,
        )
        assert found is light
        assert light.port == port

    async def test_find_by_serial_without_a_known_object_is_unchanged(
        self, moved: tuple[Light, int]
    ) -> None:
        light, port = moved
        found = await find_by_serial(
            SERIAL,
            timeout=2.0,
            broadcast_address=LOOPBACK,
            port=port,
            idle_timeout_multiplier=0.5,
        )
        assert found is not None
        assert found is not light
        assert light.port != port

    async def test_find_by_serial_not_found_returns_none(self) -> None:
        light = Light(serial=SERIAL, ip=LOOPBACK, port=get_free_port())
        assert (
            await find_by_serial(
                SERIAL,
                timeout=0.5,
                broadcast_address=LOOPBACK,
                port=get_free_port(),
                idle_timeout_multiplier=0.5,
                device=light,
            )
            is None
        )

    async def test_same_address_result_changes_nothing(self) -> None:
        with _emulator_on_new_port() as port:
            light = Light(serial=SERIAL, ip=LOOPBACK, port=port, timeout=2.0)
            found = await _first(
                discover_udp(
                    timeout=2.0,
                    broadcast_address=LOOPBACK,
                    port=port,
                    idle_timeout_multiplier=0.5,
                    known_devices=[light],
                )
            )
            assert found is light
            assert light.connection.address_epoch == 0

    async def test_other_serials_yield_new_objects(
        self, moved: tuple[Light, int]
    ) -> None:
        light, port = moved
        stranger = Light(serial="d073d5000a02", ip=LOOPBACK, port=port)
        found = await _first(
            discover_udp(
                timeout=2.0,
                broadcast_address=LOOPBACK,
                port=port,
                idle_timeout_multiplier=0.5,
                known_devices=[stranger],
            )
        )
        assert found is not stranger
        assert found.serial == SERIAL

    async def test_discover_mdns_moves_the_existing_object(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        light = Light(serial=SERIAL, ip="192.0.2.10", port=56700)
        announced = Light(serial=SERIAL, ip="192.0.2.11", port=56700)

        async def announcements(**_kwargs: object):
            yield announced

        monkeypatch.setattr(
            "lifx.network.discovery.mdns.discovery.discover_devices_mdns",
            announcements,
        )
        found = await _first(discover_mdns(known_devices=[light]))
        assert found is light
        assert light.ip == "192.0.2.11"
        assert light.connection.address_epoch == 1
