# Animation flow control: ack-gated frame delivery

## Requirements

- Keep the asyncio core and public async API unchanged.
- Flow control is decided by the animation library internally, NOT exposed as a
  downstream/consumer-facing choice (user decision, 2026-07-16 — supersedes the earlier
  "opt-in mode" framing from the spike session).
- Preserve the zero-allocation prebaked-template send path (`PacketTemplate`).

## The Problem (measured)

`Animator.send_frame()` is pure blind fire ("No ACKs, no waiting",
`animator.py:311-359`). Streaming 20 FPS × 4 Set64 packets/frame at a Tile set while a
separate socket polled `GetColor` at 2/s:

| Condition | Frames delivered | Concurrent query loss | Query median |
|-----------|------------------|----------------------|--------------|
| baseline (no stream) | — | 0% | 16.1 ms |
| blind (today) | 600/600 offered | **14.6%** | 102.1 ms |
| glowup (ack every frame) | 404/600 | 6.1% | 51.1 ms |
| **photons (ack-gated)** | 530/600 | **0.0%** | 101.7 ms |

Blind streaming starves the device's inbound queue: 1 in 7 other requests to the device
vanish. Any consumer that streams while also sending commands (LedFx + HA/app control)
experiences this as "unreliable bulbs". **Operator visual verdict: the ack-gated arm was
also the smoothest to watch; the every-frame-ack arm was by far the choppiest.**

## How to Build It

Photons' `NoisyNetworkCannon` pattern, validated on real Tiles:

1. Set `ack_required` (header byte 22, bit 1) on the **first** packet of each frame
   only — it acts as a flow-control probe. Sequence byte is offset 23.
2. Track outstanding probe acks `{seq: sent_at}`. Before sending a new frame, sweep
   arrived acks non-blockingly; if outstanding ≥ 2, **drop this frame** (do not queue).
   Expire outstanding entries after ~1 s.
3. Acks are packet type 45 (`Acknowledgement`), matched on (source, sequence).
4. Latest-frame-wins always: a dropped frame is skipped, never buffered.

Working implementation: `sources/003-ack-paced-frames/stream.py` — `FrameStreamer`
(template flag/sequence stamping, `collect_acks()`) and `arm_photons()` (the gate loop).
Measured ack RTT under streaming load: ~98 ms median, ~150 ms p95 on Tiles.

The real build needs an ack-capable transport in the animator (the spike used
`UdpTransport` instead of the animator's raw non-listening socket) — expose this
properly rather than reaching into privates as the spike did.

## What to Avoid

- **Glowup's ack-every-frame serialisation**: at 4+ packets/frame it over-paces — 33% of
  frames skipped and visibly the choppiest arm. Right instinct, too tight.
- **Increasing FPS to compensate for drops** — the device applies what it can; pushing
  harder only worsens inbound-queue starvation.
- Waiting synchronously for the probe ack before sending the frame's remaining packets —
  the probe is fire-and-observe, not a gate on the current frame.

## Constraints

- ~20 FPS over WiFi/Set64 is a platform ceiling; visual smoothness will never match
  directly-clocked LED strips (WLED/WS2812B) regardless of client design.
- Ack RTT under load is ~100 ms — the outstanding-ack limit (2) and expiry (1 s) are
  tuned to that; revalidate if targeting different device families.
- Set64 has no response packet; the ack flag is the only delivery signal available.

## Origin

Synthesized from spike: 003.
Source files: sources/003-ack-paced-frames/
