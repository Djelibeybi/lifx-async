# Phase 4: Animation Flow Control - Research

**Researched:** 2026-07-17
**Domain:** UDP flow control inside the lifx-async animation layer (`src/lifx/animation/`)
**Confidence:** HIGH — all findings verified by direct codebase reading, spike 003 hardware measurements, and the installed lifx-emulator-core 3.6.3 source

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

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

### Claude's Discretion

(None recorded in CONTEXT.md — design details within the locked decisions are open,
including the ack-receive mechanism, constants placement, and the large-tile probe
attachment point, which this research decides and hardware UAT validates.)

### Deferred Ideas (OUT OF SCOPE)

(None recorded in CONTEXT.md.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ANIM-01 | Ack-gated internal flow control (probe 1 pkt/frame, gate at 2 outstanding, ~1 s expiry, latest-frame-wins, zero retransmits, no toggle) | Recommended design (sync non-blocking sweep on the animator's own socket) + spike 003 measured tuning; constants and edit points below |
| ANIM-02 | Zero-allocation prebaked path preserved; ack collection is a proper animator facility | `AckGate` facility in new `src/lifx/animation/flow.py`; ack flag baked ONCE into the probe template at init — hot path unchanged except one dict write per sent frame |
| ANIM-03 | Tiles hardware UAT: 0% concurrent-query loss + operator visual verdict | Manual-only UAT; spike harness `stream.py` pattern reusable; emulator cannot model RTT under load (constraint in CONTEXT.md) |
| ANIM-04 | Large-matrix framebuffer path (multi-Set64 + CopyFrameBuffer) under same flow control; probe attachment decided, recorded, hardware-validated | Actual template structure mapped below; probe attaches to the final CopyFrameBuffer via new `PacketGenerator.probe_template_index`; **latent chunking bug found for 13-wide tiles that must be fixed for ANIM-04 to pass** |
</phase_requirements>

## Summary

The animator today is pure blind fire: `send_frame()` is a synchronous method over a raw
non-blocking UDP socket with **no receive path at all** (`animator.py:311-359`). Spike 003
measured that this starves the device's inbound queue (14.6% concurrent-query loss at
20 FPS on Tiles) and that photons-style ack-gating eliminates the loss entirely (0.0%)
while remaining the visually smoothest arm.

The key design insight from this research: **the animator's existing socket already
receives the acks.** LIFX devices reply to the source address of the probe packet, and a
UDP socket that has sent via `sendto` is bound to an ephemeral port that receives those
replies. No `UdpTransport`, no `loop.add_reader`, no background task, and no async
variant of `send_frame` is needed — a synchronous, non-blocking `recvfrom_into` sweep at
the top of `send_frame` (exactly where the gating decision is made) collects acks with
zero event-loop coupling and one preallocated buffer. This preserves the sync
`send_frame` contract, the zero-allocation hot path, and the public API, satisfying
D4-02/D4-03/D4-05 simultaneously.

Two significant discoveries change the plan's shape. First, the large-tile template
structure already prebakes a `CopyFrameBuffer` packet per tile (verified in
`packets.py:352-382`), so the D4-04 probe-attachment question is answerable from code:
attach the probe to the **final CopyFrameBuffer template** in large-tile mode via a new
`PacketGenerator.probe_template_index` property (default 0 = first packet for every
other generator, matching the ROADMAP's locked "ack flag on the first packet" wording
and the spike's measured arm). Second, a **latent chunking bug**: the animation
generator slices colours at raw 64-pixel boundaries while stamping row-aligned rect
offsets — correct only when `tile_width` divides 64. The ANIM-04 target device (Ceiling
13×26, product 201) has width 13, so today's animation path would paint garbled frames
on the exact hardware the UAT runs against. The row-aligned fix (mirroring
`MatrixLight.set_matrix_colors`, `devices/matrix.py:836-859`) must land in this phase.

**Primary recommendation:** Add an `AckGate` facility (`src/lifx/animation/flow.py`)
swept synchronously inside `send_frame`; bake the ack flag once into the probe template
selected by `PacketGenerator.probe_template_index`; fix large-tile chunking to
row-aligned batches; extend `AnimatorStats` with `gated: bool = False`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Frame gating decision (outstanding-ack count, expiry) | Animation layer (`flow.py`, new) | — | D4-01: flow control is internal animator behaviour |
| Ack reception + header peek | Animation layer (`Animator._socket` sweep) | — | Device replies to the probe's source port — the animator's own socket is the only socket that can receive them |
| Probe flag placement (which template carries `ack_required`) | Animation layer (`packets.py` generators) | — | Only the generator knows the template ordering (Set64s vs CopyFrameBuffer) |
| Sequence stamping / template mutation | Animation layer (`animator.py` send loop) | — | Existing hot path; unchanged except probe tracking |
| Large-tile row-aligned chunking | Animation layer (`MatrixPacketGenerator`) | — | Mirrors the proven device-layer strategy (`set_matrix_colors`) without touching the device layer (D4-05) |
| Retransmission / reliability | **Nobody** | — | Zero retransmits by design (D4-01); latest-frame-wins is the recovery mechanism; Phase 3's retry engine explicitly NOT reused |
| Consumer pacing (FPS clock) | Downstream consumer (LedFx) | — | Consumer keeps its own tick loop; gated frames return `gated=True` stats and are simply dropped |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `socket` | 3.10–3.14 | Non-blocking UDP send/recv sweep | Already the animator's transport; zero dependencies is a hard project constraint [VERIFIED: codebase `pyproject.toml` — zero runtime deps] |
| Python stdlib `struct` | 3.10–3.14 | Header field peeks (`unpack_from`) | Already used throughout `packets.py` [VERIFIED: codebase] |
| Python stdlib `time.monotonic` | 3.10–3.14 | Outstanding-ack timestamps/expiry | Steady clock; matches `transport.py` usage (spike used `perf_counter`; either works — recommend `monotonic` for consistency with the network layer) [VERIFIED: codebase] |

### Supporting (dev only, already installed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest + pytest-asyncio | 8.4.2+ / 0.24+ (`asyncio_mode = "auto"`) | Test framework | All automated tests [VERIFIED: pyproject.toml] |
| pytest-cov | 7.0+ with `--cov-branch` in addopts | Branch coverage | CI requires 100% branch patch coverage [VERIFIED: pyproject.toml addopts] |
| lifx-emulator-core | 3.6.3 (installed) | In-process emulator; **answers `ack_required` with Acknowledgement (45) on every handled packet, including Set64 (715) and CopyFrameBuffer (716)**; per-device scenarios can drop or delay acks (`drop_packets: {45: 1.0}`, `response_delays: {45: 0.5}`) | Integration tests for gating [VERIFIED: emulator source `server.py:250-265`, `devices/device.py:299-330`, `scenarios/models.py:58-66`, `devices/device.py:51-52`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Sync `recvfrom_into` sweep on the animator's socket | `UdpTransport` (asyncio) | Forces a running event loop, allocates a queue entry per datagram, needs a background-task lifecycle the sync `Animator` has no place for, and would push `send_frame` towards async — breaking the "synchronous for minimum overhead" contract and existing sync callers/tests. The spike used it only for convenience |
| Sync sweep | `loop.add_reader(sock.fileno(), cb)` | Requires a running loop at socket-creation time (send_frame is callable without one today), per-ack callback overhead, and fragile teardown (`remove_reader` in `close()`/`__del__` after the loop is gone). Sweeping at frame boundaries is exactly when the gate decision is needed anyway — a reader callback adds no earlier decision point |
| Same-socket ack receive | Second dedicated ack socket | Cannot work: the device addresses the Acknowledgement to the probe packet's source port. Only the sending socket receives it [VERIFIED: spike 003 received acks on the sending transport; LIFX LAN protocol behaviour] |

**Installation:** none — zero new dependencies.

## Package Legitimacy Audit

No external packages are installed by this phase. All work uses the Python standard
library and already-installed dev dependencies.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Consumer tick loop (e.g. LedFx, effects layer)
        │  send_frame(hsbk)                      ── unchanged public API
        ▼
┌─ Animator.send_frame (sync) ──────────────────────────────────────────┐
│ 1. ensure socket (lazy, non-blocking)                                 │
│ 2. AckGate.sweep(socket, source, now)   ◄── non-blocking recvfrom     │
│      pop acks matching (source, seq) ── expire entries > 1 s          │
│ 3. gated? (outstanding ≥ 2) ──yes──► return AnimatorStats(gated=True) │
│      │ no                              (frame DROPPED, never queued)  │
│ 4. framebuffer.apply → generator.update_colors (prebaked templates)   │
│ 5. for each template: stamp seq, sendto                               │
│      template idx == probe_template_index → AckGate.track(seq, now)   │
└───────────────────────────────────────────────────────────────────────┘
        │ UDP datagrams                       ▲ Acknowledgement (45)
        ▼                                     │ to the socket's ephemeral port
   LIFX device ───────────────────────────────┘
   (probe template carries ack_required, baked at init:
    standard/multizone/light → first packet;
    large-tile → final CopyFrameBuffer)
```

### Recommended Project Structure

```
src/lifx/animation/
├── animator.py        # + AckGate wiring, gate-check in send_frame, stats fields
├── flow.py            # NEW: AckGate + flow-control constants (only new file)
├── packets.py         # + FLAGS_OFFSET/ACK_REQUIRED_FLAG, probe_template_index,
│                      #   row-aligned large-tile chunking fix
├── framebuffer.py     # unchanged
└── orientation.py     # unchanged
tests/test_animation/
├── test_flow.py       # NEW: AckGate unit branch matrix
├── test_animator.py   # updated mocked-socket tests + gating tests + emulator gating
└── test_packets.py    # + 13-wide row-aligned templates, probe_template_index
```

### Pattern 1: Sync non-blocking ack sweep on the sending socket (Q1 answer — the ONE recommended design)

**What:** `AckGate` holds `outstanding: dict[int, float]` (probe seq → sent monotonic
time) and a preallocated `bytearray` receive buffer. At the top of `send_frame`, after
the lazy socket exists, `sweep()` drains the socket with `recvfrom_into` until
`BlockingIOError`, peeking pkt_type (bytes 32–33 LE), source (bytes 4–8 LE), and
sequence (byte 23) directly from the buffer — no `parse_message`, no object allocation.
Matching entries are popped; entries older than `ACK_EXPIRY_SECONDS` are pruned. If
`len(outstanding) >= ACK_INFLIGHT_LIMIT`, the frame is dropped before any framebuffer
work.

**When to use:** every `send_frame` call, all device families (see Don't Hand-Roll and
Pitfall 6 for why uniformly).

**Why this design wins** (against the alternatives weighed above): keeps `send_frame`
synchronous and loop-free (existing test asserts
`not inspect.iscoroutinefunction(animator.send_frame)` — `test_animator.py:148-152`),
touches no public API, reuses the one socket that can physically receive the acks, and
does the sweep at the only moment a gating decision is consumed.

**Concrete edit points:**

1. **`src/lifx/animation/flow.py` (new)** — constants + `AckGate` (see Code Examples).
2. **`src/lifx/animation/packets.py`**
   - Module constants next to `SEQUENCE_OFFSET = 23`: `FLAGS_OFFSET = 22`,
     `ACK_REQUIRED_FLAG = 0x02` (header byte 22 bit 1 [VERIFIED: `_build_header`
     packs flags at offset 22 via `struct.pack_into("<8s6sBB", header, 8, ...)` —
     8+8+6=22; spike used the same offsets against real hardware]).
   - `PacketGenerator.probe_template_index` property, default `0`.
     `MatrixPacketGenerator` overrides: `0` for standard tiles; **last template index**
     (the final CopyFrameBuffer) in large-tile mode.
   - Fix `_create_large_tile_templates` chunking to row-aligned batches (Pitfall 1).
3. **`src/lifx/animation/animator.py`**
   - `__init__`: create `self._ack_gate = AckGate()`; compute
     `probe_idx = packet_generator.probe_template_index`; bake the flag once:
     `self._templates[probe_idx].data[FLAGS_OFFSET] |= ACK_REQUIRED_FLAG`; store
     `self._probe_index = probe_idx`. The hot path never touches the flags byte again.
   - `send_frame`: (a) explicit input-length check first (`len(hsbk) !=
     self._framebuffer.canvas_size` → ValueError with "must match pixel_count" wording
     so the wrong-length contract holds even for gated frames — `canvas_size` equals
     the expected input length in every framebuffer mode [VERIFIED: FrameBuffer
     constructor defaults make `canvas_size == pixel_count` for passthrough modes]);
     (b) ensure socket; (c) `self._ack_gate.sweep(self._socket, self._source, now)`;
     (d) if `self._ack_gate.gated`: return `AnimatorStats(packets_sent=0,
     total_time_ms=..., gated=True, acks_outstanding=n)`; (e) existing apply →
     update_colors → send loop, and when `i == self._probe_index`:
     `self._ack_gate.track(seq_just_stamped, now)`.
   - `close()`: also `self._ack_gate.reset()`.
   - `AnimatorStats`: add `gated: bool = False` and `acks_outstanding: int = 0`
     (frozen dataclass with defaults — existing constructions/tests unaffected).
4. **`src/lifx/animation/__init__.py`**: optionally export `FLAGS_OFFSET` alongside
   `SEQUENCE_OFFSET` (consistency); do NOT export `AckGate` (internal facility, D4-02).

### Pattern 2: Probe attachment for the large-matrix path (Q2 answer, D4-04)

**What the code sends today** [VERIFIED: `packets.py:298-384`]: for each large tile
(`pixels_per_tile > 64`), templates are ordered `[Set64(fb_index=1, y=k·rows) × N,
CopyFrameBuffer(src_fb=1 → dst_fb=0, full tile rect, duration=0)]`, repeated per tile.
So **yes — a CopyFrameBuffer packet is already prebaked in the template list**, one per
tile, always last for its tile; the final template overall is the last tile's CopyFB.
The `CopyFrameBuffer` template has `color_count=0` and is skipped by `update_colors`.

**Decision (to record per ROADMAP criterion 4, validate on hardware):** attach the
probe to the **final CopyFrameBuffer template** (last template in the list) in
large-tile mode; first template (index 0) everywhere else.

**Rationale:**
- The CopyFB is the frame-commit packet — nothing is visible until the swap. Acking it
  matches Glowup's proven field behaviour on >64-zone ceilings (D4-04).
- The device processes datagrams in arrival order, so the CopyFB ack RTT includes the
  device's drain of the frame's whole Set64 burst — a strictly better congestion signal
  than the first Set64's ack on a multi-packet frame.
- Its payload is 15 bytes (vs 522 for Set64), so the probe adds no parse skew.
- Ceiling 13×26 is a single tile, so "last template" and "the tile's CopyFB" coincide;
  for hypothetical multi-tile large chains the last tile's CopyFB still terminates the
  frame.
- Standard mode stays probe-on-first-packet: that is the exact arm spike 003 measured
  (0.0% loss) and the wording locked in ROADMAP success criterion 1.

Tagged [ASSUMED → hardware-validate]: that a Ceiling 13×26 under 20 FPS streaming acks
the CopyFB with RTTs compatible with the limit-2/1 s tuning. ANIM-04's UAT on
192.168.19.231 confirms or adjusts; the `probe_template_index` seam makes flipping to
"first Set64" a one-line generator change if hardware disagrees.

### Pattern 3: Ack correlation and sequence wrap (Q4 answer)

Templates prebake `source` and `target`; the send loop stamps a fresh sequence byte per
packet from a single 0–255 counter, so **one frame consumes N sequences and the probe's
seq is whichever value lands on the probe template**. Correlation on sweep: match
`pkt_type == 45 and source == self._source and seq in outstanding` (the spike matched
seq-only within the outstanding dict; adding the source check is free and filters any
stray datagram).

Wrap analysis: a collision needs the counter to wrap 256 while a probe is still
outstanding (≤1 s). Sequence burn rate = packets_per_frame × FPS:

| Device | Packets/frame | Seq/s @20 FPS | Wrap time |
|--------|--------------|---------------|-----------|
| Tiles I chain (5×64) | 5 | 100 | 2.56 s ✓ safe |
| Ceiling 16×8 | 3 | 60 | 4.3 s ✓ |
| Ceiling 13×26 (fixed chunking) | 8 (7 Set64 + CopyFB) | 160 | 1.6 s ✓ |
| Hypothetical >12.8 pkt/frame | >256/s | <1 s ⚠ possible overwrite |

On a collision, `outstanding[seq] = now` overwrites the stale entry; the older ack then
releases the newer slot early. That errs towards **sending** (today's baseline
behaviour), never towards stalling — self-healing and acceptable. Document in the
`AckGate` docstring; no extra mechanism warranted.

Also note: gated frames consume **no** sequence numbers (nothing is sent), which
further slows wrap under congestion — exactly when it matters.

### Anti-Patterns to Avoid

- **Ack-every-frame serialisation (Glowup arm):** waits on each frame's ack before the
  next tick — measured 33% frame skips and visibly the choppiest arm on Tiles. The
  probe is fire-and-observe, never a gate on the current frame's remaining packets.
- **Queueing gated frames:** latest-frame-wins is the recovery mechanism; a queue turns
  congestion into latency and stale frames.
- **Retransmitting unacked probes:** zero retransmits by design (D4-01); an expired
  probe just frees a gate slot.
- **`parse_message()` in the sweep:** full parse allocates header objects per datagram;
  peek the three fields with `struct.unpack_from`/indexing instead.
- **Raising FPS to compensate for gated frames:** pushing harder worsens the inbound
  queue starvation the gate exists to prevent (spike finding).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ack packet identification | Custom protocol parser or reuse of `parse_message` | 3 fixed-offset peeks (`pkt_type`@32-33, `source`@4-8, `seq`@23) validated by `nbytes >= 36` | Header layout is fixed by the LIFX protocol; the offsets are already canon in this module (`SEQUENCE_OFFSET`) and spike-proven on hardware |
| Large-tile chunk math | New geometry logic | Mirror `set_matrix_colors` row-aligned batching (`rows_per_batch = 64 // width`) [VERIFIED: `devices/matrix.py:836-859`] | The device fills Set64 rects row-major from (x, y) with the given width; the device layer already encodes the correct, hardware-proven strategy |
| Congestion tuning | Adaptive RTT estimators, windows, retransmit timers | Fixed `limit=2`, `expiry=1.0 s` from spike 003 measurements (~98 ms median / ~150 ms p95 ack RTT under load) | Measured on the target hardware class; adaptive schemes are unfalsifiable without per-family hardware campaigns and violate "zero retransmits, keep it boring" |
| Reliability layer | Frame retry / keepalive wrappers | Latest-frame-wins + Phase 5 documentation telling consumers NOT to add their own | DOCS-02 explicitly documents that consumers must not reimplement acks/retries |

**Key insight:** every reliability mechanism beyond the gate (retries, queues, adaptive
windows) was either measured worse in spike 003 or reintroduces the queue starvation
this phase exists to remove.

## Common Pitfalls

### Pitfall 1: Large-tile chunking is misaligned for widths that don't divide 64 — the ANIM-04 device is affected TODAY

**What goes wrong:** `_create_large_tile_templates` slices colours at raw 64-pixel
boundaries (`color_start = pkt_idx * 64`, `packets.py:309`) but stamps rect offsets in
whole rows (`y_offset = pkt_idx * rows_per_packet` where `rows_per_packet = 64 //
tile_width`, `packets.py:223, 320`). The device fills each Set64 row-major from
(0, y_offset) — so the packet's colours land at linear pixel `y_offset × width`, not at
`pkt_idx × 64`. The two agree only when `width` divides 64 (16×8 Ceiling: 4 rows = 64
px exactly ✓). For the Ceiling 13×26 (product 201, `LIFX Ceiling 13x26` [VERIFIED:
`products/registry.py:1450-1457`]): `rows_per_packet = 64 // 13 = 4` → each rect covers
52 pixels, but colours advance 64 per packet — every packet after the first is shifted
by 12·pkt_idx pixels and rows overlap. Streaming would paint garbled frames on the
exact UAT device.
**Why it happens:** the generator was written against 16×8 (the documented example in
its docstring) where the bug is invisible.
**How to avoid:** chunk row-aligned like the device layer: `rows_per_packet = 64 //
width`; `packets_per_tile = ceil(height / rows_per_packet)`; per-packet `color_count =
min(rows_per_packet, height - y_offset) × width`. For 13×26 that is 7 Set64 packets
(6×52 + 1×26 colours) + 1 CopyFB = 8 packets/frame. The 16×8 shape is unchanged
(2×64 + CopyFB), so existing tests keep passing. `packets_per_tile` (public property)
changes value only for non-divisible widths — no known external consumer besides tests.
**Warning signs:** hardware UAT shows striped/garbled output on the Ceiling while 16×8
devices look fine.

### Pitfall 2: Mocked-socket tests break because MagicMock doesn't raise BlockingIOError

**What goes wrong:** every `TestAnimatorSendFrame` test patches `socket.socket` with a
bare `MagicMock` (`test_animator.py:120-196`, plus `test_for_light_sends_single_packet`
at :283). After the change, `sweep()` calls `recvfrom_into` on the mock, which returns a
`MagicMock` instead of raising — the drain loop misbehaves (non-int `nbytes`,
never-ending loop, or TypeError).
**How to avoid:** add a conftest helper/fixture (e.g. `mock_udp_socket()` returning a
`MagicMock` with `recvfrom_into.side_effect = BlockingIOError`) and use it in all six
affected tests. This is a mechanical, enumerable change (Q6 list in Validation
Architecture).

### Pitfall 3: Emulator integration tests now gate — packet-count assertions get flaky

**What goes wrong:** the emulator acks every `ack_required` packet immediately
(fast-path, `server.py:250-265`), so on localhost acks normally return between frames
and nothing gates. But `test_animation_loop_simulation` (matrix and multizone variants)
sleeps only 0.01 s between 5 frames and asserts `total_packets >= 5`; a scheduling
hiccup could leave 2 acks outstanding and gate a frame (matrix 8×8 = 1 packet/frame →
4 < 5 → fail).
**How to avoid:** in those tests count `sent + gated` frames, or sweep-tolerant assert
(`total_packets >= 3` is masking, not fixing — prefer asserting on
`stats.gated is False` after allowing ack drain, or drive gating deterministically with
scenarios per Pitfall 4).
**Warning signs:** rare CI-only failures on the emulator integration tests.

### Pitfall 4: Testing gating with real timing instead of deterministic scenarios

**What goes wrong:** tests that rely on ack RTT races are unfalsifiable/flaky.
**How to avoid (Q6):** two deterministic levers exist:
1. **Unit level (preferred for the branch matrix):** inject crafted 36-byte ack
   datagrams / `BlockingIOError` sequences through the mocked socket's
   `recvfrom_into.side_effect`, and pass explicit `now` values to `sweep`/`track` (design
   `AckGate` methods to take `now: float` so expiry needs no sleeping).
2. **Emulator level:** per-device scenario `drop_packets: {45: 1.0}` makes the emulator
   drop ALL acks [VERIFIED: `scenarios/models.py` + `manager.py`; the
   `emulator_server_with_scenarios` fixture already exposes this,
   `tests/conftest.py:527`] — after 2 sent frames the 3rd is deterministically gated;
   expiry can then be tested by waiting just over 1 s (single sleep, deterministic
   direction). `response_delays: {45: 0.5}` also works but reintroduces timing.

### Pitfall 5: No-ack environments throttle to ~2 frames/s

**What goes wrong:** if acks never arrive (device offline mid-stream, pathological
filtering), the gate opens only via expiry: throughput degrades to
`ACK_INFLIGHT_LIMIT / ACK_EXPIRY_SECONDS = 2` frames/s.
**Why it's acceptable:** for a dead device output doesn't matter; for a congested
device throttling is precisely the intent; photons ships the same behaviour. On a LAN
nothing legitimately strips acks.
**How to avoid surprises:** document in the `send_frame` docstring and Phase 5 docs;
surface `gated`/`acks_outstanding` in `AnimatorStats` so a consumer can observe it.

### Pitfall 6: Windows `recvfrom` can raise ConnectionResetError on unconnected UDP sockets

**What goes wrong:** on Windows, an earlier `sendto` that triggered an ICMP
port-unreachable can surface as `ConnectionResetError` (WSAECONNRESET) from a later
`recvfrom` on the same socket — even unconnected. The sweep loop must not crash
`send_frame`.
**How to avoid:** in `sweep`, catch `BlockingIOError` → stop (normal empty case), and
`OSError` → stop for this sweep (next frame sweeps again). Both branches must be in the
test matrix (CI runs Windows per the cross-platform emulator note in CLAUDE.md).
**Warning signs:** Windows-only CI failures streaming to a closed emulator port.

### Pitfall 7: Validation contract regression on gated frames

**What goes wrong:** today a wrong-length `hsbk` always raises `ValueError` (via
`framebuffer.apply`). If the gate returns before `apply`, wrong-length input passes
silently whenever gated.
**How to avoid:** explicit length check at the very top of `send_frame` (edit point 3a
above); keep the message matching the existing test regex "must match pixel_count"
(`test_animator.py:117`). FrameBuffer's own raises remain covered by
`test_framebuffer.py` directly.

## Code Examples

All verified against the current codebase and spike 003's hardware-proven reference
implementation (`.claude/skills/spike-findings-lifx-async/sources/003-ack-paced-frames/stream.py`).

### AckGate facility (new `src/lifx/animation/flow.py`)

```python
# Source: spike 003 stream.py collect_acks()/arm_photons(), adapted to sync sockets
import struct

ACK_PKT_TYPE = 45          # Device.Acknowledgement [VERIFIED: protocol/packets.py:34-37]
ACK_INFLIGHT_LIMIT = 2     # gate while >= 2 probe acks outstanding (spike-measured)
ACK_EXPIRY_SECONDS = 1.0   # outstanding entries expire (spike-measured)
_MIN_HEADER = 36

class AckGate:
    """Tracks outstanding ack probes; sweeps arrived acks non-blockingly."""

    __slots__ = ("_outstanding", "_buf")

    def __init__(self) -> None:
        self._outstanding: dict[int, float] = {}
        self._buf = bytearray(64)  # ack packets are exactly 36 bytes

    @property
    def gated(self) -> bool:
        return len(self._outstanding) >= ACK_INFLIGHT_LIMIT

    def track(self, sequence: int, now: float) -> None:
        self._outstanding[sequence] = now  # wrap collision: overwrite (errs to sending)

    def sweep(self, sock: socket.socket, source: int, now: float) -> None:
        buf = self._buf
        while True:
            try:
                nbytes, _addr = sock.recvfrom_into(buf)
            except BlockingIOError:
                break            # no more datagrams — the normal exit
            except OSError:
                break            # e.g. Windows WSAECONNRESET after ICMP unreachable
            if nbytes < _MIN_HEADER:
                continue         # runt datagram — ignore
            if buf[32] | (buf[33] << 8) != ACK_PKT_TYPE:
                continue         # not an Acknowledgement
            if struct.unpack_from("<I", buf, 4)[0] != source:
                continue         # another client's traffic
            self._outstanding.pop(buf[23], None)
        # prune expired probes (frees gate slots; zero retransmits by design)
        expired = [s for s, t in self._outstanding.items() if now - t > ACK_EXPIRY_SECONDS]
        for seq in expired:
            del self._outstanding[seq]

    def reset(self) -> None:
        self._outstanding.clear()
```

### send_frame gating (edit to `animator.py:311-359`)

```python
# Gate check BEFORE framebuffer work; probe flag was baked at __init__.
def send_frame(self, hsbk: list[tuple[int, int, int, int]]) -> AnimatorStats:
    start_time = time.perf_counter()
    if len(hsbk) != self._framebuffer.canvas_size:
        raise ValueError(
            f"HSBK length ({len(hsbk)}) must match pixel_count "
            f"({self._framebuffer.canvas_size})"
        )
    if self._socket is None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setblocking(False)

    now = time.monotonic()
    self._ack_gate.sweep(self._socket, self._source, now)
    if self._ack_gate.gated:
        return AnimatorStats(
            packets_sent=0,
            total_time_ms=(time.perf_counter() - start_time) * 1000,
            gated=True,
            acks_outstanding=len(self._ack_gate._outstanding),  # or expose a count property
        )

    device_data = self._framebuffer.apply(hsbk)
    self._packet_generator.update_colors(self._templates, device_data)
    for i, tmpl in enumerate(self._templates):
        tmpl.data[SEQUENCE_OFFSET] = self._sequence
        if i == self._probe_index:
            self._ack_gate.track(self._sequence, now)
        self._sequence = (self._sequence + 1) % 256
        self._socket.sendto(tmpl.data, self._addr)
    ...
```

(Prefer an `outstanding_count` property on `AckGate` over touching `_outstanding` from
the animator — pyright strict + cleanliness.)

### Row-aligned large-tile chunking (fix in `MatrixPacketGenerator`)

```python
# Mirrors devices/matrix.py set_matrix_colors (hardware-proven):
# rows_per_packet rows per Set64, colours sliced to the same rows the rect covers.
self._rows_per_packet = self._MAX_COLORS_PER_PACKET // tile_width       # e.g. 64//13 = 4
self._packets_per_tile = -(-tile_height // self._rows_per_packet)       # ceil; 13×26 → 7

# per packet, in _create_large_tile_templates:
y_offset = pkt_idx * self._rows_per_packet
rows = min(self._rows_per_packet, tile_height - y_offset)
color_count = rows * tile_width                                          # 52, …, 26
color_start = y_offset * tile_width                                      # row-aligned
```

### probe_template_index (add to `packets.py` generators)

```python
class PacketGenerator(ABC):
    @property
    def probe_template_index(self) -> int:
        """Template index that carries the ack_required flow-control probe."""
        return 0  # first packet of the frame (spike-measured arm)

class MatrixPacketGenerator(PacketGenerator):
    @property
    def probe_template_index(self) -> int:
        if self._is_large_tile:
            # Final CopyFrameBuffer — the frame-commit packet (Glowup-style; D4-04)
            return self._tile_count * (self._packets_per_tile + 1) - 1
        return 0
```

### Deterministic emulator gating test (scenario lever)

```python
# Source: tests/conftest.py emulator_server_with_scenarios + emulator scenarios/models.py
_, _ = await emulator_server_with_scenarios(
    device_type="tile", serial="d073d5000007",
    scenarios={"drop_packets": {45: 1.0}},   # emulator drops ALL acks
)
# frames 1 and 2 send (outstanding 1 → 2); frame 3 is deterministically gated
assert animator.send_frame(frame).gated is False
assert animator.send_frame(frame).gated is False
assert animator.send_frame(frame).gated is True
```

## Flow-Control Constants (Q3 answer)

**Location:** `src/lifx/animation/flow.py` (module-level `Final`s), NOT `src/lifx/const.py`
— D4-05 scopes this phase to `src/lifx/animation/` only, and these are animation-layer
tuning values, not shared network configuration. Header offsets live in
`animation/packets.py` beside the existing `SEQUENCE_OFFSET`.

| Constant | Value | Module | Provenance |
|----------|-------|--------|-----------|
| `ACK_INFLIGHT_LIMIT` | `2` | `flow.py` | Spike 003 `PHOTONS_INFLIGHT_LIMIT` [VERIFIED: measured 0.0% query loss] |
| `ACK_EXPIRY_SECONDS` | `1.0` | `flow.py` | Spike 003 `PHOTONS_ACK_EXPIRY` [VERIFIED] |
| `ACK_PKT_TYPE` | `45` | `flow.py` | `Device.Acknowledgement.PKT_TYPE` [VERIFIED: `protocol/packets.py:34-37`] |
| `FLAGS_OFFSET` | `22` | `packets.py` | Header layout [VERIFIED: `_build_header` + spike stream.py] |
| `ACK_REQUIRED_FLAG` | `0x02` | `packets.py` | Bit 1 of flags byte [VERIFIED: `_build_header` flags packing] |

## Device-Family Applicability (Q5 answer)

**Apply flow control uniformly to all three animator families.** Rationale:

- `ack_required` is a Frame Address header flag honoured for **every** set packet —
  `Light.SetColor` (102), `SetExtendedColorZones` (510), `Tile.Set64` (715),
  `Tile.CopyFrameBuffer` (716). The connection layer already relies on acks for set
  packets (`_requires_ack` metadata), and the emulator acks all handled types
  [VERIFIED: emulator `server.py` fast-path ack + generator comment "SET requests:
  ack_required=True"]. Set64's lack of a *response* packet is irrelevant — the ack is a
  separate header-level mechanism.
- One code path (`probe_template_index` default 0) means zero per-family branching in
  the hot path and no capability matrix to maintain — matching D4-02's "the layer that
  sends frames decides" and ROADMAP criterion 1, which has no family carve-outs.
- For 1-packet frames (Light, ≤82-zone multizone) the gate is naturally slack: at
  20 FPS with sub-100 ms ack RTTs, outstanding rarely reaches 2; it engages exactly
  when the device congests, which is the desired behaviour. The limit-2/1 s tuning was
  measured on Tiles [VERIFIED] and is conservative for lighter frames [ASSUMED —
  low-risk; ANIM-03/04 UATs cover matrix; multizone/light behaviour follows the same
  protocol mechanics].

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Blind fire ("No ACKs, no waiting") | Photons-style ack-gated probe (`NoisyNetworkCannon` pattern) | This phase (spike 003, 2026-07) | 14.6% → 0.0% concurrent-query loss at 20 FPS |
| Glowup ack-every-frame serialisation | Rejected — probe never gates the current frame | Spike 003 | Ack-every-frame skipped 33% of frames, visibly choppiest |
| Spike's external private-reaching `FrameStreamer` | Proper internal `AckGate` facility + `probe_template_index` seam | This phase | D4-03: no reaching into `_templates`/`_framebuffer` from outside |

**Deprecated/outdated:** none removed; `UdpTransport.receive_many` deprecation is
unrelated and untouched (scope D4-05).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Ceiling 13×26 acks the CopyFrameBuffer probe with RTTs compatible with limit-2/1 s tuning under 20 FPS | Pattern 2 | Gating too tight/loose on the large path — ANIM-04 hardware UAT detects; one-line fallback to probe index 0 |
| A2 | The Ceiling 13×26 device chain reports a single tile of width 13 (not 26-wide landscape) | Pitfall 1 | Row-aligned fix is orientation-agnostic (correct for any width), so only the packet-count arithmetic in tests changes (26-wide → rows_per_packet=2, 7 packets — same count); verify from `get_device_chain()` during UAT |
| A3 | Limit-2/1 s tuning transfers acceptably to multizone/light single-packet frames | Device-Family Applicability | Worst case: unnecessary gating on those families — observable via `AnimatorStats.gated`; retune per family later |
| A4 | Windows `ConnectionResetError` on unconnected-UDP `recvfrom` is the only extra OSError family the sweep must survive | Pitfall 6 | Broad `except OSError: break` already covers unknown variants safely |

## Open Questions (RESOLVED)

1. **Exact probe RTT behaviour on Ceiling 13×26 under load** — what we know: Tiles
   RTTs (~98/150 ms) and Glowup's field practice; what's unclear: whether the CopyFB
   ack on this firmware lands in the same band; recommendation: this IS the ANIM-04
   hardware UAT — record measured RTTs in the verification evidence, keep
   `probe_template_index` as the adjustment seam.
2. **Whether `AnimatorStats.acks_outstanding` should be public** — it aids UAT
   harnesses and LedFx observability but grows the public dataclass; recommendation:
   include it (defaulted, additive, cheap) — matches ROADMAP criterion 1's
   observability needs.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv + Python 3.10–3.14 | build/test | ✓ | project venv is 3.14 | — |
| pytest/pytest-asyncio/pytest-cov | automated tests | ✓ | 8.4.2+/0.24+/7.0+ | — |
| lifx-emulator-core (embedded) | integration tests, incl. ack scenarios and 13×26 tile emulation (`create_tile_device(tile_width=13, tile_height=26)` or `create_device(201, ...)`) | ✓ | 3.6.3 | tests marked `@pytest.mark.emulator` auto-skip |
| Tiles hardware (192.168.19.243 / .18.62) | ANIM-03 UAT | manual — LAN access required | — | none (UAT is mandatory per CONTEXT.md) |
| Ceiling Capsule (192.168.19.231, product 201) | ANIM-04 UAT | manual — LAN access; **power on first (`set_power`) or animation is invisible** | — | none |

**Missing dependencies with no fallback:** none for automated work; the two hardware
UATs require Avi at the network with the devices (already planned as manual gates).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥8.4.2 + pytest-asyncio ≥0.24 (`asyncio_mode = "auto"`), pytest-cov ≥7.0 with `--cov-branch` in addopts |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (markers include `emulator`) |
| Quick run command | `uv run pytest tests/test_animation/ -x -q` |
| Full suite command | `uv run --frozen pytest` |

### Phase Requirements → Test Map

| Req ID | Behaviour | Test Type | Automated Command | File Exists? |
|--------|-----------|-----------|-------------------|-------------|
| ANIM-01 | AckGate sweep/track/expiry/gated branch matrix; gated frame returns `gated=True`, sends nothing, skips framebuffer work; seq-wrap overwrite | unit | `uv run pytest tests/test_animation/test_flow.py tests/test_animation/test_animator.py -x` | ❌ Wave 0 (`test_flow.py`); `test_animator.py` exists, needs new tests + mock-socket fixes |
| ANIM-01 | Deterministic gating end-to-end (emulator drops all acks via scenario `{45: 1.0}`; expiry reopens gate) | integration (emulator) | `uv run pytest tests/test_animation/test_animator.py -m emulator -x` | ❌ Wave 0 (new test class) |
| ANIM-02 | Probe flag baked once on `probe_template_index` (standard→0, large→last CopyFB, multizone/light→0); other templates' flags byte stays 0; templates unchanged otherwise; `AnimatorStats` additive fields | unit | `uv run pytest tests/test_animation/test_packets.py tests/test_animation/test_animator.py -x` | files exist; new tests Wave 0 |
| ANIM-02 | Type/lint gates | static | `uv run pyright && uv run ruff check .` | ✅ |
| ANIM-04 | Row-aligned 13×26 templates (7 Set64: 52×6+26 colours, y offsets 0,4,…,24, fb_index=1, hsbk_start row-aligned; + CopyFB); 16×8 shape unchanged | unit | `uv run pytest tests/test_animation/test_packets.py -x` | exists; new tests Wave 0 |
| ANIM-04 | Large-tile streaming against an emulated 13×26 device (product 201), probe on CopyFB acked, gating engages under ack-drop scenario | integration (emulator) | `uv run pytest tests/test_animation/ -m emulator -x` | ❌ Wave 0 (new fixture: 13×26 emulated tile device) |
| ANIM-03 | 0% concurrent-query loss + ≥85% delivered frames + operator visual verdict on Tiles at 20 FPS | **manual-only UAT** — emulator cannot model real ack RTT under load (CONTEXT.md constraint); requires Avi watching | UAT harness modelled on spike `stream.py` (photons arm + query prober) | ❌ Wave/UAT plan |
| ANIM-04 | Same flow control on Ceiling Capsule 192.168.19.231; probe-attachment decision recorded + validated; power-on before visual runs | **manual-only UAT** — hardware-specific RTT and visual verdict | UAT harness (same script, ceiling host) | ❌ Wave/UAT plan |

### Existing tests that change (enumerated)

1. `test_animator.py::TestAnimatorSendFrame` — `test_send_frame_sends_packets`,
   `test_send_frame_returns_stats`, `test_send_frame_reuses_socket`,
   `test_send_frame_sends_to_correct_address`, `test_close_closes_socket` — mocked
   socket needs `recvfrom_into.side_effect = BlockingIOError` (shared fixture).
2. `test_animator.py::TestAnimatorForLightFactory::test_for_light_sends_single_packet`
   — same mock fix; also the single template now carries the ack flag (assertion on
   flags byte if added).
3. `test_animator.py` emulator loop tests (`test_animation_loop_simulation` ×2,
   `test_send_frame_sends_packets` integration) — must tolerate/observe gating
   (Pitfall 3): assert on sent+gated totals or drain acks between frames.
4. `test_packets.py` large-tile tests (16×8) — remain green under the row-aligned fix
   (64 divisible by 16); extend, don't modify.
5. No test currently asserts "no receive path"/"no waiting" textually — the sync
   contract test (`test_send_frame_is_synchronous`) stays valid by design.

### Branch matrix for 100% branch patch coverage (new code)

- `AckGate.sweep`: empty-socket first pass; ack matching outstanding (popped); unknown
  seq; runt datagram (<36 B); wrong pkt_type; wrong source; `OSError` break; expiry
  prunes ≥1 entry; nothing expired.
- `AckGate.gated`: below limit / at limit.
- `AckGate.track`: fresh seq; wrap-collision overwrite.
- `send_frame`: length mismatch raise; first-call socket creation; gated early return
  (framebuffer.apply NOT called — assert via spy); non-gated send with probe tracked at
  correct sequence; probe template flag set, others clear.
- `probe_template_index`: standard matrix / large matrix / multizone / light.
- `MatrixPacketGenerator` large-tile: divisible width (16×8), non-divisible width
  (13×26), final partial-row batch.
- `close()`/`reset()`: outstanding cleared.

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_animation/ -x -q`
- **Per wave merge:** `uv run --frozen pytest` (coverage runs with `--cov-branch` via addopts; CI enforces 100% **branch** patch coverage — check branch partials, not just lines)
- **Phase gate:** full suite green + `uv run pyright` + `uv run ruff check .` before `/gsd-verify-work`; hardware UATs (ANIM-03/04) are explicit human gates

### Wave 0 Gaps

- [ ] `tests/test_animation/test_flow.py` — AckGate unit branch matrix (ANIM-01)
- [ ] Shared `mock_udp_socket` fixture in `tests/test_animation/conftest.py` — unblocks all mocked-socket tests
- [ ] Emulator fixture for a 13×26 large-tile device (product 201 via `create_tile_device(tile_width=13, tile_height=26)`) (ANIM-04)
- [ ] Emulator gating test class using `emulator_server_with_scenarios` with `drop_packets: {45: 1.0}` (ANIM-01)
- [ ] UAT harness script (photons arm + concurrent query prober, adapted from spike `stream.py`) for ANIM-03/04 manual gates

## Security Domain

Internal library phase; no auth/session/crypto surface. Relevant category:

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | The ack sweep parses **untrusted UDP datagrams**: validate `nbytes >= 36` before any offset read; fixed-offset peeks only (no length-prefixed parsing); match source ID before acting — mirrors the discovery layer's source-validation DoS posture |
| V2/V3/V4/V6 | no | No auth, sessions, access control, or cryptography in scope |

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Spoofed/garbage datagrams to the animator's ephemeral port | Tampering/DoS | Source-ID + pkt_type + outstanding-seq triple match; runt-datagram discard; sweep is O(queued datagrams) per frame with a bounded kernel recv buffer |
| Ack flood attempting to unlatch the gate | DoS (of the pacing) | Worst case equals today's blind-fire baseline (gate never closes) — no new failure mode below the current shipped behaviour |

## Project Constraints (from CLAUDE.md)

- uv exclusively (`uv run pytest`, `uv run pyright`, `uv run ruff`); never pip/poetry.
- All imports at top of file; Australian English in prose/docs.
- Zero runtime dependencies — this phase adds none.
- Strict pyright + ruff clean; 100% **branch** patch coverage in CI (check branch partials).
- Never manually edit generated files (`src/lifx/protocol/*` generated code — untouched here; `animation/packets.py` is hand-written and editable).
- Failing tests must be fixed, not skipped; uncommitted files must be handled.
- Commits: `git commit -s`, GPG-signed (automatic).
- Emulator-marked tests auto-skip when unavailable; `LIFX_EMULATOR_EXTERNAL=1` for hardware.

## Sources

### Primary (HIGH confidence)
- Codebase: `src/lifx/animation/animator.py`, `packets.py`, `framebuffer.py`; `src/lifx/network/transport.py`; `src/lifx/protocol/packets.py` (Acknowledgement=45); `src/lifx/devices/matrix.py` (row-aligned batching); `src/lifx/products/registry.py` (product 201); `tests/test_animation/*`; `tests/conftest.py`; `pyproject.toml`
- Spike 003 (hardware-measured): `.claude/skills/spike-findings-lifx-async/references/animation-flow-control.md` + `sources/003-ack-paced-frames/stream.py`
- lifx-emulator-core 3.6.3 installed source (`server.py`, `devices/device.py`, `scenarios/models.py`, `handlers/tile_handlers.py`, `factories/factory.py`)
- Phase inputs: `04-CONTEXT.md`, `ROADMAP.md` Phase 4

### Secondary (MEDIUM confidence)
- Glowup field behaviour on >64-zone ceilings (acks the CopyFrameBuffer swap) — as cited in CONTEXT.md D4-04

### Tertiary (LOW confidence)
- Windows WSAECONNRESET-on-unconnected-UDP-recvfrom quirk [ASSUMED — training knowledge; mitigated by broad `OSError` handling either way]

## Metadata

**Confidence breakdown:**
- Recommended design (sync sweep): HIGH — mechanism proven by spike 003 on hardware; socket behaviour verified in code
- Large-tile probe attachment: HIGH for template structure (read from code); MEDIUM for the CopyFB choice pending ANIM-04 hardware validation (adjustment seam provided)
- 13-wide chunking bug: HIGH — arithmetic verified against both the generator and the device layer's correct implementation
- Test strategy / emulator capabilities: HIGH — emulator ack fast-path and scenario levers read from installed source
- Tuning transfer to multizone/light: MEDIUM — same protocol mechanics, not separately measured

**Research date:** 2026-07-17
**Valid until:** 2026-08-17 (stable internal codebase domain; revalidate if lifx-emulator-core major-bumps)
