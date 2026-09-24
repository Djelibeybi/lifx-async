---
phase: 18-typed-move-and-morph-palette-effects
plan: 06
subsystem: devices
tags: [multizone, move-effect, palette, apply_theme, emulator]

# Dependency graph
requires:
  - phase: 18-typed-move-and-morph-palette-effects (plan 03)
    provides: "MultiZoneEffect.move(), _coerce_direction(), the widened direction setter"
  - phase: 18-typed-move-and-morph-palette-effects (plan 04)
    provides: "derive_effect_palette()/validate_effect_palette() in component_state.py"
provides:
  - "MultiZoneLight.set_move_effect(direction, speed, duration=0, palette=None) — one-call typed Move method (EFFECT-01 R5)"
  - "MultiZoneLight._derive_move_palette() — private palette-derivation step reusing derive_effect_palette() (EFFECT-02 R9)"
  - "Corrected MultiZoneLight class docstring and set_move_effect() docstring with an executed example (R7)"
affects: [18-07]

# Actuals (#2632)
actuals:
  tokens: 5614
  tasks: 3
  commits: 3
plan_head_before: a5618c79dd18a851207369c55bd3a7cf11095e3c

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Effect built before palette handling: MultiZoneEffect.move() runs first so bad direction/speed/duration raise before any packet or zone read (D-10)"
    - "Paint-then-send: a caller-supplied or derived palette is wrapped in a Theme and painted via apply_theme(theme, duration=0) before the Move SetEffect is sent (D-20)"
    - "Timeout-as-fallback: a LifxTimeoutError reading zones logs at DEBUG and Move still starts unpainted, mirroring the SKY support probe and the Morph palette read (D-23)"

key-files:
  created: []
  modified:
    - src/lifx/devices/multizone.py
    - tests/test_devices/test_multizone_move.py

key-decisions:
  - "set_move_effect() calls validate_effect_palette() only when an explicit palette is given; get_all_color_zones() is called only through _derive_move_palette(), and only when palette is None — proven by wraps= spy assertions across every branch"
  - "Task 2 (tdd=\"true\") produced zero RED failures: Task 1's tracer already implemented the complete production behaviour (as its own plan action mandated, D-10 through D-23), so all 56 new edge-case tests passed on first run with no GREEN implementation needed — documented in TDD Gate Compliance below, following the identical precedent already recorded in 18-04-SUMMARY.md"
  - "'Single colour' derivation reuses derive_effect_palette()'s HSBK.__eq__ rule unchanged; set_move_effect() adds no new equality or tolerance logic of its own"

requirements-completed: [EFFECT-01, EFFECT-02]

coverage:
  - id: D1
    description: "MultiZoneLight.set_move_effect(direction, speed, duration=0, palette=None) starts Move in one call: on a single-colour strip it paints the LIFX-app-style shuffled three-colour blend through apply_theme() before sending Move, proven by an emulator tracer test with a packet-capture ordering assertion (paint before SetEffect) and a Theme-argument assertion"
    requirement: "EFFECT-01"
    verification:
      - kind: integration
        ref: "tests/test_devices/test_multizone_move.py::TestSetMoveEffectEmulator::test_single_colour_strip_is_painted_then_moved"
        status: pass
      - kind: integration
        ref: "tests/test_devices/test_multizone_move.py::TestDocumentedMoveExamples::test_set_move_effect_docstring_example_runs_verbatim"
        status: pass
    human_judgment: false
  - id: D2
    description: "Explicit-palette validation (empty/oversized raises before any packet), invalid direction/speed/duration raising the same ValueError as move() with no OverflowError leak, an explicit palette reaching apply_theme() unchanged with get_all_color_zones() never awaited, a multi-colour strip left untouched, and a zone-read timeout falling back to an unpainted Move with one DEBUG record"
    requirement: "EFFECT-02"
    verification:
      - kind: integration
        ref: "tests/test_devices/test_multizone_move.py::TestSetMoveEffectPalette"
        status: pass
    human_judgment: false
  - id: D3
    description: "The raw set_effect(MultiZoneEffect) path sends exactly one SetEffect and reads or paints nothing (R6/R9 prohibition), proven by an exact captured-packet-type-sequence assertion"
    requirement: "EFFECT-02"
    verification:
      - kind: integration
        ref: "tests/test_devices/test_multizone_move.py::TestRawPathPaintsNothing::test_raw_set_effect_sends_only_set_effect_and_zones_unchanged"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every error set_effect() raises reaches the caller through set_move_effect() unchanged: StateUnhandled on a real emulator switch proven to originate from SetEffect (not the read or the paint), plus mocked LifxTimeoutError/LifxDeviceNotFoundError propagation"
    requirement: "EFFECT-01"
    verification:
      - kind: integration
        ref: "tests/test_devices/test_multizone_move.py::TestSetMoveEffectErrors::test_state_unhandled_comes_from_set_effect"
        status: pass
      - kind: unit
        ref: "tests/test_devices/test_multizone_move.py::TestSetMoveEffectErrors::test_set_effect_errors_propagate_from_mock"
        status: pass
    human_judgment: false
  - id: D5
    description: "The MultiZoneLight class docstring's two stale keyword-first Move calls are replaced with the shipped typed call, and set_move_effect()'s docstring example is executed verbatim against the emulator (R7)"
    requirement: "EFFECT-01"
    verification:
      - kind: unit
        ref: "src/lifx module scan: no set_move_effect(speed= call remains under src/lifx"
        status: pass
      - kind: integration
        ref: "tests/test_devices/test_multizone_move.py::TestDocumentedMoveExamples::test_set_move_effect_docstring_example_runs_verbatim"
        status: pass
    human_judgment: false

