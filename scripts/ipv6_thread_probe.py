#!/usr/bin/env python3
"""Hardware probe for the IPv6/Thread mDNS discovery path.

Thread-connected LIFX devices have no IPv4 address and are advertised over
mDNS by a Thread border router on the device's behalf. This script exercises
the library's own mDNS code against real hardware and reports what it sees,
so the three wire-level claims of the IPv6 branch can each be checked
independently:

1. records  AAAA records are parsed, and the address chosen per device is
            visible along with the classification (GUA/ULA/link-local) that
            drove the choice.
2. ports    The same sweep is run twice, once bound to an ephemeral port and
            once bound to 5353 the way the pre-fix transport did. The
            difference between the two device sets is the mDNSResponder
            unicast-stealing bug, measured rather than assumed.
3. connect  Each discovered device is contacted, separating "the wrong
            address was chosen" from "the address was right but the device
            did not answer".
4. control  With --serial, the one named device is driven through a
            set_power and a set_color roundtrip with readback, and its full
            pre-run state is restored afterwards. With --uat-output it writes
            a privacy-sanitised Phase 11 diagnostic record. This schema does
            not replace or feed the immutable Phase 10 merge-gate artefact.
5. stream   With --stream as well, a short bounded Animator frame run is
            delivered to the same device, strictly after the control stage.
            Its result is recorded as an artefact and gates nothing.

Usage:
    uv run scripts/ipv6_thread_probe.py
    uv run scripts/ipv6_thread_probe.py --stage records --timeout 20
    uv run scripts/ipv6_thread_probe.py --stage ports
    uv run scripts/ipv6_thread_probe.py --serial d073d5123456 \\
        --device-alias thread-target-alpha \\
        --uat-output .planning/phases/11-mdns-hardening/11-UAT-RESULTS.json

The control stage mutates a real device, so it is opt-in per device: without
--serial nothing is written to any light and the control stage is recorded as
not_run. A fleet-wide write is exactly what this probe must never do.

This is a diagnostic and deliberately reaches into the private record cache
of ``lifx.network.discovery.mdns.discovery``: the point is to show what the
library parsed, not to re-implement the parsing (``scripts/mdns_probe.py``
already does that, and so tests nothing about the library).
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import re
import shutil
import socket
import struct
import subprocess  # nosec B404
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from lifx.animation.animator import Animator
from lifx.color import HSBK
from lifx.const import (
    IDLE_TIMEOUT_MULTIPLIER,
    LIFX_MDNS_SERVICE,
    MAX_RESPONSE_TIME,
    MDNS_ADDRESS,
    MDNS_PORT,
)
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixEffect, MatrixLight
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight
from lifx.exceptions import LifxError, LifxNetworkError, LifxTimeoutError
from lifx.network.discovery.mdns import discovery as mdns_discovery
from lifx.network.discovery.mdns.discovery import (
    _create_device_from_record,
    _discover_lifx_services,
    _LifxRecordCache,
)
from lifx.network.discovery.mdns.dns import (
    DNS_TYPE_A,
    DNS_TYPE_AAAA,
    DNS_TYPE_SRV,
    DNS_TYPE_TXT,
    SrvData,
    TxtData,
    build_address_query,
    build_ptr_query,
    parse_dns_response,
)
from lifx.network.discovery.mdns.transport import MdnsTransport
from lifx.network.discovery.mdns.types import _LifxServiceRecord
from lifx.network.transport import _UdpProtocol
from lifx.network.utils import IdleDeadline
from lifx.products import get_product
from lifx.protocol.protocol_types import FirmwareEffect

_ULA_NETWORK = ipaddress.ip_network("fc00::/7")

RULE = "=" * 72
THIN = "-" * 72

# The three values the UAT record's stages map may hold. "not_run" is a
# first-class outcome: an honest "we never got there" is always available, so
# there is never a reason to record a pass that did not happen.
STAGE_PASSED = "passed"
STAGE_FAILED = "failed"
STAGE_NOT_RUN = "not_run"

UAT_SCHEMA_VERSION = 2
UAT_KIND = "thread-hardware-uat-sanitised"
UAT_PHASE = "11"

_DEVICE_ALIAS_PATTERN = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
_LIBRARY_HEAD_PATTERN = re.compile(r"[0-9a-f]{7,64}\Z")
_UAT_RECORD_KEYS = {
    "schema_version",
    "kind",
    "phase",
    "device_alias",
    "network",
    "timestamp",
    "library_head",
    "stages",
    "restored",
}
_UAT_NETWORK_KEYS = {"address_family", "connectivity"}
_UAT_STAGE_KEYS = {"connect", "control", "streaming"}
_UAT_STAGE_VALUES = {STAGE_PASSED, STAGE_FAILED, STAGE_NOT_RUN}

_POWER_ON = 65535
_POWER_OFF = 0

# The control stage derives its write target from the pre-write reading rather
# than hardcoding one, so the readback assertion cannot pass on colour the
# device already held.
_CONTROL_HUE_SHIFT = 137.0
_HUE_TOLERANCE_DEGREES = 1.0

# Real firmware ramps. A LIFX device reports the instantaneous driver level
# while it brings the LEDs up, even when the write asks for a zero-length
# transition, so a readback taken one round trip after the write can catch the
# ramp instead of the result. Measured against a Thread Tube on 2026-08-28:
# 4980 at t+0.098s, 65535 at t+0.525s. A single immediate sample therefore
# asserts that the device finished ramping inside one round trip, which is a
# latency claim rather than a control claim. The control stage polls for the
# settled value instead. This bounds how long the assertion waits; it does not
# change what the assertion requires.
_SETTLE_TIMEOUT_SECONDS = 2.0
_SETTLE_POLL_SECONDS = 0.1

# The streaming run is bounded so it cannot become an endurance test: a few
# seconds at a modest frame rate is enough to record whether frames flow.
_STREAM_SECONDS = 3.0
_STREAM_FPS = 10.0


def classify_address(addr: str) -> str:
    """Classify an address the way _pick_address's preference order sees it."""
    try:
        parsed = ipaddress.ip_address(addr)
    except ValueError:
        return "invalid"
    if parsed.version == 4:
        return "IPv4"
    if parsed.is_link_local:
        return "link-local"
    if parsed in _ULA_NETWORK:
        return "ULA"
    if parsed.is_global:
        return "GUA"
    return "IPv6-other"


