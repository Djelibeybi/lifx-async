"""Hardware UAT for software effects on light components (spec #241).

Walks an operator through every user-visible behaviour of component effects on
a real LIFX Ceiling and/or Mirror: ring order and direction, single-component
effects with the idle component under caller control, two effects at once,
overlap rules between whole-light and component effects, and restore from a lit
component, a dark component and a light that is off.

Each step is described first and only runs when you press a key, so there is
time to read what to watch for. Effects keep animating while the script waits
for your verdict. Press:

- any key to start the described step (``s`` skips it, ``q`` quits)
- ``p`` pass, ``f`` fail or ``n`` note-and-fail after watching the light

The light's own colours, power and stored turn-on colours are captured before
the run and put back at the end, including after a quit or an error.

Software effects stream frames, which a Thread mesh is not built for, so a
light evidenced as Thread is refused with a message and the run stops. Pass
``--enable-thread`` to stream to it anyway; every ``start_effect()`` call then
gets ``enable_thread=True``.

The summary names steps and verdicts only. It never prints serials, addresses
or labels, so it can be pasted into a pull request as it is.

Usage:
    uv run python scripts/uat_component_effects.py --ceiling 192.0.2.10
    uv run python scripts/uat_component_effects.py --mirror 192.0.2.20 \\
        --report uat-mirror.md
    uv run python scripts/uat_component_effects.py --ceiling 192.0.2.10 \\
        --enable-thread
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from lifx import HSBK, CeilingLight, Device, MirrorLight
from lifx.devices.component.effect_support import (
    reinstate_stored_colors,
    stored_colors_snapshot,
)
from lifx.effects import (
    EffectAurora,
    EffectColorloop,
    EffectCylon,
    EffectFlicker,
    EffectPlasma,
    EffectRainbow,
    EffectSpin,
)
from lifx.exceptions import LifxUnsupportedCommandError

# Single-key input differs by platform: msvcrt on Windows, termios/tty elsewhere.
if sys.platform == "win32":
    import msvcrt
else:
    import termios
    import tty

# Calm baselines, so "restored" is easy to recognise by eye. The Mirror pair
# follows examples/mirror_components.py: neither ring at full brightness, the
# back a little ahead, so each ring's change can be followed at once.
SOFT_WHITE = HSBK(hue=0, saturation=0.0, brightness=0.35, kelvin=4500)
AMBER = HSBK(hue=30, saturation=0.4, brightness=0.6, kelvin=2700)
BLUE = HSBK(hue=230, saturation=1.0, brightness=0.6, kelvin=3500)
GREEN = HSBK(hue=120, saturation=1.0, brightness=0.6, kelvin=3500)

Action = Callable[[], Awaitable[None]]


@dataclass
class Step:
    """One operator-observed check."""

    key: str
    title: str
    watch: str
    action: Action


@dataclass
class Result:
    """The operator's verdict on one step."""

    key: str
    title: str
    verdict: str
    note: str = ""


@dataclass
class Scenario:
    """A group of steps that share a starting picture."""

    title: str
    setup: Action
    steps: list[Step] = field(default_factory=list)


# --------------------------------------------------------------------------
# Keyboard
# --------------------------------------------------------------------------


def _read_key_blocking() -> str:
    """Read one key press without waiting for Enter where the terminal allows."""
    if not sys.stdin.isatty():
        return (sys.stdin.readline().strip() or "\n")[0].lower()
    if sys.platform == "win32":
        return msvcrt.getwch().lower()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return sys.stdin.read(1).lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


async def read_key(prompt: str) -> str:
    """Prompt and read one key in a thread, so running effects keep animating."""
    print(prompt, end="", flush=True)
    key = await asyncio.to_thread(_read_key_blocking)
    print()
    if key == "\x03":
        raise KeyboardInterrupt
    return key


async def read_line(prompt: str) -> str:
    """Prompt and read a whole line in a thread."""
    return (await asyncio.to_thread(input, prompt)).strip()


class OperatorQuitError(Exception):
    """The operator asked to stop the run."""


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


