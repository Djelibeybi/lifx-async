#!/usr/bin/env python3
"""Example: Discover LIFX devices using mDNS.

This example demonstrates how to discover LIFX devices on your local network
using mDNS/DNS-SD instead of UDP broadcast. mDNS discovery has several advantages:

- Single network query (vs 1+N for broadcast discovery)
- Device type detection without extra queries (from TXT record)
- Can work across subnets with an mDNS reflector

Usage:
    uv run python examples/14_mdns_discovery.py
"""

from __future__ import annotations

import asyncio

import lifx


async def discover_with_mdns() -> None:
    """Discover devices using mDNS and print their info."""
    print("Discovering LIFX devices via mDNS...")
    print("-" * 60)

    device_count = 0
    async for device in lifx.discover_mdns(timeout=5.0):
        device_count += 1
        async with device:
            # get_color() returns color, power, and label in a single request
            color, power, label = await device.get_color()
            power_str = "ON" if power > 0 else "OFF"

            print(f"\nDevice #{device_count}")
            print(f"  Type:   {type(device).__name__}")
            print(f"  Label:  {label}")
            print(f"  Serial: {device.serial}")
            print(f"  IP:     {device.ip}:{device.port}")
            print(f"  Power:  {power_str}")
            print(
                f"  Color:  H={color.hue:.0f} S={color.saturation:.0%} "
                f"B={color.brightness:.0%} K={color.kelvin}"
            )

    print("-" * 60)
    if device_count == 0:
        print("No devices found. Make sure LIFX devices are on your network.")
    else:
        print(f"Found {device_count} device(s)")


async def discover_raw_records() -> None:
    """Discover devices using low-level mDNS API (raw service records)."""
    print("\nLow-level mDNS discovery (raw service records):")
    print("-" * 60)

    async for record in lifx.discover_lifx_services(timeout=3.0):
        print(f"  Serial: {record.serial}")
        print(f"  IP: {record.ip}:{record.port}")
        print(f"  Product ID: {record.product_id}")
        print(f"  Firmware: {record.firmware}")
        print()


async def main() -> None:
    """Run both discovery methods."""
    # High-level API - yields device instances (Light, MatrixLight, etc.)
    await discover_with_mdns()

    # Low-level API - yields raw mDNS service records
    await discover_raw_records()


if __name__ == "__main__":
    asyncio.run(main())
