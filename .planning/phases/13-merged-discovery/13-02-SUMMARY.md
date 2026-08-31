---
phase: 13-merged-discovery
plan: 02
subsystem: discovery
tags: [asyncio, udp, single-flight, threading, replay, deadlines]

requires:
  - phase: 13-merged-discovery
    provides: UDP-only public entry point, explicit caller observation sinks, and immutable pre-merge invariants from Plan 13-01
provides:
  - process-wide active-only single-flight coordination for compatible UDP discovery sweeps
  - ordered raw accepted-response replay with caller-loop fan-out and explicit observation transfer
  - caller-origin deadline enforcement with subscriber-specific device settings
  - deterministic cancellation, interpreter-exit, and post-fork lifecycle handling
affects: [13-03-merged-discovery, discover, discover_udp, discovery-measurements]

actuals:
  tokens: 11488
  tasks: 2
  commits: 7

tech-stack:
  added: []
  patterns:
    - lazy process-wide worker thread owning one manually managed asyncio loop
    - active-only single-flight registry keyed exclusively by wire and timing compatibility
    - append-before-fan-out raw replay with caller-loop thread-safe delivery

key-files:
  created:
    - src/lifx/network/discovery_coordinator.py
  modified:
    - src/lifx/network/discovery.py
    - src/lifx/api.py
    - tests/test_network/test_discovery_coordinator.py
    - tests/test_api/test_api_discovery.py

key-decisions:
  - "Store and replay only accepted DiscoveryResponse records; construct DiscoveredDevice values after fan-out with each subscriber's timeout and retry settings."
  - "Keep the coordinator process-wide across caller loops, but retain completed outcomes nowhere so every later non-overlapping call starts fresh."
  - "Carry the caller-owned observation sink and wall deadline explicitly on every subscription rather than depending on ambient ContextVar state in the worker thread."
  - "Route discover() and discover_udp() through shared enumeration while leaving find_by_ip() and lower-level discover_devices() on their direct targeted paths."

patterns-established:
  - "Single-flight boundary: compatibility is exactly broadcast address, port, timeout, maximum response time, and idle multiplier; device construction settings never split a sweep."
  - "Cross-thread delivery boundary: schedule observation plus record as one ordered caller-loop turn, with deadline checks before delivery and before and after construction."
  - "Lifecycle boundary: non-last detach removes only the subscriber; last detach waits for producer generator and transport closure before acknowledging."

requirements-completed: [FIND-02, FIND-09, FIND-10]

coverage:
  - id: D1
    description: "Compatible overlapping UDP enumeration callers share one process-wide validated producer with ordered prefix and suffix delivery."
    requirement: FIND-10
    verification:
      - kind: integration
        ref: "tests/test_network/test_discovery_coordinator.py#compatible, cross-loop, replay, and active-only tests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Public discover() and discover_udp() use shared raw fan-out while preserving caller settings, deadlines, observations, and direct find_by_ip() semantics."
    requirement: FIND-02
    verification:
      - kind: integration
        ref: "uv run --frozen pytest -o addopts='' tests/test_network/test_discovery_coordinator.py tests/test_api/test_api_discovery.py tests/test_network/test_discovery_rebroadcast.py tests/test_network/test_discovery_errors.py -q"
        status: pass
    human_judgment: false
  - id: D3
    description: "Normal, abandoned, interpreter-exit, and post-fork cleanup retain no completed discovery state or worker ownership."
    requirement: FIND-09
    verification:
      - kind: integration
        ref: "tests/test_network/test_discovery_coordinator.py#detach, subprocess exit, and guarded Linux fork tests"
        status: pass
    human_judgment: false

duration: 23min
completed: 2026-08-31
status: complete
---

# Phase 13 Plan 02: Shared UDP Discovery Coordinator Summary

**Process-wide active UDP single-flight with ordered raw replay, subscriber-owned deadlines and observations, and deterministic cross-loop lifecycle cleanup**

## Performance

