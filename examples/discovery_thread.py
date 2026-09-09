#!/usr/bin/env python3
"""Example: Discover Thread devices and report their mesh information.

A LIFX device on Thread firmware sits behind a Thread border router, so UDP
broadcast never reaches it. mDNS/DNS-SD is the discovery path that finds it,
and its TXT record says which radio the device uses before any connection is
opened.

For each Thread device this example calls ``get_thread_info()`` and prints the
device's routing role, network name, routing locators and the health of its
link to the next hop toward the Thread leader,
including the RSSI approximation LIFX advise (link margin minus 100 dBm).

Usage:
    uv run python examples/discovery_thread.py
"""

from __future__ import annotations

import asyncio

from lifx import (
    Connectivity,
    Device,
    LifxTimeoutError,
    LifxUnsupportedCommandError,
    ThreadInfo,
    discover_mdns,
)


def print_thread_info(device: Device, info: ThreadInfo) -> None:
    """Print one block describing a Thread device and its link health."""
    print(f"\n{device.label or device.serial}")
    print(f"  Serial:        {device.serial}")
    print(f"  IP:            {device.ip}:{device.port}")
    print(f"  Role:          {info.role.name}")
    print(f"  Network:       {info.network_name}")
    print(f"  RLOC:          0x{info.rloc:04x}")
    print(f"  Next hop:      0x{info.next_hop:04x}")
    print(
        f"  Link quality:  in {info.link_quality_in}/3, out {info.link_quality_out}/3"
    )
    print(f"  Link margin:   {info.link_margin_db} dB")
    print(f"  RSSI:          {info.rssi} {info.rssi_unit}")


async def discover_thread_devices() -> None:
    """Discover Thread devices over mDNS and print their mesh information."""
    print("Discovering Thread devices via mDNS...")
    print("-" * 60)

    thread_count = 0
    async for device in discover_mdns():
        # The TXT record reports the radio before a connection is opened, so
        # WiFi devices are skipped without any traffic to them.
        if device.connectivity is not Connectivity.THREAD:
            continue

        try:
            async with device:
                # Entering the device runs state initialisation. The device's
                # own frame address report is now authoritative, so a device
                # the TXT record misreported is caught here.
                if device.connectivity is not Connectivity.THREAD:
                    print(f"\n{device.serial}: reported WiFi once contacted, skipped")
                    continue

                info = await device.get_thread_info()
                thread_count += 1
                print_thread_info(device, info)
        except LifxUnsupportedCommandError as e:
            print(f"\n{device.serial}: {e}")
            continue
        except LifxTimeoutError:
            print(f"\n{device.serial}: no response")
            continue

    print()
    print("-" * 60)
    if thread_count == 0:
        print(
            "No Thread devices found. Thread devices are advertised over mDNS by"
            " their border router, so check that one is on this network."
        )
    else:
        print(f"Found {thread_count} Thread device(s)")


async def main() -> None:
    """Run Thread device discovery."""
    await discover_thread_devices()


if __name__ == "__main__":
    asyncio.run(main())
