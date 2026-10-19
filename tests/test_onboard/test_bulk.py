"""Tests for bulk_onboard(): serial attempts, termination, interleaved verification."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from lifx import DeviceEventType
from lifx.onboard import (
    HomeNetwork,
    HostRejoinError,
    InvalidSoftApTargetError,
    OnboardEvent,
    OnboardEventQueue,
    OnboardEventType,
    OnboardPhase,
    Result,
    SoftApNotFoundError,
    SoftApSendError,
    VerifyTimeoutError,
    bulk_onboard,
)
from lifx.protocol.models import Serial
from tests.test_onboard.conftest import (
    HOME_PASSWORD,
    HOME_SSID,
    ORIGINAL_SSID,
    OTHER_SOFTAP_SSID,
    SOFTAP_SERIAL,
    SOFTAP_SSID,
    FakeSoftApClient,
    FakeWatcher,
    add_color_light,
    growing_emulator,
    make_joiner,
    make_scanner,
    softap_network,
)
from tests.test_onboard.test_onboard import FAST, HAPPY_PATH_EVENTS
from tests.test_onboard.test_verify import WatcherFactory

OTHER_SERIAL = softap_network(OTHER_SOFTAP_SSID).serial

#: Bulk timing on top of the single-device overrides.
BULK = {**FAST, "scan_interval": 0.005}


async def _collect(home_network: HomeNetwork, **overrides: Any) -> list:
    """Run bulk_onboard() with fakes to completion, returning the results."""
    kwargs = {**BULK, **overrides}
    return [result async for result in bulk_onboard(home_network, **kwargs)]


class TestSerialAttempts:
    async def test_two_softaps_are_onboarded_one_after_the_other(
        self, home_network: HomeNetwork
    ) -> None:
        scanner = make_scanner([softap_network(), softap_network(OTHER_SOFTAP_SSID)])
        joiner = make_joiner(current=ORIGINAL_SSID, reporter=True)
        softap = FakeSoftApClient()

        results = await _collect(
            home_network,
            scanner=scanner,
            joiner=joiner,
            softap=softap,
            verify=False,
            max_devices=2,
        )

        assert [result.serial for result in results] == [SOFTAP_SERIAL, OTHER_SERIAL]
        assert all(result.error is None and result.phase is None for result in results)
        assert all(result.verified is False for result in results)
        assert all(result.host_network == ORIGINAL_SSID for result in results)
        assert [network.ssid for network in joiner.joins] == [
            SOFTAP_SSID,
            OTHER_SOFTAP_SSID,
        ]
        assert joiner.calls.count("join") == 2
        assert joiner.calls.count("rejoin") == 2
        assert [target for target, _ in softap.sent] == [SOFTAP_SERIAL, OTHER_SERIAL]
        assert softap.opened == softap.closed == 2

    async def test_a_recurring_serial_is_attempted_once(
        self, home_network: HomeNetwork
    ) -> None:
        scanner = make_scanner([softap_network()])
        joiner = make_joiner(current=ORIGINAL_SSID, reporter=True)

        results = await _collect(
            home_network,
            scanner=scanner,
            joiner=joiner,
            softap=FakeSoftApClient(),
            verify=False,
            stop_when_idle_for=0.05,
        )

        assert [result.serial for result in results] == [SOFTAP_SERIAL]
        assert joiner.calls.count("join") == 1
        # The SoftAP kept showing up after its attempt and was left alone.
        assert len(scanner.calls) >= 2

    async def test_max_devices_caps_attempts(self, home_network: HomeNetwork) -> None:
        scanner = make_scanner(
            [
                softap_network(),
                softap_network(OTHER_SOFTAP_SSID),
                softap_network("LIFX Tile 111111"),
            ]
        )
        joiner = make_joiner(current=ORIGINAL_SSID, reporter=True)

        results = await _collect(
            home_network,
            scanner=scanner,
            joiner=joiner,
            softap=FakeSoftApClient(),
            verify=False,
            max_devices=2,
        )

        assert [result.serial for result in results] == [SOFTAP_SERIAL, OTHER_SERIAL]
        assert joiner.calls.count("join") == 2

    async def test_stop_when_idle_for_ends_an_empty_run(
        self, home_network: HomeNetwork
    ) -> None:
        scanner = make_scanner()
        joiner = make_joiner(current=ORIGINAL_SSID, reporter=True)

        results = await _collect(
            home_network,
            scanner=scanner,
            joiner=joiner,
            softap=FakeSoftApClient(),
            verify=False,
            stop_when_idle_for=0.05,
        )

        assert results == []
        assert len(scanner.calls) >= 1
        assert joiner.calls == []

    async def test_a_failing_scan_is_logged_and_scanning_continues(
        self, home_network: HomeNetwork
    ) -> None:
        scanner = make_scanner(OSError("airport: busy"), [softap_network()])

        results = await _collect(
            home_network,
            scanner=scanner,
            joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
            softap=FakeSoftApClient(),
            verify=False,
            max_devices=1,
        )

        assert [result.serial for result in results] == [SOFTAP_SERIAL]
        assert len(scanner.calls) == 2

    async def test_a_failed_device_is_reported_and_the_next_still_attempted(
        self, home_network: HomeNetwork
    ) -> None:
        class FlakySoftApClient(FakeSoftApClient):
            async def send_access_point(
                self, target: Serial, network: HomeNetwork
            ) -> None:
                if not self.sent and not self.closed:
                    raise SoftApSendError("SoftAP closed the connection")
                await super().send_access_point(target, network)

        scanner = make_scanner([softap_network(), softap_network(OTHER_SOFTAP_SSID)])
        joiner = make_joiner(
            current=ORIGINAL_SSID, reporter=True, forgetter=True, disassociator=True
        )
        softap = FlakySoftApClient()
        seen: list[OnboardEvent] = []

        results = await _collect(
            home_network,
            scanner=scanner,
            joiner=joiner,
            softap=softap,
            verify=False,
            max_devices=2,
            on_event=seen.append,
        )

        failed, succeeded = results
        assert failed.serial == SOFTAP_SERIAL
        assert failed.phase is OnboardPhase.CONFIGURE
        assert isinstance(failed.error, SoftApSendError)
        assert failed.error.result is failed
        assert failed.host_network == ORIGINAL_SSID
        assert succeeded.serial == OTHER_SERIAL
        assert succeeded.error is None
        # Host recovery ran between the two attempts.
        assert joiner.calls.count("forget") == 2
        assert joiner.calls.count("disassociate") == 2
        assert joiner.rejoins == [(ORIGINAL_SSID, ""), (ORIGINAL_SSID, "")]
        failures = [event for event in seen if event.type is OnboardEventType.FAILED]
        assert len(failures) == 1
        assert failures[0].serial == SOFTAP_SERIAL
        assert failures[0].error is failed.error

    async def test_a_default_softap_connection_is_built_when_none_is_given(
        self, home_network: HomeNetwork
    ) -> None:
        results = await _collect(
            home_network,
            scanner=make_scanner(),
            joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
            verify=False,
            stop_when_idle_for=0.02,
        )
        assert results == []


class TestTargets:
    async def test_foreign_serials_are_ignored_and_a_missing_target_reported_last(
        self, home_network: HomeNetwork
    ) -> None:
        scanner = make_scanner([softap_network(), softap_network(OTHER_SOFTAP_SSID)])
        joiner = make_joiner(current=ORIGINAL_SSID, reporter=True)
        seen: list[OnboardEvent] = []

        results = await _collect(
            home_network,
            scanner=scanner,
            joiner=joiner,
            softap=FakeSoftApClient(),
            verify=False,
            targets=[OTHER_SERIAL, "ab:cd:ef"],
            stop_when_idle_for=0.05,
            on_event=seen.append,
        )

        onboarded, missing = results
        assert onboarded.serial == OTHER_SERIAL
        assert onboarded.error is None
        assert missing.serial == Serial.from_string("d073d5abcdef")
        assert missing.phase is OnboardPhase.SCAN
        assert isinstance(missing.error, SoftApNotFoundError)
        assert missing.error.phase is OnboardPhase.SCAN
        assert missing.error.result is missing
        assert missing.verified is False
        assert missing.took >= 0.0
        assert [network.ssid for network in joiner.joins] == [OTHER_SOFTAP_SSID]
        failed = seen[-1]
        assert failed.type is OnboardEventType.FAILED
        assert failed.phase is OnboardPhase.SCAN
        assert failed.serial == missing.serial
        assert failed.error is missing.error

    async def test_the_loop_ends_once_every_target_is_attempted(
        self, home_network: HomeNetwork
    ) -> None:
        scanner = make_scanner([softap_network(), softap_network(OTHER_SOFTAP_SSID)])

        results = await _collect(
            home_network,
            scanner=scanner,
            joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
            softap=FakeSoftApClient(),
            verify=False,
            targets=[str(SOFTAP_SERIAL)],
        )

        assert [result.serial for result in results] == [SOFTAP_SERIAL]
        assert len(scanner.calls) == 1

    async def test_an_invalid_target_is_rejected_before_any_scan(
        self, home_network: HomeNetwork
    ) -> None:
        scanner = make_scanner([softap_network()])

        with pytest.raises(InvalidSoftApTargetError, match="Neighbour"):
            await _collect(
                home_network,
                scanner=scanner,
                joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
                softap=FakeSoftApClient(),
                verify=False,
                targets=["Neighbour4C0A17"],
            )

        assert scanner.calls == []


class TestEvents:
    async def test_scanning_is_emitted_per_resumption_and_discovered_per_device(
        self, home_network: HomeNetwork
    ) -> None:
        networks = [softap_network(), softap_network(OTHER_SOFTAP_SSID)]
        scanner = make_scanner(networks)
        queue = OnboardEventQueue()
        seen: list[OnboardEvent] = []

        await _collect(
            home_network,
            scanner=scanner,
            joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
            softap=FakeSoftApClient(),
            verify=False,
            stop_when_idle_for=0.05,
            on_event=seen.append,
            events=queue,
        )

        per_device = HAPPY_PATH_EVENTS[1:]
        assert [event.type for event in seen] == (
            [OnboardEventType.SCANNING]
            + per_device
            + [OnboardEventType.SCANNING]
            + per_device
            + [OnboardEventType.SCANNING]
        )
        queue.close()
        queued = [event async for event in queue]
        assert [event.type for event in queued] == [e.type for e in seen]
        assert queue.dropped == 0
        scanning = seen[0]
        assert scanning.phase is OnboardPhase.SCAN
        assert scanning.timeout == 0.05
        first, second = (e for e in seen if e.type is OnboardEventType.DISCOVERED)
        assert first.serial == SOFTAP_SERIAL
        assert first.ssid == SOFTAP_SSID
        assert first.networks == tuple(networks)
        assert second.serial == OTHER_SERIAL
        # Nothing new showed up after the second device, so the many idle
        # scan rounds that followed emitted nothing.
        assert len(scanner.calls) > 3

    async def test_a_raising_callback_is_logged_and_does_not_stop_the_run(
        self, home_network: HomeNetwork, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.ERROR, logger="lifx.onboard.bulk")

        def on_event(event: OnboardEvent) -> None:
            if event.type is OnboardEventType.SCANNING:
                raise RuntimeError(HOME_PASSWORD)

        results = await _collect(
            home_network,
            scanner=make_scanner([softap_network()]),
            joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
            softap=FakeSoftApClient(),
            verify=False,
            max_devices=1,
            on_event=on_event,
        )

        assert [result.serial for result in results] == [SOFTAP_SERIAL]
        assert "event callback failed for scanning: RuntimeError" in caplog.text
        assert HOME_PASSWORD not in caplog.text


# ---- interleaved verification ------------------------------------------------


class FakeWatcherFactory:
    """Stands in for ``DeviceWatcher`` so the owned watcher is a ``FakeWatcher``."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.watchers: list[FakeWatcher] = []

    def __call__(self, **kwargs: Any) -> FakeWatcher:
        self.calls.append(kwargs)
        watcher = FakeWatcher()
        self.watchers.append(watcher)
        return watcher

    @property
    def watcher(self) -> FakeWatcher:
        (watcher,) = self.watchers
        return watcher


