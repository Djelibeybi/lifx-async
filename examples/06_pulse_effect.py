"""Example demonstrating pulse effects.

This example shows how to use the effects framework to create various
pulse effects (blink, strobe, breathe, ping, solid).

Requirements:
- One or more LIFX lights on the network
"""

import asyncio

from lifx import HSBK, Conductor, EffectPulse, Light, discover


async def main() -> None:
    """Run pulse effect examples."""
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

    # Example 1: Basic blink effect
    print("\n1. Basic blink effect (5 cycles)")
    effect = EffectPulse(mode="blink", cycles=5)
    await conductor.start(effect, lights)
    await asyncio.sleep(6)  # Wait for effect to complete

    # Example 2: Strobe effect
    print("\n2. Strobe effect (20 rapid flashes)")
    effect = EffectPulse(mode="strobe", cycles=20)
    await conductor.start(effect, lights)
    await asyncio.sleep(3)  # 0.1s * 20 cycles + buffer

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

    # Example 5: Solid effect (minimal brightness variation)
    print("\n5. Solid effect (minimal brightness variation)")
    green = HSBK.from_rgb(0, 255, 0)
    effect = EffectPulse(mode="solid", period=3.0, cycles=2, color=green)
    await conductor.start(effect, lights)
    await asyncio.sleep(7)

    print("\nAll effects completed!")
    print("Lights have been restored to their original state")


if __name__ == "__main__":
    asyncio.run(main())
