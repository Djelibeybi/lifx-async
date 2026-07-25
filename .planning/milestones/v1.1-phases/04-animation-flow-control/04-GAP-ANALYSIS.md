# 04-09 Gap Analysis: ANIM-03 Decision Brief

**Question:** is the ~3.4% concurrent-query loss that failed 04-06's fixed 0% threshold
mechanically fixable (H1-fixable), an irreducible device/load floor (H1-floor), or a
spike-003 small-sample miscalibration (H2)?

**Discipline:** the interpretation rules R1–R5 were fixed in `04-09-PLAN.md` before this
analysis ran, mirroring the fixed-before-run UAT thresholds. The statistics runner
`gap_analysis.py` was committed (545d4b6) before its first execution. This brief applies
the pre-declared rules to the committed 04-08 evidence — it adds none and adjusts none.
Every number in the tables below is reproducible with one command:

```
uv run python .planning/phases/04-animation-flow-control/gap_analysis.py
```

## Evidence inventory

| File | Role | Commit |
|------|------|--------|
| `04-GAP-INVESTIGATION.json` | Per-arm aggregates from the five-arm hardware run (2026-07-17T03:28:57, exit 0, no re-runs) | dd6a15e |
| `04-GAP-INVESTIGATION-EVENTS.jsonl` | 1009 per-query + 7500 per-frame timestamped events for the clustering analysis | dd6a15e |
| `04-GAP-SPIKE-FORENSICS.md` | Spike 003 forensics: sample-size audit settling the H2 calibration half; enumerated spike-vs-shipped mechanical differences | 0f453e8 |
| `uat_loss_investigation.py` | The threshold-free instrument, committed strictly before the evidence it produced | f7c0854 |
| `gap_analysis.py` | This brief's statistics runner, committed strictly before its first run | 545d4b6 |

**Recorded 04-08 deviations qualifying the evidence:** one only — a scoped pre-commit
large-file exemption for `*-EVENTS.jsonl` evidence logs (1c2ddc1); the evidence bytes
themselves are untouched and the instrument needed no mechanism fixes (the battery ran
start-to-finish on its first attempt). Both devices were reachable throughout;
ANIM-03 was deliberately left open pending this brief and the operator's routing.

**Settled input carried in from the spike 003 forensics:** the 0% threshold was
calibrated from exactly one 50-query photons round. A 0/50 observation carries a ≥6%
rule-of-three upper bound and had an ≈18% probability of occurring even if the device's
true rate is the UAT-measured 3.37% — the threshold outran its evidence's resolution.
That settled the calibration half of H2; whether the residual loss is fixable or a
floor is what the tables below discriminate.

## Statistical tables

Verbatim output of `gap_analysis.py` against the committed evidence:

