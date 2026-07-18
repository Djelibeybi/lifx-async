"""Internal ack-gated flow control for the Animation layer (ANIM-01/ANIM-02).

This module is a private animator facility -- it is never exported from
`lifx.animation.__init__` (D4-02: no downstream-facing toggle). Consumers
call `Animator.send_frame()` exactly as before; the gating decisions made
here are entirely internal.

`AckGate` implements the photons-style ack-gated pacing measured in spike
003: one `ack_required` probe per frame, new frames gated while two or more
probe acks are outstanding, outstanding entries expire after roughly one
second, and gated frames are dropped rather than queued (latest-frame-wins).
Spike 003 measured this design at 0.0% concurrent-query loss on Tiles under
20 FPS streaming, versus 14.6% for blind fire, while remaining the visually
smoothest arm (D4-01).

Latest-frame-wins recovery model: a gated frame is never retried or queued.
The caller simply calls `send_frame()` again on its own cadence; the next
frame either sends (if the gate has reopened) or is dropped again. There is
no retransmission of probes and no backlog to drain -- congestion is shed by
dropping stale frames, not by delaying delivery of fresh ones.

Wrap-collision overwrite semantics: sequence numbers are a single uint8
(0-255) counter shared by the whole frame, so `track()` may be called with a
sequence that is already present in `_outstanding` if the counter wraps
while an old probe is still outstanding (see `track()` docstring for the
detailed analysis). The dict write simply overwrites the stale entry. This
errs towards *sending* -- the older, now-forgotten probe's eventual ack (or
expiry) frees a slot early -- never towards permanently stalling. This is
self-healing and considered acceptable (D4-01); no additional bookkeeping is
warranted.

No-ack degradation floor: if acks never arrive at all (device disconnected
mid-stream, pathological network filtering), the gate only reopens via
expiry. Throughput therefore degrades to a floor of
`ACK_INFLIGHT_LIMIT / ACK_EXPIRY_SECONDS` = 2 frames/s. This is intended
throttling, not a bug -- for a dead device the output doesn't matter, and
for a congested device this is exactly the desired behaviour (research
Pitfall 5).
"""

from __future__ import annotations

import socket
import struct
from typing import Final

# Device.Acknowledgement packet type [VERIFIED: protocol/packets.py].
ACK_PKT_TYPE: Final[int] = 45

# Gate new frames while this many probe acks are outstanding. Spike-003
# measured on Tiles under 20 FPS load: this value eliminated concurrent-query
# loss entirely (0.0%) while remaining the visually smoothest arm (D4-01).
ACK_INFLIGHT_LIMIT: Final[int] = 2

# Outstanding probes older than this many seconds are pruned, freeing a gate
# slot even if no ack ever arrives (zero retransmits by design). Spike-003
# measured on Tiles under 20 FPS load: ack RTT ~98 ms median / ~150 ms p95
# (D4-01).
ACK_EXPIRY_SECONDS: Final[float] = 1.0

# Acknowledgement datagrams are always exactly 36 bytes (header only, no
# payload); anything shorter cannot be a genuine ack.
_MIN_ACK_SIZE: Final[int] = 36


class AckGate:
    """Tracks outstanding ack probes and sweeps arrived acks non-blockingly.

    One `AckGate` instance belongs to a single `Animator`. It holds a
    preallocated receive buffer and a plain `dict[int, float]` mapping each
    outstanding probe's sequence number to the monotonic time it was sent --
    no per-datagram allocation occurs anywhere in `sweep()`.

    See the module docstring for the latest-frame-wins recovery model, the
    wrap-collision overwrite semantics, and the no-ack degradation floor.
    """

    __slots__ = ("_outstanding", "_buf")

    def __init__(self) -> None:
        """Initialise an empty, open gate."""
        self._outstanding: dict[int, float] = {}
        # Ack packets are exactly 36 bytes; oversize the buffer slightly so
        # `recvfrom_into` never truncates a genuine ack.
        self._buf = bytearray(64)

    @property
    def gated(self) -> bool:
        """Whether a new frame must be dropped (>= ACK_INFLIGHT_LIMIT outstanding)."""
        return len(self._outstanding) >= ACK_INFLIGHT_LIMIT

    @property
    def outstanding_count(self) -> int:
        """Number of probe acks currently outstanding."""
        return len(self._outstanding)

    def track(self, sequence: int, now: float) -> None:
        """Record a newly sent probe awaiting its ack.

        Args:
            sequence: The uint8 sequence number stamped on the probe packet.
            now: The monotonic time the probe was sent.

        A sequence-number collision (the uint8 counter wrapped back to a
        value that is still outstanding) simply overwrites the stale entry.
        This errs towards sending, never towards stalling: the collision can
        only happen if the previous probe hasn't been acked or expired yet,
        so overwriting frees what would otherwise be a permanently stuck
        slot the moment either the new probe's ack arrives or it expires --
        self-healing, no extra mechanism required (see module docstring).
        """
        self._outstanding[sequence] = now

    def sweep(self, sock: socket.socket, source: int, now: float) -> None:
        """Drain arrived acks from `sock` and prune expired probes.

        Args:
            sock: The animator's own non-blocking UDP socket (the only
                socket that can physically receive the device's replies,
                since LIFX devices ack to the probe packet's source port).
            source: This client's protocol source ID -- acks from any other
                source are untrusted traffic and are ignored.
            now: The current monotonic time, used both to timestamp nothing
                (sweep does not track) and to prune expired entries.

        Datagrams are read into a single preallocated buffer and inspected
        via fixed-offset peeks only (`struct.unpack_from`/indexing) -- no
        `parse_message`, no object allocation, mirroring the discovery
        layer's untrusted-input posture (V5): length is validated before any
        offset is read, and pkt_type + source + tracked-sequence must all
        match before any state changes.
        """
        buf = self._buf
        while True:
            try:
                nbytes, _addr = sock.recvfrom_into(buf)
            except BlockingIOError:
                break  # No more datagrams queued -- the normal empty exit.
            except OSError:
                # E.g. Windows WSAECONNRESET surfacing on a later recvfrom_into
                # after an earlier sendto triggered an ICMP port-unreachable.
                # Stop this sweep; the next frame's sweep tries again.
                break

            if nbytes < _MIN_ACK_SIZE:
                continue  # Runt datagram -- cannot be a genuine ack.
            if buf[32] | (buf[33] << 8) != ACK_PKT_TYPE:
                continue  # Not an Acknowledgement.
            if struct.unpack_from("<I", buf, 4)[0] != source:
                continue  # Another client's traffic -- never act on it.
            self._outstanding.pop(buf[23], None)

        # Prune expired probes -- zero retransmits by design; an expired
        # probe only frees a gate slot, it never triggers a resend.
        expired = [
            seq
            for seq, sent_at in self._outstanding.items()
            if now - sent_at > ACK_EXPIRY_SECONDS
        ]
        for seq in expired:
            del self._outstanding[seq]

    def reset(self) -> None:
        """Clear all outstanding probes, reopening the gate."""
        self._outstanding.clear()
