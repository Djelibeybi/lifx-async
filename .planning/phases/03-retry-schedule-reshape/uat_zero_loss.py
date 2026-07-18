"""RETRY-01/RETRY-02 hardware evidence: zero-loss packets/trial + latency.

Standalone measurement script (optional per 03-CONTEXT.md -- RETRY-01 through
RETRY-04 are already closed by plan 03-02's emulator-backed test suite). Drives
the real, shipped ``DeviceConnection.request()`` against the quiesced gen4
test downlight at 192.168.18.95, the RTT-sensitive device where spike 002
measured 1.37 packets/trial (target: 1.0) and a 62 ms median latency inflated
by the old jitter sleep (target: roughly raw RTT). Mirrors the honest-
reporting contract of Phase 2's ``uat_rounds.py``.

This script lives in the phase directory. It is never imported from ``src/``
or ``tests/`` and is not shipped as part of the ``lifx-async`` package.

Run:
    uv run python .planning/phases/03-retry-schedule-reshape/uat_zero_loss.py \\
        --trials 60 \\
        --json-out .planning/phases/03-retry-schedule-reshape/03-UAT-RESULTS.json

Honest-reporting rules (fixed in this file BEFORE any run, never adjusted
after seeing results):
    - Pass thresholds and the exit-code contract below are final. A run that
      misses them is a genuine signal to record, not a reason to relax them.
    - Every run's actual per-trial numbers are written to the results JSON,
      pass or fail or skipped.

Exit codes:
    0 -- PASS: zero failed trials AND median packets/trial == 1 AND mean
         packets/trial <= 1.05 (tolerates roughly 3 genuine WiFi-loss
         retransmits in 60 trials -- the schedule working as designed --
         while still proving the old duplicate storm is gone).
    1 -- FAIL: device reachable but the thresholds above were not met. A
         genuine regression signal -- report it, never massage it.
    2 -- ENV-ERROR: the reachability probe failed (device unreachable from
         this machine). Recorded honestly; does not fail the phase since
         this measurement is optional per 03-CONTEXT.md.
"""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import TypedDict

from lifx.exceptions import LifxError
from lifx.network.connection import DeviceConnection
from lifx.protocol import packets


class TrialResult(TypedDict):
    """One trial's measured send count, latency, and success flag."""

    tx_count: int
    latency_ms: float
    ok: bool


DEFAULT_IP = "192.168.18.95"
DEFAULT_JSON_OUT = Path(
    ".planning/phases/03-retry-schedule-reshape/03-UAT-RESULTS.json"
)

# Spike 002 baselines (540 trials, 3 device generations, seeded loss
# injection) -- see
# .claude/skills/spike-findings-lifx-async/references/retry-schedule.md
BASELINE = {
    "lifx-async_packets_per_trial": 1.37,
    "photons_packets_per_trial": 1.08,
    "gen4_median_latency_ms": 62.0,
}

# Fixed pass thresholds (set before any run, never adjusted afterwards).
MEDIAN_PACKETS_THRESHOLD = 1.0
MEAN_PACKETS_THRESHOLD = 1.05


class _SendSpy:
    """Counts calls to a bound ``send_packet`` while delegating to it.

    Plain attribute assignment (no mock imports in a script) -- wraps the
    connection's real ``send_packet`` so every retransmit issued by the
    shipped retry engine is counted, without reimplementing any schedule
    logic.
    """

    def __init__(self, bound_send_packet: object) -> None:
        self._bound_send_packet = bound_send_packet
        self.count = 0

    async def __call__(self, *args: object, **kwargs: object) -> object:
        self.count += 1
        return await self._bound_send_packet(*args, **kwargs)  # type: ignore[operator]


async def probe(conn: DeviceConnection, timeout: float) -> bool:
    """One generous-timeout reachability probe before the trial loop."""
    try:
        await conn.request(packets.Light.GetColor(), timeout=timeout)
    except LifxError:
        return False
    return True


