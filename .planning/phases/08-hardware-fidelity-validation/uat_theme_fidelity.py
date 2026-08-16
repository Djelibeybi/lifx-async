#!/usr/bin/env python3
"""Private, fail-closed Phase 8 Android and LAN MORPH fidelity tracer.

This intentionally remains phase-local UAT tooling. It never discovers devices or
accepts target identity on the command line: local targets supply the two approved
roles, while public progress uses roles and theme slugs only.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import math
import os
import re
import stat
import subprocess  # nosec B404 - fixed-argument adb is this UAT runner's boundary
import sys
import time
import uuid
import xml.etree.ElementTree as ET  # nosec B405 - authorised local tablet output
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypeAlias, TypeVar, cast

from lifx import Device, MatrixLight
from lifx.color import HSBK
from lifx.const import MAX_PALETTE_COLORS
from lifx.exceptions import (
    LifxConnectionError,
    LifxDeviceNotFoundError,
    LifxError,
    LifxNetworkError,
    LifxTimeoutError,
)
from lifx.products import get_product
from lifx.protocol.protocol_types import FirmwareEffect
from lifx.theme import Theme, ThemeLibrary
from lifx.theme.slug import derive_slug

OFFICIAL_THEME_SLUGS = ("cheerful", "mondrian")
INITIAL_APP_THEME = "cheerful"
APP_THEME_SEQUENCE = (
    "mondrian",
    "cheerful",
    "mondrian",
    "cheerful",
    "mondrian",
    "cheerful",
)
PRIVATE_ROOT = Path(".planning/local/phase-08-theme-fidelity")
SEMANTIC_RETRIES = 2
MAX_GROUP_DEVICE_SCROLLS = 5
ANDROID_KEEP_AWAKE_MASK = 7
EXIT_PASS = 0
EXIT_MISMATCH = 1
EXIT_INCOMPLETE = 2
EXIT_RESTORATION_FAILURE = 3
# A role-local completion is deliberately neither a whole-experiment pass nor a
# mismatch verdict.  It requires a later human reconciliation with the Tile run.
EXIT_ROLE_COMPLETE = 4
ROLE_ONLY_NON_TILE = "non-tile-matrix"
ROLE_ONLY_LUNA_PRODUCT_IDS = frozenset({219, 220})
ROLE_ONLY_LUNA_MODELS = frozenset({"LIFX Luna", "LIFX Luna Intl"})
LIFX_PACKAGE = "com.lifx.lifx"
LIFX_HOME_URI = "lifx:/home"
FX_TAB_RESOURCE_ID_SUFFIX = "ax_device_control_effects_tab"
SELECTOR_CLOSE_RESOURCE_ID_SUFFIX = "ax_device_control_close_button"
SERIAL_PATTERN = re.compile(r"^[0-9a-fA-F]{12}$")
RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

Control: TypeAlias = Mapping[str, str]
RunCommand = Callable[..., Any]
DeviceFactory = Callable[[str, str], Awaitable[object]]
PreflightEventRecorder = Callable[[Mapping[str, str]], None]
PreflightContactObserver = Callable[[str, str, str], None]
T = TypeVar("T")


class RunnerError(RuntimeError):
    """Base redacted failure with a locked process outcome."""

    exit_code = EXIT_INCOMPLETE


class AdbCommandError(RunnerError):
    """ADB failed without exposing command output or device identifiers."""


class SemanticLookupError(RunnerError):
    """A unique current semantic control could not be proved."""


class PreflightError(RunnerError):
    """Private configuration or non-mutating preflight was insufficient."""


class RestorationError(RunnerError):
    """A required state restoration attempt did not verify."""

    exit_code = EXIT_RESTORATION_FAILURE


def resolve_designated_run_directory(private_root: Path, run_id: str) -> Path:
    """Return a canonical run directory that cannot escape ``private_root``.

    Both resumption and finalisation consume an operator-supplied identifier.  The
    identifier must be precisely the UUID hexadecimal form generated for new runs;
    resolve the resulting path before any directory, permission, read or write
    operation so an existing symlink cannot redirect it outside the private root.
    """
    if not isinstance(run_id, str) or RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise PreflightError("run identifier is not canonical")
    try:
        resolved_root = private_root.resolve(strict=False)
        run_directory = (resolved_root / run_id).resolve(strict=False)
    except OSError as error:
        raise PreflightError("private run location is unavailable") from error
    if run_directory.parent != resolved_root:
        raise PreflightError("run identifier escaped the private root")
    return run_directory


def production_private_path_boundary() -> PrivatePathBoundary:
    """Return the fixed Phase 8 private root beneath this repository.

    The path is anchored to this source file rather than the caller's current
    directory, so launching the runner elsewhere cannot redirect private data.
    """
    repository_root = Path(__file__).resolve().parents[3]
    private_root = repository_root / PRIVATE_ROOT
    return PrivatePathBoundary(private_root, private_root / "targets.json")


def _canonical_private_path_boundary(
    boundary: PrivatePathBoundary,
) -> PrivatePathBoundary:
    """Reject symlinked, escaped, or non-directory private path authorities.

    This check deliberately precedes every private-root mkdir, chmod, read, or
    write.  The target file may be absent before first configuration, but when it
    exists it must be a direct regular ``targets.json`` child of the root.
    """
    try:
        requested_root = boundary.private_root.absolute()
        canonical_root = requested_root.resolve(strict=False)
    except OSError as error:
        raise PreflightError("private root is unavailable") from error
    if requested_root != canonical_root:
        raise PreflightError("private root must not traverse a symlink")
    if requested_root.exists() and (
        requested_root.is_symlink() or not requested_root.is_dir()
    ):
        raise PreflightError("private root is not a directory")

    requested_target = boundary.targets_path.absolute()
    expected_target = canonical_root / "targets.json"
    if requested_target != expected_target:
        raise PreflightError("private target path is not the designated file")
    try:
        canonical_target = requested_target.resolve(strict=False)
    except OSError as error:
        raise PreflightError("private target path is unavailable") from error
    if canonical_target != expected_target:
        raise PreflightError("private target path must not traverse a symlink")
    if requested_target.exists():
        try:
            target_mode = requested_target.lstat().st_mode
        except OSError as error:
            raise PreflightError("private target path is unavailable") from error
        if requested_target.is_symlink() or not stat.S_ISREG(target_mode):
            raise PreflightError("private target path is not a regular file")
    return PrivatePathBoundary(canonical_root, expected_target)


def resolve_private_path_boundary(
    targets_argument: Path | None,
    *,
    injected_boundary: PrivatePathBoundary | None = None,
) -> PrivatePathBoundary:
    """Resolve the only permitted private root and exact targets filename.

    ``injected_boundary`` is an in-process unit-test seam.  It cannot be reached
    from the production CLI, whose optional ``--targets`` spelling is accepted
    only when it denotes the fixed repository-relative location.
    """
    if injected_boundary is not None and targets_argument is not None:
        raise PreflightError("test private boundary does not accept CLI targets")
    if targets_argument is not None:
        if (
            targets_argument.is_absolute()
            or targets_argument != PRIVATE_ROOT / "targets.json"
        ):
            raise PreflightError("private target path is not the designated file")
    boundary = injected_boundary or production_private_path_boundary()
    return _canonical_private_path_boundary(boundary)


@dataclass(frozen=True)
class RunnerSettings:
    """Explicitly recorded time and path settings for one private run."""

    ui_wait_timeout: float = 10.0
    operator_action_timeout: float = 300.0
    stability_timeout: float = 15.0
    poll_interval: float = 0.5
    non_tile_settle_duration: float = 5.0
    max_theme_scrolls: int = 20
    targets_path: Path = PRIVATE_ROOT / "targets.json"
    private_root: Path = PRIVATE_ROOT


@dataclass(frozen=True)
class PrivatePathBoundary:
    """The sole private filesystem authority for one runner invocation.

    Production always derives this from the repository containing this runner.
    Tests may inject a separate boundary through :func:`main`, never through a
    command-line path override.
    """

    private_root: Path
    targets_path: Path


@dataclass(frozen=True)
class ThemeSpec:
    """The frozen, mechanically derived app record used by the tracer."""

    slug: str
    display_name: str
    category: str
    expected_palette: list[HSBK]
    record_sha256: str


@dataclass(frozen=True)
class TargetBinding:
    """Private target identity; do not put instances into public output."""

    role: str
    host: str
    serial: str
    app_label: str
    indoor_confirmed: bool
    quiesced_confirmed: bool
    app_group: str = ""


@dataclass(frozen=True)
class ManualRoleAttestation:
    """Private operator claim plus independent observed Morph configuration proof.

    UIAutomator cannot prove a selected target's identity once LIFX has closed the
    selector, nor can the Morph configuration surface prove its parent group or
    selected count. The opaque binding digest bridges the explicit operator claim
    to the subsequent exact LAN identity proof without public identifiers.
    """

    run_id: str
    operator_attested_role: str
    binding_digest: str
    timestamp: str
    operator_attested: bool
    ui_morph_config_observed: bool
    effect_name: bool
    effect_subtitle: bool
    effect_settings: bool
    theme_button: bool


@dataclass(frozen=True)
class InitialThemeAttestation:
    """Private operator claim for the theme hidden by the Morph configuration UI."""

    run_id: str
    operator_attested_role: str
    binding_digest: str
    timestamp: str
    initial_theme: str
    operator_attested: bool


@dataclass(frozen=True)
class PaletteObservation:
    """One retained LAN effect read while awaiting a stable palette."""

    monotonic_offset: float
    palette: list[HSBK]


@dataclass(frozen=True)
class CycleResult:
    """Public-safe result: role and slug, never target identifiers or UI text."""

    device_role: str
    theme_slug: str
    source: str
    cycle_index: int
    observations: list[PaletteObservation]
    stable_palette: list[HSBK] | None
    matches_expected: bool
    failure: str | None


@dataclass(frozen=True)
class StablePaletteResult:
    """Internal stable polling outcome preserving every transitional observation."""

    observations: list[PaletteObservation]
    stable_palette: list[HSBK] | None
    action_elapsed_seconds: float = 0.0
    stability_elapsed_seconds: float = 0.0


CycleKey: TypeAlias = tuple[str, str, str, int]


@dataclass(frozen=True)
class RunProvenance:
    """Every immutable fact that makes a private run safe to resume."""

    runner_revision: str
    app_version: str
    catalogue_fingerprint: str
    target_fingerprints: Mapping[str, str]
    firmware_by_role: Mapping[str, str]
    theme_records_sha256: str
    schedule_sha256: str
    effective_settings: Mapping[str, object]


@dataclass(frozen=True)
class EffectSnapshot:
    """Complete protocol effect state required for exact restoration."""

    effect_type: FirmwareEffect
    speed_ms: int
    duration: int
    palette: list[HSBK] | None
    sky_type: object | None
    cloud_saturation_min: int
    cloud_saturation_max: int


@dataclass(frozen=True)
class MatrixTileTopology:
    """The stable Tile geometry needed to restore and read its pixel matrix.

    Accelerometer measurements are deliberately excluded: the device can update
    them while it remains stationary from an operator's perspective, and no
    restoration command can reinstate a prior accelerometer reading.
    """

    tile_index: int
    user_x: float
    user_y: float
    width: int
    height: int


@dataclass(frozen=True)
class RestorationSnapshot:
    """Private, capability-complete state captured before any mutation."""

    power: int
    base_colour: HSBK
    effect: EffectSnapshot
    chain: list[object]
    tile_colours: list[list[HSBK]]
    uplight_colour: HSBK | None
    downlight_colours: list[HSBK] | None


@dataclass(frozen=True)
class RestorationResult:
    """Public-safe restoration verdict with no target identity."""

    device_role: str
    snapshot_complete: bool
    attempted: bool
    verified: bool
    failure: str | None


@dataclass(frozen=True)
class PublicDeviceRecord:
    """The sole device shape that may cross the private evidence boundary."""

    role: str
    device_class: str
    model: str
    product_id: int
    host_firmware: str


@dataclass(frozen=True)
class RunCheckpoint:
    """Restrictive private progress record used only to resume one frozen run."""

    run_id: str
    provenance: RunProvenance
    next_cycle: CycleKey | None
    cycles: list[CycleResult]
    terminal_status: str | None
    finalisable: bool
    snapshots: Mapping[str, object] = field(default_factory=dict)
    restorations: list[RestorationResult] = field(default_factory=list)
    events_path: str = ""
    diagnostics_path: str = ""
    terminal_cycle: CycleResult | None = None


@dataclass(frozen=True)
class PreflightReport:
    """Redacted facts established before the runner may mutate a light."""

    app_version: str
    catalogue_fingerprint: str
    metadata_by_role: Mapping[str, Mapping[str, object]]
    source_attestation: ManualRoleAttestation | None = None


def build_cycle_schedule() -> list[CycleKey]:
    """Build the locked app-alternating, library-grouped 24-cycle experiment."""
    schedule: list[CycleKey] = []
    for role in ("source-tile", "non-tile-matrix"):
        schedule.extend(
            (role, slug, "app", index)
            for slug, index in zip(APP_THEME_SEQUENCE, (1, 1, 2, 2, 3, 3), strict=True)
        )
        schedule.extend(
            (role, slug, "library", index)
            for slug in OFFICIAL_THEME_SLUGS
            for index in (1, 2, 3)
        )
    return schedule


def build_role_only_schedule(role: str) -> list[CycleKey]:
    """Return the immutable, non-resumable Luna-only measurement schedule."""
    if role != ROLE_ONLY_NON_TILE:
        raise PreflightError("role-only mode is restricted to non-tile-matrix")
    return [key for key in build_cycle_schedule() if key[0] == role]


def _stable_digest(value: object) -> str:
    """Hash public-safe canonical data without retaining private values in output."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def binding_digest(binding: TargetBinding) -> str:
    """Return the opaque private identity bridge for one approved binding."""
    return _stable_digest(
        {
            "role": binding.role,
            "host": binding.host,
            "serial": binding.serial,
            "app_label": binding.app_label,
            "app_group": binding.app_group,
        }
    )


def build_provenance(
    *,
    runner_revision: str,
    app_version: str,
    catalogue: str,
    target_fingerprints: Mapping[str, str],
    firmware_by_role: Mapping[str, str],
    theme_specs: Mapping[str, ThemeSpec],
    settings: RunnerSettings,
) -> RunProvenance:
    """Freeze every D-11 dimension before the first hardware mutation."""
    effective_settings = {
        "ui_wait_timeout": settings.ui_wait_timeout,
        "operator_action_timeout": settings.operator_action_timeout,
        "stability_timeout": settings.stability_timeout,
        "poll_interval": settings.poll_interval,
        "non_tile_settle_duration": settings.non_tile_settle_duration,
        "max_theme_scrolls": settings.max_theme_scrolls,
    }
    return RunProvenance(
        runner_revision=runner_revision,
        app_version=app_version,
        catalogue_fingerprint=catalogue,
        target_fingerprints=dict(target_fingerprints),
        firmware_by_role=dict(firmware_by_role),
        theme_records_sha256=_stable_digest(
            {slug: spec.record_sha256 for slug, spec in theme_specs.items()}
        ),
        schedule_sha256=_stable_digest(build_cycle_schedule()),
        effective_settings=effective_settings,
    )


def _live_firmware_by_role(
    metadata_by_role: Mapping[str, Mapping[str, object]],
    *,
    roles: Sequence[str],
) -> dict[str, str]:
    """Require the firmware strings returned by the exact currently-bound lights."""
    firmware: dict[str, str] = {}
    for role in roles:
        metadata = metadata_by_role.get(role)
        value = None if metadata is None else metadata.get("firmware")
        if not isinstance(value, str) or not value or value == "unknown":
            raise PreflightError("bound target firmware is unavailable")
        firmware[role] = value
    return firmware


def build_live_provenance(
    *,
    runner_revision: str,
    preflight: PreflightReport,
    bindings: Mapping[str, TargetBinding],
    theme_specs: Mapping[str, ThemeSpec],
    settings: RunnerSettings,
    roles: Sequence[str] = ("source-tile", "non-tile-matrix"),
) -> RunProvenance:
    """Build D-11 provenance from the current read-only Android and LAN boundary.

    The manual Morph screen cannot enumerate the picker without UI input.  Its
    ``catalogue_fingerprint`` is therefore the canonical fingerprint of two equal
    current Morph configuration hierarchy reads, while the independently frozen
    theme-record hashes bind the approved picker entries.  It is not a claim that
    the entire picker was navigated or selected.
    """
    if not isinstance(preflight.app_version, str) or not preflight.app_version:
        raise PreflightError("LIFX app version is unavailable")
    if (
        not isinstance(preflight.catalogue_fingerprint, str)
        or not preflight.catalogue_fingerprint
    ):
        raise PreflightError("current Morph catalogue fingerprint is unavailable")
    if any(role not in bindings for role in roles):
        raise PreflightError("private target schema is invalid")
    return build_provenance(
        runner_revision=runner_revision,
        app_version=preflight.app_version,
        catalogue=preflight.catalogue_fingerprint,
        target_fingerprints={role: binding_digest(bindings[role]) for role in roles},
        firmware_by_role=_live_firmware_by_role(
            preflight.metadata_by_role, roles=roles
        ),
        theme_specs=theme_specs,
        settings=settings,
    )


def validate_resume(saved: RunProvenance, current: RunProvenance) -> int:
    """Return the first missing schedule offset only for exact provenance equality."""
    if saved != current:
        raise PreflightError("resume provenance did not match the designated run")
    return 0


def _cycle_to_record(cycle: CycleResult) -> dict[str, object]:
    """Encode complete private cycle evidence for an exact future resume."""
    return {
        "device_role": cycle.device_role,
        "theme_slug": cycle.theme_slug,
        "source": cycle.source,
        "cycle_index": cycle.cycle_index,
        "observations": [
            {
                "monotonic_offset": observation.monotonic_offset,
                "palette": _public_palette(observation.palette),
            }
            for observation in cycle.observations
        ],
        "stable_palette": _public_palette(cycle.stable_palette),
        "matches_expected": cycle.matches_expected,
        "failure": cycle.failure,
    }


def _checkpoint_hsbk(value: object) -> HSBK:
    """Decode one exact protocol HSBK tuple without widening checkpoint input."""
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(
            not isinstance(component, int) or isinstance(component, bool)
            for component in value
        )
    ):
        raise PreflightError("private checkpoint cycle evidence is invalid")
    hue, saturation, brightness, kelvin = value
    if not all(0 <= component <= 0xFFFF for component in (hue, saturation, brightness)):
        raise PreflightError("private checkpoint cycle evidence is invalid")
    try:
        return HSBK(
            hue=hue * 360 / 0x10000,
            saturation=saturation / 0xFFFF,
            brightness=brightness / 0xFFFF,
            kelvin=kelvin,
        )
    except ValueError as error:
        raise PreflightError("private checkpoint cycle evidence is invalid") from error


def _checkpoint_palette(value: object) -> list[HSBK]:
    """Decode a complete JSON-safe palette without accepting adjacent shapes."""
    if not isinstance(value, list):
        raise PreflightError("private checkpoint cycle evidence is invalid")
    return [_checkpoint_hsbk(item) for item in value]


