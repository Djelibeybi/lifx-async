"""Phase 14 THREAD-02 request-observation tracer: production send to validated JSONL.

Traces one real production ``DeviceConnection`` request end to end through
``scripts.measurement_support``'s private observer seam, validates each
observed event against a closed privacy-safe schema, appends it as one JSONL
row, and reloads + deterministically re-derives the same logical completion
latency and winning-sequence acknowledgement RTT from the appended journal
(D-07).

This module is production-quality skeleton code, not a throwaway path: Plan
14-02 extends it with the complete session manifest and discovery/animation
journal schema (D-18/D-20). Plan 14-01 owns only the request-event
validate/append/reload/derive primitives and one end-to-end proof that they
survive a real retransmitted acknowledgement.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess  # nosec B404
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from lifx.animation.animator import AnimatorStats
from lifx.const import DISCOVERY_TIMEOUT, REQUEST_RETRANSMIT_GAPS
from lifx.devices.light import Light
from lifx.exceptions import (
    LifxConnectionError,
    LifxError,
    LifxNetworkError,
    LifxProtocolError,
    LifxTimeoutError,
)
from lifx.network.connection import DeviceConnection
from lifx.protocol.models import Serial
from scripts.measurement_support import (
    ANIMATION_SCHEDULE,
    DISCOVERY_ROUNDS,
    REQUEST_TRIALS,
    STALENESS_CAP_S,
    STALENESS_CONFIRM_ABSENT_POLLS,
    STALENESS_POLL_INTERVAL_S,
    CapturedState,
    RestoreOutcome,
    _capture_request_observations,
    _RequestObservation,
    _RequestObservationSink,
    append_jsonl,
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

_SCHEMA_VERSION = 1
_KIND = "request_observation_event"
_CATEGORIES: frozenset[str] = frozenset(
    {
        "logical_start",
        "sent",
        "accepted",
        "timeout",
        "send_error",
        "cancelled",
        "cleanup",
    }
)
_ROW_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "kind",
        "session_id",
        "category",
        "sequence",
        "timestamp_ns",
        "thread_connection",
    }
)
# Alias-shaped only: alphanumeric plus hyphen/underscore, never a raw serial
# or address. Mirrors the alias-safety pattern used by
# scripts/measure_merged_discovery.py's _validate_alias().
_SESSION_ID_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
# Rejects an alias-shaped string that is ALSO serial-shaped (all-hex, colon-
# or hyphen-separated MAC form, or bare 12-digit hex) -- an identifier must
# never be usable as a session_id (T-14-02).
_SERIAL_PATTERN = re.compile(
    r"(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\Z|[0-9a-fA-F]{12}\Z"
)
_SEQUENCE_MAX = 255  # protocol sequence number is uint8


def _validate_request_event(record: Mapping[str, Any]) -> None:
    """Raise ``ValueError`` if ``record`` is not a well-formed, privacy-safe row.

    Validation is closed: an unrecognised key is rejected outright rather
    than checked against a forbidden-value denylist, so a field added later
    that happens to carry identity content cannot silently slip through
    (T-14-02).
    """
    record_keys = set(record.keys())
    if record_keys != _ROW_KEYS:
        raise ValueError(
            f"request event has unexpected keys: {record_keys ^ _ROW_KEYS}"
        )
    if record.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("request event has wrong schema_version")
    if record.get("kind") != _KIND:
        raise ValueError("request event has wrong kind")

    session_id = record.get("session_id")
    if (
        not isinstance(session_id, str)
        or _SESSION_ID_PATTERN.fullmatch(session_id) is None
    ):
        raise ValueError("request event has an invalid privacy-safe session_id")
    if _SERIAL_PATTERN.fullmatch(session_id) is not None:
        raise ValueError("identifier-shaped session_id is forbidden")

    category = record.get("category")
    if category not in _CATEGORIES:
        raise ValueError(f"request event has unknown category: {category!r}")

    sequence = record.get("sequence")
    if sequence is not None and (
        isinstance(sequence, bool)
        or not isinstance(sequence, int)
        or not (0 <= sequence <= _SEQUENCE_MAX)
    ):
        raise ValueError("request event sequence must be null or a uint8 int")

    timestamp_ns = record.get("timestamp_ns")
    if (
        isinstance(timestamp_ns, bool)
        or not isinstance(timestamp_ns, int)
        or timestamp_ns < 0
    ):
        raise ValueError("request event timestamp_ns must be a non-negative int")

    thread_connection = record.get("thread_connection")
    if thread_connection is not None and not isinstance(thread_connection, bool):
        raise ValueError("request event thread_connection must be null or bool")
    if thread_connection is not None and category != "accepted":
        raise ValueError("thread_connection is only meaningful on an accepted event")


def build_request_event(
    *,
    session_id: str,
    observation: _RequestObservation,
) -> dict[str, Any]:
    """Build and validate one JSONL-ready row from a captured observation."""
    record: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "kind": _KIND,
        "session_id": session_id,
        "category": observation.category,
        "sequence": observation.sequence,
        "timestamp_ns": observation.timestamp_ns,
        "thread_connection": observation.thread_connection,
    }
    _validate_request_event(record)
    return record


def append_request_event(path: Path, record: Mapping[str, Any]) -> None:
    """Validate ``record`` and append it as one JSON line to ``path``.

    Append-only: existing rows are never rewritten, matching the journal
    contract this schema is designed to slot into (D-18/D-20).
    """
    _validate_request_event(record)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(record), sort_keys=True))
        handle.write("\n")


def reload_request_events(path: Path) -> list[dict[str, Any]]:
    """Read back every validated row from an append-only journal at ``path``."""
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        record = json.loads(stripped)
        _validate_request_event(record)
        events.append(record)
    return events


def derive_request_result(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Derive logical latency and winning-sequence ACK RTT from one request's events.

    Deterministic and side-effect-free: the same event list always yields
    the same derived result, which is what proves the appended journal
    round-trips through :func:`reload_request_events` without loss (D-07).
    """
    logical_start_ns: int | None = None
    sent_ns_by_sequence: dict[int, int] = {}
    accepted: Mapping[str, Any] | None = None

    for event in events:
        category = event["category"]
        if category == "logical_start":
            logical_start_ns = event["timestamp_ns"]
        elif category == "sent":
            sequence = event["sequence"]
            if sequence is not None:
                sent_ns_by_sequence[sequence] = event["timestamp_ns"]
        elif category == "accepted":
            accepted = event

    if logical_start_ns is None:
        raise ValueError("no logical_start event in the supplied request events")
    if accepted is None:
        raise ValueError("no accepted event in the supplied request events")

    accepted_sequence = accepted["sequence"]
    accepted_ns = accepted["timestamp_ns"]
    if accepted_sequence not in sent_ns_by_sequence:
        raise ValueError(
            f"accepted sequence {accepted_sequence!r} has no matching sent event"
        )

    return {
        "logical_start_ns": logical_start_ns,
        "accepted_ns": accepted_ns,
        "accepted_sequence": accepted_sequence,
        "logical_latency_ns": accepted_ns - logical_start_ns,
        "ack_rtt_ns": accepted_ns - sent_ns_by_sequence[accepted_sequence],
        "thread_connection": accepted["thread_connection"],
    }


