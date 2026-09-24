---
phase: 18-typed-move-and-morph-palette-effects
plan: 07
subsystem: docs
tags: [multizone, move-effect, documentation, migration-guide, api-reference]

# Dependency graph
requires:
  - phase: 18-typed-move-and-morph-palette-effects (plan 06)
    provides: "MultiZoneLight.set_move_effect(), MultiZoneEffect.move(), the widened direction setter"
provides:
  - "docs/user-guide/effects.md ## Firmware Move effect section with two self-contained, verbatim-executed examples (EFFECT-01 R7)"
  - "docs/migration/effect-api-changes.md and docs/api/devices.md rewritten off every stale keyword-first Move example, including the invalid multizone set_effect(effect_type=FirmwareEffect.OFF) form"
  - "AGENTS.md component_state.py entry widened to name derive_effect_palette()/validate_effect_palette()"
  - "Phase-wide gates run and passing: strict docs build, prose (no em dash), changelog-untouched, split-boundary (no connectivity/Thread line under src/lifx), and 100% branch patch coverage for multizone.py/matrix.py/component_state.py"
affects: []

# Actuals (#2632)
actuals:
  tokens: 3157
  tasks: 3
  commits: 4
plan_head_before: 1c2f3c10c362ad0521df98793e3673baca615ef1

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Self-contained doc examples: each fenced python block in a user-guide section imports what it uses and relies on no name an earlier block defined, so a verbatim-execution test can run every block in document order with a fresh namespace per block"
    - "Prose-not-code for a removed API's old signature: when a method name is reused with a different signature, the migration guide describes the old call in prose instead of a runnable code sample, so the sample never reads as valid current code"

key-files:
  created: []
  modified:
    - docs/user-guide/effects.md
    - tests/test_devices/test_multizone_move.py
    - docs/migration/effect-api-changes.md
    - docs/api/devices.md
    - AGENTS.md
    - src/lifx/devices/component_state.py

key-decisions:
  - "Every keyword-first set_move_effect(speed=..., direction=...) call describing the pre-4.3.0 API is prose, not a code sample: the method name now exists with a different signature, so a literal call would read as valid current code (per plan action text)"
  - "The devices.md MultiZone Control 'Stop the effect' call was changed to stop_effect() rather than a bare set_effect(MultiZoneEffect(effect_type=FirmwareEffect.OFF, ...)) reconstruction, since MultiZoneLight already ships stop_effect() for exactly this purpose"
  - "[Rule 1] Fixed a pre-existing em dash in component_state.py's derive_effect_palette() docstring (added in plan 04): the phase-wide added-lines prose gate scans the whole phase diff from merge-base, not just this plan's own additions, so an earlier plan's em dash blocked this plan's Task 3 verify"
  - "[Rule 1] Reverted an unnecessary speed=5.0 override introduced while turning a '...' ellipsis placeholder into literal code in the migration guide's unified-naming FLAME line: 5.0 is not set_effect()'s 3.0 default, and examples must never override a default they do not need"

requirements-completed: [EFFECT-01, EFFECT-02]

coverage:
  - id: D1
    description: "docs/user-guide/effects.md gains a '## Firmware Move effect' section, directly before '## Next Steps', with two self-contained python examples (the one-call typed method and the builder form) describing the LIFX-app-style palette behaviour; a new test extracts every python block under that heading and executes it verbatim, in document order against an emulator strip, with a fresh namespace per block, then asserts get_effect() reports MOVE"
    requirement: "EFFECT-01"
    verification:
      - kind: integration
        ref: "tests/test_devices/test_multizone_move.py::TestDocumentedMoveExamples::test_user_guide_move_example_runs_verbatim"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every stale Move example is gone from src/lifx and docs/: the migration guide's Move section and the docs/api/devices.md MultiZone Control example now show set_move_effect(Direction.FORWARD, 5.0) and stop_effect(); the migration guide documents the direction setter's ValueError-for-a-bare-int narrowing with Direction(value) as the fix; the Summary of Removals line no longer names an invalid set_effect() keyword form; the MultiZoneEffect API reference lead-in names move() and set_move_effect()"
    requirement: "EFFECT-01"
    verification:
      - kind: other
        ref: "multi-line-aware regex scan of src/lifx and docs/ for set_move_effect(\\s*speed\\s*= and set_effect(\\s*effect_type\\s*=\\s*FirmwareEffect\\.MOVE — 0 hits across 132 scanned files"
        status: pass
      - kind: other
        ref: "region-scoped scan of the MultiZone Control and Firmware Move effect sections for any set_effect(\\s*effect_type\\s*= keyword call — 0 hits, covering both the MOVE and OFF invalid forms"
        status: pass
    human_judgment: false
  - id: D3
    description: "AGENTS.md's component_state.py entry names derive_effect_palette()/validate_effect_palette(); the phase-wide gates all pass: strict zensical build and llms.txt validation, the added-lines-are-Australian-English-no-em-dash check, the changelog-untouched check, the split-boundary scan (no added connectivity/Thread line under src/lifx, only the three planned library files changed), and 100% branch patch coverage for multizone.py, matrix.py and component_state.py"
    requirement: "EFFECT-02"
    verification:
      - kind: other
        ref: "uv run --frozen zensical build --clean --strict; uv run --frozen llmstxt-standalone validate"
        status: pass
      - kind: other
        ref: ".github/check_patch_coverage.py --source src/lifx/devices/multizone.py --source src/lifx/devices/matrix.py --source src/lifx/devices/component_state.py -> PASS total (86 changed executable lines, 30 changed branches)"
        status: pass
      - kind: unit
        ref: "tests/test_repository_guidance.py"
        status: pass
      - kind: other
        ref: "uv run --frozen pytest -q (full default suite): 4545 passed, 700 deselected; ruff check ., ruff format --check ., pyright all clean"
        status: pass
    human_judgment: false

