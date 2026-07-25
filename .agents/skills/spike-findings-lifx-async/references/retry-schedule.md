# Retry schedule: reshape the per-attempt windows

## Requirements

- Keep the asyncio core and public async API unchanged (callers still pass
  `timeout`/`max_retries`).
- Honour the caller's timeout as WALL time, not response-time-minus-sleeps.

## The Problem (measured)

`DeviceConnection`'s retry loop (`connection.py:470-548`) distributes the 16 s budget as
`(timeout/511)·2^attempt` → windows ≈ 31, 63, 125, 250, 500 ms … 8 s, with full-jitter
sleeps (`uniform(0, 0.1·2^n)`) between attempts that are EXCLUDED from the budget.
Raced against Glowup's 3×2 s fresh deadlines and Photons' escalating retransmits
(540 trials, 3 device generations, injected per-direction loss):

| Loss | Regime | Fail | Pkts/trial | Median |
|------|--------|------|-----------|--------|
| 0% | lifx-async | 0/60 | **1.37** | 15.2 ms |
| 0% | photons | 0/60 | 1.08 | 16.7 ms |
| 50% | lifx-async | 3/60 | 3.70 | 213.8 ms |
| 50% | **photons** | **1/60** | 3.10 | 504.6 ms |
| 50% | glowup | 24/60 | 2.27 | 2,003 ms |

Two defects confirmed:

1. **31 ms first window fires pure duplicates.** At zero loss, attempt #1's response won
   all 60 trials, yet 1.37 packets/trial went out. On a gen4 downlight (RTT often
   >31 ms) the already-arrived response sat unread through the inter-attempt sleep,
   doubling median latency (62 ms vs 26–32 ms for other regimes).
2. **Wall time ≈ 2× budget.** Sleeps excluded from the 16 s budget produced successful
   requests taking 23.4–29.0 s of wall time at 50% loss.

## How to Build It

Adopt the Photons shape (best-balanced: 1 failure in 180 trials, bounded worst case):

- **Floor the first window** at ~200 ms (Photons' first gap; also both Glowup and
  Photons independently assume "an acked bulb answers within 200 ms").
- **Escalating gaps, not doubling windows**: e.g. gaps 0.2, 0.3, 0.4, 0.5, 0.7, 0.9,
  1.0, then grow toward a cap. Fresh sequence per retransmit (already the case),
  first reply wins via the shared response queue (already the case — keep it).
- **Never sleep blind.** Replace sleep-then-retry with retransmit-while-listening: keep
  consuming the shared queue continuously; a timer decides when to retransmit. (The
  current design's jitter sleep is where arrived responses go unread.)
- **Count everything against the caller's timeout** so wall time honours it.

Working reference implementation of all three regimes: `sources/002-.../race.py`
(`regime_photons()` is the send-while-listening loop shape).

## What to Avoid

- **Glowup's fresh-deadline patience** (3×2 s, single in-flight): collapses under loss —
  40% failure at 50% loss, 2 s median stalls at 25% loss. Its low packet cost is not
  worth it.
- **Removing the retransmits entirely** — at 50% loss the multi-transmit regimes still
  succeeded 95–98% of the time; a single-shot design would fail ~44%.
- Full-jitter sleeps between attempts. Jitter matters for thundering-herd on shared
  infrastructure; per-device UDP to a bulb is not that. It costs latency for nothing.

## Constraints

- Sequence is uint8; the shared-queue correlation (source, sequence, serial) must keep
  accepting responses from ALL sequences issued for the logical request.
- Duplicate late replies are normal (Photons documents this); they must be silently
  discarded, never treated as protocol errors.

## Origin

Synthesized from spike: 002.
Source files: sources/002-retry-storm-vs-fresh-deadline/
