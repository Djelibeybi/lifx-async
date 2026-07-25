"""Reproducible statistics over the 04-08 ANIM-03 gap-investigation evidence.

Reads exactly two committed evidence files (both produced by the
04-08 hardware run and committed in dd6a15e):

- ``04-GAP-INVESTIGATION.json``  -- per-arm aggregates + references
- ``04-GAP-INVESTIGATION-EVENTS.jsonl`` -- per-query / per-frame events

and prints every statistical table embedded in ``04-GAP-ANALYSIS.md``,
so each number in the decision brief is reproducible by rerunning:

    uv run python .planning/phases/04-animation-flow-control/gap_analysis.py

This script computes statistics and evaluates the arithmetic inputs of the
pre-declared interpretation rules R1-R5 (fixed in 04-09-PLAN.md before this
analysis ran). It renders no verdict -- interpretation lives in the brief.

Zero third-party dependencies: stdlib only.
"""

from __future__ import annotations

import bisect
import json
import math
import statistics
from pathlib import Path
from typing import Any

Z95: float = 1.96  # two-sided 95% normal quantile (Wilson intervals)
QUERY_WINDOW_S: float = 2.0  # UAT prober per-query timeout (query_timeout)

HERE: Path = Path(__file__).resolve().parent
INVESTIGATION_JSON: Path = HERE / "04-GAP-INVESTIGATION.json"
EVENTS_JSONL: Path = HERE / "04-GAP-INVESTIGATION-EVENTS.jsonl"

# ---------------------------------------------------------------------------
# Statistical primitives
# ---------------------------------------------------------------------------


def wilson_interval(losses: int, n: int) -> tuple[float, float]:
    """Closed-form Wilson score 95% interval for a binomial proportion."""
    if n == 0:
        return (0.0, 1.0)
    p_hat = losses / n
    z2 = Z95 * Z95
    denom = 1.0 + z2 / n
    centre = p_hat + z2 / (2.0 * n)
    spread = Z95 * math.sqrt(p_hat * (1.0 - p_hat) / n + z2 / (4.0 * n * n))
    return (max(0.0, (centre - spread) / denom), min(1.0, (centre + spread) / denom))


def rule_of_three_upper(n: int) -> float:
    """95% upper bound on the true rate given 0 observed events in n trials."""
    return 3.0 / n


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Exact two-sided Fisher test p-value for the 2x2 table [[a, b], [c, d]].

    Two-sided by summing hypergeometric probabilities of all tables (with the
    same margins) no more probable than the observed one.
    """
    row1, row2 = a + b, c + d
    col1 = a + c
    total = row1 + row2
    denom = math.comb(total, col1)

    def prob(x: int) -> float:
        return math.comb(row1, x) * math.comb(row2, col1 - x) / denom

    p_obs = prob(a)
    lo = max(0, col1 - row2)
    hi = min(col1, row1)
    return min(
        1.0,
        sum(p for x in range(lo, hi + 1) if (p := prob(x)) <= p_obs * (1.0 + 1e-9)),
    )


def p_zero_losses(n: int, p: float) -> float:
    """P(0 losses in n independent queries | per-query loss probability p)."""
    return (1.0 - p) ** n


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p)."""
    return sum(math.comb(n, i) * p**i * (1.0 - p) ** (n - i) for i in range(k + 1))


def pct(x: float) -> str:
    return f"{100.0 * x:.2f}%"


def ci_str(losses: int, n: int) -> str:
    lo, hi = wilson_interval(losses, n)
    return f"[{pct(lo)}, {pct(hi)}]"


# ---------------------------------------------------------------------------
# Evidence loading
# ---------------------------------------------------------------------------


def load_investigation() -> dict[str, Any]:
    with INVESTIGATION_JSON.open() as f:
        return json.load(f)


def load_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with EVENTS_JSONL.open() as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


# ---------------------------------------------------------------------------
# Table sections (a)-(h) + rule inputs + (i) proposed-threshold derivation
# ---------------------------------------------------------------------------


