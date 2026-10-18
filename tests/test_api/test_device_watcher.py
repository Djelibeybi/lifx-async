"""The device watcher: continuous discovery, events and liveness."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from lifx_emulator import EmulatedLifxServer
from lifx_emulator.devices import DeviceManager
from lifx_emulator.factories import create_color_light
from lifx_emulator.repositories import DeviceRepository
from lifx_emulator.scenarios import HierarchicalScenarioManager

from lifx import DeviceEvent, DeviceEventType, DeviceWatcher
from lifx.devices import Light
from lifx.network.discovery.mdns.discovery import _override_mdns_service_source
from lifx.network.discovery.mdns.types import _LifxServiceRecord
from tests.conftest import IPV6_DEVICE_SERIAL, EmulatorRunner, get_free_port

LOOPBACK = "127.0.0.1"
SERIAL_A = "d073d5000b01"
SERIAL_B = "d073d5000b02"


class FakeClock:
    """One source of time for the watcher and every connection."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


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
def _emulator(serials: tuple[str, ...], port: int | None = None) -> Iterator[int]:
    scenario_manager = HierarchicalScenarioManager()
    port = port or get_free_port()
    server = EmulatedLifxServer(
        devices=[
            create_color_light(serial=s, scenario_manager=scenario_manager)
            for s in serials
        ],
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


def _watcher(port: int, **kwargs) -> DeviceWatcher:
    kwargs.setdefault("sweep_interval", 3600.0)
    kwargs.setdefault("discovery_timeout", 0.5)
    kwargs.setdefault("idle_timeout_multiplier", 0.5)
    kwargs.setdefault("device_timeout", 2.0)
    return DeviceWatcher(broadcast_address=LOOPBACK, port=port, **kwargs)


def _drain(watcher: DeviceWatcher) -> list[DeviceEvent]:
    events: list[DeviceEvent] = []
    while (event := watcher.get_event_nowait()) is not None:
        events.append(event)
    return events


class TestAdded:
    async def test_two_devices_added_and_same_objects_returned(self) -> None:
        with _emulator((SERIAL_A, SERIAL_B)) as port:
            async with _watcher(port) as watcher:
                events = _drain(watcher)
                assert [e.type for e in events] == [DeviceEventType.ADDED] * 2
                assert {e.serial for e in events} == {SERIAL_A, SERIAL_B}
                first = watcher.devices
                assert len(first) == 2
                assert {d.serial for d in first} == {SERIAL_A, SERIAL_B}
                assert all(isinstance(d, Light) for d in first)
                assert {id(d) for d in watcher.devices} == {id(d) for d in first}
                assert watcher.get(SERIAL_A) is next(
                    d for d in first if d.serial == SERIAL_A
                )
                assert watcher.get("D073D5000B01") is watcher.get(SERIAL_A)
                assert watcher.get("d073d5ffffff") is None
                assert watcher.get("not a serial") is None
                assert {id(e.device) for e in events} == {id(d) for d in first}

                # A further sweep adds nothing and keeps the objects.
                await watcher.sweep()
                assert _drain(watcher) == []
                assert {id(d) for d in watcher.devices} == {id(d) for d in first}


class TestMoved:
    async def test_restart_on_new_port_is_one_update(self) -> None:
        with _emulator((SERIAL_A,)) as first_port:
            async with _watcher(first_port) as watcher:
                light = watcher.get(SERIAL_A)
                assert light is not None
                _drain(watcher)
                with _emulator((SERIAL_A,)) as second_port:
                    watcher.port = second_port
                    await watcher.sweep()
                events = _drain(watcher)
                assert len(events) == 1
                (event,) = events
                assert event.type is DeviceEventType.UPDATED
                assert event.device is light
                assert set(event.changes) == {"address"}
                assert event.changes["address"] == (
                    (LOOPBACK, first_port),
                    (LOOPBACK, second_port),
                )
                assert light.port == second_port


class TestFieldChanges:
    async def test_label_group_location_and_firmware_changes_are_reported(
        self,
    ) -> None:
        with _emulator((SERIAL_A,)) as port:
            async with _watcher(port) as watcher:
                light = watcher.get(SERIAL_A)
                assert isinstance(light, Light)
                _drain(watcher)
                await light.get_label()
                await light.get_host_firmware()
                await light.get_wifi_firmware()
                await light.get_location()
                await light.get_group()
                await watcher.sweep()
                (event,) = _drain(watcher)
                assert event.type is DeviceEventType.UPDATED
                assert set(event.changes) == {
                    "label",
                    "wifi_firmware",
                    "location",
                    "group",
                }
                old, new = event.changes["label"]
                assert old is None and new == light.label
                await watcher.sweep()
                assert _drain(watcher) == []


class TestLiveness:
    async def test_silent_device_is_removed_and_returns_as_same_object(
        self, clock: FakeClock
    ) -> None:
        port = get_free_port()
        with _emulator((SERIAL_A,), port):
            watcher = _watcher(port, sweep_interval=3600.0, silence_threshold=30.0)
            await watcher.__aenter__()
            light = watcher.get(SERIAL_A)
            assert light is not None
            _drain(watcher)
        try:
            clock.now += 29.0
            await watcher.sweep()
            assert _drain(watcher) == []
            clock.now += 2.0
            await watcher.sweep()
            (removed,) = _drain(watcher)
            assert removed.type is DeviceEventType.REMOVED
            assert removed.device is light
            assert watcher.devices == []
            assert watcher.get(SERIAL_A) is light
            # Still silent: nothing more is said.
            await watcher.sweep()
            assert _drain(watcher) == []
            with _emulator((SERIAL_A,), port):
                clock.now += 5.0
                await watcher.sweep()
                (added,) = _drain(watcher)
            assert added.type is DeviceEventType.ADDED
            assert added.device is light
            assert watcher.devices == [light]
        finally:
            await watcher.__aexit__(None, None, None)

    async def test_default_threshold_is_larger_of_30_and_five_intervals(self) -> None:
        assert DeviceWatcher(sweep_interval=2.0).silence_threshold == 30.0
        assert DeviceWatcher(sweep_interval=30.0).silence_threshold == 150.0
        assert (
            DeviceWatcher(sweep_interval=2.0, silence_threshold=7.0).silence_threshold
            == 7.0
        )

    async def test_answering_device_is_never_silent_even_if_sweeps_miss_it(
        self, clock: FakeClock
    ) -> None:
        with _emulator((SERIAL_A,)) as port:
            async with _watcher(port, silence_threshold=30.0) as watcher:
                light = watcher.get(SERIAL_A)
                assert light is not None
                await light.get_label()
                await watcher.sweep()
                _drain(watcher)
                watcher.port = get_free_port()  # every sweep now misses it
                for _ in range(4):
                    clock.now += 20.0
                    await light.get_label()
                    await watcher.sweep()
                    assert _drain(watcher) == []
                assert watcher.devices == [light]
                clock.now += 31.0
                await watcher.sweep()
                assert [e.type for e in _drain(watcher)] == [DeviceEventType.REMOVED]

    async def test_caller_traffic_revives_a_silent_device(
        self, clock: FakeClock
    ) -> None:
        with _emulator((SERIAL_A,)) as port:
            async with _watcher(port, silence_threshold=30.0) as watcher:
                light = watcher.get(SERIAL_A)
                assert light is not None
                _drain(watcher)
                watcher.port = get_free_port()
                clock.now += 31.0
                await watcher.sweep()
                assert [e.type for e in _drain(watcher)] == [DeviceEventType.REMOVED]
                await light.get_label()
                await watcher.sweep()
                (event,) = _drain(watcher)
                assert event.type is DeviceEventType.ADDED
                assert event.device is light


class TestQueue:
    async def test_full_queue_drops_oldest_and_counts(self) -> None:
        with _emulator((SERIAL_A, SERIAL_B)) as port:
            async with _watcher(port, max_queue_size=1) as watcher:
                assert watcher.dropped_events == 1
                (event,) = _drain(watcher)
                assert event.type is DeviceEventType.ADDED
                # The sweep itself is not held up by the unread queue.
                await asyncio.wait_for(watcher.sweep(), timeout=5.0)

    def test_queue_size_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            DeviceWatcher(max_queue_size=0)

    def test_sweep_interval_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            DeviceWatcher(sweep_interval=0)


class TestConsumption:
    async def test_iterator_and_callbacks_receive_every_event_in_order(
        self, clock: FakeClock
    ) -> None:
        seen: list[DeviceEvent] = []
        port = get_free_port()
        with _emulator((SERIAL_A,), port):
            watcher = _watcher(port, silence_threshold=30.0)
            remove = watcher.add_listener(seen.append)
            second: list[DeviceEvent] = []
            watcher.add_listener(second.append)
            await watcher.__aenter__()
        clock.now += 31.0
        await watcher.sweep()
        remove()
        with _emulator((SERIAL_A,), port):
            await watcher.sweep()
        await watcher.__aexit__(None, None, None)

        iterated = [event async for event in watcher]
        assert [e.type for e in iterated] == [
            DeviceEventType.ADDED,
            DeviceEventType.REMOVED,
            DeviceEventType.ADDED,
        ]
        assert [e.type for e in seen] == [
            DeviceEventType.ADDED,
            DeviceEventType.REMOVED,
        ]
        assert second == iterated

    async def test_a_failing_callback_does_not_stop_delivery(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        def boom(event: DeviceEvent) -> None:
            raise RuntimeError("consumer bug")

        seen: list[DeviceEvent] = []
        with _emulator((SERIAL_A,)) as port:
            watcher = _watcher(port)
            watcher.add_listener(boom)
            watcher.add_listener(seen.append)
            with caplog.at_level(logging.ERROR):
                async with watcher:
                    pass
        assert len(seen) == 1
        assert "consumer bug" in caplog.text

    async def test_iterator_waits_for_the_next_event(self) -> None:
        with _emulator((SERIAL_A,)) as port:
            async with _watcher(port) as watcher:
                _drain(watcher)
                waiter = asyncio.ensure_future(anext(watcher))
                await asyncio.sleep(0.05)
                assert not waiter.done()
                with _emulator((SERIAL_A,)) as second:
                    watcher.port = second
                    await watcher.sweep()
                event = await asyncio.wait_for(waiter, timeout=2.0)
                assert event.type is DeviceEventType.UPDATED


class TestMdns:
    async def test_ipv6_device_found_only_by_mdns_is_tracked(self) -> None:
        with _emulator((IPV6_DEVICE_SERIAL,)) as port:
            record = _LifxServiceRecord(
                serial=IPV6_DEVICE_SERIAL,
                ip=LOOPBACK,
                port=port,
                product_id=27,
                firmware="4.112",
                connectivity="thread",
                service_instance="device._lifx._udp.local",
            )

            async def source():
                yield record

            with _override_mdns_service_source(source):
                unused = get_free_port()
                async with _watcher(unused, mdns=True) as watcher:
                    (event,) = _drain(watcher)
                    assert event.type is DeviceEventType.ADDED
                    assert event.serial == IPV6_DEVICE_SERIAL
                    assert watcher.devices == [event.device]

    async def test_mdns_is_off_by_default(self) -> None:
        asked = False

        async def source():
            nonlocal asked
            asked = True
            return
            yield  # noqa: B901

        with _override_mdns_service_source(source):
            async with _watcher(get_free_port()):
                pass
        assert asked is False


class TestLifecycle:
    async def test_exit_cancels_sweeps_and_leaves_devices_usable(self) -> None:
        with _emulator((SERIAL_A,)) as port:
            async with _watcher(port, sweep_interval=0.05) as watcher:
                assert watcher.running
                light = watcher.get(SERIAL_A)
                assert light is not None
                await light.get_label()
            assert not watcher.running
            sweeps = watcher.sweep_count
            await asyncio.sleep(0.2)
            assert watcher.sweep_count == sweeps
            # The caller still holds a working object.
            await light.get_color()
            await light.connection.close()

    async def test_periodic_sweeps_run_and_survive_a_failing_sweep(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        calls = 0

        async def flaky(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("socket gone")
            return
            yield  # noqa: B901

        with patch("lifx.watcher.discover_udp", flaky):
            with caplog.at_level(logging.WARNING):
                async with DeviceWatcher(
                    broadcast_address=LOOPBACK, sweep_interval=0.05
                ) as watcher:
                    for _ in range(100):
                        if calls >= 4:
                            break
                        await asyncio.sleep(0.05)
        assert calls >= 4
        assert watcher.sweep_count >= 3
        assert "socket gone" in caplog.text

    async def test_the_periodic_task_survives_a_sweep_that_raises(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        polls = 0

        async def poll(self_: DeviceWatcher) -> None:
            nonlocal polls
            polls += 1
            if polls == 2:
                raise RuntimeError("poll bug")

        with patch.object(DeviceWatcher, "_poll_devices", poll):
            with caplog.at_level(logging.WARNING):
                async with _watcher(get_free_port(), sweep_interval=0.05):
                    for _ in range(100):
                        if polls >= 4:
                            break
                        await asyncio.sleep(0.05)
        assert polls >= 4
        assert "poll bug" in caplog.text

    async def test_exit_without_entry_is_harmless(self) -> None:
        watcher = _watcher(get_free_port())
        await watcher.__aexit__(None, None, None)
        assert not watcher.running

    async def test_removing_a_listener_twice_is_harmless(self) -> None:
        watcher = _watcher(get_free_port())
        remove = watcher.add_listener(lambda event: None)
        remove()
        remove()

    async def test_cannot_enter_twice(self) -> None:
        watcher = _watcher(get_free_port())
        async with watcher:
            with pytest.raises(RuntimeError):
                await watcher.__aenter__()

    async def test_sweep_requires_an_open_watcher(self) -> None:
        with pytest.raises(RuntimeError):
            await _watcher(get_free_port()).sweep()

    async def test_iterator_ends_when_closed_and_drained(self) -> None:
        async with _watcher(get_free_port()) as watcher:
            pass
        assert [e async for e in watcher] == []
