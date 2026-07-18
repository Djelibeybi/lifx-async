---
phase: 04-animation-flow-control
plan: 11
subsystem: animation
tags: [gap-closure, anim-03, paired-relative, criterion-redesign, hardware-uat, fail-evidence]
requires:
  - "04-10: twice-FAILed amended absolute gate evidence + operator routing decision (verbatim '2' = paired-relative redesign)"
provides:
  - "04-CRITERION-DESIGN.md + criterion_design.py: evidence-derived paired-relative ANIM-03 criterion with exact power and retrodiction, committed before the operator checkpoint"
  - "Operator approval of the complete final wording (blocking checkpoint, verbatim reply '1' = approve as presented, unamended)"
  - "Amended ROADMAP Phase 4 criterion 3 and REQUIREMENTS ANIM-03 (paired-relative wording); 04-06/04-07 second-generation supersession notices"
  - "uat_ack_stream.py reworked into the paired ambient/gated/blind-fire harness with the 0/1/2/3 exit contract"
  - "Fresh paired ANIM-03 evidence: FAIL, twice, with both sessions VALID (04-UAT-TILES-paired-run1-FAIL.json; 04-UAT-TILES.json)"
affects:
  - "Fresh operator routing required: /gsd-plan-phase 4 --gaps with the two paired FAIL JSONs + this summary as evidence"
  - "04-06 Task 2 and all of 04-07 REMAIN GATED -- the paired-gate headless PASS prerequisite does not exist"
tech-stack:
  added: []
  patterns:
    - "Protocol-fixed-before-data: design commit (cc81606) and both application commits (cff1457, f872d97) strictly precede the evidence commit (bfeae3e)"
    - "Paired same-session comparison: identical prober in ambient/gated/blind blocks; only the streaming treatment differs between arms"
    - "INCONCLUSIVE (exit 3) as a declared outcome distinct from PASS and FAIL -- validity-first evaluation, never silently retried"
    - "Blind-fire constructed at instrument level only (D4-02: shipped Animator has no flow-control toggle)"
key-files:
  created:
    - .planning/phases/04-animation-flow-control/04-CRITERION-DESIGN.md
    - .planning/phases/04-animation-flow-control/criterion_design.py
    - .planning/phases/04-animation-flow-control/04-UAT-TILES-paired-run1-FAIL.json
  modified:
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/phases/04-animation-flow-control/04-06-PLAN.md
    - .planning/phases/04-animation-flow-control/04-07-PLAN.md
    - .planning/phases/04-animation-flow-control/uat_ack_stream.py
    - .planning/phases/04-animation-flow-control/04-UAT-TILES.json
    - .planning/STATE.md
decisions:
  - "Operator approved the complete paired-relative wording as presented (checkpoint reply verbatim '1'); applied verbatim with no amendments"
  - "Paired gate FAILed twice with both sessions VALID (gated 2.94% vs blind 7.20% ratio 2.45 p=0.0973; gated 5.51% vs blind 9.73% ratio 1.77 p=0.1601) -- a genuine signal under the operator's own rule; thresholds untouched, fresh operator routing required"
  - "ANIM-03 deliberately NOT marked complete (plan mandate: completion owned by 04-06 Task 2, which stays gated)"
metrics:
  duration: ~50min
  tasks: 4
  files: 10
  completed: 2026-07-17
status: complete
---

# Phase 04 Plan 11: Paired-Relative ANIM-03 Criterion Redesign + Paired Evidence Summary

The operator-approved paired-relative criterion (evidence-derived, power-stated,
robust to the measured ~8x session variance) is fully designed, approved from
complete concrete wording, and applied with the protocol provably committed before
the data — and the fresh paired run then **FAILed the paired gate twice with both
sessions VALID**: the gated arm beat blind-fire in both runs (2.45x, then 1.77x)
but never met the approved significance-plus-ratio bar nor the clean escape, so
04-06 Task 2 and 04-07 stay gated pending fresh operator routing.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Criterion design brief + reproducible stats runner | cc81606 (`docs(04-11)`) | 04-CRITERION-DESIGN.md, criterion_design.py |
| 2 | Blocking operator checkpoint (decision record, no files) | — | reply verbatim below |
| 3a | Governing documents + annotations | cff1457 (`docs(04-11)`) | ROADMAP.md, REQUIREMENTS.md, 04-06-PLAN.md, 04-07-PLAN.md |
| 3b | Paired-mode harness rework | f872d97 (`feat(04-11)`) | uat_ack_stream.py |
| 4 | Paired FAIL evidence (both attempts) + STATE gate note | bfeae3e (`test(04-11)`) | 04-UAT-TILES.json, 04-UAT-TILES-paired-run1-FAIL.json, STATE.md |

