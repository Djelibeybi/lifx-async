"""Find specific LIFX devices by label, serial, or IP address.

This example demonstrates the targeted discovery functions:
- find_by_label() - Find a device by its label/name
- find_by_serial() - Find a device by its serial number
- find_by_ip() - Find a device by its IP address

These functions are more efficient than discovering all devices and then
filtering, especially on large networks.
"""

import argparse
import asyncio
import time

from lifx import find_by_ip, find_by_label, find_by_serial


async def find_by_label_example(label: str, exact_match: bool = False) -> None:
    """Find device(s) by label."""
    start = time.monotonic()

    print(f"\nSearching for device(s) with label: '{label}'")
    print()

    async for device in find_by_label(
        label, exact_match=exact_match, broadcast_address="255.255.255.255"
    ):
        async with device:
            elapsed = f"{time.monotonic() - start:.2f}"
            print(
                f"[{device.serial}] {device.label}: {device.model}"
                f" - {device.group} ({device.ip}) in {elapsed} seconds"
            )


async def find_by_serial_example(serial: str) -> None:
    """Find a device by its serial number."""
    print(f"\nSearching for device with serial: {serial}")
    print()

    start = time.monotonic()

    device = await find_by_serial(serial, timeout=5.0)

    if device is None:
        print(f"❌ No device found with serial '{serial}'")
        print("\nTroubleshooting:")
        print("1. Check that the serial number is correct (12 hex digits)")
        print("2. Ensure the device is powered on and on the network")
        print("3. Serial format: 'd073d5123456' or 'd0:73:d5:12:34:56'")
        return

    print(f"✅ Found device in {time.monotonic() - start:.2f} seconds!")
    await display_device_info(device)


async def find_by_ip_example(ip: str) -> None:
    """Find a device by its IP address."""
    print(f"\nSearching for device at IP: {ip}")
    print()

    start = time.monotonic()
    device = await find_by_ip(ip, timeout=5.0)

    if device is None:
        print(f"❌ No device found at IP '{ip}'")
        print("\nTroubleshooting:")
        print("1. Verify the IP address is correct")
        print("2. Ensure the device is powered on and reachable")
        print("3. Check that no firewall is blocking UDP port 56700")
        return

    print(f"✅ Found device in {time.monotonic() - start:.2f} seconds!")
    await display_device_info(device)


async def display_device_info(device) -> None:
    """Display detailed information about a device."""
    print("\nDevice Information:")
    print(f"  Type: {type(device).__name__}")
    print(f"  Serial: {device.serial}")
    print(f"  IP Address: {device.ip}")
    print(f"  Port: {device.port}")

    start = time.monotonic()

    # Connect to get additional info
    async with device:
        # Get basic info
        color, power, label = await device.get_color()

        print(f"  Label: {label}")
        print(f"  Product: {device.model}")
        print(f"  Power: {'ON' if power else 'OFF'}")

        # Display firmware version
        if device.host_firmware:
            fw = device.host_firmware
            print(f"  Firmware: {fw.version_major}.{fw.version_minor}")

        # Display MAC address if available
        if device.mac_address:
            print(f"  MAC Address: {device.mac_address}")

        # Display color information for color-capable lights
        if hasattr(device, "get_color"):
            print("\n  Color State:")
            print(f"    Hue: {color.hue:.1f}°")
            print(f"    Saturation: {color.saturation * 100:.1f}%")
            print(f"    Brightness: {color.brightness * 100:.1f}%")
            print(f"    Kelvin: {color.kelvin}K")

        # Display device-specific capabilities
        if device.capabilities:
            cap = device.capabilities
            print("\n  Capabilities:")
            print(f"    Color: {cap.has_color}")
            print(f"    Infrared: {cap.has_infrared}")
            print(f"    Multizone: {cap.has_multizone}")
            print(f"    Chain: {cap.has_chain}")
            print(f"    Matrix: {cap.has_matrix}")
            print(f"    HEV: {cap.has_hev}")

        print(f"\nRetrieved device info in {time.monotonic() - start:.2f} seconds")


async def main():
    """Main function to parse arguments and execute the appropriate search."""
    parser = argparse.ArgumentParser(
        description="Find specific LIFX devices by label, serial, or IP address",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find a device by label (substring match)
  python 10_find_specific_devices.py --label "Living"  # Matches "Living Room"

  # Find a device by exact label
  python 10_find_specific_devices.py --label "Living Room" --exact

  # Find a device by serial number
  python 10_find_specific_devices.py --serial d073d5123456

  # Find a device by IP address
  python 10_find_specific_devices.py --ip 192.168.1.100

  # Serial number formats (both work):
  python 10_find_specific_devices.py --serial d073d5123456
  python 10_find_specific_devices.py --serial d0:73:d5:12:34:56
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--label",
        "-l",
        type=str,
        help="Find device by label/name (case-insensitive, substring match by default)",
    )
    parser.add_argument(
        "--exact",
        "-e",
        action="store_true",
        help="Use exact match for label search (default: substring match)",
    )
    group.add_argument(
        "--serial",
        "-s",
        type=str,
        help="Find device by serial number (12 hex digits, with or without colons)",
    )
    group.add_argument(
        "--ip",
        "-i",
        type=str,
        help="Find device by IP address",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("LIFX Device Finder")
    print("=" * 70)

    try:
        if args.label:
            await find_by_label_example(args.label, exact_match=args.exact)
        elif args.serial:
            await find_by_serial_example(args.serial)
        elif args.ip:
            await find_by_ip_example(args.ip)
    except KeyboardInterrupt:
        print("\n\nSearch cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
