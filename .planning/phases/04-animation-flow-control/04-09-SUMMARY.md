---
phase: 04-animation-flow-control
plan: 09
subsystem: animation
tags: [gap-closure, anim-03, statistics, routing-decision, human-gate]
requires:
  - "04-08: 04-GAP-INVESTIGATION.json / 04-GAP-INVESTIGATION-EVENTS.jsonl hardware evidence + 04-GAP-SPIKE-FORENSICS.md"
provides:
  - "gap_analysis.py: reproducible stdlib-only stats runner (Wilson CIs, Fisher exact, binomials, event clustering) over the 04-08 evidence"
  - "04-GAP-ANALYSIS.md: decision brief — verdict H2 under pre-declared rules, route recalibrate, proposed amendment text (NOT applied)"
  - "Operator routing decision, verbatim: recalibrate, endorsing the brief's proposed amendment wording"
affects:
  - "Follow-up amendment plan: ROADMAP criterion 3 + REQUIREMENTS ANIM-03 + uat_ack_stream.py MAX_QUERY_LOSS_PCT (operator-approved wording)"
  - "04-06 Task 2 / 04-07: remain gated until the amendment lands and 04-06 re-runs under the amended criterion"
tech-stack:
  added: []
  patterns:
    - "Interpretation rules R1-R5 fixed in the plan before analysis ran — the analysis applies them, it never bends them"
    - "Stats runner committed before its first execution: the analysis protocol is provably fixed in git history ahead of its numbers"
    - "Threshold changes are operator decisions recorded verbatim with evidence — never executor decisions"
key-files:
  created:
    - .planning/phases/04-animation-flow-control/gap_analysis.py
    - .planning/phases/04-animation-flow-control/04-GAP-ANALYSIS.md
  modified: []
decisions:
  - "Verdict H2 (R2 fired; R1/R3/R4/R5 not fired): spike 003's 0/50 was a small-sample draw — the spike-faithful replica lost 9/185 = 4.86% at power, and the shipped path significantly outperforms the spike methodology (Fisher two-sided p = 0.0342)"
  - "Operator routing decision (verbatim reply: '1'): recalibrate — operator-authored amendment (pooled <= 5.0% per run, <= 9.0% per round) applied by a follow-up plan, then 04-06 re-runs under the amended criterion"
  - "ANIM-03 deliberately NOT marked complete: the requirement resolves when the amendment lands and 04-06 re-runs, not with this routing decision"
metrics:
  duration: ~12min
  tasks: 2
  files: 2
  completed: 2026-07-17
status: complete
---

# Phase 04 Plan 09: ANIM-03 Gap Analysis and Operator Routing Decision Summary

Pre-declared rules R1–R5 applied to the 04-08 evidence produced verdict H2 (spike 003's
0% threshold was a small-sample miscalibration — the shipped path significantly
outperforms the spike methodology, Fisher p = 0.0342), and the operator routed the gap
to recalibrate, endorsing the brief's proposed amendment (pooled ≤ 5.0% per run,
≤ 9.0% per round).

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1a | Reproducible stats runner (committed before first run) | 545d4b6 (`feat(04-09)`) | gap_analysis.py |
| 1b | Decision brief applying the pre-declared rules | e109f00 (`docs(04-09)`) | 04-GAP-ANALYSIS.md |
| 2 | Operator routing decision (checkpoint:decision, blocking) | this summary | 04-09-SUMMARY.md |

## Verdict (Task 1)

**H2** — the ANIM-03 0% concurrent-query-loss criterion was a spike-003 small-sample
miscalibration, not a defect in the shipped implementation. Rules applied exactly as
fixed in 04-09-PLAN.md before the analysis ran:

- **R2 FIRED**: replica arm (spike 003 methodology at power) lost 9/185 = 4.86%
  (n ≥ 150, ≥ 2%); P(0 in 185 | p = 3.37%) = 0.0018 — the spike's 0/50 was a
  small-sample draw from a lossy distribution.
