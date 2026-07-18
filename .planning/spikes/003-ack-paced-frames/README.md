---
spike: 003
name: ack-paced-frames
type: standard
validates: "Given a 20 FPS frame stream to a matrix/multizone bulb, when frames are ack-paced (latest-wins, 200ms cap, no retries) vs blind-fired, then frame application is smoother and the bulb stays responsive to concurrent queries"
verdict: VALIDATED
related: [001, 002]
tags: [animation, ack-pacing, backpressure, real-hardware]
---

# Spike 003: ack-paced-frames

## What This Validates

Given a 20 FPS frame stream to a matrix device, when frames are delivered ack-paced
(Glowup style or Photons style) vs blind-fired (lifx-async today), then delivered frame
rate, ack RTT behaviour, and the device's responsiveness to concurrent ordinary queries
differ measurably — and visibly.

## Research

Three real delivery strategies replicated:

| Arm | Source | Mechanism |
|-----|--------|-----------|
| blind | lifx-async `animator.py:311-359` ("No ACKs, no waiting") | fire every frame's Set64 packets on a fixed tick |
| glowup | Glowup `transport.py:598-763` | `ack_required` on the **last** packet per frame; wait ≤200 ms for the Acknowledgement (type 45) before the next frame; latest-frame-wins; zero retransmits |
| photons | Photons `cannons.py:107-133` (`NoisyNetworkCannon`) | `ack_required` on the **first** packet per frame as a flow-control probe; new frames gated while ≥2 probe acks outstanding; acks collected asynchronously |

Shared context: both reference clients converge on a 200 ms "acked bulb answers promptly"
expectation (Glowup `ACK_TIMEOUT`, Photons `gap_between_ack_and_res`). Photons also
observes average ack RTT ~5 ms with ~200 ms spikes (Glowup comment, `transport.py:61`).

The harness reuses lifx-async's own animation machinery (prebaked `PacketTemplate`s,
`FrameBuffer` orientation mapping) but sends through an ack-capable transport, flipping
the `ack_required` header bit (byte 22, bit 1) per arm. A concurrent prober on a separate
socket sends `GetColor` every 500 ms to measure how responsive the device remains under
each strategy, against a no-streaming baseline.

## How to Run

```bash
uv run python .planning/spikes/003-ack-paced-frames/stream.py run \
    --host 192.168.19.243   # System Test Tiles I (gen 3)
```

~2 minutes: baseline, then 30 s per arm with 5 s rest. **Watch the tiles while it runs** —
visual smoothness is part of the verdict. Do not run concurrently with Spikes 001/002.

## What to Expect

- **blind**: 100% frames offered to the wire; unknown delivery; query RTT under load shows
  whether the device's inbound queue suffers.
- **glowup**: delivered-frame confirmation via acks; if the device can't sustain 20 FPS ×
  packets-per-frame, frames skip (latest-wins) rather than queue — watch for whether
  motion stays fluid or stutters.
- **photons**: near-blind throughput with a safety valve; gated frames only under
  congestion.

## Observability

- `results-<runid>.jsonl` / `summary-<runid>.json` — per arm: frames target/sent/skipped,
  ack RTT median/p95/max, ack timeouts, concurrent-query RTT stats and loss vs baseline.

## Investigation Trail

- Built on animator privates (`_templates`, `_framebuffer`, `_packet_generator`) — spike
  licence; a real implementation would expose an ack-capable send path properly.

## Results

**Verdict: VALIDATED — blind-firing (lifx-async today) makes the device drop 1 in 7
concurrent queries; Photons-style ack-gating delivers 88% of frames with ZERO query loss
AND was judged the smoothest by eye. This is the most likely root of the "asyncio clients
feel unreliable" anecdote.**

Run 20260716-210408: System Test Tiles I (684 pixels, 4 Set64 packets/frame, 20 FPS,
30 s per arm), concurrent GetColor prober at 2/s on a separate socket.

| Condition | Frames delivered | Query loss | Query median |
|-----------|------------------|-----------|--------------|
| baseline (no stream) | — | 0% (0/20) | 16.1 ms |
| blind (lifx-async today) | 600/600 offered | **14.6%** | 102.1 ms |
| glowup (ack per frame) | 404/600 (196 skipped) | 6.1% | 51.1 ms |
| photons (ack-gated) | 530/600 (70 gated) | **0.0%** | 101.7 ms |

**Visual verdict (operator, watching live):** glowup was by far the choppiest; blind
second; photons the smoothest — despite photons sending fewer frames than blind.
Interpretation: unthrottled blast causes uneven application at the device (visible
hiccups); gated delivery matches the device's actual consumption rate. Operator context:
none approach the smoothness of directly-clocked addressable LEDs (WLED/WS2812B) — the
~20 FPS WiFi/Set64 pipeline is a platform ceiling, not a client defect.

Key findings:

1. **Blind streaming starves the device's inbound queue.** Query loss 0%→14.6% and median
   16→102 ms the moment unacked frames flow. Any app that streams (LedFx!) while also
   sending commands or polling state experiences ~15% command loss — which users read as
   "unreliable bulbs". Glowup ack-paces everything, so its commands stick; this, not
   keepalive or retries, best explains the anecdote.
2. **Photons' one-ack-per-frame flow control is the port-worthy design**: 88% frame
   delivery, zero query loss, best visual smoothness, ack RTT ~98 ms median under load.
3. **Glowup's every-frame ack over-serialises** at this packet-per-frame count: 33%
   frames skipped, visibly choppy. Right idea, too tight.

Measurement artefact (recorded, does not affect findings): the glowup arm's `ack_ms`
stats are invalid — `wait_ack` returned elapsed-before-receive rather than send-to-ack
time (median 0.0 is impossible). The photons arm measured ack RTT correctly via its
outstanding-send timestamps. Pacing behaviour itself used real ack arrivals in both arms.
