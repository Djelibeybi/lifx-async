"""Basic device discovery example.

This example demonstrates how to discover LIFX devices on your network
and display information about each device found.
"""

import asyncio
import logging

from lifx import Light, discover

# Enable logging to see what's happening
logging.basicConfig(level=logging.INFO)


async def main():
    """Discover lights and display information."""
    print("Discovering LIFX lights...")
    print("This will broadcast on your network and wait for responses.")
    print()

    # Discover lights with 5 second timeout
    async for light in discover(timeout=5.0, broadcast_address="255.255.255.255"):
        # Display information about each device
        print("Light:")
        print(f"  Serial: {light.serial}")
        print(f"  IP: {light.ip}")
        print(f"  Port: {light.port}")

        if isinstance(light, Light):
            color, power, label = await light.get_color()
            print(f"  Label: {label}")
            print(f"  Power: {'ON' if power else 'OFF'}")
            print(f"  Color: {color.as_dict()}")

        print()


if __name__ == "__main__":
    asyncio.run(main())
