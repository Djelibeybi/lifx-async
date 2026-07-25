# 04-11 Criterion Design: Paired-Relative ANIM-03 Gate

**Question:** what should replace the twice-FAILed absolute ANIM-03 gate, given the
operator's routing decision (verbatim reply "2" — redesign the gate shape to paired
and relative) after the amended absolute gate (the operator's own 9.0%/round + 5.0%
pooled) FAILed twice in a fresh session at pooled 11.21% then 5.74%?

**Discipline:** this brief follows the 04-09 pattern — the statistics runner
`criterion_design.py` is committed before its numbers are relied on; the brief adds
no data and adjusts none; nothing below is applied to ROADMAP.md, REQUIREMENTS.md,
`uat_ack_stream.py` or `src/` until the operator approves the complete wording at
the 04-11 blocking checkpoint. Every number in this brief is reproducible with one
command:

```
uv run python .planning/phases/04-animation-flow-control/criterion_design.py
```

The runner hard-codes every evidence count with a per-row source citation and,
wherever the source JSON is on disk, parses it and asserts the hard-coded counts
match — the evidence base is provably faithful to the committed bytes.

## Why the absolute gate cannot work

The same code on the same device (System Test Tiles I, 192.168.19.243) measured
these pooled ack-gated loss rates within one day:

| Session | Evidence | Gated pooled | Wilson 95% CI |
|---------|----------|--------------|----------------|
| B (04-08 shipped arm) | 04-GAP-INVESTIGATION.json | 2/189 = **1.06%** | [0.29%, 3.78%] |
| A (04-06, runs 1+2) | 04-UAT-TILES-run1-FAIL.json + commit 5de88f6 | 9/267 = **3.37%** | [1.78%, 6.28%] |
| C (04-10, runs 1+2) | 04-UAT-TILES-amended-run1-FAIL.json + 04-UAT-TILES.json @ d154ccf | 19/229 = **8.30%** | [5.38%, 12.59%] |

That is a **7.8x session-to-session spread** (1.06% → 8.30%) with the code, device,
FPS, prober cadence and thresholds byte-identical across sessions. Any absolute
threshold calibrated from one session therefore produces coin-flip UATs: a bound
tight enough to be meaningful in session B's environment is unreachable in session
C's, and a bound loose enough for session C certifies nothing in session B.

Both prior calibrations were single-session:

- The original 0% target came from spike 003's **one** 50-query photons round
  (0/50; rule-of-three upper bound ≥ 6%; ≈ 18% chance of a 0/50 draw even at the
  UAT-measured 3.37% rate — settled by the 04-09 analysis, verdict H2).
- The 14.6% blind-fire baseline the gate was built to beat is itself a **single
  41-query session** (6/41; Wilson 95% CI [6.88%, 28.44%]).

The full multi-session evidence table (13 rows, spike 003 + sessions A/B/C, each
row disk-asserted where the source is on disk) is section (1) of the runner output.

The fix is to stop asking "is the absolute number low?" and start asking "in THIS
session's environment, does the ack gate deliver a large measured improvement over
not having it?" — a paired same-session comparison, with the session's own ambient
loss as a validity precondition and a sane absolute ceiling so that "relatively
better but absurdly lossy" can never pass.

## The paired-relative criterion

The full rule, exactly as it will run:

**SESSION SHAPE.** Reachability probe unchanged (exit 2 ENV-ERROR, no streaming,
fallback contract unchanged). Then, on the target device:

1. **Ambient control block**: 60 s, prober only, no streaming.
2. **Alternating rounds, gated first**: G, B, G, B, G, B — 3 rounds per arm,
   30 s each, 10 s rests between every block.
   - **Gated rounds**: the SHIPPED `Animator.send_frame()` ack-gated path at
     20 FPS (unchanged from the existing harness).
   - **Blind-fire rounds**: spike 003 `arm_blind` mechanics at instrument level
     only — per-packet awaited sends of the animator's prebaked templates with the
     ack flag cleared, no probes, no gating, on the instrument's own transport.
     D4-02 upheld: the shipped Animator gains no flow-control toggle; src/ and
     tests/ are untouched.
   - The **IDENTICAL DeviceConnection prober** (max_retries=0, 2 queries/s, 2 s
     timeout) runs in every block — ambient, gated and blind — so the query
     measurement instrument is byte-identical and only the streaming treatment
     differs between arms.

