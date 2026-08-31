---
phase: 13-merged-discovery
plan: 05
subsystem: discovery
tags: [asyncio, udp, mdns, serial-lookup, cancellation, deadlines]

requires:
  - phase: 13-merged-discovery
    provides: process-wide shared UDP discovery coordination from Plan 13-02
  - phase: 13-merged-discovery
    provides: directly verified mDNS device construction from Plan 13-03
  - phase: 13-merged-discovery
    provides: typed source events and cancellation-resistant aggregate cleanup from Plan 13-04
provides:
  - dual-source exact-serial lookup across shared UDP and verified mDNS discovery
  - malformed-input rejection before any network work while preserving intentional ASCII-space normalisation
  - caller-deadline and loser-cleanup guarantees across success, failure, timeout, and cancellation
  - deterministic repeated and concurrent lookup lifecycle coverage
affects: [13-06-emulator-evidence, 13-07-fleet-evidence, find_by_serial]

actuals:
  tokens: 7631
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - per-call typed event queue for exact serial matches and source terminal states
    - raw UDP discovery records constructed only after both source legs have closed
    - winner pumps suspended at the yield boundary until aggregate cancellation owns finalisation

key-files:
  created: []
  modified:
    - src/lifx/api.py
    - tests/test_api/test_api_discovery.py

key-decisions:
  - "Canonicalise the requested serial once before source creation and preserve malformed input as a quiet None result."
  - "Race shared UDP records and directly verified mDNS devices under one caller-origin wall deadline with no source preference."
  - "Cancel and reap both source legs before constructing a UDP winner or returning an already constructed mDNS winner."
  - "Keep a winning source pump suspended at its yield boundary until aggregate cleanup cancels it, so asynchronous generator finalisers cannot be interrupted by normal task completion."

patterns-established:
  - "Lookup boundary: only exact canonical serial matches enter the per-call winner queue; a no-match leg completion cannot mask the other source."
  - "Ownership boundary: source tasks and generators are fully reaped before every return, propagated error, or caller cancellation."
  - "Deadline boundary: compatible shared UDP replay retains the producer deadline while the lookup independently enforces its caller-origin wall deadline."

requirements-completed: [FIND-05, FIND-09]

coverage:
  - id: D1
    description: "find_by_serial() returns the first exact valid match from shared UDP or verified mDNS without source preference."
    requirement: FIND-05
    verification:
      - kind: integration
        ref: "tests/test_api/test_api_discovery.py#TestFindBySerialRace"
        status: pass
    human_judgment: false
  - id: D2
    description: "Repeated, concurrent, timeout, failure, and cancellation paths retain no per-call winner state or owned discovery resources."
    requirement: FIND-05
    verification:
      - kind: integration
        ref: "tests/test_api/test_api_discovery.py#TestFindBySerialRaceLifecycle"
        status: pass
    human_judgment: false
  - id: D3
    description: "Malformed serials return None before network work, ASCII spaces normalise intentionally, and the public signature exposes no source selector."
    requirement: FIND-09
    verification:
      - kind: unit
        ref: "tests/test_api/test_api_discovery.py#test_find_by_serial_malformed_input_starts_no_network_work"
        status: pass
      - kind: unit
        ref: "tests/test_api/test_api_discovery.py#test_find_by_serial_intentionally_normalises_ascii_spaces"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-08-31
status: complete
---

# Phase 13 Plan 05: Dual-Source Serial Lookup Summary

**Exact serial lookup now races shared UDP and verified mDNS under one deadline, reaping both source legs before returning any result**

## Performance

- **Duration:** 15 min
- **Started:** 2026-08-30T16:41:42Z
- **Completed:** 2026-08-30T16:56:57Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Reworked `find_by_serial()` into a first-valid dual-source race that accepts exact canonical serial matches from either shared UDP or directly verified mDNS discovery.
- Preserved the public invalid-input contract by returning `None` before source creation for malformed serials while explicitly covering `Serial.from_string()`'s intentional ASCII-space stripping.
- Enforced one caller-origin deadline across replay, source work, UDP construction, and return, without replacing the shared coordinator's producer-origin wire deadline.
- Added deterministic ordering, failure, no-match, repetition, concurrency, cancellation, construction, and finalisation coverage with no fixed sleeps or ambient mDNS dependency.

## Task Commits

Task 1 followed the mandatory RED/GREEN cycle and Task 2 was committed atomically:

