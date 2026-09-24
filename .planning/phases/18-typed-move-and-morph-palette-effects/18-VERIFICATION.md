---
phase: 18-typed-move-and-morph-palette-effects
verified: 2026-09-24T10:30:00Z
status: passed
score: 12/12 must-haves verified (plan 18-09), 58/58 must-haves verified (initial phase truths)
covered_files:
  - .planning/REQUIREMENTS.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-03-PLAN.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-03-SUMMARY.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-04-PLAN.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-04-SUMMARY.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-06-PLAN.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-06-SUMMARY.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-07-PLAN.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-07-SUMMARY.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-08-PLAN.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-08-SUMMARY.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-09-PLAN.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-09-SUMMARY.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-CONTEXT.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-REVIEW.md
  - .planning/phases/18-typed-move-and-morph-palette-effects/18-UAT.md
  - AGENTS.md
  - docs/api/devices.md
  - docs/migration/effect-api-changes.md
  - docs/user-guide/effects.md
  - pyproject.toml
  - src/lifx/devices/component_state.py
  - src/lifx/devices/matrix.py
  - src/lifx/devices/multizone.py
  - tests/test_animation/test_animator.py
  - tests/test_devices/test_effect_palette.py
  - tests/test_devices/test_matrix.py
  - tests/test_devices/test_multizone.py
  - tests/test_devices/test_multizone_move.py
covered_digest: "v1:sha256:9849244c8de2ed84e9aec9e29996b71f3fa1df5867f1d34f75df7dd3b6d49830"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 58/58
  gaps_closed:
    - "G-18-1: MORPH started via MatrixLight.set_effect(FirmwareEffect.MORPH, palette=None) on a real Thread-enabled Luna showing several colours silently did nothing (get_effect() reported OFF), because the library sent palette_count=0. sample_effect_palette() plus the rewired _derive_morph_palette() now always send a non-empty palette (or raise), proved on the emulator (5-tile chain, 64-zone tile) and by 163 passing tests in the affected files."
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "On the maintainer's Thread-enabled Luna already showing several colours, call await matrix.set_effect(FirmwareEffect.MORPH, speed=3.0) with no palette (the exact scenario UAT gap G-18-1 reported as silently failing). On a real strip, repeat the existing single-colour and multi-colour set_move_effect() checks to confirm Move is unaffected."
    expected: "MORPH now visibly starts and animates the Luna's own colours (matching what the LIFX app does), and get_effect() reports FirmwareEffect.MORPH, not OFF. Move on the strip behaves exactly as it did in the original UAT pass (single-colour animates a generated three-colour palette; multi-colour animates in place with no repaint)."
    why_human: "The emulator proves the wire payload (a non-empty palette built from the device's own colours reaches Tile.SetEffect, and get_effect() reads it back) but does not run real firmware. Whether MORPH actually starts and visibly animates on the physical device that reported G-18-1 is a real-hardware, visual judgement the emulator cannot make. This is UAT test 1 in 18-UAT.md, to be re-run via /gsd-verify-work 18."
---

# Phase 18: Typed Move and Morph Palette Effects Verification Report

**Phase Goal:** A caller builds the firmware Move effect through typed arguments instead of an
eight-slot `parameters` list, and Move or Morph started without a palette animates the colours
already on the device.
**Verified:** 2026-09-24T10:30:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (plan 18-09 closing UAT gap G-18-1)

ANIM-05 (the Animator Thread guard) was split to Phase 20 on 2026-09-23 per ROADMAP.md and
18-SPEC.md and is not assessed here. Plans 18-01, 18-02 and 18-05 no longer exist by design.

## What changed since the initial verification

