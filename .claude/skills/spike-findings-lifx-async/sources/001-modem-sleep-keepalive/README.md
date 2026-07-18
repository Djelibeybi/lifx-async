---
spike: 001
name: modem-sleep-keepalive
type: standard
validates: "Given a real bulb idle >60s, when first-command latency and loss are measured over repeated trials with vs without a 15s unicast GetService keepalive, then keepalive trials show materially lower latency/loss"
verdict: PARTIAL
related: []
tags: [keepalive, modem-sleep, latency, real-hardware]
---

# Spike 001: modem-sleep-keepalive

## What This Validates

Given a real bulb idle >60 s, when first-command latency and loss are measured over
repeated trials with vs without a 15 s unicast `GetService` keepalive, then keepalive
trials show materially lower latency/loss.

## Research

- **Glowup** (`/Volumes/External/Developer/pkivolowitz/glowup/infrastructure/bulb_keepalive.py`)
  runs a dedicated daemon: unicast `GetService` burst (2 packets, 50 ms apart) to every
  bulb every 15 s, plus ARP scans (5 s) and a subnet ping-sweep (60 s). Its docstring
  claims bulbs enter "Max Modem Sleep" after ~10 s idle.
- **Unverified**: LIFX contacts have neither confirmed nor denied the modem-sleep claim.
- **Plausible mechanism**: modern LIFX bulbs are ESP32-based; "modem sleep" is ESP-IDF's
  own power-save terminology (`WIFI_PS_MIN_MODEM`/`WIFI_PS_MAX_MODEM`). In Max Modem Sleep
  the station radio powers down between DTIM beacons and the AP buffers unicast frames
  until the next DTIM wakeup — observable as first-packet latency (potentially hundreds of
  ms depending on DTIM interval) and drops under AP buffer pressure.
- **Design consequence**: rather than trusting the claimed ~10 s threshold, Experiment 1
  measures the full dose–response curve (latency vs idle duration). A latency cliff
  locates the sleep onset and tells us the correct keepalive interval directly.
- **Confound control**: each trial snapshots the host ARP table entry for the bulb before
  probing, separating client-side ARP expiry from bulb-side effects. Older LIFX
  generations use non-ESP32 WiFi silicon, so the effect may vary by generation — run
  against a generational spread of bulbs.

## How to Run

```bash
# List candidate bulbs
uv run python .planning/spikes/001-modem-sleep-keepalive/probe.py discover

# Shakedown (~3 min)
uv run python .planning/spikes/001-modem-sleep-keepalive/probe.py run \
    --hosts <ip1>,<ip2> --quick

# Full run (~35 min, bulbs run concurrently)
uv run python .planning/spikes/001-modem-sleep-keepalive/probe.py run \
    --hosts <ip1>,<ip2>,<ip3>
```

**Precondition:** test bulbs must be quiesced from other pollers (Home Assistant, LIFX
app) for the duration — background polling is an accidental keepalive and will flatten
the very effect being measured.

## What to Expect

- **If the idle effect is real:** Experiment 1 shows first-probe RTT jumping (or losses
  appearing) beyond some idle threshold, while probes 2–5 of each train stay fast
  (~5–20 ms). Experiment 2 shows the keepalive condition holding first-probe RTT near the
  awake baseline.
- **If the effect is absent:** flat curve, no A/B difference — Glowup's advantage lies
  elsewhere (retry regime, ack pacing), and the keepalive hypothesis is INVALIDATED.

## Observability

- `results-<runid>.jsonl` — every trial as one event: phase, idle duration, keepalive
  condition, ARP state before probe, per-probe RTTs (ms), first-probe loss flag.
- `summary-<runid>.json` + stdout table — per bulb/phase/condition: n, first-probe loss %,
  first-probe median/p95/max RTT vs awake-probe median.

## Investigation Trail

- Built single-shot prober on lifx-async's own `UdpTransport` + `create_message` with
  retries disabled — the library's default 8-retry budget would mask exactly the losses
  this spike counts. One persistent unicast socket per bulb (parity with both libraries).
- Probe train of 5 per trial: probe #1 carries the post-idle signal; probes #2–5 give the
  same bulb's awake baseline within the same trial.
- A/B trials alternate condition per iteration to control for network drift.
- Shakedown (n=2) exposed two harness bugs (bytes-vs-str label handling — the library
  already converts user-visible fields to str — and a truncating p95 index) and hinted at
  first-probe spikes at idle=10 s; both fixed before the full run.
- Full run: 7 bulbs (2× gen2, 2× gen3 Tiles, 3× gen4) × 45 trials, run 20260716-201013.

## Results

**Verdict: PARTIAL — the strong modem-sleep hypothesis is INVALIDATED on this network;
keepalive gives a modest, consistent tail-latency benefit on gen4 devices only.**

Evidence (315 trials, 1573 probes):

- **Zero packet loss anywhere.** Every first probe after every idle duration (up to
  120 s) got a response within 2 s, on all seven bulbs, keepalive or not.
- **No latency cliff.** First-probe medians after 120 s idle ≈ idle=0 baselines
  (~2–40 ms). No dose–response with idle duration at all.
- **Latency spikes are background noise, not idle-related.** 100–900 ms spikes occurred
  at every idle duration including 5 s, and 2.8% of *awake* probes (35/1258) also
  spiked >100 ms. The spike rate does not grow with idle time.
- **Keepalive shrinks the tail, pooled across bulbs (60 s idle):** median 16.5→8.9 ms,
  p90 69.8→42.3 ms, max 224→81 ms. The effect concentrates in gen4 downlights
  (e.g. Downlight 2: median 45.1→7.0 ms); gen2 and gen3 show no meaningful difference.
- **Gen2 bulbs are the fastest and most consistent of the fleet** (2–4 ms medians) —
  the oldest WiFi silicon shows no power-save signature whatsoever.
- **ARP was resolved in 313/315 trials** — client-side ARP expiry is not a factor here.

Interpretation: on this network (non-mesh, well-provisioned APs), bulbs do not go
meaningfully unreachable when idle. Glowup's keepalive rationale (Max Modem Sleep +
DTIM buffering) may still hold on the mesh networks its comments reference (TP-Link
Deco/Orbi), but it cannot explain a reliability gap between clients *here*. Whatever
made Glowup feel more reliable than the asyncio clients on this network, it is not this.
The gen4-only tail effect suggests newer firmware does use WiFi power-save, just with a
fast (sub-250 ms) wake — worth a footnote in library docs, not an architecture change.

Caveats: n=5 per cell (35 pooled per A/B condition); single host, single network; a
mesh-network replication would be needed before generalising the "no cliff" claim.
