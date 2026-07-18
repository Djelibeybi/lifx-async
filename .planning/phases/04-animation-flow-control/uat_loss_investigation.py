"""04-08 gap investigation: discriminate H1 (real residual loss) from H2 (calibration).

This is an INVESTIGATION instrument, not a UAT gate. It contains no pass/fail
thresholds, renders no verdict, and writes no verdict fields of any kind -- it
is structurally incapable of the threshold-tampering the UAT rules forbid.
Its only exit codes are:

    0 -- measurement completed; every number recorded exactly as measured,
         whatever the numbers show.
    2 -- ENV-ERROR: the PRIMARY device's reachability probe failed. An honest
         skipped JSON is written and nothing is streamed.

Background: the 04-06 ANIM-03 UAT failed its fixed 0% concurrent-query-loss
gate reproducibly (pooled 9/267 ~= 3.4%, evidence commit 5de88f6), while spike
003's photons arm measured 0.0% -- from a single 50-query round (see
04-GAP-SPIKE-FORENSICS.md). This instrument gathers the hardware evidence that
discriminates the hypotheses, in five arms run in this order:

    control  -- prober only, no streaming, on the primary device. Establishes
                the ambient single-shot loss floor with ~240 queries (the
                spike baseline had only n=20).
    shipped  -- the exact 04-06 protocol (fresh `Animator.for_matrix()` per
                round, 20 FPS hue sweep, concurrent `DeviceConnection` prober)
                plus per-query and per-frame timestamped events.
    replica  -- spike 003's photons arm reproduced faithfully (separate
                asyncio `UdpTransport`, per-packet awaited sends, raw-socket
                prober) at >= 150 total queries, so a genuinely-0% methodology
                is distinguishable from the ~3.4% UAT rate.
    sweep    -- shipped-arm mechanics at 10 and 15 FPS. Tests whether loss
                scales with offered load.
    fallback -- a shorter control + shipped battery on the second Tiles
                device. Rules device-specific behaviour in or out.

Run:
    uv run python .planning/phases/04-animation-flow-control/\\
uat_loss_investigation.py \\
        --tiles-ip 192.168.19.243 --fallback-ip 192.168.18.62 \\
        --json-out .planning/phases/04-animation-flow-control/\\
04-GAP-INVESTIGATION.json \\
        --events-out .planning/phases/04-animation-flow-control/\\
04-GAP-INVESTIGATION-EVENTS.jsonl

Honest-reporting rules (04-06 precedent, fixed BEFORE any run):
    - The protocol constants below are final. This file is committed before
      any hardware run so the protocol is provably fixed pre-run.
    - Every arm's numbers are written verbatim to the JSON/JSONL outputs.
      There is no preferred result -- both directions discriminate.
    - Interpretation happens in 04-09 against its pre-declared rules, never
      here.

Provenance: the shipped-arm mechanics (prober, observer, reachability guard)
are copied from `uat_ack_stream.py`; the replica-arm mechanics (streamer,
collect_acks, raw prober) are copied from
`.planning/spikes/003-ack-paced-frames/stream.py`. Each copy is marked at the
definition it reproduces.

Ack RTT measurement note (shipped/sweep arms): `AckRttObserver` takes
read-only snapshots of `Animator._ack_gate._outstanding` once per
`send_frame()` call -- measurement-only private reach (03-03/04-05
precedent); RTT resolution is one frame tick, not the true wire RTT.
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
from typing import Any, Final, TextIO

from lifx.animation.animator import Animator
from lifx.animation.flow import ACK_EXPIRY_SECONDS, ACK_PKT_TYPE
from lifx.animation.packets import ACK_REQUIRED_FLAG, FLAGS_OFFSET, SEQUENCE_OFFSET
from lifx.const import LIFX_UDP_PORT, TIMEOUT_ERRORS
from lifx.devices.matrix import MatrixLight
from lifx.exceptions import LifxError, LifxTimeoutError
from lifx.network.connection import DeviceConnection
from lifx.network.message import create_message, parse_message
from lifx.network.transport import UdpTransport
from lifx.network.utils import allocate_source
from lifx.protocol import packets

# ---------------------------------------------------------------------------
# Fixed protocol constants -- declared (and committed) BEFORE the hardware
# run, honest-reporting precedent. None of these is a pass/fail threshold;
# they define only how much is measured and at what cadence.
# ---------------------------------------------------------------------------

# Seconds streamed per round in every streaming arm (04-06 round shape).
ROUND_SECONDS: Final[float] = 30.0
# Primary streaming rate -- the rate 04-06 measured and spike 003 used.
STREAM_FPS: Final[float] = 20.0
# Shipped-arm rounds: 4 x ~45 queries doubles the per-run sample of 04-06.
SHIPPED_ROUNDS: Final[int] = 4
# Replica-arm rounds: 4 x ~50 raw-prober queries targets >= 150 total, so a
# genuinely-0% methodology is distinguishable from ~3.4% (P(0/150) < 1%).
REPLICA_ROUNDS: Final[int] = 4
# FPS sweep values (shipped mechanics at reduced offered load).
SWEEP_FPS: Final[tuple[float, ...]] = (10.0, 15.0)
# Rounds per sweep FPS value.
SWEEP_ROUNDS_PER_FPS: Final[int] = 2
# Ambient control duration on the primary device (~240 queries at 2/s --
# the spike baseline had only n=20).
CONTROL_SECONDS: Final[float] = 120.0
# Shorter ambient control on the fallback device.
FALLBACK_CONTROL_SECONDS: Final[float] = 60.0
# Shipped rounds on the fallback device.
FALLBACK_SHIPPED_ROUNDS: Final[int] = 2
# Connection-prober queries per second (04-06 cadence; spike used 1/0.5 s).
QUERY_RATE: Final[float] = 2.0
# Connection-prober per-query timeout in seconds (04-06 value).
QUERY_TIMEOUT: Final[float] = 2.0
# Replica raw-prober timeout in seconds (spike 003 QUERY_TIMEOUT).
REPLICA_QUERY_TIMEOUT: Final[float] = 1.0
# Replica raw-prober inter-query rest in seconds (spike 003 QUERY_INTERVAL).
REPLICA_QUERY_INTERVAL: Final[float] = 0.5
# Rest between arms, seconds (spike rested 5 s between arms; be gentler).
INTER_ARM_REST_SECONDS: Final[float] = 10.0

# Replica-arm gate tuning, copied from spike 003 stream.py (identical to the
# shipped ACK_INFLIGHT_LIMIT / ACK_EXPIRY_SECONDS in src/lifx/animation/flow.py
# per D4-01 -- the gate constants are not a variable in this comparison).
PHOTONS_INFLIGHT_LIMIT: Final[int] = 2
PHOTONS_ACK_EXPIRY: Final[float] = 1.0

# Light.StateColor packet type, matched by the replica raw prober
# (spike 003 stream.py STATE_COLOR).
STATE_COLOR_PKT_TYPE: Final[int] = 107

# Canonical arm execution order (also the only accepted --arms values).
ARM_ORDER: Final[tuple[str, ...]] = (
    "control",
    "shipped",
    "replica",
    "sweep",
    "fallback",
)

# Reference numbers this investigation is compared against by 04-09 -- these
# are context for the reader of the JSON, never gates applied by this script.
REFERENCE: Final[dict[str, Any]] = {
    "spike_003_photons": {
        "queries": 50,
        "lost": 0,
        "rounds": 1,
        "source": ".planning/spikes/003-ack-paced-frames/results-20260716-210408.jsonl",
    },
    "uat_04_06_pooled": {
        "queries": 267,
        "lost": 9,
        "loss_pct": 3.37,
        "source": "04-UAT-TILES-run1-FAIL.json + 04-UAT-TILES.json",
    },
}


def _constants_block() -> dict[str, Any]:
    """The fixed protocol constants, recorded verbatim into the results JSON."""
    return {
        "round_seconds": ROUND_SECONDS,
        "stream_fps": STREAM_FPS,
        "shipped_rounds": SHIPPED_ROUNDS,
        "replica_rounds": REPLICA_ROUNDS,
        "sweep_fps": list(SWEEP_FPS),
        "sweep_rounds_per_fps": SWEEP_ROUNDS_PER_FPS,
        "control_seconds": CONTROL_SECONDS,
        "fallback_control_seconds": FALLBACK_CONTROL_SECONDS,
        "fallback_shipped_rounds": FALLBACK_SHIPPED_ROUNDS,
        "query_rate": QUERY_RATE,
        "query_timeout": QUERY_TIMEOUT,
        "replica_query_timeout": REPLICA_QUERY_TIMEOUT,
        "replica_query_interval": REPLICA_QUERY_INTERVAL,
        "inter_arm_rest_seconds": INTER_ARM_REST_SECONDS,
        "photons_inflight_limit": PHOTONS_INFLIGHT_LIMIT,
        "photons_ack_expiry": PHOTONS_ACK_EXPIRY,
    }


# ---------------------------------------------------------------------------
# Event capture -- one JSON object per line, flushed per event (at least once
# per round). Per-query and per-frame timestamps are the whole point of this
# instrument: 04-06's JSON only had counts.
# ---------------------------------------------------------------------------


class EventWriter:
    """Appends one JSON object per line to the events file, flushing each write."""

    def __init__(self, handle: TextIO) -> None:
        self._handle = handle

    def emit(self, **fields: Any) -> None:
        self._handle.write(json.dumps(fields) + "\n")
        self._handle.flush()


@dataclass(frozen=True)
class RoundContext:
    """Per-round event context shared by the prober and the frame loop.

    The `outcome` field on query events records the measured result of one
    query ("ok"/"lost") -- a raw observation, never a verdict.
    """

    events: EventWriter
    arm: str
    device_role: str  # "primary" | "fallback"
    fps: float | None  # None for control arms (no streaming)
    round_index: int
    round_start: float  # monotonic

    def emit_query(self, result: str, latency_ms: float | None) -> None:
        self.events.emit(
            arm=self.arm,
            device=self.device_role,
            fps=self.fps,
            round=self.round_index,
            kind="query",
            t=round(time.monotonic() - self.round_start, 4),
            outcome=result,
            latency_ms=latency_ms,
        )

    def emit_frame(self, gated: bool, outstanding: int) -> None:
        self.events.emit(
            arm=self.arm,
            device=self.device_role,
            fps=self.fps,
            round=self.round_index,
            kind="frame",
            t=round(time.monotonic() - self.round_start, 4),
            gated=gated,
            outstanding=outstanding,
        )


# ---------------------------------------------------------------------------
# Shared measurement plumbing.
# ---------------------------------------------------------------------------


@dataclass
class _QueryStats:
    """Concurrent single-shot query prober results for one round/block."""

    ok: int = 0
    lost: int = 0
    latencies_ms: list[float] = field(default_factory=list)


def _frame_hsbk(frame_index: int, pixel_count: int) -> list[tuple[int, int, int, int]]:
    """A moving hue-sweep frame, protocol-ready uint16 HSBK (spike 003 shape)."""
    step = 65536 // max(pixel_count, 1)
    return [
        ((frame_index * 800 + idx * step) % 65536, 65535, 16384, 3500)
        for idx in range(pixel_count)
    ]


def _pct(values: list[float], p: float) -> float:
    idx = min(len(values) - 1, math.ceil(len(values) * p) - 1)
    return sorted(values)[idx]


def _query_block(stats: _QueryStats) -> dict[str, Any]:
    """Per-round query aggregates from raw prober counts."""
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


def _ack_block(rtt_samples_ms: list[float], expiries: int) -> dict[str, Any]:
    """Per-round ack RTT aggregates."""
    return {
        "ack_rtt_median_ms": (
            round(statistics.median(rtt_samples_ms), 1) if rtt_samples_ms else None
        ),
        "ack_rtt_p95_ms": (
            round(_pct(rtt_samples_ms, 0.95), 1) if rtt_samples_ms else None
        ),
        "ack_rtt_samples": len(rtt_samples_ms),
        "ack_expiries": expiries,
    }


def _pooled(rounds: list[dict[str, Any]]) -> dict[str, Any]:
    """Pooled query counts across a list of per-round aggregate dicts."""
    ok = sum(r["queries_ok"] for r in rounds)
    lost = sum(r["queries_lost"] for r in rounds)
    total = ok + lost
    return {
        "queries_ok": ok,
        "queries_lost": lost,
        "query_loss_pct": round(100 * lost / total, 2) if total else None,
    }


async def _reachability_probe(device: MatrixLight, timeout: float) -> bool:
    """One generous-timeout GetColor probe on the normal (retrying) connection.

    Copied from uat_ack_stream.py `_reachability_probe` -- same guard shape.
    """
    try:
        await device.connection.request(packets.Light.GetColor(), timeout=timeout)
    except LifxError:
        return False
    return True


class AckRttObserver:
    """Measures probe ack RTT/expiry via read-only `AckGate` snapshots.

    Copied from uat_ack_stream.py `AckRttObserver` (04-05): `observe()` is
    called once per `send_frame()` and diffs the gate's live `_outstanding`
    dict (private-reach, measurement-only, 03-03 precedent) against the
    previous snapshot. A vanished sequence younger than `ACK_EXPIRY_SECONDS`
    was acked (RTT = now - sent_at); older means it expired. Resolution is
    one frame tick. Nothing on the animator or gate is ever mutated.
    """

    def __init__(self, animator: Animator) -> None:
        self._gate = animator._ack_gate  # noqa: SLF001 -- measurement-only
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


# ---------------------------------------------------------------------------
# Probers: connection prober (shipped/control/sweep/fallback arms) and the
# replica raw-socket prober.
# ---------------------------------------------------------------------------


async def connection_prober(
    ip: str,
    port: int,
    serial: str,
    stop: asyncio.Event,
    ctx: RoundContext,
) -> _QueryStats:
    """Concurrent single-shot GetColor prober on a dedicated connection.

    Copied from uat_ack_stream.py `query_prober` (the exact 04-06 prober),
    extended only to emit a timestamped event per query. `max_retries=0` is
    load-bearing: Phase 3's retransmit schedule must never mask loss here --
    this measures whether *this exact* query round-trips.
    """
    conn = DeviceConnection(
        serial=serial, ip=ip, port=port, max_retries=0, timeout=QUERY_TIMEOUT
    )
    stats = _QueryStats()
    interval = 1.0 / QUERY_RATE
    try:
        while not stop.is_set():
            sent = time.perf_counter()
            try:
                await conn.request(packets.Light.GetColor(), timeout=QUERY_TIMEOUT)
            except LifxError:
                stats.lost += 1
                ctx.emit_query("lost", None)
            else:
                latency_ms = (time.perf_counter() - sent) * 1000
                stats.ok += 1
                stats.latencies_ms.append(latency_ms)
                ctx.emit_query("ok", round(latency_ms, 1))
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except TIMEOUT_ERRORS:
                pass
    finally:
        await conn.close()
    return stats


async def replica_query_prober(
    ip: str,
    serial: bytes,
    stop: asyncio.Event,
    ctx: RoundContext,
) -> _QueryStats:
    """Concurrent GetColor prober on a raw socket -- spike 003's prober.

    Copied from spike 003 stream.py `query_prober` (source/sequence/pkt_type/
    addr matching, REPLICA_QUERY_TIMEOUT deadline, REPLICA_QUERY_INTERVAL
    rest), extended only to emit a timestamped event per query and to use the
    3.10-compatible TIMEOUT_ERRORS tuple for `wait_for`.
    """
    transport = UdpTransport(port=0, broadcast=False)
    await transport.open()
    source = allocate_source()
    stats = _QueryStats()
    seq = 0
    try:
        while not stop.is_set():
            seq = (seq + 1) % 256
            msg = create_message(
                packets.Light.GetColor(),
                source=source,
                target=serial,
                sequence=seq,
                res_required=True,
            )
            sent = time.perf_counter()
            await transport.send(msg, (ip, LIFX_UDP_PORT))
            deadline = sent + REPLICA_QUERY_TIMEOUT
            got = False
            while time.perf_counter() < deadline:
                try:
                    data, addr = await transport.receive(
                        timeout=deadline - time.perf_counter()
                    )
                except LifxTimeoutError:
                    break
                try:
                    header, _ = parse_message(data)
                except Exception:  # nosec B112 -- skip unparsable datagrams
                    continue
                if (
                    addr[0] == ip
                    and header.source == source
                    and header.pkt_type == STATE_COLOR_PKT_TYPE
                    and header.sequence == seq
                ):
                    latency_ms = (time.perf_counter() - sent) * 1000
                    stats.ok += 1
                    stats.latencies_ms.append(latency_ms)
                    ctx.emit_query("ok", round(latency_ms, 1))
                    got = True
                    break
            if not got:
                stats.lost += 1
                ctx.emit_query("lost", None)
            try:
                await asyncio.wait_for(stop.wait(), timeout=REPLICA_QUERY_INTERVAL)
            except TIMEOUT_ERRORS:
                pass
    finally:
        await transport.close()
    return stats


# ---------------------------------------------------------------------------
# Replica streaming path -- spike 003's photons arm, reproduced faithfully.
# ---------------------------------------------------------------------------


class ReplicaStreamer:
    """Sends animator-prebaked frame packets via an ack-capable transport.

    Copied from spike 003 stream.py `FrameStreamer`: reaches into animator
    privates for templates/framebuffer/generator (spike licence, measurement
    only). The shipped animator already bakes the ack flag onto its probe
    template; like the spike, `send_frame()` sets/clears the flags bit per
    packet, producing identical wire bytes on Tiles (probe on packet 0).
    """

    def __init__(self, animator: Animator, transport: UdpTransport) -> None:
        self.animator = animator
        self.transport = transport
        self.templates = animator._templates  # noqa: SLF001 -- spike licence
        self.framebuffer = animator._framebuffer  # noqa: SLF001
        self.generator = animator._packet_generator  # noqa: SLF001
        self.addr = (animator._ip, LIFX_UDP_PORT)  # noqa: SLF001
        self.sequence = 0
        self.pixels = animator.pixel_count

    async def send_frame(self, frame_i: int, ack_packet: int | None) -> int | None:
        """Send one frame with per-packet awaited sends (spike 003 send_frame).

        `ack_packet` selects which template carries the ack flag (index into
        templates, or None for pure blind fire). Returns the sequence number
        carrying the ack request, if any. The awaited `transport.send()` per
        packet yields to the event loop between the packets of a frame --
        the key mechanical difference from the shipped synchronous burst.
        """
        device_data = self.framebuffer.apply(_frame_hsbk(frame_i, self.pixels))
        self.generator.update_colors(self.templates, device_data)
        ack_seq: int | None = None
        for i, tmpl in enumerate(self.templates):
            tmpl.data[SEQUENCE_OFFSET] = self.sequence
            if ack_packet is not None and i == ack_packet:
                tmpl.data[FLAGS_OFFSET] |= ACK_REQUIRED_FLAG
                ack_seq = self.sequence
            else:
                tmpl.data[FLAGS_OFFSET] &= ~ACK_REQUIRED_FLAG
            self.sequence = (self.sequence + 1) % 256
            await self.transport.send(bytes(tmpl.data), self.addr)
        return ack_seq

    async def collect_acks(
        self, outstanding: dict[int, float]
    ) -> tuple[list[float], int]:
        """Non-blocking sweep of arrived acks (spike 003 collect_acks).

        Returns (RTTs in seconds, number of entries pruned by expiry). The
        expiry count is the only addition to the spike's version, so the
        aggregate JSON can record `ack_expiries` per round.
        """
        rtts: list[float] = []
        while True:
            try:
                data, _addr = await self.transport.receive(timeout=0.001)
            except LifxTimeoutError:
                break
            try:
                header, _ = parse_message(data)
            except Exception:  # nosec B112 -- skip unparsable datagrams
                continue
            if header.pkt_type == ACK_PKT_TYPE and header.sequence in outstanding:
                rtts.append(time.perf_counter() - outstanding.pop(header.sequence))
        now = time.perf_counter()
        expired = [s for s, t in outstanding.items() if now - t > PHOTONS_ACK_EXPIRY]
        for seq in expired:
            del outstanding[seq]
        return rtts, len(expired)


# ---------------------------------------------------------------------------
# Round runners.
# ---------------------------------------------------------------------------


async def run_control_block(
    device: MatrixLight,
    arm: str,
    device_role: str,
    seconds: float,
    events: EventWriter,
    round_index: int = 0,
) -> dict[str, Any]:
    """Prober-only block: no streaming, just the ambient single-shot floor."""
    ctx = RoundContext(events, arm, device_role, None, round_index, time.monotonic())
    stop = asyncio.Event()
    prober_task = asyncio.create_task(
        connection_prober(device.ip, device.port, device.serial, stop, ctx)
    )
    try:
        await asyncio.sleep(seconds)
    finally:
        stop.set()
        stats = await prober_task
    return {"round": round_index, "duration_s": seconds, **_query_block(stats)}


async def run_shipped_round(
    device: MatrixLight,
    arm: str,
    device_role: str,
    fps: float,
    round_index: int,
    events: EventWriter,
) -> dict[str, Any]:
    """One 04-06-shaped round: shipped Animator + concurrent connection prober.

    Mechanics copied from uat_ack_stream.py `run_round`/`stream_round`
    (fresh `Animator.for_matrix()` per round, monotonic-deadline ticks),
    extended only to emit per-frame events.
    """
    animator = await Animator.for_matrix(device)
    observer = AckRttObserver(animator)
    ctx = RoundContext(events, arm, device_role, fps, round_index, time.monotonic())
    stop = asyncio.Event()
    prober_task = asyncio.create_task(
        connection_prober(device.ip, device.port, device.serial, stop, ctx)
    )
    tick = 1.0 / fps
    pixels = animator.pixel_count
    offered = 0
    sent = 0
    gated = 0
    try:
        start = time.monotonic()
        while time.monotonic() - start < ROUND_SECONDS:
            frame = _frame_hsbk(offered, pixels)
            stats = animator.send_frame(frame)
            now = time.monotonic()
            offered += 1
            if stats.gated:
                gated += 1
            else:
                sent += 1
            observer.observe(now)
            ctx.emit_frame(gated=stats.gated, outstanding=stats.acks_outstanding)
            next_at = start + offered * tick
            await asyncio.sleep(max(0.0, next_at - time.monotonic()))
    finally:
        stop.set()
        query_stats = await prober_task
        animator.close()
    return {
        "round": round_index,
        "fps": fps,
        "offered": offered,
        "sent": sent,
        "gated": gated,
        "delivered_ratio": round(sent / offered, 4) if offered else 0.0,
        **_query_block(query_stats),
        **_ack_block(observer.rtt_samples_ms, observer.expiries),
    }


async def run_replica_round(
    device: MatrixLight,
    round_index: int,
    events: EventWriter,
) -> dict[str, Any]:
    """One spike-003-faithful photons round (stream.py `arm_photons`).

    Separate `UdpTransport` streaming socket, per-packet awaited sends, probe
    ack on packet 0, gate on PHOTONS_INFLIGHT_LIMIT outstanding, expiry after
    PHOTONS_ACK_EXPIRY, and the spike's raw-socket prober -- extended only to
    emit per-frame/per-query events.
    """
    animator = await Animator.for_matrix(device)
    transport = UdpTransport(port=0, broadcast=False)
    await transport.open()
    streamer = ReplicaStreamer(animator, transport)
    serial_bytes = bytes.fromhex(device.serial) + b"\x00\x00"
    ctx = RoundContext(
        events, "replica", "primary", STREAM_FPS, round_index, time.monotonic()
    )
    stop = asyncio.Event()
    prober_task = asyncio.create_task(
        replica_query_prober(device.ip, serial_bytes, stop, ctx)
    )
    tick = 1.0 / STREAM_FPS
    outstanding: dict[int, float] = {}
    rtt_samples_ms: list[float] = []
    expiries = 0
    offered = 0
    sent = 0
    gated = 0
    try:
        start = time.monotonic()
        while time.monotonic() - start < ROUND_SECONDS:
            new_rtts, expired = await streamer.collect_acks(outstanding)
            rtt_samples_ms.extend(rtt * 1000 for rtt in new_rtts)
            expiries += expired
            if len(outstanding) >= PHOTONS_INFLIGHT_LIMIT:
                gated += 1
                ctx.emit_frame(gated=True, outstanding=len(outstanding))
            else:
                ack_seq = await streamer.send_frame(offered, ack_packet=0)
                if ack_seq is not None:
                    outstanding[ack_seq] = time.perf_counter()
                sent += 1
                ctx.emit_frame(gated=False, outstanding=len(outstanding))
            offered += 1
            next_at = start + offered * tick
            await asyncio.sleep(max(0.0, next_at - time.monotonic()))
    finally:
        stop.set()
        query_stats = await prober_task
        await transport.close()
        animator.close()
    # The spike recorded leftover outstanding probes as ack_timeouts at round
    # end; count them with the expiries here.
    expiries += len(outstanding)
    return {
        "round": round_index,
        "fps": STREAM_FPS,
        "offered": offered,
        "sent": sent,
        "gated": gated,
        "delivered_ratio": round(sent / offered, 4) if offered else 0.0,
        **_query_block(query_stats),
        **_ack_block(rtt_samples_ms, expiries),
    }


# ---------------------------------------------------------------------------
# Arms.
# ---------------------------------------------------------------------------


async def arm_control(device: MatrixLight, events: EventWriter) -> dict[str, Any]:
    """Arm 1: ambient single-shot loss floor, no streaming, primary device."""
    print(f"arm=control: {CONTROL_SECONDS:.0f} s prober-only on primary")
    block = await run_control_block(
        device, "control", "primary", CONTROL_SECONDS, events
    )
    print(json.dumps(block, indent=2))
    return {"rounds": [block], "pooled": _pooled([block])}


async def arm_shipped(device: MatrixLight, events: EventWriter) -> dict[str, Any]:
    """Arm 2: the exact 04-06 protocol plus per-event capture."""
    rounds: list[dict[str, Any]] = []
    for i in range(SHIPPED_ROUNDS):
        print(f"arm=shipped round {i}: {ROUND_SECONDS:.0f} s @ {STREAM_FPS:.0f} FPS")
        result = await run_shipped_round(
            device, "shipped", "primary", STREAM_FPS, i, events
        )
        print(json.dumps(result, indent=2))
        rounds.append(result)
    return {"rounds": rounds, "pooled": _pooled(rounds)}


async def arm_replica(device: MatrixLight, events: EventWriter) -> dict[str, Any]:
    """Arm 3: spike 003's photons methodology at adequate sample size."""
    rounds: list[dict[str, Any]] = []
    for i in range(REPLICA_ROUNDS):
        print(f"arm=replica round {i}: {ROUND_SECONDS:.0f} s @ {STREAM_FPS:.0f} FPS")
        result = await run_replica_round(device, i, events)
        print(json.dumps(result, indent=2))
        rounds.append(result)
    return {"rounds": rounds, "pooled": _pooled(rounds)}