async def run_scenario(scenario: Scenario, results: list[Result]) -> None:
    """Set up one scenario, then run each step on a key press."""
    print(f"\n=== {scenario.title} ===")
    print("Setting the starting picture...")
    await scenario.setup()
    for step in scenario.steps:
        print(f"\n[{step.key}] {step.title}")
        print(f"    Watch for: {step.watch}")
        key = await read_key("    Press any key to start (s skip, q quit): ")
        if key == "q":
            raise OperatorQuitError
        if key == "s":
            results.append(Result(step.key, step.title, "SKIP"))
            continue
        await step.action()
        while True:
            key = await read_key("    Verdict? p pass, f fail, n fail with note: ")
            if key in ("p", "f", "n"):
                break
            if key == "q":
                raise OperatorQuitError
        note = await read_line("    Note: ") if key == "n" else ""
        verdict = "PASS" if key == "p" else "FAIL"
        results.append(Result(step.key, step.title, verdict, note))


def render_report(results: list[Result], products: list[str]) -> str:
    """Render a Markdown summary with no device identifiers."""
    passed = sum(r.verdict == "PASS" for r in results)
    failed = sum(r.verdict == "FAIL" for r in results)
    skipped = sum(r.verdict == "SKIP" for r in results)
    lines = [
        "## Component effects hardware UAT",
        "",
        f"Products: {', '.join(products)}",
        f"Result: {passed} passed, {failed} failed, {skipped} skipped",
        "",
        "| Step | Check | Verdict | Note |",
        "|------|-------|---------|------|",
    ]
    for r in results:
        note = r.note.replace("|", "\\|")
        lines.append(f"| {r.key} | {r.title} | {r.verdict} | {note} |")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Ceiling
# --------------------------------------------------------------------------


async def capture_ceiling(ceiling: CeilingLight) -> Action:
    """Capture the Ceiling's colours, power and stored colours, returning a restorer."""
    stored = stored_colors_snapshot(ceiling)
    power = await ceiling.get_power()
    uplight = await ceiling.get_uplight_color()
    downlight = await ceiling.get_downlight_colors()

    async def restore() -> None:
        await ceiling.stop_effect()
        if uplight.brightness > 0:
            await ceiling.set_uplight_color(uplight)
        else:
            await ceiling.turn_uplight_off()
        if any(c.brightness > 0 for c in downlight):
            await ceiling.set_downlight_colors(downlight)
        else:
            await ceiling.turn_downlight_off()
        await ceiling.set_power(power > 0)
        # The writes above remember colours; the user's own stored colours win.
        if stored is not None:
            await reinstate_stored_colors(ceiling, stored)

    return restore