1. **Task 1 RED: Define the dual-source exact-match contract** - `4ff7792` (test)
2. **Task 1 GREEN: Race shared UDP and verified mDNS serial matches** - `092067c` (feat)
3. **Task 2: Prove repeated, concurrent, cancelled, and early-return lifecycle safety** - `d04f6c1` (fix)

## Files Created/Modified

- `src/lifx/api.py` - Adds serial-specific source pumps, the per-call race owner, caller-deadline enforcement, and invalid-input prevalidation.
- `tests/test_api/test_api_discovery.py` - Adds the exact-match race and lifecycle matrix and updates the legacy ownership seam for shared UDP discovery.

## Decisions Made

- UDP pumps publish validated raw discovery records so device construction cannot begin until the race owner has cancelled and reaped both legs; verified mDNS candidates are already constructed at their required liveness boundary.
- A source that publishes a winner remains suspended at the yield boundary until the race owner cancels it. This gives aggregate cleanup sole ownership of asynchronous generator finalisation and prevents normal pump completion from interrupting a blocked `finally` block.
- Source terminal events are bookkeeping rather than results. `None` is returned only when both legs have completed without a match or the caller deadline expires.
- Every lookup owns its event queue and mDNS work. Compatible UDP callers retain Plan 13-02 sharing and replay semantics without sharing match or failure state.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Protected source finalisers after a winner was queued**

- **Found during:** Task 2 cancellation-after-match lifecycle test
- **Issue:** A winning pump could return immediately after queueing its match and enter its asynchronous generator `finally` block before aggregate cleanup ran. Cancelling that already-finalising pump could interrupt a blocked finaliser instead of waiting for it.
- **Fix:** Kept each winning pump suspended at its source yield boundary until the race owner cancels it, then let `_cancel_and_reap()` shield and await the single aggregate cleanup path.
- **Files modified:** `src/lifx/api.py`
- **Verification:** The cancellation-after-match test, all 27 serial/cancellation/concurrency tests, the public discovery suite, adjacent coordinator/liveness suites, and the complete repository suite pass.
- **Committed in:** `d04f6c1`

**2. [Rule 1 - Bug] Reconciled generated closeout prose and formatting**

- **Found during:** Plan metadata closeout
- **Issue:** The state handlers advanced to Plan 6 but retained Plan 13-04 activity prose, recorded the realised duration without standard spacing, and emitted a malformed roadmap status cell.
- **Fix:** Updated the current activity description, normalised the duration display, and restored roadmap table spacing without altering handler-owned counts.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** State names Plan 6 of 7 as ready, the roadmap shows 5/7 in progress, and `git diff --check` passes.
- **Committed in:** Plan metadata commit

**3. [Rule 1 - Bug] Restored the mandatory DCO trailer on the metadata commit**

- **Found during:** Final commit verification
- **Issue:** The GSD commit helper created a correctly GPG-signed metadata commit but omitted the repository-required `Signed-off-by` trailer.
- **Fix:** Amended the same unpushed metadata commit with `git commit --amend -S -s --no-edit` after adding this record.
- **Files modified:** None beyond the existing metadata commit contents.
- **Verification:** The final commit reports the mandated signing key and contains the DCO trailer.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs)
**Impact on plan:** The runtime fix is confined to source ownership and is necessary for the plan's explicit pre-return cleanup contract; the metadata corrections keep closeout state and repository history internally consistent. No public API or implementation scope changed.

## Issues Encountered

None.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 13-06 can exercise the completed merged-discovery and serial-lookup paths through the paired emulator CI harness and prepare the private fleet handoff. There are no implementation blockers.

## Automated Gates

- Task 1 RED proof: 10 failed, 2 passed, 67 deselected against the prior UDP-only implementation.
- Task 1 planned selection: 18 passed, 61 deselected.
- Task 2 lifecycle selection: 8 passed, 79 deselected.
- Complete serial/cancellation/concurrency selection: 27 passed, 60 deselected.
- Public API discovery suite with `ResourceWarning` promoted: 87 passed.
- Adjacent coordinator and mDNS liveness suites: 47 passed, 1 skipped.
- Repository suite: 4,271 passed, 1 skipped, 12 deselected.
- Repository Ruff formatting and lint: passed.
- Repository Pyright: 0 errors, 0 warnings.

## Self-Check: PASSED

Both implementation/test files and all three signed, DCO-compliant task commits were verified before state advancement. The TDD RED commit precedes the GREEN implementation commit, and the resolved deviation is recorded in `.planning/WINDOWS.md`.

---
*Phase: 13-merged-discovery*
*Completed: 2026-08-31*
