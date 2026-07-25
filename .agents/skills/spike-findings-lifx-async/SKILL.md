---
name: spike-findings-lifx-async
description: Implementation blueprint from spike experiments. Requirements, proven patterns, and verified knowledge for building lifx-async reliability improvements. Auto-loaded during implementation work.
---

<context>
## Project: lifx-async

Original prompt: "switch from asyncio to threading for concurrency" — reframed after
investigation into: why do LIFX bulbs feel more reliable with Glowup (threaded) than with
asyncio clients (lifx-async, aiolifx)? Bulbs cannot observe a client's concurrency model —
only packets, timing, and how promptly responses are drained. Five spikes against Avi's
real 73-device fleet isolated the true levers. Threading itself was disproven (Spike 004);
the real causes were discovery fragility (005), inbound-queue starvation during blind
streaming (003), and retry-schedule defects (002). Reference implementations studied:
Glowup (threaded, `/Volumes/External/Developer/pkivolowitz/glowup/`) and Photons (asyncio,
insider-authored, `/Volumes/External/Developer/Djelibeybi/photons`) — findings port as
techniques, never as dependencies.

Spike sessions wrapped: 2026-07-16
</context>

<requirements>
## Requirements

- Must run validation against real LIFX hardware — the emulator cannot model modem sleep,
  WiFi loss, or per-AP broadcast delivery.
- Test bulbs must be quiesced from other pollers (Home Assistant, LIFX app) during
  measurements — background polling is an accidental keepalive/confound.
- Any adopted fix must keep the asyncio core and public async API unchanged.
- Repeated rounds are mandatory for discovery/loss claims — single rounds mislead
  (spike 005's shakedown found 71/73 by luck; the 6-round median was 48/73).
</requirements>

<findings_index>
## Feature Areas

| Area | Reference | Key Finding |
|------|-----------|-------------|
| Discovery | references/discovery.md | Single broadcast finds median 48/73 devices on a multi-AP network; Photons' 6-broadcast escalating schedule finds 73/73 at 29% of Glowup's packet cost. Highest-impact fix. |
| Retry schedule | references/retry-schedule.md | 31 ms first window fires pure duplicates and stalls arrived responses behind jitter sleeps; wall time hits 29 s vs 16 s budget. Adopt Photons-shaped gaps, listen during backoff. |
| Animation flow control | references/animation-flow-control.md | Blind streaming drops 14.6% of concurrent queries; ack-gated delivery (probe first packet, gate on 2 outstanding) achieves 0% query loss AND best visual smoothness. |
| Concurrency & keepalive | references/concurrency-and-keepalive.md | Landmines: threading confers no wire advantage (collapses under CPU load); keepalive daemons unnecessary on healthy networks (gen4-only sub-250 ms wake tail). |

## Source Files

Original spike harnesses (probe/race/stream/wire/sweep scripts + READMEs with full data)
are preserved in `sources/`. Raw results JSONL remains in `.planning/spikes/*/`.
</findings_index>

<metadata>
## Processed Spikes

- 001-modem-sleep-keepalive
- 002-retry-storm-vs-fresh-deadline
- 003-ack-paced-frames
- 004-asyncio-thread-wire-equivalence
- 005-discovery-regimes
</metadata>
