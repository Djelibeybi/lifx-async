# Phase 14: Thread Revalidation and Docs - Pattern Map

**Mapped:** 2026-08-31
**Files analysed:** 19 new or modified source/configuration files
**Analogues found:** 19 / 19
**Tracked-source gate:** Every existing analogue named below was verified with `git ls-files` from the repository root. No capability mirror or gitignored runtime path is referenced.

## Scope Notes

- The exact evidence directory and filenames are deliberately not invented here. D-18 to D-20 require one immutable manifest, five append-only journals, and deterministically generated summary/ledger/report products; their names remain the planner's discretion.
- Physical evidence files are generated products, not hand-edited implementation files. Their pattern is assigned under `scripts/thread_revalidation.py` and `scripts/measurement_support.py`.
- `src/lifx/api.py`, the discovery implementations, and existing discovery examples are read-only behavioural references for this phase; the locked scope adds no public API.
- `src/lifx/animation/animator.py` is a read-only analogue for current `send_frame()` return/stats behaviour. THREAD-03 adds only script-level scheduling, evidence classification, fakes, liveness, and restoration; it changes no production animation file or test.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analogue | Match Quality |
|---|---|---|---|---|
| `scripts/thread_revalidation.py` | service / orchestrator | batch + event-driven + file-I/O | `scripts/measure_merged_discovery.py` | exact role/flow |
| `scripts/measurement_support.py` | utility | transform + file-I/O | `scripts/measure_merged_discovery.py` and `scripts/ipv6_thread_probe.py` | exact extracted-helper match |
| `scripts/measure_merged_discovery.py` | service | batch + file-I/O | itself | exact |
| `scripts/ipv6_thread_probe.py` | service | request-response + file-I/O | itself | exact |
| `src/lifx/network/connection.py` | service | request-response + streaming | itself | exact |
| `tests/test_scripts/test_thread_revalidation.py` | test | batch + file-I/O + transform | `tests/test_scripts/test_measure_merged_discovery.py` | exact role/flow |
| `tests/test_scripts/test_measure_merged_discovery.py` | test | batch + file-I/O | itself | exact |
| `tests/test_scripts/test_ipv6_thread_probe.py` | test | request-response + event-driven | itself | exact |
| `tests/test_network/test_connection_retry.py` | test | request-response + event-driven | itself | exact |
| `examples/discovery_progressive.py` | utility / example | streaming + request-response | `examples/discovery_broadcast.py` and `examples/discovery_mdns.py` | role-match |
| `docs/user-guide/discovery.md` | component / documentation | transform | `docs/user-guide/advanced-usage.md` | exact content-source match |
| `docs/user-guide/advanced-usage.md` | component / documentation | transform | itself | exact |
| `docs/api/network.md` | component / documentation | request-response | itself | exact |
| `mkdocs.yml` | config | transform | itself | exact |
| `tests/test_network/test_mdns/test_phase_contract.py` | test | transform + file-I/O | itself | exact |
| `tests/test_repository_guidance.py` | test | transform + file-I/O | `tests/test_network/test_mdns/test_phase_contract.py` | exact role/flow |
| `AGENTS.md` | config / guidance | transform | itself | exact |
| `CLAUDE.md` | config / guidance | transform | `AGENTS.md` | ownership-match |
| `pyproject.toml` | config | batch | itself | exact |

## Pattern Assignments

### `scripts/measurement_support.py` and shared-helper migrations

**Apply to:** `scripts/measurement_support.py`, `scripts/measure_merged_discovery.py`, `scripts/ipv6_thread_probe.py`, and their existing test modules.

**Primary analogue:** `scripts/measure_merged_discovery.py`

**Imports pattern** (`scripts/measure_merged_discovery.py:4-22`): keep all imports at the top, use only stdlib/runtime-existing facilities, and type collection boundaries explicitly.

```python
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import re
import shutil
import subprocess  # nosec B404
import time
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
```

**Validate-before-append pattern** (`scripts/measure_merged_discovery.py:499-532`):

```python
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
```

Copy the ordering and error shape, but split Phase 14 into one manifest plus distinct discovery/request/animation/staleness/closure journal paths. Never rewrite a journal during resume. Generated views may be replaced only after validating all source journals.

**Privacy gate pattern** (`scripts/measure_merged_discovery.py:94-107,137-205`): keep forbidden identifier keys central, reject identifier/address-shaped values recursively, and validate aliases before any output file is opened.

```python
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


def _validate_alias(alias: object) -> str:
    if not isinstance(alias, str) or _ALIAS_PATTERN.fullmatch(alias) is None:
        raise ValueError("invalid privacy-safe device alias")
    if _SERIAL_PATTERN.fullmatch(alias) is not None:
        raise ValueError("identifier-shaped alias is forbidden")
    return alias
```

