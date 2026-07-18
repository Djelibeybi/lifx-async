---
spike: 005
name: discovery-regimes
type: comparison
validates: "Given a ~20-device fleet, when lifx-async, Glowup and Photons discovery regimes each run repeatedly, then coverage, time-to-full-coverage, and packet cost differ measurably"
verdict: VALIDATED
related: [002]
tags: [discovery, broadcast, coverage, real-hardware]
---

# Spike 005: discovery-regimes

## What This Validates

Given a real fleet (73 devices observed — far larger than the ~20 assumed at definition),
when the three clients' discovery broadcast schedules run repeatedly under an identical
collector, then coverage per round, time-to-90%-coverage, and packet cost differ
measurably.

## Research

Broadcast schedules replicated from source (the only variable — same socket, same
validation, same fixed listen window; native early-exit rules applied post-hoc):

| Regime | Schedule (10 s window) | Broadcasts |
|--------|------------------------|-----------|
| lifx-async (`discovery.py:233`) | single GetService at t=0, then listen (native stop: 4 s idle gap) | 1 |
| Glowup (`transport.py:2521-2547`) | wake burst 3× 0.1 s apart, then every 0.5 s | 22 |
| Photons (`session/network.py:93-98`) | escalating gaps 0.6, 1.2, 1.8, 2, 2… | 6–7 |

## How to Run

```bash
uv run python .planning/spikes/005-discovery-regimes/sweep.py run   # 6 rounds, ~7 min
uv run python .planning/spikes/005-discovery-regimes/sweep.py run --quick
```

Do not run concurrently with the other spikes.

## What to Expect

- If single-broadcast is fragile, lifx-async misses devices in some rounds (each miss is
  an "unavailable" entity in a Home Assistant-style consumer).
- Re-broadcast regimes should reach full coverage at the cost of response storms
  (every device answers every broadcast).

## Observability

- `results-<runid>.jsonl` — per round: regime, devices found, per-device first-seen ms,
  broadcasts sent, total responses received.
- `summary-<runid>.json` — per regime: coverage min/med/max, native-rule coverage,
  t90, response cost, per-device miss counts.

## Investigation Trail

- Shakedown (1 round) immediately exposed the trade: lifx-async 71/73 (2 missed),
  Glowup 73/73 at 2,133 response packets/round, Photons 73/73 at 836.

## Results

**Verdict: VALIDATED — and the most severe lifx-async finding of the series. The
single-broadcast regime found a median of 48/73 devices per round (worst round: 27).
Both re-broadcasting regimes found 73/73 in effectively every round.**

Run 20260716-211339: 6 rounds × 3 regimes × 10 s windows, 73-device production fleet.

| Regime | Broadcasts/round | Found (min/med/max of 73) | t90 | Responses/round |
|--------|------------------|---------------------------|-----|-----------------|
| lifx-async | 1 | **27 / 48 / 73** | 189 ms | 96 |
| glowup | 22 | 73 / 73 / 73 | 386 ms | 2,146 |
| photons | 6–7 | 72 / 73 / 73 | 710 ms | 615 |

Key findings:

1. **Single-broadcast discovery is a coin flip on this network.** Per-round results were
   bimodal: ~65–73 found (broadcast propagated everywhere) or ~27–31 (large clusters
   missed). 50 distinct devices were missed in at least one round; 147 total misses in
   6 rounds. In a Home Assistant-style consumer every miss is a device going
   "unavailable" — this alone plausibly explains "lifx-async is no more stable than
   aiolifx" (aiolifx-era discovery has the same shape).
2. **Not a subnet split.** Known test devices in both 192.168.18.x and .19.x were partially
   present in bad rounds. The likelier mechanism is per-AP broadcast delivery: each AP
   repeats a broadcast to its associated wireless clients at DTIM, best-effort; when one
   AP drops it, all bulbs on that AP miss the round. Unverifiable without AP association
   data — recorded as interpretation, not fact.
3. **Devices answer each GetService broadcast twice** (two StateService packets —
   responses were exactly 2× devices found in every lifx-async round).
4. **Photons' 6-broadcast escalating schedule is the sweet spot**: full coverage
   (one single-device miss in 6 rounds) at 29% of Glowup's response-storm cost. Glowup's
   0.5 s hammer provokes ~2,100 responses per discovery — reliable, but the fleet spends
   ~210 packets/s answering it.

Library implication (for wrap-up): re-broadcast during the discovery window on an
escalating schedule (even 3 broadcasts at 0/0.6/1.8 s would likely transform coverage);
dedup by serial is already in place from the Phase 1 rework, so responses to later
broadcasts are handled naturally.
