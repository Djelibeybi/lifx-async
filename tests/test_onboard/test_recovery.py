"""Tests for the rejoin phase and host recovery after failure or cancellation."""

from __future__ import annotations

import asyncio
import logging
import traceback

import pytest

from lifx.onboard import (
    HomeNetwork,
    HostLeftSoftApError,
    HostRejoinError,
    OnboardEvent,
    OnboardEventType,
    OnboardPhase,
    SoftApDialError,
    SoftApSendError,
    SoftApWaitTimeoutError,
    onboard,
)
from tests.conftest import HANG_GUARD_TIMEOUT
from tests.test_onboard.conftest import (
    HOME_PASSWORD,
    HOME_SSID,
    ORIGINAL_SSID,
    SOFTAP_SSID,
    FakeJoiner,
    FakeSoftApClient,
    make_joiner,
    make_scanner,
    softap_network,
)
from tests.test_onboard.test_onboard import FAST, HAPPY_PATH_EVENTS

OVERRIDE_SSID = "Guest-Network"
OVERRIDE_PASSWORD = "guest-pass-word"
CAFE_SSID = "Cafe-WiFi"


def _full_joiner(**kwargs) -> FakeJoiner:
    kwargs.setdefault("current", ORIGINAL_SSID)
    return make_joiner(reporter=True, forgetter=True, disassociator=True, **kwargs)


async def _run(
    home_network: HomeNetwork,
    joiner: FakeJoiner,
    *,
    softap: FakeSoftApClient | None = None,
    on_event=None,
    **overrides,
):
    seen: list[OnboardEvent] = []

    def record(event: OnboardEvent) -> None:
        seen.append(event)
        if on_event is not None:
            on_event(event)

    result = await onboard(
        home_network,
        scanner=make_scanner([softap_network()]),
        joiner=joiner,
        softap=softap if softap is not None else FakeSoftApClient(),
        verify=False,
        on_event=record,
        **{**FAST, **overrides},
    )
    return result, seen


def _rejoin_ssids(joiner: FakeJoiner) -> list[str]:
    """The distinct SSIDs rejoin() was asked for, in first-seen order."""
    ordered: list[str] = []
    for ssid, _ in joiner.rejoins:
        if ssid not in ordered:
            ordered.append(ssid)
    return ordered


