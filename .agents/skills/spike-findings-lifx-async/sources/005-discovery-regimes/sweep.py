"""Spike 005: discovery broadcast schedules raced on a real fleet.

Three clients discover LIFX devices with radically different broadcast
schedules. This harness runs the SAME collector (one broadcast socket, dedup
by serial, first-seen timestamps) under each schedule, isolating the schedule
as the only variable:

  lifx-async : ONE GetService broadcast at t=0, then listen
               (src/lifx/network/discovery.py:233 — no re-broadcast).
  glowup     : wake burst 3x 0.1 s apart, then re-broadcast every 0.5 s for
               the whole window (transport.py:2521-2547).
  photons    : broadcasts on the escalating discovery schedule
               timeouts=[(0.6,1.8),(1,2),(2,6),(4,10),(5,20)] → within a 10 s
               window: t=0, 0.6, 1.8, 3.6, 5.6, 7.6, 9.6
               (session/network.py:93-98).

All rounds use the same fixed listen window so late responders are observed
for every regime; native early-exit rules are applied post-hoc from the
timestamps (e.g. lifx-async's 4 s idle deadline after its single broadcast).

Usage:
  uv run python .planning/spikes/005-discovery-regimes/sweep.py run \
      [--rounds 6] [--window 10] [--quick]

Results: JSONL event log + JSON summary in this directory.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lifx.exceptions import LifxTimeoutError
from lifx.network.message import create_message, parse_message
from lifx.network.transport import UdpTransport
from lifx.network.utils import allocate_source
from lifx.protocol.packets import Device as DevicePackets

LIFX_PORT = 56700
STATE_SERVICE = 3
BROADCAST = "255.255.255.255"
INTER_ROUND_GAP = 3.0

# lifx-async native idle deadline: IDLE_TIMEOUT_MULTIPLIER 4.0 x MAX_RESPONSE_TIME 1.0
LIFX_ASYNC_IDLE_S = 4.0

SPIKE_DIR = Path(__file__).parent


def schedule_lifx(window: float) -> list[float]:
    return [0.0]


def schedule_glowup(window: float) -> list[float]:
    times = [0.0, 0.1, 0.2]  # DISCOVERY_WAKE_BURSTS=3, DISCOVERY_WAKE_DELAY=0.1
    t = 0.5
    while t < window:  # DISCOVERY_INTERVAL=0.5
        times.append(round(t, 2))
        t += 0.5
    return times


def schedule_photons(window: float) -> list[float]:
    # Expansion of [(0.6,1.8),(1,2),(2,6),(4,10),(5,20)]: gaps 0.6, 1.2, 1.8,
    # then 2, then 2..6 by 2, then 4..10 by 4, then 5..20 by 5, then 20 forever.
    gaps = [0.6, 1.2, 1.8, 2.0, 2.0, 4.0, 6.0, 4.0, 8.0, 10.0, 5.0]
    times, t = [0.0], 0.0
    for g in gaps:
        t += g
        if t >= window:
            break
        times.append(round(t, 2))
    return times


SCHEDULES = {
    "lifx-async": schedule_lifx,
    "glowup": schedule_glowup,
    "photons": schedule_photons,
}


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


async def run_round(
    regime: str, window: float, log: EventLog, round_i: int
) -> dict[str, Any]:
    """One discovery round: broadcast on the regime's schedule, collect all."""
    schedule = SCHEDULES[regime](window)
    source = allocate_source()
    message = create_message(
        DevicePackets.GetService(), source=source, sequence=0, res_required=True
    )
    first_seen: dict[str, float] = {}
    responses = 0
    async with UdpTransport(port=0, broadcast=True) as transport:
        start = time.perf_counter()
        next_tx = iter(schedule)
        pending_tx: float | None = next(next_tx)
        while True:
            now = time.perf_counter() - start
            if now >= window:
                break
            # Send any due broadcasts.
            while pending_tx is not None and now >= pending_tx:
                await transport.send(message, (BROADCAST, LIFX_PORT))
                pending_tx = next(next_tx, None)
                now = time.perf_counter() - start
            wait = min(
                pending_tx - now if pending_tx is not None else window - now,
                window - now,
            )
            try:
                data, addr = await transport.receive(timeout=max(wait, 0.001))
            except LifxTimeoutError:
                continue
            try:
                header, _ = parse_message(data)
            except Exception:  # nosec B112 — skip unparsable datagrams
                continue
            if header.pkt_type != STATE_SERVICE or header.source != source:
                continue
            responses += 1
            serial = header.target[:6].hex()
            if serial not in first_seen:
                first_seen[serial] = round((time.perf_counter() - start) * 1000, 1)
    result = {
        "regime": regime,
        "round": round_i,
        "window_s": window,
        "broadcasts": len(schedule),
        "responses": responses,
        "found": len(first_seen),
        "first_seen_ms": first_seen,
    }
    log.emit("round", **result)
    return result


