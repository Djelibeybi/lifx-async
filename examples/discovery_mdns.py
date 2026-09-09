#!/usr/bin/env python3
"""Example: Discover LIFX devices using mDNS.

This example demonstrates how to discover LIFX devices on your local network
using mDNS/DNS-SD instead of UDP broadcast. mDNS discovery has several advantages:

- Device type detection without extra queries (from TXT record)
- May work across subnets when the network provides an mDNS reflector
- Reports each device's WiFi or Thread connectivity

With ``fetch_radio_info`` set before entering each device, state initialisation
also fetches the reading for the device's own radio: the WiFi signal on a WiFi
device, or the Thread mesh information on a Thread device, and neither while
the radio is still unknown.

Usage:
    uv run python examples/discovery_mdns.py
"""

from __future__ import annotations

import asyncio

import lifx


def describe_radio(device: lifx.Device) -> str:
    """Describe the radio reading state initialisation collected, if any."""
    state = device.state
    if state is None:
        return "state not initialised"
    if state.thread_info is not None:
        info = state.thread_info
        return (
            f"{info.rssi} {info.rssi_unit} ({info.role.name} on {info.network_name},"
            f" next hop 0x{info.next_hop:04x})"
        )
    if state.wifi_info.rssi is not None:
        return f"{state.wifi_info.rssi} {state.wifi_info.rssi_unit}"
    # The radio was unknown when the batch ran, or the device did not answer.
    return "no reading"


async def discover_with_mdns() -> None:
    """Discover devices using mDNS and print their info."""
    print("Discovering LIFX devices via mDNS...")
    print("-" * 60)

    device_count = 0
    async for device in lifx.discover_mdns():
        device_count += 1
        # Set before `async with`: entering the device runs state
        # initialisation, which is where the radio query joins the batch.
        device.fetch_radio_info = True
        async with device:
            # get_color() returns color, power, and label in a single request
            color, power, label = await device.get_color()
            power_str = "ON" if power > 0 else "OFF"

            print(f"\nDevice #{device_count}")
            print(f"  Type:   {type(device).__name__}")
            print(f"  Label:  {label}")
            print(f"  Serial: {device.serial}")
            print(f"  IP:     {device.ip}:{device.port}")
            print(f"  Link:   {device.connectivity}")
            print(f"  Signal: {describe_radio(device)}")
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


async def main() -> None:
    """Run supported device-level mDNS discovery."""
    await discover_with_mdns()


if __name__ == "__main__":
    asyncio.run(main())