**External alias-map boundary** (`scripts/measure_merged_discovery.py:750-766`):

```python
def _load_alias_map(path: Path) -> dict[str, str]:
    """Load an external raw-identity-to-alias mapping only into memory."""
    repository = Path(__file__).resolve().parents[1]
    resolved = path.expanduser().resolve()
    if resolved == repository or repository in resolved.parents:
        raise ValueError("--alias-map must be outside the repository")
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value:
        raise ValueError("alias map must be a non-empty JSON object")
```

The helper must accept raw identities only transiently in memory, map at the journal write boundary, suppress them from repr/error payloads, and pass raw values only to the final leak scan. Do not add hashing, a repository fallback map, or a raw-capture ingestion path.

**Tests to copy** (`tests/test_scripts/test_measure_merged_discovery.py:82-116,238-268,390-419,478-490`):

```python
def test_append_preserves_every_prior_byte(self, tmp_path: Path) -> None:
    output = tmp_path / "measurements.jsonl"
    first = _row()
    second = _row(arm="merged")

    _append_measurement_row(output, first)
    prefix = output.read_bytes()
    _append_measurement_row(output, second)

    assert output.read_bytes().startswith(prefix)
    assert _load_measurements(output) == [first, second]


def test_privacy_rejects_before_output_is_opened(...):
    output = tmp_path / "must-not-exist.jsonl"
    row = _row()
    mutation(row)
    with pytest.raises(ValueError, match="privacy|identifier|alias|confounds"):
        _append_measurement_row(output, row)
    assert not output.exists()
```

Also preserve deterministic, row-order-independent generation (`tests/test_scripts/test_measure_merged_discovery.py:238-247`) and reject an alias-map path inside the repository (`tests/test_scripts/test_measure_merged_discovery.py:478-490`).

---

### `scripts/thread_revalidation.py` (orchestrator, batch/event-driven/file-I/O)

**Primary analogue:** `scripts/measure_merged_discovery.py`

**Mode-driven CLI and validation pattern** (`scripts/measure_merged_discovery.py:1115-1203,1206-1248`):

```python
async def main_async(args: argparse.Namespace) -> int:
    if args.validate_only:
        rows = _load_measurements(args.output)
        _validate_measurements(rows, ...)
        if args.summary is not None:
            args.summary.parent.mkdir(parents=True, exist_ok=True)
            args.summary.write_text(_render_measurement_summary(rows), encoding="utf-8")
        return 0

    # Validate all collection preconditions before opening hardware/output.
    ...
    for round_number in range(1, args.rounds + 1):
        ...
        _append_measurement_row(...)


def main() -> int:
    parser = argparse.ArgumentParser(...)
    ...
    try:
        return asyncio.run(main_async(args))
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    return 2
```

Use explicit subcommands/modes for manifest initialisation, discovery, requests, animation, staleness, closure, and validation. Hardware activity must never occur on import or under the default test command. A mode resumes only manifest-declared missing/incomplete work and refuses immutable manifest drift.

**Serial mutation and restoration pattern:** `scripts/ipv6_thread_probe.py:647-677,719-797,1208-1264`

```python
@dataclass
class CapturedState:
    kind: str
    power: int
    tiles: list[list[HSBK]] | None = None
    effect: MatrixEffect | None = None
    zones: list[HSBK] | None = None
    multizone_effect: MultiZoneEffect | None = None
    color: HSBK | None = None


async def stage_target(device: Light, outcome: TargetOutcome, ...) -> None:
    try:
        async with device:
            captured = await _capture_device_state(device)
            try:
                # Mutating stage work.
                ...
            finally:
                outcome.restored = await _restore_device_state(device, captured)
    except Exception as exc:
        ...
```

Phase 14 must strengthen `_restore_device_state()` rather than copy its current success definition: after restore commands, recapture/read back every applicable field and compare against `CapturedState`. Record command outcome and verification outcome separately. If either fails, append the failure, stop before the next device, and require a new session after operator-confirmed recovery.

**Restoration test pattern** (`tests/test_scripts/test_ipv6_thread_probe.py:1666-1718,1721-1852,2003-2111`): use class-shaped fakes, assert write ordering and full-state recovery, inject ordinary exceptions and `KeyboardInterrupt`, and prove the restoration result lands in evidence. Add new mismatch tests where SETs return successfully but readback differs.

