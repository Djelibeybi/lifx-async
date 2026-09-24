---
phase: 18-typed-move-and-morph-palette-effects
plan: 04
subsystem: devices
tags: [matrix, morph, palette, firmware-effect, emulator]

# Dependency graph
requires: []
provides:
  - "derive_effect_palette(colors, min_kelvin, max_kelvin) -> list[HSBK] | None -- shared firmware-effect default-palette rule (D-13 to D-18, D-22)"
  - "validate_effect_palette(palette) -> None -- shared palette size rule (non-empty, at most MAX_PALETTE_COLORS)"
  - "MatrixLight._derive_morph_palette() and the MORPH-only default-palette branch in set_effect() (D-13, D-14, D-19, D-23)"
  - "MatrixEffect._validate_palette delegates to validate_effect_palette"
  - "Five golden Tile.SetEffect payloads pinning FLAME/SKY/explicit-palette/pre-change-MORPH bytes"
affects: [18-06, 18-07]

# Actuals (#2632)
actuals:
  tokens: 8479
  tasks: 2
  commits: 6
  plan_head_before: 4ea0709

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Rebuild-through-replace(): a derived value is applied with dataclasses.replace(effect, palette=...) rather than a post-construction attribute assignment, so the dataclass's own __post_init__ validates it exactly like caller-supplied input -- reusable wherever a computed field must pass the same validation as a user-supplied one"
    - "Golden-payload regression testing: capture wire bytes from the unmodified code in a test-only commit before touching src/, then prove immutability with a git-log ancestry + AST-parsed-constant-equality gate"
    - "Timeout-as-fallback, not failure: a best-effort read (get_all_tile_colors() before MORPH) that times out logs at DEBUG and the caller-requested action proceeds anyway, mirroring the existing SKY support probe -- a fire-and-forget effect send is never turned into a hard failure by an optional read"

key-files:
  created:
    - tests/test_devices/test_effect_palette.py
  modified:
    - src/lifx/devices/component_state.py
    - src/lifx/devices/matrix.py
    - tests/test_devices/test_matrix.py

key-decisions:
  - "derive_effect_palette() lives in component_state.py next to is_dark()/hsk_matches() per D-22, unchanged from the plan's placement"
  - "The MORPH branch rebuilds the effect with dataclasses.replace(effect, palette=await self._derive_morph_palette()) rather than assigning effect.palette after construction, so the derived palette is revalidated by the same rule as a caller's (review L131@92a657d, maintainer item L543@92a657d)"
  - "validate_effect_palette() was added to component_state.py one commit earlier than the plan's Task/Task split (in the Task 1 helper commit, 64a8a92, rather than Task 2) -- purely an ordering choice with no functional difference, since Task 2 still owns the MatrixEffect delegation and its own test coverage"
  - "'Single colour' is decided by HSBK.__eq__ (uint16 wire equality) rather than hsk_matches(), matching D-17's stricter, no-perceptual-tolerance rule"

requirements-completed: [EFFECT-02]

