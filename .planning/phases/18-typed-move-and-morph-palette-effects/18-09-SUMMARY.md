---
phase: 18-typed-move-and-morph-palette-effects
plan: 09
subsystem: devices
tags: [matrix, morph, palette, firmware-effect, emulator, gap-closure]

# Dependency graph
requires:
  - phase: 18-typed-move-and-morph-palette-effects (plan 04)
    provides: "derive_effect_palette(colors, min_kelvin, max_kelvin) -> list[HSBK] | None and validate_effect_palette(palette) -> None in component_state.py"
  - phase: 18-typed-move-and-morph-palette-effects (plan 07)
    provides: "AGENTS.md component_state.py entry naming derive_effect_palette()/validate_effect_palette(), and the phase-wide docs/split-boundary/coverage gates this plan re-runs"
provides:
  - "sample_effect_palette(colors) -> list[HSBK] -- Morph's multi-colour palette rule (D-25): up to 16 distinct colours in first-seen order, otherwise 16 evenly sampled pixels de-duplicated in sample order"
  - "MatrixLight._derive_morph_palette() always returns a non-empty palette or raises LifxTimeoutError/LifxProtocolError -- MORPH never sends palette_count=0 again (D-24, D-26, D-27)"
  - "docs/api/devices.md MatrixEffect section and AGENTS.md component_state.py entry describing the closed gap"
affects: []

# Actuals (#2632)
actuals:
  tokens: 8525
  tasks: 3
  commits: 5
  plan_head_before: da23276504143a976f3973cc641c2f7d21bcef65

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fallback-through-a-second-pure-helper: derive_effect_palette() keeps its single-colour contract unchanged (None means 'not one colour'), and the caller falls through to a second pure helper (sample_effect_palette()) rather than adding a mode flag that would leak a Morph-only policy into a function Move shares -- reusable wherever two callers need different fallback behaviour from one shared rule"
    - "Even-sampling-then-dedup: MAX_PALETTE_COLORS pixels sampled at i * n // MAX_PALETTE_COLORS, then de-duplicated in sample order rather than distinct-then-sample -- guarantees a bounded, deterministic sample size regardless of how many distinct colours the input contains"

key-files:
  created: []
  modified:
    - src/lifx/devices/component_state.py
    - src/lifx/devices/matrix.py
    - tests/test_devices/test_effect_palette.py
    - tests/test_devices/test_matrix.py
    - docs/api/devices.md
    - AGENTS.md

key-decisions:
  - "sample_effect_palette() dedups on the ORIGINAL colour count (n = len(colors)) for the sampling stride, not the pre-deduplicated distinct count, per D-25's literal 'i * n // 16' formula -- confirmed against the maintainer's 40-pixel worked example before writing the implementation"
  - "The RED test for the read-failure raise mocks LifxTimeoutError/LifxProtocolError directly (unittest.mock side_effect) rather than driving the raise through the emulator, keeping the parametrised case fast; the emulator drop_packets scenario is reserved for the end-to-end raise-and-leaves-OFF case, matching the plan's own split between the two test method names"
  - "GREEN commit uses a fix(devices) scope rather than feat(devices): AGENTS.md's commit-type table treats this as a bug fix (D-26 reverses commit 5a9d254's over-wide catch), not a new feature, and the project's own scope rules forbid phase/plan numbers as Conventional Commit scopes"

requirements-completed: [EFFECT-02]