@pytest.fixture
def fake_watchers(monkeypatch: pytest.MonkeyPatch) -> FakeWatcherFactory:
    factory = FakeWatcherFactory()
    monkeypatch.setattr("lifx.onboard.bulk.DeviceWatcher", factory)
    return factory


Timeline = list[tuple[Any, ...]]


class Consumer:
    """Drives ``bulk_onboard()`` in a task and records events and results in order."""

    def __init__(self) -> None:
        self.timeline: Timeline = []
        self.results: list[Result] = []
        self.task: asyncio.Task[None] | None = None
        self._waiters: dict[tuple[OnboardEventType, Serial | None], asyncio.Event] = {}

    def on_event(self, event: OnboardEvent) -> None:
        self.timeline.append(("event", event.type, event.serial))
        self._waiters.setdefault((event.type, event.serial), asyncio.Event()).set()

    async def seen(self, event_type: OnboardEventType, serial: Serial | None) -> None:
        waiter = self._waiters.setdefault((event_type, serial), asyncio.Event())
        await asyncio.wait_for(waiter.wait(), 5.0)

    def start(self, home_network: HomeNetwork, **overrides: Any) -> asyncio.Task[None]:
        async def consume() -> None:
            kwargs = {**BULK, "on_event": self.on_event, **overrides}
            async for result in bulk_onboard(home_network, **kwargs):
                self.results.append(result)
                self.timeline.append(("result", result.serial))

        self.task = asyncio.ensure_future(consume())
        return self.task

    async def finish(self) -> list[Result]:
        assert self.task is not None
        await asyncio.wait_for(self.task, 5.0)
        return self.results

    def index(self, *entry: Any) -> int:
        return self.timeline.index(entry)

    def scanning_resumed(self, round_number: int) -> int:
        """The timeline index of the ``round_number``-th ``SCANNING`` event."""
        rounds = [
            index
            for index, entry in enumerate(self.timeline)
            if entry == ("event", OnboardEventType.SCANNING, None)
        ]
        return rounds[round_number - 1]

    async def results_yielded(self, count: int) -> None:
        for _ in range(200):
            if len(self.results) >= count:
                return
            await asyncio.sleep(0.01)
        raise AssertionError(f"{len(self.results)} results, wanted {count}")