coverage:
  - id: D1
    description: "Five golden Tile.SetEffect payloads (FLAME/SKY with no palette, MORPH/FLAME with an explicit palette, MORPH with no palette) captured from the unmodified set_effect() and pinned immutable in a test-only commit that precedes the derivation"
    requirement: "EFFECT-02"
    verification:
      - kind: unit
        ref: "tests/test_devices/test_effect_palette.py::TestTileSetEffectGoldens"
        status: pass
      - kind: other
        ref: "AST-parsed golden-constant equality + git merge-base ancestry gate (Task 1 verify block)"
        status: pass
    human_judgment: false
  - id: D2
    description: "derive_effect_palette() implements the full R10 rule: hued colour generates hue +/-45 degrees wrapped modulo 360; white colour generates whites at the device's min/max kelvin, falling back to 1500/9000 K when unknown; 'single colour' is HSBK.__eq__ (uint16, no tolerance); an empty or multi-colour input derives nothing"
    requirement: "EFFECT-02"
    verification:
      - kind: unit
        ref: "tests/test_devices/test_effect_palette.py::TestDeriveEffectPalette"
        status: pass
    human_judgment: false
  - id: D3
    description: "MatrixLight.set_effect() derives a default MORPH palette only when effect_type is MORPH and palette is None, after MatrixEffect(...) construction (so argument validation runs first), applying the result with dataclasses.replace(); a colour-read timeout logs at DEBUG and still sends the effect with no palette, mirroring the SKY support probe"
    requirement: "EFFECT-02"
    verification:
      - kind: unit
        ref: "tests/test_devices/test_effect_palette.py::TestMorphDerivationMock"
        status: pass
      - kind: integration
        ref: "tests/test_devices/test_effect_palette.py::TestMorphDefaultPaletteEmulator"
        status: pass
    human_judgment: false
  - id: D4
    description: "MatrixEffect._validate_palette() and MultiZoneEffect's future palette validation (plan 06) share one size rule, validate_effect_palette(); the derived palette is proven to pass through it via a wraps= patch, and a patched 17-colour derivation raises before any packet is sent"
    requirement: "EFFECT-02"
    verification:
      - kind: unit
        ref: "tests/test_devices/test_effect_palette.py::TestValidateEffectPalette"
        status: pass
      - kind: unit
        ref: "tests/test_devices/test_effect_palette.py::TestMorphDerivationMock::test_derived_palette_passes_through_shared_validator"
        status: pass
    human_judgment: false
  - id: D5
    description: "FLAME, SKY and any explicitly supplied palette are byte-identical to before the change and never read the device's colours; a device already showing more than one colour, or an empty colour result, still sends palette_count=0"
    requirement: "EFFECT-02"
    verification:
      - kind: unit
        ref: "tests/test_devices/test_effect_palette.py::TestMorphDerivationMock::test_flame_sky_and_explicit_palette_never_read_colours"
        status: pass
      - kind: unit
        ref: "tests/test_devices/test_effect_palette.py::TestMorphDerivationMock::test_empty_colour_result_sends_no_palette"
        status: pass
      - kind: integration
        ref: "tests/test_devices/test_matrix.py::TestSkyEffectFirmwareGate::test_set_effect_without_palette"
        status: pass
    human_judgment: false

# Metrics
duration: 25min
completed: 2026-09-23
status: complete
---

# Phase 18 Plan 04: Morph Default Palette Summary

**MatrixLight.set_effect(MORPH, palette=None) now reads the device's own colours and animates them, generating a three-colour palette only when every colour is identical, sharing one `derive_effect_palette()`/`validate_effect_palette()` rule with the multizone Move path plan 06 will build.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-09-23T09:12:30Z
- **Completed:** 2026-09-23T09:37:30Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- `derive_effect_palette(colors, min_kelvin, max_kelvin)` in `component_state.py`, next to `is_dark()`/`hsk_matches()`: derives `None` (send the colours already shown) for an empty or multi-colour input, and a three-colour palette for a single colour — whites at the device's kelvin range (falling back to 1500/9000 K) for a white, or hue +/-45 degrees wrapped modulo 360 for a hued colour.
- `validate_effect_palette(palette)`, the one size rule (non-empty, at most 16 colours) `MatrixEffect._validate_palette` now delegates to, ready for `MultiZoneEffect`'s future palette validation in plan 06.
- `MatrixLight._derive_morph_palette()` and the MORPH-only branch in `set_effect()`: reads `get_all_tile_colors()` only when `effect_type == FirmwareEffect.MORPH and palette is None`, after `MatrixEffect(...)` construction so argument validation still runs first, and applies the result with `dataclasses.replace(effect, palette=...)` so the derived palette is revalidated exactly like a caller-supplied one. A `LifxTimeoutError` reading the colours logs at DEBUG and the effect is still sent with no palette, mirroring the existing SKY support probe.
- Five golden `Tile.SetEffect` payloads, captured from the unmodified `set_effect()` in a test-only commit before any `src/` change, pin FLAME/SKY-with-no-palette, MORPH/FLAME-with-an-explicit-palette and pre-change MORPH-with-no-palette byte-for-byte. A verify gate parses the constants at the capture commit and at HEAD and fails if any of the five values changed, and fails unless the capture commit is a strict ancestor of the first commit adding `_derive_morph_palette()`.
- An emulator tracer test proves a single hued colour on a real emulated tile gets the exact three-colour palette the rule predicts; two further emulator tests prove a multi-tile chain showing several colours derives nothing, and a single white gets whites at the device's own registry kelvin range (2500/9000 K for product 55, not the generic 1500/9000 K fallback); a `drop_packets` scenario on Get64 proves the timeout fallback against a real dropped packet.
- The two existing `test_matrix.py` tests that assumed the old unconditional "MORPH always sends `palette_count=0`" behaviour (`test_set_effect_without_palette`, `test_set_effect_other_effects_skip_the_gate`) now explicitly set up a multi-colour device before asserting that behaviour, with no other change to the file (confirmed by a removed-non-docstring-lines gate: 0 lines removed).