coverage:
  - id: D1
    description: "sample_effect_palette() implements the full D-25 sampling rule: up to 16 distinct colours in first-seen order (HSBK.__eq__/uint16 wire equality), otherwise 16 colours at pixel index i * n // 16 for i in 0..15, de-duplicated in sample order; an empty input returns an empty list; derive_effect_palette()'s code stays AST-identical to 3dab68e"
    requirement: "EFFECT-02"
    verification:
      - kind: unit
        ref: "tests/test_devices/test_effect_palette.py::TestSampleEffectPalette"
        status: pass
      - kind: other
        ref: "AST-parsed derive_effect_palette() code-unchanged gate (matches 3dab68e signature/body, docstring excluded)"
        status: pass
    human_judgment: false
  - id: D2
    description: "MatrixLight._derive_morph_palette() always returns a non-empty palette or raises: an empty flattened colour result raises LifxProtocolError naming the device before any send; a non-empty multi-colour result falls through derive_effect_palette() -> sample_effect_palette() when the single-colour rule does not apply; proved end-to-end on the emulated 5-tile chain (tracer) and the 64-zone tile (Task 2)"
    requirement: "EFFECT-02"
    verification:
      - kind: unit
        ref: "tests/test_devices/test_effect_palette.py::TestMorphDerivationMock"
        status: pass
      - kind: integration
        ref: "tests/test_devices/test_effect_palette.py::TestMorphDefaultPaletteEmulator::test_multi_colour_chain_sends_its_own_colours"
        status: pass
      - kind: integration
        ref: "tests/test_devices/test_effect_palette.py::TestMorphDefaultPaletteEmulator::test_more_than_sixteen_colours_sends_sixteen_evenly_sampled"
        status: pass
    human_judgment: false
  - id: D3
    description: "A failed colour read (LifxTimeoutError or LifxProtocolError) when MORPH starts with no palette propagates to the caller with nothing sent and no palette log record; on the emulator a dropped Get64 raises LifxTimeoutError and leaves the device on OFF, proved with a genuine RED (three failing test items) before the GREEN commit removed the try/except"
    requirement: "EFFECT-02"
    verification:
      - kind: unit
        ref: "tests/test_devices/test_effect_palette.py::TestMorphDerivationMock::test_failed_colour_read_raises_before_send"
        status: pass
      - kind: integration
        ref: "tests/test_devices/test_effect_palette.py::TestMorphDefaultPaletteEmulator::test_colour_read_timeout_raises_and_sends_nothing"
        status: pass
    human_judgment: false
  - id: D4
    description: "FLAME, SKY, every explicit palette and the entire Move path (multizone.py, test_multizone_move.py, derive_effect_palette()'s code) are byte-for-byte and behaviourally unchanged from their pre-gap-closure state; the five _GOLDEN_ constants equal their 24c42bc capture"
    requirement: "EFFECT-02"
    verification:
      - kind: other
        ref: "git diff --stat 3dab68e -- src/lifx/devices/multizone.py tests/test_devices/test_multizone_move.py (empty)"
        status: pass
      - kind: other
        ref: "AST-parsed golden-constant equality gate against 24c42bc (all 5 unchanged)"
        status: pass
    human_judgment: false
  - id: D5
    description: "docs/api/devices.md's MatrixEffect section and AGENTS.md's component_state.py entry describe the closed gap; the full default suite (4562 passed), strict docs build, added-lines prose/em-dash gate, changelog-untouched gate, split-boundary gate and 100% branch patch coverage on multizone.py/matrix.py/component_state.py all pass"
    requirement: "EFFECT-02"
    verification:
      - kind: other
        ref: "uv run --frozen zensical build --clean --strict; uv run --frozen llmstxt-standalone validate"
        status: pass
      - kind: other
        ref: ".github/check_patch_coverage.py -> PASS total (96 changed executable lines, 36 changed branches)"
        status: pass
      - kind: unit
        ref: "tests/test_repository_guidance.py"
        status: pass
    human_judgment: true
    rationale: "The plan's own <verification> block requires /gsd-verify-work 18 to re-run UAT test 1 on real hardware (a Thread-enabled Luna) to confirm MORPH visibly starts and morphs -- that is real-hardware human judgment this executor cannot perform."

# Metrics
duration: ~35min
completed: 2026-09-24
status: complete
---

# Phase 18 Plan 09: Morph Multi-Colour Palette Gap Closure Summary

**Closes UAT gap G-18-1: `MatrixLight.set_effect(MORPH, palette=None)` now always sends a non-empty palette built from the device's own colours (or raises), because real firmware never starts MORPH with `palette_count=0`.**

## Performance