def _sighting(watcher: FakeWatcher, serial: Serial) -> None:
    watcher.emit(DeviceEventType.ADDED, str(serial), "192.0.2.10")


class TestInterleavedVerification:
    async def test_owned_watcher_serves_the_run_and_results_arrive_in_completion_order(
        self, home_network: HomeNetwork, fake_watchers: FakeWatcherFactory
    ) -> None:
        class SlowSecondConfigure(FakeSoftApClient):
            async def send_access_point(
                self, target: Serial, network: HomeNetwork
            ) -> None:
                if target == OTHER_SERIAL:
                    # The first device verifies while this one is configured.
                    _sighting(fake_watchers.watcher, SOFTAP_SERIAL)
                    await asyncio.sleep(0.02)
                await super().send_access_point(target, network)

        consumer = Consumer()
        consumer.start(
            home_network,
            scanner=make_scanner([softap_network(), softap_network(OTHER_SOFTAP_SSID)]),
            joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
            softap=SlowSecondConfigure(),
            verify=True,
            verify_timeout=5.0,
            verify_poll=0.05,
            max_devices=2,
        )
        await consumer.seen(OnboardEventType.VERIFYING, OTHER_SERIAL)
        watcher = fake_watchers.watcher
        assert watcher.running
        assert watcher.listener_count == 1
        _sighting(watcher, OTHER_SERIAL)
        first, second = await consumer.finish()

        assert first.serial == SOFTAP_SERIAL
        assert second.serial == OTHER_SERIAL
        assert first.verified and second.verified
        assert first.error is None and second.error is None
        # The first result was yielded as soon as the second handoff let the
        # generator resume, before scanning started again.
        assert consumer.index("result", SOFTAP_SERIAL) < consumer.scanning_resumed(3)
        assert consumer.index("result", SOFTAP_SERIAL) > consumer.index(
            "event", OnboardEventType.REJOINED, OTHER_SERIAL
        )
        # Its verification ran alongside the second device's handoff.
        assert consumer.index(
            "event", OnboardEventType.VERIFYING, SOFTAP_SERIAL
        ) < consumer.index("event", OnboardEventType.JOINING, OTHER_SERIAL)
        assert consumer.index(
            "event", OnboardEventType.VERIFIED, SOFTAP_SERIAL
        ) < consumer.index("event", OnboardEventType.CONFIGURED, OTHER_SERIAL)
        (call,) = fake_watchers.calls
        assert call == {"sweep_interval": 0.05, "mdns": False}
        assert watcher.entered == 1
        assert watcher.exited == 1
        assert not watcher.running
        assert watcher.listener_count == 0

    async def test_a_verification_completing_while_scanning_is_yielded_promptly(
        self, home_network: HomeNetwork, fake_watchers: FakeWatcherFactory
    ) -> None:
        consumer = Consumer()
        consumer.start(
            home_network,
            scanner=make_scanner([softap_network()]),
            joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
            softap=FakeSoftApClient(),
            verify=True,
            verify_timeout=5.0,
            scan_interval=3600.0,
            stop_when_idle_for=5.0,
            max_devices=2,
        )
        await consumer.seen(OnboardEventType.VERIFYING, SOFTAP_SERIAL)
        assert consumer.results == []
        _sighting(fake_watchers.watcher, SOFTAP_SERIAL)
        await consumer.results_yielded(1)
        assert [result.serial for result in consumer.results] == [SOFTAP_SERIAL]
        assert consumer.results[0].verified is True
        assert consumer.task is not None and not consumer.task.done()
        consumer.task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer.task
        assert fake_watchers.watcher.exited == 1

    async def test_a_supplied_watcher_is_reused_and_left_running(
        self, home_network: HomeNetwork, fake_watchers: FakeWatcherFactory
    ) -> None:
        watcher = FakeWatcher()
        watcher.running = True
        consumer = Consumer()
        consumer.start(
            home_network,
            scanner=make_scanner([softap_network(), softap_network(OTHER_SOFTAP_SSID)]),
            joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
            softap=FakeSoftApClient(),
            verify=watcher,
            verify_timeout=5.0,
            max_devices=2,
        )
        await consumer.seen(OnboardEventType.VERIFYING, OTHER_SERIAL)
        assert watcher.listener_count == 2
        _sighting(watcher, OTHER_SERIAL)
        await consumer.results_yielded(1)
        _sighting(watcher, SOFTAP_SERIAL)
        results = await consumer.finish()

        assert [result.serial for result in results] == [OTHER_SERIAL, SOFTAP_SERIAL]
        assert all(result.verified for result in results)
        assert fake_watchers.calls == []
        assert watcher.entered == 0
        assert watcher.exited == 0
        assert watcher.running
        assert watcher.listener_count == 0

    async def test_verification_timing_out_yields_a_verify_phase_failure(
        self, home_network: HomeNetwork, fake_watchers: FakeWatcherFactory
    ) -> None:
        consumer = Consumer()
        consumer.start(
            home_network,
            scanner=make_scanner([softap_network()]),
            joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
            softap=FakeSoftApClient(),
            verify=True,
            verify_timeout=0.05,
            max_devices=1,
        )
        (result,) = await consumer.finish()

        assert result.serial == SOFTAP_SERIAL
        assert result.verified is False
        assert result.phase is OnboardPhase.VERIFY
        assert isinstance(result.error, VerifyTimeoutError)
        assert result.error.result is result
        assert result.host_network == ORIGINAL_SSID
        assert result.took >= 0.05
        assert consumer.timeline[-2:] == [
            ("event", OnboardEventType.FAILED, SOFTAP_SERIAL),
            ("result", SOFTAP_SERIAL),
        ]
        assert fake_watchers.watcher.listener_count == 0
        assert fake_watchers.watcher.exited == 1

    async def test_a_configured_device_whose_rejoin_fails_is_not_verified(
        self, home_network: HomeNetwork, fake_watchers: FakeWatcherFactory
    ) -> None:
        consumer = Consumer()
        consumer.start(
            home_network,
            scanner=make_scanner([softap_network()]),
            joiner=make_joiner(
                current=ORIGINAL_SSID, reporter=True, rejoin_failures=99
            ),
            softap=FakeSoftApClient(),
            verify=True,
            verify_timeout=5.0,
            max_devices=1,
        )
        (result,) = await consumer.finish()

        assert result.phase is OnboardPhase.REJOIN
        assert isinstance(result.error, HostRejoinError)
        assert result.verified is False
        types = [entry[1] for entry in consumer.timeline if entry[0] == "event"]
        assert OnboardEventType.CONFIGURED in types
        assert OnboardEventType.VERIFYING not in types
        assert fake_watchers.watcher.listener_count == 0
        assert fake_watchers.watcher.exited == 1

    async def test_verify_false_opens_no_watcher(
        self, home_network: HomeNetwork, fake_watchers: FakeWatcherFactory
    ) -> None:
        results = await _collect(
            home_network,
            scanner=make_scanner([softap_network()]),
            joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
            softap=FakeSoftApClient(),
            verify=False,
            max_devices=1,
        )
        assert [result.verified for result in results] == [False]
        assert fake_watchers.calls == []

    async def test_no_device_found_opens_no_watcher(
        self, home_network: HomeNetwork, fake_watchers: FakeWatcherFactory
    ) -> None:
        results = await _collect(
            home_network,
            scanner=make_scanner(),
            joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
            softap=FakeSoftApClient(),
            verify=True,
            stop_when_idle_for=0.02,
        )
        assert results == []
        assert fake_watchers.watchers[0].entered == 0


