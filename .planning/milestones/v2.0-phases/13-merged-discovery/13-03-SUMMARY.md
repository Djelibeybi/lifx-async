---
phase: 13-merged-discovery
plan: 03
subsystem: discovery
tags: [asyncio, mdns, liveness, deadlines, privacy]

requires:
  - phase: 13-merged-discovery
    provides: invocation-local mDNS records, caller-owned observations, and immutable entry-gate invariants from Plan 13-01
provides:
  - product-directed current-call mDNS liveness verification before merge eligibility
  - one-deadline, sixteen-worker candidate verification with deterministic cleanup
  - privacy-bounded sweep and candidate failure events with standalone compatibility
  - immutable StateColor construction snapshots without volatile getter caching
affects: [13-04-merged-discovery, discover, discover_mdns, discovery-measurements]

actuals:
  tokens: 16603
  tasks: 2
  commits: 5

tech-stack:
  added: []
  patterns:
    - product-directed GetColor verification with a synthetic-only future Echo branch
    - one monotonic caller deadline shared by record consumption, queueing, and requests
    - bounded typed failures that exclude exception text, identities, endpoints, and payloads

key-files:
  created:
    - tests/test_network/test_mdns/test_liveness.py
    - .planning/phases/13-merged-discovery/deferred-items.md
  modified:
    - src/lifx/devices/light.py
    - src/lifx/network/mdns/discovery.py
    - src/lifx/network/mdns/transport.py
    - tests/test_devices/test_state_light.py

key-decisions:
  - "Use GetColor for every currently supported classifier outcome; unsupported products drop locally, and exact Echo remains reachable only through a synthetically injected future non-Light class."
  - "Treat sixteen concurrent probes as a reasoned D-07 safety bound, not a measured optimum."
  - "Create the caller deadline before consuming mDNS records so queue wait, retries, and cleanup cannot obtain fresh time windows."
  - "Preserve standalone mDNS propagation and detail logging while the merged private sink receives only bounded stage, reason, and error-type fields."

patterns-established:
  - "State adoption boundary: one private helper decodes StateColor for both normal get_color() and discovery construction, while getters continue to perform network requests."
  - "Candidate verification boundary: classifier, correlated response validation, construction, connectivity, and StateColor adoption all complete before a device may yield."
  - "Failure boundary: expected sweep and candidate failures emit exactly once at their catch or rejection site; cancellation and unexpected errors propagate after cleanup."

requirements-completed: [FIND-01, FIND-04, FIND-08]

coverage:
  - id: D1
    description: "Every current supported mDNS candidate proves current-call liveness with correlated GetColor and carries adopted StateColor before eligibility."
    requirement: FIND-04
    verification:
      - kind: integration
        ref: "tests/test_network/test_mdns/test_liveness.py#supported subclasses, response validation, adoption, and cleanup"
        status: pass
    human_judgment: false
  - id: D2
    description: "mDNS record consumption, probe queueing, requests, and cleanup share one caller deadline with no more than sixteen active probes."
    requirement: FIND-01
    verification:
      - kind: integration
        ref: "tests/test_network/test_mdns/test_liveness.py#probe cap, queued expiry, early close, cancellation, and fresh-call tests"
        status: pass
    human_judgment: false
  - id: D3
    description: "Raw candidate observations retain eligible firmware and connectivity only in the current context while typed failures and merged logs suppress sensitive values."
    requirement: FIND-08
    verification:
      - kind: integration
        ref: "tests/test_network/test_mdns/test_liveness.py#observation, malformed firmware, sweep failure, candidate failure, and logging tests"
        status: pass
    human_judgment: false

duration: 29min
completed: 2026-08-31
status: complete
---

# Phase 13 Plan 03: mDNS Liveness Verification Summary

**Current-call, product-directed mDNS verification with one bounded deadline, privacy-safe failure events, and pre-yield StateColor adoption**

## Performance

- **Duration:** 29 min
- **Started:** 2026-08-30T15:34:12Z
- **Completed:** 2026-08-30T16:02:50Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added one private StateColor adoption seam that records an immutable construction snapshot and updates compatible existing state without fabricating a partial `LightState`.
- Required every currently supported mDNS candidate to answer a correlated GetColor request before construction, with unsupported products isolated and exact Echo retained only for a synthetic future non-Light classifier outcome.
- Bounded record consumption, a fixed sixteen-worker pool, queue wait, retries, and cleanup under one monotonic caller deadline; the cap is a reasoned safety choice rather than a measured optimum.
- Added exactly-once, value-suppressed sweep and candidate failure events while preserving standalone mDNS propagation, absorption, and logging behaviour.
- Proved wrong identity/type/payload responses, silence, StateUnhandled, expected failures, cancellation, early close, malformed firmware, and unexpected errors cannot leak candidates or resources.

## Task Commits

Each task was committed atomically with separate RED and GREEN gates:

1. **Task 1 RED: Define the StateColor adoption contract** - `515f3a5` (test)
2. **Task 1 GREEN: Adopt StateColor construction snapshots** - `075f1ef` (feat)
3. **Task 2 RED: Define the mDNS liveness contract** - `dfcdd00` (test)
4. **Task 2 GREEN: Verify bounded mDNS candidates** - `536a213` (feat)

## Files Created/Modified