- **Duration:** ~35 min
- **Started:** ~2026-09-23T23:35:00Z
- **Completed:** 2026-09-24T00:01:29Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- `sample_effect_palette(colors)` in `component_state.py`, placed directly after `derive_effect_palette()`: de-duplicates under `HSBK.__eq__` (uint16 wire equality) keeping first-seen order; up to `MAX_PALETTE_COLORS` (16) distinct colours are returned as-is; more than 16 samples 16 pixels at index `i * n // 16` for `i` in `range(16)` and de-duplicates the sample in sample order. `derive_effect_palette()`'s code stays AST-identical to 3dab68e; only its docstring was reworded so `None` no longer promises "send no palette" (it now points to `sample_effect_palette()` as Morph's fallback).
- `MatrixLight._derive_morph_palette()` now always returns a non-empty palette or raises: an empty flattened colour result raises `LifxProtocolError` naming the device (by label or serial) before any send; a single colour still gets the generated three-colour palette from `derive_effect_palette()`; a multi-colour device now falls through to `sample_effect_palette()` instead of returning `None`. The MORPH branch in `set_effect()` is unchanged, so the sampled palette is revalidated by `validate_effect_palette()` exactly like a caller-supplied one.
- Task 3 (`tdd="true"`) proved the read-failure behaviour change with a genuine RED: two tests were rewritten to expect a raise instead of a silent fallback, ran red (3 failing test items: "DID NOT RAISE"), committed on their own, then the GREEN commit deleted `_derive_morph_palette()`'s `try`/`except` around `get_all_tile_colors()` and narrowed its return type from `list[HSBK] | None` to `list[HSBK]`. A failed colour read (`LifxTimeoutError` or `LifxProtocolError`) now propagates to `set_effect()`'s caller with nothing sent; the SKY support probe's own timeout handling and Move's read-failure fallback (`MultiZoneLight._derive_move_palette()`) are untouched.
- An emulator tracer (Task 1) proves the fix end-to-end: a 5-tile chain painted red on tile 0 and blue on tiles 1-4 reports `[Colors.RED, Colors.BLUE]` as its MORPH palette through `get_effect()`, in first-seen order, exactly what a real Luna needed to start morphing. Task 2 adds a second emulator proof on a real 64-zone tile: 64 distinct hues sample down to the colours at pixels 0, 4, 8 ... 60. Task 3's emulator test proves the failure path: a dropped Get64 (`scenario_manager` drop_packets) raises `LifxTimeoutError` and leaves the device on OFF, both before and after the scenario clears.
- `TestSampleEffectPalette` (Task 2) pins every clause of the maintainer's rule by hand-written pixel indices, never recomputed from the `i * n // 16` formula: first-seen order, uint16-identical colours counting once, the 16/17-colour boundary, the 40-pixel literal indices from the maintainer's own worked example, de-duplication of a sampled duplicate, and the case where sampling collapses 17 distinct hues down to one colour. `TestMorphDerivationMock` gained multi-tile flattening tests (two tiles of 32 distinct hues; three tiles with cross-tile duplicates) and `wraps=`-patched proof that a single colour never calls the sampler while a multi-colour device calls it exactly once with the flattened list.
- `docs/api/devices.md`'s `### MatrixEffect` section and `AGENTS.md`'s `component_state.py` entry now describe the palette rule: `sample_effect_palette()` alongside `derive_effect_palette()` and `validate_effect_palette()`, and the raised errors on a failed or empty colour read.

## Task Commits

Each task was committed atomically; Task 3 (`tdd="true"`) split into RED, GREEN and docs commits per the TDD gate:

1. **Task 1 (tracer): the helper, wiring and end-to-end proof** - `8d12832` (fix) - `sample_effect_palette()`, `_derive_morph_palette()` wiring, all test updates the change turned red, and the emulator tracer
2. **Task 2: pin the sampling rule** - `0bd88c8` (test) - `TestSampleEffectPalette` plus mock/emulator coverage for multi-tile flattening, the sampler being called or not, and the more-than-16-colours emulator case. Touches only `tests/test_devices/test_effect_palette.py`, confirmed by the commit-scope verify gate.
3. **Task 3 RED: expect the raise** - `a940d03` (test) - two tests rewritten to expect `LifxTimeoutError`/`LifxProtocolError` instead of a silent fallback; 3 test items failed against the pre-GREEN code
4. **Task 3 GREEN: raise instead of falling back** - `e78a4ee` (fix) - removes the `try`/`except` in `_derive_morph_palette()`, narrows its return type
5. **Task 3 docs: describe the gap closure** - `871d5bb` (docs) - `docs/api/devices.md` MatrixEffect paragraph and the `AGENTS.md` `component_state.py` entry

**Plan metadata:** committed separately after this summary (see below).

## Files Created/Modified

- `src/lifx/devices/component_state.py` - Adds `sample_effect_palette()`; rewords `derive_effect_palette()`'s docstring (code unchanged) and the module docstring's second paragraph.
- `src/lifx/devices/matrix.py` - `_derive_morph_palette()` raises `LifxProtocolError` for an empty colour result, falls through to `sample_effect_palette()` when `derive_effect_palette()` returns `None`, and (Task 3) no longer catches `LifxTimeoutError`/`LifxProtocolError` around the read; `set_effect()`'s `palette` docstring entry and Raises section updated to match.
- `tests/test_devices/test_effect_palette.py` - Renames and rewrites the goldens/mock/emulator tests the behaviour change affects, adds `TestSampleEffectPalette` and the multi-tile/sampler-usage/oversized-sample cases to `TestMorphDerivationMock`, adds the 64-colour emulator test, and rewrites the two read-failure tests to expect a raise.
- `tests/test_devices/test_matrix.py` - `test_set_effect_without_palette`'s final assertion now expects `[Colors.RED, Colors.BLUE]` instead of `None`; only its docstring and one comment in `test_set_effect_other_effects_skip_the_gate` reworded (confirmed by an AST diff gate: no other function's body changed).
- `docs/api/devices.md` - New paragraph in `### MatrixEffect` describing the palette rule and the raised errors.
- `AGENTS.md` - `component_state.py` entry widened to name `sample_effect_palette()`.

