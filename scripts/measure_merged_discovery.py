#!/usr/bin/env python3
"""Measure direct UDP and public merged discovery with privacy-safe JSONL."""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import re
import shutil
import subprocess  # nosec B404
import sys
import time
import uuid
from collections import defaultdict
from collections.abc import AsyncGenerator, Iterable, Mapping, Sequence
from contextlib import aclosing, asynccontextmanager, nullcontext
from pathlib import Path
from typing import Literal, cast

from lifx_emulator import EmulatedLifxServer
from lifx_emulator.devices import DeviceManager
from lifx_emulator.factories import create_color_light
from lifx_emulator.repositories import DeviceRepository
from lifx_emulator.scenarios import HierarchicalScenarioManager

from lifx.api import discover
from lifx.const import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DISCOVERY_TIMEOUT,
    IDLE_TIMEOUT_MULTIPLIER,
    MAX_RESPONSE_TIME,
)
from lifx.devices import Device
from lifx.network.discovery import discover_devices
from lifx.network.discovery.mdns.discovery import _override_mdns_service_source
from lifx.network.discovery.mdns.types import _LifxServiceRecord
from lifx.protocol.models import Serial
from scripts.measurement_support import (
    _capture_discovery_observations,
    _DiscoveryObservation,
)

_SCHEMA_VERSION = 1
_KIND = "merged_discovery_measurement"
_ARMS = {"baseline", "merged"}
_IMPLEMENTATION_PATHS = {"direct_udp", "merged_dual"}
_ENVIRONMENTS = {"emulator", "fleet"}
_QUIESCENCE = {"quiesced", "not_quiesced", "unknown"}
_SOURCES = {"udp", "mdns"}
_TARGETS = {"owned_loopback_dynamic", "fleet"}
_EVIDENCE_CLASSIFICATIONS = {"synthetic_mdns_lower_bound", "representative"}
_ROUND_CLASSIFICATIONS = {"single_round", "repeated_rounds"}
_CONFOUNDS = {
    "background_pollers",
    "busy_network",
    "wireless_interference",
}
_Arm = Literal["baseline", "merged"]
_ALIAS_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9-]{0,63}\Z")
_REVISION_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
_IPV4_PATTERN = re.compile(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])")
_SERIAL_PATTERN = re.compile(
    r"(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\Z|[0-9a-fA-F]{12}\Z"
)
_FORBIDDEN_KEYS = {
    "address",
    "device_ip",
    "device_serial",
    "exception",
    "hostname",
    "ip",
    "mac",
    "packet",
    "port",
    "raw_identity",
    "serial",
    "txt",
}
_ROW_KEYS = {
    "schema_version",
    "kind",
    "scenario_id",
    "pair_id",
    "round",
    "arm",
    "implementation_path",
    "environment",
    "revision",
    "quiescence",
    "confounds",
    "elapsed_ns",
    "first_result_ns",
    "unique_count",
    "devices",
    "target",
    "find08",
}
_QUALIFIED_ROW_KEYS = _ROW_KEYS | {
    "evidence_classification",
    "round_classification",
}
_SYNTHETIC_ALIASES = {
    "020000000001": "synthetic-primary",
    "020000000002": "synthetic-secondary",
}


def _validate_alias(alias: object) -> str:
    """Return one controlled alias or reject identifier-shaped text."""
    if not isinstance(alias, str) or _ALIAS_PATTERN.fullmatch(alias) is None:
        raise ValueError("invalid privacy-safe device alias")
    if _SERIAL_PATTERN.fullmatch(alias) is not None:
        raise ValueError("identifier-shaped alias is forbidden")
    return alias


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).casefold() in _FORBIDDEN_KEYS or _contains_forbidden_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_key(child) for child in value)
    return False


def _string_exposes_network_value(value: str) -> bool:
    """Detect address or identifier-shaped strings outside controlled fields."""
    if _IPV4_PATTERN.search(value) is not None:
        return True
    for token in re.split(r"[=,;\s]+", value):
        if not token:
            continue
        try:
            ipaddress.ip_address(token)
        except ValueError:
            pass
        else:
            return True
    return False