# Metrics
duration: 26min
completed: 2026-09-23
status: complete
---

# Phase 18 Plan 06: Typed Move Device Method Summary

**`MultiZoneLight.set_move_effect(direction, speed, duration=0, palette=None)` starts the firmware Move effect in one call, painting a caller-supplied or LIFX-app-style generated palette through `apply_theme()` before Move starts on a single-colour strip, while the raw `set_effect(MultiZoneEffect)` path stays byte-for-byte unchanged.**

## Performance

- **Duration:** 26 min
- **Started:** 2026-09-23T19:41:00+10:00
- **Completed:** 2026-09-23T20:06:33+10:00
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- `MultiZoneLight.set_move_effect(direction, speed, duration=0, palette=None)`: builds the effect first with `MultiZoneEffect.move()` so bad arguments raise before any packet, then paints (a validated explicit palette, or a derived one when `palette=None`) through `apply_theme(Theme(...), duration=0)` when there is something to paint, then sends the effect via the existing `set_effect()` so every error it raises propagates unchanged.
- `MultiZoneLight._derive_move_palette()`: reads `get_all_color_zones()`, and calls the shared `derive_effect_palette()` from plan 04 — `None` (send no palette) when the strip already shows more than one distinct colour, or a generated three-colour palette when every zone is identical (`HSBK.__eq__`, uint16 wire equality). A `LifxTimeoutError` reading the zones logs one structured DEBUG record naming the serial and falls back to an unpainted Move.
- An emulator tracer test proves the full single-colour flow end-to-end: paint via `apply_theme()`'s shuffled blend, packet-capture ordering (`SetExtendedColorZones` before `SetEffect`), and `get_effect()` reporting `MOVE`/`speed=5000` with `Direction.FORWARD` on the received packet.
- 56 further emulator and mock tests prove every other branch: explicit-palette validation (empty/17-colour raises before any packet), invalid direction/speed/duration matching `move()`'s own `ValueError` contract (including `10**400` raising `ValueError`, never `OverflowError`), an explicit palette reaching `apply_theme()` unchanged with `get_all_color_zones()` never awaited, a multi-colour strip left untouched, a dropped-packet timeout falling back to an unpainted Move with exactly one DEBUG record, the raw path sending exactly `[SetEffect, GetEffect]` with the zones untouched, `StateUnhandled` on a real emulator switch proven to originate from `SetEffect` (not the read or paint), and mocked `LifxTimeoutError`/`LifxDeviceNotFoundError` propagation.
- The `MultiZoneLight` class docstring's two stale `set_move_effect(speed=5.0, direction="forward")` calls are replaced with `await light.set_move_effect(Direction.FORWARD, 5.0)` (importing `Direction` from `lifx`), and a new executed-example test proves `set_move_effect()`'s own docstring example runs verbatim against the emulator.
- `tests/test_devices/test_multizone.py` remains byte-identical to the merge-base throughout; the patch-coverage checker reports `PASS` for `src/lifx/devices/multizone.py` (52 changed executable lines, 18 changed branches, all covered).

## Task Commits

1. **Task 1 (tracer): typed Move method, palette derivation, tracer test** - `e80382f` (feat)
2. **Task 2 (tdd="true"): exhaustive edge-case tests for palettes, raw path and errors** - `687209a` (test) — see TDD Gate Compliance below
3. **Task 3: corrected class docstring, executed example** - `e957a19` (docs)

**Plan metadata:** committed separately after this summary (see below).

## Files Created/Modified

