#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["lifx-async"]
#
# [tool.uv.sources]
# lifx-async = { path = "../../../", editable = true }
# ///
"""Diff the captured theme palettes against the built-in theme library.

Also re-derives each theme's category from its position in the picker order and
reports any that disagree with the stored value. The sweep's inline detection
treated an all-caps entry as a heading, which misfiled the ten Aussie Rules
clubs following "GWS"; the stored capture has that corrected, so a healthy run
reports zero.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from lifx.theme import ThemeLibrary

#: Capture data lives one level up, alongside this tools directory.
DATA = Path(__file__).parent.parent

HEADINGS = [
    "🙂 MOODS",
    "🎨 ART SERIES",
    "🎵 MUSIC",
    "🌳 NATURE",
    "🔭 SPACE",
    "👾 PLAY",
    "🎉 HOLIDAYS",
    "🏆 AUSSIE RULES",
    "🏉 LEAGUE",
    "🏉 UNION",
    "🗄️ ARCHIVES",
]


def slug(name: str) -> str:
    """Reduce a display name to a library key, dropping emoji and accents."""
    # Emoji and pictographs carry no meaning in a key and sit at either end.
    stripped = "".join(
        ch
        for ch in name
        if unicodedata.category(ch)[0] in {"L", "N", "Z"} or ch in " '’-&/"
    )
    ascii_only = (
        unicodedata.normalize("NFKD", stripped).encode("ascii", "ignore").decode()
    )
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", ascii_only.lower())).strip("_")


def palette_key(colors) -> list[tuple[float, float, float, int]]:
    """Order-insensitive comparison key; the app shuffles palette order."""
    return sorted(
        (
            round(c["hue"] if isinstance(c, dict) else c.hue, 1),
            round(c["saturation"] if isinstance(c, dict) else c.saturation, 3),
            round(c["brightness"] if isinstance(c, dict) else c.brightness, 3),
            c["kelvin"] if isinstance(c, dict) else c.kelvin,
        )
        for c in colors
    )


def main() -> None:
    """Print the repair result and the library diff."""
    names = [
        line
        for line in (DATA / "picker-order.txt").read_text().splitlines()
        if line.strip()
    ]
    category_of: dict[str, str] = {}
    current = "unknown"
    for name in names:
        if name in HEADINGS:
            current = name
            continue
        category_of[name] = current

    records = [
        json.loads(line)
        for line in (DATA / "themes.jsonl").read_text().splitlines()
        if line
    ]

    # The stored capture is already repaired, so this reports rather than
    # rewrites: nothing here should ever overwrite the captured data, which
    # took hours of hardware time to produce.
    repaired = 0
    for record in records:
        correct = category_of.get(record["name"], "unknown")
        if record["category"] != correct:
            record["category"] = correct
            repaired += 1

    print(f"Categories needing repair: {repaired}\n")

    counts = Counter(r["category"] for r in records)
    for heading in HEADINGS:
        print(f"  {heading:20} {counts.get(heading, 0)}")
    print(f"  {'TOTAL':20} {len(records)}\n")

    # Slug collisions must be resolved before any of this becomes library keys.
    by_slug = defaultdict(list)
    for record in records:
        by_slug[slug(record["name"])].append(record)
    collisions = {k: v for k, v in by_slug.items() if len(v) > 1}
    print(f"Slug collisions: {len(collisions)}")
    for key, group in sorted(collisions.items()):
        same = len({tuple(palette_key(r["colors"])) for r in group}) == 1
        detail = " (identical palettes)" if same else " (DIFFERENT palettes)"
        print(f"  {key}: {[r['name'] for r in group]}{detail}")
    print()

    library = {
        name: ThemeLibrary.get(name) for name in ThemeLibrary.get_available_themes()
    }
    lib_keys = set(library)
    captured = {slug(r["name"]): r for r in records}

    exact, differing = [], []
    for key in sorted(lib_keys & set(captured)):
        got = palette_key(captured[key]["colors"])
        want = palette_key(library[key].colors)
        (exact if got == want else differing).append((key, want, got))

    print(
        f"In both: {len(lib_keys & set(captured))}"
        f"  exact: {len(exact)}  differing: {len(differing)}"
    )
    print(f"New (app only): {len(set(captured) - lib_keys)}")
    print(f"Library only:   {len(lib_keys - set(captured))}")
    print(f"  {sorted(lib_keys - set(captured))}\n")

    print("Differences in shared themes:")
    for key, want, got in differing:
        only_lib = [c for c in want if c not in got]
        only_dev = [c for c in got if c not in want]
        print(f"  {key}: {len(want)}->{len(got)} colours")
        for a, b in zip(only_lib, only_dev):
            print(f"      lib {a}   dev {b}")
        if len(only_lib) != len(only_dev):
            print(f"      lib-only {only_lib}  dev-only {only_dev}")


if __name__ == "__main__":
    main()
