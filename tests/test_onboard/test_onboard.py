"""Tests for the onboard() sequence: targets, phases, events and results."""

from __future__ import annotations

import pytest

from lifx.onboard import (
    HomeNetwork,
    InvalidSoftApTargetError,
    OnboardEventQueue,
    OnboardEventType,
    OnboardPhase,
    SoftApJoinError,
    SoftApNetwork,
    SoftApNotFoundError,
    SoftApWaitTimeoutError,
    onboard,
)
from lifx.protocol.models import Serial
from tests.test_onboard.conftest import (
    HOME_SSID,
    ORIGINAL_SSID,
    OTHER_SOFTAP_SSID,
    SOFTAP_SERIAL,
    SOFTAP_SSID,
    FakeSoftApClient,
    make_joiner,
    make_scanner,
    softap_network,
)

FAST = {
    "find_timeout": 0.2,
    "find_poll": 0.005,
    "wait_timeout": 0.2,
    "wait_poll": 0.005,
    "dial_timeout": 0.2,
    "rejoin_timeout": 0.2,
    "rejoin_poll": 0.005,
    "auto_join_wait": 0.05,
}

HAPPY_PATH_EVENTS = [
    OnboardEventType.SCANNING,
    OnboardEventType.DISCOVERED,
    OnboardEventType.JOINING,
    OnboardEventType.JOINED,
    OnboardEventType.WAITING_FOR_SOFTAP,
    OnboardEventType.ON_SOFTAP,
    OnboardEventType.DIALING,
    OnboardEventType.CONFIGURED,
    OnboardEventType.REJOINING,
    OnboardEventType.REJOINED,
]

#: What a ``verify=True`` run appends to the happy path.
VERIFY_EVENTS = [OnboardEventType.VERIFYING, OnboardEventType.VERIFIED]


async def test_full_ssid_target_skips_the_scan(home_network: HomeNetwork) -> None:
    joiner = make_joiner(current=ORIGINAL_SSID, reporter=True)
    softap = FakeSoftApClient()
    seen = []

    result = await onboard(
        home_network,
        scanner=None,
        joiner=joiner,
        target=SOFTAP_SSID,
        softap=softap,
        verify=False,
        on_event=seen.append,
        **FAST,
    )

    assert result.serial == SOFTAP_SERIAL
    assert result.verified is False
    assert result.phase is None
    assert result.error is None
    assert result.host_network == ORIGINAL_SSID
    assert result.took >= 0.0
    assert [event.type for event in seen] == HAPPY_PATH_EVENTS[2:]
    assert [network.ssid for network in joiner.joins] == [SOFTAP_SSID]
    assert softap.sent == [(SOFTAP_SERIAL, home_network)]
    assert softap.opened == 1
    assert softap.closed == 1
    assert joiner.rejoins == [(ORIGINAL_SSID, "")]
    joined = seen[1]
    assert joined.phase is OnboardPhase.JOIN
    assert joined.ssid == SOFTAP_SSID
    assert joined.serial == SOFTAP_SERIAL
    assert joined.took is not None
    assert seen[-1].ssid == ORIGINAL_SSID
    configured = seen[5]
    assert configured.ssid == HOME_SSID
    assert configured.serial == SOFTAP_SERIAL


async def _run(home_network: HomeNetwork, **overrides):
    """Run onboard() with fakes, returning (result, joiner, scanner, softap, events)."""
    scanner = overrides.pop("scanner", make_scanner([softap_network()]))
    joiner = overrides.pop("joiner", make_joiner(current=ORIGINAL_SSID, reporter=True))
    softap = overrides.pop("softap", FakeSoftApClient())
    seen = []
    kwargs = {**FAST, **overrides}
    result = await onboard(
        home_network,
        scanner=scanner,
        joiner=joiner,
        softap=softap,
        verify=False,
        on_event=seen.append,
        **kwargs,
    )
    return result, joiner, scanner, softap, seen


