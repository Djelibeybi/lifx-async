# 04-12 Sweep Design: Cross-Device ANIM-03/ANIM-04 Certification

**Question:** what replaces the twice-FAILed single-device Tiles paired gate, given the
operator's ruling that the gen3 Tiles radios are notoriously flaky, the measured
consistent 2–2.5x improvement on them IS a win, and certification should move to
different targets?

**Discipline:** this brief follows the 04-11 pattern — the statistics runner
`sweep_design.py` is committed with the brief; every number below is reproducible with
one command; nothing in this brief is applied to ROADMAP.md, REQUIREMENTS.md,
`uat_ack_stream.py` or `src/` until the operator approves the complete final wording at
the 04-12 blocking checkpoint (exactly one ask; protocol fixed before data):

```
uv run python .planning/phases/04-animation-flow-control/sweep_design.py
```

The runner asserts the paired double-FAIL evidence counts against the committed on-disk
JSONs, re-derives the per-device pass probability at the historical rates by exact
enumeration BEFORE using it as an aggregation input, and computes every aggregation
number by exact binomial enumeration (`math.comb`, no approximations).

## 1. The operator ruling, verbatim

After the second valid-session paired FAIL on System Test Tiles I, the operator ruled:

> "We need to try different targets. The Tiles are notoriously flaky devices due to
> suboptimal antenna design, so even this amount of improvement is a win. There is
> also a lot of other stuff happening on my PC at the moment and the network, so
> overall we're working in a noisy environment"

Derived rulings this design encodes:

1. **Tiles ruling:** gen3 Tiles radios are known-flaky; the measured consistent
   2–2.5x improvement on them IS a win; Tiles loss numbers must not gate
   certification. System Test Tiles II (192.168.18.62) stays in the sweep as
   known-bad-radio REFERENCE DATA only — never in the aggregation numerator or
   denominator.
2. **Cross-device retarget:** ANIM-03 certification moves from "standard Tiles" to a
   cross-device paired sweep over healthy-radio matrix devices. Paths (outdoor
   lights) are excluded — unsociable hour. All sweep targets have been disabled in
   Home Assistant (operator confirmed — no status-polling interference).

### The operator-approved sweep roster (discovery-verified reachable at planning time)

| # | Device | IP (DHCP — may drift) | Serial | Class → profile | Role |
|---|--------|----------------------|--------|-----------------|------|
| 1 | Playroom Luna | 192.168.19.182 | d073d5893c04 | MatrixLight (product 219, gen4) → tiles | gate |
| 2 | Dining Room Table Candle | 192.168.18.81 | d073d55956e8 | MatrixLight → tiles | gate |
| 3 | Makerspace Candle | 192.168.18.32 | d073d582bff4 | MatrixLight → tiles | gate |
| 4 | Makerspace Tube | 192.168.19.199 | d073d5866777 | MatrixLight → tiles | gate |
| 5 | Makerspace Ceiling | 192.168.19.119 | d073d5a132d9 | CeilingLight → ceiling | gate + ANIM-04 evidence |
| 6 | Playroom Ceiling | 192.168.19.82 | d073d5a132b8 | CeilingLight → ceiling | gate + ANIM-04 evidence |
| 7 | My Office Ceiling Capsule | 192.168.19.231 | d073d587daab | CeilingLight (product 201, 13×26) → ceiling | gate + ANIM-04 evidence + THE visual device |
| 8 | System Test Tiles II | 192.168.18.62 | d073d53e11be | MatrixLight (gen3 Tiles) → tiles | REFERENCE DATA ONLY — never gates |

IPs are DHCP leases and may drift: device resolution is serial-authoritative — the
serial is the device's identity; the roster IP is only a serial-checked fast path,
with broadcast discovery by serial (`find_by_serial`) as the fallback. A single
moved/unreachable device becomes that device's ENV-ERROR row, never a whole-sweep
abort.

## 2. The per-device rule, restated UNCHANGED

The paired-relative rule from 04-CRITERION-DESIGN.md is reused byte-for-byte — the
operator approved it at the 04-11 checkpoint (verbatim reply "1") and **no per-device
parameter is re-tuned by this design**:

- **Session shape:** reachability probe → 60 s ambient control block (prober only,
  no streaming) → alternating rounds gated-first (G, B, G, B, G, B — 3 rounds per
  arm, 30 s each, 10 s rests), with the IDENTICAL DeviceConnection prober
  (max_retries=0, 2 queries/s, 2 s timeout) in every block.
- **Session validity** (checked first; any miss → INCONCLUSIVE, exit 3, never PASS,
  never FAIL): V1 ambient pooled loss ≤ 2.5%; V2 ambient queries n ≥ 100; V3 every
  gated round delivered_ratio ≥ 0.50.
- **PASS rule** (valid sessions only): gated pooled ≤ 9.0% AND (gated pooled ≤ 2.5%
  clean escape OR (Fisher one-sided p < 0.05 AND blind/gated ≥ 2.0)).
- **Exit contract:** 0 PASS / 1 FAIL / 2 ENV-ERROR / 3 INCONCLUSIVE.

The ceiling profile keeps its per-gated-round checks (packets/frame assertion and
≥ 1 ack RTT sample per gated round) with exactly ONE generalisation: the
packets/frame expectation becomes **chain-dims-derived** (section 5) because the
hard-coded 8 is valid only for the 13×26 Capsule, and the sweep adds ceiling-class
devices with other geometries. This changes no constant of the paired gate itself.

## 3. Cross-device aggregation, derived

**Rule family:** sweep PASS iff (valid gate devices N_valid ≥ quorum Q) AND
(per-device PASSes among them ≥ K). The 7 gate devices are the population;
per-device INCONCLUSIVE and ENV-ERROR rows are EXCLUDED from N_valid but always
reported; per-device FAILs count in N_valid; Tiles II is never in either count.

**Exact binomial power** (runner section 4; per-device P(PASS) grid includes the
declared historical 0.9008 — cross-checked by exact enumeration in runner section 2
before use — plus pessimistic 0.85 and optimistic 0.95; healthy radios plausibly
pass via the 2.5% clean escape more often than Tiles I did):

| N_valid | allowed FAILs | K | P@0.85 | P@0.9008 | P@0.95 |
|---------|---------------|---|--------|----------|--------|
| 7 | 0 | 7 | 0.3206 | 0.4813 | 0.6983 |
| 7 | 1 | 6 | 0.7166 | 0.8523 | 0.9556 |
| 7 | 2 | 5 | 0.9262 | 0.9749 | 0.9962 |
| 6 | 0 | 6 | 0.3771 | 0.5343 | 0.7351 |
| 6 | 1 | 5 | 0.7765 | 0.8873 | 0.9672 |
| 6 | 2 | 4 | 0.9527 | 0.9845 | 0.9978 |
| 5 | 0 | 5 | 0.4437 | 0.5931 | 0.7738 |
| 5 | 1 | 4 | 0.8352 | 0.9197 | 0.9774 |
| 5 | 2 | 3 | 0.9734 | 0.9916 | 0.9988 |

**All-must-pass power, surfaced explicitly:** at the historical per-device rate,
requiring 7/7 gives P(sweep PASS) = 0.9008⁷ = **0.4813** — a coin-flip sweep. Any
zero-allowed-FAILs choice would be made with that number in front of the operator,
never blindly. It is not chosen.

**Null scenario (false-pass risk, computed — runner section 3):** under
p_gated = p_blind (flow control gives no improvement) the relative rule cannot
systematically fire (Fisher type-I error ≤ α = 0.05 by construction); only the clean
escape (plus chance Fisher wins at the low rate) can produce a per-device PASS:

| Null scenario (both arms) | per-device P(PASS \| null) | of which clean escape |
|---------------------------|---------------------------|-----------------------|
| 0.0278 (ambient-healthy, low loss) | 0.4717 | 0.4716 |
| 0.146 (lossy, no improvement) | 0.0200 | 0.000023 |

**Choice rule (pre-declared, 04-11 precedent):** minimum acceptable
P(sweep PASS | historical per-device rate, N_valid = 7) = **0.85** (the 04-11
adjustment-rule bar); pick the STRICTEST K meeting it:

- a = 0 (K = N_valid): 0.4813 < 0.85 — rejected
- **a = 1 (K = N_valid − 1): 0.8523 ≥ 0.85 — CHOSEN (strictest meeting the bar)**
- a = 2 (K = N_valid − 2): 0.9749 ≥ 0.85 — not strictest

