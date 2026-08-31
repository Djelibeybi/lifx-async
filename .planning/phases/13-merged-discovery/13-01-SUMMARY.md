---
phase: 13-merged-discovery
plan: 01
subsystem: discovery
tags: [asyncio, udp, mdns, emulator, jsonl, privacy]

requires:
  - phase: 11-mdns-discovery-hardening
    provides: bounded direct-response mDNS discovery and private service-record model
  - phase: 12-ipv6-thread-support
    provides: normalised serial identity and validated UDP discovery boundaries
provides:
  - public UDP-only discover_udp() preserving the pre-merge discovery contract
  - explicit caller-owned private discovery observation sink
  - append-only direct-versus-merged measurement harness with hermetic emulator ownership
  - immutable privacy-safe pre-merge entry-gate evidence
affects: [13-02-shared-discovery, merged-discovery, discovery-measurements]

actuals:
  tokens: 18944
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - caller-selected observation sinks passed explicitly across producer boundaries
    - context-local private mDNS source injection with owned async-generator closure
    - validate-before-append privacy-safe JSONL evidence

key-files:
  created:
    - src/lifx/network/discovery_observation.py
    - scripts/measure_merged_discovery.py
    - tests/test_scripts/test_measure_merged_discovery.py
    - .planning/phases/13-merged-discovery/13-MEASUREMENTS.jsonl
    - .planning/phases/13-merged-discovery/13-ENTRY-GATE.md
  modified:
    - src/lifx/api.py
    - src/lifx/__init__.py
    - src/lifx/network/discovery.py
    - src/lifx/network/mdns/discovery.py
    - tests/test_api/test_api_discovery.py

key-decisions:
  - "Keep discover() as a thin UDP-only delegate until the shared coordinator lands, while exposing the identical behaviour as discover_udp()."
  - "Select observations in the caller context once, then pass the sink explicitly to producers rather than relying on ContextVar propagation."
  - "Measure the baseline through direct discover_devices() so later paired evidence includes coordinator overhead instead of hiding it."
  - "Keep emulator mDNS injection private, context-local, and generator-owned so evidence collection cannot open an ambient multicast socket."

patterns-established:
  - "Observation boundary: emit accepted source evidence only after validation and first-wins deduplication, immediately before delivery."
  - "Evidence boundary: raw identities remain transient; only aliases, categorical provenance, counts, and timings cross into tracked files."

requirements-completed: [FIND-02, FIND-07, FIND-08, FIND-09]

coverage:
  - id: D1
    description: "Public UDP-only discovery entry point with the complete pre-merge behavioural invariant suite."
    requirement: FIND-02
    verification:
      - kind: integration
        ref: "uv run --frozen pytest -o addopts='' tests/test_api/test_api_discovery.py tests/test_network/test_discovery_rebroadcast.py tests/test_network/test_discovery_errors.py -q"
        status: pass
    human_judgment: false
  - id: D2
    description: "Append-only paired measurement harness with direct baseline provenance, source ordering, FIND-08 evidence, privacy validation, and owned emulator lifecycle."
    requirement: FIND-07
    verification:
      - kind: integration
        ref: "tests/test_scripts/test_measure_merged_discovery.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Immutable pre-merge entry gate with one schema-valid privacy-safe emulator baseline row."
    requirement: FIND-09
    verification:
      - kind: other
        ref: "scripts/measure_merged_discovery.py --mode baseline-only --environment emulator --rounds 1"
        status: pass
    human_judgment: false

duration: 29min
completed: 2026-08-31
status: complete
---

# Phase 13 Plan 01: Merged Discovery Entry Gate Summary

**UDP-only public enumeration with explicit source observation, a hermetic paired-measurement harness, and immutable privacy-safe pre-merge evidence**

## Performance

- **Duration:** 29 min
- **Started:** 2026-08-30T14:27:51Z
- **Completed:** 2026-08-30T14:56:59Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Added `discover_udp()` with the exact existing discovery signature and kept `discover()` broadcast-only for the entry gate.
- Established explicit, caller-owned accepted-source observations and a context-local hermetic mDNS record source without changing public signatures.
- Built and exercised an append-only measurement harness that owns a dynamic-port emulator, preserves direct baseline provenance, validates privacy before writes, and records source winner order and FIND-08 identity evidence.
- Committed a single baseline emulator row and an exact pre-merge gate record after 117 focused tests passed.

## Task Commits

Each task was committed atomically, with TDD tasks retaining separate RED and GREEN gates:

1. **Task 1 RED: Pin broadcast-only public entry behaviour** - `96ef452` (test)
2. **Task 1 GREEN: Expose UDP-only enumeration and observations** - `691882f` (feat)
3. **Task 2 RED: Define the measurement harness contract** - `35a4ce6` (test)
4. **Task 2 GREEN: Build the paired measurement harness** - `c484a02` (feat)
5. **Task 3: Record the passing pre-merge entry gate** - `5effbc2` (docs)

## Files Created/Modified

- `src/lifx/api.py` - Exposes `discover_udp()` and retains pre-merge `discover()` delegation.
- `src/lifx/__init__.py` - Publishes all three discovery enumerators.
- `src/lifx/network/discovery.py` - Captures and explicitly passes the caller observation sink to accepted UDP delivery.
- `src/lifx/network/discovery_observation.py` - Defines the private value-suppressed observation model and caller-owned scope.
- `src/lifx/network/mdns/discovery.py` - Adds the private context-local service-record override with deterministic generator closure.
- `scripts/measure_merged_discovery.py` - Implements direct, merged, and paired append-only measurements plus validation and deterministic summaries.
- `tests/test_api/test_api_discovery.py` - Pins public discovery ordering, timing, validation, isolation, and cleanup invariants.
- `tests/test_scripts/test_measure_merged_discovery.py` - Verifies schema, privacy, source order, mDNS injection, emulator ownership, and cleanup.
- `.planning/phases/13-merged-discovery/13-MEASUREMENTS.jsonl` - Stores the single validated baseline entry row.
- `.planning/phases/13-merged-discovery/13-ENTRY-GATE.md` - Records the exact revision, commands, outcomes, ownership proof, and tuning check.

## Decisions Made

- `discover()` remains UDP-only at this ancestry point so Plan 13-02 has a falsifiable before/after boundary.
- The measurement baseline calls direct `discover_devices()` permanently; later public sharing costs therefore remain visible in FIND-07 deltas.
- Context variables select private caller scopes only. Producer delivery receives the selected observation sink explicitly, which remains safe when later work crosses event-loop or thread boundaries.
- Emulator evidence injects one matching private mDNS record source and never constructs the ambient mDNS transport while that scope is active.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected mistaken public-default expectations in the initial RED test**

- **Found during:** Task 1 (broadcast-only public baseline tracer)
- **Issue:** The first RED draft asserted obsolete discovery defaults instead of the repository's established maximum-response, idle-window, and retry defaults.
- **Fix:** Bound the signature assertions to the current public constants before committing the RED gate; no production tuning value changed.
- **Files modified:** `tests/test_api/test_api_discovery.py`
- **Verification:** The focused public and lower-level discovery selection passed before and after implementation.
- **Committed in:** `96ef452`

**2. [Rule 1 - Bug] Reconciled stale closeout text and roadmap spacing emitted by state handlers**

- **Found during:** Plan metadata closeout
- **Issue:** The state handlers advanced Plan 13-01 but retained the begin-phase activity description, omitted the duration space, and emitted a malformed roadmap status cell.
- **Fix:** Aligned the activity text with the completed entry gate, normalised the metric display, and restored roadmap table spacing without changing handler-owned counts.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** State names Plan 2 of 7 as ready, the roadmap shows 1/7 in progress, and `git diff --check` passes.
- **Committed in:** Plan metadata commit

**3. [Rule 1 - Bug] Added the required DCO trailer omitted by the metadata helper**

- **Found during:** Final commit verification
- **Issue:** The GSD commit helper produced a cryptographically signed metadata commit but omitted the repository-mandated developer sign-off trailer.
- **Fix:** Amended the unpushed metadata commit with explicit GPG signing and `-s` sign-off after updating this summary and the resolved deviation ledger.
- **Files modified:** `.planning/phases/13-merged-discovery/13-01-SUMMARY.md`, `.planning/WINDOWS.md`
- **Verification:** The final commit message contains `Signed-off-by` and Git records the configured signing key.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs)
**Impact on plan:** The corrections made the entry test and closeout metadata describe the real repository state without scope expansion.

## Issues Encountered

None beyond the corrected RED-test expectation documented above.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 13-02 can now introduce shared discovery against a committed broadcast-only ancestor. The public invariants, explicit observation hand-off, direct measurement baseline, hermetic mDNS seam, and immutable entry evidence are ready for reuse. No blocker remains.

## Self-Check: PASSED

All created artefacts and all five task/TDD commits were verified before state advancement.

---
*Phase: 13-merged-discovery*
*Completed: 2026-08-31*
