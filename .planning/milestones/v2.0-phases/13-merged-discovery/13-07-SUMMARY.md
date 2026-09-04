---
phase: 13-merged-discovery
plan: 07
subsystem: discovery-evidence
tags: [fleet, privacy, measurement, coverage, mdns, udp]

requires:
  - phase: 13-merged-discovery
    provides: exact-head merged discovery implementation and hermetic emulator evidence
provides:
  - six current-production-revision representative physical-fleet pairs
  - deterministic timing, result-count, and source-contribution summary
  - unsupported-product filtering at the public discovery evidence boundary
  - complete local Phase 13 quality and patch-coverage evidence
affects: [phase-14-thread-validation, discovery, measurement]

actuals:
  tokens: 7000
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - public discovery results define the eligible measurement population
    - raw evidence remains append-only and derived summaries regenerate deterministically

key-files:
  created:
    - .planning/phases/13-merged-discovery/13-07-SUMMARY.md
    - .planning/phases/13-merged-discovery/13-SECURITY.md
  modified:
    - .planning/phases/13-merged-discovery/13-MEASUREMENTS.jsonl
    - .planning/phases/13-merged-discovery/13-MEASUREMENT-SUMMARY.md
    - scripts/measure_merged_discovery.py
    - tests/test_scripts/test_measure_merged_discovery.py

key-decisions:
  - "Treat only devices yielded by discover() as eligible measurement identities; unsupported Switch traffic remains below the public boundary."
  - "Record variable fleet baseline counts as advisory and preserve the operator-supplied non-quiesced confounds without a pass/fail threshold."
  - "Close FIND-08 with the named non-gating population gap because no eligible physical WiFi device remained after public product filtering."

patterns-established:
  - "Fleet evidence: raw accepted observations are intersected with yielded public-device aliases before source contribution or FIND-08 analysis."
  - "Derived reporting: pair deltas, source overlap, evidence qualification, and null timing remain exact JSONL-derived values."

requirements-completed: [FIND-01, FIND-02, FIND-03, FIND-04, FIND-05, FIND-07, FIND-08, FIND-09, FIND-10]

coverage:
  - id: D1
    description: "Six complete representative physical-fleet pairs retain exact timing, result, source, and confound observations without private identities."
    requirement: FIND-07
    verification:
      - kind: integration
        ref: "scripts/measure_merged_discovery.py --validate-only"
        status: pass
      - kind: integration
        ref: "tests/test_scripts/test_measure_merged_discovery.py (53 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Unsupported products are excluded through the same yielded-device boundary as discover(), leaving the named FIND-08 population gap."
    requirement: FIND-08
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_measure_merged_discovery.py#test_find08_ignores_raw_observations_not_yielded_by_discovery"
        status: pass
      - kind: integration
        ref: "canonical fleet JSONL validation"
        status: pass
    human_judgment: false
  - id: D3
    description: "The final Phase 13 source diff has complete changed-line and changed-branch coverage."
    requirement: FIND-02
    verification:
      - kind: e2e
        ref: "scripts/check_patch_coverage.py (1990 executable lines, 676 branches)"
        status: pass
      - kind: e2e
        ref: "complete frozen suite (4394 passed, 12 deselected)"
        status: pass
    human_judgment: false

duration: 4h56m
completed: 2026-08-31
status: complete
---

# Phase 13 Plan 07: Representative Fleet Evidence Summary

**Current-revision fleet evidence closes merged discovery while preserving confounds, filtering unsupported products, and retaining exact 100% patch coverage**

## Performance

- **Duration:** 4h 56m
- **Started:** 2026-08-31T07:45:47+10:00
- **Completed:** 2026-08-31T12:41:33+10:00
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Appended six complete sequential physical-fleet baseline and merged pairs for the final production revision without changing the prior 282,350-byte canonical evidence prefix; 36 fleet pairs are now retained in total.
- Regenerated a byte-identical summary containing exact pair deltas, source contribution and overlap, qualification metadata, and the named FIND-08 non-gating population gap.
- Made measurement eligibility follow the devices yielded by `discover()`, so unsupported Switch observations cannot enter aliases, source counts, or FIND-08 evidence.
- Passed the complete 4,401-test frozen suite, Ruff, Pyright, and 100% patch coverage across 1,990 executable lines and 676 branches.
- Closed the independent code-review and ASVS Level 1 security gates, including exact-revision evidence and explicit acceptance of the two low residual risks.

## Task Commits

