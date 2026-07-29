"""Paint a theme (colour palette) onto one or more LIFX devices.

Every colour-capable device paints a theme according to its own geometry:

- Light (bulbs, HEV, infrared): one colour picked at random from the palette
- MultiZoneLight (Z strips, Beam): palette blended evenly across the zones
- MatrixLight / CeilingLight (Tile, Candle, Path, Ceiling): palette interpolated
  across the 2D pixel grid using the Canvas API

`DeviceGroup.apply_theme()` dispatches to the right implementation per device,
so a mixed group of bulbs, strips and tiles can be painted in one call.

Usage:
    # List the built-in themes and exit
    python theme_paint.py --list

    # Paint a built-in theme onto every device on the network
    python theme_paint.py --theme exciting

    # Target specific devices by IP address and/or serial number
    python theme_paint.py --theme fire 192.168.1.100 d073d5123456

    # Fade a custom palette in over two seconds
    python theme_paint.py --colors ff0000,00ff00,0000ff --duration 2.0

    # Leave devices that are off alone
    python theme_paint.py --theme evening --no-power-on
"""

#  Copyright (c) 2026 Avi Miller <me@dje.li>
#  Licensed under the Universal Permissive License v 1.0 as shown at https://opensource.org/license/UPL

import argparse
import asyncio
import sys

from lifx import (
    HSBK,
    CeilingLight,
    DeviceGroup,
    Light,
    MatrixLight,
    MultiZoneLight,
    Theme,
    ThemeLibrary,
    discover,
    find_by_ip,
    find_by_serial,
    get_theme,
)


def parse_hex_colors(spec: str) -> Theme:
    """Build a custom theme from a comma-separated list of hex RGB colours.

    Args:
        spec: Colours as `ff0000,00ff00,#0000ff` (leading `#` optional).

    Returns:
        Theme containing the parsed colours.

    Raises:
        ValueError: If a colour is not six hex digits.
    """
    colors: list[HSBK] = []

    for raw in spec.split(","):
        value = raw.strip().lstrip("#")
        if len(value) != 6:
            raise ValueError(f"'{raw.strip()}' is not a six digit hex colour")
        red, green, blue = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
        colors.append(HSBK.from_rgb(red, green, blue))

    if not colors:
        raise ValueError("No colours supplied")

    return Theme(colors)


async def resolve_devices(targets: list[str]) -> list[Light]:
    """Resolve IP addresses or serial numbers to Light devices.

    Auto-detects IPs (contain '.') vs serials.

    Args:
        targets: List of IP addresses or serial numbers.

    Returns:
        List of resolved Light devices.
    """
    lights: list[Light] = []

    for target in targets:
        if "." in target:
            print(f"  Looking up IP {target}...")
            device = await find_by_ip(target, timeout=5.0)
        else:
            print(f"  Looking up serial {target}...")
            device = await find_by_serial(target, timeout=5.0)

        if device is None:
            print(f"  Warning: No device found for '{target}', skipping")
        elif not isinstance(device, Light):
            print(
                f"  Warning: {target} is a {type(device).__name__},"
                " not a colour-capable light, skipping"
            )
        else:
            print(f"  Resolved: {device.label} [{device.serial}] -> {device.ip}")
            lights.append(device)

    return lights


async def discover_lights() -> list[Light]:
    """Discover all colour-capable lights on the network.

    Returns:
        List of discovered Light devices.
    """
    print("Discovering LIFX devices...")
    return [device async for device in discover() if isinstance(device, Light)]


async def describe(light: Light) -> str:
    """Describe how a theme will be painted onto a light.

    Args:
        light: Device to describe.

    Returns:
        Human readable description of the paint geometry.
    """
    # CeilingLight extends MatrixLight, so check it first.
    if isinstance(light, CeilingLight):
        tiles = await light.get_device_chain()
        zones = sum(tile.total_zones for tile in tiles)
        return f"ceiling, {zones} pixels (interpolated)"

    if isinstance(light, MatrixLight):
        tiles = await light.get_device_chain()
        zones = sum(tile.total_zones for tile in tiles)
        return f"matrix, {len(tiles)} tile(s), {zones} pixels (interpolated)"

    if isinstance(light, MultiZoneLight):
        zone_count = await light.get_zone_count()
        return f"multizone, {zone_count} zones (blended)"

    return "single zone (one random palette colour)"


async def main(
    targets: list[str],
    theme: Theme,
    theme_name: str,
    duration: float,
    power_on: bool,
) -> int:
    """Paint a theme onto the requested devices.

    Args:
        targets: IP addresses or serial numbers; empty means discover.
        theme: Theme to paint.
        theme_name: Name of the theme, for display.
        duration: Transition duration in seconds.
        power_on: Turn devices on before painting.

    Returns:
        Process exit code.
    """
    if targets:
        print("Resolving devices...")
        lights = await resolve_devices(targets)
    else:
        lights = await discover_lights()

    if not lights:
        print("No colour-capable lights found.")
        return 1

    print(f"\nPainting '{theme_name}' ({len(theme.colors)} colours) onto:")
    for light in lights:
        print(f"  {light.label} [{light.serial}] - {await describe(light)}")

    async with DeviceGroup(list(lights)) as group:
        await group.apply_theme(theme, power_on=power_on, duration=duration)

    print(f"\nDone: {len(lights)} device(s) painted over {duration:.1f}s.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Paint a theme onto LIFX bulbs, strips and matrix devices"
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="IP addresses and/or serial numbers (default: discover everything)",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--theme",
        "-t",
        default="evening",
        help="Name of a built-in theme (default: evening)",
    )
    source.add_argument(
        "--colors",
        "-c",
        help="Custom palette as comma-separated hex RGB, e.g. ff0000,00ff00,0000ff",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=float,
        default=1.0,
        help="Transition duration in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--no-power-on",
        dest="power_on",
        action="store_false",
        help="Leave powered-off devices off instead of turning them on",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List the built-in themes and exit",
    )
    args = parser.parse_args()

    if args.list:
        names = ThemeLibrary.get_available_themes()
        print(f"{len(names)} built-in themes:\n")
        for name in names:
            print(f"  {name}")
        sys.exit(0)

    if args.colors:
        try:
            selected_theme = parse_hex_colors(args.colors)
        except ValueError as err:
            parser.error(str(err))
        selected_name = "custom"
    else:
        try:
            selected_theme = get_theme(args.theme)
        except KeyError as err:
            parser.error(str(err).strip('"'))
        selected_name = args.theme

    sys.exit(
        asyncio.run(
            main(
                args.targets,
                selected_theme,
                selected_name,
                args.duration,
                args.power_on,
            )
        )
    )
