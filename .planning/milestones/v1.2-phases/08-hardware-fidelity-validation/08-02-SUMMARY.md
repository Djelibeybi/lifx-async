---
phase: 08-hardware-fidelity-validation
plan: 02
subsystem: testing
tags: [hardware-uat, adb, lifx, restoration, evidence, coverage]
requires:
  - phase: 08-01
    provides: private semantic Android tracer, target bindings, and stable palette readback
provides:
  - Complete injectable two-device 24-cycle runner with restrictive checkpoints and restoration
  - Fail-closed CLI run, resume, validation, and finalisation paths
  - Allowlisted public evidence projection and derived 25-row ceiling determination inventory
affects: [08-03, 08-04, hardware fidelity evidence]
actuals:
  tokens: 30692
  tasks: 3
  commits: 6
tech-stack:
  added: []
  patterns: [injected ADB/LAN/clock/checkpoint/filesystem seams, restore-before-finalise]
key-files:
  created: []
  modified:
    - .planning/phases/08-hardware-fidelity-validation/uat_theme_fidelity.py
    - .planning/phases/08-hardware-fidelity-validation/tests/test_uat_theme_fidelity.py
key-decisions:
  - "The CLI writes a restrictive designated-run projection before --finalise can produce public evidence."
  - "Both selected devices and Android keep-awake state restore through terminal-path finally blocks."
patterns-established:
  - "All hardware, ADB, clock, checkpoint, and public-evidence boundaries are injectable for hardware-free coverage."
requirements-completed: [FIDELITY-01, FIDELITY-02, FIDELITY-03]
coverage:
  - id: D1
    description: Deterministic two-role 24-cycle schedule, strict resume provenance, and semantic app/library flow
    requirement: FIDELITY-02
    verification:
      - kind: unit
        ref: .planning/phases/08-hardware-fidelity-validation/tests/test_uat_theme_fidelity.py
        status: pass
    human_judgment: false
  - id: D2
    description: Capability-complete snapshot and verified restoration lifecycle
    requirement: FIDELITY-03
    verification:
      - kind: unit
        ref: .planning/phases/08-hardware-fidelity-validation/tests/test_uat_theme_fidelity.py
        status: pass
    human_judgment: false
  - id: D3
    description: Actual Tile and indoor non-Tile hardware execution plus designated public evidence
    requirement: FIDELITY-01
    verification: []
    human_judgment: true
    rationale: Plan 08-04 performs the required real-hardware UAT; this plan validates only injected boundaries.
duration: resumed execution; wall time not captured
completed: 2026-08-15
status: complete
---

# Phase 08 Plan 02: Complete Hardware-Fidelity Runner Summary

**A fail-closed, resumable 24-cycle Tile/non-Tile fidelity runner with complete restoration and privacy-safe JSON/Markdown finalisation.**

## Performance

- **Duration:** Resumed execution; wall time not captured
- **Completed:** 2026-08-15
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Implemented the fixed 24-key schedule, provenance-gated resume, semantic Android path, and safe non-Tile preflight.
- Added complete device/effect/pixel/Ceiling restoration with Android keep-awake cleanup on terminal paths.
- Added injected production boundaries, `--run`, `--resume`, `--finalise`, and `--validate-evidence`; 78 focused tests reach 100% statement and branch coverage.

## Task Commits

1. **Task 1: Exact 24-cycle schedule and provenance resume** — `202f26b`, `2e3322d`
2. **Task 2: Capability-complete restoration** — `f3ad0cf`, `b7e95c1`
3. **Task 3: Fail-closed evidence finalisation** — `bab914e`, `b7ff5b1`

## Files Modified

- `.planning/phases/08-hardware-fidelity-validation/uat_theme_fidelity.py` — production adapters, lifecycle, checkpointing, CLI dispatch, restoration, and evidence gates.
- `.planning/phases/08-hardware-fidelity-validation/tests/test_uat_theme_fidelity.py` — injected production-path coverage with no real ADB or LAN mutation.

## Decisions Made

- A run becomes finalisable only after all 24 cycles are terminal and both restorations verify; mismatches remain valid failed evidence.
- The generated public record is allowlisted rather than redacted from private checkpoint data.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Correctness] Added the missing production lifecycle and CLI seams**
- **Found during:** Task 3
- **Issue:** The preserved implementation reached 100% coverage for pure helpers but its CLI still stopped after tracer preflight.
- **Fix:** Added injected ADB, device, clock, checkpoint, filesystem, and evidence-writer boundaries; wired the real two-device lifecycle and all required CLI modes.
- **Verification:** 78 focused tests, 100% branch coverage, Ruff, Pyright, and commit hooks pass.
- **Committed in:** `b7ff5b1`

**Total deviations:** 1 auto-fixed (Rule 2)

## Known Stubs

None. Plan 08-04 remains the deliberate, separately authorised real-hardware execution step.

## Next Phase Readiness

Plan 08-03 can consume the mechanical 25-row ceiling determination derivation. Plan 08-04 can run the private CLI against the approved Tile and indoor non-Tile device after operator preflight; no hardware was contacted or mutated by this plan's tests.

## Post-Completion Correction

- **2026-08-16:** The user superseded the earlier private `reset_palette` assumption. The
  capture-era observation is not a canonical reusable signature, so the target schema and runner
  no longer request, decode or reject it. Two consecutive equal readbacks still establish
  stability; a stable palette unequal to the expected shipped theme remains retained mismatch
  evidence.

## Self-Check: PASSED

- Verified `uat_theme_fidelity.py` and its focused test suite exist.
- Verified Task 3 GREEN commit `b7ff5b1` exists.

---

*Phase: 08-hardware-fidelity-validation*
*Completed: 2026-08-15*
