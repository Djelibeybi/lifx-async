"""Private request-observation event, sink, and capture context (Phase 14).

Owns the request-engine measurement primitives per D-17/D-19: a script that
wants to observe one production ``DeviceConnection`` request attaches this
module's sink to the current asyncio task, and
``lifx.network.connection._transmit_and_listen()`` reads that selection
ONCE per thin wrapper and propagates it explicitly (see
``_current_request_observer()`` in ``connection.py``). Nothing here is
imported by, or imports from, the test suite -- this module is the single
owner of the request-observation event, sink and capture context for every
Phase 14 measurement script (D-17/D-19).

Observations are value-only: bounded category, sequence number, an integer
``time.monotonic_ns()`` timestamp, and the device-reported ``thread_connection``
boolean (accepted-response events only). No serial, address, packet content
or exception text is ever carried.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import math
import random
import re
import shutil
import statistics
import subprocess  # nosec B404
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixEffect, MatrixLight
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight
from lifx.protocol.protocol_types import FirmwareEffect

# Must match lifx.network.connection._REQUEST_OBSERVER_TASK_ATTRIBUTE exactly
# -- this is the task attribute name the production request engine reads.
_OBSERVER_TASK_ATTRIBUTE = "_lifx_request_observer"

_RequestCategory = Literal[
    "logical_start",
    "sent",
    "accepted",
    "timeout",
    "send_error",
    "cancelled",
    "cleanup",
]
_REQUEST_CATEGORIES: frozenset[str] = frozenset(
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


@dataclass(frozen=True, repr=False)
class _RequestObservation:
    """One in-memory request-engine event, identity- and packet-free.

    ``sequence`` is ``None`` for request-scoped events (``logical_start``,
    ``timeout``, ``cancelled``, ``cleanup``) and set for the
    transmission-scoped events (``sent``, ``accepted``). ``thread_connection``
    is only ever non-``None`` on an ``accepted`` event.
    """

    category: _RequestCategory
    sequence: int | None
    timestamp_ns: int
    thread_connection: bool | None = None

    def __repr__(self) -> str:
        """Render every field -- none of them is identity-bearing content."""
        return (
            f"{type(self).__name__}(category={self.category!r}, "
            f"sequence={self.sequence!r}, timestamp_ns={self.timestamp_ns!r}, "
            f"thread_connection={self.thread_connection!r})"
        )


@dataclass(repr=False)
class _RequestObservationSink:
    """Caller-owned append-only sink for one measured production request."""

    _observations: list[_RequestObservation] = field(
        default_factory=list,
        init=False,
        repr=False,
    )

    @property
    def observations(self) -> tuple[_RequestObservation, ...]:
        """Return an immutable snapshot of observations in arrival order."""
        return tuple(self._observations)

    def emit(self, observation: _RequestObservation) -> None:
        """Append one already validated in-memory observation."""
        self._observations.append(observation)

    def observe(
        self,
        category: str,
        sequence: int | None,
        timestamp_ns: int,
        thread_connection: bool | None,
    ) -> None:
        """Receive the production callable's value-only event payload."""
        if category not in _REQUEST_CATEGORIES:
            raise ValueError(f"unknown request observation category: {category!r}")
        self.emit(
            _RequestObservation(
                category=cast(_RequestCategory, category),
                sequence=sequence,
                timestamp_ns=timestamp_ns,
                thread_connection=thread_connection,
            )
        )

    def __repr__(self) -> str:
        """Suppress all observation values while retaining a useful count."""
        return f"{type(self).__name__}(count={len(self._observations)})"


@contextmanager
def _capture_request_observations() -> Iterator[_RequestObservationSink]:
    """Attach one caller-local repository observer for the exact async call.

    Must be entered from inside the task that will issue the observed
    request -- ``lifx.network.connection._current_request_observer()``
    resolves ``asyncio.current_task()`` at the moment each thin request
    wrapper runs, so a sink attached from a different task is never seen.
    """
    task = asyncio.current_task()
    if task is None:
        raise RuntimeError("request observation capture requires an asyncio task")
    sink = _RequestObservationSink()
    had_previous = hasattr(task, _OBSERVER_TASK_ATTRIBUTE)
    previous = getattr(task, _OBSERVER_TASK_ATTRIBUTE, None)

    setattr(task, _OBSERVER_TASK_ATTRIBUTE, sink.observe)
    try:
        yield sink
    finally:
        if had_previous:
            setattr(task, _OBSERVER_TASK_ATTRIBUTE, previous)
        else:
            delattr(task, _OBSERVER_TASK_ATTRIBUTE)


