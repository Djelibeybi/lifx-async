"""Spike 001: modem-sleep-keepalive — post-idle latency/loss measurement.

Measures whether LIFX bulbs respond slower (or drop packets) after an idle
period, and whether a Glowup-style unicast GetService keepalive removes the
effect. Two experiments per bulb, all bulbs concurrently:

  Experiment 1 (idle curve): probe first-command RTT/loss after increasing
  idle durations. If a WiFi power-save sleep onset exists, the curve shows a
  latency cliff at the onset threshold.

  Experiment 2 (keepalive A/B): alternate trials of a fixed idle period with
  and without keepalive bursts (2x GetService, 50 ms apart, every 15 s).

Every trial records the host's ARP-table state for the bulb immediately
before probing, to separate client-side ARP expiry from bulb-side effects.

Usage:
  uv run python .planning/spikes/001-modem-sleep-keepalive/probe.py discover
  uv run python .planning/spikes/001-modem-sleep-keepalive/probe.py run \
      --hosts 192.168.1.10,192.168.1.11 [--quick]

Results: JSONL event log + JSON summary in this directory.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import subprocess  # nosec B404 — fixed-argument arp(8) lookup only
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lifx.exceptions import LifxTimeoutError
from lifx.network.message import create_message, parse_message
from lifx.network.transport import UdpTransport
from lifx.network.utils import allocate_source
from lifx.protocol.packets import Device as DevicePackets
from lifx.protocol.packets import Light as LightPackets

LIFX_PORT = 56700
PROBE_TIMEOUT = 2.0  # parity with Glowup SOCKET_TIMEOUT
PROBE_TRAIN = 5  # probes per trial: #1 = post-idle, #2-5 = awake baseline
PROBE_GAP = 0.1  # gap between train probes (seconds)
KEEPALIVE_INTERVAL = 15.0  # Glowup KEEPALIVE_INTERVAL
KEEPALIVE_BURST = 2  # Glowup KEEPALIVE_BURST
KEEPALIVE_BURST_DELAY = 0.05  # Glowup KEEPALIVE_BURST_DELAY

SPIKE_DIR = Path(__file__).parent


@dataclass
class EventLog:
    path: Path
    events: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, category: str, bulb: str, **fields: Any) -> None:
        event = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
            + f".{int(time.time() % 1 * 1000):03d}",
            "category": category,
            "bulb": bulb,
            **fields,
        }
        self.events.append(event)
        with self.path.open("a") as f:
            f.write(json.dumps(event) + "\n")


def arp_state(ip: str) -> str:
    """Host ARP-table state for ip: resolved | incomplete | absent | error."""
    try:
        out = subprocess.run(  # nosec B603 B607 — fixed argv, no shell, ip is operator-supplied
            ["arp", "-n", ip], capture_output=True, text=True, timeout=5
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return "error"
    if "no entry" in out or not out.strip():
        return "absent"
    if "incomplete" in out:
        return "incomplete"
    return "resolved"


class BulbProber:
    """One persistent unicast socket per bulb (parity with both libraries)."""

    def __init__(self, ip: str, log: EventLog) -> None:
        self.ip = ip
        self.log = log
        self.source = allocate_source()
        self.sequence = 0
        self.serial = b"\x00" * 8
        self.label = ""
        self.transport = UdpTransport(port=0, broadcast=False)

    def _next_seq(self) -> int:
        self.sequence = (self.sequence + 1) % 256
        return self.sequence

    async def _drain(self) -> int:
        """Discard queued datagrams (stale keepalive responses etc.)."""
        drained = 0
        while True:
            try:
                await self.transport.receive(timeout=0.01)
                drained += 1
            except LifxTimeoutError:
                return drained

    async def resolve(self) -> None:
        """Learn serial + label via GetService/GetColor. Wakes the bulb."""
        await self.transport.open()
        msg = create_message(
            DevicePackets.GetService(),
            source=self.source,
            sequence=self._next_seq(),
            res_required=True,
        )
        for attempt in range(3):
            await self.transport.send(msg, (self.ip, LIFX_PORT))
            try:
                while True:
                    data, addr = await self.transport.receive(timeout=2.0)
                    header, _ = parse_message(data)
                    if addr[0] == self.ip and header.pkt_type == 3:
                        self.serial = header.target
                        break
                break
            except LifxTimeoutError:
                if attempt == 2:
                    raise
        rtt, extra = await self.probe()
        if rtt is None:
            raise LifxTimeoutError(f"{self.ip}: no GetColor response during resolve")
        self.label = extra.get("label", "")
        await self._drain()

    async def probe(self) -> tuple[float | None, dict[str, Any]]:
        """One single-shot GetColor (101) -> StateColor (107). No retries.

        Returns (rtt_seconds | None-on-loss, extras).
        """
        await self._drain()
        seq = self._next_seq()
        msg = create_message(
            LightPackets.GetColor(),
            source=self.source,
            target=self.serial,
            sequence=seq,
            res_required=True,
        )
        start = time.perf_counter()
        await self.transport.send(msg, (self.ip, LIFX_PORT))
        deadline = start + PROBE_TIMEOUT
        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return None, {"seq": seq}
            try:
                data, addr = await self.transport.receive(timeout=remaining)
            except LifxTimeoutError:
                return None, {"seq": seq}
            rtt = time.perf_counter() - start
            try:
                header, payload = parse_message(data)
            except Exception:  # nosec B112 — skip unparsable datagrams, keep waiting
                continue
            if (
                addr[0] == self.ip
                and header.source == self.source
                and header.pkt_type == 107
            ):
                state = LightPackets.StateColor.unpack(payload)
                # Library convention: user-visible fields are already str.
                raw = state.label
                label = (
                    raw.rstrip("\x00")
                    if isinstance(raw, str)
                    else raw.rstrip(b"\x00").decode("utf-8", "replace")
                )
                return rtt, {
                    "seq": seq,
                    "matched_seq": header.sequence == seq,
                    "label": label,
                    "power": state.power,
                }

    async def keepalive_burst(self) -> None:
        """Glowup-style burst: 2x unicast GetService, 50 ms apart."""
        msg = create_message(
            DevicePackets.GetService(),
            source=self.source,
            target=self.serial,
            sequence=self._next_seq(),
            res_required=True,
        )
        for i in range(KEEPALIVE_BURST):
            await self.transport.send(msg, (self.ip, LIFX_PORT))
            if i < KEEPALIVE_BURST - 1:
                await asyncio.sleep(KEEPALIVE_BURST_DELAY)

    async def idle(self, seconds: float, keepalive: bool) -> None:
        """Idle period; optionally sending keepalive bursts every 15 s."""
        end = time.monotonic() + seconds
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            if keepalive:
                wait = min(remaining, KEEPALIVE_INTERVAL)
                await asyncio.sleep(wait)
                if time.monotonic() < end:
                    await self.keepalive_burst()
            else:
                await asyncio.sleep(remaining)

    async def trial(self, phase: str, idle_s: float, keepalive: bool) -> None:
        """One trial: idle -> ARP snapshot -> probe train -> log."""
        await self.idle(idle_s, keepalive)
        arp = arp_state(self.ip)
        rtts: list[float | None] = []
        extras: list[dict[str, Any]] = []
        for _ in range(PROBE_TRAIN):
            rtt, extra = await self.probe()
            rtts.append(rtt)
            extras.append(extra)
            await asyncio.sleep(PROBE_GAP)
        self.log.emit(
            "trial",
            self.ip,
            phase=phase,
            label=self.label,
            idle_s=idle_s,
            keepalive=keepalive,
            arp_before=arp,
            rtts_ms=[round(r * 1000, 2) if r is not None else None for r in rtts],
            first_probe_ms=round(rtts[0] * 1000, 2) if rtts[0] is not None else None,
            first_probe_lost=rtts[0] is None,
            losses=sum(1 for r in rtts if r is None),
        )

    async def run_idle_curve(self, steps: list[float], trials: int) -> None:
        for step in steps:
            for _ in range(trials):
                await self.trial("idle_curve", step, keepalive=False)

    async def run_keepalive_ab(self, idle_s: float, trials_per_cond: int) -> None:
        for i in range(trials_per_cond * 2):
            keepalive = i % 2 == 1  # alternate A/B to control for drift
            await self.trial("keepalive_ab", idle_s, keepalive)

    async def close(self) -> None:
        await self.transport.close()


def summarise(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate trial events into per-bulb, per-phase, per-condition stats."""
    summary: dict[str, Any] = {}
    trials = [e for e in events if e["category"] == "trial"]
    for e in trials:
        if e["phase"] == "idle_curve":
            key = f"idle={e['idle_s']:g}s"
        else:
            key = "keepalive" if e["keepalive"] else "no-keepalive"
        bucket = (
            summary.setdefault(f"{e['bulb']} ({e['label']})", {})
            .setdefault(e["phase"], {})
            .setdefault(key, {"first_ms": [], "later_ms": [], "lost_first": 0, "n": 0})
        )
        bucket["n"] += 1
        if e["first_probe_lost"]:
            bucket["lost_first"] += 1
        else:
            bucket["first_ms"].append(e["first_probe_ms"])
        bucket["later_ms"].extend(r for r in e["rtts_ms"][1:] if r is not None)
    for bulb in summary.values():
        for phase in bulb.values():
            for stats in phase.values():
                for k in ("first_ms", "later_ms"):
                    vals = stats.pop(k)
                    if vals:
                        stats[k.replace("_ms", "")] = {
                            "median_ms": round(statistics.median(vals), 2),
                            "p95_ms": round(
                                sorted(vals)[
                                    min(len(vals) - 1, math.ceil(len(vals) * 0.95) - 1)
                                ],
                                2,
                            ),
                            "max_ms": round(max(vals), 2),
                        }
                stats["first_loss_pct"] = round(
                    100 * stats["lost_first"] / stats["n"], 1
                )
    return summary