def _contains_forbidden_value(
    value: object,
    *,
    forbidden_values: frozenset[str],
    field_name: str | None = None,
) -> bool:
    if isinstance(value, dict):
        return any(
            _contains_forbidden_value(
                child,
                forbidden_values=forbidden_values,
                field_name=str(key),
            )
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(
            _contains_forbidden_value(
                child,
                forbidden_values=forbidden_values,
                field_name=field_name,
            )
            for child in value
        )
    if not isinstance(value, str):
        return False
    if value in forbidden_values:
        return True
    if field_name not in {"revision", "scenario_id", "pair_id"} and (
        _SERIAL_PATTERN.fullmatch(value) is not None
    ):
        return True
    return _string_exposes_network_value(value)


def _build_measurement_row(
    *,
    scenario_id: str,
    pair_id: str,
    round_number: int,
    arm: str,
    implementation_path: str,
    environment: str,
    revision: str,
    quiescence: str,
    confounds: Sequence[str],
    elapsed_ns: int,
    first_result_ns: int | None,
    devices: Sequence[Mapping[str, object]],
    target: str,
    find08: Mapping[str, object],
    unique_count: int | None = None,
) -> dict[str, object]:
    """Build one raw immutable measurement row and validate it."""
    row: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "kind": _KIND,
        "scenario_id": scenario_id,
        "pair_id": pair_id,
        "round": round_number,
        "arm": arm,
        "implementation_path": implementation_path,
        "environment": environment,
        "revision": revision,
        "quiescence": quiescence,
        "confounds": list(confounds),
        "elapsed_ns": elapsed_ns,
        "first_result_ns": first_result_ns,
        "unique_count": len(devices) if unique_count is None else unique_count,
        "devices": [dict(device) for device in devices],
        "target": target,
        "find08": dict(find08),
        "evidence_classification": (
            "synthetic_mdns_lower_bound"
            if environment == "emulator"
            else "representative"
        ),
        "round_classification": (
            "single_round" if environment == "emulator" else "repeated_rounds"
        ),
    }
    _validate_measurements([row])
    return row


