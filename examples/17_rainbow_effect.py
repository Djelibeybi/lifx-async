"""Example demonstrating rainbow effect.

EffectRainbow spreads a full 360-degree rainbow across all pixels on a
device and scrolls it over time. On multizone strips and matrix lights
this produces a moving rainbow. On single bulbs it cycles through hues
(similar to colorloop but with fixed brightness/saturation).

For a simpler single-color hue rotation, see 07_colorloop_effect.py.

Usage:
    # Discover all lights on the network
    python 17_rainbow_effect.py

    # Target specific devices by IP address
    python 17_rainbow_effect.py 192.168.1.100 192.168.1.101

    # Target specific devices by serial number
    python 17_rainbow_effect.py d073d5123456 d073d5abcdef

    # Mix IP addresses and serial numbers
    python 17_rainbow_effect.py 192.168.1.100 d073d5123456
"""

#  Copyright (c) 2026 Avi Miller <me@dje.li>
#  Licensed under the Universal Permissive License v 1.0 as shown at https://opensource.org/license/UPL

import asyncio
import sys

from lifx import Light, discover, find_by_ip, find_by_serial
from lifx.effects import Conductor, EffectRainbow


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
    """Run rainbow effect examples."""
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

    # Example 1: Rainbow scrolling every 10 seconds
    print("\n1. Rainbow effect (15 seconds)")
    effect = EffectRainbow(period=10)
    await conductor.start(effect, lights)
    await asyncio.sleep(15)
    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    await asyncio.sleep(2)

    # Example 2: Fast rainbow with lower brightness
    print("\n2. Fast rainbow at 50% brightness (15 seconds)")
    effect = EffectRainbow(period=3, brightness=0.5)
    await conductor.start(effect, lights)
    await asyncio.sleep(15)
    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    # Example 3: Rainbow with device spread (only with multiple lights)
    # Each device's rainbow is offset by 'spread' degrees so adjacent
    # devices display different parts of the spectrum simultaneously.
    if len(lights) > 1:
        await asyncio.sleep(2)

        print("\n3. Rainbow with 90-degree device spread (15 seconds)")
        effect = EffectRainbow(period=10, spread=90)
        await conductor.start(effect, lights)
        await asyncio.sleep(15)
        await conductor.stop(lights)
        print("Stopped. Lights restored to original state.")

    print("\nAll effects completed!")
    print("Lights have been restored to their original state")


if __name__ == "__main__":
    asyncio.run(main())
