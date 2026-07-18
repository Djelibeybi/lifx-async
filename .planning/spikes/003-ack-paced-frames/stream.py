"""Spike 003: ack-paced frame delivery vs blind fire, against real tiles.

Streams a 20 FPS hue-sweep animation to a matrix device for a fixed duration
under three delivery strategies, while a concurrent prober measures how
responsive the device stays to ordinary queries:

  blind   : lifx-async today — fire every frame's packets, never listen.
  glowup  : ack_required on the LAST packet of each frame; wait <=200 ms for
            the Acknowledgement before the next frame; latest-frame-wins
            (missed ticks are skipped, not queued); zero retransmits.
  photons : ack_required on the FIRST packet of each frame as a flow-control
            probe; a new frame is dropped while too many probe acks are
            outstanding (inflight limit 2); acks collected asynchronously.

The animation is watchable — judge visual smoothness live while the numbers
are collected.

Usage:
  uv run python .planning/spikes/003-ack-paced-frames/stream.py run \
      --host <tiles-ip> [--seconds 30] [--fps 20]

Results: JSONL event log + JSON summary in this directory.
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
from lifx.devices.matrix import MatrixLight
from lifx.exceptions import LifxTimeoutError
from lifx.network.message import create_message, parse_message
from lifx.network.transport import UdpTransport
from lifx.network.utils import allocate_source
from lifx.protocol.packets import Light as LightPackets

LIFX_PORT = 56700
ACK_TYPE = 45
STATE_COLOR = 107
FLAGS_OFFSET = 22  # header byte: bit0 res_required, bit1 ack_required
SEQ_OFFSET = 23
ACK_TIMEOUT = 0.2  # Glowup ACK_TIMEOUT
PHOTONS_INFLIGHT_LIMIT = 2
PHOTONS_ACK_EXPIRY = 1.0
QUERY_INTERVAL = 0.5
QUERY_TIMEOUT = 1.0
REST_BETWEEN_ARMS = 5.0

SPIKE_DIR = Path(__file__).parent


@dataclass
class EventLog:
    path: Path
    events: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, category: str, **fields: Any) -> None:
        event = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
            + f".{int(time.time() % 1 * 1000):03d}",
            "category": category,
            **fields,
        }
        self.events.append(event)
        with self.path.open("a") as f:
            f.write(json.dumps(event) + "\n")


@dataclass
class ArmStats:
    frames_target: int = 0
    frames_sent: int = 0
    frames_skipped: int = 0
    ack_rtts_ms: list[float] = field(default_factory=list)
    ack_timeouts: int = 0


class FrameStreamer:
    """Sends animator-prebaked frame packets via an ack-capable transport."""

    def __init__(self, animator: Animator, transport: UdpTransport) -> None:
        self.animator = animator
        self.transport = transport
        self.templates = animator._templates  # noqa: SLF001 — spike reaches into privates
        self.framebuffer = animator._framebuffer  # noqa: SLF001
        self.generator = animator._packet_generator  # noqa: SLF001
        self.addr = (animator._ip, LIFX_PORT)  # noqa: SLF001
        self.sequence = 0
        self.pixels = animator.pixel_count

    def frame_hsbk(self, frame_i: int) -> list[tuple[int, int, int, int]]:
        step = 65536 // max(self.pixels, 1)
        return [
            ((frame_i * 800 + idx * step) % 65536, 65535, 16384, 3500)
            for idx in range(self.pixels)
        ]

    async def send_frame(self, frame_i: int, ack_packet: int | None) -> int | None:
        """Send one frame; ack_packet selects which template gets the ack flag
        (index into templates, or None for pure blind fire). Returns the
        sequence number carrying the ack request, if any."""
        device_data = self.framebuffer.apply(self.frame_hsbk(frame_i))
        self.generator.update_colors(self.templates, device_data)
        ack_seq: int | None = None
        for i, tmpl in enumerate(self.templates):
            tmpl.data[SEQ_OFFSET] = self.sequence
            if ack_packet is not None and i == ack_packet:
                tmpl.data[FLAGS_OFFSET] |= 0x02
                ack_seq = self.sequence
            else:
                tmpl.data[FLAGS_OFFSET] &= ~0x02
            self.sequence = (self.sequence + 1) % 256
            await self.transport.send(bytes(tmpl.data), self.addr)
        return ack_seq

    async def wait_ack(self, seq: int, timeout: float) -> float | None:
        """Wait for the Acknowledgement matching seq; returns elapsed s or None."""
        deadline = time.perf_counter() + timeout
        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return None
            try:
                data, _addr = await self.transport.receive(timeout=remaining)
            except LifxTimeoutError:
                return None
            try:
                header, _ = parse_message(data)
            except Exception:  # nosec B112 — skip unparsable datagrams
                continue
            if header.pkt_type == ACK_TYPE and header.sequence == seq:
                return timeout - remaining

    async def collect_acks(self, outstanding: dict[int, float]) -> list[float]:
        """Non-blocking sweep of arrived acks; returns RTTs, prunes expired."""
        rtts = []
        while True:
            try:
                data, _addr = await self.transport.receive(timeout=0.001)
            except LifxTimeoutError:
                break
            try:
                header, _ = parse_message(data)
            except Exception:  # nosec B112 — skip unparsable datagrams
                continue
            if header.pkt_type == ACK_TYPE and header.sequence in outstanding:
                rtts.append(time.perf_counter() - outstanding.pop(header.sequence))
        now = time.perf_counter()
        for seq in [s for s, t in outstanding.items() if now - t > PHOTONS_ACK_EXPIRY]:
            del outstanding[seq]
        return rtts


async def arm_blind(streamer: FrameStreamer, seconds: float, fps: int) -> ArmStats:
    stats = ArmStats()
    tick = 1 / fps
    start = time.perf_counter()
    frame_i = 0
    while time.perf_counter() - start < seconds:
        await streamer.send_frame(frame_i, ack_packet=None)
        stats.frames_sent += 1
        frame_i += 1
        next_at = start + frame_i * tick
        await asyncio.sleep(max(0.0, next_at - time.perf_counter()))
    stats.frames_target = frame_i
    return stats


async def arm_glowup(streamer: FrameStreamer, seconds: float, fps: int) -> ArmStats:
    stats = ArmStats()
    tick = 1 / fps
    start = time.perf_counter()
    last_frame = -1
    while time.perf_counter() - start < seconds:
        # Latest-frame-wins: render whatever frame the clock says is current.
        frame_i = int((time.perf_counter() - start) / tick)
        stats.frames_skipped += max(0, frame_i - last_frame - 1)
        last_frame = frame_i
        ack_seq = await streamer.send_frame(
            frame_i, ack_packet=len(streamer.templates) - 1
        )
        stats.frames_sent += 1
        assert ack_seq is not None
        rtt = await streamer.wait_ack(ack_seq, ACK_TIMEOUT)
        if rtt is None:
            stats.ack_timeouts += 1
        else:
            stats.ack_rtts_ms.append(rtt * 1000)
        next_at = start + (frame_i + 1) * tick
        await asyncio.sleep(max(0.0, next_at - time.perf_counter()))
    stats.frames_target = int(seconds / tick)
    return stats


async def arm_photons(streamer: FrameStreamer, seconds: float, fps: int) -> ArmStats:
    stats = ArmStats()
    tick = 1 / fps
    start = time.perf_counter()
    outstanding: dict[int, float] = {}
    frame_i = 0
    while time.perf_counter() - start < seconds:
        for rtt in await streamer.collect_acks(outstanding):
            stats.ack_rtts_ms.append(rtt * 1000)
        if len(outstanding) >= PHOTONS_INFLIGHT_LIMIT:
            stats.frames_skipped += 1  # gated: too many probe acks outstanding
        else:
            ack_seq = await streamer.send_frame(frame_i, ack_packet=0)
            assert ack_seq is not None
            outstanding[ack_seq] = time.perf_counter()
            stats.frames_sent += 1
        frame_i += 1
        next_at = start + frame_i * tick
        await asyncio.sleep(max(0.0, next_at - time.perf_counter()))
    stats.frames_target = frame_i
    stats.ack_timeouts = len(outstanding)
    return stats


ARMS = {"blind": arm_blind, "glowup": arm_glowup, "photons": arm_photons}


async def query_prober(
    ip: str, serial: bytes, stop: asyncio.Event
) -> tuple[list[float], int]:
    """Concurrent GetColor prober on its own socket: (rtts_ms, losses)."""
    transport = UdpTransport(port=0, broadcast=False)
    await transport.open()
    source = allocate_source()
    rtts: list[float] = []
    losses = 0
    seq = 0
    try:
        while not stop.is_set():
            seq = (seq + 1) % 256
            msg = create_message(
                LightPackets.GetColor(),
                source=source,
                target=serial,
                sequence=seq,
                res_required=True,
            )
            sent = time.perf_counter()
            await transport.send(msg, (ip, LIFX_PORT))
            deadline = sent + QUERY_TIMEOUT
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
                except Exception:  # nosec B112 — skip unparsable datagrams
                    continue
                if (
                    addr[0] == ip
                    and header.source == source
                    and header.pkt_type == STATE_COLOR
                    and header.sequence == seq
                ):
                    rtts.append((time.perf_counter() - sent) * 1000)
                    got = True
                    break
            if not got:
                losses += 1
            try:
                await asyncio.wait_for(stop.wait(), timeout=QUERY_INTERVAL)
            except TimeoutError:
                pass
    finally:
        await transport.close()
    return rtts, losses


def pct(vals: list[float], p: float) -> float:
    idx = min(len(vals) - 1, math.ceil(len(vals) * p) - 1)
    return sorted(vals)[idx]


async def cmd_run(args: argparse.Namespace) -> None:
    run_id = time.strftime("%Y%m%d-%H%M%S")
    log = EventLog(SPIKE_DIR / f"results-{run_id}.jsonl")
    print(f"Run {run_id}: streaming {args.seconds}s per arm at {args.fps} FPS")
    print(f"Event log: {log.path}")

    async with await MatrixLight.from_ip(args.host) as device:
        label = await device.get_label()
        animator = await Animator.for_matrix(device)
        serial_bytes = bytes.fromhex(device.serial) + b"\x00\x00"
    transport = UdpTransport(port=0, broadcast=False)
    await transport.open()
    streamer = FrameStreamer(animator, transport)
    print(
        f"Target: {label} ({args.host}), {streamer.pixels} pixels, "
        f"{len(streamer.templates)} packets/frame"
    )
    log.emit(
        "run_start",
        host=args.host,
        label=label,
        pixels=streamer.pixels,
        packets_per_frame=len(streamer.templates),
        fps=args.fps,
        seconds=args.seconds,
    )

    # Baseline query responsiveness with no streaming.
    stop = asyncio.Event()
    baseline_task = asyncio.create_task(query_prober(args.host, serial_bytes, stop))
    await asyncio.sleep(args.seconds / 3)
    stop.set()
    base_rtts, base_losses = await baseline_task
    log.emit(
        "baseline",
        query_median_ms=round(statistics.median(base_rtts), 1) if base_rtts else None,
        query_p95_ms=round(pct(base_rtts, 0.95), 1) if base_rtts else None,
        losses=base_losses,
        n=len(base_rtts) + base_losses,
    )

    try:
        for arm_name, arm in ARMS.items():
            print(f"\n▶ arm={arm_name} — watch the tiles now")
            stop = asyncio.Event()
            prober = asyncio.create_task(query_prober(args.host, serial_bytes, stop))
            stats = await arm(streamer, args.seconds, args.fps)
            stop.set()
            query_rtts, query_losses = await prober
            queries = len(query_rtts) + query_losses
            event: dict[str, Any] = {
                "arm": arm_name,
                "frames_target": stats.frames_target,
                "frames_sent": stats.frames_sent,
                "frames_skipped": stats.frames_skipped,
                "ack_timeouts": stats.ack_timeouts,
                "query_n": queries,
                "query_loss_pct": round(100 * query_losses / queries, 1)
                if queries
                else None,
            }
            if stats.ack_rtts_ms:
                event["ack_ms"] = {
                    "median": round(statistics.median(stats.ack_rtts_ms), 1),
                    "p95": round(pct(stats.ack_rtts_ms, 0.95), 1),
                    "max": round(max(stats.ack_rtts_ms), 1),
                }
            if query_rtts:
                event["query_ms"] = {
                    "median": round(statistics.median(query_rtts), 1),
                    "p95": round(pct(query_rtts, 0.95), 1),
                    "max": round(max(query_rtts), 1),
                }
            log.emit("arm", **event)
            print(f"  {json.dumps(event, indent=2)}")
            await asyncio.sleep(REST_BETWEEN_ARMS)
    finally:
        await transport.close()
        animator.close()

    summary_path = SPIKE_DIR / f"summary-{run_id}.json"
    summary_path.write_text(
        json.dumps([e for e in log.events if e["category"] != "trial"], indent=2) + "\n"
    )
    print(f"\nSummary written to {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Stream the three arms")
    run.add_argument("--host", required=True, help="Matrix device IP")
    run.add_argument("--seconds", type=float, default=30.0)
    run.add_argument("--fps", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(cmd_run(args))


if __name__ == "__main__":
    main()