## Task Commits

Task 2 carries `tdd="true"`, so its RED and GREEN phases are separate commits. Task 1 (`type="tracer"`) is production-quality and split into four Conventional Commits per the plan's own instructions (goldens, helper, wiring, tracer test):

1. **Task 1a: golden capture** - `24c42bc` (test) - five `_GOLDEN_*` payloads pinned against the unmodified `set_effect()`
2. **Task 1b: shared helper** - `64a8a92` (feat) - `derive_effect_palette()` and `validate_effect_palette()` added to `component_state.py`, not yet wired into any device method
3. **Task 1c: wiring** - `24f0f7e` (feat) - `_derive_morph_palette()` and the MORPH branch in `set_effect()`, plus the two `test_matrix.py` fixes and the golden case's multi-colour stub
4. **Task 1d: tracer test** - `3a56bcd` (test) - `TestMorphDefaultPaletteEmulator` proving the single-hued-colour case end-to-end on the emulator
5. **Task 2 RED** - `4b03cb8` (test) - failing tests for the remaining R10 edges and the validator delegation (1 failed, 27 passed — see TDD Gate Compliance below)
6. **Task 2 GREEN** - `570df4a` (feat) - `MatrixEffect._validate_palette` delegates to `validate_effect_palette`; docstrings widened

No REFACTOR commit: the GREEN implementation needed no cleanup pass.

**Plan metadata:** committed separately after this summary (see below).

## Files Created/Modified

- `src/lifx/devices/component_state.py` - Adds `derive_effect_palette()`, `validate_effect_palette()`, `_EFFECT_PALETTE_HUE_STEP`; widens the module docstring.
- `src/lifx/devices/matrix.py` - Adds `MatrixLight._derive_morph_palette()`; wires the MORPH-only default-palette branch into `set_effect()` via `dataclasses.replace()`; delegates `MatrixEffect._validate_palette` to the shared rule; widens `set_effect()`'s `palette` docstring entry; drops the now-unused `MAX_PALETTE_COLORS` import.
- `tests/test_devices/test_effect_palette.py` - New file: five golden payload constants, `TestTileSetEffectGoldens`, `TestMorphDefaultPaletteEmulator` (tracer plus three further emulator cases), `TestDeriveEffectPalette`, `TestValidateEffectPalette`, `TestMorphDerivationMock`.
- `tests/test_devices/test_matrix.py` - `test_set_effect_without_palette` and `test_set_effect_other_effects_skip_the_gate` updated to a multi-colour device precondition; no other change.

## Golden Capture

Captured with `uv run --frozen python` against the unmodified `set_effect()`, before any change to `matrix.py`, in commit `24c42bc` (which touches nothing under `src/`):

| Constant | Hex payload |
|---|---|
| `_GOLDEN_FLAME_NO_PALETTE` | `00000000000003b80b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d` |
| `_GOLDEN_SKY_NO_PALETTE` | `00000000000005b80b0000000000000000000000000000000000000200000032000000b4000000000000000000000000000000000000000000000000000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d` |
| `_GOLDEN_MORPH_EXPLICIT` | `0000000000000288130000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000020000ffffffffac0dabaaffffffffac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d` |
| `_GOLDEN_FLAME_EXPLICIT` | `00000000000003b80b0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000020000ffffffffac0d9c1bffffffffac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d` |
| `_GOLDEN_MORPH_NO_PALETTE_BEFORE` | `00000000000002b80b000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d000000000000ac0d` |

