"""Example demonstrating background effect execution.

This example shows how conductor.start() returns immediately, allowing
effects to run in the background while you continue doing other work.

Requirements:
- One or more LIFX lights on the network
"""

import asyncio

from lifx import discover
from lifx.effects import Conductor, EffectColorloop


async def main() -> None:
    """Run background effect example."""
    print("Discovering LIFX devices...")

    async with discover() as group:
        if not group.lights:
            print("No lights found")
            return

        print(f"Found {len(group.lights)} light(s)")
        conductor = Conductor()

        # Start a colorloop effect in the background
        print("\nStarting colorloop effect in background...")
        effect = EffectColorloop(period=30, change=20, synchronized=True)
        await conductor.start(effect, group.lights)
        print("✓ conductor.start() returned immediately!")
        print("  Effect is now running in the background")

        # Do other work while effect runs
        print("\nDoing other work while effect runs:")
        for i in range(5):
            await asyncio.sleep(2)
            print(f"  Tick {i + 1}/5 - effect still running...")

        # Stop the effect
        print("\nStopping effect and restoring lights...")
        await conductor.stop(group.lights)
        print("✓ Effect stopped, lights restored!")


if __name__ == "__main__":
    asyncio.run(main())