def arm_pools(data: dict[str, Any]) -> list[tuple[str, str, int, int]]:
    """(arm label, device, lost, n) for every pooled arm, plus fallback splits."""
    arms = data["arms"]
    fb = arms["fallback"]
    fb_ctrl = fb["control"]
    fb_ship_lost = sum(r["queries_lost"] for r in fb["shipped_rounds"])
    fb_ship_n = sum(r["queries_ok"] + r["queries_lost"] for r in fb["shipped_rounds"])

    def pooled(name: str) -> tuple[int, int]:
        p = arms[name]["pooled"]
        return p["queries_lost"], p["queries_ok"] + p["queries_lost"]

    rows: list[tuple[str, str, int, int]] = []
    for name in ("control", "shipped", "replica", "sweep"):
        lost, n = pooled(name)
        rows.append((name, "primary", lost, n))
    rows.append(
        (
            "fallback-control",
            "fallback",
            fb_ctrl["queries_lost"],
            fb_ctrl["queries_ok"] + fb_ctrl["queries_lost"],
        )
    )
    rows.append(("fallback-shipped", "fallback", fb_ship_lost, fb_ship_n))
    lost, n = (
        fb["pooled"]["queries_lost"],
        (fb["pooled"]["queries_ok"] + fb["pooled"]["queries_lost"]),
    )
    rows.append(("fallback (all)", "fallback", lost, n))
    return rows


def section_a_wilson(data: dict[str, Any]) -> None:
    print("(a) Per-arm pooled loss with Wilson 95% intervals")
    print(f"    {'arm':<18} {'device':<9} {'lost/n':<9} {'loss%':<8} wilson 95% CI")
    for name, device, lost, n in arm_pools(data):
        print(
            f"    {name:<18} {device:<9} {f'{lost}/{n}':<9} "
            f"{pct(lost / n):<8} {ci_str(lost, n)}"
        )
    print()


def section_b_rule_of_three(data: dict[str, Any]) -> None:
    print("(b) Rule-of-three 95% upper bounds (zero-loss arms only, 3/n)")
    for name, device, lost, n in arm_pools(data):
        if lost == 0:
            print(f"    {name:<18} {device:<9} 0/{n:<7} upper bound {pct(3.0 / n)}")
    print()


def section_c_fisher(data: dict[str, Any]) -> tuple[float, int, int, int, int]:
    ship = data["arms"]["shipped"]["pooled"]
    repl = data["arms"]["replica"]["pooled"]
    a, b = ship["queries_lost"], ship["queries_ok"]
    c, d = repl["queries_lost"], repl["queries_ok"]
    p = fisher_exact_two_sided(a, b, c, d)
    print("(c) Fisher exact test (two-sided): shipped vs replica pooled losses")
    print(f"    table [[lost, ok]]: shipped [{a}, {b}]  replica [{c}, {d}]")
    print(f"    shipped loss {pct(a / (a + b))}  replica loss {pct(c / (c + d))}")
    print(f"    two-sided p = {p:.4f}")
    print()
    return p, a, b, c, d


def section_d_p_zero(data: dict[str, Any]) -> float:
    ref = data["reference"]["uat_04_06_pooled"]
    p_uat = ref["lost"] / ref["queries"]
    print(
        "(d) P(zero losses in n | p) with p = pooled 04-06 UAT rate "
        f"{ref['lost']}/{ref['queries']} = {pct(p_uat)}"
    )
    for n in (50, 150, 176, 185):
        print(f"    n = {n:<4} P(0 losses) = {p_zero_losses(n, p_uat):.4f}")
    print()
    return p_uat


def _median_str(values: list[float]) -> str:
    return f"{statistics.median(values):.3f}" if values else "n/a"


