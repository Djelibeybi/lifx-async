# Phase 3: Retry Schedule Reshape — Context

**Source:** Spike 002 (`.planning/spikes/002-retry-storm-vs-fresh-deadline/`) and the
`spike-findings-lifx-async` skill (`references/retry-schedule.md`). Distilled from the
spike-series review + v1.1 milestone scoping (2026-07-16); no separate discuss-phase
interview.

## Decisions (settled)

- **D3-01**: Replace the exponential window distribution (`timeout/(2^(n+1)-1) · 2^attempt`
  → 31 ms first window) with a Photons-shaped schedule: floored first window (~200 ms),
  escalating retransmit gaps thereafter. Reference expansion in the spike:
  gaps ≈ 0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1.0, then growing toward a cap.
- **D3-02**: Listen during backoff — never sleep blind. Replace the jittered
  inter-attempt `asyncio.sleep()` with retransmit-while-listening: the shared response
  queue is consumed continuously; a timer decides when to retransmit. A response arriving
  at any moment is accepted immediately.
- **D3-03**: The caller's `timeout` is WALL time. All waiting counts against the budget;
  a 16 s budget can never take 29 s (spike observed 23.4–29.0 s overruns from
  budget-excluded sleeps).
- **D3-04**: Preserve the correlation contract: one source per logical request, fresh
  sequence per retransmit, shared queue accepts responses from ALL issued sequences,
  first reply wins, late/duplicate replies silently discarded (DEBUG at most).
- **D3-05**: Public API unchanged — `request()`/`request_stream()` signatures, `timeout`
  and `max_retries` parameters keep working. `max_retries` reinterpreted naturally as the
  retransmit cap within the wall budget (document precisely). Constants in `const.py`.
- **D3-06**: Scope is `connection.py` request paths only. No discovery changes (Phase 2,
  shipped), no animation changes (Phase 4), no ack semantics changes.

## Measured baselines (success targets)

From spike 002 (540 trials, 3 device generations, seeded loss injection):

- Zero-loss: lifx-async sent 1.37 packets/trial where 1.0 suffices — tx#1 won all 60
  trials; every extra packet was a pure duplicate. Target: 1.0 packets/trial at zero loss
  on healthy RTTs (≤200 ms).
- Gen4 downlight median latency 62 ms vs 26–32 ms for the other regimes (response sat
  unread through the jitter sleep). Target: median ≈ raw RTT.
- 50% loss: 3/60 failures (budget exhaustion) — the reshaped schedule must not regress
  resilience (Photons shape measured 1/180 across all rates).
- Wall-time: observed successes at 23.4–29.0 s against the 16 s budget. Target: elapsed
  ≤ timeout, always.

## Constraints

- Multi-response streams (`_request_stream_impl` semantics: idle timeout 2.0 s after
  first response, early exit) must keep working; the reshape applies to how attempts and
  waiting are scheduled, not to stream semantics.
- The retry-budget arithmetic duplication between `_request_stream_impl` and
  `_request_ack_stream_impl` is a known candidate cleanup (flagged post-Phase-1); if the
  reshape touches both paths, unify rather than duplicating the new schedule twice —
  but do not expand scope beyond the request paths.
- Emulator-backed tests can control timing via patched constants; loss behaviour can be
  validated with the spike's client-side injection pattern if needed at the transport
  seam. CI: 100% branch patch coverage; pyright strict; ruff clean.
- Optional headless hardware validation: re-run the spike's race harness
  (`.planning/spikes/002-retry-storm-vs-fresh-deadline/race.py`) regime comparison, or a
  targeted zero-loss packets-per-trial measurement against a quiesced test downlight
  (192.168.18.95 gen4 is the sensitive one). Repeated trials mandatory.

## Requirements in scope

RETRY-01 (floored first window/escalating gaps), RETRY-02 (listen during backoff),
RETRY-03 (wall-time budget), RETRY-04 (correlation contract preserved).