**Commit order verified:** cc81606 → cff1457 → f872d97 → bfeae3e — the design and
both application commits strictly precede the evidence commit
(protocol-fixed-before-data, 04-08/04-10 discipline). All commits GPG-signed with
`git commit -s`. `git diff` across all plan commits touches no src/ or tests/
paths and installs nothing (D4-02, D4-01 upheld).

## The Operator Decision (Task 2)

The complete final wording (ROADMAP criterion 3 replacement, REQUIREMENTS ANIM-03
replacement, harness gate contract), the parameter/derivation table, the exact
power numbers, the retrodiction table and the wall-time statement were presented
inline at the blocking checkpoint — exactly one ask. The options were presented as
a numbered list with option 1 = "Approve the proposed wording as presented".

**Operator reply, verbatim: "1"** — approve, as presented, unamended. The proposal
became the governing text with no substitutions.

## The Design (Task 1)

Every parameter derived by a stated rule from the committed multi-session
evidence, reproducible with one command
(`uv run python .planning/phases/04-animation-flow-control/criterion_design.py`;
hard-coded counts asserted against every on-disk source JSON; Fisher machinery
reproduces the committed 04-08 reference p = 0.0342, one-sided 0.0284):

- **Evidence basis:** session-level gated pooled rates 1.06% / 3.37% / 8.30%
  (7.8x spread, same code, same device, one day) — any absolute threshold from
  one session is a coin-flip UAT. Both prior calibrations were single-session
  (spike 003's 0/50; the 14.6% blind baseline's 6/41).
- **Rule:** session valid (ambient ≤ 2.5%, ambient n ≥ 100, every gated round
  delivered ≥ 0.50 — else INCONCLUSIVE, exit 3) AND gated pooled ≤ 9.0% AND
  (gated pooled ≤ 2.5% OR (Fisher one-sided p < 0.05 AND blind/gated ≥ 2.0)).
- **Declared exact power (enumeration, no approximations):** P(PASS) at the
  historical rates (p_g = 2.78%, p_b = 14.6%) = **0.9008** at n = 100 per arm
  (0.9443 at 120, 0.9696 at 140). The pre-declared adjustment rule (raise to 4
  rounds/arm if < 0.85) did NOT fire; 3 rounds per arm stood.
- **Retrodiction:** session B PASS (clean escape); session C run 1 FAIL (ceiling);
  spike 003 relative-rule satisfied (p = 0.0067) but ambient-power INCONCLUSIVE
  (n = 20 < 100); sessions A and C-run-2 honestly INDETERMINATE (no paired
  comparator was ever measured).
- **Wall time:** ~5.25 min/attempt declared; ≤ ~11 min device budget over the
  hard two-attempt limit. Actual: two attempts, ~5.5 min each.

## The Application (Task 3)

Applied the approved wording EXACTLY (single-line reflow of the ROADMAP criterion
being the only permitted deviation, 04-10 precedent):

- **ROADMAP criterion 3**: the paired-relative wording; 04-06/04-07 plan bullets
  refreshed onto the 04-11 gate.
- **REQUIREMENTS ANIM-03**: approved wording; checkbox `- [ ]` (unchecked);
  Traceability row untouched ("Pending").
- **04-06/04-07 plans**: exactly one additional 04-11 AMENDMENT NOTICE block each,
  appended after their 04-10 notices — every other line byte-identical.
