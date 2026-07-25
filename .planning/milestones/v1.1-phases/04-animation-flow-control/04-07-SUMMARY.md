---
phase: 04-animation-flow-control
plan: 07
subsystem: testing
tags: [hardware-uat, anim-04, ceiling-capsule, superseded, never-executed]

# ─── NOT A COMPLETION RECORD ───────────────────────────────────────────────
# This plan was NEVER executed. It was superseded in full before dispatch.
# It is closed out, not completed. See "Why this file exists" below.
status: superseded
executed: false              # zero tasks ran; zero commits; no artifact produced
superseded_by: ["04-12", "04-13"]
closed_out: 2026-07-17       # date of the 04-13 operator ruling

# This plan completed NO requirements. Its ANIM-04 claim was resolved elsewhere
# (04-12 Capsule sweep session + 04-13 operator ruling) — see "Requirement disposition".
requirements-completed: []

requires:
  - phase: 04-animation-flow-control (04-05, 04-06)
    provides: the harness and Tiles baseline this plan would have built on
provides: []                 # nothing — this plan produced no artifact
affects: []

key-files:
  created: []                # 04-UAT-CEILING.json was never created
  modified: []
---

# Phase 04, Plan 07 — Closed out as SUPERSEDED (never executed)

**ANIM-04 Ceiling Capsule UAT: superseded in full before dispatch. Its headless measurement was covered by the Capsule's own 04-12 sweep session, and its operator visual checkpoint landed on 04-13 Task 4. ANIM-04 was ultimately resolved by operator ruling, not by this plan.**

## Why this file exists

This is a **closure record, not a completion record**. It exists for two reasons:

1. **To stop this plan being re-executed.** The ROADMAP says "do not execute this plan", but that is prose — nothing enforced it. `/gsd-execute-phase` skips plans where `has_summary: true`, so this file makes the supersession a gate rather than a comment.
2. **To let the phase read as complete on disk.** GSD counts a phase complete only when every `*-PLAN.md` has a matching `*-SUMMARY.md` (`plan-scan.cjs`: `completed = planCount > 0 && summaryCount >= planCount`). It has no concept of a superseded plan, so without this file Phase 4 reads `11/13 → completed=false` **permanently**, and any disk-derived count (`state sync`) silently reports 2 completed phases instead of 3.

**Read `status: superseded` / `executed: false`, not the summary count.** A tool inferring "13 summaries ⇒ 13 plans executed" would be wrong: **11 of Phase 4's 13 plans were executed.** This plan ran none of its tasks.

## What actually happened

Nothing was dispatched. There are **no `04-07` execution commits** in the repository, and the plan's declared artifact `04-UAT-CEILING.json` was **never created** — both consistent with a plan that never ran.

### Task 1 — Headless ANIM-04 measurement (Ceiling Capsule, power-on first) — **superseded**

Covered instead by the Ceiling Capsule's own session in **04-12**'s cross-device paired sweep, which measured the same large-matrix framebuffer path (row-aligned `Set64` + `CopyFrameBuffer` per frame) on the same hardware.

### Task 2 — Operator visual verdict, Ceiling streaming — **superseded**

Its intended owner, 04-12 Task 5, was skipped when the sweep returned an aggregate FAIL. Visual ownership passed to **04-13 Task 4**, where the operator gave an explicit dual verdict on the Capsule, verbatim: *"Geometry was fine. It was as smooth as the tiles. No multi-second freezes but it stuttered throughout."* The operator approved with the observation recorded — geometry PASS; the stutter judged the documented latest-frame-wins degradation under device saturation at 20 FPS, not a failure mode.

## Commits

**None.** This plan produced no commits and no files.

## Requirement disposition

**ANIM-04 — not completed by this plan.** It was resolved by the operator ruling recorded in `04-RULING.md` (`a6ece8e`, verbatim reply "2", 2026-07-17): the 04-12 cross-device directional dossier was **accepted over** an honestly-recorded statistical FAIL — an acceptance, never a statistical pass. `REQUIREMENTS.md` marks ANIM-04 Complete on that ruling, sourced to 04-12/04-13.

## Stale content in this plan (do not act on it)

`04-07-PLAN.md` describes the Capsule as **13×26**. That was an early-planning units mix-up. The operator's correction (2026-07-17) stands: the Capsule is **16×8 zones (128 zones), 26 in × 13 in physical**. The corrected figures were applied to ROADMAP, REQUIREMENTS and `uat_ack_stream.py` under 04-13. The plan text was left as-is because the plan is superseded and never executes; this note is the record.

## Self-Check

**SUPERSEDED — not applicable.** This plan did not run, and no self-check is claimed.