class TestRejoinTargets:
    async def test_order_is_override_then_original_then_home(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner(rejoin_failures=10_000)
        with pytest.raises(HostRejoinError) as info:
            await _run(
                home_network,
                joiner,
                rejoin_ssid=OVERRIDE_SSID,
                rejoin_password=OVERRIDE_PASSWORD,
                rejoin_timeout=0.03,
            )
        assert _rejoin_ssids(joiner) == [OVERRIDE_SSID, ORIGINAL_SSID, HOME_SSID]
        assert (OVERRIDE_SSID, OVERRIDE_PASSWORD) in joiner.rejoins
        assert (ORIGINAL_SSID, "") in joiner.rejoins
        assert (HOME_SSID, HOME_PASSWORD) in joiner.rejoins
        assert info.value.phase is OnboardPhase.REJOIN
        assert HOME_PASSWORD not in str(info.value)
        assert OVERRIDE_PASSWORD not in str(info.value)

    async def test_override_equal_to_home_takes_the_home_password(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()
        result, seen = await _run(home_network, joiner, rejoin_ssid=HOME_SSID)
        assert joiner.rejoins == [(HOME_SSID, HOME_PASSWORD)]
        assert result.host_network == HOME_SSID
        assert _rejoin_ssids(joiner) == [HOME_SSID]

    async def test_override_password_is_used_when_given(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()
        await _run(
            home_network, joiner, rejoin_ssid=HOME_SSID, rejoin_password="other-pw"
        )
        assert joiner.rejoins == [(HOME_SSID, "other-pw")]

    async def test_failed_override_falls_through_to_the_original(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner(rejoin_failures=10_000, rejoin_failures_for=OVERRIDE_SSID)
        joiner.after_disassociate = [ORIGINAL_SSID]
        result, seen = await _run(
            home_network, joiner, rejoin_ssid=OVERRIDE_SSID, rejoin_password="x"
        )
        assert result.host_network == ORIGINAL_SSID
        assert _rejoin_ssids(joiner) == [OVERRIDE_SSID]
        rejoining = [e.ssid for e in seen if e.type is OnboardEventType.REJOINING]
        assert rejoining == [OVERRIDE_SSID, ORIGINAL_SSID]
        assert seen[-1].type is OnboardEventType.REJOINED
        assert seen[-1].ssid == ORIGINAL_SSID

    async def test_unknown_original_tries_only_the_home_network(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = make_joiner(forgetter=True, disassociator=True)
        result, seen = await _run(home_network, joiner)
        assert joiner.rejoins == [(HOME_SSID, HOME_PASSWORD)]
        assert result.host_network == HOME_SSID
        assert joiner.calls[-3:] == ["forget", "disassociate", "rejoin"]

    async def test_host_already_on_a_softap_means_the_original_is_unknown(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner(current="LIFX Beam 0d0e0f")
        result, _ = await _run(home_network, joiner)
        assert joiner.rejoins == [(HOME_SSID, HOME_PASSWORD)]
        assert result.host_network == HOME_SSID

    async def test_original_equal_to_home_tries_only_the_home_network(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner(current=HOME_SSID)
        joiner.after_disassociate = [None] * 1000
        result, _ = await _run(home_network, joiner)
        assert joiner.rejoins == [(HOME_SSID, HOME_PASSWORD)]
        assert result.host_network == HOME_SSID


class TestLeavingTheSoftAp:
    async def test_forget_then_disassociate_before_rejoin(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()
        joiner.after_disassociate = [ORIGINAL_SSID]
        await _run(home_network, joiner)
        rejoin_steps = [c for c in joiner.calls if c in ("forget", "disassociate")]
        assert rejoin_steps == ["forget", "disassociate"]
        assert joiner.forgotten == [SOFTAP_SSID]
        assert joiner.calls.index("forget") > joiner.calls.index("join")

    async def test_disassociate_is_skipped_when_already_off_the_softap(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()

        def leave_on_configured(event: OnboardEvent) -> None:
            if event.type is OnboardEventType.CONFIGURED:
                joiner.current = CAFE_SSID

        result, _ = await _run(home_network, joiner, on_event=leave_on_configured)
        assert "disassociate" not in joiner.calls
        assert joiner.forgotten == [SOFTAP_SSID]
        assert result.host_network == CAFE_SSID
        assert joiner.rejoins == []

    async def test_disassociate_is_skipped_when_the_reporter_sees_no_network(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()

        def drop_on_configured(event: OnboardEvent) -> None:
            if event.type is OnboardEventType.CONFIGURED:
                joiner.current = None

        result, _ = await _run(home_network, joiner, on_event=drop_on_configured)
        assert "disassociate" not in joiner.calls
        assert joiner.forgotten == [SOFTAP_SSID]
        # Off every network, auto-join gets its budget and then the join is forced.
        assert joiner.rejoins == [(ORIGINAL_SSID, "")]
        assert result.host_network == ORIGINAL_SSID

    async def test_without_a_reporter_disassociate_is_always_called(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = make_joiner(forgetter=True, disassociator=True)
        result, _ = await _run(home_network, joiner)
        assert joiner.calls == ["join", "forget", "disassociate", "rejoin"]
        assert result.host_network == HOME_SSID

    async def test_without_capabilities_rejoin_is_forced(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = make_joiner()
        result, _ = await _run(home_network, joiner)
        assert joiner.calls == ["join", "rejoin"]
        assert result.host_network == HOME_SSID

    async def test_forget_and_disassociate_errors_are_logged_not_raised(
        self, home_network: HomeNetwork, caplog: pytest.LogCaptureFixture
    ) -> None:
        joiner = _full_joiner(
            forget_error=OSError("no such profile"),
            disassociate_error=OSError("busy"),
        )
        with caplog.at_level(logging.WARNING, logger="lifx.onboard"):
            result, _ = await _run(home_network, joiner)
        assert result.phase is None
        assert "forgetting" in caplog.text
        assert "leaving" in caplog.text
        assert joiner.rejoins


class TestReporterErrors:
    """A failing ``current_ssid()`` means "unknown", and leaves no trace."""

    def _error(self) -> RuntimeError:
        # A subprocess backend echoing its argv would do this.
        return RuntimeError(
            f"nmcli dev wifi connect {HOME_SSID} password {HOME_PASSWORD}"
        )

    async def test_error_during_wait_is_logged_by_type_and_the_run_completes(
        self, home_network: HomeNetwork, caplog: pytest.LogCaptureFixture
    ) -> None:
        joiner = _full_joiner()
        joiner.after_join = [self._error()]
        with caplog.at_level(logging.DEBUG, logger="lifx.onboard"):
            result, seen = await _run(home_network, joiner)
        assert result.phase is None
        assert [event.type for event in seen] == HAPPY_PATH_EVENTS
        assert "RuntimeError" in caplog.text
        assert "wait" in caplog.text
        assert HOME_PASSWORD not in caplog.text
        assert "nmcli" not in caplog.text
        assert all(HOME_PASSWORD not in str(event.error) for event in seen)
        # The reporter recovered and still saw the SoftAP, so the host left it.
        assert "disassociate" in joiner.calls
        assert result.host_network == ORIGINAL_SSID

    async def test_error_on_every_poll_still_raises_the_wait_error(
        self, home_network: HomeNetwork, caplog: pytest.LogCaptureFixture
    ) -> None:
        joiner = _full_joiner()
        joiner.after_join = [self._error() for _ in range(100_000)]
        softap = FakeSoftApClient(probe_failures=100_000)
        with caplog.at_level(logging.DEBUG, logger="lifx.onboard"):
            with pytest.raises(SoftApWaitTimeoutError) as info:
                await _run(home_network, joiner, softap=softap)
        error = info.value
        assert error.phase is OnboardPhase.WAIT
        rendered = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        assert HOME_PASSWORD not in rendered
        assert "nmcli" not in rendered
        assert HOME_PASSWORD not in caplog.text
        # With the host's network unknown, nothing is disassociated; the
        # original network is still known from before the join, and is
        # rejoined once the auto-join budget runs out.
        assert "disassociate" not in joiner.calls
        assert joiner.rejoins == [(ORIGINAL_SSID, "")]
        assert error.result is not None
        assert error.result.host_network == ORIGINAL_SSID

    async def test_error_recording_the_original_leaves_it_unknown(
        self, home_network: HomeNetwork, caplog: pytest.LogCaptureFixture
    ) -> None:
        joiner = _full_joiner()
        joiner.ssid_sequence.append(self._error())
        with caplog.at_level(logging.DEBUG, logger="lifx.onboard"):
            result, _ = await _run(home_network, joiner)
        assert result.phase is None
        assert _rejoin_ssids(joiner) == [HOME_SSID]
        assert result.host_network == HOME_SSID
        assert "RuntimeError" in caplog.text
        assert HOME_PASSWORD not in caplog.text


class TestAutoJoin:
    async def test_auto_join_landing_on_the_original_needs_no_rejoin(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()
        joiner.after_disassociate = [None, ORIGINAL_SSID]
        result, seen = await _run(home_network, joiner)
        assert joiner.rejoins == []
        assert result.host_network == ORIGINAL_SSID
        assert seen[-1].ssid == ORIGINAL_SSID

    async def test_the_os_picking_another_network_is_kept(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()
        joiner.after_disassociate = [None, CAFE_SSID]
        result, seen = await _run(home_network, joiner)
        assert joiner.rejoins == []
        assert result.host_network == CAFE_SSID
        assert seen[-1].type is OnboardEventType.REJOINED
        assert seen[-1].ssid == CAFE_SSID

    async def test_auto_join_budget_starts_only_after_leaving_the_softap(
        self, home_network: HomeNetwork
    ) -> None:
        # Twenty polls still on the SoftAP outlast auto_join_wait many times
        # over; a budget counted from disassociate would already have expired
        # and forced a join before the OS lands the host on the original.
        # Windows sleeps in roughly 15 ms steps, so those polls can take
        # 0.3 s; the rejoin budget is widened so only the auto-join budget
        # can decide the outcome.
        joiner = _full_joiner()
        joiner.after_disassociate = [SOFTAP_SSID] * 20 + [None, ORIGINAL_SSID]
        result, _ = await _run(
            home_network,
            joiner,
            auto_join_wait=0.05,
            rejoin_poll=0.005,
            rejoin_timeout=2.0,
        )
        assert joiner.rejoins == []
        assert result.host_network == ORIGINAL_SSID

    async def test_auto_join_expiring_forces_the_join(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()
        joiner.after_disassociate = [None] * 1000
        result, _ = await _run(home_network, joiner)
        assert joiner.rejoins == [(ORIGINAL_SSID, "")]
        assert result.host_network == ORIGINAL_SSID

    async def test_never_leaving_the_softap_is_bounded_by_rejoin_timeout(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()
        joiner.after_disassociate = [SOFTAP_SSID] * 100_000
        result, _ = await _run(home_network, joiner, rejoin_timeout=0.05)
        assert joiner.rejoins == [(ORIGINAL_SSID, "")]
        assert result.host_network == ORIGINAL_SSID

    async def test_a_rejoin_error_while_already_on_the_target_is_success(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner(rejoin_failures=1, rejoin_error_lands_anyway=True)
        joiner.after_disassociate = [None] * 1000
        result, _ = await _run(home_network, joiner)
        assert joiner.rejoins == [(ORIGINAL_SSID, "")]
        assert result.host_network == ORIGINAL_SSID

    async def test_rejoin_is_retried_every_rejoin_poll(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = make_joiner(rejoin_failures=2)
        result, _ = await _run(home_network, joiner)
        assert joiner.rejoins == [(HOME_SSID, HOME_PASSWORD)] * 3
        assert result.host_network == HOME_SSID


class TestFailuresAfterJoin:
    """Every phase past JOIN fails with its typed error and recovers the host."""

    def _assert_recovered(self, joiner: FakeJoiner) -> None:
        after_join = joiner.calls[joiner.calls.index("join") + 1 :]
        assert "forget" in after_join
        assert "disassociate" in after_join
        assert after_join.index("forget") < after_join.index("disassociate")
        assert after_join.index("disassociate") < after_join.index("rejoin")

    async def test_wait_timeout(self, home_network: HomeNetwork) -> None:
        joiner = _full_joiner()
        softap = FakeSoftApClient(probe_failures=100_000)
        with pytest.raises(SoftApWaitTimeoutError) as info:
            await _run(home_network, joiner, softap=softap)
        assert info.value.phase is OnboardPhase.WAIT
        assert info.value.result is not None
        assert info.value.result.phase is OnboardPhase.WAIT
        assert info.value.result.host_network == ORIGINAL_SSID
        self._assert_recovered(joiner)
        assert softap.opened == 0

    async def test_host_left_softap_aborts_the_wait_early(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()
        joiner.after_join = [SOFTAP_SSID, CAFE_SSID]
        softap = FakeSoftApClient(probe_failures=100_000)
        with pytest.raises(HostLeftSoftApError) as info:
            await _run(home_network, joiner, softap=softap, wait_timeout=10.0)
        assert info.value.phase is OnboardPhase.WAIT
        assert CAFE_SSID in str(info.value)
        assert len(softap.probes) == 1
        # Recovery forgets the SoftAP but, as the host is already elsewhere,
        # neither disassociates nor forces a join: it keeps the OS's choice.
        after_join = joiner.calls[joiner.calls.index("join") + 1 :]
        assert "forget" in after_join
        assert "disassociate" not in after_join
        assert joiner.rejoins == []
        assert info.value.result is not None
        assert info.value.result.host_network == CAFE_SSID

    async def test_dial_error(self, home_network: HomeNetwork) -> None:
        joiner = _full_joiner()
        softap = FakeSoftApClient(open_error=SoftApDialError("handshake failed"))
        with pytest.raises(SoftApDialError) as info:
            await _run(home_network, joiner, softap=softap)
        assert info.value.phase is OnboardPhase.DIAL
        assert softap.sent == []
        self._assert_recovered(joiner)

    async def test_dial_timeout(self, home_network: HomeNetwork) -> None:
        joiner = _full_joiner()
        softap = FakeSoftApClient(open_takes=HANG_GUARD_TIMEOUT)
        with pytest.raises(SoftApDialError) as info:
            await _run(home_network, joiner, softap=softap, dial_timeout=0.01)
        assert info.value.phase is OnboardPhase.DIAL
        assert isinstance(info.value.__cause__, asyncio.TimeoutError)
        self._assert_recovered(joiner)

    async def test_configure_error_still_closes_the_client(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()
        softap = FakeSoftApClient(send_error=SoftApSendError("write failed"))
        with pytest.raises(SoftApSendError) as info:
            await _run(home_network, joiner, softap=softap)
        assert info.value.phase is OnboardPhase.CONFIGURE
        assert softap.closed == 1
        self._assert_recovered(joiner)

    async def test_rejoin_failure_runs_one_recovery_pass(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner(rejoin_failures=10_000)
        with pytest.raises(HostRejoinError) as info:
            await _run(home_network, joiner, rejoin_timeout=0.02)
        assert info.value.phase is OnboardPhase.REJOIN
        assert joiner.calls.count("forget") == 2
        assert info.value.result is not None
        assert info.value.result.host_network is None

    async def test_failed_is_emitted_once_with_the_error(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()
        softap = FakeSoftApClient(open_error=SoftApDialError("handshake failed"))
        seen: list[OnboardEvent] = []
        with pytest.raises(SoftApDialError) as info:
            await _run(home_network, joiner, softap=softap, on_event=seen.append)
        types = [event.type for event in seen]
        assert types == [
            OnboardEventType.SCANNING,
            OnboardEventType.DISCOVERED,
            OnboardEventType.JOINING,
            OnboardEventType.JOINED,
            OnboardEventType.WAITING_FOR_SOFTAP,
            OnboardEventType.ON_SOFTAP,
            OnboardEventType.DIALING,
            OnboardEventType.FAILED,
        ]
        failed = seen[-1]
        assert failed.error is info.value
        assert failed.phase is OnboardPhase.DIAL
        assert failed.serial == info.value.result.serial
        # Recovery is quiet: it logs rather than emitting rejoin events.
        assert OnboardEventType.REJOINING not in types

    async def test_recovery_is_bounded_by_its_budget(
        self, home_network: HomeNetwork, caplog: pytest.LogCaptureFixture
    ) -> None:
        joiner = _full_joiner(rejoin_hangs=True)
        softap = FakeSoftApClient(probe_failures=100_000)
        with caplog.at_level(logging.WARNING, logger="lifx.onboard"):
            with pytest.raises(SoftApWaitTimeoutError):
                await _run(
                    home_network,
                    joiner,
                    softap=softap,
                    rejoin_timeout=0.02,
                    auto_join_wait=0.01,
                )
        assert "gave up" in caplog.text
        assert joiner.rejoins == [(ORIGINAL_SSID, "")]


class TestCancellation:
    async def _cancel_during_wait(
        self, home_network: HomeNetwork, joiner: FakeJoiner, *, cancel_twice: bool
    ) -> asyncio.Task:
        softap = FakeSoftApClient(probe_failures=100_000)
        waiting = asyncio.Event()

        def on_event(event: OnboardEvent) -> None:
            if event.type is OnboardEventType.WAITING_FOR_SOFTAP:
                waiting.set()

        task = asyncio.ensure_future(
            _run(home_network, joiner, softap=softap, on_event=on_event)
        )
        await asyncio.wait_for(waiting.wait(), HANG_GUARD_TIMEOUT)
        task.cancel()
        if cancel_twice:
            await asyncio.sleep(0.01)
            task.cancel()
        return task

    async def test_cancel_during_wait_still_recovers_the_host(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()
        task = await self._cancel_during_wait(home_network, joiner, cancel_twice=False)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, HANG_GUARD_TIMEOUT)
        after_join = joiner.calls[joiner.calls.index("join") + 1 :]
        assert "forget" in after_join
        assert "disassociate" in after_join
        assert joiner.rejoins == [(ORIGINAL_SSID, "")]

    async def test_a_second_cancel_during_recovery_does_not_cut_it_short(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()
        joiner.after_disassociate = [None] * 1000
        task = await self._cancel_during_wait(home_network, joiner, cancel_twice=True)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, HANG_GUARD_TIMEOUT)
        assert joiner.rejoins == [(ORIGINAL_SSID, "")]

    async def test_cancel_during_recovery_after_a_failure_wins(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner()
        joiner.after_disassociate = [None] * 1000
        softap = FakeSoftApClient(probe_failures=100_000)
        recovering = asyncio.Event()

        def on_event(event: OnboardEvent) -> None:
            if event.type is OnboardEventType.WAITING_FOR_SOFTAP:
                recovering.set()

        task = asyncio.ensure_future(
            _run(home_network, joiner, softap=softap, on_event=on_event)
        )
        await asyncio.wait_for(recovering.wait(), HANG_GUARD_TIMEOUT)
        # Let the wait phase expire and recovery begin, then cancel.
        while "disassociate" not in joiner.calls:
            await asyncio.sleep(0.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as info:
            await asyncio.wait_for(task, HANG_GUARD_TIMEOUT)
        # The failure is logged, not chained: a chained error could carry a
        # backend's message into the cancellation's traceback. asyncio may
        # attach another CancelledError as the implicit context, which is
        # harmless; a backend's Exception never may be.
        assert info.value.__cause__ is None
        assert not isinstance(info.value.__context__, Exception)
        assert joiner.rejoins == [(ORIGINAL_SSID, "")]


class TestNoPasswordInTracebacks:
    async def test_cancel_while_sleeping_after_a_rejoin_error_leaves_no_trace(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = _full_joiner(rejoin_failures=10_000, rejoin_error_echoes_password=True)
        joiner.after_disassociate = [None] * 100_000
        task = asyncio.ensure_future(
            _run(
                home_network,
                joiner,
                rejoin_poll=0.5,
                rejoin_timeout=0.05,
                auto_join_wait=0.01,
            )
        )
        # The first rejoin attempt has failed and the loop is sleeping.
        while not joiner.rejoins:
            await asyncio.sleep(0.001)
        await asyncio.sleep(0.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as info:
            await asyncio.wait_for(task, HANG_GUARD_TIMEOUT)
        error = info.value
        rendered = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        assert HOME_PASSWORD not in rendered
        assert "nmcli" not in rendered
        chain = []
        link: BaseException | None = error
        while link is not None:
            chain.append(link)
            link = link.__context__
        assert all(HOME_PASSWORD not in str(link) for link in chain)
        # Recovery still ran, and its own rejoin errors left no trace either.
        assert len(joiner.rejoins) >= 2
