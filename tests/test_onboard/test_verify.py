"""Tests for LAN verification: the device must be seen off the SoftAP address."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from lifx import DeviceEventType, DeviceWatcher
from lifx.onboard import (
    SOFTAP_ADDRESS,
    HomeNetwork,
    OnboardEvent,
    OnboardEventType,
    OnboardPhase,
    VerifyTimeoutError,
    onboard,
)
from lifx.onboard.verify import LanVerification, verify_on_lan
from lifx.protocol.models import Serial
from tests.conftest import get_free_port
from tests.test_onboard.conftest import (
    LOOPBACK,
    ORIGINAL_SSID,
    SOFTAP_SERIAL,
    SOFTAP_SSID,
    FakeSoftApClient,
    FakeWatcher,
    emulator,
    loopback_watcher,
    make_joiner,
)
from tests.test_onboard.test_onboard import FAST, HAPPY_PATH_EVENTS, VERIFY_EVENTS

pytestmark = pytest.mark.emulator

SERIAL = str(SOFTAP_SERIAL)


class WatcherFactory:
    """Stands in for ``DeviceWatcher`` so an owned watcher sweeps the loopback."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.calls: list[dict[str, Any]] = []
        self.watchers: list[DeviceWatcher] = []

    def __call__(self, **kwargs: Any) -> DeviceWatcher:
        self.calls.append(kwargs)
        watcher = loopback_watcher(self.port, **kwargs)
        self.watchers.append(watcher)
        return watcher


@pytest.fixture
def watcher_factory(monkeypatch: pytest.MonkeyPatch) -> WatcherFactory:
    factory = WatcherFactory(0)
    monkeypatch.setattr("lifx.onboard.machine.DeviceWatcher", factory)
    return factory


def _onboard(home_network: HomeNetwork, **overrides: Any):
    """``onboard()`` with the full-SSID target and fakes for the WiFi side."""
    joiner = overrides.pop("joiner", make_joiner(current=ORIGINAL_SSID, reporter=True))
    softap = overrides.pop("softap", FakeSoftApClient())
    kwargs = {**FAST, "verify_timeout": 5.0, "verify_poll": 0.05, **overrides}
    return onboard(
        home_network,
        scanner=None,
        joiner=joiner,
        target=SOFTAP_SSID,
        softap=softap,
        **kwargs,
    )


