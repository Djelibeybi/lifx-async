---
phase: 13-merged-discovery
plan: 04
subsystem: discovery
tags: [asyncio, udp, mdns, deduplication, cancellation, privacy]

requires:
  - phase: 13-merged-discovery
    provides: process-wide shared UDP discovery coordination from Plan 13-02
  - phase: 13-merged-discovery
    provides: verified mDNS devices and bounded typed failure events from Plan 13-03
provides:
  - one default discovery stream that concurrently consumes UDP and verified mDNS
  - first-valid serial deduplication with winner and duplicate observations
  - expected mDNS failure isolation with one privacy-bounded diagnostic
  - cancellation-resistant ownership and cleanup for both source generators
affects: [13-05-measurement, 13-06-documentation, discover, find_by_serial]

actuals:
  tokens: 10447
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - one caller-origin monotonic deadline shared by both discovery legs
    - unbounded internal event queue with bounded source producers and first-valid serial winners
    - typed expected-failure events separated from unexpected exception propagation
    - shielded source cleanup that survives repeated caller cancellation

key-files:
  created: []
  modified:
    - src/lifx/api.py
    - src/lifx/network/discovery.py
    - src/lifx/network/discovery_observation.py
    - src/lifx/network/mdns/discovery.py
    - tests/conftest.py
    - tests/test_api/test_api_discovery.py

key-decisions:
  - "Start one deadline in discover() and pass it into both private source seams so neither leg receives a fresh timeout window."
  - "Normalise every candidate through Serial and let the first valid source event win; later occurrences emit duplicate observations without yielding."
  - "Prefer the typed mDNS failure sink over an outer fallback event so one absorbed failure produces exactly one diagnostic."
  - "Shield the aggregate source cleanup task and re-raise repeated cancellation only after both generators have finalised."

patterns-established:
  - "Merge boundary: source pumps publish devices, observations, completion, and failures; only discover() selects winners and yields public devices."
  - "Failure boundary: expected mDNS availability failures degrade to UDP, while cancellation and unexpected errors propagate after cleanup."
  - "Privacy boundary: merged diagnostics include only stable source, stage, reason, and exception type fields."

requirements-completed: [FIND-01, FIND-03, FIND-04, FIND-09, FIND-10]

coverage:
  - id: D1
    description: "Default discovery streams first-valid unique devices from concurrent UDP and verified mDNS legs under one caller deadline."
    requirement: FIND-01
    verification:
      - kind: integration
        ref: "tests/test_api/test_api_discovery.py#merged ordering, deduplication, deadline, and freshness tests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Expected mDNS sweep and candidate failures degrade once without suppressing productive UDP or verified partial results."
    requirement: FIND-09
    verification:
      - kind: integration
        ref: "tests/test_api/test_api_discovery.py#transport, partial-record, and candidate failure tests"
        status: pass
    human_judgment: false
  - id: D3
    description: "Cancellation and unexpected failures finalise both source generators and propagate without leaked discovery resources."
    requirement: FIND-10
    verification:
      - kind: integration
        ref: "tests/test_api/test_api_discovery.py#repeated cancellation and unexpected failure tests"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-31
status: complete
---

# Phase 13 Plan 04: Merged Default Discovery Summary

**Concurrent UDP and verified mDNS discovery with first-valid serial winners, bounded degradation, and cancellation-safe cleanup**

## Performance

- **Duration:** 20 min
- **Started:** 2026-08-30T16:13:09Z
- **Completed:** 2026-08-30T16:33:07Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Changed the public default `discover()` path to consume shared UDP and verified mDNS concurrently while preserving the explicit UDP-only and mDNS-only APIs.
- Enforced one caller-origin deadline and first-valid serial deduplication across both legs, including deterministic accepted, winner, and duplicate observations.
- Isolated expected mDNS sweep and candidate failures so productive UDP and already verified mDNS devices remain available with exactly one bounded diagnostic per failure.
- Made owned cleanup resilient to repeated cancellation and proved fresh-call construction across 73 sequential invocations.
- Exercised the real mDNS transport, record-cache, verification, and correlated StateColor seams rather than limiting failure coverage to top-level mocks.

## Task Commits

Each task was committed atomically with separate RED and GREEN gates:

1. **Task 1 RED: Define the merged default stream contract** - `4568474` (test)
2. **Task 1 GREEN: Merge UDP and verified mDNS streams** - `292ae33` (feat)
3. **Task 2 RED: Define the merged failure isolation contract** - `aac6497` (test)
4. **Task 2 GREEN: Isolate expected mDNS failures** - `687edee` (fix)