- **uat_ack_stream.py**: paired-gate constants (superseded per-round 9.0% /
  pooled-only 5.0% / delivered 0.85 constants deleted); `BlindStreamer` (adapted
  from ReplicaStreamer — own transport, per-packet awaited sends, ack flag
  CLEARED on every packet, no ack state); `run_ambient_block` (adapted from
  run_control_block); `run_blind_round` with the byte-identical `query_prober`;
  alternating G,B session flow with `--rounds` now meaning rounds per arm;
  `fisher_one_sided` copied from criterion_design.py; validity-first `_evaluate`
  returning (outcome, reasons); exit contract 0/1/2/3; docstring rewritten to
  match the code in every location. ruff format/check + pyright clean; pre-commit
  hooks (bandit, codespell included) passed at commit time. All six synthetic
  gate scenarios verified: relative-rule PASS, no-significance FAIL, ceiling FAIL
  despite a ≥ 2x relative win, clean-escape PASS with a low blind arm,
  ambient-validity INCONCLUSIVE, delivered-sanity INCONCLUSIVE.

## The Runs (Task 4) — FAIL twice, flagged loudly

Fixed rules committed before the run (verified via git log) and never adjusted
after it. Device: primary Tiles 192.168.19.243 (fallback never used — no
ENV-ERROR occurred). Two attempts total (hard budget); first attempt preserved as
`04-UAT-TILES-paired-run1-FAIL.json` before the single re-run.

**Attempt 1 — exit 1 (FAIL), session VALID:**

| Block | Figures |
|-------|---------|
| Ambient (60 s) | **0/113 = 0.0%** loss (bounds: ≤ 2.5%, n ≥ 100 — VALID), median 12.9 ms |
| Gated rounds (loss %) | 4.76 / 2.13 / 2.13 — delivered 0.8317 / 0.9233 / 0.9267 (all ≥ 0.50 sanity floor; recorded evidence, not pass/fail) |
| Blind rounds (loss %) | 18.75 / 0.0 / 6.82 |
| Gated pooled | **4/136 = 2.94%** (ceiling 9.0% passed; clean escape 2.5% missed by one lost query) |
| Blind pooled | **9/125 = 7.20%** |
| Fisher one-sided p | **0.0973** (not < 0.05) |
| Improvement ratio | **2.45** (≥ 2.0 satisfied) |
| Ack RTT med/p95 | 100.2–100.3 / 150.2–150.4 ms (vs ~98/150 ms spike reference) |

FAIL reason: relative rule missed on significance alone — the ratio bar was met.

**Attempt 2 — the single transient-rule-out re-run, identical flags — exit 1
(FAIL), session VALID:**

| Block | Figures |
|-------|---------|
| Ambient (60 s) | **0/114 = 0.0%** loss — VALID, median 13.7 ms |
| Gated rounds (loss %) | 10.81 / 2.13 / 4.65 — delivered 0.8183 / 0.93 / 0.9233 (all ≥ 0.50) |
| Blind rounds (loss %) | 10.81 / 15.15 / 4.65 |
| Gated pooled | **7/127 = 5.51%** (ceiling passed; no clean escape) |
| Blind pooled | **11/113 = 9.73%** |
| Fisher one-sided p | **0.1601** (not < 0.05) |
| Improvement ratio | **1.77** (< 2.0) |
| Ack RTT med/p95 | 100.2 / 150.2–150.3 ms |

**What the numbers say (recorded, not interpreted beyond flagging):**

- Both sessions passed EVERY validity precondition — clean ambient floors
  (0/113, 0/114), all delivered ratios comfortably above 0.50. Under the
  approved rule's own semantics this is a genuine gated-arm signal, NOT an
  environment excuse: INCONCLUSIVE was available and did not fire.
- The gated arm was numerically better than same-session blind-fire in both
  runs (2.94% vs 7.20%; 5.51% vs 9.73%) — the flow control is doing something —
  but never met the operator-approved bar (significance AND ≥ 2x, or ≤ 2.5%
  clean). Attempt 1 missed the clean escape by exactly one lost query and
  missed significance (p = 0.0973); attempt 2 missed both relative conditions.
- The 9.0% pooled ceiling passed in both runs; gated loss sat in the 2.9–5.5%
  band consistent with the historical 2.78% pooled evidence rate and far below
  the 14.6% blind baseline; ack RTT medians match the spike reference
  throughout.