class TestOwnedWatcher:
    async def test_device_appearing_verifies_and_closes_the_watcher(
        self, home_network: HomeNetwork, watcher_factory: WatcherFactory
    ) -> None:
        seen = []
        with emulator((SERIAL,)) as port:
            watcher_factory.port = port
            result = await _onboard(home_network, verify=True, on_event=seen.append)

        assert result.verified is True
        assert result.phase is None
        assert result.serial == SOFTAP_SERIAL
        assert result.host_network == ORIGINAL_SSID
        assert [e.type for e in seen] == HAPPY_PATH_EVENTS[2:] + VERIFY_EVENTS
        verifying, verified = seen[-2:]
        assert verifying.phase is OnboardPhase.VERIFY
        assert verifying.serial == SOFTAP_SERIAL
        assert verifying.timeout == 5.0
        assert verified.phase is OnboardPhase.VERIFY
        assert verified.serial == SOFTAP_SERIAL
        assert verified.address == LOOPBACK
        assert verified.took is not None and 0.0 <= verified.took < 5.0
        # The library's own watcher: polled at verify_poll, UDP only, closed after.
        (call,) = watcher_factory.calls
        assert call["sweep_interval"] == 0.05
        assert call["mdns"] is False
        (watcher,) = watcher_factory.watchers
        assert not watcher.running

    async def test_sighting_at_the_softap_address_never_counts(
        self, home_network: HomeNetwork, watcher_factory: WatcherFactory
    ) -> None:
        joiner = make_joiner(current=ORIGINAL_SSID, reporter=True, forgetter=True)
        seen = []
        with emulator((SERIAL,)) as port:
            watcher_factory.port = port
            with pytest.raises(VerifyTimeoutError) as info:
                await _onboard(
                    home_network,
                    verify=True,
                    joiner=joiner,
                    softap=FakeSoftApClient(address=LOOPBACK),
                    on_event=seen.append,
                    verify_timeout=1.0,
                )
        error = info.value
        assert error.phase is OnboardPhase.VERIFY
        assert SERIAL in str(error)
        assert error.__cause__ is None
        result = error.result
        assert result is not None
        assert result.phase is OnboardPhase.VERIFY
        assert result.error is error
        assert result.verified is False
        assert result.serial == SOFTAP_SERIAL
        assert result.host_network == ORIGINAL_SSID
        assert [e.type for e in seen] == HAPPY_PATH_EVENTS[2:] + [
            OnboardEventType.VERIFYING,
            OnboardEventType.FAILED,
        ]
        (watcher,) = watcher_factory.watchers
        # The watcher did see the device, at the address verification ignores.
        assert watcher.get(SERIAL) is not None
        assert not watcher.running
        # The host was already home: no second rejoin, no recovery.
        assert joiner.rejoins == [(ORIGINAL_SSID, "")]
        assert joiner.forgotten == [SOFTAP_SSID]

    async def test_cancellation_during_verification_closes_the_watcher(
        self, home_network: HomeNetwork, watcher_factory: WatcherFactory
    ) -> None:
        watcher_factory.port = get_free_port()  # nothing answers there
        joiner = make_joiner(current=ORIGINAL_SSID, reporter=True, forgetter=True)
        verifying = asyncio.Event()

        def on_event(event: OnboardEvent) -> None:
            if event.type is OnboardEventType.VERIFYING:
                verifying.set()

        task = asyncio.ensure_future(
            _onboard(home_network, verify=True, joiner=joiner, on_event=on_event)
        )
        await asyncio.wait_for(verifying.wait(), 5.0)
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        (watcher,) = watcher_factory.watchers
        assert not watcher.running
        assert joiner.rejoins == [(ORIGINAL_SSID, "")]

    async def test_verify_false_opens_no_watcher(
        self, home_network: HomeNetwork, watcher_factory: WatcherFactory
    ) -> None:
        seen = []
        result = await _onboard(home_network, verify=False, on_event=seen.append)
        assert result.verified is False
        assert watcher_factory.calls == []
        assert [e.type for e in seen] == HAPPY_PATH_EVENTS[2:]


class TestSuppliedWatcher:
    async def test_running_watcher_is_used_and_left_running(
        self, home_network: HomeNetwork
    ) -> None:
        port = get_free_port()
        seen = []
        verifying = asyncio.Event()

        def on_event(event: OnboardEvent) -> None:
            seen.append(event)
            if event.type is OnboardEventType.VERIFYING:
                verifying.set()

        async with loopback_watcher(port) as watcher:
            assert watcher.devices == []
            task = asyncio.ensure_future(
                _onboard(home_network, verify=watcher, on_event=on_event)
            )
            await asyncio.wait_for(verifying.wait(), 5.0)
            assert not task.done()
            with emulator((SERIAL,), port):
                await watcher.sweep()
                result = await asyncio.wait_for(task, 5.0)
            assert watcher.running
            assert watcher.get(SERIAL) is not None
        assert result.verified is True
        assert [e.type for e in seen] == HAPPY_PATH_EVENTS[2:] + VERIFY_EVENTS
        assert seen[-1].address == LOOPBACK

    async def test_a_record_from_before_verification_does_not_count(
        self, home_network: HomeNetwork
    ) -> None:
        with emulator((SERIAL,)) as port:
            async with loopback_watcher(port) as watcher:
                assert watcher.get(SERIAL) is not None
                with pytest.raises(VerifyTimeoutError) as info:
                    await _onboard(home_network, verify=watcher, verify_timeout=0.2)
                assert watcher.running
        assert info.value.result is not None
        assert info.value.result.verified is False


