---
phase: 18-typed-move-and-morph-palette-effects
plan: 08
subsystem: testing
tags: [ruff, plc0415, lint, test-hygiene]

# Dependency graph
requires:
  - phase: 18-typed-move-and-morph-palette-effects (plans 03, 06)
    provides: "Evidence that tests/test_devices/test_multizone.py was byte-identical to the merge-base while its PLC0415 ignore was still present, recorded before this plan's import-only edit"
provides:
  - "tests/test_devices/test_multizone.py and tests/test_animation/test_animator.py with every function-local import hoisted to module scope"
  - "The Phase 16 D-05 PLC0415 handoff closed for both of Phase 18's owned test paths, with the two per-file-ignore lines deleted from pyproject.toml"
affects: []

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 2453
  tasks: 2
  commits: 2
plan_head_before: c29da66ce5bbb99fdbfcc5cc4e3e856e219edcb1

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Import-only diff gate: an ast/difflib gate maps every changed non-blank line to an Import/ImportFrom node's line span in both the merge-base and working-tree versions, so a mechanical hoist sweep can be proven to have touched nothing but import placement"

key-files:
  created: []
  modified:
    - tests/test_devices/test_multizone.py
    - tests/test_animation/test_animator.py
    - pyproject.toml

key-decisions:
  - "Hoisted the two test_multizone.py imports by merging their names into the existing module-scope protocol_types import block rather than adding a second import statement, avoiding a duplicate import of the same module"
  - "Hoisted all 18 test_animator.py sites (inspect, struct, lifx.animation, MirrorLight, MatrixLight, MultiZoneLight) into the module's existing import block, adding HEADER_SIZE to the existing lifx.animation.packets import rather than a new line"

requirements-completed: [EFFECT-01]

coverage:
  - id: D1
    description: "Every function-local import in tests/test_animation/test_animator.py and tests/test_devices/test_multizone.py is hoisted to module scope, both per-file-ignore entries are deleted from pyproject.toml, and ruff check . exits 0"
    requirement: "EFFECT-01"
    verification:
      - kind: other
        ref: "uv run --frozen ruff check . -> All checks passed! (ruff-exit=0)"
        status: pass
      - kind: other
        ref: "uv run --frozen ruff check --isolated --select PLC0415 tests/test_animation tests/test_devices/test_multizone.py -> All checks passed!"
        status: pass
    human_judgment: false
  - id: D2
    description: "PLC0415 is proven active on both swept paths via a stdin probe (exit 1, PLC0415 reported) under each filename"
    requirement: "EFFECT-01"
    verification:
      - kind: other
        ref: "stdin probe against tests/test_animation/_plc0415_probe.py and tests/test_devices/test_multizone.py -> both probe-exit=1, RULE-ACTIVE-ON-BOTH-PATHS"
        status: pass
    human_judgment: false
  - id: D3
    description: "No test was lost or added: the sorted --collect-only -qq node-ID sets for both paths are identical before and after the sweep (263 node IDs each), captured under set -o pipefail with a clean-tree precondition"
    requirement: "EFFECT-01"
    verification:
      - kind: other
        ref: "diff .cache/phase-18/nodeids-before.txt .cache/phase-18/nodeids-after.txt -> empty; before=263 after=263 NODEID-SETS-EQUAL"
        status: pass
      - kind: unit
        ref: "uv run --frozen pytest tests/test_devices/test_multizone.py -q -> 63 passed"
        status: pass
    human_judgment: false
  - id: D4
    description: "Both swept test files differ from the merge-base only inside import statements — an ast/difflib diff gate maps every changed non-blank line to an Import/ImportFrom node's line span and reports zero NON-IMPORT-CHANGE lines"
    requirement: "EFFECT-01"
    verification:
      - kind: other
        ref: "ast/difflib import-only diff gate over tests/test_animation/test_animator.py and tests/test_devices/test_multizone.py -> swept-files=[both], non-import-changes=0, SWEEP-DIFF-IMPORT-ONLY"
        status: pass
    human_judgment: false
  - id: D5
    description: "ruff check --fix and ruff format ran only on the owned paths per task, never on the repository root, and every phase commit touching a swept path or pyproject.toml touches nothing else"
    requirement: "EFFECT-01"
    verification:
      - kind: other
        ref: "sweep-commit confinement history check over git merge-base HEAD main..HEAD -> sweep-commits=2 SWEEP-CONFINED-TO-OWNED-PATHS"
        status: pass
    human_judgment: false
  - id: D6
    description: "The pyproject.toml handoff comment states the new count of unswept paths (five) and keeps Phase 19's tests/test_theme/** sentence intact"
    requirement: "EFFECT-01"
    verification:
      - kind: other
        ref: "manual read of pyproject.toml:90-96 after the edit: comment says 'these five paths are not yet swept', names Phase 19's tests/test_theme/** deletion, keeps src/**, .planning/** and the two archived skill-harness sentences"
        status: pass
    human_judgment: false
  - id: D7
    description: "Full default suite passes, ruff format --check and pyright are clean after the sweep"
    requirement: "EFFECT-01"
    verification:
      - kind: other
        ref: "uv run --frozen pytest -p no:cacheprovider --no-cov -q -> 4545 passed, 700 deselected; uv run --frozen ruff format --check . -> 295 files already formatted; uv run --frozen pyright -> zero errors, zero warnings, zero notices"
        status: pass
    human_judgment: false

# Metrics
duration: 20min
completed: 2026-09-23
status: complete
---

# Phase 18 Plan 8: PLC0415 Test Import Hoist Summary