- The design's own power statement declared P(PASS | historical rates,
  n≈100–136) ≈ 0.90 — two consecutive FAILs at healthy ambient is itself
  information for the operator's routing.

**Executor discipline held:** thresholds untouched after the runs; exactly one
re-run; first FAIL preserved under its distinct filename before it; both
outcomes committed; fallback IP untouched (ENV-ERROR-only, none occurred); no
third attempt.

**Supersession citation:** Task 4's first run intentionally overwrote the 04-10
amended-absolute-gate FAIL evidence in `04-UAT-TILES.json` in place; the
superseded bytes remain in history at commit **d154ccf** (04-10 precedent:
supersede in place, cite the commit).

## Routing (per plan step 4, FAIL branch)

- 04-06 Task 2 (Tiles visual checkpoint — sole ANIM-03 visual owner) and all of
  04-07 (Ceiling UAT, inheriting the paired shared gate) **remain gated**.
- REQUIREMENTS ANIM-03 checkbox remains unchecked; Traceability row remains
  "Pending".
- STATE.md "UAT sequencing gate" bullet updated with the full paired FAIL detail
  and the required next step: **fresh operator routing** via
  `/gsd-plan-phase 4 --gaps` with `04-UAT-TILES-paired-run1-FAIL.json`,
  `04-UAT-TILES.json` and this summary as the new evidence. A FAIL under the
  operator's own approved rule is a new operator decision, never an executor
  edit.

## Deviations from Plan

All declared/allowed — none silent:

1. **[Declared allowance] ROADMAP single-line reflow** — the approved criterion 3
   text reflowed onto one line to match the list style; content verbatim.
2. **[Additive, gate-neutral] `reasons` field in the results JSON** — `_evaluate`
   returns human-readable reasons per the plan's item 11; recording them in the
   JSON (alongside the mandated `validity_reasons`) is an additive
   evidence-recording measure consistent with the honest-reporting rules.
3. **[Schema rename consistent with the plan] `rounds_requested` →
   `rounds_per_arm`** in the results JSON — `--rounds` now means rounds PER ARM
   (plan item 9); the old key name would have been misleading.

### Deliberate non-action

- **ANIM-03 NOT marked complete** despite appearing in this plan's frontmatter
  `requirements` — plan mandate: completion is owned by 04-06 Task 2 in every
  outcome, and on FAIL it stays gated. `requirements mark-complete` was
  deliberately not run.
- **src/ and tests/ untouched** across all four commits (verified via
  `git diff cc81606^..bfeae3e --name-only`: only `.planning/` paths). D4-01's
  src/ tuning constants (gate 2 outstanding, ~1 s expiry) unchanged — only the
  UAT judging rule changed. No dependencies installed.

## Known Stubs

None — the harness measures real hardware; both evidence JSONs contain real
measured per-block data.

## Threat Flags

None new. T-04-23 (criterion cherry-picking): every parameter rule-derived and
reproducible, runner committed before the checkpoint, adjustment rule
pre-declared and reported (did not fire), approval before application, wording
applied verbatim, rules untouched post-run. T-04-24 (self-inflicted outbound
load): fixed 30 s rounds, 3 per arm, 10 s rests, 60 s ambient, two-attempt
budget honoured, reachability guard held, fallback unused. T-04-25
(repudiation/retry laundering): superseded bytes cited at d154ccf; first-attempt
FAIL preserved under its distinct filename before the re-run; INCONCLUSIVE never
fired and was never used as a retry channel.

## Self-Check: PASSED

- FOUND: 04-CRITERION-DESIGN.md, criterion_design.py, 04-UAT-TILES-paired-run1-FAIL.json (outcome FAIL, gated 2.94%), 04-UAT-TILES.json (outcome FAIL, gated 5.51%)
- FOUND: commits cc81606, cff1457, f872d97, bfeae3e in order (design + application strictly before evidence)
- VERIFIED: no src/ or tests/ paths in any plan commit; ANIM-03 checkbox unchecked; Traceability "Pending"
