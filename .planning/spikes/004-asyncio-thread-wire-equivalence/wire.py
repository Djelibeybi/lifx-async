"""Spike 004: asyncio vs threading — does the concurrency model touch the wire?

Runs the SAME two workloads against the same bulb from an asyncio sender and a
threaded blocking-socket sender (Glowup-style), and compares what the wire and
the bulb can observe:

  Workload A (request/response): GetColor probes at a fixed rate, single
  in-flight, RTT recorded per probe. Measures how promptly each model drains
  responses.

  Workload B (paced stream): fire-and-forget packets on a strict 20 FPS tick
  for a fixed duration; the scheduled-vs-actual send offset is recorded per
  packet. Measures send-timing jitter — what frame pacing looks like to a bulb.

Both workloads optionally run under matched in-process load (--load K): K
concurrent tasks/threads each burning ~2 ms CPU then yielding for 10 ms —
the same application logic expressed in each concurrency model. This models
the "busy Home Assistant event loop" hypothesis fairly.

Usage:
  uv run python .planning/spikes/004-asyncio-thread-wire-equivalence/wire.py run \
      --host <bulb-ip> [--probes 300] [--rate 20] [--seconds 30] [--load 0]

Results: JSONL event log + JSON summary in this directory.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import socket
import statistics
import threading
import time
from pathlib import Path
from typing import Any

from lifx.exceptions import LifxTimeoutError
from lifx.network.message import create_message, parse_message
from lifx.network.transport import UdpTransport
from lifx.network.utils import allocate_source
from lifx.protocol.packets import Light as LightPackets

LIFX_PORT = 56700
STATE_COLOR = 107
PROBE_TIMEOUT = 2.0
LOAD_CPU_S = 0.002
LOAD_YIELD_S = 0.01

SPIKE_DIR = Path(__file__).parent


def _burn_cpu(seconds: float) -> None:
    end = time.perf_counter() + seconds
    x = 0
    while time.perf_counter() < end:
        x += 1


def _probe_message(source: int, serial: bytes, seq: int) -> bytes:
    return create_message(
        LightPackets.GetColor(),
        source=source,
        target=serial,
        sequence=seq,
        res_required=True,
    )


def _stream_message(source: int, serial: bytes, seq: int) -> bytes:
    return create_message(
        LightPackets.GetColor(),
        source=source,
        target=serial,
        sequence=seq,
        res_required=False,  # fire-and-forget: no response traffic
    )


# ---------------------------------------------------------------- threaded arm


def threaded_arm(
    ip: str, serial: bytes, probes: int, rate: float, seconds: float, load: int
) -> dict[str, Any]:
    stop_load = threading.Event()

    def load_worker() -> None:
        while not stop_load.is_set():
            _burn_cpu(LOAD_CPU_S)
            time.sleep(LOAD_YIELD_S)

    workers = [threading.Thread(target=load_worker, daemon=True) for _ in range(load)]
    for w in workers:
        w.start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(PROBE_TIMEOUT)
    source = allocate_source()
    rtts: list[float] = []
    losses = 0
    try:
        # Workload A: paced request/response, single in-flight.
        interval = 1.0 / rate
        next_at = time.perf_counter()
        for i in range(probes):
            seq = i % 256
            msg = _probe_message(source, serial, seq)
            sent = time.perf_counter()
            sock.sendto(msg, (ip, LIFX_PORT))
            deadline = sent + PROBE_TIMEOUT
            got = False
            while time.perf_counter() < deadline:
                try:
                    sock.settimeout(max(deadline - time.perf_counter(), 0.001))
                    data, addr = sock.recvfrom(1500)
                except TimeoutError:
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
            next_at += interval
            time.sleep(max(0.0, next_at - time.perf_counter()))

        # Workload B: strict-tick fire-and-forget stream.
        jitter: list[float] = []
        tick = 1.0 / rate
        start = time.perf_counter()
        n_frames = int(seconds * rate)
        for i in range(n_frames):
            scheduled = start + i * tick
            time.sleep(max(0.0, scheduled - time.perf_counter()))
            actual = time.perf_counter()
            sock.sendto(_stream_message(source, serial, i % 256), (ip, LIFX_PORT))
            jitter.append((actual - scheduled) * 1000)
    finally:
        stop_load.set()
        sock.close()
    return {"rtts_ms": rtts, "losses": losses, "jitter_ms": jitter}


# ----------------------------------------------------------------- asyncio arm


async def asyncio_arm(
    ip: str, serial: bytes, probes: int, rate: float, seconds: float, load: int
) -> dict[str, Any]:
    stop_load = asyncio.Event()

    async def load_worker() -> None:
        while not stop_load.is_set():
            _burn_cpu(LOAD_CPU_S)
            await asyncio.sleep(LOAD_YIELD_S)

    workers = [asyncio.create_task(load_worker()) for _ in range(load)]

    transport = UdpTransport(port=0, broadcast=False)
    await transport.open()
    source = allocate_source()
    rtts: list[float] = []
    losses = 0
    try:
        interval = 1.0 / rate
        next_at = time.perf_counter()
        for i in range(probes):
            seq = i % 256
            msg = _probe_message(source, serial, seq)
            sent = time.perf_counter()
            await transport.send(msg, (ip, LIFX_PORT))
            deadline = sent + PROBE_TIMEOUT
            got = False
            while time.perf_counter() < deadline:
                try:
                    data, addr = await transport.receive(
                        timeout=max(deadline - time.perf_counter(), 0.001)
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
            next_at += interval
            await asyncio.sleep(max(0.0, next_at - time.perf_counter()))

        jitter: list[float] = []
        tick = 1.0 / rate
        start = time.perf_counter()
        n_frames = int(seconds * rate)
        for i in range(n_frames):
            scheduled = start + i * tick
            await asyncio.sleep(max(0.0, scheduled - time.perf_counter()))
            actual = time.perf_counter()
            await transport.send(
                _stream_message(source, serial, i % 256), (ip, LIFX_PORT)
            )
            jitter.append((actual - scheduled) * 1000)
    finally:
        stop_load.set()
        for w in workers:
            w.cancel()
        await transport.close()
    return {"rtts_ms": rtts, "losses": losses, "jitter_ms": jitter}


# -------------------------------------------------------------------- plumbing


def pct(vals: list[float], p: float) -> float:
    idx = min(len(vals) - 1, math.ceil(len(vals) * p) - 1)
    return sorted(vals)[idx]


def stats_block(vals: list[float]) -> dict[str, float]:
    return {
        "median": round(statistics.median(vals), 2),
        "p95": round(pct(vals, 0.95), 2),
        "p99": round(pct(vals, 0.99), 2),
        "max": round(max(vals), 2),
    }


def resolve_serial(ip: str) -> bytes:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    source = allocate_source()
    msg = create_message(
        LightPackets.GetColor(), source=source, sequence=0, res_required=True
    )
    try:
        for _ in range(3):
            sock.sendto(msg, (ip, LIFX_PORT))
            try:
                while True:
                    data, addr = sock.recvfrom(1500)
                    header, _ = parse_message(data)
                    if addr[0] == ip and header.pkt_type == STATE_COLOR:
                        return header.target
            except TimeoutError:
                continue
        raise TimeoutError(f"{ip}: no response while resolving serial")
    finally:
        sock.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run both arms")
    run.add_argument("--host", required=True, help="Bulb IP")
    run.add_argument("--probes", type=int, default=300)
    run.add_argument("--rate", type=float, default=20.0)
    run.add_argument("--seconds", type=float, default=30.0)
    run.add_argument("--load", type=int, default=0, help="Concurrent load workers")
    run.add_argument("--quick", action="store_true", help="Shakedown: small counts")
    args = parser.parse_args()
    if args.quick:
        args.probes, args.seconds = 40, 5.0

    run_id = time.strftime("%Y%m%d-%H%M%S")
    serial = resolve_serial(args.host)
    results: dict[str, Any] = {
        "host": args.host,
        "probes": args.probes,
        "rate": args.rate,
        "seconds": args.seconds,
        "load": args.load,
    }
    print(f"Run {run_id}: {args.host}, load={args.load}")

    print("▶ threaded arm")
    threaded = threaded_arm(
        args.host, serial, args.probes, args.rate, args.seconds, args.load
    )
    time.sleep(2.0)
    print("▶ asyncio arm")
    async_res = asyncio.run(
        asyncio_arm(args.host, serial, args.probes, args.rate, args.seconds, args.load)
    )

    for name, res in (("threaded", threaded), ("asyncio", async_res)):
        results[name] = {
            "rtt_ms": stats_block(res["rtts_ms"]) if res["rtts_ms"] else None,
            "losses": res["losses"],
            "probe_n": len(res["rtts_ms"]) + res["losses"],
            "send_jitter_ms": stats_block(res["jitter_ms"])
            if res["jitter_ms"]
            else None,
        }
        print(f"  {name}: {json.dumps(results[name])}")

    out = SPIKE_DIR / f"summary-{run_id}-load{args.load}.json"
    out.write_text(json.dumps(results, indent=2) + "\n")
    print(f"Summary written to {out}")


if __name__ == "__main__":
    main()
