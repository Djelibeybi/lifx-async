# Phase 4: Animation Flow Control - Pattern Map

**Mapped:** 2026-07-17
**Files analyzed:** src/lifx/animation/animator.py, packets.py, framebuffer.py, orientation.py
(all modified in place) + new ack-gate/tuning constants
**Analogs found:** 5 strong precedents in Phase 2/3 network code, no analog exists yet for
an async-receive-capable animator (flagged as No Analog Found)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|---------------|
| `src/lifx/const.py` (new `ANIMATION_ACK_*` tuning constants) | config | event-driven (schedule) | `src/lifx/const.py:36-65` (`DISCOVERY_REBROADCAST_GAPS`, `REQUEST_RETRANSMIT_GAPS`) | exact |
| `src/lifx/animation/animator.py` (`send_frame` → ack-gated dispatch) | service (hot loop) | streaming | `src/lifx/network/connection.py:428-665` (`_transmit_and_listen`) for the schedule/deadline shape; `animator.py:311-359` itself for the zero-alloc constraint to preserve | role-match (need async variant) |
| `src/lifx/animation/animator.py` (new ack-receive path) | event-driven consumer | request-response probe | `src/lifx/network/transport.py:26-73` (`_UdpProtocol` + `asyncio.Queue`) | exact (reusable facility) |
| `src/lifx/animation/packets.py` (ack-flag flip on probe packet) | utility (byte mutation) | transform | `src/lifx/animation/packets.py:42-115` (`_build_header`, `SEQUENCE_OFFSET`) — extend, don't replace | exact |
| `src/lifx/animation/framebuffer.py` / `orientation.py` | utility | transform | unchanged — cited only as "must not regress" | n/a |
| `tests/test_animation/test_animator.py` (new ack-gating tests) | test | request-response | `tests/test_animation/test_animator.py:120-200` (socket mocking) + `tests/test_network/test_connection.py:426-479` (ack-stream mocking idiom) | role-match |

## Pattern Assignments

### `src/lifx/const.py` — new tuning constants

**Analog:** `src/lifx/const.py:36-65`

Both existing schedules are `Final[tuple[float, ...]]` module constants, read at
*runtime* (not captured as def-time defaults) so tests can monkeypatch them for fast
schedule-exhaustion coverage. Mirror this exactly for the ack-gate tuning:

```python
# lines 36-39
# Photons-shaped gaps in seconds between successive discovery re-broadcasts
# after the first send (cumulative offsets 0.6, 1.8, 3.6, 5.6, 7.6), capped
# by DISCOVERY_TIMEOUT.
DISCOVERY_REBROADCAST_GAPS: Final[tuple[float, ...]] = (0.6, 1.2, 1.8, 2.0, 2.0)
```

```python
# lines 48-65
# Photons-shaped gaps in seconds between successive request transmissions; ...
REQUEST_RETRANSMIT_GAPS: Final[tuple[float, ...]] = (0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1.0, 2.0, 3.0, 4.0, 5.0)
```

New constants should follow the same doc-comment-with-rationale style, e.g.
`ANIMATION_ACK_EXPIRY_S: Final[float] = 1.0` (D4-01's "~1 s" outstanding-probe
expiry) and `ANIMATION_MAX_OUTSTANDING_ACKS: Final[int] = 2` (the gate threshold).
Consumers must read these as `lifx.const.ANIMATION_ACK_EXPIRY_S` (module attribute
lookup), never bind them as function defaults, so tests can patch fast schedules —
same rule called out explicitly at `connection.py:514-516` and `discovery.py:249-253`.

---

### `src/lifx/animation/animator.py` — ack-gated `send_frame`

**Analog (schedule/deadline shape):** `src/lifx/network/connection.py:428-665`
`_transmit_and_listen`

Do NOT port the retry/retransmit machinery itself (D4-05 excludes `connection.py`
changes and animation acks are explicitly NOT retried — latest-frame-wins is the
recovery mechanism, not retransmission). Port only the *shape* of:
- correlation keying by `(source, sequence)` — reuse `SEQUENCE_OFFSET` already in
  `animator.py:36,350`
- an outstanding-count / expiry structure instead of a queue-per-request; expire
  entries older than `ANIMATION_ACK_EXPIRY_S` (`connection.py:520-523` shows the
  `time.monotonic()` deadline-capture idiom to copy: capture `start = time.monotonic()`
  once, compare against it, never blind-sleep).

**Analog (constraint to preserve):** `src/lifx/animation/animator.py:311-359`
`send_frame` itself — the current zero-allocation hot path:

```python
# lines 335-359 (current, must survive unmodified when gate is closed)
start_time = time.perf_counter()
device_data = self._framebuffer.apply(hsbk)
self._packet_generator.update_colors(self._templates, device_data)
if self._socket is None:
    self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self._socket.setblocking(False)
for tmpl in self._templates:
    tmpl.data[SEQUENCE_OFFSET] = self._sequence
    self._sequence = (self._sequence + 1) % 256
    self._socket.sendto(tmpl.data, self._addr)
```

The ack-gate decision (send vs drop-as-gated) must happen *before* this block, as a
cheap counter/dict check — no new allocation on the hot path when the gate is open.
`AnimatorStats` (lines 53-64) is the natural place to add a `gated: bool` /
`outstanding_acks: int` field so callers can observe drops (`dataclass(frozen=True)`
pattern already established).

---

### `src/lifx/animation/animator.py` — new async ack-receive facility

**Analog:** `src/lifx/network/transport.py:26-73`

```python
# lines 26-52
class _UdpProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple[bytes, tuple[str, int]]] = asyncio.Queue(...)

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        ...

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            self.queue.put_nowait((data, addr))
        except asyncio.QueueFull:
            ...

    def error_received(self, exc: Exception) -> None: ...
    def connection_lost(self, exc: Exception | None) -> None: ...
```

`UdpTransport.open()` (`transport.py:108-142`) wires this via
`loop.create_datagram_endpoint(lambda: protocol, ...)`. **No `loop.add_reader`
pattern exists anywhere in the codebase** — the project's sole async-receive idiom
is `asyncio.DatagramProtocol` + queue via `create_datagram_endpoint`. The animator
currently uses a raw blocking-disabled `socket.socket` with `sendto()` only (no
receive path at all — CLAUDE.md/spike note: "No ACKs, no waiting"). For D4-03, the
cleanest fit is to give `Animator` an *additional* `UdpTransport`-backed receive
side (reusing `_UdpProtocol`/`create_datagram_endpoint`) rather than inventing a new
reader mechanism, while keeping the existing raw socket for the zero-alloc send
path untouched. This is a genuine new integration point — flagged below under "No
Analog Found" for the specific wiring, but the receive *primitive* to reuse is
`transport.py:26-142`.

---

### `src/lifx/animation/packets.py` — probe-packet ack flag

**Analog:** `src/lifx/animation/packets.py:42-115` (`_build_header`) and
`src/lifx/protocol/header.py:138-141`

```python
# packets.py:42-52 (module-level header constants)
HEADER_SIZE = 36
SEQUENCE_OFFSET = 23  # Offset of sequence byte in header
...
ACK_REQUIRED = 0
RES_REQUIRED = 0
```

```python
# packets.py:106-110 (flags byte construction — this is FLAGS_OFFSET=22)
target_padded = target + b"\x00\x00" if len(target) == 6 else target
flags = (RES_REQUIRED & 0b1) | ((ACK_REQUIRED & 0b1) << 1)
struct.pack_into("<8s6sBB", header, 8, target_padded, b"\x00" * 6, flags, 0)
```

Confirms CONTEXT.md's D4-03 byte offsets: the Frame Address block starts at
absolute offset 8; `struct.pack_into("<8s6sBB", header, 8, ...)` packs
`8s`(target)+`6s`(reserved)+`B`(flags)+`B`(sequence) starting at 8, so flags land
at absolute offset **8+8+6=22** (bit 1 = ack_required, matches
`protocol/header.py:141`) and sequence at absolute offset **23**
(`SEQUENCE_OFFSET`, already exported). For the "ack_required probe on ONE packet
per frame" (D4-01), mutate `tmpl.data[22]` in place on the chosen template — same
zero-allocation idiom as the existing `tmpl.data[SEQUENCE_OFFSET] = self._sequence`
line in `animator.py:350`. Do not rebuild the header; flip the bit in the
prebaked bytearray.

**D4-04 probe-attachment analog:** `MatrixPacketGenerator._create_large_tile_templates`
(`packets.py:298-384`) already distinguishes Set64 templates (`color_count > 0`)
from the trailing `CopyFrameBuffer` template (`color_count=0`, appended last per
tile at lines 373-382). The gate/probe logic can use this existing
`color_count == 0` discriminator (`update_colors` already skips these at
`packets.py:403-405`) to identify which template in a large-tile frame is the
CopyFrameBuffer swap, for whichever probe-attachment point hardware validation
settles on (Set64 vs CopyFrameBuffer per D4-04).

---

### `tests/test_animation/test_animator.py` — ack-gating tests

**Analog (socket mocking):** `tests/test_animation/test_animator.py:120-200`