# Metrics
duration: 25min
completed: 2026-09-23
status: complete
---

# Phase 18 Plan 7: Move Documentation and Phase-Wide Gates Summary

**Documents the typed `set_move_effect()`/`MultiZoneEffect.move()` API and its LIFX-app-style palette behaviour in the effects user guide (with a verbatim-executed example), rewrites every stale keyword-first Move example in the migration guide and API reference, and closes out the phase's docs-build, prose, split-boundary and 100% branch patch-coverage gates.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-09-23T10:05:00Z
- **Completed:** 2026-09-23T10:30:06Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- `docs/user-guide/effects.md` gains a `## Firmware Move effect` section, directly before `## Next Steps`, describing Move as firmware-only (one packet, no Conductor, no Animator), the LIFX-app-style palette rule `set_move_effect()` implements (generate-and-paint on a single colour, leave a multi-colour strip alone, paint an explicit palette unchanged with no zone read), and showing both the one-call typed method and the builder form in two self-contained python examples.
- A new test, `TestDocumentedMoveExamples::test_user_guide_move_example_runs_verbatim`, and its supporting `_markdown_section_examples()` helper extract every python block under that heading and run each verbatim, in document order against the `d073d5000005` emulator strip, with a fresh namespace holding only `light` per block, then assert `get_effect()` reports MOVE.
- `docs/migration/effect-api-changes.md`'s Move passages are rewritten to the shipped API: every keyword-first `set_move_effect(speed=..., direction=...)` call describing the pre-4.3.0 method is now prose rather than a runnable sample (since the same method name exists today with a different signature); the "After"/"New Code" blocks show `set_move_effect(Direction.FORWARD, 5.0)`; a new paragraph documents the `direction` setter's narrowed `ValueError` for a bare integer with `Direction(value)` as the fix; the Summary of Removals line no longer points readers at an invalid `set_effect()` keyword form.
- `docs/api/devices.md`'s MultiZone Control example now calls `set_move_effect(Direction.FORWARD, 5.0)` and `stop_effect()` instead of the two invalid `set_effect(effect_type=...)` keyword forms it previously showed for MOVE and OFF; the `### MultiZoneEffect` API reference lead-in now names `MultiZoneEffect.move()` and `MultiZoneLight.set_move_effect()`.
- A multi-line-aware Python regex scan of every `.py`/`.md` file under `src/lifx` and `docs/` (132 files) finds zero remaining `set_move_effect(\s*speed\s*=` or `set_effect(\s*effect_type\s*=\s*FirmwareEffect\.MOVE` occurrences, including forms split across lines; a region-scoped scan of the MultiZone Control and Firmware Move effect sections finds zero `set_effect(\s*effect_type\s*=` keyword calls at all, covering the invalid OFF form as well as MOVE.
- `AGENTS.md`'s `component_state.py` Device Layer entry is widened to name `derive_effect_palette()` and `validate_effect_palette()`, the firmware-effect palette rule shared by Morph and Move, alongside its existing content; `tests/test_repository_guidance.py` still passes.
- The phase-wide gates all pass: strict `zensical build` and `llmstxt-standalone validate`; the added-lines Australian-English/no-em-dash check across `docs`, `AGENTS.md`, `src/lifx` and `tests`; the `docs/changelog.md`-untouched check; the split-boundary scan (zero added connectivity/Thread lines under `src/lifx`, and only the three planned library files — `multizone.py`, `matrix.py`, `component_state.py` — changed under `src/lifx` across the whole phase); and 100% branch patch coverage for all three (86 changed executable lines, 30 changed branches, `PASS total`). The full default suite passes: 4545 passed, 700 deselected. `ruff check .`, `ruff format --check .` and `pyright` are all clean.

## Task Commits

1. **Task 1 (tracer): user-guide Move section and verbatim-executed example** - `2d25d3b` (docs)
2. **Task 2: migration guide and devices API reference rewrite** - `666e7de` (docs)
3. **Task 3: AGENTS.md widening and phase-wide gates** - `96e2574` (docs)
4. **Task 2 follow-up fix: drop a non-default speed argument introduced while de-ellipsis-ing an illustrative line** - `f0279ff` (fix)

**Plan metadata:** committed separately after this summary (see below).

## Files Created/Modified