def _validate_measurements(
    rows: Sequence[Mapping[str, object]],
    *,
    require_complete_pairs: bool = False,
    require_final_evidence: bool = False,
    current_revision: str | None = None,
    expected_revision: str | None = None,
    forbidden_values: Iterable[str] = (),
) -> None:
    """Validate rows independently and optionally require complete pairs."""
    if expected_revision is not None and (
        _REVISION_PATTERN.fullmatch(expected_revision) is None
    ):
        raise ValueError("expected revision must be a 40-character lowercase SHA")
    if current_revision is not None and (
        _REVISION_PATTERN.fullmatch(current_revision) is None
    ):
        raise ValueError("current revision must be a 40-character lowercase SHA")
    forbidden = frozenset(forbidden_values)
    pairs: dict[tuple[str, str, int], dict[str, Mapping[str, object]]] = {}
    for row in rows:
        row_keys = set(row)
        if row_keys != _ROW_KEYS and row_keys != _QUALIFIED_ROW_KEYS:
            if _contains_forbidden_key(row):
                raise ValueError(
                    "privacy validation rejected a forbidden identifier field"
                )
            raise ValueError("invalid measurement row fields")
        if _contains_forbidden_key(row):
            raise ValueError("privacy validation rejected a forbidden identifier field")
        if _contains_forbidden_value(row, forbidden_values=forbidden):
            raise ValueError("privacy validation rejected a raw identifier or address")
        if row["schema_version"] != _SCHEMA_VERSION or row["kind"] != _KIND:
            raise ValueError("invalid measurement schema identity")
        for key in ("scenario_id", "pair_id"):
            if not isinstance(row[key], str) or not row[key]:
                raise ValueError(f"invalid {key}")
        if type(row["round"]) is not int or row["round"] < 1:
            raise ValueError("round must be a positive integer")
        arm = row["arm"]
        if arm not in _ARMS:
            raise ValueError("invalid measurement arm")
        expected_path = "direct_udp" if arm == "baseline" else "merged_dual"
        if row["implementation_path"] not in _IMPLEMENTATION_PATHS or (
            row["implementation_path"] != expected_path
        ):
            raise ValueError("invalid implementation_path for arm")
        if row["environment"] not in _ENVIRONMENTS:
            raise ValueError("invalid environment")
        if row_keys == _QUALIFIED_ROW_KEYS:
            expected_evidence = (
                "synthetic_mdns_lower_bound"
                if row["environment"] == "emulator"
                else "representative"
            )
            expected_round = (
                "single_round"
                if row["environment"] == "emulator"
                else "repeated_rounds"
            )
            if (
                row["evidence_classification"] not in _EVIDENCE_CLASSIFICATIONS
                or row["evidence_classification"] != expected_evidence
            ):
                raise ValueError("invalid evidence_classification for environment")
            if (
                row["round_classification"] not in _ROUND_CLASSIFICATIONS
                or row["round_classification"] != expected_round
            ):
                raise ValueError("invalid round_classification for environment")
        if row["target"] not in _TARGETS:
            raise ValueError("invalid categorical target")
        revision = row["revision"]
        if (
            not isinstance(revision, str)
            or _REVISION_PATTERN.fullmatch(revision) is None
        ):
            raise ValueError("invalid revision")
        if row["quiescence"] not in _QUIESCENCE:
            raise ValueError("invalid quiescence")
        confounds = row["confounds"]
        if (
            not isinstance(confounds, list)
            or len(confounds) != len(set(confounds))
            or not set(confounds) <= _CONFOUNDS
        ):
            raise ValueError("invalid confounds")
        elapsed_ns = row["elapsed_ns"]
        unique_count = row["unique_count"]
        for key, integer_value in (
            ("elapsed_ns", elapsed_ns),
            ("unique_count", unique_count),
        ):
            if type(integer_value) is not int or integer_value < 0:
                raise ValueError(f"{key} must be a non-negative integer")
        assert isinstance(elapsed_ns, int)
        assert isinstance(unique_count, int)
        first_result_ns = row["first_result_ns"]
        if first_result_ns is not None and (
            type(first_result_ns) is not int
            or first_result_ns < 0
            or first_result_ns > elapsed_ns
        ):
            raise ValueError("first_result_ns must be a bounded integer or null")
        devices = row["devices"]
        if not isinstance(devices, list) or unique_count < len(devices):
            raise ValueError("unique_count cannot be smaller than the alias count")
        if unique_count and first_result_ns is None:
            raise ValueError("first_result_ns cannot be null for non-empty output")
        if not unique_count and first_result_ns is not None:
            raise ValueError("first_result_ns must be null for empty output")
        seen_aliases: set[str] = set()
        for device in devices:
            if not isinstance(device, dict) or set(device) != {
                "alias",
                "sources",
                "winner",
                "source_order",
            }:
                raise ValueError("invalid device contribution")
            alias = _validate_alias(device["alias"])
            if alias in seen_aliases:
                raise ValueError("duplicate alias in measurement row")
            seen_aliases.add(alias)
            sources = device["sources"]
            if (
                not isinstance(sources, list)
                or not sources
                or sources != sorted(set(sources))
                or not set(sources) <= _SOURCES
            ):
                raise ValueError("invalid contributing sources")
            source_order = device["source_order"]
            if (
                not isinstance(source_order, list)
                or not source_order
                or len(source_order) != len(set(source_order))
                or not set(source_order) <= _SOURCES
                or set(source_order) != set(sources)
            ):
                raise ValueError("invalid contributing source order")
            if device["winner"] != source_order[0]:
                raise ValueError("device winner must be the first observed source")
        _validate_find08(row["find08"])

        round_number = row["round"]
        assert isinstance(round_number, int)
        key = (str(row["scenario_id"]), str(row["pair_id"]), round_number)
        pair = pairs.setdefault(key, {})
        if arm in pair:
            raise ValueError("duplicate arm in measurement pair")
        pair[str(arm)] = row

    for pair in pairs.values():
        if require_complete_pairs and set(pair) != _ARMS:
            raise ValueError(
                "measurement pair requires complete baseline and merged arms"
            )
        if set(pair) != _ARMS:
            continue
        baseline = pair["baseline"]
        merged = pair["merged"]
        comparable = (
            "scenario_id",
            "pair_id",
            "round",
            "environment",
            "revision",
            "quiescence",
            "confounds",
            "target",
        )
        if any(baseline[key] != merged[key] for key in comparable):
            raise ValueError("measurement pair carries incomparable scenario metadata")

    if require_final_evidence:
        complete_pairs = [pair for pair in pairs.values() if set(pair) == _ARMS]
        if current_revision is None:
            raise ValueError(
                "current revision is required for final evidence validation"
            )
        fleet_pairs = [
            pair
            for pair in complete_pairs
            if pair["baseline"]["environment"] == "fleet"
            and pair["baseline"]["revision"] == current_revision
        ]
        if len(fleet_pairs) < 6:
            raise ValueError(
                "final evidence requires at least six complete current-revision "
                "fleet pairs"
            )
        emulator_pairs = [
            pair
            for pair in complete_pairs
            if pair["baseline"]["environment"] == "emulator"
            and pair["baseline"]["revision"] == current_revision
        ]
        if not emulator_pairs:
            raise ValueError("final evidence requires a current-revision emulator pair")

    if expected_revision is not None:
        selected = [row for row in rows if row["revision"] == expected_revision]
        if len(selected) != 2:
            raise ValueError(
                "expected revision requires exactly one two-row measurement pair"
            )
        selected_keys = {
            (str(row["scenario_id"]), str(row["pair_id"]), cast(int, row["round"]))
            for row in selected
        }
        if len(selected_keys) != 1 or {row["arm"] for row in selected} != _ARMS:
            raise ValueError(
                "expected revision requires one complete baseline and merged pair"
            )
        if any(set(row) != _QUALIFIED_ROW_KEYS for row in selected):
            raise ValueError("expected revision pair requires evidence qualifications")


