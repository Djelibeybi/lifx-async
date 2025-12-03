"""MatrixLight tile effects example.

Demonstrates using built-in tile effects: MORPH, FLAME, and SKY with various parameters.
"""

import argparse
import asyncio

from lifx import HSBK, Colors, MatrixLight
from lifx.protocol.protocol_types import FirmwareEffect, TileEffectSkyType


async def main(ip: str):
    """Demonstrate MatrixLight tile effects."""
    print(f"Connecting to MatrixLight at {ip}...\n")

    async with await MatrixLight.from_ip(ip) as matrix:
        # Get device info
        _, power, label = await matrix.get_color()
        print(f"Connected to: {label}\n")

        if power == 0:
            print("Turning device ON...")
            await matrix.set_power(True)
            await asyncio.sleep(1)

        # Get current effect state
        print("Getting current effect state...")
        current_effect = await matrix.get_effect()
        print(f"Current effect: {current_effect.effect_type}")
        if current_effect.effect_type != FirmwareEffect.OFF:
            print(f"  Speed: {current_effect.speed}")
            print(f"  Duration: {current_effect.duration}s")
            if current_effect.palette:
                print(f"  Palette: {len(current_effect.palette)} colors")
        print()

        # Demonstrate MORPH effect
        print("Starting MORPH effect...")
        print("  (smooth color transitions across tiles)")
        await matrix.set_effect(
            effect_type=FirmwareEffect.MORPH,
            speed=5,
            palette=[Colors.RED, Colors.BLUE, Colors.GREEN, Colors.PURPLE],
        )
        print("  Running for 10 seconds...")
        await asyncio.sleep(10)

        # Demonstrate FLAME effect
        print("\nStarting FLAME effect...")
        print("  (flickering fire animation)")
        await matrix.set_effect(
            effect_type=FirmwareEffect.FLAME,
            speed=3,
            palette=[Colors.ORANGE, Colors.RED, Colors.YELLOW],
        )
        print("  Running for 10 seconds...")
        await asyncio.sleep(10)

        # Demonstrate SKY effect with SUNRISE
        print("\nStarting SKY effect with SUNRISE...")
        print("  (sunrise color progression)")
        await matrix.set_effect(
            effect_type=FirmwareEffect.SKY,
            speed=10,
            sky_type=TileEffectSkyType.SUNRISE,
        )
        print("  Running for 10 seconds...")
        await asyncio.sleep(10)

        # Demonstrate SKY effect with CLOUDS
        print("\nStarting SKY effect with CLOUDS...")
        print("  (moving cloud patterns)")
        await matrix.set_effect(
            effect_type=FirmwareEffect.SKY,
            speed=5,
            sky_type=TileEffectSkyType.CLOUDS,
            cloud_saturation_min=50,
            cloud_saturation_max=180,
        )
        print("  Running for 10 seconds...")
        await asyncio.sleep(10)

        # Demonstrate custom palette effect
        print("\nStarting MORPH effect with custom ocean palette...")
        ocean_palette = [
            Colors.CYAN,
            Colors.BLUE,
            HSBK(hue=210, saturation=1.0, brightness=0.4, kelvin=3500),  # deep blue
            HSBK(36408, 65535, 38550, 3500),  # Ocean blue
        ]
        await matrix.set_effect(
            effect_type=FirmwareEffect.MORPH,
            speed=3,
            palette=ocean_palette,
        )
        print("  Running for 10 seconds...")
        await asyncio.sleep(10)

        # Stop effect and restore
        print("\nStopping effect...")
        await matrix.set_effect(effect_type=FirmwareEffect.OFF)
        await asyncio.sleep(1)

        # Verify effect stopped
        final_effect = await matrix.get_effect()
        print(f"Final effect state: {final_effect.effect_type}")

        if power == 0:
            print("\nTurning device back OFF...")
            await matrix.set_power(False)

    print("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Demonstrate LIFX MatrixLight tile effects"
    )
    parser.add_argument(
        "--ip",
        required=True,
        help="IP address of the MatrixLight (e.g., 192.168.1.100)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.ip))
