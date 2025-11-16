"""Example demonstrating colorloop effect.

This example shows how to use the colorloop effect to create a continuous
rainbow color rotation across lights. Includes both spread mode (lights
display different colors) and synchronized mode (all lights same color).

Requirements:
- One or more LIFX lights on the network
"""

import asyncio

from lifx import Light, discover
from lifx.effects import Conductor, EffectColorloop


async def main() -> None:
    """Run colorloop effect examples."""
    print("Discovering LIFX devices...")

    lights: list[Light] = []
    async for device in discover():
        if isinstance(device, Light):
            lights.append(device)

    if not lights:
        print("No lights found")
        return

    print(f"Found {len(lights)} light(s)")
    conductor = Conductor()

    # Example 1: Basic rainbow effect
    print("\n1. Basic rainbow effect (30 seconds)")
    effect = EffectColorloop(period=30, change=20, spread=60)
    await conductor.start(effect, lights)
    await asyncio.sleep(30)
    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    await asyncio.sleep(2)  # Brief pause

    # Example 2: Fast color rotation with high saturation
    print("\n2. Fast rainbow (20 seconds)")
    effect = EffectColorloop(
        period=15, change=30, spread=45, saturation_min=0.9, saturation_max=1.0
    )
    await conductor.start(effect, lights)
    await asyncio.sleep(20)
    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    await asyncio.sleep(2)  # Brief pause

    # Example 3: Colorloop with fixed brightness
    print("\n3. Colorloop with fixed 70% brightness (25 seconds)")
    effect = EffectColorloop(
        period=20, change=25, spread=30, brightness=0.7, transition=1.5
    )
    await conductor.start(effect, lights)
    await asyncio.sleep(25)
    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    await asyncio.sleep(2)  # Brief pause

    # Example 4: Synchronized colorloop - all lights same color
    print("\n4. Synchronized colorloop - all lights change together (30 seconds)")
    effect = EffectColorloop(period=30, change=20, synchronized=True, brightness=0.8)
    await conductor.start(effect, lights)
    await asyncio.sleep(30)
    await conductor.stop(lights)
    print("Stopped. Lights restored to original state.")

    print("\nAll effects completed!")
    print("Lights have been restored to their original state")


if __name__ == "__main__":
    asyncio.run(main())
