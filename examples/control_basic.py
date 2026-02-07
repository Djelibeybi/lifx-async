"""Simple light control example.

Demonstrates basic operations: turning lights on/off and changing colors.
"""

import argparse
import asyncio

from lifx import Colors, Light


async def main(ip: str):
    """Control a single light."""
    print(f"Connecting to light at {ip}...")

    async with await Light.from_ip(ip) as light:
        # Get device state
        color, power, label = await light.get_color()
        print(f"Connected to: {label}\n")

        if power == 0:
            # Turn on the light
            print("Turning light ON...")
            await light.set_power(True)
            await asyncio.sleep(1)

        # Set to blue
        print("Setting color to BLUE...")
        await light.set_color(Colors.BLUE, duration=1.0)
        await asyncio.sleep(2)

        # Change to red
        print("Changing color to RED...")
        await light.set_hue(hue=0, duration=1.0)
        await asyncio.sleep(2)

        # Reduce saturation
        print("Reducing saturation to 50%...")
        await light.set_saturation(saturation=0.5, duration=1.0)
        await asyncio.sleep(2)

        # Adjust brightness
        print("Adjusting brightness to 30%...")
        await light.set_brightness(0.3, duration=1.0)
        await asyncio.sleep(2)

        # Set to warm white
        print("Switching to incandescent white...")
        await light.set_kelvin(kelvin=2700, duration=1.0)
        await asyncio.sleep(2)

        # Restore original state
        print("Restoring original state...")
        await light.set_color(color, duration=1.0)
        await asyncio.sleep(2)

        if power == 0:
            # Turn off
            print("Turning light back OFF...")
            await light.set_power(False, duration=1.0)

    print("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Control a LIFX light")
    parser.add_argument(
        "--ip", required=True, help="IP address of the light (e.g., 192.168.1.100)"
    )
    args = parser.parse_args()

    asyncio.run(main(args.ip))