class TestTargets:
    async def test_serial_target_scans_until_that_device_appears(
        self, home_network: HomeNetwork
    ) -> None:
        scanner = make_scanner(
            [softap_network(OTHER_SOFTAP_SSID)],
            [softap_network(OTHER_SOFTAP_SSID), softap_network()],
        )
        result, _, scanner, softap, seen = await _run(
            home_network, scanner=scanner, target=SOFTAP_SERIAL, min_rssi=-70.0
        )
        assert result.serial == SOFTAP_SERIAL
        assert len(scanner.calls) == 2
        assert scanner.calls[0] == {"min_rssi": -70.0, "include_non_lifx": False}
        assert [event.type for event in seen] == HAPPY_PATH_EVENTS
        discovered = seen[1]
        assert discovered.phase is OnboardPhase.SCAN
        assert discovered.serial == SOFTAP_SERIAL
        assert discovered.ssid == SOFTAP_SSID
        assert [n.ssid for n in discovered.networks] == [OTHER_SOFTAP_SSID, SOFTAP_SSID]
        assert softap.sent[0][0] == SOFTAP_SERIAL

    async def test_serial_string_with_separators_is_accepted(
        self, home_network: HomeNetwork
    ) -> None:
        result, *_ = await _run(home_network, target="D0:73:D5:0A:0B:0C")
        assert result.serial == SOFTAP_SERIAL

    async def test_suffix_target_scans_for_the_serial(
        self, home_network: HomeNetwork
    ) -> None:
        scanner = make_scanner([softap_network(OTHER_SOFTAP_SSID), softap_network()])
        result, joiner, *_ = await _run(home_network, scanner=scanner, target="0a0b0c")
        assert result.serial == SOFTAP_SERIAL
        assert [n.ssid for n in joiner.joins] == [SOFTAP_SSID]

    async def test_no_target_takes_the_first_lifx_softap(
        self, home_network: HomeNetwork
    ) -> None:
        foreign = SoftApNetwork.foreign("Neighbour4C0A17", "02:00:00:00:00:01")
        scanner = make_scanner([foreign, softap_network(OTHER_SOFTAP_SSID)])
        result, joiner, *_ = await _run(
            home_network, scanner=scanner, include_non_lifx=True
        )
        assert result.serial == Serial.from_softap_ssid(OTHER_SOFTAP_SSID)
        assert [n.ssid for n in joiner.joins] == [OTHER_SOFTAP_SSID]
        assert scanner.calls[0]["include_non_lifx"] is True

    async def test_full_ssid_target_never_calls_scan(
        self, home_network: HomeNetwork
    ) -> None:
        scanner = make_scanner([softap_network()])
        _, _, scanner, _, seen = await _run(
            home_network, scanner=scanner, target=SOFTAP_SSID
        )
        assert scanner.calls == []
        assert seen[0].type is OnboardEventType.JOINING

    @pytest.mark.parametrize(
        "target", ["LIFX Candle Color zzzzzz", "LIFXabc", "not-a-serial", "0a0b0", ""]
    )
    async def test_unparseable_target_is_rejected_before_any_phase(
        self, home_network: HomeNetwork, target: str
    ) -> None:
        scanner = make_scanner([softap_network()])
        joiner = make_joiner(current=ORIGINAL_SSID, reporter=True)
        seen = []
        with pytest.raises(InvalidSoftApTargetError) as info:
            await onboard(
                home_network,
                scanner=scanner,
                joiner=joiner,
                target=target,
                softap=FakeSoftApClient(),
                verify=False,
                on_event=seen.append,
                **FAST,
            )
        assert info.value.phase is None
        assert info.value.result is None
        assert seen == []
        assert scanner.calls == []
        assert joiner.calls == []

    async def test_scan_needs_a_scanner(self, home_network: HomeNetwork) -> None:
        joiner = make_joiner(current=ORIGINAL_SSID, reporter=True)
        with pytest.raises(ValueError, match="scanner is required"):
            await onboard(
                home_network,
                scanner=None,
                joiner=joiner,
                target=SOFTAP_SERIAL,
                softap=FakeSoftApClient(),
                verify=False,
                **FAST,
            )
        assert joiner.calls == []


