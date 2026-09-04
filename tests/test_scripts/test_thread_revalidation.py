"""Tests for the Phase 14 THREAD-02 request-observation tracer.

Wave-0 RED suite for plan 14-01 (14-CONTEXT.md D-07/D-17/D-19). Covers the
closed-schema validation contract, the append/reload round trip, deterministic
latency/RTT derivation, and one end-to-end trace of a retransmitted fake
SetPower acknowledgement through the real ``DeviceConnection`` retry engine.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from lifx.animation.animator import AnimatorStats
from lifx.color import HSBK
from lifx.const import REQUEST_RETRANSMIT_GAPS
from lifx.devices.ceiling import CeilingLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixEffect, MatrixLight
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight
from lifx.exceptions import LifxNetworkError, LifxTimeoutError
from lifx.network.connection import DeviceConnection
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Device
from lifx.protocol.protocol_types import FirmwareEffect
from scripts.measurement_support import (
    ANIMATION_SCHEDULE,
    DISCOVERY_ROUNDS,
    REQUEST_TRIALS,
    STALENESS_CAP_S,
    STALENESS_CONFIRM_ABSENT_POLLS,
    STALENESS_POLL_INTERVAL_S,
    CapturedState,
    RestoreOutcome,
    capture_device_state,
    contains_forbidden_key,
    contains_forbidden_value,
    generate_manifest_schedules,
    git_revision,
    is_binary_power,
    load_jsonl,
    restore_and_verify_device_state,
    summarise_latencies_ns,
    validate_alias,
    validate_revision,
    validate_session_id,
)
from scripts.thread_revalidation import (
    PowerScriptError,
    RosterDriftError,
    _load_target_alias_map,
    _posix_evidence_dir,
    _run_power_script,
    _validate_request_event,
    append_animation_event,
    append_closure_event,
    append_discovery_event,
    append_request_event,
    append_request_trial_event,
    append_staleness_event,
    build_animation_event,
    build_closure_event,
    build_discovery_event,
    build_manifest,
    build_request_event,
    build_request_trial_event,
    build_staleness_event,
    contains_forbidden_vocabulary,
    derive_class_ledger_from_roster,
    derive_request_result,
    expected_alias_roster,
    expected_roster_by_class,
    generate_class_ledger,
    generate_report,
    generate_summary,
    init_manifest,
    load_manifest,
    reload_animation_events,
    reload_closure_events,
    reload_discovery_events,
    reload_request_events,
    reload_request_trial_events,
    reload_staleness_events,
    run_animation_observation,
    run_discovery_session,
    run_one_request_trial,
    run_request_trials,
    run_staleness_experiment,
    trace_request,
    validate_expected_roster,
    validate_staged_evidence,
)
from scripts.thread_revalidation import (
    main as thread_revalidation_main,
)

_REVISION = "a" * 40
_REVISION_B = "b" * 40


def _manifest_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "session_id": "session-alpha",
        "protocol_version": 1,
        "revision": _REVISION,
        "inventory": [
            {"alias": "candle-1", "device_class": "MatrixLight", "available": True},
            {"alias": "mini-1", "device_class": "Light", "available": True},
        ],
        "confounders": [],
        "seed": 42,
    }
    kwargs.update(overrides)
    return kwargs


def _discovery_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "session_id": "session-alpha",
        "protocol_version": 1,
        "revision": _REVISION,
        "round_number": 1,
        "source": "discover",
        "outcome": "success",
        "devices": ["candle-1"],
        "provenance": "synthetic",
        "confounders": [],
    }
    kwargs.update(overrides)
    return kwargs


def _request_trial_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "session_id": "session-alpha",
        "protocol_version": 1,
        "revision": _REVISION,
        "alias": "candle-1",
        "trial": 1,
        "outcome": "completed",
        "logical_latency_ns": 1_000_000,
        "ack_rtt_ns": 900_000,
        "thread_connection": True,
        "provenance": "synthetic",
        "confounders": [],
    }
    kwargs.update(overrides)
    return kwargs


def _animation_rate(fps: int, duration_s: float, **overrides: Any) -> dict[str, Any]:
    rate: dict[str, Any] = {
        "fps": fps,
        "duration_s": duration_s,
        "outcome": "completed",
        "offered": fps * int(duration_s),
        "packets_sent": fps * int(duration_s),
        "total_time_ms": 5.0,
        "gated": 0,
        "acks_outstanding": 0,
        "failed": 0,
    }
    rate.update(overrides)
    return rate


def _animation_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "session_id": "session-alpha",
        "protocol_version": 1,
        "revision": _REVISION,
        "alias": "candle-1",
        "pre_liveness": True,
        "rates": [
            _animation_rate(fps, duration) for fps, duration in ANIMATION_SCHEDULE
        ],
        "post_liveness": True,
        "restored": True,
        "restoration_verified": True,
        "provenance": "synthetic",
        "confounders": [],
    }
    kwargs.update(overrides)
    return kwargs


def _present_poll(poll: int, elapsed_s: float) -> dict[str, Any]:
    return {
        "poll": poll,
        "elapsed_s": elapsed_s,
        "discover_present": True,
        "discover_mdns_present": True,
    }


def _absent_poll(poll: int, elapsed_s: float) -> dict[str, Any]:
    return {
        "poll": poll,
        "elapsed_s": elapsed_s,
        "discover_present": False,
        "discover_mdns_present": False,
    }


def _staleness_kwargs(**overrides: Any) -> dict[str, Any]:
    polls = [
        _present_poll(1, 0.0),
        _absent_poll(2, 60.0),
        _absent_poll(3, 120.0),
        _absent_poll(4, 180.0),
    ]
    kwargs: dict[str, Any] = {
        "session_id": "session-alpha",
        "protocol_version": 1,
        "revision": _REVISION,
        "alias": "candle-1",
        "disconnect_ns": 0,
        "polls": polls,
        "disposition": "confirmed_expiry",
        "restored_available_ns": 200,
        "restoration_duration_s": 12.5,
        "provenance": "synthetic",
        "confounders": [],
    }
    kwargs.update(overrides)
    return kwargs


def _closure_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "session_id": "session-alpha",
        "protocol_version": 1,
        "revision": _REVISION,
        "device_class": "MatrixLight",
        "disposition": "evidence_backed",
        "aliases": ["candle-1"],
        "provenance": "physical",
    }
    kwargs.update(overrides)
    return kwargs


def _seed_complete_session(session_dir: Path) -> None:
    """Build a session that closes every available class on real predicates.

    Deliberately NOT a fixture of hand-written ledger output: it seeds the
    journals the closure derivation actually reads, so a test built on it
    exercises `_alias_has_physical_discovery_evidence` and
    `_alias_has_complete_physical_requests` rather than a stub of them. Every
    roster alias gets physical discovery evidence and a full REQUEST_TRIALS
    run, and the two gap-only classes get their named-gap rows.
    """
    aliases = [entry["alias"] for entry in _FULL_ROSTER]
    init_manifest(
        session_dir,
        session_id="session-alpha",
        protocol_version=1,
        revision=_REVISION,
        inventory=_FULL_ROSTER,
        confounders=[],
        seed=7,
    )
    append_discovery_event(
        session_dir / "14-DISCOVERY.jsonl",
        build_discovery_event(
            **_discovery_kwargs(devices=aliases, provenance="physical")
        ),
    )
    for alias in aliases:
        for trial in range(1, REQUEST_TRIALS + 1):
            append_request_trial_event(
                session_dir / "14-REQUESTS.jsonl",
                build_request_trial_event(
                    **_request_trial_kwargs(
                        alias=alias, trial=trial, provenance="physical"
                    )
                ),
            )
    for device_class in ("InfraredLight", "HevLight"):
        append_closure_event(
            session_dir / "14-CLOSURE.jsonl",
            build_closure_event(
                **_closure_kwargs(
                    device_class=device_class,
                    disposition="named_gap",
                    aliases=[],
                    gap_reason="no Thread-capable hardware of this class",
                    gap_recorded_date="2026-09-04",
                    provenance=None,
                )
            ),
        )


# Mirrors the existing test_connection_retry.py convention: sends to this
# address vanish and no responses ever arrive.
_OFFLINE_IP = "192.168.1.100"
_OFFLINE_SERIAL = "d073d5001234"
_ACKNOWLEDGEMENT_PKT_TYPE = 45


def _valid_record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": 1,
        "kind": "request_observation_event",
        "session_id": "trial-01",
        "category": "sent",
        "sequence": 0,
        "timestamp_ns": 1_000,
        "thread_connection": None,
    }
    record.update(overrides)
    return record


class TestValidateRequestEvent:
    """Closed-schema validation: unexpected content is rejected outright."""

    def test_accepts_a_well_formed_row(self) -> None:
        _validate_request_event(_valid_record())  # must not raise

    def test_rejects_unexpected_extra_key(self) -> None:
        record = _valid_record()
        record["serial"] = "d073d5001234"
        with pytest.raises(ValueError, match="unexpected keys"):
            _validate_request_event(record)

    def test_rejects_missing_key(self) -> None:
        record = _valid_record()
        del record["timestamp_ns"]
        with pytest.raises(ValueError, match="unexpected keys"):
            _validate_request_event(record)

    def test_rejects_wrong_schema_version(self) -> None:
        with pytest.raises(ValueError, match="schema_version"):
            _validate_request_event(_valid_record(schema_version=2))

    def test_rejects_wrong_kind(self) -> None:
        with pytest.raises(ValueError, match="kind"):
            _validate_request_event(_valid_record(kind="something_else"))

    def test_rejects_empty_session_id(self) -> None:
        with pytest.raises(ValueError, match="session_id"):
            _validate_request_event(_valid_record(session_id=""))

    def test_rejects_serial_shaped_session_id(self) -> None:
        with pytest.raises(ValueError, match="identifier-shaped"):
            _validate_request_event(_valid_record(session_id="d073d5001234"))

    def test_rejects_unknown_category(self) -> None:
        with pytest.raises(ValueError, match="category"):
            _validate_request_event(_valid_record(category="mystery"))

    @pytest.mark.parametrize("sequence", [-1, 256, True, 1.5, "0"])
    def test_rejects_invalid_sequence(self, sequence: Any) -> None:
        with pytest.raises(ValueError, match="sequence"):
            _validate_request_event(_valid_record(sequence=sequence))

    def test_accepts_null_sequence(self) -> None:
        _validate_request_event(_valid_record(category="logical_start", sequence=None))

    @pytest.mark.parametrize("timestamp_ns", [-1, True, 1.5, "0"])
    def test_rejects_invalid_timestamp(self, timestamp_ns: Any) -> None:
        with pytest.raises(ValueError, match="timestamp_ns"):
            _validate_request_event(_valid_record(timestamp_ns=timestamp_ns))

    def test_rejects_non_boolean_thread_connection(self) -> None:
        with pytest.raises(ValueError, match="null or bool"):
            _validate_request_event(
                _valid_record(category="accepted", thread_connection="yes")
            )

    def test_rejects_thread_connection_on_non_accepted_category(self) -> None:
        with pytest.raises(ValueError, match="thread_connection"):
            _validate_request_event(
                _valid_record(category="sent", thread_connection=True)
            )

    def test_accepts_thread_connection_on_accepted_category(self) -> None:
        _validate_request_event(
            _valid_record(category="accepted", thread_connection=True)
        )


class TestAppendAndReload:
    """Append-only journal round trip (D-18/D-20 precursor)."""

    def test_append_then_reload_round_trips(self, tmp_path: Path) -> None:
        path = tmp_path / "journal.jsonl"
        first = _valid_record(category="logical_start", sequence=None)
        second = _valid_record(category="sent", sequence=0)
        append_request_event(path, first)
        append_request_event(path, second)

        events = reload_request_events(path)

        assert events == [first, second]

    def test_append_rejects_invalid_record_before_writing(self, tmp_path: Path) -> None:
        path = tmp_path / "journal.jsonl"
        with pytest.raises(ValueError):
            append_request_event(path, _valid_record(category="not-a-category"))
        assert not path.exists() or path.read_text() == ""

    def test_reload_rejects_a_tampered_row(self, tmp_path: Path) -> None:
        path = tmp_path / "journal.jsonl"
        append_request_event(path, _valid_record())
        with path.open("a", encoding="utf-8") as handle:
            handle.write('{"schema_version": 1}\n')
        with pytest.raises(ValueError):
            reload_request_events(path)

    def test_reload_skips_blank_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "journal.jsonl"
        append_request_event(path, _valid_record())
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n")
        events = reload_request_events(path)
        assert len(events) == 1


class TestDeriveRequestResult:
    """Deterministic logical-latency / winning-sequence-RTT derivation (D-07)."""

    def test_derives_distinct_logical_latency_and_ack_rtt(self) -> None:
        events = [
            _valid_record(category="logical_start", sequence=None, timestamp_ns=90),
            _valid_record(category="sent", sequence=0, timestamp_ns=100),
            _valid_record(category="sent", sequence=1, timestamp_ns=150),
            _valid_record(
                category="accepted",
                sequence=1,
                timestamp_ns=200,
                thread_connection=False,
            ),
        ]

        result = derive_request_result(events)

        assert result["logical_latency_ns"] == 200 - 90
        assert result["ack_rtt_ns"] == 200 - 150
        assert result["logical_latency_ns"] != result["ack_rtt_ns"]
        assert result["accepted_sequence"] == 1
        assert result["thread_connection"] is False

    def test_raises_without_logical_start(self) -> None:
        events = [
            _valid_record(category="sent", sequence=0, timestamp_ns=100),
            _valid_record(category="accepted", sequence=0, timestamp_ns=150),
        ]
        with pytest.raises(ValueError, match="logical_start"):
            derive_request_result(events)

    def test_raises_without_accepted(self) -> None:
        events = [
            _valid_record(category="logical_start", sequence=None, timestamp_ns=90),
            _valid_record(category="sent", sequence=0, timestamp_ns=100),
        ]
        with pytest.raises(ValueError, match="accepted"):
            derive_request_result(events)

    def test_raises_when_accepted_sequence_has_no_matching_sent(self) -> None:
        events = [
            _valid_record(category="logical_start", sequence=None, timestamp_ns=90),
            _valid_record(category="sent", sequence=0, timestamp_ns=100),
            _valid_record(category="accepted", sequence=1, timestamp_ns=150),
        ]
        with pytest.raises(ValueError, match="no matching sent"):
            derive_request_result(events)

    def test_a_sent_event_with_a_null_sequence_is_ignored(self) -> None:
        """A schema-valid but sequence-less "sent" row (never emitted by
        production, but not schema-forbidden either) records nothing and
        does not disturb derivation from the real sequenced sent/accepted
        pair."""
        events = [
            _valid_record(category="logical_start", sequence=None, timestamp_ns=90),
            _valid_record(category="sent", sequence=None, timestamp_ns=95),
            _valid_record(category="sent", sequence=0, timestamp_ns=100),
            _valid_record(category="accepted", sequence=0, timestamp_ns=150),
        ]

        result = derive_request_result(events)

        assert result["accepted_sequence"] == 0
        assert result["ack_rtt_ns"] == 150 - 100

    def test_non_correlating_categories_are_ignored(self) -> None:
        """timeout/send_error/cancelled/cleanup events carry no sequence
        table entry or terminal state of their own -- derivation only reads
        logical_start/sent/accepted, and other categories in the same event
        list must not change the result."""
        events = [
            _valid_record(category="logical_start", sequence=None, timestamp_ns=90),
            _valid_record(category="sent", sequence=0, timestamp_ns=100),
            _valid_record(category="accepted", sequence=0, timestamp_ns=150),
            _valid_record(category="cleanup", sequence=None, timestamp_ns=160),
        ]

        result = derive_request_result(events)

        assert result["logical_latency_ns"] == 150 - 90
        assert result["ack_rtt_ns"] == 150 - 100


def _header(
    *, source: int, sequence: int, target: bytes, pkt_type: int, payload_len: int
) -> LifxHeader:
    """Build a valid header for direct queue injection (mirrors
    tests/test_network/test_connection_retry.py's helper of the same name)."""
    return LifxHeader(
        size=36 + payload_len,
        protocol=1024,
        source=source,
        target=target,
        tagged=False,
        ack_required=False,
        res_required=False,
        sequence=sequence,
        pkt_type=pkt_type,
    )


async def _wait_for_keys(
    conn: DeviceConnection, count: int, deadline: float = 2.0
) -> None:
    """Poll ``conn._pending_requests`` until at least ``count`` keys exist."""
    start = time.monotonic()
    while len(conn._pending_requests) < count:
        if time.monotonic() - start > deadline:
            raise AssertionError(
                f"Timed out waiting for {count} pending request key(s); "
                f"got {len(conn._pending_requests)}"
            )
        await asyncio.sleep(0.001)


class TestTraceRequestEndToEnd:
    """One real request path, retransmitted, observed end to end (D-03/D-05/D-07)."""

    async def test_retransmitted_ack_journals_and_derives_distinct_values(
        self, tmp_path: Path
    ) -> None:
        """A no-op SetPower whose first transmission's ack never arrives,
        and whose retransmitted (sequence 1) ack IS accepted, produces a
        validated journal with distinct logical_latency_ns and ack_rtt_ns,
        and the journal file contains no identifier or packet content."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=3
        )
        journal_path = tmp_path / "request-events.jsonl"
        task: asyncio.Task[dict[str, Any]] | None = None
        try:
            await conn.open()
            with patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.05,)):
                task = asyncio.create_task(
                    trace_request(
                        conn,
                        Device.SetPower(level=65535),
                        session_id="fleet-01",
                        journal_path=journal_path,
                        timeout=2.0,
                    )
                )
                await _wait_for_keys(conn, 2)
                key1 = max(conn._pending_requests, key=lambda k: k[1])
                source, sequence, _serial = key1
                assert sequence == 1
                header = _header(
                    source=source,
                    sequence=sequence,
                    target=bytes.fromhex(conn.serial) + b"\x00\x00",
                    pkt_type=_ACKNOWLEDGEMENT_PKT_TYPE,
                    payload_len=0,
                )
                conn._pending_requests[key1].put_nowait((header, b""))
                result = await asyncio.wait_for(task, timeout=1.0)
                task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()

        assert result["accepted_sequence"] == 1
        assert result["logical_latency_ns"] != result["ack_rtt_ns"]
        assert result["ack_rtt_ns"] >= 0
        assert result["thread_connection"] is False

        journal_events = reload_request_events(journal_path)
        assert len(journal_events) >= 3
        assert all(event["session_id"] == "fleet-01" for event in journal_events)
        # Reloading and re-deriving from the on-disk journal must agree with
        # the in-memory result -- proving append/reload is lossless (D-07).
        reloaded_result = derive_request_result(journal_events)
        assert reloaded_result == result

        raw_journal_text = journal_path.read_text(encoding="utf-8")
        assert _OFFLINE_IP not in raw_journal_text
        assert _OFFLINE_SERIAL not in raw_journal_text
        assert conn.serial not in raw_journal_text

    async def test_timeout_still_journals_partial_evidence_and_reraises(
        self, tmp_path: Path
    ) -> None:
        """A trial that never gets an ack still appends its observed events
        (logical_start/sent/timeout/cleanup) before LifxTimeoutError
        propagates -- a failed trial remains part of the evidence (D-03)."""

        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=0.15, max_retries=2
        )
        journal_path = tmp_path / "request-events.jsonl"
        try:
            await conn.open()
            with pytest.raises(LifxTimeoutError):
                await trace_request(
                    conn,
                    Device.SetPower(level=65535),
                    session_id="fleet-02",
                    journal_path=journal_path,
                    timeout=0.15,
                )
        finally:
            await conn.close()

        journal_events = reload_request_events(journal_path)
        categories = [event["category"] for event in journal_events]
        assert categories == ["logical_start", "sent", "timeout", "cleanup"]

    def test_build_request_event_round_trips_through_validation(self) -> None:
        """build_request_event() output already satisfies
        _validate_request_event() -- no separate manual construction path
        can silently drift from the schema it is supposed to produce."""
        from scripts.measurement_support import _RequestObservation

        observation = _RequestObservation(
            category="accepted",
            sequence=3,
            timestamp_ns=42,
            thread_connection=True,
        )
        record = build_request_event(session_id="fleet-03", observation=observation)
        _validate_request_event(record)  # must not raise
        assert record["sequence"] == 3
        assert record["thread_connection"] is True

    async def test_finally_journals_nothing_when_the_capture_context_never_yields(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`sink` stays `None` if `_capture_request_observations()` itself
        raises before yielding -- the `finally` block's `if sink is not
        None:` guard must skip the journal loop entirely rather than crash
        on a `None` sink, and the caller's own exception still propagates."""
        import scripts.measurement_support as measurement_support

        monkeypatch.setattr(measurement_support.asyncio, "current_task", lambda: None)
        journal_path = tmp_path / "request-events.jsonl"

        with pytest.raises(RuntimeError, match="requires an asyncio task"):
            await trace_request(
                None,  # type: ignore[arg-type]
                Device.SetPower(level=65535),
                session_id="fleet-04",
                journal_path=journal_path,
            )

        assert not journal_path.exists()


# ---------------------------------------------------------------------------
# Plan 14-02: shared schedule/statistics primitives (measurement_support.py)
# ---------------------------------------------------------------------------


class TestGenerateManifestSchedules:
    """Seeded, deterministic D-02/D-06 jitter generation."""

    def test_same_seed_yields_byte_identical_schedules(self) -> None:
        first = generate_manifest_schedules(42)
        second = generate_manifest_schedules(42)
        assert first == second

    def test_different_seed_yields_different_schedule(self) -> None:
        first = generate_manifest_schedules(42)
        second = generate_manifest_schedules(43)
        assert first != second

    def test_discovery_gaps_count_and_bounds(self) -> None:
        schedules = generate_manifest_schedules(1)
        assert len(schedules.discovery_round_gaps_s) == DISCOVERY_ROUNDS - 1
        assert all(5.0 <= gap <= 15.0 for gap in schedules.discovery_round_gaps_s)

    def test_request_gaps_count_and_bounds(self) -> None:
        schedules = generate_manifest_schedules(1)
        assert len(schedules.request_trial_gaps_s) == REQUEST_TRIALS - 1
        assert all(0.5 <= gap <= 1.5 for gap in schedules.request_trial_gaps_s)

    def test_does_not_perturb_global_random_state(self) -> None:
        random.seed(1234)
        before = random.getstate()
        generate_manifest_schedules(999)
        assert random.getstate() == before

    @pytest.mark.parametrize("seed", [-1, 2**64, True, 1.5, "0"])
    def test_rejects_invalid_seed(self, seed: Any) -> None:
        with pytest.raises(ValueError, match="seed"):
            generate_manifest_schedules(seed)


class TestSummariseLatenciesNs:
    """Locked D-08 exact median/nearest-rank-p95/max statistics."""

    def test_empty_distribution_is_undefined(self) -> None:
        assert summarise_latencies_ns([]) is None

    def test_single_value(self) -> None:
        result = summarise_latencies_ns([100])
        assert result == {"count": 1, "median_ns": 100, "p95_ns": 100, "max_ns": 100}

    def test_even_count_median(self) -> None:
        result = summarise_latencies_ns([10, 20, 30, 40])
        assert result is not None
        assert result["median_ns"] == 25
        assert result["max_ns"] == 40

    def test_odd_count_median(self) -> None:
        result = summarise_latencies_ns([10, 20, 30])
        assert result is not None
        assert result["median_ns"] == 20

    def test_p95_nearest_rank_boundary(self) -> None:
        # ceil(0.95 * 20) = 19 -> 1-indexed 19th smallest -> index 18.
        values = list(range(1, 21))
        result = summarise_latencies_ns(values)
        assert result is not None
        assert result["p95_ns"] == 19

    def test_order_independent(self) -> None:
        values = [5, 1, 4, 2, 3]
        assert summarise_latencies_ns(values) == summarise_latencies_ns(
            list(reversed(values))
        )


# ---------------------------------------------------------------------------
# Plan 14-02: session manifest (D-01..D-20)
# ---------------------------------------------------------------------------


class TestManifest:
    """Immutable manifest: create-exclusive, byte/semantic-compare on reopen."""

    def test_build_manifest_freezes_generated_schedules_and_constants(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        schedules = generate_manifest_schedules(42)
        assert manifest["discovery_round_gaps_s"] == list(
            schedules.discovery_round_gaps_s
        )
        assert manifest["request_trial_gaps_s"] == list(schedules.request_trial_gaps_s)
        assert manifest["animation_schedule"] == [
            list(rate) for rate in ANIMATION_SCHEDULE
        ]
        assert manifest["staleness_poll_interval_s"] == STALENESS_POLL_INTERVAL_S
        assert (
            manifest["staleness_confirm_absent_polls"] == STALENESS_CONFIRM_ABSENT_POLLS
        )
        assert manifest["staleness_cap_s"] == STALENESS_CAP_S
        assert manifest["request_retransmit_floor_s"] == REQUEST_RETRANSMIT_GAPS[0]

    def test_init_creates_and_reopen_is_idempotent(self, tmp_path: Path) -> None:
        first = init_manifest(tmp_path, **_manifest_kwargs())
        second = init_manifest(tmp_path, **_manifest_kwargs())
        assert first == second
        assert load_manifest(tmp_path) == first

    def test_init_rejects_protocol_version_drift(self, tmp_path: Path) -> None:
        init_manifest(tmp_path, **_manifest_kwargs())
        with pytest.raises(ValueError, match="does not match"):
            init_manifest(tmp_path, **_manifest_kwargs(protocol_version=2))

    def test_init_rejects_revision_drift(self, tmp_path: Path) -> None:
        init_manifest(tmp_path, **_manifest_kwargs())
        with pytest.raises(ValueError, match="does not match"):
            init_manifest(tmp_path, **_manifest_kwargs(revision=_REVISION_B))

    def test_init_rejects_inventory_drift(self, tmp_path: Path) -> None:
        init_manifest(tmp_path, **_manifest_kwargs())
        with pytest.raises(ValueError, match="does not match"):
            init_manifest(tmp_path, **_manifest_kwargs(inventory=[]))

    def test_init_rejects_confounder_drift(self, tmp_path: Path) -> None:
        init_manifest(tmp_path, **_manifest_kwargs())
        with pytest.raises(ValueError, match="does not match"):
            init_manifest(
                tmp_path, **_manifest_kwargs(confounders=["background_pollers"])
            )

    def test_init_rejects_seed_drift(self, tmp_path: Path) -> None:
        init_manifest(tmp_path, **_manifest_kwargs())
        with pytest.raises(ValueError, match="does not match"):
            init_manifest(tmp_path, **_manifest_kwargs(seed=43))

    def test_init_rejects_schedule_drift_via_tampered_file(
        self, tmp_path: Path
    ) -> None:
        init_manifest(tmp_path, **_manifest_kwargs())
        manifest_file = tmp_path / "14-MANIFEST.json"
        tampered = json.loads(manifest_file.read_text(encoding="utf-8"))
        tampered["discovery_round_gaps_s"][0] = 999.0
        with pytest.raises(ValueError, match="discovery_round_gaps_s"):
            _validate_manifest_public(tampered)

    def test_init_rejects_constant_drift(self, tmp_path: Path) -> None:
        init_manifest(tmp_path, **_manifest_kwargs())
        with patch(
            "scripts.thread_revalidation.REQUEST_RETRANSMIT_GAPS",
            (REQUEST_RETRANSMIT_GAPS[0] + 1.0, *REQUEST_RETRANSMIT_GAPS[1:]),
        ):
            with pytest.raises(ValueError, match="does not match"):
                init_manifest(tmp_path, **_manifest_kwargs())

    def test_rejects_duplicate_alias_in_inventory(self) -> None:
        with pytest.raises(ValueError, match="duplicate alias"):
            build_manifest(
                **_manifest_kwargs(
                    inventory=[
                        {
                            "alias": "candle-1",
                            "device_class": "MatrixLight",
                            "available": True,
                        },
                        {
                            "alias": "candle-1",
                            "device_class": "Light",
                            "available": True,
                        },
                    ]
                )
            )

    def test_rejects_gap_class_in_inventory(self) -> None:
        with pytest.raises(ValueError, match="available class"):
            build_manifest(
                **_manifest_kwargs(
                    inventory=[
                        {
                            "alias": "infrared-1",
                            "device_class": "InfraredLight",
                            "available": True,
                        }
                    ]
                )
            )

    def test_rejects_extra_key(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["serial"] = "d073d5001234"
        with pytest.raises(ValueError, match="unexpected keys"):
            _validate_manifest_public(manifest)


def _validate_manifest_public(manifest: dict[str, Any]) -> None:
    """Reach the module-private validator through its one call site."""
    from scripts.thread_revalidation import _validate_manifest

    _validate_manifest(manifest)


# ---------------------------------------------------------------------------
# Plan 14-02: 14-DISCOVERY.jsonl (THREAD-01)
# ---------------------------------------------------------------------------


class TestDiscoveryEvent:
    def test_build_and_validate_round_trip(self) -> None:
        record = build_discovery_event(**_discovery_kwargs())
        assert record["call_order"] == 1  # round 1 -> discover first
        reload_discovery_events  # noqa: B018 -- imported for other tests

    def test_alternation_is_schema_enforced(self) -> None:
        round1 = build_discovery_event(
            **_discovery_kwargs(round_number=1, source="discover")
        )
        round1_mdns = build_discovery_event(
            **_discovery_kwargs(
                round_number=1, source="discover_mdns", outcome="empty", devices=[]
            )
        )
        round2 = build_discovery_event(
            **_discovery_kwargs(round_number=2, source="discover_mdns")
        )
        round2_udp = build_discovery_event(
            **_discovery_kwargs(
                round_number=2, source="discover", outcome="empty", devices=[]
            )
        )
        assert round1["call_order"] == 1
        assert round1_mdns["call_order"] == 2
        assert round2["call_order"] == 1
        assert round2_udp["call_order"] == 2

    def test_success_requires_devices(self) -> None:
        with pytest.raises(ValueError, match="requires at least one device"):
            build_discovery_event(**_discovery_kwargs(outcome="success", devices=[]))

    def test_non_success_forbids_devices(self) -> None:
        with pytest.raises(ValueError, match="only a success"):
            build_discovery_event(
                **_discovery_kwargs(outcome="empty", devices=["candle-1"])
            )

    @pytest.mark.parametrize(
        "outcome", ["empty", "failed", "timeout", "interrupted", "incomplete"]
    )
    def test_every_failure_outcome_is_representable(self, outcome: str) -> None:
        record = build_discovery_event(**_discovery_kwargs(outcome=outcome, devices=[]))
        assert record["outcome"] == outcome

    def test_rejects_out_of_range_round(self) -> None:
        with pytest.raises(ValueError, match="six rounds"):
            build_discovery_event(**_discovery_kwargs(round_number=7))

    def test_rejects_identifier_shaped_device_alias(self) -> None:
        with pytest.raises(ValueError, match="identifier-shaped alias"):
            build_discovery_event(**_discovery_kwargs(devices=["d073d5001234"]))

    def test_append_preserves_prior_bytes_and_rejects_duplicate_round(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "14-DISCOVERY.jsonl"
        first = build_discovery_event(
            **_discovery_kwargs(round_number=1, source="discover")
        )
        append_discovery_event(path, first)
        prefix = path.read_bytes()
        second = build_discovery_event(
            **_discovery_kwargs(round_number=2, source="discover_mdns")
        )
        append_discovery_event(path, second)
        assert path.read_bytes().startswith(prefix)

        duplicate = build_discovery_event(
            **_discovery_kwargs(
                round_number=1, source="discover", outcome="empty", devices=[]
            )
        )
        with pytest.raises(ValueError, match="duplicate row"):
            append_discovery_event(path, duplicate)
        # The rejected duplicate must not have touched the journal.
        assert reload_discovery_events(path) == [first, second]

    def test_privacy_rejects_forbidden_key_before_output_opens(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "missing.jsonl"
        record = build_discovery_event(**_discovery_kwargs())
        record["serial"] = "d073d5001234"  # not a schema key -> rejected before write
        with pytest.raises(ValueError):
            append_discovery_event(path, record)
        assert not path.exists()


# ---------------------------------------------------------------------------
# Plan 14-02: 14-REQUESTS.jsonl (THREAD-02)
# ---------------------------------------------------------------------------


class TestRequestTrialEvent:
    def test_completed_trial_round_trips(self) -> None:
        record = build_request_trial_event(**_request_trial_kwargs())
        assert record["outcome"] == "completed"
        assert record["thread_connection"] is True

    @pytest.mark.parametrize(
        "outcome",
        ["timeout", "send_error", "power_out_of_range", "cancelled", "interrupted"],
    )
    def test_non_completed_outcomes_forbid_latency_fields(self, outcome: str) -> None:
        record = build_request_trial_event(
            **_request_trial_kwargs(
                outcome=outcome,
                logical_latency_ns=None,
                ack_rtt_ns=None,
                thread_connection=None,
            )
        )
        assert record["logical_latency_ns"] is None

    def test_completed_requires_latency_fields(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            build_request_trial_event(
                **_request_trial_kwargs(outcome="completed", logical_latency_ns=None)
            )

    def test_non_completed_rejects_latency_fields(self) -> None:
        with pytest.raises(ValueError, match="must not carry latency"):
            build_request_trial_event(
                **_request_trial_kwargs(outcome="timeout", logical_latency_ns=100)
            )

    def test_rejects_trial_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="100 trials"):
            build_request_trial_event(**_request_trial_kwargs(trial=101))

    def test_append_rejects_duplicate_trial(self, tmp_path: Path) -> None:
        path = tmp_path / "14-REQUESTS.jsonl"
        first = build_request_trial_event(**_request_trial_kwargs(trial=1))
        append_request_trial_event(path, first)
        with pytest.raises(ValueError, match="duplicate row"):
            append_request_trial_event(
                path, build_request_trial_event(**_request_trial_kwargs(trial=1))
            )
        assert reload_request_trial_events(path) == [first]

    def test_power_out_of_range_is_a_valid_terminal_outcome(self) -> None:
        record = build_request_trial_event(
            **_request_trial_kwargs(
                outcome="power_out_of_range",
                logical_latency_ns=None,
                ack_rtt_ns=None,
                thread_connection=None,
            )
        )
        assert record["outcome"] == "power_out_of_range"


# ---------------------------------------------------------------------------
# Plan 14-02: 14-ANIMATION.jsonl (THREAD-03)
# ---------------------------------------------------------------------------


class TestAnimationEvent:
    def test_build_and_validate_round_trip(self) -> None:
        record = build_animation_event(**_animation_kwargs())
        assert [rate["fps"] for rate in record["rates"]] == [1, 2, 5]

    def test_zero_useful_throughput_is_valid(self) -> None:
        zero_rates = [
            _animation_rate(fps, duration, packets_sent=0, offered=fps * int(duration))
            for fps, duration in ANIMATION_SCHEDULE
        ]
        record = build_animation_event(**_animation_kwargs(rates=zero_rates))
        assert all(rate["packets_sent"] == 0 for rate in record["rates"])

    def test_rejects_wrong_rate_count(self) -> None:
        with pytest.raises(ValueError, match="frozen D-10"):
            build_animation_event(**_animation_kwargs(rates=[_animation_rate(1, 10.0)]))

    def test_rejects_fps_out_of_schedule_order(self) -> None:
        rates = [_animation_rate(fps, duration) for fps, duration in ANIMATION_SCHEDULE]
        rates[0]["fps"] = 2
        with pytest.raises(ValueError, match="frozen D-10 schedule"):
            build_animation_event(**_animation_kwargs(rates=rates))

    def test_restoration_verified_requires_restored(self) -> None:
        with pytest.raises(ValueError, match="restoration_verified cannot be true"):
            build_animation_event(
                **_animation_kwargs(restored=False, restoration_verified=True)
            )

    def test_restoration_failed_is_representable_and_retained(
        self, tmp_path: Path
    ) -> None:
        record = build_animation_event(
            **_animation_kwargs(restored=False, restoration_verified=False)
        )
        path = tmp_path / "14-ANIMATION.jsonl"
        append_animation_event(path, record)
        reloaded = reload_animation_events(path)
        assert reloaded == [record]
        assert reloaded[0]["restored"] is False

    def test_rejects_ack_delivery_narration_field(self) -> None:
        """Dedicated negative test (Task 2 acceptance criteria): the closed
        rate schema has no field that could hold an acks-delivered/expired
        narration derived from `acks_outstanding` -- adding one is rejected."""
        rates = [_animation_rate(fps, duration) for fps, duration in ANIMATION_SCHEDULE]
        rates[0]["acks_delivered"] = 3
        with pytest.raises(ValueError, match="invalid animation rate"):
            build_animation_event(**_animation_kwargs(rates=rates))

    def test_generate_summary_never_derives_an_ack_delivery_count(self) -> None:
        """Structural proof alongside the schema rejection above: nothing in
        the generated summary claims acknowledgement delivery/expiry."""
        record = build_animation_event(**_animation_kwargs())
        summary = generate_summary(
            discovery_rows=[],
            request_rows=[],
            animation_rows=[record],
            staleness_rows=[],
            closure_rows=[],
        )
        rendered = json.dumps(summary)
        for forbidden_term in ("acks_delivered", "acks_received", "ack_delivery"):
            assert forbidden_term not in rendered

    def test_append_rejects_duplicate_alias(self, tmp_path: Path) -> None:
        path = tmp_path / "14-ANIMATION.jsonl"
        first = build_animation_event(**_animation_kwargs())
        append_animation_event(path, first)
        with pytest.raises(ValueError, match="duplicate row"):
            append_animation_event(path, build_animation_event(**_animation_kwargs()))


# ---------------------------------------------------------------------------
# Plan 14-02: 14-STALENESS.jsonl (THREAD-04)
# ---------------------------------------------------------------------------


class TestStalenessEvent:
    def test_confirmed_expiry_after_three_consecutive_both_legs_absent(self) -> None:
        record = build_staleness_event(**_staleness_kwargs())
        assert record["first_absence_poll"] == 2
        assert record["confirmed_expiry_poll"] == 4
        assert record["disposition"] == "confirmed_expiry"

    def test_one_leg_present_does_not_count_as_absent(self) -> None:
        polls = [
            _present_poll(1, 0.0),
            {
                "poll": 2,
                "elapsed_s": 60.0,
                "discover_present": False,
                "discover_mdns_present": True,  # mDNS still advertises
            },
            {
                "poll": 3,
                "elapsed_s": 120.0,
                "discover_present": False,
                "discover_mdns_present": True,
            },
        ]
        record = build_staleness_event(
            **_staleness_kwargs(
                polls=polls,
                disposition="interrupted",
                restored_available_ns=None,
                restoration_duration_s=None,
            )
        )
        assert record["first_absence_poll"] is None
        assert record["confirmed_expiry_poll"] is None

    def test_censored_requires_cap(self) -> None:
        polls = [_present_poll(1, 0.0), _absent_poll(2, STALENESS_CAP_S)]
        record = build_staleness_event(
            **_staleness_kwargs(
                polls=polls, disposition="censored", restored_available_ns=999
            )
        )
        assert record["disposition"] == "censored"
        assert record["confirmed_expiry_poll"] is None

    def test_censored_rejected_below_cap(self) -> None:
        with pytest.raises(ValueError, match="reach the cap"):
            build_staleness_event(
                **_staleness_kwargs(
                    polls=[_present_poll(1, 0.0)],
                    disposition="censored",
                    restored_available_ns=1,
                )
            )

    def test_interrupted_allows_null_restoration(self) -> None:
        record = build_staleness_event(
            **_staleness_kwargs(
                polls=[_present_poll(1, 0.0)],
                disposition="interrupted",
                restored_available_ns=None,
                restoration_duration_s=None,
            )
        )
        assert record["restored_available_ns"] is None
        assert record["restoration_duration_s"] is None

    def test_closed_disposition_allows_null_restoration(self) -> None:
        """T-14-06 change 1: a power-on script hard-failure can leave a
        confirmed_expiry/censored/restored_before_expiry row without ever
        confirming restoration -- disposition and restoration are
        deliberately decoupled so the power failure can never erase the
        already-determined finding."""
        record = build_staleness_event(
            **_staleness_kwargs(
                disposition="confirmed_expiry",
                restored_available_ns=None,
                restoration_duration_s=None,
            )
        )
        assert record["disposition"] == "confirmed_expiry"
        assert record["restored_available_ns"] is None
        assert record["restoration_duration_s"] is None

    def test_restoration_duration_requires_a_restored_timestamp(self) -> None:
        with pytest.raises(ValueError, match="restoration_duration_s must be null"):
            build_staleness_event(
                **_staleness_kwargs(
                    disposition="confirmed_expiry",
                    restored_available_ns=None,
                    restoration_duration_s=12.5,
                )
            )

    def test_negative_restoration_duration_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            build_staleness_event(**_staleness_kwargs(restoration_duration_s=-1.0))

    def test_append_rejects_duplicate_alias(self, tmp_path: Path) -> None:
        path = tmp_path / "14-STALENESS.jsonl"
        first = build_staleness_event(**_staleness_kwargs())
        append_staleness_event(path, first)
        with pytest.raises(ValueError, match="duplicate row"):
            append_staleness_event(path, build_staleness_event(**_staleness_kwargs()))


# ---------------------------------------------------------------------------
# Plan 14-02: 14-CLOSURE.jsonl (THREAD-05)
# ---------------------------------------------------------------------------


class TestClosureEvent:
    def test_evidence_backed_requires_physical_provenance(self) -> None:
        with pytest.raises(ValueError, match="physical provenance"):
            build_closure_event(**_closure_kwargs(provenance="synthetic"))

    def test_evidence_backed_requires_available_class(self) -> None:
        with pytest.raises(ValueError, match="currently available"):
            build_closure_event(
                **_closure_kwargs(device_class="InfraredLight", aliases=["mini-1"])
            )

    def test_named_gap_only_for_infrared_and_hev(self) -> None:
        with pytest.raises(ValueError, match="named gap"):
            build_closure_event(
                **_closure_kwargs(
                    device_class="Light",
                    disposition="named_gap",
                    aliases=[],
                    gap_reason="no hardware",
                    gap_recorded_date="2026-08-31",
                    provenance=None,
                )
            )

    def test_named_gap_round_trip(self) -> None:
        record = build_closure_event(
            **_closure_kwargs(
                device_class="InfraredLight",
                disposition="named_gap",
                aliases=[],
                gap_reason="no Thread-capable fleet hardware",
                gap_recorded_date="2026-08-31",
                provenance=None,
            )
        )
        assert record["disposition"] == "named_gap"
        assert record["aliases"] == []

    def test_named_gap_rejects_poor_result_substitution(self) -> None:
        """AC-17: an available class performing poorly cannot become a gap."""
        with pytest.raises(ValueError, match="named gap"):
            build_closure_event(
                **_closure_kwargs(
                    device_class="MatrixLight",
                    disposition="named_gap",
                    aliases=[],
                    gap_reason="poor Thread performance",
                    gap_recorded_date="2026-08-31",
                    provenance=None,
                )
            )

    def test_append_rejects_duplicate_class(self, tmp_path: Path) -> None:
        path = tmp_path / "14-CLOSURE.jsonl"
        first = build_closure_event(**_closure_kwargs())
        append_closure_event(path, first)
        with pytest.raises(ValueError, match="duplicate row"):
            append_closure_event(path, build_closure_event(**_closure_kwargs()))


# ---------------------------------------------------------------------------
# Plan 14-02: deterministic derived products (D-20)
# ---------------------------------------------------------------------------


def _full_closure_rows() -> list[dict[str, Any]]:
    available = ["Light", "MultiZoneLight", "MatrixLight", "CeilingLight"]
    rows = [
        build_closure_event(
            **_closure_kwargs(
                device_class=device_class, aliases=[f"{device_class.lower()}-1"]
            )
        )
        for device_class in available
    ]
    rows.extend(
        build_closure_event(
            **_closure_kwargs(
                device_class=device_class,
                disposition="named_gap",
                aliases=[],
                gap_reason="no Thread-capable fleet hardware",
                gap_recorded_date="2026-08-31",
                provenance=None,
            )
        )
        for device_class in ("InfraredLight", "HevLight")
    )
    return rows


class TestClassLedger:
    def test_complete_ledger_has_all_six_classes(self) -> None:
        ledger = generate_class_ledger(_full_closure_rows())
        assert ledger["complete"] is True
        assert ledger["missing_classes"] == []
        assert set(ledger["classes"]) == {
            "Light",
            "MultiZoneLight",
            "MatrixLight",
            "CeilingLight",
            "InfraredLight",
            "HevLight",
        }

    def test_incomplete_ledger_reports_missing_classes(self) -> None:
        ledger = generate_class_ledger(_full_closure_rows()[:-1])
        assert ledger["complete"] is False
        assert ledger["missing_classes"] == ["HevLight"]

    def test_rejects_duplicate_class_disposition(self) -> None:
        rows = _full_closure_rows()
        rows.append(rows[0])
        with pytest.raises(ValueError, match="duplicate closure disposition"):
            generate_class_ledger(rows)

    def test_order_independent(self) -> None:
        rows = _full_closure_rows()
        shuffled = list(reversed(rows))
        assert generate_class_ledger(rows) == generate_class_ledger(shuffled)


class TestGenerateSummaryAndReport:
    def test_deterministic_regardless_of_row_order(self) -> None:
        discovery_rows = [
            build_discovery_event(
                **_discovery_kwargs(round_number=1, source="discover")
            ),
            build_discovery_event(
                **_discovery_kwargs(round_number=1, source="discover_mdns")
            ),
        ]
        request_rows = [
            build_request_trial_event(**_request_trial_kwargs(trial=1)),
            build_request_trial_event(**_request_trial_kwargs(trial=2)),
        ]
        animation_rows = [build_animation_event(**_animation_kwargs())]
        staleness_rows = [build_staleness_event(**_staleness_kwargs())]
        closure_rows = _full_closure_rows()

        first = generate_summary(
            discovery_rows=discovery_rows,
            request_rows=request_rows,
            animation_rows=animation_rows,
            staleness_rows=staleness_rows,
            closure_rows=closure_rows,
        )
        second = generate_summary(
            discovery_rows=list(reversed(discovery_rows)),
            request_rows=list(reversed(request_rows)),
            animation_rows=list(animation_rows),
            staleness_rows=list(staleness_rows),
            closure_rows=list(reversed(closure_rows)),
        )
        assert first == second
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

    def test_request_summary_uses_locked_statistics(self) -> None:
        request_rows = [
            build_request_trial_event(
                **_request_trial_kwargs(
                    trial=trial, logical_latency_ns=trial * 1000, ack_rtt_ns=trial * 900
                )
            )
            for trial in range(1, 5)
        ]
        summary = generate_summary(
            discovery_rows=[],
            request_rows=request_rows,
            animation_rows=[],
            staleness_rows=[],
            closure_rows=[],
        )
        expected = summarise_latencies_ns([1000, 2000, 3000, 4000])
        assert summary["requests"]["candle-1"]["logical_latency"] == expected

    def test_empty_journals_produce_a_complete_but_gapless_summary(self) -> None:
        summary = generate_summary(
            discovery_rows=[],
            request_rows=[],
            animation_rows=[],
            staleness_rows=[],
            closure_rows=[],
        )
        assert summary["requests"] == {}
        assert summary["class_ledger"]["complete"] is False

    def test_report_never_parses_its_own_output(self) -> None:
        summary = generate_summary(
            discovery_rows=[],
            request_rows=[],
            animation_rows=[],
            staleness_rows=[],
            closure_rows=_full_closure_rows(),
        )
        report_first = generate_report(summary)
        report_second = generate_report(copy.deepcopy(summary))
        assert report_first == report_second
        assert "InfraredLight" in report_first


# ---------------------------------------------------------------------------
# Plan 14-02: minimal CLI (D-17) -- init/validate only, no hardware I/O
# ---------------------------------------------------------------------------


class TestCli:
    def test_no_subcommand_performs_no_io(self, tmp_path: Path, capsys: Any) -> None:
        before = list(tmp_path.iterdir())
        exit_code = thread_revalidation_main([])
        assert exit_code == 2
        assert list(tmp_path.iterdir()) == before

    def test_init_then_validate_round_trip(self, tmp_path: Path, capsys: Any) -> None:
        session_dir = tmp_path / "session"
        inventory = tmp_path / "roster.json"
        inventory.write_text(json.dumps(_FULL_ROSTER), encoding="utf-8")
        exit_code = thread_revalidation_main(
            [
                "init",
                "--session-dir",
                str(session_dir),
                "--session-id",
                "session-alpha",
                "--protocol-version",
                "1",
                "--revision",
                _REVISION,
                "--seed",
                "7",
                "--inventory",
                str(inventory),
            ]
        )
        assert exit_code == 0
        assert (session_dir / "14-MANIFEST.json").exists()

        # Defect 2: init states its verdict as one explicit JSON object, not
        # just implied by the exit code -- the manifest stays available but
        # wrapped in the consistent command/ok/reason envelope.
        init_result = json.loads(capsys.readouterr().out)
        assert init_result["command"] == "init"
        assert init_result["ok"] is True
        assert init_result["reason"] is None
        assert init_result["manifest"]["session_id"] == "session-alpha"

        # Seed the five journals directly (schema-only in this plan; no CLI
        # hardware mode exists yet -- Plan 14-06 supplies real rows).
        append_closure_event(
            session_dir / "14-CLOSURE.jsonl",
            build_closure_event(
                **_closure_kwargs(device_class="MatrixLight", aliases=["candle-1"])
            ),
        )

        exit_code = thread_revalidation_main(
            ["validate", "--session-dir", str(session_dir)]
        )
        assert exit_code == 0

        # validate INSPECTS, it does not produce. It previously wrote all
        # three products unconditionally, which made inspecting a session
        # mutate it -- and on a complete session actively corrupt it, because
        # the ledger it wrote came from the closure-rows-only
        # generate_class_ledger() and so declared every available class
        # missing. generate is the only producer; these must not appear.
        assert not (session_dir / "14-SUMMARY.json").exists()
        assert not (session_dir / "14-CLASS-LEDGER.json").exists()
        assert not (session_dir / "14-REPORT.md").exists()

        # Defect 2: validate must report what it actually checked and found,
        # never a silent green light -- even a partial session states its
        # counts and the resulting ledger completeness explicitly.
        validate_result = json.loads(capsys.readouterr().out)
        assert validate_result["command"] == "validate"
        assert validate_result["ok"] is True
        assert validate_result["counts"] == {
            "discovery": 0,
            "requests": 0,
            "animation": 0,
            "staleness": 0,
            "closure": 1,
        }
        assert validate_result["class_ledger"]["complete"] is False

    def test_validate_never_overwrites_a_complete_session_s_products(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        """validate on a COMPLETE session must not corrupt its ledger.

        The regression this pins: validate used to write products from
        generate_summary(), whose class_ledger is the closure-rows-only
        generate_class_ledger(). Closure rows carry named gaps alone, so on a
        finished session that ledger declared all four available classes
        missing -- and validate overwrote a correct `complete: true` ledger
        with it while printing `ok: true`. Both halves are asserted here: the
        products are untouched, and the reported verdict is the roster-derived
        one that generate and the staged validator also use.
        """
        session_dir = tmp_path / "session"
        roster = tmp_path / "roster.json"
        roster.write_text(json.dumps(_FULL_ROSTER), encoding="utf-8")
        assert (
            thread_revalidation_main(
                [
                    "init",
                    "--session-dir",
                    str(session_dir),
                    "--session-id",
                    "session-alpha",
                    "--revision",
                    _REVISION,
                    "--seed",
                    "7",
                    "--inventory",
                    str(roster),
                ]
            )
            == 0
        )
        capsys.readouterr()

        sentinel = "sentinel-must-survive\n"
        for name in ("14-SUMMARY.json", "14-CLASS-LEDGER.json", "14-REPORT.md"):
            (session_dir / name).write_text(sentinel, encoding="utf-8")

        assert (
            thread_revalidation_main(["validate", "--session-dir", str(session_dir)])
            == 0
        )

        for name in ("14-SUMMARY.json", "14-CLASS-LEDGER.json", "14-REPORT.md"):
            assert (session_dir / name).read_text(encoding="utf-8") == sentinel, (
                f"validate rewrote {name}; it must inspect, never produce"
            )

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "validate"
        assert result["class_ledger"]["missing_classes"] == sorted(
            {"Light", "MultiZoneLight", "MatrixLight", "CeilingLight"}
            | {"InfraredLight", "HevLight"}
        )

    def test_validate_reports_the_roster_derived_verdict_not_the_closure_only_one(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        """The two ledger sources must be distinguishable, and validate picks right.

        An EMPTY session cannot pin this: the closure-rows-only
        generate_class_ledger() and the roster-derived ledger both report all
        six classes missing, so the two agree by accident. This builds a
        session that is complete for every available class, where they
        diverge sharply: the closure-rows-only ledger sees named gaps alone
        and calls the four available classes missing, while the roster-derived
        ledger reads discovery and request evidence and closes them. That
        divergence is the exact bug, so it is what the test asserts.
        """
        session_dir = tmp_path / "session"
        _seed_complete_session(session_dir)
        capsys.readouterr()

        assert (
            thread_revalidation_main(["validate", "--session-dir", str(session_dir)])
            == 0
        )
        result = json.loads(capsys.readouterr().out)

        assert result["class_ledger"]["complete"] is True
        assert result["class_ledger"]["missing_classes"] == []

        # The source it must NOT be using would call every available class
        # missing on this very same session.
        closure_only = generate_class_ledger(
            reload_closure_events(session_dir / "14-CLOSURE.jsonl")
        )
        assert sorted(closure_only["missing_classes"]) == sorted(
            {"CeilingLight", "Light", "MatrixLight", "MultiZoneLight"}
        )

    def test_init_rejects_drift_via_cli(self, tmp_path: Path) -> None:
        session_dir = tmp_path / "session"
        roster_file = tmp_path / "roster.json"
        roster_file.write_text(json.dumps(_FULL_ROSTER), encoding="utf-8")
        base_args = [
            "init",
            "--session-dir",
            str(session_dir),
            "--session-id",
            "session-alpha",
            "--revision",
            _REVISION,
            "--seed",
            "7",
            "--inventory",
            str(roster_file),
        ]
        assert thread_revalidation_main(base_args) == 0
        # argparse's error() path calls sys.exit(2) after printing the cause.
        with pytest.raises(SystemExit):
            thread_revalidation_main([*base_args, "--seed", "8"])

    def test_init_rejects_an_incomplete_roster_before_writing_a_manifest(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        """THREAD-05 roster authority (D-19): the CLI's own completeness gate
        fires at `init`, before any hardware collection could ever start --
        distinct from `generate`'s later Task 3 gate. Defect 2: the refusal
        is stated as an explicit JSON verdict, not just an exit code."""
        session_dir = tmp_path / "session"
        incomplete_inventory = tmp_path / "incomplete-roster.json"
        incomplete_inventory.write_text(
            json.dumps(
                [
                    {
                        "alias": "candle-1",
                        "device_class": "MatrixLight",
                        "available": True,
                    }
                ]
            ),
            encoding="utf-8",
        )
        exit_code = thread_revalidation_main(
            [
                "init",
                "--session-dir",
                str(session_dir),
                "--session-id",
                "session-alpha",
                "--revision",
                _REVISION,
                "--seed",
                "7",
                "--inventory",
                str(incomplete_inventory),
            ]
        )
        assert exit_code == 1
        assert (
            not session_dir.exists() or not (session_dir / "14-MANIFEST.json").exists()
        )

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "init"
        assert result["ok"] is False
        assert result["reason"] == "incomplete_expected_roster"

    def test_init_states_an_unreadable_inventory_file_as_json(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        """A missing roster file is a JSON verdict, never a traceback.

        The roster is operator-authored, so a wrong path is the single most
        likely way this gate is met in practice. It must read as an explicit
        refusal rather than an unhandled OSError the operator has to decode.
        """
        exit_code = thread_revalidation_main(
            [
                "init",
                "--session-dir",
                str(tmp_path / "session"),
                "--session-id",
                "session-alpha",
                "--revision",
                _REVISION,
                "--seed",
                "7",
                "--inventory",
                str(tmp_path / "absent-roster.json"),
            ]
        )
        assert exit_code == 1
        assert not (tmp_path / "session" / "14-MANIFEST.json").exists()

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "init"
        assert result["ok"] is False
        assert result["reason"] == "unreadable_inventory"

    def test_init_states_a_malformed_inventory_file_as_json(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        """Hand-authored JSON is hand-broken JSON; say so explicitly."""
        malformed = tmp_path / "roster.json"
        malformed.write_text('[{"alias": "light-1",]', encoding="utf-8")
        exit_code = thread_revalidation_main(
            [
                "init",
                "--session-dir",
                str(tmp_path / "session"),
                "--session-id",
                "session-alpha",
                "--revision",
                _REVISION,
                "--seed",
                "7",
                "--inventory",
                str(malformed),
            ]
        )
        assert exit_code == 1
        assert not (tmp_path / "session" / "14-MANIFEST.json").exists()

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "init"
        assert result["ok"] is False
        assert result["reason"] == "malformed_inventory"


class TestModuleEntryPoint:
    """The `if __name__ == "__main__":` guard itself, not just `main()`.

    `runpy.run_module(..., run_name="__main__")` re-executes the module body
    under the `__main__` name, so this is the one way to actually exercise
    the guard and its `sys.exit(main())` call rather than excluding it --
    the module's own entry point is otherwise unreachable from a normal
    import (Plan 14-03, D-25 coverage closure).
    """

    def test_running_as_main_with_no_subcommand_exits_2(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import runpy

        monkeypatch.setattr(sys, "argv", ["thread_revalidation.py"])

        with pytest.raises(SystemExit) as excinfo:
            runpy.run_module("scripts.thread_revalidation", run_name="__main__")

        assert excinfo.value.code == 2


# ---------------------------------------------------------------------------
# Plan 14-02: shared privacy/schema primitives exercised directly
# ---------------------------------------------------------------------------


class TestSharedPrivacyPrimitives:
    def test_validate_alias_rejects_non_string(self) -> None:
        with pytest.raises(ValueError, match="invalid privacy-safe alias"):
            validate_alias(123)

    def test_validate_alias_rejects_pattern_mismatch(self) -> None:
        with pytest.raises(ValueError, match="invalid privacy-safe alias"):
            validate_alias("1-starts-with-digit")

    def test_validate_alias_accepts_well_formed(self) -> None:
        assert validate_alias("candle-1") == "candle-1"

    def test_validate_session_id_rejects_non_string(self) -> None:
        with pytest.raises(ValueError, match="invalid privacy-safe session_id"):
            validate_session_id(None)

    def test_validate_session_id_rejects_identifier_shaped(self) -> None:
        with pytest.raises(ValueError, match="identifier-shaped session_id"):
            validate_session_id("d073d5001234")

    def test_validate_revision_rejects_short_string(self) -> None:
        with pytest.raises(ValueError, match="40-character"):
            validate_revision("deadbeef")

    def test_validate_revision_accepts_exact_sha(self) -> None:
        assert validate_revision(_REVISION) == _REVISION

    def test_contains_forbidden_key_detects_nested_key(self) -> None:
        assert contains_forbidden_key({"outer": {"serial": "x"}}) is True
        assert contains_forbidden_key({"outer": [{"ip": "x"}]}) is True
        assert contains_forbidden_key({"outer": "fine"}) is False

    def test_contains_forbidden_value_detects_ipv4(self) -> None:
        assert contains_forbidden_value("192.168.1.1") is True

    def test_contains_forbidden_value_detects_ipv6(self) -> None:
        assert contains_forbidden_value("::1") is True

    def test_contains_forbidden_value_detects_serial_shaped_string(self) -> None:
        assert contains_forbidden_value("d073d5001234") is True

    def test_contains_forbidden_value_accepts_ordinary_string(self) -> None:
        assert contains_forbidden_value("candle-1") is False
        assert contains_forbidden_value({"nested": ["candle-1"]}) is False
        assert contains_forbidden_value(42) is False

    def test_load_jsonl_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert load_jsonl(tmp_path / "absent.jsonl") == []

    def test_load_jsonl_skips_blank_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "rows.jsonl"
        path.write_text('{"a": 1}\n\n{"a": 2}\n', encoding="utf-8")
        assert load_jsonl(path) == [{"a": 1}, {"a": 2}]

    def test_load_jsonl_rejects_invalid_json_with_line_number(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "rows.jsonl"
        path.write_text("not json\n", encoding="utf-8")
        with pytest.raises(ValueError, match="line 1"):
            load_jsonl(path)

    def test_load_jsonl_rejects_non_object_row(self, tmp_path: Path) -> None:
        path = tmp_path / "rows.jsonl"
        path.write_text("[1, 2]\n", encoding="utf-8")
        with pytest.raises(ValueError, match="row is not an object"):
            load_jsonl(path)

    def test_git_revision_raises_without_git(self) -> None:
        with patch("scripts.measurement_support.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="git is required"):
                git_revision()

    def test_git_revision_returns_current_head(self) -> None:
        # Exercises the real subprocess path against this checkout's git.
        revision = git_revision()
        assert len(revision) == 40


# ---------------------------------------------------------------------------
# Plan 14-02: additional manifest/journal validation branches
# ---------------------------------------------------------------------------


class TestManifestValidationBranches:
    def test_rejects_extra_top_level_key_via_public_builder(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["extra"] = 1
        with pytest.raises(ValueError, match="unexpected keys"):
            _validate_manifest_public(manifest)

    def test_rejects_wrong_schema_version(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["schema_version"] = 2
        with pytest.raises(ValueError, match="wrong schema_version"):
            _validate_manifest_public(manifest)

    def test_rejects_wrong_kind(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["kind"] = "something_else"
        with pytest.raises(ValueError, match="wrong kind"):
            _validate_manifest_public(manifest)

    def test_rejects_inventory_not_a_list(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["inventory"] = {}
        with pytest.raises(ValueError, match="inventory must be a list"):
            _validate_manifest_public(manifest)

    def test_rejects_invalid_inventory_entry_shape(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["inventory"] = [{"alias": "x"}]
        with pytest.raises(ValueError, match="invalid manifest inventory entry"):
            _validate_manifest_public(manifest)

    def test_rejects_non_boolean_available(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["inventory"][0]["available"] = "yes"
        with pytest.raises(ValueError, match="available must be a boolean"):
            _validate_manifest_public(manifest)

    def test_rejects_invalid_confounders_on_manifest(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["confounders"] = ["not_a_real_confounder"]
        with pytest.raises(ValueError, match="invalid confounders"):
            _validate_manifest_public(manifest)

    def test_rejects_non_integer_seed(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["seed"] = "42"
        with pytest.raises(ValueError, match="unsigned 64-bit"):
            _validate_manifest_public(manifest)

    def test_rejects_request_trial_gaps_mismatch(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["request_trial_gaps_s"][0] = 999.0
        with pytest.raises(ValueError, match="request_trial_gaps_s"):
            _validate_manifest_public(manifest)

    def test_rejects_animation_schedule_mismatch(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["animation_schedule"] = [[1, 5.0], [2, 10.0], [5, 10.0]]
        with pytest.raises(ValueError, match="frozen D-10 schedule"):
            _validate_manifest_public(manifest)

    def test_rejects_staleness_poll_interval_mismatch(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["staleness_poll_interval_s"] = 30.0
        with pytest.raises(ValueError, match="staleness_poll_interval_s"):
            _validate_manifest_public(manifest)

    def test_rejects_staleness_confirm_polls_mismatch(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["staleness_confirm_absent_polls"] = 5
        with pytest.raises(ValueError, match="staleness_confirm_absent_polls"):
            _validate_manifest_public(manifest)

    def test_rejects_staleness_cap_mismatch(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["staleness_cap_s"] = 100.0
        with pytest.raises(ValueError, match="staleness_cap_s"):
            _validate_manifest_public(manifest)

    def test_rejects_non_positive_retransmit_floor(self) -> None:
        manifest = build_manifest(**_manifest_kwargs())
        manifest["request_retransmit_floor_s"] = 0
        with pytest.raises(ValueError, match="positive number"):
            _validate_manifest_public(manifest)


@pytest.mark.parametrize(
    ("builder", "kwargs_factory"),
    [
        (build_discovery_event, _discovery_kwargs),
        (build_request_trial_event, _request_trial_kwargs),
        (build_animation_event, _animation_kwargs),
        (build_staleness_event, _staleness_kwargs),
        (build_closure_event, _closure_kwargs),
    ],
)
class TestEveryJournalSharesTheClosedSchemaContract:
    """Every journal's row rejects an extra key, wrong schema_version, wrong kind."""

    def test_rejects_extra_key(self, builder: Any, kwargs_factory: Any) -> None:
        record = builder(**kwargs_factory())
        record["not_a_real_field"] = 1
        with pytest.raises(ValueError, match="unexpected keys"):
            _revalidate(builder, record)

    def test_rejects_wrong_schema_version(
        self, builder: Any, kwargs_factory: Any
    ) -> None:
        record = builder(**kwargs_factory())
        record["schema_version"] = 999
        with pytest.raises(ValueError, match="wrong schema_version"):
            _revalidate(builder, record)

    def test_rejects_wrong_kind(self, builder: Any, kwargs_factory: Any) -> None:
        record = builder(**kwargs_factory())
        record["kind"] = "not-a-real-kind"
        with pytest.raises(ValueError, match="wrong kind"):
            _revalidate(builder, record)


_VALIDATOR_BY_BUILDER = {
    build_discovery_event: "_validate_discovery_event",
    build_request_trial_event: "_validate_request_trial_event",
    build_animation_event: "_validate_animation_event",
    build_staleness_event: "_validate_staleness_event",
    build_closure_event: "_validate_closure_event",
}


def _revalidate(builder: Any, record: dict[str, Any]) -> None:
    """Re-run the exact private validator paired with ``builder`` on a tampered row."""
    import scripts.thread_revalidation as module

    validator = getattr(module, _VALIDATOR_BY_BUILDER[builder])
    validator(record)


class TestRequestTrialValidationBranches:
    def test_rejects_unknown_outcome(self) -> None:
        record = build_request_trial_event(**_request_trial_kwargs())
        record["outcome"] = "mystery"
        with pytest.raises(ValueError, match="unknown outcome"):
            _revalidate(build_request_trial_event, record)

    def test_rejects_non_boolean_thread_connection_when_completed(self) -> None:
        record = build_request_trial_event(**_request_trial_kwargs())
        record["thread_connection"] = "true"
        with pytest.raises(ValueError, match="boolean thread_connection"):
            _revalidate(build_request_trial_event, record)

    def test_rejects_unknown_provenance(self) -> None:
        record = build_request_trial_event(**_request_trial_kwargs())
        record["provenance"] = "made_up"
        with pytest.raises(ValueError, match="unknown provenance"):
            _revalidate(build_request_trial_event, record)


class TestAnimationValidationBranches:
    def test_rejects_wrong_duration(self) -> None:
        rates = [_animation_rate(fps, duration) for fps, duration in ANIMATION_SCHEDULE]
        rates[0]["duration_s"] = 5.0
        with pytest.raises(ValueError, match="duration_s does not match"):
            build_animation_event(**_animation_kwargs(rates=rates))

    def test_rejects_unknown_rate_outcome(self) -> None:
        rates = [_animation_rate(fps, duration) for fps, duration in ANIMATION_SCHEDULE]
        rates[0]["outcome"] = "mystery"
        with pytest.raises(ValueError, match="invalid animation rate outcome"):
            build_animation_event(**_animation_kwargs(rates=rates))

    def test_rejects_negative_count_field(self) -> None:
        rates = [_animation_rate(fps, duration) for fps, duration in ANIMATION_SCHEDULE]
        rates[0]["gated"] = -1
        with pytest.raises(ValueError, match="non-negative integer"):
            build_animation_event(**_animation_kwargs(rates=rates))

    def test_rejects_negative_total_time_ms(self) -> None:
        rates = [_animation_rate(fps, duration) for fps, duration in ANIMATION_SCHEDULE]
        rates[0]["total_time_ms"] = -1.0
        with pytest.raises(ValueError, match="total_time_ms"):
            build_animation_event(**_animation_kwargs(rates=rates))

    def test_rejects_non_boolean_liveness(self) -> None:
        record = build_animation_event(**_animation_kwargs())
        record["pre_liveness"] = "yes"
        with pytest.raises(ValueError, match="pre_liveness must be a boolean"):
            _revalidate(build_animation_event, record)

    def test_rejects_non_boolean_post_liveness(self) -> None:
        record = build_animation_event(**_animation_kwargs())
        record["post_liveness"] = "yes"
        with pytest.raises(ValueError, match="post_liveness must be a boolean"):
            _revalidate(build_animation_event, record)

    def test_rejects_non_boolean_restored(self) -> None:
        record = build_animation_event(**_animation_kwargs())
        record["restored"] = "yes"
        with pytest.raises(ValueError, match="must be boolean"):
            _revalidate(build_animation_event, record)

    def test_rejects_unknown_provenance(self) -> None:
        record = build_animation_event(**_animation_kwargs())
        record["provenance"] = "made_up"
        with pytest.raises(ValueError, match="unknown provenance"):
            _revalidate(build_animation_event, record)


class TestStalenessValidationBranches:
    def test_rejects_negative_disconnect_ns(self) -> None:
        with pytest.raises(ValueError, match="disconnect_ns"):
            build_staleness_event(**_staleness_kwargs(disconnect_ns=-1))

    def test_rejects_invalid_poll_entry_shape(self) -> None:
        record = build_staleness_event(**_staleness_kwargs())
        record["polls"][0] = {"poll": 1}
        with pytest.raises(ValueError, match="invalid staleness poll entry"):
            _revalidate(build_staleness_event, record)

    def test_rejects_non_contiguous_poll_numbers(self) -> None:
        record = build_staleness_event(**_staleness_kwargs())
        record["polls"][1]["poll"] = 99
        with pytest.raises(ValueError, match="contiguous"):
            _revalidate(build_staleness_event, record)

    def test_rejects_elapsed_s_exceeding_cap(self) -> None:
        record = build_staleness_event(**_staleness_kwargs())
        record["polls"][-1]["elapsed_s"] = STALENESS_CAP_S + 1.0
        with pytest.raises(ValueError, match="non-decreasing and within the cap"):
            _revalidate(build_staleness_event, record)

    def test_rejects_non_boolean_presence_flag(self) -> None:
        record = build_staleness_event(**_staleness_kwargs())
        record["polls"][0]["discover_present"] = "yes"
        with pytest.raises(ValueError, match="presence flags must be boolean"):
            _revalidate(build_staleness_event, record)

    def test_rejects_first_absence_poll_mismatch(self) -> None:
        record = build_staleness_event(**_staleness_kwargs())
        record["first_absence_poll"] = 99
        with pytest.raises(ValueError, match="first_absence_poll does not match"):
            _revalidate(build_staleness_event, record)

    def test_rejects_confirmed_expiry_poll_mismatch(self) -> None:
        record = build_staleness_event(**_staleness_kwargs())
        record["confirmed_expiry_poll"] = 99
        with pytest.raises(ValueError, match="confirmed_expiry_poll does not match"):
            _revalidate(build_staleness_event, record)

    def test_rejects_unknown_disposition(self) -> None:
        record = build_staleness_event(**_staleness_kwargs())
        record["disposition"] = "mystery"
        with pytest.raises(ValueError, match="unknown disposition"):
            _revalidate(build_staleness_event, record)

    def test_rejects_confirmed_run_with_non_confirmed_disposition(self) -> None:
        record = build_staleness_event(
            **_staleness_kwargs(disposition="confirmed_expiry", restored_available_ns=1)
        )
        record["disposition"] = "interrupted"
        with pytest.raises(
            ValueError, match="requires the confirmed_expiry disposition"
        ):
            _revalidate(build_staleness_event, record)

    def test_rejects_invalid_restored_available_ns_type_when_interrupted(self) -> None:
        record = build_staleness_event(
            **_staleness_kwargs(
                polls=[_present_poll(1, 0.0)],
                disposition="interrupted",
                restored_available_ns=None,
                restoration_duration_s=None,
            )
        )
        record["restored_available_ns"] = -1
        with pytest.raises(ValueError, match="null or non-negative"):
            _revalidate(build_staleness_event, record)

    def test_rejects_unknown_provenance(self) -> None:
        record = build_staleness_event(**_staleness_kwargs())
        record["provenance"] = "made_up"
        with pytest.raises(ValueError, match="unknown provenance"):
            _revalidate(build_staleness_event, record)


class TestClosureValidationBranches:
    def test_rejects_unknown_device_class(self) -> None:
        record = build_closure_event(**_closure_kwargs())
        record["device_class"] = "NotARealClass"
        with pytest.raises(ValueError, match="unknown device_class"):
            _revalidate(build_closure_event, record)

    def test_rejects_unknown_disposition(self) -> None:
        record = build_closure_event(**_closure_kwargs())
        record["disposition"] = "mystery"
        with pytest.raises(ValueError, match="unknown disposition"):
            _revalidate(build_closure_event, record)

    def test_rejects_aliases_not_a_list(self) -> None:
        record = build_closure_event(**_closure_kwargs())
        record["aliases"] = "candle-1"
        with pytest.raises(ValueError, match="aliases must be a list"):
            _revalidate(build_closure_event, record)

    def test_rejects_duplicate_alias(self) -> None:
        record = build_closure_event(**_closure_kwargs(aliases=["candle-1", "mini-1"]))
        record["aliases"] = ["candle-1", "candle-1"]
        with pytest.raises(ValueError, match="duplicate alias"):
            _revalidate(build_closure_event, record)

    def test_rejects_evidence_backed_without_aliases(self) -> None:
        with pytest.raises(ValueError, match="at least one alias"):
            build_closure_event(**_closure_kwargs(aliases=[]))

    def test_rejects_empty_gap_reason(self) -> None:
        with pytest.raises(ValueError, match="non-empty gap_reason"):
            build_closure_event(
                **_closure_kwargs(
                    device_class="InfraredLight",
                    disposition="named_gap",
                    aliases=[],
                    gap_reason="",
                    gap_recorded_date="2026-08-31",
                    provenance=None,
                )
            )

    def test_rejects_malformed_gap_date(self) -> None:
        with pytest.raises(ValueError, match="ISO gap_recorded_date"):
            build_closure_event(
                **_closure_kwargs(
                    device_class="InfraredLight",
                    disposition="named_gap",
                    aliases=[],
                    gap_reason="no hardware",
                    gap_recorded_date="31-08-2026",
                    provenance=None,
                )
            )

    def test_rejects_provenance_on_named_gap(self) -> None:
        record = build_closure_event(
            **_closure_kwargs(
                device_class="InfraredLight",
                disposition="named_gap",
                aliases=[],
                gap_reason="no hardware",
                gap_recorded_date="2026-08-31",
                provenance=None,
            )
        )
        record["provenance"] = "physical"
        with pytest.raises(ValueError, match="must not carry a provenance"):
            _revalidate(build_closure_event, record)


class TestDiscoveryValidationBranches:
    def test_rejects_unknown_source(self) -> None:
        record = build_discovery_event(**_discovery_kwargs())
        record["source"] = "mystery"
        with pytest.raises(ValueError, match="unknown source"):
            _revalidate(build_discovery_event, record)

    def test_rejects_call_order_tamper(self) -> None:
        record = build_discovery_event(**_discovery_kwargs())
        record["call_order"] = 2
        with pytest.raises(ValueError, match="D-02 alternation"):
            _revalidate(build_discovery_event, record)

    def test_rejects_unknown_outcome(self) -> None:
        record = build_discovery_event(**_discovery_kwargs())
        record["outcome"] = "mystery"
        with pytest.raises(ValueError, match="unknown outcome"):
            _revalidate(build_discovery_event, record)

    def test_rejects_devices_not_a_list(self) -> None:
        record = build_discovery_event(**_discovery_kwargs())
        record["devices"] = "candle-1"
        with pytest.raises(ValueError, match="devices must be a list"):
            _revalidate(build_discovery_event, record)

    def test_rejects_duplicate_alias_within_one_event(self) -> None:
        record = build_discovery_event(**_discovery_kwargs())
        record["devices"] = ["candle-1", "candle-1"]
        with pytest.raises(ValueError, match="duplicate alias"):
            _revalidate(build_discovery_event, record)

    def test_rejects_unknown_provenance(self) -> None:
        record = build_discovery_event(**_discovery_kwargs())
        record["provenance"] = "made_up"
        with pytest.raises(ValueError, match="unknown provenance"):
            _revalidate(build_discovery_event, record)


class TestReloadEveryJournal:
    """Every reload_* function validates each row it loads back (not just build)."""

    def test_reload_staleness_events(self, tmp_path: Path) -> None:
        path = tmp_path / "14-STALENESS.jsonl"
        record = build_staleness_event(**_staleness_kwargs())
        append_staleness_event(path, record)
        assert reload_staleness_events(path) == [record]

    def test_reload_closure_events(self, tmp_path: Path) -> None:
        path = tmp_path / "14-CLOSURE.jsonl"
        record = build_closure_event(**_closure_kwargs())
        append_closure_event(path, record)
        assert reload_closure_events(path) == [record]


class TestGenerateSummaryNonCompletedRequestRow:
    def test_non_completed_row_is_counted_without_latency(self) -> None:
        rows = [
            build_request_trial_event(**_request_trial_kwargs(trial=1)),
            build_request_trial_event(
                **_request_trial_kwargs(
                    trial=2,
                    outcome="timeout",
                    logical_latency_ns=None,
                    ack_rtt_ns=None,
                    thread_connection=None,
                )
            ),
        ]
        summary = generate_summary(
            discovery_rows=[],
            request_rows=rows,
            animation_rows=[],
            staleness_rows=[],
            closure_rows=[],
        )
        outcomes = summary["requests"]["candle-1"]["outcomes"]
        assert outcomes == {"completed": 1, "timeout": 1}


class TestRemainingProtocolAndStalenessAndClosureBranches:
    def test_rejects_non_positive_protocol_version(self) -> None:
        with pytest.raises(ValueError, match="protocol_version must be a positive"):
            build_discovery_event(**_discovery_kwargs(protocol_version=0))

    def test_rejects_empty_polls_list(self) -> None:
        with pytest.raises(ValueError, match="non-empty list"):
            build_staleness_event(**_staleness_kwargs(polls=[]))

    def test_rejects_confirmed_expiry_disposition_without_a_confirmed_run(self) -> None:
        with pytest.raises(ValueError, match="requires a confirmed_expiry_poll"):
            build_staleness_event(
                **_staleness_kwargs(
                    polls=[_present_poll(1, 0.0)],
                    disposition="confirmed_expiry",
                    restored_available_ns=1,
                )
            )

    def test_rejects_cap_reached_without_confirmation_under_non_censored_disposition(
        self,
    ) -> None:
        with pytest.raises(ValueError, match="require the .*censored disposition"):
            build_staleness_event(
                **_staleness_kwargs(
                    polls=[_present_poll(1, 0.0), _present_poll(2, STALENESS_CAP_S)],
                    disposition="interrupted",
                    restored_available_ns=None,
                )
            )

    def test_rejects_evidence_backed_with_gap_fields(self) -> None:
        with pytest.raises(ValueError, match="must not carry gap fields"):
            build_closure_event(**_closure_kwargs(gap_reason="should not be here"))

    def test_privacy_backstop_rejects_ip_shaped_gap_reason(self) -> None:
        """gap_reason is the one closure field with no dedicated privacy check
        of its own -- proves the generic recursive backstop, not just the
        closed key/type/enum checks, actually runs and catches a leaked
        address hiding in otherwise-valid free text."""
        with pytest.raises(ValueError, match="privacy validation rejected"):
            build_closure_event(
                **_closure_kwargs(
                    device_class="InfraredLight",
                    disposition="named_gap",
                    aliases=[],
                    gap_reason="unreachable at 192.168.1.1",
                    gap_recorded_date="2026-08-31",
                    provenance=None,
                )
            )

    def test_rejects_named_gap_with_aliases(self) -> None:
        with pytest.raises(ValueError, match="must not carry aliases"):
            build_closure_event(
                **_closure_kwargs(
                    device_class="InfraredLight",
                    disposition="named_gap",
                    aliases=["mini-1"],
                    gap_reason="no hardware",
                    gap_recorded_date="2026-08-31",
                    provenance=None,
                )
            )


class TestGenerateReportPopulatedSections:
    def test_report_renders_populated_requests_animation_and_staleness(self) -> None:
        summary = generate_summary(
            discovery_rows=[
                build_discovery_event(**_discovery_kwargs()),
            ],
            request_rows=[build_request_trial_event(**_request_trial_kwargs())],
            animation_rows=[build_animation_event(**_animation_kwargs())],
            staleness_rows=[build_staleness_event(**_staleness_kwargs())],
            closure_rows=_full_closure_rows(),
        )
        report = generate_report(summary)
        assert "candle-1" in report
        assert "outcomes" in report
        assert "restored=True" in report
        assert "confirmed_expiry" in report


# ---------------------------------------------------------------------------
# Plan 14-03: shared device-state capture, restoration and exact comparison
# (D-05/D-14/D-16). These fakes are device-shape doubles for the SHARED
# measurement_support primitive, independent of scripts/ipv6_thread_probe.py's
# own fakes -- proving the helper works across Light, MultiZoneLight, and both
# Matrix-shaped classes (MatrixLight and its CeilingLight subclass) with no
# probe-specific behaviour in the loop.
# ---------------------------------------------------------------------------

_TILE_COLOURS = [
    [HSBK(10.0, 1.0, 1.0, 3500), HSBK(20.0, 0.5, 0.5, 4000)],
    [HSBK(30.0, 0.25, 0.75, 2700), HSBK(40.0, 0.0, 1.0, 6500)],
]
_ZONE_COLOURS = [HSBK(float((index * 40) % 360), 0.5, 0.75, 3500) for index in range(8)]


class TestIsBinaryPower:
    """The D-05 preflight predicate: exactly {0, 65535} is acceptable."""

    @pytest.mark.parametrize("power", [0, 65535])
    def test_binary_levels_are_accepted(self, power: int) -> None:
        assert is_binary_power(power) is True

    @pytest.mark.parametrize("power", [1, 5242, 65534, -1, 32768])
    def test_intermediate_or_invalid_levels_are_rejected(self, power: int) -> None:
        assert is_binary_power(power) is False


class _FakeLight(Light):
    """A plain Light double that applies or ignores writes on request."""

    def __init__(
        self,
        *,
        power: int = 0,
        color: HSBK | None = None,
        applies_writes: bool = True,
    ) -> None:
        super().__init__(serial="d073d5000001", ip="127.0.0.1")
        self.calls: list[tuple[str, Any]] = []
        self.applies_writes = applies_writes
        self._power = power
        self._color = color if color is not None else HSBK(10.0, 1.0, 1.0, 3500)

    async def get_color(self) -> tuple[HSBK, int, str]:
        self.calls.append(("get_color", None))
        return (self._color, self._power, "Fake Light")

    async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
        self.calls.append(("set_color", color))
        if self.applies_writes:
            self._color = color

    async def set_power(self, level: bool | int) -> None:
        self.calls.append(("set_power", level))
        if self.applies_writes:
            self._power = 65535 if level in (True, 65535) else 0


class _MatrixLikeFakeMixin:
    """Shared get/set fake behaviour for MatrixLight and CeilingLight doubles.

    A mixin rather than a shared base class, so `_FakeMatrix` and
    `_FakeCeiling` can each subclass the REAL production class the shared
    helper's `isinstance()` checks branch on -- proving the helper handles
    the CeilingLight subclass generically, with no special-casing anywhere.
    """

    calls: list[tuple[str, Any]]
    _power: int
    _effect_type: FirmwareEffect
    _tiles: list[list[HSBK]]

    def _init_matrix_fake(self, *, power: int, effect_type: FirmwareEffect) -> None:
        self.calls = []
        self._power = power
        self._effect_type = effect_type
        self._tiles = [list(row) for row in _TILE_COLOURS]

    async def __aenter__(self) -> Any:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def get_all_tile_colors(self) -> list[list[HSBK]]:
        self.calls.append(("get_all_tile_colors", None))
        return [list(tile) for tile in self._tiles]

    async def get_power(self) -> int:
        self.calls.append(("get_power", None))
        return self._power

    async def set_power(self, level: bool | int) -> None:
        self.calls.append(("set_power", level))
        self._power = 65535 if level in (True, 65535) else 0

    async def get_effect(self) -> MatrixEffect:
        self.calls.append(("get_effect", None))
        return MatrixEffect(
            effect_type=self._effect_type, speed=5000, duration=0, from_device=True
        )

    async def set_effect(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("set_effect", kwargs))
        self._effect_type = kwargs["effect_type"]  # type: ignore[assignment]

    async def set_matrix_colors(
        self, tile_index: int, colors: list[HSBK], duration: int = 0
    ) -> None:
        self.calls.append(("set_matrix_colors", (tile_index, list(colors))))
        self._tiles[tile_index] = list(colors)


class _FakeMatrix(_MatrixLikeFakeMixin, MatrixLight):
    def __init__(
        self, *, power: int = 0, effect_type: FirmwareEffect = FirmwareEffect.OFF
    ) -> None:
        super().__init__(serial="d073d5000002", ip="127.0.0.1")
        self._init_matrix_fake(power=power, effect_type=effect_type)


class _FakeCeiling(_MatrixLikeFakeMixin, CeilingLight):
    def __init__(
        self, *, power: int = 0, effect_type: FirmwareEffect = FirmwareEffect.OFF
    ) -> None:
        super().__init__(serial="d073d5000003", ip="127.0.0.1")
        self._init_matrix_fake(power=power, effect_type=effect_type)


class _FakeMultiZone(MultiZoneLight):
    def __init__(self, *, power: int = 0) -> None:
        super().__init__(serial="d073d5000004", ip="127.0.0.1")
        self.calls: list[tuple[str, Any]] = []
        self._power = power
        self._zones = list(_ZONE_COLOURS)
        self._effect = MultiZoneEffect(effect_type=FirmwareEffect.OFF, speed=0)

    async def __aenter__(self) -> _FakeMultiZone:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get_all_color_zones(self) -> list[HSBK]:
        self.calls.append(("get_all_color_zones", None))
        return list(self._zones)

    async def get_power(self) -> int:
        self.calls.append(("get_power", None))
        return self._power

    async def get_effect(self) -> MultiZoneEffect:
        self.calls.append(("get_effect", None))
        return self._effect

    async def set_power(self, level: bool | int, duration: float = 0.0) -> None:
        self.calls.append(("set_power", level))
        self._power = 65535 if level in (True, 65535) else 0

    async def set_all_color_zones(
        self, colors: list[HSBK], *args: object, **kwargs: object
    ) -> None:
        self.calls.append(("set_all_color_zones", list(colors)))
        self._zones = list(colors)

    async def set_effect(self, effect: MultiZoneEffect) -> None:
        self.calls.append(("set_effect", effect))
        self._effect = effect


class TestCaptureDeviceState:
    """capture_device_state() reads the shape each real class actually holds."""

    async def test_light_capture_uses_get_color(self) -> None:
        device = _FakeLight(power=65535, color=HSBK(50.0, 1.0, 1.0, 3500))

        state = await capture_device_state(device)

        assert state == CapturedState(
            kind="light", power=65535, color=HSBK(50.0, 1.0, 1.0, 3500)
        )

    async def test_matrix_capture_reads_tiles_power_and_effect(self) -> None:
        device = _FakeMatrix(power=65535, effect_type=FirmwareEffect.MORPH)

        state = await capture_device_state(device)

        assert state.kind == "matrix"
        assert state.tiles == _TILE_COLOURS
        assert state.power == 65535
        assert state.effect is not None
        assert state.effect.effect_type is FirmwareEffect.MORPH

    async def test_matrix_capture_with_no_running_effect_records_none(self) -> None:
        device = _FakeMatrix(effect_type=FirmwareEffect.OFF)

        state = await capture_device_state(device)

        assert state.effect is None

    async def test_ceiling_capture_takes_the_matrix_path(self) -> None:
        """CeilingLight extends MatrixLight; capture needs no special-casing."""
        device = _FakeCeiling(power=65535, effect_type=FirmwareEffect.FLAME)

        state = await capture_device_state(device)

        assert state.kind == "matrix"
        assert state.tiles == _TILE_COLOURS
        assert state.effect is not None
        assert state.effect.effect_type is FirmwareEffect.FLAME

    async def test_multizone_capture_reads_zones_power_and_effect(self) -> None:
        device = _FakeMultiZone(power=65535)

        state = await capture_device_state(device)

        assert state.kind == "multizone"
        assert state.zones == _ZONE_COLOURS
        assert state.power == 65535
        assert state.multizone_effect == device._effect


class TestRestoreAndVerifyDeviceState:
    """restore_and_verify_device_state() proves restoration with a recapture."""

    async def test_light_restore_write_order_and_exact_verification(self) -> None:
        device = _FakeLight(power=0, color=HSBK(10.0, 1.0, 1.0, 3500))
        state = CapturedState(
            kind="light", power=65535, color=HSBK(99.0, 0.5, 0.8, 4000)
        )

        result = await restore_and_verify_device_state(device, state)

        assert result == RestoreOutcome(restored=True, restoration_verified=True)
        assert [name for name, _ in device.calls] == [
            "set_color",
            "set_power",
            "get_color",
        ]

    async def test_matrix_restore_write_order_and_exact_verification(self) -> None:
        device = _FakeMatrix(power=0, effect_type=FirmwareEffect.OFF)
        captured = await capture_device_state(
            _FakeMatrix(power=65535, effect_type=FirmwareEffect.MORPH)
        )

        result = await restore_and_verify_device_state(device, captured)

        assert result == RestoreOutcome(restored=True, restoration_verified=True)
        names = [name for name, _ in device.calls]
        assert names == [
            "set_matrix_colors",
            "set_matrix_colors",
            "set_power",
            "set_effect",
            "get_all_tile_colors",
            "get_power",
            "get_effect",
        ]

    async def test_ceiling_restore_write_order_and_exact_verification(self) -> None:
        device = _FakeCeiling(power=0, effect_type=FirmwareEffect.OFF)
        captured = await capture_device_state(
            _FakeCeiling(power=65535, effect_type=FirmwareEffect.SKY)
        )

        result = await restore_and_verify_device_state(device, captured)

        assert result == RestoreOutcome(restored=True, restoration_verified=True)

    async def test_multizone_restore_write_order_and_exact_verification(self) -> None:
        device = _FakeMultiZone(power=0)
        captured = await capture_device_state(_FakeMultiZone(power=65535))

        result = await restore_and_verify_device_state(device, captured)

        assert result == RestoreOutcome(restored=True, restoration_verified=True)
        names = [name for name, _ in device.calls]
        assert names == [
            "set_all_color_zones",
            "set_effect",
            "set_power",
            "get_all_color_zones",
            "get_power",
            "get_effect",
        ]

    async def test_readback_mismatch_when_commands_do_not_apply(self) -> None:
        """SET-success/readback-mismatch: commands complete, state does not change."""
        device = _FakeLight(
            power=0, color=HSBK(10.0, 1.0, 1.0, 3500), applies_writes=False
        )
        state = CapturedState(
            kind="light", power=65535, color=HSBK(99.0, 0.5, 0.8, 4000)
        )

        result = await restore_and_verify_device_state(device, state)

        assert result == RestoreOutcome(
            restored=True, restoration_verified=False, detail="readback_mismatch"
        )

    async def test_ordinary_command_failure_is_reported_without_a_readback(
        self,
    ) -> None:
        device = _FakeLight(power=0)

        async def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("radio went away")

        device.set_color = _boom  # type: ignore[method-assign]
        state = CapturedState(
            kind="light", power=65535, color=HSBK(1.0, 1.0, 1.0, 3500)
        )
        reported: list[BaseException] = []

        result = await restore_and_verify_device_state(
            device, state, on_command_exception=reported.append
        )

        assert result == RestoreOutcome(
            restored=False, restoration_verified=False, detail="command_failed"
        )
        assert len(reported) == 1
        assert isinstance(reported[0], OSError)
        # No readback is attempted after a command failure.
        assert not any(name == "get_color" for name, _ in device.calls)

    async def test_readback_exception_after_successful_commands(self) -> None:
        device = _FakeLight(power=0)
        state = CapturedState(
            kind="light", power=65535, color=HSBK(1.0, 1.0, 1.0, 3500)
        )

        async def _flaky_get_color() -> tuple[HSBK, int, str]:
            raise OSError("readback timed out")

        device.get_color = _flaky_get_color  # type: ignore[method-assign]
        reported: list[BaseException] = []

        result = await restore_and_verify_device_state(
            device, state, on_command_exception=reported.append
        )

        assert result == RestoreOutcome(
            restored=True, restoration_verified=False, detail="readback_failed"
        )
        assert len(reported) == 1
        assert isinstance(reported[0], OSError)

    @pytest.mark.parametrize(
        "make_exc", [asyncio.CancelledError, KeyboardInterrupt], ids=["cancel", "kbint"]
    )
    async def test_cancellation_and_keyboard_interrupt_are_reported_then_reraised(
        self, make_exc: type[BaseException]
    ) -> None:
        """Both stop safely: reported to the caller's own diagnostic, never
        swallowed -- cancellation semantics must still propagate."""
        device = _FakeLight(power=0)

        async def _interrupt(*args: object, **kwargs: object) -> None:
            raise make_exc

        device.set_color = _interrupt  # type: ignore[method-assign]
        state = CapturedState(
            kind="light", power=65535, color=HSBK(1.0, 1.0, 1.0, 3500)
        )
        reported: list[BaseException] = []

        with pytest.raises(make_exc):
            await restore_and_verify_device_state(
                device, state, on_command_exception=reported.append
            )

        assert len(reported) == 1
        assert isinstance(reported[0], make_exc)

    @pytest.mark.parametrize(
        "make_exc", [asyncio.CancelledError, KeyboardInterrupt], ids=["cancel", "kbint"]
    )
    async def test_cancellation_and_keyboard_interrupt_during_readback(
        self, make_exc: type[BaseException]
    ) -> None:
        """The same honest-outcome, never-swallowed contract applies when the
        interrupt arrives during the POST-command recapture, not just during
        the restore commands themselves."""
        device = _FakeLight(power=0)
        state = CapturedState(
            kind="light", power=65535, color=HSBK(1.0, 1.0, 1.0, 3500)
        )

        async def _interrupt() -> tuple[HSBK, int, str]:
            raise make_exc

        device.get_color = _interrupt  # type: ignore[method-assign]
        reported: list[BaseException] = []

        with pytest.raises(make_exc):
            await restore_and_verify_device_state(
                device, state, on_command_exception=reported.append
            )

        assert len(reported) == 1
        assert isinstance(reported[0], make_exc)
        # The restore commands themselves (set_color, set_power) still ran.
        assert [name for name, _ in device.calls] == ["set_color", "set_power"]

    async def test_works_with_no_on_command_exception_callback(self) -> None:
        """The callback is optional -- a caller that does not supply one still
        gets the bounded outcome without a TypeError."""
        device = _FakeLight(power=0)

        async def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("radio went away")

        device.set_color = _boom  # type: ignore[method-assign]
        state = CapturedState(
            kind="light", power=65535, color=HSBK(1.0, 1.0, 1.0, 3500)
        )

        result = await restore_and_verify_device_state(device, state)

        assert result.restored is False

    @pytest.mark.parametrize(
        "make_exc", [asyncio.CancelledError, KeyboardInterrupt], ids=["cancel", "kbint"]
    )
    async def test_cancellation_and_interrupt_reraise_with_no_callback(
        self, make_exc: type[BaseException]
    ) -> None:
        """The callback is optional on the cancellation/interrupt path too --
        absence must never suppress the re-raise."""
        device = _FakeLight(power=0)

        async def _interrupt(*args: object, **kwargs: object) -> None:
            raise make_exc

        device.set_color = _interrupt  # type: ignore[method-assign]
        state = CapturedState(
            kind="light", power=65535, color=HSBK(1.0, 1.0, 1.0, 3500)
        )

        with pytest.raises(make_exc):
            await restore_and_verify_device_state(device, state)

    @pytest.mark.parametrize(
        "make_exc", [asyncio.CancelledError, KeyboardInterrupt], ids=["cancel", "kbint"]
    )
    async def test_cancellation_and_interrupt_during_readback_with_no_callback(
        self, make_exc: type[BaseException]
    ) -> None:
        """Same as above, but the interrupt arrives during the post-command
        recapture rather than the restore commands themselves."""
        device = _FakeLight(power=0)
        state = CapturedState(
            kind="light", power=65535, color=HSBK(1.0, 1.0, 1.0, 3500)
        )

        async def _interrupt() -> tuple[HSBK, int, str]:
            raise make_exc

        device.get_color = _interrupt  # type: ignore[method-assign]

        with pytest.raises(make_exc):
            await restore_and_verify_device_state(device, state)

    async def test_readback_exception_with_no_callback(self) -> None:
        """An ordinary readback exception with no callback still returns the
        bounded outcome instead of raising."""
        device = _FakeLight(power=0)
        state = CapturedState(
            kind="light", power=65535, color=HSBK(1.0, 1.0, 1.0, 3500)
        )

        async def _flaky_get_color() -> tuple[HSBK, int, str]:
            raise OSError("readback timed out")

        device.get_color = _flaky_get_color  # type: ignore[method-assign]

        result = await restore_and_verify_device_state(device, state)

        assert result == RestoreOutcome(
            restored=True, restoration_verified=False, detail="readback_failed"
        )


class TestPowerOutOfRangePreflight:
    """D-05/D-16: an intermediate captured power refuses mutation up front."""

    async def test_intermediate_power_performs_zero_mutation(self) -> None:
        device = _FakeLight(power=5242)
        state = CapturedState(kind="light", power=5242, color=HSBK(1.0, 1.0, 1.0, 3500))

        result = await restore_and_verify_device_state(device, state)

        assert result == RestoreOutcome(
            restored=False, restoration_verified=False, detail="power_out_of_range"
        )
        assert device.calls == []

    def test_intermediate_power_is_distinct_from_every_other_detail(self) -> None:
        """The preflight refusal is its own bounded category -- never mistaken
        for a timeout, retransmission, or D-16 restoration command/readback
        failure."""
        outcome = RestoreOutcome(
            restored=False, restoration_verified=False, detail="power_out_of_range"
        )
        assert outcome.detail not in {
            "command_failed",
            "readback_failed",
            "readback_mismatch",
        }

    async def test_resume_only_after_a_stable_binary_recapture(self) -> None:
        """After a refusal, the SAME session resumes normally once a fresh
        capture is binary -- the earlier refusal does not poison later work."""
        device = _FakeLight(power=5242, color=HSBK(1.0, 1.0, 1.0, 3500))
        intermediate = CapturedState(
            kind="light", power=5242, color=HSBK(1.0, 1.0, 1.0, 3500)
        )

        refused = await restore_and_verify_device_state(device, intermediate)
        assert refused.detail == "power_out_of_range"
        assert device.calls == []

        # The device settles to a binary level; a fresh capture now succeeds.
        device._power = 65535
        recaptured = await capture_device_state(device)
        assert is_binary_power(recaptured.power)
        device.calls.clear()

        result = await restore_and_verify_device_state(device, recaptured)

        assert result == RestoreOutcome(restored=True, restoration_verified=True)


class TestRestoreOutcome:
    """RestoreOutcome's own invariant and bounded-detail enforcement."""

    def test_verified_cannot_be_true_without_restored(self) -> None:
        with pytest.raises(ValueError, match="restoration_verified cannot be true"):
            RestoreOutcome(restored=False, restoration_verified=True)

    def test_rejects_an_unbounded_detail(self) -> None:
        with pytest.raises(ValueError, match="invalid restore outcome detail"):
            RestoreOutcome(
                restored=False, restoration_verified=False, detail="something_raw"
            )


# ---------------------------------------------------------------------------
# Plan 14-04: hermetically-proven physical protocol mode drivers.
# ---------------------------------------------------------------------------

_FULL_ROSTER: list[dict[str, Any]] = [
    {"alias": "mini-1", "device_class": "Light", "available": True},
    {"alias": "neon-1", "device_class": "MultiZoneLight", "available": True},
    {"alias": "ceiling-1", "device_class": "CeilingLight", "available": True},
    {"alias": "candle-1", "device_class": "MatrixLight", "available": True},
    {"alias": "tube-1", "device_class": "MatrixLight", "available": True},
]


class TestExpectedRoster:
    """THREAD-05 inventory authority: the roster is validated BEFORE any I/O."""

    def test_full_roster_is_accepted(self) -> None:
        validate_expected_roster(_FULL_ROSTER)  # must not raise

    def test_expected_alias_roster_lists_every_alias(self) -> None:
        assert expected_alias_roster(_FULL_ROSTER) == frozenset(
            {"mini-1", "neon-1", "ceiling-1", "candle-1", "tube-1"}
        )

    def test_expected_roster_by_class_groups_aliases(self) -> None:
        by_class = expected_roster_by_class(_FULL_ROSTER)
        assert by_class["MatrixLight"] == frozenset({"candle-1", "tube-1"})
        assert by_class["Light"] == frozenset({"mini-1"})

    @pytest.mark.parametrize(
        "device_class", ["Light", "MultiZoneLight", "CeilingLight"]
    )
    def test_rejects_a_roster_missing_a_required_class(self, device_class: str) -> None:
        roster = [
            entry for entry in _FULL_ROSTER if entry["device_class"] != device_class
        ]
        with pytest.raises(ValueError, match="missing required class"):
            validate_expected_roster(roster)

    def test_rejects_a_roster_with_only_one_matrixlight_alias(self) -> None:
        roster = [entry for entry in _FULL_ROSTER if entry["alias"] != "tube-1"]
        with pytest.raises(ValueError, match="two distinct MatrixLight aliases"):
            validate_expected_roster(roster)

    def test_empty_roster_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="missing required class"):
            validate_expected_roster([])


class _FakeAsyncDeviceIterator:
    """A minimal ``discover(timeout=...)``-shaped async generator double."""

    def __init__(
        self, devices: Sequence[Any] = (), *, error: BaseException | None = None
    ) -> None:
        self._devices = list(devices)
        self._error = error

    def __call__(self, timeout: float = 0.0) -> _FakeAsyncDeviceIterator:
        return self

    def __aiter__(self) -> _FakeAsyncDeviceIterator:
        return self._iter()

    async def _iter(self) -> Any:
        if self._error is not None:
            raise self._error
        for device in self._devices:
            yield device


class _StubDevice:
    """A bare ``.serial``-only double -- discovery only reads that field."""

    def __init__(self, serial: str) -> None:
        self.serial = serial


def _manifest_for_roster(**overrides: Any) -> dict[str, Any]:
    return build_manifest(**_manifest_kwargs(inventory=_FULL_ROSTER, **overrides))


class TestRunDiscoverySession:
    """THREAD-01: six paired, order-alternated rounds (D-01/D-02)."""

    async def test_records_all_six_rounds_alternating_source_order(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()
        alias_map = {"d073d5000005": "mini-1"}
        discover_fn = _FakeAsyncDeviceIterator([_StubDevice("d073d5000005")])
        mdns_fn = _FakeAsyncDeviceIterator([])
        sleeps: list[float] = []

        async def _sleep(seconds: float) -> None:
            sleeps.append(seconds)

        await run_discovery_session(
            session_dir=tmp_path,
            manifest=manifest,
            alias_map=alias_map,
            discover_fn=discover_fn,
            discover_mdns_fn=mdns_fn,
            sleep=_sleep,
        )

        rows = reload_discovery_events(tmp_path / "14-DISCOVERY.jsonl")
        assert len(rows) == DISCOVERY_ROUNDS * 2
        for row in rows:
            expected_first = "discover" if row["round"] % 2 == 1 else "discover_mdns"
            if row["source"] == expected_first:
                assert row["call_order"] == 1
            else:
                assert row["call_order"] == 2
        discover_rows = [row for row in rows if row["source"] == "discover"]
        assert all(row["outcome"] == "success" for row in discover_rows)
        assert all(row["devices"] == ["mini-1"] for row in discover_rows)
        mdns_rows = [row for row in rows if row["source"] == "discover_mdns"]
        assert all(row["outcome"] == "empty" for row in mdns_rows)
        # Five inter-round gaps for six rounds, taken from the frozen schedule.
        assert sleeps == list(manifest["discovery_round_gaps_s"])

    async def test_resumes_without_re_recording_existing_rounds(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()
        journal_path = tmp_path / "14-DISCOVERY.jsonl"
        append_discovery_event(
            journal_path,
            build_discovery_event(
                session_id=manifest["session_id"],
                protocol_version=manifest["protocol_version"],
                revision=manifest["revision"],
                round_number=1,
                source="discover",
                outcome="empty",
                provenance="physical",
            ),
        )
        calls: list[str] = []

        def _track(name: str) -> _FakeAsyncDeviceIterator:
            calls.append(name)
            return _FakeAsyncDeviceIterator([])

        await run_discovery_session(
            session_dir=tmp_path,
            manifest=manifest,
            alias_map={},
            discover_fn=lambda timeout=0.0: (
                calls.append("discover") or _FakeAsyncDeviceIterator([])
            )(),
            discover_mdns_fn=lambda timeout=0.0: (
                calls.append("discover_mdns") or _FakeAsyncDeviceIterator([])
            )(),
            sleep=lambda seconds: asyncio.sleep(0),
        )

        rows = reload_discovery_events(journal_path)
        assert len(rows) == DISCOVERY_ROUNDS * 2
        # Round 1's discover call was never repeated.
        assert calls.count("discover") == DISCOVERY_ROUNDS - 1

    async def test_records_failed_outcome_on_network_error(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()

        await run_discovery_session(
            session_dir=tmp_path,
            manifest=manifest,
            alias_map={},
            discover_fn=_FakeAsyncDeviceIterator(error=LifxNetworkError("boom")),
            discover_mdns_fn=_FakeAsyncDeviceIterator([]),
            sleep=lambda seconds: asyncio.sleep(0),
        )

        rows = reload_discovery_events(tmp_path / "14-DISCOVERY.jsonl")
        discover_rows = [row for row in rows if row["source"] == "discover"]
        assert all(row["outcome"] == "failed" for row in discover_rows)

    async def test_roster_drift_stops_the_session(self, tmp_path: Path) -> None:
        manifest = _manifest_for_roster()
        alias_map = {"d073d5009999": "unexpected-alias"}

        with pytest.raises(RosterDriftError):
            await run_discovery_session(
                session_dir=tmp_path,
                manifest=manifest,
                alias_map=alias_map,
                discover_fn=_FakeAsyncDeviceIterator([_StubDevice("d073d5009999")]),
                discover_mdns_fn=_FakeAsyncDeviceIterator([]),
                sleep=lambda seconds: asyncio.sleep(0),
            )

    async def test_unmapped_device_is_skipped_not_drift(self, tmp_path: Path) -> None:
        manifest = _manifest_for_roster()

        await run_discovery_session(
            session_dir=tmp_path,
            manifest=manifest,
            alias_map={},  # nothing resolves -- not the same as roster drift
            discover_fn=_FakeAsyncDeviceIterator([_StubDevice("d073d5001111")]),
            discover_mdns_fn=_FakeAsyncDeviceIterator([]),
            sleep=lambda seconds: asyncio.sleep(0),
        )

        rows = reload_discovery_events(tmp_path / "14-DISCOVERY.jsonl")
        discover_rows = [row for row in rows if row["source"] == "discover"]
        assert all(row["outcome"] == "empty" for row in discover_rows)

    async def test_cancellation_records_interrupted_and_reraises(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()

        async def _cancelling_call(timeout: float = 0.0) -> Any:
            raise asyncio.CancelledError()
            yield  # pragma: no cover - never reached, makes this a generator

        with pytest.raises(asyncio.CancelledError):
            await run_discovery_session(
                session_dir=tmp_path,
                manifest=manifest,
                alias_map={},
                discover_fn=_cancelling_call,
                discover_mdns_fn=_FakeAsyncDeviceIterator([]),
                sleep=lambda seconds: asyncio.sleep(0),
            )

        rows = reload_discovery_events(tmp_path / "14-DISCOVERY.jsonl")
        assert rows[0]["outcome"] == "interrupted"


class TestRunOneRequestTrial:
    """The thin production glue over a real DeviceConnection (D-05/D-07)."""

    async def test_completed_trial_derives_logical_and_ack_latency(self) -> None:
        device = Light(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=3
        )
        task: asyncio.Task[tuple[str, dict[str, Any] | None]] | None = None
        try:
            await device.connection.open()
            task = asyncio.create_task(run_one_request_trial(device, 65535))
            await _wait_for_keys(device.connection, 1)
            key = next(iter(device.connection._pending_requests))
            source, sequence, _serial = key
            header = _header(
                source=source,
                sequence=sequence,
                target=bytes.fromhex(device.connection.serial) + b"\x00\x00",
                pkt_type=_ACKNOWLEDGEMENT_PKT_TYPE,
                payload_len=0,
            )
            device.connection._pending_requests[key].put_nowait((header, b""))
            outcome, derived = await asyncio.wait_for(task, timeout=1.0)
            task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await device.connection.close()

        assert outcome == "completed"
        assert derived is not None
        assert derived["logical_latency_ns"] >= 0
        assert derived["ack_rtt_ns"] >= 0
        assert derived["thread_connection"] is False

    async def test_timeout_is_reported_without_derived_result(self) -> None:
        device = Light(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=0.1, max_retries=1
        )
        try:
            await device.connection.open()
            outcome, derived = await run_one_request_trial(device, 65535)
        finally:
            await device.connection.close()

        assert outcome == "timeout"
        assert derived is None

    async def test_send_error_is_reported_without_derived_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        device = Light(serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=0.1)

        async def _raise_network_error(level: bool | int) -> None:
            raise LifxNetworkError("socket gone")

        monkeypatch.setattr(device, "set_power", _raise_network_error)

        outcome, derived = await run_one_request_trial(device, 65535)

        assert outcome == "send_error"
        assert derived is None

    async def test_anomalous_accepted_event_with_no_matching_sent_is_send_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """derive_request_result() raising ValueError is a send-side anomaly,
        not a fabricated latency (defensive branch; production sequence
        correlation already guarantees a matching sent event)."""
        import scripts.thread_revalidation as thread_revalidation_module

        device = Light(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=3
        )
        task: asyncio.Task[tuple[str, dict[str, Any] | None]] | None = None
        monkeypatch.setattr(
            thread_revalidation_module,
            "derive_request_result",
            lambda events: (_ for _ in ()).throw(ValueError("no matching sent")),
        )
        try:
            await device.connection.open()
            task = asyncio.create_task(run_one_request_trial(device, 65535))
            await _wait_for_keys(device.connection, 1)
            key = next(iter(device.connection._pending_requests))
            source, sequence, _serial = key
            header = _header(
                source=source,
                sequence=sequence,
                target=bytes.fromhex(device.connection.serial) + b"\x00\x00",
                pkt_type=_ACKNOWLEDGEMENT_PKT_TYPE,
                payload_len=0,
            )
            device.connection._pending_requests[key].put_nowait((header, b""))
            outcome, derived = await asyncio.wait_for(task, timeout=1.0)
            task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await device.connection.close()

        assert outcome == "send_error"
        assert derived is None


class TestRunRequestTrials:
    """THREAD-02: the frozen 100-trial loop, resumable, D-05 preflight (D-03/D-06)."""

    async def test_all_trials_already_recorded_is_a_no_op(self, tmp_path: Path) -> None:
        manifest = _manifest_for_roster()
        journal_path = tmp_path / "14-REQUESTS.jsonl"
        for trial in range(1, REQUEST_TRIALS + 1):
            append_request_trial_event(
                journal_path,
                build_request_trial_event(
                    **_request_trial_kwargs(
                        session_id=manifest["session_id"],
                        revision=manifest["revision"],
                        alias="mini-1",
                        trial=trial,
                        provenance="physical",
                    )
                ),
            )
        get_power_called = False

        async def _get_power() -> int:
            nonlocal get_power_called
            get_power_called = True
            return 65535  # pragma: no cover - never reached

        await run_request_trials(
            session_dir=tmp_path,
            manifest=manifest,
            alias="mini-1",
            get_power=_get_power,
            run_trial=lambda power: _async_return(("completed", None)),
            sleep=lambda seconds: asyncio.sleep(0),
        )

        assert get_power_called is False
        assert len(reload_request_trial_events(journal_path)) == REQUEST_TRIALS

    async def test_runs_every_trial_and_records_gaps(self, tmp_path: Path) -> None:
        manifest = _manifest_for_roster()
        gaps_seen: list[float] = []

        async def _sleep(seconds: float) -> None:
            gaps_seen.append(seconds)

        call_count = 0

        async def _run_trial(power: int) -> tuple[str, dict[str, Any] | None]:
            nonlocal call_count
            call_count += 1
            return "completed", {
                "logical_latency_ns": call_count,
                "ack_rtt_ns": call_count,
                "thread_connection": True,
            }

        await run_request_trials(
            session_dir=tmp_path,
            manifest=manifest,
            alias="mini-1",
            get_power=lambda: _async_return(65535),
            run_trial=_run_trial,
            sleep=_sleep,
        )

        rows = reload_request_trial_events(tmp_path / "14-REQUESTS.jsonl")
        assert len(rows) == REQUEST_TRIALS
        assert {row["trial"] for row in rows} == set(range(1, REQUEST_TRIALS + 1))
        assert all(row["outcome"] == "completed" for row in rows)
        assert gaps_seen == list(manifest["request_trial_gaps_s"])

    async def test_power_out_of_range_stops_all_trials_without_mutation(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()
        run_trial_called = False

        async def _run_trial(power: int) -> tuple[str, dict[str, Any] | None]:
            nonlocal run_trial_called
            run_trial_called = True
            return "completed", None  # pragma: no cover - never called

        await run_request_trials(
            session_dir=tmp_path,
            manifest=manifest,
            alias="mini-1",
            get_power=lambda: _async_return(32768),
            run_trial=_run_trial,
            sleep=lambda seconds: asyncio.sleep(0),
        )

        rows = reload_request_trial_events(tmp_path / "14-REQUESTS.jsonl")
        assert len(rows) == REQUEST_TRIALS
        assert all(row["outcome"] == "power_out_of_range" for row in rows)
        assert run_trial_called is False

    async def test_resumes_only_missing_trials(self, tmp_path: Path) -> None:
        manifest = _manifest_for_roster()
        journal_path = tmp_path / "14-REQUESTS.jsonl"
        for trial in range(1, REQUEST_TRIALS):
            append_request_trial_event(
                journal_path,
                build_request_trial_event(
                    **_request_trial_kwargs(
                        session_id=manifest["session_id"],
                        revision=manifest["revision"],
                        alias="mini-1",
                        trial=trial,
                        provenance="physical",
                    )
                ),
            )
        call_count = 0

        async def _run_trial(power: int) -> tuple[str, dict[str, Any] | None]:
            nonlocal call_count
            call_count += 1
            return "completed", {
                "logical_latency_ns": 1,
                "ack_rtt_ns": 1,
                "thread_connection": True,
            }

        await run_request_trials(
            session_dir=tmp_path,
            manifest=manifest,
            alias="mini-1",
            get_power=lambda: _async_return(65535),
            run_trial=_run_trial,
            sleep=lambda seconds: asyncio.sleep(0),
        )

        assert call_count == 1
        rows = reload_request_trial_events(journal_path)
        assert len(rows) == REQUEST_TRIALS

    async def test_timeout_and_send_error_trials_remain_evidence(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()
        outcomes = iter(["timeout"] * 50 + ["send_error"] * 50)

        async def _run_trial(power: int) -> tuple[str, dict[str, Any] | None]:
            return next(outcomes), None

        await run_request_trials(
            session_dir=tmp_path,
            manifest=manifest,
            alias="mini-1",
            get_power=lambda: _async_return(65535),
            run_trial=_run_trial,
            sleep=lambda seconds: asyncio.sleep(0),
        )

        rows = reload_request_trial_events(tmp_path / "14-REQUESTS.jsonl")
        assert sum(1 for row in rows if row["outcome"] == "timeout") == 50
        assert sum(1 for row in rows if row["outcome"] == "send_error") == 50


async def _async_return(value: Any) -> Any:
    return value


class _FakeAnimatorStatsSequence:
    """Returns one canned ``AnimatorStats`` per call, in order."""

    def __init__(self, stats: Sequence[AnimatorStats | Exception]) -> None:
        self._stats = list(stats)
        self.calls = 0

    def __call__(self) -> AnimatorStats:
        self.calls += 1
        result = self._stats[min(self.calls - 1, len(self._stats) - 1)]
        if isinstance(result, Exception):
            raise result
        return result


class _FakeMonotonicClock:
    """A controllable monotonic clock -- each ``sleep()`` advances it exactly."""

    def __init__(self, start: float = 0.0) -> None:
        self.value = start
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.value

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class TestRunAnimationObservation:
    """THREAD-03: the frozen D-10 ascending observation, restored on exit (D-14)."""

    async def test_completed_observation_tallies_current_behaviour_stats(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()
        clock = _FakeMonotonicClock()
        restored_state = RestoreOutcome(restored=True, restoration_verified=True)
        liveness_calls: list[bool] = []

        async def _check_liveness() -> bool:
            liveness_calls.append(True)
            return True

        async def _make_send_frame() -> Any:
            return _FakeAnimatorStatsSequence(
                [AnimatorStats(packets_sent=1, total_time_ms=1.0, acks_outstanding=0)]
            )

        async def _restore(state: CapturedState) -> RestoreOutcome:
            return restored_state

        row = await run_animation_observation(
            session_dir=tmp_path,
            manifest=manifest,
            alias="candle-1",
            capture_state=lambda: _async_return(CapturedState(kind="light", power=0)),
            check_liveness=_check_liveness,
            make_send_frame=_make_send_frame,
            restore=_restore,
            now=clock.now,
            sleep=clock.sleep,
        )

        assert len(row["rates"]) == len(ANIMATION_SCHEDULE)
        assert all(rate["outcome"] == "completed" for rate in row["rates"])
        assert all(rate["offered"] == rate["packets_sent"] for rate in row["rates"])
        assert row["restored"] is True
        assert row["restoration_verified"] is True
        assert len(liveness_calls) == 2  # pre AND post

        journal_rows = reload_animation_events(tmp_path / "14-ANIMATION.jsonl")
        assert len(journal_rows) == 1

    async def test_zero_successful_sends_is_a_valid_completed_result(
        self, tmp_path: Path
    ) -> None:
        """D-12: zero useful throughput can never fail Phase 14."""
        manifest = _manifest_for_roster()
        clock = _FakeMonotonicClock()

        async def _make_send_frame() -> Any:
            return _FakeAnimatorStatsSequence(
                [
                    AnimatorStats(
                        packets_sent=0,
                        total_time_ms=0.1,
                        gated=True,
                        acks_outstanding=2,
                    )
                ]
            )

        row = await run_animation_observation(
            session_dir=tmp_path,
            manifest=manifest,
            alias="candle-1",
            capture_state=lambda: _async_return(CapturedState(kind="light", power=0)),
            check_liveness=lambda: _async_return(True),
            make_send_frame=_make_send_frame,
            restore=lambda state: _async_return(
                RestoreOutcome(restored=True, restoration_verified=True)
            ),
            now=clock.now,
            sleep=clock.sleep,
        )

        assert all(rate["outcome"] == "completed" for rate in row["rates"])
        assert all(rate["packets_sent"] == 0 for rate in row["rates"])
        assert all(rate["gated"] == rate["offered"] for rate in row["rates"])

    async def test_send_frame_exception_counts_as_failed_but_rate_completes(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()
        clock = _FakeMonotonicClock()

        async def _make_send_frame() -> Any:
            return _FakeAnimatorStatsSequence([RuntimeError("socket gone")])

        row = await run_animation_observation(
            session_dir=tmp_path,
            manifest=manifest,
            alias="candle-1",
            capture_state=lambda: _async_return(CapturedState(kind="light", power=0)),
            check_liveness=lambda: _async_return(False),
            make_send_frame=_make_send_frame,
            restore=lambda state: _async_return(
                RestoreOutcome(restored=True, restoration_verified=True)
            ),
            now=clock.now,
            sleep=clock.sleep,
        )

        assert all(rate["outcome"] == "completed" for rate in row["rates"])
        assert all(rate["failed"] == rate["offered"] for rate in row["rates"])
        assert row["pre_liveness"] is False

    async def test_construction_failure_records_a_failed_attempt_and_still_restores(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()
        clock = _FakeMonotonicClock()
        restore_called = False

        async def _make_send_frame() -> Any:
            raise RuntimeError("no such device")

        async def _restore(state: CapturedState) -> RestoreOutcome:
            nonlocal restore_called
            restore_called = True
            return RestoreOutcome(restored=True, restoration_verified=True)

        row = await run_animation_observation(
            session_dir=tmp_path,
            manifest=manifest,
            alias="candle-1",
            capture_state=lambda: _async_return(CapturedState(kind="light", power=0)),
            check_liveness=lambda: _async_return(True),
            make_send_frame=_make_send_frame,
            restore=_restore,
            now=clock.now,
            sleep=clock.sleep,
        )

        assert all(rate["outcome"] == "failed" for rate in row["rates"])
        assert restore_called is True

    async def test_cancellation_pads_remaining_rates_restores_then_reraises(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()
        clock = _FakeMonotonicClock()
        restore_called = False

        def _stats() -> AnimatorStats:
            raise asyncio.CancelledError()

        async def _make_send_frame() -> Any:
            return _stats

        async def _restore(state: CapturedState) -> RestoreOutcome:
            nonlocal restore_called
            restore_called = True
            return RestoreOutcome(restored=True, restoration_verified=True)

        with pytest.raises(asyncio.CancelledError):
            await run_animation_observation(
                session_dir=tmp_path,
                manifest=manifest,
                alias="candle-1",
                capture_state=lambda: _async_return(
                    CapturedState(kind="light", power=0)
                ),
                check_liveness=lambda: _async_return(True),
                make_send_frame=_make_send_frame,
                restore=_restore,
                now=clock.now,
                sleep=clock.sleep,
            )

        assert restore_called is True
        rows = reload_animation_events(tmp_path / "14-ANIMATION.jsonl")
        assert len(rows) == 1
        assert all(rate["outcome"] == "interrupted" for rate in rows[0]["rates"])

    async def test_cancellation_during_construction_pads_all_rates(
        self, tmp_path: Path
    ) -> None:
        """Cancellation of make_send_frame() itself (before any rate starts)
        still produces a valid, fully-padded three-rate row after restore."""
        manifest = _manifest_for_roster()
        clock = _FakeMonotonicClock()
        restore_called = False

        async def _make_send_frame() -> Any:
            raise asyncio.CancelledError()

        async def _restore(state: CapturedState) -> RestoreOutcome:
            nonlocal restore_called
            restore_called = True
            return RestoreOutcome(restored=True, restoration_verified=True)

        with pytest.raises(asyncio.CancelledError):
            await run_animation_observation(
                session_dir=tmp_path,
                manifest=manifest,
                alias="candle-1",
                capture_state=lambda: _async_return(
                    CapturedState(kind="light", power=0)
                ),
                check_liveness=lambda: _async_return(True),
                make_send_frame=_make_send_frame,
                restore=_restore,
                now=clock.now,
                sleep=clock.sleep,
            )

        assert restore_called is True
        rows = reload_animation_events(tmp_path / "14-ANIMATION.jsonl")
        assert len(rows) == 1
        assert len(rows[0]["rates"]) == len(ANIMATION_SCHEDULE)
        assert all(rate["outcome"] == "interrupted" for rate in rows[0]["rates"])

    async def test_already_recorded_alias_is_a_no_op(self, tmp_path: Path) -> None:
        manifest = _manifest_for_roster()
        existing = build_animation_event(
            **_animation_kwargs(
                session_id=manifest["session_id"],
                revision=manifest["revision"],
                alias="candle-1",
            )
        )
        append_animation_event(tmp_path / "14-ANIMATION.jsonl", existing)
        called = False

        async def _make_send_frame() -> Any:
            nonlocal called
            called = True
            return _FakeAnimatorStatsSequence([])  # pragma: no cover

        row = await run_animation_observation(
            session_dir=tmp_path,
            manifest=manifest,
            alias="candle-1",
            capture_state=lambda: _async_return(CapturedState(kind="light", power=0)),
            check_liveness=lambda: _async_return(True),
            make_send_frame=_make_send_frame,
            restore=lambda state: _async_return(
                RestoreOutcome(restored=True, restoration_verified=True)
            ),
        )

        assert called is False
        assert row == existing


class TestRunStalenessExperiment:
    """THREAD-04: absolute 60s cadence, 3-pair confirmation, 3h censoring (D-04)."""

    async def test_confirms_expiry_after_three_consecutive_absent_pairs(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()
        clock = _FakeMonotonicClock()
        polls_seen = iter(
            [(True, True), (False, False), (False, False), (False, False)]
        )

        async def _poll() -> tuple[bool, bool]:
            return next(polls_seen)

        row = await run_staleness_experiment(
            session_dir=tmp_path,
            manifest=manifest,
            alias="candle-1",
            disconnect_ns=0,
            poll=_poll,
            restore_available=lambda: _async_return((999, 42.0)),
            now=clock.now,
            sleep=clock.sleep,
            interval_s=1.0,
            confirm_polls=3,
            cap_s=100.0,
        )

        assert row["disposition"] == "confirmed_expiry"
        assert row["confirmed_expiry_poll"] == 4
        assert row["restored_available_ns"] == 999
        assert row["restoration_duration_s"] == 42.0

    async def test_reaches_cap_without_confirmation_is_censored(
        self, tmp_path: Path
    ) -> None:
        """Uses the real frozen cadence/cap (STALENESS_POLL_INTERVAL_S/
        STALENESS_CAP_S) rather than an injected shorter one: the row schema
        (_validate_staleness_event) hard-checks elapsed_s against the real
        D-04 three-hour constant, so a "censored" row can only validate at
        the genuine cap -- the fake clock makes this instant regardless of
        the simulated 180 polls it takes to get there."""
        manifest = _manifest_for_roster()
        clock = _FakeMonotonicClock()

        async def _poll() -> tuple[bool, bool]:
            return True, True  # always present -- never confirms expiry

        row = await run_staleness_experiment(
            session_dir=tmp_path,
            manifest=manifest,
            alias="candle-1",
            disconnect_ns=0,
            poll=_poll,
            restore_available=lambda: _async_return((999, 42.0)),
            now=clock.now,
            sleep=clock.sleep,
        )

        assert row["disposition"] == "censored"
        assert row["confirmed_expiry_poll"] is None
        assert len(row["polls"]) == round(STALENESS_CAP_S / STALENESS_POLL_INTERVAL_S)

    async def test_restored_before_expiry_stops_the_experiment(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()
        clock = _FakeMonotonicClock()

        async def _poll() -> tuple[bool, bool]:
            return False, False

        async def _should_stop_early() -> bool:
            return True

        row = await run_staleness_experiment(
            session_dir=tmp_path,
            manifest=manifest,
            alias="candle-1",
            disconnect_ns=0,
            poll=_poll,
            restore_available=lambda: _async_return((123, 7.0)),
            should_stop_early=_should_stop_early,
            now=clock.now,
            sleep=clock.sleep,
            interval_s=1.0,
            confirm_polls=3,
            cap_s=100.0,
        )

        assert row["disposition"] == "restored_before_expiry"

    async def test_cadence_overrun_is_recorded_as_a_confounder(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()
        clock = _FakeMonotonicClock()

        async def _poll() -> tuple[bool, bool]:
            # This single poll call overruns the real 60-second cadence.
            clock.value += STALENESS_POLL_INTERVAL_S * 2
            return True, True

        row = await run_staleness_experiment(
            session_dir=tmp_path,
            manifest=manifest,
            alias="candle-1",
            disconnect_ns=0,
            poll=_poll,
            restore_available=lambda: _async_return((999, 42.0)),
            now=clock.now,
            sleep=clock.sleep,
        )

        assert "unquiesced_environment" in row["confounders"]
        assert row["disposition"] == "censored"

    async def test_cancellation_records_interrupted_with_polls_so_far(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest_for_roster()
        clock = _FakeMonotonicClock()
        poll_count = 0

        async def _poll() -> tuple[bool, bool]:
            nonlocal poll_count
            poll_count += 1
            if poll_count == 2:
                raise asyncio.CancelledError()
            return True, True

        with pytest.raises(asyncio.CancelledError):
            await run_staleness_experiment(
                session_dir=tmp_path,
                manifest=manifest,
                alias="candle-1",
                disconnect_ns=0,
                poll=_poll,
                restore_available=lambda: _async_return(None),
                now=clock.now,
                sleep=clock.sleep,
                interval_s=1.0,
                confirm_polls=3,
                cap_s=100.0,
            )

        rows = reload_staleness_events(tmp_path / "14-STALENESS.jsonl")
        assert len(rows) == 1
        assert rows[0]["disposition"] == "interrupted"
        assert len(rows[0]["polls"]) == 1
        assert rows[0]["restored_available_ns"] is None
        assert rows[0]["restoration_duration_s"] is None

    async def test_cancellation_during_restoration_wait_preserves_disposition(
        self, tmp_path: Path
    ) -> None:
        """T-14-06 change 2: restoration polling has no deadline, so an
        operator's Ctrl-C is the ONLY way out of it. A cancellation raised
        from inside ``restore_available`` (simulating that unbounded wait)
        must be caught, persist the row and re-raise unchanged -- exactly
        like a cancellation mid-poll -- but the absence-detection protocol
        had ALREADY closed as ``confirmed_expiry`` by this point (all four
        polls are present, including the confirming one), so the persisted
        disposition must stay ``confirmed_expiry``, never be downgraded to
        ``interrupted``: the schema itself forbids a non-confirmed_expiry
        disposition once the polls contain a confirmed three-pair-absent
        window. Only the restoration fields stay null -- restoration itself
        is what was interrupted, not expiry detection."""
        manifest = _manifest_for_roster()
        clock = _FakeMonotonicClock()
        polls_seen = iter(
            [(True, True), (False, False), (False, False), (False, False)]
        )

        async def _poll() -> tuple[bool, bool]:
            return next(polls_seen)

        async def _restore_available() -> tuple[int, float] | None:
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await run_staleness_experiment(
                session_dir=tmp_path,
                manifest=manifest,
                alias="candle-1",
                disconnect_ns=0,
                poll=_poll,
                restore_available=_restore_available,
                now=clock.now,
                sleep=clock.sleep,
                interval_s=1.0,
                confirm_polls=3,
                cap_s=100.0,
            )

        rows = reload_staleness_events(tmp_path / "14-STALENESS.jsonl")
        assert len(rows) == 1
        assert rows[0]["disposition"] == "confirmed_expiry"
        # All four polls that already confirmed expiry are preserved --
        # cancellation during the UNBOUNDED restoration wait must never
        # discard evidence collected before it, only fail to add a
        # restoration timestamp.
        assert len(rows[0]["polls"]) == 4
        assert rows[0]["confirmed_expiry_poll"] == 4
        assert rows[0]["restored_available_ns"] is None
        assert rows[0]["restoration_duration_s"] is None

    async def test_cancellation_during_restoration_wait_after_censoring(
        self, tmp_path: Path
    ) -> None:
        """The same preserve-disposition rule applies to ``censored`` -- not
        only ``confirmed_expiry`` -- proving the fix is general rather than
        special-cased to one disposition."""
        manifest = _manifest_for_roster()
        clock = _FakeMonotonicClock()

        async def _poll() -> tuple[bool, bool]:
            return True, True  # always present -- never confirms expiry

        async def _restore_available() -> tuple[int, float] | None:
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await run_staleness_experiment(
                session_dir=tmp_path,
                manifest=manifest,
                alias="candle-1",
                disconnect_ns=0,
                poll=_poll,
                restore_available=_restore_available,
                now=clock.now,
                sleep=clock.sleep,
            )

        rows = reload_staleness_events(tmp_path / "14-STALENESS.jsonl")
        assert len(rows) == 1
        assert rows[0]["disposition"] == "censored"
        assert rows[0]["restored_available_ns"] is None
        assert rows[0]["restoration_duration_s"] is None

    async def test_already_recorded_alias_is_a_no_op(self, tmp_path: Path) -> None:
        manifest = _manifest_for_roster()
        existing = build_staleness_event(
            **_staleness_kwargs(
                session_id=manifest["session_id"],
                revision=manifest["revision"],
                alias="candle-1",
            )
        )
        append_staleness_event(tmp_path / "14-STALENESS.jsonl", existing)
        poll_called = False

        async def _poll() -> tuple[bool, bool]:
            nonlocal poll_called
            poll_called = True
            return True, True  # pragma: no cover

        row = await run_staleness_experiment(
            session_dir=tmp_path,
            manifest=manifest,
            alias="candle-1",
            disconnect_ns=0,
            poll=_poll,
            restore_available=lambda: _async_return(None),
        )

        assert poll_called is False
        assert row == existing


def _physical_discovery_row(alias: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
    return build_discovery_event(
        session_id=manifest["session_id"],
        protocol_version=manifest["protocol_version"],
        revision=manifest["revision"],
        round_number=1,
        source="discover",
        outcome="success",
        devices=[alias],
        provenance="physical",
    )


def _physical_request_rows(
    alias: str, manifest: Mapping[str, Any]
) -> list[dict[str, Any]]:
    return [
        build_request_trial_event(
            session_id=manifest["session_id"],
            protocol_version=manifest["protocol_version"],
            revision=manifest["revision"],
            alias=alias,
            trial=trial,
            outcome="completed",
            logical_latency_ns=1,
            ack_rtt_ns=1,
            thread_connection=True,
            provenance="physical",
        )
        for trial in range(1, REQUEST_TRIALS + 1)
    ]


def _physical_animation_row(alias: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
    return build_animation_event(
        **_animation_kwargs(
            session_id=manifest["session_id"],
            revision=manifest["revision"],
            alias=alias,
            provenance="physical",
        )
    )


class TestDeriveClassLedgerFromRoster:
    """THREAD-05: the ledger is derived from the roster and journals ONLY."""

    def test_fully_evidenced_roster_closes_every_available_class(self) -> None:
        manifest = _manifest_for_roster()
        discovery_rows = [
            _physical_discovery_row(alias, manifest)
            for alias in expected_alias_roster(_FULL_ROSTER)
        ]
        request_rows = [
            row
            for alias in expected_alias_roster(_FULL_ROSTER)
            for row in _physical_request_rows(alias, manifest)
        ]
        # Deliberately no animation evidence at all: closure requires only
        # discovery plus complete request trials (THREAD-03 is a recorded
        # scope boundary, not a closure requirement).
        closure_rows = [
            build_closure_event(
                **_closure_kwargs(
                    session_id=manifest["session_id"],
                    revision=manifest["revision"],
                    device_class="InfraredLight",
                    disposition="named_gap",
                    aliases=[],
                    gap_reason="no Thread-capable fleet hardware",
                    gap_recorded_date="2026-08-31",
                    provenance=None,
                )
            ),
            build_closure_event(
                **_closure_kwargs(
                    session_id=manifest["session_id"],
                    revision=manifest["revision"],
                    device_class="HevLight",
                    disposition="named_gap",
                    aliases=[],
                    gap_reason="no Thread-capable fleet hardware",
                    gap_recorded_date="2026-08-31",
                    provenance=None,
                )
            ),
        ]

        ledger = derive_class_ledger_from_roster(
            inventory=_FULL_ROSTER,
            discovery_rows=discovery_rows,
            request_rows=request_rows,
            closure_rows=closure_rows,
        )

        assert ledger["complete"] is True
        assert ledger["missing_classes"] == []
        assert ledger["classes"]["MatrixLight"]["aliases"] == ["candle-1", "tube-1"]
        assert ledger["classes"]["InfraredLight"]["disposition"] == "named_gap"

    def test_signature_has_no_animation_rows_parameter(self) -> None:
        """Regression guard (decision 2026-09-04): closure derivation must
        never regain an animation dependency. Thread animation is a recorded
        scope boundary (THREAD-03), not a closure requirement, so
        `derive_class_ledger_from_roster` intentionally has no
        `animation_rows` parameter for a caller to accidentally wire back
        in."""
        import inspect

        assert (
            "animation_rows"
            not in inspect.signature(derive_class_ledger_from_roster).parameters
        )

    def test_one_incomplete_alias_keeps_the_whole_class_incomplete(self) -> None:
        manifest = _manifest_for_roster()
        discovery_rows = [
            _physical_discovery_row(alias, manifest)
            for alias in expected_alias_roster(_FULL_ROSTER)
        ]
        # tube-1 (the second MatrixLight) has no request trials at all.
        request_rows = [
            row
            for alias in expected_alias_roster(_FULL_ROSTER)
            if alias != "tube-1"
            for row in _physical_request_rows(alias, manifest)
        ]
        ledger = derive_class_ledger_from_roster(
            inventory=_FULL_ROSTER,
            discovery_rows=discovery_rows,
            request_rows=request_rows,
            closure_rows=[],
        )

        assert ledger["complete"] is False
        assert "MatrixLight" in ledger["missing_classes"]
        # A sibling class with full evidence is unaffected.
        assert "Light" not in ledger["missing_classes"]

    def test_missing_named_gap_row_keeps_gap_class_missing(self) -> None:
        ledger = derive_class_ledger_from_roster(
            inventory=_FULL_ROSTER,
            discovery_rows=[],
            request_rows=[],
            closure_rows=[],
        )
        assert "InfraredLight" in ledger["missing_classes"]
        assert "HevLight" in ledger["missing_classes"]

    def test_synthetic_provenance_never_closes_a_class(self) -> None:
        """A synthetic row can never be laundered into fleet evidence (AC-17)."""
        manifest = _manifest_for_roster()
        discovery_rows = [
            build_discovery_event(
                session_id=manifest["session_id"],
                protocol_version=manifest["protocol_version"],
                revision=manifest["revision"],
                round_number=1,
                source="discover",
                outcome="success",
                devices=[alias],
                provenance="synthetic",
            )
            for alias in expected_alias_roster(_FULL_ROSTER)
        ]

        ledger = derive_class_ledger_from_roster(
            inventory=_FULL_ROSTER,
            discovery_rows=discovery_rows,
            request_rows=[],
            closure_rows=[],
        )
        assert ledger["complete"] is False


class TestForbiddenVocabulary:
    """SPEC prohibitions: no authoritative benchmark/tuning claim in evidence."""

    @pytest.mark.parametrize(
        "phrase",
        [
            "benchmark",
            "regression gate",
            "universal",
            "performance limit",
            "guaranteed",
            "tuning",
            "ceiling",
            "authoritative",
        ],
    )
    def test_detects_every_forbidden_phrase(self, phrase: str) -> None:
        assert contains_forbidden_vocabulary(f"This is a {phrase} result") == phrase

    def test_benign_text_is_accepted(self) -> None:
        assert contains_forbidden_vocabulary("no Thread-capable fleet hardware") is None

    def test_closure_event_rejects_forbidden_gap_reason(self) -> None:
        with pytest.raises(ValueError, match="forbidden evidence-language"):
            build_closure_event(
                **_closure_kwargs(
                    device_class="InfraredLight",
                    disposition="named_gap",
                    aliases=[],
                    gap_reason="authoritative Thread benchmark result",
                    gap_recorded_date="2026-08-31",
                    provenance=None,
                )
            )


class TestLoadTargetAliasMap:
    """The runtime-only serial-to-alias resolution helper (D-19)."""

    def test_loads_and_canonicalises_serials(self, tmp_path: Path) -> None:
        path = tmp_path / "target-map.json"
        path.write_text(json.dumps({"d0:73:d5:00:00:05": "mini-1"}), encoding="utf-8")

        aliases = _load_target_alias_map(path)

        assert aliases == {"d073d5000005": "mini-1"}

    def test_rejects_an_empty_map(self, tmp_path: Path) -> None:
        path = tmp_path / "target-map.json"
        path.write_text("{}", encoding="utf-8")

        with pytest.raises(ValueError, match="non-empty"):
            _load_target_alias_map(path)

    def test_rejects_a_duplicate_normalised_serial(self, tmp_path: Path) -> None:
        path = tmp_path / "target-map.json"
        path.write_text(
            json.dumps({"d073d5000005": "mini-1", "d0:73:d5:00:00:05": "mini-2"}),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="duplicate"):
            _load_target_alias_map(path)


class TestRunGitFailsClosedWithoutAGitExecutable:
    """validate_staged_evidence()'s own git-required guard (D-19 fail-closed)."""

    def test_raises_when_git_is_not_on_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        monkeypatch.setattr(
            thread_revalidation_module.shutil, "which", lambda _name: None
        )

        with pytest.raises(RuntimeError, match="git is required"):
            validate_staged_evidence(str(tmp_path))


def _init_bare_git_repo(repo_dir: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=repo_dir,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True)


def _stage_full_evidence(
    repo_dir: Path, evidence_dir: Path, manifest: dict[str, Any]
) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "14-MANIFEST.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    discovery_rows = [
        _physical_discovery_row(alias, manifest)
        for alias in expected_alias_roster(_FULL_ROSTER)
    ]
    request_rows = [
        row
        for alias in expected_alias_roster(_FULL_ROSTER)
        for row in _physical_request_rows(alias, manifest)
    ]
    animation_rows = [
        _physical_animation_row(alias, manifest)
        for alias in expected_alias_roster(_FULL_ROSTER)
    ]
    closure_rows = [
        build_closure_event(
            **_closure_kwargs(
                session_id=manifest["session_id"],
                revision=manifest["revision"],
                device_class=device_class,
                disposition="named_gap",
                aliases=[],
                gap_reason="no Thread-capable fleet hardware",
                gap_recorded_date="2026-08-31",
                provenance=None,
            )
        )
        for device_class in ("InfraredLight", "HevLight")
    ]

    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        path.write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in rows)
            + ("\n" if rows else ""),
            encoding="utf-8",
        )

    _write_jsonl(evidence_dir / "14-DISCOVERY.jsonl", discovery_rows)
    _write_jsonl(evidence_dir / "14-REQUESTS.jsonl", request_rows)
    _write_jsonl(evidence_dir / "14-ANIMATION.jsonl", animation_rows)
    _write_jsonl(evidence_dir / "14-STALENESS.jsonl", [])
    _write_jsonl(evidence_dir / "14-CLOSURE.jsonl", closure_rows)

    summary = generate_summary(
        discovery_rows=discovery_rows,
        request_rows=request_rows,
        animation_rows=animation_rows,
        staleness_rows=[],
        closure_rows=closure_rows,
    )
    summary["class_ledger"] = derive_class_ledger_from_roster(
        inventory=manifest["inventory"],
        discovery_rows=discovery_rows,
        request_rows=request_rows,
        closure_rows=closure_rows,
    )
    (evidence_dir / "14-SUMMARY.json").write_text(
        json.dumps(summary, sort_keys=True), encoding="utf-8"
    )
    (evidence_dir / "14-CLASS-LEDGER.json").write_text(
        json.dumps(summary["class_ledger"], sort_keys=True), encoding="utf-8"
    )
    (evidence_dir / "14-REPORT.md").write_text(
        generate_report(summary), encoding="utf-8"
    )

    subprocess.run(
        ["git", "add", str(evidence_dir.relative_to(repo_dir))],
        cwd=repo_dir,
        check=True,
    )


class _StubConnectedDevice:
    """A bare async-context-manager device double for CLI wiring tests.

    The underlying THREAD-0x orchestration functions
    (``run_discovery_session``/``run_request_trials``/
    ``run_animation_observation``/``run_staleness_experiment``) are already
    exhaustively tested against fakes and real production glue elsewhere
    (``TestRunDiscoverySession``, ``TestRunRequestTrials``,
    ``TestRunAnimationObservation``, ``TestRunStalenessExperiment``,
    ``TestRunOneRequestTrial``). The tests below prove only the CLI
    wrapper's own wiring and JSON reporting (Defect 2), by replacing the
    orchestration call itself with a fake that writes the same journal rows
    production code would -- never a real socket or discovery sweep.
    """

    serial = "d073d5000005"

    async def __aenter__(self) -> _StubConnectedDevice:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get_power(self) -> int:
        return 65535


class TestCliHardwareModeJsonOutput:
    """Defect 2: discover/request/animation/staleness each report an
    explicit JSON verdict too -- never implied by the exit code alone."""

    def test_discover_emits_json_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        alias_map_path = tmp_path / "alias-map.json"
        alias_map_path.write_text(
            json.dumps({"d073d5000005": "mini-1"}), encoding="utf-8"
        )

        async def _fake_run_discovery_session(**kwargs: Any) -> None:
            append_discovery_event(
                kwargs["session_dir"] / "14-DISCOVERY.jsonl",
                build_discovery_event(
                    session_id=manifest["session_id"],
                    protocol_version=manifest["protocol_version"],
                    revision=manifest["revision"],
                    round_number=1,
                    source="discover",
                    outcome="success",
                    devices=["mini-1"],
                    provenance="physical",
                ),
            )

        monkeypatch.setattr(
            thread_revalidation_module,
            "run_discovery_session",
            _fake_run_discovery_session,
        )

        exit_code = thread_revalidation_main(
            [
                "discover",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
            ]
        )
        assert exit_code == 0

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "discover"
        assert result["ok"] is True
        assert result["reason"] is None
        assert result["rounds_recorded"] == 1
        assert result["rounds_expected"] == DISCOVERY_ROUNDS * 2

    def test_request_emits_json_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        alias_map_path = tmp_path / "alias-map.json"
        alias_map_path.write_text(
            json.dumps({"d073d5000005": "mini-1"}), encoding="utf-8"
        )

        async def _fake_resolve_target_device(
            alias: str, alias_map: Any, **_: Any
        ) -> Any:
            assert alias == "mini-1"
            return _StubConnectedDevice()

        async def _fake_run_request_trials(**kwargs: Any) -> None:
            for row in _physical_request_rows("mini-1", manifest)[:3]:
                append_request_trial_event(
                    kwargs["session_dir"] / "14-REQUESTS.jsonl", row
                )

        monkeypatch.setattr(
            thread_revalidation_module,
            "_resolve_target_device",
            _fake_resolve_target_device,
        )
        monkeypatch.setattr(
            thread_revalidation_module, "run_request_trials", _fake_run_request_trials
        )

        exit_code = thread_revalidation_main(
            [
                "request",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--alias",
                "mini-1",
            ]
        )
        assert exit_code == 0

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "request"
        assert result["ok"] is True
        assert result["reason"] is None
        assert result["alias"] == "mini-1"
        assert result["trials_recorded"] == 3
        assert result["trials_expected"] == REQUEST_TRIALS
        assert result["outcomes"] == {"completed": 3}

    def test_animation_emits_json_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        alias_map_path = tmp_path / "alias-map.json"
        alias_map_path.write_text(
            json.dumps({"d073d5000005": "mini-1"}), encoding="utf-8"
        )

        async def _fake_resolve_target_device(
            alias: str, alias_map: Any, **_: Any
        ) -> Any:
            return _StubConnectedDevice()

        animation_row = _physical_animation_row("mini-1", manifest)

        async def _fake_run_animation_observation(**kwargs: Any) -> dict[str, Any]:
            append_animation_event(
                kwargs["session_dir"] / "14-ANIMATION.jsonl", animation_row
            )
            return animation_row

        monkeypatch.setattr(
            thread_revalidation_module,
            "_resolve_target_device",
            _fake_resolve_target_device,
        )
        monkeypatch.setattr(
            thread_revalidation_module,
            "run_animation_observation",
            _fake_run_animation_observation,
        )

        exit_code = thread_revalidation_main(
            [
                "animation",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--alias",
                "mini-1",
            ]
        )
        assert exit_code == 0

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "animation"
        assert result["ok"] is True
        assert result["reason"] is None
        assert result["alias"] == "mini-1"
        assert result["restored"] is True
        assert result["restoration_verified"] is True
        assert result["rate_outcomes"] == ["completed", "completed", "completed"]

    def test_staleness_emits_json_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        alias_map_path = tmp_path / "alias-map.json"
        alias_map_path.write_text(
            json.dumps({"d073d5000005": "mini-1"}), encoding="utf-8"
        )

        staleness_row = build_staleness_event(
            **_staleness_kwargs(
                session_id=manifest["session_id"],
                revision=manifest["revision"],
                alias="mini-1",
                provenance="physical",
            )
        )

        async def _fake_run_staleness_experiment(**kwargs: Any) -> dict[str, Any]:
            append_staleness_event(
                kwargs["session_dir"] / "14-STALENESS.jsonl", staleness_row
            )
            return staleness_row

        monkeypatch.setattr(
            thread_revalidation_module,
            "run_staleness_experiment",
            _fake_run_staleness_experiment,
        )

        exit_code = thread_revalidation_main(
            [
                "staleness",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--alias",
                "mini-1",
                "--disconnect-ns",
                "0",
            ]
        )
        assert exit_code == 0

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "staleness"
        assert result["ok"] is True
        assert result["reason"] is None
        assert result["alias"] == "mini-1"
        assert result["disposition"] == "confirmed_expiry"
        assert result["first_absence_poll"] == 2
        assert result["confirmed_expiry_poll"] == 4


def _write_executable_script(path: Path, body: str) -> Path:
    """Write a script the host OS can actually execute as argv[0].

    Windows has no shebang support, so a `#!/bin/sh` file handed to
    subprocess raises WinError 193 rather than running. Writing a `.cmd`
    there keeps these tests exercising the real `_run_power_script` path on
    both platforms instead of skipping the one where an operator is most
    likely to supply something the OS refuses to run.
    """
    if sys.platform == "win32":
        cmd = path.with_suffix(".cmd")
        cmd.write_text(f"@echo off\n{_as_cmd(body)}\n", encoding="utf-8")
        return cmd
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _as_cmd(body: str) -> str:
    """Translate the small shell vocabulary these tests use into cmd.exe.

    Pattern-matched rather than looked up in a table, so a test that adds a
    new line cannot silently fall through untranslated and pass on Windows
    for the wrong reason. Anything outside the vocabulary raises here
    instead, which is how the `touch` marker line was caught rather than
    quietly skipped.
    """
    return "\n".join(_as_cmd_line(line) for line in body.splitlines())


def _as_cmd_line(line: str) -> str:
    if match := re.fullmatch(r"exit (\d+)", line):
        return f"exit /b {match.group(1)}"
    if match := re.fullmatch(r"sleep (\d+)", line):
        # ping's count is one more than the seconds it waits.
        return f"ping -n {int(match.group(1)) + 1} 127.0.0.1 >nul"
    if match := re.fullmatch(r"touch (.+)", line):
        # `type nul >` is cmd.exe's create-empty-file; quoted because a
        # Windows temp path routinely contains spaces.
        return f'type nul > "{match.group(1)}"'
    if match := re.fullmatch(r"echo (.+)", line):
        return f"echo {match.group(1)}"
    raise AssertionError(f"no cmd.exe translation for shell line: {line!r}")


class _RestorationDiscoverStub:
    """Mimics ``discover(timeout=...)``/``discover_mdns(timeout=...)``.

    Reports the device present starting from its ``present_from_call``-th
    invocation -- used to hermetically prove the CLI's unbounded
    restoration-wait loop actually polls more than once before succeeding,
    with no real socket or device involved.
    """

    def __init__(self, serial: str, *, present_from_call: int) -> None:
        self._serial = serial
        self._present_from_call = present_from_call
        self.calls = 0

    def __call__(self, timeout: float = 0.0) -> _RestorationDiscoverStub:
        self.calls += 1
        return self

    def __aiter__(self) -> Any:
        return self._iter()

    async def _iter(self) -> Any:
        if self.calls >= self._present_from_call:
            yield _StubDevice(self._serial)


class TestRunPowerScript:
    """T-14-06 change 1: direct argv-list execution, never a shell."""

    def test_rejects_a_missing_script(self, tmp_path: Path) -> None:
        with pytest.raises(PowerScriptError) as exc_info:
            _run_power_script(tmp_path / "does-not-exist.sh", stage="off")
        assert exc_info.value.reason == "missing_or_not_executable"
        assert exc_info.value.stage == "off"

    def test_rejects_a_non_executable_script(self, tmp_path: Path) -> None:
        """Unrunnable is a PowerScriptError on both platforms, by two routes.

        POSIX catches it up front: os.access(X_OK) is false on a file that
        was never chmod'd, so nothing is ever spawned. Windows cannot -- it
        reports every existing file as executable -- so the refusal comes
        from the OS instead, as WinError 193 on a shebang script it has no
        way to run. Both must surface as the same hard stop rather than a
        raw OSError escaping a verb that promises one JSON object.
        """
        script = tmp_path / "script.sh"
        script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        # Deliberately not chmod'd executable.
        with pytest.raises(PowerScriptError) as exc_info:
            _run_power_script(script, stage="on")
        assert exc_info.value.reason in {"missing_or_not_executable", "not_executable"}

    def test_rejects_a_nonzero_exit(self, tmp_path: Path) -> None:
        script = _write_executable_script(tmp_path / "script.sh", "exit 3")
        with pytest.raises(PowerScriptError) as exc_info:
            _run_power_script(script, stage="off")
        assert exc_info.value.reason == "exit_code_3"

    def test_rejects_a_timeout(self, tmp_path: Path) -> None:
        script = _write_executable_script(tmp_path / "script.sh", "sleep 5")
        with pytest.raises(PowerScriptError) as exc_info:
            _run_power_script(script, stage="on", timeout_s=0.2)
        assert exc_info.value.reason == "timeout"

    def test_succeeds_silently_on_exit_zero(self, tmp_path: Path) -> None:
        script = _write_executable_script(tmp_path / "script.sh", "exit 0")
        _run_power_script(script, stage="off")  # must not raise

    def test_never_invokes_a_shell_and_passes_an_argv_list(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        script = _write_executable_script(tmp_path / "script.sh", "exit 0")
        captured: dict[str, Any] = {}
        real_run = subprocess.run

        def _spy(argv: Any, **kwargs: Any) -> Any:
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            return real_run(argv, **kwargs)

        monkeypatch.setattr(thread_revalidation_module.subprocess, "run", _spy)
        _run_power_script(script, stage="off")

        assert captured["argv"] == [str(script)]
        assert isinstance(captured["argv"], list)
        assert captured["kwargs"].get("shell", False) is False
        assert captured["kwargs"]["capture_output"] is True

    def test_a_chatty_script_never_pollutes_this_process_stdout(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        script = _write_executable_script(
            tmp_path / "script.sh", 'echo "not part of the JSON verdict"'
        )
        _run_power_script(script, stage="off")
        assert capsys.readouterr().out == ""


class TestCliStalenessPowerScripts:
    """T-14-06 changes 1-3: operator-supplied power-off/power-on scripts
    drive the physical power cycle, restoration polling is unbounded, and
    progress goes to stderr while stdout carries exactly one JSON object."""

    @staticmethod
    def _session(tmp_path: Path) -> tuple[Path, dict[str, Any], Path]:
        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        alias_map_path = tmp_path / "alias-map.json"
        alias_map_path.write_text(
            json.dumps({"d073d5000005": "mini-1"}), encoding="utf-8"
        )
        return session_dir, manifest, alias_map_path

    def test_power_off_and_power_on_must_be_supplied_together(
        self, tmp_path: Path
    ) -> None:
        session_dir, _manifest, alias_map_path = self._session(tmp_path)
        power_off = _write_executable_script(tmp_path / "off.sh", "exit 0")

        with pytest.raises(SystemExit) as exc_info:
            thread_revalidation_main(
                [
                    "staleness",
                    "--session-dir",
                    str(session_dir),
                    "--alias-map",
                    str(alias_map_path),
                    "--alias",
                    "mini-1",
                    "--power-off",
                    str(power_off),
                ]
            )
        assert exc_info.value.code == 2

    def test_power_on_alone_is_rejected(self, tmp_path: Path) -> None:
        session_dir, _manifest, alias_map_path = self._session(tmp_path)
        power_on = _write_executable_script(tmp_path / "on.sh", "exit 0")

        with pytest.raises(SystemExit) as exc_info:
            thread_revalidation_main(
                [
                    "staleness",
                    "--session-dir",
                    str(session_dir),
                    "--alias-map",
                    str(alias_map_path),
                    "--alias",
                    "mini-1",
                    "--disconnect-ns",
                    "0",
                    "--power-on",
                    str(power_on),
                ]
            )
        assert exc_info.value.code == 2

    def test_disconnect_ns_is_mutually_exclusive_with_power_off(
        self, tmp_path: Path
    ) -> None:
        session_dir, _manifest, alias_map_path = self._session(tmp_path)
        power_off = _write_executable_script(tmp_path / "off.sh", "exit 0")
        power_on = _write_executable_script(tmp_path / "on.sh", "exit 0")

        with pytest.raises(SystemExit) as exc_info:
            thread_revalidation_main(
                [
                    "staleness",
                    "--session-dir",
                    str(session_dir),
                    "--alias-map",
                    str(alias_map_path),
                    "--alias",
                    "mini-1",
                    "--disconnect-ns",
                    "0",
                    "--power-off",
                    str(power_off),
                    "--power-on",
                    str(power_on),
                ]
            )
        assert exc_info.value.code == 2

    def test_neither_disconnect_ns_nor_power_scripts_is_rejected(
        self, tmp_path: Path
    ) -> None:
        session_dir, _manifest, alias_map_path = self._session(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            thread_revalidation_main(
                [
                    "staleness",
                    "--session-dir",
                    str(session_dir),
                    "--alias-map",
                    str(alias_map_path),
                    "--alias",
                    "mini-1",
                ]
            )
        assert exc_info.value.code == 2

    def test_power_off_failure_is_a_hard_stop_and_mutates_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir, _manifest, alias_map_path = self._session(tmp_path)
        power_off = _write_executable_script(tmp_path / "off.sh", "exit 9")
        power_on = _write_executable_script(tmp_path / "on.sh", "exit 0")

        experiment_started = False

        async def _fake_run_staleness_experiment(**kwargs: Any) -> dict[str, Any]:
            nonlocal experiment_started
            experiment_started = True  # pragma: no cover
            raise AssertionError("must never be called after power-off fails")

        monkeypatch.setattr(
            thread_revalidation_module,
            "run_staleness_experiment",
            _fake_run_staleness_experiment,
        )

        exit_code = thread_revalidation_main(
            [
                "staleness",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--alias",
                "mini-1",
                "--power-off",
                str(power_off),
                "--power-on",
                str(power_on),
            ]
        )
        assert exit_code == 1
        assert experiment_started is False
        assert not (session_dir / "14-STALENESS.jsonl").exists()

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["command"] == "staleness"
        assert result["ok"] is False
        assert result["reason"] == "power_off_failed"
        assert result["detail"] == "exit_code_9"
        assert "nothing was mutated" in result["message"]
        assert f"power off: {power_off}" in captured.err
        assert "FAILED" in captured.err

    def test_power_on_failure_persists_the_row_and_says_the_device_is_dark(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir, manifest, alias_map_path = self._session(tmp_path)
        power_off = _write_executable_script(tmp_path / "off.sh", "exit 0")
        power_on = _write_executable_script(tmp_path / "on.sh", "exit 5")

        async def _fake_run_staleness_experiment(**kwargs: Any) -> dict[str, Any]:
            restore_result = await kwargs["restore_available"]()
            assert restore_result is None
            row = build_staleness_event(
                **_staleness_kwargs(
                    session_id=manifest["session_id"],
                    revision=manifest["revision"],
                    alias="mini-1",
                    disconnect_ns=kwargs["disconnect_ns"],
                    restored_available_ns=None,
                    restoration_duration_s=None,
                    provenance="physical",
                )
            )
            append_staleness_event(kwargs["session_dir"] / "14-STALENESS.jsonl", row)
            return row

        monkeypatch.setattr(
            thread_revalidation_module,
            "run_staleness_experiment",
            _fake_run_staleness_experiment,
        )

        exit_code = thread_revalidation_main(
            [
                "staleness",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--alias",
                "mini-1",
                "--power-off",
                str(power_off),
                "--power-on",
                str(power_on),
            ]
        )
        assert exit_code == 1

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["command"] == "staleness"
        assert result["ok"] is False
        assert result["reason"] == "power_on_failed"
        assert result["restoration_duration_s"] is None
        assert "physically powered off" in result["message"]
        assert "DARK" in captured.err
        assert f"power on: {power_on}" in captured.err
        assert "FAILED" in captured.err

        rows = reload_staleness_events(session_dir / "14-STALENESS.jsonl")
        assert len(rows) == 1
        assert rows[0]["restored_available_ns"] is None
        assert rows[0]["restoration_duration_s"] is None

    def test_power_off_captures_disconnect_and_power_on_polls_unbounded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        import lifx.api as lifx_api_module
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir, manifest, alias_map_path = self._session(tmp_path)
        power_off = _write_executable_script(tmp_path / "off.sh", "exit 0")
        power_on = _write_executable_script(tmp_path / "on.sh", "exit 0")

        # The device is reported present starting on the SECOND restoration
        # poll -- proving the wait loop genuinely has no deadline and keeps
        # polling rather than succeeding trivially on the first attempt.
        discover_stub = _RestorationDiscoverStub("d073d5000005", present_from_call=2)
        mdns_stub = _RestorationDiscoverStub("d073d5000005", present_from_call=2)
        monkeypatch.setattr(lifx_api_module, "discover", discover_stub)
        monkeypatch.setattr(lifx_api_module, "discover_mdns", mdns_stub)

        captured_disconnect_ns: list[int] = []

        async def _fake_run_staleness_experiment(**kwargs: Any) -> dict[str, Any]:
            captured_disconnect_ns.append(kwargs["disconnect_ns"])
            restore_result = await kwargs["restore_available"]()
            assert restore_result is not None
            restored_ns, duration_s = restore_result
            row = build_staleness_event(
                **_staleness_kwargs(
                    session_id=manifest["session_id"],
                    revision=manifest["revision"],
                    alias="mini-1",
                    disconnect_ns=kwargs["disconnect_ns"],
                    restored_available_ns=restored_ns,
                    restoration_duration_s=duration_s,
                    provenance="physical",
                )
            )
            append_staleness_event(kwargs["session_dir"] / "14-STALENESS.jsonl", row)
            return row

        monkeypatch.setattr(
            thread_revalidation_module,
            "run_staleness_experiment",
            _fake_run_staleness_experiment,
        )

        before_ns = time.monotonic_ns()
        exit_code = thread_revalidation_main(
            [
                "staleness",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--alias",
                "mini-1",
                "--power-off",
                str(power_off),
                "--power-on",
                str(power_on),
            ]
        )
        after_ns = time.monotonic_ns()
        assert exit_code == 0

        assert len(captured_disconnect_ns) == 1
        assert before_ns <= captured_disconnect_ns[0] <= after_ns

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["ok"] is True
        assert result["restoration_duration_s"] is not None
        assert result["restoration_duration_s"] >= 0

        assert f"power off: {power_off}" in captured.err
        assert "disconnect captured" in captured.err
        assert f"power on: {power_on}" in captured.err
        assert "polling for restoration" in captured.err
        assert "waiting for restoration" in captured.err
        assert "restored after" in captured.err
        # discover_stub only reports present from its 2nd call, so at least
        # one "waiting" poll must have happened before the eventual success.
        assert discover_stub.calls >= 2
        assert mdns_stub.calls >= 2

    def test_already_recorded_alias_never_runs_power_off(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        """A same-alias resume must never cut power on an already-measured
        device (Rule 2: missing critical functionality otherwise)."""
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir, manifest, alias_map_path = self._session(tmp_path)
        existing = build_staleness_event(
            **_staleness_kwargs(
                session_id=manifest["session_id"],
                revision=manifest["revision"],
                alias="mini-1",
                provenance="physical",
            )
        )
        append_staleness_event(session_dir / "14-STALENESS.jsonl", existing)

        power_off_ran = tmp_path / "off-ran.marker"
        power_off = _write_executable_script(
            tmp_path / "off.sh", f"touch {power_off_ran}\nexit 0"
        )
        power_on = _write_executable_script(tmp_path / "on.sh", "exit 0")

        experiment_called = False

        async def _fake_run_staleness_experiment(**kwargs: Any) -> dict[str, Any]:
            nonlocal experiment_called
            experiment_called = True  # pragma: no cover
            raise AssertionError("must never be called for an already-recorded alias")

        monkeypatch.setattr(
            thread_revalidation_module,
            "run_staleness_experiment",
            _fake_run_staleness_experiment,
        )

        exit_code = thread_revalidation_main(
            [
                "staleness",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--alias",
                "mini-1",
                "--power-off",
                str(power_off),
                "--power-on",
                str(power_on),
            ]
        )
        assert exit_code == 0
        assert experiment_called is False
        assert not power_off_ran.exists()

        result = json.loads(capsys.readouterr().out)
        assert result["ok"] is True
        assert result["disposition"] == existing["disposition"]


class TestCliAllFlag:
    """`--all` iterates the frozen manifest inventory instead of one `--alias`.

    `request --all` and `animation --all` share the exact per-alias
    resolve/connect/run helper functions used by `--alias` -- these tests
    prove only the CLI-level orchestration difference (continue-through-
    failure versus halt-immediately), never a real socket or device.
    """

    @staticmethod
    def _alias_map_path(tmp_path: Path) -> Path:
        alias_map_path = tmp_path / "alias-map.json"
        alias_map_path.write_text(
            json.dumps(
                {
                    "d073d5000001": "mini-1",
                    "d073d5000002": "neon-1",
                    "d073d5000003": "ceiling-1",
                    "d073d5000004": "candle-1",
                    "d073d5000005": "tube-1",
                }
            ),
            encoding="utf-8",
        )
        return alias_map_path

    @pytest.mark.parametrize("subcommand", ["request", "animation"])
    def test_alias_and_all_are_mutually_exclusive(
        self, subcommand: str, tmp_path: Path
    ) -> None:
        session_dir = tmp_path / "session"
        init_manifest(session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER))
        alias_map_path = self._alias_map_path(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            thread_revalidation_main(
                [
                    subcommand,
                    "--session-dir",
                    str(session_dir),
                    "--alias-map",
                    str(alias_map_path),
                    "--alias",
                    "mini-1",
                    "--all",
                ]
            )
        assert exc_info.value.code == 2

    @pytest.mark.parametrize("subcommand", ["request", "animation"])
    def test_neither_alias_nor_all_is_rejected(
        self, subcommand: str, tmp_path: Path
    ) -> None:
        session_dir = tmp_path / "session"
        init_manifest(session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER))
        alias_map_path = self._alias_map_path(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            thread_revalidation_main(
                [
                    subcommand,
                    "--session-dir",
                    str(session_dir),
                    "--alias-map",
                    str(alias_map_path),
                ]
            )
        assert exc_info.value.code == 2

    def test_request_all_runs_every_inventory_alias_in_sorted_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        alias_map_path = self._alias_map_path(tmp_path)
        attempted: list[str] = []

        async def _fake_resolve_target_device(
            alias: str, alias_map: Any, **_: Any
        ) -> Any:
            return _StubConnectedDevice()

        async def _fake_run_request_trials(**kwargs: Any) -> None:
            alias = kwargs["alias"]
            attempted.append(alias)
            for row in _physical_request_rows(alias, manifest):
                append_request_trial_event(
                    kwargs["session_dir"] / "14-REQUESTS.jsonl", row
                )

        monkeypatch.setattr(
            thread_revalidation_module,
            "_resolve_target_device",
            _fake_resolve_target_device,
        )
        monkeypatch.setattr(
            thread_revalidation_module, "run_request_trials", _fake_run_request_trials
        )

        exit_code = thread_revalidation_main(
            [
                "request",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--all",
            ]
        )
        assert exit_code == 0
        sorted_aliases = sorted(expected_alias_roster(_FULL_ROSTER))
        assert attempted == sorted_aliases

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "request"
        assert result["ok"] is True
        assert result["reason"] is None
        assert result["aliases"] == sorted_aliases
        assert result["offending_aliases"] == []
        assert [entry["alias"] for entry in result["results"]] == sorted_aliases
        for entry in result["results"]:
            assert entry["trials_recorded"] == REQUEST_TRIALS
            assert entry["trials_expected"] == REQUEST_TRIALS
            assert entry["outcomes"] == {"completed": REQUEST_TRIALS}
            assert entry["error"] is None
            assert entry["outcomes"].get("power_out_of_range", 0) == 0

    def test_request_all_continues_past_power_out_of_range(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        alias_map_path = self._alias_map_path(tmp_path)
        attempted: list[str] = []

        async def _fake_resolve_target_device(
            alias: str, alias_map: Any, **_: Any
        ) -> Any:
            return _StubConnectedDevice()

        async def _fake_run_request_trials(**kwargs: Any) -> None:
            alias = kwargs["alias"]
            attempted.append(alias)
            journal_path = kwargs["session_dir"] / "14-REQUESTS.jsonl"
            if alias == "candle-1":
                for trial in range(1, REQUEST_TRIALS + 1):
                    append_request_trial_event(
                        journal_path,
                        build_request_trial_event(
                            session_id=manifest["session_id"],
                            protocol_version=manifest["protocol_version"],
                            revision=manifest["revision"],
                            alias=alias,
                            trial=trial,
                            outcome="power_out_of_range",
                            provenance="physical",
                        ),
                    )
            else:
                for row in _physical_request_rows(alias, manifest):
                    append_request_trial_event(journal_path, row)

        monkeypatch.setattr(
            thread_revalidation_module,
            "_resolve_target_device",
            _fake_resolve_target_device,
        )
        monkeypatch.setattr(
            thread_revalidation_module, "run_request_trials", _fake_run_request_trials
        )

        exit_code = thread_revalidation_main(
            [
                "request",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--all",
            ]
        )
        assert exit_code == 1
        sorted_aliases = sorted(expected_alias_roster(_FULL_ROSTER))
        # every alias was still attempted -- one bad alias never stops the rest
        assert attempted == sorted_aliases

        result = json.loads(capsys.readouterr().out)
        assert result["ok"] is False
        assert result["reason"] == "offending_aliases_present"
        assert result["offending_aliases"] == ["candle-1"]
        for entry in result["results"]:
            if entry["alias"] == "candle-1":
                assert entry["outcomes"] == {"power_out_of_range": REQUEST_TRIALS}
            else:
                assert entry["outcomes"].get("power_out_of_range", 0) == 0

    def test_request_all_continues_past_a_per_alias_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        alias_map_path = self._alias_map_path(tmp_path)
        attempted: list[str] = []

        async def _fake_resolve_target_device(
            alias: str, alias_map: Any, **_: Any
        ) -> Any:
            if alias == "mini-1":
                raise RuntimeError(
                    f"could not resolve expected alias to a live device: {alias!r}"
                )
            return _StubConnectedDevice()

        async def _fake_run_request_trials(**kwargs: Any) -> None:
            alias = kwargs["alias"]
            attempted.append(alias)
            for row in _physical_request_rows(alias, manifest):
                append_request_trial_event(
                    kwargs["session_dir"] / "14-REQUESTS.jsonl", row
                )

        monkeypatch.setattr(
            thread_revalidation_module,
            "_resolve_target_device",
            _fake_resolve_target_device,
        )
        monkeypatch.setattr(
            thread_revalidation_module, "run_request_trials", _fake_run_request_trials
        )

        exit_code = thread_revalidation_main(
            [
                "request",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--all",
            ]
        )
        assert exit_code == 1
        sorted_aliases = sorted(expected_alias_roster(_FULL_ROSTER))
        # "mini-1" itself never reaches run_request_trials (resolution failed)
        assert attempted == [alias for alias in sorted_aliases if alias != "mini-1"]

        result = json.loads(capsys.readouterr().out)
        assert result["ok"] is False
        assert result["offending_aliases"] == ["mini-1"]
        mini_entry = next(e for e in result["results"] if e["alias"] == "mini-1")
        assert mini_entry["trials_recorded"] == 0
        assert mini_entry["outcomes"] == {}
        assert mini_entry["error"] == "RuntimeError"

    def test_request_all_is_safely_rerunnable_after_interruption(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        """A previously fully journaled alias is not re-mutated on rerun.

        Per-trial resumability itself is `run_request_trials`' own
        responsibility (exercised directly in ``TestRunRequestTrials``);
        this wiring test proves ``--all`` does not bypass or duplicate it.
        """
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        alias_map_path = self._alias_map_path(tmp_path)

        # Simulate an interrupted prior --all run: one alias already has its
        # complete, already-journaled series.
        for row in _physical_request_rows("candle-1", manifest):
            append_request_trial_event(session_dir / "14-REQUESTS.jsonl", row)

        attempted: list[str] = []

        async def _fake_resolve_target_device(
            alias: str, alias_map: Any, **_: Any
        ) -> Any:
            return _StubConnectedDevice()

        async def _fake_run_request_trials(**kwargs: Any) -> None:
            alias = kwargs["alias"]
            attempted.append(alias)
            journal_path = kwargs["session_dir"] / "14-REQUESTS.jsonl"
            existing = [
                row
                for row in reload_request_trial_events(journal_path)
                if row["alias"] == alias
            ]
            if len(existing) >= REQUEST_TRIALS:
                return  # already-recorded trial numbers are skipped (D-18)
            for row in _physical_request_rows(alias, manifest):
                append_request_trial_event(journal_path, row)

        monkeypatch.setattr(
            thread_revalidation_module,
            "_resolve_target_device",
            _fake_resolve_target_device,
        )
        monkeypatch.setattr(
            thread_revalidation_module, "run_request_trials", _fake_run_request_trials
        )

        exit_code = thread_revalidation_main(
            [
                "request",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--all",
            ]
        )
        assert exit_code == 0
        assert attempted == sorted(expected_alias_roster(_FULL_ROSTER))

        candle_rows = [
            row
            for row in reload_request_trial_events(session_dir / "14-REQUESTS.jsonl")
            if row["alias"] == "candle-1"
        ]
        assert len(candle_rows) == REQUEST_TRIALS  # not duplicated

        result = json.loads(capsys.readouterr().out)
        assert result["ok"] is True
        for entry in result["results"]:
            assert entry["trials_recorded"] == REQUEST_TRIALS

    def test_animation_all_runs_every_inventory_alias_in_sorted_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        alias_map_path = self._alias_map_path(tmp_path)
        attempted: list[str] = []

        async def _fake_resolve_target_device(
            alias: str, alias_map: Any, **_: Any
        ) -> Any:
            return _StubConnectedDevice()

        async def _fake_run_animation_observation(**kwargs: Any) -> dict[str, Any]:
            alias = kwargs["alias"]
            attempted.append(alias)
            row = _physical_animation_row(alias, manifest)
            append_animation_event(kwargs["session_dir"] / "14-ANIMATION.jsonl", row)
            return row

        monkeypatch.setattr(
            thread_revalidation_module,
            "_resolve_target_device",
            _fake_resolve_target_device,
        )
        monkeypatch.setattr(
            thread_revalidation_module,
            "run_animation_observation",
            _fake_run_animation_observation,
        )

        exit_code = thread_revalidation_main(
            [
                "animation",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--all",
            ]
        )
        assert exit_code == 0
        sorted_aliases = sorted(expected_alias_roster(_FULL_ROSTER))
        assert attempted == sorted_aliases

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "animation"
        assert result["ok"] is True
        assert result["reason"] is None
        assert result["aliases"] == sorted_aliases
        assert result["poisoned_alias"] is None
        assert result["not_attempted"] == []
        assert [entry["alias"] for entry in result["results"]] == sorted_aliases
        for entry in result["results"]:
            assert entry["restored"] is True
            assert entry["restoration_verified"] is True
            assert entry["error"] is None
            assert entry["rate_outcomes"] == ["completed", "completed", "completed"]

    def test_animation_all_halts_immediately_on_restoration_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        alias_map_path = self._alias_map_path(tmp_path)
        attempted: list[str] = []
        sorted_aliases = sorted(expected_alias_roster(_FULL_ROSTER))
        failing_alias = sorted_aliases[1]

        async def _fake_resolve_target_device(
            alias: str, alias_map: Any, **_: Any
        ) -> Any:
            return _StubConnectedDevice()

        async def _fake_run_animation_observation(**kwargs: Any) -> dict[str, Any]:
            alias = kwargs["alias"]
            attempted.append(alias)
            restored = alias != failing_alias
            row = dict(_physical_animation_row(alias, manifest))
            row["restored"] = restored
            row["restoration_verified"] = restored
            append_animation_event(kwargs["session_dir"] / "14-ANIMATION.jsonl", row)
            return row

        monkeypatch.setattr(
            thread_revalidation_module,
            "_resolve_target_device",
            _fake_resolve_target_device,
        )
        monkeypatch.setattr(
            thread_revalidation_module,
            "run_animation_observation",
            _fake_run_animation_observation,
        )

        exit_code = thread_revalidation_main(
            [
                "animation",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--all",
            ]
        )
        assert exit_code == 1
        # iteration halts the instant restoration fails -- the rest of the
        # roster is never touched
        assert attempted == sorted_aliases[:2]

        result = json.loads(capsys.readouterr().out)
        assert result["ok"] is False
        assert result["reason"] == "restoration_failed"
        assert result["poisoned_alias"] == failing_alias
        assert result["not_attempted"] == sorted_aliases[2:]
        assert [entry["alias"] for entry in result["results"]] == sorted_aliases[:2]
        failing_entry = result["results"][1]
        assert failing_entry["alias"] == failing_alias
        assert failing_entry["restored"] is False
        assert failing_entry["restoration_verified"] is False
        assert failing_entry["error"] is None

    def test_animation_all_halts_on_a_per_alias_error_without_attempting_the_next(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        alias_map_path = self._alias_map_path(tmp_path)
        attempted: list[str] = []
        sorted_aliases = sorted(expected_alias_roster(_FULL_ROSTER))
        failing_alias = sorted_aliases[2]

        async def _fake_resolve_target_device(
            alias: str, alias_map: Any, **_: Any
        ) -> Any:
            attempted.append(alias)
            if alias == failing_alias:
                raise RuntimeError(
                    f"could not resolve expected alias to a live device: {alias!r}"
                )
            return _StubConnectedDevice()

        async def _fake_run_animation_observation(**kwargs: Any) -> dict[str, Any]:
            alias = kwargs["alias"]
            row = _physical_animation_row(alias, manifest)
            append_animation_event(kwargs["session_dir"] / "14-ANIMATION.jsonl", row)
            return row

        monkeypatch.setattr(
            thread_revalidation_module,
            "_resolve_target_device",
            _fake_resolve_target_device,
        )
        monkeypatch.setattr(
            thread_revalidation_module,
            "run_animation_observation",
            _fake_run_animation_observation,
        )

        exit_code = thread_revalidation_main(
            [
                "animation",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--all",
            ]
        )
        assert exit_code == 1
        # the failing alias's resolve is attempted, but the NEXT alias never is
        assert attempted == sorted_aliases[:3]

        result = json.loads(capsys.readouterr().out)
        assert result["ok"] is False
        assert result["poisoned_alias"] == failing_alias
        assert result["not_attempted"] == sorted_aliases[3:]
        failing_entry = result["results"][-1]
        assert failing_entry["alias"] == failing_alias
        assert failing_entry["restored"] is False
        assert failing_entry["restoration_verified"] is False
        assert failing_entry["error"] == "RuntimeError"

    def test_animation_all_is_safely_rerunnable_after_interruption(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        """A previously journaled alias's animation row is left untouched on
        a re-run --all (its own alias-uniqueness resume, exercised directly
        in ``TestRunAnimationObservation``); this wiring test proves
        ``--all`` does not bypass or duplicate it.
        """
        import scripts.thread_revalidation as thread_revalidation_module

        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        alias_map_path = self._alias_map_path(tmp_path)

        existing_row = _physical_animation_row("candle-1", manifest)
        append_animation_event(session_dir / "14-ANIMATION.jsonl", existing_row)

        attempted: list[str] = []

        async def _fake_resolve_target_device(
            alias: str, alias_map: Any, **_: Any
        ) -> Any:
            return _StubConnectedDevice()

        async def _fake_run_animation_observation(**kwargs: Any) -> dict[str, Any]:
            alias = kwargs["alias"]
            attempted.append(alias)
            journal_path = kwargs["session_dir"] / "14-ANIMATION.jsonl"
            existing = [
                row
                for row in reload_animation_events(journal_path)
                if row["alias"] == alias
            ]
            if existing:
                return existing[0]  # already-recorded alias is a no-op (D-18)
            row = _physical_animation_row(alias, manifest)
            append_animation_event(journal_path, row)
            return row

        monkeypatch.setattr(
            thread_revalidation_module,
            "_resolve_target_device",
            _fake_resolve_target_device,
        )
        monkeypatch.setattr(
            thread_revalidation_module,
            "run_animation_observation",
            _fake_run_animation_observation,
        )

        exit_code = thread_revalidation_main(
            [
                "animation",
                "--session-dir",
                str(session_dir),
                "--alias-map",
                str(alias_map_path),
                "--all",
            ]
        )
        assert exit_code == 0
        assert attempted == sorted(expected_alias_roster(_FULL_ROSTER))

        candle_rows = [
            row
            for row in reload_animation_events(session_dir / "14-ANIMATION.jsonl")
            if row["alias"] == "candle-1"
        ]
        assert len(candle_rows) == 1  # not duplicated

        result = json.loads(capsys.readouterr().out)
        assert result["ok"] is True


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
class TestPosixEvidenceDir:
    """Git speaks forward slashes everywhere; the caller may not.

    On Windows an operator supplies a native path and `str(Path(...))`
    produces backslashes, but `git diff --cached --name-only` reports index
    paths with forward slashes on every platform. Comparing the two directly
    matched nothing, so all nine correctly-staged evidence files were
    reported `missing_evidence_path`. Normalising the caller's separators is
    what makes the comparison meaningful.
    """

    def test_backslash_paths_normalise_to_git_s_vocabulary(self) -> None:
        assert (
            _posix_evidence_dir(r".planning\phases\14-thread\14-EVIDENCE")
            == ".planning/phases/14-thread/14-EVIDENCE"
        )

    def test_forward_slash_paths_are_unchanged(self) -> None:
        assert (
            _posix_evidence_dir(".planning/phases/14-thread/14-EVIDENCE")
            == ".planning/phases/14-thread/14-EVIDENCE"
        )

    def test_a_trailing_separator_of_either_kind_is_stripped(self) -> None:
        assert _posix_evidence_dir("a/b/") == "a/b"
        assert _posix_evidence_dir("a\\b\\") == "a/b"


class TestValidateStagedEvidence:
    """D-19/T-14-11: the staged INDEX is authoritative, never the working tree."""

    def test_complete_staged_evidence_passes(self, tmp_path: Path) -> None:
        _init_bare_git_repo(tmp_path)
        manifest = _manifest_for_roster()
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        _stage_full_evidence(tmp_path, evidence_dir, manifest)

        with _chdir(tmp_path):
            failures = validate_staged_evidence(str(evidence_dir.relative_to(tmp_path)))

        assert failures == []

    def test_a_native_windows_style_dir_validates_identically(
        self, tmp_path: Path
    ) -> None:
        """Backslashes must normalise at EVERY site, not most of them.

        Runs on any platform: the point is that the argument's separators do
        not change the outcome, and a backslash string is what a Windows
        operator and `str(Path(...))` both produce there.

        The first fix normalised the expected-path set and the staged-path
        prefix but missed the blob-read construction, which rebuilt the path
        from the raw argument. Windows CI went from reporting all nine paths
        missing to reporting all nine blobs unreadable -- a different symptom
        with the same cause and no less broken. This asserts equality against
        the forward-slash result rather than merely asserting success, so a
        future site that forgets to normalise fails here too.
        """
        _init_bare_git_repo(tmp_path)
        manifest = _manifest_for_roster()
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        _stage_full_evidence(tmp_path, evidence_dir, manifest)
        relative = evidence_dir.relative_to(tmp_path).as_posix()

        with _chdir(tmp_path):
            forward = validate_staged_evidence(relative)
            backslash = validate_staged_evidence(relative.replace("/", "\\"))
            trailing = validate_staged_evidence(relative + "/")

        assert forward == []
        assert backslash == forward
        assert trailing == forward

    def test_unreadable_staged_blob_is_reported(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_bare_git_repo(tmp_path)
        manifest = _manifest_for_roster()
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        _stage_full_evidence(tmp_path, evidence_dir, manifest)

        import scripts.thread_revalidation as thread_revalidation_module

        original_read = thread_revalidation_module._read_staged_blob

        def _flaky_read(path: str) -> bytes:
            if path.endswith("14-REPORT.md"):
                raise subprocess.CalledProcessError(1, ["git", "show"])
            return original_read(path)

        monkeypatch.setattr(
            thread_revalidation_module, "_read_staged_blob", _flaky_read
        )

        with _chdir(tmp_path):
            failures = validate_staged_evidence(str(evidence_dir.relative_to(tmp_path)))

        assert any(f.category == "unreadable_staged_blob" for f in failures)

    def test_manifest_schema_failure_is_reported(self, tmp_path: Path) -> None:
        _init_bare_git_repo(tmp_path)
        manifest = _manifest_for_roster()
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        _stage_full_evidence(tmp_path, evidence_dir, manifest)
        (evidence_dir / "14-MANIFEST.json").write_text("not json", encoding="utf-8")
        subprocess.run(
            [
                "git",
                "add",
                str((evidence_dir / "14-MANIFEST.json").relative_to(tmp_path)),
            ],
            cwd=tmp_path,
            check=True,
        )

        with _chdir(tmp_path):
            failures = validate_staged_evidence(str(evidence_dir.relative_to(tmp_path)))

        assert len(failures) == 1
        assert failures[0].category == "schema_validation_failed"
        assert failures[0].path.endswith("14-MANIFEST.json")

    def test_incomplete_roster_in_a_fully_staged_manifest_is_reported(
        self, tmp_path: Path
    ) -> None:
        """Distinct from `missing_evidence_path`: all nine paths are present,
        but the staged manifest's OWN inventory is roster-incomplete."""
        _init_bare_git_repo(tmp_path)
        incomplete_manifest = build_manifest(**_manifest_kwargs())
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        _stage_full_evidence(tmp_path, evidence_dir, incomplete_manifest)

        with _chdir(tmp_path):
            failures = validate_staged_evidence(str(evidence_dir.relative_to(tmp_path)))

        assert any(f.category == "incomplete_expected_roster" for f in failures)

    def test_invalid_json_in_a_staged_product_is_reported(self, tmp_path: Path) -> None:
        _init_bare_git_repo(tmp_path)
        manifest = _manifest_for_roster()
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        _stage_full_evidence(tmp_path, evidence_dir, manifest)
        (evidence_dir / "14-SUMMARY.json").write_text("not json", encoding="utf-8")
        subprocess.run(
            [
                "git",
                "add",
                str((evidence_dir / "14-SUMMARY.json").relative_to(tmp_path)),
            ],
            cwd=tmp_path,
            check=True,
        )

        with _chdir(tmp_path):
            failures = validate_staged_evidence(str(evidence_dir.relative_to(tmp_path)))

        assert len(failures) == 1
        assert failures[0].category == "schema_validation_failed"
        assert failures[0].path.endswith("14-SUMMARY.json")

    def test_tampered_products_are_reported_as_not_regenerated(
        self, tmp_path: Path
    ) -> None:
        """All three generated products (summary/ledger/report) mismatching
        their journals-derived recomputation are each independently caught."""
        _init_bare_git_repo(tmp_path)
        manifest = _manifest_for_roster()
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        _stage_full_evidence(tmp_path, evidence_dir, manifest)
        (evidence_dir / "14-SUMMARY.json").write_text(
            json.dumps(
                {"schema_version": 1, "kind": "session_summary", "tampered": True}
            ),
            encoding="utf-8",
        )
        (evidence_dir / "14-CLASS-LEDGER.json").write_text(
            json.dumps({"schema_version": 1, "kind": "class_ledger", "tampered": True}),
            encoding="utf-8",
        )
        (evidence_dir / "14-REPORT.md").write_text(
            "tampered report\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "add", str(evidence_dir.relative_to(tmp_path))],
            cwd=tmp_path,
            check=True,
        )

        with _chdir(tmp_path):
            failures = validate_staged_evidence(str(evidence_dir.relative_to(tmp_path)))

        categories = {f.category for f in failures}
        assert "summary_not_regenerated_from_journals" in categories
        assert "class_ledger_not_regenerated_from_journals" in categories
        assert "report_not_regenerated_from_journals" in categories

    def test_missing_evidence_path_is_reported(self, tmp_path: Path) -> None:
        _init_bare_git_repo(tmp_path)
        manifest = _manifest_for_roster()
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        _stage_full_evidence(tmp_path, evidence_dir, manifest)
        subprocess.run(
            [
                "git",
                "rm",
                "--cached",
                "-q",
                str((evidence_dir / "14-REPORT.md").relative_to(tmp_path)),
            ],
            cwd=tmp_path,
            check=True,
        )

        with _chdir(tmp_path):
            failures = validate_staged_evidence(str(evidence_dir.relative_to(tmp_path)))

        assert any(f.category == "missing_evidence_path" for f in failures)

    def test_unexpected_extra_staged_path_is_reported(self, tmp_path: Path) -> None:
        _init_bare_git_repo(tmp_path)
        manifest = _manifest_for_roster()
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        _stage_full_evidence(tmp_path, evidence_dir, manifest)
        (evidence_dir / "extra.txt").write_text("nope", encoding="utf-8")
        subprocess.run(
            ["git", "add", str((evidence_dir / "extra.txt").relative_to(tmp_path))],
            cwd=tmp_path,
            check=True,
        )

        with _chdir(tmp_path):
            failures = validate_staged_evidence(str(evidence_dir.relative_to(tmp_path)))

        assert any(f.category == "unexpected_staged_path" for f in failures)

    def test_worktree_edit_after_staging_does_not_affect_the_check(
        self, tmp_path: Path
    ) -> None:
        _init_bare_git_repo(tmp_path)
        manifest = _manifest_for_roster()
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        _stage_full_evidence(tmp_path, evidence_dir, manifest)
        # Mutate the WORKING TREE after staging -- the index must be unaffected.
        (evidence_dir / "14-REPORT.md").write_text("corrupted", encoding="utf-8")

        with _chdir(tmp_path):
            failures = validate_staged_evidence(str(evidence_dir.relative_to(tmp_path)))

        assert failures == []

    def test_incomplete_ledger_is_reported_without_the_gap_closures(
        self, tmp_path: Path
    ) -> None:
        _init_bare_git_repo(tmp_path)
        manifest = _manifest_for_roster()
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "14-MANIFEST.json").write_text(
            json.dumps(manifest, sort_keys=True), encoding="utf-8"
        )
        for name in (
            "14-DISCOVERY.jsonl",
            "14-REQUESTS.jsonl",
            "14-ANIMATION.jsonl",
            "14-STALENESS.jsonl",
            "14-CLOSURE.jsonl",
        ):
            (evidence_dir / name).write_text("", encoding="utf-8")
        summary = generate_summary(
            discovery_rows=[],
            request_rows=[],
            animation_rows=[],
            staleness_rows=[],
            closure_rows=[],
        )
        summary["class_ledger"] = derive_class_ledger_from_roster(
            inventory=manifest["inventory"],
            discovery_rows=[],
            request_rows=[],
            closure_rows=[],
        )
        (evidence_dir / "14-SUMMARY.json").write_text(
            json.dumps(summary, sort_keys=True), encoding="utf-8"
        )
        (evidence_dir / "14-CLASS-LEDGER.json").write_text(
            json.dumps(summary["class_ledger"], sort_keys=True), encoding="utf-8"
        )
        (evidence_dir / "14-REPORT.md").write_text(
            generate_report(summary), encoding="utf-8"
        )
        subprocess.run(
            ["git", "add", str(evidence_dir.relative_to(tmp_path))],
            cwd=tmp_path,
            check=True,
        )

        with _chdir(tmp_path):
            failures = validate_staged_evidence(str(evidence_dir.relative_to(tmp_path)))

        assert any(f.category == "six_class_ledger_incomplete" for f in failures)

    def test_private_sentinel_never_appears_in_a_failure(self, tmp_path: Path) -> None:
        """A raw-looking value in a rejected row must never reach a failure message."""
        _init_bare_git_repo(tmp_path)
        manifest = _manifest_for_roster()
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "14-MANIFEST.json").write_text(
            json.dumps(manifest, sort_keys=True), encoding="utf-8"
        )
        private_sentinel = "192.168.77.201"
        # A malformed discovery row carrying a raw-looking value as an alias.
        bad_row = {
            "schema_version": 1,
            "kind": "discovery_round_event",
            "session_id": manifest["session_id"],
            "protocol_version": manifest["protocol_version"],
            "revision": manifest["revision"],
            "round": 1,
            "source": "discover",
            "call_order": 1,
            "outcome": "success",
            "devices": [private_sentinel],
            "provenance": "physical",
            "confounders": [],
        }
        (evidence_dir / "14-DISCOVERY.jsonl").write_text(
            json.dumps(bad_row) + "\n", encoding="utf-8"
        )
        for name in (
            "14-REQUESTS.jsonl",
            "14-ANIMATION.jsonl",
            "14-STALENESS.jsonl",
            "14-CLOSURE.jsonl",
        ):
            (evidence_dir / name).write_text("", encoding="utf-8")
        (evidence_dir / "14-SUMMARY.json").write_text("{}", encoding="utf-8")
        (evidence_dir / "14-CLASS-LEDGER.json").write_text("{}", encoding="utf-8")
        (evidence_dir / "14-REPORT.md").write_text("", encoding="utf-8")
        subprocess.run(
            ["git", "add", str(evidence_dir.relative_to(tmp_path))],
            cwd=tmp_path,
            check=True,
        )

        with _chdir(tmp_path):
            failures = validate_staged_evidence(str(evidence_dir.relative_to(tmp_path)))

        assert failures  # something failed
        for failure in failures:
            assert private_sentinel not in failure.path
            assert private_sentinel not in failure.category


@contextmanager
def _chdir(path: Path) -> Any:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class TestCliGenerateAndValidateStaged:
    """Smoke-level CLI coverage for the new `generate`/`validate-staged` modes."""

    def test_generate_writes_nothing_when_the_ledger_is_incomplete(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        """Generation is atomic (Defect 3): a roster-complete session with no
        observed evidence yet still has an incomplete ledger, and `generate`
        must leave the evidence directory exactly as it found it. Defect 2:
        the incompleteness is stated explicitly as JSON, not merely implied
        by the exit code."""
        session_dir = tmp_path / "session"
        init_manifest(session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER))
        exit_code = thread_revalidation_main(
            ["generate", "--session-dir", str(session_dir)]
        )
        assert exit_code == 1
        assert not (session_dir / "14-SUMMARY.json").exists()
        assert not (session_dir / "14-CLASS-LEDGER.json").exists()
        assert not (session_dir / "14-REPORT.md").exists()

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "generate"
        assert result["ok"] is False
        assert result["reason"] == "class_ledger_incomplete"
        assert set(result["missing_classes"]) == {
            "CeilingLight",
            "HevLight",
            "InfraredLight",
            "Light",
            "MatrixLight",
            "MultiZoneLight",
        }

    def test_generate_writes_products_when_the_ledger_is_complete(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        session_dir = tmp_path / "session"
        manifest = init_manifest(
            session_dir, **_manifest_kwargs(inventory=_FULL_ROSTER)
        )
        # One discovery round/source row lists every alias -- discovery is
        # unique per (session, source, round), not per alias.
        append_discovery_event(
            session_dir / "14-DISCOVERY.jsonl",
            build_discovery_event(
                session_id=manifest["session_id"],
                protocol_version=manifest["protocol_version"],
                revision=manifest["revision"],
                round_number=1,
                source="discover",
                outcome="success",
                devices=sorted(expected_alias_roster(_FULL_ROSTER)),
                provenance="physical",
            ),
        )
        for alias in expected_alias_roster(_FULL_ROSTER):
            for row in _physical_request_rows(alias, manifest):
                append_request_trial_event(session_dir / "14-REQUESTS.jsonl", row)
            append_animation_event(
                session_dir / "14-ANIMATION.jsonl",
                _physical_animation_row(alias, manifest),
            )
        for device_class in ("InfraredLight", "HevLight"):
            append_closure_event(
                session_dir / "14-CLOSURE.jsonl",
                build_closure_event(
                    **_closure_kwargs(
                        session_id=manifest["session_id"],
                        revision=manifest["revision"],
                        device_class=device_class,
                        disposition="named_gap",
                        aliases=[],
                        gap_reason="no Thread-capable fleet hardware",
                        gap_recorded_date="2026-08-31",
                        provenance=None,
                    )
                ),
            )

        exit_code = thread_revalidation_main(
            ["generate", "--session-dir", str(session_dir)]
        )

        assert exit_code == 0
        assert (session_dir / "14-SUMMARY.json").exists()
        ledger = json.loads((session_dir / "14-CLASS-LEDGER.json").read_text())
        assert ledger["complete"] is True
        assert (session_dir / "14-REPORT.md").exists()

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "generate"
        assert result["ok"] is True
        assert result["reason"] is None
        assert result["missing_classes"] == []
        assert set(result["classes"]) == {
            "CeilingLight",
            "HevLight",
            "InfraredLight",
            "Light",
            "MatrixLight",
            "MultiZoneLight",
        }

    def test_generate_rejects_an_incomplete_roster(self, tmp_path: Path) -> None:
        session_dir = tmp_path / "session"
        init_manifest(session_dir, **_manifest_kwargs())  # only 2 inventory entries
        with pytest.raises(SystemExit):
            thread_revalidation_main(["generate", "--session-dir", str(session_dir)])
        assert not (session_dir / "14-SUMMARY.json").exists()

    @pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
    def test_validate_staged_cli_reports_missing_paths(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        _init_bare_git_repo(tmp_path)
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "14-MANIFEST.json").write_text("{}", encoding="utf-8")
        subprocess.run(
            ["git", "add", str(evidence_dir.relative_to(tmp_path))],
            cwd=tmp_path,
            check=True,
        )
        with _chdir(tmp_path):
            exit_code = thread_revalidation_main(
                [
                    "validate-staged",
                    "--evidence-dir",
                    str(evidence_dir.relative_to(tmp_path)),
                ]
            )
        assert exit_code == 1

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "validate-staged"
        assert result["ok"] is False
        assert result["reason"] == "staged_evidence_invalid"
        assert result["failures"]
        assert all(
            set(failure) == {"path", "category"} for failure in result["failures"]
        )

    @pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
    def test_validate_staged_cli_reports_success(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        _init_bare_git_repo(tmp_path)
        manifest = _manifest_for_roster()
        evidence_dir = tmp_path / "evidence" / "session-alpha"
        _stage_full_evidence(tmp_path, evidence_dir, manifest)

        with _chdir(tmp_path):
            exit_code = thread_revalidation_main(
                [
                    "validate-staged",
                    "--evidence-dir",
                    str(evidence_dir.relative_to(tmp_path)),
                ]
            )
        assert exit_code == 0

        result = json.loads(capsys.readouterr().out)
        assert result["command"] == "validate-staged"
        assert result["ok"] is True
        assert result["reason"] is None
        assert result["failures"] == []
