"""Example demonstrating pulse effects.

This example shows how to use the effects framework to create various
pulse effects (blink, strobe, breathe, ping).

Usage:
    # Discover all lights on the network
    python effects_pulse.py

    # Target specific devices by IP address
    python effects_pulse.py 192.168.1.100 192.168.1.101

    # Target specific devices by serial number
    python effects_pulse.py d073d5123456 d073d5abcdef

    # Mix IP addresses and serial numbers
    python effects_pulse.py 192.168.1.100 d073d5123456
"""

import asyncio
import sys

from lifx import (
    HSBK,
    Conductor,
    EffectPulse,
    Light,
    discover,
    find_by_ip,
    find_by_serial,
)


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
    """Run pulse effect examples."""
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

    # Example 1: Basic blink effect
    print("\n1. Basic blink effect (5 cycles)")
    effect = EffectPulse(mode="blink", cycles=5)
    await conductor.start(effect, lights)
    await asyncio.sleep(6)  # Wait for effect to complete

    # Example 2: Strobe effect with red color for contrast
    print("\n2. Red strobe effect (15 flashes)")
    red_strobe = HSBK.from_rgb(255, 0, 0)
    effect = EffectPulse(mode="strobe", period=0.2, cycles=15, color=red_strobe)
    await conductor.start(effect, lights)
    await asyncio.sleep(4)  # 0.2s * 15 cycles + buffer

    # Example 3: Breathe effect with custom color
    print("\n3. Breathe effect with blue color")
    blue = HSBK.from_rgb(0, 0, 255)
    effect = EffectPulse(mode="breathe", period=2.0, cycles=3, color=blue)
    await conductor.start(effect, lights)
    await asyncio.sleep(7)  # 2.0s * 3 cycles + buffer

    # Example 4: Ping effect (single pulse)
    print("\n4. Ping effect (single pulse)")
    red = HSBK.from_rgb(255, 0, 0)
    effect = EffectPulse(mode="ping", color=red)
    await conductor.start(effect, lights)
    await asyncio.sleep(2)

    # Example 5: Slow breathe with warm white
    print("\n5. Slow warm breathe (3 cycles)")
    warm = HSBK(hue=40, saturation=0.3, brightness=0.9, kelvin=2500)
    effect = EffectPulse(mode="breathe", period=3.0, cycles=3, color=warm)
    await conductor.start(effect, lights)
    await asyncio.sleep(10)  # 3.0s * 3 cycles + buffer

    print("\nAll effects completed!")
    print("Lights have been restored to their original state")


if __name__ == "__main__":
    asyncio.run(main())