def apply_native_early_exit(result: dict[str, Any]) -> dict[str, Any]:
    """Coverage each regime would report under its native stop rule."""
    times = sorted(result["first_seen_ms"].values())
    out = {"window": result["found"]}
    if result["regime"] == "lifx-async":
        # Single broadcast + stop after a 4 s idle gap between responses.
        kept, last = 0, 0.0
        for t in times:
            if t - last > LIFX_ASYNC_IDLE_S * 1000:
                break
            kept += 1
            last = t
        out["native"] = kept
    else:
        out["native"] = result["found"]  # both use full fixed windows
    return out


def summarise(rounds: list[dict[str, Any]]) -> dict[str, Any]:
    roster: set[str] = set()
    for r in rounds:
        roster |= set(r["first_seen_ms"])
    summary: dict[str, Any] = {"roster_size": len(roster)}
    for regime in SCHEDULES:
        rs = [r for r in rounds if r["regime"] == regime]
        if not rs:
            continue
        found = [r["found"] for r in rs]
        native = [apply_native_early_exit(r)["native"] for r in rs]
        t90 = []
        for r in rs:
            times = sorted(r["first_seen_ms"].values())
            k = max(1, int(len(roster) * 0.9))
            if len(times) >= k:
                t90.append(times[k - 1])
        missed: dict[str, int] = {}
        for r in rs:
            for serial in roster - set(r["first_seen_ms"]):
                missed[serial] = missed.get(serial, 0) + 1
        summary[regime] = {
            "rounds": len(rs),
            "broadcasts_per_round": rs[0]["broadcasts"],
            "found_min_med_max": [min(found), statistics.median(found), max(found)],
            "native_rule_found_med": statistics.median(native),
            "t90_ms_med": statistics.median(t90) if t90 else None,
            "responses_per_round_med": statistics.median(r["responses"] for r in rs),
            "devices_missed_in_any_round": missed,
        }
    return summary


async def cmd_run(args: argparse.Namespace) -> None:
    run_id = time.strftime("%Y%m%d-%H%M%S")
    log = EventLog(SPIKE_DIR / f"results-{run_id}.jsonl")
    print(f"Run {run_id}: {args.rounds} rounds x {list(SCHEDULES)} x {args.window}s")
    print(f"Event log: {log.path}")
    rounds: list[dict[str, Any]] = []
    for i in range(args.rounds):
        for regime in SCHEDULES:
            result = await run_round(regime, args.window, log, i)
            print(
                f"  round {i} {regime:>10}: found {result['found']:>2} "
                f"({result['responses']} responses, {result['broadcasts']} broadcasts)"
            )
            rounds.append(result)
            await asyncio.sleep(INTER_ROUND_GAP)
    summary = summarise(rounds)
    summary_path = SPIKE_DIR / f"summary-{run_id}.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print(f"\nSummary written to {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run the discovery rounds")
    run.add_argument("--rounds", type=int, default=6)
    run.add_argument("--window", type=float, default=10.0)
    run.add_argument("--quick", action="store_true", help="Shakedown: 1 round")
    args = parser.parse_args()
    if args.quick:
        args.rounds = 1
    asyncio.run(cmd_run(args))


if __name__ == "__main__":
    main()
