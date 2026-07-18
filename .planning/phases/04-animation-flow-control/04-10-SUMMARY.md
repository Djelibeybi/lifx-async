---
phase: 04-animation-flow-control
plan: 10
subsystem: animation
tags: [gap-closure, anim-03, recalibration, hardware-uat, fail-evidence]
requires:
  - "04-09: operator routing decision (verbatim '1' = recalibrate) + 04-GAP-ANALYSIS.md '## Proposed amendment' wording"
provides:
  - "Amended ROADMAP Phase 4 success criterion 3 and REQUIREMENTS ANIM-03 (operator-approved wording: pooled <= 5.0%/run, <= 9.0%/round)"
  - "Amended uat_ack_stream.py: MAX_QUERY_LOSS_PCT = 9.0 per round + MAX_POOLED_QUERY_LOSS_PCT = 5.0 pooled, self-consistent docstring contract and thresholds JSON"
  - "Fresh ANIM-03 headless evidence under the amended gate: FAIL, twice (04-UAT-TILES-amended-run1-FAIL.json pooled 11.21%; 04-UAT-TILES.json re-run pooled 5.74%)"
  - "Supersession annotations on 04-06-PLAN.md (Task 1 superseded) and 04-07-PLAN.md (inherited amended gate)"
affects:
  - "Fresh operator routing required: /gsd-plan-phase 4 --gaps with the two FAIL JSONs + this summary as evidence"
  - "04-06 Task 2 and all of 04-07 REMAIN GATED — the amended-gate headless PASS prerequisite does not exist"
tech-stack:
  added: []
  patterns:
    - "Protocol-fixed-before-data: both amendment commits (99d7d8d, 40d782a) strictly precede the evidence commit (d154ccf) in git history"
    - "Thresholds never adjusted after a run — a FAIL under the operator's own amended gate routes back to the operator, it is never an executor edit"
    - "First FAIL preserved under a distinct filename before the single transient-rule-out re-run"
key-files:
  created:
    - .planning/phases/04-animation-flow-control/04-UAT-TILES-amended-run1-FAIL.json
  modified:
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/phases/04-animation-flow-control/04-06-PLAN.md
    - .planning/phases/04-animation-flow-control/04-07-PLAN.md
    - .planning/phases/04-animation-flow-control/uat_ack_stream.py
    - .planning/phases/04-animation-flow-control/04-UAT-TILES.json
    - .planning/STATE.md
decisions:
  - "Operator-approved amendment applied verbatim from 04-GAP-ANALYSIS.md '## Proposed amendment' (routing recorded in 04-09-SUMMARY.md); only declared deviations: ROADMAP single-line reflow + additive pooled_query_loss_pct evidence field"
  - "Amended-gate run FAILed twice (pooled 11.21% then 5.74% vs 5.0%; delivered_ratio below 0.85 in two rounds of each run — a NEW failure mode); thresholds untouched, outcome routed back to the operator"
  - "ANIM-03 deliberately NOT marked complete (plan mandate: completion owned by 04-06 Task 2, which stays gated)"
metrics:
  duration: ~18min
  tasks: 3
  files: 8
  completed: 2026-07-17
status: complete
---

# Phase 04 Plan 10: ANIM-03 Recalibration Applied + Amended-Gate Evidence Summary

The operator-approved recalibration (pooled ≤ 5.0%/run, ≤ 9.0%/round) is fully applied
to ROADMAP, REQUIREMENTS and the harness with the amendment provably committed before
the data — and the fresh 3-round Tiles run then **FAILed the amended gate twice**
(pooled 11.21% and 5.74% vs ≤ 5.0%, with delivered-ratio misses the 0.85 floor had
never tripped before), so 04-06 Task 2 and 04-07 stay gated pending a fresh operator
routing.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Amendment to governing documents + 04-06/04-07 supersession annotations | 99d7d8d (`docs(04-10)`) | ROADMAP.md, REQUIREMENTS.md, 04-06-PLAN.md, 04-07-PLAN.md |
| 2 | Harness gate recalibration (9.0%/round + 5.0% pooled) | 40d782a (`feat(04-10)`) | uat_ack_stream.py |
| 3 | Amended-gate FAIL evidence (both runs) + STATE gate note | d154ccf (`test(04-10)`) | 04-UAT-TILES.json, 04-UAT-TILES-amended-run1-FAIL.json, STATE.md |

