"""Example demonstrating flame effect.

EffectFlame creates a fire/candle flicker using layered sine waves for organic
brightness variation. Warm colors range from deep red to yellow. On matrix
lights, a vertical brightness gradient makes the bottom rows hotter.

Works on all color devices — single bulbs flicker like candles, strips look
like a fire along a wall, and matrix lights get a 2D fire with vertical
gradient.

Usage:
    # Discover all lights on the network
    python effects_flame.py

    # Target specific devices by IP address
    python effects_flame.py 192.168.1.100 192.168.1.101

    # Target specific devices by serial number
    python effects_flame.py d073d5123456 d073d5abcdef

    # Mix IP addresses and serial numbers
    python effects_flame.py 192.168.1.100 d073d5123456
"""

#  Copyright (c) 2026 Avi Miller <me@dje.li>
#  Licensed under the Universal Permissive License v 1.0 as shown at https://opensource.org/license/UPL

import asyncio
import sys

from lifx import Light, discover, find_by_ip, find_by_serial
from lifx.effects import Conductor, EffectFlame


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
    """Run flame effect examples."""
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

    # Example 1: Default candle flicker
    print("\n1. Candle flicker - default settings (15 seconds)")
    effect = EffectFlame()
    await conductor.start(effect, lights)
    await asyncio.sleep(15)
    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    await asyncio.sleep(2)

    # Example 2: Intense fast fire
    print("\n2. Intense fire - high intensity and speed (15 seconds)")
    effect = EffectFlame(intensity=1.0, speed=2.0, brightness=1.0)
    await conductor.start(effect, lights)
    await asyncio.sleep(15)
    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    await asyncio.sleep(2)

    # Example 3: Gentle low ember glow
    print("\n3. Low ember glow - low intensity, narrow kelvin range (15 seconds)")
    effect = EffectFlame(
        intensity=0.3,
        speed=0.5,
        brightness=0.4,
        kelvin_min=1500,
        kelvin_max=1800,
    )
    await conductor.start(effect, lights)
    await asyncio.sleep(15)
    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    print("\nAll effects completed!")
    print("Lights have been restored to their original state")


if __name__ == "__main__":
    asyncio.run(main())
