#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["rich>=15.0.0", "lifx-async"]
#
# [tool.uv.sources]
# lifx-async = { path = "../", editable = true }
# ///
"""Ground-truth audit of the serial-to-MAC derivation rule.

Enumerates every discoverable LIFX device on the local network and reports,
side by side, the serial number, the MAC address the library *derives* from it
(``Device.get_mac_address()``), and the *real* MAC observed in the OS ARP
table, plus a verdict classifying the relationship. The resulting correlation
dataset (grouped by product and firmware) confirms, refines, or refutes the
``version_major == 3`` off-by-one rule in ``src/lifx/devices/base.py``.

Usage:
    uv run scripts/serial_mac_audit.py [--csv] [--timeout N] [--self-test]

Caveats:
    - Rows cover responders only: devices that never answer the broadcast (or
      fail the follow-up queries) do not appear in the dataset.
    - A single discovery round under-counts (6-round median 48/73 devices in
      Spike 005) — re-running the sweep enlarges the dataset.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import re

# subprocess is used with fixed argv lists only (arp/ip neigh), never a shell.
import subprocess  # nosec B404
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

import lifx
from lifx import Device, LifxError, discover
from lifx.products import get_registry

#: Locked column set — table and CSV output share this order.
CSV_COLUMNS = [
    "serial",
    "derived_mac",
    "real_mac",
    "verdict",
    "product_id",
    "product_name",
    "firmware",
    "ip",
    # Whether the library's derivation matched the independent ARP observation.
    # This is the column the audit exists to fill: a "no" identifies a device
    # whose firmware the get_mac_address() rule gets wrong.
    "rule_ok",
]

#: Rich styles for the verdict column — visually distinct at a glance.
VERDICT_STYLES = {
    "identical": "green",
    "off-by-one": "yellow",
    "off-by-minus-one": "magenta",
    "mismatch": "bold red",
    "unknown": "dim",
}

#: Rendering of the ``rule`` column — does get_mac_address() match reality?
RULE_CELLS = {
    "yes": "[green]✓[/]",
    "no": "[bold red]✗[/]",
    "unknown": "[dim]—[/]",
}

#: Short summary-panel headers. Full verdict names ellipsise to ``off-by-…``
#: for BOTH off-by columns at normal terminal widths, which hides the exact
#: distinction the audit exists to measure. The CSV keeps the full names.
VERDICT_HEADERS = {
    "identical": "same",
    "off-by-one": "+1",
    "off-by-minus-one": "-1",
    "mismatch": "mism",
    "unknown": "unkn",
}

#: ``arp -an`` line format as emitted on macOS, using documentation addresses
#: only: MACs from RFC 7042 ``00:00:5e:00:53:xx``, IPs from the RFC 1918 private ranges.
#:
#: Interface names and the optional ``ifscope`` flag vary from host to host, so
#: nothing here should be read as canonical macOS output -- the parser keys on
#: the ``(ip) at mac`` shape and must not depend on the rest. What the fixture
#: does pin is the four properties under test: unpadded octets, an
#: ``(incomplete)`` entry, and a duplicate IP seen on two interfaces.
ARP_FIXTURE_DARWIN = (
    "? (192.168.1.137) at 0:0:5e:0:53:f8 on en0 [ethernet]\n"
    "? (192.168.1.254) at (incomplete) on en0 [ethernet]\n"
    "? (192.168.1.1) at 00:00:5e:00:53:e on en0 ifscope [ethernet]\n"
    "? (192.168.1.1) at 00:00:5e:00:53:e on en1 [ethernet]\n"
)

#: ``/proc/net/arp`` shape, header row included. Third entry has ``Flags``
#: ``0x0`` (incomplete) and must be skipped.
PROC_NET_ARP_FIXTURE = (
    "IP address       HW type     Flags       HW address            Mask     Device\n"
    "192.168.1.20       0x1         0x2         d0:73:d5:01:02:04     *        wlan0\n"
    "192.168.1.30       0x1         0x2         d0:73:d5:0a:0b:0c     *        wlan0\n"
    "192.168.1.40       0x1         0x0         00:00:00:00:00:00     *        wlan0\n"
)

#: ``ip -4 neigh show`` shape. The FAILED entry carries no ``lladdr`` and must
#: be skipped.
IP_NEIGH_FIXTURE = (
    "192.168.1.20 dev wlan0 lladdr d0:73:d5:01:02:04 REACHABLE\n"
    "192.168.1.30 dev wlan0 lladdr d0:73:d5:0a:0b:0c STALE\n"
    "192.168.1.40 dev wlan0 FAILED\n"
)


@dataclass
class AuditRow:
    """One device's correlation result; fields mirror :data:`CSV_COLUMNS`.

    ``real_mac`` is the empty string when no ARP entry was found (rendered as
    a dim placeholder in the table, empty in CSV output).
    """

    serial: str
    derived_mac: str
    real_mac: str
    verdict: str
    product_id: str
    product_name: str
    firmware: str
    ip: str

    @property
    def rule_ok(self) -> str:
        """Whether ``get_mac_address()`` matched the real MAC: yes/no/unknown.

        ``verdict`` describes the serial → real-MAC relationship. This instead
        grades the *library's* derivation against that same observation, so a
        firmware the rule mishandles is visible directly rather than only by
        eye-diffing the derived and real columns.
        """
        if not self.derived_mac or not self.real_mac:
            return "unknown"
        return (
            "yes"
            if normalise_mac(self.derived_mac) == normalise_mac(self.real_mac)
            else "no"
        )


def firmware_sort_key(firmware: str) -> tuple[int, int]:
    """Order a ``major.minor`` firmware string numerically, not lexically.

    Sorting the display string puts 3.9 *after* 3.70 and 3.100 *before* 3.50 —
    the exact decimal-vs-integer trap the offset rule itself turns on. The
    boundary is meant to be readable straight off an ordered firmware column,
    so the column has to be ordered the way the rule compares.
    """
    major, _, minor = firmware.partition(".")
    try:
        return (int(major), int(minor))
    except ValueError:
        # Unprobed devices carry an empty firmware; sort them last.
        return (1 << 30, 1 << 30)


#: Strict ``arp -an`` line shape: IP in parentheses, then a hex/colon MAC.
_ARP_DARWIN_LINE = re.compile(r"\S+ \((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-fA-F:]+) ")


def _is_valid_mac(mac: str) -> bool:
    """Return True when ``mac`` has exactly six octets of one or two hex digits."""
    parts = mac.split(":")
    return len(parts) == 6 and all(
        1 <= len(part) <= 2 and all(c in "0123456789abcdefABCDEF" for c in part)
        for part in parts
    )


def normalise_mac(mac: str) -> str:
    """Zero-pad every octet of a colon-separated MAC to lowercase two-digit hex.

    macOS ``arp`` emits unpadded octets (e.g. ``00:00:5e:00:53:e``); both the
    derived and the real MAC must pass through here before any comparison.
    """
    return ":".join(f"{int(octet, 16):02x}" for octet in mac.split(":"))


def serial_to_mac(serial: str) -> str:
    """Render a 12-hex-digit LIFX serial as a colon-separated lowercase MAC."""
    return ":".join(serial[i : i + 2].lower() for i in range(0, 12, 2))


def shorten_product(product: str) -> str:
    """Drop the redundant leading ``LIFX `` that every product name carries.

    Every row repeats it, so it buys nothing and costs the width that forced
    product names to wrap over three or four lines. Never strips a name down
    to nothing, and the CSV keeps the untouched name.
    """
    remainder = product[len("LIFX ") :] if product.startswith("LIFX ") else product
    return remainder or product


def abbreviate_mac(mac: str, serial: str) -> str:
    """Shorten a MAC to its final octet when the leading five match the serial.

    The whole off-by-one question lives in the last octet, and the first five
    are identical to the serial by construction — printing them for every row
    costs the width that made the table unreadable. Any MAC that diverges
    earlier is returned in full, because that divergence is exactly the
    surprise the audit exists to catch and must never be hidden.
    """
    if not mac:
        return ""
    prefix = serial_to_mac(serial).rsplit(":", 1)[0]
    if normalise_mac(mac).startswith(f"{prefix}:"):
        return mac.rsplit(":", 1)[1]
    return mac


def _add_arp_entry(
    entries: dict[str, str], conflicted: set[str], ip: str, mac: str
) -> None:
    """Record one ARP observation, detecting same-IP/different-MAC conflicts.

    Duplicate lines that agree on the (normalised) MAC keep the first entry; a
    conflicting duplicate marks the IP so the caller can drop it entirely — an
    honest ``unknown`` beats a coin-flip verdict from a stale ARP table.
    """
    normalised = normalise_mac(mac)
    existing = entries.get(ip)
    if existing is not None and existing != normalised:
        conflicted.add(ip)
        return
    entries.setdefault(ip, normalised)


def _drop_conflicted(entries: dict[str, str], conflicted: set[str]) -> dict[str, str]:
    """Remove every conflicted IP from the map so its verdict is ``unknown``."""
    for ip in conflicted:
        entries.pop(ip, None)
    return entries


def parse_arp_darwin(text: str, conflicted: set[str] | None = None) -> dict[str, str]:
    """Parse macOS ``arp -an`` output into ``{ip: normalised_mac}``.

    ``(incomplete)`` entries fail the MAC group naturally. Duplicate IPs that
    agree on the MAC (multi-interface hosts) keep one entry; duplicates with
    CONFLICTING MACs are dropped entirely (recorded in ``conflicted``).
    Anything not matching the strict IP/MAC shape is discarded.
    """
    if conflicted is None:
        conflicted = set()
    entries: dict[str, str] = {}
    for line in text.splitlines():
        match = _ARP_DARWIN_LINE.match(line)
        if match is None or not _is_valid_mac(match.group(2)):
            continue
        _add_arp_entry(entries, conflicted, match.group(1), match.group(2))
    return _drop_conflicted(entries, conflicted)


def parse_arp_linux(text: str, conflicted: set[str] | None = None) -> dict[str, str]:
    """Parse ``/proc/net/arp`` into ``{ip: normalised_mac}`` (Linux bonus).

    Columns are ``IP address, HW type, Flags, HW address, Mask, Device``;
    entries with ``Flags`` of ``0x0`` are incomplete and skipped. Conflicting
    duplicate IPs are dropped entirely (recorded in ``conflicted``).
    """
    if conflicted is None:
        conflicted = set()
    entries: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        ip, _hw_type, flags, mac = parts[0], parts[1], parts[2], parts[3]
        if flags == "0x0" or not _is_valid_mac(mac):
            continue
        _add_arp_entry(entries, conflicted, ip, mac)
    return _drop_conflicted(entries, conflicted)


def classify_verdict(serial: str, real_mac: str | None) -> str:
    """Classify the serial → real MAC relationship.

    Returns ``unknown`` when there is no ARP observation, ``identical`` when
    the real MAC equals the serial rendered as a MAC, ``off-by-one`` when only
    the final octet differs by exactly ``+1 % 256``, ``off-by-minus-one`` when
    it differs by exactly ``-1 % 256`` (a −1 relationship is exactly the kind
    of signal this audit exists to surface, so it must not be lumped into a
    generic mismatch), and ``mismatch`` otherwise.
    """
    if real_mac is None:
        return "unknown"
    real = normalise_mac(real_mac)
    if real == serial_to_mac(serial):
        return "identical"
    serial_octets = [int(serial[i : i + 2], 16) for i in range(0, 12, 2)]
    real_octets = [int(octet, 16) for octet in real.split(":")]
    if real_octets[:5] == serial_octets[:5]:
        if real_octets[5] == (serial_octets[5] + 1) % 256:
            return "off-by-one"
        if real_octets[5] == (serial_octets[5] - 1) % 256:
            return "off-by-minus-one"
    return "mismatch"


#: ``ip -4 neigh show`` line shape: IP first, then ``lladdr`` and a MAC.
_IP_NEIGH_LINE = re.compile(r"(\d+\.\d+\.\d+\.\d+)\s.*\blladdr\s+([0-9a-fA-F:]+)")


def parse_ip_neigh(text: str, conflicted: set[str] | None = None) -> dict[str, str]:
    """Parse ``ip -4 neigh show`` output into ``{ip: normalised_mac}``.

    Conflicting duplicate IPs are dropped entirely (recorded in
    ``conflicted``).
    """
    if conflicted is None:
        conflicted = set()
    entries: dict[str, str] = {}
    for line in text.splitlines():
        match = _IP_NEIGH_LINE.match(line)
        if match is None or not _is_valid_mac(match.group(2)):
            continue
        _add_arp_entry(entries, conflicted, match.group(1), match.group(2))
    return _drop_conflicted(entries, conflicted)


async def _probe(
    device: Device,
    semaphore: asyncio.Semaphore,
    rows: list[AuditRow],
    progress: Progress,
    task_id: TaskID,
    err_console: Console,
) -> None:
    """Query one device (exactly two requests) and record an audit row.

    A device that fails to answer produces a row with verdict ``unknown``
    rather than aborting the sweep.
    """
    async with semaphore:
        row = AuditRow(
            serial=device.serial,
            derived_mac="",
            real_mac="",
            verdict="unknown",
            product_id="",
            product_name="unknown",
            firmware="",
            ip=device.ip,
        )
        try:
            version = await device.get_version()
            firmware = await device.get_host_firmware()
            # Cached after get_host_firmware() — no extra network traffic.
            row.derived_mac = await device.get_mac_address()
            row.product_id = str(version.product)
            row.firmware = f"{firmware.version_major}.{firmware.version_minor}"
            # get_product() substitutes a synthetic "LIFX Light" for unknown
            # IDs, which would silently merge every unrecognised product into
            # one summary bucket — and a product newer than the bundled
            # registry is exactly the device most likely to carry the firmware
            # this audit is measuring. Go through the registry so an unknown ID
            # stays visibly distinct.
            product = get_registry().get_product(version.product)
            row.product_name = (
                product.name
                if product is not None
                else f"unknown product {version.product}"
            )
        except LifxError as exc:
            err_console.print(
                f"[dim]{device.serial} ({device.ip}) did not answer: "
                f"{escape(str(exc))}[/dim]"
            )
        except Exception as exc:
            # Non-LifxError failures must still be visible to the operator —
            # gather(return_exceptions=True) would otherwise swallow them.
            err_console.print(
                f"[dim]{device.serial} ({device.ip}) unexpected error: "
                f"{escape(str(exc))}[/dim]"
            )
        finally:
            # Record the row BEFORE closing: a raising close() must never
            # silently drop a device from the dataset.
            rows.append(row)
            progress.advance(task_id)
            try:
                await device.connection.close()
            except Exception as exc:
                # A close failure must not affect the dataset — log and move on.
                err_console.print(
                    f"[dim]{device.serial} ({device.ip}) close failed: "
                    f"{escape(str(exc))}[/dim]"
                )


async def _sweep(timeout: float, err_console: Console) -> list[AuditRow]:
    """Broadcast-discover the fleet and probe each device as it arrives."""
    rows: list[AuditRow] = []
    semaphore = asyncio.Semaphore(16)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=err_console,
        transient=True,
    ) as progress:
        # total stays None for the whole discovery window. The device count is
        # genuinely unknown until the generator is exhausted, and probes finish
        # while it is still yielding — so setting a running total here makes the
        # bar snap to 100% and back every time a probe lands before the next
        # device arrives. Indeterminate is the honest widget for this window.
        task_id = progress.add_task("Discovering devices", total=None)
        tasks: list[asyncio.Task[None]] = []
        try:
            # Lowered device_timeout/max_retries stop one dead device holding a
            # concurrency slot for the default 16 s.
            async for device in discover(
                timeout=timeout, device_timeout=5.0, max_retries=3
            ):
                tasks.append(
                    asyncio.create_task(
                        _probe(device, semaphore, rows, progress, task_id, err_console)
                    )
                )
                progress.update(
                    task_id, description=f"Discovering devices ({len(tasks)} found)"
                )
        except Exception as exc:
            # A broadcast socket that dies part-way (a flapping interface on a
            # 73-device sweep) must not throw away the rows already collected —
            # every other failure in this script degrades to a row, not a
            # traceback. The already-started probes are still awaited below.
            err_console.print(
                f"[yellow]Discovery stopped early ({escape(str(exc))}) — "
                f"reporting the {len(tasks)} device(s) already found.[/yellow]"
            )
        finally:
            # Discovery is done, so the total is final — the bar can now be
            # determinate and drain monotonically to 100% exactly once.
            progress.update(
                task_id, total=len(tasks), description=f"Probing {len(tasks)} device(s)"
            )
            # Backstop only: _probe converts failures to rows internally.
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    return rows


def _run_snapshot(argv: list[str], err_console: Console) -> str | None:
    """Run one ARP snapshot command, degrading to None instead of crashing.

    A missing binary or a hung invocation must never throw away a completed
    fleet sweep — losing a 73-device dataset to a missing ``arp`` is worse
    than reporting every verdict as unknown. Non-zero exits are announced so
    the operator can tell "ARP lookup broke" from "no ARP entries existed".
    """
    command = " ".join(argv)
    try:
        # Fixed argv list, no shell; output goes through a strict IP/MAC parser.
        result = subprocess.run(  # nosec B603 B607
            argv, capture_output=True, text=True, check=False, timeout=10.0
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        # OSError covers FileNotFoundError (no arp binary) and PermissionError
        # (binary present but not executable under a hardened image or an
        # AppArmor/SELinux denial) alike — both would otherwise discard a
        # completed fleet sweep at the very last step.
        err_console.print(
            f"[yellow]`{command}` failed ({escape(str(exc))}) — "
            "verdicts will be unknown.[/yellow]"
        )
        return None
    if result.returncode != 0:
        err_console.print(
            f"[yellow]`{command}` exited {result.returncode}: "
            f"{escape(result.stderr.strip())} — ARP data may be missing or "
            "incomplete.[/yellow]"
        )
    return result.stdout


def read_arp_table(err_console: Console) -> dict[str, str]:
    """Take ONE ARP snapshot after all probes complete — never per-IP calls.

    Discovery unicast plus the two probe requests already populated the
    entries. Unsupported platforms and failed snapshots return an empty map
    (verdicts unknown), with the degradation announced on stderr.
    """
    entries: dict[str, str] = {}
    conflicted: set[str] = set()
    if sys.platform == "darwin":
        output = _run_snapshot(["arp", "-an"], err_console)
        if output is not None:
            entries = parse_arp_darwin(output, conflicted)
    elif sys.platform.startswith("linux"):
        proc_arp = Path("/proc/net/arp")
        proc_text: str | None = None
        if proc_arp.exists():
            try:
                proc_text = proc_arp.read_text()
            except OSError as exc:
                # Same contract as _run_snapshot: an unreadable /proc entry
                # degrades to unknown verdicts, never to a lost sweep.
                err_console.print(
                    f"[yellow]/proc/net/arp unreadable ({escape(str(exc))}) — "
                    "falling back to `ip neigh`.[/yellow]"
                )
        if proc_text is not None:
            entries = parse_arp_linux(proc_text, conflicted)
        else:
            output = _run_snapshot(["ip", "-4", "neigh", "show"], err_console)
            if output is not None:
                entries = parse_ip_neigh(output, conflicted)
    else:
        err_console.print(
            "[yellow]No ARP support on this platform — all verdicts will be "
            "unknown.[/yellow]"
        )
    if conflicted:
        err_console.print(
            "[yellow]Dropped conflicting ARP entries (verdicts unknown) for: "
            f"{escape(', '.join(sorted(conflicted)))}[/yellow]"
        )
    return entries


def write_csv(rows: list[AuditRow]) -> None:
    """Emit only CSV on stdout — no Rich object ever touches stdout here.

    ``lineterminator`` is forced to ``\\n``: the excel dialect's default
    ``\\r\\n`` would leave a carriage return glued to the final column, so a
    Unix filter matching on ``rule_ok`` finds nothing (and Windows would
    translate it again into a blank row between every record).
    """
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow([getattr(row, column) for column in CSV_COLUMNS])


def build_summary_panel(rows: list[AuditRow]) -> Panel:
    """Group verdict counts by (product, firmware) — the point of the audit."""
    counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in rows:
        counts[(row.product_name, row.firmware)][row.verdict] += 1
    summary = Table()
    summary.add_column("product", no_wrap=True)
    summary.add_column("firmware", no_wrap=True, justify="right")
    for verdict, style in VERDICT_STYLES.items():
        summary.add_column(
            f"[{style}]{VERDICT_HEADERS[verdict]}[/]", justify="right", no_wrap=True
        )
    for (product, firmware), verdict_counts in sorted(
        counts.items(), key=lambda item: (item[0][0], firmware_sort_key(item[0][1]))
    ):
        summary.add_row(
            shorten_product(product),
            firmware,
            *(str(verdict_counts.get(verdict, 0)) for verdict in VERDICT_STYLES),
        )
    return Panel(
        summary,
        expand=False,
        title="Correlation by product + firmware",
        subtitle="same=identical  +1=off-by-one  -1=off-by-minus-one  "
        "mism=mismatch  unkn=unknown",
    )


def build_rule_panel(rows: list[AuditRow]) -> Panel:
    """Name the firmware versions where ``get_mac_address()`` disagrees with ARP.

    This is the headline the audit was commissioned to produce, so it gets its
    own panel rather than leaving the reader to spot it in the row detail.
    """
    graded = [row for row in rows if row.rule_ok != "unknown"]
    broken: dict[tuple[str, str], int] = defaultdict(int)
    # A `mismatch` verdict means the observed MAC shares no prefix with the
    # serial at all — usually the gateway's MAC via proxy ARP across a VLAN or
    # mesh AP, i.e. not the device's MAC and no evidence about the rule. Those
    # rows are reported separately so a routing artefact cannot be read as a
    # firmware the library mishandles; that misreading is what would put a
    # wrong constant into base.py.
    suspect = sum(
        1 for row in graded if row.rule_ok == "no" and row.verdict == "mismatch"
    )
    for row in graded:
        if row.rule_ok == "no" and row.verdict != "mismatch":
            broken[(row.product_name, row.firmware)] += 1
    suspect_note = (
        ""
        if not suspect
        else f"\n\n[dim]{suspect} row(s) excluded: the observed MAC shares no "
        "prefix with the serial (proxy ARP / L2 boundary), so it is not "
        "evidence about the rule.[/]"
    )
    if not graded:
        body = "[dim]No device could be graded — no ARP entry matched a responder.[/]"
        style = "dim"
    elif not broken:
        body = (
            f"[green]get_mac_address() matched the real MAC on all "
            f"{len(graded) - suspect} graded device(s).[/]{suspect_note}"
        )
        style = "green"
    else:
        lines = [
            "[bold red]get_mac_address() disagrees with the real MAC on "
            f"{sum(broken.values())} of {len(graded) - suspect} graded device(s):[/]",
            "",
        ]
        lines += [
            f"  [bold red]✗[/] {product} — firmware {firmware} ({count} device(s))"
            for (product, firmware), count in sorted(
                broken.items(),
                key=lambda item: (item[0][0], firmware_sort_key(item[0][1])),
            )
        ]
        body = "\n".join(lines) + suspect_note
        style = "bold red"
    return Panel(
        body, expand=False, border_style=style, title="Library rule vs reality"
    )


def render_results(rows: list[AuditRow]) -> None:
    """Print the colour-coded results table plus the summary panel to stdout."""
    console = Console()
    table = Table(
        title="Serial → MAC correlation audit",
        caption=(
            "derived/real show the final octet only when the leading five match "
            "the serial; a MAC that diverges earlier is shown in full. "
            "The redundant 'LIFX ' product prefix and product_id are omitted "
            "here — use --csv for the complete record."
        ),
        caption_justify="left",
    )
    # product_id is dropped from the human table: product_name already
    # identifies the device, and the column was costing width that the MACs
    # and the verdict need. --csv still carries the full CSV_COLUMNS set.
    table.add_column("serial", no_wrap=True)
    table.add_column("derived", no_wrap=True, justify="right")
    table.add_column("real", no_wrap=True, justify="right")
    table.add_column("verdict", no_wrap=True)
    table.add_column("rule", no_wrap=True, justify="center")
    table.add_column("product")
    table.add_column("fw", no_wrap=True, justify="right")
    table.add_column("ip", no_wrap=True)
    for row in rows:
        style = VERDICT_STYLES[row.verdict]
        derived = abbreviate_mac(row.derived_mac, row.serial)
        real = abbreviate_mac(row.real_mac, row.serial)
        table.add_row(
            row.serial,
            derived or "[dim]—[/]",
            real or "[dim]—[/]",
            f"[{style}]{row.verdict}[/]",
            RULE_CELLS[row.rule_ok],
            shorten_product(row.product_name),
            row.firmware,
            row.ip,
        )
    console.print(table)
    console.print(build_summary_panel(rows))
    console.print(build_rule_panel(rows))


def run_self_test() -> None:
    """Exercise normalisation, ARP parsing, and verdict logic without hardware."""
    if not __debug__:
        # Every check below is a bare assert, which -O / PYTHONOPTIMIZE strips
        # from the bytecode. Running on and printing "passed" would report a
        # suite that executed nothing as green.
        print(
            "Self-test cannot run under -O / PYTHONOPTIMIZE: assertions are "
            "stripped, so it would pass without checking anything.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    # Normalisation: the unpadded-octet forms macOS arp emits, and idempotency.
    assert normalise_mac("00:00:5e:00:53:e") == "00:00:5e:00:53:0e", (
        "single unpadded final octet must be zero-padded"
    )
    assert normalise_mac("0:0:5e:0:53:f8") == "00:00:5e:00:53:f8", (
        "multiple unpadded octets must be zero-padded"
    )
    assert normalise_mac("00:00:5e:00:53:f8") == "00:00:5e:00:53:f8", (
        "normalisation must be idempotent on already-padded input"
    )

    # Serial rendering.
    assert serial_to_mac("d073d5010203") == "d0:73:d5:01:02:03", (
        "serial must render as a colon-separated lowercase MAC"
    )

    # Display abbreviation: last octet only when the leading five match the
    # serial, full MAC whenever they do not — an early divergence is the
    # surprise this audit exists to catch and must never be abbreviated away.
    assert abbreviate_mac("d0:73:d5:01:02:03", "d073d5010203") == "03", (
        "matching leading octets must abbreviate to the final octet"
    )
    assert abbreviate_mac("d0:73:d5:01:02:04", "d073d5010203") == "04", (
        "an off-by-one final octet must still abbreviate"
    )
    assert abbreviate_mac("d0:73:d5:01:ff:03", "d073d5010203") == "d0:73:d5:01:ff:03", (
        "divergence before the final octet must render the MAC in full"
    )
    assert abbreviate_mac("d0:73:d5:1:2:3", "d073d5010203") == "3", (
        "unpadded macOS octets must still match the serial prefix"
    )
    assert abbreviate_mac("", "d073d5010203") == "", (
        "an absent MAC must abbreviate to the empty string"
    )

    # Product shortening drops only the redundant leading vendor prefix.
    assert shorten_product("LIFX Clean A19 1200lm") == "Clean A19 1200lm", (
        "the redundant 'LIFX ' prefix must be dropped"
    )
    assert shorten_product("Clean A19") == "Clean A19", (
        "a name without the prefix must pass through untouched"
    )
    assert shorten_product("LIFX ") == "LIFX ", (
        "shortening must never reduce a name to nothing"
    )

    # Every verdict needs a distinct short summary header — full names
    # ellipsise to an identical 'off-by-…' for both off-by columns.
    assert set(VERDICT_HEADERS) == set(VERDICT_STYLES), (
        "every verdict must have a short summary header"
    )
    assert len(set(VERDICT_HEADERS.values())) == len(VERDICT_HEADERS), (
        "short summary headers must be mutually distinct"
    )

    # rule_ok grades the LIBRARY's derivation, not the serial relationship.
    def _row(derived: str, real: str) -> AuditRow:
        return AuditRow(
            serial="d073d5010203",
            derived_mac=derived,
            real_mac=real,
            verdict="identical",
            product_id="1",
            product_name="LIFX Test",
            firmware="3.50",
            ip="192.168.1.1",
        )

    assert _row("d0:73:d5:01:02:03", "d0:73:d5:01:02:03").rule_ok == "yes", (
        "a derivation matching the real MAC must grade yes"
    )
    assert _row("d0:73:d5:01:02:04", "d0:73:d5:01:02:03").rule_ok == "no", (
        "a derivation the real MAC contradicts must grade no"
    )
    assert _row("d0:73:d5:01:02:03", "d0:73:d5:1:2:3").rule_ok == "yes", (
        "grading must normalise before comparing, not diff raw strings"
    )
    assert _row("d0:73:d5:01:02:03", "").rule_ok == "unknown", (
        "a device with no ARP entry cannot grade the rule"
    )
    assert _row("", "d0:73:d5:01:02:03").rule_ok == "unknown", (
        "a device that never answered cannot grade the rule"
    )
    assert set(RULE_CELLS) == {"yes", "no", "unknown"}, (
        "every rule_ok value needs a table rendering"
    )
    assert "rule_ok" in CSV_COLUMNS, "the rule grade must reach the CSV"

    # ARP parsing against the macOS-format fixture.
    parsed = parse_arp_darwin(ARP_FIXTURE_DARWIN)
    assert parsed == {
        "192.168.1.137": "00:00:5e:00:53:f8",
        "192.168.1.1": "00:00:5e:00:53:0e",
    }, f"unexpected ARP parse result: {parsed}"
    assert "192.168.1.254" not in parsed, "(incomplete) entry must be absent"

    # Duplicate IPs that AGREE on the MAC keep a single entry.
    agreeing = (
        "? (10.0.0.1) at 00:00:5e:00:53:ff on en0 ifscope [ethernet]\n"
        "? (10.0.0.1) at 00:00:5e:00:53:ff on en1 [ethernet]\n"
    )
    agree_conflicts: set[str] = set()
    assert parse_arp_darwin(agreeing, agree_conflicts) == {
        "10.0.0.1": "00:00:5e:00:53:ff"
    }, "agreeing duplicate lines must keep a single entry"
    assert agree_conflicts == set(), "agreeing duplicates must not be conflicts"

    # Duplicate IPs with CONFLICTING MACs are dropped entirely (unknown beats
    # a coin-flip verdict from a stale ARP table).
    conflicting = (
        "? (10.0.0.1) at 00:00:5e:00:53:ff on en0 ifscope [ethernet]\n"
        "? (10.0.0.1) at 00:00:5e:00:53:01 on en1 [ethernet]\n"
        "? (10.0.0.2) at 00:00:5e:00:53:66 on en0 [ethernet]\n"
    )
    conflict_set: set[str] = set()
    parsed_conflict = parse_arp_darwin(conflicting, conflict_set)
    assert parsed_conflict == {"10.0.0.2": "00:00:5e:00:53:66"}, (
        "an IP with conflicting MACs must be dropped from the map"
    )
    assert conflict_set == {"10.0.0.1"}, "the conflicted IP must be recorded"

    # Linux parsers. Neither can be exercised by running this tool on macOS,
    # and a broken parser returns {} — indistinguishable from a cold ARP cache
    # — so the only thing standing between a column-shift regression and an
    # audit that can never grade a device on Linux is this fixture.
    linux_conflicts: set[str] = set()
    assert parse_arp_linux(PROC_NET_ARP_FIXTURE, linux_conflicts) == {
        "192.168.1.20": "d0:73:d5:01:02:04",
        "192.168.1.30": "d0:73:d5:0a:0b:0c",
    }, "the /proc/net/arp columns must parse to {ip: normalised_mac}"
    assert linux_conflicts == set(), "the fixture has no conflicting duplicates"

    neigh_conflicts: set[str] = set()
    assert parse_ip_neigh(IP_NEIGH_FIXTURE, neigh_conflicts) == {
        "192.168.1.20": "d0:73:d5:01:02:04",
        "192.168.1.30": "d0:73:d5:0a:0b:0c",
    }, "`ip -4 neigh show` lines must parse to {ip: normalised_mac}"
    assert neigh_conflicts == set(), "the fixture has no conflicting duplicates"

    # Firmware ordering is numeric per component — the whole point of the
    # correlation panel is reading the boundary off an ordered column, and
    # 3.9 sorts ABOVE 3.70 under the string ordering this replaced.
    assert sorted(
        ["3.50", "3.69", "3.9", "3.70", "3.90", "3.100"], key=firmware_sort_key
    ) == ["3.9", "3.50", "3.69", "3.70", "3.90", "3.100"], (
        "firmware must order by integer major/minor, not lexically"
    )
    assert firmware_sort_key("") > firmware_sort_key("4.99"), (
        "an unprobed device (empty firmware) must sort last"
    )

    # Verdict classification.
    assert classify_verdict("d073d5010203", "d0:73:d5:01:02:03") == "identical"
    assert classify_verdict("d073d5010203", "d0:73:d5:01:02:04") == "off-by-one"
    assert classify_verdict("d073d50102ff", "d0:73:d5:01:02:00") == "off-by-one", (
        "final-octet wraparound (0xff + 1) % 256 == 0x00 must be off-by-one"
    )
    assert (
        classify_verdict("d073d5010203", "d0:73:d5:01:02:02") == "off-by-minus-one"
    ), "a -1 final octet must be off-by-minus-one, not a generic mismatch"
    assert (
        classify_verdict("d073d5010200", "d0:73:d5:01:02:ff") == "off-by-minus-one"
    ), "final-octet wraparound (0x00 - 1) % 256 == 0xff must be off-by-minus-one"
    assert classify_verdict("d073d5010203", "d0:73:d5:01:02:05") == "mismatch", (
        "off-by-one matches ONLY +1 mod 256, not +2"
    )
    assert classify_verdict("d073d5010203", "d0:73:d5:01:02:01") == "mismatch", (
        "off-by-minus-one matches ONLY -1 mod 256, not -2"
    )
    assert classify_verdict("d073d5010203", "d0:73:d5:01:03:03") == "mismatch", (
        "a difference in a non-final octet must be a mismatch"
    )
    assert classify_verdict("d073d5010203", None) == "unknown"

    # PEP 723 local-source pin: lifx must resolve to this checkout, not PyPI.
    repo_root = Path(__file__).resolve().parent.parent
    expected = repo_root / "src" / "lifx" / "__init__.py"
    actual = Path(lifx.__file__ or "").resolve()
    assert actual == expected, (
        f"lifx resolved to {actual}, expected the local checkout at {expected} — "
        "the PEP 723 [tool.uv.sources] pin did not take effect"
    )

    print("Self-test passed: all assertions OK.", file=sys.stderr)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Build and evaluate the CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Audit the serial → MAC correlation across every discoverable "
            "LIFX device on the local network."
        ),
        epilog=(
            "Rows cover responders only, and a single discovery round "
            "under-counts (6-round median 48/73 devices in Spike 005) — "
            "re-running the sweep enlarges the dataset."
        ),
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="emit only CSV rows on stdout (all progress output goes to stderr)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="discovery timeout in seconds (default: 15)",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        dest="self_test",
        help="run the embedded hardware-free self-test and exit",
    )
    return parser.parse_args(argv)


def main() -> None:
    """Entry point."""
    args = parse_args()
    if args.self_test:
        run_self_test()
        return

    # All Rich chrome lives on stderr in BOTH modes, so --csv pipes cleanly.
    err_console = Console(stderr=True)
    rows = asyncio.run(_sweep(args.timeout, err_console))
    arp_map = read_arp_table(err_console)
    for row in rows:
        real_mac = arp_map.get(row.ip)
        if real_mac is not None:
            row.real_mac = real_mac
        # Classify whenever there is an observation. The serial always comes
        # from discovery, so a device that answered the broadcast but dropped
        # its two probe packets — the common case at a median 48/73 response
        # rate — still yields a real verdict instead of a blanket unknown.
        row.verdict = classify_verdict(row.serial, real_mac)
    rows.sort(
        key=lambda row: (
            row.product_name,
            firmware_sort_key(row.firmware),
            row.serial,
        )
    )

    if args.csv:
        write_csv(rows)
        # The headline verdict must survive --csv: STATE.md names that exact
        # invocation as the standing re-run procedure, and a refutation of the
        # rule would otherwise be visible only by hand-scanning rule_ok.
        err_console.print(build_rule_panel(rows))
    else:
        render_results(rows)

    err_console.print(
        f"[dim]{len(rows)} responder(s) — rows cover responders only; a single "
        "round under-counts, so re-run to enlarge the dataset.[/dim]"
    )


if __name__ == "__main__":
    main()