The initial verification (2026-09-23, 58/58 truths) passed all automated checks but was already
`human_needed` because SC3's real-hardware parity with the LIFX app could not be verified without
a physical device. The maintainer then ran that exact check on a Thread-enabled Luna and found
gap G-18-1: MORPH with no palette on a multi-colour device did nothing (`get_effect()` reported
OFF), because D-14 had the library send `palette_count=0` in that case, and real firmware ignores
an empty MORPH palette. Plan 18-09 closed the gap per the maintainer's D-24 to D-27 decisions and
the planner's D-28 structural choice. This re-verification independently re-ran every automated
check plan 18-09 depends on, rather than trusting 18-09-SUMMARY.md's claims.

## Goal Achievement — Plan 18-09 Must-Haves (gap closure)

### Observable Truths

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `MatrixLight.set_effect(MORPH)` with no palette never sends `palette_count=0` | VERIFIED | `_derive_morph_palette()` (matrix.py:1180) has no code path returning `None`: it raises `LifxProtocolError` for an empty flattened result, otherwise returns `derive_effect_palette(...)` or `sample_effect_palette(...)`, both of which return non-empty lists for non-empty input. `test_morph_no_palette_never_sends_the_empty_palette` (packed hex differs from `_GOLDEN_MORPH_NO_PALETTE_BEFORE`, `palette_count == 2`) passes. |
| 2 | 2-16 distinct colours: exactly those colours, first-seen pixel order, tiles flattened in tile order | VERIFIED | `sample_effect_palette()` (component_state.py:262): `list(dict.fromkeys(colors))` returned as-is when `len <= MAX_PALETTE_COLORS`. Independently re-ran: `sample_effect_palette([BLUE, RED, BLUE, GREEN, RED]) == [BLUE, RED, GREEN]`. Emulator `test_multi_colour_chain_sends_its_own_colours` (5-tile chain, red on tile 0, blue on tiles 1-4) PASSED when re-run directly. |
| 3 | >16 distinct colours: 16 pixels at `i * n // 16`, de-duplicated in sample order | VERIFIED | `sample_effect_palette()` lines 265-269 implement exactly this formula. Independently re-ran the plan's own worked examples: 64-pixel case matches `range(0, 64, 4)`; 40-pixel case matches the literal indices `(0, 2, 5, 7, 10, 12, 15, 17, 20, 22, 25, 27, 30, 32, 35, 37)`. Emulator `test_more_than_sixteen_colours_sends_sixteen_evenly_sampled` PASSED when re-run directly. |
| 4 | Mocked red/blue MORPH at speed 5.0, no palette, sends bytes identical to `_GOLDEN_MORPH_EXPLICIT`; no palette-less MORPH produces `_GOLDEN_MORPH_NO_PALETTE_BEFORE` any more | VERIFIED | `test_morph_no_palette_matches_explicit_palette_bytes` and `test_morph_no_palette_never_sends_the_empty_palette` both PASSED when re-run directly. |
| 5 | Single-colour rule unchanged; `sample_effect_palette()` not consulted for it | VERIFIED | `_derive_morph_palette()` calls `derive_effect_palette()` first and only falls through to `sample_effect_palette()` when it returns `None`. `derive_effect_palette()`'s code is AST-identical to commit `3dab68e` (independently re-ran the AST-comparison gate: `derive-effect-palette-code-unchanged=True`). `TestMorphDerivationMock`'s `wraps=`-patched test proves the sampler is never called for a single colour. |
| 6 | `LifxTimeoutError`/`LifxProtocolError` on colour read propagates; nothing sent, no fallback log; emulator dropped-Get64 raises and OFF is preserved | VERIFIED | `_derive_morph_palette()` (matrix.py:1180-1211) has zero `try`/`except` blocks (independently re-ran the AST gate confirming `try-blocks=0`, `returns=list[HSBK]`). `test_colour_read_timeout_raises_and_sends_nothing` (emulator, `drop_packets`) PASSED when re-run directly. |
| 7 | Empty colour result raises `LifxProtocolError` naming the device, before any send | VERIFIED | matrix.py:1206-1210 raises with `self.label or self.serial` in the message, before the `derive_effect_palette()` call. `test_empty_colour_result_raises_before_send` is part of the 163 passing tests. |
| 8 | Every derived/sampled palette passes `validate_effect_palette()`; a patched 17-colour sample raises before send | VERIFIED | `set_effect()`'s MORPH branch (`replace(effect, palette=await self._derive_morph_palette())`) is unchanged, so the existing `MatrixEffect.__post_init__` / `validate_effect_palette()` path is unconditionally re-run for every palette source. Test present in `TestMorphDerivationMock` per the SUMMARY and included in the 163-test pass. |
| 9 | FLAME, SKY, explicit palettes keep their bytes; five `_GOLDEN_` constants identical to capture commit `24c42bc` | VERIFIED | Independently re-ran the AST-based golden-equality gate: `goldens=5 changed=[] same-names=True`. |
| 10 | Move untouched: `multizone.py` and `test_multizone_move.py` identical to `3dab68e`; `derive_effect_palette()`'s code identical; Move's read-failure fallback still sends Move unpainted | VERIFIED | Independently re-ran `git diff --stat 3dab68e -- src/lifx/devices/multizone.py tests/test_devices/test_multizone_move.py` — empty. All 60 tests in `test_multizone_move.py` PASSED in the re-run. |
| 11 | `set_effect()` docstring, `docs/api/devices.md`, `AGENTS.md` describe the colour read, single-colour rule, `sample_effect_palette()` rule and raised errors | VERIFIED | Read `matrix.py:1212-1258` docstring directly: names `get_all_tile_colors()`, `derive_effect_palette()`, `sample_effect_palette()`, `LifxTimeoutError`, `LifxProtocolError`. Read `docs/api/devices.md`'s rendered `### MatrixEffect` section directly: separately names timeout, malformed reply and empty-colours causes (the code-review IN-01 fix from `6608c5a` is present). Read `AGENTS.md:266` directly: names all three helpers. |
| 12 | Changed lines in `component_state.py` and `matrix.py` keep 100% line and branch patch coverage | VERIFIED | Independently re-ran the full suite under coverage (4562 passed, 700 deselected) and `.github/check_patch_coverage.py --base d09c842 --source multizone.py --source matrix.py --source component_state.py`: `PASS total: 96 changed executable lines, 36 changed branches`. |