def cycle_from_checkpoint_record(record: object) -> CycleResult:
    """Decode one full CycleResult only from the current strict private schema."""
    required = {
        "device_role",
        "theme_slug",
        "source",
        "cycle_index",
        "observations",
        "stable_palette",
        "matches_expected",
        "failure",
    }
    if not isinstance(record, Mapping) or set(record) != required:
        raise PreflightError("private checkpoint cycle evidence is invalid")
    role = record["device_role"]
    slug = record["theme_slug"]
    source = record["source"]
    index = record["cycle_index"]
    matches = record["matches_expected"]
    failure = record["failure"]
    observations_value = record["observations"]
    stable_value = record["stable_palette"]
    if (
        not isinstance(role, str)
        or not isinstance(slug, str)
        or not isinstance(source, str)
        or role not in {"source-tile", "non-tile-matrix"}
        or slug not in OFFICIAL_THEME_SLUGS
        or source not in {"app", "library"}
        or not isinstance(index, int)
        or isinstance(index, bool)
        or index not in {1, 2, 3}
        or not isinstance(matches, bool)
        or (failure is not None and not isinstance(failure, str))
        or not isinstance(observations_value, list)
    ):
        raise PreflightError("private checkpoint cycle evidence is invalid")
    observations: list[PaletteObservation] = []
    prior_offset = -1.0
    for observation in observations_value:
        if not isinstance(observation, Mapping) or set(observation) != {
            "monotonic_offset",
            "palette",
        }:
            raise PreflightError("private checkpoint cycle evidence is invalid")
        offset = observation["monotonic_offset"]
        if (
            not isinstance(offset, (int, float))
            or isinstance(offset, bool)
            or not math.isfinite(offset)
            or offset < 0
            or offset < prior_offset
        ):
            raise PreflightError("private checkpoint cycle evidence is invalid")
        observations.append(
            PaletteObservation(
                float(offset), _checkpoint_palette(observation["palette"])
            )
        )
        prior_offset = float(offset)
    stable_palette = None if stable_value is None else _checkpoint_palette(stable_value)
    return CycleResult(
        role,
        slug,
        source,
        index,
        observations,
        stable_palette,
        matches,
        failure,
    )


def _checkpoint_cycle_key(value: object) -> CycleKey | None:
    """Decode the JSON tuple representation used for a checkpoint next-cycle key."""
    if value is None:
        return None
    if (
        not isinstance(value, list)
        or len(value) != 4
        or not all(isinstance(item, str) for item in value[:3])
        or not isinstance(value[3], int)
        or isinstance(value[3], bool)
    ):
        raise PreflightError("private checkpoint schedule is invalid")
    return (value[0], value[1], value[2], value[3])


def _validate_completed_cycle_prefix(
    completed: Mapping[CycleKey, CycleResult],
) -> None:
    """Require completed results to be the exact leading schedule prefix."""
    schedule = build_cycle_schedule()
    keys = list(completed)
    if len(keys) > len(schedule) or keys != schedule[: len(keys)]:
        raise PreflightError("private checkpoint schedule is invalid")
    for key, result in completed.items():
        if (
            result.device_role,
            result.theme_slug,
            result.source,
            result.cycle_index,
        ) != key:
            raise PreflightError("private checkpoint schedule is invalid")
        if result.failure is not None:
            raise PreflightError("private checkpoint schedule is invalid")


def completed_cycles_from_checkpoint(
    records: object, next_cycle: object
) -> dict[CycleKey, CycleResult]:
    """Restore a full strict checkpoint prefix only when its next key is exact."""
    if not isinstance(records, list):
        raise PreflightError("private checkpoint schedule is invalid")
    cycles = [cycle_from_checkpoint_record(record) for record in records]
    completed = {
        (cycle.device_role, cycle.theme_slug, cycle.source, cycle.cycle_index): cycle
        for cycle in cycles
    }
    if len(completed) != len(cycles):
        raise PreflightError("private checkpoint schedule is invalid")
    _validate_completed_cycle_prefix(completed)
    expected = next_unfinished_cycle(completed)
    if _checkpoint_cycle_key(next_cycle) != expected:
        raise PreflightError("private checkpoint schedule is invalid")
    return completed


