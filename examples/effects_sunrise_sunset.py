"""Example demonstrating sunrise and sunset effects.

EffectSunrise transitions from night to daylight over a configurable duration.
EffectSunset transitions from daylight to night and optionally powers off the
light when complete.

Both effects use a radial model that expands outward (sunrise) or contracts
inward (sunset) through color phases: deep navy (night), purple/magenta
(dawn/dusk), orange/gold (golden hour), warm white (day).

The ``origin`` parameter controls the sun's center point:
- ``"bottom"`` (default): Center of the bottom row — ideal for rectangular tiles
- ``"center"``: Middle of the canvas — ideal for round/oval Ceiling lights

Matrix devices only — these effects require a 2D pixel grid for the radial
sun simulation.

Usage:
    # Discover all matrix lights on the network
    python effects_sunrise_sunset.py

    # Target specific devices by IP address
    python effects_sunrise_sunset.py 192.168.1.100 192.168.1.101

    # Target specific devices by serial number
    python effects_sunrise_sunset.py d073d5123456 d073d5abcdef

    # Show brightness and kelvin values while animating
    python effects_sunrise_sunset.py --show-hsbk 192.168.1.100
"""

#  Copyright (c) 2026 Avi Miller <me@dje.li>
#  Licensed under the Universal Permissive License v 1.0 as shown at https://opensource.org/license/UPL

import asyncio
import sys

from lifx import Light, discover, find_by_ip, find_by_serial
from lifx.effects import Conductor, EffectSunrise, EffectSunset


async def resolve_devices(targets: list[str]) -> list[Light]:
    """Resolve a list of IP addresses or serial numbers to Light devices.

    Auto-detects IPs (contain '.') vs serials (hex digits).

    Args:
        targets: List of IP addresses or serial numbers.

    Returns:
        List of resolved Light devices.
    """
    lights: list[Light] = []

    for target in targets:
        if "." in target:
            print(f"  Looking up IP {target}...")
            device = await find_by_ip(target, timeout=5.0)
        else:
            print(f"  Looking up serial {target}...")
            device = await find_by_serial(target, timeout=5.0)

        if device is None:
            print(f"  Warning: No device found for '{target}', skipping")
        elif not isinstance(device, Light):
            print(
                f"  Warning: {target} is a {type(device).__name__},"
                " not a Light, skipping"
            )
        else:
            print(f"Resolved: {device.label} [{device.serial}] -> {device.ip}")
            lights.append(device)

    return lights


async def discover_lights() -> list[Light]:
    """Discover all lights on the network.

    Returns:
        List of discovered Light devices.
    """
    print("Discovering LIFX devices...")
    lights: list[Light] = []
    async for device in discover():
        if isinstance(device, Light):
            lights.append(device)
    return lights


async def _monitor_sun_effect(
    conductor: Conductor,
    lights: list[Light],
    duration: float,
    show_hsbk: bool = False,
) -> None:
    """Print brightness and kelvin while a sun effect runs.

    Uses conductor.get_last_frame() to read the actual HSBK values
    being sent to the first device every 2 seconds.

    Args:
        conductor: The conductor running the effect.
        lights: Lights running the effect (first is sampled).
        duration: Total duration of the effect in seconds.
        show_hsbk: If True, print per-frame stats while animating.
    """
    if not show_hsbk:
        await asyncio.sleep(duration + 2)
        return

    elapsed = 0.0
    while elapsed < duration:
        await asyncio.sleep(2)
        elapsed += 2

        colors = conductor.get_last_frame(lights[0])
        if not colors:
            continue

        avg_brightness = sum(c.brightness for c in colors) / len(colors)
        avg_kelvin = sum(c.kelvin for c in colors) / len(colors)
        pct = min(elapsed / duration * 100, 100.0)
        print(
            f"   {pct:5.1f}%  brightness: {avg_brightness:5.1%}"
            f"  kelvin: {avg_kelvin:,.0f}K"
        )

    await asyncio.sleep(2)  # buffer for effect to finish


async def main() -> None:
    """Run sunrise and sunset effect examples."""
    show_hsbk = "--show-hsbk" in sys.argv
    targets = [a for a in sys.argv[1:] if not a.startswith("--")]

    if targets:
        print("Resolving target devices...")
        lights = await resolve_devices(targets)
    else:
        lights = await discover_lights()

    if not lights:
        print("No lights found")
        return

    print(f"Found {len(lights)} light(s)")
    print("Note: Sunrise/sunset effects only work on matrix lights (tiles/candles).")
    print("Incompatible devices will be automatically skipped.")

    conductor = Conductor()

    # Example 1: Sunrise from bottom (default, ideal for rectangular tiles)
    # In real use, you'd set duration=1800 (30 minutes) or more
    print("\n1. Sunrise from bottom edge - 30 second demo")
    print("   Watch the transition: night -> dawn -> golden hour -> daylight")
    effect = EffectSunrise(duration=30, brightness=1.0)
    await conductor.start(effect, lights)
    await _monitor_sun_effect(conductor, lights, duration=30, show_hsbk=show_hsbk)
    print("Sunrise complete. Lights are at full daylight.")

    await asyncio.sleep(3)

    # Example 2: Sunset with power off
    print("\n2. Sunset with auto power-off - 30 second demo")
    print("   Watch the transition: daylight -> golden hour -> dusk -> night -> off")
    effect = EffectSunset(power_on=True, duration=30, brightness=1.0, power_off=True)
    await conductor.start(effect, lights)
    await _monitor_sun_effect(conductor, lights, duration=30, show_hsbk=show_hsbk)
    print("Sunset complete. Lights have been powered off.")

    await asyncio.sleep(3)

    # Example 3: Sunrise from center (ideal for round/oval Ceiling lights)
    # The sun expands outward from the middle instead of rising from the bottom
    print("\n3. Sunrise from center (for Ceiling lights) - 30 second demo")
    print("   The sun expands outward from the center of the canvas")
    effect = EffectSunrise(duration=30, brightness=1.0, origin="center")
    await conductor.start(effect, lights)
    await _monitor_sun_effect(conductor, lights, duration=30, show_hsbk=show_hsbk)
    print("Center sunrise complete.")

    print("\nAll effects completed!")


if __name__ == "__main__":
    asyncio.run(main())