def section_e_clustering(events: list[dict[str, Any]]) -> None:
    """Loss-vs-frame-burst clustering over shipped/sweep-arm query events.

    For each query (send time t) join against the frame events of the same
    (arm, device, fps, round) group:
      m1: gate-outstanding at query send (latest frame event with f.t <= t)
      m2: count of non-gated frames inside the query window [t, t + 2.0 s]
      m3: seconds since the last non-gated frame at query send
    """
    frame_groups: dict[tuple[str, str, float | None, int], list[dict[str, Any]]] = {}
    for e in events:
        if e["kind"] == "frame":
            key = (e["arm"], e["device"], e["fps"], e["round"])
            frame_groups.setdefault(key, []).append(e)

    indexed: dict[
        tuple[str, str, float | None, int],
        tuple[list[float], list[int], list[float]],
    ] = {}
    for key, frames in frame_groups.items():
        frames.sort(key=lambda f: f["t"])
        all_ts = [f["t"] for f in frames]
        outst = [f["outstanding"] for f in frames]
        ng_ts = [f["t"] for f in frames if not f["gated"]]
        indexed[key] = (all_ts, outst, ng_ts)

    by_outcome: dict[str, dict[str, list[float]]] = {
        "ok": {"m1": [], "m2": [], "m3": []},
        "lost": {"m1": [], "m2": [], "m3": []},
    }
    missing = {"m1": 0, "m3": 0}
    lost_rows: list[str] = []

    for e in events:
        if e["kind"] != "query" or e["arm"] not in ("shipped", "sweep"):
            continue
        key = (e["arm"], e["device"], e["fps"], e["round"])
        all_ts, outst, ng_ts = indexed[key]
        t = e["t"]

        i = bisect.bisect_right(all_ts, t) - 1
        m1 = float(outst[i]) if i >= 0 else None
        lo = bisect.bisect_left(ng_ts, t)
        hi = bisect.bisect_right(ng_ts, t + QUERY_WINDOW_S)
        m2 = float(hi - lo)
        j = bisect.bisect_right(ng_ts, t) - 1
        m3 = (t - ng_ts[j]) if j >= 0 else None

        bucket = by_outcome[e["outcome"]]
        if m1 is None:
            missing["m1"] += 1
        else:
            bucket["m1"].append(m1)
        bucket["m2"].append(m2)
        if m3 is None:
            missing["m3"] += 1
        else:
            bucket["m3"].append(m3)

        if e["outcome"] == "lost":
            lost_rows.append(
                f"    {e['arm']:<8} fps={e['fps']:<5} round={e['round']} "
                f"t={t:8.3f}s  outstanding={m1 if m1 is not None else 'n/a'}  "
                f"non-gated-in-window={int(m2)}  "
                f"since-last-non-gated="
                f"{f'{m3:.3f}s' if m3 is not None else 'n/a'}"
            )

    print("(e) Event clustering: shipped + sweep arm queries vs frame events")
    print("    (m1 = gate-outstanding at query send; m2 = non-gated frames in")
    print("     [t, t+2.0 s]; m3 = seconds since last non-gated frame)")
    for outcome in ("ok", "lost"):
        b = by_outcome[outcome]
        print(
            f"    outcome={outcome:<5} n={len(b['m2']):<4} "
            f"median m1={_median_str(b['m1'])}  "
            f"median m2={_median_str(b['m2'])}  "
            f"median m3={_median_str(b['m3'])}"
        )
    if missing["m1"] or missing["m3"]:
        print(
            f"    (queries with no preceding frame event: m1 missing for "
            f"{missing['m1']}, m3 missing for {missing['m3']})"
        )
    print("    every lost shipped/sweep query in detail:")
    for row in lost_rows:
        print(row)
    print()


def per_fps_pools(data: dict[str, Any]) -> list[tuple[float, int, int]]:
    """(fps, lost, n) pooled: 10/15 from the sweep arm, 20 from the shipped arm."""
    sweep_rounds = data["arms"]["sweep"]["rounds"]
    pools: dict[float, list[int]] = {}
    for r in sweep_rounds:
        acc = pools.setdefault(r["fps"], [0, 0])
        acc[0] += r["queries_lost"]
        acc[1] += r["queries_ok"] + r["queries_lost"]
    ship = data["arms"]["shipped"]["pooled"]
    rows = [(fps, acc[0], acc[1]) for fps, acc in sorted(pools.items())]
    rows.append((20.0, ship["queries_lost"], ship["queries_ok"] + ship["queries_lost"]))
    return rows