## Files Created/Modified

- `src/lifx/api.py` - Adds source pumps, merged event handling, first-valid serial selection, expected-failure degradation, and cancellation-resistant cleanup.
- `src/lifx/network/discovery.py` - Accepts the caller deadline and observation sink through the private shared-UDP seam.
- `src/lifx/network/discovery_observation.py` - Extends the internal observation stage vocabulary for accepted, winner, and duplicate merge dispositions.
- `src/lifx/network/mdns/discovery.py` - Accepts the caller deadline through the private verified-mDNS seam.
- `tests/conftest.py` - Keeps legacy public discovery tests deterministic with a private empty-mDNS fixture while allowing merged tests to opt into the real source.
- `tests/test_api/test_api_discovery.py` - Covers ordering, deduplication, observations, deadlines, freshness, degradation, privacy, partial results, unexpected failures, and cleanup.

## Decisions Made

- The default API owns one unbounded event queue because both source producers are already bounded and blocking either producer could conceal the earliest valid result.
- Serial validation and canonicalisation occur at the merge boundary before a device becomes eligible to win or affect deduplication state.
- A typed failure emitted by the verified mDNS sink suppresses the outer exception fallback, avoiding duplicate logs while retaining a defensive fallback for custom sources.
- Cleanup uses a separately owned aggregate task and `asyncio.shield()` so repeated cancellation cannot interrupt generator finalisation; the first repeated cancellation is re-raised after cleanup.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Propagated merge observations and the exact caller deadline through source-private seams**

- **Found during:** Task 1 implementation
- **Issue:** The plan's primary file list did not include the internal observation type or verified-mDNS entry seam, but winner/duplicate dispositions and one true caller deadline could not be implemented correctly without updating them.
- **Fix:** Extended the private observation stage literal and added private deadline/sink parameters while preserving every public source-specific signature.
- **Files modified:** `src/lifx/network/discovery_observation.py`, `src/lifx/network/mdns/discovery.py`, `src/lifx/network/discovery.py`
- **Verification:** Public signature assertions, merged deadline tests, focused discovery tests, full Pyright, and the repository regression suite pass.
- **Committed in:** `292ae33`

**2. [Rule 1 - Bug] Reconciled stale closeout prose and roadmap formatting**

- **Found during:** Plan metadata closeout
- **Issue:** The state handlers advanced to Plan 5 but retained Plan 13-03 activity prose, recorded the realised duration without standard spacing, and emitted a malformed roadmap status cell.
- **Fix:** Updated the current activity description, normalised the duration display, and restored roadmap table spacing without altering handler-owned counts.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** State names Plan 5 of 7 as ready, the roadmap shows 4/7 in progress, and `git diff --check` passes.
- **Committed in:** Plan metadata commit

**3. [Rule 1 - Bug] Restored the mandatory DCO trailer on the metadata commit**

- **Found during:** Final commit verification
- **Issue:** The GSD commit helper created a correctly GPG-signed metadata commit but omitted the repository-required `Signed-off-by` trailer.
- **Fix:** Amended the same unpushed metadata commit with `git commit --amend -S -s --no-edit` after adding this record.
- **Files modified:** None beyond the existing metadata commit contents
- **Verification:** The final commit reports the mandated signing key and contains the DCO trailer.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 2 missing critical functionality)
**Impact on plan:** The additional private-seam edits are required to satisfy the stated one-deadline and observation contracts without changing public source-specific APIs; the metadata correction keeps closeout state internally consistent.

## Issues Encountered

None.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 13-05 can measure merged discovery latency and duplicate behaviour against the completed one-deadline, first-valid runtime contract. Plan 13-06 can document the default merged API while retaining `discover_udp()` and `discover_mdns()` as explicit diagnostic and compatibility paths.

## Automated Gates

- Task 1 planned selection: 49 passed, 6 deselected.
- Task 2 failure-isolation selection: 12 passed.
- Complete Plan 13-04 discovery selection: 67 passed.
- Adjacent coordinator and liveness suites: 47 passed, 1 skipped.
- Repository suite: 4,251 passed, 1 skipped, 12 deselected.
- Repository Ruff formatting and lint: passed.
- Repository Pyright: 0 errors, 0 warnings.

## Self-Check: PASSED

All six implementation and test files and all four signed, DCO-compliant task commits were verified before state advancement.

---
*Phase: 13-merged-discovery*
*Completed: 2026-08-31*
