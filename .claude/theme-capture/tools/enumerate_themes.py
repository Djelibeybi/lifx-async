#!/usr/bin/env python3
"""Enumerate every theme in the LIFX app's theme picker by scrolling it.

Assumes the picker sheet is already open. Dumps the UI hierarchy, records the
visible theme cells, swipes up, and repeats until nothing new appears.
"""

from __future__ import annotations

import subprocess  # nosec B404 - driving adb is the whole point of this tool
import sys
import time
import xml.etree.ElementTree as ET  # nosec B405 - input is uiautomator's

# own output from a USB-attached device the operator controls, not untrusted
from pathlib import Path

SCRATCH = str(Path(__file__).parent.parent)

# The sheet occupies the right-hand portion of the screen; swipe inside it so
# the device list in the left pane is never touched.
SWIPE_X = 900
SWIPE_FROM_Y = 2450
SWIPE_TO_Y = 1900

# Chrome inside the sheet that is not a theme cell.
NOT_A_THEME = {"Themes", "Current Colours", "Save", "Cancel", "Done"}

# Theme cells live below the radio buttons and above the save button.
LIST_TOP = 1830
LIST_BOTTOM = 2580


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
    sh("shell", "uiautomator", "dump", "/sdcard/e.xml")
    sh("pull", "/sdcard/e.xml", f"{SCRATCH}/e.xml")
    return ET.parse(f"{SCRATCH}/e.xml").getroot()  # nosec B314


def visible_cells(root: ET.Element) -> list[tuple[str, int, int]]:
    """Return (name, x, y) for every theme cell currently on screen."""
    cells = []
    for node in root.iter("node"):
        text = (node.get("text") or "").strip()
        if not text or text in NOT_A_THEME:
            continue
        bounds = node.get("bounds") or ""
        nums = [int(n) for n in bounds.replace("][", ",")[1:-1].split(",")]
        if len(nums) != 4:
            continue
        x1, y1, x2, y2 = nums
        # Sheet-only, and inside the scrolling list region.
        if x1 < 300 or not (LIST_TOP <= y1 <= LIST_BOTTOM):
            continue
        cells.append((text, (x1 + x2) // 2, (y1 + y2) // 2))
    return cells


def scroll_to_top() -> None:
    """Rewind the sheet, which may be left scrolled by an earlier pass."""
    for _ in range(80):
        sh(
            "shell",
            "input",
            "swipe",
            str(SWIPE_X),
            str(SWIPE_TO_Y),
            str(SWIPE_X),
            str(SWIPE_FROM_Y),
            "300",
        )
    time.sleep(1.0)


def main() -> None:
    """Scroll the picker and print every theme found, in order."""
    scroll_to_top()

    ordered: list[str] = []
    seen: set[str] = set()
    stale_rounds = 0

    while stale_rounds < 2:
        found_new = False
        for name, _x, _y in visible_cells(dump()):
            if name not in seen:
                seen.add(name)
                ordered.append(name)
                found_new = True

        stale_rounds = 0 if found_new else stale_rounds + 1
        print(f"  {len(ordered)} found...", file=sys.stderr)

        sh(
            "shell",
            "input",
            "swipe",
            str(SWIPE_X),
            str(SWIPE_FROM_Y),
            str(SWIPE_X),
            str(SWIPE_TO_Y),
            "400",
        )
        time.sleep(1.2)

    print(f"\n{len(ordered)} entries:\n")
    for entry in ordered:
        print(entry)


if __name__ == "__main__":
    main()
