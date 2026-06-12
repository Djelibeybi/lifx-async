---
phase: 01-unify-duplicated-discovery-loops
plan: "04"
subsystem: network
tags: [deprecation, warnings, transport, testing]

# Dependency graph
requires: []
provides:
  - "UdpTransport.receive_many emits DeprecationWarning naming v2.0 at call time (D-09)"
  - "pytest.warns test asserting deprecation fires (D-12)"
affects:
  - "v2.0 removal of receive_many"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "stdlib warnings.warn with stacklevel=2 for deprecation signalling"
    - ".. deprecated:: reStructuredText docstring note for deprecated methods"
    - "pytest.warns(DeprecationWarning, match=...) to assert warning fires"

key-files:
  created: []
  modified:
    - src/lifx/network/transport.py
    - tests/test_network/test_transport.py

key-decisions:
  - "warnings.warn placed before the if self._protocol is None guard so it fires even when the guard would raise"
  - "stacklevel=2 so the warning points at the caller, not at receive_many itself"
  - "Method body otherwise untouched — deprecation cycle starts here, removal deferred to v2.0"

patterns-established:
  - "Deprecation pattern: import warnings + warnings.warn(msg, DeprecationWarning, stacklevel=2) before first guard"
  - "Docstring pattern: .. deprecated:: note after Raises section, pointing to replacement"

requirements-completed:
  - D-09
  - D-12

# Metrics
duration: 2min
completed: 2026-06-13
---

# Phase 1 Plan 04: Deprecate UdpTransport.receive_many Summary

**UdpTransport.receive_many emits a stacklevel=2 DeprecationWarning naming v2.0 with a `.. deprecated::` docstring note, verified by a new pytest.warns test (D-09, D-12)**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-12T15:33:06Z
- **Completed:** 2026-06-12T15:35:13Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `import warnings` to `transport.py` import block (alphabetically ordered with stdlib)
- Added `warnings.warn(..., DeprecationWarning, stacklevel=2)` at the top of `receive_many` body, before the protocol-closed guard, naming v2.0 as the removal target
- Added `.. deprecated::` reStructuredText docstring note after the Raises section, pointing callers to `receive()` in a loop or `_discover_with_packet()` as replacements
- Added `test_receive_many_emits_deprecation_warning` test using `pytest.warns(DeprecationWarning, match="v2.0")`
- All 30 existing transport tests continue to pass (D-10)

## Task Commits

Each task was committed atomically using TDD RED/GREEN:

1. **RED: test_receive_many_emits_deprecation_warning (failing)** - `fc624dc` (test)
2. **GREEN: deprecate receive_many in transport.py** - `b17fd32` (feat)

**Plan metadata:** _(docs commit follows)_

_Note: TDD plan — RED commit (test) precedes GREEN commit (implementation)_

## Files Created/Modified

- `src/lifx/network/transport.py` — Added `import warnings`; added `warnings.warn` call and `.. deprecated::` docstring note to `receive_many`
- `tests/test_network/test_transport.py` — Added `test_receive_many_emits_deprecation_warning`

## Decisions Made

- `warnings.warn` placed before the `if self._protocol is None:` guard, so the deprecation warning is always emitted at call time regardless of socket state.
- `stacklevel=2` ensures warnings point at the caller site, not at the internal `receive_many` frame.
- Method body otherwise unchanged — this is a deprecation-only change; removal is deferred to v2.0.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Pre-commit hook (ruff E501) caught a docstring line > 88 characters in the test. Fixed by shortening the docstring text before the final RED commit.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `receive_many` deprecation cycle started; removal can proceed in v2.0 without breaking current callers.
- Plans 01-02 and 01-03 (discovery refactor) are independent; no blocking dependencies from this plan.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Deprecation signalling only; the method body (including existing oversized/undersized packet-drop DoS guards) is untouched.

---
*Phase: 01-unify-duplicated-discovery-loops*
*Completed: 2026-06-13*

## Self-Check: PASSED

- `src/lifx/network/transport.py` — FOUND
- `tests/test_network/test_transport.py` — FOUND
- `.planning/phases/01-unify-duplicated-discovery-loops/01-04-SUMMARY.md` — FOUND
- Commit `fc624dc` (RED test) — FOUND
- Commit `b17fd32` (GREEN feat) — FOUND
