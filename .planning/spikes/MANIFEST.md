# Spike Manifest

## Idea

Original prompt: "switch from asyncio to threading for concurrency." Reframed after
investigation: LIFX bulbs are anecdotally more reliable/responsive with Glowup (a threaded
client, source at `/Volumes/External/Developer/pkivolowitz/glowup/`) than with lifx-async or
aiolifx (both asyncio). Bulbs cannot observe a client's concurrency model — only packets,
timing, and how promptly responses are drained. These spikes isolate which of Glowup's wire
behaviours actually cause the reliability gap, and whether lifx-async can adopt them without
abandoning its asyncio core.

Code study of Glowup identified four candidate levers absent from lifx-async:

1. **Idle keepalive** — unicast `GetService` burst (2 packets, 50 ms apart) to every bulb
   every 15 s. Glowup's stated rationale is preventing the bulb WiFi radio entering
   "Max Modem Sleep" (~10 s idle) and keeping kernel ARP entries warm. **Caveat: LIFX
   contacts have neither confirmed nor denied the modem-sleep behaviour** — treat it as an
   unverified hypothesis. Supporting context: modern LIFX bulbs are ESP32-based, and
   "modem sleep" is ESP-IDF's own term (`WIFI_PS_MIN_MODEM`/`WIFI_PS_MAX_MODEM`) — in Max
   Modem Sleep the radio powers down between DTIM beacons and the AP buffers unicast
   frames until the next wakeup. Older LIFX generations use different WiFi silicon, so the
   effect may vary by device generation. Spike 001 tests the observable effect (post-idle
   latency/loss) across generations, which is meaningful whichever mechanism is responsible
   (bulb radio sleep, AP power-save buffering/DTIM, client-side ARP expiry, or mesh
   forwarding).
2. **Ack-paced frame delivery** — animation frames wait ≤200 ms for an Acknowledgement
   (type 45) before the next send; latest-frame-wins slot; zero retransmits.
3. **Retry regime** — Glowup: 3 quick fresh-deadline retries (queries), 0 for frames.
   lifx-async: up to 8 retries with exponential backoff over a 16 s budget.
4. **Wake bursts** before commands (mesh-router DTIM workaround).

Code study of Photons (asyncio, insider-authored) added a third reference regime:

- **Retransmits on an escalating-gap schedule** (`timeouts=[(0.2,0.2),(0.1,0.5),(0.2,1),(1,5)]`
  → gaps ≈0.2, 0.3, 0.4, 0.5, 0.7 … backing off to 5 s) until the caller's
  `message_timeout` (default 10 s). **Fresh sequence number per retransmit**, first reply
  wins, duplicate late replies expected and discarded.
- **`gap_between_ack_and_res = 0.2 s`** — converges with Glowup's `ACK_TIMEOUT = 0.2`:
  two independent codebases assume an acked bulb answers within 200 ms.
- **No keepalive code and no power-save handling anywhere** — but its DeviceFinder polls
  light state every 10 s while running, an incidental keepalive. Both "reliable" reference
  clients keep bulbs continuously warm, one deliberately, one incidentally.
- **`NoisyNetworkCannon`** for tile animation on lossy WiFi: acks only the *first* Set64
  per frame as a flow-control probe, gates new frames on outstanding acks (vs Glowup's
  ack-final-packet-of-every-frame). Unchanged frames force-resent every 0.5 s to ride
  through UDP loss. Spike 003 gains this as a third arm.

Threading itself is the null hypothesis, tested last (Spike 004).

**Candidate — spike 006 (raised 2026-07-17, Phase 5 UAT; not yet scheduled).** Spike 002
established the Photons schedule as the winner and lifx-async shipped its gap tuple verbatim —
`REQUEST_RETRANSMIT_GAPS` == `race.py`'s `PHOTONS_GAPS` == the expansion of Photons'
`timeouts=[(0.2,0.2),(0.1,0.5),(0.2,1),(1,5)]`, plateau on the final gap included. But it shipped
inside a **different envelope than the one that was raced**, and that envelope has never been
measured:

| | raced `regime_photons` (won, 1/180) | shipped |
|---|---|---|
| gaps | `0.2 … 5.0` | same |
| timeout | `10.0` | `16.0` (`DEFAULT_REQUEST_TIMEOUT`) |
| retry cap | none — retransmits to the deadline | `max_retries=8` (`DEFAULT_MAX_RETRIES`) |
| sends | t=0 … 9.0, 10 packets across the full window | t=0 … 6.0, **9 packets, then silent to 16 s** |