- `src/lifx/devices/multizone.py` - Adds `MultiZoneLight._derive_move_palette()` and `MultiZoneLight.set_move_effect()`; imports `derive_effect_palette`/`validate_effect_palette` from `component_state`; replaces the two stale keyword-first Move calls in the class docstring.
- `tests/test_devices/test_multizone_move.py` - Adds `TestSetMoveEffectEmulator` (tracer), `TestSetMoveEffectPalette`, `TestRawPathPaintsNothing`, `TestSetMoveEffectErrors` (mock and emulator), and `TestDocumentedMoveExamples::test_set_move_effect_docstring_example_runs_verbatim`.

## Decisions Made

- Implemented D-10, D-13 to D-15, D-20 to D-23 exactly as locked in `18-CONTEXT.md`: effect built first, palette validated or derived, painted via `apply_theme()` at `duration=0`, then sent. No new architectural decisions were needed beyond what the plan and its maintainer adjudication already settled.
- Task 2's TDD outcome (documented fully below) is recorded as a decision rather than a defect: the plan's own Task 1 action text required the complete production method in the tracer commit, so Task 2's exhaustive tests had no remaining gap to close.

## Deviations from Plan

### Auto-fixed Issues

None — the implementation followed the plan's Task 1 action text exactly, and no Rule 1-3 auto-fixes were needed.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** None. The one notable process deviation (Task 2's RED phase producing zero failures) is documented under TDD Gate Compliance below rather than as a functional deviation, since no plan requirement, acceptance criterion or verify gate was affected.

## TDD Gate Compliance

Task 2 carries `tdd="true"`. Its actual gate outcome, investigated and documented in full per `tdd.md`'s "feature may already exist" guidance:

| Gate | Commit | Evidence |
|------|--------|----------|
| RED | `687209a` | `test(devices): cover set_move_effect() palettes, raw path and errors` — **0 failed, 56 passed** on first run. |
| GREEN | (none) | No implementation commit exists because no implementation gap existed. |
| REFACTOR | (none) | No cleanup needed. |

**Why RED produced no failures.** Task 1 is `type="tracer"`, and this plan's own `<execution_flow>` guidance states a tracer "is production-quality, never a throwaway." Task 1's `<action>` text spelled out the *complete* `set_move_effect()` method in four numbered steps — effect-first construction, explicit-vs-derived palette branching with `validate_effect_palette()`, the `apply_theme()` paint, and delegation to `set_effect()` — not a partial slice reserved for later expansion. Every behaviour Task 2's tests exercise (explicit-palette validation, the multi-colour skip, the timeout fallback, the untouched raw path, and error propagation through the unmodified `set_effect()`) was therefore already correctly implemented by Task 1's commit (`e80382f`), before Task 2's tests were ever written.

I investigated this per the fail-fast rule ("Unexpected GREEN in RED phase... the feature may already exist... investigate") before proceeding: I re-read Task 1's action text against the committed implementation, re-derived each Task 2 behaviour by hand against that implementation, and confirmed no code path was missing. This mirrors the exact precedent already recorded in `18-04-SUMMARY.md`'s own TDD Gate Compliance section, where 27 of 28 new tests passed immediately because "Task 1 had already implemented the underlying derivation and wiring; they are regression coverage, not RED targets" — the only difference here is that the *entire* Task 2 suite falls into that category rather than a subset, because Task 1's action text left literally nothing for Task 2 to implement.

`gsd_run check tdd-red-evidence` was not invoked, following the same precedent recorded in `18-03-SUMMARY.md` and `18-04-SUMMARY.md`: it parses `node --test` TAP output and has no pytest-summary parser, so it cannot classify this project's test output.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `set_move_effect()` is fully documented (class docstring, method docstring with an executed example) and ready for plan 07, which documents it in the user guide and migration guide and extends the verbatim-example harness there.
- `tests/test_devices/test_multizone.py` remains untouched, ready for plan 08's import-only `PLC0415` hoist.
- No blockers.

## Self-Check: PASSED

- `src/lifx/devices/multizone.py`: FOUND
- `tests/test_devices/test_multizone_move.py`: FOUND
- Commits `e80382f`, `687209a`, `e957a19`: all FOUND in `git log --oneline --all`
- Plan `<verification>` re-run: `pytest tests/test_devices -q --no-cov` 888 passed, no skips; `test_multizone.py` byte-identical to merge-base; patch-coverage checker `PASS` for `src/lifx/devices/multizone.py` (52 changed executable lines, 18 changed branches)
- Full suite: `4544 passed, 700 deselected`; `ruff check .`, `ruff format --check .` and `pyright` all clean (0 errors)

---
*Phase: 18-typed-move-and-morph-palette-effects*
*Completed: 2026-09-23*