def print_summary(summary: dict[str, Any]) -> None:
    for bulb, phases in summary.items():
        print(f"\n=== {bulb} ===")
        for phase, conditions in phases.items():
            print(f"  {phase}:")
            for cond, s in conditions.items():
                first = s.get("first", {})
                later = s.get("later", {})
                print(
                    f"    {cond:>16}: n={s['n']:>2}  "
                    f"first-loss={s['first_loss_pct']:>5.1f}%  "
                    f"first med={first.get('median_ms', '-'):>8} "
                    f"p95={first.get('p95_ms', '-'):>8} "
                    f"max={first.get('max_ms', '-'):>8}  "
                    f"| awake med={later.get('median_ms', '-')}"
                )


async def run_bulb(
    ip: str, log: EventLog, args: argparse.Namespace, stagger: float
) -> None:
    await asyncio.sleep(stagger)
    prober = BulbProber(ip, log)
    try:
        await prober.resolve()
        log.emit("resolved", ip, label=prober.label, serial=prober.serial.hex())
        if not args.skip_curve:
            await prober.run_idle_curve(args.idle_steps, args.curve_trials)
        if not args.skip_ab:
            await prober.run_keepalive_ab(args.ab_idle, args.ab_trials)
    except Exception as e:
        log.emit("error", ip, error=f"{type(e).__name__}: {e}")
        raise
    finally:
        await prober.close()