**Hoisted all 20 function-local imports across `tests/test_devices/test_multizone.py` (2 sites) and `tests/test_animation/test_animator.py` (18 sites) to module scope, then deleted both per-file-ignore lines from `pyproject.toml`, closing the Phase 16 D-05 PLC0415 handoff for Phase 18's owned test paths with zero tests lost and zero non-import changes.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-09-23T10:24:00Z
- **Completed:** 2026-09-23T10:44:14Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `tests/test_devices/test_multizone.py`'s two function-local imports (`MultiZoneEffectParameter`, `MultiZoneEffectSettings` inside `TestMultiZoneEffect.test_get_effect` and `test_get_effect_when_off`) are merged into the existing module-scope `from lifx.protocol.protocol_types import (...)` block; the `tests/test_devices/test_multizone.py` per-file-ignore line is deleted from `pyproject.toml`.
- `tests/test_animation/test_animator.py`'s 18 function-local imports (`inspect` x3, `struct` + `HEADER_SIZE` from `lifx.animation.packets`, `lifx.animation`, `MirrorLight` from `lifx.devices.mirror`, and `MatrixLight`/`MultiZoneLight` across 11 sites) are hoisted into the module's existing import block; the `tests/test_animation/**` per-file-ignore line is deleted from `pyproject.toml` and its handoff comment rewritten to name five remaining unswept paths.
- `uv run --frozen ruff check .` exits 0 with neither Phase 18 per-file-ignore entry present; the repository-wide `PLC0415` rule now covers both of this phase's test paths with no suppression comment anywhere under `tests/`.
- A stdin probe containing a function-local import, linted under each swept filename, is reported as `PLC0415` (exit 1) proving the rule is genuinely active rather than vacuously passing.
- The before/after `--collect-only -qq` node-ID sets for both paths are byte-identical (263 node IDs each): no test was de-collected or added by the mechanical sweep.
- An ast/difflib diff gate proves both swept files differ from the merge-base only inside `Import`/`ImportFrom` node line spans — zero non-import changes (no assertion, fixture, test body, docstring or comment touched).
- Every phase commit touching a swept path or `pyproject.toml` touches nothing else (`SWEEP-CONFINED-TO-OWNED-PATHS`), because `ruff check --fix`/`ruff format` were run scoped to each task's owned path only, never against `.` or the repository root.
- The full default suite passes (4545 passed, 700 deselected), and `ruff format --check .` and `pyright` are both clean.

## Task Commits

1. **Task 1 (tracer): test_multizone.py hoist and ignore deletion** - `2f0be2f` (test)
2. **Task 2: test_animation tree sweep and ignore deletion** - `da1597c` (test)

**Plan metadata:** committed separately after this summary (see below).

## Files Created/Modified

- `tests/test_devices/test_multizone.py` - Two function-local imports merged into the module-scope `protocol_types` import block; no other line changed.
- `tests/test_animation/test_animator.py` - 18 function-local imports (across `inspect`, `struct`, `lifx.animation`, `lifx.animation.packets.HEADER_SIZE`, `lifx.devices.mirror.MirrorLight`, `lifx.devices.matrix.MatrixLight`, `lifx.devices.multizone.MultiZoneLight`) hoisted into the module's existing import block; no other line changed.
- `pyproject.toml` - Both Phase 18 `PLC0415` per-file-ignore entries deleted (`tests/test_devices/test_multizone.py` in Task 1, `tests/test_animation/**` in Task 2); the handoff comment above `[tool.ruff.lint.per-file-ignores]` rewritten to name the five remaining unswept paths and keep Phase 19's `tests/test_theme/**` sentence intact.

## Decisions Made

- Merged the hoisted names into each file's existing module-scope import statement (adding to the `protocol_types` import in `test_multizone.py`, and to the `lifx.animation.packets` import for `HEADER_SIZE` in `test_animator.py`) rather than adding parallel new import lines, avoiding duplicate imports of the same module.
- Left the `# Mock StateEffect response` comments in `test_multizone.py` in place above the code they still describe, per the plan's instruction not to touch non-import lines.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The Phase 16 D-05 `PLC0415` handoff is fully closed for Phase 18: both owned test paths (`tests/test_animation/**`, `tests/test_devices/test_multizone.py`) are now under the repository-wide rule with no exemption.
- Five per-file-ignore paths remain (`src/**`, `.planning/**`, `tests/test_theme/**`, `.agents/skills/**`, `.claude/skills/**`); `tests/test_theme/**` is Phase 19's own handoff line and was untouched here.
- This was the last plan of Phase 18. EFFECT-01 was already recorded complete by plan 18-07 (D-12's own truth was carried as part of that plan's phase-wide gate); this plan's requirements-completed lists EFFECT-01 again per its own frontmatter, and the shared-ID gate will only re-mark it complete if it was not already so — no action needed either way.
- No blockers.

## Self-Check: PASSED

- `tests/test_devices/test_multizone.py`: FOUND, contains merged `protocol_types` import with no function-local import remaining
- `tests/test_animation/test_animator.py`: FOUND, contains `import inspect` at module scope
- `pyproject.toml`: FOUND, neither `tests/test_animation/**` nor `tests/test_devices/test_multizone.py` PLC0415 entry present
- Commits `2f0be2f`, `da1597c`: both FOUND in `git log --oneline --all`
- Plan `<verification>` re-run: `uv run --frozen ruff check .` exits 0; before/after node-ID sets for both paths identical (263 each); import-only diff gate reports `SWEEP-DIFF-IMPORT-ONLY` with zero non-import changes; every phase sweep commit confined to owned paths; full default suite passes (4545 passed, 700 deselected); `ruff format --check .` and `pyright` both clean

---
*Phase: 18-typed-move-and-morph-palette-effects*
*Completed: 2026-09-23*
