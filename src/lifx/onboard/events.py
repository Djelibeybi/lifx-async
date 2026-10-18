"""Progress events emitted by the onboarding state machine.

Events reach a caller two ways: an ``on_event`` callback, called synchronously
as each event happens, and :class:`OnboardEventQueue`, a bounded queue that
drops the oldest event when it is full. Neither path ever blocks the state
machine, so a slow UI cannot stall an onboarding mid-handoff.

An event never carries the home network password; there is no field for it.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from enum import Enum

from lifx.onboard.errors import OnboardPhase
from lifx.onboard.models import SoftApNetwork
from lifx.protocol.models import Serial

__all__ = ["OnboardEvent", "OnboardEventQueue", "OnboardEventType"]


class OnboardEventType(Enum):
    """What an :class:`OnboardEvent` reports."""

    SCANNING = "scanning"
    DISCOVERED = "discovered"
    JOINING = "joining"
    JOINED = "joined"
    WAITING_FOR_SOFTAP = "waiting_for_softap"
    ON_SOFTAP = "on_softap"
    DIALING = "dialing"
    CONFIGURED = "configured"
    REJOINING = "rejoining"
    REJOINED = "rejoined"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass(frozen=True)
class OnboardEvent:
    """One step of progress through the onboarding sequence.

    Attributes:
        type: What happened.
        phase: The phase the event belongs to; ``None`` only when a failure
            has no phase.
        serial: The device being onboarded, once known.
        ssid: The network the event concerns (a SoftAP or a host network).
        address: The SoftAP address, for the wait and dial phases.
        networks: Every network the scan returned, for ``DISCOVERED``.
        timeout: The budget a phase started with, for the events that open one.
        took: Seconds a step took, for the events that close one.
        error: The failure, for ``FAILED``.
    """

    type: OnboardEventType
    phase: OnboardPhase | None
    serial: Serial | None = None
    ssid: str | None = None
    address: str | None = None
    networks: tuple[SoftApNetwork, ...] = ()
    timeout: float | None = None
    took: float | None = None
    error: BaseException | None = None


class OnboardEventQueue:
    """A bounded queue of :class:`OnboardEvent` that never blocks the producer.

    When the queue is full the oldest event is dropped and :attr:`dropped`
    is incremented, the way ``DeviceWatcher`` bounds its event iterator.
    Iterate with ``async for``; the loop ends once :meth:`close` has been
    called and every queued event has been consumed. The state machine never
    closes a queue it was handed, so one queue can serve several runs.

    Args:
        maxsize: The most events held at once; at least 1.
    """

    def __init__(self, maxsize: int = 256) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        self.maxsize = maxsize
        self._queue: deque[OnboardEvent] = deque()
        self._dropped = 0
        self._closed = False
        self._wakeup = asyncio.Event()

    @property
    def dropped(self) -> int:
        """Events dropped because the queue was full."""
        return self._dropped

    def __len__(self) -> int:
        return len(self._queue)

    def put(self, event: OnboardEvent) -> None:
        """Queue ``event``, dropping the oldest event first when full."""
        if len(self._queue) >= self.maxsize:
            self._queue.popleft()
            self._dropped += 1
        self._queue.append(event)
        self._wakeup.set()

    def get_nowait(self) -> OnboardEvent | None:
        """Pop the oldest queued event, or ``None`` if there is none."""
        if self._queue:
            return self._queue.popleft()
        return None

    def close(self) -> None:
        """End iteration once the queued events have been consumed."""
        self._closed = True
        self._wakeup.set()

    def __aiter__(self) -> OnboardEventQueue:
        return self

    async def __anext__(self) -> OnboardEvent:
        while True:
            event = self.get_nowait()
            if event is not None:
                return event
            if self._closed:
                raise StopAsyncIteration
            self._wakeup.clear()
            await self._wakeup.wait()
