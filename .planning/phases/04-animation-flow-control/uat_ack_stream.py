"""ANIM-03/ANIM-04 hardware evidence: paired ambient/gated/blind-fire battery.

Drives a paired same-session battery against a real matrix device: an
ambient control block (prober only, no streaming), then alternating
ack-gated and instrument-level blind-fire streaming rounds -- with the
IDENTICAL single-shot query prober in every block, so only the streaming
treatment differs between arms. The gated rounds run the SHIPPED
`Animator.for_matrix()` / `send_frame()` ack-gated flow control
(ANIM-01/ANIM-02, see `src/lifx/animation/flow.py` and
`src/lifx/animation/animator.py`); the blind-fire rounds are spike 003
`arm_blind` mechanics constructed at instrument level only -- per-packet
awaited sends of the animator's prebaked templates with the ack flag
CLEARED on every packet, no probes, no gating, on this script's own
transport. The shipped Animator gains no flow-control toggle (D4-02);
src/ and tests/ are untouched.

Two device profiles:
    tiles   -- ANIM-03: ack-gated concurrent-query loss is a large measured
               improvement over same-session blind-fire (Fisher one-sided
               p < FISHER_ALPHA AND blind/gated >= MIN_IMPROVEMENT_RATIO,
               OR gated pooled <= CLEAN_GATED_LOSS_PCT) within an absolute
               ceiling of MAX_GATED_POOLED_LOSS_PCT pooled gated loss.
               Ambient-degraded sessions are INCONCLUSIVE, never PASS or
               FAIL. (Paired-relative criterion designed in
               04-CRITERION-DESIGN.md, operator-approved at the 04-11
               checkpoint.)
    ceiling -- ANIM-04: the paired shape above, plus the unchanged
               large-tile checks: every sent gated frame matches the
               packets/frame expectation derived from the REPORTED chain
               dimensions by the row-aligned chunking rule
               (`expected_packets_per_frame()` -- a 13x26 chain geometry
               expects 8 packets/frame; the Capsule itself REPORTS a 16x8
               chain (128 zones; 26 in x 13 in physical) and expects 3;
               04-SWEEP-DESIGN.md section 5, superseding the old
               hard-coded 8) and every
               gated round has >= 1 ack RTT sample (the CopyFrameBuffer
               probe is being acked -- assumption A1 evidence). Powers the
               device on first -- streaming is invisible on a powered-off
               ceiling. Blind-fire rounds stream its full chain-dims-shaped
               frames unpaced at instrument level.

Sweep mode (cross-device ANIM-03/ANIM-04 certification, 04-12): alongside
the single-device CLI mode above, two additional modes run the
operator-approved cross-device paired sweep over the module-level
`ROSTER` (7 healthy-radio gate devices + System Test Tiles II retained as
known-bad-radio REFERENCE DATA only, never gating):
    --sweep-device SERIAL   resolves ONE roster entry serial-
                             authoritatively (roster IP fast path,
                             `find_by_serial` broadcast-discovery
                             fallback), auto-selects its profile
                             (CeilingLight instance -> ceiling, any other
                             MatrixLight -> tiles), captures its as-found
                             power+colour, runs the IDENTICAL paired
                             session above, and restores it in a `finally`
                             block -- writing `04-UAT-SWEEP-<serial>.json`
                             under the existing per-session exit contract
                             (0/1/2/3).
    --sweep-verdict          deterministically aggregates the 8 on-disk
                             per-device JSONs into `04-UAT-SWEEP.json`
                             under the frozen K-of-N_valid/quorum rule
                             (04-SWEEP-DESIGN.md section 3: the sweep
                             PASSes iff at least SWEEP_QUORUM of the 7
                             gate devices produced valid sessions and at
                             most SWEEP_MAX_ALLOWED_FAILS of those FAILed;
                             Tiles II is reported but never counted),
                             exiting 0 PASS / 1 FAIL / 2 ENV-ERROR (all 7
                             gate rows ENV-ERROR -- nothing was measured)
                             / 3 INCONCLUSIVE (below quorum).
The single-device mode's required arguments are unchanged and it remains
the vehicle for the Task 5 consolidated visual checkpoint.

Session shape (every block runs the same DeviceConnection prober,
max_retries=0, 2 queries/s, 2 s timeout):
    1. reachability probe (exit 2 ENV-ERROR if it fails; no streaming)
    2. ambient control block: AMBIENT_CONTROL_SECONDS, prober only
    3. alternating rounds, gated first -- G, B, G, B, ... at --rounds per
       arm (default 3), --duration seconds each (default 30), with
       INTER_ROUND_REST_SECONDS rests between every block

Run (Tiles):
    uv run python .planning/phases/04-animation-flow-control/uat_ack_stream.py \\
        --ip <tiles-ip> --profile tiles \\
        --json-out .planning/phases/04-animation-flow-control/04-UAT-TILES.json

Run (Ceiling):
    uv run python .planning/phases/04-animation-flow-control/uat_ack_stream.py \\
        --ip <ceiling-ip> --profile ceiling \\
        --json-out .planning/phases/04-animation-flow-control/04-UAT-CEILING.json

Run (Sweep, one roster device):
    uv run python .planning/phases/04-animation-flow-control/uat_ack_stream.py \\
        --sweep-device d073d587daab

Run (Sweep, aggregate verdict from the on-disk per-device JSONs):
    uv run python .planning/phases/04-animation-flow-control/uat_ack_stream.py \\
        --sweep-verdict

Honest-reporting rules (fixed in this file BEFORE any run, never adjusted
after seeing results):
    - Pass thresholds and the exit-code contract below are final. A run that
      misses them is a genuine signal to record, not a reason to relax them.
    - Every run's actual per-block numbers are written to the results JSON,
      whatever the outcome.
    - Repeated rounds (default 3 per arm) are mandatory for loss claims -- a
      single round proves nothing about a rare-but-real loss event (STATE
      blocker).
    - The gate shape was redesigned once, 2026-07-17, by operator decision
      after the amended absolute gate FAILed twice -- routing verbatim "2",
      design in 04-CRITERION-DESIGN.md, approved at the 04-11 checkpoint
      (verbatim "1") -- fixed BEFORE any paired run, never after one.
    - 04-12 retargets WHICH devices certify ANIM-03/ANIM-04 (a cross-device
      sweep, Tiles II as reference-only) and adds the sweep aggregation
      rule; the per-device paired gate itself (this file's constants and
      `_evaluate`) is reused byte-for-byte, never re-tuned.
    - INCONCLUSIVE is a declared outcome with its own exit code, never
      silently retried: it means the session's own environment failed the
      validity preconditions, so the session can certify nothing either way.

Ack RTT measurement note: `AckRttObserver` below takes read-only snapshots
of `Animator._ack_gate._outstanding` (which already maps each probe's
sequence to its sent-at monotonic time) once per `send_frame()` call -- it
never polls the socket independently and never mutates the gate (`AckGate`
declares `__slots__`, so the 03-03 method-wrap pattern cannot apply). RTT
resolution is therefore one frame tick (~50 ms at 20 FPS), not the true
wire RTT. This is measurement-only private reach in the spirit of Phase
3's `uat_zero_loss.py`; the library's public surface is never touched.

Exit codes (per-session, both the single-device CLI mode and
--sweep-device; --sweep-verdict reuses the same numbers at sweep level --
see its docstring above):
    0 -- PASS: session valid AND gated pooled loss <=
         MAX_GATED_POOLED_LOSS_PCT AND (gated pooled <=
         CLEAN_GATED_LOSS_PCT OR (Fisher one-sided p < FISHER_ALPHA AND
         blind/gated improvement >= MIN_IMPROVEMENT_RATIO)). Ceiling
         profile additionally requires every sent gated frame to match the
         chain-dims-derived expected_packets_per_frame() AND >= 1 ack RTT
         sample per gated round.
    1 -- FAIL: session valid but the pass rule above was missed. A genuine
         signal -- report it, never massage it.
    2 -- ENV-ERROR: the reachability probe failed (device unreachable from
         this machine), OR (--sweep-device only) neither the roster-IP fast
         path nor the find_by_serial fallback could resolve the device. No
         streaming is attempted -- an off-network run must never fabricate
         a pass or spray hundreds of frames at nothing.
    3 -- INCONCLUSIVE (ENV-DEGRADED): the session failed a validity
         precondition -- ambient pooled loss > MAX_AMBIENT_LOSS_PCT,
         ambient queries < MIN_AMBIENT_QUERIES, or any gated round's
         delivered_ratio < MIN_GATED_DELIVERED_SANITY. Never a pass,
         never a fail; the environment (not the gate) was the problem.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lifx.animation.animator import Animator
from lifx.animation.flow import ACK_EXPIRY_SECONDS
from lifx.animation.packets import ACK_REQUIRED_FLAG, FLAGS_OFFSET, SEQUENCE_OFFSET
from lifx.api import find_by_serial
from lifx.color import HSBK
from lifx.const import DISCOVERY_TIMEOUT, LIFX_UDP_PORT, TIMEOUT_ERRORS
from lifx.devices.ceiling import CeilingLight
from lifx.devices.matrix import MatrixLight
from lifx.exceptions import LifxError
from lifx.network.connection import DeviceConnection
from lifx.network.transport import UdpTransport
from lifx.products import is_ceiling_product
from lifx.protocol import packets

# Spike 003 baseline (30 s @ 20 FPS, real Tiles hardware) -- historical
# fact for the reader of the results JSON, never a threshold. See
# .claude/skills/spike-findings-lifx-async/sources/003-ack-paced-frames/.
BASELINE: dict[str, Any] = {
    "blind_fire_query_loss_pct": 14.6,
    "ack_gated_query_loss_pct": 0.0,
    "ack_gated_delivered": "530/600",
    "ack_rtt_median_ms": 98.0,
    "ack_rtt_p95_ms": 150.0,
}

# Large-tile Ceiling, 13x26 chain geometry (superseded roster assumption):
# 7 row-aligned Set64 packets + 1 final CopyFrameBuffer (assumption A2 --
# see src/lifx/animation/packets.py). Kept as a documented reference value (see
# `_thresholds()`); the actual per-frame assertion now uses
# `expected_packets_per_frame()`, computed from the REPORTED chain
# dimensions of whichever ceiling-class device is streaming
# (04-SWEEP-DESIGN.md section 5). My Office Ceiling Capsule's REPORTED
# chain is 16x8 (128 zones; 26 in x 13 in physical, not 13x26) and expects
# 3, measured 2026-07-17 (04-UAT-SWEEP-d073d587daab.json) -- this constant
# is a superseded reference value, not the Capsule's actual expectation.
EXPECTED_CEILING_PACKETS_PER_FRAME: int = 8

# Fixed paired-gate constants (set before any run, never adjusted
# afterwards). The gate was recalibrated 2026-07-17 by operator decision
# (04-GAP-ANALYSIS.md, routed "1" in 04-09-SUMMARY.md), then REDESIGNED
# 2026-07-17 by operator decision after the amended absolute gate FAILed
# twice: routing verbatim "2", paired-relative design derived from the
# multi-session evidence in 04-CRITERION-DESIGN.md, complete final wording
# approved at the 04-11 blocking checkpoint (verbatim "1"). Fixed BEFORE
# any paired run, never after one.
AMBIENT_CONTROL_SECONDS: float = 60.0
MAX_AMBIENT_LOSS_PCT: float = 2.5  # session validity V1
MIN_AMBIENT_QUERIES: int = 100  # session validity V2
MIN_GATED_DELIVERED_SANITY: float = 0.50  # session validity V3 (not pass/fail)
FISHER_ALPHA: float = 0.05  # relative rule significance
MIN_IMPROVEMENT_RATIO: float = 2.0  # relative rule point-ratio floor
CLEAN_GATED_LOSS_PCT: float = 2.5  # clean escape
MAX_GATED_POOLED_LOSS_PCT: float = 9.0  # absolute ceiling
INTER_ROUND_REST_SECONDS: float = 10.0
CEILING_MIN_ACK_RTT_SAMPLES: int = 1

# Cross-device sweep aggregation constants (04-12, 04-SWEEP-DESIGN.md
# section 3). The per-device paired gate above is reused UNCHANGED; only
# this aggregation rule is new. Chosen by the pre-declared bar (minimum
# acceptable P(sweep PASS | historical per-device rate, N_valid=7) = 0.85,
# the 04-11 adjustment-rule bar): K = N_valid - SWEEP_MAX_ALLOWED_FAILS
# gives power 0.8523 (>= 0.85, strictest meeting the bar). Quorum: a sweep
# must never certify from a minority of the 7-device gate roster, so
# Q = (strict majority of 7 - 1) + 1 = 5.
SWEEP_QUORUM: int = 5
SWEEP_MAX_ALLOWED_FAILS: int = 1

# Serial-authoritative resolution timeouts (04-SWEEP-DESIGN.md section
# (v)): the roster IP is only a fast path (short timeout); the
# find_by_serial broadcast-discovery fallback needs the library's normal
# discovery window.
SWEEP_RESOLVE_FAST_PATH_TIMEOUT: float = 5.0
SWEEP_RESOLVE_DISCOVERY_TIMEOUT: float = DISCOVERY_TIMEOUT


@dataclass(frozen=True)
class RosterEntry:
    """One 04-12 cross-device sweep roster entry.

    `role` is `"gate"` (counts toward N_valid/K in the aggregation) or
    `"reference"` (System Test Tiles II -- always reported, never counted;
    04-SWEEP-DESIGN.md section 1, the operator's Tiles ruling).
    """

    label: str
    ip: str
    serial: str
    role: str


# The operator-approved sweep roster (04-SWEEP-DESIGN.md section 1). IPs
# are DHCP leases and may drift between planning and execution: resolution
# is serial-authoritative (`_resolve_roster_device`) -- the roster IP below
# is only a fast path whose reported serial must match.
ROSTER: tuple[RosterEntry, ...] = (
    RosterEntry("Playroom Luna", "192.168.19.182", "d073d5893c04", "gate"),
    RosterEntry("Dining Room Table Candle", "192.168.18.81", "d073d55956e8", "gate"),
    RosterEntry("Makerspace Candle", "192.168.18.32", "d073d582bff4", "gate"),
    RosterEntry("Makerspace Tube", "192.168.19.199", "d073d5866777", "gate"),
    RosterEntry("Makerspace Ceiling", "192.168.19.119", "d073d5a132d9", "gate"),
    RosterEntry("Playroom Ceiling", "192.168.19.82", "d073d5a132b8", "gate"),
    RosterEntry("My Office Ceiling Capsule", "192.168.19.231", "d073d587daab", "gate"),
    RosterEntry("System Test Tiles II", "192.168.18.62", "d073d53e11be", "reference"),
)


@dataclass
class _QueryStats:
    """Concurrent single-shot query prober results for one block."""

    ok: int = 0
    lost: int = 0
    latencies_ms: list[float] = field(default_factory=list)


class AckRttObserver:
    """Measures probe ack RTT/expiry via read-only `AckGate` snapshots.

    `AckGate._outstanding` already maps each outstanding probe's sequence
    to the monotonic time it was sent, and `AckGate` declares `__slots__`,
    so its `track()` method cannot be shadowed by attribute assignment (the
    03-03 `send_packet` wrap pattern does not apply). Instead, `observe()`
    is called once per `send_frame()` and diffs the gate's live
    `_outstanding` dict (private-reach, measurement-only) against the
    previous snapshot: a newly present sequence is a tracked probe whose
    `sent_at` is adopted from the gate's own value; a sequence that
    vanished (or whose `sent_at` changed -- uint8 wrap overwrite) was
    resolved by the gate's own `sweep()` -- age <= `ACK_EXPIRY_SECONDS`
    means an ack arrived (RTT = now - sent_at); older means it expired.

    The diff misses nothing: `send_frame()` sweeps *before* it tracks, so
    a probe tracked in call N is always visible to the `observe()` after
    call N and can only be resolved during a later call. Resolution
    granularity remains one frame tick (~50 ms at 20 FPS), as documented.

    Measurement-only: nothing on the animator or gate is ever mutated, so
    gating behaviour is byte-for-byte identical to an unobserved animator.
    """

    def __init__(self, animator: Animator) -> None:
        self._gate = animator._ack_gate  # noqa: SLF001 -- measurement-only, 03-03 precedent
        self._sent_at: dict[int, float] = {}
        self.rtt_samples_ms: list[float] = []
        self.expiries = 0

    def observe(self, now: float) -> None:
        """Diff sequences the real gate has resolved since the last call."""
        outstanding = self._gate._outstanding  # noqa: SLF001
        for seq, sent_at in list(self._sent_at.items()):
            if outstanding.get(seq) == sent_at:
                continue  # Still outstanding, unchanged.
            del self._sent_at[seq]
            age = now - sent_at
            if age <= ACK_EXPIRY_SECONDS:
                self.rtt_samples_ms.append(age * 1000)
            else:
                self.expiries += 1
        for seq, sent_at in outstanding.items():
            self._sent_at.setdefault(seq, sent_at)


def _frame_hsbk(frame_index: int, pixel_count: int) -> list[tuple[int, int, int, int]]:
    """A moving hue-sweep frame, protocol-ready uint16 HSBK (spike 003 shape)."""
    step = 65536 // max(pixel_count, 1)
    return [
        ((frame_index * 800 + idx * step) % 65536, 65535, 16384, 3500)
        for idx in range(pixel_count)
    ]


class BlindStreamer:
    """Sends animator-prebaked frame packets blind: no acks, no gating.

    Adapted from `ReplicaStreamer` in uat_loss_investigation.py (04-08,
    itself from spike 003 stream.py `FrameStreamer`): reaches into animator
    privates for templates/framebuffer/generator (measurement-only,
    03-03/04-05 precedent), sends each packet with an awaited
    `transport.send()` on this instrument's OWN `UdpTransport`, and CLEARS
    the ack flag on every packet -- spike 003 `arm_blind` mechanics: no
    probes, no gating, no ack collection, no ack-related state at all.
    Pure blind fire, constructed at instrument level only (D4-02: the
    shipped Animator has no flow-control toggle).
    """

    def __init__(self, animator: Animator, transport: UdpTransport) -> None:
        self.transport = transport
        self.templates = animator._templates  # noqa: SLF001 -- measurement-only
        self.framebuffer = animator._framebuffer  # noqa: SLF001
        self.generator = animator._packet_generator  # noqa: SLF001
        self.addr = (animator._ip, LIFX_UDP_PORT)  # noqa: SLF001
        self.sequence = 0
        self.pixels = animator.pixel_count

    async def send_frame(self, frame_i: int) -> None:
        """Send one frame, per-packet awaited, ack flag cleared everywhere."""
        device_data = self.framebuffer.apply(_frame_hsbk(frame_i, self.pixels))
        self.generator.update_colors(self.templates, device_data)
        for tmpl in self.templates:
            tmpl.data[SEQUENCE_OFFSET] = self.sequence
            tmpl.data[FLAGS_OFFSET] &= ~ACK_REQUIRED_FLAG
            self.sequence = (self.sequence + 1) % 256
            await self.transport.send(bytes(tmpl.data), self.addr)


def _pct(values: list[float], p: float) -> float:
    idx = min(len(values) - 1, math.ceil(len(values) * p) - 1)
    return sorted(values)[idx]


def fisher_one_sided(
    gated_lost: int, gated_ok: int, blind_lost: int, blind_ok: int
) -> float:
    """One-sided Fisher exact p (alternative: gated loss rate < blind loss rate).

    Copied from criterion_design.py (04-11, standalone-script discipline):
    conditioning on the total number of losses, p is the hypergeometric
    lower tail P(X <= gated_lost) where X is the count of losses falling in
    the gated arm.
    """
    row1 = gated_lost + gated_ok  # gated arm n
    row2 = blind_lost + blind_ok  # blind arm n
    col1 = gated_lost + blind_lost  # total losses
    total = row1 + row2
    denom = math.comb(total, col1)
    lo = max(0, col1 - row2)
    tail = sum(
        math.comb(row1, x) * math.comb(row2, col1 - x)
        for x in range(lo, gated_lost + 1)
    )
    return min(1.0, tail / denom)


def expected_packets_per_frame(tile_count: int, width: int, height: int) -> int:
    """Row-aligned packets/frame expectation, mirroring MatrixPacketGenerator.

    Independent derivation from the REPORTED chain dimensions
    (04-SWEEP-DESIGN.md section 5) -- never reads the generator's own
    `packets_per_tile` back, which would be circular: pixels = width x
    height; if pixels <= 64 the expectation is `tile_count` (one Set64 per
    tile, no CopyFrameBuffer); else `rows_per_packet = 64 // width`,
    `set64_per_tile = ceil(height / rows_per_packet)`, and the expectation
    is `tile_count * (set64_per_tile + 1)` for the final CopyFrameBuffer
    per tile.

    Worked examples: 13x26 chain geometry -> 64//13=4 rows/packet,
    ceil(26/4)=7 Set64, +1 CopyFB = 8; 16x8 ceiling (the Capsule's REPORTED
    chain) -> 64//16=4, ceil(8/4)=2, +1 = 3; five 8x8 tiles -> 64 pixels
    <= 64 -> one Set64 per tile, no CopyFB = 5.
    """
    pixels = width * height
    if pixels <= 64:
        return tile_count
    rows_per_packet = 64 // width
    set64_per_tile = math.ceil(height / rows_per_packet)
    return tile_count * (set64_per_tile + 1)


async def _reachability_probe(device: MatrixLight, timeout: float) -> bool:
    """One generous-timeout GetColor probe on the normal (retrying) connection."""
    try:
        await device.connection.request(packets.Light.GetColor(), timeout=timeout)
    except LifxError:
        return False
    return True


async def query_prober(
    ip: str,
    port: int,
    serial: str,
    query_rate: float,
    query_timeout: float,
    stop: asyncio.Event,
) -> _QueryStats:
    """Concurrent single-shot GetColor prober on a dedicated connection.

    `max_retries=0` is load-bearing: Phase 3's retransmit schedule must
    never mask loss here (STATE blocker) -- this measures whether *this
    exact* query round-trips, not whether the retry engine eventually
    recovers it. Runs on its own `DeviceConnection`, never sharing any
    streaming socket. The SAME prober runs in the ambient, gated and blind
    blocks -- the measurement instrument is byte-identical across arms.
    """
    conn = DeviceConnection(
        serial=serial, ip=ip, port=port, max_retries=0, timeout=query_timeout
    )
    stats = _QueryStats()
    interval = 1.0 / query_rate
    try:
        while not stop.is_set():
            sent = time.perf_counter()
            try:
                await conn.request(packets.Light.GetColor(), timeout=query_timeout)
            except LifxError:
                stats.lost += 1
            else:
                stats.ok += 1
                stats.latencies_ms.append((time.perf_counter() - sent) * 1000)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except TIMEOUT_ERRORS:
                pass
    finally:
        await conn.close()
    return stats


def _query_aggregates(stats: _QueryStats) -> dict[str, Any]:
    """Per-block query aggregates from raw prober counts."""
    queries = stats.ok + stats.lost
    return {
        "queries_ok": stats.ok,
        "queries_lost": stats.lost,
        "query_loss_pct": round(100 * stats.lost / queries, 2) if queries else None,
        "query_latency_median_ms": (
            round(statistics.median(stats.latencies_ms), 1)
            if stats.latencies_ms
            else None
        ),
    }


async def run_ambient_block(
    device: MatrixLight,
    query_rate: float,
    query_timeout: float,
) -> dict[str, Any]:
    """Prober-only ambient control block: no streaming, the session's floor.

    Adapted from `run_control_block` in uat_loss_investigation.py (04-08).
    """
    stop = asyncio.Event()
    prober_task = asyncio.create_task(
        query_prober(
            device.ip, device.port, device.serial, query_rate, query_timeout, stop
        )
    )
    try:
        await asyncio.sleep(AMBIENT_CONTROL_SECONDS)
    finally:
        stop.set()
        stats = await prober_task
    return {
        "duration_s": AMBIENT_CONTROL_SECONDS,
        **_query_aggregates(stats),
    }


async def stream_round(
    animator: Animator,
    observer: AckRttObserver,
    profile: str,
    duration: float,
    fps: float,
    expected_packets_per_frame_value: int | None = None,
) -> dict[str, Any]:
    """Tick the SHIPPED Animator at `fps` for `duration` seconds.

    Monotonic-deadline scheduler (no drift): each tick's target time is
    computed from the round's start plus `offered * tick`, never from the
    previous tick's actual completion time. `expected_packets_per_frame_value`
    is the chain-dims-derived expectation (`expected_packets_per_frame()`)
    for the ceiling profile's per-frame shape assertion; `None` disables the
    check (non-ceiling profiles).
    """
    tick = 1.0 / fps
    pixels = animator.pixel_count
    offered = 0
    sent = 0
    gated = 0
    packet_shape_ok = True
    start = time.monotonic()
    while time.monotonic() - start < duration:
        frame = _frame_hsbk(offered, pixels)
        stats = animator.send_frame(frame)
        now = time.monotonic()
        offered += 1
        if stats.gated:
            gated += 1
        else:
            sent += 1
            if (
                profile == "ceiling"
                and expected_packets_per_frame_value is not None
                and stats.packets_sent != expected_packets_per_frame_value
            ):
                packet_shape_ok = False
        observer.observe(now)
        next_at = start + offered * tick
        await asyncio.sleep(max(0.0, next_at - time.monotonic()))
    return {
        "offered": offered,
        "sent": sent,
        "gated": gated,
        "delivered_ratio": round(sent / offered, 4) if offered else 0.0,
        "packet_shape_ok": packet_shape_ok,
        "expected_packets_per_frame": expected_packets_per_frame_value,
    }


async def run_round(
    device: MatrixLight,
    profile: str,
    round_index: int,
    duration: float,
    fps: float,
    query_rate: float,
    query_timeout: float,
    expected_packets_per_frame_value: int | None = None,
) -> dict[str, Any]:
    """One GATED round: shipped Animator streaming + concurrent prober."""
    animator = await Animator.for_matrix(device)
    observer = AckRttObserver(animator)
    stop = asyncio.Event()
    prober_task = asyncio.create_task(
        query_prober(
            device.ip, device.port, device.serial, query_rate, query_timeout, stop
        )
    )
    try:
        stream_result = await stream_round(
            animator, observer, profile, duration, fps, expected_packets_per_frame_value
        )
    finally:
        stop.set()
        query_stats = await prober_task
        animator.close()

    ack_rtt_median_ms = (
        round(statistics.median(observer.rtt_samples_ms), 1)
        if observer.rtt_samples_ms
        else None
    )
    ack_rtt_p95_ms = (
        round(_pct(observer.rtt_samples_ms, 0.95), 1)
        if observer.rtt_samples_ms
        else None
    )

    return {
        "round": round_index,
        "arm": "gated",
        **stream_result,
        **_query_aggregates(query_stats),
        "ack_rtt_median_ms": ack_rtt_median_ms,
        "ack_rtt_p95_ms": ack_rtt_p95_ms,
        "ack_rtt_samples": len(observer.rtt_samples_ms),
        "ack_expiries": observer.expiries,
    }


async def run_blind_round(
    device: MatrixLight,
    round_index: int,
    duration: float,
    fps: float,
    query_rate: float,
    query_timeout: float,
) -> dict[str, Any]:
    """One BLIND-FIRE round: unpaced instrument-level streaming + prober.

    A fresh `Animator.for_matrix()` supplies templates only (its socket is
    never used for these sends); the `BlindStreamer` streams on its own
    transport with the ack flag cleared on every packet. The prober is the
    SAME `query_prober` used by the ambient and gated blocks.
    """
    animator = await Animator.for_matrix(device)
    transport = UdpTransport(port=0, broadcast=False)
    await transport.open()
    streamer = BlindStreamer(animator, transport)
    stop = asyncio.Event()
    prober_task = asyncio.create_task(
        query_prober(
            device.ip, device.port, device.serial, query_rate, query_timeout, stop
        )
    )
    tick = 1.0 / fps
    offered = 0
    sent = 0
    try:
        start = time.monotonic()
        while time.monotonic() - start < duration:
            await streamer.send_frame(offered)
            offered += 1
            sent += 1
            next_at = start + offered * tick
            await asyncio.sleep(max(0.0, next_at - time.monotonic()))
    finally:
        stop.set()
        query_stats = await prober_task
        await transport.close()
        animator.close()

    return {
        "round": round_index,
        "arm": "blind",
        "offered": offered,
        "sent": sent,
        **_query_aggregates(query_stats),
    }


def _pooled_counts(rounds: list[dict[str, Any]]) -> tuple[int, int]:
    """(lost, n) pooled across the given per-round aggregate dicts."""
    lost = sum(r["queries_lost"] for r in rounds)
    n = sum(r["queries_ok"] + r["queries_lost"] for r in rounds)
    return lost, n


def _pooled_block(rounds: list[dict[str, Any]]) -> dict[str, Any]:
    lost, n = _pooled_counts(rounds)
    return {
        "lost": lost,
        "n": n,
        "loss_pct": round(100 * lost / n, 2) if n else None,
    }


def _paired_stats(
    gated_rounds: list[dict[str, Any]], blind_rounds: list[dict[str, Any]]
) -> tuple[float | None, float | None]:
    """(fisher_one_sided_p, improvement_ratio) for the paired arms.

    improvement_ratio = blind loss % / gated loss %; None when undefined
    (either arm empty, or gated lost 0 -- the ratio condition is then
    handled categorically by `_evaluate`).
    """
    g_lost, g_n = _pooled_counts(gated_rounds)
    b_lost, b_n = _pooled_counts(blind_rounds)
    if g_n == 0 or b_n == 0:
        return None, None
    p = fisher_one_sided(g_lost, g_n - g_lost, b_lost, b_n - b_lost)
    if g_lost == 0:
        return p, None
    ratio = (100 * b_lost / b_n) / (100 * g_lost / g_n)
    return p, round(ratio, 2)


def _validity_reasons(
    ambient: dict[str, Any], gated_rounds: list[dict[str, Any]]
) -> list[str]:
    """Session-validity misses (V1/V2/V3). Empty list = valid session."""
    reasons: list[str] = []
    amb_n = ambient["queries_ok"] + ambient["queries_lost"]
    if amb_n < MIN_AMBIENT_QUERIES:
        reasons.append(
            f"ambient sample n={amb_n} below the minimum "
            f"{MIN_AMBIENT_QUERIES} (validity V2)"
        )
    amb_loss = (100 * ambient["queries_lost"] / amb_n) if amb_n else None
    if amb_loss is None or amb_loss > MAX_AMBIENT_LOSS_PCT:
        shown = f"{amb_loss:.2f}%" if amb_loss is not None else "unmeasurable"
        reasons.append(
            f"ambient pooled loss {shown} exceeds the validity bound "
            f"{MAX_AMBIENT_LOSS_PCT}% (validity V1)"
        )
    for r in gated_rounds:
        if r["delivered_ratio"] < MIN_GATED_DELIVERED_SANITY:
            reasons.append(
                f"gated round {r.get('round', '?')} delivered_ratio "
                f"{r['delivered_ratio']} below the sanity floor "
                f"{MIN_GATED_DELIVERED_SANITY} (validity V3)"
            )
    return reasons


def _evaluate(
    ambient: dict[str, Any],
    gated_rounds: list[dict[str, Any]],
    blind_rounds: list[dict[str, Any]],
    profile: str,
) -> tuple[str, list[str]]:
    """Apply the fixed paired-gate contract. Returns (outcome, reasons).

    Outcome is one of "PASS", "FAIL", "INCONCLUSIVE". Validity is checked
    FIRST and is terminal: no pass/fail rule is evaluated on an invalid
    session (INCONCLUSIVE is never a pass and never a fail).
    """
    validity = _validity_reasons(ambient, gated_rounds)
    if validity:
        return "INCONCLUSIVE", validity

    reasons: list[str] = []
    passing = True

    g_lost, g_n = _pooled_counts(gated_rounds)
    b_lost, b_n = _pooled_counts(blind_rounds)
    if g_n == 0:
        return "FAIL", ["no gated-arm queries were measured"]
    gated_pct = 100 * g_lost / g_n

    if profile == "ceiling":
        for r in gated_rounds:
            if not r["packet_shape_ok"]:
                expected = r.get(
                    "expected_packets_per_frame", EXPECTED_CEILING_PACKETS_PER_FRAME
                )
                reasons.append(
                    f"gated round {r.get('round', '?')}: a sent frame was not "
                    f"exactly {expected} packets"
                )
                passing = False
            if r["ack_rtt_samples"] < CEILING_MIN_ACK_RTT_SAMPLES:
                reasons.append(
                    f"gated round {r.get('round', '?')}: fewer than "
                    f"{CEILING_MIN_ACK_RTT_SAMPLES} ack RTT samples"
                )
                passing = False

    if gated_pct > MAX_GATED_POOLED_LOSS_PCT:
        reasons.append(
            f"gated pooled loss {gated_pct:.2f}% exceeds the absolute ceiling "
            f"{MAX_GATED_POOLED_LOSS_PCT}%"
        )
        passing = False

    if gated_pct <= CLEAN_GATED_LOSS_PCT:
        reasons.append(
            f"clean escape: gated pooled loss {gated_pct:.2f}% <= "
            f"{CLEAN_GATED_LOSS_PCT}%"
        )
    else:
        p, ratio = _paired_stats(gated_rounds, blind_rounds)
        fisher_ok = p is not None and p < FISHER_ALPHA
        if g_lost == 0:
            ratio_ok = b_lost > 0
        elif ratio is None:
            ratio_ok = False
        else:
            ratio_ok = ratio >= MIN_IMPROVEMENT_RATIO
        p_shown = f"{p:.4f}" if p is not None else "undefined"
        if fisher_ok and ratio_ok:
            reasons.append(
                f"relative rule: Fisher one-sided p = {p_shown} < "
                f"{FISHER_ALPHA} and blind/gated improvement "
                f"{ratio if ratio is not None else 'categorical'} >= "
                f"{MIN_IMPROVEMENT_RATIO} (gated {g_lost}/{g_n} vs blind "
                f"{b_lost}/{b_n})"
            )
        else:
            if not fisher_ok:
                reasons.append(
                    f"relative rule missed: Fisher one-sided p = {p_shown} "
                    f"not < {FISHER_ALPHA} (gated {g_lost}/{g_n} vs blind "
                    f"{b_lost}/{b_n})"
                )
            if not ratio_ok:
                reasons.append(
                    f"relative rule missed: blind/gated improvement "
                    f"{ratio if ratio is not None else 'undefined'} below "
                    f"{MIN_IMPROVEMENT_RATIO}"
                )
            reasons.append(
                f"no clean escape: gated pooled loss {gated_pct:.2f}% > "
                f"{CLEAN_GATED_LOSS_PCT}%"
            )
            passing = False

    return ("PASS" if passing else "FAIL"), reasons


def _thresholds() -> dict[str, Any]:
    return {
        "ambient_control_seconds": AMBIENT_CONTROL_SECONDS,
        "max_ambient_loss_pct": MAX_AMBIENT_LOSS_PCT,
        "min_ambient_queries": MIN_AMBIENT_QUERIES,
        "min_gated_delivered_sanity": MIN_GATED_DELIVERED_SANITY,
        "fisher_alpha": FISHER_ALPHA,
        "min_improvement_ratio": MIN_IMPROVEMENT_RATIO,
        "clean_gated_loss_pct": CLEAN_GATED_LOSS_PCT,
        "max_gated_pooled_loss_pct": MAX_GATED_POOLED_LOSS_PCT,
        "inter_round_rest_seconds": INTER_ROUND_REST_SECONDS,
        "ceiling_expected_packets_per_frame": EXPECTED_CEILING_PACKETS_PER_FRAME,
        "ceiling_min_ack_rtt_samples": CEILING_MIN_ACK_RTT_SAMPLES,
    }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _write(path: Path, results: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2) + "\n")


def _env_error_results(
    *,
    profile: str | None,
    ip: str | None,
    reason: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a recorded ENV-ERROR results dict -- never a fabricated pass."""
    results: dict[str, Any] = {
        "timestamp": _now(),
        "profile": profile,
        "ip": ip,
        "outcome": "ENV-ERROR",
        "skipped": True,
        "reason": reason,
        "restoration": {
            "attempted": False,
            "succeeded": False,
            "reason": "device unreachable",
        },
        "thresholds": _thresholds(),
        "baseline": BASELINE,
        "pass": False,  # nosec B105 -- verdict placeholder, not a credential
    }
    if extra:
        results.update(extra)
    return results


def _exit_code_for_outcome(outcome: str) -> int:
    return {  # nosec B105 -- exit-code lookup table, not a credential
        "PASS": 0,
        "FAIL": 1,
        "INCONCLUSIVE": 3,
    }.get(outcome, 1)


def _print_outcome(outcome: str, reasons: list[str]) -> None:
    print(f"\n{outcome}:")
    for reason in reasons:
        print(f"  - {reason}")
    if outcome == "INCONCLUSIVE":
        print(
            "ENV-DEGRADED: the session failed a validity precondition -- this "
            "session can certify nothing either way (not a pass, not a fail)."
        )
    elif outcome == "FAIL":
        print(
            "FAIL: device reachable, session valid, but the paired pass rule was "
            "missed -- see the JSON output for per-block detail"
        )


async def run_paired_session(
    device: MatrixLight,
    profile: str,
    fps: float,
    duration: float,
    rounds: int,
    query_rate: float,
    query_timeout: float,
) -> dict[str, Any]:
    """Run the full ambient/gated/blind paired battery against an OPEN device.

    Shared by the single-device (--ip/--profile) and sweep-device
    (--sweep-device) CLI modes so the session shape is byte-identical
    between them. Callers own reachability, power-on/settle and
    restoration -- this function only measures.
    """
    chain = await device.get_device_chain()
    chain_width = chain[0].width if chain else None
    chain_height = chain[0].height if chain else None
    tile_count = len(chain) if chain else 0
    expected_packets: int | None = None
    if profile == "ceiling" and chain_width is not None and chain_height is not None:
        expected_packets = expected_packets_per_frame(
            tile_count, chain_width, chain_height
        )

    print(f"\nambient control: {AMBIENT_CONTROL_SECONDS:.0f}s prober-only")
    ambient = await run_ambient_block(device, query_rate, query_timeout)
    print(json.dumps(ambient, indent=2))

    rounds_list: list[dict[str, Any]] = []
    gated_rounds: list[dict[str, Any]] = []
    blind_rounds: list[dict[str, Any]] = []
    for i in range(rounds):
        print(f"\nresting {INTER_ROUND_REST_SECONDS:.0f}s")
        await asyncio.sleep(INTER_ROUND_REST_SECONDS)
        print(
            f"round {i} arm=gated: streaming {duration}s @ {fps} FPS "
            f"(profile={profile})"
        )
        gated = await run_round(
            device,
            profile,
            i,
            duration,
            fps,
            query_rate,
            query_timeout,
            expected_packets,
        )
        print(json.dumps(gated, indent=2))
        rounds_list.append(gated)
        gated_rounds.append(gated)

        print(f"\nresting {INTER_ROUND_REST_SECONDS:.0f}s")
        await asyncio.sleep(INTER_ROUND_REST_SECONDS)
        print(
            f"round {i} arm=blind: streaming {duration}s @ {fps} FPS "
            "(instrument-level blind fire)"
        )
        blind = await run_blind_round(
            device, i, duration, fps, query_rate, query_timeout
        )
        print(json.dumps(blind, indent=2))
        rounds_list.append(blind)
        blind_rounds.append(blind)

    outcome, reasons = _evaluate(ambient, gated_rounds, blind_rounds, profile)
    validity = _validity_reasons(ambient, gated_rounds)
    fisher_p, improvement_ratio = _paired_stats(gated_rounds, blind_rounds)
    return {
        "profile": profile,
        "fps": fps,
        "duration_s": duration,
        "rounds_per_arm": rounds,
        "chain_width": chain_width,
        "chain_height": chain_height,
        "expected_packets_per_frame": expected_packets,
        "ambient": ambient,
        "rounds": rounds_list,
        "gated_pooled": _pooled_block(gated_rounds),
        "blind_pooled": _pooled_block(blind_rounds),
        "fisher_one_sided_p": fisher_p,
        "improvement_ratio": improvement_ratio,
        "session_valid": not validity,
        "validity_reasons": validity,
        "thresholds": _thresholds(),
        "baseline": BASELINE,
        "outcome": outcome,
        "reasons": reasons,
        "pass": outcome == "PASS",
    }


async def run_managed_session(
    device: MatrixLight, profile: str, args: argparse.Namespace
) -> tuple[dict[str, Any], dict[str, Any], bool | None]:
    """As-found capture -> ceiling power-on precondition -> paired session -> restore.

    Tiles-profile sessions never power the device on (query-loss
    measurement needs no visibility -- least household disturbance at an
    unsociable hour); the ceiling profile keeps its unchanged power-on +
    1 s settle + confirmation. Restoration (device-level power + the
    single device-level HSBK colour from `get_color()`) is attempted in a
    `finally` block regardless of the measurement outcome and never alters
    it (04-SWEEP-DESIGN.md section (v)). Per-pixel matrix contents and
    running firmware effects are NOT captured -- the public-API feasibility
    boundary.

    Returns (session results, restoration status, ceiling_power_confirmed).
    """
    restoration: dict[str, Any] = {
        "attempted": False,
        "succeeded": False,
        "reason": None,
    }
    ceiling_power_confirmed: bool | None = None
    as_found_color: HSBK | None = None
    as_found_power: int | None = None
    try:
        as_found_color, as_found_power, _label = await device.get_color()
        if profile == "ceiling":
            await device.set_power(True)
            await asyncio.sleep(1.0)  # settle delay -- D4-04 UAT prerequisite
            ceiling_power_confirmed = (await device.get_power()) > 0
        # tiles profile: never powers the device on.

        session = await run_paired_session(
            device,
            profile,
            args.fps,
            args.duration,
            args.rounds,
            args.query_rate,
            args.query_timeout,
        )
    finally:
        if as_found_color is not None:
            restoration["attempted"] = True
            try:
                await device.set_color(as_found_color)
                await device.set_power(bool(as_found_power))
                restoration["succeeded"] = True
            except LifxError as exc:
                restoration["reason"] = str(exc)

    return session, restoration, ceiling_power_confirmed


async def _resolve_profile(device: MatrixLight) -> str:
    """CeilingLight instance -> "ceiling"; any other MatrixLight -> "tiles".

    Devices returned by `find_by_serial` -> `DiscoveredDevice.create_device()`
    are already correctly typed, so `isinstance` resolves this directly. The
    `MatrixLight.from_ip` roster-IP fast path always returns a generic
    `MatrixLight` regardless of the real product, so isinstance cannot see
    Ceiling there -- fall back to `get_version()` + the products registry's
    `is_ceiling_product` check on the reported product ID.
    """
    if isinstance(device, CeilingLight):
        return "ceiling"
    version = await device.get_version()
    return "ceiling" if is_ceiling_product(version.product) else "tiles"


async def _resolve_roster_device(
    entry: RosterEntry,
) -> tuple[MatrixLight | None, dict[str, Any]]:
    """Serial-authoritative resolution: roster IP fast path, then discovery.

    The serial is the device's identity; the roster IP is only a fast path
    whose reported serial must match. On unreachable or mismatch, falls
    back to broadcast discovery by serial (`find_by_serial`). Returns
    `(None, ...)` if both fail -- the caller writes that device's own
    ENV-ERROR row and the sweep continues; a single moved/unreachable
    device never aborts the sweep (04-SWEEP-DESIGN.md section (v)).
    """
    candidate: MatrixLight | None = None
    try:
        candidate = await MatrixLight.from_ip(
            entry.ip, timeout=SWEEP_RESOLVE_FAST_PATH_TIMEOUT
        )
    except LifxError:
        candidate = None

    if candidate is not None:
        if candidate.serial.lower() == entry.serial.lower():
            return candidate, {"method": "roster-ip", "ip": entry.ip}
        await candidate.close()

    discovered = await find_by_serial(
        entry.serial, timeout=SWEEP_RESOLVE_DISCOVERY_TIMEOUT
    )
    if isinstance(discovered, MatrixLight):
        return discovered, {"method": "discovery-by-serial", "ip": discovered.ip}
    if discovered is not None:
        await discovered.close()
    return None, {"method": "unresolved", "ip": None}


async def run_sweep_device(
    entry: RosterEntry, args: argparse.Namespace
) -> tuple[dict[str, Any], int]:
    """Resolve one ROSTER device serial-authoritatively and run its session.

    Returns (per-device results dict, exit code) under the existing
    single-session exit contract (0/1/2/3). A resolution or reachability
    failure writes that device's own ENV-ERROR row -- the caller continues
    the sweep with the next roster entry; a single device never aborts it
    (04-SWEEP-DESIGN.md section (v)).
    """
    resolve_timeout = max(args.query_timeout, 5.0)
    device, resolution = await _resolve_roster_device(entry)
    if device is None:
        print(
            f"ENV-ERROR: {entry.label} ({entry.serial}) could not be resolved by "
            f"roster IP {entry.ip} or by broadcast discovery -- not streaming, "
            "not recording a pass."
        )
        results = _env_error_results(
            profile=None,
            ip=None,
            reason=(
                f"neither roster IP {entry.ip} nor discovery-by-serial resolved "
                f"{entry.serial}"
            ),
            extra={
                "serial": entry.serial,
                "label": entry.label,
                "role": entry.role,
                "resolution": resolution,
            },
        )
        return results, 2

    profile = await _resolve_profile(device)
    try:
        reachable = await _reachability_probe(device, timeout=resolve_timeout)
        if not reachable:
            print(
                f"ENV-ERROR: {entry.label} ({resolution['ip']}) did not respond "
                "to the reachability probe -- not streaming, not recording a pass."
            )
            results = _env_error_results(
                profile=profile,
                ip=resolution["ip"],
                reason=f"reachability probe to {resolution['ip']} failed",
                extra={
                    "serial": entry.serial,
                    "label": entry.label,
                    "role": entry.role,
                    "resolution": resolution,
                },
            )
            return results, 2

        session, restoration, ceiling_power_confirmed = await run_managed_session(
            device, profile, args
        )
    finally:
        await device.close()

    _print_outcome(session["outcome"], session["reasons"])
    results = {
        "timestamp": _now(),
        "serial": entry.serial,
        "label": entry.label,
        "role": entry.role,
        "profile": profile,
        "resolution": resolution,
        "ip": resolution["ip"],
        "ceiling_power_confirmed": ceiling_power_confirmed,
        "restoration": restoration,
        **session,
    }
    return results, _exit_code_for_outcome(session["outcome"])


def aggregate_sweep(evidence_dir: Path) -> dict[str, Any]:
    """Deterministically aggregate the 8 on-disk per-device JSONs.

    Reads `04-UAT-SWEEP-<serial>.json` for every ROSTER entry -- a missing
    file is itself an ENV-ERROR row, never fabricated. Applies the frozen
    K-of-N_valid/quorum rule (04-SWEEP-DESIGN.md section 3): the sweep
    PASSes iff N_valid (PASS + FAIL among gate devices) >= SWEEP_QUORUM and
    at most SWEEP_MAX_ALLOWED_FAILS of those valid gate sessions FAILed.
    System Test Tiles II (role "reference") is always reported but never
    counted in N_valid or the FAIL tally.
    """
    devices: list[dict[str, Any]] = []
    counts: dict[str, int] = {
        "PASS": 0,  # nosec B105 -- outcome tally, not a credential
        "FAIL": 0,
        "INCONCLUSIVE": 0,
        "ENV-ERROR": 0,
    }
    gate_total = sum(1 for e in ROSTER if e.role == "gate")

    for entry in ROSTER:
        path = evidence_dir / f"04-UAT-SWEEP-{entry.serial}.json"
        if path.exists():
            data = json.loads(path.read_text())
            outcome = data.get("outcome", "ENV-ERROR")
        else:
            outcome = "ENV-ERROR"
        devices.append(
            {
                "serial": entry.serial,
                "label": entry.label,
                "role": entry.role,
                "outcome": outcome,
            }
        )
        if entry.role == "gate":
            counts[outcome] = counts.get(outcome, 0) + 1

    n_valid = counts["PASS"] + counts["FAIL"]
    if n_valid >= SWEEP_QUORUM:
        sweep_outcome = "PASS" if counts["FAIL"] <= SWEEP_MAX_ALLOWED_FAILS else "FAIL"
    else:
        sweep_outcome = "INCONCLUSIVE"
    if counts["ENV-ERROR"] == gate_total:
        sweep_outcome = "ENV-ERROR"

    return {
        "timestamp": _now(),
        "devices": devices,
        "aggregation": {
            "k": max(n_valid - SWEEP_MAX_ALLOWED_FAILS, 0),
            "n_valid": n_valid,
            "quorum": SWEEP_QUORUM,
            "allowed_fails": SWEEP_MAX_ALLOWED_FAILS,
            "counts": counts,
        },
        "rules": {
            "quorum": SWEEP_QUORUM,
            "max_allowed_fails": SWEEP_MAX_ALLOWED_FAILS,
            **_thresholds(),
        },
        "outcome": sweep_outcome,
    }


def _sweep_exit_code(outcome: str) -> int:
    return {  # nosec B105 -- exit-code lookup table, not a credential
        "PASS": 0,
        "FAIL": 1,
        "ENV-ERROR": 2,
        "INCONCLUSIVE": 3,
    }.get(outcome, 1)


async def _run_single_device_mode(args: argparse.Namespace) -> int:
    """The preserved --ip/--profile/--json-out CLI mode."""
    async with await MatrixLight.from_ip(args.ip) as device:
        reachable = await _reachability_probe(
            device, timeout=max(args.query_timeout, 5.0)
        )
        if not reachable:
            print(
                f"ENV-ERROR: {args.ip} did not respond to the reachability probe -- "
                "the device is not visible from this machine; not streaming, not "
                "recording a pass."
            )
            results = _env_error_results(
                profile=args.profile,
                ip=args.ip,
                reason=f"reachability probe to {args.ip} failed",
            )
            _write(args.json_out, results)
            return 2

        session, restoration, ceiling_power_confirmed = await run_managed_session(
            device, args.profile, args
        )

    _print_outcome(session["outcome"], session["reasons"])
    results = {
        "timestamp": _now(),
        "ip": args.ip,
        "ceiling_power_confirmed": ceiling_power_confirmed,
        "restoration": restoration,
        **session,
    }
    _write(args.json_out, results)
    return _exit_code_for_outcome(session["outcome"])


async def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--ip", help="single-device mode: Matrix/Ceiling device IP address"
    )
    parser.add_argument(
        "--profile",
        choices=["tiles", "ceiling"],
        help=(
            "single-device mode: tiles=ANIM-03 paired loss gate; "
            "ceiling=ANIM-04 large-tile CopyFB path"
        ),
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="single-device mode: path to write the results JSON",
    )
    parser.add_argument(
        "--sweep-device",
        metavar="SERIAL",
        help=(
            "sweep mode: run ONE paired session for this ROSTER serial, "
            "writing 04-UAT-SWEEP-<serial>.json"
        ),
    )
    parser.add_argument(
        "--sweep-verdict",
        action="store_true",
        help=(
            "sweep mode: deterministically aggregate the 8 on-disk per-device "
            "04-UAT-SWEEP-<serial>.json files into 04-UAT-SWEEP.json"
        ),
    )
    parser.add_argument("--fps", type=float, default=20.0, help="Streaming frame rate")
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Seconds streamed per round (~600 offered frames at 20 FPS, spike 003)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help=(
            "Rounds PER ARM (gated and blind-fire each get this many rounds, "
            "alternating gated-first; repeated rounds are mandatory for loss "
            "claims -- STATE blocker)"
        ),
    )
    parser.add_argument(
        "--query-rate",
        type=float,
        default=2.0,
        help="Concurrent GetColor queries per second (spike 003 prober cadence)",
    )
    parser.add_argument(
        "--query-timeout", type=float, default=2.0, help="Per-query timeout in seconds"
    )
    args = parser.parse_args()

    single_device_requested = bool(args.ip or args.profile or args.json_out)
    modes_selected = sum(
        [bool(args.sweep_verdict), bool(args.sweep_device), single_device_requested]
    )
    if modes_selected != 1:
        parser.error(
            "choose exactly one mode: --ip/--profile/--json-out (single-device), "
            "--sweep-device SERIAL, or --sweep-verdict"
        )
    if single_device_requested and not (args.ip and args.profile and args.json_out):
        parser.error(
            "single-device mode requires --ip, --profile and --json-out together"
        )

    if args.sweep_verdict:
        evidence_dir = Path(__file__).resolve().parent
        result = aggregate_sweep(evidence_dir)
        _write(evidence_dir / "04-UAT-SWEEP.json", result)
        print(json.dumps(result, indent=2))
        return _sweep_exit_code(result["outcome"])

    if args.sweep_device:
        serial = args.sweep_device.replace(":", "").replace("-", "").lower()
        entry = next((e for e in ROSTER if e.serial == serial), None)
        if entry is None:
            parser.error(f"--sweep-device {args.sweep_device} is not in ROSTER")
        evidence_dir = Path(__file__).resolve().parent
        results, exit_code = await run_sweep_device(entry, args)
        _write(evidence_dir / f"04-UAT-SWEEP-{entry.serial}.json", results)
        return exit_code

    return await _run_single_device_mode(args)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
