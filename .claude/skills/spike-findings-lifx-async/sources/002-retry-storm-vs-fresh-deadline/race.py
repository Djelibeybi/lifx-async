"""Spike 002: retry regimes raced under injected loss, against real bulbs.

Faithfully replicates the retransmit regime of three LIFX clients and races
them on the same bulbs under client-side Bernoulli loss injection:

  lifx-async : 9 attempts; per-attempt window = (timeout/511) * 2^n
               (~31 ms, 63 ms, ... 8 s; budget 16 s); jittered sleep between
               attempts (uniform(0, 0.1*2^n), excluded from budget); fresh
               sequence per attempt; late replies to earlier attempts accepted.
  glowup     : 3 attempts, each a fresh 2.0 s deadline, no inter-attempt
               sleep; responses matched on packet type only, so late replies
               from earlier attempts are also accepted.
  photons    : continuous retransmits at escalating gaps (0.2, 0.3, 0.4, 0.5,
               0.7, 0.9, 1.0, 2, 3, 4, then every 5 s) until a 10 s message
               timeout; fresh sequence per retransmit; first reply wins.

Loss injection: each direction (send, receive) independently drops with the
configured per-direction probability. Offered sends are counted as wire
pressure whether or not the injector drops them (models loss in transit).

Usage:
  uv run python .planning/spikes/002-retry-storm-vs-fresh-deadline/race.py run \
      --hosts <gen2-ip>,<gen3-ip>,<gen4-ip> [--loss-rates 0,0.25,0.5] [--trials 20]

Results: JSONL event log + JSON summary in this directory.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lifx.exceptions import LifxTimeoutError
from lifx.network.message import create_message, parse_message
from lifx.network.transport import UdpTransport
from lifx.network.utils import allocate_source
from lifx.protocol.packets import Light as LightPackets

LIFX_PORT = 56700
STATE_COLOR = 107
INTER_TRIAL_GAP = 0.5

# lifx-async constants (src/lifx/const.py, network/connection.py)
LIFX_ASYNC_TIMEOUT = 16.0
LIFX_ASYNC_MAX_RETRIES = 8
LIFX_ASYNC_SLEEP_BASE = 0.1

# Glowup constants (transport.py)
GLOWUP_ATTEMPTS = 3
GLOWUP_DEADLINE = 2.0

# Photons constants (photons_transport/targets/__init__.py retry gaps expanded)
PHOTONS_GAPS = [0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1.0, 2.0, 3.0, 4.0, 5.0]
PHOTONS_TIMEOUT = 10.0

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


@dataclass
class TrialResult:
    success: bool
    elapsed_s: float
    packets_offered: int
    satisfied_by_tx: int | None  # which transmission (1-based) won, if known


class LossyProber:
    """Persistent per-bulb socket with per-direction Bernoulli loss injection."""

    def __init__(self, ip: str, loss: float, rng: random.Random) -> None:
        self.ip = ip
        self.loss = loss
        self.rng = rng
        self.serial = b"\x00" * 8
        self.label = ""
        self.transport = UdpTransport(port=0, broadcast=False)
        self.offered = 0

    async def open(self) -> None:
        await self.transport.open()
        # Resolve serial/label loss-free.
        source = allocate_source()
        msg = create_message(
            LightPackets.GetColor(), source=source, sequence=0, res_required=True
        )
        for attempt in range(5):
            await self.transport.send(msg, (self.ip, LIFX_PORT))
            try:
                while True:
                    data, addr = await self.transport.receive(timeout=2.0)
                    header, payload = parse_message(data)
                    if addr[0] == self.ip and header.pkt_type == STATE_COLOR:
                        self.serial = header.target
                        state = LightPackets.StateColor.unpack(payload)
                        raw = state.label
                        self.label = (
                            raw.rstrip("\x00")
                            if isinstance(raw, str)
                            else raw.rstrip(b"\x00").decode("utf-8", "replace")
                        )
                        return
            except LifxTimeoutError:
                if attempt == 4:
                    raise

    async def send(self, source: int, sequence: int) -> None:
        """Offer one GetColor to the wire; injector may drop it in transit."""
        self.offered += 1
        if self.rng.random() < self.loss:
            return  # lost in transit — bulb never sees it
        msg = create_message(
            LightPackets.GetColor(),
            source=source,
            target=self.serial,
            sequence=sequence,
            res_required=True,
        )
        await self.transport.send(msg, (self.ip, LIFX_PORT))

    async def recv(self, timeout: float, accept: Any) -> tuple[int, int] | None:
        """Wait up to timeout for an accepted response; returns (source, seq).

        `accept(header) -> bool` implements each regime's matching rule.
        Accepted responses are dropped with the injected loss probability
        (models response lost in transit).
        """
        deadline = time.perf_counter() + timeout
        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return None
            try:
                data, addr = await self.transport.receive(timeout=remaining)
            except LifxTimeoutError:
                return None
            try:
                header, _ = parse_message(data)
            except Exception:  # nosec B112 — skip unparsable datagrams
                continue
            if addr[0] != self.ip or header.pkt_type != STATE_COLOR:
                continue
            if not accept(header):
                continue
            if self.rng.random() < self.loss:
                continue  # response lost in transit
            return header.source, header.sequence

    async def drain(self) -> None:
        while True:
            try:
                await self.transport.receive(timeout=0.05)
            except LifxTimeoutError:
                return

    async def close(self) -> None:
        await self.transport.close()


async def regime_lifx_async(p: LossyProber) -> TrialResult:
    """lifx-async: exponential per-attempt windows summing to the 16 s budget."""
    source = allocate_source()
    start = time.perf_counter()
    offered_before = p.offered
    total_weight = (2 ** (LIFX_ASYNC_MAX_RETRIES + 1)) - 1
    base_timeout = LIFX_ASYNC_TIMEOUT / total_weight
    total_sleep = 0.0
    sequences: set[int] = set()

    def accept(header: Any) -> bool:
        return header.source == source and header.sequence in sequences

    for attempt in range(LIFX_ASYNC_MAX_RETRIES + 1):
        elapsed_response = time.perf_counter() - start - total_sleep
        current_timeout = min(
            base_timeout * (2**attempt), LIFX_ASYNC_TIMEOUT - elapsed_response
        )
        if current_timeout <= 0:
            break
        sequences.add(attempt)
        await p.send(source, attempt)
        got = await p.recv(current_timeout, accept)
        if got is not None:
            return TrialResult(
                True,
                time.perf_counter() - start,
                p.offered - offered_before,
                got[1] + 1,
            )
        if attempt < LIFX_ASYNC_MAX_RETRIES:
            sleep = random.uniform(0, LIFX_ASYNC_SLEEP_BASE * (2**attempt))
            total_sleep += sleep
            await asyncio.sleep(sleep)
    return TrialResult(
        False, time.perf_counter() - start, p.offered - offered_before, None
    )


async def regime_glowup(p: LossyProber) -> TrialResult:
    """Glowup: 3 fresh 2 s deadlines, type-only matching, no inter-attempt sleep."""
    source = allocate_source()
    start = time.perf_counter()
    offered_before = p.offered

    def accept(_header: Any) -> bool:
        return True  # Glowup matches on packet type only

    for attempt in range(GLOWUP_ATTEMPTS):
        await p.send(source, attempt)
        got = await p.recv(GLOWUP_DEADLINE, accept)
        if got is not None:
            return TrialResult(
                True,
                time.perf_counter() - start,
                p.offered - offered_before,
                got[1] + 1 if got[0] == source else None,
            )
    return TrialResult(
        False, time.perf_counter() - start, p.offered - offered_before, None
    )


async def regime_photons(p: LossyProber) -> TrialResult:
    """Photons: continuous escalating-gap retransmits until 10 s message timeout."""
    source = allocate_source()
    start = time.perf_counter()
    offered_before = p.offered
    deadline = start + PHOTONS_TIMEOUT
    sequences: set[int] = set()

    def accept(header: Any) -> bool:
        return header.source == source and header.sequence in sequences

    tx = 0
    gap_iter = iter(PHOTONS_GAPS)
    gap = next(gap_iter)
    sequences.add(tx)
    await p.send(source, tx)
    next_tx_at = start + gap
    while True:
        now = time.perf_counter()
        if now >= deadline:
            return TrialResult(False, now - start, p.offered - offered_before, None)
        wait = min(next_tx_at, deadline) - now
        got = await p.recv(max(wait, 0.001), accept)
        if got is not None:
            return TrialResult(
                True,
                time.perf_counter() - start,
                p.offered - offered_before,
                got[1] + 1,
            )
        if time.perf_counter() >= next_tx_at:
            tx += 1
            sequences.add(tx % 256)
            await p.send(source, tx % 256)
            gap = next(gap_iter, PHOTONS_GAPS[-1])
            next_tx_at = time.perf_counter() + gap


REGIMES = {
    "lifx-async": regime_lifx_async,
    "glowup": regime_glowup,
    "photons": regime_photons,
}


def summarise(events: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for e in events:
        if e["category"] != "trial":
            continue
        bucket = (
            summary.setdefault(f"{e['bulb']} ({e['label']})", {})
            .setdefault(f"loss={e['loss']:g}", {})
            .setdefault(
                e["regime"],
                {"n": 0, "failures": 0, "elapsed_ms": [], "packets": []},
            )
        )
        bucket["n"] += 1
        bucket["packets"].append(e["packets_offered"])
        if e["success"]:
            bucket["elapsed_ms"].append(e["elapsed_ms"])
        else:
            bucket["failures"] += 1
    for bulb in summary.values():
        for loss in bulb.values():
            for stats in loss.values():
                elapsed = stats.pop("elapsed_ms")
                packets = stats.pop("packets")
                stats["fail_pct"] = round(100 * stats["failures"] / stats["n"], 1)
                stats["avg_packets_per_trial"] = round(sum(packets) / len(packets), 2)
                if elapsed:
                    idx = min(len(elapsed) - 1, math.ceil(len(elapsed) * 0.95) - 1)
                    stats["success_ms"] = {
                        "median": round(statistics.median(elapsed), 1),
                        "p95": round(sorted(elapsed)[idx], 1),
                        "max": round(max(elapsed), 1),
                    }
    return summary


def print_summary(summary: dict[str, Any]) -> None:
    for bulb, losses in summary.items():
        print(f"\n=== {bulb} ===")
        for loss, regimes in losses.items():
            print(f"  {loss}:")
            for regime, s in regimes.items():
                ms = s.get("success_ms", {})
                print(
                    f"    {regime:>11}: n={s['n']:>2}  fail={s['fail_pct']:>5.1f}%  "
                    f"pkts/trial={s['avg_packets_per_trial']:>5}  "
                    f"med={ms.get('median', '-'):>7} p95={ms.get('p95', '-'):>7} "
                    f"max={ms.get('max', '-'):>8}"
                )


async def run_bulb(
    ip: str,
    log: EventLog,
    loss_rates: list[float],
    trials: int,
    stagger: float,
) -> None:
    await asyncio.sleep(stagger)
    for loss in loss_rates:
        rng = random.Random(f"spike-002:{ip}:{loss}")  # nosec B311 — reproducible injection
        prober = LossyProber(ip, loss, rng)
        await prober.open()
        try:
            for trial in range(trials):
                for regime_name, regime in REGIMES.items():
                    await prober.drain()
                    result = await regime(prober)
                    log.emit(
                        "trial",
                        ip,
                        label=prober.label,
                        loss=loss,
                        regime=regime_name,
                        trial=trial,
                        success=result.success,
                        elapsed_ms=round(result.elapsed_s * 1000, 1),
                        packets_offered=result.packets_offered,
                        satisfied_by_tx=result.satisfied_by_tx,
                    )
                    await asyncio.sleep(INTER_TRIAL_GAP)
        finally:
            await prober.close()


async def cmd_run(args: argparse.Namespace) -> None:
    run_id = time.strftime("%Y%m%d-%H%M%S")
    log = EventLog(SPIKE_DIR / f"results-{run_id}.jsonl")
    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
    print(f"Run {run_id}: {len(hosts)} bulb(s), regimes={list(REGIMES)}")
    print(f"Loss rates {args.loss_rates}, {args.trials} trials/regime/rate")
    print(f"Event log: {log.path}")
    log.emit(
        "run_start", "-", hosts=hosts, loss_rates=args.loss_rates, trials=args.trials
    )
    results = await asyncio.gather(
        *(
            run_bulb(ip, log, args.loss_rates, args.trials, i * 2.0)
            for i, ip in enumerate(hosts)
        ),
        return_exceptions=True,
    )
    for ip, result in zip(hosts, results):
        if isinstance(result, BaseException):
            print(f"!! {ip}: {type(result).__name__}: {result}")
    summary = summarise(log.events)
    summary_path = SPIKE_DIR / f"summary-{run_id}.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print_summary(summary)
    print(f"\nSummary written to {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Race the regimes")
    run.add_argument("--hosts", required=True, help="Comma-separated bulb IPs")
    run.add_argument(
        "--loss-rates",
        default="0,0.25,0.5",
        help="Per-direction Bernoulli loss probabilities (comma-separated)",
    )
    run.add_argument("--trials", type=int, default=20)
    run.add_argument("--quick", action="store_true", help="Shakedown: 3 trials")
    args = parser.parse_args()
    if args.quick:
        args.trials = 3
    args.loss_rates = [float(s) for s in str(args.loss_rates).split(",")]
    asyncio.run(cmd_run(args))


if __name__ == "__main__":
    main()
