---
phase: 08-hardware-fidelity-validation
plan: 04
subsystem: hardware-uat
tags: [lifx, morph, hardware-uat, restoration, exception-closeout]
requires:
  - phase: 08-02
    provides: private fail-closed hardware runner and finalisation gate
  - phase: 08-03
    provides: corrected Phase 8 documentation-count boundary
provides:
  - Operator-approved record of the separate Tile and non-Tile fidelity observations
  - Explicit retention of the unresolved Tile restoration exception
  - Deliberate withholding of synthetic official 24-cycle evidence
affects: [Phase-08-verification, Phase-09-documentation, hardware-fidelity-validation]
actuals:
  tokens: 2546
  tasks: 2
  commits: 1
tech-stack:
  added: []
  patterns: [role-local hardware evidence remains separate when the finalisation gate fails]
key-files:
  created:
    - .planning/phases/08-hardware-fidelity-validation/08-UAT.md
    - .planning/phases/08-hardware-fidelity-validation/08-04-SUMMARY.md
    - .planning/phases/08-hardware-fidelity-validation/08-CEILING-DETERMINATIONS.json
    - .planning/phases/08-hardware-fidelity-validation/08-EXCEPTION-OVERRIDE.json
  modified:
    - .planning/phases/08-hardware-fidelity-validation/08-CONTEXT.md
    - .planning/phases/08-hardware-fidelity-validation/08-DISCUSSION-LOG.md
key-decisions:
  - "Close Plan 08-04 by operator-approved exception without manufacturing a finalisable combined run."
  - "Retain the Tile restoration/device-state failure as an unresolved safety/infrastructure exception."
requirements-completed: []
coverage:
  - id: D1
    description: Source-Tile app and library theme observations
    requirement: FIDELITY-02
    verification: []
    human_judgment: true
    rationale: "Twelve private stable expected matches were accepted by the operator, but restoration did not verify and no designated finalisable run exists."
  - id: D2
    description: Independent non-Tile app and library theme observations
    requirement: FIDELITY-03
    verification: []
    human_judgment: true
    rationale: "Twelve private stable expected matches and successful role-local restoration do not satisfy the designated two-role finalisation contract."
  - id: D3
    description: Official sanitised evidence finalisation
    requirement: FIDELITY-01
    verification: []
    human_judgment: true
    rationale: "Official finalisation was deliberately withheld because the single-run restoration gate was not met."
duration: operator-guided hardware session
completed: 2026-08-16
status: complete
---

# Phase 08 Plan 04: Hardware Fidelity Exception Closeout Summary

**Operator-approved hardware theme-fidelity observations for both roles, with the source-Tile restoration failure retained and no synthetic official 24-cycle record.**

## Performance

- **Duration:** Operator-guided hardware session
- **Completed:** 2026-08-16
- **Tasks:** 2/2
- **Files modified:** 4

## Accomplishments

- Recorded the operator's acceptance of twelve stable expected app/library observations on the
  source-Tile role and twelve independently stable expected observations on the non-Tile role.
- Recorded that the non-Tile app observations used a five-second post-change settling interval.
- Preserved the source-Tile restoration/device-state failure as an unresolved exception rather than
  misrepresenting separate role-local records as one finalisable 24-cycle run.

## Task Commits

1. **Task 1: Run and classify the real-hardware UAT** — operator-guided session; no public
   evidence artefact was eligible for commit.
2. **Task 2: Close documentation by approved exception** — this documentation commit.

## Files Created/Modified

- `.planning/phases/08-hardware-fidelity-validation/08-UAT.md` — concise acceptance record and
  explicit finalisation withholding.
- `.planning/phases/08-hardware-fidelity-validation/08-CONTEXT.md` — D-24 exception-closeout
  decision.
- `.planning/phases/08-hardware-fidelity-validation/08-DISCUSSION-LOG.md` — decision rationale
  and rejected synthetic-finalisation path.

## Decisions Made

- The operator accepted the observed theme-fidelity outcome; no more hardware work is required for
  this closeout.
- The Tile restoration/device-state failure remains open and prevents official finalisation.
- Phase and requirement completion are intentionally left to Phase 8 verification; this summary
  completes the plan documentation only.

## Deviations from Plan

### Operator-Approved Exception

The planned authoritative results JSON and derived official report were not created. The source
Tile and non-Tile observations were captured in separate private role-local sessions, and the
source-Tile restoration did not verify. The user explicitly authorised closeout with this exception
rather than a retry, resume, or manufactured combined result.

## Known Stubs

None.

## Next Phase Readiness

Plan 08-04 is closed by exception. A Phase 8 verifier must preserve the unresolved restoration
exception and determine the requirements and phase-level outcome; Phase 9 must not treat this as
official finalised evidence.

The post-close [ceiling determinations](08-CEILING-DETERMINATIONS.json) close only the independent
per-slug true-length question. The [structured exception override](08-EXCEPTION-OVERRIDE.json)
records the operator's accepted closeout without converting the unverified Tile restoration into a
pass or synthetic two-role result.

## Self-Check: PASSED

- Confirmed the UAT record, exception decision, and summary exist without private identifiers or
  an official evidence artefact.
- Confirmed the focused runner suite passed with complete statement and branch coverage, and Ruff
  and Pyright were clean.
