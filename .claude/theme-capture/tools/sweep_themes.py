#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["lifx-async"]
#
# [tool.uv.sources]
# lifx-async = { path = "../../../", editable = true }
# ///
"""Capture every LIFX app theme palette by driving the app and reading the light.

For each theme in the picker: tap it, tap Save, wait for the device to take the
effect, then read the palette back off the light with StateTileEffect. Results
are appended to a JSONL file as they are captured, so an interrupted run keeps
everything up to that point and can resume.

The app shuffles palette order on every application, so a captured palette is
only meaningful as an unordered set.

Usage:
    ./sweep_themes.py --ip 192.168.19.243
    ./sweep_themes.py --ip 192.168.19.243 --limit 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess  # nosec B404 - driving adb is the whole point of this tool
import sys
import time
import xml.etree.ElementTree as ET  # nosec B405 - input is uiautomator's

# own output from a USB-attached device the operator controls, not untrusted
from pathlib import Path

from lifx import Device, MatrixLight
from lifx.protocol.protocol_types import FirmwareEffect

#: Capture data lives one level up, alongside this tools directory.
DATA = Path(__file__).parent.parent

#: Widget coordinates mapped from the picker (Galaxy Tab S10 FE+, portrait).
THEME_BUTTON = (1099, 524)
SAVE_BUTTON = (900, 2682)
SWIPE_X = 900

#: The scrolling region of the theme sheet.
LIST_TOP = 1830
LIST_BOTTOM = 2580

#: Sheet chrome that is not a theme cell.
NOT_A_THEME = {"Themes", "Current Colours", "Save", "Cancel", "Done"}

#: Seconds to let the device pick up a newly saved effect before reading it.
SETTLE = 2.5

#: The picker's category headings, matched exactly. Detecting these by shape
#: does not work: "GWS" is an all-caps three-letter club name, not a heading.
HEADINGS = {
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
}


def sh(*args: str) -> str:
    """Run an adb command and return stdout."""
    return subprocess.run(
        ["adb", *args],  # nosec B603 B607 - fixed argv, no shell, adb from PATH
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout


def dump() -> ET.Element:
    """Pull the current UI hierarchy."""
    sh("shell", "uiautomator", "dump", "/sdcard/s.xml")
    sh("pull", "/sdcard/s.xml", str(DATA / "s.xml"))
    return ET.parse(DATA / "s.xml").getroot()  # nosec B314


def _bounds(node: ET.Element) -> tuple[int, int, int, int] | None:
    """Parse a node's bounds attribute into (x1, y1, x2, y2)."""
    raw = (node.get("bounds") or "").replace("][", ",")[1:-1]
    try:
        nums = [int(n) for n in raw.split(",")]
    except ValueError:
        return None
    return (nums[0], nums[1], nums[2], nums[3]) if len(nums) == 4 else None