class TestCancellation:
    async def test_cancelling_during_wait_recovers_the_host_and_closes_the_watcher(
        self, home_network: HomeNetwork, fake_watchers: FakeWatcherFactory
    ) -> None:
        joiner = make_joiner(
            current=ORIGINAL_SSID, reporter=True, forgetter=True, disassociator=True
        )
        consumer = Consumer()
        task = consumer.start(
            home_network,
            scanner=make_scanner([softap_network()]),
            joiner=joiner,
            softap=FakeSoftApClient(probe_failures=10**6, probe_takes=0.005),
            verify=True,
            wait_timeout=5.0,
        )
        await consumer.seen(OnboardEventType.WAITING_FOR_SOFTAP, SOFTAP_SERIAL)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert consumer.results == []
        assert joiner.calls.count("join") == 1
        assert "forget" in joiner.calls
        assert "disassociate" in joiner.calls
        assert joiner.rejoins == [(ORIGINAL_SSID, "")]
        assert joiner.forgotten == [SOFTAP_SSID]
        assert fake_watchers.watcher.entered == 1
        assert fake_watchers.watcher.exited == 1
        assert not fake_watchers.watcher.running

    async def test_cancelling_after_configure_closes_the_pending_listener(
        self, home_network: HomeNetwork, fake_watchers: FakeWatcherFactory
    ) -> None:
        joiner = make_joiner(current=ORIGINAL_SSID, reporter=True, rejoin_hangs=True)
        consumer = Consumer()
        task = consumer.start(
            home_network,
            scanner=make_scanner([softap_network()]),
            joiner=joiner,
            softap=FakeSoftApClient(),
            verify=True,
            verify_timeout=5.0,
        )
        await consumer.seen(OnboardEventType.REJOINING, SOFTAP_SERIAL)
        assert fake_watchers.watcher.listener_count == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert consumer.results == []
        # Cancelled while waiting on auto-join; the bounded recovery then
        # forced a rejoin. Each hung rejoin() costs one rejoin_timeout and
        # fails the target over until recovery's budget runs out.
        assert joiner.rejoins[0] == (ORIGINAL_SSID, "")
        assert len(joiner.rejoins) <= 2
        assert fake_watchers.watcher.listener_count == 0
        assert fake_watchers.watcher.exited == 1

    async def test_cancelling_with_a_pending_verification_abandons_it(
        self, home_network: HomeNetwork, fake_watchers: FakeWatcherFactory
    ) -> None:
        consumer = Consumer()
        task = consumer.start(
            home_network,
            scanner=make_scanner([softap_network()]),
            joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
            softap=FakeSoftApClient(),
            verify=True,
            verify_timeout=5.0,
        )
        await consumer.seen(OnboardEventType.VERIFYING, SOFTAP_SERIAL)
        assert fake_watchers.watcher.listener_count == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert consumer.results == []
        assert fake_watchers.watcher.listener_count == 0
        assert fake_watchers.watcher.exited == 1


