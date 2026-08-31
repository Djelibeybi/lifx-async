"""Repository-only value-suppressed observations for discovery measurements."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Literal, cast

_DiscoverySource = Literal["udp", "mdns"]
_DiscoveryStage = Literal["accepted", "winner", "duplicate"]
_OBSERVER_TASK_ATTRIBUTE = "_lifx_discovery_observer"


@dataclass(frozen=True, repr=False)
class _DiscoveryObservation:
    """One in-memory discovery event whose identity is omitted from repr."""

    source: _DiscoverySource
    stage: _DiscoveryStage
    raw_identity: str = field(repr=False)
    firmware_major: int | None = None
    firmware_minor: int | None = None
    connectivity: str | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        """Render categories only so logs cannot expose a hardware identity."""
        return f"{type(self).__name__}(source={self.source!r}, stage={self.stage!r})"


@dataclass(repr=False)
class _DiscoveryObservationSink:
    """Caller-owned append-only sink for one measured discovery call."""

    _observations: list[_DiscoveryObservation] = field(
        default_factory=list,
        init=False,
        repr=False,
    )

    @property
    def observations(self) -> tuple[_DiscoveryObservation, ...]:
        """Return an immutable snapshot of observations in arrival order."""
        return tuple(self._observations)

    def emit(self, observation: _DiscoveryObservation) -> None:
        """Append one already validated in-memory observation."""
        self._observations.append(observation)

    def observe(
        self,
        source: str,
        stage: str,
        raw_identity: str,
        firmware_major: int | None,
        firmware_minor: int | None,
        connectivity: str | None,
    ) -> None:
        """Receive the production callable's value-only event payload."""
        _emit_discovery_observation(
            self,
            source=source,
            stage=stage,
            raw_identity=raw_identity,
            firmware_major=firmware_major,
            firmware_minor=firmware_minor,
            connectivity=connectivity,
        )

    def __repr__(self) -> str:
        """Suppress all observation values while retaining a useful count."""
        return f"{type(self).__name__}(count={len(self._observations)})"


_DISCOVERY_OBSERVATION_SINK: ContextVar[_DiscoveryObservationSink | None] = ContextVar(
    "lifx_discovery_observation_sink", default=None
)


@contextmanager
def _capture_discovery_observations() -> Iterator[_DiscoveryObservationSink]:
    """Attach one caller-local repository observer for the exact async call."""
    task = asyncio.current_task()
    if task is None:
        raise RuntimeError("discovery observation capture requires an asyncio task")
    sink = _DiscoveryObservationSink()
    token = _DISCOVERY_OBSERVATION_SINK.set(sink)
    previous = getattr(task, _OBSERVER_TASK_ATTRIBUTE, None)
    had_previous = hasattr(task, _OBSERVER_TASK_ATTRIBUTE)

    setattr(task, _OBSERVER_TASK_ATTRIBUTE, sink.observe)
    try:
        yield sink
    finally:
        if had_previous:
            setattr(task, _OBSERVER_TASK_ATTRIBUTE, previous)
        else:
            delattr(task, _OBSERVER_TASK_ATTRIBUTE)
        _DISCOVERY_OBSERVATION_SINK.reset(token)


def _current_discovery_observation_sink() -> _DiscoveryObservationSink | None:
    """Return the sink selected by the current caller context, if any."""
    return _DISCOVERY_OBSERVATION_SINK.get()


def _emit_discovery_observation(
    sink: _DiscoveryObservationSink | None,
    *,
    source: _DiscoverySource,
    stage: _DiscoveryStage,
    raw_identity: str,
    firmware_major: int | None = None,
    firmware_minor: int | None = None,
    connectivity: str | None = None,
) -> None:
    """Emit one observation only when an explicit sink was supplied."""
    if sink is None:
        return
    sink.emit(
        _DiscoveryObservation(
            source=cast(_DiscoverySource, source),
            stage=cast(_DiscoveryStage, stage),
            raw_identity=raw_identity,
            firmware_major=firmware_major,
            firmware_minor=firmware_minor,
            connectivity=connectivity,
        )
    )