**Quorum derivation:** a sweep must never certify from a minority of the 7-device
gate roster. At the quorum floor the minimum certifying PASS count is Q − 1;
requiring that to be ≥ a strict majority of 7 (= 4) gives **Q = 4 + 1 = 5**. Below
quorum the sweep is INCONCLUSIVE.

**The chosen rule, one sentence a harness can implement:**

> The sweep PASSes iff at least 5 of the 7 gate devices produce valid sessions
> (N_valid ≥ 5) and at most 1 of those valid sessions is a FAIL (per-device PASSes
> ≥ N_valid − 1); Tiles II never enters either count.

**False-certification argument.** For the chosen K at N_valid = 7 (runner section 4):

- power: P(sweep PASS | historical rates) = **0.8523**
- null: P(sweep PASS | no improvement, both arms 0.0278) = **0.0459**
- null: P(sweep PASS | no improvement, both arms 0.146) = **0.000000** (< 10⁻⁶)

What the rule certifies: on at least a strict roster majority of healthy-radio
devices, ack-gated streaming either measurably beats same-session blind-fire
(significance + ratio) or holds gated loss at the healthy-ambient ceiling. The clean
escape (gated pooled ≤ 2.5%) is an honest per-device PASS path even when the
same-session blind arm happens to be low: gated loss at or below the healthy-ambient
ceiling is DIRECT non-starvation evidence — a device whose queries round-trip at the
healthy floor while streaming is not being starved, which is exactly what ANIM-03
certifies. The low-rate null "pass" (4.59% at sweep level) is precisely a fleet that
is not starving — the requirement's own success condition — while a lossy fleet the
flow control does not help essentially never certifies (< 10⁻⁶).

## 4. Attempt budget and session logistics, derived

**Attempt budget: ONE attempt per device, no per-device re-runs.** The single-device
mode needed a transient-rule-out re-run because one session was the entire evidence;
the sweep's replication is cross-device (7 independent sessions), so a transient hit
on one device is absorbed by the aggregation rule (1 allowed FAIL, INCONCLUSIVE
excluded from N_valid) instead of a re-run — and one-attempt removes any
retry-until-pass surface entirely. **Contingency:** if the operator amends the budget
upward, first attempts are preserved as `04-UAT-SWEEP-<serial>-run1-<OUTCOME>.json`
before any re-run.

**Ambient block: keep 60 s.** At the fixed 2 q/s cadence a 60 s block yields at most
~120 queries; the measured healthy sessions yielded 113 and 114 (disk-asserted in
runner section 6). V2's non-retunable n ≥ 100 therefore leaves no material shortening
room.

**Wall time:** 60 s ambient + 3 round-pairs × (10 s rest + 30 s gated + 10 s rest +
30 s blind) = 300 s = 5 min streaming + setup (resolution, chain query, per-round
animator setup, restore) ≈ 5.25–5.5 min per device. 8 devices SEQUENTIAL — never
parallel: measurement isolation and network load — ≈ 44 min streaming plus
resolution/restore overhead → **~45–55 min total**.

## 5. ANIM-04 piggyback definition

The sweep captures on the three ceiling-class devices (Makerspace Ceiling, Playroom
Ceiling, My Office Ceiling Capsule) everything 04-07 Task 1 required:

- **Reported chain dimensions** (width, height, tile count) per session.
- **Packets/frame asserted against the chain-dims-derived expectation** — every sent
  gated frame's `stats.packets_sent` compared to
  `expected_packets_per_frame(tile_count, width, height)`, the read-only mirror of
  MatrixPacketGenerator's row-aligned chunking rule (an independent derivation from
  the REPORTED dims — never the generator's own `packets_per_tile` read back, which
  would be circular): pixels = width × height; if pixels ≤ 64 the expectation is
  tile_count (one Set64 per tile, no CopyFrameBuffer); else
  rows_per_packet = 64 // width, set64_per_tile = ceil(height / rows_per_packet),
  expectation = tile_count × (set64_per_tile + 1) for the final CopyFrameBuffer per
  tile. Worked examples (runner section 5, all asserted):
  - 13×26 Capsule → 64//13 = 4 rows/packet, ceil(26/4) = 7 Set64, +1 CopyFB = **8**
  - 16×8 ceiling → 64//16 = 4 rows/packet, ceil(8/4) = 2 Set64, +1 CopyFB = **3**
  - five 8×8 tiles → 64 px ≤ 64 → one Set64 per tile, no CopyFB = **5**
