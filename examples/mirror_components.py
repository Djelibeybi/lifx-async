"""Independent front/back control for a LIFX Mirror.

Demonstrates the MirrorLight API: reading the component layout, driving the
front (room-facing task light) and back (wall-facing backwash) rings
independently, painting a per-zone gradient, applying a different theme to each
component, and restoring colours after the whole light is powered off.

Both components are closed rings of 25 zones each, so either one can carry its
own gradient or theme.

The mirror's original power state and colours are restored before exiting.
"""

import argparse
import asyncio

from lifx import HSBK, Device, MirrorLight
from lifx.theme import get_theme

# Warm task light for the front ring, dim amber backwash for the back ring
TASK_WHITE = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=4500)
BACKWASH = HSBK(hue=30, saturation=0.4, brightness=0.3, kelvin=2700)


def gradient(zone_count: int, start_hue: float, end_hue: float) -> list[HSBK]:
    """Build a hue gradient with one colour per zone."""
    if zone_count == 1:
        return [HSBK(hue=start_hue, saturation=1.0, brightness=0.7, kelvin=3500)]

    step = (end_hue - start_hue) / (zone_count - 1)
    return [
        HSBK(
            hue=(start_hue + step * i) % 360,
            saturation=1.0,
            brightness=0.7,
            kelvin=3500,
        )
        for i in range(zone_count)
    ]


async def main(ip: str, serial: str | None = None, hold: float = 3.0) -> None:
    """Run the front/back component demo against one Mirror."""
    print(f"Connecting to Mirror at {ip}...\n")

    # connect() asks the device what it is and returns the matching class.
    # Passing a known serial skips the extra GetService round trip.
    async with await Device.connect(ip, serial) as mirror:
        assert isinstance(mirror, MirrorLight), f"{ip} is not a Mirror light"

        color, power, label = await mirror.get_color()
        layout = mirror.layout
        print(f"Connected to: {label}")
        print(f"Power: {'ON' if power > 0 else 'OFF'}")
        print(f"Current color: {color}")
        print(f"Matrix: {layout.width}x{layout.height} ({layout.buffer_size} buffer)")
        print(f"Front zones: {mirror.front_zone_count} (on: {mirror.front_is_on})")
        print(f"Back zones:  {mirror.back_zone_count} (on: {mirror.back_is_on})\n")

        # Capture everything needed to put the mirror back as we found it
        original_power = power
        original_front = await mirror.get_front_colors()
        original_back = await mirror.get_back_colors()
        front_was_on = mirror.front_is_on
        back_was_on = mirror.back_is_on

        print("1. Front only: warm task light, back off")
        await mirror.turn_back_off()
        await mirror.turn_front_on(TASK_WHITE, duration=1.0)
        await asyncio.sleep(hold)

        print("2. Back only: amber backwash, front off")
        await mirror.turn_front_off(duration=1.0)
        await mirror.turn_back_on(BACKWASH, duration=1.0)
        await asyncio.sleep(hold)

        print("3. Both components lit with different colours")
        await mirror.set_front_colors(TASK_WHITE, duration=1.0)
        await asyncio.sleep(hold)

        print("4. Hue gradient around the front ring, back left as-is")
        await mirror.set_front_colors(
            gradient(mirror.front_zone_count, 0, 300), duration=1.0
        )
        await asyncio.sleep(hold)

        print("5. Counter-rotating gradient around the back ring")
        await mirror.set_back_colors(
            gradient(mirror.back_zone_count, 300, 0), duration=1.0
        )
        await asyncio.sleep(hold)

        print("6. A different theme on each component: evening / galaxy")
        await mirror.apply_front_theme(get_theme("evening"), duration=1.0)
        await mirror.apply_back_theme(get_theme("galaxy"), duration=1.0)
        await asyncio.sleep(hold)

        # Powering the whole light off captures both components' colours, so a
        # single component can be brought back without touching the other.
        print("7. Whole light off, then back ring only restored from memory")
        await mirror.set_power(False, duration=1.0)
        await asyncio.sleep(hold)
        await mirror.turn_back_on(duration=1.0)
        await asyncio.sleep(hold)

        print("\nRestoring original state...")
        if front_was_on:
            await mirror.turn_front_on(original_front, duration=1.0)
        else:
            # A component that was off has brightness 0 in every zone, which
            # turn_front_off() rejects as an explicit colour list. Passing no
            # colours stores the current ones instead.
            await mirror.turn_front_off(duration=1.0)

        if back_was_on:
            await mirror.turn_back_on(original_back, duration=1.0)
        else:
            await mirror.turn_back_off(duration=1.0)

        if original_power == 0:
            await mirror.set_power(False, duration=1.0)

    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Control the front and back components of a LIFX Mirror"
    )
    parser.add_argument(
        "--ip",
        required=True,
        help="IP address of the Mirror (e.g., 192.168.1.100)",
    )
    parser.add_argument(
        "--serial",
        help="Serial number, e.g. d073d5123456 (skips the serial lookup)",
    )
    parser.add_argument(
        "--hold",
        type=float,
        default=3.0,
        help="Seconds to hold each step before moving on (default: 3.0)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.ip, args.serial, args.hold))