def _validate_find08(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {"disposition", "devices"}:
        raise ValueError("invalid FIND-08 evidence")
    if value["disposition"] not in {"observed", "no_eligible_find08_population"}:
        raise ValueError("invalid FIND-08 disposition")
    devices = value["devices"]
    if not isinstance(devices, list):
        raise ValueError("invalid FIND-08 devices")
    aliases: set[str] = set()
    for device in devices:
        if not isinstance(device, dict) or set(device) != {"alias", "match"}:
            raise ValueError("invalid FIND-08 device evidence")
        alias = _validate_alias(device["alias"])
        if alias in aliases or type(device["match"]) is not bool:
            raise ValueError("invalid duplicate or match in FIND-08 evidence")
        aliases.add(alias)
    if value["disposition"] == "observed" and not devices:
        raise ValueError("observed FIND-08 evidence requires devices")
    if value["disposition"] == "no_eligible_find08_population" and devices:
        raise ValueError("empty-population FIND-08 evidence cannot contain devices")


def _append_measurement_row(
    path: Path,
    row: Mapping[str, object],
    *,
    forbidden_values: Iterable[str] = (),
) -> None:
    """Validate then append one compact row without reading or rewriting bytes."""
    _validate_measurements([row], forbidden_values=forbidden_values)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def _load_measurements(path: Path) -> list[dict[str, object]]:
    """Load JSONL with line-numbered errors and preserve file order."""
    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{path.name} line {line_number}: invalid JSON: {error}"
                ) from error
            if not isinstance(value, dict):
                raise ValueError(
                    f"{path.name} line {line_number}: row is not an object"
                )
            rows.append(value)
    return rows


