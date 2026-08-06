"""Switch button configuration example.

Demonstrates reading and changing the button backlight colors and haptic
feedback duration on a LIFX Switch or Dimmer. Restores the original
configuration when done.
"""

import argparse
import asyncio

from lifx import HSBK, Device, Switch


async def main(ip: str, serial: str | None = None):
    """Configure the buttons on a single switch."""
    print(f"Connecting to switch at {ip}...")

    # connect() asks the device what it is and returns the matching class.
    # Passing a known serial skips the extra GetService round trip.
    async with await Device.connect(ip, serial) as switch:
        if not isinstance(switch, Switch):
            print(f"Device at {ip} is a {type(switch).__name__}, not a Switch.")
            return

        label = await switch.get_label()
        print(f"Connected to: {label}\n")

        # Read the current device-wide button configuration
        original = await switch.get_button_config()
        print("Current button configuration:")
        print(f"  Haptic duration:    {original.haptic_duration_ms}ms")
        print(f"  Backlight when on:  {original.backlight_on_color}")
        print(f"  Backlight when off: {original.backlight_off_color}")

        # Set both backlight colors. One configuration applies to every
        # button on the device - they cannot be configured individually.
        print("\nSetting backlights to GREEN (on) and dim RED (off)...")
        await switch.set_button_config(
            backlight_on_color=HSBK(
                hue=120, saturation=1.0, brightness=0.8, kelvin=3500
            ),
            backlight_off_color=HSBK(
                hue=0, saturation=1.0, brightness=0.2, kelvin=3500
            ),
        )
        await asyncio.sleep(5)

        # Arguments left out keep their current value, so this changes only
        # the haptic feedback duration (0-500ms; 0 disables it). The LIFX
        # Dimmer has no haptic motor and ignores this value.
        print("Disabling haptic feedback...")
        await switch.set_button_config(haptic_duration_ms=0)
        await asyncio.sleep(5)

        # Restore the original configuration
        print("Restoring original configuration...")
        await switch.set_button_config(
            haptic_duration_ms=original.haptic_duration_ms,
            backlight_on_color=original.backlight_on_color,
            backlight_off_color=original.backlight_off_color,
        )

    print("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Configure LIFX Switch or Dimmer buttons"
    )
    parser.add_argument(
        "--ip", required=True, help="IP address of the switch (e.g., 192.168.1.100)"
    )
    parser.add_argument(
        "--serial",
        help="Serial number, e.g. d073d5123456 (skips the serial lookup)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.ip, args.serial))
