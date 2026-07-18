# Concurrency model & keepalive: landmines and settled questions

This reference records what was DISPROVEN. Its job is to stop future sessions from
re-litigating these paths.

## Settled: do NOT switch from asyncio to threading

The original idea that triggered the spike series. Measured (300 probes + 30 s paced
stream per arm, same bulb, identical workloads):

| Condition | Arm | RTT med | Losses | Send jitter med / max |
|-----------|-----|---------|--------|----------------------|
| idle | threaded | 10.0 ms | 0 | 4.8 ms / 5.8 ms |
| idle | asyncio | 11.3 ms | 0 | **1.1 ms** / 5.7 ms |
| 50 load workers | threaded | 154.6 ms | 3 | **12,616 ms / 24,553 ms** |
| 50 load workers | asyncio | 90.3 ms | 0 | 89.3 ms / 130 ms |

- Bulbs cannot observe the concurrency model; idle RTTs are indistinguishable.
- asyncio's tick pacing is 4× tighter than `time.sleep()` (macOS granularity floor).
- Under matched CPU-bearing load, GIL contention pushed the threaded arm's stream 24 s
  behind schedule; asyncio degraded gracefully (cooperative round-robin).
- Caveat: CPU-burning load is adversarial to threads; socket-blocked threads (Glowup's
  actual shape) don't contend like this. The claim is "no threading advantage exists",
  not "threaded clients misbehave".

Glowup's real reliability advantages were located elsewhere: discovery re-broadcast,
ack-paced delivery — see the other references. Its query-retry regime is actually the
worst of the three tested.

## Mostly settled: idle keepalive is NOT needed on healthy networks

Glowup runs a keepalive daemon (unicast GetService burst every 15 s) citing "Max Modem
Sleep". LIFX has neither confirmed nor denied the mechanism. Measured on 7 bulbs across
3 generations (315 trials, idle 0–120 s):

- **Zero packet loss at every idle duration.** No latency cliff anywhere — post-120 s
  medians equal awake baselines.
- 100–900 ms latency spikes occur but are background WiFi noise (2.8% of fully-awake
  probes spike too); rate does not grow with idle time.
- **Gen4-only tail effect**: keepalive pooled at 60 s idle shrank median 16.5→8.9 ms,
  p90 70→42 ms, max 224→81 ms. Newer firmware likely uses WiFi power-save with a fast
  (sub-250 ms) wake. Gen2 devices never sleep at all (2–4 ms RTT, most consistent in
  the fleet).
- ARP was resolved in 313/315 trials — client-side ARP expiry is not a factor.

**Guidance:** do not add a keepalive daemon to the library. Worth a docs footnote: apps
wanting minimal first-command latency on recent hardware may poll state periodically
(Photons' DeviceFinder polls at 10 s and gets this incidentally). Caveat: unverified on
mesh networks (TP-Link Deco/Orbi) that Glowup's comments reference — the effect may be
real there.

## Reusable measurement facts

- LIFX devices answer each GetService broadcast with ~2 StateService packets.
- Ack RTT expectation: ~5–20 ms idle, ~100 ms under streaming load; both Glowup and
  Photons independently hard-code a 200 ms "acked bulb answers by now" assumption.
- Single-shot probes (retries disabled) are mandatory when measuring loss — the library's
  retry budget masks exactly what's being counted.

## Origin

Synthesized from spikes: 001, 004.
Source files: sources/001-modem-sleep-keepalive/, sources/004-asyncio-thread-wire-equivalence/