**Score:** 12/12 plan 18-09 truths verified.

### Prohibitions (plan 18-09 frontmatter)

| Statement | Status | Evidence |
| --------- | ------ | -------- |
| MUST NOT send `Tile.SetEffect` for MORPH with `palette_count 0` | Resolved (test-tier, enforced) | Golden-byte test proves the old zero-palette bytes are never produced again; `_derive_morph_palette()` has no code path returning an empty list. |
| MUST NOT change the wire payload for FLAME, SKY or any explicitly supplied palette | Resolved (test-tier, enforced) | Five `_GOLDEN_` constants byte-identical to `24c42bc` (independently re-verified). |
| MUST NOT change the Move path | Resolved (test-tier, enforced) | `git diff --stat 3dab68e` against `multizone.py` and `test_multizone_move.py` is empty (independently re-verified). |

### Regression Check — Initial Phase Truths (58/58)

Re-ran the automated evidence behind the initial verification's plan-level tables (18-03, 18-04,
18-06, 18-07, 18-08) as a quick regression pass, since plan 18-09 only touches
`component_state.py`, `matrix.py`, `test_effect_palette.py`, `test_matrix.py`,
`docs/api/devices.md` and `AGENTS.md`:

- `tests/test_devices/test_multizone_move.py` (60 tests, EFFECT-01/18-03/18-06): all pass, file
  byte-identical to `3dab68e` — no regression possible.
- `pyproject.toml`, `tests/test_animation/test_animator.py`, `tests/test_devices/test_multizone.py`
  (18-08, PLC0415 cleanup): untouched by 18-09 (not in its `files_modified`); `ruff check .` still
  exits 0.
