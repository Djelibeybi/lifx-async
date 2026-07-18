# 04-13 Ruling Record: ANIM-03/ANIM-04 Resolution by Operator Ruling

**Purpose of this document:** record the operator's ruling on ANIM-03/ANIM-04
honestly, get the exact final governing wording approved at one blocking
checkpoint (04-13 Task 2), and stage that wording for verbatim application in
Task 3. Nothing in this document is applied to any governing document until
the operator approves it. The FAIL evidence files this ruling cites
(`04-UAT-SWEEP.json`, `04-UAT-SWEEP-*.json`, `04-UAT-TILES*.json`,
`04-GAP-*.json*`) are never modified — only cited, read-only.

## 1. The ruling, verbatim

After the 04-12 cross-device sweep honestly FAILed its aggregate statistical
bar (5 of 5 valid gate sessions FAILed, 2 INCONCLUSIVE, in the lossiest
network window measured anywhere in this phase — `04-UAT-SWEEP.json`), the
routing options were presented to the operator. Option 2 read, verbatim:

> "Operator judgement now — accept the eight-device directional dossier as
> satisfying the intent, record the ruling, do the Capsule visual, close
> Phase 4."

**The operator's verbatim reply: "2"** (2026-07-17).

Supporting operator context, verbatim, from earlier in the same session:

> "The Tiles are notoriously flaky devices due to suboptimal antenna design,
> so even this amount of improvement is a win. There is also a lot of other
> stuff happening on my PC at the moment and the network, so overall we're
> working in a noisy environment"

## 2. What the ruling is and is not

The statistical sweep criterion was designed (`04-SWEEP-DESIGN.md`),
operator-approved at the 04-12 checkpoint (verbatim reply "1" = approve as
presented, commits `ec87a76` and `4e7640b`), and honestly FAILed in a
degraded network window (`04-UAT-SWEEP.json`, evidence commit `15e2cc0`).

The operator, with full context — including the accumulated multi-session
directional history and the observed anomalous ambient network conditions at
measurement time — accepted the cross-device directional dossier below as
satisfying the requirement's **intent**.

**This is an operator acceptance over a recorded FAIL. It is not, and must
never be described as, a statistical pass.** The sweep's own pre-declared
statistical bar (N_valid ≥ 5 quorum, at most 1 of those valid sessions may
FAIL) was not met — 5 of 5 valid sessions FAILed. The FAIL evidence files
(`04-UAT-SWEEP.json`, the 8 per-device `04-UAT-SWEEP-<serial>.json` files,
`04-UAT-TILES*.json`, `04-GAP-*.json*`) are never modified; this document and
the wording it proposes cite them read-only.

## 3. The dossier (the basis of the ruling — cite, never modify)

| Session | Device(s) | Gated vs comparator | Ratio | Fisher p | Recorded outcome | Evidence file |
|---|---|---|---|---|---|---|
| 04-08 five-arm | Tiles I | shipped 2/189 = 1.06% vs replica 9/185 = 4.86% (blind baseline 14.6%) | ~5.25 (historical pooled 2.78% vs 14.6%) | 0.0342 | threshold-free investigation | 04-GAP-INVESTIGATION.json |
| 04-11 paired run 1 | Tiles I | 4/136 = 2.94% vs 9/125 = 7.20% | 2.45 | 0.0973 | VALID FAIL | 04-UAT-TILES-paired-run1-FAIL.json |
| 04-11 paired run 2 | Tiles I | 7/127 = 5.51% vs 11/113 = 9.73% | 1.77 | 0.1601 | VALID FAIL | 04-UAT-TILES.json |
| 04-12 sweep | 8 devices, one attempt each | gated 13.7–38.9% vs blind 25.9–94.7% | 1.28–3.38 | 0.018–0.184 (Capsule 1e-12) | aggregate FAIL (5/5 valid FAIL, 2 INCONCLUSIVE) | 04-UAT-SWEEP.json + 8 per-device JSONs |