## Decisions Made

- `sample_effect_palette()`'s sampling stride uses `n = len(colors)` (the original, pre-deduplication pixel count), not the count of already-distinct colours, exactly matching D-25's `i * n // 16` formula. Confirmed against the maintainer's 40-pixel worked example (indices 0, 2, 5, 7, 10, 12, 15, 17, 20, 22, 25, 27, 30, 32, 35, 37) before writing the implementation.
- The GREEN commit uses a `fix(devices)` scope rather than `feat(devices)`, since removing the over-wide `except` clause (which commit `5a9d254` had introduced) is a bug fix per D-26, not new functionality.
- The RED tests mock `LifxTimeoutError`/`LifxProtocolError` directly via `AsyncMock(side_effect=...)` for the fast parametrised unit case, and drive the raise through a real dropped `Get64` (`scenario_manager` `drop_packets`) for the emulator end-to-end case — matching the plan's own split between the two renamed test methods.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## TDD Gate Compliance

Task 3 (`tdd="true"`) followed RED -> GREEN with a separate docs commit (no source REFACTOR needed):

| Gate | Commit | Evidence |
|------|--------|----------|
| RED | `a940d03` | `test(devices): expect a failed Morph colour read to raise` — exactly 3 test items failed against the pre-change code: `TestMorphDefaultPaletteEmulator::test_colour_read_timeout_raises_and_sends_nothing` and both parametrised cases of `TestMorphDerivationMock::test_failed_colour_read_raises_before_send`, all with the intentional assertion failure `Failed: DID NOT RAISE LifxTimeoutError`/`LifxProtocolError` — not a collection or fixture crash. |
| GREEN | `e78a4ee` | `fix(devices): raise when the Morph colour read fails` — all 163 tests across `test_effect_palette.py`, `test_matrix.py` and `test_multizone_move.py` pass; full suite 4562 passed. Uses a `fix` type per this project's commit-type table (bug fix, not new feature) rather than the generic `feat` the tdd.md reference names — CLAUDE.md/AGENTS.md project convention takes precedence. |
| REFACTOR | (none) | No cleanup needed after GREEN; the docs update landed as its own `docs(devices)` commit per the plan's own three-commit structure for this task. |

**`gsd_run check tdd-red-evidence` was not invoked**, following the precedent recorded in `18-04-SUMMARY.md`: it parses `node --test` TAP output and has no pytest-summary parser. RED evidence was confirmed directly from pytest's own report (`-rf` failure list showing exactly the three target test items, each failing on the named assertion, not a fixture or import error).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- UAT gap G-18-1 is closed in code, tests and docs. `/gsd-verify-work 18` should re-run UAT test 1 on real hardware (the maintainer's Thread-enabled Luna) to confirm MORPH now visibly starts and morphs on a multi-colour device, and that Move on a real strip is unaffected.
- The five `_GOLDEN_` constants, `derive_effect_palette()`'s code, and the entire Move path (`multizone.py`, `test_multizone_move.py`) remain byte-for-byte and behaviourally unchanged, so no other phase's work is disturbed.
- No blockers.

## Self-Check: PASSED

- `src/lifx/devices/component_state.py`: FOUND
- `src/lifx/devices/matrix.py`: FOUND
- `tests/test_devices/test_effect_palette.py`: FOUND
- `tests/test_devices/test_matrix.py`: FOUND
- `docs/api/devices.md`: FOUND
- `AGENTS.md`: FOUND
- Commits `8d12832`, `0bd88c8`, `a940d03`, `e78a4ee`, `871d5bb`: all FOUND in `git log --oneline --all`
- Plan `<verification>` re-run: `uv run --frozen pytest tests/test_devices -q --no-cov` 906 passed; full suite `uv run --frozen pytest -q` 4562 passed, 700 deselected; patch-coverage checker `PASS total` for `multizone.py`/`matrix.py`/`component_state.py` (96 changed executable lines, 36 changed branches); strict `zensical build` and `llmstxt-standalone validate` both pass; golden and `derive_effect_palette()` immutability gates both pass; Move path (`multizone.py`, `test_multizone_move.py`) diff against 3dab68e is empty

---
*Phase: 18-typed-move-and-morph-palette-effects*
*Completed: 2026-09-24*