class TestPassword:
    async def test_the_password_never_reaches_logs_events_or_results(
        self,
        home_network: HomeNetwork,
        caplog: pytest.LogCaptureFixture,
        fake_watchers: FakeWatcherFactory,
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="lifx.onboard")
        joiner = make_joiner(rejoin_failures=1, rejoin_error_echoes_password=True)
        seen: list[OnboardEvent] = []

        results = await _collect(
            home_network,
            scanner=make_scanner([softap_network()]),
            joiner=joiner,
            softap=FakeSoftApClient(),
            verify=True,
            verify_timeout=0.02,
            max_devices=1,
            on_event=seen.append,
        )

        (result,) = results
        assert joiner.rejoins == [(HOME_SSID, HOME_PASSWORD)] * 2
        assert isinstance(result.error, VerifyTimeoutError)
        assert HOME_PASSWORD not in caplog.text
        assert HOME_PASSWORD not in repr(seen)
        assert HOME_PASSWORD not in repr(results)
        assert HOME_PASSWORD not in str(result.error)
        assert result.error.__cause__ is None


@pytest.mark.emulator
class TestEmulator:
    async def test_an_earlier_device_verifies_while_a_later_one_is_configured(
        self, home_network: HomeNetwork, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        factory = WatcherFactory(0)
        monkeypatch.setattr("lifx.onboard.bulk.DeviceWatcher", factory)
        consumer = Consumer()
        first_verified = asyncio.Event()

        with growing_emulator() as (server, port):
            factory.port = port

            def on_event(event: OnboardEvent) -> None:
                consumer.on_event(event)
                # The device reboots onto the LAN once it has its credentials.
                if event.type is OnboardEventType.CONFIGURED:
                    assert event.serial is not None
                    add_color_light(server, str(event.serial))
                if (
                    event.type is OnboardEventType.VERIFIED
                    and event.serial == SOFTAP_SERIAL
                ):
                    first_verified.set()

            class SlowSecondConfigure(FakeSoftApClient):
                async def send_access_point(
                    self, target: Serial, network: HomeNetwork
                ) -> None:
                    if target == OTHER_SERIAL:
                        await asyncio.wait_for(first_verified.wait(), 5.0)
                    await super().send_access_point(target, network)

            consumer.start(
                home_network,
                scanner=make_scanner(
                    [softap_network(), softap_network(OTHER_SOFTAP_SSID)]
                ),
                joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
                softap=SlowSecondConfigure(),
                verify=True,
                verify_timeout=5.0,
                verify_poll=0.05,
                max_devices=2,
                on_event=on_event,
            )
            first, second = await consumer.finish()

        assert first.serial == SOFTAP_SERIAL
        assert second.serial == OTHER_SERIAL
        assert first.verified and second.verified
        assert first.error is None and second.error is None
        assert consumer.index("result", SOFTAP_SERIAL) < consumer.scanning_resumed(3)
        assert consumer.index(
            "event", OnboardEventType.VERIFIED, SOFTAP_SERIAL
        ) < consumer.index("event", OnboardEventType.CONFIGURED, OTHER_SERIAL)
        (call,) = factory.calls
        assert call == {"sweep_interval": 0.05, "mdns": False}
        (watcher,) = factory.watchers
        assert not watcher.running
        assert {d.serial for d in watcher.devices} == {
            str(SOFTAP_SERIAL),
            str(OTHER_SERIAL),
        }