- **Duration:** 23 min
- **Started:** 2026-08-30T15:03:47Z
- **Completed:** 2026-08-30T15:26:55Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added a lazy process-wide coordinator that shares one compatible validated UDP producer across caller loops and OS threads without backpressuring the wire schedule.
- Preserved ordered prefix replay and suffix delivery while constructing subscriber-specific devices only after fan-out and enforcing each caller's original wall deadline.
- Transferred caller-owned discovery observations explicitly across the worker boundary and proved concurrent sinks remain isolated.
- Added bounded last-subscriber, abandoned-generator, interpreter-exit, and post-fork cleanup with no completed-result cache.
- Kept `find_by_ip()` and direct `discover_devices()` outside the named public sharing boundary while routing `discover()` and `discover_udp()` through `discover_devices_shared()`.

## Task Commits

Each task was committed atomically, with separate RED and GREEN gates:

1. **Task 1 RED: Define the process-wide coordinator contract** - `4387d82` (test)
2. **Task 1 GREEN: Implement active UDP sweep coordination** - `fc9737d` (feat)
3. **Task 2 RED: Require shared public enumeration** - `1dfe0de` (test)
4. **Task 2 GREEN: Integrate the shared UDP facade** - `faa1efc` (feat)
5. **Deterministic test refinement: Replace scheduling nudge with explicit replay receipt** - `1dee4a0` (test)
6. **Post-wave correction: Make the cross-loop test gate cancellation-safe** - `fix: resolve post-merge conflicts from wave 2` (fix)

## Files Created/Modified

- `src/lifx/network/discovery_coordinator.py` - Owns the lazy worker loop, active registry, raw replay, caller-loop fan-out, deadline checks, and bounded lifecycle hooks.
- `src/lifx/network/discovery.py` - Adds `discover_devices_shared()` and applies caller-specific construction only after raw coordination.
- `src/lifx/api.py` - Routes public UDP enumeration through the shared facade and documents producer-origin versus caller-origin deadlines.
- `tests/test_network/test_discovery_coordinator.py` - Proves compatibility, cross-loop sharing, ordered replay, observation isolation, deadlines, active-only state, cancellation, exit, and fork behaviour.
- `tests/test_api/test_api_discovery.py` - Pins the shared public delegate while retaining direct targeted lookup coverage.

## Decisions Made

- The coordinator retains accepted raw responses only for the lifetime of an active sweep. It never stores caller-specific `DiscoveredDevice` instances or terminal outcomes.
- One manually managed asyncio loop in a lazy worker thread preserves the locked process-wide sharing guarantee across independent caller loops.
- Subscription registration schedules the complete accepted prefix before admitting future suffix fan-out, which makes replay order deterministic without producer backpressure.
- Caller observations and wall deadlines are explicit subscription fields. The worker never consults caller `ContextVar` state.
- Public enumeration shares only UDP. Targeted `find_by_ip()` continues to own a direct producer so Phase 12 address and endpoint semantics remain unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed concurrent coordinator startup readiness race**

- **Found during:** Task 1 cross-loop verification
- **Issue:** A second caller arriving after thread creation but before loop publication could mistake a healthy starting worker for a stopping worker and attempt to join it.
- **Fix:** Added an explicit shared readiness wait for concurrent starters; only a worker already marked as stopping is joined before restart.
- **Files modified:** `src/lifx/network/discovery_coordinator.py`, `tests/test_network/test_discovery_coordinator.py`
- **Verification:** The deterministic two-thread/two-loop sharing test passes repeatedly and produces one producer invocation.
- **Committed in:** `fc9737d`

**2. [Rule 1 - Bug] Coalesced idle-stop requests and tolerated concurrent loop closure**

- **Found during:** Task 1 lifecycle verification
- **Issue:** Multiple idle-stop tasks could stop the loop again during async-generator shutdown, while teardown could race a loop that had already begun closing.
- **Fix:** Retained at most one idle-stop task and made bounded shutdown join an already-stopping worker without submitting work to its closing loop.
- **Files modified:** `src/lifx/network/discovery_coordinator.py`, `tests/test_network/test_discovery_coordinator.py`
- **Verification:** The coordinator suite passes without thread-exception or unawaited-coroutine warnings.
- **Committed in:** `fc9737d`

