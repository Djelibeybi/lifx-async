---
phase: 08-hardware-fidelity-validation
plan: 01
subsystem: hardware-uat
tags: [lifx, morph, adb, uiautomator, privacy, preflight]
requires:
  - phase: 06-generated-theme-library
    provides: Theme.palette_equals(), generated theme records, and MatrixLight MORPH APIs
provides:
  - Phase-local semantic Android/LAN MORPH tracer contracts
  - Restrictive private-target, diagnostics, and keep-awake lifecycle boundary
affects: [08-02, 08-04, hardware-fidelity-validation]
actuals:
  tokens: 10747
  tasks: 2
  commits: 4
tech-stack:
  added: []
  patterns: [phase-local UAT runner, fixed-argv ADB, semantic hierarchy selection, fail-closed private configuration]
key-files:
  created:
    - .planning/phases/08-hardware-fidelity-validation/uat_theme_fidelity.py
    - .planning/phases/08-hardware-fidelity-validation/tests/conftest.py
    - .planning/phases/08-hardware-fidelity-validation/tests/test_uat_theme_fidelity.py
  modified:
    - .gitignore
key-decisions:
  - "Use Theme.palette_equals() as the sole unordered duplicate-sensitive palette comparison seam."
  - "Keep all target identifiers, traces, hierarchies, and diagnostics under a mode-restricted local-only root."
patterns-established:
  - "Resolve each Android tap from the immediately current hierarchy; retry a semantic miss exactly twice."
  - "Capture and restore Android keep-awake in an outer finally block."
requirements-completed: []
coverage:
  - id: D1
    description: "Private semantic Android and targeted Tile MORPH tracer contracts"
    requirement: FIDELITY-02
    verification:
      - kind: integration
        ref: ".planning/phases/08-hardware-fidelity-validation/tests/test_uat_theme_fidelity.py (19 passed)"
        status: pass
    human_judgment: true
    rationale: "Injected tests prove orchestration only; real Tile hardware evidence remains required."
  - id: D2
    description: "Fail-closed target, ADB, diagnostics, and Android keep-awake boundary"
    verification:
      - kind: unit
        ref: ".planning/phases/08-hardware-fidelity-validation/tests/test_uat_theme_fidelity.py -k preflight (12 passed)"
        status: pass
    human_judgment: false
duration: 10min
completed: 2026-08-16
status: complete
---

# Phase 08 Plan 01: Hardware MORPH Tracer Summary

**Phase-local MORPH tracer contracts with semantic Android navigation, exact LIFX palette comparison, and fail-closed private hardware boundaries.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-08-15T17:24:00Z
- **Completed:** 2026-08-15T17:34:15Z
- **Tasks:** 2/2
- **Files modified:** 4

## Accomplishments

- Added a dependency-free private tracer that derives Cheerful and Mondrian from `data/themes.jsonl`, resolves semantic Android controls from fresh hierarchies, and calls `MatrixLight.set_effect(FirmwareEffect.MORPH, ...)`.
- Locked stability and expected-readback comparisons to `Theme.palette_equals()` so palette order is ignored while duplicate HSBK entries remain significant.
- Added strict local target schemas, restrictive private file modes, redacted ADB failures and diagnostics, exact Android keep-awake restoration, and focused injected tests.

## Task Commits

1. **Task 1: Trace cheerful from app Save and library MORPH through source-Tile restoration** - `567268e` (test), `0670b66` (feat)
2. **Task 2: Enforce fail-closed preflight, Android lifecycle and private diagnostics** - `9f281cc` (test), `4d975c4` (feat)

## Files Created/Modified

- `.planning/phases/08-hardware-fidelity-validation/uat_theme_fidelity.py` - phase-local tracer, ADB boundary, semantic UI selection, private storage and preflight contracts.
- `.planning/phases/08-hardware-fidelity-validation/tests/test_uat_theme_fidelity.py` - injected contract tests for tracer ordering, equality, schema, ADB, diagnostics and restoration.
- `.planning/phases/08-hardware-fidelity-validation/tests/conftest.py` - phase-local runner import bootstrap.
- `.gitignore` - narrowly ignores only the Phase 8 private local root.

## Verification

- Focused Phase 8 runner tests — 19 passed.
- Ruff check — passed.
- Pyright on the Phase 8 runner — 0 errors.

## Decisions Made

- Hardware truth is deliberately not marked complete: injected tests establish safety and orchestration, while FIDELITY-02 still needs the designated real-hardware UAT in Plan 08-04.
- Public output uses only `source-tile` / `non-tile-matrix` roles and theme slugs; target identifiers and raw UI content stay private.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test correctness] Corrected the stable-readback assertion to retain the second consecutive device observation.**
- **Found during:** Task 1
- **Issue:** The test expected the first reordered stable palette, although the polling contract retains the second consecutive read.
- **Fix:** Asserted the final observation while preserving unordered `Theme.palette_equals()` comparison.
- **Files modified:** `.planning/phases/08-hardware-fidelity-validation/tests/test_uat_theme_fidelity.py`
- **Verification:** Focused tracer suite passed.
- **Committed in:** `0670b66`

## Known Stubs

None.

## Next Phase Readiness

Plan 08-02 can expand the tested semantic tracer into the complete resumable two-theme/two-device schedule. A private target file and quiesced real hardware remain required before Plan 08-04 can establish FIDELITY-02/03 truth.

## Self-Check: PASSED

- Confirmed all four task commits exist and all four implementation/test files are present.

---
*Phase: 08-hardware-fidelity-validation*
*Completed: 2026-08-16*