class TestSightings:
    """Staged events, for transitions the emulator cannot produce."""

    @staticmethod
    def _staging(fake: FakeWatcher, *sightings: tuple[Any, ...]):
        """Deliver ``sightings`` to the fake the moment VERIFYING is emitted."""
        seen: list[OnboardEvent] = []

        def on_event(event: OnboardEvent) -> None:
            seen.append(event)
            if event.type is OnboardEventType.VERIFYING:
                for sighting in sightings:
                    fake.emit(*sighting)

        return seen, on_event

    async def test_an_update_leaving_the_softap_address_counts(
        self, home_network: HomeNetwork
    ) -> None:
        fake = FakeWatcher()
        seen, on_event = self._staging(
            fake,
            (DeviceEventType.ADDED, "d073d5ffffff", LOOPBACK),
            (DeviceEventType.ADDED, SERIAL, SOFTAP_ADDRESS),
            (DeviceEventType.REMOVED, SERIAL, LOOPBACK),
            (
                DeviceEventType.UPDATED,
                SERIAL,
                "192.0.2.10",
                56700,
                {"address": ((SOFTAP_ADDRESS, 56700), ("192.0.2.10", 56700))},
            ),
            (DeviceEventType.ADDED, SERIAL, "192.0.2.11"),
        )
        result = await _onboard(
            home_network, verify=cast(DeviceWatcher, fake), on_event=on_event
        )
        assert result.verified is True
        assert seen[-1].type is OnboardEventType.VERIFIED
        assert seen[-1].address == "192.0.2.10"
        # A supplied watcher is never entered or exited by the library.
        assert fake.entered == 0 and fake.exited == 0
        assert fake.listener_count == 0

    async def test_a_zone_suffix_still_matches_the_softap_address(
        self, home_network: HomeNetwork
    ) -> None:
        fake = FakeWatcher()
        seen, on_event = self._staging(
            fake,
            (DeviceEventType.ADDED, SERIAL, "fe80::1%en0"),
            (DeviceEventType.ADDED, SERIAL, "not an address"),
        )
        result = await _onboard(
            home_network,
            verify=cast(DeviceWatcher, fake),
            softap=FakeSoftApClient(address="fe80::1"),
            on_event=on_event,
        )
        assert result.verified is True
        assert seen[-1].address == "not an address"

    async def test_no_sighting_times_out_and_removes_the_listener(
        self, home_network: HomeNetwork
    ) -> None:
        fake = FakeWatcher()
        with pytest.raises(VerifyTimeoutError):
            await _onboard(
                home_network, verify=cast(DeviceWatcher, fake), verify_timeout=0.05
            )
        assert fake.listener_count == 0
        assert fake.entered == 0


class TestVerifyOnLan:
    """The reusable entry point bulk onboarding shares one watcher through."""

    async def test_concurrent_verifications_do_not_steal_each_others_events(
        self,
    ) -> None:
        fake = FakeWatcher()
        other = Serial.from_string("d073d5000002")
        first = asyncio.ensure_future(
            verify_on_lan(
                fake, SOFTAP_SERIAL, softap_address=SOFTAP_ADDRESS, timeout=2.0
            )
        )
        second = asyncio.ensure_future(
            verify_on_lan(fake, other, softap_address=SOFTAP_ADDRESS, timeout=2.0)
        )
        await asyncio.sleep(0)
        assert fake.listener_count == 2
        fake.emit(DeviceEventType.ADDED, str(other), "192.0.2.2")
        sighting = await asyncio.wait_for(second, 1.0)
        assert sighting.address == "192.0.2.2"
        assert sighting.port == 56700
        assert not first.done()
        fake.emit(DeviceEventType.ADDED, SERIAL, "192.0.2.1", 56701)
        assert (await asyncio.wait_for(first, 1.0)).port == 56701
        assert fake.listener_count == 0

    async def test_a_slow_initial_sweep_is_bounded_by_the_timeout(self) -> None:
        fake = FakeWatcher(enter_takes=5.0)
        with pytest.raises(VerifyTimeoutError, match="0.05s"):
            await verify_on_lan(
                fake,
                SOFTAP_SERIAL,
                softap_address=SOFTAP_ADDRESS,
                timeout=0.05,
                open_watcher=True,
            )
        assert fake.exited == 1
        assert fake.listener_count == 0

    async def test_close_is_idempotent(self) -> None:
        fake = FakeWatcher()
        verification = LanVerification(
            fake, SOFTAP_SERIAL, softap_address=SOFTAP_ADDRESS
        )
        assert verification.sighting is None
        verification.close()
        verification.close()
        assert fake.listener_count == 0