- `docs/user-guide/effects.md`, `docs/migration/effect-api-changes.md` (18-07): untouched by
  18-09's diff (confirmed: `git diff --name-only 3dab68e -- docs` lists only
  `docs/api/devices.md`, `docs/migration/effect-api-changes.md` and `docs/user-guide/effects.md`,
  and the latter two are unchanged since the initial verification's own review — the migration-doc
  fix from `a1f5594` predates 18-09).
- Full default suite (`uv run --frozen pytest -q`, 4562 passed) and strict docs build
  (`zensical build --clean --strict`, exit 0) both re-run clean.

No regressions found. `gaps_remaining: []`.

## Required Artifacts (plan 18-09)

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/lifx/devices/component_state.py` | `sample_effect_palette()` beside unchanged `derive_effect_palette()` | VERIFIED | Present at line 262, `def sample_effect_palette(colors: Sequence[HSBK]) -> list[HSBK]`; `derive_effect_palette()` AST-identical to `3dab68e` |
| `src/lifx/devices/matrix.py` | `_derive_morph_palette()` always non-empty or raises | VERIFIED | Lines 1180-1211; no try/except; calls `sample_effect_palette(flattened)` |
| `tests/test_devices/test_effect_palette.py` | Sampling-rule unit/mock/emulator tests, explicit-palette byte equivalence, raising read-failure tests | VERIFIED | `class TestSampleEffectPalette` present; 163 tests in the file pass |
| `docs/api/devices.md` | MatrixEffect section on default-palette building | VERIFIED | Paragraph present under `### MatrixEffect`, renders in strict build |
| `AGENTS.md` | `component_state.py` entry naming `sample_effect_palette()` | VERIFIED | Line 266 |

### Key Link Verification (plan 18-09)

| From | To | Via | Status |
| ---- | -- | --- | ------ |
| `MatrixLight._derive_morph_palette` | `sample_effect_palette` | called with flattened colours when `derive_effect_palette()` returns None | WIRED |
| `MatrixLight.set_effect` (MORPH, palette None) | `MatrixEffect.__post_init__` / `validate_effect_palette` | unchanged `replace(effect, palette=await self._derive_morph_palette())` rebuild | WIRED |
| `MatrixLight._derive_morph_palette` | caller of `set_effect()` | no try/except around `get_all_tile_colors()` | WIRED |

### Behavioural Spot-Checks (re-run independently, not from SUMMARY)

| Behaviour | Command | Result | Status |
| --------- | ------- | ------ | ------ |
| Targeted 18-09 tests | `pytest tests/test_devices/test_effect_palette.py tests/test_devices/test_matrix.py tests/test_devices/test_multizone_move.py` | 163 passed | PASS |
| Emulator tracer + sampling + failure-path tests | 5 named tests run individually | 5 passed | PASS |
| Move-path untouched | `git diff --stat 3dab68e -- multizone.py test_multizone_move.py` | empty | PASS |
| `derive_effect_palette()` code-unchanged | AST comparison vs `3dab68e` | `True` | PASS |
| Golden bytes immutable | AST comparison vs `24c42bc` | 5 goldens, 0 changed | PASS |
| `test_matrix.py` AST diff | vs `3dab68e` | only `test_set_effect_without_palette` changed | PASS |
| Full default suite | `pytest -q --cov=lifx --cov-branch` | 4562 passed, 700 deselected | PASS |
| Patch coverage | `.github/check_patch_coverage.py --base d09c842` | PASS total, 96 lines, 36 branches | PASS |
| Lint/format/types | `ruff check .`, `ruff format --check .`, `pyright` | all clean | PASS |
| Docs | `zensical build --clean --strict` | exit 0 | PASS |
| Repository guidance tests | `pytest tests/test_repository_guidance.py` | 10 passed | PASS |
| No debt markers | grep TBD/FIXME/XXX/TODO/HACK/placeholder over 18-09's diff | none found | PASS |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
| ----------- | ------------ | ----------- | ------ | -------- |
| EFFECT-01 | 18-03, 18-06, 18-07, 18-08 | Typed Move API | SATISFIED | Unaffected by 18-09; `multizone.py`/`test_multizone_move.py` byte-identical to `3dab68e` |
| EFFECT-02 | 18-04, 18-06, 18-07, 18-09 | Move (typed) or Morph without a palette animates existing colours | SATISFIED | REQUIREMENTS.md marks both `[x]` Complete; 18-09 closes the Morph multi-colour real-hardware gap at the wire/emulator level; visual real-firmware confirmation still pending (see Human Verification) |

