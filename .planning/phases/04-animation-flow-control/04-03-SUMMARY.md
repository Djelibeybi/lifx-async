---
phase: 04-animation-flow-control
plan: 03
subsystem: animation
tags: [packets, matrix, ceiling, row-alignment, ack-probe, pyright]

# Dependency graph
requires:
  - phase: 04-animation-flow-control
    provides: "04-01's RED branch-matrix suite (TestMatrixPacketGeneratorRowAlignedChunking, TestHeaderFlagConstants, TestProbeTemplateIndex) — the exact GREEN target this plan closes"
provides:
  - "Row-aligned large-tile chunking in MatrixPacketGenerator (fixes ANIM-04's latent 13-wide-tile bug)"
  - "FLAGS_OFFSET/ACK_REQUIRED_FLAG header constants + PacketGenerator.probe_template_index seam that plan 04-04's Animator wiring consumes"
affects: [04-04-animator-ack-gate-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Row-aligned chunking: rows_per_packet = 64 // tile_width; packets_per_tile = ceil(tile_height / rows_per_packet); per-packet color_start = y_offset * tile_width (mirrors devices/matrix.py set_matrix_colors)"
    - "probe_template_index property: default 0 on the PacketGenerator ABC; MatrixPacketGenerator overrides to the final CopyFrameBuffer index in large-tile mode"

key-files:
  created: []
  modified:
    - src/lifx/animation/packets.py
    - src/lifx/animation/__init__.py

key-decisions:
  - "D4-04 encoded in code: large-tile mode attaches the ack probe to the final CopyFrameBuffer template (frame-commit packet) rather than the first Set64 — matches Glowup's proven field behaviour on >64-zone ceilings and gives a strictly better congestion signal (CopyFB ack RTT includes the drain of the preceding Set64 burst). probe_template_index is documented as the one-line fallback seam to index 0 should the ANIM-04 hardware UAT (plan 04-07) disagree."
  - "Removed the dead zero-count guard (and its pragma) in _create_large_tile_templates: ceiling division on packets_per_tile guarantees the final packet always covers at least one row, so the guard was unreachable."

requirements-completed: [ANIM-02, ANIM-04]

coverage:
  - id: D1
    description: "Row-aligned _create_large_tile_templates: 13x26 now produces 7 Set64 (52x6+26 colours, y offsets 0,4,...,24, row-aligned hsbk_start) + 1 CopyFrameBuffer = 8 packets/tile; 16x8 shape unchanged (2x64 + CopyFB)"
    requirement: "ANIM-04"
    verification:
      - kind: unit
        ref: "tests/test_animation/test_packets.py::TestMatrixPacketGeneratorRowAlignedChunking (11/11 pass)"
        status: pass
    human_judgment: false
  - id: D2
    description: "FLAGS_OFFSET=22, ACK_REQUIRED_FLAG=0x02 constants; PacketGenerator.probe_template_index (default 0) + MatrixPacketGenerator override (final CopyFrameBuffer in large-tile mode, D4-04); generators never set the ack flag themselves at creation"
    requirement: "ANIM-02"
    verification:
      - kind: unit
        ref: "tests/test_animation/test_packets.py::TestHeaderFlagConstants + TestProbeTemplateIndex (10/10 pass)"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-17
status: complete
---

# Phase 4 Plan 03: Row-Aligned Chunking + Probe-Attachment Seam Summary

**Fixed the latent large-tile chunking bug (raw 64-pixel colour slicing vs row-aligned rect offsets) that garbled frames on any tile width not dividing 64, and added the FLAGS_OFFSET/ACK_REQUIRED_FLAG/probe_template_index seam that plan 04-04's Animator wiring consumes — closing the full 04-01 RED suite (21 tests) with zero test edits.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-17 (approx)
- **Completed:** 2026-07-17
- **Tasks:** 2 completed
- **Files modified:** 2 (`src/lifx/animation/packets.py`, `src/lifx/animation/__init__.py`)

## Accomplishments

- Fixed `MatrixPacketGenerator._create_large_tile_templates` and `packets_per_tile` to chunk row-aligned: `rows_per_packet = 64 // tile_width`, `packets_per_tile = ceil(tile_height / rows_per_packet)`, per-packet `color_start = y_offset * tile_width`. The Ceiling 13x26 now correctly produces 7 Set64 packets (52 colours x 6 + 26 colours) with y offsets `0,4,8,12,16,20,24` + 1 CopyFrameBuffer = 8 packets/frame, matching the device's row-major Set64 fill order. The 16x8 shape is unchanged (2x64 + CopyFB) since 64 divides 16 evenly.
- Removed the now-dead zero-count guard (and its `# pragma: no cover`) — ceiling division guarantees the final packet always covers at least one row.
- Updated the `MatrixPacketGenerator` class docstring with the corrected 16x8 example, the new 13x26 example, and the row-alignment rule.
- Added `FLAGS_OFFSET = 22` and `ACK_REQUIRED_FLAG = 0x02` module constants beside `SEQUENCE_OFFSET`.
- Added `PacketGenerator.probe_template_index` (concrete property on the ABC, default `0`) and overrode it in `MatrixPacketGenerator` to return the final CopyFrameBuffer's index (`tile_count * (packets_per_tile + 1) - 1`) in large-tile mode, with the D4-04 decision and rationale recorded verbatim in the docstring.
- Exported `FLAGS_OFFSET` from `lifx.animation` alongside `SEQUENCE_OFFSET`. Did NOT export any `AckGate`-related names (internal facility per D4-02, not yet built — that's plan 04-04's job).

## Task Commits

Each task was committed atomically:

1. **Task 1: Row-aligned large-tile chunking in MatrixPacketGenerator** - `bb14b15` (fix)
2. **Task 2: Header flag constants + probe_template_index seam** - `180a845` (feat)

**Plan metadata:** committed alongside this SUMMARY.

## Files Created/Modified

- `src/lifx/animation/packets.py` - Row-aligned `packets_per_tile`/`_create_large_tile_templates`; `FLAGS_OFFSET`/`ACK_REQUIRED_FLAG` constants; `PacketGenerator.probe_template_index` + `MatrixPacketGenerator` override; docstring updates.
- `src/lifx/animation/__init__.py` - Added `FLAGS_OFFSET` to imports and `__all__`.

## GREEN Evidence

```
uv run pytest tests/test_animation/test_packets.py -q -k "RowAlignedChunking or MatrixPacketGenerator"
  -> 37 passed, 37 deselected  (Task 1 verify)

uv run pytest tests/test_animation/test_packets.py -q
  -> 74 passed  (whole file — the full 04-01 RED suite is GREEN, zero test edits)

uv run ruff format src/lifx/animation/packets.py src/lifx/animation/__init__.py
  -> 2 files left unchanged

uv run ruff check src/lifx/animation/
  -> All checks passed!

uv run pyright src/lifx/animation/
  -> 0 errors, 0 warnings, 0 notices

git status --porcelain tests/ src/lifx/network/ src/lifx/const.py
  -> (empty — scope guard satisfied, D4-05)

git diff --stat bb14b15~1..180a845
  -> src/lifx/animation/__init__.py |  2 ++
     src/lifx/animation/packets.py  | 39 +++++++++++++++++++++++++++++++++++++++
     2 files changed, 41 insertions(+)
```

Confirmed the 17 originally-failing tests from 04-01's RED evidence table are now
all passing:
- All 8 RED tests in `TestMatrixPacketGeneratorRowAlignedChunking` → pass (Task 1)
- Both RED tests in `TestHeaderFlagConstants` → pass (Task 2)
- All 7 RED tests in `TestProbeTemplateIndex` → pass (Task 2, including the 3
  tests depending on both fixes: `test_large_tile_13x26_is_final_copyfb`,
  `test_multi_tile_large_is_last_copyfb`, `test_probe_index_points_at_copyfb_template`)

The 4 pre-existing invariance guards from 04-01 (`test_rect_geometry_13x26`,
`test_copy_fb_last_13x26`, `test_divisible_width_unchanged_16x8`,
`test_templates_flags_byte_zero_at_creation`) continued to pass throughout.

## D4-04 Decision Record (as encoded in code)

Recorded verbatim in `MatrixPacketGenerator.probe_template_index`'s docstring
(`src/lifx/animation/packets.py`): in large-tile mode the ack probe attaches to
the **final CopyFrameBuffer** template — the frame-commit packet, since nothing
is visible until the buffer swap. This matches Glowup's proven field behaviour
on >64-zone ceilings. The CopyFB's ack RTT includes the device's drain of the
preceding Set64 burst, a strictly better congestion signal than acking the
first Set64 of a multi-packet frame. Hardware-validated in the ANIM-04 UAT
(plan 04-07). The property itself is documented as the one-line fallback seam
to index 0 (first Set64) should hardware disagree. Standard (≤64px) tiles,
multizone, and light generators keep probing index 0 — the exact arm spike 003
measured at 0.0% concurrent-query loss (D4-01), with no per-family carve-outs
(D4-02).

## Deviations from Plan

None — plan executed exactly as written. Both tasks matched the plan's action
steps precisely (formula, docstring content, override logic, exports).

## Auth Gates

None encountered.

## Known Stubs

None — this plan only touches packet-geometry and a metadata property; no new
UI/data-flow surfaces were introduced.

## Threat Flags

None — the row-aligned fix tightens the existing T-04-04 mitigation (self-
inflicted rect/colour misalignment) recorded in this plan's own threat model;
`probe_template_index` reads existing prebaked template state and introduces
no new network-facing surface (it only tells the not-yet-built Animator facility
in plan 04-04 which already-prebaked template to flag).

## Issues Encountered

None. `test_flow.py` (04-02's RED suite, needs plan 04-04's `flow.py`
`AckGate` module) and the 19 04-02 animator gating/probe-baking tests in
`test_animator.py` remain RED as expected — confirmed via `git stash` that
these failures are identical before and after this plan's commits (pre-
existing, not a regression introduced here). Not in scope for 04-03 per the
execution context brief.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 04-04 can now build the `AckGate` facility and wire it into `Animator`,
  consuming `packets.FLAGS_OFFSET`, `packets.ACK_REQUIRED_FLAG`, and
  `generator.probe_template_index` to bake the ack-required flag once at
  init, per D4-03.
- ANIM-04's correctness prerequisite (row-aligned 13x26 chunking) is closed;
  the hardware hasn't been touched yet — plan 04-07's UAT will validate the
  CopyFB probe-attachment decision on the real Ceiling Capsule.
- No blockers for 04-04.

---
*Phase: 04-animation-flow-control*
*Completed: 2026-07-17*

## Self-Check: PASSED

- FOUND: src/lifx/animation/packets.py
- FOUND: src/lifx/animation/__init__.py
- FOUND: bb14b15 (Task 1 commit)
- FOUND: 180a845 (Task 2 commit)