class TestScan:
    async def test_scan_is_retried_until_the_softap_appears(
        self, home_network: HomeNetwork
    ) -> None:
        scanner = make_scanner([], [], [softap_network()])
        result, _, scanner, *_ = await _run(home_network, scanner=scanner)
        assert result.serial == SOFTAP_SERIAL
        assert len(scanner.calls) == 3

    async def test_empty_scans_raise_not_found_with_the_macos_hint(
        self, home_network: HomeNetwork
    ) -> None:
        with pytest.raises(SoftApNotFoundError) as info:
            await _run(home_network, scanner=make_scanner(), target=SOFTAP_SERIAL)
        error = info.value
        assert error.phase is OnboardPhase.SCAN
        assert "macOS" in str(error)
        assert str(SOFTAP_SERIAL) in str(error)
        assert error.__cause__ is None
        assert error.result is not None
        assert error.result.phase is OnboardPhase.SCAN
        assert error.result.error is error
        assert error.result.serial == SOFTAP_SERIAL
        assert error.result.verified is False

    async def test_other_softaps_seen_means_no_redaction_hint(
        self, home_network: HomeNetwork
    ) -> None:
        scanner = make_scanner([softap_network(OTHER_SOFTAP_SSID)])
        with pytest.raises(SoftApNotFoundError) as info:
            await _run(home_network, scanner=scanner, target=SOFTAP_SERIAL)
        assert "macOS" not in str(info.value)

    async def test_transient_error_on_the_last_scan_does_not_mask_not_found(
        self, home_network: HomeNetwork
    ) -> None:
        glitch = RuntimeError("airport busy")
        scanner = make_scanner([], glitch)
        with pytest.raises(SoftApNotFoundError) as info:
            await _run(home_network, scanner=scanner, target=SOFTAP_SERIAL)
        # The scanner's error is named by type only, never chained or quoted.
        assert info.value.__cause__ is None
        assert "RuntimeError" in str(info.value)
        assert "airport busy" not in str(info.value)
        assert "macOS" in str(info.value)
        assert len(scanner.calls) >= 2

    async def test_every_scan_failing_is_still_not_found_without_the_hint(
        self, home_network: HomeNetwork
    ) -> None:
        glitch = RuntimeError("airport busy")
        with pytest.raises(SoftApNotFoundError) as info:
            await _run(home_network, scanner=make_scanner(glitch))
        assert info.value.__cause__ is None
        assert "RuntimeError" in str(info.value)
        assert "macOS" not in str(info.value)
        assert "at all" in str(info.value)

    async def test_scan_failure_emits_failed_once_and_skips_recovery(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = make_joiner(
            current=ORIGINAL_SSID, reporter=True, forgetter=True, disassociator=True
        )
        seen = []
        with pytest.raises(SoftApNotFoundError) as info:
            await onboard(
                home_network,
                scanner=make_scanner(),
                joiner=joiner,
                softap=FakeSoftApClient(),
                verify=False,
                on_event=seen.append,
                **FAST,
            )
        assert [event.type for event in seen] == [
            OnboardEventType.SCANNING,
            OnboardEventType.FAILED,
        ]
        failed = seen[-1]
        assert failed.phase is OnboardPhase.SCAN
        assert failed.error is info.value
        assert joiner.calls == ["current_ssid"]


class TestJoin:
    async def test_join_is_retried_for_find_timeout(
        self, home_network: HomeNetwork
    ) -> None:
        joiner = make_joiner(current=ORIGINAL_SSID, reporter=True, join_failures=2)
        result, joiner, *_ = await _run(home_network, joiner=joiner)
        assert result.phase is None
        assert joiner.calls.count("join") == 3
        assert len(joiner.joins) == 1

    async def test_join_failure_raises_and_recovery_finds_the_host_at_home(
        self, home_network: HomeNetwork
    ) -> None:
        # Recovery runs from the first join attempt because a backend may have
        # changed the association before failing. Here the reporter says the
        # host never left its original network, so recovery forgets the SoftAP
        # and finds the host already home: no disassociate, no rejoin.
        joiner = make_joiner(
            current=ORIGINAL_SSID,
            reporter=True,
            forgetter=True,
            disassociator=True,
            join_failures=10_000,
        )
        with pytest.raises(SoftApJoinError) as info:
            await _run(home_network, joiner=joiner)
        assert info.value.phase is OnboardPhase.JOIN
        assert SOFTAP_SSID in str(info.value)
        assert info.value.__cause__ is None
        assert "OSError" in str(info.value)
        assert joiner.calls.count("join") >= 2
        assert "forget" in joiner.calls
        assert "disassociate" not in joiner.calls
        assert joiner.rejoins == []
        assert info.value.result is not None
        assert info.value.result.host_network == ORIGINAL_SSID


class TestWait:
    async def test_probe_attempts_are_bounded_by_wait_poll(
        self, home_network: HomeNetwork
    ) -> None:
        softap = FakeSoftApClient(probe_failures=2)
        result, _, _, softap, seen = await _run(home_network, softap=softap)
        assert softap.probes == [FAST["wait_poll"]] * 3
        on_softap = next(e for e in seen if e.type is OnboardEventType.ON_SOFTAP)
        assert on_softap.address == softap.address
        assert on_softap.took is not None
        waiting = next(e for e in seen if e.type is OnboardEventType.WAITING_FOR_SOFTAP)
        assert waiting.timeout == FAST["wait_timeout"]
        assert waiting.address == softap.address

    async def test_slow_probe_failures_retry_without_an_extra_sleep(
        self, home_network: HomeNetwork
    ) -> None:
        softap = FakeSoftApClient(probe_failures=1, probe_takes=0.02)
        result, *_ = await _run(home_network, softap=softap)
        assert result.phase is None

    async def test_real_client_is_built_when_none_is_given(
        self, home_network: HomeNetwork, closed_port: int
    ) -> None:
        joiner = make_joiner(current=ORIGINAL_SSID, reporter=True)
        with pytest.raises(SoftApWaitTimeoutError) as info:
            await onboard(
                home_network,
                scanner=make_scanner([softap_network()]),
                joiner=joiner,
                verify=False,
                softap_address="127.0.0.1",
                softap_port=closed_port,
                **FAST,
            )
        assert info.value.phase is OnboardPhase.WAIT
        assert "127.0.0.1" in str(info.value)


class TestEventsDelivery:
    async def test_events_reach_the_queue_in_order(
        self, home_network: HomeNetwork
    ) -> None:
        queue = OnboardEventQueue()
        await _run(home_network, events=queue)
        queue.close()
        assert [event.type async for event in queue] == HAPPY_PATH_EVENTS
        assert queue.dropped == 0


class TestCapabilities:
    async def test_joiner_reporter_wins_over_scanner_reporter(
        self, home_network: HomeNetwork
    ) -> None:
        scanner = make_scanner([softap_network()], reporter=["Scanner-Says"])
        joiner = make_joiner(current=ORIGINAL_SSID, reporter=True)
        result, joiner, scanner, *_ = await _run(
            home_network, scanner=scanner, joiner=joiner
        )
        assert result.host_network == ORIGINAL_SSID
        assert all("current_ssid" not in call for call in scanner.calls)

    async def test_scanner_reporter_is_used_when_the_joiner_has_none(
        self, home_network: HomeNetwork
    ) -> None:
        # The scanner reports the original network once, then the SoftAP
        # for the rest of the run, so the only way "Scanner-Says" can become
        # a rejoin target is through the scanner's reporter.
        scanner = make_scanner(
            [softap_network()], reporter=["Scanner-Says", SOFTAP_SSID]
        )
        joiner = make_joiner()
        result, joiner, *_ = await _run(
            home_network, scanner=scanner, joiner=joiner, rejoin_timeout=0.02
        )
        assert result.host_network == "Scanner-Says"
        assert joiner.rejoins == [("Scanner-Says", "")]
