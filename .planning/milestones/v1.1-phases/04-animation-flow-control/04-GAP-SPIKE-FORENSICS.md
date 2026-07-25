# 04-08 Gap Forensics: Spike 003 Raw-Data Audit

**Question under audit (H2):** was the ANIM-03 fixed 0% concurrent-query-loss threshold
calibrated from an underpowered sample in spike 003?

Every number below is computed from the named raw files on disk — never from memory or
from the gap briefing. Formulas are shown inline with their inputs so a reader can
recompute each figure by hand.

Raw sources:

- `.planning/spikes/003-ack-paced-frames/results-20260716-210408.jsonl` — the only
  complete spike run (baseline + all three arms)
- `.planning/spikes/003-ack-paced-frames/results-20260716-210318.jsonl` — the aborted
  first run (`run_start` + `baseline` events only)
- `.planning/spikes/003-ack-paced-frames/README.md` — the recorded VALIDATED verdict the
  0% threshold was derived from
- `.planning/phases/04-animation-flow-control/04-UAT-TILES-run1-FAIL.json` — 04-06 UAT
  run 1 (timestamp 2026-07-17T02:36:03)
- `.planning/phases/04-animation-flow-control/04-UAT-TILES.json` — 04-06 UAT run 2
  (timestamp 2026-07-17T02:38:00)

All measurements are against the same device: System Test Tiles I, 192.168.19.243
(684 pixels, 4 Set64 packets/frame, 20 FPS, 30 s per arm/round).

## Spike 003 sample sizes

From `results-20260716-210408.jsonl` (the complete run), the `arm` and `baseline`
events record:

| Arm | Rounds | `query_n` | `query_loss_pct` | Losses (derived) |
|-----|--------|-----------|------------------|------------------|
| baseline (no stream) | 1 | 20 | — (`losses` field = 0) | 0 |
| blind | 1 | 41 | 14.6 | 41 × 0.146 ≈ 6 |
| glowup | 1 | 49 | 6.1 | 49 × 0.061 ≈ 3 |
| **photons** | **1** | **50** | **0.0** | **0** |

The load-bearing H2 facts:

- **The photons arm — the arm the shipped `AckGate` design and the ANIM-03 0% threshold
  were calibrated from — ran exactly ONE round of 50 queries with 0 losses.** There is
  no second photons round anywhere in the spike's raw data.
- **The no-stream baseline was n=20 with 0 losses.** The aborted first run
  (`results-20260716-210318.jsonl`) contains only a `run_start` and one more `baseline`
  event (n=20, losses=0) — it adds another 20 baseline queries and nothing else. The
  spike therefore never measured the ambient single-shot floor with more than 40 queries
  total, and never during the same session as the photons arm.

The photons ack RTT block from the same event: median 98.3 ms, p95 148.8 ms, max
449.5 ms (530/600 frames sent, 70 gated, 2 ack timeouts).

## Pooled 04-06 UAT loss rate

Computed from the `queries_ok` and `queries_lost` fields of each round in the two UAT
JSONs (never from the gap briefing's summary):

**Run 1** (`04-UAT-TILES-run1-FAIL.json`):

| Round | `queries_ok` | `queries_lost` | Queries | Loss % |
|-------|--------------|----------------|---------|--------|
| 0 | 42 | 2 | 44 | 4.55 |
| 1 | 48 | 0 | 48 | 0.00 |
| 2 | 41 | 2 | 43 | 4.65 |
| **Total** | **131** | **4** | **135** | **100 × 4/135 = 2.96%** |

**Run 2** (`04-UAT-TILES.json`):

| Round | `queries_ok` | `queries_lost` | Queries | Loss % |
|-------|--------------|----------------|---------|--------|
| 0 | 48 | 0 | 48 | 0.00 |
| 1 | 38 | 3 | 41 | 7.32 |
| 2 | 41 | 2 | 43 | 4.65 |
| **Total** | **127** | **5** | **132** | **100 × 5/132 = 3.79%** |

**Pooled across both runs:**

- Total queries = 135 + 132 = **267**
- Total lost = 4 + 5 = **9**
- Pooled loss rate p = 9/267 = **0.03371 ≈ 3.37%**

Loss appeared in 4 of the 6 rounds; 2 rounds (run 1 round 1, run 2 round 0) were clean.

## Binomial implications

Using the pooled p = 9/267 ≈ 0.03371 from the section above:

**(a) What could the spike's 0/50 observation actually resolve?**

- Rule-of-three 95% upper bound for 0 losses in n queries: 3/n. For n = 50:
  3/50 = **6.0%**.
- Exact one-sided 97.5% upper bound for 0/50: solve (1 − p)⁵⁰ = 0.025 for p, giving
  p = 1 − 0.025^(1/50) = 1 − 0.92888 = **7.11%**.
  (The one-sided 95% equivalent, 1 − 0.05^(1/50), is 5.82%.)

The spike's photons observation of 0/50 is therefore statistically consistent with any
true loss rate up to ~6–7% — a band that comfortably contains the 3.37% the UAT measured.

**(b) How surprising is 0/50 if the UAT rate is the truth?**

P(0 losses in 50 | p = 0.03371) = (1 − 0.03371)⁵⁰ = 0.96629⁵⁰ = **0.180**.

Roughly an 18% chance — nearly one in five. A single 50-query round producing zero losses
was an entirely plausible outcome even if the device's true concurrent-loss rate under
this design is the UAT's ~3.4%.

**(c) How often should a UAT round come up clean if p ≈ 3.37%?**

The six UAT rounds had 44, 48, 43, 48, 41, 43 queries (mean ≈ 44.5; use 45):

P(clean ~45-query round | p = 0.03371) = (1 − 0.03371)⁴⁵ = **0.214**.

Expected clean rounds in 6 = 6 × 0.214 ≈ 1.3; observed = 2. The observed mix of clean
and lossy rounds is exactly what a true ~3.4% rate predicts — the UAT data is internally
consistent.

**(d) The spike baseline was also underpowered.**

For the baseline's 0/20: rule-of-three 95% upper bound = 3/20 = **15%** (exact one-sided
97.5% bound: 1 − 0.025^(1/20) = 16.8%). The "no-stream ambient floor is 0%" belief rests
on a sample that could not distinguish 0% from anything under 15%. The investigation
instrument's control arm (~240 queries over 120 s) exists to fix precisely this.

