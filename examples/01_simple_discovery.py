"""Basic device discovery example.

This example demonstrates how to discover LIFX devices on your network
and display information about each device found.
"""

import asyncio
import logging

from lifx import discover

# Enable logging to see what's happening
logging.basicConfig(level=logging.INFO)


async def main():
    """Discover lights and display information."""
    print("Discovering LIFX lights...")
    print("This will broadcast on your network and wait for responses.")
    print()

    # Discover lights with 5 second timeout
    async with discover(timeout=5.0, broadcast_address="192.168.19.255") as group:
        if not group.lights:
            print("No lights found!")
            print("\nTroubleshooting:")
            print("1. Ensure lights are powered on")
            print("2. Check that lights are on the same network")
            print("3. Verify firewall allows UDP port 56700")
            return

        print(f"Found {len(group.lights)} lights(s):\n")

        # Display information about each device
        for i, light in enumerate(group.lights, 1):
            print(f"Light {i}:")
            print(f"  Serial: {light.serial}")
            print(f"  IP: {light.ip}")
            print(f"  Port: {light.port}")

            async with light:
                print(f"  Product: {light.model}")
                if light.label is not None:
                    print(f"  Label: {light.label[0]}")
                if light.power is not None:
                    print(f"  Power: {'ON' if light.power[0] else 'OFF'}")
                if light.host_firmware is not None:
                    firmware = light.host_firmware[0]
                    print(
                        f"  Firmware: {firmware.version_major}.{firmware.version_minor}"
                    )
                if light.color is not None:
                    print(f"  Color: {light.color[0].as_dict()}")

            print()


if __name__ == "__main__":
    asyncio.run(main())
