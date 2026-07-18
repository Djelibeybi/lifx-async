"""Reproducible statistics for the 04-12 cross-device ANIM-03/ANIM-04 sweep design.

Every number in ``04-SWEEP-DESIGN.md`` is reproducible by rerunning:

    uv run python .planning/phases/04-animation-flow-control/sweep_design.py

The script re-derives the per-device paired-relative pass probability at the
historical rates by exact enumeration (cross-checked against the committed
04-CRITERION-DESIGN.md value 0.9008 BEFORE that number is used as an
aggregation input), computes the null-scenario per-device pass rates
(p_gated = p_blind -- flow control gives no improvement), enumerates the
exact-binomial cross-device aggregation power for allowed-FAIL counts 0/1/2
across N_valid in {5, 6, 7}, surfaces the all-must-pass power explicitly,
selects K by the pre-declared rule (minimum acceptable P(sweep PASS |
historical per-device rate) = 0.85, matching the 04-11 adjustment-rule bar;
strictest K meeting it), derives the quorum so a sweep can never certify from
a minority of the 7-device gate roster, verifies the three ANIM-04
packets/frame worked examples, and shows the session-logistics arithmetic.

This script computes; it decides nothing. The criterion itself is an
operator decision taken at the 04-12 blocking checkpoint from the design
brief's "## Final wording" section.

Zero third-party dependencies: stdlib only. The per-device paired-relative
machinery (``fisher_one_sided``, ``binom_pmf``, the relative-rule table and
the exact power enumeration) is copied from the committed
``criterion_design.py`` (04-11, standalone-script discipline) -- the
per-device rule itself is reused UNCHANGED.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

HERE: Path = Path(__file__).resolve().parent
PAIRED_RUN1: Path = HERE / "04-UAT-TILES-paired-run1-FAIL.json"
PAIRED_RUN2: Path = HERE / "04-UAT-TILES.json"

# ---------------------------------------------------------------------------
# Per-device paired-relative rule parameters -- reused UNCHANGED from
# 04-CRITERION-DESIGN.md (operator-approved at the 04-11 checkpoint,
# verbatim reply "1"). NOT re-tuned by this design.
# ---------------------------------------------------------------------------

MAX_AMBIENT_LOSS_PCT: float = 2.5  # session validity V1
MIN_AMBIENT_QUERIES: int = 100  # session validity V2
MIN_GATED_DELIVERED_SANITY: float = 0.50  # session validity V3
FISHER_ALPHA: float = 0.05  # relative rule significance
MIN_IMPROVEMENT_RATIO: float = 2.0  # relative rule point-ratio floor
CLEAN_GATED_LOSS_PCT: float = 2.5  # clean escape
MAX_GATED_POOLED_LOSS_PCT: float = 9.0  # absolute ceiling

# Declared per-arm sample basis (04-CRITERION-DESIGN.md power section).
N_PER_ARM: int = 100

# Historical per-device rates (04-CRITERION-DESIGN.md: gated pooled
# 15/540 = 2.78%; single-session blind baseline 6/41 = 14.6%).
P_GATED_HISTORICAL: float = 0.0278
P_BLIND_HISTORICAL: float = 0.146

# Committed per-device pass probability at the historical rates
# (04-CRITERION-DESIGN.md power table, n = 100) -- cross-checked by exact
# enumeration in section (2) below BEFORE being used as an aggregation
# input.
P_PASS_HISTORICAL_COMMITTED: float = 0.9008

# ---------------------------------------------------------------------------
# NEW parameters this design derives (values confirmed by the enumeration
# below; NOT applied anywhere until the operator approves them at the 04-12
# checkpoint).
# ---------------------------------------------------------------------------

GATE_DEVICES: int = 7  # the gate roster population (Tiles II never counted)
AGGREGATION_BAR: float = 0.85  # pre-declared minimum P(sweep PASS | historical)
MAJORITY_OF_ROSTER: int = GATE_DEVICES // 2 + 1  # 4 of 7

# ---------------------------------------------------------------------------
# Per-device machinery, copied from criterion_design.py (04-11)
# ---------------------------------------------------------------------------


def fisher_one_sided(
    gated_lost: int, gated_ok: int, blind_lost: int, blind_ok: int
) -> float:
    """One-sided Fisher exact p (alternative: gated loss rate < blind loss rate).

    Copied verbatim from criterion_design.py (04-11): conditioning on the
    total number of losses, p is the hypergeometric lower tail
    P(X <= gated_lost) where X is the count of losses falling in the gated
    arm.
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


