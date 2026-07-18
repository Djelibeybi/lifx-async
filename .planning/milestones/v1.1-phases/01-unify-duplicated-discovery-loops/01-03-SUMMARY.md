---
phase: 01-unify-duplicated-discovery-loops
plan: 03
subsystem: network/mdns
tags: [refactor, deadline, exception-handling, mdns, discovery]
dependency_graph:
  requires: [01-01]
  provides: [IdleDeadline adoption in mDNS discovery, typed exception routing in mDNS receive loop]
  affects: [src/lifx/network/mdns/discovery.py]
tech_stack:
  added: []
  patterns: [IdleDeadline, typed exception routing (LifxTimeoutError/LifxNetworkError/Exception)]
key_files:
  created: []
  modified:
    - src/lifx/network/mdns/discovery.py
    - tests/test_network/test_mdns/test_discovery.py
decisions:
  - "D-07: IdleDeadline replaces the third copy of inline idle/overall deadline arithmetic in discover_lifx_services"
  - "D-08: transport.receive() exceptions routed by type — LifxTimeoutError breaks cleanly, LifxNetworkError logs WARNING + breaks, unexpected exceptions log ERROR with exc_info=True and re-raise"
  - "mark_response() called after each yielded record (preserves existing idle-reset semantics)"
  - "request_time local variable removed — IdleDeadline captures its own start time"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-13"
  tasks_completed: 1
  files_modified: 2
---

# Phase 1 Plan 03: mDNS IdleDeadline Adoption and Exception Tightening Summary

**One-liner:** `discover_lifx_services` now uses `IdleDeadline` for timeout arithmetic and routes `transport.receive()` exceptions by type — retiring the third copy of the inline dual-deadline logic (D-07) and stopping genuine socket errors from silently masquerading as "no devices found" (D-08).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Adopt IdleDeadline and tighten exception handling in discover_lifx_services | ce3c827 | src/lifx/network/mdns/discovery.py, tests/test_network/test_mdns/test_discovery.py |

## What Was Built

### `src/lifx/network/mdns/discovery.py`

The `discover_lifx_services` async generator was refactored:

1. **New imports added** (alongside existing import block):
   - `from lifx.exceptions import LifxNetworkError, LifxTimeoutError`
   - `from lifx.network.utils import IdleDeadline`

2. **Inline deadline arithmetic replaced** (`D-07`): The `idle_timeout = max_response_time * idle_timeout_multiplier` / `last_response_time = request_time` setup and the dual-condition loop header (checking `elapsed_since_last >= idle_timeout` and `time.monotonic() - request_time >= timeout` with separate remaining calculations) were replaced with a single `IdleDeadline(timeout, idle_timeout)` instance. The two distinct DEBUG log messages are preserved with their original `class/method/action` fields.

3. **Typed exception routing added** (`D-08`): The bare `except Exception:` block around `transport.receive()` (which swallowed all errors into a generic "no_responses" debug log) was replaced with three typed clauses:
   - `except LifxTimeoutError: break` — clean end of collection
   - `except LifxNetworkError as e:` — WARNING dict-style log with `action: "network_error"`, then `break`
   - `except Exception as e:` — ERROR dict-style log with `action: "unexpected_error"`, `exc_info=True`, then `raise`

4. **`deadline.mark_response()` call**: Replaced `last_response_time = response_timestamp` after each yielded record, preserving idle-reset semantics.

5. **Removed `request_time` local variable**: Was only used for the inline deadline arithmetic; `IdleDeadline` captures its own start time at construction.

The inner `except Exception` block wrapping DNS parsing (lines 341-351) was not touched — that is out of D-08's scope.

### `tests/test_network/test_mdns/test_discovery.py`

Updated seven existing tests to use `LifxTimeoutError("timeout")` instead of bare `Exception("timeout")` as the terminating mock side-effect, matching the new typed exception handler. Also updated the `test_discover_idle_timeout` slow_receive helper to raise `LifxTimeoutError`.

Added two new tests for the D-08 exception branches:
- `test_discover_network_error_does_not_propagate`: verifies `LifxNetworkError` breaks cleanly without propagating
- `test_discover_unexpected_error_propagates`: verifies unexpected `RuntimeError` is re-raised

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated tests to use LifxTimeoutError instead of bare Exception**
- **Found during:** Task 1 verification (`uv run --frozen pytest tests/test_network/test_mdns/ -q`)
- **Issue:** Seven existing tests used `Exception("timeout")` as the mock side-effect for the "stop collecting" case. After tightening the exception handler to typed clauses, bare `Exception` now hits the `except Exception as e: raise` branch instead of breaking, causing those tests to fail with `Exception: timeout`.
- **Fix:** Replaced all `Exception("timeout")` / `Exception("No data")` side-effects in `TestDiscoverLifxServices` tests with `LifxTimeoutError(...)`. Also added the `LifxTimeoutError` import to the test module.
- **Files modified:** `tests/test_network/test_mdns/test_discovery.py`
- **Commit:** ce3c827 (included in same task commit)

**2. [Rule 2 - Missing critical functionality] Added tests for new LifxNetworkError and unexpected error branches**
- **Found during:** Task 1 — D-08's new exception routing paths lacked test coverage
- **Fix:** Added `test_discover_network_error_does_not_propagate` and `test_discover_unexpected_error_propagates` to cover the two new exception branches.
- **Files modified:** `tests/test_network/test_mdns/test_discovery.py`
- **Commit:** ce3c827 (included in same task commit)

## Verification Results

- `uv run pyright src/lifx/network/mdns/discovery.py`: 0 errors, 0 warnings
- `uv run ruff check src/lifx/network/mdns/discovery.py`: All checks passed
- `uv run ruff check tests/test_network/test_mdns/test_discovery.py`: All checks passed
- `uv run --frozen pytest tests/test_network/test_mdns/ -q`: 98 passed (96 pre-existing + 2 new)

## Acceptance Criteria Check

- [x] `grep -c "IdleDeadline" src/lifx/network/mdns/discovery.py` → 2
- [x] `grep -c "except LifxTimeoutError" src/lifx/network/mdns/discovery.py` → 1
- [x] `grep -c "except LifxNetworkError" src/lifx/network/mdns/discovery.py` → 1
- [x] `network_error` branch uses `_LOGGER.warning(`; `unexpected_error` branch uses `_LOGGER.error(` with `exc_info=True` and a following `raise`
- [x] `grep -c "last_response_time" src/lifx/network/mdns/discovery.py` → 0
- [x] Pyright reports 0 errors
- [x] mDNS tests pass

## Known Stubs

None.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The refactor tightens the existing mDNS receive loop without adding new attack surface. T-01-06 (socket errors silently swallowed) is now mitigated per the threat register.

## Self-Check: PASSED

- `src/lifx/network/mdns/discovery.py` — exists and contains IdleDeadline
- `tests/test_network/test_mdns/test_discovery.py` — exists and contains LifxTimeoutError import
- Commit ce3c827 — confirmed in git log