## Decisions Made

- **D-22 placement confirmed:** `derive_effect_palette()` and `validate_effect_palette()` stay in `component_state.py`, unchanged from the plan.
- **Validator added one commit early, no functional change:** `validate_effect_palette()` landed in the Task 1 helper commit (`64a8a92`) rather than waiting for Task 2. Task 2 still owns and tests the `MatrixEffect._validate_palette` delegation itself, so no acceptance criterion or verify gate was affected — logged here for transparency, not as a correctness deviation.
- **"Single colour" uses `HSBK.__eq__`, not `hsk_matches()`:** per D-17, deliberately stricter (uint16, no perceptual tolerance, brightness included) than the existing `hsk_matches()` helper, which ignores brightness.

## Deviations from Plan

None materially — plan executed as written. One organisational note (validator commit landed one commit early) is recorded under Decisions Made above; it changed no acceptance criterion, verify gate, or test outcome.

## Issues Encountered

None.

## TDD Gate Compliance

Task 2 (`tdd="true"`) followed RED -> GREEN with no REFACTOR needed:

| Gate | Commit | Evidence |
|------|--------|----------|
| RED | `4b03cb8` | `test(devices): add failing tests for the shared palette validator delegation` — 1 failed, 27 passed. The one failure, `TestMorphDerivationMock::test_derived_palette_passes_through_shared_validator`, raised `AttributeError: <module 'lifx.devices.matrix' ...> does not have the attribute 'validate_effect_palette'` from `unittest.mock.patch()` — an intentional failure demonstrating the exact delegation this task adds, per the tdd.md guidance that a patch target's absence is a legitimate RED for the behaviour under test. The other 27 new tests already passed because Task 1 had already implemented the underlying derivation and wiring; they are regression coverage, not RED targets, and their being green in the RED commit does not violate the fail-fast rules (no target test passed unexpectedly). |
| GREEN | `570df4a` | `feat(devices): delegate MatrixEffect palette validation to the shared rule` — all 28 tests in `test_effect_palette.py` pass, all 60 in `test_matrix.py` pass, full suite 4529 passed. |
| REFACTOR | (none) | No cleanup needed after GREEN. |

**`gsd_run check tdd-red-evidence` was not invoked**, following the precedent recorded in `18-03-SUMMARY.md`: it parses `node --test` TAP output and has no pytest-summary parser, so it cannot classify this project's test output. RED evidence was confirmed directly from pytest's own report (1 failed / 27 passed, the one failure a named `AttributeError` on the target test — not a collection or fixture crash).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `derive_effect_palette()` and `validate_effect_palette()` are ready for plan 06's `MultiZoneLight.set_move_effect()`, which reuses both per D-22 and the R9 palette rule.
- The golden-payload pattern (test-only capture commit, immutability gate, ancestry gate) and the `_matrix_light()`-style mocked-device helper are reusable for plan 06's own tests.
- No blockers.

## Self-Check: PASSED

- `src/lifx/devices/component_state.py`: FOUND
- `src/lifx/devices/matrix.py`: FOUND
- `tests/test_devices/test_effect_palette.py`: FOUND
- `tests/test_devices/test_matrix.py`: FOUND
- Commits `24c42bc`, `64a8a92`, `24f0f7e`, `3a56bcd`, `4b03cb8`, `570df4a`: all FOUND in `git log --oneline --all`
- Plan `<verification>` re-run: `pytest tests/test_devices -q --no-cov` 873 passed; full suite `4529 passed, 700 deselected`; patch-coverage checker `PASS` for both `component_state.py` (22 changed executable lines, 10 changed branches) and `matrix.py` (10 changed executable lines, 0 changed branches)

---
*Phase: 18-typed-move-and-morph-palette-effects*
*Completed: 2026-09-23*