The cap truncates the tuple before its tail fires: `3.0, 4.0, 5.0` are unreachable at defaults.
**The open question is whether the ~10 s silent tail costs anything under loss** — a reply that a
t=9.0 retransmit would have triggered never gets one. Independent-loss arithmetic says it should
not matter (9 sends at 50% ≈ 0.2% never-through), but this whole series exists because real bulb
loss is *bursty and correlated* (modem sleep, congestion, wake tails) — and a 10 s silent window is
exactly where a correlated burst hides. Cheap to answer: spike 002's harness already carries all
three regimes; this adds one arm.

Note this spike cannot answer the question that surfaced it (see Origin below) — there is no public
API to override the gaps at all. If the cap proves harmful the fix is source behaviour, not docs.

**Reference implementations:**

- **Glowup** (threaded) — `/Volumes/External/Developer/pkivolowitz/glowup/` — the client
  whose anecdotal reliability prompted this investigation.
- **Photons** (asyncio) — `/Volumes/External/Developer/Djelibeybi/photons` — written by a
  former LIFX engineer, powers LIFX Cloud, and Avi has contributed to it for years. A
  reliable *asyncio* client is itself evidence against threading being the lever; its
  retry/timing constants encode insider knowledge of real bulb behaviour.

## Requirements

- Must run against real LIFX hardware — the emulator cannot model modem sleep or WiFi loss.
- Test bulbs must be quiesced from other pollers (Home Assistant, LIFX app) during trials,
  otherwise background polling acts as an accidental keepalive and confounds results.
- Any adopted fix must keep the asyncio core and public async API unchanged.

## Spikes

| # | Name | Type | Validates | Verdict | Tags |
|---|------|------|-----------|---------|------|
| 001 | modem-sleep-keepalive | standard | Given a real bulb idle >60 s, when first-command latency and loss are measured over repeated trials with vs without a 15 s unicast GetService keepalive, then keepalive trials show materially lower latency/loss | PARTIAL — no idle cliff, zero loss on this network; modest gen4-only tail benefit (pooled p90 70→42 ms) | keepalive, modem-sleep, latency, real-hardware |
| 002 | retry-storm-vs-fresh-deadline | comparison | Given a slow/lossy path to a bulb, when lifx-async's 8-retry exponential backoff competes with Glowup-style 3× fresh-deadline retries, then responsiveness under stress differs measurably | VALIDATED — photons schedule best (1/180 fail); glowup worst under loss (24/60 fail @ 50%); two lifx-async defects confirmed (31 ms duplicate-firing first window; wall time 29 s vs 16 s budget) | retries, backoff, congestion, real-hardware |
| 003 | ack-paced-frames | standard | Given a 20 FPS frame stream to a matrix/multizone bulb, when frames are ack-paced (latest-wins, 200 ms cap, no retries) vs blind-fired, then frame application is smoother and the bulb stays responsive to concurrent queries | VALIDATED — blind fire drops 14.6% of concurrent queries (0% at baseline); photons-style ack-gating: 88% frames, 0% query loss, smoothest by eye. Likeliest root of the anecdote | animation, ack-pacing, backpressure, real-hardware |
| 005 | discovery-regimes | comparison | Given a 73-device fleet, when lifx-async, Glowup (0.5 s re-broadcast + wake bursts) and Photons (0.6→20 s backoff schedule) discovery regimes each run repeatedly, then coverage (devices found vs known roster), time-to-full-coverage, and packet cost differ measurably | VALIDATED — single broadcast finds median 48/73 (min 27!); photons schedule 73/73 at 29% of glowup's packet cost. Most severe lifx-async finding of the series | discovery, broadcast, coverage, real-hardware |
| 004 | asyncio-thread-wire-equivalence | standard | Given identical command workloads, when packet timestamps from lifx-async (asyncio) and a minimal threaded sender are captured and diffed, then inter-packet timing/jitter/response-drain are equivalent — threading itself is not the lever | VALIDATED — wire-equivalent at idle (asyncio jitter 4× tighter); under matched load threading collapses (12.6 s median jitter, GIL thrash) while asyncio stays bounded at 89 ms | asyncio, threading, wire-timing, null-hypothesis |
| 006 | retry-cap-vs-photons-envelope | comparison | Given a lossy path to a bulb, when the **shipped** lifx-async config (`timeout=16.0`, `max_retries=8` → 9 sends ending t≈6.0, then silent listening to 16 s) races spike 002's winning `regime_photons` envelope (`timeout=10.0`, uncapped retransmits to the deadline) and an uncapped 16 s arm, then failure rate, latency and packet cost differ measurably | CANDIDATE — not yet run | retries, backoff, max-retries, real-hardware, candidate |