async def trace_request(
    connection: DeviceConnection,
    packet: Any,
    *,
    session_id: str,
    journal_path: Path,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Trace one real production request end to end into a validated journal.

    Drives ``connection.request(packet)`` through the real retry/correlation
    engine (:meth:`DeviceConnection._transmit_and_listen`), captures its
    private observation events via
    :func:`scripts.measurement_support._capture_request_observations`,
    validates and appends every one of them to ``journal_path``, then
    reloads the appended rows for this session and derives the request
    result -- proving the full validate/append/reload/derive round trip
    against a real request path rather than synthetic events.

    Whatever ``connection.request()`` raises (for example
    ``LifxTimeoutError``) propagates unchanged; the observed events captured
    up to that point are still appended to ``journal_path`` first, so a
    failed trial remains part of the evidence (D-03).
    """
    sink: _RequestObservationSink | None = None
    try:
        with _capture_request_observations() as active_sink:
            sink = active_sink
            await connection.request(packet, timeout=timeout)
    finally:
        if sink is not None:
            for observation in sink.observations:
                append_request_event(
                    journal_path,
                    build_request_event(session_id=session_id, observation=observation),
                )

    events = reload_request_events(journal_path)
    session_events = [event for event in events if event["session_id"] == session_id]
    return derive_request_result(session_events)


# ---------------------------------------------------------------------------
# Plan 14-02: the frozen session manifest, five journal contracts, and
# deterministic derived products (D-01..D-20). Everything below is
# schema-only -- it defines and validates the evidence grammar and generates
# products from validated rows, but drives no hardware. Plan 14-06 supplies
# the real rows this contract is built to receive.
# ---------------------------------------------------------------------------

_MANIFEST_SCHEMA_VERSION = 1
_MANIFEST_KIND = "session_manifest"
_MANIFEST_FILENAME = "14-MANIFEST.json"

DISCOVERY_FILENAME = "14-DISCOVERY.jsonl"
REQUESTS_FILENAME = "14-REQUESTS.jsonl"
ANIMATION_FILENAME = "14-ANIMATION.jsonl"
STALENESS_FILENAME = "14-STALENESS.jsonl"
CLOSURE_FILENAME = "14-CLOSURE.jsonl"
SUMMARY_FILENAME = "14-SUMMARY.json"
CLASS_LEDGER_FILENAME = "14-CLASS-LEDGER.json"
REPORT_FILENAME = "14-REPORT.md"

_DEVICE_CLASSES: frozenset[str] = frozenset(
    {
        "Light",
        "MultiZoneLight",
        "MatrixLight",
        "CeilingLight",
        "InfraredLight",
        "HevLight",
    }
)
_AVAILABLE_DEVICE_CLASSES: frozenset[str] = frozenset(
    {"Light", "MultiZoneLight", "MatrixLight", "CeilingLight"}
)
_NAMED_GAP_DEVICE_CLASSES: frozenset[str] = frozenset({"InfraredLight", "HevLight"})

# Closed confounder vocabulary, mirrors scripts/measure_merged_discovery.py's
# `_CONFOUNDS` (an unquiesced/interfered environment is still evidence -- it
# is recorded, never silently dropped).
_CONFOUNDERS: frozenset[str] = frozenset(
    {
        "background_pollers",
        "busy_network",
        "wireless_interference",
        "unquiesced_environment",
    }
)
# Every evidence row is explicitly tagged physical or synthetic so a fake/test
# row can never be mistaken for physical-fleet evidence (AC-17).
_PROVENANCE: frozenset[str] = frozenset({"physical", "synthetic"})

_MANIFEST_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "kind",
        "session_id",
        "protocol_version",
        "revision",
        "inventory",
        "confounders",
        "seed",
        "discovery_round_gaps_s",
        "request_trial_gaps_s",
        "animation_schedule",
        "staleness_poll_interval_s",
        "staleness_confirm_absent_polls",
        "staleness_cap_s",
        "request_retransmit_floor_s",
    }
)
_INVENTORY_ENTRY_KEYS: frozenset[str] = frozenset(
    {"alias", "device_class", "available"}
)


def _validate_protocol_version(value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("protocol_version must be a positive integer")


def _validate_confounders(confounders: object) -> None:
    if (
        not isinstance(confounders, list)
        or len(confounders) != len(set(confounders))
        or not set(confounders) <= _CONFOUNDERS
    ):
        raise ValueError("invalid confounders")


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    """Raise ``ValueError`` unless ``manifest`` is a well-formed, frozen manifest.

    Closed-schema, like ``_validate_request_event``: an unrecognised key is
    rejected outright. Generated schedules and frozen constants are
    regenerated/re-read and compared exactly rather than trusted as stored --
    this is what makes drift in protocol, revision, inventory, confounders,
    seed, a schedule, or a constant detectable on reopen (D-18).
    """
    keys = set(manifest.keys())
    if keys != _MANIFEST_KEYS:
        raise ValueError(f"manifest has unexpected keys: {keys ^ _MANIFEST_KEYS}")
    if manifest.get("schema_version") != _MANIFEST_SCHEMA_VERSION:
        raise ValueError("manifest has wrong schema_version")
    if manifest.get("kind") != _MANIFEST_KIND:
        raise ValueError("manifest has wrong kind")

    validate_session_id(manifest["session_id"])
    _validate_protocol_version(manifest["protocol_version"])
    validate_revision(manifest["revision"])

    inventory = manifest["inventory"]
    if not isinstance(inventory, list):
        raise ValueError("manifest inventory must be a list")
    seen_aliases: set[str] = set()
    for entry in inventory:
        if not isinstance(entry, dict) or set(entry) != _INVENTORY_ENTRY_KEYS:
            raise ValueError("invalid manifest inventory entry")
        alias = validate_alias(entry["alias"])
        if alias in seen_aliases:
            raise ValueError("duplicate alias in manifest inventory")
        seen_aliases.add(alias)
        if entry["device_class"] not in _AVAILABLE_DEVICE_CLASSES:
            raise ValueError(
                "manifest inventory device_class must be an available class"
            )
        if not isinstance(entry["available"], bool):
            raise ValueError("manifest inventory available must be a boolean")

    _validate_confounders(manifest["confounders"])

    seed = manifest["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int) or not (0 <= seed < 2**64):
        raise ValueError("manifest seed must be an unsigned 64-bit integer")

    schedules = generate_manifest_schedules(seed)
    if list(manifest["discovery_round_gaps_s"]) != list(
        schedules.discovery_round_gaps_s
    ):
        raise ValueError(
            "manifest discovery_round_gaps_s does not match the seeded schedule"
        )
    if list(manifest["request_trial_gaps_s"]) != list(schedules.request_trial_gaps_s):
        raise ValueError(
            "manifest request_trial_gaps_s does not match the seeded schedule"
        )

    expected_animation = [list(rate) for rate in ANIMATION_SCHEDULE]
    if manifest["animation_schedule"] != expected_animation:
        raise ValueError(
            "manifest animation_schedule does not match the frozen D-10 schedule"
        )

    if manifest["staleness_poll_interval_s"] != STALENESS_POLL_INTERVAL_S:
        raise ValueError(
            "manifest staleness_poll_interval_s does not match the frozen constant"
        )
    if manifest["staleness_confirm_absent_polls"] != STALENESS_CONFIRM_ABSENT_POLLS:
        raise ValueError(
            "manifest staleness_confirm_absent_polls does not match the frozen constant"
        )
    if manifest["staleness_cap_s"] != STALENESS_CAP_S:
        raise ValueError("manifest staleness_cap_s does not match the frozen constant")

    floor = manifest["request_retransmit_floor_s"]
    if isinstance(floor, bool) or not isinstance(floor, (int, float)) or floor <= 0:
        raise ValueError(
            "manifest request_retransmit_floor_s must be a positive number"
        )

    if contains_forbidden_key(manifest) or contains_forbidden_value(manifest):
        raise ValueError("manifest privacy validation rejected a forbidden field/value")


def build_manifest(
    *,
    session_id: str,
    protocol_version: int,
    revision: str,
    inventory: Sequence[Mapping[str, Any]],
    confounders: Sequence[str],
    seed: int,
) -> dict[str, Any]:
    """Build and validate one immutable session manifest (does not touch disk)."""
    schedules = generate_manifest_schedules(seed)
    manifest: dict[str, Any] = {
        "schema_version": _MANIFEST_SCHEMA_VERSION,
        "kind": _MANIFEST_KIND,
        "session_id": session_id,
        "protocol_version": protocol_version,
        "revision": revision,
        "inventory": [dict(entry) for entry in inventory],
        "confounders": sorted(set(confounders)),
        "seed": seed,
        "discovery_round_gaps_s": list(schedules.discovery_round_gaps_s),
        "request_trial_gaps_s": list(schedules.request_trial_gaps_s),
        "animation_schedule": [list(rate) for rate in ANIMATION_SCHEDULE],
        "staleness_poll_interval_s": STALENESS_POLL_INTERVAL_S,
        "staleness_confirm_absent_polls": STALENESS_CONFIRM_ABSENT_POLLS,
        "staleness_cap_s": STALENESS_CAP_S,
        "request_retransmit_floor_s": REQUEST_RETRANSMIT_GAPS[0],
    }
    _validate_manifest(manifest)
    return manifest


def manifest_path(session_dir: Path) -> Path:
    """Return the fixed manifest path within one session directory."""
    return session_dir / _MANIFEST_FILENAME


def init_manifest(
    session_dir: Path,
    *,
    session_id: str,
    protocol_version: int,
    revision: str,
    inventory: Sequence[Mapping[str, Any]],
    confounders: Sequence[str],
    seed: int,
) -> dict[str, Any]:
    """Create the session manifest exclusively, or verify an exact semantic match.

    Reopening an existing session directory with identical inputs is
    idempotent. Any drift in protocol version, revision, inventory,
    confounders, seed, a generated schedule, or a frozen constant (for
    example a changed ``REQUEST_RETRANSMIT_GAPS`` floor) is rejected outright
    rather than silently accepted (D-18).
    """
    candidate = build_manifest(
        session_id=session_id,
        protocol_version=protocol_version,
        revision=revision,
        inventory=inventory,
        confounders=confounders,
        seed=seed,
    )
    path = manifest_path(session_dir)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        _validate_manifest(existing)
        if existing != candidate:
            raise ValueError(
                "session manifest already exists and does not match the "
                "requested protocol/revision/inventory/confounders/seed"
            )
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(candidate, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return candidate


def load_manifest(session_dir: Path) -> dict[str, Any]:
    """Load and validate the manifest for one session directory."""
    manifest = json.loads(manifest_path(session_dir).read_text(encoding="utf-8"))
    _validate_manifest(manifest)
    return manifest


# ---------------------------------------------------------------------------
# Shared append-only journal helper (D-18/D-20).
# ---------------------------------------------------------------------------


def _append_unique_row(
    path: Path,
    row: Mapping[str, Any],
    *,
    validate: Callable[[Mapping[str, Any]], None],
    key: tuple[Any, ...],
    key_of: Callable[[Mapping[str, Any]], tuple[Any, ...]],
) -> None:
    """Validate, reject a duplicate uniqueness key, then append without rewriting.

    Validation happens before any output is opened; a rejected row leaves the
    journal file completely untouched (it may not even exist yet).
    """
    validate(row)
    for existing_row in load_jsonl(path):
        if key_of(existing_row) == key:
            raise ValueError("duplicate row for this journal's uniqueness key")
    append_jsonl(path, row)


# ---------------------------------------------------------------------------
# 14-DISCOVERY.jsonl: repeated paired discovery rounds (THREAD-01, D-01/D-02).
# ---------------------------------------------------------------------------

_DISCOVERY_SCHEMA_VERSION = 1
_DISCOVERY_KIND = "discovery_round_event"
_DISCOVERY_SOURCES: frozenset[str] = frozenset({"discover", "discover_mdns"})
_DISCOVERY_OUTCOMES: frozenset[str] = frozenset(
    {"success", "empty", "failed", "timeout", "interrupted", "incomplete"}
)
_DISCOVERY_ROW_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "kind",
        "session_id",
        "protocol_version",
        "revision",
        "round",
        "source",
        "call_order",
        "outcome",
        "devices",
        "provenance",
        "confounders",
    }
)


def _expected_discovery_call_order(round_number: int, source: str) -> int:
    """Return the locked D-02 alternating call order for one round/source.

    Odd rounds call ``discover()`` first; even rounds call
    ``discover_mdns()`` first -- a schema-enforced fact, not a convention a
    caller could silently drift from.
    """
    first_source = "discover" if round_number % 2 == 1 else "discover_mdns"
    return 1 if source == first_source else 2


def _validate_discovery_event(record: Mapping[str, Any]) -> None:
    keys = set(record.keys())
    if keys != _DISCOVERY_ROW_KEYS:
        raise ValueError(
            f"discovery event has unexpected keys: {keys ^ _DISCOVERY_ROW_KEYS}"
        )
    if record.get("schema_version") != _DISCOVERY_SCHEMA_VERSION:
        raise ValueError("discovery event has wrong schema_version")
    if record.get("kind") != _DISCOVERY_KIND:
        raise ValueError("discovery event has wrong kind")
    validate_session_id(record["session_id"])
    _validate_protocol_version(record["protocol_version"])
    validate_revision(record["revision"])

    round_number = record["round"]
    if (
        isinstance(round_number, bool)
        or not isinstance(round_number, int)
        or not (1 <= round_number <= DISCOVERY_ROUNDS)
    ):
        raise ValueError("discovery event round must be within the frozen six rounds")

    source = record["source"]
    if source not in _DISCOVERY_SOURCES:
        raise ValueError("discovery event has an unknown source")

    if record["call_order"] != _expected_discovery_call_order(round_number, source):
        raise ValueError(
            "discovery event call_order violates the locked D-02 alternation"
        )

    outcome = record["outcome"]
    if outcome not in _DISCOVERY_OUTCOMES:
        raise ValueError("discovery event has an unknown outcome")

    devices = record["devices"]
    if not isinstance(devices, list):
        raise ValueError("discovery event devices must be a list")
    seen: set[str] = set()
    for alias in devices:
        validated = validate_alias(alias)
        if validated in seen:
            raise ValueError("duplicate alias within one discovery event")
        seen.add(validated)
    if outcome == "success" and not devices:
        raise ValueError("a success discovery outcome requires at least one device")
    if outcome != "success" and devices:
        raise ValueError("only a success discovery outcome may carry devices")

    if record["provenance"] not in _PROVENANCE:
        raise ValueError("discovery event has an unknown provenance")
    _validate_confounders(record["confounders"])
    if contains_forbidden_key(record) or contains_forbidden_value(record):
        raise ValueError(
            "discovery event privacy validation rejected a forbidden field/value"
        )


def build_discovery_event(
    *,
    session_id: str,
    protocol_version: int,
    revision: str,
    round_number: int,
    source: str,
    outcome: str,
    devices: Sequence[str] = (),
    provenance: str,
    confounders: Sequence[str] = (),
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": _DISCOVERY_SCHEMA_VERSION,
        "kind": _DISCOVERY_KIND,
        "session_id": session_id,
        "protocol_version": protocol_version,
        "revision": revision,
        "round": round_number,
        "source": source,
        "call_order": _expected_discovery_call_order(round_number, source),
        "outcome": outcome,
        "devices": sorted(set(devices)),
        "provenance": provenance,
        "confounders": sorted(set(confounders)),
    }
    _validate_discovery_event(record)
    return record


def append_discovery_event(path: Path, record: Mapping[str, Any]) -> None:
    """Append one validated discovery round outcome.

    D-18: unique per session/source/round.
    """
    _append_unique_row(
        path,
        record,
        validate=_validate_discovery_event,
        key=(record.get("session_id"), record.get("source"), record.get("round")),
        key_of=lambda row: (row.get("session_id"), row.get("source"), row.get("round")),
    )


def reload_discovery_events(path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    for row in rows:
        _validate_discovery_event(row)
    return rows


# ---------------------------------------------------------------------------
# 14-REQUESTS.jsonl: per-device no-op SetPower trials (THREAD-02, D-03/D-05..D-08).
# ---------------------------------------------------------------------------

_REQUEST_TRIAL_SCHEMA_VERSION = 1
_REQUEST_TRIAL_KIND = "request_trial_event"
_REQUEST_TRIAL_OUTCOMES: frozenset[str] = frozenset(
    {
        "completed",
        "timeout",
        "send_error",
        "power_out_of_range",
        "cancelled",
        "interrupted",
    }
)
_REQUEST_TRIAL_ROW_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "kind",
        "session_id",
        "protocol_version",
        "revision",
        "alias",
        "trial",
        "outcome",
        "logical_latency_ns",
        "ack_rtt_ns",
        "thread_connection",
        "provenance",
        "confounders",
    }
)


def _validate_request_trial_event(record: Mapping[str, Any]) -> None:
    keys = set(record.keys())
    if keys != _REQUEST_TRIAL_ROW_KEYS:
        raise ValueError(
            f"request trial event has unexpected keys: {keys ^ _REQUEST_TRIAL_ROW_KEYS}"
        )
    if record.get("schema_version") != _REQUEST_TRIAL_SCHEMA_VERSION:
        raise ValueError("request trial event has wrong schema_version")
    if record.get("kind") != _REQUEST_TRIAL_KIND:
        raise ValueError("request trial event has wrong kind")
    validate_session_id(record["session_id"])
    _validate_protocol_version(record["protocol_version"])
    validate_revision(record["revision"])
    validate_alias(record["alias"])

    trial = record["trial"]
    if (
        isinstance(trial, bool)
        or not isinstance(trial, int)
        or not (1 <= trial <= REQUEST_TRIALS)
    ):
        raise ValueError(
            "request trial event trial must be within the frozen 100 trials"
        )

    outcome = record["outcome"]
    if outcome not in _REQUEST_TRIAL_OUTCOMES:
        raise ValueError("request trial event has an unknown outcome")

    logical_latency_ns = record["logical_latency_ns"]
    ack_rtt_ns = record["ack_rtt_ns"]
    thread_connection = record["thread_connection"]
    if outcome == "completed":
        for name, value in (
            ("logical_latency_ns", logical_latency_ns),
            ("ack_rtt_ns", ack_rtt_ns),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"a completed request trial requires a non-negative {name}"
                )
        if not isinstance(thread_connection, bool):
            raise ValueError(
                "a completed request trial requires a boolean thread_connection"
            )
    else:
        if (
            logical_latency_ns is not None
            or ack_rtt_ns is not None
            or thread_connection is not None
        ):
            raise ValueError(
                "a non-completed request trial must not carry latency or "
                "thread_connection"
            )

    if record["provenance"] not in _PROVENANCE:
        raise ValueError("request trial event has an unknown provenance")
    _validate_confounders(record["confounders"])
    if contains_forbidden_key(record) or contains_forbidden_value(record):
        raise ValueError(
            "request trial event privacy validation rejected a forbidden field/value"
        )


def build_request_trial_event(
    *,
    session_id: str,
    protocol_version: int,
    revision: str,
    alias: str,
    trial: int,
    outcome: str,
    logical_latency_ns: int | None = None,
    ack_rtt_ns: int | None = None,
    thread_connection: bool | None = None,
    provenance: str,
    confounders: Sequence[str] = (),
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": _REQUEST_TRIAL_SCHEMA_VERSION,
        "kind": _REQUEST_TRIAL_KIND,
        "session_id": session_id,
        "protocol_version": protocol_version,
        "revision": revision,
        "alias": alias,
        "trial": trial,
        "outcome": outcome,
        "logical_latency_ns": logical_latency_ns,
        "ack_rtt_ns": ack_rtt_ns,
        "thread_connection": thread_connection,
        "provenance": provenance,
        "confounders": sorted(set(confounders)),
    }
    _validate_request_trial_event(record)
    return record


def append_request_trial_event(path: Path, record: Mapping[str, Any]) -> None:
    """Append one validated request trial (D-18: session/alias/trial unique)."""
    _append_unique_row(
        path,
        record,
        validate=_validate_request_trial_event,
        key=(record.get("session_id"), record.get("alias"), record.get("trial")),
        key_of=lambda row: (row.get("session_id"), row.get("alias"), row.get("trial")),
    )


def reload_request_trial_events(path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    for row in rows:
        _validate_request_trial_event(row)
    return rows


# ---------------------------------------------------------------------------
# 14-ANIMATION.jsonl: one bounded non-gating current-behaviour observation
# per available alias (THREAD-03, D-09..D-16).
# ---------------------------------------------------------------------------

_ANIMATION_SCHEMA_VERSION = 1
_ANIMATION_KIND = "animation_observation_event"
_ANIMATION_RATE_OUTCOMES: frozenset[str] = frozenset(
    {"completed", "interrupted", "failed"}
)
_ANIMATION_ROW_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "kind",
        "session_id",
        "protocol_version",
        "revision",
        "alias",
        "pre_liveness",
        "rates",
        "post_liveness",
        "restored",
        "restoration_verified",
        "provenance",
        "confounders",
    }
)
# Exactly the fields AnimatorStats already exposes -- packets_sent,
# total_time_ms, gated, acks_outstanding (src/lifx/animation/animator.py:70-91)
# -- plus script-owned scheduling/outcome fields. There is deliberately no
# ack-received or expiry-count field: AckGate.sweep() prunes expired probes
# silently (flow.py:153-161), so a falling `acks_outstanding` is ambiguous
# between "the device acknowledged" and "the probe expired unacknowledged".
# `acks_outstanding` here is the LAST observed instantaneous count for that
# rate's attempt and MUST NEVER be renamed, aggregated, or narrated as
# acknowledgement-delivery evidence -- the closed key set below is what
# enforces that: there is no field anywhere in this schema that could hold
# such a claim (see the dedicated negative test in the test suite).
_ANIMATION_RATE_KEYS: frozenset[str] = frozenset(
    {
        "fps",
        "duration_s",
        "outcome",
        "offered",
        "packets_sent",
        "total_time_ms",
        "gated",
        "acks_outstanding",
        "failed",
    }
)


def _validate_animation_rate(
    rate: object, *, expected_fps: int, expected_duration_s: float
) -> None:
    if not isinstance(rate, dict) or set(rate) != _ANIMATION_RATE_KEYS:
        raise ValueError("invalid animation rate entry")
    if rate["fps"] != expected_fps:
        raise ValueError("animation rate fps does not match the frozen D-10 schedule")
    if rate["duration_s"] != expected_duration_s:
        raise ValueError(
            "animation rate duration_s does not match the frozen D-10 schedule"
        )
    if rate["outcome"] not in _ANIMATION_RATE_OUTCOMES:
        raise ValueError("invalid animation rate outcome")
    for key in ("offered", "packets_sent", "gated", "acks_outstanding", "failed"):
        value = rate[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"animation rate {key} must be a non-negative integer")
    total_time_ms = rate["total_time_ms"]
    if (
        isinstance(total_time_ms, bool)
        or not isinstance(total_time_ms, (int, float))
        or total_time_ms < 0
    ):
        raise ValueError("animation rate total_time_ms must be a non-negative number")


def _validate_animation_event(record: Mapping[str, Any]) -> None:
    keys = set(record.keys())
    if keys != _ANIMATION_ROW_KEYS:
        raise ValueError(
            f"animation event has unexpected keys: {keys ^ _ANIMATION_ROW_KEYS}"
        )
    if record.get("schema_version") != _ANIMATION_SCHEMA_VERSION:
        raise ValueError("animation event has wrong schema_version")
    if record.get("kind") != _ANIMATION_KIND:
        raise ValueError("animation event has wrong kind")
    validate_session_id(record["session_id"])
    _validate_protocol_version(record["protocol_version"])
    validate_revision(record["revision"])
    validate_alias(record["alias"])

    if not isinstance(record["pre_liveness"], bool):
        raise ValueError("animation event pre_liveness must be a boolean")
    if not isinstance(record["post_liveness"], bool):
        raise ValueError("animation event post_liveness must be a boolean")

    rates = record["rates"]
    if not isinstance(rates, list) or len(rates) != len(ANIMATION_SCHEDULE):
        raise ValueError(
            "animation event must carry exactly the frozen D-10 ascending rate schedule"
        )
    for rate, (expected_fps, expected_duration_s) in zip(rates, ANIMATION_SCHEDULE):
        _validate_animation_rate(
            rate, expected_fps=expected_fps, expected_duration_s=expected_duration_s
        )

    restored = record["restored"]
    restoration_verified = record["restoration_verified"]
    if not isinstance(restored, bool) or not isinstance(restoration_verified, bool):
        raise ValueError(
            "animation event restored/restoration_verified must be boolean"
        )
    if restoration_verified and not restored:
        raise ValueError("restoration_verified cannot be true when restored is false")

    if record["provenance"] not in _PROVENANCE:
        raise ValueError("animation event has an unknown provenance")
    _validate_confounders(record["confounders"])
    if contains_forbidden_key(record) or contains_forbidden_value(record):
        raise ValueError(
            "animation event privacy validation rejected a forbidden field/value"
        )


def build_animation_event(
    *,
    session_id: str,
    protocol_version: int,
    revision: str,
    alias: str,
    pre_liveness: bool,
    rates: Sequence[Mapping[str, Any]],
    post_liveness: bool,
    restored: bool,
    restoration_verified: bool,
    provenance: str,
    confounders: Sequence[str] = (),
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": _ANIMATION_SCHEMA_VERSION,
        "kind": _ANIMATION_KIND,
        "session_id": session_id,
        "protocol_version": protocol_version,
        "revision": revision,
        "alias": alias,
        "pre_liveness": pre_liveness,
        "rates": [dict(rate) for rate in rates],
        "post_liveness": post_liveness,
        "restored": restored,
        "restoration_verified": restoration_verified,
        "provenance": provenance,
        "confounders": sorted(set(confounders)),
    }
    _validate_animation_event(record)
    return record


def append_animation_event(path: Path, record: Mapping[str, Any]) -> None:
    """Append one validated animation observation (D-18: session/alias unique)."""
    _append_unique_row(
        path,
        record,
        validate=_validate_animation_event,
        key=(record.get("session_id"), record.get("alias")),
        key_of=lambda row: (row.get("session_id"), row.get("alias")),
    )


def reload_animation_events(path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    for row in rows:
        _validate_animation_event(row)
    return rows


# ---------------------------------------------------------------------------
# 14-STALENESS.jsonl: advertisement-expiry experiment (THREAD-04, D-04).
# ---------------------------------------------------------------------------

_STALENESS_SCHEMA_VERSION = 1
_STALENESS_KIND = "staleness_experiment_event"
_STALENESS_DISPOSITIONS: frozenset[str] = frozenset(
    {"confirmed_expiry", "censored", "restored_before_expiry", "interrupted"}
)
_STALENESS_ROW_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "kind",
        "session_id",
        "protocol_version",
        "revision",
        "alias",
        "disconnect_ns",
        "polls",
        "first_absence_poll",
        "confirmed_expiry_poll",
        "disposition",
        "restored_available_ns",
        "restoration_duration_s",
        "provenance",
        "confounders",
    }
)
_STALENESS_POLL_KEYS: frozenset[str] = frozenset(
    {"poll", "elapsed_s", "discover_present", "discover_mdns_present"}
)


def _poll_is_absent(poll: Mapping[str, Any]) -> bool:
    """Absent means BOTH discovery legs miss the target on this poll.

    ``discover()`` routes mDNS candidates through unicast verification, so it
    can go absent within one poll of disconnect; ``discover_mdns()``
    reflects border-router advertisement and can keep reporting the device
    for far longer. THREAD-04 measures advertisement staleness, so a poll
    only counts as "absent" when neither leg sees the device -- an
    either-leg predicate would confirm "expiry" at unicast-liveness speed
    (~3 poll intervals) and publish that as the SRP lease, which is a
    different and much smaller number than what D-04 actually asks for.
    """
    return poll["discover_present"] is False and poll["discover_mdns_present"] is False


def _validate_staleness_event(record: Mapping[str, Any]) -> None:
    keys = set(record.keys())
    if keys != _STALENESS_ROW_KEYS:
        raise ValueError(
            f"staleness event has unexpected keys: {keys ^ _STALENESS_ROW_KEYS}"
        )
    if record.get("schema_version") != _STALENESS_SCHEMA_VERSION:
        raise ValueError("staleness event has wrong schema_version")
    if record.get("kind") != _STALENESS_KIND:
        raise ValueError("staleness event has wrong kind")
    validate_session_id(record["session_id"])
    _validate_protocol_version(record["protocol_version"])
    validate_revision(record["revision"])
    validate_alias(record["alias"])

    disconnect_ns = record["disconnect_ns"]
    if (
        isinstance(disconnect_ns, bool)
        or not isinstance(disconnect_ns, int)
        or disconnect_ns < 0
    ):
        raise ValueError("staleness event disconnect_ns must be a non-negative integer")

    polls = record["polls"]
    if not isinstance(polls, list) or not polls:
        raise ValueError("staleness event polls must be a non-empty list")
    previous_elapsed: float = -1.0
    for index, poll in enumerate(polls, start=1):
        if not isinstance(poll, dict) or set(poll) != _STALENESS_POLL_KEYS:
            raise ValueError("invalid staleness poll entry")
        if poll["poll"] != index:
            raise ValueError("staleness poll numbers must be contiguous starting at 1")
        elapsed_s = poll["elapsed_s"]
        if (
            isinstance(elapsed_s, bool)
            or not isinstance(elapsed_s, (int, float))
            or elapsed_s < previous_elapsed
            or elapsed_s > STALENESS_CAP_S
        ):
            raise ValueError(
                "staleness poll elapsed_s must be non-decreasing and within the cap"
            )
        previous_elapsed = elapsed_s
        if not isinstance(poll["discover_present"], bool) or not isinstance(
            poll["discover_mdns_present"], bool
        ):
            raise ValueError("staleness poll presence flags must be boolean")

    absences = [
        index for index, poll in enumerate(polls, start=1) if _poll_is_absent(poll)
    ]
    expected_first_absence = absences[0] if absences else None
    if record["first_absence_poll"] != expected_first_absence:
        raise ValueError("staleness event first_absence_poll does not match its polls")

    expected_confirmed: int | None = None
    for index in range(STALENESS_CONFIRM_ABSENT_POLLS, len(polls) + 1):
        window = polls[index - STALENESS_CONFIRM_ABSENT_POLLS : index]
        if all(_poll_is_absent(poll) for poll in window):
            expected_confirmed = index
            break
    if record["confirmed_expiry_poll"] != expected_confirmed:
        raise ValueError(
            "staleness event confirmed_expiry_poll does not match three "
            "consecutive both-legs-absent polls"
        )

    disposition = record["disposition"]
    if disposition not in _STALENESS_DISPOSITIONS:
        raise ValueError("staleness event has an unknown disposition")
    if disposition == "confirmed_expiry" and expected_confirmed is None:
        raise ValueError(
            "confirmed_expiry disposition requires a confirmed_expiry_poll"
        )
    if disposition != "confirmed_expiry" and expected_confirmed is not None:
        raise ValueError(
            "a confirmed three-pair absence requires the confirmed_expiry disposition"
        )
    if disposition == "censored" and previous_elapsed < STALENESS_CAP_S:
        raise ValueError("censored disposition requires the polls to reach the cap")
    if (
        expected_confirmed is None
        and previous_elapsed >= STALENESS_CAP_S
        and disposition != "censored"
    ):
        raise ValueError(
            "polls reaching the cap without a confirmed expiry require the "
            "censored disposition"
        )

    # `restored_available_ns` may be null for ANY disposition, not only
    # "interrupted": a closed absence/censoring/early-restoration
    # determination can still conclude without restoration ever being
    # confirmed -- exclusively because a T-14-06 power-on script
    # hard-failed after the disconnect experiment had already closed (the
    # restoration-detection wait itself is unbounded -- see
    # `run_staleness_experiment`'s ``restore_available`` contract -- so it
    # can never time out on its own). `disposition` records how the
    # absence-detection protocol closed; `restored_available_ns`
    # independently records whether/when restoration was later confirmed --
    # the two are deliberately decoupled so a power failure can never erase
    # an already-determined confirmed_expiry/censored/restored_before_expiry
    # finding.
    restored_available_ns = record["restored_available_ns"]
    if restored_available_ns is not None and (
        isinstance(restored_available_ns, bool)
        or not isinstance(restored_available_ns, int)
        or restored_available_ns < 0
    ):
        raise ValueError(
            "staleness event restored_available_ns must be null or non-negative"
        )

    # `restoration_duration_s` is the T-14-06 change 2 rediscovery figure:
    # wall time from the power-on edge (script exit) to both discovery legs
    # reporting present, which is the actually interesting measurement --
    # `restored_available_ns - disconnect_ns` is dominated by the expiry
    # wait and is not. It is present if and only if restoration was
    # confirmed (i.e. exactly when `restored_available_ns` is present).
    restoration_duration_s = record["restoration_duration_s"]
    if restored_available_ns is None:
        if restoration_duration_s is not None:
            raise ValueError(
                "staleness event restoration_duration_s must be null when "
                "restored_available_ns is null"
            )
    elif (
        isinstance(restoration_duration_s, bool)
        or not isinstance(restoration_duration_s, (int, float))
        or restoration_duration_s < 0
    ):
        raise ValueError(
            "staleness event restoration_duration_s must be a non-negative "
            "number when restored_available_ns is present"
        )

    if record["provenance"] not in _PROVENANCE:
        raise ValueError("staleness event has an unknown provenance")
    _validate_confounders(record["confounders"])
    if contains_forbidden_key(record) or contains_forbidden_value(record):
        raise ValueError(
            "staleness event privacy validation rejected a forbidden field/value"
        )


def build_staleness_event(
    *,
    session_id: str,
    protocol_version: int,
    revision: str,
    alias: str,
    disconnect_ns: int,
    polls: Sequence[Mapping[str, Any]],
    disposition: str,
    restored_available_ns: int | None = None,
    restoration_duration_s: float | None = None,
    provenance: str,
    confounders: Sequence[str] = (),
) -> dict[str, Any]:
    polls_list = [dict(poll) for poll in polls]
    absences = [
        index for index, poll in enumerate(polls_list, start=1) if _poll_is_absent(poll)
    ]
    first_absence_poll = absences[0] if absences else None
    confirmed_expiry_poll: int | None = None
    for index in range(STALENESS_CONFIRM_ABSENT_POLLS, len(polls_list) + 1):
        window = polls_list[index - STALENESS_CONFIRM_ABSENT_POLLS : index]
        if all(_poll_is_absent(poll) for poll in window):
            confirmed_expiry_poll = index
            break
    record: dict[str, Any] = {
        "schema_version": _STALENESS_SCHEMA_VERSION,
        "kind": _STALENESS_KIND,
        "session_id": session_id,
        "protocol_version": protocol_version,
        "revision": revision,
        "alias": alias,
        "disconnect_ns": disconnect_ns,
        "polls": polls_list,
        "first_absence_poll": first_absence_poll,
        "confirmed_expiry_poll": confirmed_expiry_poll,
        "disposition": disposition,
        "restored_available_ns": restored_available_ns,
        "restoration_duration_s": restoration_duration_s,
        "provenance": provenance,
        "confounders": sorted(set(confounders)),
    }
    _validate_staleness_event(record)
    return record


def append_staleness_event(path: Path, record: Mapping[str, Any]) -> None:
    """Append one validated staleness experiment (D-18: session/alias unique)."""
    _append_unique_row(
        path,
        record,
        validate=_validate_staleness_event,
        key=(record.get("session_id"), record.get("alias")),
        key_of=lambda row: (row.get("session_id"), row.get("alias")),
    )


def reload_staleness_events(path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    for row in rows:
        _validate_staleness_event(row)
    return rows


# ---------------------------------------------------------------------------
# 14-CLOSURE.jsonl: six-class evidence/named-gap ledger (THREAD-05, D-20).
# ---------------------------------------------------------------------------

_CLOSURE_SCHEMA_VERSION = 1
_CLOSURE_KIND = "closure_disposition_event"
_CLOSURE_DISPOSITIONS: frozenset[str] = frozenset({"evidence_backed", "named_gap"})
_CLOSURE_ROW_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "kind",
        "session_id",
        "protocol_version",
        "revision",
        "device_class",
        "disposition",
        "aliases",
        "gap_reason",
        "gap_recorded_date",
        "provenance",
        "confounders",
    }
)
_GAP_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def _validate_closure_event(record: Mapping[str, Any]) -> None:
    keys = set(record.keys())
    if keys != _CLOSURE_ROW_KEYS:
        raise ValueError(
            f"closure event has unexpected keys: {keys ^ _CLOSURE_ROW_KEYS}"
        )
    if record.get("schema_version") != _CLOSURE_SCHEMA_VERSION:
        raise ValueError("closure event has wrong schema_version")
    if record.get("kind") != _CLOSURE_KIND:
        raise ValueError("closure event has wrong kind")
    validate_session_id(record["session_id"])
    _validate_protocol_version(record["protocol_version"])
    validate_revision(record["revision"])

    device_class = record["device_class"]
    if device_class not in _DEVICE_CLASSES:
        raise ValueError("closure event has an unknown device_class")

    disposition = record["disposition"]
    if disposition not in _CLOSURE_DISPOSITIONS:
        raise ValueError("closure event has an unknown disposition")

    aliases = record["aliases"]
    if not isinstance(aliases, list):
        raise ValueError("closure event aliases must be a list")
    seen: set[str] = set()
    for alias in aliases:
        validated = validate_alias(alias)
        if validated in seen:
            raise ValueError("duplicate alias within one closure event")
        seen.add(validated)

    gap_reason = record["gap_reason"]
    gap_recorded_date = record["gap_recorded_date"]
    provenance = record["provenance"]

    if disposition == "evidence_backed":
        if not aliases:
            raise ValueError("evidence_backed closure requires at least one alias")
        if device_class not in _AVAILABLE_DEVICE_CLASSES:
            raise ValueError(
                "only a currently available device class may close evidence_backed"
            )
        if gap_reason is not None or gap_recorded_date is not None:
            raise ValueError("evidence_backed closure must not carry gap fields")
        if provenance != "physical":
            raise ValueError(
                "evidence_backed closure requires physical provenance -- synthetic "
                "evidence can never be labelled physical-fleet evidence"
            )
    else:
        if aliases:
            raise ValueError("named_gap closure must not carry aliases")
        if device_class not in _NAMED_GAP_DEVICE_CLASSES:
            raise ValueError(
                "only InfraredLight/HevLight may close as a named gap -- an "
                "available class cannot substitute a gap for a poor result"
            )
        if not isinstance(gap_reason, str) or not gap_reason:
            raise ValueError("named_gap closure requires a non-empty gap_reason")
        forbidden_phrase = contains_forbidden_vocabulary(gap_reason)
        if forbidden_phrase is not None:
            raise ValueError(
                f"gap_reason uses forbidden evidence-language: {forbidden_phrase!r}"
            )
        if (
            not isinstance(gap_recorded_date, str)
            or _GAP_DATE_PATTERN.fullmatch(gap_recorded_date) is None
        ):
            raise ValueError("named_gap closure requires an ISO gap_recorded_date")
        if provenance is not None:
            raise ValueError("named_gap closure must not carry a provenance")

    _validate_confounders(record["confounders"])
    if contains_forbidden_key(record) or contains_forbidden_value(record):
        raise ValueError(
            "closure event privacy validation rejected a forbidden field/value"
        )


def build_closure_event(
    *,
    session_id: str,
    protocol_version: int,
    revision: str,
    device_class: str,
    disposition: str,
    aliases: Sequence[str] = (),
    gap_reason: str | None = None,
    gap_recorded_date: str | None = None,
    provenance: str | None = None,
    confounders: Sequence[str] = (),
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": _CLOSURE_SCHEMA_VERSION,
        "kind": _CLOSURE_KIND,
        "session_id": session_id,
        "protocol_version": protocol_version,
        "revision": revision,
        "device_class": device_class,
        "disposition": disposition,
        "aliases": sorted(set(aliases)),
        "gap_reason": gap_reason,
        "gap_recorded_date": gap_recorded_date,
        "provenance": provenance,
        "confounders": sorted(set(confounders)),
    }
    _validate_closure_event(record)
    return record


def append_closure_event(path: Path, record: Mapping[str, Any]) -> None:
    """Append one validated closure disposition (D-18: session/device_class unique)."""
    _append_unique_row(
        path,
        record,
        validate=_validate_closure_event,
        key=(record.get("session_id"), record.get("device_class")),
        key_of=lambda row: (row.get("session_id"), row.get("device_class")),
    )


def reload_closure_events(path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    for row in rows:
        _validate_closure_event(row)
    return rows


# ---------------------------------------------------------------------------
# Deterministic derived products (D-20): summary, six-class ledger, report.
# Never hand-edited, never parse their own output, and reproducible from
# validated journals regardless of on-disk row order.
# ---------------------------------------------------------------------------


def generate_class_ledger(closure_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Regenerate the exact six-class disposition ledger from closure rows."""
    by_class: dict[str, Mapping[str, Any]] = {}
    for row in closure_rows:
        _validate_closure_event(row)
        device_class = row["device_class"]
        if device_class in by_class:
            raise ValueError("duplicate closure disposition for one device class")
        by_class[device_class] = row
    missing = sorted(_DEVICE_CLASSES - set(by_class))
    return {
        "schema_version": 1,
        "kind": "class_ledger",
        "classes": {
            device_class: {
                "disposition": by_class[device_class]["disposition"],
                "aliases": sorted(by_class[device_class]["aliases"]),
                "gap_reason": by_class[device_class]["gap_reason"],
                "gap_recorded_date": by_class[device_class]["gap_recorded_date"],
            }
            for device_class in sorted(by_class)
        },
        "complete": not missing,
        "missing_classes": missing,
    }


def generate_summary(
    *,
    discovery_rows: Sequence[Mapping[str, Any]],
    request_rows: Sequence[Mapping[str, Any]],
    animation_rows: Sequence[Mapping[str, Any]],
    staleness_rows: Sequence[Mapping[str, Any]],
    closure_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Regenerate the deterministic session summary from validated journals only.

    Sorts every aggregation key so the result is independent of on-disk row
    order -- proven by regenerating twice from shuffled equivalent journals
    and comparing bytes.
    """
    for row in discovery_rows:
        _validate_discovery_event(row)
    for row in request_rows:
        _validate_request_trial_event(row)
    for row in animation_rows:
        _validate_animation_event(row)
    for row in staleness_rows:
        _validate_staleness_event(row)

    coverage: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    rounds_by_source: dict[str, set[int]] = defaultdict(set)
    for row in discovery_rows:
        rounds_by_source[row["source"]].add(row["round"])
        for alias in row["devices"]:
            coverage[row["source"]][alias].add(row["round"])
    discovery_summary = {
        source: {
            "rounds_attempted": sorted(rounds_by_source[source]),
            "devices": {
                alias: sorted(rounds)
                for alias, rounds in sorted(coverage[source].items())
            },
        }
        for source in sorted(_DISCOVERY_SOURCES)
    }

    per_alias_logical: dict[str, list[int]] = defaultdict(list)
    per_alias_ack: dict[str, list[int]] = defaultdict(list)
    per_alias_outcomes: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for row in request_rows:
        alias = row["alias"]
        per_alias_outcomes[alias][row["outcome"]] += 1
        if row["outcome"] == "completed":
            per_alias_logical[alias].append(row["logical_latency_ns"])
            per_alias_ack[alias].append(row["ack_rtt_ns"])
    request_summary = {
        alias: {
            "logical_latency": summarise_latencies_ns(per_alias_logical.get(alias, [])),
            "ack_rtt": summarise_latencies_ns(per_alias_ack.get(alias, [])),
            "outcomes": dict(sorted(per_alias_outcomes[alias].items())),
        }
        for alias in sorted(per_alias_outcomes)
    }

    animation_summary = {
        row["alias"]: {
            "restored": row["restored"],
            "restoration_verified": row["restoration_verified"],
            "rates": [
                {
                    "fps": rate["fps"],
                    "outcome": rate["outcome"],
                    "offered": rate["offered"],
                    "packets_sent": rate["packets_sent"],
                    "gated": rate["gated"],
                    "failed": rate["failed"],
                }
                for rate in row["rates"]
            ],
        }
        for row in sorted(animation_rows, key=lambda row: row["alias"])
    }

    staleness_summary = {
        row["alias"]: {
            "disposition": row["disposition"],
            "first_absence_poll": row["first_absence_poll"],
            "confirmed_expiry_poll": row["confirmed_expiry_poll"],
            "restored_available_ns": row["restored_available_ns"],
            "restoration_duration_s": row["restoration_duration_s"],
        }
        for row in sorted(staleness_rows, key=lambda row: row["alias"])
    }

    return {
        "schema_version": 1,
        "kind": "session_summary",
        "discovery": discovery_summary,
        "requests": request_summary,
        "animation": animation_summary,
        "staleness": staleness_summary,
        "class_ledger": generate_class_ledger(closure_rows),
    }


def generate_report(summary: Mapping[str, Any]) -> str:
    """Render a deterministic human-readable Markdown report from ``summary``.

    Consumes only the already-generated ``summary`` dict -- it never reads or
    parses a prior ``14-REPORT.md``.
    """
    lines = [
        "# Phase 14 Thread Revalidation Report",
        "",
        "Generated solely from validated append-only JSONL journals via "
        "`generate_summary()`. Never hand-edited.",
        "",
        "## Discovery coverage (THREAD-01)",
        "",
    ]
    discovery = summary["discovery"]
    for source in sorted(discovery):
        entry = discovery[source]
        lines.append(
            f"- `{source}`: rounds attempted {entry['rounds_attempted']}, "
            f"{len(entry['devices'])} device(s) observed."
        )
    lines.extend(["", "## Request timing (THREAD-02)", ""])
    lines.extend(
        [
            "These are this fleet's and this session's observations, taken on a mesh",
            "with recorded confounders. They are not an authoritative benchmark, a",
            "universal Thread limit, a regression gate, or sufficient grounds for",
            "tuning any library constant. Each row's environmental qualification is",
            "the `confounders` field on its journal entries.",
            "",
        ]
    )
    requests = summary["requests"]
    if not requests:
        lines.append("- No request trials recorded.")
    for alias in sorted(requests):
        entry = requests[alias]
        lines.append(
            f"- `{alias}`: outcomes {entry['outcomes']}; "
            f"logical_latency={entry['logical_latency']}; ack_rtt={entry['ack_rtt']}."
        )
    lines.extend(["", "## Animation (THREAD-03, out of scope)", ""])
    lines.extend(
        [
            "Thread animation is a recorded scope boundary, not a measurement this",
            "phase completes. Thread does not have the bandwidth to sustain animation",
            "at usable or smooth frame rates, and pushing that volume of data onto a",
            "mesh is poor practice regardless of what a measurement would show.",
            "`Animator` is intended to be locked to WiFi devices in a future",
            "milestone. Class closure does not consult animation at all.",
            "",
            "Any observation below shows only that Thread carried the frames without",
            "failing. It is NOT evidence that Thread animation is usable, and it is",
            "not a throughput, pacing, ACK-delivery, smoothness, parity or",
            "performance result. The frame payload in use sends one identical",
            "brightness-0 frame per call, so firmware that short-circuits an",
            "unchanged frame does almost no work; the counters below cannot be read",
            "as rendering behaviour.",
            "",
        ]
    )
    animation = summary["animation"]
    if not animation:
        lines.append("- No animation observations recorded.")
    for alias in sorted(animation):
        entry = animation[alias]
        lines.append(
            f"- `{alias}`: restored={entry['restored']} "
            f"restoration_verified={entry['restoration_verified']}; "
            f"rates={entry['rates']}."
        )
    lines.extend(["", "## Advertisement staleness (THREAD-04)", ""])
    staleness = summary["staleness"]
    if not staleness:
        lines.append("- No staleness experiment recorded.")
    for alias in sorted(staleness):
        lines.append(f"- `{alias}`: {staleness[alias]}")
    lines.extend(["", "## Six-class ledger (THREAD-05)", ""])
    ledger = summary["class_ledger"]
    for device_class in sorted(ledger["classes"]):
        entry = ledger["classes"][device_class]
        lines.append(f"- `{device_class}`: {entry['disposition']} -- {entry}")
    if ledger["missing_classes"]:
        lines.append(f"- Missing dispositions: {ledger['missing_classes']}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Plan 14-04: hermetically-proven physical protocol mode drivers
# (THREAD-01..05, D-01..D-20). Every driver below is production-quality and
# import-safe -- it performs no I/O on import -- but DRIVING it against real
# hardware is Plan 14-06's job. Each driver is split into an injectable
# orchestration loop (fully hermetic: schedules, resume, restoration,
# schema/privacy) and a thin production glue function that calls the real
# `discover()`/`discover_mdns()`/`DeviceConnection`/`Animator` surfaces
# exactly as exposed (see the plan's <interfaces> block). This split is what
# makes the loops testable with fakes while the glue itself is exercised
# against the real production path in a handful of focused tests.
# ---------------------------------------------------------------------------


class RosterDriftError(ValueError):
    """An observed alias/identity falls outside the frozen expected roster.

    Raised the moment a hardware call resolves an identity to an alias that
    is not part of the manifest's immutable inventory -- the session stops
    immediately rather than silently absorbing an unexpected device (D-19,
    T-14-14: only one mapped inventory may ever enter tracked evidence).
    """


# THREAD-05 inventory authority: these three classes must each have at least
# one expected alias, and MatrixLight must have at least two DISTINCT
# aliases (the roster covers two physically different MatrixLight products).
# InfraredLight/HevLight are never inventory entries -- the manifest schema
# already restricts every entry's device_class to _AVAILABLE_DEVICE_CLASSES
# -- so they can only ever close via a named_gap disposition, never a roster
# omission mistaken for one.
_REQUIRED_SINGLE_ALIAS_CLASSES: frozenset[str] = frozenset(
    {"Light", "MultiZoneLight", "CeilingLight"}
)
_MATRIX_MINIMUM_ALIASES = 2


def expected_roster_by_class(
    inventory: Sequence[Mapping[str, Any]],
) -> dict[str, frozenset[str]]:
    """Group the frozen manifest inventory's aliases by device_class."""
    by_class: dict[str, set[str]] = defaultdict(set)
    for entry in inventory:
        by_class[entry["device_class"]].add(entry["alias"])
    return {
        device_class: frozenset(aliases) for device_class, aliases in by_class.items()
    }


def expected_alias_roster(inventory: Sequence[Mapping[str, Any]]) -> frozenset[str]:
    """Return every alias named anywhere in the frozen manifest inventory."""
    return frozenset(entry["alias"] for entry in inventory)


def validate_expected_roster(inventory: Sequence[Mapping[str, Any]]) -> None:
    """Raise ``ValueError`` unless the roster is complete BEFORE any hardware call.

    This is independent of any discovery result (THREAD-05 inventory
    authority): the roster is operator-approved evidence of what hardware
    exists, not a summary of what one sweep happened to see. It must name at
    least one alias for each of ``Light``, ``MultiZoneLight`` and
    ``CeilingLight``, plus two DISTINCT ``MatrixLight`` aliases. A roster
    that omits a required class or names only one MatrixLight alias is
    rejected outright -- collection must never start against an incomplete
    roster and later launder the gap as a named gap, since named gaps are
    schema-restricted to InfraredLight/HevLight alone.
    """
    by_class = expected_roster_by_class(inventory)
    missing = sorted(
        device_class
        for device_class in _REQUIRED_SINGLE_ALIAS_CLASSES
        if not by_class.get(device_class)
    )
    if missing:
        raise ValueError(f"expected roster is missing required class(es): {missing}")
    if len(by_class.get("MatrixLight", frozenset())) < _MATRIX_MINIMUM_ALIASES:
        raise ValueError(
            "expected roster must name at least two distinct MatrixLight aliases"
        )


# ---------------------------------------------------------------------------
# Discovery physical mode (THREAD-01, D-01/D-02).
# ---------------------------------------------------------------------------


async def run_discovery_session(
    *,
    session_dir: Path,
    manifest: Mapping[str, Any],
    alias_map: Mapping[str, str],
    discover_fn: Callable[..., Any],
    discover_mdns_fn: Callable[..., Any],
    timeout: float = DISCOVERY_TIMEOUT,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    confounders: Sequence[str] = (),
) -> None:
    """Run the frozen six paired, order-alternated discovery rounds (D-01/D-02).

    Resumable: a round/source pair already present in the journal is skipped
    rather than re-run, so an interrupted session picks up exactly where it
    left off without repeating or overwriting history (D-18). ``alias_map``
    resolves each discovered device's canonical serial to its privacy-safe
    alias in memory only -- an identity outside the frozen expected roster
    raises :class:`RosterDriftError` and stops the session immediately
    rather than silently mixing an unexpected device into tracked evidence.
    An identity present in ``alias_map`` but with no roster entry at all
    (nothing this session expects to see) is the same drift condition;
    an identity entirely absent from ``alias_map`` is simply not resolvable
    and is skipped -- Phase 14 tracks only its own operator-approved fleet.

    Args:
        session_dir: The session's evidence directory (holds the journal).
        manifest: The frozen session manifest (schedules, identifiers).
        alias_map: Canonical serial -> privacy-safe alias, resolved in
            memory only; never written to any tracked file.
        discover_fn: Callable with the exact ``discover(timeout=...)`` async
            generator contract. Injectable for hermetic tests; production
            callers pass ``lifx.api.discover``.
        discover_mdns_fn: Same contract for ``discover_mdns``.
        timeout: Per-call discovery timeout passed straight through.
        sleep: Injectable ``asyncio.sleep``-shaped awaitable for the
            pre-generated inter-round jitter schedule.
        confounders: Closed-vocabulary environmental confounders to record
            on every round's outcome.
    """
    journal_path = session_dir / DISCOVERY_FILENAME
    expected = expected_alias_roster(manifest["inventory"])
    already_recorded = {
        (row["source"], row["round"]) for row in reload_discovery_events(journal_path)
    }
    session_id = manifest["session_id"]
    protocol_version = manifest["protocol_version"]
    revision = manifest["revision"]
    gaps = manifest["discovery_round_gaps_s"]

    for round_number in range(1, DISCOVERY_ROUNDS + 1):
        first_source = "discover" if round_number % 2 == 1 else "discover_mdns"
        second_source = "discover_mdns" if first_source == "discover" else "discover"
        for source in (first_source, second_source):
            if (source, round_number) in already_recorded:
                continue
            call = discover_fn if source == "discover" else discover_mdns_fn
            devices: list[str] = []
            outcome = "success"
            try:
                async for device in call(timeout=timeout):
                    serial = Serial.from_string(device.serial).to_string()
                    alias = alias_map.get(serial)
                    if alias is None:
                        continue
                    if alias not in expected:
                        raise RosterDriftError(
                            "observed alias outside the frozen expected roster "
                            f"in round {round_number} ({source})"
                        )
                    devices.append(alias)
                outcome = "success" if devices else "empty"
            except asyncio.CancelledError:
                row = build_discovery_event(
                    session_id=session_id,
                    protocol_version=protocol_version,
                    revision=revision,
                    round_number=round_number,
                    source=source,
                    outcome="interrupted",
                    devices=[],
                    provenance="physical",
                    confounders=confounders,
                )
                append_discovery_event(journal_path, row)
                raise
            except (LifxNetworkError, LifxConnectionError, OSError):
                outcome = "failed"
                devices = []
            row = build_discovery_event(
                session_id=session_id,
                protocol_version=protocol_version,
                revision=revision,
                round_number=round_number,
                source=source,
                outcome=outcome,
                devices=devices,
                provenance="physical",
                confounders=confounders,
            )
            append_discovery_event(journal_path, row)
        if round_number < DISCOVERY_ROUNDS:
            gap_index = round_number - 1
            if gap_index < len(gaps):
                await sleep(gaps[gap_index])


# ---------------------------------------------------------------------------
# Request physical mode (THREAD-02, D-03/D-05..D-08).
# ---------------------------------------------------------------------------

_REQUEST_SEND_ERRORS: tuple[type[BaseException], ...] = (
    LifxConnectionError,
    LifxNetworkError,
    LifxProtocolError,
    OSError,
)


async def run_one_request_trial(
    device: Light,
    captured_power: int,
) -> tuple[str, dict[str, Any] | None]:
    """Drive one real no-op ``SetPower`` trial through the production path (D-05).

    Calls ``device.set_power(captured_power)`` -- the device's own captured
    current power level, so the trial is self-restoring by construction --
    while the private request observer is attached to the current task, then
    derives D-07's logical completion latency and winning-sequence
    acknowledgement RTT directly from the captured in-memory events (no
    journal round trip is needed here; :func:`derive_request_result` already
    proved lossless round-tripping in Plan 14-01).

    Returns:
        ``("completed", derived)`` on success, or ``(outcome, None)`` for
        ``"timeout"``/``"send_error"`` -- both remain first-class evidence
        per D-03, never silently dropped.
    """
    try:
        with _capture_request_observations() as sink:
            await device.set_power(captured_power)
    except LifxTimeoutError:
        return "timeout", None
    except _REQUEST_SEND_ERRORS:
        return "send_error", None

    events = [
        {
            "category": observation.category,
            "sequence": observation.sequence,
            "timestamp_ns": observation.timestamp_ns,
            "thread_connection": observation.thread_connection,
        }
        for observation in sink.observations
    ]
    try:
        derived = derive_request_result(events)
    except ValueError:
        # An accepted response arrived with no matching sent/logical_start
        # event -- treat as a send-side anomaly rather than fabricate timing.
        return "send_error", None
    return "completed", derived


async def run_request_trials(
    *,
    session_dir: Path,
    manifest: Mapping[str, Any],
    alias: str,
    get_power: Callable[[], Awaitable[int]],
    run_trial: Callable[[int], Awaitable[tuple[str, dict[str, Any] | None]]],
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    confounders: Sequence[str] = (),
) -> None:
    """Run the frozen 100-trial request series for one alias (D-03/D-05/D-06).

    Resumable per trial (D-18): an already-journaled trial number is
    skipped. Applies the Plan 14-03 ``power_out_of_range`` preflight stop
    rule -- a captured power outside ``{0, 65535}`` is not a real binary
    state to replay, so EVERY remaining trial for this alias is recorded as
    ``power_out_of_range`` without attempting a single mutating call.

    Args:
        session_dir: The session's evidence directory (holds the journal).
        manifest: The frozen session manifest (schedules, identifiers).
        alias: The privacy-safe alias this series is evidence for.
        get_power: Awaitable capture of the device's current power (D-05
            preflight). Injectable so a fake fleet can force the
            ``power_out_of_range`` path deterministically.
        run_trial: Awaitable driving one trial given the captured power,
            returning ``(outcome, derived)`` exactly like
            :func:`run_one_request_trial`. Injectable for hermetic tests;
            production callers bind ``run_one_request_trial`` to a real
            connected device.
        sleep: Injectable ``asyncio.sleep``-shaped awaitable for the
            pre-generated inter-trial jitter schedule.
        confounders: Closed-vocabulary environmental confounders to record
            on every trial outcome.
    """
    journal_path = session_dir / REQUESTS_FILENAME
    session_id = manifest["session_id"]
    protocol_version = manifest["protocol_version"]
    revision = manifest["revision"]
    gaps = manifest["request_trial_gaps_s"]
    already_recorded = {
        row["trial"]
        for row in reload_request_trial_events(journal_path)
        if row["alias"] == alias
    }

    def _append(trial: int, outcome: str, derived: Mapping[str, Any] | None) -> None:
        row = build_request_trial_event(
            session_id=session_id,
            protocol_version=protocol_version,
            revision=revision,
            alias=alias,
            trial=trial,
            outcome=outcome,
            logical_latency_ns=derived["logical_latency_ns"] if derived else None,
            ack_rtt_ns=derived["ack_rtt_ns"] if derived else None,
            thread_connection=derived["thread_connection"] if derived else None,
            provenance="physical",
            confounders=confounders,
        )
        append_request_trial_event(journal_path, row)

    remaining = [
        trial for trial in range(1, REQUEST_TRIALS + 1) if trial not in already_recorded
    ]
    if not remaining:
        return

    captured_power = await get_power()
    if not is_binary_power(captured_power):
        for trial in remaining:
            _append(trial, "power_out_of_range", None)
        return

    for position, trial in enumerate(remaining):
        outcome, derived = await run_trial(captured_power)
        _append(trial, outcome, derived)
        if position < len(remaining) - 1:
            gap_index = trial - 1
            if gap_index < len(gaps):
                await sleep(gaps[gap_index])


# ---------------------------------------------------------------------------
# Animation physical mode (THREAD-03, D-09..D-16). Deliberately secondary and
# non-gating: the WiFi-only animation spike has no authority here (research
# banner). Every counter this driver records is transport-side only -- it
# never infers rendering, delivery, or a performance verdict.
# ---------------------------------------------------------------------------


def _placeholder_rate_row(fps: int, duration_s: float, outcome: str) -> dict[str, Any]:
    """A zero-count rate row for a rate that never ran (D-12: honest, not omitted)."""
    return {
        "fps": fps,
        "duration_s": duration_s,
        "outcome": outcome,
        "offered": 0,
        "packets_sent": 0,
        "total_time_ms": 0.0,
        "gated": 0,
        "acks_outstanding": 0,
        "failed": 0,
    }


async def _run_one_animation_rate(
    send_frame: Callable[[], AnimatorStats],
    *,
    fps: int,
    duration_s: float,
    now: Callable[[], float],
    sleep: Callable[[float], Awaitable[None]],
) -> dict[str, Any]:
    """Offer frames for one fixed rate/duration and tally current-behaviour stats.

    Calls the caller-bound synchronous ``send_frame()`` directly from this
    async loop and ``await``s only between the absolute per-frame offer
    deadlines (never a thread/executor wrapper, per D-13). Every field
    tallied here already exists on ``AnimatorStats`` (``packets_sent``,
    ``total_time_ms``, ``gated``, ``acks_outstanding``) -- ``offered`` and
    ``failed`` are the only script-owned counters, and a raised exception
    from ``send_frame()`` is counted as ``failed`` while the rate itself
    still completes (D-12: zero useful throughput is a valid completed
    result and can never fail Phase 14). ``asyncio.CancelledError``
    propagates unchanged -- the caller pads an interrupted rate.
    """
    frame_interval = 1.0 / fps
    deadline = now() + duration_s
    offered = 0
    packets_sent = 0
    total_time_ms = 0.0
    gated = 0
    failed = 0
    last_acks_outstanding = 0
    next_offer = now()
    while now() < deadline:
        wait = next_offer - now()
        if wait > 0:
            await sleep(wait)
        offered += 1
        try:
            stats = send_frame()
        except Exception:
            failed += 1
        else:
            total_time_ms += stats.total_time_ms
            last_acks_outstanding = stats.acks_outstanding
            if stats.gated:
                gated += 1
            else:
                packets_sent += stats.packets_sent
        next_offer += frame_interval
    return {
        "fps": fps,
        "duration_s": duration_s,
        "outcome": "completed",
        "offered": offered,
        "packets_sent": packets_sent,
        "total_time_ms": total_time_ms,
        "gated": gated,
        "acks_outstanding": last_acks_outstanding,
        "failed": failed,
    }


async def run_animation_observation(
    *,
    session_dir: Path,
    manifest: Mapping[str, Any],
    alias: str,
    capture_state: Callable[[], Awaitable[CapturedState]],
    check_liveness: Callable[[], Awaitable[bool]],
    make_send_frame: Callable[[], Awaitable[Callable[[], AnimatorStats]]],
    restore: Callable[[CapturedState], Awaitable[RestoreOutcome]],
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    confounders: Sequence[str] = (),
) -> dict[str, Any]:
    """Run the frozen D-10 ascending 1/2/5 FPS observation for one alias.

    Captures state and checks liveness BEFORE the attempt, then restores and
    reads back on every exit path (success, ordinary exception, or
    cancellation) per D-14 -- the ``finally`` block below always runs.
    ``make_send_frame()`` is awaited ONCE per alias attempt (mirroring "use a
    fresh ``Animator``" -- production callers construct one ``Animator``, an
    async operation for Matrix/MultiZone devices, and return
    ``lambda: animator.send_frame(frame)`` bound to it, reused across all
    three rates); a fake fleet can inject a callable that raises, returns
    gated stats, or otherwise proves every branch without a socket.

    Cancellation mid-attempt (construction or any rate) never loses the
    schema's fixed three-rate shape: every rate not actually completed is
    padded with a zero-count ``"interrupted"`` placeholder BEFORE the row is
    built, so the row is always valid to append even on the cancelled exit
    path, and the original cancellation is re-raised only after the event
    is safely recorded and the device is restored.

    Returns:
        The already-validated animation event row, also appended to the
        session's animation journal (D-18: one row per alias; an
        already-recorded alias is a no-op).
    """
    journal_path = session_dir / ANIMATION_FILENAME
    session_id = manifest["session_id"]
    protocol_version = manifest["protocol_version"]
    revision = manifest["revision"]

    existing = [
        row for row in reload_animation_events(journal_path) if row["alias"] == alias
    ]
    if existing:
        return existing[0]

    pre_liveness = await check_liveness()
    captured = await capture_state()
    rates: list[dict[str, Any]] = []
    pending_cancellation: BaseException | None = None
    try:
        try:
            send_frame = await make_send_frame()
        except asyncio.CancelledError as exc:
            pending_cancellation = exc
        except Exception:
            # A fresh Animator could not even be built for this alias --
            # every rate is a bounded, honest "failed" attempt rather than
            # aborting without any evidence at all (D-12/D-15).
            rates = [
                _placeholder_rate_row(fps, duration_s, "failed")
                for fps, duration_s in ANIMATION_SCHEDULE
            ]
        else:
            for fps, duration_s in ANIMATION_SCHEDULE:
                try:
                    rates.append(
                        await _run_one_animation_rate(
                            send_frame,
                            fps=fps,
                            duration_s=duration_s,
                            now=now,
                            sleep=sleep,
                        )
                    )
                except asyncio.CancelledError as exc:
                    pending_cancellation = exc
                    break

        while len(rates) < len(ANIMATION_SCHEDULE):
            fps, duration_s = ANIMATION_SCHEDULE[len(rates)]
            rates.append(_placeholder_rate_row(fps, duration_s, "interrupted"))
    finally:
        restore_outcome = await restore(captured)
        post_liveness = await check_liveness()

    row = build_animation_event(
        session_id=session_id,
        protocol_version=protocol_version,
        revision=revision,
        alias=alias,
        pre_liveness=pre_liveness,
        rates=rates,
        post_liveness=post_liveness,
        restored=restore_outcome.restored,
        restoration_verified=restore_outcome.restoration_verified,
        provenance="physical",
        confounders=confounders,
    )
    append_animation_event(journal_path, row)
    if pending_cancellation is not None:
        raise pending_cancellation
    return row


# ---------------------------------------------------------------------------
# Staleness physical mode (THREAD-04, D-04). Absence requires BOTH discover()
# unicast-liveness AND discover_mdns() advertisement to miss the target on
# the same poll (see _poll_is_absent's docstring for why an either-leg
# predicate would measure the wrong thing entirely).
# ---------------------------------------------------------------------------


def _confirmed_expiry_poll(
    polls: Sequence[Mapping[str, Any]], confirm_polls: int
) -> int | None:
    """Return the poll number where N consecutive both-legs-absent polls close."""
    for index in range(confirm_polls, len(polls) + 1):
        window = polls[index - confirm_polls : index]
        if all(_poll_is_absent(poll) for poll in window):
            return index
    return None


async def run_staleness_experiment(
    *,
    session_dir: Path,
    manifest: Mapping[str, Any],
    alias: str,
    disconnect_ns: int,
    poll: Callable[[], Awaitable[tuple[bool, bool]]],
    restore_available: Callable[[], Awaitable[tuple[int, float] | None]],
    should_stop_early: Callable[[], Awaitable[bool]] | None = None,
    on_poll: Callable[[Sequence[Mapping[str, Any]]], Awaitable[None]] | None = None,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    interval_s: float = STALENESS_POLL_INTERVAL_S,
    confirm_polls: int = STALENESS_CONFIRM_ABSENT_POLLS,
    cap_s: float = STALENESS_CAP_S,
    confounders: Sequence[str] = (),
) -> dict[str, Any]:
    """Poll both discovery legs on an absolute 60-second cadence until D-04 closes.

    Absolute scheduling means a slow ``poll()`` call never compounds delay
    across the run -- the next poll's deadline is always
    ``start + poll_index * interval_s``, and a call that overran its own
    window is recorded (via the ``unquiesced_environment`` confounder) but
    never allowed to overlap the next scheduled poll. The experiment closes
    the moment ``confirm_polls`` consecutive both-legs-absent polls are
    seen (``confirmed_expiry``), the moment ``should_stop_early`` reports
    the device visibly restored (``restored_before_expiry``), or the
    ``cap_s`` three-hour boundary is reached without confirmation
    (``censored`` -- explicitly NOT a pass or a fail, per D-04). A
    cancellation mid-poll is recorded as ``interrupted`` with whatever polls
    were already collected, then re-raised. Restoration detection (the
    ``restore_available`` call, made only once disposition is otherwise
    determined) is deliberately unbounded on this module's side (T-14-06
    change 2): it returns ``(restored_available_ns, restoration_duration_s)``
    once both discovery legs report present, or ``None`` only when the
    caller could not attempt restoration at all (for example an
    operator-supplied power-on script hard-failing). A cancellation raised
    from inside ``restore_available`` -- an operator's Ctrl-C during an
    unbounded restoration wait -- is caught by the very same
    ``except asyncio.CancelledError`` branch below, so it closes exactly
    like a cancellation mid-poll: ``interrupted``, with the polls already
    collected persisted, then re-raised.

    ``on_poll``, if supplied, is awaited with the full poll list collected
    so far immediately after every poll (T-14-06 change 3). It is purely a
    progress-reporting hook -- it never influences disposition -- so a
    caller can drive live stderr progress for what is otherwise a silent
    up-to-three-hour blocking call without this module needing to know
    anything about how that progress is rendered.

    Returns:
        The already-validated staleness event row, also appended to the
        session's staleness journal.
    """
    journal_path = session_dir / STALENESS_FILENAME
    session_id = manifest["session_id"]
    protocol_version = manifest["protocol_version"]
    revision = manifest["revision"]

    existing = [
        row for row in reload_staleness_events(journal_path) if row["alias"] == alias
    ]
    if existing:
        return existing[0]

    start = now()
    polls: list[dict[str, Any]] = []
    overrun_detected = False
    poll_index = 0
    disposition = "interrupted"
    try:
        while True:
            poll_index += 1
            elapsed_s = poll_index * interval_s
            target = start + elapsed_s
            wait = target - now()
            if wait > 0:
                await sleep(wait)
            poll_started = now()
            discover_present, discover_mdns_present = await poll()
            if now() - poll_started > interval_s:
                overrun_detected = True
            polls.append(
                {
                    "poll": poll_index,
                    "elapsed_s": elapsed_s,
                    "discover_present": discover_present,
                    "discover_mdns_present": discover_mdns_present,
                }
            )
            if on_poll is not None:
                await on_poll(tuple(polls))
            if _confirmed_expiry_poll(polls, confirm_polls) is not None:
                disposition = "confirmed_expiry"
                break
            if should_stop_early is not None and await should_stop_early():
                disposition = "restored_before_expiry"
                break
            if elapsed_s >= cap_s:
                disposition = "censored"
                break
    except asyncio.CancelledError:
        # Cancelled DURING absence detection, before any disposition was
        # determined: the whole run is interrupted.
        disposition = "interrupted"
        row = build_staleness_event(
            session_id=session_id,
            protocol_version=protocol_version,
            revision=revision,
            alias=alias,
            disconnect_ns=disconnect_ns,
            polls=polls,
            disposition=disposition,
            restored_available_ns=None,
            restoration_duration_s=None,
            provenance="physical",
            confounders=confounders,
        )
        append_staleness_event(journal_path, row)
        raise

    # The absence-detection loop above is now closed with a final
    # disposition (confirmed_expiry/censored/restored_before_expiry). A
    # cancellation from here on -- an operator's Ctrl-C during the
    # deliberately UNBOUNDED restoration wait (T-14-06 change 2) is the
    # realistic case -- must NOT retroactively relabel that already-closed
    # disposition as "interrupted": the schema forbids a disposition other
    # than confirmed_expiry when the polls already contain a confirmed
    # three-pair-absent window, and semantically the absence-detection
    # protocol genuinely did close cleanly here. Only restoration itself
    # stayed unknown, so `restored_available_ns`/`restoration_duration_s`
    # are what stay null.
    try:
        restore_result = await restore_available()
    except asyncio.CancelledError:
        row = build_staleness_event(
            session_id=session_id,
            protocol_version=protocol_version,
            revision=revision,
            alias=alias,
            disconnect_ns=disconnect_ns,
            polls=polls,
            disposition=disposition,
            restored_available_ns=None,
            restoration_duration_s=None,
            provenance="physical",
            confounders=confounders,
        )
        append_staleness_event(journal_path, row)
        raise

    if restore_result is None:
        restored_available_ns: int | None = None
        restoration_duration_s: float | None = None
    else:
        restored_available_ns, restoration_duration_s = restore_result

    effective_confounders = set(confounders)
    if overrun_detected:
        effective_confounders.add("unquiesced_environment")

    row = build_staleness_event(
        session_id=session_id,
        protocol_version=protocol_version,
        revision=revision,
        alias=alias,
        disconnect_ns=disconnect_ns,
        polls=polls,
        disposition=disposition,
        restored_available_ns=restored_available_ns,
        restoration_duration_s=restoration_duration_s,
        provenance="physical",
        confounders=sorted(effective_confounders),
    )
    append_staleness_event(journal_path, row)
    return row


# ---------------------------------------------------------------------------
# Operator-supplied power-off/power-on scripts (T-14-06 change 1). The tool
# drives the physical power cycle itself instead of an operator manually
# timing a disconnect and pasting a captured timestamp: it knows the exact
# disconnect instant (captured immediately after the power-off script exits
# 0) and can attempt restoration itself once the experiment closes.
# ---------------------------------------------------------------------------


class PowerScriptError(RuntimeError):
    """One operator-supplied power-off/power-on script hard-stopped.

    Both the failing ``stage`` (``"off"``/``"on"``) and a bounded,
    non-identifying ``reason`` category (``missing_or_not_executable``,
    ``timeout``, or ``exit_code_<N>``) are exposed so a caller can build an
    explicit JSON verdict without re-deriving them. ``path`` is the
    operator's own local script path -- filesystem detail, never a device
    identifier -- so it is safe to surface directly in a JSON verdict or
    stderr progress line.
    """

    def __init__(self, *, stage: str, path: str, reason: str) -> None:
        self.stage = stage
        self.path = path
        self.reason = reason
        super().__init__(f"power-{stage} script {reason}: {path}")


# Generous enough for a slow smart-plug/relay driver's own network round
# trip, short enough that a hung script fails fast rather than stalling a
# live physical session indefinitely.
_POWER_SCRIPT_TIMEOUT_S: float = 30.0


def _run_power_script(
    path: Path, *, stage: str, timeout_s: float = _POWER_SCRIPT_TIMEOUT_S
) -> None:
    """Execute one operator-supplied power-{off,on} script directly, never via a shell.

    Raises :class:`PowerScriptError` for a missing/non-executable script, a
    non-zero exit, or a timeout -- every one of these is a hard stop for the
    caller. The script is invoked as a literal one-element argv list (never
    ``shell=True``, never string interpolation), and its own stdout/stderr
    are captured rather than inherited so a chatty script can never pollute
    this CLI's single-JSON-object stdout contract (T-14-06 change 3).
    """
    resolved = path.expanduser()
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise PowerScriptError(
            stage=stage, path=str(path), reason="missing_or_not_executable"
        )
    try:
        completed = subprocess.run(  # nosec B603
            [str(resolved)],
            timeout=timeout_s,
            capture_output=True,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise PowerScriptError(stage=stage, path=str(path), reason="timeout") from error
    except OSError as error:
        # The operator hands us an arbitrary path and the OS decides whether
        # it is runnable. Windows raises WinError 193 for a file it cannot
        # execute (a shebang script, say -- Windows has no shebang support),
        # and os.access(X_OK) cannot predict that because it reports every
        # existing file as executable there. An unrunnable script must be a
        # hard stop reported like every other one, not a raw traceback out of
        # a verb whose contract is one JSON object.
        raise PowerScriptError(
            stage=stage, path=str(path), reason="not_executable"
        ) from error
    if completed.returncode != 0:
        raise PowerScriptError(
            stage=stage,
            path=str(path),
            reason=f"exit_code_{completed.returncode}",
        )


# ---------------------------------------------------------------------------
# Roster-driven six-class ledger, evidence-language vocabulary and staged-
# index validation (THREAD-05, D-15/D-18/D-20). The ledger below is the
# authoritative closure derivation: it is computed from the manifest's
# frozen roster and the journals themselves, never trusted from a
# caller-supplied closure claim or the subset of devices one sweep observed.
# ---------------------------------------------------------------------------

# Free-text evidence language that would overstate what THREAD-03's
# deliberately secondary, non-gating observation -- or any other Phase 14
# result -- can support (SPEC/CONTEXT: no authoritative Thread benchmark, no
# universal performance claim, no retuning from confounded measurements).
# The only genuinely free-text field in the whole schema is `gap_reason`
# (14-02 SUMMARY, "Known Coverage Gaps") -- this vocabulary check is scoped
# there.
_FORBIDDEN_EVIDENCE_VOCABULARY: frozenset[str] = frozenset(
    {
        "benchmark",
        "regression gate",
        "universal",
        "performance limit",
        "guaranteed",
        "tuning",
        "ceiling",
        "authoritative",
    }
)


def contains_forbidden_vocabulary(text: str) -> str | None:
    """Return the first forbidden benchmark/tuning phrase found in ``text``."""
    lowered = text.casefold()
    for phrase in sorted(_FORBIDDEN_EVIDENCE_VOCABULARY):
        if phrase in lowered:
            return phrase
    return None


def _alias_has_physical_discovery_evidence(
    alias: str, discovery_rows: Sequence[Mapping[str, Any]]
) -> bool:
    return any(
        row["provenance"] == "physical" and alias in row["devices"]
        for row in discovery_rows
    )


def _alias_has_complete_physical_requests(
    alias: str, request_rows: Sequence[Mapping[str, Any]]
) -> bool:
    trials = {
        row["trial"]
        for row in request_rows
        if row["alias"] == alias and row["provenance"] == "physical"
    }
    return len(trials) == REQUEST_TRIALS


def derive_class_ledger_from_roster(
    *,
    inventory: Sequence[Mapping[str, Any]],
    discovery_rows: Sequence[Mapping[str, Any]],
    request_rows: Sequence[Mapping[str, Any]],
    closure_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Derive the six-class ledger from the frozen roster and journals ONLY.

    Never trusts a caller-supplied closure claim or the subset of devices a
    sweep happened to observe (THREAD-05 inventory authority). An
    ``evidence_backed`` disposition for an available class requires EVERY
    expected alias of that class to carry physical-provenance discovery
    evidence and all ``REQUEST_TRIALS`` physical request trials. A single
    missing or incomplete alias keeps the WHOLE class ``incomplete``: it can
    never substitute a named gap, and a named gap can never appear for a
    currently available class (schema already enforces this at the row
    level; this derivation enforces it at the ledger level too).

    Animation evidence plays no part in this derivation. Thread animation is
    a recorded scope boundary, not a closure requirement (THREAD-03): the
    library will not support sustained Thread animation, so an animation
    attempt is neither required nor sufficient to close a class. Animation
    rows still exist as a separate, non-gating journal (``14-ANIMATION.jsonl``)
    for whatever evidence is worth keeping -- ``generate_summary()`` still
    reports it -- but ``derive_class_ledger_from_roster`` intentionally takes
    no ``animation_rows`` parameter, so a caller cannot even accidentally
    make closure depend on it again.
    """
    for row in discovery_rows:
        _validate_discovery_event(row)
    for row in request_rows:
        _validate_request_trial_event(row)
    for row in closure_rows:
        _validate_closure_event(row)

    by_class = expected_roster_by_class(inventory)
    named_gap_rows = {
        row["device_class"]: row
        for row in closure_rows
        if row["disposition"] == "named_gap"
    }

    classes: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for device_class in sorted(_DEVICE_CLASSES):
        if device_class in _NAMED_GAP_DEVICE_CLASSES:
            gap_row = named_gap_rows.get(device_class)
            if gap_row is None:
                missing.append(device_class)
                continue
            classes[device_class] = {
                "disposition": "named_gap",
                "aliases": [],
                "gap_reason": gap_row["gap_reason"],
                "gap_recorded_date": gap_row["gap_recorded_date"],
            }
            continue

        aliases = sorted(by_class.get(device_class, frozenset()))
        if aliases and all(
            _alias_has_physical_discovery_evidence(alias, discovery_rows)
            and _alias_has_complete_physical_requests(alias, request_rows)
            for alias in aliases
        ):
            classes[device_class] = {
                "disposition": "evidence_backed",
                "aliases": aliases,
                "gap_reason": None,
                "gap_recorded_date": None,
            }
        else:
            missing.append(device_class)

    return {
        "schema_version": 1,
        "kind": "class_ledger",
        "classes": classes,
        "complete": not missing,
        "missing_classes": sorted(missing),
    }


# ---------------------------------------------------------------------------
# Staged-index evidence validation (D-19, T-14-11, Plan 14-06's commit gate).
# Reads the EXACT nine evidence blobs from Git's index after staging -- never
# working-tree bytes -- so a worktree-only edit after `git add` cannot slip
# past this check. Reports only bounded path + category failures; a matched
# private value is never printed (mirrors AGENTS.md's staged-diff inspection
# requirement, made mechanical).
# ---------------------------------------------------------------------------

_EVIDENCE_FILENAMES: tuple[str, ...] = (
    _MANIFEST_FILENAME,
    DISCOVERY_FILENAME,
    REQUESTS_FILENAME,
    ANIMATION_FILENAME,
    STALENESS_FILENAME,
    CLOSURE_FILENAME,
    SUMMARY_FILENAME,
    CLASS_LEDGER_FILENAME,
    REPORT_FILENAME,
)


@dataclass(frozen=True)
class StagedValidationFailure:
    """One bounded, privacy-safe staged-evidence failure. Never carries a value."""

    path: str
    category: str


def _run_git(*args: str) -> subprocess.CompletedProcess[bytes]:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required for staged-evidence validation")
    return subprocess.run(  # nosec B603
        [git, *args], check=True, capture_output=True, timeout=10
    )


def _posix_evidence_dir(evidence_dir: str) -> str:
    """Normalise a caller-supplied directory to Git's own path vocabulary.

    Git reports index paths with forward slashes on every platform, including
    Windows. An operator there naturally supplies a native path with
    backslashes, and `str(Path(...))` produces them too, so comparing the two
    directly matches nothing and every one of the nine evidence paths is
    reported missing. That is not a staging error, and reporting it as one
    would send someone hunting a file that is correctly staged.
    """
    return evidence_dir.replace("\\", "/").rstrip("/")


def _staged_paths_under(evidence_dir: str) -> list[str]:
    """Return every staged (index) path under ``evidence_dir``, as recorded by Git."""
    completed = _run_git("diff", "--cached", "--name-only")
    prefix = _posix_evidence_dir(evidence_dir) + "/"
    return [
        line
        for line in completed.stdout.decode("utf-8").splitlines()
        if line.startswith(prefix)
    ]


def _read_staged_blob(path: str) -> bytes:
    """Read one path's exact staged (index) bytes -- never the working tree."""
    return _run_git("show", f":{path}").stdout


def validate_staged_evidence(evidence_dir: str) -> list[StagedValidationFailure]:
    """Validate the exact nine staged evidence blobs under ``evidence_dir``.

    Reads from Git's index after ``git add``, not the working tree, so a
    post-stage edit is invisible to this check (proven by the hermetic
    tests, which stage safe content then mutate the working tree afterward
    and assert the inspected bytes never change). A missing or extra staged
    path is reported and validation stops before reading any blob content.
    Schema, roster-completeness and closure-ledger failures are reported by
    filename and a bounded category only -- never by matched content.
    """
    expected = {
        f"{_posix_evidence_dir(evidence_dir)}/{name}" for name in _EVIDENCE_FILENAMES
    }
    staged = set(_staged_paths_under(evidence_dir))

    failures = [
        StagedValidationFailure(path=path, category="missing_evidence_path")
        for path in sorted(expected - staged)
    ]
    failures.extend(
        StagedValidationFailure(path=path, category="unexpected_staged_path")
        for path in sorted(staged - expected)
    )
    if failures:
        return failures

    blobs: dict[str, bytes] = {}
    for name in _EVIDENCE_FILENAMES:
        path = f"{evidence_dir.rstrip('/')}/{name}"
        try:
            blobs[name] = _read_staged_blob(path)
        except subprocess.CalledProcessError:
            failures.append(
                StagedValidationFailure(path=path, category="unreadable_staged_blob")
            )
    if failures:
        return failures

    def _json_of(name: str) -> Any:
        return json.loads(blobs[name].decode("utf-8"))

    def _jsonl_of(name: str) -> list[dict[str, Any]]:
        return [
            json.loads(line)
            for line in blobs[name].decode("utf-8").splitlines()
            if line.strip()
        ]

    try:
        manifest = _json_of(_MANIFEST_FILENAME)
        _validate_manifest(manifest)
    except (ValueError, json.JSONDecodeError):
        return [
            StagedValidationFailure(
                path=_MANIFEST_FILENAME, category="schema_validation_failed"
            )
        ]

    try:
        validate_expected_roster(manifest["inventory"])
    except ValueError:
        failures.append(
            StagedValidationFailure(
                path=_MANIFEST_FILENAME, category="incomplete_expected_roster"
            )
        )

    journal_specs: tuple[tuple[str, Callable[[Mapping[str, Any]], None]], ...] = (
        (DISCOVERY_FILENAME, _validate_discovery_event),
        (REQUESTS_FILENAME, _validate_request_trial_event),
        (ANIMATION_FILENAME, _validate_animation_event),
        (STALENESS_FILENAME, _validate_staleness_event),
        (CLOSURE_FILENAME, _validate_closure_event),
    )
    journal_rows: dict[str, list[dict[str, Any]]] = {}
    for name, validator in journal_specs:
        try:
            rows = _jsonl_of(name)
            for row in rows:
                validator(row)
            journal_rows[name] = rows
        except (ValueError, json.JSONDecodeError):
            failures.append(
                StagedValidationFailure(path=name, category="schema_validation_failed")
            )

    if failures:
        return failures

    ledger = derive_class_ledger_from_roster(
        inventory=manifest["inventory"],
        discovery_rows=journal_rows[DISCOVERY_FILENAME],
        request_rows=journal_rows[REQUESTS_FILENAME],
        closure_rows=journal_rows[CLOSURE_FILENAME],
    )
    if not ledger["complete"]:
        failures.append(
            StagedValidationFailure(
                path=CLOSURE_FILENAME, category="six_class_ledger_incomplete"
            )
        )

    try:
        summary = _json_of(SUMMARY_FILENAME)
        class_ledger = _json_of(CLASS_LEDGER_FILENAME)
        report = blobs[REPORT_FILENAME].decode("utf-8")
    except (ValueError, json.JSONDecodeError):
        failures.append(
            StagedValidationFailure(
                path=SUMMARY_FILENAME, category="schema_validation_failed"
            )
        )
        return failures

    recomputed_summary = generate_summary(
        discovery_rows=journal_rows[DISCOVERY_FILENAME],
        request_rows=journal_rows[REQUESTS_FILENAME],
        animation_rows=journal_rows[ANIMATION_FILENAME],
        staleness_rows=journal_rows[STALENESS_FILENAME],
        closure_rows=journal_rows[CLOSURE_FILENAME],
    )
    recomputed_summary["class_ledger"] = ledger
    if summary != recomputed_summary:
        failures.append(
            StagedValidationFailure(
                path=SUMMARY_FILENAME, category="summary_not_regenerated_from_journals"
            )
        )
    if class_ledger != ledger:
        failures.append(
            StagedValidationFailure(
                path=CLASS_LEDGER_FILENAME,
                category="class_ledger_not_regenerated_from_journals",
            )
        )
    if report != generate_report(recomputed_summary):
        failures.append(
            StagedValidationFailure(
                path=REPORT_FILENAME, category="report_not_regenerated_from_journals"
            )
        )

    return failures


# ---------------------------------------------------------------------------
# Minimal CLI (D-17): manifest init and journal validation/regeneration only.
# Physical discovery/request/animation/staleness execution against real
# hardware is out of this plan's scope (Plan 14-06 supplies real rows) --
# import and a no-subcommand invocation therefore perform no I/O whatsoever.
# ---------------------------------------------------------------------------


def _emit(command: str, ok: bool, *, reason: str | None = None, **fields: Any) -> None:
    """Print exactly one privacy-safe JSON verdict object for one CLI invocation.

    Every subcommand's actual result is stated here explicitly -- never
    implied by ``$?`` alone (exit codes remain a secondary signal, per the
    project's "don't rely on $? parsing" directive). Every field passed in
    ``fields`` must already be privacy-safe (a validated alias, a bounded
    category, a count, or an already-validated manifest/ledger structure)
    -- this helper does not itself scrub content, so callers must never
    pass a raw identifier through it.
    """
    payload: dict[str, Any] = {"command": command, "ok": ok, "reason": reason}
    payload.update(fields)
    print(json.dumps(payload, sort_keys=True))


def _progress(message: str) -> None:
    """Emit one flushed stderr progress line.

    Stdout is reserved for exactly one JSON verdict per invocation (see
    ``_emit()``): a plan gate pipes stdout through ``jq -e``, so progress
    must never appear there (T-14-06 change 3). Flushed immediately -- an
    up-to-three-hour ``staleness`` run must never look like a silent hang.
    """
    print(message, file=sys.stderr, flush=True)


def _cli_init(args: argparse.Namespace) -> int:
    # The roster is a file, not an inline JSON argument: the operator authors
    # it by hand, revises it between sessions and must retype it verbatim on
    # every resume, none of which a shell-quoted argument makes tolerable. An
    # unreadable or malformed file states its verdict as JSON rather than
    # raising, so no failure mode of this gate is left to exit-code inference.
    if args.inventory:
        try:
            inventory = json.loads(args.inventory.expanduser().read_text("utf-8"))
        except OSError as error:
            _emit("init", False, reason="unreadable_inventory", detail=str(error))
            return 1
        except json.JSONDecodeError as error:
            _emit("init", False, reason="malformed_inventory", detail=str(error))
            return 1
    else:
        inventory = []
    # THREAD-05 roster authority (D-19, T-14-14): collection must never start
    # against an incomplete roster and later launder the gap as a named gap.
    # This runs BEFORE init_manifest() ever touches disk, so an incomplete
    # roster writes no manifest at all -- and states that verdict as JSON
    # rather than only an exit code (Defect 2).
    try:
        validate_expected_roster(inventory)
    except ValueError as error:
        _emit("init", False, reason="incomplete_expected_roster", detail=str(error))
        return 1
    revision = args.revision if args.revision else git_revision()
    manifest = init_manifest(
        args.session_dir,
        session_id=args.session_id,
        protocol_version=args.protocol_version,
        revision=revision,
        inventory=inventory,
        confounders=args.confound,
        seed=args.seed,
    )
    _emit("init", True, manifest=manifest)
    return 0


def _cli_validate(args: argparse.Namespace) -> int:
    """Inspect a session WITHOUT touching it. ``generate`` is the only producer.

    This used to write the summary, ledger and report unconditionally, which
    made merely inspecting a session mutate it -- and worse, corrupt it. The
    ledger it wrote came from ``generate_summary()``, whose ``class_ledger``
    is the closure-rows-only ``generate_class_ledger()``. Closure rows carry
    the two named gaps alone, so on a COMPLETE session that ledger declares
    the four available classes missing. ``_cli_generate`` and
    ``validate_staged_evidence`` both override it with the roster-derived
    ledger; this function did not, so running ``validate`` on a finished
    session overwrote a correct ``complete: true`` ledger with a wrong
    ``complete: false`` one, non-atomically, while printing ``ok: true``.

    Two changes close that. Nothing is written: an inspector that mutates its
    subject cannot be run safely against live evidence, and the atomicity
    ``generate`` gained is worthless if another verb writes the same paths
    unguarded. And the reported verdict now comes from
    ``derive_class_ledger_from_roster()``, the same source ``generate`` and
    the staged-index validator use, so the three cannot disagree about
    whether a session is complete.
    """
    session_dir = args.session_dir
    manifest = load_manifest(session_dir)  # Validates the manifest is intact.
    discovery_rows = reload_discovery_events(session_dir / DISCOVERY_FILENAME)
    request_rows = reload_request_trial_events(session_dir / REQUESTS_FILENAME)
    animation_rows = reload_animation_events(session_dir / ANIMATION_FILENAME)
    staleness_rows = reload_staleness_events(session_dir / STALENESS_FILENAME)
    closure_rows = reload_closure_events(session_dir / CLOSURE_FILENAME)
    ledger = derive_class_ledger_from_roster(
        inventory=manifest["inventory"],
        discovery_rows=discovery_rows,
        request_rows=request_rows,
        closure_rows=closure_rows,
    )
    _emit(
        "validate",
        True,
        counts={
            "discovery": len(discovery_rows),
            "requests": len(request_rows),
            "animation": len(animation_rows),
            "staleness": len(staleness_rows),
            "closure": len(closure_rows),
        },
        class_ledger={
            "complete": ledger["complete"],
            "missing_classes": ledger["missing_classes"],
        },
    )
    return 0


def _atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to a sibling temp file, then atomically replace ``path``."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _cli_generate(args: argparse.Namespace) -> int:
    """Validate, then write products ONLY when the roster-derived ledger is complete.

    Distinct from ``validate`` (which regenerates the legacy caller-supplied
    ``closure_rows`` ledger for a partial/in-progress session): ``generate``
    is the Task 3 authoritative path -- it requires a COMPLETE expected
    roster and derives the six-class ledger from the roster and journals
    directly. Nothing is written to the evidence directory unless that
    derived ledger is itself complete: an incomplete session reports its
    result and leaves every product file untouched, so a failed ``generate``
    run can never leave stale or half-written products on disk (generation
    is atomic: either every product is written, or none is).
    """
    session_dir = args.session_dir
    manifest = load_manifest(session_dir)
    validate_expected_roster(manifest["inventory"])
    discovery_rows = reload_discovery_events(session_dir / DISCOVERY_FILENAME)
    request_rows = reload_request_trial_events(session_dir / REQUESTS_FILENAME)
    animation_rows = reload_animation_events(session_dir / ANIMATION_FILENAME)
    staleness_rows = reload_staleness_events(session_dir / STALENESS_FILENAME)
    closure_rows = reload_closure_events(session_dir / CLOSURE_FILENAME)

    summary = generate_summary(
        discovery_rows=discovery_rows,
        request_rows=request_rows,
        animation_rows=animation_rows,
        staleness_rows=staleness_rows,
        closure_rows=closure_rows,
    )
    ledger = derive_class_ledger_from_roster(
        inventory=manifest["inventory"],
        discovery_rows=discovery_rows,
        request_rows=request_rows,
        closure_rows=closure_rows,
    )
    summary["class_ledger"] = ledger
    complete = bool(ledger["complete"])

    if not complete:
        _emit(
            "generate",
            False,
            reason="class_ledger_incomplete",
            missing_classes=ledger["missing_classes"],
            classes=ledger["classes"],
        )
        return 1

    report = generate_report(summary)
    _atomic_write(
        session_dir / SUMMARY_FILENAME,
        json.dumps(summary, sort_keys=True, indent=2) + "\n",
    )
    _atomic_write(
        session_dir / CLASS_LEDGER_FILENAME,
        json.dumps(summary["class_ledger"], sort_keys=True, indent=2) + "\n",
    )
    _atomic_write(session_dir / REPORT_FILENAME, report)

    _emit("generate", True, missing_classes=[], classes=ledger["classes"])
    return 0


def _cli_validate_staged(args: argparse.Namespace) -> int:
    failures = validate_staged_evidence(args.evidence_dir)
    ok = not failures
    _emit(
        "validate-staged",
        ok,
        reason=None if ok else "staged_evidence_invalid",
        failures=[
            {"path": failure.path, "category": failure.category} for failure in failures
        ],
    )
    return 0 if ok else 1


def _load_target_alias_map(path: Path) -> dict[str, str]:
    """Load an external raw-serial-to-alias mapping only into memory (D-19).

    Mirrors ``scripts/measure_merged_discovery.py``'s alias-map precedent:
    the file lives outside the repository, is read once into memory, and
    its raw identities never reach any tracked evidence.
    """
    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value:
        raise ValueError("alias map must be a non-empty JSON object")
    aliases: dict[str, str] = {}
    for raw_serial, raw_alias in value.items():
        serial = Serial.from_string(raw_serial).to_string()
        alias = validate_alias(raw_alias)
        if serial in aliases:
            raise ValueError("alias map contains a duplicate normalised serial")
        aliases[serial] = alias
    return aliases


async def _resolve_target_device(
    alias: str,
    alias_map: Mapping[str, str],
    *,
    timeout: float = DISCOVERY_TIMEOUT,
) -> Light:
    """Resolve one expected alias to a live device via one merged sweep.

    Tries ``discover()`` first, then ``discover_mdns()`` -- the same two
    legs THREAD-01 measures -- and returns the first device whose canonical
    serial maps to ``alias``. Raises ``RuntimeError`` (never a raw identity)
    if neither leg finds it.
    """
    from lifx.api import discover as api_discover
    from lifx.api import discover_mdns as api_discover_mdns

    for source in (api_discover, api_discover_mdns):
        async for device in source(timeout=timeout):
            serial = Serial.from_string(device.serial).to_string()
            if alias_map.get(serial) == alias:
                return cast("Light", device)
    raise RuntimeError(f"could not resolve expected alias to a live device: {alias!r}")


def _cli_discover(args: argparse.Namespace) -> int:
    from lifx.api import discover as api_discover
    from lifx.api import discover_mdns as api_discover_mdns

    manifest = load_manifest(args.session_dir)
    alias_map = _load_target_alias_map(args.alias_map)
    asyncio.run(
        run_discovery_session(
            session_dir=args.session_dir,
            manifest=manifest,
            alias_map=alias_map,
            discover_fn=api_discover,
            discover_mdns_fn=api_discover_mdns,
            confounders=args.confound,
        )
    )
    rows = reload_discovery_events(args.session_dir / DISCOVERY_FILENAME)
    rounds_expected = DISCOVERY_ROUNDS * 2
    _emit("discover", True, rounds_recorded=len(rows), rounds_expected=rounds_expected)
    return 0


async def _run_request_for_alias(
    *,
    session_dir: Path,
    manifest: Mapping[str, Any],
    alias: str,
    alias_map: Mapping[str, str],
    confound: Sequence[str],
) -> None:
    """Resolve one alias to a live device and run its 100-trial series.

    The single shared per-alias orchestration path for both ``--alias`` and
    ``--all``: neither CLI branch duplicates this resolve/connect/trial
    sequence, only how they react to its outcome (see ``_cli_request``).
    """
    device = await _resolve_target_device(alias, alias_map)
    async with device:
        await run_request_trials(
            session_dir=session_dir,
            manifest=manifest,
            alias=alias,
            get_power=device.get_power,
            run_trial=lambda captured_power: run_one_request_trial(
                device, captured_power
            ),
            confounders=confound,
        )


def _request_alias_summary(session_dir: Path, alias: str) -> dict[str, Any]:
    """Summarise one alias's on-disk request journal rows (source of truth).

    Read fresh from the journal rather than from in-memory state so a
    partially completed alias (an exception raised mid-series) still
    reports exactly what was actually recorded.
    """
    all_rows = reload_request_trial_events(session_dir / REQUESTS_FILENAME)
    alias_rows = [row for row in all_rows if row["alias"] == alias]
    outcomes = Counter(row["outcome"] for row in alias_rows)
    return {
        "alias": alias,
        "trials_recorded": len(alias_rows),
        "trials_expected": REQUEST_TRIALS,
        "outcomes": dict(sorted(outcomes.items())),
    }


def _cli_request(args: argparse.Namespace) -> int:
    """Run the 100-trial request series for one ``--alias`` or every ``--all`` alias.

    ``--alias`` behaves exactly as before: a raised exception propagates
    unchanged to ``main()``'s ``parser.error()`` handling. ``--all`` never
    lets one alias's failure hide another's evidence: a no-op ``SetPower``
    trial harms no device, so a ``power_out_of_range`` preflight stop or a
    resolve/network error for one alias is recorded and iteration CONTINUES
    through the remaining aliases, then reports ``ok: false`` naming every
    offending alias (Rule design: request trials are safe to keep running
    past a single alias's failure, unlike animation's mutating attempts).
    """
    manifest = load_manifest(args.session_dir)
    alias_map = _load_target_alias_map(args.alias_map)

    if args.alias is not None:
        asyncio.run(
            _run_request_for_alias(
                session_dir=args.session_dir,
                manifest=manifest,
                alias=args.alias,
                alias_map=alias_map,
                confound=args.confound,
            )
        )
        summary = _request_alias_summary(args.session_dir, args.alias)
        _emit(
            "request",
            True,
            alias=summary["alias"],
            trials_recorded=summary["trials_recorded"],
            trials_expected=summary["trials_expected"],
            outcomes=summary["outcomes"],
        )
        return 0

    aliases = sorted(entry["alias"] for entry in manifest["inventory"])
    results: list[dict[str, Any]] = []
    offending_aliases: list[str] = []
    for alias in aliases:
        error_name: str | None = None
        try:
            asyncio.run(
                _run_request_for_alias(
                    session_dir=args.session_dir,
                    manifest=manifest,
                    alias=alias,
                    alias_map=alias_map,
                    confound=args.confound,
                )
            )
        except (RuntimeError, OSError, LifxError) as error:
            error_name = type(error).__name__

        summary = _request_alias_summary(args.session_dir, alias)
        summary["error"] = error_name
        results.append(summary)
        if error_name is not None or summary["outcomes"].get("power_out_of_range", 0):
            offending_aliases.append(alias)

    ok = not offending_aliases
    _emit(
        "request",
        ok,
        reason=None if ok else "offending_aliases_present",
        aliases=aliases,
        results=results,
        offending_aliases=offending_aliases,
    )
    return 0 if ok else 1


async def _make_animation_send_frame(
    device: Light,
) -> Callable[[], AnimatorStats]:
    """Build a fresh Animator for ``device``'s class and bind one placeholder frame.

    No production animation change: this is exactly ``Animator.for_matrix``/
    ``for_multizone``/``for_light`` as already exposed (D-13). The frame is a
    fixed, non-mutating placeholder sized to ``animator.pixel_count`` --
    THREAD-03 observes transport-side behaviour only, never a rendered
    result.
    """
    from lifx.animation.animator import Animator
    from lifx.devices.matrix import MatrixLight
    from lifx.devices.multizone import MultiZoneLight

    if isinstance(device, MatrixLight):
        animator = await Animator.for_matrix(device)
    elif isinstance(device, MultiZoneLight):
        animator = await Animator.for_multizone(device)
    else:
        animator = Animator.for_light(device)

    frame = [(0, 0, 0, 3500)] * animator.pixel_count
    return lambda: animator.send_frame(frame)


async def _run_animation_for_alias(
    *,
    session_dir: Path,
    manifest: Mapping[str, Any],
    alias: str,
    alias_map: Mapping[str, str],
    confound: Sequence[str],
) -> dict[str, Any]:
    """Resolve one alias to a live device and run its animation observation.

    The single shared per-alias orchestration path for both ``--alias`` and
    ``--all``: neither CLI branch duplicates this resolve/connect/observe
    sequence, only how they react to its outcome (see ``_cli_animation``).
    """
    device = await _resolve_target_device(alias, alias_map)
    async with device:
        return await run_animation_observation(
            session_dir=session_dir,
            manifest=manifest,
            alias=alias,
            capture_state=lambda: capture_device_state(device),
            check_liveness=lambda: _device_is_live(device),
            make_send_frame=lambda: _make_animation_send_frame(device),
            restore=lambda captured: restore_and_verify_device_state(device, captured),
            confounders=confound,
        )


def _cli_animation(args: argparse.Namespace) -> int:
    """Run the animation observation for one ``--alias`` or every ``--all`` alias.

    ``--alias`` behaves exactly as before: a raised exception propagates
    unchanged to ``main()``'s ``parser.error()`` handling. ``--all`` is the
    opposite of ``request --all``'s continue-through-failure policy: a
    restoration failure -- or any exception encountered before a device's
    restored/restoration_verified state can be confirmed -- poisons the
    session (D-16), so iteration HALTS IMMEDIATELY and never attempts
    another alias. The remaining, un-attempted aliases are named explicitly
    so the operator knows recovery is still owed to them.
    """
    manifest = load_manifest(args.session_dir)
    alias_map = _load_target_alias_map(args.alias_map)

    if args.alias is not None:
        row = asyncio.run(
            _run_animation_for_alias(
                session_dir=args.session_dir,
                manifest=manifest,
                alias=args.alias,
                alias_map=alias_map,
                confound=args.confound,
            )
        )
        _emit(
            "animation",
            True,
            alias=args.alias,
            restored=row["restored"],
            restoration_verified=row["restoration_verified"],
            rate_outcomes=[rate["outcome"] for rate in row["rates"]],
        )
        return 0

    aliases = sorted(entry["alias"] for entry in manifest["inventory"])
    results: list[dict[str, Any]] = []
    poisoned_alias: str | None = None
    not_attempted: list[str] = []

    for index, alias in enumerate(aliases):
        try:
            row = asyncio.run(
                _run_animation_for_alias(
                    session_dir=args.session_dir,
                    manifest=manifest,
                    alias=alias,
                    alias_map=alias_map,
                    confound=args.confound,
                )
            )
        except (RuntimeError, OSError, LifxError) as error:
            results.append(
                {
                    "alias": alias,
                    "restored": False,
                    "restoration_verified": False,
                    "rate_outcomes": [],
                    "error": type(error).__name__,
                }
            )
            poisoned_alias = alias
            not_attempted = aliases[index + 1 :]
            break

        results.append(
            {
                "alias": alias,
                "restored": row["restored"],
                "restoration_verified": row["restoration_verified"],
                "rate_outcomes": [rate["outcome"] for rate in row["rates"]],
                "error": None,
            }
        )
        if not (row["restored"] and row["restoration_verified"]):
            poisoned_alias = alias
            not_attempted = aliases[index + 1 :]
            break

    ok = poisoned_alias is None
    _emit(
        "animation",
        ok,
        reason=None if ok else "restoration_failed",
        aliases=aliases,
        results=results,
        poisoned_alias=poisoned_alias,
        not_attempted=not_attempted,
    )
    return 0 if ok else 1


async def _device_is_live(device: Light) -> bool:
    """Pre/post liveness only (D-11): no WiFi-derived concurrent-query workload."""
    try:
        await device.get_power()
    except (LifxTimeoutError, LifxConnectionError, LifxNetworkError, LifxProtocolError):
        return False
    return True


def _cli_staleness(args: argparse.Namespace) -> int:
    """Run the THREAD-04 staleness experiment, driving the power cycle itself.

    Either a pre-captured ``--disconnect-ns`` (the hermetic/manual path, used
    by tests) or an operator-supplied ``--power-off``/``--power-on`` script
    pair (T-14-06 change 1) is required -- ``main()`` enforces exactly one of
    the two at argparse time, before any I/O here. When scripts are given,
    the tool captures the disconnect instant itself immediately after the
    power-off script exits 0, and attempts the power-on script once the
    absence-detection protocol closes. Restoration detection then polls
    both discovery legs with NO deadline (T-14-06 change 2): by the time
    restoration polling starts, the operator is already committed to a run
    that blocks for up to three hours for expiry detection, so cutting the
    restoration wait short would only turn a slow-booting bulb into a lost
    ``restored_available_ns``. How long rediscovery actually takes is
    itself recorded as ``restoration_duration_s``, measured from the
    power-on edge to both legs reporting present. The only way out of an
    unbounded restoration wait is the operator's Ctrl-C, which records
    ``interrupted`` and re-raises exactly like a cancellation mid-poll.
    Live progress is written to stderr throughout (T-14-06 change 3), so
    the wait never looks like a silent hang; stdout carries exactly one
    JSON verdict.
    """
    from lifx.api import discover as api_discover
    from lifx.api import discover_mdns as api_discover_mdns

    manifest = load_manifest(args.session_dir)
    alias_map = _load_target_alias_map(args.alias_map)
    expected = set(alias_map.values())
    if args.alias not in expected:
        raise ValueError("--alias must be a value present in --alias-map")

    # A same-alias resume is a no-op inside run_staleness_experiment() too,
    # but that check happens AFTER any power-off script would already have
    # run. Check here first so an already-recorded alias never cuts power
    # on a device a second time.
    existing_rows = [
        row
        for row in reload_staleness_events(args.session_dir / STALENESS_FILENAME)
        if row["alias"] == args.alias
    ]
    if existing_rows:
        row = existing_rows[0]
        _progress(
            f"[staleness] alias already recorded -> disposition {row['disposition']}"
        )
        _emit(
            "staleness",
            True,
            alias=args.alias,
            disposition=row["disposition"],
            first_absence_poll=row["first_absence_poll"],
            confirmed_expiry_poll=row["confirmed_expiry_poll"],
        )
        return 0

    if args.power_off is not None:
        _progress(f"[staleness] power off: {args.power_off} -> attempting")
        try:
            _run_power_script(args.power_off, stage="off")
        except PowerScriptError as error:
            _progress(
                f"[staleness] power off: {args.power_off} -> FAILED ({error.reason})"
            )
            _emit(
                "staleness",
                False,
                reason="power_off_failed",
                alias=args.alias,
                detail=error.reason,
                message=(
                    "power-off script failed; the experiment was never "
                    "started and nothing was mutated"
                ),
            )
            return 1
        disconnect_ns = time.monotonic_ns()
        _progress(f"[staleness] power off: {args.power_off} -> ok, disconnect captured")
    else:
        assert args.disconnect_ns is not None  # enforced by main()'s argparse gate
        disconnect_ns = args.disconnect_ns

    async def _poll() -> tuple[bool, bool]:
        async def _present(source: Callable[..., Any]) -> bool:
            async for device in source(timeout=DISCOVERY_TIMEOUT):
                serial = Serial.from_string(device.serial).to_string()
                if alias_map.get(serial) == args.alias:
                    return True
            return False

        return await _present(api_discover), await _present(api_discover_mdns)

    async def _on_poll(polls: Sequence[Mapping[str, Any]]) -> None:
        latest = polls[-1]
        poll_index = latest["poll"]
        elapsed_s = latest["elapsed_s"]
        absent_run = 0
        for entry in reversed(polls):
            if _poll_is_absent(entry):
                absent_run += 1
            else:
                break
        absent_run = min(absent_run, STALENESS_CONFIRM_ABSENT_POLLS)
        confirmed = (
            _confirmed_expiry_poll(polls, STALENESS_CONFIRM_ABSENT_POLLS) == poll_index
        )
        suffix = " -> expiry confirmed" if confirmed else ""
        _progress(
            f"[staleness] poll {poll_index}  t+{int(elapsed_s)}s  "
            f"discover={'present' if latest['discover_present'] else 'absent'}  "
            f"mdns={'present' if latest['discover_mdns_present'] else 'absent'}  "
            f"absent-run {absent_run}/{STALENESS_CONFIRM_ABSENT_POLLS}{suffix}"
        )
        if not confirmed and elapsed_s >= 0.9 * STALENESS_CAP_S:
            _progress(
                f"[staleness] approaching the censoring cap: t+{int(elapsed_s)}s "
                f"of {int(STALENESS_CAP_S)}s"
            )

    power_on_failed = False

    async def _restore_available() -> tuple[int, float] | None:
        """Poll both legs with NO deadline until restored, or the power-on script fails.

        The only exit besides "both legs present" is the operator's
        Ctrl-C: ``asyncio.CancelledError`` raised from inside ``await
        _poll()`` propagates unchanged out of this closure, through
        ``run_staleness_experiment``'s ``except asyncio.CancelledError``
        branch, which persists an ``interrupted`` row and re-raises.
        """
        nonlocal power_on_failed
        if args.power_on is not None:
            _progress(f"[staleness] power on: {args.power_on} -> attempting")
            try:
                _run_power_script(args.power_on, stage="on")
            except PowerScriptError as error:
                power_on_failed = True
                _progress(
                    f"[staleness] power on: {args.power_on} -> FAILED "
                    f"({error.reason}) -- device is DARK, operator must "
                    "restore power manually"
                )
                return None
            _progress(
                f"[staleness] power on: {args.power_on} -> ok, polling for restoration"
            )
        restore_start = time.monotonic()
        while True:
            discover_present, mdns_present = await _poll()
            elapsed_s = time.monotonic() - restore_start
            if discover_present and mdns_present:
                _progress(f"[staleness] restored after {int(elapsed_s)}s")
                return time.monotonic_ns(), elapsed_s
            _progress(
                f"[staleness] waiting for restoration... t+{int(elapsed_s)}s  "
                f"discover={'present' if discover_present else 'absent'}  "
                f"mdns={'present' if mdns_present else 'absent'}"
            )

    row = asyncio.run(
        run_staleness_experiment(
            session_dir=args.session_dir,
            manifest=manifest,
            alias=args.alias,
            disconnect_ns=disconnect_ns,
            poll=_poll,
            restore_available=_restore_available,
            on_poll=_on_poll,
            confounders=args.confound,
        )
    )

    if row["disposition"] == "censored":
        _progress(
            f"[staleness] reached the censoring cap ({int(STALENESS_CAP_S)}s) "
            "without confirmed expiry -> censored"
        )
    elif row["disposition"] == "restored_before_expiry":
        _progress(
            "[staleness] device restored before expiry was confirmed -> "
            "restored_before_expiry"
        )

    if power_on_failed:
        _emit(
            "staleness",
            False,
            reason="power_on_failed",
            alias=args.alias,
            disposition=row["disposition"],
            first_absence_poll=row["first_absence_poll"],
            confirmed_expiry_poll=row["confirmed_expiry_poll"],
            restoration_duration_s=row["restoration_duration_s"],
            message=(
                "power-on script failed after the disconnect experiment "
                "closed; the device is physically powered off and requires "
                "operator intervention to restore power"
            ),
        )
        return 1

    _emit(
        "staleness",
        True,
        alias=args.alias,
        disposition=row["disposition"],
        first_absence_poll=row["first_absence_poll"],
        confirmed_expiry_poll=row["confirmed_expiry_poll"],
        restoration_duration_s=row["restoration_duration_s"],
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and dispatch. No subcommand performs no I/O."""
    parser = argparse.ArgumentParser(
        description=(
            "Phase 14 Thread-revalidation orchestrator (schema-only in this plan)."
        )
    )
    subparsers = parser.add_subparsers(dest="mode")

    init_parser = subparsers.add_parser(
        "init", help="Create or verify the session manifest."
    )
    init_parser.add_argument("--session-dir", type=Path, required=True)
    init_parser.add_argument("--session-id", required=True)
    init_parser.add_argument("--protocol-version", type=int, default=1)
    init_parser.add_argument("--revision")
    init_parser.add_argument("--seed", type=int, required=True)
    init_parser.add_argument(
        "--inventory",
        type=Path,
        help=(
            "Path to a JSON file holding the operator-approved roster: a list "
            "of {alias, device_class, available} entries"
        ),
    )
    init_parser.add_argument(
        "--confound", action="append", choices=sorted(_CONFOUNDERS), default=[]
    )
    init_parser.set_defaults(func=_cli_init)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate all journals and regenerate the derived products."
    )
    validate_parser.add_argument("--session-dir", type=Path, required=True)
    validate_parser.set_defaults(func=_cli_validate)

    generate_parser = subparsers.add_parser(
        "generate",
        help="Validate roster completeness, then atomically regenerate products.",
    )
    generate_parser.add_argument("--session-dir", type=Path, required=True)
    generate_parser.set_defaults(func=_cli_generate)

    validate_staged_parser = subparsers.add_parser(
        "validate-staged",
        help="Validate the exact nine evidence blobs from Git's staged index.",
    )
    validate_staged_parser.add_argument("--evidence-dir", required=True)
    validate_staged_parser.set_defaults(func=_cli_validate_staged)

    discover_parser = subparsers.add_parser(
        "discover", help="Run the frozen six paired discovery rounds (THREAD-01)."
    )
    discover_parser.add_argument("--session-dir", type=Path, required=True)
    discover_parser.add_argument("--alias-map", type=Path, required=True)
    discover_parser.add_argument(
        "--confound", action="append", choices=sorted(_CONFOUNDERS), default=[]
    )
    discover_parser.set_defaults(func=_cli_discover)

    request_parser = subparsers.add_parser(
        "request", help="Run the frozen 100-trial request series (THREAD-02)."
    )
    request_parser.add_argument("--session-dir", type=Path, required=True)
    request_parser.add_argument("--alias-map", type=Path, required=True)
    request_target_group = request_parser.add_mutually_exclusive_group(required=True)
    request_target_group.add_argument("--alias")
    request_target_group.add_argument(
        "--all",
        action="store_true",
        help=(
            "Run the series for every alias in the frozen manifest inventory "
            "(sorted, resumable). A power_out_of_range alias never stops the "
            "remaining aliases; ok is false and every offending alias is named."
        ),
    )
    request_parser.add_argument(
        "--confound", action="append", choices=sorted(_CONFOUNDERS), default=[]
    )
    request_parser.set_defaults(func=_cli_request)

    animation_parser = subparsers.add_parser(
        "animation", help="Run the frozen 1/2/5 FPS observation (THREAD-03)."
    )
    animation_parser.add_argument("--session-dir", type=Path, required=True)
    animation_parser.add_argument("--alias-map", type=Path, required=True)
    animation_target_group = animation_parser.add_mutually_exclusive_group(
        required=True
    )
    animation_target_group.add_argument("--alias")
    animation_target_group.add_argument(
        "--all",
        action="store_true",
        help=(
            "Run the observation for every alias in the frozen manifest "
            "inventory (sorted, resumable). A restoration failure halts "
            "immediately without touching another device; ok is false and "
            "the poisoned alias plus every un-attempted alias are named."
        ),
    )
    animation_parser.add_argument(
        "--confound", action="append", choices=sorted(_CONFOUNDERS), default=[]
    )
    animation_parser.set_defaults(func=_cli_animation)

    staleness_parser = subparsers.add_parser(
        "staleness", help="Run the advertisement-expiry experiment (THREAD-04)."
    )
    staleness_parser.add_argument("--session-dir", type=Path, required=True)
    staleness_parser.add_argument("--alias-map", type=Path, required=True)
    staleness_parser.add_argument("--alias", required=True)
    staleness_power_group = staleness_parser.add_mutually_exclusive_group(required=True)
    staleness_power_group.add_argument(
        "--disconnect-ns",
        type=int,
        help=(
            "A pre-captured time.monotonic_ns() disconnect instant, for a "
            "manually-cut hermetic/test run. Mutually exclusive with "
            "--power-off/--power-on."
        ),
    )
    staleness_power_group.add_argument(
        "--power-off",
        type=Path,
        help=(
            "Operator-supplied executable that cuts power to the target "
            "device, run directly (never through a shell). Requires "
            "--power-on. The disconnect instant is captured immediately "
            "after this script exits 0."
        ),
    )
    staleness_parser.add_argument(
        "--power-on",
        type=Path,
        help=(
            "Operator-supplied executable that restores power to the "
            "target device, run directly (never through a shell) once the "
            "experiment closes. Requires --power-off."
        ),
    )
    staleness_parser.add_argument(
        "--confound", action="append", choices=sorted(_CONFOUNDERS), default=[]
    )
    staleness_parser.set_defaults(func=_cli_staleness)

    args = parser.parse_args(argv)
    if args.mode == "staleness" and (args.power_off is None) != (args.power_on is None):
        parser.error("--power-off and --power-on must be supplied together")
    func = getattr(args, "func", None)
    if func is None:
        parser.print_usage()
        return 2
    try:
        return func(args)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    sys.exit(main())
