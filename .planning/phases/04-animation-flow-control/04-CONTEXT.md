# Phase 4: Animation Flow Control — Context

**Source:** Spike 003 (`.planning/spikes/003-ack-paced-frames/`) and the
`spike-findings-lifx-async` skill (`references/animation-flow-control.md`). Distilled
from the spike-series review + v1.1 milestone scoping (2026-07-16).

## Decisions (settled)

- **D4-01**: The Animation layer paces frame delivery via ack-gated flow control as
  **internal library behaviour**: `ack_required` probe on ONE packet per frame, new
  frames gated while ≥2 probe acks are outstanding, outstanding entries expire after
  ~1 s, latest-frame-wins (gated frames are dropped, never queued). Measured tuning on
  Tiles: ack RTT ~98 ms median / ~150 ms p95 under 20 FPS load.
- **D4-02**: **No downstream-facing toggle** (user decision 2026-07-16, supersedes the
  spike's earlier "opt-in mode" framing). Consumers (LedFx) just send frames; the layer
  that sends frames decides delivery strategy.
- **D4-03**: Preserve the zero-allocation prebaked `PacketTemplate` send path. The
  ack-capable transport becomes a proper animator facility — the spike reached into
  `animator._templates`/`._framebuffer` privates and flipped header bytes externally;
  the real build exposes this correctly (header FLAGS_OFFSET=22 bit 1, SEQ_OFFSET=23).
- **D4-04**: Large-matrix framebuffer path (ANIM-04): devices whose frames span multiple
  Set64 packets plus a `CopyFrameBuffer` swap (e.g. Ceiling 13×26). Where the ack probe
  attaches (a Set64 vs the CopyFrameBuffer) is a research/hardware question — Glowup
  fire-and-forgets Set64s and acks the CopyFrameBuffer swap on >64-zone ceilings; decide
  from the codebase's actual large-tile template structure and validate on hardware.
- **D4-05**: Scope: `src/lifx/animation/` only. No device-layer, network-layer
  (`connection.py`), or effects-layer changes beyond what the animator facility needs.
  Public `Animator` API (`for_matrix`/`for_multizone`/`for_light`, `send_frame`) keeps
  working — `send_frame` remains the entry point; pacing happens inside.

## Measured baselines (success targets)

From spike 003 (Tiles I, 684 pixels, 4 packets/frame, 20 FPS, concurrent GetColor
prober at 2/s on a separate socket):

| Condition | Frames delivered | Concurrent query loss | Query median |
|-----------|------------------|----------------------|--------------|
| baseline (no stream) | — | 0% | 16.1 ms |
| blind (today) | 600/600 offered | **14.6%** | 102.1 ms |
| photons-style ack-gated | 530/600 (70 gated) | **0.0%** | 101.7 ms |

- ANIM-03 target: 0% concurrent-query loss under 20 FPS streaming on Tiles
  (192.168.19.243 or .18.62), with delivered-frame rate ≥85% and **operator visual
  verdict** (spike: ack-gated was smoothest by eye; requires Avi watching).
- ANIM-04 target: same flow control exercising the multi-packet + CopyFrameBuffer path
  on **My Office Ceiling Capsule** (192.168.19.231, product 201, 13×26 Ceiling,
  removed from HA 2026-07-16), with the probe-attachment decision recorded and
  hardware-validated. Requires power-on before visual runs (send set_power first —
  animation is invisible otherwise).

## Constraints

- ~20 FPS over WiFi/Set64 is a platform ceiling — do not chase higher FPS.
- Emulator: can validate packet construction, ack-flag placement, gating logic with a
  mocked/emulated ack source; CANNOT model real ack RTT under load — hardware UAT
  mandatory for ANIM-03/04.
- The animator's send path is currently synchronous (`send_frame` uses a raw non-blocking
  socket, no receive path at all: `animator.py:311-359` "No ACKs, no waiting"). Adding an
  ack-capable transport means the animator needs a receive capability — design carefully
  against the existing `UdpTransport` (asyncio) without regressing the zero-allocation
  hot path or forcing API changes on consumers.
- Phase 3's reshaped retry engine is live; animation acks are NOT retried (zero
  retransmits — latest-frame-wins is the recovery mechanism).
- CI: 100% branch patch coverage on automated tests; pyright strict; ruff clean.

## Requirements in scope

ANIM-01 (ack-gated internal flow control), ANIM-02 (prebaked path preserved; proper
facility), ANIM-03 (Tiles hardware UAT: 0% query loss + visual verdict), ANIM-04
(large-matrix framebuffer path incl. probe attachment, hardware-validated on the
Ceiling Capsule).
