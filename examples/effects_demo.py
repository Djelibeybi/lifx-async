# /// script
# requires-python = ">=3.11"
# dependencies = ["lifx-async"]
# ///
"""Demo script for lifx-async effects.

Discovers a LIFX device and runs a specific effect or cycles through all
compatible effects. Automatically detects device type (matrix, multizone,
or single-bulb light) and selects appropriate effects.

Usage:
    # Run a specific effect on a device by IP
    uv run examples/effects_demo.py --ip 192.168.1.100 --effect plasma

    # Run a specific effect on a device by serial
    uv run examples/effects_demo.py --serial d073d5123456 --effect flame

    # Cycle through all compatible effects
    uv run examples/effects_demo.py --ip 192.168.1.100 --cycle

    # Cycle with custom duration per effect (default 10s)
    uv run examples/effects_demo.py --ip 192.168.1.100 --cycle --duration 15

    # List all available effects
    uv run examples/effects_demo.py --list
"""

#  Copyright (c) 2026 Avi Miller <me@dje.li>
#  Licensed under the Universal Permissive License v 1.0 as shown at https://opensource.org/license/UPL

import argparse
import asyncio
import sys

from lifx import Light, find_by_ip, find_by_serial
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects import Conductor
from lifx.effects.registry import DeviceSupport, DeviceType, get_effect_registry


def classify_device(device: Light) -> DeviceType:
    """Classify a device into a DeviceType category."""
    if isinstance(device, MatrixLight):
        return DeviceType.MATRIX
    if isinstance(device, MultiZoneLight):
        return DeviceType.MULTIZONE
    return DeviceType.LIGHT


def list_effects() -> None:
    """Print all available effects with device compatibility."""
    registry = get_effect_registry()
    print(f"\nAvailable effects ({len(registry.effects)} total):\n")
    print(f"  {'Effect':<20} {'Light':<14} {'MultiZone':<14} {'Matrix':<14}")
    print(f"  {'─' * 20} {'─' * 14} {'─' * 14} {'─' * 14}")
    for info in sorted(registry.effects, key=lambda e: e.name):
        light = info.device_support.get(DeviceType.LIGHT, DeviceSupport.NOT_SUPPORTED)
        mz = info.device_support.get(DeviceType.MULTIZONE, DeviceSupport.NOT_SUPPORTED)
        matrix = info.device_support.get(DeviceType.MATRIX, DeviceSupport.NOT_SUPPORTED)
        print(f"  {info.name:<20} {light.value:<14} {mz.value:<14} {matrix.value:<14}")


async def resolve_device(ip: str | None, serial: str | None) -> Light | None:
    """Find a device by IP or serial number."""
    if ip:
        print(f"Looking up device at {ip}...")
        device = await find_by_ip(ip, timeout=5.0)
    elif serial:
        print(f"Looking up device {serial}...")
        device = await find_by_serial(serial, timeout=5.0)
    else:
        return None

    if device is None:
        print("Device not found.")
        return None

    if not isinstance(device, Light):
        print(f"Device is a {type(device).__name__}, not a Light. Cannot run effects.")
        return None

    return device


async def run_effect(device: Light, effect_name: str, duration: float) -> None:
    """Run a single named effect on a device."""
    registry = get_effect_registry()
    info = registry.get_effect(effect_name)
    if info is None:
        print(f"Unknown effect: '{effect_name}'")
        print("Use --list to see available effects.")
        return

    device_type = classify_device(device)
    support = info.device_support.get(device_type, DeviceSupport.NOT_SUPPORTED)
    if support is DeviceSupport.NOT_SUPPORTED:
        print(
            f"Effect '{effect_name}' is not supported on {device_type.value} devices."
        )
        return

    conductor = Conductor()
    effect = info.effect_class()
    label = device.label or device.serial
    print(f"Running '{effect_name}' on {label} for {duration:.0f}s...")
    await conductor.start(effect, [device])
    await asyncio.sleep(duration)
    await conductor.stop([device])
    print("Stopped. Light restored to original state.")


async def cycle_effects(device: Light, duration: float) -> None:
    """Cycle through all compatible effects on a device."""
    registry = get_effect_registry()
    device_type = classify_device(device)

    compatible = [
        (info, support)
        for info, support in registry.get_effects_for_device_type(device_type)
    ]

    if not compatible:
        print(f"No compatible effects for {device_type.value} devices.")
        return

    print(
        f"Cycling through {len(compatible)} effects on"
        f" {device.label or device.serial} ({device_type.value})"
    )
    print(f"Duration per effect: {duration:.0f}s\n")

    conductor = Conductor()
    for i, (info, support) in enumerate(compatible, 1):
        label = "recommended" if support is DeviceSupport.RECOMMENDED else "compatible"
        print(f"[{i}/{len(compatible)}] {info.name} ({label}): {info.description}")
        effect = info.effect_class()
        await conductor.start(effect, [device])
        await asyncio.sleep(duration)
        await conductor.stop([device])
        print("  Stopped.\n")
        if i < len(compatible):
            await asyncio.sleep(1)

    print("All effects completed! Light restored to original state.")


async def main() -> None:
    """Parse arguments and run the demo."""
    parser = argparse.ArgumentParser(
        description="Demo script for lifx-async effects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--ip", help="Device IP address")
    target.add_argument("--serial", help="Device serial number")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--effect", help="Run a specific effect by name")
    mode.add_argument(
        "--cycle", action="store_true", help="Cycle through all compatible effects"
    )
    mode.add_argument(
        "--list", action="store_true", help="List all available effects and exit"
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Duration per effect in seconds (default: 10)",
    )

    args = parser.parse_args()

    if args.list:
        list_effects()
        return

    if not args.ip and not args.serial:
        parser.error("--ip or --serial is required (use --list to see effects)")

    device = await resolve_device(args.ip, args.serial)
    if device is None:
        sys.exit(1)

    device_type = classify_device(device)
    label = device.label or device.serial
    cls = type(device).__name__
    print(f"Found: {label} ({cls}, {device_type.value})\n")

    if args.effect:
        await run_effect(device, args.effect, args.duration)
    elif args.cycle:
        await cycle_effects(device, args.duration)
    else:
        parser.error("--effect or --cycle is required")


if __name__ == "__main__":
    asyncio.run(main())