- **R1 not fired**: control arms lossless on both devices (0/227, 0/114).
- **R3 not fired**: the shipped path (2/189 = 1.06%) lost significantly LESS than the
  replica (Fisher two-sided p = 0.0342) — the only significant methodology difference
  points the opposite way to H1's premise; nothing for a fix plan to close.
- **R4 not fired**: FPS trend monotone (0.00% → 0.98% → 1.06%) but the 20 FPS rate
  sits below the 10 FPS rule-of-three bound (2.78%) — not demonstrable saturation.
- **R5 not fired**: lossy shipped rounds on both devices — the FAIL reproduces.

Every number is reproducible:
`uv run python .planning/phases/04-animation-flow-control/gap_analysis.py`

## Operator Routing Decision (Task 2 — recorded verbatim)

The four routes (fix / recalibrate / rerun / investigate) were presented to the
operator (Avi) as a numbered list with the brief's Verdict, Rules fired and
Consequences-per-route sections, recalibrate listed as option 1 and noted as the
evidence-supported route, including the brief's proposed amendment text
(pooled ≤ 5.0% per run + ≤ 9.0% per round).

**The operator's verbatim reply:** `1`

**Decision:** recalibrate — adopting the brief's proposed amendment wording as the
basis for the operator-authored amendment. No further rationale was given beyond
selecting the option presented with the evidence.

**Verdict the operator was given:** H2, route recalibrate (04-GAP-ANALYSIS.md
"## Verdict", quoted in full at the checkpoint).

## Follow-up Route

Per the recalibrate route, **applied by follow-up work, none of it by this plan**:

1. **Operator-authored amendment** applied under its own plan
   (`/gsd-plan-phase 4 --gaps` with 04-GAP-ANALYSIS.md and this summary as evidence):
   ROADMAP success criterion 3, REQUIREMENTS ANIM-03 wording, and
   `uat_ack_stream.py` `MAX_QUERY_LOSS_PCT` → 9.0 per round plus a pooled
   ≤ 5.0% per-run check — using the operator-endorsed wording in
   04-GAP-ANALYSIS.md "## Proposed amendment".
2. **04-06 re-run** under the amended criterion
   (`/gsd-execute-phase 4` resuming 04-06).

**Gating restated:** 04-06 Task 2 (operator visual verdict) and all of 04-07
(Ceiling, ANIM-04) remain gated until the amendment lands and 04-06 re-runs under it.

## Deviations from Plan

None - plan executed exactly as written.

### Deliberate non-action

- **ANIM-03 not marked complete in REQUIREMENTS.md** despite appearing in this plan's
  frontmatter `requirements` (04-08 precedent). The routing decision is recorded, but
  the requirement resolves only when the amendment is applied and 04-06 re-runs and
  passes under the amended criterion.
- **Nothing applied by this plan**: ROADMAP.md, REQUIREMENTS.md, uat_ack_stream.py,
  src/ and D4-01's tuning constants are all untouched — `git diff` across the plan's
  commits against those paths is empty. The amendment exists only as clearly-marked
  proposed text awaiting the follow-up plan.

## Known Stubs

None — gap_analysis.py computes real statistics from committed evidence; the brief
carries no placeholders.

## Threat Flags

None. No new network, auth, file-access or schema surface: the analysis reads two
committed evidence files and contacts no devices (T-04-18/T-04-19 mitigations held:
rules fixed pre-run, statistics reproducible, thresholds untouched, decision recorded
verbatim).

## Self-Check: PASSED

gap_analysis.py, 04-GAP-ANALYSIS.md and this summary exist on disk; commits 545d4b6
and e109f00 are present in history with the runner committed strictly before its first
run; pinned artefacts (ROADMAP.md, REQUIREMENTS.md, uat_ack_stream.py, src/) show an
empty diff across all plan commits.
