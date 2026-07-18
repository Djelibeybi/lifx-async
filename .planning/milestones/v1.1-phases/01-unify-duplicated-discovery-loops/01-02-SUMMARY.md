---
phase: 01-unify-duplicated-discovery-loops
plan: "02"
subsystem: network/discovery
tags:
  - discovery
  - dos-protection
  - refactor
  - serial-validation
  - deduplication
dependency_graph:
  requires:
    - 01-01 (IdleDeadline utility class)
  provides:
    - Unified _discover_with_packet with hoisted serial validation + dedup + IdleDeadline
    - Thin discover_devices wrapper over _discover_with_packet
  affects:
    - src/lifx/network/discovery.py
    - tests/test_network/test_discovery_errors.py
tech_stack:
  added: []
  patterns:
    - Thin async-generator wrapper pattern (discover_devices delegates to _discover_with_packet)
    - First-wins per-serial deduplication in shared generator
    - IdleDeadline dual-timeout management (from Plan 01)
    - Structured dict-style logging throughout
key_files:
  modified:
    - src/lifx/network/discovery.py
    - tests/test_network/test_discovery_errors.py
decisions:
  - D-01: Serial validation unconditional in _discover_with_packet (broadcast/multicast bit or 0xff)
  - D-02: Rejected serials logged at DEBUG only (no WARNING-level per-packet logging)
  - D-04: First-wins per-serial dedup in _discover_with_packet; vestigial responses dict deleted
  - D-05: discover_devices is thin wrapper; _parse_device_state_service deleted; struct removed
metrics:
  duration: "5 minutes"
  completed: "2026-06-13"
  tasks_completed: 2
  files_modified: 2
---

# Phase 01 Plan 02: Thin discover_devices Wrapper and Unified Discovery Loop Summary

Unified `_discover_with_packet` by hoisting serial DoS validation, first-wins deduplication, and `IdleDeadline` timeout management into the shared generator. Replaced `discover_devices`'s 200-line duplicated loop with a trivial `async for` wrapper that extracts the device port from `StateService` payload. Deleted `_parse_device_state_service` and `import struct`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Hoist serial validation + dedup into _discover_with_packet; adopt IdleDeadline | 7f21ab1 | src/lifx/network/discovery.py |
| 2 | Thin discover_devices to wrapper; delete _parse_device_state_service | 07dc874 | src/lifx/network/discovery.py, tests/test_network/test_discovery_errors.py |

## Verification

- `uv run pyright` — 0 errors, 0 warnings
- `uv run ruff check .` — all checks passed
- `uv run --frozen pytest -q` — 2498 passed, 12 deselected (emulator tests skipped cleanly)
- `uv run --frozen pytest tests/test_network/test_discovery_devices.py -q` — 7 passed
- `uv run --frozen pytest tests/test_network/ -q` — 201 passed

## What Was Built

### Task 1: _discover_with_packet refactored

- Replaced `import allocate_source` with `import IdleDeadline, allocate_source`
- Replaced inline `idle_timeout` / `last_response_time` / dual-condition loop arithmetic with `IdleDeadline(timeout, idle_timeout)` instance
- `deadline.idle_expired` and `deadline.overall_expired` checked separately to preserve distinct DEBUG log messages per timeout type
- Added serial validation guard after pkt_type check: `header.target[0] & 0x01 or header.target == b"\xff" * 8` → DEBUG log + `continue` (D-01/D-02)
- `deadline.mark_response()` called on every valid protocol response (valid source, valid pkt_type, valid serial) — placed BEFORE the dedup `continue` so a duplicate flood cannot cause premature idle expiry (Pitfall 1/D-04)
- `seen_serials: set[str]` provides first-wins per-serial deduplication; duplicates continue without yielding (D-04)
- Deleted vestigial `responses: dict[str, DiscoveryResponse]` accumulator (written but never read)
- `LifxProtocolError` handler now uses `exc_info=True` (aligned with discover_devices handler that was deleted)
- Final completion log uses `len(seen_serials)` for `devices_found`

### Task 2: discover_devices thinned; _parse_device_state_service deleted

- Removed `import struct` (only user was `_parse_device_state_service`)
- Deleted `_parse_device_state_service` function (hand-rolled `struct.unpack("<BI", ...)` duplicating `StateService.unpack()`)
- Replaced ~200-line `discover_devices` body with thin `async for resp in _discover_with_packet(DevicePackets.GetService(), ...)` wrapper
- Device port extracted from `resp.response_payload["port"]` (lowercase key from `StateService.as_dict`, NOT `resp.port` which is the broadcast port parameter — Pitfall 2/4)
- Preserved full public signature: `timeout`, `broadcast_address`, `port`, `max_response_time`, `idle_timeout_multiplier`, `device_timeout`, `max_retries`
- Preserved `AsyncGenerator[DiscoveredDevice, None]` return annotation
- Updated docstring to reflect delegation pattern and removal of internal helper

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_discovery_errors.py imported deleted _parse_device_state_service**

- **Found during:** Task 2 verification
- **Issue:** `tests/test_network/test_discovery_errors.py` imported `_parse_device_state_service` at module level, causing `ImportError` and collection failure after the function was deleted
- **Fix:** Removed `_parse_device_state_service` from import and deleted `TestParseDeviceStateServiceErrors` class (4 tests pinned to retired internal; D-10 explicitly permits this when behaviour is covered via the shared path)
- **Coverage:** Serial validation and parsing correctness are proved by `TestDiscoverySourceValidation` (source mismatch, all-ff serial, multicast serial) and emulator tests in `TestDiscoveryDeduplication`
- **Files modified:** `tests/test_network/test_discovery_errors.py`
- **Commit:** 07dc874

Note: The plan anticipated this (`tests/test_network/test_discovery_errors.py` still references `_parse_device_state_service` until Plan 05 rewrites it`), but the blocking import error required fixing now rather than in Plan 05.

## Threat Flags

No new threat surface introduced. The refactor closes surface:

| Control | File | Description |
|---------|------|-------------|
| T-01-02 mitigated | src/lifx/network/discovery.py | Broadcast/multicast serial guard now in _discover_with_packet — all callers (find_by_label, enrichment paths) are hardened |
| T-01-04 mitigated | src/lifx/network/discovery.py | Invalid serial rejection demoted to DEBUG (not WARNING) — no log-flooding amplification on hostile networks |
| T-01-05 mitigated | src/lifx/network/discovery.py | mark_response() called before dedup check — same-serial floods cannot truncate discovery prematurely |

## Known Stubs

None. All behaviour is fully implemented and verified.

## Self-Check: PASSED

- SUMMARY.md: FOUND
- Commit 7f21ab1 (Task 1): FOUND
- Commit 07dc874 (Task 2): FOUND
