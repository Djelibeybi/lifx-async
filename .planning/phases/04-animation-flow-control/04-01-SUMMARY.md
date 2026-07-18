---
phase: 04-animation-flow-control
plan: 01
subsystem: testing
tags: [pytest, packets, matrix, ceiling, ack-gating, pyright]

# Dependency graph
requires:
  - phase: 03-flow-control-planning
    provides: RED->GREEN plan cadence pattern (03-01 -> 03-02) reused here
provides:
  - RED branch-matrix suite pinning row-aligned 13x26 large-tile chunking geometry
  - RED branch-matrix suite pinning FLAGS_OFFSET/ACK_REQUIRED_FLAG constants and probe_template_index seam
affects: [04-03-implement-packets-fixes]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "getattr(obj, 'name', sentinel) for RED tests targeting not-yet-existing attributes/properties — keeps pyright strict-clean while pytest still fails on the assertion"

key-files:
  created: []
  modified:
    - tests/test_animation/test_packets.py

key-decisions:
  - "Used getattr with a None sentinel for probe_template_index accesses (not just the two module constants) so pyright strict stays clean against an attribute that doesn't exist until plan 04-03 lands"

patterns-established:
  - "RED-suite attribute access pattern: getattr(target, 'attr_name', None) + assert equals expected value, avoiding both AttributeError-based failures and pyright reportAttributeAccessIssue"

requirements-completed: [ANIM-02, ANIM-04]

coverage:
  - id: D1
    description: "RED branch matrix pins row-aligned 13x26 large-tile chunking: 7 Set64 packets (52x6+26 colours) + 1 CopyFrameBuffer, y offsets 0,4,...,24, row-aligned hsbk_start values; 16x8 and multi-tile invariance guards included"
    requirement: "ANIM-04"
    verification:
      - kind: unit
        ref: "tests/test_animation/test_packets.py::TestMatrixPacketGeneratorRowAlignedChunking (11 tests, 8 RED / 3 invariance-pass)"
        status: pass
    human_judgment: false
  - id: D2
    description: "RED branch matrix pins FLAGS_OFFSET=22 / ACK_REQUIRED_FLAG=0x02 header constants and the full probe_template_index matrix (light/multizone/standard-matrix -> 0; large-tile -> final CopyFrameBuffer)"
    requirement: "ANIM-02"
    verification:
      - kind: unit
        ref: "tests/test_animation/test_packets.py::TestHeaderFlagConstants + TestProbeTemplateIndex (10 tests, 9 RED / 1 invariance-pass)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-16
status: complete
---

# Phase 4 Plan 01: RED Branch-Matrix Suite for Packets Geometry Summary

**RED test suite pinning the row-aligned 13x26 Ceiling chunking fix and the ack-probe attachment seam (`probe_template_index` + header flag constants) that plan 04-03 must turn GREEN.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-16T14:52:00Z (approx)
- **Completed:** 2026-07-16T15:17:52Z
- **Tasks:** 2 completed
- **Files modified:** 1 (`tests/test_animation/test_packets.py`)

## Accomplishments
- Added `TestMatrixPacketGeneratorRowAlignedChunking` (11 tests) pinning the exact row-aligned geometry for the Ceiling 13x26 device: 7 Set64 packets (52 colours x 6 + 26 colours), y offsets `0,4,8,12,16,20,24`, row-aligned `hsbk_start` values, a marker-colour placement test proving today's raw-64 slicing misplaces pixel 52, and multi-tile/16x8 invariance guards.
- Added `TestHeaderFlagConstants` (3 tests) pinning `FLAGS_OFFSET=22` / `ACK_REQUIRED_FLAG=0x02` and an invariance guard that no generator sets the ack flag itself at creation time.
- Added `TestProbeTemplateIndex` (7 tests) pinning the full probe-attachment matrix: light/multizone/standard-matrix generators probe index 0; large-tile mode probes the final CopyFrameBuffer (index 7 for 13x26, index 2 for 16x8, index 15 for the 2-tile 13x26 chain).
- All pre-existing `test_packets.py` tests (53) remain untouched and green.

## Task Commits

Each task was committed atomically:

