#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["rich>=15.0.0", "lifx-async"]
#
# [tool.uv.sources]
# lifx-async = { path = "../", editable = true }
# ///
"""Inventory every LIFX Matrix device on the local network.

Discovers Matrix devices and reports what distinguishes each one: identity,
firmware, current state, the tile chain geometry, the running firmware effect,
and — for Ceiling and Mirror products — the component layout that splits the
matrix into logical parts.

Individual zone colours are deliberately not shown: this is an inventory of
what a device *is*, not what it is currently displaying. Product capability
flags are omitted for the same reason — every Matrix product carries the same
set, apart from has_chain, which only the Tile has and which the product name
and tile count already reveal.

Devices populate a live table as they answer, then the report is written to
normal terminal output so the values stay copy-pasteable. The default report is
the summary table alone; --verbose adds a detail panel per device.

Usage:
    ./scripts/scan_matrix.py
    ./scripts/scan_matrix.py --verbose
    ./scripts/scan_matrix.py --timeout 30
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from rich.columns import Columns
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from lifx import (
    HSBK,
    CeilingLight,
    FirmwareEffect,
    MatrixLight,
    MirrorLight,
    TileEffectSkyType,
    discover,
)
from lifx.const import INVALID_AMBIENT_LIGHT_RESPONSE
from lifx.devices.matrix import MatrixEffect, TileInfo

#: Discovery window in seconds. Long enough for a large fleet to answer.
DEFAULT_TIMEOUT = 15.0

#: Rendered when a value is absent rather than zero.
UNKNOWN = Text("—", style="dim")


@dataclass
class Report:
    """Everything gathered about one Matrix device.

    Attributes:
        device: The device itself, already initialized
        error: Message from a query that failed, or None if all succeeded
    """

    device: MatrixLight
    error: str | None = None
    _label: str = field(default="", repr=False)

    @property
    def label(self) -> str:
        """Device label, falling back to the serial before state exists."""
        return self._label or self.device.serial

    @property
    def kind(self) -> str:
        """Name of the device class the product registry resolved to."""
        return type(self.device).__name__

    @property
    def product_id(self) -> int | None:
        """Product ID, or None if the version was never fetched."""
        return self.device.version.product if self.device.version else None


def _firmware(major: int, minor: int, build: int) -> str:
    """Render a firmware version and the date of its build stamp.

    Build stamps are nanoseconds since the epoch, which is 19 digits of
    unreadable precision for an inventory. The date is the useful part.
    """
    if build <= 0:
        return f"{major}.{minor}"

    built = datetime.fromtimestamp(build / 1_000_000_000, tz=timezone.utc)
    return f"{major}.{minor} ({built:%Y-%m-%d})"


def _kv_table(title: str) -> Table:
    """Build the two-column key/value table used throughout the report.

    Rich wraps a title to the table's width, so a short table — a collapsed
    effect section is two words wide — would fold its own heading onto a
    second line. The floor keeps every heading on one line.
    """
    table = Table(
        title=title,
        title_style="bold cyan",
        title_justify="left",
        box=None,
        show_header=False,
        pad_edge=False,
        min_width=len(title) + 2,
    )
    table.add_column("field", style="dim", no_wrap=True)
    table.add_column("value")
    return table


def _identity_table(report: Report) -> Table:
    """Identity, product and firmware details."""
    device = report.device
    state = device.state

    table = _kv_table("Identity")
    table.add_row("Label", state.label)
    table.add_row("Serial", device.serial)
    table.add_row("MAC", state.mac_address)
    table.add_row("IP", f"{device.ip}:{device.port}")
    table.add_row("Product", f"{report.product_id} — {state.model}")
    table.add_row("Class", report.kind)
    table.add_row(
        "Host firmware",
        _firmware(
            state.host_firmware.version_major,
            state.host_firmware.version_minor,
            state.host_firmware.build,
        ),
    )
    table.add_row(
        "WiFi firmware",
        _firmware(
            state.wifi_firmware.version_major,
            state.wifi_firmware.version_minor,
            state.wifi_firmware.build,
        ),
    )

    # A single-tile device gets no chain table, so its geometry belongs here.
    # Multi-tile devices carry per-tile geometry in the chain table instead.
    if len(state.chain) == 1:
        tile = state.chain[0]
        table.add_row("Matrix", f"{tile.width}×{tile.height}")
        table.add_row("Frame buffers", str(tile.supported_frame_buffers))

    return table


def _state_table(report: Report) -> Table:
    """Current power, placement and radio state."""
    state = report.device.state

    table = _kv_table("State")
    table.add_row(
        "Power",
        Text("on", style="green") if state.power > 0 else Text("off", style="dim"),
    )
    table.add_row("Location", f"{state.location.label} ({state.location.uuid})")
    table.add_row("Group", f"{state.group.label} ({state.group.uuid})")

    # The raw signal is a tiny float; the RSSI derived from it is the number
    # anyone actually reads, so it leads.
    if state.wifi_info.signal is None:
        table.add_row("WiFi signal", UNKNOWN)
    else:
        table.add_row(
            "WiFi signal",
            f"{state.wifi_info.rssi} {state.wifi_info.rssi_unit}",
        )

    ambient = getattr(state, "ambient_light", None)
    if ambient is None:
        table.add_row("Ambient light", UNKNOWN)
    elif ambient == INVALID_AMBIENT_LIGHT_RESPONSE:
        # The sensor measures the light's own output while it is lit, so a
        # reading taken with the light on says nothing about the room.
        table.add_row("Ambient light", Text("n/a (light on)", style="dim"))
    else:
        table.add_row("Ambient light", f"{ambient:.2f} lux")

    return table


def _effect_table(effect: MatrixEffect | None) -> Table:
    """The firmware effect the device is currently running.

    A stopped device reports speed, duration and palette anyway, but they are
    leftovers rather than settings in force, so only a running effect is worth
    expanding into its configuration.
    """
    table = _kv_table("Firmware effect")

    if effect is None:
        table.add_row("Effect", UNKNOWN)
        return table

    table.add_row("Effect", effect.effect_type.name)

    if effect.effect_type is FirmwareEffect.OFF:
        return table

    table.add_row("Speed", f"{effect.speed} ms")
    table.add_row(
        "Duration", "infinite" if effect.duration == 0 else f"{effect.duration} ns"
    )

    # sky_type is carried on every effect but only means anything for SKY:
    # a MORPH reporting "SUNRISE" is a default, not a setting. The cloud
    # saturation bounds narrow further, to the CLOUDS sky type.
    if effect.effect_type is FirmwareEffect.SKY:
        table.add_row("Sky type", effect.sky_type.name)
        if effect.sky_type is TileEffectSkyType.CLOUDS:
            table.add_row(
                "Cloud saturation",
                f"{effect.cloud_saturation_min}–{effect.cloud_saturation_max}",
            )

    if not effect.palette:
        table.add_row("Palette", "0")
        return table

    # The palette is effect configuration rather than displayed output, so it
    # is shown in full: MORPH cycles through these colours, and the firmware
    # caps the list at 16 entries.
    table.add_row("Palette", f"{len(effect.palette)} colours")
    for index, color in enumerate(effect.palette, start=1):
        table.add_row(f"  {index}", _swatch(color))

    return table


def _swatch(color: HSBK) -> Text:
    """Render one palette colour as a colour block plus its HSBK values."""
    red, green, blue = color.to_rgb()
    hex_color = (
        f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"
    )

    swatch = Text("██ ", style=hex_color)
    swatch.append(
        f"h {color.hue:.0f}  s {color.saturation:.2f}  "
        f"b {color.brightness:.2f}  k {color.kelvin}",
        style="none",
    )
    return swatch


def _chain_table(chain: list[TileInfo]) -> Table:
    """One row per tile in the chain."""
    table = Table(
        title="Tile chain",
        title_style="bold cyan",
        title_justify="left",
        box=None,
        pad_edge=False,
        header_style="dim",
    )
    # Rich squeezes over-wide tables by shrinking columns, which can drive a
    # short one to zero width and drop it entirely. min_width keeps every
    # column legible on a narrow terminal.
    table.add_column("#", no_wrap=True, min_width=2)
    for column in ("Size", "user_x", "user_y", "Buffers"):
        table.add_column(column, no_wrap=True, min_width=len(column))
    table.add_column("Accel (x,y,z)", no_wrap=True, min_width=12)

    # Per-tile firmware is omitted: it always matches the device firmware
    # already shown under Identity.
    for tile in chain:
        table.add_row(
            str(tile.tile_index),
            f"{tile.width}×{tile.height}",
            f"{tile.user_x:g}",
            f"{tile.user_y:g}",
            str(tile.supported_frame_buffers),
            f"{tile.accel_meas_x}, {tile.accel_meas_y}, {tile.accel_meas_z}",
        )

    return table


def _component_table(report: Report) -> Table | None:
    """Component layout, for the products that split their matrix into parts."""
    device = report.device

    # Matrix dimensions are not repeated here: Identity carries the geometry
    # the device itself reported, which is the ground truth, while these
    # layouts come from the product registry.
    if isinstance(device, CeilingLight):
        table = _kv_table("Components")
        # The uplight is always the last zone, so its index equals the
        # downlight count and the two read as a duplicated number. Showing the
        # downlight range rather than its size keeps them distinguishable.
        zones = device.downlight_zones
        table.add_row("Uplight zone", str(device.uplight_zone))
        table.add_row(
            "Downlight zones",
            f"{zones.start}–{zones.stop - 1} ({device.downlight_zone_count} zones)",
        )
        return table

    if isinstance(device, MirrorLight):
        table = _kv_table("Components")
        layout = device.layout
        table.add_row(
            "Buffer size", f"{layout.buffer_size} ({layout.zone_count} zones)"
        )
        table.add_row(
            "Unused positions",
            ", ".join(
                str(position)
                for position, zone in enumerate(layout.zone_map)
                if zone < 0
            )
            or "none",
        )
        table.add_row("Front zones", str(device.front_zone_count))
        table.add_row("Back zones", str(device.back_zone_count))
        table.add_row(
            "Front left / right",
            f"{len(device.front_left_positions)} / {len(device.front_right_positions)}",
        )
        table.add_row(
            "Back left / right",
            f"{len(device.back_left_positions)} / {len(device.back_right_positions)}",
        )
        return table

    return None


def _device_panel(report: Report, effect: MatrixEffect | None) -> Panel:
    """Assemble the full detail panel for one device."""
    device = report.device
    state = device.state

    left = Group(_identity_table(report), Text(), _state_table(report))

    # Product capabilities are uniform across every Matrix product, so they
    # said nothing per device. has_chain is the lone exception, and the product
    # name and tile count in the summary already give that away.
    right_parts: list[RenderableType] = []

    component = _component_table(report)
    if component is not None:
        right_parts.extend([component, Text()])

    right_parts.append(_effect_table(effect))
    right = Group(*right_parts)

    body: list[RenderableType] = [Columns([left, right], padding=(0, 6))]

    # Only a real chain earns a table; a single tile's geometry is in Identity.
    if len(state.chain) > 1:
        body.extend([Text(), _chain_table(state.chain)])

    if report.error is not None:
        body.extend([Text(), Text(f"Partial data: {report.error}", style="yellow")])

    return Panel(
        Group(*body),
        title=f"[bold]{state.label}[/bold] · {report.kind}",
        title_align="left",
        subtitle=f"{device.serial} · {device.ip}",
        subtitle_align="right",
        border_style="blue",
        padding=(1, 2),
    )


def _summary_table(
    reports: list[Report], effects: dict[str, MatrixEffect | None]
) -> Table:
    """One row per device, as an at-a-glance index of the report below."""
    table = Table(
        title="Matrix devices",
        title_style="bold",
        header_style="bold cyan",
    )
    # The label is the column worth the most width, so it gets a floor and
    # ellipsis rather than being squeezed away when the terminal is narrow.
    table.add_column("Label", no_wrap=True, overflow="ellipsis", min_width=16)
    table.add_column("Class", no_wrap=True, min_width=5)
    table.add_column("PID", no_wrap=True, justify="right", min_width=3)
    for column in ("Product", "IP", "Matrix", "Tiles", "Effect", "Power"):
        table.add_column(column, no_wrap=True, min_width=len(column))

    for report in reports:
        state = report.device.state
        chain = state.chain
        size = (
            " + ".join(sorted({f"{t.width}×{t.height}" for t in chain}))
            if chain
            else "—"
        )
        effect = effects.get(report.device.serial)
        table.add_row(
            state.label,
            report.kind,
            str(report.product_id) if report.product_id is not None else "—",
            state.model,
            report.device.ip,
            size,
            str(state.tile_count),
            effect.effect_type.name if effect is not None else "—",
            Text("on", style="green") if state.power > 0 else Text("off", style="dim"),
        )

    return table


def _live_table(found: list[Report], done: bool) -> Panel:
    """The progressive table shown while the sweep is running."""
    table = Table(box=None, show_header=False, pad_edge=False)
    table.add_column("mark", no_wrap=True)
    table.add_column("label")
    table.add_column("kind", style="dim", no_wrap=True)

    for report in found:
        if report.error is not None:
            mark = Text("!", style="yellow")
        else:
            mark = Text("*", style="green")
        table.add_row(mark, report.label, report.kind)

    if not found:
        table.add_row(Text("·", style="dim"), Text("waiting…", style="dim"), "")

    title = "Scan complete" if done else "Scanning for Matrix devices…"
    return Panel(table, title=title, title_align="left", border_style="cyan")


async def _inspect(device: MatrixLight) -> tuple[Report, MatrixEffect | None]:
    """Query one device for everything the report needs.

    A device that stops answering part-way through keeps whatever was already
    gathered: with a large fleet, one slow responder should not cost the run.
    """
    report = Report(device=device)
    effect: MatrixEffect | None = None

    # Both readings are opt-in and default to off, so nothing populates the
    # matching state fields unless they are switched on before initialization.
    device.fetch_wifi_info = True
    device.fetch_ambient_light = True

    try:
        await device.refresh_state()
        report._label = device.state.label
        effect = await device.get_effect()
    except Exception as error:  # noqa: BLE001 - one device must not end the scan
        report.error = f"{type(error).__name__}: {error}"

    return report, effect


async def scan(timeout: float, verbose: bool, console: Console) -> None:
    """Discover Matrix devices and report on them.

    Args:
        timeout: Discovery window in seconds
        verbose: Print a detail panel per device below the summary table
        console: Console to render to
    """
    reports: list[Report] = []
    effects: dict[str, MatrixEffect | None] = {}

    with Live(
        _live_table(reports, done=False), console=console, transient=True
    ) as live:
        async for device in discover(timeout=timeout):
            if not isinstance(device, MatrixLight):
                await device.close()
                continue

            report, effect = await _inspect(device)
            reports.append(report)
            effects[device.serial] = effect
            live.update(_live_table(reports, done=False))

        live.update(_live_table(reports, done=True))

    try:
        if not reports:
            console.print("[yellow]No Matrix devices found.[/yellow]")
            return

        reports.sort(key=lambda r: r.label.lower())

        console.print()
        console.print(_summary_table(reports, effects))

        if verbose:
            for report in reports:
                console.print()
                console.print(_device_panel(report, effects.get(report.device.serial)))

        console.print()
        console.print(f"[bold]{len(reports)}[/bold] Matrix device(s) found.")
    finally:
        # Every discovered device holds a connection, whether or not its panel
        # was rendered.
        for report in reports:
            await report.device.close()


def main() -> None:
    """Parse arguments and run the scan."""
    parser = argparse.ArgumentParser(
        description="Inventory every LIFX Matrix device on the local network"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Discovery window in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print a detail panel for every device below the summary table",
    )
    args = parser.parse_args()

    console = Console()
    try:
        asyncio.run(scan(args.timeout, args.verbose, console))
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")


if __name__ == "__main__":
    main()
