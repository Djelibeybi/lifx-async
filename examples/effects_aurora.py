"""Example demonstrating aurora effect.

EffectAurora simulates the northern lights with flowing colored bands using
palette interpolation and sine waves. Best on multizone strips and matrix
lights where per-pixel color variation creates beautiful flowing bands.

Works on all color devices. On single bulbs it produces a slow color drift;
on strips and matrix lights it creates flowing aurora curtains.

Usage:
    # Discover all lights on the network
    python effects_aurora.py

    # Target specific devices by IP address
    python effects_aurora.py 192.168.1.100 192.168.1.101

    # Target specific devices by serial number
    python effects_aurora.py d073d5123456 d073d5abcdef

    # Mix IP addresses and serial numbers
    python effects_aurora.py 192.168.1.100 d073d5123456
"""

#  Copyright (c) 2026 Avi Miller <me@dje.li>
#  Licensed under the Universal Permissive License v 1.0 as shown at https://opensource.org/license/UPL

import asyncio
import sys

from lifx import Light, discover, find_by_ip, find_by_serial
from lifx.effects import Conductor, EffectAurora


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
    """Run aurora effect examples."""
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

    conductor = Conductor()

    # Example 1: Default aurora (green/cyan/blue/purple palette)
    print("\n1. Default aurora - green/blue/purple (20 seconds)")
    effect = EffectAurora()
    await conductor.start(effect, lights)
    await asyncio.sleep(20)
    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    await asyncio.sleep(2)

    # Example 2: Custom warm palette (sunset aurora)
    print("\n2. Warm aurora - magenta/pink/red palette (20 seconds)")
    effect = EffectAurora(palette=[280, 300, 320, 340, 10])
    await conductor.start(effect, lights)
    await asyncio.sleep(20)
    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    await asyncio.sleep(2)

    # Example 3: Fast aurora with device spread
    # Each device's aurora is offset by 'spread' degrees so adjacent
    # devices display different parts of the palette simultaneously.
    print("\n3. Fast aurora with 120-degree device spread (20 seconds)")
    effect = EffectAurora(speed=2.0, brightness=1.0, spread=120.0)
    await conductor.start(effect, lights)
    await asyncio.sleep(20)
    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    print("\nAll effects completed!")
    print("Lights have been restored to their original state")


if __name__ == "__main__":
    asyncio.run(main())