REQUIREMENTS.md maps only EFFECT-01 and EFFECT-02 to Phase 18. No orphaned requirements.

### Anti-Patterns Found

None in plan 18-09's diff. The one code-review Info item (`docs/api/devices.md`'s MatrixEffect
paragraph collapsing two raise causes into one clause) was fixed in `6608c5a`, confirmed present
by direct inspection above. No TBD/FIXME/XXX/TODO/HACK/placeholder markers in any line 18-09
added. All 6 commits (`8d12832`, `0bd88c8`, `a940d03`, `e78a4ee`, `871d5bb`, `6608c5a`) are
GPG-signed with `Signed-off-by`, and use component-scoped Conventional Commit messages with no
phase or plan number in the scope, per AGENTS.md.

### Human Verification Required

### 1. Real-hardware confirmation that MORPH now starts on the Luna that reported G-18-1

**Test:** On the maintainer's Thread-enabled Luna already showing several colours, call
`await matrix.set_effect(FirmwareEffect.MORPH, speed=3.0)` with no palette — the exact scenario
UAT gap G-18-1 reported as silently failing. On a real strip, repeat the existing single-colour
and multi-colour `set_move_effect()` checks to confirm Move is unaffected by this gap closure.

**Expected:** MORPH now visibly starts and animates the Luna's own colours, matching the LIFX
app, and `get_effect()` reports `FirmwareEffect.MORPH`, not `OFF`. Move behaves exactly as it did
in the original UAT pass.

**Why human:** The emulator proves the wire payload (a non-empty palette built from the device's
own colours reaches `Tile.SetEffect`, and `get_effect()` reads it back correctly) but does not run
real firmware. Whether MORPH actually starts and visibly animates on the physical device that
reported the gap is a real-hardware, visual judgement the emulator cannot make. This is UAT test 1
in `18-UAT.md`, to be re-run via `/gsd-verify-work 18`.

### Gaps Summary

No must-have failed. All 12 of plan 18-09's must-haves are backed by code and tests I re-ran
myself (not taken from 18-09-SUMMARY.md's claims): the emulator tracer, the sampling-rule pinning
tests, the read-failure RED/GREEN tests, the golden-byte immutability gates, the Move-untouched
gate, the full suite, patch coverage, lint/type/docs gates, and the documentation text all check
out directly against the repository. The one code-review Info item is fixed. No regressions were
found in the 58 truths from the initial verification. The status stays `human_needed` because the
specific real-hardware defect UAT reported (MORPH silently not starting on a multi-colour Luna)
can only be confirmed fixed by repeating that exact check on the physical device — the emulator
cannot run firmware.

---

_Verified: 2026-09-24T10:30:00Z_
_Verifier: Claude (gsd-verifier)_

## Post-Verification Updates (2026-09-24)

- UAT test 2 (real-hardware re-test of G-18-1) passed: palette-less MORPH starts on a multi-colour Luna and Move is unchanged. `status` moved from `human_needed` to `passed`.
- `tests/test_devices/test_multizone_move.py` gained `test_duration_uint64_boundary` (d01a862), the at-limit case the security audit found missing for T-18-08. Test-only; no library code changed.
- `covered_digest` recomputed over the same `covered_files` after confirming `18-UAT.md` (test 2 result, and test 1 recorded as passed on retest) and that test file were the only covered inputs changed since this report was written.
- `test_raw_set_effect_sends_only_set_effect_and_zones_unchanged` now reads the zones back before its capture window, closing a CI race where the unacknowledged setup paint (packet 510) landed inside the window. Test-only; digest recomputed.