## Sample-size verdict

The arithmetic shows plainly:

1. **Spike 003's photons measurement could not distinguish a true 0% from the
   UAT-measured ~3.4%.** Its single 0/50 round carries a ≥6% (rule-of-three) upper
   bound, and had an ≈18% probability of occurring even if the UAT's pooled 3.37% is the
   device's true rate. The two datasets are not in conflict — the spike simply lacked the
   resolution to see a ~3.4% rate.
2. **The 0% threshold was therefore calibrated beyond the evidence's resolution.** A
   fixed 0.0% pass gate derived from one lucky-or-not 50-query round asserts a precision
   the data never had. The same applies to the ambient floor: n=20 bounds it at ≤15%,
   not at 0%.

**Scope of this verdict:** this settles the CALIBRATION question (H2's premise is
confirmed — the threshold outran its evidence). It does **not** settle whether the
~3.4% the UAT measured is fixable (H1-fixable: a mechanical difference between the spike
arm and the shipped path) or an irreducible floor of this device/network under 20 FPS
load. That discrimination is what the hardware arms (Tasks 2–3, `uat_loss_investigation.py`)
measure: a spike-faithful replica at n ≥ 150 (P(0 in 150 | p = 0.03371) = 0.9663¹⁵⁰ ≈
0.006, so a genuinely-0% methodology is distinguishable), an ambient control at n ≈ 240,
an FPS sweep, and a second device.

## Methodology differences: spike arm vs shipped path

The mechanical differences the hardware arms will test, with citations:

**(a) Per-packet awaited sends vs synchronous burst.**
The spike streamed through an asyncio `UdpTransport` and awaited each packet's send
inside the frame loop — `stream.py` `FrameStreamer.send_frame()` (lines 106–122,
`await self.transport.send(bytes(tmpl.data), self.addr)` at line 121) yields to the
event loop between the 4 packets of a frame, naturally spacing them and letting the
prober/ack receive paths run mid-frame. The shipped path issues a synchronous
back-to-back burst — `src/lifx/animation/animator.py` `send_frame()` (lines 414–420,
`self._socket.sendto(tmpl.data, self._addr)` in a plain `for` loop with no await) puts
all 4 packets on the wire with no inter-packet gap. If the device's inbound queue is
sensitive to intra-frame packet spacing, this is the prime H1-fixable candidate. The
replica arm reproduces the spike's awaited-send behaviour; the shipped arm measures the
burst behaviour — same device, same session.

**(b) Prober construction and timeout width.**
The spike prober was a raw UDP socket matching source/sequence/pkt_type/addr with
`QUERY_TIMEOUT = 1.0` and `QUERY_INTERVAL = 0.5` — `stream.py` lines 53–54 (constants)
and 230–282 (`query_prober`). The UAT prober is a `DeviceConnection` with
`max_retries=0` and a 2.0 s per-query timeout — `uat_ack_stream.py` lines 189–226
(`query_prober`) and lines 398–400 (`--query-timeout` default 2.0). The UAT prober's
timeout is MORE generous (2.0 s vs 1.0 s), so timeout width alone cannot explain the UAT
losing more queries than the spike — a reply arriving between 1.0 s and 2.0 s would have
counted as a loss for the spike and a success for the UAT, biasing the comparison in the
opposite direction to what was observed. Both probe at the same 2/s cadence
(`QUERY_INTERVAL = 0.5` vs `--query-rate 2.0`). The remaining prober difference —
raw-socket parse loop vs `DeviceConnection` request machinery — is exactly what the
replica arm's spike-faithful raw prober isolates.

**(c) Probe attachment point — no difference.**
Both attach the `ack_required` probe to the FIRST packet of each frame on Tiles: the
spike's photons arm passes `ack_packet=0` (`stream.py` line 215, `arm_photons`); the
shipped animator bakes the flag into `probe_template_index` at construction
(`animator.py` lines 164–170), which is index 0 for a standard-tile matrix generator
(the large-tile CopyFrameBuffer exception, D4-04, does not apply to 8×8 Tiles).

Both designs share the D4-01 gate tuning: inflight limit 2 (`PHOTONS_INFLIGHT_LIMIT = 2`,
`stream.py` line 51; `ACK_INFLIGHT_LIMIT = 2`, `src/lifx/animation/flow.py` line 53) and
~1 s probe expiry (`PHOTONS_ACK_EXPIRY = 1.0`, `stream.py` line 52;
`ACK_EXPIRY_SECONDS = 1.0`, `flow.py` line 59). The gate constants are not a variable in
this comparison.