def _render_measurement_summary(rows: Sequence[Mapping[str, object]]) -> str:
    """Regenerate a deterministic human-readable summary from raw rows."""
    _validate_measurements(rows)
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row["scenario_id"]),
            str(row["pair_id"]),
            cast(int, row["round"]),
            str(row["arm"]),
        ),
    )
    paired: dict[tuple[str, str, int], dict[str, Mapping[str, object]]] = defaultdict(
        dict
    )
    for row in ordered:
        key = (str(row["scenario_id"]), str(row["pair_id"]), cast(int, row["round"]))
        paired[key][str(row["arm"])] = row
    complete_pairs = [(key, pair) for key, pair in paired.items() if set(pair) == _ARMS]
    fleet_rows = [row for row in ordered if row["environment"] == "fleet"]
    fleet_pairs = [
        pair for _, pair in complete_pairs if pair["baseline"]["environment"] == "fleet"
    ]
    baseline_counts = [
        cast(int, pair["baseline"]["unique_count"]) for pair in fleet_pairs
    ]
    variance = "not_applicable"
    if baseline_counts:
        variance = (
            "stable_baseline_counts"
            if len(set(baseline_counts)) <= 1
            else "variable_baseline_counts"
        )
    fleet_revisions = sorted({str(row["revision"]) for row in fleet_rows})
    fleet_quiescence = sorted({str(row["quiescence"]) for row in fleet_rows})
    fleet_confounds = sorted(
        {
            confound
            for row in fleet_rows
            for confound in cast(list[str], row["confounds"])
        }
    )
    find08_dispositions = sorted(
        {
            str(cast(Mapping[str, object], row["find08"])["disposition"])
            for row in fleet_rows
        }
    )
    fleet_evidence = sorted(
        {
            str(row["evidence_classification"])
            for row in fleet_rows
            if "evidence_classification" in row
        }
    )
    fleet_rounds = sorted(
        {
            str(row["round_classification"])
            for row in fleet_rows
            if "round_classification" in row
        }
    )
    emulator_evidence = sorted(
        {
            str(row["evidence_classification"])
            for row in ordered
            if row["environment"] == "emulator" and "evidence_classification" in row
        }
    )
    emulator_rounds = sorted(
        {
            str(row["round_classification"])
            for row in ordered
            if row["environment"] == "emulator" and "round_classification" in row
        }
    )
    lines = [
        "# Merged Discovery Measurement Summary",
        "",
        "Generated solely from validated append-only JSONL rows.",
        "",
        "## Evidence qualification",
        "",
        f"- Complete physical fleet pairs: {len(fleet_pairs)}.",
        "- Fleet evidence: "
        f"`{', '.join(fleet_evidence) or 'none'}` and "
        f"`{', '.join(fleet_rounds) or 'none'}`.",
        "- Emulator evidence: "
        f"`{', '.join(emulator_evidence) or 'unqualified_legacy_baseline'}` and "
        f"`{', '.join(emulator_rounds) or 'unqualified_legacy_baseline'}`; "
        "it is a synthetic mDNS lower bound, not representative fleet evidence.",
        "- Exact measured fleet implementation revision: "
        f"`{', '.join(fleet_revisions) or 'none'}`.",
        f"- Fleet quiescence: `{', '.join(fleet_quiescence) or 'none'}`.",
        f"- Fleet confounds: `{', '.join(fleet_confounds) or 'none'}`.",
        f"- Fleet baseline-count variance: `{variance}` (advisory only; no "
        "pass/fail threshold).",
        f"- FIND-08 disposition: `{', '.join(find08_dispositions) or 'none'}`; "
        "missing eligible physical WiFi population is a non-gating gap.",
        "- The mDNS liveness concurrency cap of 16 is a reasoned D-07 safety "
        "bound, not a measured optimum.",
        "",
        "## Pair deltas",
        "",
        "Deltas are merged minus direct-UDP baseline observations.",
        "",
        "| Scenario | Pair | Round | Environment | Completion delta ns | "
        "First-result delta ns | Unique delta |",
        "|---|---|---:|---|---:|---:|---:|",
    ]
    for (scenario_id, pair_id, round_number), pair in complete_pairs:
        baseline = pair["baseline"]
        merged = pair["merged"]
        baseline_first = cast(int | None, baseline["first_result_ns"])
        merged_first = cast(int | None, merged["first_result_ns"])
        first_delta = (
            "null"
            if baseline_first is None or merged_first is None
            else f"{merged_first - baseline_first:+d}"
        )
        completion_delta = cast(int, merged["elapsed_ns"]) - cast(
            int, baseline["elapsed_ns"]
        )
        unique_delta = cast(int, merged["unique_count"]) - cast(
            int, baseline["unique_count"]
        )
        lines.append(
            f"| {scenario_id} | {pair_id} | {round_number} | "
            f"{baseline['environment']} | "
            f"{completion_delta:+d} | "
            f"{first_delta} | "
            f"{unique_delta:+d} |"
        )
    lines.extend(
        [
            "",
            "## Raw observations",
            "",
            "Source counts are alias-only contributions from each exact timed call.",
            "",
            "| Scenario | Pair | Round | Arm | Elapsed ns | First result ns | "
            "Unique | UDP | mDNS | Overlap | UDP wins | mDNS wins | Qualification |",
            "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in ordered:
        confounds = cast(list[str], row["confounds"])
        clean = row["quiescence"] == "quiesced" and not confounds
        qualification = "clean" if clean else "confounded"
        if confounds:
            qualification += f" ({', '.join(confounds)})"
        first_result = row["first_result_ns"]
        devices = cast(list[Mapping[str, object]], row["devices"])
        udp = sum("udp" in cast(list[str], device["sources"]) for device in devices)
        mdns = sum("mdns" in cast(list[str], device["sources"]) for device in devices)
        overlap = sum(
            set(cast(list[str], device["sources"])) == _SOURCES for device in devices
        )
        udp_wins = sum(device["winner"] == "udp" for device in devices)
        mdns_wins = sum(device["winner"] == "mdns" for device in devices)
        lines.append(
            "| "
            f"{row['scenario_id']} | {row['pair_id']} | {row['round']} | "
            f"{row['arm']} | {row['elapsed_ns']} | "
            f"{first_result if first_result is not None else 'null'} | "
            f"{row['unique_count']} | {udp} | {mdns} | {overlap} | {udp_wins} | "
            f"{mdns_wins} | {qualification} |"
        )
    return "\n".join(lines) + "\n"


def _arms_for_mode(mode: str) -> tuple[_Arm, ...]:
    """Return the exact sequential arms selected by one CLI mode."""
    try:
        return {
            "baseline-only": ("baseline",),
            "merged-only": ("merged",),
            "paired": ("baseline", "merged"),
        }[mode]
    except KeyError as error:
        raise ValueError(f"unsupported measurement mode: {mode}") from error


def _eligible_find08_firmware(major: int, minor: int) -> bool:
    """Return whether exact integer firmware components qualify for FIND-08."""
    return major == 3 and 70 <= minor <= 99


def _normalise_find08_observations(
    observations: Iterable[tuple[str, str, int, int, str]],
) -> dict[str, object]:
    """Collapse eligible observations to alias and identity-match disposition."""
    results: dict[str, bool] = {}
    for mdns_identity, udp_identity, major, minor, raw_alias in observations:
        if not _eligible_find08_firmware(major, minor):
            continue
        alias = _validate_alias(raw_alias)
        match = (
            Serial.from_string(mdns_identity).to_string()
            == Serial.from_string(udp_identity).to_string()
        )
        previous = results.get(alias)
        if previous is not None and previous != match:
            raise ValueError("conflicting FIND-08 observations for one alias")
        results[alias] = match
    if not results:
        return {"disposition": "no_eligible_find08_population", "devices": []}
    return {
        "disposition": "observed",
        "devices": [
            {"alias": alias, "match": results[alias]} for alias in sorted(results)
        ],
    }


def _load_alias_map(path: Path) -> dict[str, str]:
    """Load an external raw-identity-to-alias mapping only into memory."""
    repository = Path(__file__).resolve().parents[1]
    resolved = path.expanduser().resolve()
    if resolved == repository or repository in resolved.parents:
        raise ValueError("--alias-map must be outside the repository")
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value:
        raise ValueError("alias map must be a non-empty JSON object")
    aliases: dict[str, str] = {}
    for raw_identity, raw_alias in value.items():
        identity = Serial.from_string(raw_identity).to_string()
        alias = _validate_alias(raw_alias)
        if identity in aliases:
            raise ValueError("alias map contains a duplicate normalised identity")
        aliases[identity] = alias
    return aliases


def _git_revision() -> str:
    """Return the exact repository revision without recording command errors."""
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to record measurement revision")
    completed = subprocess.run(  # nosec B603
        [git, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    revision = completed.stdout.strip().casefold()
    if _REVISION_PATTERN.fullmatch(revision) is None:
        raise RuntimeError("git returned an invalid revision")
    return revision


def _measurement_revision(requested: str | None) -> str:
    """Return one explicit immutable revision or the current full Git SHA."""
    revision = _git_revision() if requested is None else requested
    if _REVISION_PATTERN.fullmatch(revision) is None:
        raise ValueError("--revision must be a 40-character lowercase SHA")
    return revision


class _EmbeddedMeasurementEmulator:
    """Own one loopback emulator and a matching private mDNS record source."""

    address = "127.0.0.1"

    def __init__(self) -> None:
        self.server: EmulatedLifxServer | None = None
        self.port = 0
        self.mdns_record: _LifxServiceRecord | None = None
        self.aliases = dict(_SYNTHETIC_ALIASES)
        self.source_finalised = False
        self.existing_device_ports: tuple[int, ...] = ()
        self.later_device_port = 0
        self.advertised_service_ports: tuple[int, ...] = ()

    async def __aenter__(self) -> _EmbeddedMeasurementEmulator:
        scenario_manager = HierarchicalScenarioManager()
        first = create_color_light(
            serial="020000000001",
            firmware_version=(3, 70),
            scenario_manager=scenario_manager,
        )
        manager = DeviceManager(DeviceRepository())
        server = EmulatedLifxServer(
            devices=[first],
            device_manager=manager,
            bind_address=self.address,
            port=0,
            track_activity=False,
            scenario_manager=scenario_manager,
        )
        self.server = server
        try:
            await server.start()
            if server.transport is None:
                raise RuntimeError("emulator transport did not start")
            sockname = server.transport.get_extra_info("sockname")
            if not isinstance(sockname, tuple) or len(sockname) < 2:
                raise RuntimeError("emulator transport has no bound endpoint")
            bound_port = sockname[1]
            if type(bound_port) is not int or bound_port <= 0:
                raise RuntimeError("emulator did not receive a non-zero dynamic port")
            self.port = bound_port
            server.port = bound_port
            for device in server.get_all_devices():
                device.state.port = bound_port
            self.existing_device_ports = tuple(
                device.state.port for device in server.get_all_devices()
            )
            if not self.existing_device_ports or any(
                port != bound_port for port in self.existing_device_ports
            ):
                raise RuntimeError("existing emulator device port was not re-stamped")

            second = create_color_light(
                serial="020000000002",
                firmware_version=(3, 70),
                scenario_manager=scenario_manager,
            )
            if not server.add_device(second):
                raise RuntimeError("emulator rejected the later synthetic device")
            self.later_device_port = second.state.port
            if self.later_device_port != bound_port:
                raise RuntimeError("later emulator device did not inherit bound port")
            if any(
                device.state.port != bound_port for device in server.get_all_devices()
            ):
                raise RuntimeError("emulator device advertisement port drifted")

            verified = [
                discovered
                async for discovered in discover_devices(
                    timeout=0.25,
                    broadcast_address=self.address,
                    port=bound_port,
                    max_response_time=0.05,
                    idle_timeout_multiplier=1.0,
                )
            ]
            if not verified or any(device.port != bound_port for device in verified):
                raise RuntimeError(
                    "StateService did not advertise the bound dynamic port"
                )
            self.advertised_service_ports = tuple(device.port for device in verified)

            state = first.state
            self.mdns_record = _LifxServiceRecord(
                serial=state.serial,
                ip=self.address,
                port=bound_port,
                product_id=state.product,
                firmware=f"{state.version_major}.{state.version_minor}",
                connectivity="wifi",
                addresses=frozenset({self.address}),
                service_instance="synthetic-primary._lifx._udp.local",
            )
            return self
        except BaseException:
            await self._stop()
            raise

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        await self._stop()

    async def _stop(self) -> None:
        if self.server is None:
            return
        cleanup = asyncio.create_task(self.server.stop())
        cancellation: asyncio.CancelledError | None = None
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError as error:
                if cancellation is None:
                    cancellation = error
        cleanup.result()
        self.server = None
        if cancellation is not None:
            raise cancellation

    async def service_source(self) -> AsyncGenerator[_LifxServiceRecord, None]:
        """Yield the one matching synthetic record and expose finalisation."""
        if self.mdns_record is None:
            raise RuntimeError("emulator source requested before startup")
        try:
            yield self.mdns_record
        finally:
            self.source_finalised = True


async def _direct_udp_devices(
    *,
    timeout: float,
    broadcast_address: str,
    port: int,
    max_response_time: float,
    idle_timeout_multiplier: float,
    device_timeout: float,
    max_retries: int,
) -> AsyncGenerator[Device, None]:
    """Reproduce the pre-share public UDP path without calling discover_udp."""
    discovered_devices = discover_devices(
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
        device_timeout=device_timeout,
        max_retries=max_retries,
    )
    async with aclosing(discovered_devices):
        async for discovered in discovered_devices:
            try:
                device = await discovered.create_device()
            except (AttributeError, TypeError):
                continue
            if device is not None:
                yield device


def _source_contributions(
    observations: Sequence[_DiscoveryObservation],
    yielded_identities: set[str],
    aliases: Mapping[str, str],
) -> list[dict[str, object]]:
    source_order: dict[str, list[str]] = defaultdict(list)
    for observation in observations:
        identity = Serial.from_string(observation.raw_identity).to_string()
        if observation.stage == "accepted" and identity in yielded_identities:
            alias = aliases.get(identity)
            if alias is None:
                raise ValueError("discovered identity is missing from the alias map")
            if observation.source not in source_order[alias]:
                source_order[alias].append(observation.source)
    contributions: list[dict[str, object]] = []
    yielded_aliases = {aliases[identity] for identity in yielded_identities}
    for alias in sorted(yielded_aliases):
        order = source_order[alias]
        if not order:
            raise RuntimeError("yielded device has no source observation")
        contributions.append(
            {
                "alias": alias,
                "sources": sorted(order),
                "winner": order[0],
                "source_order": order,
            }
        )
    return contributions


def _find08_from_observations(
    observations: Sequence[_DiscoveryObservation],
    yielded_identities: set[str],
    aliases: Mapping[str, str],
) -> dict[str, object]:
    yielded_aliases = {aliases[identity] for identity in yielded_identities}
    by_alias: dict[str, dict[str, _DiscoveryObservation]] = defaultdict(dict)
    for observation in observations:
        if observation.stage != "accepted":
            continue
        identity = Serial.from_string(observation.raw_identity).to_string()
        alias = aliases.get(identity)
        if alias is None or alias not in yielded_aliases:
            continue
        by_alias[alias][observation.source] = observation
    evidence: list[tuple[str, str, int, int, str]] = []
    for alias, source_events in by_alias.items():
        udp = source_events.get("udp")
        mdns = source_events.get("mdns")
        if udp is None or mdns is None or mdns.connectivity != "wifi":
            continue
        if mdns.firmware_major is None or mdns.firmware_minor is None:
            continue
        evidence.append(
            (
                mdns.raw_identity,
                udp.raw_identity,
                mdns.firmware_major,
                mdns.firmware_minor,
                alias,
            )
        )
    return _normalise_find08_observations(evidence)


async def _measure_arm(
    *,
    arm: _Arm,
    scenario_id: str,
    pair_id: str,
    round_number: int,
    environment: Literal["emulator", "fleet"],
    revision: str,
    quiescence: str,
    confounds: Sequence[str],
    aliases: Mapping[str, str],
    timeout: float,
    max_response_time: float,
    idle_timeout_multiplier: float,
    emulator: _EmbeddedMeasurementEmulator | None,
) -> tuple[dict[str, object], frozenset[str]]:
    """Run one measured API call inside one caller-owned observation scope."""
    address = emulator.address if emulator is not None else "255.255.255.255"
    port = emulator.port if emulator is not None else 56700
    devices_to_close: list[Device] = []
    yielded_identities: set[str] = set()
    first_result_ns: int | None = None
    started_ns = time.monotonic_ns()
    source_scope = (
        _override_mdns_service_source(emulator.service_source)
        if arm == "merged" and emulator is not None
        else nullcontext()
    )
    try:
        with _capture_discovery_observations() as sink, source_scope:
            if arm == "baseline":
                device_stream = _direct_udp_devices(
                    timeout=timeout,
                    broadcast_address=address,
                    port=port,
                    max_response_time=max_response_time,
                    idle_timeout_multiplier=idle_timeout_multiplier,
                    device_timeout=DEFAULT_REQUEST_TIMEOUT,
                    max_retries=DEFAULT_MAX_RETRIES,
                )
            else:
                device_stream = discover(
                    timeout=timeout,
                    broadcast_address=address,
                    port=port,
                    max_response_time=max_response_time,
                    idle_timeout_multiplier=idle_timeout_multiplier,
                    device_timeout=DEFAULT_REQUEST_TIMEOUT,
                    max_retries=DEFAULT_MAX_RETRIES,
                )
            async with aclosing(device_stream):
                async for device in device_stream:
                    if first_result_ns is None:
                        first_result_ns = time.monotonic_ns() - started_ns
                    identity = Serial.from_string(device.serial).to_string()
                    yielded_identities.add(identity)
                    devices_to_close.append(device)
            elapsed_ns = time.monotonic_ns() - started_ns
            observations = sink.observations
    finally:
        for device in devices_to_close:
            await device.connection.close()

    row = _build_measurement_row(
        scenario_id=scenario_id,
        pair_id=pair_id,
        round_number=round_number,
        arm=arm,
        implementation_path="direct_udp" if arm == "baseline" else "merged_dual",
        environment=environment,
        revision=revision,
        quiescence=quiescence,
        confounds=confounds,
        elapsed_ns=elapsed_ns,
        first_result_ns=first_result_ns,
        devices=_source_contributions(observations, yielded_identities, aliases),
        target="owned_loopback_dynamic" if emulator is not None else "fleet",
        find08=_find08_from_observations(observations, yielded_identities, aliases),
        unique_count=len(yielded_identities),
    )
    return row, frozenset(aliases)


@asynccontextmanager
async def _no_emulator() -> AsyncGenerator[None, None]:
    """Provide the fleet branch with the same async ownership shape."""
    yield None


async def main_async(args: argparse.Namespace) -> int:
    """Run or validate the requested measurement workflow."""
    if args.validate_only:
        rows = _load_measurements(args.output)
        expected_revision = getattr(args, "expected_revision", None)
        has_fleet_evidence = any(row.get("environment") == "fleet" for row in rows)
        emulator_revisions = {
            str(row["revision"])
            for row in rows
            if row.get("environment") == "emulator"
            and row.get("arm") in _ARMS
            and set(row) == _QUALIFIED_ROW_KEYS
        }
        fleet_revisions = {
            str(row["revision"])
            for row in rows
            if row.get("environment") == "fleet"
            and row.get("arm") in _ARMS
            and set(row) == _QUALIFIED_ROW_KEYS
        }
        final_revision = getattr(args, "final_revision", None)
        if final_revision is None:
            shared_revisions = emulator_revisions & fleet_revisions
            final_revision = (
                next(iter(shared_revisions)) if len(shared_revisions) == 1 else None
            )
        _validate_measurements(
            rows,
            require_final_evidence=has_fleet_evidence,
            current_revision=final_revision,
            expected_revision=expected_revision,
        )
        if args.summary is not None:
            args.summary.parent.mkdir(parents=True, exist_ok=True)
            args.summary.write_text(_render_measurement_summary(rows), encoding="utf-8")
        return 0

    if args.rounds < 1:
        raise ValueError("--rounds must be at least one")
    if args.quiescence is None:
        raise ValueError("measurement collection requires --quiescence")
    if args.environment == "fleet" and args.alias_map is None:
        raise ValueError("--environment fleet requires an external --alias-map")
    if args.environment == "fleet" and args.mode == "paired" and args.rounds < 6:
        raise ValueError("paired fleet evidence requires at least six rounds")
    revision = _measurement_revision(getattr(args, "revision", None))
    scenario_id = f"{args.environment}-{revision[:12]}-{uuid.uuid4().hex[:12]}"
    emulator_context = (
        _EmbeddedMeasurementEmulator()
        if args.environment == "emulator"
        else _no_emulator()
    )
    async with emulator_context as emulator:
        aliases = (
            emulator.aliases
            if emulator is not None
            else _load_alias_map(args.alias_map)
        )
        forbidden_values = frozenset(aliases)
        for round_number in range(1, args.rounds + 1):
            pair_id = f"{scenario_id}-round-{round_number}"
            for arm in _arms_for_mode(args.mode):
                row, _ = await _measure_arm(
                    arm=arm,
                    scenario_id=scenario_id,
                    pair_id=pair_id,
                    round_number=round_number,
                    environment=args.environment,
                    revision=revision,
                    quiescence=args.quiescence,
                    confounds=args.confound,
                    aliases=aliases,
                    timeout=args.timeout,
                    max_response_time=args.max_response_time,
                    idle_timeout_multiplier=args.idle_timeout_multiplier,
                    emulator=emulator,
                )
                _append_measurement_row(
                    args.output,
                    row,
                    forbidden_values=forbidden_values,
                )

    rows = _load_measurements(args.output)
    _validate_measurements(rows)
    if args.summary is not None:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(_render_measurement_summary(rows), encoding="utf-8")
    return 0


def main() -> int:
    """Parse CLI arguments and run the measurement harness."""
    parser = argparse.ArgumentParser(
        description="Measure direct UDP and public merged LIFX discovery.",
    )
    parser.add_argument(
        "--mode",
        choices=("baseline-only", "merged-only", "paired"),
        default="paired",
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--revision")
    parser.add_argument("--expected-revision")
    parser.add_argument("--final-revision")
    parser.add_argument(
        "--environment", choices=("emulator", "fleet"), default="emulator"
    )
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=DISCOVERY_TIMEOUT)
    parser.add_argument("--max-response-time", type=float, default=MAX_RESPONSE_TIME)
    parser.add_argument(
        "--idle-timeout-multiplier",
        type=float,
        default=IDLE_TIMEOUT_MULTIPLIER,
    )
    parser.add_argument(
        "--quiescence",
        choices=("quiesced", "not_quiesced", "unknown"),
    )
    parser.add_argument(
        "--confound",
        action="append",
        choices=sorted(_CONFOUNDS),
        default=[],
    )
    parser.add_argument("--alias-map", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    try:
        return asyncio.run(main_async(args))
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    sys.exit(main())