The 04-12 sweep's per-device rows, reproduced from `04-12-SUMMARY.md` for the
complete cited record:

| Device | Role | Outcome | Gated pooled | Blind pooled | Fisher p | Ratio | Validity |
|---|---|---|---|---|---|---|---|
| Playroom Luna | gate | FAIL | 24/81 = 29.63% | 29/69 = 42.03% | 0.0790 | 1.42 | valid |
| Dining Room Table Candle | gate | INCONCLUSIVE | 2/155 = 1.29% | 5/140 = 3.57% | 0.1841 | 2.77 | ambient n=90 < 100 (V2) |
| Makerspace Candle | gate | FAIL | 27/77 = 35.06% | 30/67 = 44.78% | 0.1544 | 1.28 | valid |
| Makerspace Tube | gate | FAIL | 24/86 = 27.91% | 28/73 = 38.36% | 0.1094 | 1.37 | valid |
| Makerspace Ceiling | gate | FAIL | 24/79 = 30.38% | 28/68 = 41.18% | 0.1166 | 1.36 | valid |
| Playroom Ceiling | gate | FAIL | 28/72 = 38.89% | 32/54 = 59.26% | 0.0184 | 1.52 | valid |
| My Office Ceiling Capsule | gate | INCONCLUSIVE | 23/82 = 28.05% | 36/38 = 94.74% | 1.0e-12 | 3.38 | 2 gated rounds delivered_ratio < 0.50 (V3) |
| System Test Tiles II | reference | FAIL | 14/102 = 13.73% | 22/85 = 25.88% | 0.0280 | 1.89 | valid (never counted) |

**One-line summary:** the gated arm won directionally in **every session ever
measured** across this phase — 8 devices, 2 radio generations, ~10 sessions,
ratios 1.28x–5.25x — while the ambient loss floor swung ~10x between session
windows (0/113 ambient loss in 04-11 vs gated losses of 13.7%–38.9% in the
04-12 window). The statistical certification bar was never cleared in a
single session window because the environment's ambient loss floor is
volatile session-to-session, not because the flow control fails to help.

## 4. The dims correction, verbatim

The operator's correction, verbatim (2026-07-17):

> "26"x13" is the physical size of the Ceiling. It has 128 zones arranged in
> 8 rows of 16"

**The corrected facts:** My Office Ceiling Capsule has a **16-wide × 8-high
zone grid (128 zones)**; its **physical panel is 26 in × 13 in**. Every
governing reference that swapped physical inches for a zone-grid figure (the
"13×26 Capsule" wording carried through `04-SWEEP-DESIGN.md`,
`04-06-PLAN.md`/`04-07-PLAN.md` supersession notices, and the applied
ANIM-04/criterion-4 wording) was an early-planning units mix-up — physical
inches were used where a zone count belonged.

**What the sweep already validated against the true dims:** the harness's
`expected_packets_per_frame()` is derived independently from the REPORTED
chain dimensions on every session — never a hard-coded per-product constant.
For the Capsule's actual reported chain (16×8), it correctly computed 3
packets/frame (64 // 16 = 4 rows/packet, ceil(8/4) = 2 Set64, +1
CopyFrameBuffer = 3), and every gated frame across all 3 rounds matched that
expectation (`packet_shape_ok: true` on every round,
`04-UAT-SWEEP-d073d587daab.json`). The CopyFrameBuffer ack-probe attachment
(D4-04) is confirmed: every gated round recorded ≥ 1 ack RTT sample (median
150.0–150.2 ms across the 3 gated rounds, well under the 1 s expiry tuning).
The dims mix-up is a roster-documentation error corrected here — it never
affected the harness's measurement, which always worked from the reported
chain, not the roster's assumed geometry.

**Scope rule:** governing/live documents are corrected (ROADMAP, REQUIREMENTS,
live plan bullets, harness comments); historical records
(`04-SWEEP-DESIGN.md`, prior SUMMARYs, evidence JSONs) are left as records of
what was believed/measured at the time and are not rewritten.