def is_reachable_choice(addr: str) -> bool:
    """Whether an address can be connected to without a zone/scope ID."""
    classification = classify_address(addr)
    if classification != "link-local":
        return classification != "invalid"
    return "%" in addr


@dataclass
class SweepResult:
    """Everything one mDNS sweep observed."""

    cache: _LifxRecordCache
    local_port: int
    packet_count: int = 0
    lifx_packet_count: int = 0
    malformed_count: int = 0
    sources: set[str] = field(default_factory=set)
    resolved: list[_LifxServiceRecord] = field(default_factory=list)


class _LegacyMdnsTransport(MdnsTransport):
    """The pre-fix transport: SO_REUSEPORT, bind 5353, join the group.

    Reproduced verbatim from the transport this branch replaced, so the port
    comparison isolates exactly one variable.
    """

    bound_port: int = 0

    async def open(self) -> None:
        """Open a socket bound to 5353 the way the pre-fix code did."""
        if self._protocol is not None:
            return

        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass

        try:
            sock.bind(("", MDNS_PORT))
        except OSError:
            sock.bind(("", 0))

        type(self).bound_port = sock.getsockname()[1]

        mreq = struct.pack("4sl", socket.inet_aton(MDNS_ADDRESS), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        sock.setblocking(False)
        self._socket = sock

        protocol = _UdpProtocol()
        self._protocol = protocol
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: protocol, sock=sock
        )


async def sweep(
    timeout: float, transport: MdnsTransport, verbose: bool = False
) -> SweepResult:
    """Run one full mDNS discovery sweep, keeping every record it parsed."""
    cache = _LifxRecordCache()
    queried_targets: set[str] = set()
    query_attempts: dict[str, int] = {}
    start = time.monotonic()
    idle_timeout = MAX_RESPONSE_TIME * IDLE_TIMEOUT_MULTIPLIER

    async with transport:
        sock = transport._socket  # noqa: SLF001 - diagnostic needs the real port
        local_port = sock.getsockname()[1] if sock is not None else 0
        result = SweepResult(cache=cache, local_port=local_port)

        await transport.send(build_ptr_query(LIFX_MDNS_SERVICE))
        retransmit_at = [start + 1.0, start + 3.0]
        deadline = IdleDeadline(timeout, idle_timeout)

        while True:
            now = time.monotonic()
            cache.expire(now)

            # Match production clock ordering: elapsed goodbyes disappear
            # before one due PTR retransmission is processed.
            if retransmit_at and now >= retransmit_at[0]:
                retransmit_at.pop(0)
                await transport.send(build_ptr_query(LIFX_MDNS_SERVICE))

            if deadline.idle_expired or deadline.overall_expired:
                break

            remaining = deadline.remaining()
            if remaining <= 0:
                break
            if retransmit_at:
                remaining = min(remaining, retransmit_at[0] - now)
            expiry_delay = cache.next_expiry_delay(now)
            if expiry_delay is not None:
                remaining = min(remaining, expiry_delay)

            # A due clock cause is handled at the top of the loop. Do not
            # invent a positive wait that could reorder simultaneous causes.
            if remaining <= 0:
                continue

            try:
                data, addr = await transport.receive(timeout=remaining)
            except LifxTimeoutError:
                if (
                    retransmit_at
                    or cache.next_expiry_delay(time.monotonic()) is not None
                ):
                    continue
                break

            try:
                response = parse_dns_response(data)
            except (ValueError, IndexError, struct.error) as exc:
                result.malformed_count += 1
                if verbose:
                    print(f"    [malformed packet from {addr[0]}: {exc}]")
                continue

            if not response.header.is_response:
                continue

            result.packet_count += 1
            result.sources.add(addr[0])

            if cache.add_packet(response.records, addr[0]):
                result.lifx_packet_count += 1
                # Reset after parsing and cache work resumes so the quiet
                # window excludes consumer work and measures network silence.
                deadline.mark_response()

                for target in cache.pending_targets():
                    target_key = target.casefold()
                    if target_key in queried_targets:
                        continue

                    attempts = query_attempts.get(target_key)
                    if attempts is None:
                        if len(query_attempts) >= 64:
                            continue
                        attempts = 0
                    if attempts >= 2:
                        continue

                    query_attempts[target_key] = attempts + 1
                    if verbose:
                        print(f"    [follow-up A/AAAA query for {target}]")
                    try:
                        await transport.send(build_address_query(target))
                    except LifxNetworkError:
                        continue
                    queried_targets.add(target_key)

    cache.expire(time.monotonic())
    result.resolved = cache.resolve()
    return result