**Error handling:** do not place live `device.serial`, `device.ip`, raw exceptions, or packet content into journal-safe exceptions. The current probe prints those values for private diagnostics (`scripts/ipv6_thread_probe.py:792-795`); that print pattern must not be copied into tracked Phase 14 output.

---

### `src/lifx/network/connection.py` and `tests/test_network/test_connection_retry.py`

**Role/data flow:** service + request-response/streaming; exact in-place analogue.

**Owning seam** (`src/lifx/network/connection.py:739-784`): `_transmit_and_listen()` already owns the one logical start, every sequence send, the shared response queue, accepted response header, deadline, and correlation cleanup. Add the private opt-in observation at this seam; do not time only around `Device.set_power()` and do not build a harness-specific sender.

**Core send/accept pattern** (`src/lifx/network/connection.py:821-843,845-913,933-1001`):

```python
request_source = allocate_source()
response_queue: asyncio.Queue[tuple[LifxHeader, bytes] | _ConnectionClosed] = (
    asyncio.Queue(maxsize=100)
)
correlation_keys: list[tuple[int, int, str]] = []
start = time.monotonic()
deadline = start + timeout

try:
    key = (request_source, 0, self._serial)
    self._pending_requests[key] = response_queue
    correlation_keys.append(key)
    await self.send_packet(..., source=request_source, sequence=0, ...)
    ...
    sequence = tx_count
    key = (request_source, sequence, self._serial)
    self._pending_requests[key] = response_queue
    correlation_keys.append(key)
    await self.send_packet(..., source=request_source, sequence=sequence, ...)
    ...
    header, payload = response
    ...
    has_yielded = True
    last_response_time = time.monotonic()
    yield header, payload
finally:
    for key in correlation_keys:
        if self._pending_requests.get(key) is response_queue:
            self._pending_requests.pop(key, None)
```

Emit initial-start, transmission-sent, accepted-response, timeout, send-error, and cancellation/cleanup events. Retain a per-sequence send timestamp so winning ACK RTT is `accepted_ns - sent_ns[header.sequence]`, while logical latency is `accepted_ns - logical_start_ns`. Observer absence must be a no-op and all public request signatures/results must remain unchanged.

**Private observation shape:** copy `tests/test_discovery_observation.py:17-74,82-101`.

```python
@dataclass(frozen=True, repr=False)
class _DiscoveryObservation:
    source: _DiscoverySource
    stage: _DiscoveryStage
    raw_identity: str = field(repr=False)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(source={self.source!r}, stage={self.stage!r})"


@contextmanager
def _capture_discovery_observations() -> Iterator[_DiscoveryObservationSink]:
    ...
    try:
        yield sink
    finally:
        ...
```

For request events, omit serial/address/packet/exception text entirely rather than merely marking them `repr=False`; the orchestrator already knows the selected alias.

**Tests** (`tests/test_network/test_connection_retry.py:43-97,250-293,437-503`): reuse bounded pending-key waits, patched runtime retry gaps, direct response-queue injection, and `finally: await conn.close()`. Assert exact event order/timestamps for initial and retransmitted ACKs, timeout/send failure/cancellation, observer absence, repr suppression, and acceptance of a late ACK for an earlier sequence.

---

### Current `Animator.send_frame()` and stats (read-only analogue)

`src/lifx/animation/animator.py:69-91,370-487` is the factual production authority for the existing result/stat fields available to the Phase 14 script. The orchestrator creates a fresh Animator, offers frames on D-10's one ascending 1/2/5 FPS ten-second-per-rate schedule, and maps current results to offered/sent/gated/failed/interrupted observations. A successful full socket send is `sent`, not proof of delivery or rendering. Optional ACK/expiry values are recorded only if current behaviour already exposes them; their absence and zero useful throughput are valid completed results.

All new THREAD-03 tests belong in `tests/test_scripts/test_thread_revalidation.py` with an injected Animator fake. They prove exact alias selection, the fixed schedule, current-stat mapping, pre/post liveness, interruption, state restoration/readback, and valid zero-throughput completion. Production animation source and tests remain unchanged per D-09 through D-15.

---

### `tests/test_scripts/test_thread_revalidation.py`

**Primary analogue:** `tests/test_scripts/test_measure_merged_discovery.py`

Use production builders to create synthetic rows (`tests/test_scripts/test_measure_merged_discovery.py:47-79`), small class-grouped tests, `tmp_path`, `argparse.Namespace`, patched clocks/schedules, and injected discovery/device/Animator fakes. Cover:

- immutable manifest create-or-compare and protocol/revision/seed drift rejection;
- pre-generated discovery/request jitter plus D-10's single fixed ascending animation schedule;
- exact uniqueness keys and append-only resume without repeating completed mutations;
- ordinary median, nearest-rank p95, maximum, and empty request-latency distributions; animation integer counts remain descriptive only;
- every failed, timeout, interrupted, censored, restoration-failed, and zero-result terminal state;
- three consecutive paired absences, three-hour censoring, reconnect closure, and no one-miss expiry;
- exact six-class ledger with four evidence-backed available classes and two dated named gaps;
- privacy rejection before any journal/output is created;
- deterministic regeneration from journals only; validator must never parse its own Markdown;
- hardware modes gated behind explicit CLI inputs with no import-time sockets or filesystem writes.

For restoration mechanics, reuse the class-shaped fakes and failure tests at `tests/test_scripts/test_ipv6_thread_probe.py:1666-1852,1899-2111`.

---

### `examples/discovery_progressive.py`

**Analogues:** `examples/discovery_broadcast.py:7-40` and `examples/discovery_mdns.py:15-60`.

```python
import asyncio

import lifx


async def main() -> None:
    async for device in lifx.discover(...):
        ...
    async for device in lifx.discover_udp(...):
        ...
    async for device in lifx.discover_mdns(...):
        ...


if __name__ == "__main__":
    asyncio.run(main())
```

Keep imports at the top, use public `lifx` exports, type `main() -> None`, and show all three APIs progressively. Any address/serial shown must be documentation-only synthetic data (for example `192.0.2.0/24`, `2001:db8::/32`, and clearly synthetic serials). The test should execute the example against injected fakes; it must not perform ambient discovery.

---

### Discovery documentation and navigation

**Apply to:** `docs/user-guide/discovery.md`, `docs/user-guide/advanced-usage.md`, `docs/api/network.md`, and `mkdocs.yml`.

**Content source:** move, do not duplicate, the discovery body currently at `docs/user-guide/advanced-usage.md:16-83` into the new canonical guide. Preserve the proven targeted IPv6 validation wording and correct the obsolete “two discovery methods”/single-run claims.

Organise the new guide in the locked journey order:

1. unchanged `discover()` consumer;
2. explicit `discover_udp()` and `discover_mdns()` source control;
3. targeted lookup and IPv6 scope requirements;
4. method selection;
5. the four mDNS limitations;
6. troubleshooting.

**Single-source example inclusion:** `mkdocs.yml:160-174` already enables PyMdown Snippets. Include the executable file directly:

````markdown
```python
--8<-- "examples/discovery_progressive.py"
```
````

**Navigation pattern:** add `user-guide/discovery.md` beside the existing user-guide entries in both the llmstxt section (`mkdocs.yml:127-134`) and the ordinary site navigation (same user-guide navigation structure elsewhere in `mkdocs.yml`). Keep `docs/api/network.md` concise and factual; it should point to the guide rather than carry the consumer journey. Leave only a short summary/link in advanced usage.

**Known correction while editing:** `docs/api/network.md:141-147` says “exponential backoff and jitter”, but the current connection engine uses fixed escalating gaps and no blind jitter sleep. Replace it with wording consistent with `src/lifx/network/connection.py:760-770`.

---

### Documentation and repository-guidance contract tests

**Apply to:** `tests/test_network/test_mdns/test_phase_contract.py` and `tests/test_repository_guidance.py`.

**Primary analogue:** `tests/test_network/test_mdns/test_phase_contract.py:1-46,74-112,176-250`.

```python
import ast
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _normalised_prose(relative_path: Path) -> str:
    text = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    prose_lines = (
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    return " ".join(" ".join(prose_lines).split()).casefold()
```

Update the Phase 11 contract's canonical public-guidance path from advanced usage to `docs/user-guide/discovery.md`, and include the progressive example among audited public paths. Preserve its positive exact-phrase checks and negative unsupported/private-API checks.

The new repository-guidance test should read tracked files directly and assert:

- `CLAUDE.md` imports `@AGENTS.md` and contains only genuinely Claude-specific instructions beyond that import;
- shared architecture headings/prose are not duplicated in `CLAUDE.md`;
- neither guide contains `TaskGroup` as the repository's multi-device implementation;
- `AGENTS.md` accurately names independent per-device connections coordinated with `asyncio.gather()` on Python 3.10;
- the progressive example compiles/runs under fakes, the guide includes it via `--8<--`, all three public discovery APIs are named, all four limitations are present, navigation includes the guide, and synthetic-vs-hardware qualification is explicit.

Prefer semantic normalisation/AST inspection over brittle whole-file snapshots.

---

### `AGENTS.md`, `CLAUDE.md`, and `pyproject.toml`