- **CopyFrameBuffer ack RTT median/p95 and expiry counts per gated round** (≥ 1
  sample per gated round — the unchanged A1 evidence check).
- **A1/A2 dispositions:** the CopyFrameBuffer probe attachment per D4-04 confirmed
  (acks arriving on the frame-commit packet) or contradicted-with-evidence (in which
  case the documented one-line `probe_template_index` fallback seam to index 0 is
  the routing, decided by the operator — never silently flipped).

**What remains human-only:** rendering geometry — striping, offset bands, garbled or
stale regions on the physical panel. Numbers count packets; only eyes see geometry.
That is the consolidated visual checkpoint (section 6).

## 6. Visual checkpoint consolidation

**ONE visual ask total**, on My Office Ceiling Capsule (the operator is at their
desk; the Capsule is in their office), with a DUAL verdict:

- **Smoothness (ANIM-03's human-only criterion):** a continuously moving colour
  cycle at a steady ~20 FPS cadence — occasional single skipped frames are normal
  (latest-frame-wins), but no multi-second freezes, stutter clusters, or persistent
  crawling.
- **Geometry (ANIM-04's striping check):** the colour cycle sweeps coherently across
  the whole 13×26 panel — the row-aligned chunking fix on the exact 13-wide hardware
  the old code would have corrupted.

**Disposition:** 04-06 Task 2 is superseded — visual ownership moves to 04-12
Task 5; 04-07 is superseded in full (Task 1 by the Capsule's sweep session, Task 2 by
04-12 Task 5); the sole-visual-owner rule moves to 04-12 Task 5, which becomes the
only ANIM-03/ANIM-04 visual checkpoint and executes only on aggregate sweep PASS.

## 7. Retrodiction, honest

No sweep-roster device has any prior paired data, so retrodiction is limited to
reclassification:

- **The historical Tiles I paired sessions reclassify as reference data** under the
  new criterion (runner section 1, disk-asserted): run 1 gated 4/136 = 2.94% vs
  blind 9/125 = 7.20%, ratio 2.45x, Fisher one-sided p = 0.0973; run 2 gated
  7/127 = 5.51% vs blind 11/113 = 9.73%, ratio 1.77x, p = 0.1601 — both sessions
  VALID. They show consistent 1.77–2.45x gated wins on a known-flaky radio:
  supporting evidence for the operator's ruling, no longer a gate.
- **No comparator can be manufactured for devices never measured.** The 7 gate
  devices have no historical paired sessions; the sweep itself is their first
  evidence. The power analysis (section 3) rests on the declared historical rates
  from Tiles I — the only measured rates that exist — which healthy radios plausibly
  beat via the clean escape.

## 8. Final wording (PROPOSED — NOT applied; operator decision required)

Nothing below has been applied. ROADMAP.md, REQUIREMENTS.md, `uat_ack_stream.py`,
04-06-PLAN.md and 04-07-PLAN.md are untouched by this plan's Task 1; this section
exists solely so the operator decides from concrete wording (04-09/04-11 precedent).
Task 3 applies the approved (or operator-amended) wording verbatim.

### (i) ROADMAP Phase 4 success criterion 3 — proposed replacement

> 3. Hardware UAT (cross-device paired sweep): the paired same-session battery — ambient control (prober only), then alternating ack-gated and instrument-level blind-fire rounds under 20 FPS streaming — runs once per device over the 7-device healthy-radio matrix roster (Playroom Luna, Dining Room Table Candle, Makerspace Candle, Makerspace Tube, Makerspace Ceiling, Playroom Ceiling, My Office Ceiling Capsule), each session judged by the unchanged 04-CRITERION-DESIGN.md paired-relative rule (validity: ambient ≤ 2.5%, ambient n ≥ 100, every gated round delivered ≥ 0.50, else INCONCLUSIVE; PASS: gated pooled ≤ 9.0% AND (gated pooled ≤ 2.5% OR Fisher one-sided p < 0.05 AND blind/gated ≥ 2.0)); the sweep certifies iff at least 5 of the 7 gate devices produce valid sessions (N_valid ≥ 5, quorum) and at most one valid session FAILs (per-device PASSes ≥ N_valid − 1); INCONCLUSIVE and ENV-ERROR rows are excluded from N_valid but always reported; below quorum the sweep is INCONCLUSIVE, never a pass or a fail (aggregation derived per 04-SWEEP-DESIGN.md: power 0.8523 at the historical per-device rate, all-must-pass 0.4813 rejected); System Test Tiles II (gen3 Tiles, known-flaky radio — operator ruling 2026-07-17: its measured consistent 2–2.5x gated improvement IS a win and Tiles loss numbers never gate certification) runs as reference data only, never in the aggregation

### (ii) ROADMAP Phase 4 success criterion 4 — proposed replacement

> 4. Hardware UAT (large-matrix framebuffer path): the sweep's three ceiling-class devices (Makerspace Ceiling, Playroom Ceiling, My Office Ceiling Capsule 13×26) stream the framebuffer path (multi-packet frames + buffer swap) under the same flow control within their paired sweep sessions — every sent gated frame matches the packets/frame expectation derived from the reported chain dimensions by the row-aligned chunking rule (pixels ≤ 64 → one Set64 per tile; else tile_count × (ceil(height / (64 // width)) + 1) including the final CopyFrameBuffer per tile), every gated round records ≥ 1 CopyFrameBuffer ack RTT sample (the D4-04 ack-probe attachment decision confirmed or contradicted with evidence), and rendering geometry (no striping/garbled regions) is confirmed visually on the Capsule at the consolidated 04-12 visual checkpoint

### (iii) REQUIREMENTS ANIM-03 — proposed replacement (checkbox stays unchecked)

> - [ ] **ANIM-03**: Hardware validation across the 7-device healthy-radio matrix sweep roster:
>   under 20 FPS streaming, each device's paired session is judged by the unchanged
>   paired-relative rule (Fisher one-sided p < 0.05 and >= 2x lower, or gated pooled <= 2.5%,
>   within a 9.0% pooled ceiling; ambient-degraded sessions INCONCLUSIVE), and the sweep
>   certifies iff N_valid >= 5 and at most one valid session FAILs; System Test Tiles II
>   (known-flaky gen3 radio, operator ruling 2026-07-17) is reference data only and never gates

### (iv) REQUIREMENTS ANIM-04 — proposed replacement (checkbox stays unchecked)

> - [ ] **ANIM-04**: Flow control covers the large-matrix framebuffer path (multi-packet
>   frames + buffer swap), hardware-validated on the sweep's three ceiling-class devices:
>   every sent gated frame matches the chain-dims-derived row-aligned packets/frame
>   expectation, CopyFrameBuffer ack RTT evidence is recorded per gated round (the D4-04
>   ack-probe attachment decision), and rendering geometry is confirmed visually on the
>   13×26 Capsule

### (v) Harness sweep contract (`uat_ack_stream.py`) — proposed

**Preserved:** the single-device CLI mode (`--ip/--profile/--json-out`), the
per-device paired-gate constants (byte-identical to their 04-11 values), and
`_evaluate` semantics — prior evidence stays reproducible. The paired gate itself is
not re-tuned.

**ROSTER constant:** module-level list of the 8 roster entries (label, ip, serial,
role) with gate vs reference encoded; Tiles II role `"reference"`.

**New CLI modes:**

- `--sweep-device SERIAL` runs ONE paired session for that roster entry and writes
  `04-UAT-SWEEP-<serial>.json` (existing per-session exit contract 0/1/2/3).
- `--sweep-verdict` deterministically aggregates the 8 on-disk per-device JSONs into
  `04-UAT-SWEEP.json` per the approved K/quorum rule (Tiles II reported, never
  counted) and exits **0 PASS / 1 FAIL / 2 ENV-ERROR (all 7 gate rows ENV-ERROR —
  nothing was measured) / 3 INCONCLUSIVE (below quorum, N_valid < 5)** at sweep
  level.

**Serial-authoritative resolution per session:** the serial is the device's
identity; the roster IP is only a fast path — attempt `MatrixLight.from_ip` on the
roster IP and confirm the reported serial matches the roster serial; on unreachable
or mismatch, fall back to broadcast discovery by serial (`find_by_serial`); both
failing → that device's ENV-ERROR JSON is written and the sweep continues.

**Profile auto-selection:** CeilingLight instance → ceiling profile; any other
MatrixLight → tiles profile (on the from_ip fallback path, detect class via
get_version + the products registry if isinstance is not available).

**Ceiling packet-shape generalisation:**
`expected_packets_per_frame(tile_count, width, height)` mirroring the row-aligned
rule in packets.py; the ceiling profile's per-frame assertion compares
`stats.packets_sent` against this value computed from the REPORTED chain dimensions.
The Capsule still expects 8; a 16×8 ceiling expects 3.

**As-found state capture/restore per session:** before streaming, capture
`get_power()` and `get_color()`; ceiling profile keeps its unchanged power-on + 1 s
settle + `get_power()` confirmation; tiles-profile sessions do NOT power devices on
(query-loss measurement needs no visibility — least household disturbance). After
the session (in a `finally` block), restore the captured colour then the captured
power state. "As found" covers device-level power and the single device-level HSBK
colour from `get_color()`; per-pixel matrix contents and running firmware effects
are NOT captured — the public-API feasibility boundary; a device restored to
powered-off is indistinguishable from as-found. Restoration status
(attempted/succeeded/failed with reason) is recorded in the per-device JSON;
restoration failure never aborts the sweep and never alters the measurement outcome.

**Per-device JSON schema** (`04-UAT-SWEEP-<serial>.json`): the existing paired-session
schema plus `serial`, `label`, `role`, `resolution` (method: `roster-ip` |
`discovery-by-serial`; resolved ip), `profile` (auto-selected),
`expected_packets_per_frame`, and `restoration` {attempted, succeeded, reason}.

**Sweep-level JSON schema** (`04-UAT-SWEEP.json`): a `devices` list of 8 entries each
carrying serial/label/role/outcome, an `aggregation` block (K, N_valid, quorum,
pass/fail/inconclusive/env-error counts), the rules/thresholds block, and a top-level
`outcome`.

### (vi) Supersession notices — proposed exact text

**Appended to 04-06-PLAN.md (after its 04-11 notice; every other line
byte-identical):**

> **SUPERSESSION NOTICE (2026-07-17, applied by 04-12):** After the paired-relative
> gate FAILed twice on System Test Tiles I with both sessions VALID (04-11), the
> operator ruled the gen3 Tiles radios notoriously flaky — "even this amount of
> improvement is a win" — and retargeted ANIM-03 certification to the 04-12
> cross-device paired sweep over 7 healthy-radio matrix devices
> (04-SWEEP-DESIGN.md, approved at the 04-12 checkpoint). Consequences here:
>
> - **Task 2 (operator visual verdict) is SUPERSEDED — visual ownership moves to
>   04-12 Task 5**, the single consolidated smoothness + geometry checkpoint on My
>   Office Ceiling Capsule. The sole-visual-owner rule moves with it: 04-12 Task 5
>   is now the only ANIM-03 visual checkpoint.
> - This plan is now fully superseded (Task 1 by 04-11's paired headless run, Task 2
>   by 04-12 Task 5). Do not execute any task from this plan.

**Appended to 04-07-PLAN.md (after its 04-11 notice; every other line
byte-identical):**

> **SUPERSESSION NOTICE (2026-07-17, applied by 04-12):** The operator retargeted
> ANIM-03/ANIM-04 certification to the 04-12 cross-device paired sweep
> (04-SWEEP-DESIGN.md, approved at the 04-12 checkpoint). This plan is superseded IN
> FULL:
>
> - **Task 1 (headless ceiling measurement) is covered by the Capsule's sweep
>   session** in 04-12 Task 4: 13×26 framebuffer path under the paired gate,
>   chain-dims-derived packets/frame expectation, CopyFrameBuffer ack RTT evidence,
>   A1/A2 dispositions.
> - **Task 2 (operator visual checkpoint) is covered by 04-12 Task 5**, the single
>   consolidated smoothness + geometry verdict on the Capsule.
> - Do not execute any task from this plan.

**What changes for downstream plans:** ANIM-03 and ANIM-04 completion is owned by
04-12 Task 5 (the consolidated visual checkpoint), which executes only on aggregate
sweep PASS; on aggregate FAIL or INCONCLUSIVE both requirements stay unchecked and
fresh operator routing is required.