**3. [Rule 1 - Bug] Replaced registration timing assumptions in late-subscriber tests**

- **Found during:** Task 1 and final deterministic test review
- **Issue:** Early test drafts released the producer before proving that the late subscriber had registered, allowing a legitimately completed sweep to start fresh and relying on a scheduling nudge.
- **Fix:** Made tests await receipt of the replayed prefix before releasing the suffix gate.
- **Files modified:** `tests/test_network/test_discovery_coordinator.py`
- **Verification:** The focused coordinator suite reports 14 passed and 1 platform-guarded skip with no sleep-based test synchronisation.
- **Committed in:** `1dee4a0`

**4. [Rule 1 - Bug] Reconciled stale and malformed closeout state**

- **Found during:** Plan metadata closeout
- **Issue:** The state handlers advanced Plan 13-02 but retained Plan 13-01 activity prose, duplicated the phase label in added decisions, and emitted a malformed roadmap status cell.
- **Fix:** Updated the activity text, removed redundant decision prefixes, and restored roadmap table spacing without changing handler-owned plan or requirement counts.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** State names Plan 3 of 7 as ready, the roadmap shows 2/7 in progress, and `git diff --check` passes.
- **Committed in:** Plan metadata commit

**5. [Rule 1 - Bug] Restored the mandatory DCO trailer on the metadata commit**

- **Found during:** Final commit verification
- **Issue:** The GSD commit helper produced a correctly GPG-signed metadata commit but omitted the repository-required `Signed-off-by` trailer.
- **Fix:** Amended the same metadata commit with `git commit --amend -S -s --no-edit` before final verification.
- **Files modified:** None beyond the existing metadata commit contents
- **Verification:** `git show --show-signature --format=fuller --no-patch HEAD` reports a good signature from the mandated key and the commit body contains the DCO trailer.
- **Committed in:** Plan metadata commit

**6. [Rule 1 - Bug] Removed a blocked executor worker from the coordinator test gate**

- **Found during:** Post-wave full-suite process-exit verification
- **Issue:** `_GatedDiscoveryProducer` awaited `threading.Event.wait` through the default executor. Cancelling the final subscriber closed the async generator but could not stop that worker, so pytest reported passing assertions and then hung in `threading._shutdown`.
- **Fix:** Replaced the executor wait with cancellation-safe asynchronous polling of the same cross-thread event and asserted that final detach closes the producer while the release gate remains unset.
- **Files modified:** `tests/test_network/test_discovery_coordinator.py`
- **Verification:** The bounded reproducer exits with 1 passed, the Wave 2 selection exits with 186 passed and 1 skipped, and the repository suite exits with 4,232 passed, 1 skipped, and 12 deselected.
- **Committed in:** `fix: resolve post-merge conflicts from wave 2`

---

**Total deviations:** 6 auto-fixed (6 Rule 1 bugs)
**Impact on plan:** All fixes strengthened the specified cross-loop and deterministic-lifecycle contracts without broadening scope.

## Issues Encountered

The post-wave gate found and resolved the test-only blocked executor worker documented above.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 13-03 can merge the invocation-local mDNS leg onto a proven process-wide UDP subscription. Shared UDP state is active-only, caller settings and observations remain isolated, and the entry-gate discovery invariants remain green.

## Verification

- Focused Task 2 selection: 103 passed, 1 platform-guarded skip.
- Coordinator selection after deterministic refinement: 14 passed, 1 platform-guarded skip.
- Post-wave focused process-exit reproducer: 1 passed and normal exit.
- Affected Wave 2 selection: 186 passed, 1 skipped, and normal exit.
- Repository suite after post-wave correction: 4,232 passed, 1 skipped, 12 deselected, and normal exit.
- Repository Ruff: passed.
- Repository Pyright: 0 errors, 0 warnings.

## Self-Check: PASSED

All five implementation/test files, the summary artefact, and all six task, TDD, and corrective commits were verified across initial execution and the post-wave repair.

---
*Phase: 13-merged-discovery*
*Completed: 2026-08-31*
