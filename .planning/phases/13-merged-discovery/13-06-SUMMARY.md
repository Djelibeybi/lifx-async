---
phase: 13-merged-discovery
plan: 06
subsystem: discovery-evidence
tags: [emulator, exact-head, codecov, jsonl, privacy]

requires:
  - phase: 13-merged-discovery
    provides: merged UDP and mDNS discovery implementation through Plan 13-05
provides:
  - exact-head ordinary PR CI and 100.00% Codecov patch verification
  - one locally executed hermetic paired emulator measurement stamped with the verified revision
  - append-only canonical evidence with its original 705-byte prefix preserved
  - validated private fleet-readiness handoff for Plan 13-07
affects: [13-07-fleet-evidence, merged-discovery-verification]

actuals:
  tokens: 3642
  tasks: 3
  commits: 1

tech-stack:
  added: []
  patterns:
    - ordinary exact-head PR CI and Codecov prove the implementation revision
    - executor-run hermetic measurements are stamped with the already verified immutable revision
    - append-only evidence preserves the byte-identical historical prefix

key-files:
  created:
    - .planning/phases/13-merged-discovery/13-06-SUMMARY.md
    - .planning/phases/13-merged-discovery/13-MEASUREMENT-SUMMARY.md
  modified:
    - .planning/phases/13-merged-discovery/13-06-PLAN.md
    - .planning/phases/13-merged-discovery/13-MEASUREMENTS.jsonl

key-decisions:
  - "Keep all Phase 13-only measurement machinery out of the permanent CI workflow."
  - "Use ordinary exact-head PR CI plus the 100.00% Codecov patch gate as the remote revision proof."
  - "Run the hermetic emulator pair locally only after those gates pass and identify it explicitly as executor-produced evidence."

patterns-established:
  - "Evidence provenance: exact-head CI qualification and local hermetic collection are distinct claims."
  - "Privacy boundary: validate the private readiness handoff without copying its path, contents, mapping, or live identifiers into tracked evidence."

requirements-completed: [FIND-01, FIND-02, FIND-03, FIND-04, FIND-05, FIND-07, FIND-08, FIND-09, FIND-10]

coverage:
  - id: D1
    description: "The immutable implementation revision passed ordinary pull-request CI and the 100.00% Codecov patch gate without Phase 13-only workflow steps."
    requirement: FIND-07
    verification:
      - kind: e2e
        ref: "PR 220 exact head 1abe9902b4a20f290d33af6189eb2c1c66dab5e4"
        status: pass
    human_judgment: false
  - id: D2
    description: "One hermetic emulator pair records a direct-UDP baseline and merged dual-source result at the exact verified revision."
    requirement: FIND-07
    verification:
      - kind: integration
        ref: "scripts/measure_merged_discovery.py --validate-only --expected-revision 1abe9902b4a20f290d33af6189eb2c1c66dab5e4"
        status: pass
      - kind: integration
        ref: "tests/test_scripts/test_measure_merged_discovery.py (38 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The ignored mode-0600 fleet-readiness handoff is structurally valid and its external alias mapping is readable without exposing private values."
    requirement: FIND-08
    verification:
      - kind: manual_procedural
        ref: "local privacy-safe readiness validation"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-08-31
status: complete
---

# Phase 13 Plan 06: Exact-Head Emulator Evidence Summary

**Ordinary exact-head PR CI and 100.00% patch coverage qualify a locally executed hermetic UDP/mDNS emulator pair without permanent Phase 13 CI machinery**

## Performance

- **Duration:** 15 min
- **Started:** 2026-08-30T21:23:00Z
- **Completed:** 2026-08-30T21:38:48Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Verified that PR 220's immutable implementation revision passed ordinary CI and reported `100.00% of diff hit (target 100.00%)` from Codecov.
- Appended one schema-valid local emulator pair stamped with that revision: the baseline follows `direct_udp` with UDP-only contribution, while the merged arm follows `merged_dual` with both UDP and mDNS contribution.
- Proved the canonical JSONL retained its byte-identical 705-byte historical prefix and regenerated the deterministic human-readable summary.
- Validated the private ignored mode-0600 fleet handoff, its categorical readiness state, and its readable external mapping without exposing private data or collecting from physical devices.

## Task Commits

1. **Exact-head implementation and coverage boundary** - `1abe990` (refactor)
2. **Plan amendment, local evidence pair, and closeout** - this signed, DCO-bearing metadata commit (docs)

## Files Created/Modified

- `.planning/phases/13-merged-discovery/13-06-PLAN.md` - Records the operator-approved evidence-path amendment that supersedes CI-produced Phase 13 artefacts.
- `.planning/phases/13-merged-discovery/13-MEASUREMENTS.jsonl` - Appends exactly one locally executed two-row emulator pair after the unchanged historical prefix.
- `.planning/phases/13-merged-discovery/13-MEASUREMENT-SUMMARY.md` - Deterministic rendering of all validated canonical rows.
- `.planning/phases/13-merged-discovery/13-06-SUMMARY.md` - Records provenance, validation, privacy, and next-plan readiness.

## Decisions Made

- Phase-specific measurement steps remain removed from `.github/workflows/ci.yml`; ordinary CI remains the permanent project contract.
- The successful ordinary PR workflow and exact 100.00% patch result qualify revision `1abe9902b4a20f290d33af6189eb2c1c66dab5e4` before local collection.
- The paired emulator rows are executor-produced local evidence stamped with that qualified revision. They are not described as CI-generated or artefact-downloaded.
- Physical fleet collection is intentionally untouched until Plan 13-07.

## Deviations from Plan

### Operator-Approved Evidence Path Amendment

- **Original plan:** Add a Phase 13-only nested checkout, measurement step, and uploaded CI artefact, then download its rows.
- **Decision:** Remove all Phase 13-specific work from the CI workflow.
- **Adaptation:** Verify ordinary exact-head CI and Codecov remotely, then execute and validate the hermetic pair locally at that immutable revision.
- **Impact:** Evidence provenance changes, but hermeticity, exact-revision stamping, append-only integrity, and the physical-fleet privacy boundary remain intact.

## Issues Encountered

- The sandboxed `uv` cache and GPG trust database were not writable. Validation used a task-specific temporary `uv` cache, and signature verification used the operator's normal keyring. No repository configuration changed.

## Known Stubs

None.

## User Setup Required

None - the previously prepared private readiness handoff is valid and available to the next executor.

## Next Phase Readiness

Plan 13-07 can collect the representative physical-fleet rounds from the validated private handoff. No physical discovery was run in this plan, and no private path, mapping content, or live identifier entered tracked evidence.

## Automated Gates

- Exact PR head: ordinary CI successful.
- Codecov patch: `100.00% of diff hit (target 100.00%)`.
- Measurement harness tests: 38 passed.
- Canonical validator: exact-revision two-row pair accepted.
- Historical evidence integrity: original 705-byte prefix retained SHA-256 `c41c20d8aa266dab877fa137b0f4812bd9b534f2ba974209d5eeaa21127c7f98`.
- Exact-head commit: required GPG fingerprint and DCO trailer verified.
- Private handoff: ignored, mode 0600, structurally valid, and external mapping readable.

## Self-Check: PASSED

All four planning evidence files exist, the immutable implementation commit exists and verifies, the historical JSONL prefix is byte-identical, the new exact-revision pair validates, and the private handoff remained ignored and untracked.

---
*Phase: 13-merged-discovery*
*Completed: 2026-08-31*
