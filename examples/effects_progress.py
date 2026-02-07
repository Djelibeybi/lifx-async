"""Example demonstrating progress bar effect.

EffectProgress displays an animated progress bar on multizone lights (strips
and beams). The filled region has a traveling bright spot, and the position
can be updated at any time from external code.

Multizone devices only — single bulbs and matrix lights are not supported.

Usage:
    # Discover all multizone lights on the network
    python effects_progress.py

    # Target specific devices by IP address
    python effects_progress.py 192.168.1.100 192.168.1.101

    # Target specific devices by serial number
    python effects_progress.py d073d5123456 d073d5abcdef

    # Mix IP addresses and serial numbers
    python effects_progress.py 192.168.1.100 d073d5123456
"""

#  Copyright (c) 2026 Avi Miller <me@dje.li>
#  Licensed under the Universal Permissive License v 1.0 as shown at https://opensource.org/license/UPL

import asyncio
import sys

from lifx import Light, discover, find_by_ip, find_by_serial
from lifx.color import HSBK, Colors
from lifx.effects import Conductor, EffectProgress


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


async def main() -> None:
    """Run progress bar effect examples."""
    targets = sys.argv[1:]

    if targets:
        print("Resolving target devices...")
        lights = await resolve_devices(targets)
    else:
        lights = await discover_lights()

    if not lights:
        print("No lights found")
        return

    print(f"Found {len(lights)} light(s)")
    print("Note: Progress effect only works on multizone lights (strips/beams).")
    print("Incompatible devices will be automatically skipped.")

    conductor = Conductor()

    # Example 1: Simulated download progress (red bar on green background)
    # Steps one pixel at a time on a typical 60-zone strip (~1.67% per step)
    print("\n1. Simulated download progress - red on green, per-pixel steps")
    zone_count = 60  # typical strip zone count
    step_pct = 100.0 / zone_count  # ~1.67% per pixel
    effect = EffectProgress(
        foreground=Colors.RED,
        background=HSBK(hue=120, saturation=1.0, brightness=0.3, kelvin=3500),
        end_value=100,
        spot_speed=0.5,
    )
    await conductor.start(effect, lights)

    # Advance one pixel at a time
    position = 0.0
    while position <= 100.0:
        effect.position = min(position, 100.0)
        pct = int(position)
        if pct % 10 == 0 or position >= 100.0:
            print(f"   Progress: {pct}%")
        await asyncio.sleep(0.15)
        position += step_pct

    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    await asyncio.sleep(2)

    # Example 2: Temperature gauge with gradient foreground
    # The gradient defines the full color range up front — as the bar
    # grows, more of the gradient is revealed (like a thermometer).
    print("\n2. Temperature gauge - gradient from blue to red")
    gradient = [
        HSBK(hue=240, saturation=1.0, brightness=0.8, kelvin=3500),  # blue (cold)
        HSBK(hue=180, saturation=1.0, brightness=0.8, kelvin=3500),  # cyan
        HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),  # green
        HSBK(hue=60, saturation=1.0, brightness=0.9, kelvin=3500),  # yellow
        HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),  # red (hot)
    ]
    effect = EffectProgress(
        foreground=gradient,
        background=HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=3500),
        start_value=20.0,
        end_value=80.0,
        position=20.0,
        spot_speed=1.5,
    )
    await conductor.start(effect, lights)

    # Simulate temperature rising — the gradient reveals progressively
    for temp in range(20, 81):
        effect.position = float(temp)
        if temp % 10 == 0:
            print(f"   Temperature: {temp}C")
        await asyncio.sleep(0.3)

    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    print("\nAll effects completed!")
    print("Lights have been restored to their original state")


if __name__ == "__main__":
    asyncio.run(main())