def _instance_view(cache: _LifxRecordCache) -> list[tuple[str, dict[str, object]]]:
    """Pull the per-instance record set out of the cache for reporting."""
    fallback: dict[str, str] = cache._fallback_ip_by_instance  # noqa: SLF001

    views: list[tuple[str, dict[str, object]]] = []
    for instance in sorted(cache.owners_for(DNS_TYPE_TXT)):
        txt_records = cache.records_for(instance, DNS_TYPE_TXT)
        txt_values = [
            record.parsed_data
            for record in txt_records
            if isinstance(record.parsed_data, TxtData)
        ]
        srv_values = [
            record.parsed_data
            for record in cache.records_for(instance, DNS_TYPE_SRV)
            if isinstance(record.parsed_data, SrvData)
        ]
        txt = txt_values[0] if txt_values else None
        srv = srv_values[0] if srv_values else None
        target = srv.target.lower() if srv is not None else None
        addresses = cache.addresses_for(target) if target else frozenset()
        a_values = [
            record.parsed_data
            for record in cache.records_for(target or "", DNS_TYPE_A)
            if isinstance(record.parsed_data, str)
        ]
        aaaa_values = [
            record.parsed_data
            for record in cache.records_for(target or "", DNS_TYPE_AAAA)
            if isinstance(record.parsed_data, str)
        ]
        views.append(
            (
                instance,
                {
                    "txt": txt,
                    "txt_count": len(txt_values),
                    "srv": srv,
                    "srv_count": len(srv_values),
                    "target": target,
                    "a": a_values[0] if a_values else None,
                    "aaaa": aaaa_values,
                    "addresses": addresses,
                    "chosen": cache.selected_address_for(target) if target else None,
                    "fallback": fallback.get(instance),
                },
            )
        )
    return views


def report_records(result: SweepResult) -> None:
    """Print the per-instance record dump with address selection reasoning."""
    print(RULE)
    print("STAGE 1: mDNS records and address selection")
    print(RULE)
    print(f"Queried from local port {result.local_port} (legacy unicast)")
    print(
        f"Packets: {result.packet_count} received, "
        f"{result.lifx_packet_count} LIFX-bearing, "
        f"{result.malformed_count} malformed"
    )
    print(f"Responding sources: {', '.join(sorted(result.sources)) or 'none'}")

    views = _instance_view(result.cache)
    if not views:
        print("\nNo LIFX service instances seen. Nothing to report.")
        return

    print(f"\n{len(views)} service instance(s):")

    v4_count = 0
    aaaa_count = 0
    linklocal_chosen = 0

    for instance, view in views:
        txt = view["txt"]
        srv = view["srv"]
        target = view["target"]
        a_ip = view["a"]
        aaaa_ips = view["aaaa"]
        assert isinstance(txt, TxtData)
        assert isinstance(aaaa_ips, list)

        serial = txt.pairs.get("id", "?")
        product_id = txt.pairs.get("p", "?")
        firmware = txt.pairs.get("fw", "?")
        try:
            product_name = get_product(int(product_id)).name
        except (ValueError, KeyError):
            product_name = "unknown product"

        print(f"\n{THIN}")
        print(f"  instance : {instance}")
        print(f"  serial   : {serial}")
        print(f"  product  : {product_id} ({product_name})")
        print(f"  firmware : {firmware}")

        if isinstance(srv, SrvData):
            print(f"  SRV      : {srv.target}:{srv.port}")
        else:
            print("  SRV      : (none advertised)")

        if a_ip is not None:
            v4_count += 1
            print(f"  A        : {a_ip}  [IPv4]")
        else:
            print("  A        : (none)")

        if aaaa_ips:
            aaaa_count += 1
            print(f"  AAAA     : {len(aaaa_ips)} record(s)")
            for addr in aaaa_ips:
                print(f"             {addr}  [{classify_address(addr)}]")
        else:
            print("  AAAA     : (none)")

        if view["addresses"]:
            chosen = view["chosen"]
        elif isinstance(view["fallback"], str):
            chosen = view["fallback"]
        else:
            chosen = None

        if chosen is None:
            if target is not None:
                print("  CHOSEN   : none - pending address records for SRV target")
            else:
                print("  CHOSEN   : none - no SRV record and no fallback source")
            continue
        assert isinstance(chosen, str)

        classification = classify_address(chosen)
        if isinstance(a_ip, str) and chosen == a_ip:
            reason = "A record present; IPv4 preferred over IPv6"
        elif chosen == view["fallback"]:
            reason = "no SRV record; fell back to the response packet's source"
        elif classification == "link-local":
            reason = "ONLY link-local AAAA records available"
            linklocal_chosen += 1
        else:
            reason = f"routable {classification} preferred over link-local"

        print(f"  CHOSEN   : {chosen}  [{classification}]")
        print(f"  WHY      : {reason}")
        if not is_reachable_choice(chosen):
            print("  WARNING  : link-local without a zone ID is not connectable")

    print(f"\n{THIN}")
    print("Summary:")
    print(f"  instances with an A record    : {v4_count}")
    print(f"  instances with AAAA record(s) : {aaaa_count}")
    print(f"  resolved to a usable record   : {len(result.resolved)}")
    print(f"  chose a bare link-local addr  : {linklocal_chosen}")
    pending = result.cache.pending_targets()
    if pending:
        print(f"  still-unresolved SRV targets  : {len(pending)}")
        for target in pending:
            print(f"      {target}")


async def stage_records(timeout: float, verbose: bool) -> SweepResult:
    """Run the record-level sweep and report it."""
    result = await sweep(timeout, MdnsTransport(), verbose=verbose)
    report_records(result)
    return result


