---
phase: 04-animation-flow-control
plan: 06
subsystem: testing
tags: [hardware-uat, anim-03, tiles, superseded, partial-execution]

# ─── NOT A COMPLETION RECORD ───────────────────────────────────────────────
# This plan was PARTIALLY executed and then superseded before completion.
# It is closed out, not completed. See "Why this file exists" below.
status: superseded
executed: partial            # Task 1 ran (twice, both FAIL); Task 2 never ran
superseded_by: ["04-11", "04-12", "04-13"]
closed_out: 2026-07-17       # date of the 04-13 operator ruling

# This plan completed NO requirements. Its ANIM-03 claim was resolved elsewhere
# (04-12 cross-device sweep + 04-13 operator ruling) — see "Requirement disposition".
requirements-completed: []

requires:
  - phase: 04-animation-flow-control (04-05)
    provides: the uat_ack_stream.py harness this plan's Task 1 ran
provides:
  - "04-UAT-TILES.json + 04-UAT-TILES-run1-FAIL.json — honest Task 1 FAIL evidence from two Tiles runs at the original 0% gate (retained, cited read-only by 04-RULING.md)"
  - "uat_ack_stream.py: AckRttObserver made read-only against the slotted AckGate (a real harness fix, commit 5f1d80b)"
affects: [04-11, 04-12, 04-13]

key-files:
  created:
    - .planning/phases/04-animation-flow-control/04-UAT-TILES.json
    - .planning/phases/04-animation-flow-control/04-UAT-TILES-run1-FAIL.json
  modified:
    - .planning/phases/04-animation-flow-control/uat_ack_stream.py
---

# Phase 04, Plan 06 — Closed out as SUPERSEDED (partially executed)

**ANIM-03 Tiles UAT: Task 1 ran twice and honestly FAILed at the original 0% gate; its measurement ownership then moved to 04-11, and its operator visual checkpoint (Task 2) never ran — visual ownership landed on 04-13 Task 4. ANIM-03 was ultimately resolved by operator ruling, not by this plan.**

## Why this file exists

This is a **closure record, not a completion record**. It exists for two reasons:

1. **To stop this plan being re-executed.** The ROADMAP says "do not execute this plan", but that is prose — nothing enforced it. `/gsd-execute-phase` skips plans where `has_summary: true`, so this file makes the supersession a gate rather than a comment.
2. **To let the phase read as complete on disk.** GSD counts a phase complete only when every `*-PLAN.md` has a matching `*-SUMMARY.md` (`plan-scan.cjs`: `completed = planCount > 0 && summaryCount >= planCount`). It has no concept of a superseded plan, so without this file Phase 4 reads `11/13 → completed=false` **permanently**, and any disk-derived count (`state sync`) silently reports 2 completed phases instead of 3.

**Read `status: superseded` / `executed: partial`, not the summary count.** A tool inferring "13 summaries ⇒ 13 plans executed" would be wrong: **11 of Phase 4's 13 plans were executed.** This plan ran one of its two tasks; 04-07 ran none.

## What actually happened

### Task 1 — Run the headless ANIM-03 measurement (3 rounds, Tiles) — **RAN, FAILed twice**

Executed against real Tiles hardware. Both runs FAILed the plan's original 0% loss gate (~3.7% observed). The evidence was recorded honestly and the threshold was **not** adjusted after the fact.

A real defect was found and fixed while running it: `AckRttObserver` mutated a slotted `AckGate`, raising on `__slots__`. Fixed read-only in `5f1d80b`.

The gate this task measured against was subsequently superseded **twice** — first the 0% gate (recalibrated by 04-10 after 04-09 showed the spike's 0/50 was a small-sample draw), then 04-10's amended absolute gate (which itself FAILed twice). Measurement ownership finally moved to **04-11**'s paired ambient/gated/blind harness (`f872d97`, `bfeae3e`), and then to **04-12**'s cross-device sweep.

### Task 2 — Operator visual verdict, Tiles streaming smoothness — **NEVER RAN, superseded**

Its intended owner, 04-12 Task 5, was skipped when the sweep returned an aggregate FAIL. Visual ownership passed to **04-13 Task 4**, where the operator gave an explicit dual verdict (smoothness + geometry) on the Ceiling Capsule and approved with the observation recorded.

## Commits

| Commit | What |
|--------|------|
| `5f1d80b` | `fix(04-06): make AckRttObserver read-only against slotted AckGate` — 1 file, 35+/29− (harness only; no `src/` change) |
| `5de88f6` | `test(04-06): record ANIM-03 Tiles UAT FAIL evidence (both runs)` — 2 evidence files, 152+ |

No `src/` code shipped under this plan. Its FAIL evidence is retained unmodified and is cited read-only by `04-RULING.md`.

## Requirement disposition

**ANIM-03 — not completed by this plan.** It was resolved by the operator ruling recorded in `04-RULING.md` (`a6ece8e`, verbatim reply "2", 2026-07-17): the 04-12 cross-device directional dossier was **accepted over** an honestly-recorded statistical FAIL — an acceptance, never a statistical pass. `REQUIREMENTS.md` marks ANIM-03 Complete on that ruling, sourced to 04-12/04-13.

This plan's `must_haves` were therefore never satisfied on their own terms, and this file does not claim they were. The 0%-loss truth it asserted was **disproven** as calibrated (04-09), which is why the criterion was redesigned rather than the run repeated.

## Self-Check

**SUPERSEDED — not applicable.** This plan did not complete, and no self-check is claimed. Its partial evidence stands on its own and is cited by the ruling that replaced it.