**Canonical ownership:** `AGENTS.md` remains the shared and GSD-facing source. Replace the false line at `AGENTS.md:306` with source-accurate Python 3.10-compatible `asyncio.gather()` guidance. Reduce `CLAUDE.md` from its duplicated current body (`CLAUDE.md:1-462`) to `@AGENTS.md` plus genuinely Claude-specific material.

**Configuration pattern:** `pyproject.toml:90-123` explicitly enumerates hand-written scripts for Pyright and coverage.

```toml
[tool.pyright]
typeCheckingMode = "standard"
pythonVersion = "3.10"
include = ["src", "scripts/generate_theme_data.py"]

[tool.pytest.ini_options]
pythonpath = ["src", "scripts"]
addopts = """\
    ...
    --cov=lifx
    --cov=generate_theme_data
    ...
    """
```

Extend those explicit targets for the new hand-written measurement modules, or give the planner an equivalent explicit acceptance command that proves they are type-checked and covered. Do not add a runtime dependency or raise the Python floor.

## Shared Patterns

### Privacy and evidence identity

**Sources:** `scripts/measure_merged_discovery.py:94-205,750-766`; `tests/test_discovery_observation.py:17-74`; `AGENTS.md:17-38`.

Apply to every observer, journal, manifest, generated report, test fixture, and example:

- raw identity exists transiently only in memory;
- the external alias map must resolve outside the repository;
- request/discovery observers are value-only and repr-suppressed;
- write-boundary schema/privacy validation occurs before opening output;
- never persist serials, MACs, addresses, hostnames, ports/endpoints, packet bytes, raw exception strings, private captures, or the alias map;
- synthetic examples must be obviously synthetic and stable across related artefacts.

### Append-only source of truth and deterministic derivation

**Sources:** `scripts/measure_merged_discovery.py:499-545`; `tests/test_scripts/test_measure_merged_discovery.py:82-116,238-268`.

The manifest is create-exclusive/immutable. Journals append terminal facts and retain inconvenient outcomes. Validation rejects duplicates and cross-journal inconsistencies. Summary, ledger, and report are regenerated from validated journals in stable sort order and are never repaired by hand.

### Cancellation-safe ownership and restoration

**Sources:** `scripts/ipv6_thread_probe.py:1208-1264`; `src/lifx/network/connection.py:990-996`; `tests/test_scripts/test_ipv6_thread_probe.py:2003-2111`.

Every async generator, connection, target context, Animator, request-observer capture, and mutating stage has one clear owner and a `finally` cleanup. Restoration is attempted after clean completion, ordinary failure, cancellation, and `BaseException`; Phase 14 adds readback verification before reporting success.

### Private request instrumentation and read-only animation use

**Sources:** `tests/test_discovery_observation.py:17-131`; `src/lifx/network/connection.py:739-784`; `src/lifx/animation/animator.py:69-91,370-487`.

The request observer attaches only when explicitly requested, produces no side effect when absent, carries no user-visible identifier, and leaves public request behaviour unchanged. THREAD-03 consumes current `Animator.send_frame()` results/stats from the script without adding an observer, changing a constructor, or modifying production animation behaviour.

### Tests mirror the owning seam

- Script schemas/privacy/resume/restoration: `tests/test_scripts/`.
- Request send/accept/correlation: `tests/test_network/test_connection_retry.py`.
- Bounded animation schedule/current-stat mapping/zero-throughput/restoration: `tests/test_scripts/test_thread_revalidation.py` with an injected Animator fake.
- Documentation and guidance: tracked-file contract tests.

Use fake clocks and direct queue/socket injection. Synthetic/emulator tests prove mechanics only and must never be labelled Thread fleet evidence.

## No Analogue Found

No implementation file lacks a usable tracked analogue. The exact Phase 14 manifest/journal/generated-evidence schemas have no single existing file with the complete multi-stage contract, but their storage, privacy, validation, deterministic-summary, and restoration components are all covered by the assigned analogues above. The planner should combine those patterns with the locked D-01 to D-24 protocol rather than inventing a parallel framework.

## Metadata

**Analogue search scope:** `scripts/`, `src/lifx/network/`, read-only `src/lifx/animation/animator.py`, `tests/test_scripts/`, `tests/test_network/`, `tests/test_discovery_observation.py`, `examples/`, `docs/`, repository guidance, and build/test configuration.

**Primary tracked analogues:** 17 existing files checked; 9 used for concrete excerpts and the remainder used as in-place or testing/documentation counterparts.

**Pattern extraction date:** 2026-08-31

**Privacy note:** No live fleet identifier, endpoint, hostname, alias-map content, or raw diagnostic value was read or written while producing this map.