async def stage_ports(timeout: float) -> None:
    """Compare an ephemeral-port sweep against a 5353-bound one."""
    print(f"\n{RULE}")
    print("STAGE 2: ephemeral port vs port 5353")
    print(RULE)
    print("Running the library's own discovery twice, changing only the")
    print("local port the query is sent from.\n")

    print("  [A] ephemeral port (current behaviour)...")
    ephemeral = {r.serial: r for r in await _collect(timeout)}
    print(f"      found {len(ephemeral)} device(s)")

    print("  [B] port 5353 with SO_REUSEPORT (pre-fix behaviour)...")
    original = mdns_discovery.MdnsTransport
    mdns_discovery.MdnsTransport = _LegacyMdnsTransport  # type: ignore[misc]
    try:
        legacy = {r.serial: r for r in await _collect(timeout)}
    finally:
        mdns_discovery.MdnsTransport = original  # type: ignore[misc]
    print(f"      found {len(legacy)} device(s)")

    if _LegacyMdnsTransport.bound_port != MDNS_PORT:
        print(
            f"\n  NOTE: could not bind 5353 (got {_LegacyMdnsTransport.bound_port}); "
            "this run did not reproduce the pre-fix condition."
        )

    only_ephemeral = sorted(set(ephemeral) - set(legacy))
    only_legacy = sorted(set(legacy) - set(ephemeral))

    print(f"\n{THIN}")
    print(f"  both        : {len(set(ephemeral) & set(legacy))}")
    print(f"  ephemeral   : {len(only_ephemeral)} found only when bound ephemeral")
    for serial in only_ephemeral:
        print(f"      {serial}  {ephemeral[serial].ip}")
    print(f"  5353        : {len(only_legacy)} found only when bound to 5353")
    for serial in only_legacy:
        print(f"      {serial}  {legacy[serial].ip}")

    print()
    if only_ephemeral and not only_legacy:
        print("  VERDICT: binding 5353 loses devices. The fix is doing real work.")
    elif not only_ephemeral and not only_legacy:
        print("  VERDICT: no difference on this network. Either no mDNS daemon is")
        print("           holding 5353, or responses arrived by multicast anyway.")
    else:
        print("  VERDICT: mixed result - re-run to check it is not just packet loss.")


async def _collect(timeout: float) -> list[_LifxServiceRecord]:
    """Collect service records through the internal discovery generator."""
    records: list[_LifxServiceRecord] = []
    async for record in _discover_lifx_services(timeout=timeout):
        records.append(record)
    return records


async def stage_connect(records: list[_LifxServiceRecord]) -> None:
    """Contact each discovered device and classify any failure."""
    print(f"\n{RULE}")
    print("STAGE 3: connecting to discovered devices")
    print(RULE)

    if not records:
        print("No devices discovered, nothing to connect to.")
        return

    unreachable_choice = 0
    succeeded = 0
    failed = 0

    for record in sorted(records, key=lambda r: r.serial):
        classification = classify_address(record.ip)
        label = f"  {record.serial}  {record.ip}  [{classification}]"

        if not is_reachable_choice(record.ip):
            unreachable_choice += 1
            print(f"{label}\n      SKIP: address selection problem, not a device fault")
            print("      link-local address has no zone ID, so it cannot be routed")
            continue

        device = _create_device_from_record(record)
        if device is None:
            print(f"{label}\n      SKIP: relay/button-only product")
            continue

        try:
            async with device:
                color, power, name = await device.get_color()
        except LifxTimeoutError:
            failed += 1
            print(f"{label}\n      FAIL: timed out - address looks valid, no answer")
            continue
        except LifxError as exc:
            failed += 1
            print(f"{label}\n      FAIL: {type(exc).__name__}: {exc}")
            continue
        except OSError as exc:
            failed += 1
            print(f"{label}\n      FAIL: socket error: {exc}")
            continue

        succeeded += 1
        state = "on" if power > 0 else "off"
        print(f"{label}\n      OK: {name!r} ({type(device).__name__}) {state}")
        print(
            f"      H={color.hue:.0f} S={color.saturation:.0%} "
            f"B={color.brightness:.0%} K={color.kelvin}"
        )

    print(f"\n{THIN}")
    print(f"  connected            : {succeeded}")
    print(f"  failed to answer     : {failed}")
    print(f"  bad address chosen   : {unreachable_choice}")
    if unreachable_choice:
        print("\n  A non-zero 'bad address chosen' means _pick_address() had only")
        print("  link-local AAAA records to work with. That is an address-selection")
        print("  gap, not a connectivity failure.")


@dataclass(frozen=True)
class TargetNotFound:
    """Why a --serial value could not be turned into a controllable device.

    Returned by `_select_target()` instead of raising, so a mistyped serial or
    an absent device is recorded as a failed connect stage rather than ending
    the run in a traceback.
    """

    serial: str
    reason: str


@dataclass
class CapturedState:
    """A device's pre-run state, in the shape that device actually holds.

    A `MatrixLight` holds a per-pixel image and possibly a running firmware
    effect; `get_color()` returns a single triple and cannot represent either.
    Capturing the wrong shape means the probe cannot put the device back.
    """

    kind: str
    power: int
    tiles: list[list[HSBK]] | None = None
    effect: MatrixEffect | None = None
    zones: list[HSBK] | None = None
    multizone_effect: MultiZoneEffect | None = None
    color: HSBK | None = None


@dataclass
class TargetOutcome:
    """Per-stage results for the named target.

    Mutated in place by `stage_target()` so that a partially completed run
    still writes an honest record: an interrupt part-way through leaves the
    stages it never reached at "not_run" rather than losing the run entirely.
    """

    connect: str = STAGE_NOT_RUN
    control: str = STAGE_NOT_RUN
    streaming: str = STAGE_NOT_RUN
    restored: bool = True


