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
    """Discover devices and display information."""
    print("Discovering LIFX devices...")
    print("This will broadcast on your network and wait for responses.")
    print()

    # Discover devices with 3 second timeout
    async with discover(timeout=3.0) as group:
        if not group.devices:
            print("No devices found!")
            print("\nTroubleshooting:")
            print("1. Ensure devices are powered on")
            print("2. Check that devices are on the same network")
            print("3. Verify firewall allows UDP port 56700")
            return

        print(f"Found {len(group.devices)} device(s):\n")

        # Display information about each device
        for i, device in enumerate(group.devices, 1):
            print(f"Device {i}:")
            print(f"  Serial: {device.serial}")
            print(f"  IP: {device.ip}")
            print(f"  Port: {device.port}")

            try:
                # Get device label
                label = await device.get_label()
                print(f"  Label: {label}")

                # Get power state
                power = await device.get_power()
                print(f"  Power: {'ON' if power else 'OFF'}")

                # Get version info
                version = await device.get_version()
                print(f"  Product ID: {version.product}")

                # Get firmware info
                firmware = await device.get_host_firmware()
                print(f"  Firmware: {firmware.version_major}.{firmware.version_minor}")

            except Exception as e:
                print(f"  Error querying device: {e}")

            print()


if __name__ == "__main__":
    asyncio.run(main())