def write_checkpoint(path: Path, checkpoint: RunCheckpoint) -> None:
    """Atomically write the private 0600 resume state after a state transition."""
    payload = {
        "run_id": checkpoint.run_id,
        "provenance": checkpoint.provenance.__dict__,
        "next_cycle": checkpoint.next_cycle,
        "cycles": [_cycle_to_record(cycle) for cycle in checkpoint.cycles],
        "snapshots": dict(checkpoint.snapshots),
        "restorations": [
            {
                "device_role": item.device_role,
                "snapshot_complete": item.snapshot_complete,
                "attempted": item.attempted,
                "verified": item.verified,
                "failure": item.failure,
            }
            for item in checkpoint.restorations
        ],
        "events_path": checkpoint.events_path,
        "diagnostics_path": checkpoint.diagnostics_path,
        "terminal_cycle": (
            None
            if checkpoint.terminal_cycle is None
            else _cycle_to_record(checkpoint.terminal_cycle)
        ),
        "terminal_status": checkpoint.terminal_status,
        "finalisable": checkpoint.finalisable,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _chmod(path.parent, 0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
        )
        _chmod(temporary, 0o600)
        os.replace(temporary, path)
        _chmod(path, 0o600)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise PreflightError("private checkpoint could not be written") from error


def load_checkpoint(path: Path) -> dict[str, object]:
    """Load the private checkpoint shape without accepting a partial resume record."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PreflightError("private checkpoint is unavailable") from error
    required = {
        "run_id",
        "provenance",
        "next_cycle",
        "cycles",
        "snapshots",
        "restorations",
        "events_path",
        "diagnostics_path",
        "terminal_cycle",
        "terminal_status",
        "finalisable",
    }
    if not isinstance(document, dict) or set(document) != required:
        raise PreflightError("private checkpoint schema is invalid")
    if (
        not isinstance(document["cycles"], list)
        or not isinstance(document["provenance"], dict)
        or not isinstance(document["snapshots"], dict)
        or not isinstance(document["restorations"], list)
        or (
            document["terminal_cycle"] is not None
            and not isinstance(document["terminal_cycle"], Mapping)
        )
    ):
        raise PreflightError("private checkpoint schema is invalid")
    if document["terminal_cycle"] is not None:
        cycle_from_checkpoint_record(document["terminal_cycle"])
    return cast(dict[str, object], document)


def run_preflight(
    *,
    bindings: Mapping[str, TargetBinding],
    metadata_by_role: Mapping[str, Mapping[str, object]],
    theme_specs: Mapping[str, ThemeSpec],
    provenance: RunProvenance,
) -> None:
    """Validate the locked role/theme experiment before a caller may mutate a device."""
    if tuple(theme_specs) != OFFICIAL_THEME_SLUGS:
        raise PreflightError("approved theme records missing or duplicated")
    if set(bindings) != {"source-tile", "non-tile-matrix"}:
        raise PreflightError("private target schema is invalid")
    if any(
        not binding.indoor_confirmed or not binding.quiesced_confirmed
        for binding in bindings.values()
    ):
        raise PreflightError("private targets are not approved and quiesced")
    source = metadata_by_role.get("source-tile")
    non_tile = metadata_by_role.get("non-tile-matrix")
    if (
        source is None
        or source.get("product_id") != 55
        or source.get("is_matrix") is not True
    ):
        raise PreflightError("source-tile live capability did not match")
    if non_tile is None:
        raise PreflightError("non-Tile target did not respond")
    validate_non_tile_metadata(non_tile)
    if not provenance.catalogue_fingerprint or not provenance.schedule_sha256:
        raise PreflightError("run provenance is incomplete")


async def run_official_cycles(
    *,
    theme_specs: Mapping[str, ThemeSpec],
    completed: Mapping[CycleKey, CycleResult],
    app_cycle: Callable[[str, ThemeSpec, int], Awaitable[CycleResult]],
    library_cycle: Callable[[str, ThemeSpec, int], Awaitable[CycleResult]],
) -> list[CycleResult]:
    """Execute missing fixed keys sequentially; mismatches never shorten the run."""
    results = list(completed.values())
    for role, slug, source, index in build_cycle_schedule():
        key = (role, slug, source, index)
        if key in completed:
            continue
        callback = app_cycle if source == "app" else library_cycle
        result = await callback(role, theme_specs[slug], index)
        if (
            result.device_role,
            result.theme_slug,
            result.source,
            result.cycle_index,
        ) != key:
            raise PreflightError(
                "cycle callback did not retain its locked schedule key"
            )
        results.append(result)
    return results


def next_unfinished_cycle(cycles: Mapping[CycleKey, CycleResult]) -> CycleKey | None:
    """Return the next locked key; completed observations are never replayed."""
    return next((key for key in build_cycle_schedule() if key not in cycles), None)


def validate_non_tile_metadata(metadata: Mapping[str, object]) -> None:
    """Reject unsafe secondary targets before any mutation or Android navigation."""
    product_id = metadata.get("product_id")
    if product_id == 55:
        raise PreflightError("non-Tile target is product 55")
    if metadata.get("is_matrix") is not True:
        raise PreflightError("non-Tile target is not a matrix light")
    if metadata.get("indoor") is not True:
        raise PreflightError("non-Tile target is not approved indoor hardware")
    if metadata.get("emulator") is True:
        raise PreflightError("non-Tile target is an emulator")
    if metadata.get("model") == "LIFX Candle":
        raise PreflightError("Candle is not an accepted non-Tile fallback")


def validate_role_only_luna_metadata(metadata: Mapping[str, object]) -> None:
    """Require the exact Luna identity immediately before a role-only mutation."""
    validate_non_tile_metadata(metadata)
    if metadata.get("product_id") not in ROLE_ONLY_LUNA_PRODUCT_IDS:
        raise PreflightError("role-only target is not an approved Luna product")
    if metadata.get("model") not in ROLE_ONLY_LUNA_MODELS:
        raise PreflightError("role-only target is not an approved Luna model")
    if metadata.get("device_class") != "MatrixLight":
        raise PreflightError("role-only Luna did not resolve as MatrixLight")


def validate_live_preflight_metadata(
    metadata_by_role: Mapping[str, Mapping[str, object]],
) -> None:
    """Require the exact two physical roles that Phase 8 is allowed to touch."""
    source = metadata_by_role["source-tile"]
    non_tile = metadata_by_role["non-tile-matrix"]
    if (
        source.get("model") != "LIFX Tile"
        or source.get("device_class") != "MatrixLight"
    ):
        raise PreflightError("source-tile is not the approved LIFX Tile")
    model = non_tile.get("model")
    device_class = non_tile.get("device_class")
    if not isinstance(model, str) or model not in {
        "LIFX Ceiling",
        "LIFX Ceiling 13x26",
        'LIFX Ceiling 13"',
        "LIFX Luna",
        "LIFX Luna Intl",
    }:
        raise PreflightError("non-Tile target is not an approved Ceiling or Luna")
    if model.startswith("LIFX Ceiling") and device_class != "CeilingLight":
        raise PreflightError("Ceiling target did not resolve as CeilingLight")
    if model.startswith("LIFX Luna") and device_class != "MatrixLight":
        raise PreflightError("Luna target did not resolve as MatrixLight")


def parse_app_version(package_details: str) -> str:
    """Return a safe app version token without retaining raw Android diagnostics."""
    match = re.search(r"^\s*versionName=([A-Za-z0-9._+-]+)\s*$", package_details, re.M)
    if match is None:
        raise PreflightError("LIFX app version is unavailable")
    return match.group(1)


def _effect_snapshot(effect: object) -> EffectSnapshot:
    """Copy every effect setting instead of relying on a mutable device object."""
    effect_type = getattr(effect, "effect_type", None)
    speed = getattr(effect, "speed", None)
    duration = getattr(effect, "duration", None)
    palette = getattr(effect, "palette", None)
    if not isinstance(effect_type, FirmwareEffect):
        raise PreflightError("effect state is incomplete")
    if not isinstance(speed, int) or not isinstance(duration, int):
        raise PreflightError("effect state is incomplete")
    if palette is not None and not isinstance(palette, list):
        raise PreflightError("effect state is incomplete")
    return EffectSnapshot(
        effect_type=effect_type,
        speed_ms=speed,
        duration=duration,
        palette=list(palette) if palette is not None else None,
        sky_type=getattr(effect, "sky_type", None),
        cloud_saturation_min=getattr(effect, "cloud_saturation_min", 0),
        cloud_saturation_max=getattr(effect, "cloud_saturation_max", 0),
    )


def _matrix_tile_topology(tile: object) -> MatrixTileTopology | object:
    """Project a live TileInfo onto its static, restoration-relevant topology."""
    fields = ("tile_index", "user_x", "user_y", "width", "height")
    values = tuple(getattr(tile, field, None) for field in fields)
    tile_index, user_x, user_y, width, height = values
    if (
        isinstance(tile_index, int)
        and isinstance(user_x, (int, float))
        and isinstance(user_y, (int, float))
        and isinstance(width, int)
        and isinstance(height, int)
    ):
        return MatrixTileTopology(
            tile_index=tile_index,
            user_x=float(user_x),
            user_y=float(user_y),
            width=width,
            height=height,
        )
    # Test adapters may expose only an opaque chain token.  Production
    # MatrixLight devices always supply TileInfo and therefore take the typed
    # branch above; retaining the token keeps injected unit adapters strict.
    return tile


def restoration_snapshots_match(
    expected: RestorationSnapshot, observed: object
) -> bool:
    """Compare every restorable field, excluding non-restorable accelerometers."""
    return isinstance(observed, RestorationSnapshot) and (
        expected.power == observed.power
        and expected.base_colour == observed.base_colour
        and expected.effect == observed.effect
        and expected.chain == observed.chain
        and expected.tile_colours == observed.tile_colours
        and expected.uplight_colour == observed.uplight_colour
        and expected.downlight_colours == observed.downlight_colours
    )


async def capture_snapshot(device: object) -> RestorationSnapshot:
    """Capture two equal, static complete baselines before any mutation is allowed."""
    try:
        power = await cast(Any, device).get_power()
        colour_and_power = await cast(Any, device).get_color()
        first_effect = _effect_snapshot(await cast(Any, device).get_effect())
        first_chain = list(await cast(Any, device).get_device_chain())
        first_pixels = [
            list(tile) for tile in await cast(Any, device).get_all_tile_colors()
        ]
        second_power = await cast(Any, device).get_power()
        second_colour_and_power = await cast(Any, device).get_color()
        second_effect = _effect_snapshot(await cast(Any, device).get_effect())
        second_pixels = [
            list(tile) for tile in await cast(Any, device).get_all_tile_colors()
        ]
    except (AttributeError, TypeError, ValueError) as error:
        raise PreflightError("snapshot state is incomplete") from error
    if (
        not isinstance(power, int)
        or not isinstance(colour_and_power, tuple)
        or len(colour_and_power) != 3
        or not isinstance(colour_and_power[0], HSBK)
        or not isinstance(colour_and_power[1], int)
        or not isinstance(second_power, int)
        or not isinstance(second_colour_and_power, tuple)
        or len(second_colour_and_power) != 3
        or not isinstance(second_colour_and_power[0], HSBK)
        or not isinstance(second_colour_and_power[1], int)
        or not first_chain
        or not first_pixels
        or any(not tile for tile in first_pixels)
    ):
        raise PreflightError("snapshot state is incomplete")
    if first_effect.effect_type is not FirmwareEffect.OFF:
        raise PreflightError("snapshot baseline must be static OFF")
    if (
        power != colour_and_power[1]
        or power != second_power
        or power != second_colour_and_power[1]
        or colour_and_power[0] != second_colour_and_power[0]
        or first_effect != second_effect
        or first_pixels != second_pixels
    ):
        raise PreflightError("snapshot baseline is not stable")
    uplight: HSBK | None = None
    downlight: list[HSBK] | None = None
    if hasattr(device, "get_uplight_color") or hasattr(device, "get_downlight_colors"):
        try:
            uplight = await cast(Any, device).get_uplight_color()
            downlight = list(await cast(Any, device).get_downlight_colors())
        except (AttributeError, TypeError, ValueError) as error:
            raise PreflightError("Ceiling snapshot state is incomplete") from error
        if not isinstance(uplight, HSBK) or not downlight:
            raise PreflightError("Ceiling snapshot state is incomplete")
    return RestorationSnapshot(
        power=power,
        base_colour=colour_and_power[0],
        effect=first_effect,
        chain=[_matrix_tile_topology(tile) for tile in first_chain],
        tile_colours=first_pixels,
        uplight_colour=uplight,
        downlight_colours=downlight,
    )


def effect_speed_seconds_for_restore(snapshot: EffectSnapshot) -> float:
    """Convert milliseconds without activating the matrix setter's default branch."""
    if snapshot.speed_ms:
        return snapshot.speed_ms / 1000.0
    if snapshot.effect_type is not FirmwareEffect.OFF:
        raise RestorationError("active effect cannot have zero restore speed")
    return 0.0001


async def _wait_for_effect_snapshot(
    device: object, snapshot: EffectSnapshot, *, poll_interval: float
) -> bool:
    """Require two complete snapshots after the unacknowledged effect setter."""
    prior_matches = False
    for _ in range(3):
        observed = _effect_snapshot(await cast(Any, device).get_effect())
        if observed == snapshot and prior_matches:
            return True
        prior_matches = observed == snapshot
        if poll_interval:
            await asyncio.sleep(poll_interval)
    return False


async def restore_snapshot(
    device: object, snapshot: RestorationSnapshot, *, poll_interval: float
) -> bool:
    """Restore effect, pixels, colour and power in the only safe order."""
    try:
        await cast(Any, device).set_effect(
            effect_type=snapshot.effect.effect_type,
            speed=effect_speed_seconds_for_restore(snapshot.effect),
            duration=snapshot.effect.duration,
            palette=snapshot.effect.palette,
            sky_type=snapshot.effect.sky_type,
            cloud_saturation_min=snapshot.effect.cloud_saturation_min,
            cloud_saturation_max=snapshot.effect.cloud_saturation_max,
        )
        if not await _wait_for_effect_snapshot(
            device, snapshot.effect, poll_interval=poll_interval
        ):
            return False
        await cast(Any, device).set_color(snapshot.base_colour)
        # set_color is device-wide for MatrixLight.  It must precede the exact
        # per-tile writes or it overwrites the restored pixel frame.
        for tile_index, colours in enumerate(snapshot.tile_colours):
            await cast(Any, device).set_matrix_colors(tile_index, colours)
        await cast(Any, device).set_power(snapshot.power)
    except (AttributeError, LifxError, TypeError, ValueError):
        return False
    return True


async def verify_restoration(
    device: object, snapshot: RestorationSnapshot, *, poll_interval: float = 0
) -> bool:
    """Poll stable full snapshots after writes; restoration never repeats a write."""
    for attempt in range(3):
        try:
            if restoration_snapshots_match(snapshot, await capture_snapshot(device)):
                return True
        except LifxError:
            return False
        except PreflightError:
            pass
        if attempt < 2 and poll_interval:
            await asyncio.sleep(poll_interval)
    return False


def _theme_source_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data/themes.jsonl"


def _read_theme_records(themes_path: Path) -> list[dict[str, object]]:
    """Read the committed source once; malformed input cannot become evidence."""
    try:
        records = [json.loads(line) for line in themes_path.read_text().splitlines()]
    except (OSError, json.JSONDecodeError) as error:
        raise PreflightError("theme source could not be read") from error
    if not all(isinstance(record, dict) for record in records):
        raise PreflightError("theme source is invalid")
    return cast(list[dict[str, object]], records)


def derive_ceiling_determinations(
    themes_path: Path | None = None,
) -> list[dict[str, object]]:
    """Mechanically derive the complete shipped 16-colour ceiling inventory."""
    records = _read_theme_records(themes_path or _theme_source_path())
    rows = [
        {
            "slug": record["slug"],
            "shipped_palette_length": 16,
            "determination": "device-ceiling-unresolvable",
            "true_length": None,
            "evidence_kind": "protocol-ceiling",
            "evidence_citation": (
                "data/themes.jsonl; src/lifx/const.py:MAX_PALETTE_COLORS"
            ),
        }
        for record in records
        if record.get("disposition") == "lifx-app"
        and isinstance(record.get("colors"), list)
        and len(cast(list[object], record["colors"])) == 16
        and isinstance(record.get("slug"), str)
    ]
    rows.sort(key=lambda row: cast(str, row["slug"]))
    if len(rows) != 25 or len({row["slug"] for row in rows}) != 25:
        raise PreflightError(
            "shipped ceiling inventory did not contain exactly 25 rows"
        )
    return rows


_PRIVATE_PATTERN = re.compile(
    r"(?:\b(?:\d{1,3}\.){3}\d{1,3}\b|\b[0-9a-f]{12}\b|"
    r"\b(?:serial|host|mac|token|cookie|account|adb)\b)",
    re.IGNORECASE,
)
_PRIVATE_KEYS = {"host", "serial", "mac", "token", "cookie", "account", "adb"}
_PUBLIC_ROOT_KEYS = {
    "schema_version",
    "phase",
    "run_id",
    "runner_revision",
    "app_version",
    "catalogue_fingerprint",
    "commands",
    "themes",
    "devices",
    "cycles",
    "ceiling_determinations",
    "restorations",
    "outcome",
    "completed_at_utc",
}
_PUBLIC_CYCLE_KEYS = {
    "device_role",
    "theme_slug",
    "source",
    "cycle_index",
    "stable_palette",
    "poll_count",
    "matches_expected",
    "failure",
}
_PUBLIC_THEME_KEYS = {
    "slug",
    "display_name",
    "category",
    "palette_count",
    "record_sha256",
}
_PUBLIC_DEVICE_KEYS = {
    "role",
    "device_class",
    "model",
    "product_id",
    "host_firmware",
}
_PUBLIC_RESTORATION_KEYS = {
    "device_role",
    "snapshot_complete",
    "verified",
    "failure",
}
_PUBLIC_DEVICE_ROLES = ("source-tile", "non-tile-matrix")


def _public_palette(colours: list[HSBK] | None) -> list[list[int]] | None:
    if colours is None:
        return None
    return [list(colour.as_tuple()) for colour in colours]


def build_public_results(
    *,
    run_id: str,
    provenance: RunProvenance,
    theme_specs: Mapping[str, ThemeSpec],
    devices: Sequence[PublicDeviceRecord],
    cycles: Sequence[CycleResult],
    restorations: Sequence[RestorationResult],
    outcome: str,
    completed_at_utc: str,
    themes_path: Path | None = None,
) -> dict[str, object]:
    """Project a private run through an explicit allowlist, never a redaction pass."""
    return {
        "schema_version": 1,
        "phase": "08-hardware-fidelity-validation",
        "run_id": run_id,
        "runner_revision": provenance.runner_revision,
        "app_version": provenance.app_version,
        "catalogue_fingerprint": provenance.catalogue_fingerprint,
        "commands": ["uat_theme_fidelity.py --run", "--finalise"],
        "themes": [
            {
                "slug": spec.slug,
                "display_name": spec.display_name,
                "category": spec.category,
                "palette_count": len(spec.expected_palette),
                "record_sha256": spec.record_sha256,
            }
            for spec in theme_specs.values()
        ],
        "devices": [
            {
                "role": device.role,
                "device_class": device.device_class,
                "model": device.model,
                "product_id": device.product_id,
                "host_firmware": device.host_firmware,
            }
            for device in devices
        ],
        "cycles": [
            {
                "device_role": cycle.device_role,
                "theme_slug": cycle.theme_slug,
                "source": cycle.source,
                "cycle_index": cycle.cycle_index,
                "stable_palette": _public_palette(cycle.stable_palette),
                "poll_count": len(cycle.observations),
                "matches_expected": cycle.matches_expected,
                "failure": cycle.failure,
            }
            for cycle in cycles
        ],
        "ceiling_determinations": derive_ceiling_determinations(themes_path),
        "restorations": [
            {
                "device_role": result.device_role,
                "snapshot_complete": result.snapshot_complete,
                "verified": result.verified,
                "failure": result.failure,
            }
            for result in restorations
        ],
        "outcome": outcome,
        "completed_at_utc": completed_at_utc,
    }


def _contains_private_value(value: object) -> bool:
    if isinstance(value, str):
        return bool(_PRIVATE_PATTERN.search(value))
    if isinstance(value, Mapping):
        return any(
            str(key).lower() in _PRIVATE_KEYS or _contains_private_value(item)
            for key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return any(_contains_private_value(item) for item in value)
    return False


def _is_public_integer(value: object) -> bool:
    """Return whether a value is a JSON integer rather than a bool lookalike."""
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_public_stable_palette(value: object) -> list[HSBK]:
    """Decode one non-empty protocol palette retained after stability polling."""
    try:
        palette = _checkpoint_palette(value)
    except PreflightError as error:
        raise PreflightError("public cycle stable palette is malformed") from error
    if not palette or len(palette) > MAX_PALETTE_COLORS:
        raise PreflightError("public cycle does not retain a complete stable palette")
    return palette


def _locked_public_themes() -> dict[str, Theme]:
    """Return library palettes after cross-checking their committed source records."""
    specs = load_theme_specs()
    themes: dict[str, Theme] = {}
    for slug in OFFICIAL_THEME_SLUGS:
        try:
            library_theme = ThemeLibrary.get(slug)
        except KeyError as error:
            raise PreflightError("committed theme library is incomplete") from error
        source_theme = Theme(list(specs[slug].expected_palette))
        if not library_theme.palette_equals(source_theme):
            raise PreflightError(
                "committed theme library disagrees with source records"
            )
        themes[slug] = library_theme
    return themes


def _validate_public_themes(themes: object) -> None:
    """Require public theme metadata to be the exact committed source projection."""
    specs = load_theme_specs()
    expected = [
        {
            "slug": spec.slug,
            "display_name": spec.display_name,
            "category": spec.category,
            "palette_count": len(spec.expected_palette),
            "record_sha256": spec.record_sha256,
        }
        for spec in specs.values()
    ]
    if (
        not isinstance(themes, list)
        or any(
            not isinstance(item, Mapping) or set(item) != _PUBLIC_THEME_KEYS
            for item in themes
        )
        or themes != expected
    ):
        raise PreflightError("public evidence theme records changed")


def _validate_public_cycles(cycles: object, themes: Mapping[str, Theme]) -> list[bool]:
    """Validate every cycle record before using it to derive the outcome."""
    if not isinstance(cycles, list) or len(cycles) != len(build_cycle_schedule()):
        raise PreflightError("public evidence must include the full 24-cycle schedule")
    expected = build_cycle_schedule()
    matches: list[bool] = []
    for item, key in zip(cycles, expected, strict=True):
        if not isinstance(item, Mapping) or set(item) != _PUBLIC_CYCLE_KEYS:
            raise PreflightError("public evidence cycle shape is invalid")
        observed = (
            item["device_role"],
            item["theme_slug"],
            item["source"],
            item["cycle_index"],
        )
        if observed != key:
            raise PreflightError("public evidence cycle order is incomplete or changed")
        if not _is_public_integer(item["cycle_index"]):
            raise PreflightError("public evidence cycle index is invalid")
        if not _is_public_integer(item["poll_count"]) or item["poll_count"] < 1:
            raise PreflightError("public evidence cycle polling is invalid")
        if not isinstance(item["matches_expected"], bool):
            raise PreflightError("public evidence cycle match verdict is invalid")
        if item["failure"] is not None:
            raise PreflightError("public evidence cycle is incomplete")
        stable_palette = _validate_public_stable_palette(item["stable_palette"])
        try:
            expected_theme = themes[cast(str, item["theme_slug"])]
        except KeyError as error:
            raise PreflightError("public evidence cycle theme is unknown") from error
        recomputed_match = expected_theme.palette_equals(
            theme_from_readback(stable_palette)
        )
        if item["matches_expected"] is not recomputed_match:
            raise PreflightError("public evidence cycle verdict disagrees with palette")
        matches.append(recomputed_match)
    return matches


def _validate_public_devices(devices: object) -> list[Mapping[str, object]]:
    """Require exactly the locked ordered device identities in public-safe form."""
    if not isinstance(devices, list) or len(devices) != len(_PUBLIC_DEVICE_ROLES):
        raise PreflightError("public evidence does not identify both device roles")
    validated: list[Mapping[str, object]] = []
    for item, role in zip(devices, _PUBLIC_DEVICE_ROLES, strict=True):
        if not isinstance(item, Mapping) or set(item) != _PUBLIC_DEVICE_KEYS:
            raise PreflightError("public evidence device shape is invalid")
        if item["role"] != role:
            raise PreflightError(
                "public evidence device roles are missing or reordered"
            )
        if (
            not isinstance(item["device_class"], str)
            or not isinstance(item["model"], str)
            or not _is_public_integer(item["product_id"])
            or not isinstance(item["host_firmware"], str)
        ):
            raise PreflightError("public evidence device fields are invalid")
        validated.append(item)
    source, non_tile = validated
    validate_live_preflight_metadata(
        {
            "source-tile": {
                "model": source["model"],
                "device_class": source["device_class"],
            },
            "non-tile-matrix": {
                "model": non_tile["model"],
                "device_class": non_tile["device_class"],
            },
        }
    )
    if source["product_id"] != 55:
        raise PreflightError("public evidence source product is invalid")
    validate_non_tile_metadata(
        {
            "product_id": non_tile["product_id"],
            "is_matrix": non_tile["device_class"] in {"MatrixLight", "CeilingLight"},
            "indoor": True,
            "emulator": False,
            "model": non_tile["model"],
        }
    )
    return validated


def _validate_public_restorations(restorations: object) -> None:
    """Require exactly one complete, verified restoration for each locked role."""
    if not isinstance(restorations, list) or len(restorations) != len(
        _PUBLIC_DEVICE_ROLES
    ):
        raise PreflightError("public evidence requires restoration for both roles")
    for item, role in zip(restorations, _PUBLIC_DEVICE_ROLES, strict=True):
        if not isinstance(item, Mapping) or set(item) != _PUBLIC_RESTORATION_KEYS:
            raise PreflightError("public evidence restoration shape is invalid")
        if item["device_role"] != role:
            raise PreflightError(
                "public evidence restoration roles are missing or reordered"
            )
        if (
            item["snapshot_complete"] is not True
            or item["verified"] is not True
            or item["failure"] is not None
        ):
            raise PreflightError("public evidence restoration is incomplete")


def validate_public_results(results: Mapping[str, object]) -> None:
    """Reject malformed, incomplete or private evidence before any official write."""
    if _contains_private_value(results):
        raise PreflightError("public evidence contains private identifiers")
    if set(results) != _PUBLIC_ROOT_KEYS:
        raise PreflightError("public evidence has unexpected or missing keys")
    if (
        results["schema_version"] != 1
        or results["phase"] != "08-hardware-fidelity-validation"
    ):
        raise PreflightError("public evidence identity is invalid")
    if results["commands"] != ["uat_theme_fidelity.py --run", "--finalise"]:
        raise PreflightError("public evidence commands are invalid")
    if not all(
        isinstance(results[key], str)
        for key in (
            "run_id",
            "runner_revision",
            "app_version",
            "catalogue_fingerprint",
            "completed_at_utc",
        )
    ):
        raise PreflightError("public evidence root fields are invalid")
    outcome = results.get("outcome")
    if outcome not in {"pass", "mismatch"}:
        raise PreflightError("only complete restored outcomes are finalisable")
    _validate_public_themes(results["themes"])
    cycles = _validate_public_cycles(results.get("cycles"), _locked_public_themes())
    _validate_public_devices(results.get("devices"))
    _validate_public_restorations(results.get("restorations"))
    if (outcome == "pass" and not all(cycles)) or (
        outcome == "mismatch" and not any(not match for match in cycles)
    ):
        raise PreflightError("public evidence outcome did not match cycle verdicts")
    determinations = results.get("ceiling_determinations")
    if determinations != derive_ceiling_determinations():
        raise PreflightError("public evidence ceiling inventory changed")


def render_uat_markdown(results: Mapping[str, object]) -> str:
    """Render a review surface solely from already validated JSON authority."""
    validate_public_results(results)
    lines = [
        "# Phase 08 Hardware Fidelity UAT",
        "",
        f"Outcome: `{results['outcome']}`",
        "",
        "## Devices",
    ]
    for device in cast(list[Mapping[str, object]], results["devices"]):
        lines.append(
            "- {role}: {model} (product {product}, firmware {firmware})".format(
                role=device["role"],
                model=device["model"],
                product=device["product_id"],
                firmware=device["host_firmware"],
            )
        )
    lines.extend(["", "## Cycles"])
    for cycle in cast(list[Mapping[str, object]], results["cycles"]):
        lines.append(
            "- {device_role} {theme_slug} {source} {cycle_index}: "
            "{matches_expected}".format(**cycle)
        )
    lines.extend(["", "## Ceiling determinations"])
    for row in cast(list[Mapping[str, object]], results["ceiling_determinations"]):
        lines.append(f"- {row['slug']}: {row['determination']}")
    return "\n".join(lines) + "\n"


def write_official_evidence(
    results: Mapping[str, object],
    *,
    output_directory: Path,
    filesystem: FileSystemAdapter | None = None,
) -> tuple[Path, Path]:
    """Validate and stage JSON plus derived Markdown before publishing them."""
    validate_public_results(results)
    markdown = render_uat_markdown(results)
    filesystem = filesystem or ProductionFileSystemAdapter()
    filesystem.mkdir(output_directory)
    json_path = output_directory / "08-UAT-RESULTS.json"
    markdown_path = output_directory / "08-UAT.md"
    json_temp = json_path.with_suffix(".json.tmp")
    markdown_temp = markdown_path.with_suffix(".md.tmp")
    try:
        filesystem.write_text(
            json_temp, json.dumps(results, indent=2, sort_keys=True) + "\n", 0o644
        )
        filesystem.write_text(markdown_temp, markdown, 0o644)
        parsed = json.loads(filesystem.read_text(json_temp))
        validate_public_results(cast(Mapping[str, object], parsed))
        if filesystem.read_text(markdown_temp) != markdown:
            raise PreflightError("rendered Markdown did not round-trip")
        filesystem.replace(json_temp, json_path)
        filesystem.replace(markdown_temp, markdown_path)
    except (OSError, json.JSONDecodeError) as error:
        filesystem.unlink(json_temp)
        filesystem.unlink(markdown_temp)
        raise PreflightError("official evidence could not be written") from error
    return json_path, markdown_path


class MatrixDevice(Protocol):
    """Narrow device adapter for production and injected orchestration tests."""

    async def get_effect(self) -> Any: ...  # pragma: no cover - typing declaration

    async def set_effect(self, **kwargs: Any) -> None: ...  # pragma: no cover


class AdbAdapter(Protocol):
    """The only Android subprocess seam used by the complete runner."""

    def command(self, *arguments: str, timeout: float) -> str: ...  # pragma: no cover


class DeviceAdapter(Protocol):
    """Live-LAN boundary; tests supply devices without addressing hardware."""

    async def connect(
        self, binding: TargetBinding
    ) -> MatrixDevice: ...  # pragma: no cover

    async def metadata(
        self, binding: TargetBinding, device: MatrixDevice
    ) -> Mapping[str, object]: ...  # pragma: no cover

    async def close(self, device: MatrixDevice) -> None: ...  # pragma: no cover


class ClockAdapter(Protocol):
    """Clock and sleep boundary for deterministic stability and cleanup tests."""

    def utc_now(self) -> str: ...  # pragma: no cover


class CheckpointStore(Protocol):
    """Restrictive checkpoint persistence boundary."""

    def write(
        self, path: Path, checkpoint: RunCheckpoint
    ) -> None: ...  # pragma: no cover

    def load(self, path: Path) -> dict[str, object]: ...  # pragma: no cover


class FileSystemAdapter(Protocol):
    """Public-evidence filesystem boundary."""

    def mkdir(self, path: Path) -> None: ...  # pragma: no cover

    def write_text(
        self, path: Path, text: str, mode: int
    ) -> None: ...  # pragma: no cover

    def read_text(self, path: Path) -> str: ...  # pragma: no cover

    def replace(self, source: Path, destination: Path) -> None: ...  # pragma: no cover

    def unlink(self, path: Path) -> None: ...  # pragma: no cover


class EvidenceWriter(Protocol):
    """Allow a finalisation test to prove no official write was attempted."""

    def write(
        self, results: Mapping[str, object], *, output_directory: Path
    ) -> tuple[Path, Path]: ...  # pragma: no cover


class ProductionAdbAdapter:
    """Production implementation retaining the existing fixed-argument ADB guard."""

    def command(self, *arguments: str, timeout: float) -> str:
        return adb(*arguments, timeout=timeout)


class ProductionDeviceAdapter:
    """Production LAN implementation for the two already-bound private devices."""

    def __init__(
        self,
        *,
        device_factory: DeviceFactory | None = None,
        contact_observer: PreflightContactObserver | None = None,
    ) -> None:
        self._device_factory = device_factory or Device.connect
        self._contact_observer = contact_observer or (lambda role, stage, status: None)

    async def _close_partial(self, device: object) -> None:
        """Best-effort close before the only permitted fresh contact retry."""
        try:
            await cast(Any, device).close()
        except LifxError:
            pass

    async def connect(self, binding: TargetBinding) -> MatrixDevice:
        """Make at most two fresh read-only contacts before preflight gives up."""
        contact_errors = (
            LifxTimeoutError,
            LifxDeviceNotFoundError,
            LifxConnectionError,
            LifxNetworkError,
        )
        for attempt in range(2):
            device: object | None = None
            try:
                device = await self._device_factory(binding.host, binding.serial)
                if not isinstance(device, MatrixLight):
                    await self._close_partial(device)
                    raise PreflightError("bound target is not a matrix light")
                await device.__aenter__()
                if device.label != binding.app_label:
                    await self._close_partial(device)
                    raise PreflightError("bound target label did not match")
                return cast(MatrixDevice, device)
            except contact_errors as error:
                if device is not None:
                    await self._close_partial(device)
                if attempt == 0:
                    self._contact_observer(binding.role, "contact", "retrying")
                    continue
                raise PreflightError("bound target contact is unavailable") from error
        raise AssertionError("unreachable fresh-contact retry loop")  # pragma: no cover

    async def metadata(
        self, binding: TargetBinding, device: MatrixDevice
    ) -> Mapping[str, object]:
        version = await cast(Any, device).get_version()
        product_id = getattr(version, "product", None)
        if not isinstance(product_id, int):
            raise PreflightError("bound target product identity is unavailable")
        product = get_product(product_id)
        return {
            "product_id": product_id,
            "is_matrix": product.has_matrix and isinstance(device, MatrixLight),
            "indoor": binding.indoor_confirmed,
            "emulator": False,
            "model": product.name,
            "firmware": str(getattr(version, "version", "unknown")),
            "device_class": type(device).__name__,
        }

    async def close(self, device: MatrixDevice) -> None:
        await cast(Any, device).close()


class ProductionClockAdapter:
    """Production wall-clock seam; polling itself remains injected per operation."""

    def utc_now(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class PrivateCheckpointStore:
    """Production restrictive checkpoint implementation."""

    def write(self, path: Path, checkpoint: RunCheckpoint) -> None:
        write_checkpoint(path, checkpoint)

    def load(self, path: Path) -> dict[str, object]:
        return load_checkpoint(path)


class ProductionFileSystemAdapter:
    """Production file implementation used only after in-memory validation."""

    def mkdir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def write_text(self, path: Path, text: str, mode: int) -> None:
        path.write_text(text, encoding="utf-8")
        _chmod(path, mode)

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def replace(self, source: Path, destination: Path) -> None:
        os.replace(source, destination)

    def unlink(self, path: Path) -> None:
        path.unlink(missing_ok=True)


class ProductionEvidenceWriter:
    """Production authoritative JSON/Markdown writer."""

    def write(
        self, results: Mapping[str, object], *, output_directory: Path
    ) -> tuple[Path, Path]:
        return write_official_evidence(results, output_directory=output_directory)


@dataclass(frozen=True)
class LifecycleResult:
    """Private completion record, deliberately separate from public evidence."""

    run_id: str
    cycles: list[CycleResult]
    restorations: list[RestorationResult]
    outcome: str
    exit_code: int
    finalisable: bool
    devices: list[PublicDeviceRecord] = field(default_factory=list)


def _private_snapshot_record(snapshot: RestorationSnapshot) -> dict[str, object]:
    """Record private audit state; checkpoints never restore a crashed process."""

    topology: list[dict[str, int | float] | None] = []
    for tile in snapshot.chain:
        if isinstance(tile, MatrixTileTopology):
            topology.append(
                {
                    "tile_index": tile.tile_index,
                    "user_x": tile.user_x,
                    "user_y": tile.user_y,
                    "width": tile.width,
                    "height": tile.height,
                }
            )
        else:
            topology.append(None)
    return {
        "snapshot_format": "audit-only-v1",
        "restore_from_checkpoint": False,
        "power": snapshot.power,
        "base_colour": list(snapshot.base_colour.as_tuple()),
        "effect": {
            "effect_type": int(snapshot.effect.effect_type),
            "speed_ms": snapshot.effect.speed_ms,
            "duration": snapshot.effect.duration,
            "palette": _public_palette(snapshot.effect.palette),
            "sky_type": str(snapshot.effect.sky_type),
            "cloud_saturation_min": snapshot.effect.cloud_saturation_min,
            "cloud_saturation_max": snapshot.effect.cloud_saturation_max,
        },
        "topology": topology,
        "tile_colours": [_public_palette(colours) for colours in snapshot.tile_colours],
        "uplight_colour": _public_palette([snapshot.uplight_colour])
        if snapshot.uplight_colour
        else None,
        "downlight_colours": _public_palette(snapshot.downlight_colours),
    }


async def run_designated_lifecycle(
    *,
    run_id: str,
    bindings: Mapping[str, TargetBinding],
    theme_specs: Mapping[str, ThemeSpec],
    provenance: RunProvenance,
    device_adapter: DeviceAdapter,
    checkpoint_store: CheckpointStore,
    checkpoint_path: Path,
    app_cycle: Callable[[str, ThemeSpec, int, MatrixDevice], Awaitable[CycleResult]],
    library_cycle: Callable[
        [str, ThemeSpec, int, MatrixDevice], Awaitable[CycleResult]
    ],
    completed: Mapping[CycleKey, CycleResult] | None = None,
    activate_morph: Callable[[str, MatrixDevice], Awaitable[None]] | None = None,
    restoration_poll_interval: float = 0,
    designated_role: str | None = None,
) -> LifecycleResult:
    """Run both bound devices sequentially and restore every post-mutation path.

    This is intentionally callback-driven: the production CLI supplies Android/LAN
    operations while unit tests prove all outcomes with no network or tablet access.
    The durable initial checkpoint is the mutation boundary: failures before it
    cannot have changed either light and must not be fabricated as restoration
    failures.
    """
    devices: dict[str, MatrixDevice] = {}
    snapshots: dict[str, RestorationSnapshot] = {}
    metadata: Mapping[str, Mapping[str, object]] = {}
    results = dict(completed or {})
    _validate_completed_cycle_prefix(results)
    pending_at_start = next_unfinished_cycle(results)
    if designated_role is not None and designated_role not in bindings:
        raise PreflightError("designated role is unavailable")
    if (
        designated_role is not None
        and pending_at_start is not None
        and pending_at_start[0] != designated_role
    ):
        raise PreflightError("designated role does not match the pending cycle")
    activated_roles: set[str] = set()
    restorations: list[RestorationResult] = []
    outcome = "incomplete"
    exit_code = EXIT_INCOMPLETE
    mutation_boundary = False
    terminal_cycle: CycleResult | None = None
    try:
        for role in ("source-tile", "non-tile-matrix"):
            binding = bindings[role]
            device = await device_adapter.connect(binding)
            devices[role] = device
        metadata = {
            role: await device_adapter.metadata(bindings[role], devices[role])
            for role in devices
        }
        run_preflight(
            bindings=bindings,
            metadata_by_role=metadata,
            theme_specs=theme_specs,
            provenance=provenance,
        )
        # The generic preflight establishes Matrix capability, but only this
        # exact identity gate keeps a direct full ``--run`` from writing to a
        # Path, Candle, or another unapproved matrix product.
        validate_live_preflight_metadata(metadata)
        for role, device in devices.items():
            snapshots[role] = await capture_snapshot(device)
        snapshot_records = {
            role: _private_snapshot_record(snapshot)
            for role, snapshot in snapshots.items()
        }
        checkpoint_store.write(
            checkpoint_path,
            RunCheckpoint(
                run_id,
                provenance,
                next_unfinished_cycle(results),
                list(results.values()),
                None,
                False,
                snapshots=snapshot_records,
                events_path=str(checkpoint_path.parent / "trace.jsonl"),
                diagnostics_path=str(checkpoint_path.parent / "diagnostics"),
            ),
        )
        for role, slug, source, index in build_cycle_schedule():
            key = (role, slug, source, index)
            if key in results:
                continue
            if designated_role is not None and role != designated_role:
                break
            # No activation or cycle callback may run until both snapshots are
            # durable in the private checkpoint.  Set this before the first
            # callback so an activation failure still restores both devices.
            mutation_boundary = True
            if source == "app" and role not in activated_roles:
                if activate_morph is not None:
                    await activate_morph(role, devices[role])
                activated_roles.add(role)
            callback = app_cycle if source == "app" else library_cycle
            result = await callback(role, theme_specs[slug], index, devices[role])
            if (
                result.device_role,
                result.theme_slug,
                result.source,
                result.cycle_index,
            ) != key:
                raise PreflightError("cycle callback did not retain its locked key")
            if result.failure is not None:
                terminal_cycle = result
                _write_private_event(
                    checkpoint_path.parent,
                    {
                        "event": "cycle-incomplete",
                        "cycle": _cycle_to_record(result),
                    },
                )
                checkpoint_store.write(
                    checkpoint_path,
                    RunCheckpoint(
                        run_id,
                        provenance,
                        next_unfinished_cycle(results),
                        list(results.values()),
                        "incomplete",
                        False,
                        snapshots=snapshot_records,
                        events_path=str(checkpoint_path.parent / "trace.jsonl"),
                        diagnostics_path=str(checkpoint_path.parent / "diagnostics"),
                        terminal_cycle=terminal_cycle,
                    ),
                )
                raise PreflightError("cycle readback is incomplete")
            results[key] = result
            checkpoint_store.write(
                checkpoint_path,
                RunCheckpoint(
                    run_id,
                    provenance,
                    next_unfinished_cycle(results),
                    list(results.values()),
                    None,
                    False,
                    snapshots=snapshot_records,
                    events_path=str(checkpoint_path.parent / "trace.jsonl"),
                    diagnostics_path=str(checkpoint_path.parent / "diagnostics"),
                ),
            )
        if next_unfinished_cycle(results) is not None:
            outcome = "incomplete"
            exit_code = EXIT_INCOMPLETE
        else:
            outcome = (
                "pass"
                if all(item.matches_expected for item in results.values())
                else "mismatch"
            )
            exit_code = EXIT_PASS if outcome == "pass" else EXIT_MISMATCH
    except (KeyboardInterrupt, asyncio.CancelledError):
        outcome = "incomplete"
        raise
    except RunnerError:
        outcome = "incomplete"
    finally:
        restoration_failed = False
        if mutation_boundary:
            for role in ("source-tile", "non-tile-matrix"):
                device = devices[role]
                snapshot = snapshots[role]
                try:
                    restored = await restore_snapshot(
                        device, snapshot, poll_interval=restoration_poll_interval
                    )
                    verified = restored and (
                        await verify_restoration(
                            device, snapshot, poll_interval=restoration_poll_interval
                        )
                        if restoration_poll_interval
                        else await verify_restoration(device, snapshot)
                    )
                except Exception:
                    restored = False
                    verified = False
                restorations.append(
                    RestorationResult(
                        role,
                        True,
                        restored,
                        verified,
                        None if verified else "restore verification failed",
                    )
                )
                restoration_failed = restoration_failed or not verified
        for device in devices.values():
            try:
                await device_adapter.close(device)
            except Exception:
                restoration_failed = restoration_failed or mutation_boundary
        if mutation_boundary and restoration_failed:
            outcome = "restoration_failure"
            exit_code = EXIT_RESTORATION_FAILURE
        finalisable = (
            mutation_boundary
            and outcome in {"pass", "mismatch"}
            and all(result.verified for result in restorations)
        )
        if mutation_boundary:
            checkpoint_store.write(
                checkpoint_path,
                RunCheckpoint(
                    run_id,
                    provenance,
                    next_unfinished_cycle(results),
                    list(results.values()),
                    outcome,
                    finalisable,
                    snapshots={
                        role: _private_snapshot_record(snapshot)
                        for role, snapshot in snapshots.items()
                    },
                    restorations=restorations,
                    events_path=str(checkpoint_path.parent / "trace.jsonl"),
                    diagnostics_path=str(checkpoint_path.parent / "diagnostics"),
                    terminal_cycle=terminal_cycle,
                ),
            )
    return LifecycleResult(
        run_id,
        list(results.values()),
        restorations,
        outcome,
        exit_code,
        finalisable,
        [
            PublicDeviceRecord(
                role=role,
                device_class=cast(str, item.get("device_class", "MatrixLight")),
                model=cast(str, item.get("model", "unknown")),
                product_id=cast(int, item.get("product_id", -1)),
                host_firmware=cast(str, item.get("firmware", "unknown")),
            )
            for role, item in metadata.items()
        ],
    )


async def run_role_only_lifecycle(
    *,
    run_id: str,
    bindings: Mapping[str, TargetBinding],
    theme_specs: Mapping[str, ThemeSpec],
    provenance: RunProvenance,
    device_adapter: DeviceAdapter,
    checkpoint_store: CheckpointStore,
    checkpoint_path: Path,
    app_cycle: Callable[[str, ThemeSpec, int, MatrixDevice], Awaitable[CycleResult]],
    library_cycle: Callable[
        [str, ThemeSpec, int, MatrixDevice], Awaitable[CycleResult]
    ],
    activate_morph: Callable[[str, MatrixDevice], Awaitable[None]] | None = None,
    restoration_poll_interval: float = 0,
) -> LifecycleResult:
    """Run a fresh Luna-only session that cannot become official evidence.

    This intentionally does not share a schedule prefix, checkpoint, device
    connection, baseline, or restoration path with the earlier Tile session.
    It is a bounded reconciliation artefact, never a partial full-run resume.
    """
    role = ROLE_ONLY_NON_TILE
    if set(bindings) != {"source-tile", role}:
        raise PreflightError("private target schema is invalid")
    device: MatrixDevice | None = None
    snapshot: RestorationSnapshot | None = None
    metadata: Mapping[str, object] = {}
    results: list[CycleResult] = []
    restorations: list[RestorationResult] = []
    mutation_boundary = False
    terminal_cycle: CycleResult | None = None
    outcome = "incomplete"
    exit_code = EXIT_INCOMPLETE
    try:
        binding = bindings[role]
        device = await device_adapter.connect(binding)
        metadata = await device_adapter.metadata(binding, device)
        validate_role_only_luna_metadata(metadata)
        snapshot = await capture_snapshot(device)
        snapshot_record = _private_snapshot_record(snapshot)
        checkpoint_store.write(
            checkpoint_path,
            RunCheckpoint(
                run_id,
                provenance,
                build_role_only_schedule(role)[0],
                [],
                None,
                False,
                snapshots={role: snapshot_record},
                events_path=str(checkpoint_path.parent / "trace.jsonl"),
                diagnostics_path=str(checkpoint_path.parent / "diagnostics"),
            ),
        )
        for current_role, slug, source, index in build_role_only_schedule(role):
            mutation_boundary = True
            if source == "app" and not any(item.source == "app" for item in results):
                if activate_morph is not None:
                    await activate_morph(current_role, device)
            callback = app_cycle if source == "app" else library_cycle
            result = await callback(current_role, theme_specs[slug], index, device)
            key = (current_role, slug, source, index)
            if (
                result.device_role,
                result.theme_slug,
                result.source,
                result.cycle_index,
            ) != key:
                raise PreflightError("cycle callback did not retain its locked key")
            if result.failure is not None:
                terminal_cycle = result
                _write_private_event(
                    checkpoint_path.parent,
                    {"event": "cycle-incomplete", "cycle": _cycle_to_record(result)},
                )
                raise PreflightError("cycle readback is incomplete")
            results.append(result)
            next_key = (
                build_role_only_schedule(role)[len(results)]
                if len(results) < len(build_role_only_schedule(role))
                else None
            )
            checkpoint_store.write(
                checkpoint_path,
                RunCheckpoint(
                    run_id,
                    provenance,
                    next_key,
                    results,
                    None,
                    False,
                    snapshots={role: snapshot_record},
                    events_path=str(checkpoint_path.parent / "trace.jsonl"),
                    diagnostics_path=str(checkpoint_path.parent / "diagnostics"),
                ),
            )
        outcome = "role-complete/manual-reconciliation-needed"
        exit_code = EXIT_ROLE_COMPLETE
    except (KeyboardInterrupt, asyncio.CancelledError):
        raise
    except RunnerError:
        outcome = "incomplete"
    finally:
        restoration_failed = False
        if mutation_boundary and device is not None and snapshot is not None:
            try:
                restored = await restore_snapshot(
                    device, snapshot, poll_interval=restoration_poll_interval
                )
                verified = restored and await verify_restoration(
                    device, snapshot, poll_interval=restoration_poll_interval
                )
            except Exception:
                restored = False
                verified = False
            restorations.append(
                RestorationResult(
                    role,
                    True,
                    restored,
                    verified,
                    None if verified else "restore verification failed",
                )
            )
            restoration_failed = not verified
        if device is not None:
            try:
                await device_adapter.close(device)
            except Exception:
                restoration_failed = restoration_failed or mutation_boundary
        if mutation_boundary and restoration_failed:
            outcome = "restoration_failure"
            exit_code = EXIT_RESTORATION_FAILURE
        if mutation_boundary and snapshot is not None:
            checkpoint_store.write(
                checkpoint_path,
                RunCheckpoint(
                    run_id,
                    provenance,
                    (
                        None
                        if len(results) == len(build_role_only_schedule(role))
                        else build_role_only_schedule(role)[len(results)]
                    ),
                    results,
                    outcome,
                    False,
                    snapshots={role: _private_snapshot_record(snapshot)},
                    restorations=restorations,
                    events_path=str(checkpoint_path.parent / "trace.jsonl"),
                    diagnostics_path=str(checkpoint_path.parent / "diagnostics"),
                    terminal_cycle=terminal_cycle,
                ),
            )
    return LifecycleResult(
        run_id,
        results,
        restorations,
        outcome,
        exit_code,
        False,
        [
            PublicDeviceRecord(
                role,
                cast(str, metadata.get("device_class", "MatrixLight")),
                cast(str, metadata.get("model", "unknown")),
                cast(int, metadata.get("product_id", -1)),
                cast(str, metadata.get("firmware", "unknown")),
            )
        ]
        if metadata
        else [],
    )


def _empty_theme() -> Theme:
    """Create identity-less empty Theme despite Theme's public white default."""
    theme = Theme()
    theme.colors = []
    return theme


def theme_from_readback(palette: list[HSBK] | None) -> Theme:
    """Adapt a device palette to the repository's sole equality type."""
    if palette is None:
        return _empty_theme()
    if not palette:
        return _empty_theme()
    return Theme(list(palette))


def normalise_category_heading(value: str) -> str:
    """Apply the library's one category slug rule to picker headings."""
    return derive_slug(value)


def _record_colour(value: Mapping[str, object]) -> HSBK:
    """Convert one canonical JSONL uint16 HSBK record without rounding drift."""
    try:
        raw_hue = value["hue"]
        raw_saturation = value["saturation"]
        raw_brightness = value["brightness"]
        raw_kelvin = value["kelvin"]
    except (KeyError, TypeError, ValueError) as error:
        raise PreflightError("invalid public theme record") from error
    if not all(
        isinstance(item, int)
        for item in (raw_hue, raw_saturation, raw_brightness, raw_kelvin)
    ):
        raise PreflightError("invalid public theme record")
    hue = cast(int, raw_hue)
    saturation = cast(int, raw_saturation)
    brightness = cast(int, raw_brightness)
    kelvin = cast(int, raw_kelvin)
    if not all(0 <= item <= 65535 for item in (hue, saturation, brightness)):
        raise PreflightError("invalid public theme record")
    return HSBK(
        hue=hue * 360 / 65536,
        saturation=saturation / 65535,
        brightness=brightness / 65535,
        kelvin=kelvin,
    )


def load_theme_specs(themes_path: Path | None = None) -> dict[str, ThemeSpec]:
    """Load exactly the approved slugs from data/themes.jsonl and freeze each record."""
    if themes_path is None:
        themes_path = Path(__file__).resolve().parents[3] / "data/themes.jsonl"
    records: dict[str, ThemeSpec] = {}
    try:
        lines = themes_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise PreflightError("theme record source unavailable") from error
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise PreflightError("invalid public theme record") from error
        if record.get("slug") not in OFFICIAL_THEME_SLUGS:
            continue
        if record.get("disposition") != "lifx-app":
            raise PreflightError("approved theme is not an app record")
        slug = record["slug"]
        name = record.get("name")
        category = record.get("category")
        colours = record.get("colors")
        if (
            not isinstance(slug, str)
            or not isinstance(name, str)
            or not isinstance(category, str)
        ):
            raise PreflightError("invalid public theme record")
        if not isinstance(colours, list) or not all(
            isinstance(item, dict) for item in colours
        ):
            raise PreflightError("invalid public theme record")
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
        records[slug] = ThemeSpec(
            slug=slug,
            display_name=name,
            category=category,
            expected_palette=[_record_colour(item) for item in colours],
            record_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
        )
    if tuple(records) != OFFICIAL_THEME_SLUGS:
        raise PreflightError("approved theme records missing or duplicated")
    return records


def _redacted_error(kind: str) -> str:
    return f"{kind}; inspect private run diagnostics"


def adb(
    *arguments: str,
    timeout: float = 10.0,
    run: RunCommand = subprocess.run,
) -> str:
    """Run fixed-argv ADB and reject all failures except successful pull progress."""
    command = ["adb", *arguments]
    try:
        result = run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AdbCommandError(_redacted_error("adb command failed")) from error
    allows_pull_progress = bool(arguments) and arguments[0] == "pull"
    if result.returncode != 0 or (result.stderr and not allows_pull_progress):
        raise AdbCommandError(_redacted_error("adb command failed"))
    return str(result.stdout)


def _control_from_element(element: ET.Element) -> dict[str, str]:
    return {key: value for key, value in element.attrib.items() if value is not None}


def dump_ui_hierarchy(
    private_directory: Path,
    *,
    timeout: float = 10.0,
    run: RunCommand = subprocess.run,
) -> list[Control]:
    """Dump current authorised UI hierarchy into the restrictive private run root."""
    private_directory.mkdir(parents=True, exist_ok=True)
    _chmod(private_directory, 0o700)
    destination = private_directory / "hierarchy.xml"
    adb("shell", "uiautomator", "dump", "/sdcard/phase8.xml", timeout=timeout, run=run)
    adb("pull", "/sdcard/phase8.xml", str(destination), timeout=timeout, run=run)
    _chmod(destination, 0o600)
    try:
        root = ET.parse(destination).getroot()  # nosec B314 - local adb output
    except (ET.ParseError, OSError) as error:
        raise SemanticLookupError(_redacted_error("invalid UI hierarchy")) from error
    return [_control_from_element(node) for node in root.iter("node")]


def _text(control: Control) -> str:
    return (control.get("text") or control.get("content-desc") or "").strip()


def _control_bounds(control: Control) -> tuple[int, int, int, int]:
    """Parse one live control's non-empty bounds without exposing its XML."""
    raw = control.get("bounds", "")
    values = [int(item) for item in re.findall(r"-?\d+", raw)]
    if len(values) != 4 or values[0] >= values[2] or values[1] >= values[3]:
        raise SemanticLookupError(_redacted_error("semantic control has no tap bounds"))
    return values[0], values[1], values[2], values[3]


def _tap_point(control: Control) -> tuple[int, int]:
    left, top, right, bottom = _control_bounds(control)
    return ((left + right) // 2, (top + bottom) // 2)


def find_semantic_control(
    controls: Iterable[Control],
    *,
    exact_text: str | None = None,
    resource_id_suffix: str | None = None,
    normalised_category: str | None = None,
) -> Control:
    """Return one current hierarchy control or fail on zero/ambiguous candidates."""
    candidates: list[Control] = []
    for control in controls:
        text = _text(control)
        resource_id = control.get("resource-id", "")
        text_matches = exact_text is None or text == exact_text
        resource_matches = resource_id_suffix is None or resource_id.endswith(
            resource_id_suffix
        )
        category_matches = (
            normalised_category is None
            or normalise_category_heading(text) == normalised_category
        )
        if text_matches and resource_matches and category_matches:
            candidates.append(control)
    if len(candidates) != 1:
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    return candidates[0]


def _with_semantic_retries(resolve: Callable[[], T]) -> T:
    """Perform the initial lookup plus exactly two fresh-hierarchy retries."""
    failure: SemanticLookupError | None = None
    for _ in range(SEMANTIC_RETRIES + 1):
        try:
            return resolve()
        except SemanticLookupError as error:
            failure = error
    assert failure is not None
    raise failure


def scroll_to_semantic_theme(
    display_name: str,
    *,
    dump_hierarchy: Callable[[], Sequence[Control]],
    swipe_scrollable: Callable[[Control], None],
    max_scrolls: int = 20,
) -> Control:
    """Use fresh semantic picker dumps and one current picker container per swipe."""
    if max_scrolls < 0:
        raise SemanticLookupError(_redacted_error("theme scroll limit is invalid"))
    previous: tuple[tuple[str, ...], ...] | None = None
    # `max_scrolls` was checked above, so range always enters at least once.
    for index in range(max_scrolls + 1):  # pragma: no branch
        controls = dump_hierarchy()
        try:
            return find_semantic_control(controls, exact_text=display_name)
        except SemanticLookupError:
            signature = _hierarchy_signature(controls)
            if index == max_scrolls or (previous is not None and signature == previous):
                raise SemanticLookupError(_redacted_error("theme not found"))
            scrollables = [
                control for control in controls if control.get("scrollable") == "true"
            ]
            if len(scrollables) != 1:
                raise SemanticLookupError(_redacted_error("theme picker unavailable"))
            previous = signature
            swipe_scrollable(scrollables[0])
    raise AssertionError(
        "non-negative scroll range did not execute"
    )  # pragma: no cover


def _hierarchy_signature(controls: Sequence[Control]) -> tuple[tuple[str, ...], ...]:
    """Retain only semantic node facts to recognise an unchanged post-swipe surface."""
    return tuple(
        sorted(
            tuple(
                control.get(attribute, "")
                for attribute in (
                    "text",
                    "content-desc",
                    "resource-id",
                    "class",
                    "scrollable",
                    "bounds",
                )
            )
            for control in controls
        )
    )


def scroll_to_bound_device_control(
    app_label: str,
    *,
    dump_hierarchy: Callable[[], Sequence[Control]],
    swipe_scrollable: Callable[[Control], None],
    max_group_device_scrolls: int = MAX_GROUP_DEVICE_SCROLLS,
) -> Control:
    """Find one group target with bounded fresh scrolling and no fallback surface."""
    if max_group_device_scrolls < 0:
        raise SemanticLookupError(
            _redacted_error("group device scroll limit is invalid")
        )
    previous: tuple[tuple[str, ...], ...] | None = None
    for index in range(max_group_device_scrolls + 1):  # pragma: no branch
        controls = dump_hierarchy()
        label_matches = [control for control in controls if _text(control) == app_label]
        if len(label_matches) == 1:
            return label_matches[0]
        if len(label_matches) > 1:
            raise SemanticLookupError(_redacted_error("semantic control unavailable"))
        signature = _hierarchy_signature(controls)
        if index == max_group_device_scrolls or signature == previous:
            raise SemanticLookupError(_redacted_error("group device not found"))
        scrollables = [
            control
            for control in controls
            if control.get("scrollable") == "true"
            and control.get("class") == "android.widget.ScrollView"
        ]
        if len(scrollables) != 1:
            raise SemanticLookupError(_redacted_error("semantic control unavailable"))
        previous = signature
        swipe_scrollable(scrollables[0])
    raise AssertionError(
        "non-negative scroll range did not execute"
    )  # pragma: no cover


def run_hierarchy_reconnaissance(  # pragma: no cover - retired automatic path
    dump_hierarchy: Callable[[], Sequence[Control]],
    *,
    approved_label: str,
    theme_spec: ThemeSpec,
) -> list[dict[str, str]]:
    """Prove private home/device/MORPH/picker shapes before authoritative taps."""
    controls = dump_hierarchy()
    find_semantic_control(controls, exact_text=approved_label)
    # Shape facts omit all private text and raw XML but are useful in a private trace.
    return [
        {"stage": "home", "control_count": str(len(controls))},
        {"stage": "device", "theme_slug": theme_spec.slug},
    ]


def _unique_raw_text_control(controls: Iterable[Control], text: str) -> Control:
    """Find one UIAutomator text attribute without content-description fallback."""
    candidates = [control for control in controls if control.get("text", "") == text]
    if len(candidates) != 1:
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    return candidates[0]


def _configured_group_page_controls(
    binding: TargetBinding, controls: Sequence[Control]
) -> Sequence[Control]:
    """Prove that one exact right detail panel displays the configured group heading."""
    panel = _unique_detail_panel(controls)
    panel_left, panel_top, panel_right, panel_bottom = _control_bounds(panel)
    headings: list[Control] = []
    for control in controls:
        if control.get("text", "") != binding.app_group:
            continue
        centre_x, centre_y = _tap_point(control)
        if (
            panel_left <= centre_x <= panel_right
            and panel_top <= centre_y <= panel_bottom
        ):
            headings.append(control)
    if len(headings) != 1:
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    return controls


def _unique_detail_panel(controls: Sequence[Control]) -> Control:
    """Return the sole right-side panel, excluding similarly suffixed controls."""
    panels = [
        control
        for control in controls
        if control.get("resource-id", "").rsplit("/", 1)[-1] == "detail_panel"
    ]
    if len(panels) != 1:
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    return panels[0]


def _contains_bounds(
    outer: tuple[int, int, int, int], inner: tuple[int, int, int, int]
) -> bool:
    """Return whether one complete live control lies within another's bounds."""
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and inner[2] <= outer[2]
        and inner[3] <= outer[3]
    )


def _bounds_area(bounds: tuple[int, int, int, int]) -> int:
    """Calculate a positive screen area for a validated control bounds tuple."""
    return (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])


def _is_group_target_marker(control: Control) -> bool:
    """Recognise only the stateful group selector's unset label or positive count."""
    text = control.get("text", "").strip()
    return text == "Lights" or (text.isascii() and text.isdecimal() and int(text) > 0)


def _resolve_group_target_selector_association(
    controls: Sequence[Control],
) -> tuple[Control, Control]:
    """Resolve one stateful selector marker and its small clickable container."""
    panel_bounds = _control_bounds(_unique_detail_panel(controls))
    panel_area = _bounds_area(panel_bounds)
    clickable_controls = [
        (control, _control_bounds(control))
        for control in controls
        if control.get("clickable") == "true"
        and _contains_bounds(panel_bounds, _control_bounds(control))
        and _bounds_area(_control_bounds(control)) < panel_area
    ]
    associations: list[tuple[Control, Control]] = []
    for marker in controls:
        if not _is_group_target_marker(marker):
            continue
        marker_bounds = _control_bounds(marker)
        if not _contains_bounds(panel_bounds, marker_bounds):
            continue
        containing = [
            (control, bounds)
            for control, bounds in clickable_controls
            if _contains_bounds(bounds, marker_bounds)
        ]
        if not containing:
            continue
        smallest_area = min(_bounds_area(bounds) for _, bounds in containing)
        smallest = [
            control
            for control, bounds in containing
            if _bounds_area(bounds) == smallest_area
        ]
        if len(smallest) != 1:
            raise SemanticLookupError(_redacted_error("semantic control unavailable"))
        associations.append((marker, smallest[0]))
    if len(associations) != 1:
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    return associations[0]


def resolve_group_target_selector(controls: Sequence[Control]) -> Control:
    """Resolve a known-empty selector through one small clickable association."""
    marker, selector_control = _resolve_group_target_selector_association(controls)
    if marker.get("text", "") != "Lights":
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    return selector_control


def resolve_selected_group_fx_control(
    binding: TargetBinding, controls: Sequence[Control]
) -> Control:
    """Prove the selected group control surface and return its current FX tab."""
    _configured_group_page_controls(binding, controls)
    marker, _ = _resolve_group_target_selector_association(controls)
    if marker.get("text", "") != "1":
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    return find_semantic_control(controls, resource_id_suffix=FX_TAB_RESOURCE_ID_SUFFIX)


def _unique_morph_config_control(
    controls: Sequence[Control],
    *,
    basename: str,
    exact_text: str | None = None,
    interactive: bool = False,
) -> Control:
    """Resolve one in-panel Morph configuration control without parent tabs."""
    panel_bounds = _control_bounds(_unique_detail_panel(controls))
    candidates = [
        control
        for control in controls
        if control.get("resource-id", "").rsplit("/", 1)[-1] == basename
        and _contains_bounds(panel_bounds, _control_bounds(control))
    ]
    if len(candidates) != 1:
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    control = candidates[0]
    if exact_text is not None and control.get("text", "") != exact_text:
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    if interactive and not (
        control.get("clickable") == "true" and control.get("enabled") == "true"
    ):
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    return control


def attest_manual_role_position(
    binding: TargetBinding,
    controls: Sequence[Control],
    *,
    run_id: str,
    timestamp: str,
    attested_role: str | None = None,
) -> ManualRoleAttestation:
    """Bind one explicit operator claim to the current Morph config observation.

    This deliberately performs no Android action.  It does not try to recover a
    lost selector, navigate Home, select a target, or close a panel: those steps
    belong to the operator because the app hides selected-target identity there.
    """
    if attested_role != binding.role:
        raise PreflightError("manual role position checkpoint is required")
    _unique_morph_config_control(controls, basename="effect_name", exact_text="Morph")
    _unique_morph_config_control(
        controls, basename="effect_subtitle", exact_text="Effect"
    )
    _unique_morph_config_control(
        controls, basename="effect_settings_controller_scroll_view"
    )
    _unique_morph_config_control(controls, basename="theme_button", interactive=True)
    return ManualRoleAttestation(
        run_id=run_id,
        operator_attested_role=cast(str, attested_role),
        binding_digest=binding_digest(binding),
        timestamp=timestamp,
        operator_attested=True,
        ui_morph_config_observed=True,
        effect_name=True,
        effect_subtitle=True,
        effect_settings=True,
        theme_button=True,
    )


def validate_manual_role_attestation(
    attestation: ManualRoleAttestation,
    binding: TargetBinding,
    *,
    run_id: str,
) -> None:
    """Require a current-run, current-role private bridge before an app write."""
    if (
        attestation.run_id != run_id
        or attestation.operator_attested_role != binding.role
        or attestation.binding_digest != binding_digest(binding)
        or not all(
            (
                attestation.operator_attested,
                attestation.ui_morph_config_observed,
                attestation.effect_name,
                attestation.effect_subtitle,
                attestation.effect_settings,
                attestation.theme_button,
            )
        )
    ):
        raise PreflightError("manual role position attestation is unavailable")


def manual_attestation_record(attestation: ManualRoleAttestation) -> dict[str, object]:
    """Encode the private, non-identifying attestation checkpoint record."""
    return {
        "event": "manual-role-attestation",
        "run_id": attestation.run_id,
        "role": attestation.operator_attested_role,
        "binding_digest": attestation.binding_digest,
        "timestamp": attestation.timestamp,
        "operator_attested": attestation.operator_attested,
        "ui_morph_config_observed": attestation.ui_morph_config_observed,
        "effect_name": attestation.effect_name,
        "effect_subtitle": attestation.effect_subtitle,
        "effect_settings": attestation.effect_settings,
        "theme_button": attestation.theme_button,
    }


def attest_initial_theme(
    binding: TargetBinding,
    *,
    run_id: str,
    timestamp: str,
    attested_role: str | None = None,
    attested_initial_theme: str | None = None,
) -> InitialThemeAttestation:
    """Bind the operator's hidden-current-theme claim to one configured role.

    LIFX does not expose the current picker theme from the Morph configuration
    hierarchy, so this intentionally validates an explicit operator claim rather
    than treating the UI proof as theme evidence.
    """
    if attested_role != binding.role or attested_initial_theme != INITIAL_APP_THEME:
        raise PreflightError("initial theme attestation is required")
    return InitialThemeAttestation(
        run_id=run_id,
        operator_attested_role=cast(str, attested_role),
        binding_digest=binding_digest(binding),
        timestamp=timestamp,
        initial_theme=INITIAL_APP_THEME,
        operator_attested=True,
    )


def validate_initial_theme_attestation(
    attestation: InitialThemeAttestation,
    binding: TargetBinding,
    *,
    run_id: str,
) -> None:
    """Reject a missing, stale, cross-role or non-Cheerful operator claim."""
    if (
        attestation.run_id != run_id
        or attestation.operator_attested_role != binding.role
        or attestation.binding_digest != binding_digest(binding)
        or attestation.initial_theme != INITIAL_APP_THEME
        or not attestation.operator_attested
    ):
        raise PreflightError("initial theme attestation is unavailable")


def initial_theme_attestation_record(
    attestation: InitialThemeAttestation,
) -> dict[str, object]:
    """Encode the private theme claim without representing it as UI observation."""
    return {
        "event": "initial-theme-attestation",
        "run_id": attestation.run_id,
        "role": attestation.operator_attested_role,
        "binding_digest": attestation.binding_digest,
        "timestamp": attestation.timestamp,
        "initial_theme": attestation.initial_theme,
        "operator_attested": attestation.operator_attested,
    }


def resolve_selected_target_selector_close(
    binding: TargetBinding, controls: Sequence[Control]
) -> Control:
    """Resolve the one semantic close control above a selected target selector."""
    _configured_group_page_controls(binding, controls)
    marker, _ = _resolve_group_target_selector_association(controls)
    if marker.get("text", "") != "1":
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    selector = _unique_raw_text_control(controls, "Select lights")
    close_control = find_semantic_control(
        controls, resource_id_suffix=SELECTOR_CLOSE_RESOURCE_ID_SUFFIX
    )
    panel_bounds = _control_bounds(_unique_detail_panel(controls))
    close_bounds = _control_bounds(close_control)
    selector_bounds = _control_bounds(selector)
    close_x, close_y = _tap_point(close_control)
    overlaps_panel_horizontally = not (
        close_bounds[2] < panel_bounds[0] or close_bounds[0] > panel_bounds[2]
    )
    if (
        close_control.get("clickable") != "true"
        or not (
            panel_bounds[0] <= close_x <= panel_bounds[2]
            and panel_bounds[1] <= close_y <= panel_bounds[3]
        )
        or not overlaps_panel_horizontally
        or close_bounds[3] > selector_bounds[1]
    ):
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    return close_control


def resolve_post_target_selection_transition(  # pragma: no cover - retired
    binding: TargetBinding, controls: Sequence[Control]
) -> tuple[str, Control]:
    """Choose a validated selector close or selector-absent selected group surface."""
    selector_count = sum(
        control.get("text", "") == "Select lights" for control in controls
    )
    if selector_count == 0:
        return "effects", resolve_selected_group_fx_control(binding, controls)
    if selector_count != 1:
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    return "close", resolve_selected_target_selector_close(binding, controls)


def resolve_post_target_selection_fx(  # pragma: no cover - retired automatic path
    binding: TargetBinding,
    *,
    dump_hierarchy: Callable[[], Sequence[Control]],
    tap_control: Callable[[Control], None],
) -> Control:
    """Close a persisted selector once, then prove the selected group FX surface."""
    transition, control = _with_semantic_retries(
        lambda: resolve_post_target_selection_transition(binding, dump_hierarchy())
    )
    if transition == "effects":
        return control
    tap_control(control)

    def resolve_closed_selector_fx() -> Control:
        controls = dump_hierarchy()
        if any(control.get("text", "") == "Select lights" for control in controls):
            raise SemanticLookupError(_redacted_error("semantic control unavailable"))
        return resolve_selected_group_fx_control(binding, controls)

    return _with_semantic_retries(resolve_closed_selector_fx)


def _require_home_ready(
    bindings: Mapping[str, TargetBinding], controls: Sequence[Control]
) -> None:
    """Prove Home exposes each bound device or only its exact configured group card."""
    if any(control.get("text", "") == "Select lights" for control in controls):
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    for binding in bindings.values():
        label_matches = [
            control for control in controls if _text(control) == binding.app_label
        ]
        if len(label_matches) == 1:
            continue
        if len(label_matches) > 1:
            raise SemanticLookupError(_redacted_error("semantic control unavailable"))
        find_semantic_control(
            controls,
            resource_id_suffix=(
                f"ax_device_list_group_card_button_{binding.app_group}"
            ),
        )


def resolve_bound_device_control(  # pragma: no cover - retired automatic path
    binding: TargetBinding,
    *,
    dump_hierarchy: Callable[[], Sequence[Control]],
    tap_control: Callable[[Control], None],
    swipe_scrollable: Callable[[Control], None],
    max_group_device_scrolls: int = MAX_GROUP_DEVICE_SCROLLS,
) -> Control:
    """Resolve one label, expanding only its exact configured group-card if absent."""
    controls = dump_hierarchy()
    label_matches = [
        control for control in controls if _text(control) == binding.app_label
    ]
    if len(label_matches) == 1:
        return label_matches[0]
    if len(label_matches) > 1:
        raise SemanticLookupError(_redacted_error("semantic control unavailable"))
    group_card_suffix = f"ax_device_list_group_card_button_{binding.app_group}"
    group_control = find_semantic_control(
        controls, resource_id_suffix=group_card_suffix
    )
    tap_control(group_control)
    group_page = _with_semantic_retries(
        lambda: _configured_group_page_controls(binding, dump_hierarchy())
    )
    tap_control(resolve_group_target_selector(group_page))
    _with_semantic_retries(
        lambda: _unique_raw_text_control(dump_hierarchy(), "Select lights")
    )
    return scroll_to_bound_device_control(
        binding.app_label,
        dump_hierarchy=dump_hierarchy,
        swipe_scrollable=swipe_scrollable,
        max_group_device_scrolls=max_group_device_scrolls,
    )


def preflight_app_reconnaissance(
    bindings: Mapping[str, TargetBinding],
    theme_specs: Mapping[str, ThemeSpec],
    *,
    max_theme_scrolls: int,
    open_home: Callable[[], None],
    dump_hierarchy: Callable[[], Sequence[Control]],
    tap_control: Callable[[Control], None],
    return_to_morph: Callable[[], None],
    swipe: Callable[[], None],
    swipe_device_list: Callable[[Control], None],
) -> str:
    """Prove the current semantic app path without selecting a theme or Save."""
    open_home()
    _with_semantic_retries(lambda: _require_home_ready(bindings, dump_hierarchy()))
    source_control = _with_semantic_retries(
        lambda: resolve_bound_device_control(
            bindings["source-tile"],
            dump_hierarchy=dump_hierarchy,
            tap_control=tap_control,
            swipe_scrollable=swipe_device_list,
        )
    )
    tap_control(source_control)
    effects_tab = resolve_post_target_selection_fx(
        bindings["source-tile"],
        dump_hierarchy=dump_hierarchy,
        tap_control=tap_control,
    )
    tap_control(effects_tab)
    morph_control = _with_semantic_retries(
        lambda: find_semantic_control(dump_hierarchy(), exact_text="MORPH")
    )
    tap_control(morph_control)
    morph_surface = dump_hierarchy()
    find_semantic_control(morph_surface, exact_text="MORPH")

    cheerful = theme_specs["cheerful"]
    moods_picker = dump_hierarchy()
    find_semantic_control(moods_picker, exact_text=cheerful.display_name)
    find_semantic_control(moods_picker, resource_id_suffix="save_button")

    return_to_morph()
    art_surface = dump_hierarchy()
    find_semantic_control(art_surface, exact_text="MORPH")
    mondrian = theme_specs["mondrian"]
    scroll_to_semantic_theme(
        mondrian.display_name,
        dump_hierarchy=dump_hierarchy,
        swipe_scrollable=lambda control: swipe(),
        max_scrolls=max_theme_scrolls,
    )
    stable_picker = dump_hierarchy()
    find_semantic_control(stable_picker, resource_id_suffix="save_button")
    initial = catalogue_fingerprint([*moods_picker, *stable_picker])
    current = catalogue_fingerprint([*moods_picker, *dump_hierarchy()])
    require_catalogue_stable(initial, current)
    return initial


async def poll_stable_palette(
    *,
    read_palette: Callable[[], list[HSBK] | Awaitable[list[HSBK] | None] | None],
    timeout: float,
    poll_interval: float,
) -> StablePaletteResult:
    """Retain polls and accept only two consecutive Theme.palette_equals reads."""
    start = time.monotonic()
    observations: list[PaletteObservation] = []
    prior: Theme | None = None
    while time.monotonic() - start <= timeout:
        value = read_palette()
        if inspect.isawaitable(value):
            palette = await cast(Awaitable[list[HSBK] | None], value)
        else:
            palette = value
        observed_theme = theme_from_readback(palette)
        observation = PaletteObservation(
            monotonic_offset=time.monotonic() - start,
            palette=list(observed_theme.colors),
        )
        observations.append(observation)
        if prior is not None and prior.palette_equals(observed_theme):
            return StablePaletteResult(observations, list(observed_theme.colors))
        prior = observed_theme
        if poll_interval:
            await asyncio.sleep(poll_interval)
    return StablePaletteResult(observations, None)


async def _read_effect_palette(device: MatrixDevice) -> list[HSBK] | None:
    effect = await device.get_effect()
    return getattr(effect, "palette", None)


async def run_tracer_cycle(
    *,
    device: MatrixDevice,
    theme_spec: ThemeSpec,
    app_save: Callable[[], Awaitable[None]],
    restore: Callable[[], Awaitable[bool]],
    settings: RunnerSettings,
    device_role: str,
) -> CycleResult:
    """Run app Save then library MORPH, always attempting verified restoration."""
    expected = Theme(list(theme_spec.expected_palette))
    observations: list[PaletteObservation] = []
    failure: str | None = None
    stable_palette: list[HSBK] | None = None
    source = "app"
    matches = False
    try:
        await app_save()
        app_result = await poll_stable_palette(
            read_palette=lambda: _read_effect_palette(device),
            timeout=settings.stability_timeout,
            poll_interval=settings.poll_interval,
        )
        observations.extend(app_result.observations)
        if app_result.stable_palette is None:
            failure = "app readback did not stabilise"
        else:
            stable_palette = app_result.stable_palette
            matches = expected.palette_equals(theme_from_readback(stable_palette))
        if failure is None and matches:
            source = "library"
            await device.set_effect(
                effect_type=FirmwareEffect.MORPH,
                palette=expected.colors,
            )
            library_result = await poll_stable_palette(
                read_palette=lambda: _read_effect_palette(device),
                timeout=settings.stability_timeout,
                poll_interval=settings.poll_interval,
            )
            observations.extend(library_result.observations)
            stable_palette = library_result.stable_palette
            if stable_palette is None:
                failure = "library readback did not stabilise"
            else:
                matches = expected.palette_equals(theme_from_readback(stable_palette))
    except RunnerError:
        failure = _redacted_error("tracer incomplete")
    finally:
        restored = await restore()
        if not restored:
            failure = "restoration failed"
    return CycleResult(
        device_role=device_role,
        theme_slug=theme_spec.slug,
        source=source,
        cycle_index=0,
        observations=observations,
        stable_palette=stable_palette,
        matches_expected=matches,
        failure=failure,
    )


def _chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError as error:
        raise PreflightError(
            "private path permissions could not be enforced"
        ) from error
    if path.stat().st_mode & 0o777 != mode:
        raise PreflightError("private path permissions are too permissive")


def ensure_private_root(private_root: Path) -> None:
    """Create and lock the only permitted local output root."""
    private_root.mkdir(parents=True, exist_ok=True)
    _chmod(private_root, 0o700)


def load_target_bindings(
    path: Path,
    *,
    private_root: Path,
    private_paths: PrivatePathBoundary | None = None,
) -> dict[str, TargetBinding]:
    """Strictly load local identities before ADB or LAN calls can be made."""
    boundary = _canonical_private_path_boundary(
        private_paths or PrivatePathBoundary(private_root, path)
    )
    if boundary.private_root != private_root or boundary.targets_path != path:
        raise PreflightError("private target path is not the designated file")
    ensure_private_root(boundary.private_root)
    if not path.is_file():
        raise PreflightError("private target file is unavailable")
    _chmod(path, 0o600)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PreflightError("private target file is invalid") from error
    required = {"schema_version", "source-tile", "non-tile-matrix"}
    if not isinstance(document, dict) or set(document) != required:
        raise PreflightError("private target schema is invalid")
    if document["schema_version"] != 1:
        raise PreflightError("private target schema is invalid")
    bindings: dict[str, TargetBinding] = {}
    fields = {
        "host",
        "serial",
        "app_label",
        "app_group",
        "indoor_confirmed",
        "quiesced_confirmed",
    }
    for role in ("source-tile", "non-tile-matrix"):
        item = document[role]
        if not isinstance(item, dict) or set(item) != fields:
            raise PreflightError("private target schema is invalid")
        host = item["host"]
        serial = item["serial"]
        label = item["app_label"]
        group = item["app_group"]
        indoor = item["indoor_confirmed"]
        quiesced = item["quiesced_confirmed"]
        if (
            not isinstance(host, str)
            or not host
            or not isinstance(label, str)
            or not label
            or not isinstance(group, str)
            or not group
        ):
            raise PreflightError("private target schema is invalid")
        if not isinstance(serial, str) or not SERIAL_PATTERN.fullmatch(serial):
            raise PreflightError("private target schema is invalid")
        if indoor is not True or quiesced is not True:
            raise PreflightError("private target is not approved")
        bindings[role] = TargetBinding(
            role, host, serial.lower(), label, indoor, quiesced, group
        )
    return bindings


def require_one_authorised_adb_device(timeout: float, run: RunCommand) -> None:
    output = adb("devices", timeout=timeout, run=run)
    require_one_authorised_adb_output(output)


def require_one_authorised_adb_output(output: str) -> None:
    """Accept exactly one unlocked, authorised ADB transport."""
    entries = [line.split("\t") for line in output.splitlines()[1:] if line.strip()]
    if len(entries) != 1 or len(entries[0]) != 2 or entries[0][1] != "device":
        raise PreflightError("exactly one authorised Android device is required")


def _tap_control(control: Control, *, timeout: float, run: RunCommand) -> None:
    x, y = _tap_point(control)
    adb("shell", "input", "tap", str(x), str(y), timeout=timeout, run=run)


def _scrollable_swipe_points(control: Control) -> tuple[int, int, int, int]:
    """Derive a safe upward gesture from one current scrollable control's bounds."""
    raw = control.get("bounds", "")
    values = [int(item) for item in re.findall(r"-?\d+", raw)]
    if len(values) != 4 or values[0] >= values[2] or values[1] >= values[3]:
        raise SemanticLookupError(
            _redacted_error("semantic control has no scroll bounds")
        )
    left, top, right, bottom = values
    centre_x = (left + right) // 2
    height = bottom - top
    start_y = top + (3 * height) // 4
    end_y = top + height // 4
    if start_y <= end_y:
        raise SemanticLookupError(
            _redacted_error("semantic control has no scroll bounds")
        )
    return centre_x, start_y, centre_x, end_y


def _swipe_scrollable_control(
    control: Control, *, timeout: float, run: RunCommand
) -> None:
    """Swipe only the current semantic scroll container using its own geometry."""
    start_x, start_y, end_x, end_y = _scrollable_swipe_points(control)
    adb(
        "shell",
        "input",
        "swipe",
        str(start_x),
        str(start_y),
        str(end_x),
        str(end_y),
        "400",
        timeout=timeout,
        run=run,
    )


def _open_lifx_home(  # pragma: no cover - retired automatic path
    *, timeout: float, run: RunCommand
) -> None:
    """Navigate the running app to its declared Home deep link with fixed arguments."""
    adb(
        "shell",
        "am",
        "start",
        "-W",
        "-a",
        "android.intent.action.VIEW",
        "-c",
        "android.intent.category.BROWSABLE",
        "-d",
        LIFX_HOME_URI,
        LIFX_PACKAGE,
        timeout=timeout,
        run=run,
    )


def _write_private_event(directory: Path, event: Mapping[str, object]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    _chmod(directory, 0o700)
    trace = directory / "trace.jsonl"
    with trace.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    _chmod(trace, 0o600)


async def _wait_for_active_morph(
    device: MatrixDevice, *, timeout: float, poll_interval: float
) -> bool:
    """Require two equal, complete MORPH observations after the sole play tap."""
    attempts = max(2, int(timeout / poll_interval) + 1) if poll_interval else 3
    prior: EffectSnapshot | None = None
    for attempt in range(attempts):
        effect = _effect_snapshot(await device.get_effect())
        active = (
            effect.effect_type is FirmwareEffect.MORPH
            and effect.palette is not None
            and bool(effect.palette)
            and all(isinstance(colour, HSBK) for colour in effect.palette)
        )
        if active and effect == prior:
            return True
        prior = effect if active else None
        if attempt < attempts - 1 and poll_interval:
            await asyncio.sleep(poll_interval)
    return False


async def semantic_morph_activation(
    binding: TargetBinding,
    device: MatrixDevice,
    *,
    settings: RunnerSettings,
    run_directory: Path,
    run_id: str = "legacy",
    timestamp: str = "legacy",
    attested_role: str | None = None,
    attested_initial_theme: str | None = None,
    run: RunCommand = subprocess.run,
) -> None:
    """Start Morph once, then prove its active palette through read-only LAN state."""
    _write_private_event(
        run_directory,
        {"event": "morph-activation", "role": binding.role, "status": "starting"},
    )
    try:
        controls = dump_ui_hierarchy(
            run_directory, timeout=settings.ui_wait_timeout, run=run
        )
        attestation = attest_manual_role_position(
            binding,
            controls,
            run_id=run_id,
            timestamp=timestamp,
            attested_role=attested_role,
        )
        validate_manual_role_attestation(attestation, binding, run_id=run_id)
        initial_theme_attestation = attest_initial_theme(
            binding,
            run_id=run_id,
            timestamp=timestamp,
            attested_role=attested_role,
            attested_initial_theme=attested_initial_theme,
        )
        validate_initial_theme_attestation(
            initial_theme_attestation, binding, run_id=run_id
        )
        _write_private_event(
            run_directory, initial_theme_attestation_record(initial_theme_attestation)
        )
        play_button = _unique_morph_config_control(
            controls, basename="play_button", interactive=True
        )
        _tap_control(play_button, timeout=settings.ui_wait_timeout, run=run)
        if not await _wait_for_active_morph(
            device,
            timeout=settings.stability_timeout,
            poll_interval=settings.poll_interval,
        ):
            raise PreflightError("Morph activation did not stabilise")
    except (LifxError, RunnerError) as error:
        _write_private_event(
            run_directory,
            {"event": "morph-activation", "role": binding.role, "status": "failed"},
        )
        raise PreflightError("Morph activation is unavailable") from error
    _write_private_event(
        run_directory,
        {"event": "morph-activation", "role": binding.role, "status": "passed"},
    )


async def semantic_app_save(
    binding: TargetBinding,
    theme_spec: ThemeSpec,
    *,
    settings: RunnerSettings,
    run_directory: Path,
    run_id: str = "legacy",
    timestamp: str = "legacy",
    attested_role: str | None = None,
    run: RunCommand = subprocess.run,
    open_home: Callable[[], None] | None = None,
) -> None:
    """Apply one theme from an operator-attested Morph configuration surface.

    The app path intentionally owns only theme-button, picker scrolling, exact
    theme and current Save.  A picker heading may be observed but is never a
    category switch control.  Home, group expansion, target selection, selector
    closing and effect navigation are not safe to automate after the app hides
    identity.
    """
    del open_home  # Compatibility-only: automatic Home navigation is retired.

    def dump() -> list[Control]:
        return dump_ui_hierarchy(
            run_directory, timeout=settings.ui_wait_timeout, run=run
        )

    def event(stage: str) -> None:
        _write_private_event(run_directory, {"stage": stage, "theme": theme_spec.slug})

    def prove_config() -> tuple[ManualRoleAttestation, Control]:
        controls = dump()
        return (
            attest_manual_role_position(
                binding,
                controls,
                run_id=run_id,
                timestamp=timestamp,
                attested_role=attested_role,
            ),
            _unique_morph_config_control(
                controls, basename="theme_button", interactive=True
            ),
        )

    attestation, theme_button = _with_semantic_retries(prove_config)
    validate_manual_role_attestation(attestation, binding, run_id=run_id)
    _write_private_event(run_directory, manual_attestation_record(attestation))
    _tap_control(theme_button, timeout=settings.ui_wait_timeout, run=run)
    event("theme-picker-opened")

    def swipe_picker(scrollable: Control) -> None:
        _swipe_scrollable_control(scrollable, timeout=settings.ui_wait_timeout, run=run)
        event("theme-picker-scrolled")

    theme_control = scroll_to_semantic_theme(
        theme_spec.display_name,
        dump_hierarchy=dump,
        swipe_scrollable=swipe_picker,
        max_scrolls=settings.max_theme_scrolls,
    )
    _tap_control(theme_control, timeout=settings.ui_wait_timeout, run=run)
    event("theme-selected")
    save_control = _with_semantic_retries(
        lambda: find_semantic_control(dump(), resource_id_suffix="save_button")
    )
    _tap_control(save_control, timeout=settings.ui_wait_timeout, run=run)
    event("save-selected")


def _redacted_progress(role: str, message: str) -> None:
    if role not in {"source-tile", "non-tile-matrix"}:
        raise PreflightError("unknown public device role")
    print(f"{role}: {message}", file=sys.stderr)


async def with_android_keep_awake(
    action: Callable[[], Awaitable[T]],
    *,
    timeout: float,
    run: RunCommand = subprocess.run,
    adb_command: Callable[..., str] | None = None,
) -> T:
    """Set the temporary Android keep-awake mask and restore its exact old value."""
    command = adb_command or (
        lambda *arguments: adb(*arguments, timeout=timeout, run=run)
    )
    prior = command(
        "shell", "settings", "get", "global", "stay_on_while_plugged_in"
    ).strip()
    if not prior.isdecimal():
        raise PreflightError("Android keep-awake setting is invalid")
    command(
        "shell",
        "settings",
        "put",
        "global",
        "stay_on_while_plugged_in",
        str(ANDROID_KEEP_AWAKE_MASK),
    )
    try:
        return await action()
    finally:
        try:
            command(
                "shell",
                "settings",
                "put",
                "global",
                "stay_on_while_plugged_in",
                prior,
            )
            if (
                command(
                    "shell", "settings", "get", "global", "stay_on_while_plugged_in"
                ).strip()
                != prior
            ):
                raise RestorationError("Android keep-awake restoration did not verify")
        except AdbCommandError as error:
            raise RestorationError("Android keep-awake restoration failed") from error


def _preflight_stage_event(
    *, role: str | None = None, stage: str, status: str
) -> dict[str, str]:
    """Build the fixed, private-safe stage record without target identifiers."""
    event = {"event": "preflight-stage", "stage": stage, "status": status}
    if role is not None:
        event["role"] = role
    return event


async def run_non_mutating_preflight(
    *,
    bindings: Mapping[str, TargetBinding],
    theme_specs: Mapping[str, ThemeSpec],
    settings: RunnerSettings,
    device_adapter: DeviceAdapter,
    adb_command: Callable[..., str],
    dump_hierarchy: Callable[[], Sequence[Control]],
    attested_role: str | None = None,
    record_event: PreflightEventRecorder | None = None,
    run_id: str = "preflight",
    timestamp: str = "preflight",
    # Compatibility-only injection names: manual preflight intentionally never
    # invokes them.  Retaining the call surface avoids silently treating an old
    # caller as permission for automatic navigation.
    open_home: Callable[[], None] | None = None,
    tap_control: Callable[[Control], None] | None = None,
    return_to_morph: Callable[[], None] | None = None,
    swipe: Callable[[], None] | None = None,
    swipe_device_list: Callable[[Control], None] | None = None,
) -> PreflightReport:
    """Check current manual Morph position and both bound lights without UI mutation."""
    event_recorder = record_event or (lambda event: None)

    def stage(*, role: str | None = None, name: str, status: str) -> None:
        event_recorder(_preflight_stage_event(role=role, stage=name, status=status))

    if attested_role not in bindings:
        raise PreflightError("manual role position checkpoint is required")
    assert attested_role is not None
    require_one_authorised_adb_output(adb_command("devices"))
    package_path = adb_command("shell", "pm", "path", LIFX_PACKAGE)
    if not package_path.startswith("package:"):
        raise PreflightError("LIFX app is unavailable")
    if "mDreamingLockscreen=false" not in adb_command("shell", "dumpsys", "window"):
        raise PreflightError("Android screen is locked")
    app_version = parse_app_version(
        adb_command("shell", "dumpsys", "package", LIFX_PACKAGE)
    )

    async def inspect() -> PreflightReport:
        attested_binding = bindings[attested_role]
        initial_surface = dump_hierarchy()
        source_attestation = attest_manual_role_position(
            attested_binding,
            initial_surface,
            run_id=run_id,
            timestamp=timestamp,
            attested_role=attested_role,
        )
        validate_manual_role_attestation(
            source_attestation, attested_binding, run_id=run_id
        )
        stage(role=attested_role, name="manual-ui-attestation", status="passed")
        catalogue = catalogue_fingerprint(initial_surface)
        require_catalogue_stable(catalogue, catalogue_fingerprint(dump_hierarchy()))
        devices: dict[str, MatrixDevice] = {}
        try:
            for role in ("source-tile", "non-tile-matrix"):
                stage(role=role, name="contact", status="starting")
                try:
                    devices[role] = await device_adapter.connect(bindings[role])
                except (PreflightError, LifxError):
                    stage(role=role, name="contact", status="failed")
                    raise
                stage(role=role, name="contact", status="passed")
            metadata: dict[str, Mapping[str, object]] = {}
            for role in ("source-tile", "non-tile-matrix"):
                stage(role=role, name="metadata", status="starting")
                try:
                    metadata[role] = await device_adapter.metadata(
                        bindings[role], devices[role]
                    )
                except (PreflightError, LifxError):
                    stage(role=role, name="metadata", status="failed")
                    raise
                stage(role=role, name="metadata", status="passed")
            provenance = build_live_provenance(
                runner_revision="phase-08",
                preflight=PreflightReport(
                    app_version, catalogue, metadata, source_attestation
                ),
                bindings=bindings,
                theme_specs=theme_specs,
                settings=settings,
            )
            run_preflight(
                bindings=bindings,
                metadata_by_role=metadata,
                theme_specs=theme_specs,
                provenance=provenance,
            )
            validate_live_preflight_metadata(metadata)
            for role in ("source-tile", "non-tile-matrix"):
                stage(role=role, name="snapshot", status="starting")
                try:
                    await capture_snapshot(devices[role])
                except (PreflightError, LifxError):
                    stage(role=role, name="snapshot", status="failed")
                    raise
                stage(role=role, name="snapshot", status="passed")
            stage(name="preflight-complete", status="passed")
            return PreflightReport(app_version, catalogue, metadata, source_attestation)
        finally:
            for role in reversed(tuple(devices)):
                await device_adapter.close(devices[role])

    return await with_android_keep_awake(
        inspect, timeout=settings.ui_wait_timeout, adb_command=adb_command
    )


async def run_role_only_preflight(
    *,
    bindings: Mapping[str, TargetBinding],
    theme_specs: Mapping[str, ThemeSpec],
    settings: RunnerSettings,
    device_adapter: DeviceAdapter,
    adb_command: Callable[..., str],
    dump_hierarchy: Callable[[], Sequence[Control]],
    attested_role: str | None,
    record_event: PreflightEventRecorder | None = None,
    run_id: str = "preflight",
    timestamp: str = "preflight",
) -> PreflightReport:
    """Prove one fresh Luna baseline without addressing the failed Tile role."""
    role = ROLE_ONLY_NON_TILE
    if set(bindings) != {"source-tile", role} or attested_role != role:
        raise PreflightError("role-only Luna position checkpoint is required")
    if tuple(theme_specs) != OFFICIAL_THEME_SLUGS:
        raise PreflightError("approved theme records missing or duplicated")
    binding = bindings[role]
    if not binding.indoor_confirmed or not binding.quiesced_confirmed:
        raise PreflightError("role-only target is not approved and quiesced")
    event_recorder = record_event or (lambda event: None)

    def stage(name: str, status: str) -> None:
        event_recorder(_preflight_stage_event(role=role, stage=name, status=status))

    require_one_authorised_adb_output(adb_command("devices"))
    package_path = adb_command("shell", "pm", "path", LIFX_PACKAGE)
    if not package_path.startswith("package:"):
        raise PreflightError("LIFX app is unavailable")
    if "mDreamingLockscreen=false" not in adb_command("shell", "dumpsys", "window"):
        raise PreflightError("Android screen is locked")
    app_version = parse_app_version(
        adb_command("shell", "dumpsys", "package", LIFX_PACKAGE)
    )

    async def inspect() -> PreflightReport:
        initial_surface = dump_hierarchy()
        attestation = attest_manual_role_position(
            binding,
            initial_surface,
            run_id=run_id,
            timestamp=timestamp,
            attested_role=attested_role,
        )
        validate_manual_role_attestation(attestation, binding, run_id=run_id)
        stage("manual-ui-attestation", "passed")
        stage("contact", "starting")
        device: MatrixDevice | None = None
        try:
            device = await device_adapter.connect(binding)
            stage("contact", "passed")
            stage("metadata", "starting")
            metadata = await device_adapter.metadata(binding, device)
            validate_role_only_luna_metadata(metadata)
            stage("metadata", "passed")
            stage("snapshot", "starting")
            # capture_snapshot itself takes two complete equal static-OFF reads.
            await capture_snapshot(device)
            stage("snapshot", "passed")
            catalogue = catalogue_fingerprint(initial_surface)
            require_catalogue_stable(catalogue, catalogue_fingerprint(dump_hierarchy()))
            event_recorder(
                _preflight_stage_event(stage="preflight-complete", status="passed")
            )
            return PreflightReport(
                app_version, catalogue, {role: metadata}, attestation
            )
        except (PreflightError, LifxError):
            # Keep contact/metadata/snapshot failures traceable without naming a device.
            raise
        finally:
            if device is not None:
                await device_adapter.close(device)

    return await with_android_keep_awake(
        inspect, timeout=settings.ui_wait_timeout, adb_command=adb_command
    )


def write_diagnostics(
    private_root: Path,
    *,
    screenshot: bytes,
    hierarchy: str,
    role: str,
) -> list[Path]:
    """Keep raw failure artefacts private while exposing only an opaque run location."""
    ensure_private_root(private_root)
    directory = private_root / "diagnostics"
    directory.mkdir(exist_ok=True)
    _chmod(directory, 0o700)
    screenshot_path = directory / "screen.png"
    hierarchy_path = directory / "hierarchy.xml"
    screenshot_path.write_bytes(screenshot)
    hierarchy_path.write_text(hierarchy, encoding="utf-8")
    _chmod(screenshot_path, 0o600)
    _chmod(hierarchy_path, 0o600)
    _redacted_progress(role, "diagnostics retained in private directory")
    return [screenshot_path, hierarchy_path]


def catalogue_fingerprint(controls: Sequence[Control]) -> str:
    """Hash only the semantic picker catalogue while it remains in private state."""
    canonical = "\n".join(sorted(_text(control) for control in controls))
    return hashlib.sha256(canonical.encode()).hexdigest()


def require_catalogue_stable(initial: str, current: str) -> None:
    """Fail closed when the app's semantic catalogue drifts within preflight."""
    if initial != current:
        raise PreflightError("app catalogue changed during preflight")


def build_parser() -> argparse.ArgumentParser:
    """Expose only locked roles plus explicit run, resume and evidence modes."""
    parser = argparse.ArgumentParser(description="Run the private Phase 8 MORPH tracer")
    parser.add_argument(
        "--targets",
        type=Path,
        help="must be .planning/local/phase-08-theme-fidelity/targets.json",
    )
    parser.add_argument("--ui-wait-timeout", type=float, default=10.0)
    parser.add_argument("--operator-action-timeout", type=float, default=300.0)
    parser.add_argument("--stability-timeout", type=float, default=15.0)
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--non-tile-settle-duration", type=float, default=5.0)
    parser.add_argument("--max-theme-scrolls", type=int, default=20)
    parser.add_argument("--preflight-only", action="store_true")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--run", action="store_true")
    modes.add_argument("--resume", metavar="RUN_ID")
    modes.add_argument("--finalise", metavar="RUN_ID")
    modes.add_argument("--validate-evidence", metavar="PATH", type=Path)
    parser.add_argument(
        "--role-only",
        choices=(ROLE_ONLY_NON_TILE,),
        help=(
            "start a fresh Luna-only reconciliation session; this mode cannot "
            "resume, finalise, or produce official evidence"
        ),
    )
    parser.add_argument(
        "--attest-role",
        choices=("source-tile", "non-tile-matrix"),
        help=(
            "confirm the operator has manually positioned this exact configured "
            "target and role on its Morph configuration surface"
        ),
    )
    parser.add_argument(
        "--attest-initial-theme",
        choices=(INITIAL_APP_THEME,),
        help=(
            "confirm the manually positioned Morph configuration is currently "
            "set to Cheerful before the first alternating app Save"
        ),
    )
    return parser


async def _connect_source_tile(binding: TargetBinding) -> MatrixLight:
    """Target one pre-approved Tile and prove app/LAN identity before mutation."""
    device = await Device.connect(binding.host, binding.serial)
    if not isinstance(device, MatrixLight):
        await device.close()
        raise PreflightError("source-tile is not a matrix light")
    await device.__aenter__()
    if device.label != binding.app_label:
        await device.close()
        raise PreflightError("source-tile identity did not match")
    version = await device.get_version()
    if version.product != 55:
        await device.close()
        raise PreflightError("source-tile product did not match")
    return device


async def _production_app_cycle(
    role: str,
    theme_spec: ThemeSpec,
    index: int,
    device: MatrixDevice,
    *,
    binding: TargetBinding,
    settings: RunnerSettings,
    run_directory: Path,
    run_id: str = "legacy",
    timestamp: str = "legacy",
    attested_role: str | None = None,
    attested_initial_theme: str | None = None,
) -> CycleResult:
    """Perform one app cycle: semantic Save strictly precedes LAN stable readback."""
    if attested_role != role or attested_initial_theme != INITIAL_APP_THEME:
        raise PreflightError("manual role position checkpoint is required")
    await semantic_app_save(
        binding,
        theme_spec,
        settings=settings,
        run_directory=run_directory,
        run_id=run_id,
        timestamp=timestamp,
        attested_role=attested_role,
    )
    expected = Theme(list(theme_spec.expected_palette))
    stable = await poll_stable_palette(
        read_palette=lambda: _read_effect_palette(device),
        timeout=settings.stability_timeout,
        poll_interval=settings.poll_interval,
    )
    palette = stable.stable_palette
    matches = palette is not None and expected.palette_equals(
        theme_from_readback(palette)
    )
    return CycleResult(
        role,
        theme_spec.slug,
        "app",
        index,
        stable.observations,
        palette,
        matches,
        None if palette is not None else "app readback did not stabilise",
    )


async def _wait_for_operator_morph_palette(
    device: MatrixDevice,
    *,
    previous_app_palette: list[HSBK] | None,
    operator_action_timeout: float,
    stability_timeout: float,
    poll_interval: float,
    role: str = "source-tile",
    non_tile_settle_duration: float = 5.0,
) -> tuple[StablePaletteResult, str | None]:
    """Wait for a human action, then prove its fresh MORPH readback is stable.

    Human response time is bounded independently from the short LAN stability
    window.  The first complete nonempty MORPH palette different from the prior
    app result starts that stability window; it cannot spend the stability budget
    while an operator or chat relay is still acting.
    """
    action_attempts = (
        max(1, int(operator_action_timeout / poll_interval) + 1) if poll_interval else 1
    )
    stability_attempts = (
        max(1, int(stability_timeout / poll_interval) + 1) if poll_interval else 1
    )
    observations: list[PaletteObservation] = []
    previous = (
        Theme(list(previous_app_palette)) if previous_app_palette is not None else None
    )
    saw_unchanged = False
    action_start = time.monotonic()
    candidate: Theme | None = None
    for attempt in range(action_attempts):
        try:
            effect = _effect_snapshot(await device.get_effect())
        except (LifxError, PreflightError):
            effect = None
        if (
            effect is not None
            and effect.effect_type is FirmwareEffect.MORPH
            and effect.palette is not None
            and bool(effect.palette)
            and all(isinstance(colour, HSBK) for colour in effect.palette)
        ):
            palette = list(effect.palette)
            observed = Theme(palette)
            observations.append(
                PaletteObservation(
                    time.monotonic() - action_start, list(observed.colors)
                )
            )
            if previous is not None and previous.palette_equals(observed):
                saw_unchanged = True
            else:
                candidate = observed
                break
        if attempt < action_attempts - 1 and poll_interval:
            await asyncio.sleep(poll_interval)
    action_elapsed = time.monotonic() - action_start
    if candidate is None:
        failure = (
            "app readback was unchanged"
            if saw_unchanged
            else "app readback did not stabilise"
        )
        return (
            StablePaletteResult(
                observations,
                None,
                action_elapsed_seconds=action_elapsed,
            ),
            failure,
        )

    non_tile = role == ROLE_ONLY_NON_TILE
    if non_tile:
        # A Luna or Ceiling can report its first MORPH palette before the saved
        # theme finishes applying. The trigger proves the operator action only.
        await asyncio.sleep(non_tile_settle_duration)
        observations.clear()

    stability_start = time.monotonic()
    prior = candidate
    for _ in range(stability_attempts):
        if poll_interval:
            await asyncio.sleep(poll_interval)
        try:
            effect = _effect_snapshot(await device.get_effect())
        except (LifxError, PreflightError):
            effect = None
        complete_morph = (
            effect is not None
            and effect.effect_type is FirmwareEffect.MORPH
            and effect.palette is not None
            and bool(effect.palette)
            and all(isinstance(colour, HSBK) for colour in effect.palette)
        )
        if complete_morph:
            assert effect is not None and effect.palette is not None
            observed = Theme(list(effect.palette))
            observations.append(
                PaletteObservation(
                    time.monotonic() - action_start, list(observed.colors)
                )
            )
            if previous is not None and previous.palette_equals(observed):
                if non_tile:
                    return (
                        StablePaletteResult(
                            observations,
                            None,
                            action_elapsed_seconds=action_elapsed,
                            stability_elapsed_seconds=(
                                time.monotonic() - stability_start
                            ),
                        ),
                        "app readback was unchanged",
                    )
                saw_unchanged = True
                prior = None
            elif prior is not None and prior.palette_equals(observed):
                return (
                    StablePaletteResult(
                        observations,
                        list(observed.colors),
                        action_elapsed_seconds=action_elapsed,
                        stability_elapsed_seconds=time.monotonic() - stability_start,
                    ),
                    None,
                )
            else:
                prior = observed
        else:
            if non_tile:
                return (
                    StablePaletteResult(
                        observations,
                        None,
                        action_elapsed_seconds=action_elapsed,
                        stability_elapsed_seconds=time.monotonic() - stability_start,
                    ),
                    "app readback did not stabilise",
                )
            prior = None
    failure = (
        "app readback was unchanged"
        if saw_unchanged
        else "app readback did not stabilise"
    )
    return (
        StablePaletteResult(
            observations,
            None,
            action_elapsed_seconds=action_elapsed,
            stability_elapsed_seconds=time.monotonic() - stability_start,
        ),
        failure,
    )


async def _guided_operator_app_cycle(
    role: str,
    theme_spec: ThemeSpec,
    index: int,
    device: MatrixDevice,
    *,
    settings: RunnerSettings,
    run_directory: Path,
    previous_app_palette: list[HSBK] | None,
    attested_role: str | None,
    attested_initial_theme: str | None,
) -> CycleResult:
    """Prompt for one manual app Save, then record a read-only LAN observation."""
    if attested_role != role or attested_initial_theme != INITIAL_APP_THEME:
        raise PreflightError("manual role position checkpoint is required")
    _write_private_event(
        run_directory,
        {
            "event": "operator-action",
            "role": role,
            "theme": theme_spec.slug,
            "status": "requested",
            "elapsed_seconds": 0.0,
        },
    )
    _redacted_progress(
        role,
        f"ACTION apply and Save {theme_spec.display_name} in Morph; "
        "start or keep Morph running"
        + (
            f"; allow {settings.non_tile_settle_duration:g} seconds to settle"
            if role == ROLE_ONLY_NON_TILE
            else ""
        ),
    )
    stable, observation_failure = await _wait_for_operator_morph_palette(
        device,
        previous_app_palette=previous_app_palette,
        operator_action_timeout=settings.operator_action_timeout,
        stability_timeout=settings.stability_timeout,
        poll_interval=settings.poll_interval,
        role=role,
        non_tile_settle_duration=settings.non_tile_settle_duration,
    )
    palette = stable.stable_palette
    expected = Theme(list(theme_spec.expected_palette))
    matches = palette is not None and expected.palette_equals(
        theme_from_readback(palette)
    )
    failure = observation_failure
    _write_private_event(
        run_directory,
        {
            "event": "operator-action",
            "role": role,
            "theme": theme_spec.slug,
            "status": "observed" if palette is not None else "incomplete",
            "action_elapsed_seconds": stable.action_elapsed_seconds,
            "stability_elapsed_seconds": stable.stability_elapsed_seconds,
            "elapsed_seconds": (
                stable.action_elapsed_seconds + stable.stability_elapsed_seconds
            ),
        },
    )
    return CycleResult(
        role,
        theme_spec.slug,
        "app",
        index,
        stable.observations,
        palette,
        matches,
        failure,
    )


def guided_app_cycle_callback(
    *,
    settings: RunnerSettings,
    run_directory: Path,
    completed: Mapping[CycleKey, CycleResult],
    attested_role: str | None,
    attested_initial_theme: str | None,
) -> Callable[[str, ThemeSpec, int, MatrixDevice], Awaitable[CycleResult]]:
    """Create the stateful read-only app callback from retained schedule evidence."""
    previous_app_palettes: dict[str, list[HSBK]] = {}
    for role, slug, source, index in build_cycle_schedule():
        prior = completed.get((role, slug, source, index))
        if source == "app" and prior is not None and prior.stable_palette is not None:
            previous_app_palettes[role] = list(prior.stable_palette)

    async def observe(
        role: str, spec: ThemeSpec, index: int, device: MatrixDevice
    ) -> CycleResult:
        result = await _guided_operator_app_cycle(
            role,
            spec,
            index,
            device,
            settings=settings,
            run_directory=run_directory,
            previous_app_palette=previous_app_palettes.get(role),
            attested_role=attested_role,
            attested_initial_theme=attested_initial_theme,
        )
        if result.stable_palette is not None:
            previous_app_palettes[role] = list(result.stable_palette)
        return result

    return observe


async def _production_library_cycle(
    role: str,
    theme_spec: ThemeSpec,
    index: int,
    device: MatrixDevice,
    *,
    settings: RunnerSettings,
) -> CycleResult:
    """Perform one library MORPH cycle, using the same stable readback contract."""
    expected = Theme(list(theme_spec.expected_palette))
    await device.set_effect(effect_type=FirmwareEffect.MORPH, palette=expected.colors)
    stable = await poll_stable_palette(
        read_palette=lambda: _read_effect_palette(device),
        timeout=settings.stability_timeout,
        poll_interval=settings.poll_interval,
    )
    palette = stable.stable_palette
    matches = palette is not None and expected.palette_equals(
        theme_from_readback(palette)
    )
    return CycleResult(
        role,
        theme_spec.slug,
        "library",
        index,
        stable.observations,
        palette,
        matches,
        None if palette is not None else "library readback did not stabilise",
    )


def validate_evidence_file(
    path: Path, *, filesystem: FileSystemAdapter | None = None
) -> None:
    """Validate a selected JSON authority without writing or touching hardware."""
    filesystem = filesystem or ProductionFileSystemAdapter()
    try:
        document = json.loads(filesystem.read_text(path))
    except (OSError, json.JSONDecodeError) as error:
        raise PreflightError("official evidence is unavailable") from error
    if not isinstance(document, Mapping):
        raise PreflightError("official evidence root is invalid")
    validate_public_results(document)


def finalise_private_results(
    result_path: Path,
    *,
    output_directory: Path,
    filesystem: FileSystemAdapter | None = None,
    evidence_writer: EvidenceWriter | None = None,
) -> tuple[Path, Path]:
    """Finalise only a designated terminal run prepared by the private lifecycle."""
    filesystem = filesystem or ProductionFileSystemAdapter()
    try:
        private = json.loads(filesystem.read_text(result_path))
    except (OSError, json.JSONDecodeError) as error:
        raise PreflightError("designated private run is unavailable") from error
    if not isinstance(private, Mapping) or private.get("finalisable") is not True:
        raise PreflightError("designated run is not finalisable")
    public = private.get("public_results")
    if not isinstance(public, Mapping):
        raise PreflightError("designated run has no public evidence projection")
    validate_public_results(public)
    writer = evidence_writer or ProductionEvidenceWriter()
    return writer.write(public, output_directory=output_directory)


def write_private_run_result(
    result: LifecycleResult,
    *,
    provenance: RunProvenance,
    theme_specs: Mapping[str, ThemeSpec],
    output_path: Path,
    clock: ClockAdapter | None = None,
    filesystem: FileSystemAdapter | None = None,
    role_only: bool = False,
) -> None:
    """Persist only the designated run projection consumed by ``--finalise``."""
    filesystem = filesystem or ProductionFileSystemAdapter()
    clock = clock or ProductionClockAdapter()
    payload: dict[str, object] = {"finalisable": result.finalisable}
    if role_only:
        payload.update(
            {
                "scope": "role-only-non-tile-matrix",
                "outcome": result.outcome,
                "cycle_count": len(result.cycles),
                "manual_reconciliation_required": True,
            }
        )
    if result.finalisable:
        payload["public_results"] = build_public_results(
            run_id=result.run_id,
            provenance=provenance,
            theme_specs=theme_specs,
            devices=result.devices,
            cycles=result.cycles,
            restorations=result.restorations,
            outcome=result.outcome,
            completed_at_utc=clock.utc_now(),
        )
    filesystem.write_text(
        output_path, json.dumps(payload, sort_keys=True) + "\n", 0o600
    )


def production_manual_position_callbacks(
    settings: RunnerSettings, run_directory: Path
) -> tuple[Callable[..., str], Callable[[], Sequence[Control]]]:
    """Build the read-only Android boundary used for operator positioning proof."""

    def adb_command(*arguments: str) -> str:
        return adb(
            *arguments,
            timeout=settings.ui_wait_timeout,
            run=subprocess.run,
        )

    def dump_hierarchy() -> Sequence[Control]:
        return dump_ui_hierarchy(
            run_directory,
            timeout=settings.ui_wait_timeout,
            run=subprocess.run,
        )

    return adb_command, dump_hierarchy


async def main(
    argv: Sequence[str] | None = None,
    *,
    private_paths: PrivatePathBoundary | None = None,
) -> int:
    """Run explicit private modes; bare invocation stays a non-mutating preflight."""
    args = build_parser().parse_args(argv)
    try:
        path_boundary = resolve_private_path_boundary(
            args.targets, injected_boundary=private_paths
        )
    except RunnerError:
        _redacted_progress(
            args.role_only or "source-tile", "incomplete; inspect private diagnostics"
        )
        return EXIT_INCOMPLETE
    settings = RunnerSettings(
        ui_wait_timeout=args.ui_wait_timeout,
        operator_action_timeout=args.operator_action_timeout,
        stability_timeout=args.stability_timeout,
        poll_interval=args.poll_interval,
        non_tile_settle_duration=args.non_tile_settle_duration,
        max_theme_scrolls=args.max_theme_scrolls,
        targets_path=path_boundary.targets_path,
        private_root=path_boundary.private_root,
    )
    progress_role = args.role_only or "source-tile"
    time_settings = (
        settings.ui_wait_timeout,
        settings.operator_action_timeout,
        settings.stability_timeout,
        settings.poll_interval,
        settings.non_tile_settle_duration,
    )
    if any(not math.isfinite(value) or value < 0 for value in time_settings):
        _redacted_progress(progress_role, "incomplete; inspect private diagnostics")
        return EXIT_INCOMPLETE
    if settings.max_theme_scrolls < 0:
        _redacted_progress(progress_role, "incomplete; inspect private diagnostics")
        return EXIT_INCOMPLETE
    if args.role_only is not None and (
        args.resume is not None
        or args.finalise is not None
        or args.validate_evidence is not None
        or (not args.preflight_only and not args.run)
    ):
        _redacted_progress(
            ROLE_ONLY_NON_TILE, "incomplete; inspect private diagnostics"
        )
        return EXIT_INCOMPLETE
    if args.validate_evidence is not None:
        try:
            validate_evidence_file(args.validate_evidence)
            return EXIT_PASS
        except RunnerError:
            return EXIT_INCOMPLETE
    if args.finalise is not None:
        try:
            run_directory = resolve_designated_run_directory(
                settings.private_root, args.finalise
            )
            finalise_private_results(
                run_directory / "result.json",
                output_directory=Path(__file__).resolve().parent,
            )
            return EXIT_PASS
        except RunnerError:
            return EXIT_INCOMPLETE
    run_id = args.resume or uuid.uuid4().hex
    try:
        run_directory = resolve_designated_run_directory(settings.private_root, run_id)
    except RunnerError:
        _redacted_progress(progress_role, "incomplete; inspect private diagnostics")
        return EXIT_INCOMPLETE
    ensure_private_root(settings.private_root)
    run_directory.mkdir(mode=0o700, exist_ok=args.resume is not None)
    _chmod(run_directory, 0o700)
    try:
        bindings = load_target_bindings(
            settings.targets_path,
            private_root=settings.private_root,
            private_paths=path_boundary,
        )
        specs = load_theme_specs()
        _write_private_event(
            run_directory,
            {
                "event": "preflight-settings",
                "ui_wait_timeout": settings.ui_wait_timeout,
                "operator_action_timeout": settings.operator_action_timeout,
                "stability_timeout": settings.stability_timeout,
                "poll_interval": settings.poll_interval,
                "non_tile_settle_duration": settings.non_tile_settle_duration,
                "max_theme_scrolls": settings.max_theme_scrolls,
                "mode": (
                    "role-only-non-tile-matrix"
                    if args.role_only == ROLE_ONLY_NON_TILE
                    else "full-phase-08"
                ),
                "role": args.role_only or args.attest_role or "source-tile",
                "ui_method": "manual-role-position-attestation",
                "theme_hashes": {
                    slug: spec.record_sha256 for slug, spec in specs.items()
                },
            },
        )
        adb_command, dump_hierarchy = production_manual_position_callbacks(
            settings, run_directory
        )
        if args.role_only == ROLE_ONLY_NON_TILE:
            if args.attest_role != ROLE_ONLY_NON_TILE:
                raise PreflightError("role-only Luna position checkpoint is required")

            def record_role_only_event(event: Mapping[str, str]) -> None:
                _write_private_event(run_directory, event)

            preflight = await run_role_only_preflight(
                bindings=bindings,
                theme_specs=specs,
                settings=settings,
                device_adapter=ProductionDeviceAdapter(
                    contact_observer=lambda role, stage, status: record_role_only_event(
                        _preflight_stage_event(role=role, stage=stage, status=status)
                    )
                ),
                adb_command=adb_command,
                dump_hierarchy=dump_hierarchy,
                attested_role=args.attest_role,
                record_event=record_role_only_event,
                run_id=run_id,
                timestamp=ProductionClockAdapter().utc_now(),
            )
            if preflight.source_attestation is not None:
                _write_private_event(
                    run_directory,
                    manual_attestation_record(preflight.source_attestation),
                )
            if args.preflight_only:
                metadata = preflight.metadata_by_role[ROLE_ONLY_NON_TILE]
                _redacted_progress(
                    ROLE_ONLY_NON_TILE,
                    "PREFLIGHT PASS "
                    f"{metadata['device_class']} {metadata['model']} "
                    f"product {metadata['product_id']} firmware {metadata['firmware']}",
                )
                return EXIT_PASS
            if args.attest_initial_theme != INITIAL_APP_THEME:
                raise PreflightError("initial theme attestation is required")
            initial_attestation = attest_initial_theme(
                bindings[ROLE_ONLY_NON_TILE],
                run_id=run_id,
                timestamp=ProductionClockAdapter().utc_now(),
                attested_role=args.attest_role,
                attested_initial_theme=args.attest_initial_theme,
            )
            validate_initial_theme_attestation(
                initial_attestation, bindings[ROLE_ONLY_NON_TILE], run_id=run_id
            )
            _write_private_event(
                run_directory, initial_theme_attestation_record(initial_attestation)
            )
            role_provenance = build_live_provenance(
                runner_revision="phase-08-role-only",
                preflight=preflight,
                bindings=bindings,
                theme_specs=specs,
                settings=settings,
                roles=(ROLE_ONLY_NON_TILE,),
            )
            role_provenance = RunProvenance(
                **{
                    **role_provenance.__dict__,
                    "schedule_sha256": _stable_digest(
                        build_role_only_schedule(ROLE_ONLY_NON_TILE)
                    ),
                    "effective_settings": {
                        **role_provenance.effective_settings,
                        "mode": "role-only-non-tile-matrix",
                    },
                }
            )
            checkpoint_path = run_directory / "checkpoint.json"
            guided_app_cycle = guided_app_cycle_callback(
                settings=settings,
                run_directory=run_directory,
                completed={},
                attested_role=args.attest_role,
                attested_initial_theme=args.attest_initial_theme,
            )
            result = await with_android_keep_awake(
                lambda: run_role_only_lifecycle(
                    run_id=run_id,
                    bindings=bindings,
                    theme_specs=specs,
                    provenance=role_provenance,
                    device_adapter=ProductionDeviceAdapter(),
                    checkpoint_store=PrivateCheckpointStore(),
                    checkpoint_path=checkpoint_path,
                    app_cycle=guided_app_cycle,
                    library_cycle=lambda role, spec, index, device: (
                        _production_library_cycle(
                            role, spec, index, device, settings=settings
                        )
                    ),
                    restoration_poll_interval=settings.poll_interval,
                ),
                timeout=settings.ui_wait_timeout,
            )
            write_private_run_result(
                result,
                provenance=role_provenance,
                theme_specs=specs,
                output_path=run_directory / "result.json",
                role_only=True,
            )
            _redacted_progress(ROLE_ONLY_NON_TILE, f"run finished: {result.outcome}")
            return result.exit_code
        if args.preflight_only or (not args.run and args.resume is None):

            def record_preflight_event(event: Mapping[str, str]) -> None:
                _write_private_event(run_directory, event)

            def observe_contact(role: str, stage: str, status: str) -> None:
                record_preflight_event(
                    _preflight_stage_event(role=role, stage=stage, status=status)
                )

            preflight = await run_non_mutating_preflight(
                bindings=bindings,
                theme_specs=specs,
                settings=settings,
                device_adapter=ProductionDeviceAdapter(
                    contact_observer=observe_contact
                ),
                adb_command=adb_command,
                dump_hierarchy=dump_hierarchy,
                run_id=run_id,
                timestamp=ProductionClockAdapter().utc_now(),
                attested_role=args.attest_role,
                record_event=record_preflight_event,
            )
            if preflight.source_attestation is not None:
                _write_private_event(
                    run_directory,
                    manual_attestation_record(preflight.source_attestation),
                )
            for role in ("source-tile", "non-tile-matrix"):
                metadata = preflight.metadata_by_role.get(role)
                if metadata is None:
                    continue
                _redacted_progress(
                    role,
                    "PREFLIGHT PASS "
                    f"{metadata['device_class']} {metadata['model']} "
                    f"product {metadata['product_id']} firmware {metadata['firmware']}",
                )
            _redacted_progress(
                "source-tile",
                "PREFLIGHT PASS "
                f"app {preflight.app_version} "
                f"catalogue {preflight.catalogue_fingerprint}",
            )
            if not args.preflight_only:
                _redacted_progress(
                    "source-tile", "PREFLIGHT PASS; explicit --run required"
                )
            return EXIT_PASS
        checkpoint_path = run_directory / "checkpoint.json"
        checkpoint_store = PrivateCheckpointStore()
        completed: dict[CycleKey, CycleResult] = {}
        if args.resume:
            checkpoint = checkpoint_store.load(checkpoint_path)
            if checkpoint.get("run_id") != args.resume:
                raise PreflightError("resume run identity did not match")
            completed = completed_cycles_from_checkpoint(
                checkpoint["cycles"], checkpoint["next_cycle"]
            )
        pending = next_unfinished_cycle(completed)
        active_role = pending[0] if pending is not None else None
        if pending is None:
            raise PreflightError("designated run has no pending cycle")
        if args.attest_role != active_role:
            raise PreflightError("manual role position checkpoint is required")
        if pending[2] == "app":
            if args.attest_initial_theme != INITIAL_APP_THEME:
                raise PreflightError("manual role position checkpoint is required")
            initial_attestation = attest_initial_theme(
                bindings[pending[0]],
                run_id=run_id,
                timestamp=ProductionClockAdapter().utc_now(),
                attested_role=args.attest_role,
                attested_initial_theme=args.attest_initial_theme,
            )
            validate_initial_theme_attestation(
                initial_attestation, bindings[pending[0]], run_id=run_id
            )
            _write_private_event(
                run_directory, initial_theme_attestation_record(initial_attestation)
            )

        def record_run_provenance_event(event: Mapping[str, str]) -> None:
            _write_private_event(run_directory, event)

        def observe_run_provenance_contact(role: str, stage: str, status: str) -> None:
            record_run_provenance_event(
                _preflight_stage_event(role=role, stage=stage, status=status)
            )

        live_preflight = await run_non_mutating_preflight(
            bindings=bindings,
            theme_specs=specs,
            settings=settings,
            device_adapter=ProductionDeviceAdapter(
                contact_observer=observe_run_provenance_contact
            ),
            adb_command=adb_command,
            dump_hierarchy=dump_hierarchy,
            run_id=run_id,
            timestamp=ProductionClockAdapter().utc_now(),
            attested_role=args.attest_role,
            record_event=record_run_provenance_event,
        )
        if live_preflight.source_attestation is not None:
            _write_private_event(
                run_directory,
                manual_attestation_record(live_preflight.source_attestation),
            )
        provenance = build_live_provenance(
            runner_revision="phase-08",
            preflight=live_preflight,
            bindings=bindings,
            theme_specs=specs,
            settings=settings,
        )
        if args.resume:
            saved = cast(
                Mapping[str, object],
                checkpoint_store.load(checkpoint_path)["provenance"],
            )
            if saved != provenance.__dict__:
                raise PreflightError(
                    "resume provenance did not match the designated run"
                )
        guided_app_cycle = guided_app_cycle_callback(
            settings=settings,
            run_directory=run_directory,
            completed=completed,
            attested_role=args.attest_role,
            attested_initial_theme=args.attest_initial_theme,
        )

        result = await with_android_keep_awake(
            lambda: run_designated_lifecycle(
                run_id=run_id,
                bindings=bindings,
                theme_specs=specs,
                provenance=provenance,
                device_adapter=ProductionDeviceAdapter(),
                checkpoint_store=checkpoint_store,
                checkpoint_path=checkpoint_path,
                app_cycle=guided_app_cycle,
                library_cycle=lambda role, spec, index, device: (
                    _production_library_cycle(
                        role, spec, index, device, settings=settings
                    )
                ),
                completed=completed,
                restoration_poll_interval=settings.poll_interval,
                designated_role=active_role,
            ),
            timeout=settings.ui_wait_timeout,
        )
        write_private_run_result(
            result,
            provenance=provenance,
            theme_specs=specs,
            output_path=run_directory / "result.json",
        )
        _redacted_progress("source-tile", f"run finished: {result.outcome}")
        return result.exit_code
    except RestorationError:
        return EXIT_RESTORATION_FAILURE
    except LifxError:
        _redacted_progress(progress_role, "incomplete; inspect private diagnostics")
        return EXIT_INCOMPLETE
    except RunnerError:
        _redacted_progress(progress_role, "incomplete; inspect private diagnostics")
        return EXIT_INCOMPLETE


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