1. **Task 1: RED tests — row-aligned large-tile chunking for non-64-divisible widths** - `ab98a06` (test)
2. **Task 2: RED tests — header flag constants and probe_template_index seam** - `40aac75` (test)

**Plan metadata:** committed alongside this SUMMARY.

## Files Created/Modified
- `tests/test_animation/test_packets.py` - Added `TestMatrixPacketGeneratorRowAlignedChunking`, `TestHeaderFlagConstants`, `TestProbeTemplateIndex`; added `from lifx.animation import packets` module import for attribute-access RED tests.

## RED Evidence Table

| Class | Test | Status today | Reason |
|---|---|---|---|
| TestMatrixPacketGeneratorRowAlignedChunking | test_packets_per_tile_13x26 | RED (fail) | `packets_per_tile` gives 6, expected 7 |
| TestMatrixPacketGeneratorRowAlignedChunking | test_template_count_13x26 | RED (fail) | 7 templates today, expected 8 |
| TestMatrixPacketGeneratorRowAlignedChunking | test_color_counts_13x26 | RED (fail) | `[64,64,64,64,64,18]` vs expected `[52]*6+[26]` |
| TestMatrixPacketGeneratorRowAlignedChunking | test_y_offsets_13x26 | RED (fail) | only 6 y-offsets exist, missing `24` |
| TestMatrixPacketGeneratorRowAlignedChunking | test_hsbk_start_row_aligned_13x26 | RED (fail) | multiples of 64 vs expected row-aligned values |
| TestMatrixPacketGeneratorRowAlignedChunking | test_final_partial_row_batch_13x26 | RED (fail) | last Set64 y_offset is 20, expected 24 |
| TestMatrixPacketGeneratorRowAlignedChunking | test_rect_geometry_13x26 | PASS (invariance) | fb_index/width byte layout unaffected by fix |
| TestMatrixPacketGeneratorRowAlignedChunking | test_copy_fb_last_13x26 | PASS (invariance) | CopyFrameBuffer structure unaffected by fix |
| TestMatrixPacketGeneratorRowAlignedChunking | test_update_colors_lands_row_aligned_13x26 | RED (fail) | marker colour lands in template 0, not template 1 |
| TestMatrixPacketGeneratorRowAlignedChunking | test_divisible_width_unchanged_16x8 | PASS (invariance) | 64 divides 16 evenly — bug doesn't manifest |
| TestMatrixPacketGeneratorRowAlignedChunking | test_multi_tile_large_13x26 | RED (fail) | 14 templates today, expected 16 |
| TestHeaderFlagConstants | test_flags_offset_constant | RED (fail) | `FLAGS_OFFSET` doesn't exist (getattr -> None) |
| TestHeaderFlagConstants | test_ack_required_flag_constant | RED (fail) | `ACK_REQUIRED_FLAG` doesn't exist (getattr -> None) |
| TestHeaderFlagConstants | test_templates_flags_byte_zero_at_creation | PASS (invariance) | generators never set the flags byte today |
| TestProbeTemplateIndex | test_default_zero_light | RED (fail) | `probe_template_index` doesn't exist |
| TestProbeTemplateIndex | test_default_zero_multizone | RED (fail) | `probe_template_index` doesn't exist |
| TestProbeTemplateIndex | test_standard_matrix_zero | RED (fail) | `probe_template_index` doesn't exist |
| TestProbeTemplateIndex | test_large_tile_13x26_is_final_copyfb | RED (fail) | `probe_template_index` doesn't exist; also depends on Task 1 fix |
| TestProbeTemplateIndex | test_large_tile_16x8_is_final_copyfb | RED (fail) | `probe_template_index` doesn't exist |
| TestProbeTemplateIndex | test_multi_tile_large_is_last_copyfb | RED (fail) | `probe_template_index` doesn't exist; also depends on Task 1 fix |
| TestProbeTemplateIndex | test_probe_index_points_at_copyfb_template | RED (fail) | `probe_template_index` doesn't exist; also depends on Task 1 fix |

**Totals:** 21 new tests — 17 RED (fail today, exit 1, no collection errors) + 4 invariance guards (pass today and after the 04-03 fix).

## Verification Run