## 5. Proposed final wording (complete, ready to apply verbatim)

Nothing below has been applied. ROADMAP.md, REQUIREMENTS.md, STATE.md,
`uat_ack_stream.py`, 04-06-PLAN.md and 04-07-PLAN.md are untouched by this
task. This section exists solely so the operator decides from concrete
wording (04-09/04-11/04-12 precedent). 04-13 Task 3 applies the approved (or
operator-amended) wording verbatim.

### (i) ROADMAP Phase 4 success criterion 3 — proposed replacement

> 3. Hardware UAT (cross-device paired sweep — resolved by operator ruling):
>    the operator-approved cross-device paired-sweep criterion
>    (`04-SWEEP-DESIGN.md`) ran once per device over the 7-device
>    healthy-radio matrix roster and honestly FAILed its aggregate
>    statistical bar on 2026-07-17 — 5 of 5 valid gate sessions FAILed, 2
>    INCONCLUSIVE, in the lossiest ambient network window measured anywhere
>    in this phase (`04-UAT-SWEEP.json`: gated pooled loss 13.7%–38.9% vs
>    blind 25.9%–94.7%). The gated arm nonetheless won directionally in every
>    one of the 8 sessions (ratios 1.28x–3.38x), consistent with every prior
>    session measured across the phase (~10 sessions, 2 radio generations,
>    ratios 1.28x–5.25x: 04-GAP-INVESTIGATION.json, 04-UAT-TILES.json,
>    04-UAT-TILES-paired-run1-FAIL.json, 04-UAT-SWEEP.json). **Resolution is
>    BY OPERATOR RULING** (verbatim reply "2", 2026-07-17) accepting this
>    cross-device directional dossier as satisfying the requirement's intent
>    — an acceptance over a recorded FAIL, never a statistical pass; the FAIL
>    evidence stands unmodified. The operator's visual smoothness verdict on
>    the Capsule (04-13 Task 4) completes ANIM-03.

### (ii) ROADMAP Phase 4 success criterion 4 — proposed replacement

> 4. Hardware UAT (large-matrix framebuffer path): the framebuffer-path
>    evidence captured in the 04-12 sweep sessions of the three ceiling-class
>    devices (Makerspace Ceiling, Playroom Ceiling, My Office Ceiling
>    Capsule) stands — every sent gated frame matched the chain-dims-derived
>    row-aligned packets/frame expectation on every round
>    (`packet_shape_ok: true` in all per-device JSONs), every gated round
>    recorded ≥ 1 CopyFrameBuffer ack RTT sample (medians 50.1–50.2 ms on the
>    two 8×8 ceilings, 150.0–150.2 ms on the Capsule's 16×8 chain — the D4-04
>    ack-probe attachment confirmed on all three). My Office Ceiling Capsule
>    is **16×8 zones (128 zones, 8 rows of 16; 26 in × 13 in physical)** —
>    supersedes the earlier units mix-up that attributed physical inches to
>    the zone grid (operator correction verbatim, 2026-07-17). The operator's
>    visual geometry verdict on the Capsule (04-13 Task 4) completes ANIM-04.

### (iii) REQUIREMENTS ANIM-03 — proposed replacement (checkbox stays unchecked)

> - [ ] **ANIM-03**: Hardware validation resolved by operator ruling: the
>   cross-device paired-sweep criterion ran once per the 7-device
>   healthy-radio matrix roster and honestly FAILed its aggregate
>   statistical bar on 2026-07-17 (5/5 valid gate sessions FAILed, 2
>   INCONCLUSIVE — `04-UAT-SWEEP.json`), while the gated arm won
>   directionally in every session ever measured across the phase (8
>   devices, 2 radio generations, ~10 sessions, ratios 1.28x–5.25x). By
>   operator ruling (verbatim reply "2", 2026-07-17) the cross-device
>   directional dossier is accepted as satisfying the requirement's intent —
>   an acceptance over a recorded FAIL, never a statistical pass. Completed
>   by the operator's visual smoothness verdict on My Office Ceiling Capsule
>   (04-13 Task 4).