async def arm_sweep(device: MatrixLight, events: EventWriter) -> dict[str, Any]:
    """Arm 4: shipped mechanics at reduced FPS -- does loss scale with load?"""
    rounds: list[dict[str, Any]] = []
    for fps in SWEEP_FPS:
        for i in range(SWEEP_ROUNDS_PER_FPS):
            print(f"arm=sweep round {i}: {ROUND_SECONDS:.0f} s @ {fps:.0f} FPS")
            result = await run_shipped_round(device, "sweep", "primary", fps, i, events)
            print(json.dumps(result, indent=2))
            rounds.append(result)
    return {"rounds": rounds, "pooled": _pooled(rounds)}


async def arm_fallback(
    fallback_ip: str, events: EventWriter
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Arm 5: control + shipped rounds on the second Tiles device.

    Unreachability degrades to a recorded "env-error" arm status and the run
    CONTINUES -- the primary evidence stands alone.
    """
    print(f"arm=fallback: probing {fallback_ip}")
    try:
        device = await MatrixLight.from_ip(fallback_ip)
    except LifxError as exc:
        print(f"arm=fallback env-error: {exc}")
        return {
            "arm_status": "env-error",
            "reason": f"could not reach fallback device {fallback_ip}: {exc}",
        }, None
    async with device:
        if not await _reachability_probe(device, timeout=5.0):
            print(f"arm=fallback env-error: reachability probe to {fallback_ip} failed")
            return {
                "arm_status": "env-error",
                "reason": f"reachability probe to {fallback_ip} failed",
            }, None
        label = await device.get_label()
        chain = await device.get_device_chain()
        info: dict[str, Any] = {
            "ip": fallback_ip,
            "label": label,
            "chain_width": chain[0].width if chain else None,
            "chain_height": chain[0].height if chain else None,
        }
        print(f"arm=fallback: {FALLBACK_CONTROL_SECONDS:.0f} s control on {label}")
        control = await run_control_block(
            device, "fallback", "fallback", FALLBACK_CONTROL_SECONDS, events
        )
        print(json.dumps(control, indent=2))
        shipped_rounds: list[dict[str, Any]] = []
        for i in range(FALLBACK_SHIPPED_ROUNDS):
            print(
                f"arm=fallback shipped round {i}: "
                f"{ROUND_SECONDS:.0f} s @ {STREAM_FPS:.0f} FPS"
            )
            result = await run_shipped_round(
                device, "fallback", "fallback", STREAM_FPS, i, events
            )
            print(json.dumps(result, indent=2))
            shipped_rounds.append(result)
    return {
        "arm_status": "measured",
        "control": control,
        "shipped_rounds": shipped_rounds,
        "pooled": _pooled([control, *shipped_rounds]),
    }, info


# ---------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _write_json(path: Path, results: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2) + "\n")


def _parse_arms(raw: str) -> list[str]:
    """Validate and order the requested arm subset."""
    requested = [a.strip() for a in raw.split(",") if a.strip()]
    unknown = [a for a in requested if a not in ARM_ORDER]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown arm(s) {unknown}; valid arms: {', '.join(ARM_ORDER)}"
        )
    return [a for a in ARM_ORDER if a in requested]


async def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--tiles-ip",
        default="192.168.19.243",
        help="Primary Tiles device (the device 04-06 measured)",
    )
    parser.add_argument(
        "--fallback-ip",
        default="192.168.18.62",
        help="Second Tiles device for the fallback arm",
    )
    parser.add_argument(
        "--skip-fallback",
        action="store_true",
        help="Skip the fallback arm entirely",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        required=True,
        help="Path to write the per-arm aggregate JSON",
    )
    parser.add_argument(
        "--events-out",
        type=Path,
        required=True,
        help="Path to write the per-query/per-frame events JSONL",
    )
    parser.add_argument(
        "--arms",
        type=_parse_arms,
        default=list(ARM_ORDER),
        help=(
            "Comma-separated subset of arms to run "
            f"({','.join(ARM_ORDER)}; default: all five, in that order)"
        ),
    )
    args = parser.parse_args()
    selected: list[str] = list(args.arms)

    try:
        device = await MatrixLight.from_ip(args.tiles_ip)
    except LifxError as exc:
        print(
            f"ENV-ERROR: could not reach primary device {args.tiles_ip} ({exc}) -- "
            "not streaming, recording the skip honestly."
        )
        _write_json(
            args.json_out,
            {
                "timestamp": _now(),
                "tiles_ip": args.tiles_ip,
                "fallback_ip": args.fallback_ip,
                "skipped": True,
                "reason": f"could not reach primary device {args.tiles_ip}: {exc}",
                "protocol_constants": _constants_block(),
                "reference": REFERENCE,
            },
        )
        return 2

    fallback_info: dict[str, Any] | None = None
    async with device:
        reachable = await _reachability_probe(device, timeout=5.0)
        if not reachable:
            print(
                f"ENV-ERROR: {args.tiles_ip} did not respond to the reachability "
                "probe -- not streaming, recording the skip honestly."
            )
            _write_json(
                args.json_out,
                {
                    "timestamp": _now(),
                    "tiles_ip": args.tiles_ip,
                    "fallback_ip": args.fallback_ip,
                    "skipped": True,
                    "reason": f"reachability probe to {args.tiles_ip} failed",
                    "protocol_constants": _constants_block(),
                    "reference": REFERENCE,
                },
            )
            return 2

        label = await device.get_label()
        chain = await device.get_device_chain()
        primary_info: dict[str, Any] = {
            "ip": args.tiles_ip,
            "label": label,
            "chain_width": chain[0].width if chain else None,
            "chain_height": chain[0].height if chain else None,
        }
        print(f"primary: {label} ({args.tiles_ip}); arms: {', '.join(selected)}")

        arms: dict[str, Any] = {}
        args.events_out.parent.mkdir(parents=True, exist_ok=True)
        with args.events_out.open("w") as handle:
            events = EventWriter(handle)
            for index, arm in enumerate(selected):
                if index:
                    print(f"resting {INTER_ARM_REST_SECONDS:.0f} s between arms")
                    await asyncio.sleep(INTER_ARM_REST_SECONDS)
                if arm == "control":
                    arms["control"] = await arm_control(device, events)
                elif arm == "shipped":
                    arms["shipped"] = await arm_shipped(device, events)
                elif arm == "replica":
                    arms["replica"] = await arm_replica(device, events)
                elif arm == "sweep":
                    arms["sweep"] = await arm_sweep(device, events)
                elif arm == "fallback":
                    if args.skip_fallback:
                        print("arm=fallback skipped (--skip-fallback)")
                        arms["fallback"] = {
                            "arm_status": "skipped",
                            "reason": "--skip-fallback requested",
                        }
                    else:
                        arms["fallback"], fallback_info = await arm_fallback(
                            args.fallback_ip, events
                        )

    results: dict[str, Any] = {
        "timestamp": _now(),
        "tiles_ip": args.tiles_ip,
        "fallback_ip": args.fallback_ip,
        "arms_run": selected,
        "devices": {"primary": primary_info, "fallback": fallback_info},
        "protocol_constants": _constants_block(),
        "reference": REFERENCE,
        "arms": arms,
    }
    _write_json(args.json_out, results)
    print(f"measurement complete -- aggregates written to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