def ceiling_scenarios(ceiling: CeilingLight, *, enable_thread: bool) -> list[Scenario]:
    """Build the Ceiling checks: downlight soft white, uplight amber."""

    async def lit() -> None:
        await ceiling.stop_effect()
        await ceiling.set_power(True)
        await ceiling.set_downlight_colors(SOFT_WHITE)
        await ceiling.set_uplight_color(AMBER)

    async def downlight_dark() -> None:
        await lit()
        await ceiling.turn_downlight_off()

    async def light_off() -> None:
        await lit()
        await ceiling.set_power(False)

    return [
        Scenario(
            "Ceiling: one light component animating",
            lit,
            [
                Step(
                    "C1",
                    "Flicker on the downlight only",
                    "the downlight flickers across the whole grid; the uplight "
                    "stays steady amber",
                    lambda: ceiling.downlight.start_effect(
                        EffectFlicker(), enable_thread=enable_thread
                    ),
                ),
                Step(
                    "C2",
                    "Change the idle uplight while the downlight animates",
                    "the uplight turns blue at once and stays blue; the downlight "
                    "keeps flickering",
                    lambda: ceiling.set_uplight_color(BLUE),
                ),
                Step(
                    "C3",
                    "Colorloop on the uplight as well",
                    "both run at once: the uplight cycles hues, the downlight "
                    "keeps flickering, with no stutter in either",
                    lambda: ceiling.uplight.start_effect(
                        EffectColorloop(period=10), enable_thread=enable_thread
                    ),
                ),
                Step(
                    "C4",
                    "Stop the downlight's effect only",
                    "the downlight returns to soft white; the uplight keeps "
                    "cycling hues",
                    lambda: ceiling.downlight.stop_effect(),
                ),
                Step(
                    "C5",
                    "Stop everything on the light",
                    "the uplight returns to blue (its colour before its effect); "
                    "the downlight stays soft white",
                    lambda: ceiling.stop_effect(),
                ),
                Step(
                    "C6",
                    "Write to the animating component",
                    "after the uplight starts cycling, it turns green and stops "
                    "cycling; the downlight is untouched",
                    lambda: _then(
                        ceiling.uplight.start_effect(
                            EffectColorloop(period=10), enable_thread=enable_thread
                        ),
                        ceiling.set_uplight_color(GREEN),
                        pause=4.0,
                    ),
                ),
            ],
        ),
        Scenario(
            "Ceiling: overlap rules",
            lit,
            [
                Step(
                    "C7",
                    "Component effects, then a whole-light effect replaces them",
                    "first the downlight flickers and the uplight cycles; after a "
                    "few seconds Aurora takes over the whole light",
                    lambda: _then(
                        ceiling.downlight.start_effect(
                            EffectFlicker(), enable_thread=enable_thread
                        ),
                        ceiling.uplight.start_effect(
                            EffectColorloop(period=10), enable_thread=enable_thread
                        ),
                        ceiling.start_effect(
                            EffectAurora(), enable_thread=enable_thread
                        ),
                        pause=4.0,
                    ),
                ),
                Step(
                    "C8",
                    "Stop the whole-light effect",
                    "the light returns to the starting picture: downlight soft "
                    "white, uplight amber (not a frame from any effect)",
                    lambda: ceiling.stop_effect(),
                ),
                Step(
                    "C9",
                    "Whole-light Aurora, then a downlight effect moves it",
                    "Aurora runs on the whole light; after a few seconds the "
                    "downlight switches to Flicker and Aurora carries on in the "
                    "uplight only",
                    lambda: _then(
                        ceiling.start_effect(
                            EffectAurora(), enable_thread=enable_thread
                        ),
                        ceiling.downlight.start_effect(
                            EffectFlicker(), enable_thread=enable_thread
                        ),
                        pause=4.0,
                    ),
                ),
                Step(
                    "C10",
                    "Stop the downlight's effect",
                    "the downlight returns to soft white; the uplight keeps "
                    "its aurora and it does not spread back over the downlight",
                    lambda: ceiling.downlight.stop_effect(),
                ),
                Step(
                    "C11",
                    "Stop everything on the light",
                    "the uplight returns to amber",
                    lambda: ceiling.stop_effect(),
                ),
            ],
        ),
        Scenario(
            "Ceiling: restore from dark",
            downlight_dark,
            [
                Step(
                    "C12",
                    "Effect on a dark downlight",
                    "the downlight comes on and flickers; the uplight stays amber",
                    lambda: ceiling.downlight.start_effect(
                        EffectFlicker(), enable_thread=enable_thread
                    ),
                ),
                Step(
                    "C13",
                    "Stop it",
                    "the downlight goes dark again; the uplight stays amber and "
                    "the light stays on",
                    lambda: ceiling.downlight.stop_effect(),
                ),
            ],
        ),
        Scenario(
            "Ceiling: restore from off",
            light_off,
            [
                Step(
                    "C14",
                    "Effect on the uplight of a light that is off",
                    "only the uplight comes on and cycles hues; the downlight "
                    "stays dark",
                    lambda: ceiling.uplight.start_effect(
                        EffectColorloop(period=10), enable_thread=enable_thread
                    ),
                ),
                Step(
                    "C15",
                    "Stop it",
                    "the light goes off",
                    lambda: ceiling.uplight.stop_effect(),
                ),
                Step(
                    "C16",
                    "Power the whole light on",
                    "the starting picture comes back (downlight soft white, "
                    "uplight amber), not the effect's last frame",
                    lambda: ceiling.set_power(True),
                ),
            ],
        ),
    ]


# --------------------------------------------------------------------------
# Mirror
# --------------------------------------------------------------------------


async def capture_mirror(mirror: MirrorLight) -> Action:
    """Capture the Mirror's colours, power and stored colours, returning a restorer."""
    stored = stored_colors_snapshot(mirror)
    power = await mirror.get_power()
    front = await mirror.get_front_colors()
    back = await mirror.get_back_colors()

    async def restore() -> None:
        await mirror.stop_effect()
        if any(c.brightness > 0 for c in front):
            await mirror.set_front_colors(front)
        else:
            await mirror.turn_front_off()
        if any(c.brightness > 0 for c in back):
            await mirror.set_back_colors(back)
        else:
            await mirror.turn_back_off()
        await mirror.set_power(power > 0)
        # The writes above remember colours; the user's own stored colours win.
        if stored is not None:
            await reinstate_stored_colors(mirror, stored)

    return restore


