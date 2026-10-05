"""Shared transition contracts through real Ceiling/Mirror device methods."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from unittest.mock import AsyncMock

import pytest

from lifx.color import HSBK
from lifx.devices.base import (
    CollectionInfo,
    DeviceCapabilities,
    DeviceVersion,
    FirmwareInfo,
)
from lifx.devices.ceiling import CeilingLight, CeilingLightState
from lifx.devices.component.state import WRITE_SETTLE_MARGIN
from lifx.devices.matrix import MatrixLightState, TileInfo
from lifx.devices.mirror import MirrorLight, MirrorLightState
from lifx.exceptions import LifxError, LifxTimeoutError
from lifx.products import get_mirror_layout
from lifx.protocol import packets
from lifx.protocol.base import Packet

RED = HSBK(0, 1, 0.7, 3500)
BLUE = HSBK(240, 1, 0.4, 3500)
GREEN = HSBK(120, 1, 0.6, 3500)
DARK = HSBK(0, 1, 0, 3500)


@dataclass
class Wire:
    """Deterministic packet peer; device methods and state logic stay real."""

    width: int
    height: int
    colours: list[HSBK]
    power: int = 65535
    packets: list[Packet] = field(default_factory=list)
    before: Callable[[Packet], Awaitable[None]] | None = None
    buffers: dict[int, list[HSBK]] = field(default_factory=dict)

    async def exchange(self, packet: Packet, **_kwargs):
        self.packets.append(packet)
        if self.before is not None:
            await self.before(packet)
        if isinstance(packet, packets.Tile.Get64):
            rect = packet.rect
            colours = []
            for offset in range(64):
                row, column = (
                    rect.y + offset // rect.width,
                    rect.x + offset % rect.width,
                )
                colours.append(
                    self.colours[row * self.width + column]
                    if row < self.height and column < self.width
                    else DARK
                )
            return packets.Tile.State64(
                tile_index=packet.tile_index,
                rect=rect,
                colors=[c.to_protocol() for c in colours],
            )
        if isinstance(packet, packets.Light.GetPower):
            return packets.Light.StatePower(level=self.power)
        if isinstance(packet, packets.Light.SetPower):
            self.power = packet.level
        elif isinstance(packet, packets.Light.SetColor):
            self.colours[:] = [HSBK.from_protocol(packet.color)] * len(self.colours)
        elif isinstance(packet, packets.Tile.Set64):
            rect = packet.rect
            target = (
                self.colours
                if rect.fb_index == 0
                else self.buffers.setdefault(rect.fb_index, list(self.colours))
            )
            for offset, colour in enumerate(packet.colors):
                row, column = (
                    rect.y + offset // rect.width,
                    rect.x + offset % rect.width,
                )
                if row < self.height and column < self.width:
                    target[row * self.width + column] = HSBK.from_protocol(colour)
        elif isinstance(packet, packets.Tile.CopyFrameBuffer):
            self.colours[:] = self.buffers[packet.src_fb_index]
        else:
            raise AssertionError(f"Unexpected packet: {type(packet).__qualname__}")
        return packets.Device.Acknowledgement()


@dataclass
class Rig:
    light: CeilingLight | MirrorLight
    wire: Wire
    names: tuple[str, str]
    positions: tuple[tuple[int, ...], tuple[int, ...]]
    clock: list[float]

    async def on(self, side: int, colour: HSBK | None = None, duration: float = 0):
        await getattr(self.light, f"turn_{self.names[side]}_on")(colour, duration)

    async def off(self, side: int, colour: HSBK | None = None, duration: float = 0):
        await getattr(self.light, f"turn_{self.names[side]}_off")(colour, duration)

    async def read(self, side: int):
        suffix = "color" if self.names[side] == "uplight" else "colors"
        return await getattr(self.light, f"get_{self.names[side]}_{suffix}")()

    def colours(self, side: int, prefix: str = "") -> list[HSBK] | None:
        name = self.names[side]
        scalar = name == "uplight"
        value = getattr(
            self.light.state, f"{prefix}{name}_{'color' if scalar else 'colors'}"
        )
        return None if value is None else [value] if scalar else list(value)

    def external(self, side: int, colour: HSBK):
        for position in self.positions[side]:
            self.wire.colours[position] = colour

    def settle(self, duration: float = 0):
        self.clock[0] += duration + WRITE_SETTLE_MARGIN + 0.1


@pytest.fixture(params=[176, 201, 267], ids=["ceiling", "capsule", "mirror"])
def rig(request, monkeypatch) -> Rig:
    product = request.param
    clock = [100.0]
    monkeypatch.setattr("lifx.devices.component.state.time.monotonic", lambda: clock[0])
    width, height = (4, 13) if product == 267 else (16, 8) if product == 201 else (8, 8)
    colours = [RED] * (width * height)
    tile = TileInfo(0, 0, 0, 0, 0, 0, width, height, 2, 1, product, 0, 1, 0, 4)
    light = (MirrorLight if product == 267 else CeilingLight)(
        serial="d073d5000001", ip="192.0.2.1"
    )
    light._version = DeviceVersion(1, product)
    light._device_chain = [tile]
    group = CollectionInfo("00000000-0000-0000-0000-000000000000", "Synthetic", 0)
    state = MatrixLightState(
        model="Synthetic",
        label="Synthetic",
        serial=light.serial,
        mac_address="d0:73:d5:00:00:01",
        power=65535,
        capabilities=DeviceCapabilities(
            True, False, False, True, False, False, False, 1500, 9000
        ),
        host_firmware=FirmwareInfo(1, 0, 4),
        wifi_firmware=FirmwareInfo(1, 0, 4),
        location=group,
        group=group,
        color=RED,
        chain=[tile],
        tile_orientations={},
        tile_colors=list(colours),
        tile_count=1,
        effect="OFF",
        last_updated=0,
    )
    if isinstance(light, MirrorLight):
        layout = get_mirror_layout(product)
        assert layout is not None
        positions = (layout.front_positions, layout.back_positions)
        names = ("front", "back")
        light._state = MirrorLightState.from_matrix_state(
            state, [RED] * 25, [RED] * 25, *positions
        )
    else:
        positions = ((width * height - 1,), tuple(range(width * height - 1)))
        names = ("uplight", "downlight")
        light._state = CeilingLightState.from_matrix_state(
            state,
            RED,
            [RED] * (width * height - 1),
            width * height - 1,
            slice(0, width * height - 1),
        )
    wire = Wire(width, height, colours)
    light.connection = AsyncMock()
    light.connection.request.side_effect = wire.exchange
    light.connection.send_packet.side_effect = wire.exchange
    light._schedule_refresh = AsyncMock()
    return Rig(light, wire, names, positions, clock)


@pytest.mark.parametrize("side", [0, 1])
async def test_received_external_colours_replace_stale_restoration(rig: Rig, side: int):
    await rig.off(side)
    rig.settle()
    rig.external(side, BLUE)
    await rig.read(side)

    assert rig.colours(side, "last_") == [BLUE] * len(rig.positions[side])
    assert rig.colours(side) == [BLUE] * len(rig.positions[side])
    assert rig.colours(side, "stored_") == [BLUE] * len(rig.positions[side])
    await rig.on(side)
    assert [rig.wire.colours[p] for p in rig.positions[side]] == [BLUE] * len(
        rig.positions[side]
    )


@pytest.mark.parametrize("side", [0, 1])
async def test_turn_on_adopts_external_change_found_by_its_own_read(
    rig: Rig, side: int
):
    await rig.off(side)
    rig.settle()
    rig.external(side, BLUE)
    await rig.on(side)
    assert [rig.wire.colours[p] for p in rig.positions[side]] == [BLUE] * len(
        rig.positions[side]
    )


@pytest.mark.parametrize("side", [0, 1])
async def test_brightness_only_external_change_is_adopted(rig: Rig, side: int):
    await rig.off(side)
    rig.settle()
    dim_red = HSBK(RED.hue, RED.saturation, 0.2, RED.kelvin)
    rig.external(side, dim_red)
    await rig.read(side)
    await rig.on(side)
    assert rig.colours(side, "stored_") == [dim_red] * len(rig.positions[side])


@pytest.mark.parametrize("side", [0, 1])
async def test_dark_read_preserves_remembered_brightness(rig: Rig, side: int):
    await rig.off(side)
    rig.settle()
    await rig.read(side)
    assert rig.colours(side, "stored_") == [RED] * len(rig.positions[side])
    await rig.on(side)
    assert rig.colours(side) == [RED] * len(rig.positions[side])


@pytest.mark.parametrize("side", [0, 1])
async def test_external_colour_change_while_dark_keeps_restore_brightness(
    rig: Rig, side: int
):
    await rig.off(side)
    rig.settle()
    rig.external(side, HSBK(BLUE.hue, BLUE.saturation, 0, BLUE.kelvin))
    await rig.read(side)
    await rig.on(side)
    expected = HSBK(BLUE.hue, BLUE.saturation, RED.brightness, BLUE.kelvin)
    assert rig.colours(side) == [expected] * len(rig.positions[side])


@pytest.mark.parametrize("side", [0, 1])
async def test_own_fade_observation_updates_last_without_replacing_target(
    rig: Rig, side: int
):
    await rig.off(side, duration=2)
    intermediate = HSBK(RED.hue, RED.saturation, 0.3, RED.kelvin)
    rig.external(side, intermediate)  # Simulate the firmware's in-flight reply.
    await rig.read(side)
    assert rig.colours(side, "last_") == [intermediate] * len(rig.positions[side])
    assert rig.colours(side, "stored_") == [RED] * len(rig.positions[side])
    await rig.on(1 - side, BLUE, duration=1)
    assert all(rig.wire.colours[p].brightness == 0 for p in rig.positions[side])


async def test_supplied_future_colours_survive_observation_after_power_off_fade(
    rig: Rig,
):
    await rig.off(1)
    await rig.off(0, BLUE, duration=2)
    rig.settle(2)
    await rig.read(0)
    assert rig.colours(0, "stored_") == [BLUE] * len(rig.positions[0])
    await rig.on(0)
    assert rig.colours(0) == [BLUE] * len(rig.positions[0])


async def test_partial_state64_updates_only_reported_zones(rig: Rig):
    rig.wire.colours[:] = [BLUE] * len(rig.wire.colours)
    await rig.light.get64(x=1, y=1, width=2)
    reported = {
        (1 + i // 2) * rig.wire.width + 1 + i % 2
        for i in range(64)
        if 1 + i // 2 < rig.wire.height
    }
    for side in (0, 1):
        expected = [BLUE if p in reported else RED for p in rig.positions[side]]
        assert rig.colours(side, "last_") == expected
        assert rig.colours(side) == expected
    assert rig.light.state.tile_colors == [
        BLUE if p in reported else RED for p in range(len(rig.wire.colours))
    ]


async def test_two_overlapping_operations_keep_both_changes(rig: Rig):
    entered, release, second_started = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def pause_first_write(packet):
        if isinstance(packet, packets.Tile.Set64) and not entered.is_set():
            entered.set()
            await release.wait()

    async def second_call():
        second_started.set()
        await rig.on(1, GREEN)

    rig.wire.before = pause_first_write
    first = asyncio.create_task(rig.on(0, BLUE))
    await entered.wait()
    second = asyncio.create_task(second_call())
    await second_started.wait()
    # A second read here would compose from the pre-write tile and lose blue.
    assert sum(isinstance(p, packets.Tile.Get64) for p in rig.wire.packets) == (
        2 if rig.wire.height * rig.wire.width > 64 else 1
    )
    release.set()
    await asyncio.gather(first, second)
    assert [rig.wire.colours[p] for p in rig.positions[0]] == [BLUE] * len(
        rig.positions[0]
    )
    assert [rig.wire.colours[p] for p in rig.positions[1]] == [GREEN] * len(
        rig.positions[1]
    )


async def test_uniform_tile_shortcut_does_not_deadlock_or_overwrite_restoration(
    rig: Rig,
):
    await rig.on(0, RED)
    await rig.on(1, RED)
    assert any(isinstance(p, packets.Light.SetColor) for p in rig.wire.packets)
    assert rig.colours(0, "stored_") == [RED] * len(rig.positions[0])


@pytest.mark.parametrize("cancel", [False, True], ids=["failure", "cancellation"])
async def test_power_off_progress_survives_failed_second_write(rig: Rig, cancel: bool):
    await rig.off(1)
    error = asyncio.CancelledError() if cancel else RuntimeError("write failed")

    async def fail_tile(packet):
        if isinstance(packet, (packets.Tile.Set64, packets.Light.SetColor)):
            raise error

    rig.wire.before = fail_tile
    with pytest.raises(type(error)):
        await rig.off(0, BLUE)
    assert rig.light.state.power == 0
    assert getattr(rig.light.state, f"{rig.names[0]}_is_on") is False
    assert rig.colours(0) == [RED] * len(rig.positions[0])
    rig.wire.before = None
    await rig.on(0, GREEN)
    assert rig.light.state.power == 65535
    assert rig.colours(0) == [GREEN] * len(rig.positions[0])


async def test_preloaded_colours_survive_failed_power_on(rig: Rig):
    await rig.light.set_power(False)

    async def fail_power(packet):
        if isinstance(packet, packets.Light.SetPower):
            raise RuntimeError("power write failed")

    rig.wire.before = fail_power
    with pytest.raises(RuntimeError, match="power write failed"):
        await rig.on(0, BLUE)
    assert rig.colours(0) == [BLUE] * len(rig.positions[0])
    assert rig.colours(0, "stored_") == [BLUE] * len(rig.positions[0])
    assert rig.light.state.power == 0
    rig.wire.before = None
    await rig.on(0)
    assert rig.light.state.power == 65535


async def test_timeout_does_not_publish_uncertain_write_as_success(rig: Rig):
    async def lose_reply(packet):
        if isinstance(packet, packets.Light.SetColor):
            rig.wire.colours[:] = [BLUE] * len(rig.wire.colours)
            raise LifxTimeoutError("reply lost after device applied colour")

    rig.wire.before = lose_reply
    with pytest.raises(LifxTimeoutError):
        await rig.light.set_color(BLUE)
    assert rig.colours(0) == [RED] * len(rig.positions[0])
    rig.wire.before = None
    await rig.read(0)
    assert rig.colours(0) == [BLUE] * len(rig.positions[0])


async def test_cancelled_waiter_does_not_release_other_operations_lock(rig: Rig):
    entered, release = asyncio.Event(), asyncio.Event()

    async def pause_write(packet):
        if isinstance(packet, packets.Tile.Set64) and not entered.is_set():
            entered.set()
            await release.wait()

    rig.wire.before = pause_write
    first = asyncio.create_task(rig.on(0, BLUE))
    await entered.wait()
    waiter = asyncio.create_task(rig.on(1, GREEN))
    await asyncio.sleep(0)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    release.set()
    await first
    await rig.on(1, GREEN)
    assert rig.colours(0) == [BLUE] * len(rig.positions[0])
    assert rig.colours(1) == [GREEN] * len(rig.positions[1])


async def test_inference_with_supplied_snapshot_only_updates_last_fields(rig: Rig):
    snapshot = [BLUE] * len(rig.wire.colours)
    for position in rig.positions[0]:
        snapshot[position] = DARK
    result = await rig.light._determine_component_brightness(rig.names[0], snapshot)
    expected = HSBK(DARK.hue, DARK.saturation, BLUE.brightness, DARK.kelvin)
    assert result == [expected] * len(rig.positions[0])
    assert rig.colours(0) == [RED] * len(rig.positions[0])
    assert rig.colours(0, "last_") == [DARK] * len(rig.positions[0])
    assert rig.colours(0, "stored_") is None


async def test_partial_read_preserves_unreported_last_tracking(rig: Rig):
    snapshot = [GREEN] * len(rig.wire.colours)
    await rig.light._determine_component_brightness(rig.names[0], snapshot)
    rig.wire.colours[:] = [BLUE] * len(rig.wire.colours)
    await rig.light.get64(x=1, y=1, width=2)
    reported = {
        (1 + i // 2) * rig.wire.width + 1 + i % 2
        for i in range(64)
        if 1 + i // 2 < rig.wire.height
    }
    for side in (0, 1):
        assert rig.colours(side, "last_") == [
            BLUE if p in reported else GREEN for p in rig.positions[side]
        ]
        assert rig.colours(side) == [
            BLUE if p in reported else RED for p in rig.positions[side]
        ]


@pytest.mark.parametrize("whole", ["colour", "power"])
async def test_whole_light_change_waits_for_shared_state_operation(
    rig: Rig, whole: str
):
    entered, release, next_started = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def pause_write(packet):
        if isinstance(packet, packets.Tile.Set64) and not entered.is_set():
            entered.set()
            await release.wait()

    async def whole_change():
        next_started.set()
        if whole == "colour":
            await rig.light.set_color(GREEN)
        else:
            await rig.light.set_power(False)

    rig.wire.before = pause_write
    first = asyncio.create_task(rig.on(0, BLUE))
    await entered.wait()
    second = asyncio.create_task(whole_change())
    await next_started.wait()
    assert not any(
        isinstance(p, (packets.Light.SetPower, packets.Light.SetColor))
        for p in rig.wire.packets
    )
    release.set()
    await asyncio.gather(first, second)
    if whole == "colour":
        assert rig.wire.colours == [GREEN] * len(rig.wire.colours)
    else:
        assert rig.light.state.power == 0
        assert rig.colours(0, "stored_") == [BLUE] * len(rig.positions[0])


@pytest.mark.parametrize("side", [0, 1])
async def test_received_colours_reconcile_loaded_restoration(
    rig: Rig, tmp_path, side: int
):
    # Persistence remains in the real adapters, including the existing schema.
    rig.light._state_file = str(tmp_path / "synthetic-state.json")
    await rig.off(side)
    for name in rig.names:
        suffix = "color" if name == "uplight" else "colors"
        setattr(rig.light.state, f"stored_{name}_{suffix}", None)
    await rig.light._load_state_from_file()
    assert rig.colours(side, "stored_") == [RED] * len(rig.positions[side])
    rig.settle()
    rig.external(side, BLUE)
    await rig.read(side)
    await rig.on(side)
    assert rig.colours(side) == [BLUE] * len(rig.positions[side])


@pytest.mark.parametrize("side", [0, 1])
async def test_external_darkness_preserves_all_zones_across_response_chunks(
    rig: Rig, side: int
):
    await rig.light.set_color(RED)
    rig.settle()
    rig.external(side, DARK)
    await rig.read(side)
    assert rig.colours(side, "stored_") == [RED] * len(rig.positions[side])
    await rig.on(side)
    assert [rig.wire.colours[p] for p in rig.positions[side]] == [RED] * len(
        rig.positions[side]
    )


async def test_mixed_external_pattern_preserves_intentional_dark_zones(
    rig: Rig,
):
    split = min(64, len(rig.positions[1]) - 1)
    await rig.light.set_color(RED)
    rig.settle()
    for index, position in enumerate(rig.positions[1]):
        rig.wire.colours[position] = DARK if index < split else BLUE
    await rig.read(1)
    expected = [
        DARK if index < split else BLUE for index in range(len(rig.positions[1]))
    ]
    assert rig.colours(1, "stored_") == expected
    await rig.on(1)
    assert [rig.wire.colours[p] for p in rig.positions[1]] == expected


async def test_short_tile_is_rejected_before_a_component_write(rig: Rig):
    rig.light.get_all_tile_colors = AsyncMock(return_value=[[RED]])
    with pytest.raises(LifxError, match="too few for the component layout"):
        await rig.on(0, BLUE)
    assert not any(
        isinstance(p, (packets.Tile.Set64, packets.Light.SetColor))
        for p in rig.wire.packets
    )


async def test_component_write_preserves_other_and_unused_buffer_positions(rig: Rig):
    occupied = set(rig.positions[0]) | set(rig.positions[1])
    for position in range(len(rig.wire.colours)):
        if position not in occupied:
            rig.wire.colours[position] = GREEN
    before = list(rig.wire.colours)
    await rig.on(0, BLUE)
    untouched = set(range(len(before))) - set(rig.positions[0])
    assert [rig.wire.colours[p] for p in untouched] == [before[p] for p in untouched]


async def test_component_fade_rides_on_the_write_that_reaches_the_display(rig: Rig):
    await rig.on(0, BLUE, duration=2)
    displayed = [
        p
        for p in rig.wire.packets
        if (isinstance(p, packets.Tile.Set64) and p.rect.fb_index == 0)
        or (isinstance(p, packets.Tile.CopyFrameBuffer) and p.dst_fb_index == 0)
    ]
    hidden = [
        p
        for p in rig.wire.packets
        if isinstance(p, packets.Tile.Set64) and p.rect.fb_index != 0
    ]
    assert [p.duration for p in displayed] == [2000]
    assert all(p.duration == 0 for p in hidden)


@pytest.mark.parametrize("delivered", [False, True])
async def test_retry_power_on_during_pending_power_off(rig: Rig, delivered: bool):
    await rig.off(1)
    await rig.off(0, duration=10)
    rig.wire.power = 65535  # Firmware reports old power during the fade.

    async def lose_power_reply(packet):
        if isinstance(packet, packets.Light.SetPower):
            if delivered:
                rig.wire.power = packet.level
            raise LifxTimeoutError("power reply lost")

    rig.wire.before = lose_power_reply
    with pytest.raises(LifxTimeoutError):
        await rig.on(1)
    rig.wire.before = None
    rig.wire.packets.clear()
    await rig.on(1)
    assert any(
        isinstance(p, packets.Light.SetPower) and p.level == 65535
        for p in rig.wire.packets
    )


@pytest.mark.parametrize("partial", ["standalone", "expiry"])
async def test_full_read_reconciles_after_incomplete_observation(
    rig: Rig, partial: str
):
    if rig.wire.width != 16:
        return
    await rig.off(1)
    if partial == "standalone":
        rig.settle()
        await rig.light.get64(y=4)
    else:

        async def expire_between_chunks(packet):
            if isinstance(packet, packets.Tile.Get64) and packet.rect.y == 4:
                rig.settle()

        rig.wire.before = expire_between_chunks
        await rig.light.get_all_tile_colors()
        rig.wire.before = None
    rig.external(1, BLUE)
    await rig.on(1)
    assert [rig.wire.colours[p] for p in rig.positions[1]] == [BLUE] * len(
        rig.positions[1]
    )


async def test_later_read_preserves_returned_snapshot(rig: Rig):
    snapshot = await rig.light.get64()
    expected = list(snapshot)
    rig.wire.colours[:] = [BLUE] * len(rig.wire.colours)
    await rig.light.get64()
    assert snapshot == expected


def test_unknown_component_has_clear_error(rig: Rig):
    with pytest.raises(ValueError, match="Unknown light component: unknown"):
        rig.light._fields("unknown")


async def test_writes_can_complete_before_component_state_initialisation(rig: Rig):
    rig.light._state = None
    await rig.light._write_tile([BLUE] * len(rig.wire.colours), 0)
    await rig.light._write_power(True, 0)
    rig.light._update_component_flags()
    assert rig.light._state is None
    assert rig.wire.colours == [BLUE] * len(rig.wire.colours)
    assert rig.wire.power == 65535


@pytest.mark.parametrize("rect", [(0, 0, 0), (-1, 0, 8), (0, -1, 8)])
def test_invalid_observation_rectangle_does_not_change_state(rig: Rig, rect):
    original = list(rig.light.state.tile_colors)
    rig.light._adopt_tile_observation(0, *rect, [BLUE] * 64)
    assert rig.light.state.tile_colors == original
    assert rig.colours(1) == [RED] * len(rig.positions[1])


async def test_read_fills_missing_last_colours_and_tile_snapshot(rig: Rig):
    fields = rig.light._fields(rig.names[1])
    setattr(rig.light.state, "last_" + fields.colours, None)
    rig.light.state.tile_colors = []
    rig.external(1, BLUE)
    await rig.light.get_all_tile_colors()
    assert rig.colours(1, "last_") == [BLUE] * len(rig.positions[1])
    assert rig.light.state.tile_colors == rig.wire.colours


async def test_read_during_incomplete_component_initialisation(rig: Rig):
    fields = rig.light._fields(rig.names[1])
    setattr(rig.light.state, fields.colours, [])
    rig.external(0, BLUE)
    await rig.light.get_all_tile_colors()
    assert rig.colours(0, "last_") == [BLUE] * len(rig.positions[0])
    assert rig.colours(1) == []