def _clean(x_g: int, n: int) -> bool:
    return 100.0 * x_g / n <= CLEAN_GATED_LOSS_PCT


def _ceiling(x_g: int, n: int) -> bool:
    return 100.0 * x_g / n <= MAX_GATED_POOLED_LOSS_PCT


def _ratio_ok(x_g: int, x_b: int) -> bool:
    if x_g == 0:
        return x_b > 0
    return x_b / x_g >= MIN_IMPROVEMENT_RATIO


def _relative_table(n: int) -> list[list[bool]]:
    """rel[x_g][x_b] = the relative rule fires (Fisher p < alpha AND ratio >= 2).

    Copied verbatim from criterion_design.py (04-11).
    """
    rel = [[False] * (n + 1) for _ in range(n + 1)]
    for x_g in range(n + 1):
        for x_b in range(n + 1):
            if not _ratio_ok(x_g, x_b):
                continue
            p = fisher_one_sided(x_g, n - x_g, x_b, n - x_b)
            if p < FISHER_ALPHA:
                rel[x_g][x_b] = True
    return rel


def per_device_pass_probability(
    n: int, p_g: float, p_b: float, rel: list[list[bool]]
) -> float:
    """P(per-device PASS) by exact enumeration -- criterion_design.py `_power`.

    PASS = pooled gated <= ceiling AND (clean escape OR relative rule);
    session validity assumed held (its failure routes to INCONCLUSIVE and is
    handled by the aggregation's N_valid exclusion, never by this
    probability).
    """
    pmf_g = [binom_pmf(x, n, p_g) for x in range(n + 1)]
    pmf_b = [binom_pmf(x, n, p_b) for x in range(n + 1)]
    p_pass = 0.0
    for x_g in range(n + 1):
        if pmf_g[x_g] == 0.0:
            continue
        if not _ceiling(x_g, n):
            continue
        if _clean(x_g, n):
            p_pass += pmf_g[x_g]
        else:
            rel_row = rel[x_g]
            rel_mass = sum(pmf_b[x_b] for x_b in range(n + 1) if rel_row[x_b])
            p_pass += pmf_g[x_g] * rel_mass
    return p_pass


def per_device_clean_probability(n: int, p_g: float) -> float:
    """P(clean escape alone: gated pooled <= 2.5%) by exact enumeration."""
    return sum(binom_pmf(x, n, p_g) for x in range(n + 1) if _clean(x, n))


# ---------------------------------------------------------------------------
# Cross-device aggregation: exact binomial enumeration
# ---------------------------------------------------------------------------


def p_sweep_pass(n_valid: int, k: int, p_device: float) -> float:
    """P(at least k of n_valid independent devices PASS) -- exact binomial."""
    return sum(binom_pmf(x, n_valid, p_device) for x in range(k, n_valid + 1))


# ---------------------------------------------------------------------------
# ANIM-04 packets/frame expectation -- read-only mirror of
# MatrixPacketGenerator's row-aligned chunking rule
# (src/lifx/animation/packets.py: rows_per_packet = 64 // tile_width;
# packets_per_tile = ceil(tile_height / rows_per_packet); large tiles add
# one final CopyFrameBuffer per tile).
# ---------------------------------------------------------------------------


