"""Tests for onboarding events, the bounded event queue and the Result type."""

from __future__ import annotations

import asyncio
import dataclasses
import logging

import pytest

from lifx.onboard import (
    HomeNetwork,
    HostRejoinError,
    OnboardEvent,
    OnboardEventQueue,
    OnboardEventType,
    OnboardPhase,
    onboard,
)
from tests.conftest import HANG_GUARD_TIMEOUT
from tests.test_onboard.conftest import (
    HOME_PASSWORD,
    HOME_SSID,
    ORIGINAL_SSID,
    FakeSoftApClient,
    make_joiner,
    make_scanner,
    softap_network,
)
from tests.test_onboard.test_onboard import FAST


def _event(n: int) -> OnboardEvent:
    return OnboardEvent(
        type=OnboardEventType.SCANNING, phase=OnboardPhase.SCAN, timeout=float(n)
    )


def test_event_type_members_in_spec_order() -> None:
    assert [member.name for member in OnboardEventType] == [
        "SCANNING",
        "DISCOVERED",
        "JOINING",
        "JOINED",
        "WAITING_FOR_SOFTAP",
        "ON_SOFTAP",
        "DIALING",
        "CONFIGURED",
        "REJOINING",
        "REJOINED",
        "VERIFYING",
        "VERIFIED",
        "FAILED",
    ]


def test_event_is_frozen_and_has_no_password_field() -> None:
    event = _event(1)
    assert {f.name for f in dataclasses.fields(event)} == {
        "type",
        "phase",
        "serial",
        "ssid",
        "address",
        "networks",
        "timeout",
        "took",
        "error",
    }
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.ssid = "x"  # type: ignore[misc]


def test_queue_rejects_a_zero_size() -> None:
    with pytest.raises(ValueError):
        OnboardEventQueue(maxsize=0)


def test_queue_drops_the_oldest_when_full_and_counts_drops() -> None:
    queue = OnboardEventQueue(maxsize=2)
    for n in range(4):
        queue.put(_event(n))
    assert queue.dropped == 2
    assert len(queue) == 2
    first = queue.get_nowait()
    second = queue.get_nowait()
    assert first is not None and first.timeout == 2.0
    assert second is not None and second.timeout == 3.0
    assert queue.get_nowait() is None


async def test_iterator_waits_for_the_next_event_and_stops_when_closed() -> None:
    queue = OnboardEventQueue()
    waiter = asyncio.ensure_future(anext(queue))
    await asyncio.sleep(0)
    assert not waiter.done()
    queue.put(_event(7))
    event = await asyncio.wait_for(waiter, HANG_GUARD_TIMEOUT)
    assert event.timeout == 7.0

    queue.put(_event(8))
    queue.close()
    collected = [event async for event in queue]
    assert [event.timeout for event in collected] == [8.0]


async def test_closing_wakes_a_waiting_iterator() -> None:
    queue = OnboardEventQueue()
    waiter = asyncio.ensure_future(anext(queue))
    await asyncio.sleep(0)
    queue.close()
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(waiter, HANG_GUARD_TIMEOUT)


class TestDeliveryDuringOnboarding:
    async def test_a_raising_callback_does_not_abort_onboarding(
        self, home_network: HomeNetwork, caplog: pytest.LogCaptureFixture
    ) -> None:
        calls = 0

        def explode(event: OnboardEvent) -> None:
            nonlocal calls
            calls += 1
            raise RuntimeError("ui crashed")

        with caplog.at_level(logging.ERROR, logger="lifx.onboard"):
            result = await onboard(
                home_network,
                scanner=make_scanner([softap_network()]),
                joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
                softap=FakeSoftApClient(),
                verify=False,
                on_event=explode,
                **FAST,
            )
        assert result.phase is None
        assert calls == 10
        assert "event callback failed" in caplog.text

    async def test_a_full_queue_drops_the_oldest_events(
        self, home_network: HomeNetwork
    ) -> None:
        queue = OnboardEventQueue(maxsize=3)
        await onboard(
            home_network,
            scanner=make_scanner([softap_network()]),
            joiner=make_joiner(current=ORIGINAL_SSID, reporter=True),
            softap=FakeSoftApClient(),
            verify=False,
            events=queue,
            **FAST,
        )
        assert queue.dropped == 7
        queue.close()
        assert [event.type async for event in queue] == [
            OnboardEventType.CONFIGURED,
            OnboardEventType.REJOINING,
            OnboardEventType.REJOINED,
        ]

    async def test_the_password_never_appears_in_events_logs_or_errors(
        self, home_network: HomeNetwork, caplog: pytest.LogCaptureFixture
    ) -> None:
        seen: list[OnboardEvent] = []
        joiner = make_joiner(
            current=ORIGINAL_SSID,
            reporter=True,
            forgetter=True,
            disassociator=True,
            rejoin_failures=10_000,
            forget_error=OSError("no such profile"),
        )
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(HostRejoinError) as info:
                await onboard(
                    home_network,
                    scanner=make_scanner([softap_network()]),
                    joiner=joiner,
                    softap=FakeSoftApClient(),
                    verify=False,
                    on_event=seen.append,
                    events=OnboardEventQueue(),
                    rejoin_ssid=HOME_SSID,
                    rejoin_password="override-secret",
                    **FAST,
                )
        assert seen, "the run emitted events"
        for event in seen:
            assert HOME_PASSWORD not in repr(event)
            assert "override-secret" not in repr(event)
        assert HOME_PASSWORD not in caplog.text
        assert "override-secret" not in caplog.text
        error = info.value
        assert HOME_PASSWORD not in str(error)
        assert HOME_PASSWORD not in repr(error)
        assert HOME_PASSWORD not in repr(error.result)
        assert HOME_SSID in caplog.text, "SSIDs may be logged"

    async def test_a_joiner_error_echoing_the_password_is_never_repeated(
        self, home_network: HomeNetwork, caplog: pytest.LogCaptureFixture
    ) -> None:
        seen: list[OnboardEvent] = []
        joiner = make_joiner(
            current=ORIGINAL_SSID,
            reporter=True,
            forgetter=True,
            disassociator=True,
            rejoin_failures=10_000,
            rejoin_error_echoes_password=True,
        )
        joiner.after_disassociate = [None] * 100_000
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(HostRejoinError) as info:
                await onboard(
                    home_network,
                    scanner=make_scanner([softap_network()]),
                    joiner=joiner,
                    softap=FakeSoftApClient(),
                    verify=False,
                    on_event=seen.append,
                    **{**FAST, "rejoin_timeout": 0.02},
                )
        error = info.value
        assert HOME_PASSWORD not in caplog.text
        assert "nmcli" not in caplog.text
        assert HOME_PASSWORD not in str(error)
        assert HOME_PASSWORD not in repr(error.__cause__ or error)
        assert error.__cause__ is None
        for event in seen:
            assert HOME_PASSWORD not in repr(event)
