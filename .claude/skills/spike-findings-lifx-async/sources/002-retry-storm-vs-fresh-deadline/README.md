---
spike: 002
name: retry-storm-vs-fresh-deadline
type: comparison
validates: "Given a slow/lossy path to a bulb, when lifx-async's 8-retry exponential backoff competes with Glowup-style 3x fresh-deadline retries (and Photons' escalating-gap retransmits), then responsiveness under stress differs measurably"
verdict: VALIDATED
related: [001]
tags: [retries, backoff, congestion, real-hardware]
---

# Spike 002: retry-storm-vs-fresh-deadline

## What This Validates

Given a slow/lossy path to a bulb, when three real clients' retry regimes are raced on the
same hardware under injected loss, then time-to-success, failure rate, and wire pressure
(packets per logical request) differ measurably between regimes.

## Research

Exact regimes replicated from source:

| Regime | Schedule | Budget | Sequence | Matching |
|--------|----------|--------|----------|----------|
| lifx-async (`connection.py:485-515`) | 9 attempts, window `(16/511)·2^n` ≈ 31 ms → 8 s, jittered sleeps between (excluded from budget) | 16 s | fresh per attempt | source + any issued seq (shared queue; late replies accepted) |
| Glowup (`transport.py:1098-1147`) | 3 attempts × fresh 2 s deadline, no sleep | 6 s | reused | **packet type only** |
| Photons (`retry_options.py`, `targets/__init__.py:21-27`) | continuous retransmits at gaps 0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1, 2, 3, 4, then 5 s | 10 s | fresh per retransmit | source + any issued seq, first reply wins |

Correction discovered during research: lifx-async's regime is **not** a naive "retry
storm" — its early windows (31/63/125 ms) retransmit *faster* than Photons' first gap
(200 ms). The design families are similar; the open question is which schedule shape wins
under real loss, and at what wire-pressure cost. Glowup is the outlier: patient single
in-flight packets and type-only response matching.

Loss injection is client-side Bernoulli per direction (send dropped after being counted as
offered = wire pressure; accepted responses dropped before delivery), seeded per
(bulb, loss-rate) for reproducibility. Real bulbs provide authentic RTT and processing
behaviour; the injector provides controlled loss on top.

## How to Run

```bash
# Shakedown (~2 min)
uv run python .planning/spikes/002-retry-storm-vs-fresh-deadline/race.py run \
    --hosts <gen2-ip>,<gen3-ip>,<gen4-ip> --quick

# Full run (~10-20 min depending on loss draw)
uv run python .planning/spikes/002-retry-storm-vs-fresh-deadline/race.py run \
    --hosts <gen2-ip>,<gen3-ip>,<gen4-ip>
```

Do not run concurrently with Spike 001 — its idle measurements must not see extra traffic.

## What to Expect

- At `loss=0`: all regimes ≈ identical (single packet, ~5–30 ms).
- At `loss=0.25/0.5`: divergence. Expected shape: lifx-async and Photons recover fast
  (sub-second medians) at the cost of more packets per request; Glowup pays 2 s per lost
  packet but stays at ~1 packet in flight. Failure rates expose budget differences
  (Glowup 6 s vs Photons 10 s vs lifx-async 16 s).

## Observability

- `results-<runid>.jsonl` — one event per trial: regime, loss rate, success, elapsed ms,
  packets offered, which transmission satisfied the request.
- `summary-<runid>.json` + stdout table — per bulb/loss/regime: n, fail %, avg packets per
  trial, success-latency median/p95/max.

## Investigation Trail

- Replicated lifx-async's actual algorithm (read from `connection.py:470-548`) rather than
  the assumed one — the assumption ("8 retries exponential backoff = slow storm") was
  wrong in an important way; see Research correction above.

## Results

**Verdict: VALIDATED — the regimes differ dramatically under loss, and two concrete
lifx-async defects were confirmed. Surprise: Glowup's query regime is objectively the
worst, deepening the mystery of its anecdotal reliability.**

Run 20260716-204532: 3 bulbs (gen2 DL5, gen3 Tiles I, gen4 DL2) × 3 loss rates × 20
trials × 3 regimes = 540 trials.

Pooled results:

| Loss | Regime | Fail | Pkts/trial | Median success |
|------|--------|------|-----------|----------------|
| 0% | lifx-async | 0/60 | 1.37 | 15.2 ms |
| 0% | glowup | 0/60 | 1.00 | 25.2 ms |
| 0% | photons | 0/60 | 1.08 | 16.7 ms |
| 25% | lifx-async | 0/60 | 1.97 | 29.4 ms |
| 25% | glowup | 2/60 | 1.63 | 38.2 ms |
| 25% | photons | 0/60 | 1.65 | 55.9 ms |
| 50% | lifx-async | 3/60 | 3.70 | 213.8 ms |
| 50% | glowup | **24/60** | 2.27 | **2003 ms** |
| 50% | photons | 1/60 | 3.10 | 504.6 ms |

Key findings:

1. **lifx-async defect #1 — the 31 ms first-attempt window fires pure duplicates.** At
   zero loss, transmission #1 won **all 60** lifx-async trials, yet 1.37 packets/trial
   were sent — every extra packet was waste triggered by the window expiring before a
   normal response arrived. Worse, on the gen4 downlight (RTT often >31 ms) the
   already-arrived response sat unread through the jittered inter-attempt sleep, doubling
   median latency (62 ms vs 26–32 ms for the other regimes).
2. **lifx-async defect #2 — wall time can nearly double the nominal budget.** The
   inter-attempt jitter sleeps (up to `0.1·2^n` s) are excluded from the 16 s response
   budget; four successful trials at 50% loss took **23.4–29.0 s** of wall time.
3. **Photons' schedule is the best-balanced**: 1 failure in 180 trials across all loss
   rates, bounded 10 s worst case, moderate packet cost. Its shape — flat ~200–500 ms
   early gaps, no sleep-blindness (it listens continuously), escalating later gaps — is
   the port-worthy design.
4. **Glowup's query regime collapses under loss** (40% failure at 50% loss, 2 s median
   stalls at 25%) — its anecdotal reliability cannot come from this path. Combined with
   Spike 001 (keepalive marginal here), the remaining candidates are the ack-paced
   set/frame path (Spike 003) and differences in what the clients *do* (Glowup confirms
   sets via ack; a set that "sticks" reads as reliability even if queries stall).

Library implications (for the wrap-up, not this spike): floor the first-attempt window
(or adopt Photons-shaped early gaps), keep listening during backoff instead of sleeping
blind, and include sleeps in the overall budget so wall time honours the caller's
timeout.