**SESSION VALIDITY** (checked first; any miss → ENV-DEGRADED → outcome
INCONCLUSIVE, exit 3, never PASS, never FAIL):

- **V1**: ambient pooled loss ≤ 2.5%
- **V2**: ambient queries n ≥ 100
- **V3**: every gated round delivered_ratio ≥ 0.50

**PASS RULE** (evaluated only on a valid session):

> session valid AND gated pooled ≤ 9.0% AND
> [ gated pooled ≤ 2.5% OR (Fisher one-sided p < 0.05 AND blind/gated ≥ 2.0) ]

The ceiling profile additionally keeps its unchanged per-gated-round checks:
exactly 8 packets/frame and ≥ 1 ack RTT sample per gated round.

**OUTCOME CONTRACT**: 0 PASS / 1 FAIL / 2 ENV-ERROR / 3 INCONCLUSIVE — all four
defined, all honestly routed. `delivered_ratio` is recorded per round as evidence
but is no longer a pass/fail gate (V3's 0.50 sanity floor is session validity).

## Derivations

Each parameter is derived by a stated rule from named evidence rows (runner
section (2)); none is an unexplained number:

| Parameter | Value | Derivation |
|-----------|-------|------------|
| V1 ambient validity bound | 2.5% | Both healthy-session control arms were lossless: 0/227 (rule-of-three upper 1.32%) and 0/114 (upper 2.63%). A session whose prober-only ambient loss exceeds 2.5% (~3 lost of ~120) is lossier than any healthy session's statistical ceiling and cannot certify anything. |
| V2 minimum ambient sample | n ≥ 100 | Below n = 100 the 2.5% bound has no resolution (rule-of-three at n = 100 is already 3.00%). |
| V3 delivered-ratio sanity floor | 0.50 | Session validity, NOT pass/fail. The worst gated round ever measured delivered 0.6033 (04-10 run 1 round 0, 21 ack expiries) — 0.50 fires only on sessions more congested than anything in the evidence base. Above it, throttling is the flow control doing its job under ambient congestion: the FEATURE, not a defect. |
| Relative rule significance | Fisher one-sided p < 0.05 | Alpha matches the 04-09 R3 precedent. One-sided (alternative: gated < blind), hypergeometric lower tail. |
| Relative rule point ratio | blind/gated ≥ 2.0 | Conservative floor on "large improvement" — the pooled historical improvement is 5.27x (gated 15/540 = 2.78% pooled vs blind 6/41 = 14.63%). |
| Clean escape | gated pooled ≤ 2.5% | Same bound as V1: gated loss at or below the healthy-ambient ceiling proves non-starvation directly even when the same-session blind arm happens to be low — without it, a clean session could FAIL for lack of a disease to improve on. |
| Absolute ceiling | gated pooled ≤ 9.0% | Continuity with the operator's last-approved bound, now applied pooled. Excludes the worst measured session outright (session C run 1, 11.21% pooled FAILs regardless of any comparator — "relatively better but absurdly lossy" cannot pass). Sits at 0.62x the single-session blind baseline, whose own Wilson 95% lower bound on 6/41 is 6.88% — a ceiling-grazing run still needs the in-session Fisher win. |

## Statistical power

Exact enumeration (no normal approximations): X_g ~ Bin(n, p_g), X_b ~ Bin(n, p_b)
per arm, PASS = ceiling AND (clean escape OR relative rule), session validity
assumed held (its failure routes to INCONCLUSIVE, not FAIL). Runner section (3),
verbatim:

| Scenario (p_g, p_b) | n=100 P(PASS) | n=120 P(PASS) | n=140 P(PASS) |
|----------------------|---------------|---------------|---------------|
| Historical rates (0.0278, 0.146) | **0.9008** | 0.9443 | 0.9696 |
| Uniform degradation +3 pts (0.0578, 0.176) | 0.7812 | 0.8190 | 0.8669 |
| Proportional 5.25x at severity 0.0106 | 0.9131 | 0.9617 | 0.9422 |
| Proportional 5.25x at severity 0.0337 | 0.9501 | 0.9748 | 0.9888 |
| Proportional 5.25x at severity 0.0574 | 0.9383 | 0.9154 | 0.9401 |
| Proportional 5.25x at severity 0.0830 | 0.6828 | 0.5883 | 0.6213 |

**Adjustment rule (declared before computing):** if P(PASS) at the historical
rates with n = 100 came out below 0.85, rounds per arm would rise from 3 to 4.
Observed P(PASS | historical, n = 100) = **0.9008** — the rule did **not** fire;
3 rounds per arm stands.

**Declared per-arm sample expectation:** ~100–140 pooled queries per arm over 3
rounds (healthy rounds yield ~44–48 queries at 2 q/s; degraded rounds 30–41
because each lost query holds the prober for the 2 s timeout). The power table
brackets exactly this range.

**Honest reading of the low-power cells:** the +3-points and severity-0.083
scenarios have P(PASS) in the 0.59–0.87 range — deliberately. Those are sessions
whose gated loss sits at 5.8–8.3% pooled, pressed against the 9.0% ceiling; the
criterion is designed NOT to pass such sessions easily. A session that degraded
(rather than proportionally scaled) will also often trip V1 ambient validity and
route to INCONCLUSIVE rather than FAIL.

## Retrodiction

The proposed rule applied to every historical session where its inputs exist
(runner section (4)):

| Session | Inputs available | Outcome under the proposed rule |
|---------|------------------|--------------------------------|
| B (04-08) | ambient 0/227, gated 2/189, delivered all ≥ 0.50 | **PASS** via the clean escape (1.06% ≤ 2.5%, ambient valid; no comparator needed) |
| C run 1 (04-10) | gated 12/107 = 11.21% | **FAIL** the 9.0% ceiling outright, regardless of any comparator (no ambient block was measured; the ceiling verdict does not depend on one) |
| Spike 003 | gated 0/50, blind 6/41, ambient n=20 | Relative rule satisfied (Fisher one-sided p = **0.0067** < 0.05; ratio satisfied) but **INCONCLUSIVE** on ambient power — its baseline was n = 20 < 100 (validity V2) |
| A (04-06) | gated 9/267 only | **INDETERMINATE** — no paired blind arm was run |
| C run 2 (04-10) | gated 7/122 only | **INDETERMINATE** — no paired blind arm was run |

Honest note: the retrodiction cannot manufacture comparators that were never
measured — sessions A and C-run-2 lacking a blind arm is precisely the gap this
redesign closes.

Cross-check (runner section (5)): the Fisher machinery reproduces the committed
04-08 reference — two-sided p on shipped [2, 187] vs replica [9, 176] = **0.0342**;
one-sided p on the same table = 0.0284 (positive, ≤ two-sided). ✓

## Expected wall time

~5.25 min per attempt: 60 s ambient + 6 × 30 s rounds + 6 × 10 s rests + setup
(reachability probe, chain query, per-round animator setup). Hard attempt budget
of 2 → **≤ ~11 min of device time** on the primary Tiles (192.168.19.243;
fallback 192.168.18.62 on ENV-ERROR only).

## Final wording (PROPOSED — NOT applied; operator decision required)

Nothing below has been applied. ROADMAP.md, REQUIREMENTS.md, `uat_ack_stream.py`
and `src/` are untouched by this plan's Task 1; this section exists solely so the
operator decides from concrete wording (04-09 precedent). Task 3 applies the
approved (or operator-amended) wording verbatim.

**(i) ROADMAP Phase 4 success criterion 3 — proposed replacement:**

> 3. Hardware UAT (standard Tiles): a paired same-session run — ambient control (prober only, no streaming), then alternating ack-gated and instrument-level blind-fire rounds under 20 FPS streaming — shows ack-gated concurrent-query loss is a large measured improvement over same-session blind-fire (one-sided Fisher exact p < 0.05 AND >= 2x lower, OR gated pooled loss <= 2.5%) within an absolute ceiling of 9.0% pooled gated loss; sessions failing validity (ambient loss > 2.5%, ambient n < 100, or any gated round delivered < 0.50) are ENV-DEGRADED → INCONCLUSIVE, never a pass or a fail (evidence-derived per 04-CRITERION-DESIGN.md across all 20 FPS shipped-path sessions; single-session blind-fire baseline 14.6% = 6/41) — over repeated rounds

**(ii) REQUIREMENTS ANIM-03 — proposed replacement (checkbox stays unchecked):**

> - [ ] **ANIM-03**: Hardware validation on standard Tiles: under 20 FPS streaming, ack-gated
>   concurrent-query loss is a large measured improvement over same-session instrument-level
>   blind-fire (Fisher one-sided p < 0.05 and >= 2x lower, or gated pooled <= 2.5%) within a
>   9.0% pooled absolute ceiling; ambient-degraded sessions are INCONCLUSIVE, never PASS or FAIL

**(iii) Harness gate contract (`uat_ack_stream.py`) — proposed:**

Constants (names fixed so the results JSON schema is stable):

```
AMBIENT_CONTROL_SECONDS    = 60.0
MAX_AMBIENT_LOSS_PCT       = 2.5     # session validity V1
MIN_AMBIENT_QUERIES        = 100     # session validity V2
MIN_GATED_DELIVERED_SANITY = 0.50    # session validity V3 (not pass/fail)
FISHER_ALPHA               = 0.05    # relative rule significance
MIN_IMPROVEMENT_RATIO      = 2.0     # relative rule point-ratio floor
CLEAN_GATED_LOSS_PCT       = 2.5     # clean escape
MAX_GATED_POOLED_LOSS_PCT  = 9.0     # absolute ceiling
INTER_ROUND_REST_SECONDS   = 10.0
```

The three superseded pass/fail constants are deleted: the per-round loss gate
(`MAX_QUERY_LOSS_PCT`), the pooled-only loss gate (`MAX_POOLED_QUERY_LOSS_PCT`)
and the 0.85 delivered floor (`MIN_DELIVERED_RATIO`). The ceiling-profile checks
(`EXPECTED_CEILING_PACKETS_PER_FRAME = 8`, `CEILING_MIN_ACK_RTT_SAMPLES = 1`) and
the `BASELINE` dict (historical fact, not a threshold) are kept.

Session shape: reachability probe → ambient control (60 s, prober only) →
alternating G, B, G, B, G, B rounds (30 s each, 10 s rests, identical prober in
every block; `--rounds` means rounds PER ARM, default 3). Blind-fire is
instrument-level only (own transport, ack flag cleared on every packet, no
probes, no gating).

Evaluation order: validity first (V1/V2/V3 miss → INCONCLUSIVE, terminal); then
PASS RULE: gated pooled ≤ 9.0% AND (gated pooled ≤ 2.5% OR (Fisher one-sided
p < 0.05 AND blind/gated ≥ 2.0)). Improvement ratio treated as satisfied when
gated lost = 0 and blind lost > 0; when both arms lost 0 the clean escape already
decides. Ceiling profile keeps its unchanged per-gated-round checks.

Exit contract: **0 PASS / 1 FAIL / 2 ENV-ERROR / 3 INCONCLUSIVE**. Results JSON
records the ambient block, all rounds in execution order (each tagged
`"arm": "gated"` or `"arm": "blind"`), `gated_pooled` and `blind_pooled`
({lost, n, loss_pct}), `fisher_one_sided_p`, `improvement_ratio` (null when
undefined), `session_valid`, `validity_reasons`, `outcome`, `pass`, and the new
thresholds block.

**What changes for downstream plans:** the per-round 9.0% / pooled 5.0% /
delivered 0.85 gates are replaced wholesale; delivered_ratio moves from pass/fail
to a 0.50 session-validity sanity floor; INCONCLUSIVE (exit 3) becomes a declared
outcome; 04-07 (Ceiling) inherits the paired shape with its ceiling-specific
checks unchanged; 04-06 Task 2 remains the sole owner of the ANIM-03 visual
checkpoint and executes only after this plan's paired headless PASS.
