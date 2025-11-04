"""Simple light control example.

Demonstrates basic operations: turning lights on/off and changing colors.
"""

import argparse
import asyncio

from lifx import HSBK, Colors, Light


async def main(ip: str):
    """Control a single light."""
    print(f"Connecting to light at {ip}...")

    async with await Light.from_ip(ip) as light:
        # Get device name
        label = await light.get_label()
        print(f"Connected to: {label}\n")

        # Turn on the light
        print("Turning light ON...")
        await light.set_power(True)
        await asyncio.sleep(1)

        # Set to blue
        print("Setting color to BLUE...")
        await light.set_color(Colors.BLUE, duration=1.0)
        await asyncio.sleep(2)

        # Set to red
        print("Setting color to RED...")
        await light.set_color(Colors.RED, duration=1.0)
        await asyncio.sleep(2)

        # Set to green
        print("Setting color to GREEN...")
        await light.set_color(Colors.GREEN, duration=1.0)
        await asyncio.sleep(2)

        # Set custom color using HSBK
        print("Setting custom purple color...")
        purple = HSBK(hue=280, saturation=1.0, brightness=0.7, kelvin=3500)
        await light.set_color(purple, duration=1.0)
        await asyncio.sleep(2)

        # Adjust brightness
        print("Dimming to 30%...")
        await light.set_brightness(0.3, duration=1.0)
        await asyncio.sleep(2)

        # Set to warm white
        print("Setting to warm white...")
        warm_white = HSBK(hue=0, saturation=0.0, brightness=0.8, kelvin=2700)
        await light.set_color(warm_white, duration=1.0)
        await asyncio.sleep(2)

        # Turn off
        print("Turning light OFF...")
        await light.set_power(False, duration=1.0)

    print("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Control a LIFX light")
    parser.add_argument(
        "--ip", required=True, help="IP address of the light (e.g., 192.168.1.100)"
    )
    args = parser.parse_args()

    asyncio.run(main(args.ip))
