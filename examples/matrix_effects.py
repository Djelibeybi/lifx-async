"""MatrixLight tile effects example.

Demonstrates using built-in tile effects: MORPH, FLAME, SKY and COLOR_SWEEP
with various parameters.
"""

import argparse
import asyncio

from lifx import Colors, Device, MatrixLight
from lifx.protocol.protocol_types import FirmwareEffect, TileEffectSkyType


async def main(ip: str, serial: str | None = None):
    """Demonstrate MatrixLight tile effects."""
    print(f"Connecting to MatrixLight at {ip}...\n")

    # connect() asks the device what it is and returns the matching class.
    # Passing a known serial skips the extra GetService round trip.
    async with await Device.connect(ip, serial) as matrix:
        assert isinstance(matrix, MatrixLight), f"{ip} is not a matrix device"
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

        # SKY needs the matrix capability plus recent host firmware, so skip
        # the two SKY demos on devices that cannot run them.
        if await matrix.supports_sky_effect():
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
        else:
            print("\nSkipping the SKY demos: this device does not support them.")

        # Demonstrate COLOR_SWEEP effect
        #
        # COLOR_SWEEP was added in protocol.yml 0.10 (6 August 2026). The
        # protocol defines the effect type but no parameters of its own, so it
        # is driven like MORPH and FLAME: speed plus an optional palette. Which
        # products and firmware versions actually run it is not published, and
        # there is no capability flag to gate on, so a device that does not
        # support it will simply ignore the request rather than report an error.
        print("\nStarting COLOR_SWEEP effect...")
        print("  (sweeps the palette across the matrix)")
        await matrix.set_effect(
            effect_type=FirmwareEffect.COLOR_SWEEP,
            speed=5,
            palette=[Colors.PINK, Colors.PURPLE, Colors.BLUE, Colors.CYAN],
        )
        print("  Running for 10 seconds...")
        await asyncio.sleep(10)

        # Demonstrate custom palette effect
        print("\nStarting MORPH effect with custom ocean palette...")
        ocean_palette = [
            Colors.CYAN,
            Colors.BLUE,
            Colors.DARK_BLUE,
            Colors.ROYAL_BLUE,
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
    parser.add_argument(
        "--serial",
        help="Serial number, e.g. d073d5123456 (skips the serial lookup)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.ip, args.serial))