```
uv run pytest tests/test_animation/test_packets.py -q -k "RowAlignedChunking"
  -> 8 failed, 3 passed, 53 deselected — EXIT 1

uv run pytest tests/test_animation/test_packets.py -q -k "ProbeTemplateIndex or HeaderFlagConstants"
  -> 9 failed, 1 passed, 64 deselected — EXIT 1

uv run pytest tests/test_animation/test_packets.py -q -k "not RowAlignedChunking and not ProbeTemplateIndex and not HeaderFlagConstants"
  -> 53 passed, 21 deselected — EXIT 0 (zero pre-existing tests modified/broken)

uv run pytest tests/test_animation/test_packets.py -q
  -> 17 failed, 57 passed — EXIT 1 (whole-file totals)

uv run ruff format tests/test_animation/test_packets.py  -> unchanged
uv run ruff check tests/test_animation/test_packets.py --fix  -> All checks passed!
uv run pyright tests/test_animation/test_packets.py  -> 0 errors, 0 warnings, 0 notices
```

## Decisions Made
- Used `getattr(target, "attr_name", None)` (not direct attribute access) for all `probe_template_index` accesses in `TestProbeTemplateIndex`, mirroring the pattern the plan specified only for the two module constants in `TestHeaderFlagConstants`. Direct attribute access (`gen.probe_template_index`) would raise `AttributeError` at test runtime (acceptable for pytest — still exit 1, not a collection error) but fails `pyright --strict` with `reportAttributeAccessIssue` since the property doesn't exist on the class yet. The `getattr` sentinel pattern satisfies both: pytest sees a plain assertion failure (`None == 7` etc.), and pyright sees `Any` from the three-argument `getattr` overload, so it never flags a missing attribute. This was necessary to satisfy the plan's own acceptance criterion ("`uv run pyright ...` are clean") while keeping the suite RED with zero `src/` changes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Extended getattr-sentinel pattern to probe_template_index property accesses**
- **Found during:** Task 2 (header flag constants and probe seam RED tests)
- **Issue:** The plan's action text used direct attribute access (`gen.probe_template_index == N`) for `TestProbeTemplateIndex`, expecting `AttributeError` as the RED signal. Running `uv run pyright` against that draft produced 8 `reportAttributeAccessIssue` errors, violating the task's own acceptance criterion that pyright must be clean.
- **Fix:** Rewrote all 8 `probe_template_index` accesses to use `getattr(gen, "probe_template_index", None)` plus an explicit assertion, matching the pattern the plan already specified for `FLAGS_OFFSET`/`ACK_REQUIRED_FLAG`. No test semantics changed — same RED/GREEN behaviour, same docstrings.
- **Files modified:** `tests/test_animation/test_packets.py`
- **Verification:** `uv run pytest ... -k "ProbeTemplateIndex or HeaderFlagConstants"` still exits 1 with the same 9 RED / 1 pass split; `uv run pyright tests/test_animation/test_packets.py` now reports 0 errors.
- **Committed in:** `40aac75` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — pyright-strict compliance)
**Impact on plan:** Purely mechanical (attribute-access idiom); no change to what geometry/seam is pinned or which tests are RED vs. invariance. No scope creep.

## Issues Encountered
None beyond the pyright deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 04-03 has an exact GREEN target: make `packets_per_tile`/`_create_large_tile_templates` row-aligned (Task 1's 8 RED tests) and add `FLAGS_OFFSET`, `ACK_REQUIRED_FLAG`, and `PacketGenerator.probe_template_index` (Task 2's 9 RED tests), without touching any test in this file.
- The three RED tests depending on both fixes together (`test_large_tile_13x26_is_final_copyfb`, `test_multi_tile_large_is_last_copyfb`, `test_probe_index_points_at_copyfb_template`) are explicitly documented in their docstrings — 04-03 should verify these turn GREEN only after both the chunking fix and the `probe_template_index` property land.
- No blockers for 04-03.

---
*Phase: 04-animation-flow-control*
*Completed: 2026-07-16*

## Self-Check: PASSED

- FOUND: tests/test_animation/test_packets.py
- FOUND: ab98a06 (Task 1 commit)
- FOUND: 40aac75 (Task 2 commit)