1. **Planning and design:** `813d97b` preserves the complete Phase 13 contract and reviewed plans.
2. **Implementation and tests:** `39bad58` contains the merged discovery fix, security repair, deterministic coverage, tools, tests, and public documentation.
3. **Completion evidence:** the signed evidence commit containing this summary records the final measurements, review, security verdict, and verification.

## Files Created/Modified

- `.planning/phases/13-merged-discovery/13-MEASUREMENTS.jsonl` - Appends twelve alias-only representative fleet rows.
- `.planning/phases/13-merged-discovery/13-MEASUREMENT-SUMMARY.md` - Reports qualification, pair deltas, source counts, overlap, winner counts, and exact raw observations.
- `scripts/measure_merged_discovery.py` - Filters observations through yielded public devices and renders the complete deterministic report.
- `tests/test_scripts/test_measure_merged_discovery.py` - Proves unsupported-device exclusion, nullable timing, variance qualification, and deterministic rendering.
- `.planning/phases/13-merged-discovery/13-07-SUMMARY.md` - Records the final plan evidence and quality gates.
- `.planning/phases/13-merged-discovery/13-SECURITY.md` - Records the independent `SECURED` verdict and accepted-risk log.

## Decisions Made

- Unsupported product traffic may appear in lower-level discovery observations, but it is ineligible unless the public discovery call yielded a corresponding supported device.
- The representative fleet run remains explicitly `not_quiesced` with `background_pollers`, `busy_network`, and `wireless_interference`; no clean-performance claim or regression threshold is inferred.
- `variable_baseline_counts` is an advisory observation only. The mDNS liveness cap of 16 remains a reasoned D-07 safety bound, not a measured optimum.
- FIND-08 records `no_eligible_find08_population`; emulator, unsupported products, and ineligible firmware do not substitute for physical eligible WiFi evidence.

## Deviations from Plan

### User-Directed Structural and Evidence Corrections

1. Discovery implementation was consolidated under `lifx.network.discovery`, with `udp`, `mdns`, and `coordinator` as siblings and compatibility re-exports retained at the former mDNS paths.
2. Observation state moved entirely into the test tree because it has no production importability requirement.
3. Phase-specific measurement steps were removed from permanent CI; the exact implementation revision instead uses ordinary cross-platform PR CI plus locally collected hermetic evidence.
4. Unsupported raw discovery identities were excluded after the fleet exposed a Switch that `discover()` correctly does not yield.
5. After execution, the 73-commit PR history was consolidated into three signed, DCO-compliant commits. Earlier task summaries retain historical pre-squash identifiers; final implementation provenance and evidence are restamped to the consolidated implementation commit.

All corrections preserve the locked public contract and narrow the production and privacy surfaces.

## Issues Encountered

- The operator alias map preserved letter case while the first loader required lowercase values. The loader now accepts case-preserving privacy-safe aliases without weakening identity-shaped-value rejection.
- The default `uv` cache was unavailable inside the sandbox. All final commands used a task-specific cache under `/private/tmp`; dependencies and the lockfile were unchanged.
- GPG verification requires the operator keyring outside the sandbox. Commits were created with `-S -s` and are rechecked through the normal keyring before push.

## User Setup Required

None. The private fleet handoff and alias map remain ignored and outside tracked evidence.

## Next Phase Readiness

Phase 13 has passed independent code and security review and is ready for final goal verification. Phase 14 remains the separate hardware-gated Thread revalidation phase; no WiFi-derived tuning constant was changed here.

## Automated Gates

- Canonical validator: six complete fleet pairs plus one emulator pair accepted at production revision `39bad58c42627ac3612868503bb5fb9305b04cc3`.
- Evidence integrity: the pre-restamp 282,350-byte prefix retained SHA-256 `db10fa2387b858a55a8e06c0cafed49a667b9d7e07dacbcd3d007e84653eb59d`.
- Deterministic summary: two regenerations retained SHA-256 `d0aa02d57348ad65b6b4a9148cd74477d81c265efc259b14fff044bccadea9e2`.
- Focused Phase 13 suite: 280 passed.
- Complete frozen suite: 4,401 passed, 12 deselected.
- Static quality: Ruff format/check and strict Pyright passed.
- Patch coverage: 1,990 changed executable lines and 676 changed branches passed at 100% in one ordinary full-suite coverage run.
- Independent review: code review clean; security verdict `SECURED` with 32/32 threats closed.

## Self-Check: PASSED

All five plan files exist, every canonical row validates, the fleet append preserved the historical prefix, the summary regenerates byte-identically, unsupported products are absent from the eligible population, and all local quality and coverage gates pass.

---
*Phase: 13-merged-discovery*
*Completed: 2026-08-31*
