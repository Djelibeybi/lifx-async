---
phase: quick-260830-ea6
plan: "01"
subsystem: testing
tags: [pytest, pytest-retry, ci, mdns, windows]
requires:
  - phase: phase-12
    provides: Cross-platform IPv6 discovery tests and CI matrix coverage
provides:
  - One zero-delay retry for approved transient network exceptions
  - Assertion-aware retry overrides for Windows emulator tests
  - Deterministic mDNS packet-permutation timing
affects: [ci, discovery, mdns, windows]
actuals:
  tokens: 1899
  tasks: 3
  commits: 4
tech-stack:
  added: []
  patterns:
    - Global retry policy remains exception-filtered
    - Platform-specific flaky markers explicitly replace the global exception filter
key-files:
  created: []
  modified:
    - pyproject.toml
    - tests/conftest.py
    - tests/test_api/test_ipv6_e2e.py
    - tests/test_network/test_discovery_devices.py
    - tests/test_network/test_discovery_errors.py
    - tests/test_network/test_discovery_rebroadcast.py
    - tests/test_network/test_mdns/test_discovery.py
key-decisions:
  - "Retry only LifxTimeoutError and LifxConnectionError suite-wide; ordinary assertions remain immediate failures."
  - "Allow AssertionError only on the five existing Windows emulator flaky markers, alongside the approved network exceptions."
  - "Terminate the synthetic mDNS permutation script with a fake deadline rather than elapsed wall time."
requirements-completed: []
coverage:
  - id: D1
    description: One zero-delay suite-wide retry is enabled for approved transient network exceptions.
    verification:
      - kind: unit
        ref: pytest Config.fromdictargs retry ini assertion
        status: pass
    human_judgment: false
  - id: D2
    description: All five Windows emulator flaky markers retry assertion-shaped and approved network failures.
    verification:
      - kind: unit
        ref: targeted collection, retry tuple assertions, and Ruff
        status: pass
    human_judgment: false
  - id: D3
    description: The mDNS packet-permutation regression uses controlled fake-deadline exhaustion.
    verification:
      - kind: unit
        ref: tests/test_network/test_mdns/test_discovery.py#test_generator_packet_permutations_yield_one_equal_record
        status: pass
    human_judgment: false
duration: 6min
completed: 2026-08-30
status: complete
---

# Quick Task 260830-ea6: Pytest Retry Configuration Summary

**One filtered suite-wide retry, bounded Windows assertion overrides, and deterministic mDNS permutation coverage reduce matrix noise without masking ordinary assertion failures.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-08-30T00:23:25Z
- **Completed:** 2026-08-30T00:28:59Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Enabled exactly one zero-delay pytest-retry attempt for the existing network-only exception filter.
- Added a named Windows emulator exception tuple and applied it to all five pre-existing flaky markers.
- Replaced the mDNS permutation test's 0.1-second wall-clock dependency with scripted fake-deadline exhaustion.

## Task Commits

1. **Task 1: Activate one filtered suite-wide retry** - `aba54f1` (test)
2. **Task 2: Make existing Windows flaky markers retry their actual failure shape** - `4609df8` (test)
3. **Task 3 RED: Expose the synthetic deadline termination requirement** - `5fc4b0d` (test)
4. **Task 3 GREEN: Make mDNS permutation timing deterministic** - `e1ba123` (test)

All four commits are GPG-signed and include the developer sign-off.

## Files Created/Modified

- `pyproject.toml` - Enables one retry with no delay.
- `tests/conftest.py` - Defines immutable global and Windows emulator retry exception tuples.
- `tests/test_api/test_ipv6_e2e.py` - Applies the Windows exception override to targeted IPv6 emulator retrying.
- `tests/test_network/test_discovery_devices.py` - Applies the override to two emulator classes.
- `tests/test_network/test_discovery_errors.py` - Applies the override to malformed-packet emulator tests.
- `tests/test_network/test_discovery_rebroadcast.py` - Applies the override to rebroadcast emulator tests.
- `tests/test_network/test_mdns/test_discovery.py` - Uses a per-permutation fake deadline and finite scripted receiver.

## Verification

- Pytest configuration assertion: passed (`retries == "1"`, `retry_delay == "0"`).
- Retry exception tuple and five-marker assertions: passed.
- Targeted collection: 75 tests collected.
- Targeted mDNS permutation regression: 1 passed.
- Ruff checks: passed for every modified Python test file.
- Full frozen suite: 4091 passed, 12 deselected, 97% coverage in 149.37 seconds.
- Retry report: none; the full suite passed on first attempts.

## Decisions Made

- Kept the global filter exactly `LifxTimeoutError` and `LifxConnectionError` so arbitrary assertions do not become flaky suite-wide.
- Included both network exceptions and `AssertionError` in the Windows tuple because an explicit `only_on` replaces pytest-retry's global filter.
- Preserved the Windows markers' existing two retries and one-second delay; only their eligible exception set changed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The Task 3 RED timeout was the expected TDD failure proving that a non-expiring fake deadline could not terminate the scripted discovery loop; the GREEN commit added controlled exhaustion.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The retry policy and deterministic mDNS regression are ready for the cross-platform CI matrix. No blockers remain.

## Self-Check: PASSED

- All seven declared modified files exist.
- All four task commits exist and contain GPG signatures plus developer sign-offs.
- All targeted verification and the full frozen suite passed.

---
*Quick task: 260830-ea6*
*Completed: 2026-08-30*
