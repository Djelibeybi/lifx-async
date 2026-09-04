#!/usr/bin/env python3
"""Progressive discovery migration example.

This is the single executable source for the migration snippets embedded in
`docs/user-guide/discovery.md`. Each region below is included into the guide
with `pymdownx.snippets` (`--8<--`), so the guide and this file can never
drift apart: what the guide shows is exactly what runs here.

Four flows are demonstrated:

1. **Unchanged `discover()`** — existing callers keep working exactly as
   before. It still merges shared UDP broadcast discovery with verified mDNS
   results under one caller deadline.
2. **Explicit `discover_udp()`** — the same UDP broadcast leg `discover()`
   shares, named explicitly for callers who want only that source.
3. **Explicit `discover_mdns()`** — a bounded, legacy-unicast DNS-SD
   alternative. Its absence means the device did not answer that specific
   query, not that the device is offline, so callers who need certainty fall
   back to `discover()`.
4. **Targeted lookup** — skip discovery entirely when the address is already
   known, including a zoned IPv6 link-local literal.

All addresses below use RFC 5737 (`192.0.2.0/24`, `203.0.113.0/24`) and
RFC 3849 (`2001:db8::/32`) documentation ranges. They are not live network
addresses.

Usage:
    uv run python examples/discovery_progressive.py
"""

from __future__ import annotations

import asyncio

import lifx


# --8<-- [start:merged]
async def merged_discovery() -> None:
    """`discover()` is unchanged: existing callers migrate nothing.

    It still yields devices found via UDP broadcast, now merged with
    verified mDNS results under one caller deadline, so more devices can be
    found without any code change.
    """
    async for device in lifx.discover(timeout=5.0):
        async with device:
            color, power, label = await device.get_color()
            print(f"{label}: {type(device).__name__} ({device.connectivity})")


# --8<-- [end:merged]


# --8<-- [start:explicit-udp]
async def explicit_udp_discovery() -> None:
    """`discover_udp()` names the same UDP broadcast leg `discover()` shares.

    Use it when the caller wants only that source, with no mDNS leg at all.
    """
    async for device in lifx.discover_udp(timeout=5.0):
        async with device:
            color, power, label = await device.get_color()
            print(f"{label}: {type(device).__name__} ({device.connectivity})")


# --8<-- [end:explicit-udp]


# --8<-- [start:explicit-mdns]
async def explicit_mdns_discovery() -> None:
    """`discover_mdns()` is an explicit, bounded legacy-unicast alternative.

    An empty result here does not prove the device is offline: it only
    proves that device did not answer this specific DNS-SD query during the
    call. Callers that need a stronger liveness signal fall back to
    `discover()`.
    """
    found = False
    async for device in lifx.discover_mdns(timeout=5.0):
        found = True
        async with device:
            color, power, label = await device.get_color()
            print(f"{label}: {type(device).__name__} ({device.connectivity})")

    if not found:
        print("No mDNS responders in this call; falling back to discover()")
        async for device in lifx.discover(timeout=5.0):
            async with device:
                await device.get_color()


# --8<-- [end:explicit-mdns]


# --8<-- [start:targeted]
async def targeted_lookup() -> None:
    """Skip discovery entirely when the device address is already known.

    `find_by_ip()` accepts IPv4 and IPv6 literals. A link-local IPv6 literal
    must carry a zone ID identifying the network interface, for example
    `"fe80::1%en0"` — a DNS AAAA record cannot carry that ID, which is why
    mDNS alone cannot resolve link-local Thread border-router addresses.
    """
    ipv4_device = await lifx.find_by_ip("203.0.113.10")
    ipv6_device = await lifx.find_by_ip("2001:db8::10")

    for device in (ipv4_device, ipv6_device):
        if device is not None:
            async with device:
                print(f"{device.label}: {device.connectivity}")


# --8<-- [end:targeted]


async def main() -> None:
    """Run each flow in turn. Requires a reachable LIFX device."""
    await merged_discovery()
    await explicit_udp_discovery()
    await explicit_mdns_discovery()
    await targeted_lookup()


if __name__ == "__main__":
    asyncio.run(main())
