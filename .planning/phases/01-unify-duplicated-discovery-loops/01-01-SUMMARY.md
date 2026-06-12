---
phase: 01-unify-duplicated-discovery-loops
plan: "01"
subsystem: network/utils
tags: [idle-deadline, dual-timeout, monotonic-clock, tdd, utils]
dependency_graph:
  requires: []
  provides: [lifx.network.utils.IdleDeadline]
  affects: []
tech_stack:
  added: []
  patterns: [dual-deadline timer, monotonic clock, mock-time unit tests]
key_files:
  created:
    - src/lifx/network/utils.py (IdleDeadline class added)
    - tests/test_network/test_utils.py
  modified: []
decisions:
  - "Assign _last_response = _start in __init__ (single monotonic read) — avoids skew between the two initial values"
  - "idle_expired and overall_expired as separate properties — preserves the two distinct DEBUG log messages in existing discovery loops"
  - "expired = idle_expired or overall_expired convenience property — simplifies loop condition in Plans 02 and 03"
metrics:
  duration_minutes: 3
  completed_date: "2026-06-13"
  tasks_completed: 2
  files_changed: 2
---

# Phase 1 Plan 01: Add IdleDeadline to network/utils.py — Summary

**One-liner:** Monotonic dual-deadline timer (`IdleDeadline`) with `remaining()`, `mark_response()`, `idle_expired`, and `overall_expired` extracted from triplicated discovery loop arithmetic and covered by 5 deterministic mocked-time unit tests.

## What Was Built

Added `class IdleDeadline` to `src/lifx/network/utils.py`, alongside the existing `allocate_source()` function. The class encapsulates the dual-timeout (overall + idle) pattern that is hand-rolled identically in `_discover_with_packet`, `discover_devices`, and the mDNS `discover_lifx_services` loop. This is the foundation consumed by Plans 02 and 03.

### Public Surface

| Member | Type | Description |
|--------|------|-------------|
| `__init__(timeout, idle_timeout)` | method | Captures `time.monotonic()` as `_start` and `_last_response` |
| `remaining()` | method | Returns `min(overall_remaining, idle_remaining)` from one monotonic read |
| `mark_response()` | method | Resets `_last_response` to current monotonic time |
| `idle_expired` | property | True when idle window since last response has elapsed |
| `overall_expired` | property | True when overall window since construction has elapsed |
| `expired` | property | Convenience: `idle_expired or overall_expired` |

### Tests Created (`tests/test_network/test_utils.py`)

| Test | Assertion |
|------|-----------|
| `test_idle_deadline_remaining_positive_on_construction` | `remaining() > 0` immediately after construction |
| `test_idle_deadline_overall_expires` | `remaining() <= 0` and `overall_expired = True` at t=6 (timeout=5) |
| `test_idle_deadline_idle_expires` | `remaining() <= 0` and `idle_expired = True` at t=3 (idle_timeout=2, overall=5) |
| `test_idle_deadline_mark_response_resets_idle` | After `mark_response()` at t=1, `remaining() > 0` at t=1.5 |
| `test_idle_deadline_overall_caps_idle` | `remaining() < 1.0` when overall=0.05 s left but idle=1.95 s left |

All tests use `unittest.mock.patch("lifx.network.utils.time.monotonic")` with deterministic sequences — zero real sleeps.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED | `43c507c` `test(01-01): add failing test for IdleDeadline` | PASS |
| GREEN (impl) | `85220dd` `feat(01-01): implement IdleDeadline in network/utils.py` | PASS |
| GREEN (tests) | `87df234` `feat(01-01): add IdleDeadline unit tests in test_network/test_utils.py` | PASS |

## Verification Evidence

- `uv run pyright src/lifx/network/utils.py` → 0 errors, 0 warnings
- `uv run pyright` (full project) → 0 errors, 0 warnings
- `uv run ruff check .` → All checks passed
- `uv run --frozen pytest tests/test_network/test_utils.py -v` → 5 passed
- `grep -c "class IdleDeadline" src/lifx/network/utils.py` → 1
- `grep -v '^#' src/lifx/network/utils.py | grep -c 'time\.time()'` → 0

## Deviations from Plan

None — plan executed exactly as written.

The only minor fix was ruff-format reformatting `iter([...])` to `iter(\n    [\n        ...\n    ]\n)` in the test file; this was handled automatically by the pre-commit hook and re-staged before commit.

## Decisions Made

1. **Single monotonic read at construction** — `_last_response = _start` reuses the same instant captured for `_start`, avoiding any skew between the two initial values (the plan's action said "initialised to the start").
2. **`idle_expired` and `overall_expired` as separate `@property` methods** — satisfies the plan's requirement to distinguish idle vs overall expiry for the two distinct DEBUG log messages in existing discovery loops (Claude's-discretion item in D-06).
3. **Patch target is `lifx.network.utils.time.monotonic`** — patching the module-level `time` import where `IdleDeadline` reads it; this is the correct mock target for stdlib module imports.

## Known Stubs

None.

## Threat Flags

None — this plan adds a pure timing helper with no network or external-input surface.

## Self-Check: PASSED

- `src/lifx/network/utils.py` exists and contains `class IdleDeadline` ✓
- `tests/test_network/test_utils.py` exists and imports `IdleDeadline` ✓
- Commits `43c507c`, `85220dd`, `87df234` confirmed in git log ✓
