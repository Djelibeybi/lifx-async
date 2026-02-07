"""DeviceGroup operations example.

Demonstrates how to use DeviceGroup for batch operations, filtering devices
by type, and organizing devices by location or group.

Usage:
    python control_device_groups.py              # Read-only: displays device info
    python control_device_groups.py --demo       # Also runs batch color/brightness demo
"""

import argparse
import asyncio

from lifx import Colors, DeviceGroup, Light, discover


async def main(run_demo: bool = False):
    """Demonstrate DeviceGroup functionality.

    Args:
        run_demo: If True, also run batch operations that change light states
    """
    print("Discovering LIFX devices...")

    # Collect all devices
    devices = []
    async for device in discover():
        devices.append(device)

    if not devices:
        print("No devices found.")
        return

    # Create a DeviceGroup from discovered devices
    async with DeviceGroup(devices) as group:
        print(f"\nFound {len(group)} devices total")

        # =====================================================
        # Device Type Filters
        # =====================================================
        # DeviceGroup provides properties to filter devices by type

        print("\n--- Device Type Filters ---")
        print(f"  All lights:       {len(group.lights)}")
        print(f"  HEV lights:       {len(group.hev_lights)}")
        print(f"  Infrared lights:  {len(group.infrared_lights)}")
        print(f"  MultiZone lights: {len(group.multizone_lights)}")
        print(f"  Matrix lights:    {len(group.matrix_lights)}")

        # Show details for specialized device types
        if group.hev_lights:
            print("\nHEV lights found - these support germicidal cleaning cycles")
            for light in group.hev_lights:
                print(f"  - {light.label}")

        if group.infrared_lights:
            print("\nInfrared lights found - these have IR LEDs for night vision")
            for light in group.infrared_lights:
                print(f"  - {light.label}")

        if group.multizone_lights:
            print("\nMultiZone lights found - these are strips or beams with zones")
            for light in group.multizone_lights:
                print(f"  - {light.label}")

        if group.matrix_lights:
            print("\nMatrix lights found - these are tiles with addressable pixels")
            for light in group.matrix_lights:
                print(f"  - {light.label}")

        # =====================================================
        # Batch Operations Demo (optional)
        # =====================================================
        # DeviceGroup methods operate on all devices concurrently

        if run_demo:
            print("\n--- Batch Operations Demo ---")

            # Capture original state of all lights concurrently
            print("Capturing original light states...")
            state_results = await asyncio.gather(
                *(light.get_color() for light in group.lights)
            )
            original_states: dict[str, tuple] = {
                light.serial: (color, power)
                for light, (color, power, label) in zip(group.lights, state_results)
            }

            try:
                print("Setting all lights to blue...")
                await group.set_color(Colors.BLUE, duration=1.0)
                await asyncio.sleep(1.5)

                print("Dimming all lights to 50%...")
                await group.set_brightness(0.5, duration=1.0)
                await asyncio.sleep(1.5)

                print("Setting all lights to warm white...")
                await group.set_color(Colors.WARM_WHITE, duration=1.0)
                await asyncio.sleep(1.5)

            finally:
                # Restore original states concurrently
                print("Restoring original light states...")

                async def restore_light(light: Light) -> None:
                    """Restore a single light to its original state."""
                    if light.serial in original_states:
                        color, power = original_states[light.serial]
                        await light.set_color(color, duration=1.0)
                        if power == 0:
                            await light.set_power(False)

                await asyncio.gather(*(restore_light(light) for light in group.lights))
                await asyncio.sleep(1.5)
                print("Original states restored.")

        # =====================================================
        # Organization by Location
        # =====================================================
        # Group devices by their LIFX app location assignment

        print("\n--- Organization by Location ---")
        by_location = await group.organize_by_location()

        if by_location:
            print("Devices organized by location:")
            for location_name, location_group in by_location.items():
                print(f"  {location_name}: {len(location_group)} device(s)")
                for device in location_group:
                    print(f"    - {device.label}")
        else:
            print("No locations configured in the LIFX app")

        # =====================================================
        # Organization by Group
        # =====================================================
        # Group devices by their LIFX app group assignment

        print("\n--- Organization by Group ---")
        by_group = await group.organize_by_group()

        if by_group:
            print("Devices organized by group:")
            for group_name, group_devices in by_group.items():
                print(f"  {group_name}: {len(group_devices)} device(s)")
                for device in group_devices:
                    print(f"    - {device.label}")
        else:
            print("No groups configured in the LIFX app")

        # =====================================================
        # Filter Methods
        # =====================================================
        # Quick filtering to a specific location or group

        print("\n--- Filter Methods ---")
        if by_location:
            first_location = next(iter(by_location.keys()))
            try:
                filtered = await group.filter_by_location(first_location)
                print(
                    f"Filtered by location '{first_location}': {len(filtered)} devices"
                )
            except KeyError as e:
                print(f"Filter error: {e}")

        if by_group:
            first_group = next(iter(by_group.keys()))
            try:
                filtered = await group.filter_by_group(first_group)
                print(f"Filtered by group '{first_group}': {len(filtered)} devices")
            except KeyError as e:
                print(f"Filter error: {e}")

        # =====================================================
        # Iterating Over Devices
        # =====================================================
        # DeviceGroup supports iteration and indexing

        print("\n--- Iteration ---")
        print("All devices in group:")
        for i, device in enumerate(group):
            print(f"  [{i}] {device.label} ({device.serial})")

        # Access by index
        if len(group) > 0:
            first_device = group[0]
            print(f"\nFirst device: {first_device.label}")

    print("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Demonstrate DeviceGroup functionality"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run batch operations demo (changes light colors/brightness)",
    )
    args = parser.parse_args()

    asyncio.run(main(run_demo=args.demo))