async def run_trials(
    conn: DeviceConnection, trials: int, gap: float, timeout: float
) -> list[TrialResult]:
    """Run `trials` GetColor requests, recording tx count, latency, and success."""
    spy = _SendSpy(conn.send_packet)
    conn.send_packet = spy  # type: ignore[method-assign]

    results: list[TrialResult] = []
    for i in range(trials):
        spy.count = 0
        start = time.monotonic()
        ok = True
        try:
            await conn.request(packets.Light.GetColor(), timeout=timeout)
        except LifxError:
            ok = False
        elapsed_ms = (time.monotonic() - start) * 1000.0
        print(f"trial {i}: tx={spy.count} latency_ms={elapsed_ms:.1f} ok={ok}")
        results.append({"tx_count": spy.count, "latency_ms": elapsed_ms, "ok": ok})
        if i < trials - 1:
            await asyncio.sleep(gap)
    return results


def build_results(trials: list[TrialResult]) -> dict[str, object]:
    """Compute packets/trial mean+median, latency median, and the pass flag."""
    tx_counts = [t["tx_count"] for t in trials]
    latencies = [t["latency_ms"] for t in trials]
    failures = sum(1 for t in trials if not t["ok"])

    mean_packets = statistics.mean(tx_counts) if tx_counts else 0.0
    median_packets = statistics.median(tx_counts) if tx_counts else 0.0
    median_latency = statistics.median(latencies) if latencies else 0.0

    verdict_pass = (
        failures == 0
        and median_packets == MEDIAN_PACKETS_THRESHOLD
        and mean_packets <= MEAN_PACKETS_THRESHOLD
    )

    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "trials": trials,
        "trials_run": len(trials),
        "failures": failures,
        "packets_per_trial_mean": mean_packets,
        "packets_per_trial_median": median_packets,
        "latency_ms_median": median_latency,
        "thresholds": {
            "median_packets_per_trial": MEDIAN_PACKETS_THRESHOLD,
            "mean_packets_per_trial_max": MEAN_PACKETS_THRESHOLD,
        },
        "baseline": BASELINE,
        "pass": verdict_pass,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ip",
        type=str,
        default=DEFAULT_IP,
        help="IP address of the quiesced gen4 test downlight",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=60,
        help="Number of GetColor request trials (matches a spike 002 regime arm)",
    )
    parser.add_argument(
        "--gap",
        type=float,
        default=0.1,
        help="Inter-trial sleep in seconds (well under the ~20 msg/s device ceiling)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=DEFAULT_JSON_OUT,
        help="Path to write the machine-readable results JSON",
    )
    args = parser.parse_args()

    conn = DeviceConnection(serial="000000000000", ip=args.ip)
    try:
        reachable = await probe(conn, timeout=max(args.timeout, 5.0))
        if not reachable:
            print(
                f"ENV-ERROR: {args.ip} did not respond to the reachability probe -- "
                "the device is not visible from this machine; not recording a pass. "
                "This measurement is optional (03-CONTEXT.md); the phase is not failed."
            )
            results = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
                "outcome": "ENV-ERROR",
                "skipped": True,
                "reason": f"reachability probe to {args.ip} failed",
                "baseline": BASELINE,
                "pass": None,  # nosec B105 -- verdict placeholder, not a credential
            }
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(json.dumps(results, indent=2) + "\n")
            return 2

        trials = await run_trials(conn, args.trials, args.gap, args.timeout)
    finally:
        await conn.close()

    results = build_results(trials)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(results, indent=2) + "\n")

    print(
        f"packets_per_trial mean={results['packets_per_trial_mean']:.3f} "
        f"median={results['packets_per_trial_median']} "
        f"latency_ms_median={results['latency_ms_median']:.1f} "
        f"failures={results['failures']}/{results['trials_run']} "
        f"baseline={BASELINE['lifx-async_packets_per_trial']}/"
        f"{BASELINE['gen4_median_latency_ms']}ms"
    )

    if results["pass"]:
        print("PASS: zero-loss packets/trial at target, no failed trials")
        return 0
    print(
        "FAIL: device reachable but thresholds not met -- "
        f"mean={results['packets_per_trial_mean']:.3f} "
        f"median={results['packets_per_trial_median']} "
        f"failures={results['failures']}"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