```
=== 04-09 gap analysis: statistics over the 04-08 evidence ===
run timestamp: 2026-07-17T03:28:57  arms: control, shipped, replica, sweep, fallback
events: 1009 query events, 7500 frame events

(a) Per-arm pooled loss with Wilson 95% intervals
    arm                device    lost/n    loss%    wilson 95% CI
    control            primary   0/227     0.00%    [0.00%, 1.66%]
    shipped            primary   2/189     1.06%    [0.29%, 3.78%]
    replica            primary   9/185     4.86%    [2.58%, 8.99%]
    sweep              primary   1/210     0.48%    [0.08%, 2.65%]
    fallback-control   fallback  0/114     0.00%    [0.00%, 3.26%]
    fallback-shipped   fallback  4/84      4.76%    [1.87%, 11.61%]
    fallback (all)     fallback  4/198     2.02%    [0.79%, 5.08%]

(b) Rule-of-three 95% upper bounds (zero-loss arms only, 3/n)
    control            primary   0/227     upper bound 1.32%
    fallback-control   fallback  0/114     upper bound 2.63%

(c) Fisher exact test (two-sided): shipped vs replica pooled losses
    table [[lost, ok]]: shipped [2, 187]  replica [9, 176]
    shipped loss 1.06%  replica loss 4.86%
    two-sided p = 0.0342

(d) P(zero losses in n | p) with p = pooled 04-06 UAT rate 9/267 = 3.37%
    n = 50   P(0 losses) = 0.1801
    n = 150  P(0 losses) = 0.0058
    n = 176  P(0 losses) = 0.0024
    n = 185  P(0 losses) = 0.0018

(e) Event clustering: shipped + sweep arm queries vs frame events
    (m1 = gate-outstanding at query send; m2 = non-gated frames in
     [t, t+2.0 s]; m3 = seconds since last non-gated frame)
    outcome=ok    n=396  median m1=1.000  median m2=30.000  median m3=0.032
    outcome=lost  n=3    median m1=2.000  median m2=30.000  median m3=0.061
    every lost shipped/sweep query in detail:
    shipped  fps=20.0  round=1 t=  25.906s  outstanding=2.0  non-gated-in-window=37  since-last-non-gated=0.006s
    shipped  fps=20.0  round=3 t=  15.836s  outstanding=2.0  non-gated-in-window=28  since-last-non-gated=0.085s
    sweep    fps=15.0  round=1 t=   9.995s  outstanding=1.0  non-gated-in-window=30  since-last-non-gated=0.061s

(f) Loss vs FPS (10/15 from sweep arm; 20 from shipped arm; primary)
    fps   lost/n    loss%    wilson 95% CI      3/n bound
    10.0  0/108     0.00%    [0.00%, 3.43%]     2.78%
    15.0  1/102     0.98%    [0.17%, 5.35%]     2.94%
    20.0  2/189     1.06%    [0.29%, 3.78%]     1.59%

(g) Primary vs fallback device (same shipped path, 20 FPS)
    segment            device    lost/n    loss%    wilson 95% CI
    control            primary   0/227     0.00%    [0.00%, 1.66%]
    shipped            primary   2/189     1.06%    [0.29%, 3.78%]
    fallback-control   fallback  0/114     0.00%    [0.00%, 3.26%]
    fallback-shipped   fallback  4/84      4.76%    [1.87%, 11.61%]

(h) Control-arm ambient floors (no streaming, single-shot queries)
    control            primary   0/227  rule-of-three 1.32%  wilson [0.00%, 1.66%]
    fallback-control   fallback  0/114  rule-of-three 2.63%  wilson [0.00%, 3.26%]

Rule inputs (pre-declared R1-R5 predicates; arithmetic only)
    R1 ambient floor: control arms 0/227, 0/114 -> any lossy at n>=100: False
    R2 sampling artefact: replica 9/185 = 4.86% (need n>=150 and >=2.00%): True
    R3 mechanical delta: replica losses=9 (need 0 over >=150), shipped 1.06% (need >=2.00%), Fisher p=0.0342 (need <0.05): False
    R4 load saturation: rates 0.00%@10fps -> 0.98%@15fps -> 1.06%@20fps; monotone non-decreasing: True; 10fps rate < 3/108 (2.78%): True; 20fps rate >= 2.78%: False -> False
    R5 non-reproduction: shipped rounds on both devices all zero-loss: False (lossy rounds: 1 lost (round 1), 1 lost (round 3), 3 lost (round 0), 1 lost (round 1))

(i) Proposed-threshold derivation inputs (shipped path, 20 FPS only)
    pooled shipped-path evidence: 04-06 UAT 9/267 + shipped arm 2/189 + fallback shipped 4/84
    = 15/540 = 2.78%  wilson 95% CI [1.69%, 4.53%]
    worst shipped-path round in this evidence: 3/37 = 8.11%
    at p = 2.78% (pooled evidence rate): P(round<=9%) = 0.9920, P(all 3 rounds) = 0.9761, P(pooled<=5% over 135) = 0.9166
    at p = 3.37% (04-06 UAT rate): P(round<=9%) = 0.9826, P(all 3 rounds) = 0.9488, P(pooled<=5% over 135) = 0.8278
```

## Rules fired

Applying R1–R5 exactly as pre-declared in `04-09-PLAN.md`:

- **R1 (ambient floor) — NOT fired.** Both control arms are lossless: 0/227 on Tiles I
  and 0/114 on Tiles II (table h). Single-shot queries without streaming are clean on
  this network; the loss is streaming-induced, not ambient. R1's recalibration ground
  (0% unattainable even without the gate) does not apply.

- **R2 (sampling artefact confirmed) — FIRED.** The spike-faithful replica arm — the
  spike 003 methodology re-run at proper power on the same device in the same session —
  lost 9/185 = 4.86% (n ≥ 150, ≥ 2%; table a). Table (d) shows the replica had ample
  power to hold a genuinely lossless methodology at zero: P(0 losses in 185 | p = 3.37%)
  = 0.0018. It did not. Spike 003's 0/50 was therefore a small-sample draw from a lossy
  distribution — exactly the outcome the forensics doc showed had an 18% probability
  even at the UAT's measured rate. **H2 is confirmed. Per R2, combined with R4's answer,
  the route is recalibration — there is no methodology delta to fix.**

- **R3 (mechanical delta, H1-fixable) — NOT fired.** R3 required the replica to hold
  0 losses over ≥ 150 queries while the shipped arm lost ≥ 2%. The opposite occurred:
  the replica (4.86%) lost significantly MORE than the shipped path (1.06%), Fisher
  two-sided p = 0.0342 (table c). The only statistically significant methodology
  difference points in the direction that favours the shipped implementation — the
  enumerated mechanical differences from the spike 003 forensics (per-packet awaited
  sends vs synchronous burst; raw-socket vs DeviceConnection prober) offer nothing for
  a fix plan to close. No mechanical-difference ranking is produced, as R3 did not fire.

- **R4 (load saturation, H1-floor) — NOT fired.** The FPS trend is monotone
  non-decreasing (0.00% @ 10 → 0.98% @ 15 → 1.06% @ 20; table f) and the 10 FPS rate
  sits below its own rule-of-three bound, but the 20 FPS shipped rate (1.06%) is BELOW
  the 10 FPS bound (2.78%), not at or above it. The loss at the ANIM-03 operating point
  is not distinguishable as the device saturating at its ~20 msg/s limit. R4's specific
  "measured saturation floor" framing is therefore not available — the residual loss is
  real but small, present under both methodologies and on both devices (table g), and
  not proven to be FPS-load saturation.

- **R5 (non-reproduction) — NOT fired.** Lossy shipped rounds occurred on both devices
  (rounds 1 and 3 on Tiles I; rounds 0 and 1 on Tiles II). The 04-06 FAIL reproduces;
  a plain re-run route has no evidential basis. By table (d)'s formula, a byte-identical
  3-round re-run (~135–150 queries) at the measured rates would pass the fixed 0% gate
  with probability of the order of table (d)'s P(0 in 150) = 0.0058 — a near-certain
  repeat FAIL.

**Clustering note (no rule keys on this; recorded for completeness):** both lost
shipped-arm queries were sent with the ack gate saturated (outstanding = 2) versus a
median of 1 for successful queries, with 28–37 non-gated frames inside their 2 s query
windows (table e). This is consistent with loss concentrating in the device's busiest
moments, but with only 3 lost events in the shipped/sweep arms it supports no mechanical
claim beyond what R2–R4 already established.

## Verdict

**H2** — the ANIM-03 0% concurrent-query-loss criterion was a spike-003 small-sample
miscalibration, not evidence of a defect in the shipped implementation.

Fired rule: **R2** (with the spike 003 forensics having already settled the calibration
premise). Non-fired rules R1/R3/R4/R5 exclude, respectively: an ambient network floor,
a fixable mechanical delta (the shipped path significantly OUTPERFORMS the spike
methodology, Fisher p = 0.0342), a demonstrated FPS-saturation floor, and
non-reproduction. The rules do not conflict: R2's route stands, with R4's negative
answer qualifying the floor as "small residual streaming-concurrency loss" rather than
"20 FPS saturation".

The route the analysis supports is **recalibrate**: an operator-authored amendment to
the criterion, followed by a 04-06 re-run under the amended criterion. The measured
shipped-path pooled loss of 2.78% (Wilson 95% upper 4.53%; table i) remains roughly a
five-fold improvement over the 14.6% blind-fire baseline the gate was built to beat.

