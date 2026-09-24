---
phase: 18-typed-move-and-morph-palette-effects
reviewed: 2026-09-24T00:00:00Z
depth: deep
files_reviewed: 8
files_reviewed_list:
  - AGENTS.md
  - docs/api/devices.md
  - docs/migration/effect-api-changes.md
  - src/lifx/devices/component_state.py
  - src/lifx/devices/matrix.py
  - tests/test_devices/test_effect_palette.py
  - tests/test_devices/test_matrix.py
  - tests/test_devices/test_multizone_move.py
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
status: issues_found
---

# Phase 18: Code Review Report (Incremental — Morph default-palette gap closure)

**Reviewed:** 2026-09-24T00:00:00Z
**Depth:** deep
**Files Reviewed:** 8
**Status:** issues_found

## Summary

This is an incremental review of `git diff 3d12db2..HEAD`, the 18-09 plan closing UAT gap
G-18-1: `MatrixLight.set_effect(FirmwareEffect.MORPH)` with no palette must never send
`palette_count=0`, because real firmware silently ignores that and never starts MORPH. The prior
`18-REVIEW.md` (dated 2026-09-23) already reviewed the earlier phase 18 work and recorded its
resolutions (WR-01 fixed in `5a9d254`, IN-01/IN-02 deliberately left as pre-existing); those
findings are not re-raised here unless this increment reintroduced them, and it did not.

The new code was traced line-by-line against the plan's D-24 to D-28 decisions:

- `sample_effect_palette()` (new, `component_state.py`) implements D-25's sampling rule exactly:
  de-duplicate under `HSBK.__eq__` keeping first-seen order; up to `MAX_PALETTE_COLORS` (16)
  distinct colours returned as-is; otherwise 16 colours sampled at `i * len(colors) //
  MAX_PALETTE_COLORS` for `i` in `range(16)` (using the *original*, pre-dedup pixel count as the
  stride divisor, matching the maintainer's worked 40-pixel example), then de-duplicated in
  sample order. Hand-traced this formula against the plan's three worked examples (40-pixel
  literal indices, the 17-distinct-colours boundary, the 64-pixel `range(0, 64, 4)` case) and
  every one matches. `derive_effect_palette()`'s code is untouched (only its docstring was
  reworded); confirmed by both the plan's own AST-comparison gate and manual inspection.
- `MatrixLight._derive_morph_palette()` now always returns a non-empty `list[HSBK]` or raises: an
  empty flattened colour result raises `LifxProtocolError` naming the device by `self.label or
  self.serial` (never an address, matching T-18-16's mitigation) before any read of the palette
  is used; a single colour still goes through `derive_effect_palette()`; a multi-colour result
  falls through to `sample_effect_palette()`. The `try`/`except (LifxTimeoutError,
  LifxProtocolError)` around the `get_all_tile_colors()` read was deliberately removed (D-26,
  maintainer decision 2026-09-24, reversing the Morph half of `5a9d254`/WR-01 from the prior
  review) — this is flagged in the task prompt as intentional and is not treated as a regression.
  Confirmed the SKY support probe's own, separate timeout handling and
  `MultiZoneLight._derive_move_palette()`'s fallback (Move) are both untouched — `multizone.py`
  and `test_multizone_move.py` have zero functional diff against `3dab68e` (only a one-line
  docstring wording tweak from an earlier, unrelated phase-18 commit, `a1f5594`, predating this
  plan).
- Ran the full `tests/test_devices/test_effect_palette.py` and `tests/test_devices/test_matrix.py`
  suites (104 tests, all pass), `ruff check` and `pyright` on the two changed source files (clean
  on both). Hand-verified `TestSampleEffectPalette`'s pinned pixel indices, the multi-tile
  flattening tests, and the `wraps=`-patched proof that a single colour never calls the sampler
  while a multi-colour device calls it exactly once with the flattened list — all match the
  actual implementation with no drift.
- Checked for PII/real-device-identifier leakage per `AGENTS.md`'s privacy rules: no new lines in
  the diff introduce a live serial, MAC or IP; the emulator fixture identifiers
  (`d073d5000007`, `d073d5010203`) are pre-existing synthetic test values. No em dash was
  introduced in any added prose line. All newly-authored docstring prose correctly uses Australian
  "colour"; the `colors` parameter/variable name is deliberately American, matching the existing,
  previously-reviewed public-API naming convention (see the prior review's IN-01 resolution).

No BLOCKER/Critical or Warning-level defect was found in this increment. The one Info item below
is a documentation-completeness nitpick in the published API reference, not a functional or
security issue.

## Info

### IN-01: Published API reference collapses two distinct raise causes into one clause

**File:** `docs/api/devices.md:375`

**Issue:** The new `### MatrixEffect` paragraph says: "If that read fails, `set_effect()` raises
`LifxTimeoutError` or `LifxProtocolError` and sends nothing." This wording attributes both raised
exception types to a single cause ("that read fails"). In reality there are two distinct causes,
and `matrix.py`'s own docstrings for `_derive_morph_palette()` and `set_effect()` — both updated
in this same diff — correctly separate them: (1) the `get_all_tile_colors()` read itself times out
or returns a malformed reply, and (2) the read *succeeds* but the device legitimately reports zero
tile colours (D-27), which is not a failed read at all but a successful one with nothing to build
a palette from. A reader who consults only the published docs page (rather than the source
docstrings) could reasonably conclude `LifxProtocolError` is raised solely for a malformed-reply
scenario and miss that an empty-but-valid colour report raises it too. This is pre-specified
verbatim in the 18-09 plan's Task 3 action text, so it is not an implementation slip, and it passes
every automated docs gate (none of which check for this specific distinction) — but it is a real,
if narrow, precision gap between the source-of-truth docstrings and the rendered API reference.

**Fix:** Split the sentence to name both causes explicitly, mirroring `_derive_morph_palette()`'s
own docstring:

```markdown
If that read times out or gets a malformed reply, `set_effect()` raises `LifxTimeoutError` or
`LifxProtocolError` respectively and sends nothing; a device that reports no tile colours at all
also raises `LifxProtocolError`, naming the device.
```

---

_Reviewed: 2026-09-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_

## Resolution

- **IN-01:** fixed in `6608c5a`. The MatrixEffect paragraph now names the timeout, the malformed reply and the empty colour report separately, matching `_derive_morph_palette()`'s docstring.