**Commit order verified:** both amendment commits (99d7d8d, 40d782a) strictly precede
the evidence commit (d154ccf) — the protocol-fixed-before-data discipline (04-08
precedent) held. All commits GPG-signed with `git commit -s`.

## The Amendment (Tasks 1–2)

Applied verbatim from 04-GAP-ANALYSIS.md "## Proposed amendment" (operator routing
recorded verbatim as "1" in 04-09-SUMMARY.md):

- **ROADMAP Phase 4 success criterion 3**: replaced with the measured-device-floor
  wording (pooled ≤ 5.0% per run, ≤ 9.0% in any single round, evidence-derived
  parenthetical, blind-fire baseline 14.6%). Plan-list bullets for 04-06/04-07
  refreshed to reflect the supersession and the inherited amended gate.
- **REQUIREMENTS ANIM-03**: loss clause replaced; checkbox remains `- [ ]` (unchecked);
  Traceability row untouched (still "Pending").
- **04-06-PLAN.md / 04-07-PLAN.md**: annotated with AMENDMENT NOTICE blocks immediately
  after their frontmatter — bodies otherwise byte-identical (annotate, never rewrite).
- **uat_ack_stream.py**: `MAX_QUERY_LOSS_PCT` 0.0 → 9.0 (per-round loop unchanged);
  new `MAX_POOLED_QUERY_LOSS_PCT = 5.0` enforced via the single-source
  `_pooled_query_loss_pct()` helper; `_thresholds()` and the results JSON record both
  gates; module docstring (tiles profile, honest-reporting rules, exit-code contract)
  updated to agree with the code in every location. ruff format/check and pyright
  clean; pre-commit hooks (including bandit and codespell) passed at commit time.
  Functional verification proved both gates fire independently: 3×4.0% → True,
  3×8.0% (per-round pass, pooled 8.0%) → False, one 10.0% round among clean rounds
  (pooled ~3.3%) → False.

**Wording quirk recorded, not altered (per plan):** the approved ROADMAP citation names
04-UAT-TILES.json, which Task 3 overwrote with amended-gate evidence. The cited
miscalibrated-gate bytes remain in history at commit **5de88f6** (the superseded
04-06 Task 1 evidence).

## The Run (Task 3) — FAIL, flagged loudly

Fixed thresholds, committed before the run and never adjusted after it: per-round
loss ≤ 9.0%; pooled ≤ 5.0%; delivered_ratio ≥ 0.85/round; 3 rounds; 20 FPS; query
rate 2/s. Device: primary Tiles 192.168.19.243 (fallback never used — no ENV-ERROR).

**Run 1 — exit 1 (FAIL)** — preserved as `04-UAT-TILES-amended-run1-FAIL.json`:

| Round | Loss % (≤ 9.0) | Delivered (≥ 0.85) | Query median ms | Ack RTT med/p95 ms | Ack expiries |
|-------|----------------|--------------------|-----------------|--------------------|--------------|
| 0 | **11.76** | **0.6033** | 88.9 | 100.2 / 150.2 | 21 |
| 1 | **20.0** | **0.795** | 105.5 | 100.2 / 150.4 | 5 |
| 2 | 4.65 | 0.8733 | 103.5 | 100.2 / 150.3 | 0 |

Pooled: 12/107 = **11.21%** (gate 5.0%; blind-fire baseline 14.6%).

**Run 2 — the single transient-rule-out re-run, identical flags — exit 1 (FAIL)** —
`04-UAT-TILES.json`:

| Round | Loss % (≤ 9.0) | Delivered (≥ 0.85) | Query median ms | Ack RTT med/p95 ms | Ack expiries |
|-------|----------------|--------------------|-----------------|--------------------|--------------|
| 0 | 7.89 | **0.77** | 110.3 | 100.2 / 151.2 | 5 |
| 1 | 7.5 | 0.9267 | 101.1 | 100.2 / 150.2 | 0 |
| 2 | 2.27 | **0.8217** | 91.4 | 100.2 / 151.2 | 1 |

Pooled: 7/122 = **5.74%** (gate 5.0%). Per-round loss passed everywhere in run 2;
the FAIL is the pooled gate plus two delivered-ratio misses.

