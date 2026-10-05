"""Whole-tile prior state and power-on for matrix lights (Ceiling and Mirror)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.devices.ceiling import CeilingLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.effects.base import LIFXEffect
from lifx.effects.conductor import Conductor
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.state_manager import DeviceStateManager
from lifx.exceptions import LifxTimeoutError
from lifx.protocol import packets
from tests.test_devices import test_component_transitions as transitions

GREEN = HSBK.from_protocol(transitions.GREEN.to_protocol())
BLUE = HSBK.from_protocol(transitions.BLUE.to_protocol())


@pytest.fixture(params=[176, 201, 267], ids=["ceiling", "capsule", "mirror"])
def component_rig(request, monkeypatch) -> transitions.Rig:
    # The rig freezes time.monotonic, so settle delays must not use the timer.
    for module in ("state_manager", "base"):
        for name in (
            "COLOR_UPDATE_SETTLE_DELAY",
            "ZONE_UPDATE_SETTLE_DELAY",
            "POWER_ON_SETTLE_DELAY",
        ):
            monkeypatch.setattr(f"lifx.effects.{module}.{name}", 0, raising=False)
    return transitions.build_rig(request.param, monkeypatch)


def _pattern(count: int) -> list[HSBK]:
    """A tile no single colour can reproduce."""
    return [
        HSBK.from_protocol(HSBK((i * 7) % 360, 1, 0.5, 3500).to_protocol())
        for i in range(count)
    ]


async def test_restore_writes_back_the_whole_tile(component_rig: transitions.Rig):
    rig = component_rig
    before = _pattern(len(rig.wire.colours))
    rig.wire.colours[:] = before
    await rig.read(0)
    await rig.read(1)
    stored = _stored(rig)
    manager = DeviceStateManager()

    prestate = await manager.capture_state(rig.light)
    rig.wire.colours[:] = [GREEN] * len(before)
    await manager.restore_state(rig.light, prestate)

    assert rig.wire.colours == before
    assert rig.wire.power == 65535
    assert _stored(rig) == stored


class _HoldEffect(LIFXEffect):
    """Software effect that runs until stopped, drawing nothing itself."""

    def __init__(self, power_on: bool = True) -> None:
        super().__init__(power_on=power_on)
        self.playing = asyncio.Event()

    @property
    def name(self) -> str:
        return "hold"

    async def async_play(self) -> None:
        self.playing.set()
        await asyncio.Event().wait()


def _stored(rig: transitions.Rig) -> tuple[list[HSBK] | None, list[HSBK] | None]:
    return rig.colours(0, "stored_"), rig.colours(1, "stored_")


async def _run_effect(
    rig: transitions.Rig, during: Callable[[], Awaitable[None]] | None = None
) -> None:
    """Start a whole-light effect, optionally act mid-effect, then stop it."""
    conductor = Conductor()
    effect = _HoldEffect()
    await conductor.start(effect, [rig.light])
    await asyncio.wait_for(effect.playing.wait(), 1)
    if during is not None:
        await during()
    await conductor.stop([rig.light])


async def test_stored_colours_survive_an_effect_on_a_light_that_was_off(
    component_rig: transitions.Rig,
):
    """Both sides were turned off, so stored colours differ from the dark tile."""
    rig = component_rig
    await rig.on(0, GREEN)
    await rig.on(1, BLUE)
    rig.settle()
    await rig.off(1)
    rig.settle()
    await rig.off(0)
    rig.settle()
    before = _stored(rig)
    tile = list(rig.wire.colours)
    assert rig.wire.power == 0

    await _run_effect(rig)

    assert _stored(rig) == before
    assert rig.wire.colours == tile
    assert rig.wire.power == 0


async def test_stored_colours_ignore_effect_frames_read_mid_effect(
    component_rig: transitions.Rig,
):
    """A tile read while the effect runs reports frames, not colours to keep."""
    rig = component_rig
    before_tile = _pattern(len(rig.wire.colours))
    rig.wire.colours[:] = before_tile
    await rig.read(0)
    await rig.read(1)
    before = _stored(rig)

    async def frames_then_read() -> None:
        rig.wire.colours[:] = [GREEN] * len(before_tile)
        rig.settle()
        await rig.read(0)
        await rig.read(1)

    await _run_effect(rig, frames_then_read)

    assert _stored(rig) == before
    assert rig.wire.colours == before_tile
    assert rig.wire.power == 65535
    for side in (0, 1):
        reported = await rig.read(side)
        if isinstance(reported, HSBK):
            reported = [reported]
        assert reported == [before_tile[p] for p in rig.positions[side]]


async def test_effect_powers_an_off_light_on_without_a_colour_write(
    component_rig: transitions.Rig,
):
    rig = component_rig
    await rig.on(0, GREEN)
    await rig.on(1, BLUE)
    rig.settle()
    await rig.light.set_power(False)
    rig.settle()
    before = _stored(rig)
    tile = list(rig.wire.colours)
    rig.wire.packets.clear()

    async def check_powered_on() -> None:
        assert rig.wire.power == 65535
        assert rig.wire.colours == tile
        assert _stored(rig) == before
        assert not any(
            isinstance(packet, (packets.Light.SetColor, packets.Tile.Set64))
            for packet in rig.wire.packets
        )

    await _run_effect(rig, check_powered_on)

    assert _stored(rig) == before
    assert rig.wire.power == 0


class _SolidFrames(FrameEffect):
    """Frame effect painting every pixel one colour."""

    def __init__(self, colour: HSBK) -> None:
        super().__init__(power_on=True, fps=20.0)
        self.colour = colour

    @property
    def name(self) -> str:
        return "solid"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        return [self.colour] * ctx.pixel_count


async def _eventually(check: Callable[[], Awaitable[bool]]) -> None:
    for _ in range(50):
        if await check():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("condition never held")


def _ceiling_stored(ceiling: CeilingLight) -> tuple[object, object]:
    return ceiling.state.stored_uplight_color, ceiling.state.stored_downlight_colors


@pytest.mark.emulator
class TestEmulatedWholeLightEffects:
    """Observe the light itself after a real effect run on the emulator."""

    async def test_matrix_light_gets_its_whole_tile_back(self, emulator_devices):
        matrix = emulator_devices[6]
        async with matrix:
            await matrix.set_power(True)
            before = _pattern(64)
            await matrix.set_matrix_colors(0, before)
            conductor = Conductor()

            await conductor.start(_SolidFrames(GREEN), [matrix])

            async def showing_frames() -> bool:
                return (await matrix.get_all_tile_colors())[0] == [GREEN] * 64

            await _eventually(showing_frames)
            await conductor.stop([matrix])

            assert (await matrix.get_all_tile_colors())[0] == before
            assert await matrix.get_power() == 65535

    async def test_ceiling_components_unchanged_after_effect(
        self, ceiling_device: CeilingLight
    ):
        ceiling = ceiling_device
        async with ceiling:
            await ceiling.set_power(True)
            downlight = _pattern(127)
            await ceiling.set_uplight_color(BLUE)
            await ceiling.set_downlight_colors(downlight)
            await asyncio.sleep(0.6)  # let the pending write settle
            tile = (await ceiling.get_all_tile_colors())[0]
            uplight = await ceiling.get_uplight_color()
            stored = _ceiling_stored(ceiling)
            conductor = Conductor()

            await conductor.start(_SolidFrames(GREEN), [ceiling])

            async def showing_frames() -> bool:
                return (await ceiling.get_all_tile_colors())[0] == [GREEN] * 128

            await _eventually(showing_frames)
            await conductor.stop([ceiling])

            assert (await ceiling.get_all_tile_colors())[0] == tile
            assert await ceiling.get_downlight_colors() == downlight
            assert await ceiling.get_uplight_color() == uplight
            assert await ceiling.get_power() == 65535
            assert _ceiling_stored(ceiling) == stored

    async def test_ceiling_that_was_off_keeps_stored_colours(
        self, ceiling_device: CeilingLight
    ):
        ceiling = ceiling_device
        async with ceiling:
            await ceiling.set_power(True)
            await ceiling.turn_uplight_on(BLUE)
            await ceiling.turn_downlight_on(GREEN)
            await ceiling.turn_downlight_off()
            await ceiling.turn_uplight_off()
            await asyncio.sleep(0.6)
            assert await ceiling.get_power() == 0
            stored = _ceiling_stored(ceiling)
            tile = (await ceiling.get_all_tile_colors())[0]
            conductor = Conductor()
            red = HSBK(0, 1, 1, 3500)

            await conductor.start(_SolidFrames(red), [ceiling])

            async def powered_and_showing_frames() -> bool:
                return (
                    await ceiling.get_power() == 65535
                    and (await ceiling.get_all_tile_colors())[0]
                    == [HSBK.from_protocol(red.to_protocol())] * 128
                )

            await _eventually(powered_and_showing_frames)
            await conductor.stop([ceiling])

            assert await ceiling.get_power() == 0
            assert (await ceiling.get_all_tile_colors())[0] == tile
            assert _ceiling_stored(ceiling) == stored


def _mock_matrix() -> MagicMock:
    light = MagicMock(spec=MatrixLight)
    light.serial = "d073d5000001"
    light.get_color = AsyncMock(return_value=(GREEN, 65535, "Matrix"))
    light.get_all_tile_colors = AsyncMock(return_value=[_pattern(64)])
    light.set_matrix_colors = AsyncMock()
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()
    return light


async def test_unreadable_tile_falls_back_to_one_colour(caplog):
    light = _mock_matrix()
    light.get_all_tile_colors.side_effect = LifxTimeoutError("no reply")
    manager = DeviceStateManager()

    prestate = await manager.capture_state(light)
    await manager.restore_state(light, prestate)

    assert prestate.tile_colors is None
    light.set_matrix_colors.assert_not_called()
    light.set_color.assert_awaited_once_with(GREEN, duration=0.0)
    light.set_power.assert_awaited_once_with(True, duration=0.0)
    assert "_capture_tiles" in caplog.text


async def test_failed_tile_restore_still_restores_power(caplog):
    light = _mock_matrix()
    light.set_matrix_colors.side_effect = LifxTimeoutError("no reply")
    manager = DeviceStateManager()

    prestate = await manager.capture_state(light)
    await manager.restore_state(light, prestate)

    light.set_color.assert_not_called()
    light.set_power.assert_awaited_once_with(True, duration=0.0)
    assert "_restore_tiles" in caplog.text


async def test_component_light_without_state_restores_tile_and_power():
    ceiling = CeilingLight(serial="d073d5000001", ip="192.0.2.1")
    ceiling.get_color = AsyncMock(return_value=(GREEN, 0, "Ceiling"))
    tile = _pattern(64)
    ceiling.get_all_tile_colors = AsyncMock(return_value=[tile])
    ceiling.set_matrix_colors = AsyncMock()
    ceiling.set_power = AsyncMock()
    manager = DeviceStateManager()

    prestate = await manager.capture_state(ceiling)
    await manager.restore_state(ceiling, prestate)

    assert prestate.stored_colors is None
    ceiling.set_matrix_colors.assert_awaited_once_with(0, tile, duration=0)
    ceiling.set_power.assert_awaited_once_with(False, duration=0.0)


async def test_non_matrix_light_still_gets_a_startup_colour():
    light = MagicMock(spec=Light)
    light.get_power = AsyncMock(return_value=False)
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()
    effect = _HoldEffect()
    effect.async_play = AsyncMock()

    await effect.async_perform([light])

    light.set_color.assert_awaited_once()
    assert light.set_color.await_args.args[0].brightness == 0
    light.set_power.assert_awaited_once()


async def test_components_without_stored_colours_stay_without(
    component_rig: transitions.Rig,
):
    """Restoring a uniform tile goes through SetColor, which remembers colours."""
    rig = component_rig
    assert _stored(rig) == (None, None)

    await _run_effect(rig)

    assert any(isinstance(p, packets.Light.SetColor) for p in rig.wire.packets)
    assert _stored(rig) == (None, None)