```python
with patch.object(socket, "socket") as mock_socket_class:
    mock_sock = MagicMock()
    mock_socket_class.return_value = mock_sock
    stats = animator.send_frame(hsbk)
    ...
```

**Analog (ack-stream mocking idiom):** `tests/test_network/test_connection.py:426-452`
`test_set_packet_acknowledgement` — mocks an async-generator ack source
(`_request_ack_stream_impl`) yielding `True`/timing out, and asserts on the
consumer's behaviour. Mirror this for a mocked `_UdpProtocol`-style ack receiver
feeding synthetic Acknowledgement (pkt_type 45) datagrams into the animator's
outstanding-ack tracker, to test gating/expiry without a real socket.

**Emulator usage:** `tests/test_animation/test_animator.py:326-524` — existing
`@pytest.mark.emulator` classes (`TestAnimatorMatrixIntegration`,
`TestAnimatorMultiZoneIntegration`) use the `emulator_devices` fixture and call
`Animator.for_matrix`/`for_multizone` then `send_frame` directly. New ANIM-01/02
tests should extend these classes rather than create new fixtures — CONTEXT.md
notes the emulator can validate packet construction/flag placement/gating logic
but cannot model real ack RTT (hardware UAT required separately for ANIM-03/04,
out of scope for automated tests).

## Shared Patterns

### Runtime-read tuning constants (not def-time defaults)
**Source:** `src/lifx/const.py:36-65`, consumed via module-attribute read at
`connection.py:517-518` (`iter(REQUEST_RETRANSMIT_GAPS)`) and
`discovery.py:253` (`accumulate(DISCOVERY_REBROADCAST_GAPS)`)
**Apply to:** any new `ANIMATION_ACK_*` constants in `const.py` — read as
`lifx.const.X` at call time inside `animator.py`, never bound as a function
default, so tests can monkeypatch fast schedules.

### Single monotonic deadline, no blind sleep
**Source:** `connection.py:520-523,600-614` — `start = time.monotonic()`,
`deadline = start + timeout`, every wait folded into one
`asyncio.wait_for(queue.get(), timeout=wait)`
**Apply to:** the ack-gate's outstanding-probe expiry (~1s) and any wait the
async ack-receive path performs.

### Zero-allocation in-place bytearray mutation
**Source:** `animator.py:350` (`tmpl.data[SEQUENCE_OFFSET] = self._sequence`),
`packets.py:106-110` (`flags` bit-packing)
**Apply to:** the new ack_required flag flip per probe packet — mutate
`tmpl.data[22]` directly, no header rebuild, no new `PacketTemplate` allocation.

### `asyncio.DatagramProtocol` + bounded `asyncio.Queue` for async receive
**Source:** `transport.py:26-73` (`_UdpProtocol`), wired via
`create_datagram_endpoint` at `transport.py:108-142`
**Apply to:** the animator's new ack-receive capability — this is the only
async-receive primitive in the codebase; there is no `loop.add_reader` usage
anywhere to reuse instead.

## No Analog Found

| File/Piece | Role | Data Flow | Reason |
|------------|------|-----------|--------|
| Animator's dual send-path (raw blocking-disabled `socket` for hot-path sends + async `UdpTransport`-style receive for probe acks, coexisting in one object) | service | mixed sync-hot-path + async-event | No existing class combines a synchronous zero-alloc UDP sender with an async ack-listener; `DeviceConnection` is fully async (both send and receive), `Animator` is fully sync (send only, "no ACKs, no waiting" by design). This phase must design the seam from scratch — closest partial precedents cited above (transport.py for receive, connection.py for schedule/deadline shape, animator.py/packets.py for what must not regress). |
| Outstanding-ack gate data structure (count + per-probe expiry, "≥2 outstanding" threshold, latest-frame-wins drop) | utility (state) | event-driven | `connection.py`'s correlation tracking (`_pending_requests`, `correlation_keys`) is per-request-lifecycle and torn down in a `finally` block; the animator's gate is a persistent per-Animator-instance structure spanning many frames. No existing persistent-counter-with-expiry structure in the codebase to copy directly — implement fresh, informed by the deadline/expiry idiom above. |

## Metadata

**Analog search scope:** `src/lifx/animation/`, `src/lifx/network/` (connection.py,
transport.py, discovery.py, message.py), `src/lifx/const.py`, `src/lifx/protocol/header.py`,
`tests/test_animation/`, `tests/test_network/test_connection.py`
**Files scanned:** const.py, animator.py, packets.py, framebuffer.py, orientation.py,
connection.py, transport.py, discovery.py, message.py, header.py, test_animator.py,
test_connection.py
**Pattern extraction date:** 2026-07-17
</content>
