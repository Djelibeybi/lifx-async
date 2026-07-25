# Discovery: re-broadcast on an escalating schedule

## Requirements

- Keep the asyncio core and public async API unchanged.
- Preserve the Phase 1 discovery architecture: shared `_discover_with_packet()` generator,
  serial validation, first-wins per-serial dedup.

## The Problem (measured)

`discover_devices()` sends exactly ONE `GetService` broadcast (`discovery.py:233`) and
then listens. On a real 73-device, multi-AP network (6 rounds, 10 s windows):

| Regime | Broadcasts | Found (min/med/max) | Responses/round |
|--------|-----------|---------------------|-----------------|
| lifx-async (1 broadcast) | 1 | **27 / 48 / 73** | 96 |
| Photons schedule | 6–7 | 72 / 73 / 73 | 615 |
| Glowup (every 0.5 s) | 22 | 73 / 73 / 73 | 2,146 |

Results were bimodal (~30 or ~65–73 found) — consistent with per-AP broadcast delivery:
each AP repeats a broadcast to its wireless clients at DTIM, best-effort; one AP dropping
it hides every bulb associated to that AP. A missed device is an "unavailable" entity in
any HA-style consumer. This was the most severe finding of the spike series.

## How to Build It

Re-broadcast inside `_discover_with_packet()`'s receive loop on Photons' escalating
schedule, capped by the discovery window:

```python
# Gaps expanded from Photons timeouts=[(0.6,1.8),(1,2),(2,6),(4,10),(5,20)]
REBROADCAST_GAPS = [0.6, 1.2, 1.8, 2.0, 2.0]  # then stop; window closes anyway

# In the receive loop: track next_tx; when now >= next_tx, transport.send(message,...)
# again and advance the gap iterator. See sources/005-discovery-regimes/sweep.py
# run_round() for the working send/receive interleave pattern.
```

- The existing first-wins serial dedup (Phase 1, D-04) already handles duplicate
  responses to later broadcasts — no schema change needed.
- Devices answer each broadcast with ~2 StateService packets; expect response volume
  ≈ 2 × devices × broadcasts. 6 broadcasts on 73 devices ≈ 600–850 responses — fine.
- Keep the IdleDeadline: re-broadcasts reset the effective idle window naturally since
  responses keep arriving.

## What to Avoid

- **Glowup's 0.5 s hammer** — works (73/73 always) but provokes ~2,100 responses per
  discovery on a large fleet (~210 packets/s inbound). Wasteful; Photons' schedule gets
  the same coverage at 29% of the cost.
- **Trusting a single round** — the shakedown found 71/73 by luck; only repetition
  (6 rounds) exposed the median-48 reality. Any discovery change must be validated with
  repeated rounds.

## Constraints

- Broadcast delivery to WiFi clients is inherently per-AP best-effort; no client-side
  schedule achieves 100% single-round guarantee. Photons' 6-broadcast schedule missed 1
  device in 1 of 6 rounds — treat >99% per-round coverage as the achievable target.
- mDNS discovery (`discover_mdns()`) is a separate path; this finding applies to UDP
  broadcast discovery.

## Origin

Synthesized from spike: 005 (also informed by 002's schedule research).
Source files: sources/005-discovery-regimes/
