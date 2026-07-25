"""Reproducible statistics for the 04-11 paired-relative ANIM-03 criterion design.

Every number in ``04-CRITERION-DESIGN.md`` is reproducible by rerunning:

    uv run python .planning/phases/04-animation-flow-control/criterion_design.py

The script hard-codes the multi-session evidence counts (each row cites its
committed source) and, wherever the source JSON is on disk, parses it and
ASSERTS the hard-coded counts match -- the evidence table is provably
faithful to the committed bytes. It then derives every proposed parameter of
the paired-relative criterion by a stated rule, enumerates exact statistical
power (no normal approximations) at the achievable per-arm sample sizes, and
retrodicts the proposed rule against every historical session whose inputs
exist.

This script computes; it decides nothing. The criterion itself is an
operator decision taken at the 04-11 blocking checkpoint from the design
brief's "## Final wording" section.

Zero third-party dependencies: stdlib only.

Statistical primitives ``wilson_interval``, ``rule_of_three_upper`` and the
``math.comb`` hypergeometric Fisher machinery are adapted from the committed
``gap_analysis.py`` (04-09, commit 545d4b6), with a one-sided variant added
for the paired gate.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

Z95: float = 1.96  # two-sided 95% normal quantile (Wilson intervals)

HERE: Path = Path(__file__).resolve().parent
SPIKE_003_SUMMARY: Path = (
    HERE.parent.parent
    / "spikes"
    / "003-ack-paced-frames"
    / "summary-20260716-210408.json"
)
SESSION_A_RUN1: Path = HERE / "04-UAT-TILES-run1-FAIL.json"
SESSION_B_JSON: Path = HERE / "04-GAP-INVESTIGATION.json"
SESSION_C_RUN1: Path = HERE / "04-UAT-TILES-amended-run1-FAIL.json"
SESSION_C_RUN2: Path = HERE / "04-UAT-TILES.json"

# ---------------------------------------------------------------------------
# Proposed paired-relative criterion parameters (derived in section 2 below;
# NOT applied anywhere until the operator approves them at the 04-11
# checkpoint).
# ---------------------------------------------------------------------------

MAX_AMBIENT_LOSS_PCT: float = 2.5  # session validity V1
MIN_AMBIENT_QUERIES: int = 100  # session validity V2
MIN_GATED_DELIVERED_SANITY: float = 0.50  # session validity V3
FISHER_ALPHA: float = 0.05  # relative rule significance
MIN_IMPROVEMENT_RATIO: float = 2.0  # relative rule point-ratio floor
CLEAN_GATED_LOSS_PCT: float = 2.5  # clean escape
MAX_GATED_POOLED_LOSS_PCT: float = 9.0  # absolute ceiling
ROUNDS_PER_ARM: int = 3  # proposed session shape (per arm)

# ---------------------------------------------------------------------------
# Statistical primitives (adapted from gap_analysis.py, commit 545d4b6)
# ---------------------------------------------------------------------------


def wilson_interval(losses: int, n: int) -> tuple[float, float]:
    """Closed-form Wilson score 95% interval for a binomial proportion.

    Adapted verbatim from gap_analysis.py (04-09, commit 545d4b6).
    """
    if n == 0:
        return (0.0, 1.0)
    p_hat = losses / n
    z2 = Z95 * Z95
    denom = 1.0 + z2 / n
    centre = p_hat + z2 / (2.0 * n)
    spread = Z95 * math.sqrt(p_hat * (1.0 - p_hat) / n + z2 / (4.0 * n * n))
    return (max(0.0, (centre - spread) / denom), min(1.0, (centre + spread) / denom))


def rule_of_three_upper(n: int) -> float:
    """95% upper bound on the true rate given 0 observed events in n trials.

    Adapted verbatim from gap_analysis.py (04-09, commit 545d4b6).
    """
    return 3.0 / n


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Exact two-sided Fisher test p-value for the 2x2 table [[a, b], [c, d]].

    Adapted verbatim from gap_analysis.py (04-09, commit 545d4b6). Two-sided
    by summing hypergeometric probabilities of all tables (with the same
    margins) no more probable than the observed one.
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


def fisher_one_sided(
    gated_lost: int, gated_ok: int, blind_lost: int, blind_ok: int
) -> float:
    """One-sided Fisher exact p (alternative: gated loss rate < blind loss rate).

    Conditioning on the total number of losses, p is the hypergeometric lower
    tail P(X <= gated_lost) where X is the count of losses falling in the
    gated arm. Same math.comb machinery as the two-sided variant above.
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