def mirror_scenarios(mirror: MirrorLight, *, enable_thread: bool) -> list[Scenario]:
    """Build the Mirror checks: front soft white, back amber."""

    async def lit() -> None:
        await mirror.stop_effect()
        await mirror.set_power(True)
        await mirror.set_front_colors(SOFT_WHITE)
        await mirror.set_back_colors(AMBER)

    async def front_dark() -> None:
        await lit()
        await mirror.turn_front_off()

    async def light_off() -> None:
        await lit()
        await mirror.set_power(False)

    return [
        Scenario(
            "Mirror: whole-light ring canvas",
            lit,
            [
                Step(
                    "M1",
                    "Whole-light Cylon, ring order and direction",
                    "one eye on each ring circling smoothly with no jump or seam; "
                    "write down in a note which way each ring turns, viewed from "
                    "the front (expected: front clockwise, back anticlockwise, "
                    "both starting at the lower left)",
                    lambda: mirror.start_effect(
                        EffectCylon(speed=6.0, width=3, trail=0.0),
                        enable_thread=enable_thread,
                    ),
                ),
                Step(
                    "M2",
                    "Whole-light Rainbow",
                    "a continuous rainbow around each ring with no seam, and both "
                    "rings showing the same picture",
                    lambda: mirror.start_effect(
                        EffectRainbow(period=10), enable_thread=enable_thread
                    ),
                ),
                Step(
                    "M3",
                    "Whole-light Plasma",
                    "both rings show the same plasma: arcs appear at the same "
                    "zones on the front and the back at the same moment",
                    lambda: mirror.start_effect(
                        EffectPlasma(), enable_thread=enable_thread
                    ),
                ),
                Step(
                    "M4",
                    "Stop it",
                    "front soft white and back amber again, with no ring left on "
                    "an effect frame",
                    lambda: mirror.stop_effect(),
                ),
            ],
        ),
        Scenario(
            "Mirror: one ring animating",
            lit,
            [
                Step(
                    "M5",
                    "Rainbow on the front ring only",
                    "the front shows a rainbow; the back stays amber",
                    lambda: mirror.front.start_effect(
                        EffectRainbow(period=10), enable_thread=enable_thread
                    ),
                ),
                Step(
                    "M6",
                    "Change the idle back ring",
                    "the back turns blue at once and stays blue; the front keeps "
                    "its rainbow",
                    lambda: mirror.set_back_colors(BLUE),
                ),
                Step(
                    "M7",
                    "Cylon on the back ring as well",
                    "both rings animate at once with different effects",
                    lambda: mirror.back.start_effect(
                        EffectCylon(speed=6.0, width=3, trail=0.3),
                        enable_thread=enable_thread,
                    ),
                ),
                Step(
                    "M8",
                    "Stop the front ring's effect only",
                    "the front returns to soft white; the back keeps its Cylon",
                    lambda: mirror.front.stop_effect(),
                ),
                Step(
                    "M9",
                    "Stop everything on the light",
                    "the back returns to blue (its colour before its effect)",
                    lambda: mirror.stop_effect(),
                ),
                Step(
                    "M10",
                    "Write to the animating ring",
                    "after the front starts a rainbow, it turns green and stops "
                    "animating; the back is untouched",
                    lambda: _then(
                        mirror.front.start_effect(
                            EffectRainbow(period=10), enable_thread=enable_thread
                        ),
                        mirror.set_front_colors(GREEN),
                        pause=4.0,
                    ),
                ),
            ],
        ),
        Scenario(
            "Mirror: overlap rules",
            lit,
            [
                Step(
                    "M11",
                    "Ring effects, then a whole-light effect replaces them",
                    "first the front shows a rainbow and the back a Cylon; after "
                    "a few seconds Spin takes over both rings",
                    lambda: _then(
                        mirror.front.start_effect(
                            EffectRainbow(period=10), enable_thread=enable_thread
                        ),
                        mirror.back.start_effect(
                            EffectCylon(speed=6.0), enable_thread=enable_thread
                        ),
                        mirror.start_effect(EffectSpin(), enable_thread=enable_thread),
                        pause=4.0,
                    ),
                ),
                Step(
                    "M12",
                    "Stop the whole-light effect",
                    "the starting picture: front soft white, back amber",
                    lambda: mirror.stop_effect(),
                ),
                Step(
                    "M13",
                    "Whole-light Spin, then a front effect moves it",
                    "Spin runs on both rings; after a few seconds the front "
                    "switches to Aurora and Spin carries on on the back only",
                    lambda: _then(
                        mirror.start_effect(EffectSpin(), enable_thread=enable_thread),
                        mirror.front.start_effect(
                            EffectAurora(), enable_thread=enable_thread
                        ),
                        pause=4.0,
                    ),
                ),
                Step(
                    "M14",
                    "Stop the front ring's effect",
                    "the front returns to soft white; the back keeps spinning",
                    lambda: mirror.front.stop_effect(),
                ),
                Step(
                    "M15",
                    "Stop everything on the light",
                    "the back returns to amber",
                    lambda: mirror.stop_effect(),
                ),
            ],
        ),
        Scenario(
            "Mirror: restore from dark",
            front_dark,
            [
                Step(
                    "M16",
                    "Effect on a dark front ring",
                    "the front comes on with a rainbow; the back stays amber",
                    lambda: mirror.front.start_effect(
                        EffectRainbow(period=10), enable_thread=enable_thread
                    ),
                ),
                Step(
                    "M17",
                    "Stop it",
                    "the front goes dark again; the back stays amber and the "
                    "light stays on",
                    lambda: mirror.front.stop_effect(),
                ),
            ],
        ),
        Scenario(
            "Mirror: restore from off",
            light_off,
            [
                Step(
                    "M18",
                    "Effect on the back ring of a light that is off",
                    "only the back comes on with a Cylon; the front stays dark",
                    lambda: mirror.back.start_effect(
                        EffectCylon(speed=6.0), enable_thread=enable_thread
                    ),
                ),
                Step(
                    "M19",
                    "Stop it",
                    "the light goes off",
                    lambda: mirror.back.stop_effect(),
                ),
                Step(
                    "M20",
                    "Power the whole light on",
                    "the starting picture comes back (front soft white, back "
                    "amber), not the effect's last frame",
                    lambda: mirror.set_power(True),
                ),
            ],
        ),
    ]


