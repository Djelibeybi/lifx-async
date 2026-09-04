"""Discovery observation tests importing the canonical scripts-layer helper.

The event/sink/capture-context primitives themselves moved to
``scripts/measurement_support.py`` (Plan 14-03, D-17/D-19): no script may
import a helper from ``tests/``, and
``scripts/measure_merged_discovery.py`` previously loaded this module by
anchored ``importlib`` path specifically to work around that rule. This file
now only re-exports the canonical private names (so existing test imports
keep working unchanged) and proves the properties the measurement scripts
depend on: caller isolation, repr suppression, arrival order, and
deterministic cleanup.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

import scripts.measurement_support as measurement_support
from scripts.measurement_support import (
    _DISCOVERY_OBSERVER_TASK_ATTRIBUTE,
    _capture_discovery_observations,
    _current_discovery_observation_sink,
    _DiscoveryObservation,
    _DiscoveryObservationSink,
    _emit_discovery_observation,
)

__all__ = [
    "_DiscoveryObservation",
    "_DiscoveryObservationSink",
    "_capture_discovery_observations",
    "_current_discovery_observation_sink",
    "_emit_discovery_observation",
]


class TestDiscoveryObservation:
    """Repr suppresses identity while keeping the categories useful."""

    def test_repr_omits_raw_identity_and_connectivity(self) -> None:
        observation = _DiscoveryObservation(
            source="udp",
            stage="accepted",
            raw_identity="d073d5aa11bb",
            firmware_major=3,
            firmware_minor=70,
            connectivity="wifi",
        )

        rendered = repr(observation)

        assert "d073d5aa11bb" not in rendered
        assert "wifi" not in rendered
        assert "source='udp'" in rendered
        assert "stage='accepted'" in rendered

    def test_sink_repr_reveals_only_a_count(self) -> None:
        sink = _DiscoveryObservationSink()
        sink.emit(
            _DiscoveryObservation(source="mdns", stage="winner", raw_identity="abc")
        )

        rendered = repr(sink)

        assert "abc" not in rendered
        assert "count=1" in rendered


class TestCaptureDiscoveryObservations:
    """The context manager attaches, isolates, and cleans up deterministically."""

    async def test_observations_arrive_in_emitted_order(self) -> None:
        with _capture_discovery_observations() as sink:
            task = asyncio.current_task()
            assert task is not None
            observer = getattr(task, _DISCOVERY_OBSERVER_TASK_ATTRIBUTE)
            observer("udp", "accepted", "first", None, None, None)
            observer("mdns", "winner", "second", None, None, None)
            observer("udp", "duplicate", "third", None, None, None)

        stages = [observation.stage for observation in sink.observations]
        assert stages == ["accepted", "winner", "duplicate"]

    async def test_cleanup_restores_the_task_attribute_via_finally(self) -> None:
        task = asyncio.current_task()
        assert task is not None
        assert not hasattr(task, _DISCOVERY_OBSERVER_TASK_ATTRIBUTE)

        with pytest.raises(RuntimeError):
            with _capture_discovery_observations():
                assert hasattr(task, _DISCOVERY_OBSERVER_TASK_ATTRIBUTE)
                raise RuntimeError("boom")

        assert not hasattr(task, _DISCOVERY_OBSERVER_TASK_ATTRIBUTE)
        assert _current_discovery_observation_sink() is None

    async def test_nested_capture_restores_the_outer_observer(self) -> None:
        with _capture_discovery_observations() as outer:
            outer_observer = getattr(
                asyncio.current_task(), _DISCOVERY_OBSERVER_TASK_ATTRIBUTE
            )
            with _capture_discovery_observations() as inner:
                inner_observer = getattr(
                    asyncio.current_task(), _DISCOVERY_OBSERVER_TASK_ATTRIBUTE
                )
                assert inner_observer is not outer_observer
                inner_observer("udp", "accepted", "inner-only", None, None, None)
            restored_observer = getattr(
                asyncio.current_task(), _DISCOVERY_OBSERVER_TASK_ATTRIBUTE
            )
            assert restored_observer is outer_observer
            outer_observer("mdns", "winner", "outer-only", None, None, None)

        assert [o.raw_identity for o in inner.observations] == ["inner-only"]
        assert [o.raw_identity for o in outer.observations] == ["outer-only"]

    async def test_concurrent_tasks_do_not_share_a_sink(self) -> None:
        """Caller isolation: each task's capture only ever sees its own task."""
        results: dict[str, tuple[str, ...]] = {}

        async def _run(label: str) -> None:
            with _capture_discovery_observations() as sink:
                observer = getattr(
                    asyncio.current_task(), _DISCOVERY_OBSERVER_TASK_ATTRIBUTE
                )
                await asyncio.sleep(0)
                observer("udp", "accepted", label, None, None, None)
                await asyncio.sleep(0)
            results[label] = tuple(o.raw_identity for o in sink.observations)

        await asyncio.gather(_run("task-a"), _run("task-b"))

        assert results == {"task-a": ("task-a",), "task-b": ("task-b",)}

    def test_capture_outside_a_running_loop_raises(self) -> None:
        """No task can be selected without a running loop at all."""
        with pytest.raises(RuntimeError, match="no running event loop"):
            with _capture_discovery_observations():
                pass

    async def test_capture_when_current_task_is_none_raises(self) -> None:
        """`asyncio.current_task()` can return `None` from inside a running
        loop when the calling code is not itself a Task (rather than raising
        `RuntimeError` outright, which only happens with no loop at all)."""
        with patch.object(
            measurement_support.asyncio, "current_task", return_value=None
        ):
            with pytest.raises(
                RuntimeError, match="discovery observation capture requires an asyncio"
            ):
                with _capture_discovery_observations():
                    pass

    async def test_emit_without_a_sink_is_a_no_op(self) -> None:
        _emit_discovery_observation(
            None, source="udp", stage="accepted", raw_identity="unsunk"
        )
