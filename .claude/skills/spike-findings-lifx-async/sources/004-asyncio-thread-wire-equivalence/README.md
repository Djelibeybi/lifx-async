---
spike: 004
name: asyncio-thread-wire-equivalence
type: standard
validates: "Given identical command workloads, when packet timestamps from lifx-async (asyncio) and a minimal threaded sender are captured and diffed, then inter-packet timing/jitter/response-drain are equivalent — threading itself is not the lever"
verdict: VALIDATED
related: [001, 002, 003]
tags: [asyncio, threading, wire-timing, null-hypothesis]
---

# Spike 004: asyncio-thread-wire-equivalence

## What This Validates

Given identical workloads (paced request/response probes; strict-tick fire-and-forget
streaming), when run from an asyncio sender and a threaded blocking-socket sender against
the same bulb, then RTT distributions, loss, and send-tick jitter are equivalent — i.e.
the concurrency model itself is not observable from the wire. This is the null-hypothesis
test for the original "switch to threading" idea.

## Research

No external research needed — the arms replicate the socket styles of the reference
clients: threaded arm = Glowup's blocking `socket` + `settimeout` pattern; asyncio arm =
lifx-async's `UdpTransport`. The `--load K` option runs K matched load workers (each
burning ~2 ms CPU then yielding 10 ms) in the respective model, modelling the "busy Home
Assistant event loop" hypothesis with the same application logic expressed both ways.

## How to Run

```bash
# Idle conditions
uv run python .planning/spikes/004-asyncio-thread-wire-equivalence/wire.py run \
    --host <bulb-ip>

# Busy-loop conditions (50 concurrent workers)
uv run python .planning/spikes/004-asyncio-thread-wire-equivalence/wire.py run \
    --host <bulb-ip> --load 50
```

~1 minute per run. Do not run concurrently with other spikes.

## What to Expect

- **If equivalent (expected):** RTT medians/p95 within noise of each other, send jitter
  both ≪ one tick (50 ms) — threading is not the lever; Glowup's advantage (if any) comes
  from behaviours spikes 001–003 measured.
- **If asyncio degrades under load where threading doesn't:** the busy-event-loop
  hypothesis has teeth, and mitigation guidance (executor offload, loop hygiene) belongs
  in lifx-async docs.

## Observability

- `summary-<runid>-load<K>.json` — per arm: RTT median/p95/p99/max, losses, send-tick
  jitter distribution.

## Results

**Verdict: VALIDATED — at idle the models are wire-equivalent (asyncio's pacing is
slightly tighter); under matched in-process load the hypothesis inverts: threading
degrades catastrophically while asyncio degrades gracefully.**

Target: gen4 downlight (192.168.18.95), 300 probes @ 20/s + 30 s stream @ 20 FPS per arm.

| Condition | Arm | RTT med | RTT p95 | Losses | Send jitter med | Jitter max |
|-----------|-----|---------|---------|--------|-----------------|------------|
| idle | threaded | 10.0 ms | 77 ms | 0/300 | 4.8 ms | 5.8 ms |
| idle | asyncio | 11.3 ms | 73 ms | 0/300 | **1.1 ms** | 5.7 ms |
| load 50 | threaded | 154.6 ms | 604 ms | **3/300** | **12,616 ms** | 24,553 ms |
| load 50 | asyncio | 90.3 ms | 271 ms | 0/300 | 89.3 ms | 130 ms |

Key findings:

1. **Idle: no wire-observable difference.** RTT distributions are statistically
   indistinguishable. Asyncio's send-tick jitter is actually 4× tighter (1.1 vs 4.8 ms —
   the threaded arm's floor is `time.sleep()` granularity on macOS).
2. **Under load, the threaded arm collapsed.** With 50 CPU-burning threads contending for
   the GIL, the pacing thread's stream fell up to **24.5 s behind schedule** (median
   jitter 12.6 s) and dropped 3 probes. The asyncio arm under the same logic-equivalent
   load stayed orderly: jitter bounded at 130 ms, zero losses, better RTTs — cooperative
   scheduling round-robins fairly where preemptive GIL contention thrashes.
3. **Caveat:** the load model (CPU-burning workers) is deliberately adversarial to
   threads; Glowup's real threads mostly block on sockets and would not contend like
   this. The finding is not "Glowup behaves badly" — it is "threading confers no wire
   advantage, and CPU-heavy threaded apps pace worse". Single host (macOS), single bulb.

Combined with Spikes 001–002, the original idea — "switch from asyncio to threading for
concurrency" — is empirically dead: bulbs cannot see the concurrency model, and where the
models differ at all under stress, asyncio wins.