async def _then(*actions: Awaitable[None], pause: float) -> None:
    """Run actions in order, pausing between them so each change is visible."""
    for index, action in enumerate(actions):
        if index:
            await asyncio.sleep(pause)
        await action


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> int:
    """Connect to each light, run its scenarios and print the summary."""
    results: list[Result] = []
    products: list[str] = []
    targets: list[tuple[str, str]] = []
    if args.ceiling:
        targets.append(("ceiling", args.ceiling))
    if args.mirror:
        targets.append(("mirror", args.mirror))

    try:
        for kind, ip in targets:
            async with await Device.connect(ip) as light:
                expected = CeilingLight if kind == "ceiling" else MirrorLight
                if not isinstance(light, expected):
                    print(f"The {kind} address is not a {expected.__name__}.")
                    return 2
                products.append(light.model or expected.__name__)
                print(f"\nConnected to a {products[-1]}.")
                if isinstance(light, CeilingLight):
                    restore = await capture_ceiling(light)
                    scenarios = ceiling_scenarios(
                        light, enable_thread=args.enable_thread
                    )
                else:
                    restore = await capture_mirror(light)
                    scenarios = mirror_scenarios(
                        light, enable_thread=args.enable_thread
                    )
                try:
                    for scenario in scenarios:
                        await run_scenario(scenario, results)
                finally:
                    print("\nPutting the light back as it was...")
                    await restore()
    except OperatorQuitError:
        print("\nStopped early.")
    except LifxUnsupportedCommandError as error:
        print(f"\nRefused: {error}")
        print("Rerun with --enable-thread to stream effects to a Thread light.")
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted.")

    report = render_report(results, products)
    print("\n" + report)
    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")
        print(f"Summary written to {args.report}")
    return 1 if any(r.verdict == "FAIL" for r in results) else 0


def parse_args() -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        description="Hardware UAT for software effects on light components."
    )
    parser.add_argument("--ceiling", metavar="IP", help="address of a LIFX Ceiling")
    parser.add_argument("--mirror", metavar="IP", help="address of a LIFX Mirror")
    parser.add_argument(
        "--enable-thread",
        action="store_true",
        help="stream software effects to a light evidenced as Thread, which "
        "is refused by default",
    )
    parser.add_argument(
        "--report", metavar="PATH", help="also write the Markdown summary here"
    )
    args = parser.parse_args()
    if not (args.ceiling or args.mirror):
        parser.error("give --ceiling, --mirror or both")
    return args


if __name__ == "__main__":
    sys.exit(asyncio.run(main(parse_args())))