### (iv) REQUIREMENTS ANIM-04 — proposed replacement (checkbox stays unchecked)

> - [ ] **ANIM-04**: Flow control covers the large-matrix framebuffer path
>   (multi-packet frames + buffer swap), hardware-validated on the 04-12
>   sweep's three ceiling-class devices: every sent gated frame matched the
>   chain-dims-derived row-aligned packets/frame expectation on every round,
>   CopyFrameBuffer ack RTT evidence was recorded on every gated round (the
>   D4-04 ack-probe attachment confirmed on all three devices). My Office
>   Ceiling Capsule is 16×8 zones (128 zones; 26 in × 13 in physical —
>   supersedes the earlier units mix-up, operator correction verbatim,
>   2026-07-17). Completed by the operator's visual geometry verdict on the
>   Capsule (04-13 Task 4).

### (v) Final supersession notes for 04-06-PLAN.md and 04-07-PLAN.md

**Appended to 04-06-PLAN.md (after its existing notices; every other line
byte-identical):**

> **FINAL SUPERSESSION NOTICE (2026-07-17, applied by 04-13):** The 04-12
> aggregate sweep FAILed (5/5 valid sessions FAIL), so its Task 5 consolidated
> visual checkpoint never executed. By operator ruling (verbatim reply "2",
> 2026-07-17, `04-RULING.md`), ANIM-03/ANIM-04 certification is resolved by
> operator acceptance of the cross-device directional dossier, and visual
> ownership moves to **04-13 Task 4** — the same Capsule smoothness+geometry
> checkpoint 04-12 Task 5 would have run. This plan remains fully superseded;
> do not execute any task from it.

**Appended to 04-07-PLAN.md (after its existing notice; every other line
byte-identical):**

> **FINAL SUPERSESSION NOTICE (2026-07-17, applied by 04-13):** The 04-12
> aggregate sweep FAILed (5/5 valid sessions FAIL), so its Task 5 consolidated
> visual checkpoint never executed. By operator ruling (verbatim reply "2",
> 2026-07-17, `04-RULING.md`), ANIM-03/ANIM-04 certification is resolved by
> operator acceptance of the cross-device directional dossier, and visual
> ownership moves to **04-13 Task 4** — the same Capsule smoothness+geometry
> checkpoint 04-12 Task 5 would have run. This plan remains superseded in
> full; do not execute any task from it.

### (vi) STATE.md gate texts

**Visual-pending text (applied in 04-13 Task 3, immediately after wording
approval):**

> **UAT sequencing gate (updated 2026-07-17, ruling recorded):** the 04-12
> cross-device sweep honestly FAILed its aggregate statistical bar (5/5
> valid gate sessions FAIL, 2 INCONCLUSIVE — `04-UAT-SWEEP.json`), with the
> gated arm winning directionally in every session ever measured (8 devices,
> ratios 1.28x–5.25x). By operator ruling (verbatim reply "2", 2026-07-17,
> `04-RULING.md`) the cross-device directional dossier is accepted as
> satisfying ANIM-03/ANIM-04's intent — an acceptance over a recorded FAIL,
> never a statistical pass. The Capsule's dims are corrected (16×8 zones,
> 128 zones, 26 in × 13 in physical). The only remaining item is the
> operator's dual visual verdict (smoothness + geometry) on My Office
> Ceiling Capsule at 04-13 Task 4; ANIM-03/ANIM-04 checkboxes flip only after
> an approved verdict.

**Cleared close-out text (applied in 04-13 Task 5, approved-verdict branch
only):**