async def cmd_run(args: argparse.Namespace) -> None:
    run_id = time.strftime("%Y%m%d-%H%M%S")
    log = EventLog(SPIKE_DIR / f"results-{run_id}.jsonl")
    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
    curve_s = sum(args.idle_steps) * args.curve_trials if not args.skip_curve else 0
    ab_s = args.ab_idle * args.ab_trials * 2 if not args.skip_ab else 0
    est_min = (curve_s + ab_s) / 60 + 2
    print(f"Run {run_id}: {len(hosts)} bulb(s), estimated ~{est_min:.0f} min")
    print(f"Event log: {log.path}")
    log.emit(
        "run_start",
        "-",
        hosts=hosts,
        idle_steps=args.idle_steps,
        curve_trials=args.curve_trials,
        ab_idle=args.ab_idle,
        ab_trials=args.ab_trials,
    )
    results = await asyncio.gather(
        *(run_bulb(ip, log, args, i * 3.0) for i, ip in enumerate(hosts)),
        return_exceptions=True,
    )
    for ip, result in zip(hosts, results):
        if isinstance(result, BaseException):
            print(f"!! {ip}: {type(result).__name__}: {result}", file=sys.stderr)
    summary = summarise(log.events)
    summary_path = SPIKE_DIR / f"summary-{run_id}.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print_summary(summary)
    print(f"\nSummary written to {summary_path}")


async def cmd_discover(_args: argparse.Namespace) -> None:
    from lifx import discover

    print("Discovering devices (broadcast)...")
    async for device in discover():
        async with device:
            label = await device.get_label()
            print(f"  {device.ip:>15}  {device.serial}  {label}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("discover", help="List devices on the network")
    run = sub.add_parser("run", help="Run the experiments")
    run.add_argument("--hosts", required=True, help="Comma-separated bulb IPs")
    run.add_argument(
        "--idle-steps",
        default="0,5,10,15,30,60,120",
        help="Idle-curve durations in seconds (comma-separated)",
    )
    run.add_argument("--curve-trials", type=int, default=5)
    run.add_argument("--ab-idle", type=float, default=60.0)
    run.add_argument("--ab-trials", type=int, default=5, help="Trials per condition")
    run.add_argument("--skip-curve", action="store_true")
    run.add_argument("--skip-ab", action="store_true")
    run.add_argument(
        "--quick", action="store_true", help="Shakedown: tiny steps and trial counts"
    )
    args = parser.parse_args()
    if args.command == "discover":
        asyncio.run(cmd_discover(args))
        return
    if args.quick:
        args.idle_steps = "0,10,30"
        args.curve_trials = 2
        args.ab_idle = 20.0
        args.ab_trials = 2
    args.idle_steps = [float(s) for s in str(args.idle_steps).split(",")]
    asyncio.run(cmd_run(args))


if __name__ == "__main__":
    main()