def section_f_fps(data: dict[str, Any]) -> list[tuple[float, int, int]]:
    rows = per_fps_pools(data)
    print("(f) Loss vs FPS (10/15 from sweep arm; 20 from shipped arm; primary)")
    print(f"    {'fps':<5} {'lost/n':<9} {'loss%':<8} {'wilson 95% CI':<18} 3/n bound")
    for fps, lost, n in rows:
        print(
            f"    {fps:<5} {f'{lost}/{n}':<9} {pct(lost / n):<8} "
            f"{ci_str(lost, n):<18} {pct(3.0 / n)}"
        )
    print()
    return rows


def section_g_devices(data: dict[str, Any]) -> None:
    print("(g) Primary vs fallback device (same shipped path, 20 FPS)")
    print(f"    {'segment':<18} {'device':<9} {'lost/n':<9} {'loss%':<8} wilson 95% CI")
    for name, device, lost, n in arm_pools(data):
        if name in ("control", "shipped", "fallback-control", "fallback-shipped"):
            print(
                f"    {name:<18} {device:<9} {f'{lost}/{n}':<9} "
                f"{pct(lost / n):<8} {ci_str(lost, n)}"
            )
    print()


def section_h_control_floors(data: dict[str, Any]) -> None:
    print("(h) Control-arm ambient floors (no streaming, single-shot queries)")
    for name, device, lost, n in arm_pools(data):
        if name in ("control", "fallback-control"):
            print(
                f"    {name:<18} {device:<9} {lost}/{n}  rule-of-three "
                f"{pct(3.0 / n)}  wilson {ci_str(lost, n)}"
            )
    print()


def rule_inputs(
    data: dict[str, Any],
    fisher_p: float,
    fps_rows: list[tuple[float, int, int]],
) -> None:
    """Arithmetic inputs of the pre-declared rules R1-R5 (04-09-PLAN.md).

    Prints predicate inputs and whether each predicate holds. Interpretation
    (verdict + route) is the brief's job.
    """
    arms = data["arms"]
    fb = arms["fallback"]

    print("Rule inputs (pre-declared R1-R5 predicates; arithmetic only)")

    ctrl_rows = [
        (n, l_)
        for name, _dev, l_, n in arm_pools(data)
        if name in ("control", "fallback-control")
    ]
    r1 = any(lost > 0 and n >= 100 for n, lost in ctrl_rows)
    print(
        "    R1 ambient floor: control arms "
        + ", ".join(f"{lost}/{n}" for n, lost in ctrl_rows)
        + f" -> any lossy at n>=100: {r1}"
    )

    repl = arms["replica"]["pooled"]
    repl_n = repl["queries_ok"] + repl["queries_lost"]
    repl_rate = repl["queries_lost"] / repl_n
    r2 = repl_n >= 150 and repl_rate >= 0.02
    print(
        f"    R2 sampling artefact: replica {repl['queries_lost']}/{repl_n} = "
        f"{pct(repl_rate)} (need n>=150 and >=2.00%): {r2}"
    )

    ship = arms["shipped"]["pooled"]
    ship_n = ship["queries_ok"] + ship["queries_lost"]
    ship_rate = ship["queries_lost"] / ship_n
    r3 = (
        repl["queries_lost"] == 0
        and repl_n >= 150
        and ship_rate >= 0.02
        and fisher_p < 0.05
    )
    print(
        f"    R3 mechanical delta: replica losses={repl['queries_lost']} "
        f"(need 0 over >=150), shipped {pct(ship_rate)} (need >=2.00%), "
        f"Fisher p={fisher_p:.4f} (need <0.05): {r3}"
    )

    rates = [(fps, lost / n, lost, n) for fps, lost, n in fps_rows]
    mono = all(rates[i][1] <= rates[i + 1][1] for i in range(len(rates) - 1))
    n10 = rates[0][3]
    bound10 = 3.0 / n10
    below10 = rates[0][1] < bound10
    at20 = rates[-1][1] >= bound10
    r4 = mono and below10 and at20
    print(
        "    R4 load saturation: rates "
        + " -> ".join(f"{pct(r)}@{fps:g}fps" for fps, r, _, _ in rates)
        + f"; monotone non-decreasing: {mono}; 10fps rate < 3/{n10} "
        f"({pct(bound10)}): {below10}; 20fps rate >= {pct(bound10)}: {at20} "
        f"-> {r4}"
    )

    shipped_rounds = arms["shipped"]["rounds"] + fb["shipped_rounds"]
    r5 = all(r["queries_lost"] == 0 for r in shipped_rounds)
    lossy = [
        f"{r['queries_lost']} lost (round {r['round']})"
        for r in shipped_rounds
        if r["queries_lost"] > 0
    ]
    print(
        f"    R5 non-reproduction: shipped rounds on both devices all "
        f"zero-loss: {r5}" + (f" (lossy rounds: {', '.join(lossy)})" if lossy else "")
    )
    print()