def _select_target(
    records: list[_LifxServiceRecord], serial: str
) -> Light | TargetNotFound:
    """Resolve a requested serial to exactly one device from the sweep.

    Args:
        records: Everything the mDNS sweep resolved.
        serial: The serial requested on the command line, in any common
            formatting (case-insensitive, colons or hyphens tolerated).

    Returns:
        The device to control, or a TargetNotFound explaining why there is
        none.
    """
    wanted = serial.strip().lower().replace(":", "").replace("-", "")

    matches = [record for record in records if record.serial.lower() == wanted]
    if not matches:
        return TargetNotFound(
            serial=wanted,
            reason=f"no discovered device carries that serial ({len(records)} seen)",
        )

    record = matches[0]
    if not is_reachable_choice(record.ip):
        return TargetNotFound(
            serial=wanted,
            reason=f"chosen address {record.ip} has no zone ID and cannot be routed",
        )

    device = _create_device_from_record(record)
    if device is None:
        return TargetNotFound(
            serial=wanted,
            reason="relay/button-only product, so there is nothing to control",
        )
    return device


async def _capture_device_state(device: Light) -> CapturedState:
    """Read back everything the control and streaming stages will overwrite.

    For a matrix device that means every tile's colours, the power level and
    any running firmware effect. For a plain light it is the `get_color()`
    triple, which carries the power level in the same round trip.

    Args:
        device: The connected target.

    Returns:
        The captured state, naming which shape it holds.
    """
    if isinstance(device, MatrixLight):
        tiles = await device.get_all_tile_colors()
        power = await device.get_power()
        effect = await device.get_effect()
        running = effect if effect.effect_type != FirmwareEffect.OFF else None
        return CapturedState(kind="matrix", power=power, tiles=tiles, effect=running)

    if isinstance(device, MultiZoneLight):
        zones = await device.get_all_color_zones()
        power = await device.get_power()
        effect = await device.get_effect()
        return CapturedState(
            kind="multizone",
            power=power,
            zones=zones,
            multizone_effect=effect,
        )

    color, power, _label = await device.get_color()
    return CapturedState(kind="light", power=power, color=color)


async def _restore_device_state(device: Light, state: CapturedState) -> bool:
    """Put a device back exactly as it was found. Never raises.

    A restore failure is reported loudly and returned as False rather than
    propagated: the caller is already in a `finally` block, and swallowing the
    report would hide a device left mid-run from the operator.

    Args:
        device: The connected target.
        state: What `_capture_device_state()` recorded before the mutation.

    Returns:
        True when the device was fully restored, False otherwise.
    """
    try:
        if isinstance(device, MatrixLight) and state.tiles is not None:
            for index, colors in enumerate(state.tiles):
                await device.set_matrix_colors(tile_index=index, colors=colors)
            await device.set_power(state.power)
            if state.effect is not None:
                await device.set_effect(
                    effect_type=state.effect.effect_type,
                    speed=state.effect.speed / 1000,
                    duration=state.effect.duration,
                    palette=state.effect.palette,
                    sky_type=state.effect.sky_type,
                    cloud_saturation_min=state.effect.cloud_saturation_min,
                    cloud_saturation_max=state.effect.cloud_saturation_max,
                )
        elif isinstance(device, MultiZoneLight) and state.zones is not None:
            await device.set_all_color_zones(state.zones)
            if state.multizone_effect is not None:
                await device.set_effect(state.multizone_effect)
            await device.set_power(state.power)
        else:
            if state.color is not None:
                await device.set_color(state.color)
            await device.set_power(state.power)
    except Exception as exc:
        print(f"\n  WARNING: could not restore {device.serial} at {device.ip}")
        print(f"           {type(exc).__name__}: {exc}")
        print("           The device has been left mid-run. Put it right by hand.")
        return False
    return True


def _stage_result(outcome: bool | BaseException | None) -> str:
    """Map one observed stage outcome onto the record's three values.

    Args:
        outcome: True or False for a stage that ran, the exception for a stage
            that raised, or None for a stage that was never attempted.

    Returns:
        One of "passed", "failed" or "not_run".
    """
    if outcome is None:
        return STAGE_NOT_RUN
    if isinstance(outcome, BaseException):
        return STAGE_FAILED
    return STAGE_PASSED if outcome else STAGE_FAILED