- `docs/user-guide/effects.md` - New `## Firmware Move effect` section, purely additive (0 lines removed from the merge-base), directly before `## Next Steps`.
- `tests/test_devices/test_multizone_move.py` - Adds `_markdown_section_examples()` and `TestDocumentedMoveExamples::test_user_guide_move_example_runs_verbatim`.
- `docs/migration/effect-api-changes.md` - Move passages rewritten to the shipped typed API across the Direction Control, Method Naming Simplified, Migration Guide and Summary of Removals sections.
- `docs/api/devices.md` - MultiZone Control example and the `### MultiZoneEffect` lead-in updated to the typed Move API.
- `AGENTS.md` - `component_state.py` Device Layer entry widened.
- `src/lifx/devices/component_state.py` - Docstring-only fix: one pre-existing em dash in `derive_effect_palette()`'s `Returns:` section recast without changing meaning (no behaviour change).

## Decisions Made

- Every keyword-first `set_move_effect()` call illustrating the pre-4.3.0 API became prose rather than a code sample, per the plan's own action text: the method name is reused today with a different signature, so a literal call would misleadingly read as valid current code.
- The devices.md "Stop the effect" call uses the existing `stop_effect()` method rather than hand-reconstructing a `MultiZoneEffect(effect_type=FirmwareEffect.OFF, ...)` object, since that method exists for exactly this purpose and keeping the example on the typed surface matches the rest of the rewrite.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Recast a pre-existing em dash in component_state.py's derive_effect_palette() docstring**
- **Found during:** Task 3 (the added-lines prose gate, run across the whole phase diff from `merge-base HEAD main`, not just this plan's own additions)
- **Issue:** Plan 04's `derive_effect_palette()` docstring `Returns:` section used an em dash (`— animate the colours already shown`), violating the project's no-em-dash house style. Task 3's `added-lines-with-em-dash` gate scans the entire phase diff, so this earlier plan's defect blocked this plan's own Task 3 verify from passing.
- **Fix:** Recast the sentence without an em dash: "None, meaning the caller should send no palette and animate the colours already shown." No behavioural change; docstring only.
- **Files modified:** `src/lifx/devices/component_state.py`
- **Verification:** `added-lines-with-em-dash=0` after the fix; `ruff check`/`ruff format --check` on the file both clean.
- **Committed in:** `96e2574` (Task 3 commit)

**2. [Rule 1 - Bug] Dropped a non-default speed argument accidentally introduced in Task 2**
- **Found during:** Post-Task-3 self-review of the plan's "no example overrides a library default" rule
- **Issue:** While replacing an illustrative `...` ellipsis placeholder with a real `set_move_effect()` call in the migration guide's "Method Naming Simplified" section, the adjacent Matrix line's placeholder was also made literal as `set_effect(effect_type=FirmwareEffect.FLAME, speed=5.0)` — but `5.0` is not `MatrixLight.set_effect()`'s `3.0` default, and this line did not need to change at all (it never matched either banned regex).
- **Fix:** Reverted that one line back to `set_effect(effect_type=FirmwareEffect.FLAME, ...)`, matching every sibling line in the section.
- **Files modified:** `docs/migration/effect-api-changes.md`
- **Verification:** Re-ran the multi-line-aware and region-scoped stale-example scans (both still 0 hits) and the em-dash gate (0) after the revert.
- **Committed in:** `f0279ff`

---

**Total deviations:** 2 auto-fixed (both Rule 1, both docs-only, no behavioural change).
**Impact on plan:** None on shipped behaviour. Both fixes were required for this plan's own Task 3 verify gates (added-lines prose scan; default-override discipline) to pass cleanly.

## Issues Encountered

None beyond the two deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- EFFECT-01 and EFFECT-02 are both now fully documented and gated: the typed Move API and its palette behaviour appear in the published user guide, migration guide and API reference, and no page shows an API that does not exist.
- Phase 18 is complete for its post-split scope (R4 to R7, R9, R10). ANIM-05 (the Animator Thread guard, R1 to R3, R8) lives in Phase 20 per the 2026-09-23 split; `18-SPEC.md` and `18-CONTEXT.md` already mark those items moved.
- No blockers.

## Self-Check: PASSED

- `docs/user-guide/effects.md`: FOUND, contains `## Firmware Move effect` directly before `## Next Steps`
- `tests/test_devices/test_multizone_move.py`: FOUND
- `docs/migration/effect-api-changes.md`: FOUND
- `docs/api/devices.md`: FOUND
- `AGENTS.md`: FOUND, `component_state.py` line contains `derive_effect_palette()`
- `src/lifx/devices/component_state.py`: FOUND
- Commits `2d25d3b`, `666e7de`, `96e2574`, `f0279ff`: all FOUND in `git log --oneline --all`
- Plan `<verification>` re-run: `uv run --frozen zensical build --clean --strict` and `uv run --frozen llmstxt-standalone validate` both pass; full default suite 4545 passed, 700 deselected; patch-coverage checker `PASS total` for `multizone.py`/`matrix.py`/`component_state.py` (86 changed executable lines, 30 changed branches); split-boundary scan finds no added connectivity/Thread line under `src/lifx`

---
*Phase: 18-typed-move-and-morph-palette-effects*
*Completed: 2026-09-23*
