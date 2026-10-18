"""Opt-in state polling on the device watcher."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from lifx_emulator import EmulatedLifxServer
from lifx_emulator.devices import DeviceManager
from lifx_emulator.factories import (
    create_color_light,
    create_multizone_light,
    create_tile_device,
)
from lifx_emulator.repositories import DeviceRepository
from lifx_emulator.scenarios import HierarchicalScenarioManager

from lifx import DeviceEvent, DeviceEventType, DeviceWatcher
from lifx.devices import Device
from lifx.network.discovery.mdns.discovery import _override_mdns_service_source
from tests.conftest import EmulatorRunner, get_free_port
from tests.test_api.test_device_watcher import (
    SERIAL_A,
    SERIAL_B,
    FakeClock,
    _drain,
)

LOOPBACK = "127.0.0.1"
SERIAL_Z = "d073d5000b03"
SERIAL_T = "d073d5000b04"

GET_SERVICE = 2
GET_VERSION = 32
GET_LABEL = 23
GET_COLOR = 101
GET_GROUP = 51
GET_LOCATION = 48
GET_HOST_FIRMWARE = 14
GET_WIFI_FIRMWARE = 18
GET_EXTENDED_COLOR_ZONES = 511
GET64 = 707


@pytest.fixture
def clock() -> Iterator[FakeClock]:
    fake = FakeClock()
    with patch("lifx.network.connection.monotonic_now", fake):
        yield fake


@pytest.fixture(autouse=True)
def _no_ambient_mdns() -> Iterator[None]:
    async def empty_source():
        return
        yield  # noqa: B901

    with _override_mdns_service_source(empty_source):
        yield


@contextmanager
def _emulator(*devices) -> Iterator[tuple[int, EmulatedLifxServer]]:
    scenario_manager = HierarchicalScenarioManager()
    port = get_free_port()
    server = EmulatedLifxServer(
        devices=list(devices),
        device_manager=DeviceManager(DeviceRepository()),
        bind_address=LOOPBACK,
        port=port,
        scenario_manager=scenario_manager,
    )
    runner = EmulatorRunner(server)
    runner.start()
    try:
        yield port, server
    finally:
        runner.stop()


def _lights(*serials: str):
    return [create_color_light(serial=s) for s in serials]


def _watcher(port: int, **kwargs) -> DeviceWatcher:
    kwargs.setdefault("sweep_interval", 3600.0)
    kwargs.setdefault("discovery_timeout", 0.5)
    kwargs.setdefault("idle_timeout_multiplier", 0.5)
    kwargs.setdefault("device_timeout", 2.0)
    return DeviceWatcher(broadcast_address=LOOPBACK, port=port, **kwargs)


def _counts(server: EmulatedLifxServer) -> dict[int, int]:
    return dict(server.packets_received_by_type)


def _delta(before: dict[int, int], server: EmulatedLifxServer) -> dict[int, int]:
    after = _counts(server)
    return {k: v - before.get(k, 0) for k, v in after.items() if v != before.get(k, 0)}


def _updates(events: list[DeviceEvent]) -> list[DeviceEvent]:
    return [e for e in events if e.type is DeviceEventType.UPDATED]


class TestOff:
    async def test_both_flags_off_send_only_discovery_traffic(self, clock) -> None:
        with _emulator(*_lights(SERIAL_A)) as (port, server):
            async with _watcher(port) as watcher:
                await watcher.sweep()  # construction traffic settles
                before = _counts(server)
                clock.now += 10_000.0
                await watcher.sweep()
                clock.now += 10_000.0
                await watcher.sweep()
                delta = _delta(before, server)
                # Each sweep re-verifies the device (version and firmware, once
                # per sweep); nothing else is sent.
                assert set(delta) == {GET_SERVICE, GET_VERSION, GET_HOST_FIRMWARE}
                assert delta[GET_VERSION] == delta[GET_HOST_FIRMWARE] == 2


class TestHighFrequency:
    async def test_external_color_change_is_reflected_and_reported(self, clock) -> None:
        with _emulator(*_lights(SERIAL_A)) as (port, server):
            async with _watcher(port, high_frequency_polling=True) as watcher:
                assert _updates(_drain(watcher)) == []
                server.get_device(SERIAL_A).state.color.hue = 12345
                clock.now += 11.0
                await watcher.sweep()
                (event,) = _updates(_drain(watcher))
                assert set(event.changes) == {"color"}
                old, new = event.changes["color"]
                assert old != new
                light = watcher.get(SERIAL_A)
                assert light is not None
                assert light._discovery_snapshot is not None
                assert light._discovery_snapshot.colour == new
                # Nothing changed since: the next poll reports nothing.
                clock.now += 11.0
                await watcher.sweep()
                assert _updates(_drain(watcher)) == []

    async def test_power_change_is_reported(self, clock) -> None:
        with _emulator(*_lights(SERIAL_A)) as (port, server):
            async with _watcher(port, high_frequency_polling=True) as watcher:
                _drain(watcher)
                state = server.get_device(SERIAL_A).state
                state.power_level = 0 if state.power_level else 65535
                clock.now += 11.0
                await watcher.sweep()
                (event,) = _updates(_drain(watcher))
                assert set(event.changes) == {"power"}

    async def test_multizone_zones_are_polled(self, clock) -> None:
        zone_light = create_multizone_light(serial=SERIAL_Z, zone_count=8)
        with _emulator(zone_light) as (port, server):
            async with _watcher(port, high_frequency_polling=True) as watcher:
                _drain(watcher)
                server.get_device(SERIAL_Z).state.zone_colors[3].hue = 4242
                clock.now += 11.0
                await watcher.sweep()
                (event,) = _updates(_drain(watcher))
                assert "zones" in event.changes

    async def test_matrix_tiles_are_polled(self, clock) -> None:
        tile = create_tile_device(serial=SERIAL_T)
        with _emulator(tile) as (port, server):
            async with _watcher(port, high_frequency_polling=True) as watcher:
                _drain(watcher)
                server.get_device(SERIAL_T).state.tile_devices[0]["colors"][0].hue = 99
                clock.now += 11.0
                await watcher.sweep()
                (event,) = _updates(_drain(watcher))
                assert set(event.changes) == {"tiles"}

    async def test_cadence_follows_the_interval(self, clock) -> None:
        with _emulator(*_lights(SERIAL_A)) as (port, server):
            async with _watcher(
                port, high_frequency_polling=True, high_frequency_interval=60.0
            ) as watcher:
                before = _counts(server)
                clock.now += 59.0
                await watcher.sweep()
                assert GET_COLOR not in _delta(before, server)
                clock.now += 2.0
                await watcher.sweep()
                assert _delta(before, server).get(GET_COLOR) == 1
                clock.now += 30.0
                await watcher.sweep()
                assert _delta(before, server).get(GET_COLOR) == 1
                clock.now += 31.0
                await watcher.sweep()
                assert _delta(before, server).get(GET_COLOR) == 2

    async def test_interval_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="high_frequency_interval"):
            DeviceWatcher(high_frequency_interval=0)
        with pytest.raises(ValueError, match="low_frequency_interval"):
            DeviceWatcher(low_frequency_interval=-1)


class TestThread:
    async def test_thread_device_needs_the_opt_in(self, clock) -> None:
        for opt_in in (False, True):
            with _emulator(*_lights(SERIAL_A)) as (port, server):
                async with _watcher(
                    port, high_frequency_polling=True, enable_thread=opt_in
                ) as watcher:
                    light = watcher.get(SERIAL_A)
                    assert light is not None
                    light.connection._adopt_thread_connection(True)
                    before = _counts(server)
                    clock.now += 11.0
                    await watcher.sweep()
                    polled = _delta(before, server).get(GET_COLOR, 0)
                    assert polled == (1 if opt_in else 0)

    async def test_low_frequency_skips_wifi_firmware_on_thread(self, clock) -> None:
        with _emulator(*_lights(SERIAL_A)) as (port, server):
            async with _watcher(port, low_frequency_polling=True) as watcher:
                light = watcher.get(SERIAL_A)
                assert light is not None
                light.connection._adopt_thread_connection(True)
                before = _counts(server)
                clock.now += 301.0
                await watcher.sweep()
                delta = _delta(before, server)
                assert GET_WIFI_FIRMWARE not in delta
                assert delta.get(GET_HOST_FIRMWARE) == 2  # sweep re-verify plus poll


class TestLowFrequency:
    async def test_label_change_is_reported(self, clock) -> None:
        with _emulator(*_lights(SERIAL_A)) as (port, server):
            async with _watcher(port, low_frequency_polling=True) as watcher:
                _drain(watcher)
                server.get_device(SERIAL_A).state.label = "Renamed"
                before = _counts(server)
                clock.now += 301.0
                await watcher.sweep()
                (event,) = _updates(_drain(watcher))
                # The emulator reports a fresh wifi build on every query.
                assert "label" in event.changes
                assert event.changes["label"][1] == "Renamed"
                assert {
                    GET_LABEL,
                    GET_HOST_FIRMWARE,
                    GET_WIFI_FIRMWARE,
                    GET_GROUP,
                    GET_LOCATION,
                } <= set(_delta(before, server))
                assert GET_COLOR not in _delta(before, server)

    async def test_cadence_follows_the_interval(self, clock) -> None:
        with _emulator(*_lights(SERIAL_A)) as (port, server):
            async with _watcher(
                port, low_frequency_polling=True, low_frequency_interval=100.0
            ) as watcher:
                before = _counts(server)
                clock.now += 99.0
                await watcher.sweep()
                assert GET_LABEL not in _delta(before, server)
                clock.now += 2.0
                await watcher.sweep()
                assert _delta(before, server).get(GET_LABEL) == 1


class TestFailures:
    async def test_one_failing_device_does_not_stop_the_others(
        self, clock, caplog: pytest.LogCaptureFixture
    ) -> None:
        with _emulator(*_lights(SERIAL_A, SERIAL_B)) as (port, server):
            async with _watcher(
                port, high_frequency_polling=True, low_frequency_polling=True
            ) as watcher:
                _drain(watcher)
                bad = watcher.get(SERIAL_A)
                assert bad is not None
                server.get_device(SERIAL_B).state.color.hue = 777
                before = _counts(server)
                clock.now += 301.0
                real = type(bad).get_color
                with (
                    patch.object(type(bad), "get_color", autospec=True) as get_color,
                    caplog.at_level(logging.WARNING),
                ):

                    async def flaky(self):
                        if self.serial == SERIAL_A:
                            raise RuntimeError("poll blew up")
                        return await real(self)

                    get_color.side_effect = flaky
                    patched_label = patch.object(
                        type(bad), "get_label", side_effect=RuntimeError("no label")
                    )
                    with patched_label:
                        await watcher.sweep()
                events = _drain(watcher)
                updates = _updates(events)
                colored = {e.serial for e in updates if "color" in e.changes}
                assert colored == {SERIAL_B}
                assert "poll blew up" in caplog.text
                assert "no label" in caplog.text
                assert _delta(before, server).get(GET_COLOR, 0) >= 1
                # A failed poll is not silence.
                assert bad in watcher.devices

    async def test_poll_failure_does_not_mark_silent_before_threshold(
        self, clock
    ) -> None:
        with _emulator(*_lights(SERIAL_A)) as (port, server):
            async with _watcher(
                port, high_frequency_polling=True, silence_threshold=100.0
            ) as watcher:
                _drain(watcher)
                light = watcher.get(SERIAL_A)
                assert light is not None
                clock.now += 50.0
                with patch.object(
                    type(light), "get_color", side_effect=RuntimeError("nope")
                ):
                    await watcher.sweep()
                assert _drain(watcher) == []

    async def test_silent_devices_are_not_polled(self, clock) -> None:
        with _emulator(*_lights(SERIAL_A)) as (port, _server):
            watcher = _watcher(
                port,
                high_frequency_polling=True,
                silence_threshold=100.0,
                device_timeout=0.2,
                max_retries=0,
                discovery_timeout=0.5,
            )
            await watcher.__aenter__()
        try:
            _drain(watcher)
            clock.now += 200.0
            await watcher.sweep()
            assert [e.type for e in _drain(watcher)] == [DeviceEventType.REMOVED]
            clock.now += 200.0
            with patch("lifx.devices.light.Light.get_color") as get_color:
                await watcher.sweep()
            assert get_color.call_count == 0
        finally:
            await watcher.__aexit__(None, None, None)

    async def test_non_light_devices_are_skipped(self, clock) -> None:
        with _emulator(*_lights(SERIAL_A)) as (port, server):
            async with _watcher(port, high_frequency_polling=True) as watcher:
                plain = Device(serial=SERIAL_A, ip=LOOPBACK, port=port)
                before = _counts(server)
                await watcher._poll_high(SERIAL_A, plain)
                assert _delta(before, server) == {}


class TestPeriodicPolls:
    async def test_polls_run_between_sweeps(self) -> None:
        with _emulator(*_lights(SERIAL_A)) as (port, server):
            async with _watcher(
                port, high_frequency_polling=True, high_frequency_interval=0.05
            ) as watcher:
                assert watcher._poll_task is not None
                server.get_device(SERIAL_A).state.color.hue = 4321
                for _ in range(100):
                    if _updates(_drain(watcher)):
                        break
                    await asyncio.sleep(0.05)
                else:
                    pytest.fail("no poll-driven update")
            assert watcher._poll_task is None

    async def test_a_failing_periodic_poll_is_logged_and_survived(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with _emulator(*_lights(SERIAL_A)) as (port, server):
            async with _watcher(
                port, low_frequency_polling=True, low_frequency_interval=0.05
            ) as watcher:
                with (
                    patch.object(watcher, "_poll_devices", side_effect=ValueError("x")),
                    caplog.at_level(logging.WARNING),
                ):
                    for _ in range(100):
                        if "poll failed" in caplog.text:
                            break
                        await asyncio.sleep(0.05)
                assert "poll failed" in caplog.text
                assert watcher._poll_task is not None
                assert not watcher._poll_task.done()