## Consequences per route

- **fix (H1-fixable route):** a follow-up TDD src/ change plan at the 04-01..04-04
  standard (RED suite first, 100% branch coverage), then a 04-06 re-run unchanged.
  **Not supported by this evidence:** R3 did not fire and the only significant
  methodology difference favours the shipped path — there is no identified mechanical
  delta for a fix plan to close. Choosing this route would first require naming what to
  fix, which the evidence does not do.

- **recalibrate (the route this analysis supports):** the OPERATOR authors an amendment
  to ROADMAP success criterion 3, the REQUIREMENTS ANIM-03 wording, and the harness
  `MAX_QUERY_LOSS_PCT` constant in `uat_ack_stream.py`; a follow-up plan applies the
  operator-approved wording (nothing is edited by 04-09); then 04-06 re-runs under the
  amended criterion, and its Task 2 visual checkpoint plus all of 04-07 unblock behind
  it. Proposed amendment text is below, marked NOT applied.

- **rerun (non-reproduction route):** re-run 04-06 byte-identical. **Not supported:**
  R5 did not fire — the loss reproduced on both devices, and at the measured rates a
  re-run passes the fixed 0% gate with probability of order 0.6% (table d, n = 150).
  This route would defer a reproducible outcome to the next FAIL.

- **investigate (ambiguous route):** a further targeted investigation plan. **Not
  indicated:** the rules produced a clean, non-conflicting discrimination (R2 fired;
  the others cleanly did not). No open discriminating question remains that another
  hardware session would answer — the one soft spot (the clustering note's n = 3) feeds
  no rule and would not change the verdict.

Whatever the route, 04-06 Task 2 (visual verdict) and all of 04-07 (Ceiling, ANIM-04)
stay gated until the routing decision lands and its follow-up completes.

## Proposed amendment (NOT applied — operator decision required)

Nothing below has been applied. ROADMAP.md, REQUIREMENTS.md, `uat_ack_stream.py` and
`src/` are untouched by this plan; this section exists solely so the operator decides
from concrete wording. Derivation: the pooled bound is the Wilson 95% upper bound of
all 540 shipped-path 20 FPS queries (4.53% → 5.0%); the per-round bound is the smallest
whole-percent bound above the worst observed shipped-path round (8.11% → 9.0%),
equivalent to allowing 4 losses in a typical 45-query round. Pass probabilities at the
measured rates are in table (i) — the operator may of course set different numbers.

**ROADMAP success criterion 3 — current wording:**

> 3. Hardware UAT (standard Tiles): under 20 FPS streaming, concurrent queries to the
>    same device show no elevated loss — target 0% (blind-fire baseline: 14.6%) — over
>    repeated rounds

**ROADMAP success criterion 3 — proposed replacement:**

> 3. Hardware UAT (standard Tiles): under 20 FPS streaming, concurrent queries to the
>    same device stay within the measured device floor — pooled loss ≤ 5.0% per run and
>    ≤ 9.0% in any single round (evidence-derived: 15/540 = 2.78% pooled across all
>    shipped-path measurements, Wilson 95% upper bound 4.53%, per
>    04-UAT-TILES-run1-FAIL.json, 04-UAT-TILES.json and 04-GAP-INVESTIGATION.json;
>    blind-fire baseline: 14.6%) — over repeated rounds

**REQUIREMENTS ANIM-03 — proposed replacement for the loss clause:**

> **ANIM-03**: Hardware validation on standard Tiles: concurrent queries under 20 FPS
> streaming show loss within the measured device floor (pooled ≤ 5.0% per run,
> ≤ 9.0% per round; blind-fire baseline 14.6%)

**Harness (`uat_ack_stream.py`) — proposed constant/logic change (follow-up plan):**

> `MAX_QUERY_LOSS_PCT: float = 0.0` → `9.0` (per-round check, existing `_evaluate`
> logic unchanged), plus a new pooled check `MAX_POOLED_QUERY_LOSS_PCT: float = 5.0`
> applied across all rounds of a run.