def binom_pmf(k: int, n: int, p: float) -> float:
    """P(X = k) for X ~ Binomial(n, p)."""
    return math.comb(n, k) * p**k * (1.0 - p) ** (n - k)


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p).

    Adapted verbatim from gap_analysis.py (04-09, commit 545d4b6).
    """
    return sum(math.comb(n, i) * p**i * (1.0 - p) ** (n - i) for i in range(k + 1))


def pct(x: float) -> str:
    return f"{100.0 * x:.2f}%"


def ci_str(losses: int, n: int) -> str:
    lo, hi = wilson_interval(losses, n)
    return f"[{pct(lo)}, {pct(hi)}]"


# ---------------------------------------------------------------------------
# Section 1: the multi-session evidence table (hard-coded, disk-asserted)
# ---------------------------------------------------------------------------

# (session, arm, device, lost, n, source citation)
# Sources:
#   spike 003 rows -- .planning/spikes/003-ack-paced-frames/
#     summary-20260716-210408.json (on disk; asserted below): baseline block
#     n=20 losses=0; arm "blind" query_n=41 query_loss_pct=14.6 (= 6/41);
#     arm "photons" query_n=50 query_loss_pct=0.0.
#   session A run 1 -- 04-UAT-TILES-run1-FAIL.json (on disk; asserted).
#   session A run 2 -- 5/132; bytes live at commit 5de88f6 (the superseded
#     04-06 Task 1 evidence, overwritten in place by 04-10) -- not on disk,
#     not assertable here.
#   session B rows -- 04-GAP-INVESTIGATION.json (on disk; asserted): the
#     04-08 five-arm investigation aggregates.
#   session C run 1 -- 04-UAT-TILES-amended-run1-FAIL.json (on disk;
#     asserted).
#   session C run 2 -- 04-UAT-TILES.json as of 04-10 commit d154ccf; the
#     file is asserted while it still carries the amended-absolute-gate
#     schema and skipped with a note once 04-11's paired run supersedes it
#     in place (the cited bytes then live at d154ccf).
EVIDENCE_ROWS: list[tuple[str, str, str, int, int, str]] = [
    ("spike-003", "ambient baseline", "Tiles I", 0, 20, "spike 003 summary"),
    ("spike-003", "blind-fire", "Tiles I", 6, 41, "spike 003 summary"),
    ("spike-003", "photons (gated)", "Tiles I", 0, 50, "spike 003 summary"),
    ("A", "gated run 1", "Tiles I", 4, 135, "04-UAT-TILES-run1-FAIL.json"),
    ("A", "gated run 2", "Tiles I", 5, 132, "commit 5de88f6"),
    ("B", "control (ambient)", "Tiles I", 0, 227, "04-GAP-INVESTIGATION.json"),
    ("B", "shipped (gated)", "Tiles I", 2, 189, "04-GAP-INVESTIGATION.json"),
    ("B", "replica", "Tiles I", 9, 185, "04-GAP-INVESTIGATION.json"),
    ("B", "sweep (10/15 FPS)", "Tiles I", 1, 210, "04-GAP-INVESTIGATION.json"),
    ("B", "fallback control", "Tiles II", 0, 114, "04-GAP-INVESTIGATION.json"),
    ("B", "fallback shipped", "Tiles II", 4, 84, "04-GAP-INVESTIGATION.json"),
    ("C", "gated run 1", "Tiles I", 12, 107, "04-UAT-TILES-amended-run1-FAIL.json"),
    ("C", "gated run 2", "Tiles I", 7, 122, "04-UAT-TILES.json @ d154ccf"),
]

# Session-level gated pooled counts (the ~8x variance demonstration).
SESSION_GATED_POOLED: list[tuple[str, int, int]] = [
    ("B (04-08 shipped arm)", 2, 189),
    ("A (04-06, runs 1+2)", 9, 267),
    ("C (04-10, runs 1+2)", 19, 229),
]

# Pooled shipped-path 20 FPS evidence (04-09 table i): 04-06 UAT 9/267 +
# 04-08 shipped 2/189 + 04-08 fallback shipped 4/84 = 15/540.
POOLED_GATED_LOST: int = 15
POOLED_GATED_N: int = 540

# Spike 003 blind-fire baseline (single 41-query session).
BLIND_LOST: int = 6
BLIND_N: int = 41

# Worst gated-round delivered_ratio ever measured (04-10 run 1 round 0,
# 21 ack expiries) -- asserted against disk below.
WORST_DELIVERED_RATIO: float = 0.6033


def _uat_gated_counts(data: dict[str, Any]) -> tuple[int, int]:
    lost = sum(r["queries_lost"] for r in data["rounds"])
    ok = sum(r["queries_ok"] for r in data["rounds"])
    return lost, ok + lost


def assert_evidence_against_disk() -> list[str]:
    """Assert every hard-coded count against its on-disk source. Returns notes."""
    notes: list[str] = []

    spike = json.loads(SPIKE_003_SUMMARY.read_text())
    baseline = next(e for e in spike if e["category"] == "baseline")
    assert baseline["n"] == 20 and baseline["losses"] == 0, baseline
    blind = next(e for e in spike if e.get("arm") == "blind")
    assert blind["query_n"] == BLIND_N, blind
    assert blind["query_loss_pct"] == round(100 * BLIND_LOST / BLIND_N, 1), blind
    photons = next(e for e in spike if e.get("arm") == "photons")
    assert photons["query_n"] == 50 and photons["query_loss_pct"] == 0.0, photons

    a1 = json.loads(SESSION_A_RUN1.read_text())
    assert _uat_gated_counts(a1) == (4, 135), _uat_gated_counts(a1)

    b = json.loads(SESSION_B_JSON.read_text())
    arms = b["arms"]

    def pooled(name: str) -> tuple[int, int]:
        p = arms[name]["pooled"]
        return p["queries_lost"], p["queries_ok"] + p["queries_lost"]

    assert pooled("control") == (0, 227), pooled("control")
    assert pooled("shipped") == (2, 189), pooled("shipped")
    assert pooled("replica") == (9, 185), pooled("replica")
    assert pooled("sweep") == (1, 210), pooled("sweep")
    fb = arms["fallback"]
    fb_ctrl = fb["control"]
    assert (
        fb_ctrl["queries_lost"],
        fb_ctrl["queries_ok"] + fb_ctrl["queries_lost"],
    ) == (
        0,
        114,
    ), fb_ctrl
    fb_lost = sum(r["queries_lost"] for r in fb["shipped_rounds"])
    fb_n = sum(r["queries_ok"] + r["queries_lost"] for r in fb["shipped_rounds"])
    assert (fb_lost, fb_n) == (4, 84), (fb_lost, fb_n)

    c1 = json.loads(SESSION_C_RUN1.read_text())
    assert _uat_gated_counts(c1) == (12, 107), _uat_gated_counts(c1)
    worst = min(r["delivered_ratio"] for r in c1["rounds"])
    assert worst == WORST_DELIVERED_RATIO, worst

    c2 = json.loads(SESSION_C_RUN2.read_text())
    if "fisher_alpha" in c2.get("thresholds", {}):
        notes.append(
            "note: 04-UAT-TILES.json now carries 04-11 paired-gate evidence; "
            "session C run 2 counts (7/122) are asserted against history at "
            "commit d154ccf, not against the live file."
        )
    else:
        assert _uat_gated_counts(c2) == (7, 122), _uat_gated_counts(c2)

    notes.append(
        "all on-disk sources match the hard-coded evidence table "
        "(session A run 2 = 5/132 cited at commit 5de88f6, not on disk)."
    )
    return notes


def section_evidence() -> None:
    print("(1) Multi-session evidence table (hard-coded, asserted against disk)")
    print(
        f"    {'session':<10} {'arm':<20} {'device':<9} {'lost/n':<9} "
        f"{'loss%':<8} wilson 95% CI"
    )
    for session, arm, device, lost, n, source in EVIDENCE_ROWS:
        print(
            f"    {session:<10} {arm:<20} {device:<9} {f'{lost}/{n}':<9} "
            f"{pct(lost / n):<8} {ci_str(lost, n):<18} <- {source}"
        )
    print()
    print("    session-level gated pooled rates (same code, same device, one day):")
    rates: list[float] = []
    for label, lost, n in SESSION_GATED_POOLED:
        rates.append(lost / n)
        print(
            f"      {label:<24} {lost}/{n} = {pct(lost / n)}  wilson {ci_str(lost, n)}"
        )
    spread = max(rates) / min(rates)
    print(
        f"      session-to-session spread: {pct(min(rates))} .. {pct(max(rates))} "
        f"= {spread:.1f}x"
    )
    for note in assert_evidence_against_disk():
        print(f"    {note}")
    print()


# ---------------------------------------------------------------------------
# Section 2: parameter derivations (each printed with its rule)
# ---------------------------------------------------------------------------


def section_derivations() -> None:
    print("(2) Parameter derivations (proposed values; operator decision required)")

    b1 = rule_of_three_upper(227)
    b2 = rule_of_three_upper(114)
    print(
        f"    V1 ambient validity bound {MAX_AMBIENT_LOSS_PCT}%: both healthy-session "
        f"control arms were lossless"
    )
    print(
        f"       (0/227 rule-of-three upper {pct(b1)}; 0/114 upper {pct(b2)}) -- a "
        f"session whose"
    )
    print(
        f"       prober-only ambient loss exceeds {MAX_AMBIENT_LOSS_PCT}% (~3 lost of "
        f"~120) is lossier than any"
    )
    print("       healthy session's statistical ceiling and cannot certify anything.")
    print(
        f"    V2 minimum ambient sample n >= {MIN_AMBIENT_QUERIES}: below that the "
        f"{MAX_AMBIENT_LOSS_PCT}% bound has no"
    )
    print(
        f"       resolution (rule-of-three at n=100 is already "
        f"{pct(rule_of_three_upper(100))})."
    )
    print(
        f"    V3 delivered-ratio sanity floor {MIN_GATED_DELIVERED_SANITY}: worst "
        f"gated round ever measured"
    )
    print(
        f"       delivered {WORST_DELIVERED_RATIO} (04-10 run 1 round 0, 21 ack "
        f"expiries) -- 0.50 fires"
    )
    print("       only on sessions more congested than anything in the evidence")
    print("       base. Session validity only, NOT pass/fail: above it, throttling")
    print("       is the flow control doing its job under ambient congestion.")

    pooled_rate = POOLED_GATED_LOST / POOLED_GATED_N
    blind_rate = BLIND_LOST / BLIND_N
    print(
        f"    Relative rule: one-sided Fisher exact p < {FISHER_ALPHA} (alpha matches "
        f"the 04-09 R3"
    )
    print(
        f"       precedent) AND blind/gated point ratio >= {MIN_IMPROVEMENT_RATIO} -- "
        f"a conservative floor on"
    )
    print(
        f"       'large improvement': the pooled historical improvement is "
        f"{blind_rate / pooled_rate:.2f}x"
    )
    print(
        f"       (gated {pct(pooled_rate)} pooled {POOLED_GATED_LOST}/"
        f"{POOLED_GATED_N} vs blind {pct(blind_rate)} = {BLIND_LOST}/{BLIND_N})."
    )
    print(
        f"    Clean escape {CLEAN_GATED_LOSS_PCT}%: gated pooled loss at or below the "
        f"healthy-ambient ceiling"
    )
    print("       (same bound as V1) proves non-starvation directly even when the")
    print("       same-session blind arm happens to be low -- without it, a clean")
    print("       session could FAIL for lack of a disease to improve on.")

    blind_lo, _ = wilson_interval(BLIND_LOST, BLIND_N)
    print(
        f"    Absolute ceiling {MAX_GATED_POOLED_LOSS_PCT}% pooled gated loss: "
        f"continuity with the operator's"
    )
    print("       last-approved bound, now applied pooled. It excludes the worst")
    print("       measured session outright (session C run 1, 11.21% pooled) and")
    print(
        f"       sits at {MAX_GATED_POOLED_LOSS_PCT / (100 * blind_rate):.2f}x the "
        f"single-session blind baseline, whose own Wilson"
    )
    print(
        f"       95% lower bound on {BLIND_LOST}/{BLIND_N} is {pct(blind_lo)} -- a "
        f"ceiling-grazing run still"
    )
    print("       needs the in-session Fisher win.")
    print()


# ---------------------------------------------------------------------------
# Section 3: exact power by enumeration (no normal approximations)
# ---------------------------------------------------------------------------


def _clean(x_g: int, n: int) -> bool:
    return 100.0 * x_g / n <= CLEAN_GATED_LOSS_PCT


def _ceiling(x_g: int, n: int) -> bool:
    return 100.0 * x_g / n <= MAX_GATED_POOLED_LOSS_PCT


def _ratio_ok(x_g: int, x_b: int) -> bool:
    if x_g == 0:
        return x_b > 0
    return x_b / x_g >= MIN_IMPROVEMENT_RATIO


def _relative_table(n: int) -> list[list[bool]]:
    """rel[x_g][x_b] = the relative rule fires (Fisher p < alpha AND ratio >= 2)."""
    rel = [[False] * (n + 1) for _ in range(n + 1)]
    for x_g in range(n + 1):
        for x_b in range(n + 1):
            if not _ratio_ok(x_g, x_b):
                continue
            p = fisher_one_sided(x_g, n - x_g, x_b, n - x_b)
            if p < FISHER_ALPHA:
                rel[x_g][x_b] = True
    return rel


def _power(
    n: int, p_g: float, p_b: float, rel: list[list[bool]]
) -> tuple[float, float, float]:
    """(P(relative rule fires), P(clean escape), P(PASS overall)) at per-arm n."""
    pmf_g = [binom_pmf(x, n, p_g) for x in range(n + 1)]
    pmf_b = [binom_pmf(x, n, p_b) for x in range(n + 1)]
    p_clean = sum(pmf_g[x] for x in range(n + 1) if _clean(x, n))
    p_rel = 0.0
    p_pass = 0.0
    for x_g in range(n + 1):
        if pmf_g[x_g] == 0.0:
            continue
        rel_row = rel[x_g]
        rel_mass = sum(pmf_b[x_b] for x_b in range(n + 1) if rel_row[x_b])
        p_rel += pmf_g[x_g] * rel_mass
        if not _ceiling(x_g, n):
            continue
        if _clean(x_g, n):
            p_pass += pmf_g[x_g]
        else:
            p_pass += pmf_g[x_g] * rel_mass
    return p_rel, p_clean, p_pass


def section_power() -> None:
    print("(3) Exact power by enumeration (X_g ~ Bin(n, p_g), X_b ~ Bin(n, p_b))")
    print(
        "    PASS = pooled gated <= 9.0% AND (gated <= 2.5% OR (Fisher one-sided"
        f" p < {FISHER_ALPHA} AND"
    )
    print(
        f"    blind/gated >= {MIN_IMPROVEMENT_RATIO})); session validity assumed "
        f"held (it gates INCONCLUSIVE, not FAIL)."
    )
    historical = ("historical rates", 0.0278, 0.146)
    degraded = ("uniform degradation (+3 points both arms)", 0.0578, 0.176)
    proportional = [
        (f"proportional p_b = 5.25 * p_g at severity {pg:.4f}", pg, 5.25 * pg)
        for pg in (0.0106, 0.0337, 0.0574, 0.083)
    ]
    scenarios = [historical, degraded, *proportional]

    pass_at_declared: float | None = None
    for n in (100, 120, 140):
        rel = _relative_table(n)
        print(f"    per-arm n = {n}:")
        for label, p_g, p_b in scenarios:
            p_rel, p_clean, p_pass = _power(n, p_g, p_b, rel)
            print(
                f"      p_g={p_g:.4f} p_b={p_b:.4f}  P(relative)={p_rel:.4f}  "
                f"P(clean)={p_clean:.4f}  P(PASS)={p_pass:.4f}  <- {label}"
            )
            if n == 100 and label == historical[0]:
                pass_at_declared = p_pass
        print()

    assert pass_at_declared is not None
    print(
        "    Adjustment rule (declared before computing): if P(PASS) at the historical"
    )
    print(
        "    rates with n=100 is below 0.85, raise rounds per arm from 3 to 4. Observed"
    )
    if pass_at_declared < 0.85:
        verdict = "rule FIRED: recompute at 4 rounds/arm"
    else:
        verdict = "rule did NOT fire: 3 rounds per arm stands"
    print(f"    P(PASS | historical, n=100) = {pass_at_declared:.4f} -> {verdict}.")
    print()


# ---------------------------------------------------------------------------
# Section 4: retrodiction against every historical session
# ---------------------------------------------------------------------------


def section_retrodiction() -> None:
    print("(4) Retrodiction: the proposed rule applied where its inputs exist")

    # Session B: ambient 0/227 (valid, n >= 100); gated (shipped) 2/189 = 1.06%
    # <= 2.5% clean escape; all delivered ratios >= 0.50; no blind arm needed.
    b_rate = 100 * 2 / 189
    print(
        f"    session B: ambient 0/227 valid (n >= {MIN_AMBIENT_QUERIES}); gated "
        f"2/189 = {b_rate:.2f}% <= {CLEAN_GATED_LOSS_PCT}%"
    )
    print("      -> PASS via the clean escape (no comparator needed).")

    # Session C run 1: gated 12/107 = 11.21% > 9.0% ceiling.
    c1_rate = 100 * 12 / 107
    print(
        f"    session C run 1: gated 12/107 = {c1_rate:.2f}% > "
        f"{MAX_GATED_POOLED_LOSS_PCT}% ceiling"
    )
    print(
        "      -> FAIL the ceiling outright, regardless of any comparator ('relatively"
    )
    print(
        "      better but absurdly lossy' cannot pass). No ambient block was measured;"
    )
    print("      the ceiling verdict does not depend on one.")

    # Spike 003: photons 0/50 vs blind 6/41 -- relative rule inputs exist.
    p_spike = fisher_one_sided(0, 50, BLIND_LOST, BLIND_N - BLIND_LOST)
    print(
        f"    spike 003: gated 0/50 vs blind 6/41 -- Fisher one-sided p = "
        f"{p_spike:.4f} < {FISHER_ALPHA};"
    )
    print(
        "      ratio satisfied (gated lost 0, blind lost 6). But its ambient "
        "baseline was"
    )
    print(
        f"      n = 20 < {MIN_AMBIENT_QUERIES} -> INCONCLUSIVE on ambient power "
        f"(validity V2)."
    )

    # Sessions A and C run 2: no paired blind arm was measured.
    print("    session A (9/267) and session C run 2 (7/122): INDETERMINATE -- no")
    print("      paired blind arm was run; the retrodiction cannot manufacture")
    print("      comparators that were never measured. This is precisely the gap")
    print("      the paired redesign closes.")
    print()


# ---------------------------------------------------------------------------
# Section 5: cross-check against the committed Fisher reference (04-08 table)
# ---------------------------------------------------------------------------


def section_crosscheck() -> None:
    print("(5) Cross-check: Fisher machinery vs the committed 04-08 reference")
    p_two = fisher_exact_two_sided(2, 187, 9, 176)
    p_one = fisher_one_sided(2, 187, 9, 176)
    print(f"    two-sided p on shipped [2, 187] vs replica [9, 176] = {p_two:.4f}")
    print(f"    one-sided p on the same table = {p_one:.4f}")
    assert round(p_two, 4) == 0.0342, p_two
    assert 0.0 < p_one <= p_two, (p_one, p_two)
    print("    reproduces 0.0342; one-sided positive and <= two-sided. OK")
    print()


def main() -> None:
    print("=== 04-11 criterion design: paired-relative ANIM-03 gate ===")
    print()
    section_evidence()
    section_derivations()
    section_power()
    section_retrodiction()
    section_crosscheck()


if __name__ == "__main__":
    main()