def expected_packets_per_frame(tile_count: int, width: int, height: int) -> int:
    """Expected packets per sent frame from reported chain dimensions."""
    pixels = width * height
    if pixels <= 64:
        return tile_count  # one Set64 per tile, no CopyFrameBuffer
    rows_per_packet = 64 // width
    set64_per_tile = -(-height // rows_per_packet)  # ceil division
    return tile_count * (set64_per_tile + 1)  # + final CopyFrameBuffer per tile


# ---------------------------------------------------------------------------
# Section 1: the paired double-FAIL evidence that motivated the retarget
# (hard-coded, disk-asserted; reclassified as reference data by the ruling)
# ---------------------------------------------------------------------------


def _paired_counts(data: dict[str, Any]) -> tuple[int, int, int, int]:
    """(gated_lost, gated_n, blind_lost, blind_n) from a paired results JSON."""
    g = data["gated_pooled"]
    b = data["blind_pooled"]
    return g["lost"], g["n"], b["lost"], b["n"]


def section_evidence() -> None:
    print("(1) The paired double-FAIL evidence (System Test Tiles I, 04-11)")
    run1 = json.loads(PAIRED_RUN1.read_text())
    run2 = json.loads(PAIRED_RUN2.read_text())

    g1, gn1, b1, bn1 = _paired_counts(run1)
    assert (g1, gn1, b1, bn1) == (4, 136, 9, 125), (g1, gn1, b1, bn1)
    assert run1["session_valid"] is True
    p1 = fisher_one_sided(g1, gn1 - g1, b1, bn1 - b1)
    r1 = (100 * b1 / bn1) / (100 * g1 / gn1)
    assert round(p1, 4) == 0.0973, p1
    assert round(r1, 2) == 2.45, r1

    g2, gn2, b2, bn2 = _paired_counts(run2)
    assert (g2, gn2, b2, bn2) == (7, 127, 11, 113), (g2, gn2, b2, bn2)
    assert run2["session_valid"] is True
    p2 = fisher_one_sided(g2, gn2 - g2, b2, bn2 - b2)
    r2 = (100 * b2 / bn2) / (100 * g2 / gn2)
    assert round(p2, 4) == 0.1601, p2
    assert round(r2, 2) == 1.77, r2

    print(
        f"    run 1: gated {g1}/{gn1} = {100 * g1 / gn1:.2f}% vs blind "
        f"{b1}/{bn1} = {100 * b1 / bn1:.2f}%  ratio {r1:.2f}x  "
        f"Fisher one-sided p = {p1:.4f}  (VALID session, FAIL)"
    )
    print(
        f"    run 2: gated {g2}/{gn2} = {100 * g2 / gn2:.2f}% vs blind "
        f"{b2}/{bn2} = {100 * b2 / bn2:.2f}%  ratio {r2:.2f}x  "
        f"Fisher one-sided p = {p2:.4f}  (VALID session, FAIL)"
    )
    print(
        "    Under the operator's Tiles ruling these sessions reclassify as "
        "REFERENCE data:"
    )
    print(
        "    consistent 1.77-2.45x gated wins on a known-flaky gen3 Tiles radio "
        "-- supporting"
    )
    print("    evidence for the ruling, no longer a gate. Counts asserted against")
    print("    the committed evidence files on disk. OK")
    print()


# ---------------------------------------------------------------------------
# Section 2: cross-check the committed per-device pass probability
# ---------------------------------------------------------------------------


def section_crosscheck(rel: list[list[bool]]) -> None:
    print("(2) Cross-check: per-device P(PASS | historical rates) by exact enumeration")
    p_pass = per_device_pass_probability(
        N_PER_ARM, P_GATED_HISTORICAL, P_BLIND_HISTORICAL, rel
    )
    print(
        f"    p_g = {P_GATED_HISTORICAL}, p_b = {P_BLIND_HISTORICAL}, "
        f"n = {N_PER_ARM}/arm -> P(PASS) = {p_pass:.4f}"
    )
    assert round(p_pass, 4) == P_PASS_HISTORICAL_COMMITTED, p_pass
    print(
        f"    reproduces the committed 04-CRITERION-DESIGN.md value "
        f"{P_PASS_HISTORICAL_COMMITTED} -- the aggregation input is verified "
        f"before use. OK"
    )
    print()


# ---------------------------------------------------------------------------
# Section 3: null-scenario per-device rates (false-pass risk, computed)
# ---------------------------------------------------------------------------


def section_null(rel: list[list[bool]]) -> tuple[float, float]:
    print("(3) Null scenario: flow control gives NO improvement (p_gated = p_blind)")
    print(
        "    The relative rule cannot systematically fire under the null (Fisher type-I"
    )
    print(
        f"    error <= alpha = {FISHER_ALPHA} by construction); only the clean "
        f"escape (plus chance"
    )
    print("    Fisher wins at the low rate) can produce a per-device PASS.")
    null_low = per_device_pass_probability(N_PER_ARM, 0.0278, 0.0278, rel)
    clean_low = per_device_clean_probability(N_PER_ARM, 0.0278)
    null_high = per_device_pass_probability(N_PER_ARM, 0.146, 0.146, rel)
    clean_high = per_device_clean_probability(N_PER_ARM, 0.146)
    print(
        f"    both arms at 0.0278 (ambient-healthy, low loss): per-device "
        f"P(PASS | null) = {null_low:.4f}"
    )
    print(
        f"      of which clean escape alone = {clean_low:.4f} -- gated pooled "
        f"<= {CLEAN_GATED_LOSS_PCT}% is DIRECT"
    )
    print("      non-starvation evidence at the healthy-ambient ceiling: a device")
    print("      whose gated loss is at or below the healthy floor is not being")
    print("      starved, which is exactly what ANIM-03 certifies -- an honest")
    print("      per-device PASS path even when the same-session blind arm")
    print("      happens to be low.")
    print(
        f"    both arms at 0.146 (lossy, no improvement): per-device "
        f"P(PASS | null) = {null_high:.4f}"
    )
    print(
        f"      (clean escape {clean_high:.6f}; the {MAX_GATED_POOLED_LOSS_PCT}% "
        f"ceiling blocks nearly all draws"
    )
    print("      and Fisher cannot systematically fire -- a lossy device that the")
    print("      flow control does not help essentially never passes).")
    print()
    return null_low, null_high


# ---------------------------------------------------------------------------
# Section 4: cross-device aggregation power (exact binomial enumeration)
# ---------------------------------------------------------------------------


def section_aggregation(
    p_hist: float, null_low: float, null_high: float
) -> tuple[int, int]:
    print("(4) Cross-device aggregation: sweep PASS iff N_valid >= quorum AND")
    print("    per-device PASSes among valid gate devices >= K = N_valid - a")
    print("    (a = allowed FAILs). INCONCLUSIVE and ENV-ERROR rows are excluded")
    print("    from N_valid but always reported; FAILs count in N_valid; Tiles II")
    print("    is never in either count.")
    print()

    grid = [0.85, round(p_hist, 4), 0.95]
    print(
        f"    P(sweep PASS) by exact binomial enumeration, per-device P(PASS) in "
        f"{grid}:"
    )
    print(f"    {'N_valid':<9} {'allowed FAILs':<15} {'K':<4}", end="")
    for p in grid:
        print(f" P@{p:<7}", end="")
    print()
    for n_valid in (7, 6, 5):
        for a in (0, 1, 2):
            k = n_valid - a
            print(f"    {n_valid:<9} {a:<15} {k:<4}", end="")
            for p in grid:
                print(f" {p_sweep_pass(n_valid, k, p):<9.4f}", end="")
            print()
    print()

    all_must_pass = p_hist**GATE_DEVICES
    print(
        "    ALL-MUST-PASS POWER, surfaced explicitly: at the historical "
        "per-device rate"
    )
    print(
        f"    ({p_hist:.4f}), requiring 7/7 gives P(sweep PASS) = "
        f"{p_hist:.4f}^7 = {all_must_pass:.4f} --"
    )
    print("    a coin-flip sweep. Any zero-allowed-FAILs choice is made with this")
    print("    number in front of the operator, never blindly.")
    print()

    print("    Choice rule (pre-declared, 04-11 precedent): minimum acceptable")
    print(
        f"    P(sweep PASS | historical per-device rate, N_valid = "
        f"{GATE_DEVICES}) = {AGGREGATION_BAR}"
    )
    print("    (the 04-11 adjustment-rule bar); pick the STRICTEST K meeting it.")
    chosen_a: int | None = None
    for a in (0, 1, 2):
        power = p_sweep_pass(GATE_DEVICES, GATE_DEVICES - a, p_hist)
        meets = power >= AGGREGATION_BAR
        chosen_here = meets and chosen_a is None
        marker = " -> CHOSEN (strictest meeting the bar)" if chosen_here else ""
        print(
            f"      a = {a} (K = N_valid - {a}): P(sweep PASS | historical) = "
            f"{power:.4f} {'>=' if meets else '<'} {AGGREGATION_BAR}{marker}"
        )
        if chosen_here:
            chosen_a = a
    assert chosen_a is not None, "no allowed-FAIL count meets the bar"
    print()

    # Quorum derivation: a sweep must never certify from a minority of the
    # 7-device gate roster. At the quorum floor N_valid = Q, the minimum
    # certifying PASS count is K = Q - chosen_a; require K >= majority(7) = 4.
    quorum = MAJORITY_OF_ROSTER + chosen_a
    print(
        "    Quorum derivation: at the quorum floor the minimum certifying PASS "
        "count is"
    )
    print(
        f"    Q - {chosen_a}; requiring that to be >= a strict majority of the "
        f"{GATE_DEVICES}-device roster"
    )
    print(
        f"    ({MAJORITY_OF_ROSTER}) gives Q = {MAJORITY_OF_ROSTER} + {chosen_a} "
        f"= {quorum}. Below quorum the sweep is INCONCLUSIVE."
    )
    assert quorum - chosen_a >= MAJORITY_OF_ROSTER
    print()

    k_at_full = GATE_DEVICES - chosen_a
    power_chosen = p_sweep_pass(GATE_DEVICES, k_at_full, p_hist)
    null_sweep_low = p_sweep_pass(GATE_DEVICES, k_at_full, null_low)
    null_sweep_high = p_sweep_pass(GATE_DEVICES, k_at_full, null_high)
    print("    CHOSEN RULE, one sentence a harness can implement:")
    print(
        f"      The sweep PASSes iff at least {quorum} of the {GATE_DEVICES} "
        f"gate devices produce valid"
    )
    print(
        f"      sessions (N_valid >= {quorum}) and at most {chosen_a} of those "
        f"valid sessions is a FAIL"
    )
    print(
        f"      (per-device PASSes >= N_valid - {chosen_a}); Tiles II never "
        f"enters either count."
    )
    print()
    print(f"    For the chosen rule at N_valid = {GATE_DEVICES}:")
    print(f"      power:  P(sweep PASS | historical rates)        = {power_chosen:.4f}")
    print(
        f"      null:   P(sweep PASS | no improvement, both 0.0278) = "
        f"{null_sweep_low:.4f}"
    )
    print(
        f"      null:   P(sweep PASS | no improvement, both 0.146)  = "
        f"{null_sweep_high:.6f}"
    )
    print("    What the rule certifies: on at least a strict roster majority of")
    print("    healthy-radio devices, ack-gated streaming either measurably beats")
    print("    same-session blind-fire (significance + ratio) or holds gated loss")
    print("    at the healthy-ambient ceiling (direct non-starvation) -- and the")
    print("    low-rate null 'pass' is precisely a fleet that is not starving,")
    print("    which is the requirement's own success condition.")
    print()
    return chosen_a, quorum


# ---------------------------------------------------------------------------
# Section 5: ANIM-04 packets/frame worked examples
# ---------------------------------------------------------------------------


def section_packets() -> None:
    print("(5) ANIM-04 packets/frame expectation (row-aligned rule, read-only")
    print("    mirror of MatrixPacketGenerator in src/lifx/animation/packets.py)")
    cases = [
        (
            1,
            13,
            26,
            8,
            "13x26 Capsule: 64//13=4 rows/pkt, ceil(26/4)=7 Set64, +1 CopyFB",
        ),
        (1, 16, 8, 3, "16x8 ceiling: 64//16=4 rows/pkt, ceil(8/4)=2 Set64, +1 CopyFB"),
        (5, 8, 8, 5, "five 8x8 tiles: 64 px <= 64 -> one Set64 per tile, no CopyFB"),
    ]
    for tiles, w, h, want, note in cases:
        got = expected_packets_per_frame(tiles, w, h)
        assert got == want, (tiles, w, h, got, want)
        print(f"    expected_packets_per_frame({tiles}, {w}, {h}) = {got}  <- {note}")
    print("    all three worked examples verified. OK")
    print()


# ---------------------------------------------------------------------------
# Section 6: session logistics arithmetic
# ---------------------------------------------------------------------------


def section_logistics() -> None:
    print("(6) Session logistics arithmetic")
    ambient_seconds = 60.0
    query_rate = 2.0
    max_queries = int(ambient_seconds * query_rate)
    run1 = json.loads(PAIRED_RUN1.read_text())
    run2 = json.loads(PAIRED_RUN2.read_text())
    n1 = run1["ambient"]["queries_ok"] + run1["ambient"]["queries_lost"]
    n2 = run2["ambient"]["queries_ok"] + run2["ambient"]["queries_lost"]
    assert (n1, n2) == (113, 114), (n1, n2)
    print(
        f"    ambient block retention: 60 s at the fixed {query_rate} q/s cadence "
        f"yields at most"
    )
    print(
        f"    ~{max_queries} queries; measured healthy sessions yielded {n1} and "
        f"{n2} (disk-asserted)."
    )
    print(
        f"    V2's non-retunable n >= {MIN_AMBIENT_QUERIES} therefore leaves no "
        f"material shortening room:"
    )
    print("    60 s stays.")
    session = 60 + 3 * (10 + 30) * 2
    print(
        "    per-device wall time: 60 s ambient + 3 round-pairs x (10 s rest + "
        "30 s gated +"
    )
    print(
        f"    10 s rest + 30 s blind) = {session} s = {session / 60:.0f} min "
        f"streaming + setup"
    )
    print("    (resolution, chain query, per-round animator setup, restore)")
    print("    ~= 5.25-5.5 min/device; 8 devices SEQUENTIAL (measurement isolation")
    print(
        f"    and network load) ~= {8 * 5.5:.0f} min streaming + "
        f"resolution/restore overhead"
    )
    print("    -> ~45-55 min total.")
    print()


def main() -> None:
    print("=== 04-12 sweep design: cross-device ANIM-03/ANIM-04 aggregation ===")
    print()
    section_evidence()
    rel = _relative_table(N_PER_ARM)
    section_crosscheck(rel)
    null_low, null_high = section_null(rel)
    # The aggregation input is the DECLARED committed value 0.9008, used only
    # after section (2) has verified the exact enumeration reproduces it.
    section_aggregation(P_PASS_HISTORICAL_COMMITTED, null_low, null_high)
    section_packets()
    section_logistics()


if __name__ == "__main__":
    main()
