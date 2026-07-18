# Spike Wrap-Up Summary

**Date:** 2026-07-16
**Spikes processed:** 5
**Feature areas:** discovery, retry-schedule, animation-flow-control, concurrency-and-keepalive
**Skill output:** `./.claude/skills/spike-findings-lifx-async/`

## Processed Spikes

| # | Name | Type | Verdict | Feature Area |
|---|------|------|---------|--------------|
| 001 | modem-sleep-keepalive | standard | PARTIAL | concurrency-and-keepalive |
| 002 | retry-storm-vs-fresh-deadline | comparison | VALIDATED | retry-schedule |
| 003 | ack-paced-frames | standard | VALIDATED | animation-flow-control |
| 004 | asyncio-thread-wire-equivalence | standard | VALIDATED | concurrency-and-keepalive |
| 005 | discovery-regimes | comparison | VALIDATED | discovery |

## Key Findings

The original idea ("switch from asyncio to threading") was disproven: bulbs cannot
observe the concurrency model, asyncio paces 4× tighter than `time.sleep()`, and under
matched CPU load threading collapses (24 s behind schedule) where asyncio stays bounded
(130 ms). The real reliability levers, in impact order:

1. **Discovery re-broadcast** — a single GetService broadcast finds a median of 48/73
   devices per round on a multi-AP network; Photons' escalating 6-broadcast schedule
   finds all devices at 29% of Glowup's response-storm cost.
2. **Ack-gated animation delivery** — blind streaming makes the device drop 14.6% of
   concurrent queries; a one-ack-per-frame flow probe with a 2-outstanding gate delivers
   88% of frames with zero query loss and the best visual smoothness.
3. **Retry-schedule reshape** — floor the 31 ms first window (~200 ms), listen during
   backoff instead of sleeping blind, count sleeps against the caller's timeout.
4. **No keepalive daemon needed** — zero idle-related loss on a healthy network; gen4
   devices show only a sub-250 ms power-save wake tail (docs footnote, not a feature).

All measurements from real hardware: 7 quiesced test devices (gen2/3/4) plus the full
73-device production fleet for discovery. Raw data in `.planning/spikes/*/results-*.jsonl`.