def visible_cells(root: ET.Element) -> dict[str, tuple[int, int]]:
    """Map the name of every on-screen theme cell to its tap point."""
    cells: dict[str, tuple[int, int]] = {}
    for node in root.iter("node"):
        text = (node.get("text") or "").strip()
        if not text or text in NOT_A_THEME:
            continue
        box = _bounds(node)
        if box is None:
            continue
        x1, y1, x2, y2 = box
        if x1 < 300 or not (LIST_TOP <= y1 <= LIST_BOTTOM):
            continue
        cells[text] = ((x1 + x2) // 2, (y1 + y2) // 2)
    return cells


def sheet_is_open(root: ET.Element) -> bool:
    """Check whether the theme picker sheet is showing."""
    return any(
        (node.get("resource-id") or "").endswith("save_button")
        for node in root.iter("node")
    )


def open_sheet() -> None:
    """Open the theme picker if it is not already open."""
    if not sheet_is_open(dump()):
        sh("shell", "input", "tap", str(THEME_BUTTON[0]), str(THEME_BUTTON[1]))
        time.sleep(1.5)


def swipe(direction: int, settle: float = 1.0) -> None:
    """Scroll the sheet: 1 scrolls down the list, -1 scrolls back up."""
    start, end = (2450, 1900) if direction > 0 else (1900, 2450)
    sh(
        "shell",
        "input",
        "swipe",
        str(SWIPE_X),
        str(start),
        str(SWIPE_X),
        str(end),
        "400",
    )
    time.sleep(settle)


def find_and_tap(name: str, prefetch: int = 0, max_swipes: int = 90) -> int | None:
    """Scroll the sheet until the named theme is visible, then tap it.

    A UI dump costs ~2.5s while a swipe costs ~0.3s, so dumping between every
    swipe is what makes a deep search slow. The sheet always reopens at the
    top, which makes "swipes from the top" a stable coordinate: the caller
    passes the count that reached the previous theme and those are replayed
    blind, with the search proper starting from there. Themes are visited in
    list order, so the next one is at or just past that position.

    Args:
        name: Theme to find
        prefetch: Swipes to replay blind before looking
        max_swipes: Cap on searching swipes in each direction

    Returns:
        Swipes from the top used to reach the theme, or None if not found
    """
    for _ in range(prefetch):
        swipe(1, settle=0.3)

    used = prefetch

    for direction in (1, -1):
        previous: set[str] | None = None
        for _ in range(max_swipes):
            cells = visible_cells(dump())
            if name in cells:
                x, y = cells[name]
                sh("shell", "input", "tap", str(x), str(y))
                time.sleep(0.6)
                return used
            if previous is not None and set(cells) == previous:
                break  # List did not move: we are at an end, so reverse.
            previous = set(cells)
            swipe(direction)
            used += direction
    return None


def save() -> None:
    """Commit the selected theme to the running effect."""
    sh("shell", "input", "tap", str(SAVE_BUTTON[0]), str(SAVE_BUTTON[1]))
    time.sleep(SETTLE)


async def read_palette(ip: str) -> list[dict[str, float]] | None:
    """Read the running effect's palette off the device."""
    device = await Device.connect(ip)
    try:
        if not isinstance(device, MatrixLight):
            return None
        effect = await device.get_effect()
        if effect.effect_type is FirmwareEffect.OFF or not effect.palette:
            return None
        return [
            {
                "hue": c.hue,
                "saturation": c.saturation,
                "brightness": c.brightness,
                "kelvin": c.kelvin,
            }
            for c in effect.palette
        ]
    finally:
        await device.close()


def as_key(palette: list[dict[str, float]]) -> frozenset[tuple[float, ...]]:
    """Order-insensitive identity for a palette, since the app shuffles it."""
    return frozenset(
        (c["hue"], c["saturation"], c["brightness"], c["kelvin"]) for c in palette
    )


async def main() -> None:
    """Drive the picker through every theme and record each palette."""
    parser = argparse.ArgumentParser(description="Capture LIFX app theme palettes")
    parser.add_argument("--ip", required=True, help="IP of the light running MORPH")
    parser.add_argument(
        "--names", required=True, help="File of theme names, one per line"
    )
    parser.add_argument("--out", default=str(DATA / "themes.jsonl"))
    parser.add_argument("--limit", type=int, help="Stop after this many themes")
    args = parser.parse_args()

    names = [
        line.strip()
        for line in Path(args.names).read_text().splitlines()
        if line.strip()
    ]

    out = Path(args.out)
    done = set()
    if out.exists():
        done = {
            json.loads(line)["name"] for line in out.read_text().splitlines() if line
        }
        print(f"Resuming: {len(done)} already captured", file=sys.stderr)

    category = "unknown"
    previous: frozenset[tuple[float, ...]] | None = None
    position = 0  # Swipes from the top that reached the last theme.

    with out.open("a") as handle:
        for index, name in enumerate(names):
            if name in HEADINGS:
                category = name
                print(f"\n== {name}", file=sys.stderr)
                continue

            if name in done:
                continue
            if args.limit and len([d for d in done]) >= args.limit:
                break

            open_sheet()
            # Start one swipe short of the previous theme's position so the
            # search always approaches from above and never has to reverse.
            used = find_and_tap(name, prefetch=max(0, position - 1))
            if used is None:
                print(f"  MISS  {name}", file=sys.stderr)
                position = 0  # Lost our place; next search starts from the top.
                continue
            position = used
            save()

            palette = await read_palette(args.ip)
            if palette is None:
                print(f"  NONE  {name}", file=sys.stderr)
                continue

            key = as_key(palette)
            unchanged = key == previous
            if unchanged:
                # Possibly the save did not land; give it one more chance.
                await asyncio.sleep(2.0)
                retry = await read_palette(args.ip)
                if retry is not None:
                    palette, key = retry, as_key(retry)
                    unchanged = key == previous

            record = {
                "name": name,
                "category": category,
                "index": index,
                "colors": palette,
                "suspect_unchanged": unchanged,
            }
            handle.write(json.dumps(record) + "\n")
            handle.flush()
            done.add(name)
            previous = key

            flag = " (unchanged!)" if unchanged else ""
            print(f"  {len(palette):2d}  {name}{flag}", file=sys.stderr)

            if args.limit and len(done) >= args.limit:
                break


if __name__ == "__main__":
    asyncio.run(main())