def section_i_threshold_derivation(data: dict[str, Any], p_uat: float) -> None:
    """Inputs for the proposed recalibrated threshold (used only if the
    verdict supports recalibration; the amendment itself is operator-owned).
    """
    arms = data["arms"]
    ref = data["reference"]["uat_04_06_pooled"]
    ship = arms["shipped"]["pooled"]
    fb_rounds = arms["fallback"]["shipped_rounds"]

    uat_lost, uat_n = ref["lost"], ref["queries"]
    ship_lost = ship["queries_lost"]
    ship_n = ship["queries_ok"] + ship["queries_lost"]
    fb_lost = sum(r["queries_lost"] for r in fb_rounds)
    fb_n = sum(r["queries_ok"] + r["queries_lost"] for r in fb_rounds)

    lost = uat_lost + ship_lost + fb_lost
    n = uat_n + ship_n + fb_n
    rate = lost / n
    lo, hi = wilson_interval(lost, n)

    print("(i) Proposed-threshold derivation inputs (shipped path, 20 FPS only)")
    print(
        f"    pooled shipped-path evidence: 04-06 UAT {uat_lost}/{uat_n} + "
        f"shipped arm {ship_lost}/{ship_n} + fallback shipped {fb_lost}/{fb_n}"
    )
    print(f"    = {lost}/{n} = {pct(rate)}  wilson 95% CI [{pct(lo)}, {pct(hi)}]")

    round_rates = [
        (r["queries_lost"], r["queries_ok"] + r["queries_lost"])
        for r in arms["shipped"]["rounds"] + fb_rounds
    ]
    worst = max(round_rates, key=lambda x: x[0] / x[1])
    print(
        f"    worst shipped-path round in this evidence: {worst[0]}/{worst[1]} "
        f"= {pct(worst[0] / worst[1])}"
    )

    n_round = 45  # typical prober yield per 30 s round at 2 queries/s
    n_run = 3 * n_round
    k_round = math.floor(0.09 * n_round)  # <=9.0% per round
    k_run = math.floor(0.05 * n_run)  # <=5.0% pooled per run
    for label, p in (("pooled evidence rate", rate), ("04-06 UAT rate", p_uat)):
        p_round = binom_cdf(k_round, n_round, p)
        p_all_rounds = p_round**3
        p_pooled = binom_cdf(k_run, n_run, p)
        print(
            f"    at p = {pct(p)} ({label}): "
            f"P(round<=9%) = {p_round:.4f}, P(all 3 rounds) = {p_all_rounds:.4f}, "
            f"P(pooled<=5% over {n_run}) = {p_pooled:.4f}"
        )
    print()


def main() -> None:
    data = load_investigation()
    events = load_events()
    n_query = sum(1 for e in events if e["kind"] == "query")
    n_frame = sum(1 for e in events if e["kind"] == "frame")

    print("=== 04-09 gap analysis: statistics over the 04-08 evidence ===")
    print(f"run timestamp: {data['timestamp']}  arms: {', '.join(data['arms_run'])}")
    print(f"events: {n_query} query events, {n_frame} frame events")
    print()

    section_a_wilson(data)
    section_b_rule_of_three(data)
    fisher_p, *_ = section_c_fisher(data)
    p_uat = section_d_p_zero(data)
    section_e_clustering(events)
    fps_rows = section_f_fps(data)
    section_g_devices(data)
    section_h_control_floors(data)
    rule_inputs(data, fisher_p, fps_rows)
    section_i_threshold_derivation(data, p_uat)


if __name__ == "__main__":
    main()