# ---------------------------------------------------------------------------
# Private discovery-observation event, sink, and capture context (Plan 14-03,
# D-17/D-19). Moved out of tests/test_discovery_observation.py, which
# scripts/measure_merged_discovery.py previously loaded by anchored path with
# importlib: no script may import a helper from tests/. Mirrors the request-
# observation primitives above exactly -- lifx.network.discovery.udp reads
# _DISCOVERY_OBSERVER_TASK_ATTRIBUTE from the current task ONCE per sweep and
# calls it directly; nothing here is imported by, or imports from, production
# discovery code, only attached to it through that private task-attribute
# seam.
# ---------------------------------------------------------------------------

# Must match lifx.network.discovery.udp._DISCOVERY_OBSERVER_TASK_ATTRIBUTE
# exactly -- this is the task attribute name the production sweep reads.
_DISCOVERY_OBSERVER_TASK_ATTRIBUTE = "_lifx_discovery_observer"

_DiscoverySource = Literal["udp", "mdns"]
_DiscoveryStage = Literal["accepted", "winner", "duplicate"]


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
            source=cast(_DiscoverySource, source),
            stage=cast(_DiscoveryStage, stage),
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
    """Attach one caller-local repository observer for the exact async call.

    Must be entered from inside the task that will issue the observed
    discovery sweep -- ``lifx.network.discovery.udp``'s observer selector
    resolves ``asyncio.current_task()`` at the moment the sweep runs, so a
    sink attached from a different task is never seen.
    """
    task = asyncio.current_task()
    if task is None:
        raise RuntimeError("discovery observation capture requires an asyncio task")
    sink = _DiscoveryObservationSink()
    token = _DISCOVERY_OBSERVATION_SINK.set(sink)
    previous = getattr(task, _DISCOVERY_OBSERVER_TASK_ATTRIBUTE, None)
    had_previous = hasattr(task, _DISCOVERY_OBSERVER_TASK_ATTRIBUTE)

    setattr(task, _DISCOVERY_OBSERVER_TASK_ATTRIBUTE, sink.observe)
    try:
        yield sink
    finally:
        if had_previous:
            setattr(task, _DISCOVERY_OBSERVER_TASK_ATTRIBUTE, previous)
        else:
            delattr(task, _DISCOVERY_OBSERVER_TASK_ATTRIBUTE)
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


# ---------------------------------------------------------------------------
# Phase 14 shared schema/privacy validation, append/load, schedule and
# statistics primitives (D-17/D-18/D-19/D-20 -- 14-02).
#
# Every Phase 14 evidence artefact (the immutable session manifest plus the
# five append-only journals owned by scripts/thread_revalidation.py) is built
# from the helpers below: a closed privacy-safe alias grammar, a recursive
# forbidden-key/forbidden-value scan that runs BEFORE any output file is
# opened, generic line-numbered JSONL append/load, deterministic seeded
# schedule generation that never perturbs global `random` state, and the
# locked D-08 exact latency statistics. Schema-specific row shapes belong in
# thread_revalidation.py; this module owns only what is genuinely shared.
# ---------------------------------------------------------------------------

# Alias-shaped only: alphanumeric plus hyphen, never a raw serial/MAC. Mirrors
# scripts/measure_merged_discovery.py's `_ALIAS_PATTERN`/`_SERIAL_PATTERN`.
_ALIAS_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9-]{0,63}\Z")
_SERIAL_PATTERN = re.compile(
    r"(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\Z|[0-9a-fA-F]{12}\Z"
)
_REVISION_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
_IPV4_PATTERN = re.compile(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])")

# Forbidden key names anywhere in a row -- mirrors
# scripts/measure_merged_discovery.py's `_FORBIDDEN_KEYS` (AGENTS.md privacy
# posture: never track serials, MACs, addresses, hostnames, ports, packet
# content or raw exceptions).
_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
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
)


def validate_alias(alias: object) -> str:
    """Return one controlled privacy-safe alias or reject identifier-shaped text."""
    if not isinstance(alias, str) or _ALIAS_PATTERN.fullmatch(alias) is None:
        raise ValueError("invalid privacy-safe alias")
    if _SERIAL_PATTERN.fullmatch(alias) is not None:
        raise ValueError("identifier-shaped alias is forbidden")
    return alias