**What the numbers say (recorded, not interpreted beyond flagging):**

- Both runs are far lossier than the evidence the amendment was derived from
  (04-08 shipped arm 1.06%; pooled shipped-path evidence 15/540 = 2.78%). Run 1's
  20.0% round approaches the 14.6% blind-fire baseline.
- The **delivered-ratio misses (0.60, 0.77, 0.80, 0.82 vs 0.85) are a NEW failure
  mode** — no prior run of this harness ever tripped the 0.85 floor. High gated-frame
  counts (238/600 in run 1 round 0) and ack expiries (21 in that round) indicate the
  gate was throttling hard because acks were slow/absent — consistent with device or
  network congestion during this session, but that is for the operator's routing, not
  an executor conclusion.
- Ack RTT medians (100.2 ms) match the ~98 ms spike reference throughout; p95 ~150 ms
  matches the 150 ms reference.

**Executor discipline held:** thresholds untouched after the runs; exactly one re-run;
first FAIL preserved before it; both outcomes committed; no fallback-IP run (fallback
is ENV-ERROR-only and no ENV-ERROR occurred).

## Routing (per plan step 3, FAIL branch)

- 04-06 Task 2 (Tiles visual checkpoint) and all of 04-07 (Ceiling UAT) **remain
  gated** — the amended-gate headless PASS prerequisite does not exist.
- REQUIREMENTS ANIM-03 checkbox remains unchecked; Traceability row remains "Pending".
- STATE.md "UAT sequencing gate" bullet updated with the full FAIL detail and the
  required next step: **fresh operator routing** via `/gsd-plan-phase 4 --gaps` with
  `04-UAT-TILES-amended-run1-FAIL.json`, `04-UAT-TILES.json` and this summary as the
  new evidence.

## Deviations from Plan

All declared/allowed by the plan — none silent:

1. **[Declared allowance] ROADMAP single-line reflow** — the brief's wrapped
   replacement text for criterion 3 was reflowed onto one line to match the ROADMAP
   list style; content verbatim.
2. **[Plan-mandated, flagged] Additive `pooled_query_loss_pct` results field** — not
   in the operator wording; an additive evidence-recording measure consistent with the
   harness's honest-reporting rules. Gate-neutral (the gate uses the same
   `_pooled_query_loss_pct()` helper). ENV-ERROR branch dict unchanged.
3. **[Recorded wording quirk] Citation names an overwritten file** — the approved
   wording cites 04-UAT-TILES.json; the cited miscalibrated-gate bytes live at commit
   5de88f6. Applied as approved, not altered.

### Deliberate non-action

- **ANIM-03 NOT marked complete** despite appearing in this plan's frontmatter
  `requirements` — plan mandate: completion is owned by 04-06 Task 2 in every outcome,
  and on FAIL it stays gated (04-05/04-08/04-09 precedent). `requirements
  mark-complete` was deliberately not run.
- **src/ and tests/ untouched** across all three commits (verified:
  `git diff 86d81e8..HEAD --name-only` shows only `.planning/` paths). D4-01's src/
  tuning constants (gate 2, ~1 s expiry) unchanged — only UAT pass thresholds were
  recalibrated. No dependencies installed.

## Known Stubs

None — the harness measures real hardware; both evidence JSONs contain real measured
per-round data.

## Threat Flags

None new. T-04-20 (self-inflicted outbound load): fixed rounds honoured, exactly one
re-run, fallback untouched. T-04-21 (gate tampering): wording verbatim, amendment
commits strictly precede evidence, thresholds untouched post-run. T-04-22
(repudiation): superseded bytes at 5de88f6 cited; new first-FAIL preserved under the
distinct filename before the re-run.

## Self-Check: PASSED

- FOUND: .planning/phases/04-animation-flow-control/04-UAT-TILES.json (outcome FAIL, thresholds 9.0/5.0)
- FOUND: .planning/phases/04-animation-flow-control/04-UAT-TILES-amended-run1-FAIL.json (outcome FAIL, pooled 11.21)
- FOUND: commits 99d7d8d, 40d782a, d154ccf in order (amendments strictly before evidence)
- VERIFIED: no src/ or tests/ paths in any plan commit; ANIM-03 checkbox unchecked; Traceability "Pending"