> **UAT sequencing gate (cleared 2026-07-17):** ANIM-03/ANIM-04 are complete.
> Resolution: by operator ruling (verbatim reply "2", 2026-07-17,
> `04-RULING.md`) the cross-device directional dossier from the 04-12 sweep
> (aggregate statistical FAIL, 5/5 valid sessions FAIL, gated arm winning
> directionally in every session ever measured, ratios 1.28x–5.25x) was
> accepted as satisfying the requirements' intent — an acceptance over a
> recorded FAIL, never a statistical pass — and the operator gave an
> explicit dual approval verdict (smoothness + geometry) on My Office
> Ceiling Capsule's gated streaming round at 04-13 Task 4. The Capsule's
> dims are corrected everywhere they govern (16×8 zones, 128 zones, 26 in ×
> 13 in physical). No gate remains open for Phase 4.

### (vii) Harness comment-only dims corrections (`uat_ack_stream.py`)

No behaviour change; comment/docstring text only.

**(a) Module docstring** (currently: "the 13x26 Capsule still expects 8, a
16x8 ceiling expects 3") — replace with wording that keeps 13x26 as a
hypothetical chain-geometry example (matching `expected_packets_per_frame()`'s
own worked-example convention) and identifies the Capsule correctly:

> `expected_packets_per_frame()` -- a 13x26 chain geometry expects 8
> packets/frame; the Capsule itself REPORTS a 16x8 chain (128 zones; 26 in x
> 13 in physical) and expects 3; 04-SWEEP-DESIGN.md section 5, superseding
> the old hard-coded 8

**(b) `EXPECTED_CEILING_PACKETS_PER_FRAME` comment block** — the constant
value stays `8` (a superseded-assumption reference value surfaced in the
thresholds JSON; changing it would alter recorded output), but the comment
must say the value reflects the superseded roster assumption and that the
Capsule's REPORTED chain is 16×8 → 3:

> # 13x26 large-tile Ceiling (superseded roster assumption): 7 row-aligned
> # Set64 packets + 1 final CopyFrameBuffer (assumption A2 -- see
> # src/lifx/animation/packets.py). Kept as a documented reference value (see
> # `_thresholds()`); the actual per-frame assertion now uses
> # `expected_packets_per_frame()`, computed from the REPORTED chain
> # dimensions of whichever ceiling-class device is streaming
> # (04-SWEEP-DESIGN.md section 5). My Office Ceiling Capsule's REPORTED
> # chain is 16x8 (128 zones; 26 in x 13 in physical, not 13x26) and expects
> # 3, measured 2026-07-17 (04-UAT-SWEEP-d073d587daab.json) -- this constant
> # is a superseded reference value, not the Capsule's actual expectation.

**(c) `expected_packets_per_frame()` docstring worked example** — relabel the
13x26 row as a plain chain-geometry example, add the Capsule's true
attribution:

> Worked examples: 13x26 chain geometry -> 64//13=4 rows/packet, ceil(26/4)=7
> Set64, +1 CopyFB = 8; 16x8 ceiling (the Capsule's REPORTED chain) ->
> 64//16=4, ceil(8/4)=2, +1 = 3; five 8x8 tiles -> 64 pixels <= 64 -> one
> Set64 per tile, no CopyFB = 5.

## 6. What this ruling does NOT change

- The shipped `src/` flow-control behaviour (ANIM-01/ANIM-02, already
  complete and unaffected by this ruling).
- The harness's measurement semantics: `_evaluate`, the paired-gate
  constants, the aggregation rule, and `expected_packets_per_frame()`'s
  arithmetic are all byte-identical to their 04-12 values.
- Any evidence file: `04-UAT-SWEEP.json`, the 8 per-device
  `04-UAT-SWEEP-<serial>.json` files, `04-UAT-TILES*.json`,
  `04-GAP-*.json*` are cited, never edited.
- The honest FAIL record itself — the sweep's aggregate statistical outcome
  stays recorded as FAIL forever; this ruling documents an operator decision
  layered on top of that honest record, not a retroactive change to it.
