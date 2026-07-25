"""DISC-03 hardware UAT: 6-round median fleet coverage measurement.

Standalone measurement script for DISC-03 (ROADMAP Phase 2 success criterion 4).
Drives the real, shipped ``discover_devices()`` implementation over repeated
rounds against the production fleet and compares the result against the
recorded single-broadcast baseline from spike 005
(min/med/max = 27/48/73). Repeated rounds are mandatory for a coverage claim
-- a single round can mislead (the spike shakedown found 71/73 by luck
against a true median of 48).

This script lives in the phase directory. It is never imported from
``src/`` or ``tests/`` and is not shipped as part of the ``lifx-async``
package.

Run:
    uv run python .planning/phases/02-discovery-rebroadcast/uat_rounds.py

Exit codes:
    0 -- PASS: median per-round coverage equals the union roster, and the
         roster is large enough to trust (roster_size >= 60).
    1 -- FAIL: roster_size >= 60 but median < roster_size (a genuine
         coverage shortfall -- never massaged away).
    2 -- ENV-ERROR: roster_size < 60, meaning the production fleet is not
         visible from this machine (off-network or degraded run). A tiny
         or empty roster must never produce a trivial median == roster
         pass.
"""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

from lifx.network.discovery import discover_devices

DEFAULT_JSON_OUT = Path(".planning/phases/02-discovery-rebroadcast/02-UAT-RESULTS.json")
BASELINE_PATH = Path(
    ".planning/spikes/005-discovery-regimes/summary-20260716-211339.json"
)
ROSTER_SANITY_FLOOR = 60


def load_baseline() -> list[float] | None:
    """Load the spike 005 single-broadcast baseline's found_min_med_max.

    Returns None (and prints a note) if the baseline file is missing or
    unreadable -- a missing baseline must never fail the run.
    """
    try:
        data = json.loads(BASELINE_PATH.read_text())
        return data["lifx-async"]["found_min_med_max"]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"Note: could not load baseline from {BASELINE_PATH}: {exc}")
        return None


async def run_rounds(rounds: int, window: float, gap: float) -> list[list[str]]:
    """Run `rounds` discovery rounds, sleeping `gap` seconds between them."""
    per_round: list[list[str]] = []
    for i in range(rounds):
        found = {d.serial async for d in discover_devices(timeout=window)}
        print(f"round {i}: {len(found)}")
        per_round.append(sorted(found))
        if i < rounds - 1:
            await asyncio.sleep(gap)
    return per_round


def build_results(
    per_round: list[list[str]], baseline: list[float] | None
) -> dict[str, object]:
    """Compute roster, median, missed-by-round diagnostics, and pass flag."""
    round_sets = [set(r) for r in per_round]
    roster = sorted(set().union(*round_sets)) if round_sets else []
    counts = [len(r) for r in round_sets]
    median = statistics.median(counts) if counts else 0.0
    missed_by_round = [sorted(set(roster) - r) for r in round_sets]
    roster_size = len(roster)

    verdict_pass = roster_size >= ROSTER_SANITY_FLOOR and median == roster_size

    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "rounds": counts,
        "roster_size": roster_size,
        "median": median,
        "missed_by_round": missed_by_round,
        "baseline_found_min_med_max": baseline,
        "pass": verdict_pass,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rounds",
        type=int,
        default=6,
        help="Number of discovery rounds (never fewer than 6 for a coverage claim)",
    )
    parser.add_argument(
        "--window",
        type=float,
        default=10.0,
        help="Per-round discover_devices() timeout in seconds (matches spike 005)",
    )
    parser.add_argument(
        "--gap",
        type=float,
        default=3.0,
        help="Inter-round sleep in seconds (matches sweep.py's INTER_ROUND_GAP)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=DEFAULT_JSON_OUT,
        help="Path to write the machine-readable results JSON",
    )
    args = parser.parse_args()

    baseline = load_baseline()
    if baseline is not None:
        print(
            f"Baseline (spike 005, lifx-async single-broadcast): "
            f"min/med/max = {baseline[0]}/{baseline[1]}/{baseline[2]}"
        )

    per_round = await run_rounds(args.rounds, args.window, args.gap)
    results = build_results(per_round, baseline)

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(results, indent=2) + "\n")

    roster_size = results["roster_size"]
    median = results["median"]
    print(
        f"roster={roster_size} median={median} "
        f"baseline={baseline if baseline is not None else 'unavailable'}"
    )

    if roster_size < ROSTER_SANITY_FLOOR:
        print(
            f"ENV-ERROR: roster_size {roster_size} < {ROSTER_SANITY_FLOOR} -- "
            "the production fleet is not visible from this machine; "
            "not recording a pass"
        )
        return 2
    if median == roster_size:
        print("PASS: median per-round coverage equals the full roster")
        return 0
    print(
        f"FAIL: median {median} < roster {roster_size} -- measured coverage shortfall"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
