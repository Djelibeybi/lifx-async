"""Render Spike 001 results JSONL into a self-contained HTML report.

Usage:
  uv run python .planning/spikes/001-modem-sleep-keepalive/report.py \
      .planning/spikes/001-modem-sleep-keepalive/results-<runid>.jsonl
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

CHART_W, CHART_H, PAD_L, PAD_B, PAD_T = 640, 220, 60, 34, 16


def load(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip() and json.loads(line).get("category") == "trial"
    ]


def svg_idle_curve(trials: list[dict[str, Any]]) -> str:
    steps = sorted({t["idle_s"] for t in trials})
    by_step: dict[float, list[float | None]] = defaultdict(list)
    for t in trials:
        by_step[t["idle_s"]].append(t["first_probe_ms"])
    values = [v for vs in by_step.values() for v in vs if v is not None]
    if not values:
        return "<p>No data.</p>"
    y_max = max(max(values) * 1.15, 30.0)
    xw = (CHART_W - PAD_L - 20) / max(len(steps) - 1, 1)

    def x(i: int) -> float:
        return PAD_L + i * xw

    def y(v: float) -> float:
        return PAD_T + (CHART_H - PAD_T - PAD_B) * (1 - v / y_max)

    parts = [
        f'<svg viewBox="0 0 {CHART_W} {CHART_H}" role="img" '
        f'style="max-width:100%;height:auto">'
    ]
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        gy = y(y_max * frac)
        parts.append(
            f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{CHART_W - 20}" y2="{gy:.1f}" '
            f'stroke="currentColor" stroke-opacity="0.15"/>'
            f'<text x="{PAD_L - 6}" y="{gy + 4:.1f}" text-anchor="end" '
            f'font-size="10" fill="currentColor">{y_max * frac:.0f}ms</text>'
        )
    medians: list[tuple[float, float]] = []
    for i, step in enumerate(steps):
        vals = [v for v in by_step[step] if v is not None]
        losses = sum(1 for v in by_step[step] if v is None)
        for v in vals:
            parts.append(
                f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3" '
                f'fill="#4098d7" fill-opacity="0.55"/>'
            )
        if vals:
            medians.append((x(i), y(statistics.median(vals))))
        if losses:
            parts.append(
                f'<text x="{x(i):.1f}" y="{PAD_T + 10}" text-anchor="middle" '
                f'font-size="11" fill="#d64545">{losses}✕</text>'
            )
        parts.append(
            f'<text x="{x(i):.1f}" y="{CHART_H - PAD_B + 16}" text-anchor="middle" '
            f'font-size="10" fill="currentColor">{step:g}s</text>'
        )
    if len(medians) > 1:
        pts = " ".join(f"{mx:.1f},{my:.1f}" for mx, my in medians)
        parts.append(
            f'<polyline points="{pts}" fill="none" stroke="#4098d7" stroke-width="2"/>'
        )
    parts.append(
        f'<text x="{(CHART_W + PAD_L) / 2:.0f}" y="{CHART_H - 4}" text-anchor="middle" '
        f'font-size="10" fill="currentColor">idle before first probe</text></svg>'
    )
    return "".join(parts)


def svg_ab(trials: list[dict[str, Any]]) -> str:
    groups = {"no-keepalive": [], "keepalive": []}
    losses = {"no-keepalive": 0, "keepalive": 0}
    for t in trials:
        key = "keepalive" if t["keepalive"] else "no-keepalive"
        if t["first_probe_ms"] is None:
            losses[key] += 1
        else:
            groups[key].append(t["first_probe_ms"])
    values = [v for vs in groups.values() for v in vs]
    if not values:
        return "<p>No data.</p>"
    y_max = max(max(values) * 1.15, 30.0)
    h = 180

    def y(v: float) -> float:
        return PAD_T + (h - PAD_T - PAD_B) * (1 - v / y_max)

    parts = [f'<svg viewBox="0 0 360 {h}" style="max-width:100%;height:auto">']
    for frac in (0.0, 0.5, 1.0):
        gy = y(y_max * frac)
        parts.append(
            f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="340" y2="{gy:.1f}" '
            f'stroke="currentColor" stroke-opacity="0.15"/>'
            f'<text x="{PAD_L - 6}" y="{gy + 4:.1f}" text-anchor="end" '
            f'font-size="10" fill="currentColor">{y_max * frac:.0f}ms</text>'
        )
    for gi, (name, vals) in enumerate(groups.items()):
        cx = 140 + gi * 140
        colour = "#d64545" if name == "no-keepalive" else "#3f9142"
        for v in vals:
            parts.append(
                f'<circle cx="{cx + (hash(str(v)) % 40 - 20) * 0.8:.1f}" '
                f'cy="{y(v):.1f}" r="3" fill="{colour}" fill-opacity="0.55"/>'
            )
        if vals:
            my = y(statistics.median(vals))
            parts.append(
                f'<line x1="{cx - 34}" y1="{my:.1f}" x2="{cx + 34}" y2="{my:.1f}" '
                f'stroke="{colour}" stroke-width="2.5"/>'
            )
        label = name + (f" ({losses[name]}✕ lost)" if losses[name] else "")
        parts.append(
            f'<text x="{cx}" y="{h - 8}" text-anchor="middle" font-size="11" '
            f'fill="currentColor">{label}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    path = Path(sys.argv[1])
    trials = load(path)
    bulbs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trials:
        bulbs[f"{t['label']} ({t['bulb']})"].append(t)
    sections = []
    for bulb, ts in sorted(bulbs.items()):
        curve = [t for t in ts if t["phase"] == "idle_curve"]
        ab = [t for t in ts if t["phase"] == "keepalive_ab"]
        awake = [r for t in ts for r in t["rtts_ms"][1:] if r is not None]
        awake_med = statistics.median(awake) if awake else 0
        sections.append(
            f"<section><h2>{bulb}</h2>"
            f"<p>Awake baseline (probes 2–5 of every train): "
            f"median {awake_med:.1f} ms over {len(awake)} probes.</p>"
            f"<h3>First-probe RTT vs idle duration</h3>{svg_idle_curve(curve)}"
            f"<h3>Keepalive A/B (60 s idle)</h3>{svg_ab(ab)}</section>"
        )
    html = (
        "<title>Spike 001: modem-sleep-keepalive results</title>"
        "<style>body{font-family:system-ui;max-width:720px;margin:2rem auto;"
        "padding:0 1rem;line-height:1.5}section{margin-bottom:2.5rem}"
        "h2{border-bottom:1px solid currentColor;padding-bottom:.2rem}</style>"
        f"<h1>Spike 001: post-idle latency &amp; keepalive A/B</h1>"
        f"<p>Source: <code>{path.name}</code>. Dots are individual first-probe "
        f"RTTs; the line joins medians; ✕ marks lost probes (2 s timeout).</p>"
        + "".join(sections)
    )
    out = path.with_name(path.stem.replace("results", "report") + ".html")
    out.write_text(html)
    print(f"Report written to {out}")


if __name__ == "__main__":
    main()