def validate_session_id(session_id: object) -> str:
    """Return one privacy-safe session identity or reject identifier-shaped text."""
    if not isinstance(session_id, str) or _ALIAS_PATTERN.fullmatch(session_id) is None:
        raise ValueError("invalid privacy-safe session_id")
    if _SERIAL_PATTERN.fullmatch(session_id) is not None:
        raise ValueError("identifier-shaped session_id is forbidden")
    return session_id


def validate_revision(revision: object) -> str:
    """Return one exact 40-character lowercase Git SHA or reject anything else."""
    if not isinstance(revision, str) or _REVISION_PATTERN.fullmatch(revision) is None:
        raise ValueError("revision must be a 40-character lowercase SHA")
    return revision


def contains_forbidden_key(value: object) -> bool:
    """Recursively detect a forbidden identifier-shaped key anywhere in ``value``."""
    if isinstance(value, dict):
        return any(
            str(key).casefold() in _FORBIDDEN_KEYS or contains_forbidden_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(contains_forbidden_key(child) for child in value)
    return False


def _string_exposes_identity(value: str) -> bool:
    """Detect an address- or identifier-shaped string outside a controlled field."""
    if _IPV4_PATTERN.search(value) is not None:
        return True
    if _SERIAL_PATTERN.fullmatch(value) is not None:
        return True
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def contains_forbidden_value(value: object) -> bool:
    """Recursively detect a raw identifier/address-shaped value anywhere.

    A backstop over and above the closed per-schema key/type validation each
    Phase 14 row already applies -- defence in depth, not the primary gate.
    """
    if isinstance(value, dict):
        return any(contains_forbidden_value(child) for child in value.values())
    if isinstance(value, list):
        return any(contains_forbidden_value(child) for child in value)
    if isinstance(value, str):
        return _string_exposes_identity(value)
    return False


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    """Append one already-validated compact JSON row without touching prior bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), sort_keys=True, separators=(",", ":")))
        handle.write("\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL with line-numbered errors, preserving on-disk row order."""
    rows: list[dict[str, Any]] = []
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


# Locked D-01/D-02/D-03/D-06 sampling shape. Exact values are the planner's
# discretion within CONTEXT's explicit ranges (14-CONTEXT.md D-02, D-06).
DISCOVERY_ROUNDS: Literal[6] = 6
DISCOVERY_JITTER_BOUNDS: tuple[float, float] = (5.0, 15.0)
REQUEST_TRIALS: Literal[100] = 100
REQUEST_JITTER_BOUNDS: tuple[float, float] = (0.5, 1.5)

# Locked D-10 fixed ascending animation schedule: (fps, duration_seconds).
# Never randomised, never refined, never repeated -- one attempt per alias.
ANIMATION_SCHEDULE: tuple[tuple[int, float], ...] = ((1, 10.0), (2, 10.0), (5, 10.0))

# Locked D-04 staleness cadence: poll-start interval, consecutive-absence
# confirmation count, and the three-hour censoring cap. These three are
# frozen into every already-written 14-MANIFEST.json and re-checked against
# them on every reopen (`_validate_manifest()` in thread_revalidation.py) --
# changing any one of them would invalidate a live physical session, so
# they must never change. Note this cap bounds only the EXPIRY-DETECTION
# phase (the absolute-cadence poll loop before disposition is determined);
# the restoration-detection phase that follows a power-on edge is
# deliberately unbounded (T-14-06 change 2) -- see
# `scripts.thread_revalidation._cli_staleness`'s `_restore_available()`.
STALENESS_POLL_INTERVAL_S: float = 60.0
STALENESS_CONFIRM_ABSENT_POLLS: Literal[3] = 3
STALENESS_CAP_S: float = 3.0 * 60.0 * 60.0


@dataclass(frozen=True)
class ManifestSchedules:
    """One session's deterministically generated D-02/D-06 jitter sequences."""

    discovery_round_gaps_s: tuple[float, ...]
    request_trial_gaps_s: tuple[float, ...]


def generate_manifest_schedules(seed: int) -> ManifestSchedules:
    """Deterministically generate the frozen discovery/request jitter sequences.

    Uses one local ``random.Random(seed)`` instance -- never the ``random``
    module's global functions -- so generation cannot perturb any other
    caller's random state (research Pitfall/Pattern 5). The same seed always
    yields byte-identical schedules, which is what makes a reopened manifest
    comparable rather than merely plausible.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or not (0 <= seed < 2**64):
        raise ValueError("seed must be an unsigned 64-bit integer")
    rng = random.Random(seed)
    discovery_gaps = tuple(
        rng.uniform(*DISCOVERY_JITTER_BOUNDS) for _ in range(DISCOVERY_ROUNDS - 1)
    )
    request_gaps = tuple(
        rng.uniform(*REQUEST_JITTER_BOUNDS) for _ in range(REQUEST_TRIALS - 1)
    )
    return ManifestSchedules(
        discovery_round_gaps_s=discovery_gaps,
        request_trial_gaps_s=request_gaps,
    )


def summarise_latencies_ns(values: Sequence[int]) -> dict[str, float | int] | None:
    """Report the locked D-08 median/p95/max for one completed-latency set.

    Returns ``None`` for an empty distribution rather than a zero value --
    timeouts are reported separately with undefined latency (D-08). p95 uses
    empirical nearest-rank at ``ceil(0.95 * N)``, never interpolation.
    """
    if not values:
        return None
    ordered = sorted(values)
    count = len(ordered)
    p95_index = math.ceil(0.95 * count) - 1
    return {
        "count": count,
        "median_ns": statistics.median(ordered),
        "p95_ns": ordered[p95_index],
        "max_ns": ordered[-1],
    }


def git_revision() -> str:
    """Return the exact repository revision without recording command errors."""
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to record the manifest revision")
    completed = subprocess.run(  # nosec B603
        [git, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    revision = completed.stdout.strip().casefold()
    return validate_revision(revision)


# ---------------------------------------------------------------------------
# Shared device-state capture, restoration and exact comparison (D-05/D-14/
# D-16 -- 14-03). Moved out of scripts/ipv6_thread_probe.py's private
# CapturedState/_capture_device_state()/_restore_device_state() so the legacy
# probe and any future Phase 14 orchestrator restore stage share one
# implementation. Comparison is exact equality of protocol-normalised values
# (HSBK.__eq__ already compares at uint16 wire granularity, see
# src/lifx/color.py) -- never tolerance, visual judgement or object identity.
# ---------------------------------------------------------------------------

_BINARY_POWER_LEVELS = frozenset({0, 65535})


def is_binary_power(power: int) -> bool:
    """Return whether a captured power level is one of the two binary states.

    A device mid-fade reports an intermediate ``get_power()`` level. Neither
    ``Device.set_power()`` nor ``Light.set_power()`` accepts anything but 0 or
    65535 (``ValueError`` otherwise), so an intermediate captured power can
    never be replayed as a no-op SetPower or used as a restore target -- it
    must be checked BEFORE any mutating call is attempted (D-05/D-16).
    """
    return power in _BINARY_POWER_LEVELS


@dataclass
class CapturedState:
    """A device's pre-mutation state, in the shape that device actually holds.

    A ``MatrixLight`` holds a per-pixel image and possibly a running firmware
    effect; ``get_color()`` returns a single triple and cannot represent
    either. Capturing the wrong shape means restoration cannot put the device
    back, and a later exact comparison against a fresh capture of this same
    shape is what proves it did.
    """

    kind: str
    power: int
    tiles: list[list[HSBK]] | None = None
    effect: MatrixEffect | None = None
    zones: list[HSBK] | None = None
    multizone_effect: MultiZoneEffect | None = None
    color: HSBK | None = None


async def capture_device_state(device: Light) -> CapturedState:
    """Read back everything a restore stage will overwrite.

    For a matrix device that means every tile's colours, the power level and
    any running firmware effect. For a multizone device it is every zone's
    colour, power and any running firmware effect. For a plain light it is
    the ``get_color()`` triple, which carries the power level in the same
    round trip.

    Args:
        device: The connected target.

    Returns:
        The captured state, naming which shape it holds.
    """
    if isinstance(device, MatrixLight):
        tiles = await device.get_all_tile_colors()
        power = await device.get_power()
        effect = await device.get_effect()
        running = effect if effect.effect_type != FirmwareEffect.OFF else None
        return CapturedState(kind="matrix", power=power, tiles=tiles, effect=running)

    if isinstance(device, MultiZoneLight):
        zones = await device.get_all_color_zones()
        power = await device.get_power()
        effect = await device.get_effect()
        return CapturedState(
            kind="multizone",
            power=power,
            zones=zones,
            multizone_effect=effect,
        )

    color, power, _label = await device.get_color()
    return CapturedState(kind="light", power=power, color=color)


async def _run_restore_commands(device: Light, state: CapturedState) -> None:
    """Issue the device-shape-specific write sequence captured state implies."""
    if isinstance(device, MatrixLight) and state.tiles is not None:
        for index, colors in enumerate(state.tiles):
            await device.set_matrix_colors(tile_index=index, colors=colors)
        await device.set_power(state.power)
        if state.effect is not None:
            await device.set_effect(
                effect_type=state.effect.effect_type,
                speed=state.effect.speed / 1000,
                duration=state.effect.duration,
                palette=state.effect.palette,
                sky_type=state.effect.sky_type,
                cloud_saturation_min=state.effect.cloud_saturation_min,
                cloud_saturation_max=state.effect.cloud_saturation_max,
            )
    elif isinstance(device, MultiZoneLight) and state.zones is not None:
        await device.set_all_color_zones(state.zones)
        if state.multizone_effect is not None:
            await device.set_effect(state.multizone_effect)
        await device.set_power(state.power)
    else:
        if state.color is not None:
            await device.set_color(state.color)
        await device.set_power(state.power)


_RESTORE_DETAILS: frozenset[str] = frozenset(
    {
        "power_out_of_range",
        "command_failed",
        "readback_failed",
        "readback_mismatch",
    }
)


@dataclass(frozen=True)
class RestoreOutcome:
    """Bounded, privacy-safe restoration result.

    Field names mirror ``thread_revalidation.build_animation_event()``'s
    ``restored``/``restoration_verified`` schema fields exactly, so a caller
    can pass this object's two booleans straight through unchanged.
    ``detail`` is a bounded, non-identifying category for the CALLER's own
    private diagnostic -- this module never prints or persists it (D-17/
    T-14-08); it is not part of any tracked evidence schema.
    """

    restored: bool
    restoration_verified: bool
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.restoration_verified and not self.restored:
            raise ValueError(
                "restoration_verified cannot be true when restored is false"
            )
        if self.detail is not None and self.detail not in _RESTORE_DETAILS:
            raise ValueError(f"invalid restore outcome detail: {self.detail!r}")


async def restore_and_verify_device_state(
    device: Light,
    state: CapturedState,
    *,
    on_command_exception: Callable[[BaseException], None] | None = None,
) -> RestoreOutcome:
    """Restore ``state`` onto ``device``, then PROVE it with a fresh recapture.

    Restoration is evidence-backed, not acknowledgement-backed (D-16):
    ``restoration_verified`` is only ever true when every restore command
    completed AND a fresh ``capture_device_state()`` compares exactly equal
    to ``state`` (exact dataclass/HSBK equality -- see the module banner
    above). A captured power outside ``{0, 65535}`` is refused before any
    command is sent (D-05): restoring to it would raise ``ValueError`` from
    ``set_power()``, and more fundamentally it is not a real binary device
    state to put back. An ordinary command or readback exception is caught
    and reported through the return value; ``asyncio.CancelledError`` and
    ``KeyboardInterrupt`` are never swallowed -- both are reported to
    ``on_command_exception`` (if supplied) and then re-raised so cancellation
    semantics are preserved.

    Args:
        device: The connected target.
        state: What ``capture_device_state()`` recorded before mutation.
        on_command_exception: Optional caller-owned callback invoked with the
            raw exception on any command failure (ordinary, cancellation, or
            interrupt). This module never prints or persists that exception
            itself -- the callback exists purely so the CALLER can implement
            its own private, non-persisted diagnostic (D-17/T-14-08).

    Returns:
        The bounded restoration outcome.
    """
    if not is_binary_power(state.power):
        return RestoreOutcome(
            restored=False, restoration_verified=False, detail="power_out_of_range"
        )

    try:
        await _run_restore_commands(device, state)
    except (asyncio.CancelledError, KeyboardInterrupt) as exc:
        if on_command_exception is not None:
            on_command_exception(exc)
        raise
    except Exception as exc:
        if on_command_exception is not None:
            on_command_exception(exc)
        return RestoreOutcome(
            restored=False, restoration_verified=False, detail="command_failed"
        )

    try:
        readback = await capture_device_state(device)
    except (asyncio.CancelledError, KeyboardInterrupt) as exc:
        if on_command_exception is not None:
            on_command_exception(exc)
        raise
    except Exception as exc:
        if on_command_exception is not None:
            on_command_exception(exc)
        return RestoreOutcome(
            restored=True, restoration_verified=False, detail="readback_failed"
        )

    if readback == state:
        return RestoreOutcome(restored=True, restoration_verified=True)
    return RestoreOutcome(
        restored=True, restoration_verified=False, detail="readback_mismatch"
    )