- `src/lifx/devices/light.py` - Adds `_DiscoveryLightSnapshot` and centralises StateColor decoding/adoption while retaining fresh getters.
- `src/lifx/network/mdns/discovery.py` - Adds product-directed candidate verification, fixed worker bounds, one-deadline orchestration, observations, and typed sweep/candidate failures.
- `src/lifx/network/mdns/transport.py` - Adds a private detail-logging switch whose default preserves standalone diagnostics and whose merged path suppresses sensitive detail.
- `tests/test_devices/test_state_light.py` - Proves pre-state snapshots, subclass-state preservation, timestamp handling, and post-seed network freshness.
- `tests/test_network/test_mdns/test_liveness.py` - Proves classifier paths, response correlation, cap/deadline semantics, observations, privacy, compatibility, and deterministic cleanup.
- `.planning/phases/13-merged-discovery/deferred-items.md` - Records the pre-existing coordinator-test finalisation hang with its exact root cause and remediation.

## Decisions Made

- Current product support is exactly Light subclasses or `LifxUnsupportedDeviceError`: supported candidates use GetColor, unsupported candidates drop locally, and StateUnhandled never falls back to Echo.
- The exact 64-byte Echo path remains future-proofing only and is tested by injecting a synthetic non-Light classifier result rather than claiming shipping coverage.
- The sixteen-probe limit is a deterministic, patchable, reasoned safety bound. No empirical performance claim is attached to it.
- One deadline starts before mDNS record consumption and is passed through queueing and `DeviceConnection`, which preserves caller timeout/retry policy without inventing a Phase 13 retry schedule.
- Merged failure diagnostics carry only stage, stable reason, and exception class name. Raw identities, firmware text, destinations, payloads, and exception messages remain below the boundary.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reconciled generated StateColor label typing with the decoded request boundary**

- **Found during:** Task 1 Pyright verification
- **Issue:** Generated packet annotations describe `StateColor.label` as bytes, while the request decoding boundary supplies the user-visible string required by the device contract.
- **Fix:** Added an explicit `cast(str, state.label)` at the private adoption seam without broadening generated protocol types or exposing bytes.
- **Files modified:** `src/lifx/devices/light.py`
- **Verification:** Focused state tests and strict Pyright pass.
- **Committed in:** `075f1ef`

**2. [Rule 1 - Bug] Restored the context-manager transport seam used by existing mDNS tests**

- **Found during:** Task 2 adjacent-suite verification
- **Issue:** An early implementation opened the concrete transport directly, bypassing the established async-context-manager fake yielded by adjacent discovery tests.
- **Fix:** Retained explicit `__aenter__`/`__aexit__` ownership and refined the new fake to model real open-failure cleanup.
- **Files modified:** `src/lifx/network/mdns/discovery.py`, `tests/test_network/test_mdns/test_liveness.py`
- **Verification:** The full adjacent mDNS/network selection reports 452 passed.
- **Committed in:** `536a213`

**3. [Rule 1 - Bug] Reconciled stale closeout state and roadmap formatting**

- **Found during:** Plan metadata closeout
- **Issue:** The state handlers advanced to Plan 4 but retained Plan 13-02 activity prose, and the roadmap updater emitted a malformed status-table cell.
- **Fix:** Updated the current activity description, corrected the realised duration, and restored roadmap table spacing without changing handler-owned counts.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** State names Plan 4 of 7 as ready, the roadmap shows 3/7 in progress, and `git diff --check` passes.
- **Committed in:** Plan metadata commit

**4. [Rule 1 - Bug] Restored the mandatory DCO trailer on the metadata commit**

- **Found during:** Final commit verification
- **Issue:** The GSD commit helper produced a correctly GPG-signed metadata commit but omitted the repository-required `Signed-off-by` trailer.
- **Fix:** Amended the same unpushed metadata commit with `git commit --amend -S -s --no-edit`.
- **Files modified:** None beyond the existing metadata commit contents
- **Verification:** The final commit reports the mandated signing key and contains the DCO trailer.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 4 auto-fixed (4 Rule 1 bugs)
**Impact on plan:** The fixes preserve existing type and test seams and keep the planning closeout internally consistent without broadening runtime scope.

## Issues Encountered

### Pre-existing coordinator-test finalisation hang

The repository suite completes every assertion with 4,232 passed, 1 skipped, and 12 deselected, but the pytest process cannot exit normally. A bounded focused reproduction shows `test_non_last_detach_preserves_producer_and_last_detach_reaps_it` reports `1 passed in 0.02s` and then waits indefinitely in `concurrent.futures.thread._python_exit`.

The defect predates this plan: it was introduced in `fc9737d4` and is present unchanged at the Plan 13-03 starting commit `1c5eb1c`. The test cancels a producer awaiting `asyncio.to_thread(producer.release.wait)` without setting the event, so the async task closes but the executor worker cannot be cancelled. The actionable repair is recorded in `deferred-items.md` and as open broken-window entry 31; executor scope rules prohibit modifying this Plan 13-02 test in Plan 13-03.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 13-04 can merge the verified mDNS leg with shared UDP enumeration. It can consume bounded typed failures, same-call raw observations, and devices whose direct-response state has already been adopted. The pre-existing coordinator test teardown defect remains visible for repair before ship.

## Verification

- Task 1 contract: 50 passed.
- Task 2 planned selection: 51 passed.
- Adjacent mDNS/network compatibility selection: 452 passed.
- Repository assertions: 4,232 passed, 1 skipped, 12 deselected; pytest process-exit defect recorded separately above.
- Repository Ruff: passed.
- Repository Pyright: 0 errors, 0 warnings.

## Self-Check: PASSED

All seven implementation, test, summary, and deferred-ledger files and all four TDD task commits were verified before state advancement.

---
*Phase: 13-merged-discovery*
*Completed: 2026-08-31*