def _build_uat_record(
    device_alias: str,
    address_family: str | None,
    connectivity: str | None,
    outcome: TargetOutcome,
) -> dict[str, object]:
    """Assemble the machine-checkable record of what this run observed.

    Args:
        device_alias: Stable operator-managed alias with no embedded identifier.
        address_family: Non-identifying address family used for the connection.
        connectivity: Public WiFi/Thread classification, when known.
        outcome: The per-stage results, exactly as observed.

    Returns:
        The record, ready to be written as JSON.
    """
    git_path = shutil.which("git")
    if git_path is None:
        library_head = None
    else:
        try:
            completed = subprocess.run(  # nosec B603
                [git_path, "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            library_head = None
        else:
            library_head = completed.stdout.strip() or None

    return {
        "schema_version": UAT_SCHEMA_VERSION,
        "kind": UAT_KIND,
        "phase": UAT_PHASE,
        "device_alias": device_alias,
        "network": {
            "address_family": address_family,
            "connectivity": connectivity,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "library_head": library_head,
        "stages": {
            "connect": outcome.connect,
            "control": outcome.control,
            "streaming": outcome.streaming,
        },
        "restored": outcome.restored,
    }


def _write_uat_record(
    record: dict[str, object], path: Path, *, raw_serial: str
) -> None:
    """Write the UAT record to disk as JSON.

    Args:
        record: The record from `_build_uat_record()`.
        path: Where to write it. Parent directories are created.
        raw_serial: Selected device serial, used only for final leak validation.
    """
    _validate_uat_record(record, raw_serial=raw_serial)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"\nUAT record written to {path}")


def _validate_uat_record(record: dict[str, object], *, raw_serial: str) -> None:
    """Validate the complete privacy-safe Phase 11 evidence contract.

    The raw serial is used transiently to reject a leaking alias. It is never
    added to the record or returned by this consumer.
    """
    forbidden_keys = {"device_serial", "device_ip", "serial", "ip"}

    def contains_forbidden_key(value: object) -> bool:
        if isinstance(value, dict):
            return any(
                key in forbidden_keys or contains_forbidden_key(child)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return any(contains_forbidden_key(child) for child in value)
        return False

    if contains_forbidden_key(record):
        raise ValueError("refusing to write a UAT record containing raw identifiers")

    compact_serial = re.sub(r"[^a-z0-9]", "", raw_serial.casefold())

    def contains_raw_serial(value: object) -> bool:
        if isinstance(value, str):
            compact_value = re.sub(r"[^a-z0-9]", "", value.casefold())
            return bool(compact_serial and compact_serial in compact_value)
        if isinstance(value, dict):
            return any(
                contains_raw_serial(key) or contains_raw_serial(child)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return any(contains_raw_serial(child) for child in value)
        return False

    if contains_raw_serial(record):
        raise ValueError("UAT record contains the raw device serial")

    if set(record) != _UAT_RECORD_KEYS:
        raise ValueError("invalid Phase 11 UAT record fields")
    if record["schema_version"] != UAT_SCHEMA_VERSION:
        raise ValueError("invalid Phase 11 UAT schema version")
    if record["kind"] != UAT_KIND or record["phase"] != UAT_PHASE:
        raise ValueError("invalid Phase 11 UAT contract identity")

    alias = record.get("device_alias")
    if not isinstance(alias, str):
        raise ValueError("refusing to write a UAT record without a valid device alias")
    _validate_device_alias(alias, raw_serial)

    network = record["network"]
    if not isinstance(network, dict) or set(network) != _UAT_NETWORK_KEYS:
        raise ValueError("invalid Phase 11 UAT network properties")
    if network["address_family"] not in {None, "ipv4", "ipv6"}:
        raise ValueError("invalid Phase 11 UAT address family")
    if network["connectivity"] not in {None, "wifi", "thread"}:
        raise ValueError("invalid Phase 11 UAT connectivity")

    timestamp = record["timestamp"]
    if not isinstance(timestamp, str):
        raise ValueError("invalid Phase 11 UAT timestamp")
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise ValueError("invalid Phase 11 UAT timestamp") from exc
    if parsed_timestamp.tzinfo is None:
        raise ValueError("invalid Phase 11 UAT timestamp")

    library_head = record["library_head"]
    if library_head is not None and (
        not isinstance(library_head, str)
        or _LIBRARY_HEAD_PATTERN.fullmatch(library_head) is None
    ):
        raise ValueError("invalid Phase 11 UAT library head")

    stages = record["stages"]
    if not isinstance(stages, dict) or set(stages) != _UAT_STAGE_KEYS:
        raise ValueError("invalid Phase 11 UAT stages")
    if any(value not in _UAT_STAGE_VALUES for value in stages.values()):
        raise ValueError("invalid Phase 11 UAT stage result")

    if not isinstance(record["restored"], bool):
        raise ValueError("invalid Phase 11 UAT restoration result")


def _validate_device_alias(alias: str, raw_serial: str) -> str:
    """Return a stable evidence alias that cannot repeat the raw target ID."""
    cleaned = alias.strip()
    if not cleaned:
        raise ValueError("--device-alias must not be empty")

    if _DEVICE_ALIAS_PATTERN.fullmatch(cleaned) is None:
        raise ValueError(
            "--device-alias must start with a lowercase letter and contain only "
            "lowercase letters, digits, and hyphens (maximum 64 characters)"
        )

    compact_alias = re.sub(r"[^a-z0-9]", "", cleaned.casefold())
    compact_serial = re.sub(r"[^a-z0-9]", "", raw_serial.strip().casefold())
    if compact_serial and compact_serial in compact_alias:
        raise ValueError("--device-alias must not contain the raw device serial")

    return cleaned


def _address_family(address: str) -> str | None:
    """Reduce a live address to its non-identifying protocol family."""
    try:
        version = ipaddress.ip_address(address).version
    except ValueError:
        return None
    return f"ipv{version}"


def _hue_delta(first: float, second: float) -> float:
    """Smallest absolute difference between two hues, in degrees."""
    delta = abs(first - second) % 360.0
    return min(delta, 360.0 - delta)


_T = TypeVar("_T")


async def _settle(
    read: Callable[[], Awaitable[_T]],
    accept: Callable[[_T], bool],
    timeout: float,
    interval: float,
) -> tuple[bool, _T]:
    """Poll a device reading until it settles on a value `accept` allows.

    Exists because firmware ramps: see the `_SETTLE_TIMEOUT_SECONDS` comment.
    Reads once immediately, so a device that already answers correctly costs
    nothing extra, and only then starts waiting.

    Args:
        read: Coroutine function returning the current reading.
        accept: Predicate the reading has to satisfy. Never relaxed by this
            helper, which decides only how long to keep asking.
        timeout: Longest total wait, in seconds.
        interval: Delay between polls, in seconds.

    Returns:
        `(True, value)` for the first accepted reading, or `(False, last)`
        where `last` is the final reading taken before the deadline. The
        caller reports that value, so a genuine failure names what the device
        actually said instead of collapsing into "timed out".
    """
    deadline = time.monotonic() + timeout
    value = await read()
    while not accept(value):
        if time.monotonic() >= deadline:
            return False, value
        await asyncio.sleep(interval)
        value = await read()
    return True, value


def _exit_code(outcome: TargetOutcome) -> int:
    """Process exit status, from the gating stages only.

    Streaming is deliberately absent: SPEC Requirement 9 records the streaming
    run as an artefact and does not let it gate the merge.
    """
    if not outcome.restored:
        return 1
    if STAGE_FAILED in (outcome.connect, outcome.control):
        return 1
    return 0


async def run_control_stage(device: Light) -> bool:
    """Drive set_power and set_color with readback against one device.

    Both writes derive their target from a pre-write reading and both
    readbacks are polled through `_settle`, because real firmware ramps and a
    single immediate sample times the ramp rather than testing the write. Both
    assertions still demand the full requested value.

    Args:
        device: The connected target, already captured.

    Returns:
        True when every operation read back as requested.
    """
    ok = True
    timeout, interval = _SETTLE_TIMEOUT_SECONDS, _SETTLE_POLL_SECONDS

    captured_power = await device.get_power()
    baseline = captured_power
    if captured_power == _POWER_ON:
        # Turning an already-on light on again would prove nothing: the
        # readback would match a level the device already held, which is the
        # vacuous assertion this phase has been bitten by twice. Drive it off
        # first so the on-write below is an observable transition. The restore
        # puts the captured level back regardless of which way this went.
        await device.set_power(False)
        went_off, baseline = await _settle(
            device.get_power, lambda level: level == _POWER_OFF, timeout, interval
        )
        if not went_off:
            ok = False
            print(
                f"      FAIL: set_power(off) never reached {_POWER_OFF} within "
                f"{timeout:.0f}s, last read {baseline}"
            )

    await device.set_power(True)
    powered, power_after = await _settle(
        device.get_power, lambda level: level == _POWER_ON, timeout, interval
    )
    if not powered:
        ok = False
        print(
            f"      FAIL: set_power(on) never reached {_POWER_ON} within "
            f"{timeout:.0f}s, last read {power_after}"
        )
    elif power_after == baseline:
        ok = False
        print(
            f"      FAIL: set_power(on) read back as {power_after}, which the "
            "device already held, so the write proved nothing"
        )
    else:
        print(f"      OK: set_power(on) moved power {baseline} -> {power_after}")

    before, _power, _label = await device.get_color()
    target = HSBK(
        hue=(before.hue + _CONTROL_HUE_SHIFT) % 360.0,
        saturation=1.0,
        brightness=0.5,
        kelvin=before.kelvin,
    )
    await device.set_color(target)

    async def _read_hue() -> HSBK:
        colour, _p, _l = await device.get_color()
        return colour

    # Polled for the same reason as power. The colour readback won the race on
    # the 2026-08-28 Thread run, but winning once is not evidence that it
    # cannot lose, and the tolerance below is unchanged either way.
    reached, read_back = await _settle(
        _read_hue,
        lambda colour: _hue_delta(colour.hue, target.hue) <= _HUE_TOLERANCE_DEGREES,
        timeout,
        interval,
    )
    changed = _hue_delta(read_back.hue, before.hue) > _HUE_TOLERANCE_DEGREES
    if reached and changed:
        print(
            f"      OK: set_color moved hue {before.hue:.0f} -> "
            f"{read_back.hue:.0f} (asked for {target.hue:.0f})"
        )
    else:
        ok = False
        print(
            f"      FAIL: set_color asked for hue {target.hue:.0f}, read back "
            f"{read_back.hue:.0f} (was {before.hue:.0f})"
        )

    return ok


async def _build_animator(device: Light) -> Animator:
    """Build the Animator a streaming run should drive for this device.

    Split out so the streaming stage can be exercised against a double: the
    real factories all query the device, which needs hardware.
    """
    if isinstance(device, MatrixLight):
        return await Animator.for_matrix(device)
    if isinstance(device, MultiZoneLight):
        return await Animator.for_multizone(device)
    return Animator.for_light(device)


async def run_streaming_stage(device: Light) -> bool:
    """Deliver a short bounded run of animation frames to one device.

    Recorded as an artefact only. Thread frame-rate ceilings are Phase 14's
    measurement, so this reports the numbers it observed and draws no tuning
    conclusion from them.

    Runs strictly after the control stage, never alongside it: the Animator
    saturates a device's radio and would starve any concurrent query.

    Args:
        device: The connected target, already captured.

    Returns:
        True when at least one frame's packets reached the socket.
    """
    animator = await _build_animator(device)
    frames = max(1, round(_STREAM_SECONDS * _STREAM_FPS))
    interval = 1.0 / _STREAM_FPS
    packets_sent = 0
    gated_frames = 0

    try:
        for index in range(frames):
            hue = round(index * 65535 / frames)
            frame = [(hue, 65535, 30000, 3500)] * animator.pixel_count
            stats = animator.send_frame(frame)
            if stats.gated:
                gated_frames += 1
            else:
                packets_sent += stats.packets_sent
            await asyncio.sleep(interval)
    finally:
        animator.close()

    print(
        f"      streaming: {frames} frame(s) attempted at {_STREAM_FPS:.0f} fps, "
        f"{packets_sent} packet(s) sent, {gated_frames} frame(s) gated"
    )
    return packets_sent > 0


async def stage_target(
    device: Light, outcome: TargetOutcome, *, stream: bool = False
) -> None:
    """Run the control UAT against one named device, restoring it afterwards.

    Args:
        device: The target resolved from --serial.
        outcome: Mutated in place with the per-stage results.
        stream: Whether to run the optional streaming stage afterwards.
    """
    print(f"\n{RULE}")
    print("STAGE 4: control UAT against the named target")
    print(RULE)
    print(f"  {device.serial}  {device.ip}  [{classify_address(device.ip)}]")

    try:
        async with device:
            try:
                captured = await _capture_device_state(device)
            except Exception as exc:
                outcome.connect = _stage_result(exc)
                print(
                    "      FAIL: could not capture the pre-run state: "
                    f"{type(exc).__name__}: {exc}"
                )
                return

            outcome.connect = STAGE_PASSED
            print(
                f"      OK: connected, captured {captured.kind} state from "
                f"{type(device).__name__}"
            )

            try:
                try:
                    control_ok = await run_control_stage(device)
                except Exception as exc:
                    outcome.control = _stage_result(exc)
                    print(
                        f"      FAIL: control stage raised {type(exc).__name__}: {exc}"
                    )
                else:
                    outcome.control = _stage_result(control_ok)

                if stream:
                    try:
                        stream_ok = await run_streaming_stage(device)
                    except Exception as exc:
                        outcome.streaming = _stage_result(exc)
                        print(
                            "      FAIL: streaming stage raised "
                            f"{type(exc).__name__}: {exc} (recorded, does not gate)"
                        )
                    else:
                        outcome.streaming = _stage_result(stream_ok)
            finally:
                outcome.restored = await _restore_device_state(device, captured)
    except Exception as exc:
        if outcome.connect == STAGE_NOT_RUN:
            outcome.connect = _stage_result(exc)
        print(f"      FAIL: {type(exc).__name__}: {exc}")


async def main_async(args: argparse.Namespace) -> int:
    """Run the requested stages."""
    records: list[_LifxServiceRecord] = []
    outcome = TargetOutcome()
    address_family: str | None = None
    connectivity: str | None = None

    try:
        if args.stage in ("records", "all"):
            result = await stage_records(args.timeout, args.verbose)
            records = result.resolved

        if args.stage in ("ports", "all"):
            await stage_ports(args.timeout)

        if args.stage in ("connect", "all"):
            if not records:
                records = await _collect(args.timeout)

            if args.serial is None:
                await stage_connect(records)
            else:
                target = _select_target(records, args.serial)
                if isinstance(target, TargetNotFound):
                    print(f"\n{RULE}")
                    print("STAGE 4: control UAT against the named target")
                    print(RULE)
                    print(f"  {target.serial}\n      FAIL: {target.reason}")
                    outcome.connect = STAGE_FAILED
                else:
                    address_family = _address_family(target.ip)
                    connectivity = target.connectivity
                    await stage_target(target, outcome, stream=args.stream)
    finally:
        if args.uat_output is not None:
            _write_uat_record(
                _build_uat_record(
                    args.device_alias,
                    address_family,
                    connectivity,
                    outcome,
                ),
                args.uat_output,
                raw_serial=args.serial,
            )

    return _exit_code(outcome)


def main() -> int:
    """Parse arguments and run the probe."""
    parser = argparse.ArgumentParser(
        description="Probe the IPv6/Thread mDNS discovery path against hardware.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Discovery window per sweep, in seconds (default: 10.0)",
    )
    parser.add_argument(
        "--stage",
        choices=("records", "ports", "connect", "all"),
        default="all",
        help="Which stage to run (default: all)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print follow-up queries and malformed packets as they happen",
    )
    parser.add_argument(
        "--serial",
        default=None,
        metavar="SERIAL",
        help=(
            "Serial of the single device to run the control UAT against, as a "
            "12-digit hex string. Without it nothing is written to any light "
            "and the control stage is recorded as not_run."
        ),
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help=(
            "Optional: also deliver a short Animator frame run to the --serial "
            "target. Recorded in the UAT record as an artefact and never gates "
            "the exit code, because Thread frame-rate ceilings are measured in "
            "a later phase."
        ),
    )
    parser.add_argument(
        "--device-alias",
        default=None,
        metavar="ALIAS",
        help=(
            "Stable operator-managed alias or pseudonym for sanitised UAT evidence. "
            "Required with --uat-output; use 1-64 lowercase letters, digits, or "
            "hyphens, starting with a letter. It must not contain the raw serial "
            "or an IP address. The private alias-to-device mapping stays outside "
            "the repository."
        ),
    )
    parser.add_argument(
        "--uat-output",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Write a sanitised Phase 11 schema-v2 diagnostic record to PATH as "
            "JSON. Requires --serial and --device-alias. It does not replace the "
            "Phase 10 merge-gate artefact; raw serials and IP addresses are never "
            "written."
        ),
    )
    args = parser.parse_args()

    if args.uat_output is not None and args.serial is None:
        parser.error("--uat-output requires --serial: the record must name a device")
    if args.uat_output is not None and args.device_alias is None:
        parser.error("--uat-output requires --device-alias for sanitised evidence")
    if args.device_alias is not None:
        if args.serial is None:
            parser.error("--device-alias requires --serial")
        try:
            args.device_alias = _validate_device_alias(args.device_alias, args.serial)
        except ValueError as error:
            parser.error(str(error))

    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
