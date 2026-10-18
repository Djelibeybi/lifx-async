"""Tests for onboarding events, the bounded event queue and the Result type."""

from __future__ import annotations

import asyncio
import dataclasses

import pytest

from lifx.onboard import (
    OnboardEvent,
    OnboardEventQueue,
    OnboardEventType,
    OnboardPhase,
)
from tests.conftest import HANG_GUARD_TIMEOUT


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
