"""The settle window: a capture soon after a restore returns what was restored."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.state_manager import DeviceStateManager

RED = HSBK.from_protocol(HSBK(0, 1, 1, 3500).to_protocol())
DIM_BLUE = HSBK.from_protocol(HSBK(240, 1, 0.3, 3500).to_protocol())


class _Clock:
    def __init__(self) -> None:
        self.now = 500.0

    def __call__(self) -> float:
        return self.now


class _Solid(FrameEffect):
    def __init__(self) -> None:
        super().__init__(power_on=True, fps=20.0)

    @property
    def name(self) -> str:
        return "solid"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        return [RED] * ctx.pixel_count


def _count_state_reads(light: Light) -> list[str]:
    """Record the class name of every Get packet the light sends."""
    reads: list[str] = []
    connection = light.connection
    for method in ("request", "request_stream"):
        original = getattr(connection, method)

        def wrapper(
            packet: Any, *args: Any, _original: Callable[..., Any] = original, **kw: Any
        ) -> Any:
            if type(packet).__name__.startswith("Get"):
                reads.append(type(packet).__name__)
            return _original(packet, *args, **kw)

        setattr(connection, method, wrapper)
    return reads


async def _eventually(check: Callable[[], Awaitable[bool]]) -> None:
    for _ in range(50):
        if await check():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("condition never held")


@pytest.mark.emulator
class TestSettleWindowOnTheEmulator:
    async def test_a_second_capture_inside_the_window_reads_nothing(
        self, emulator_devices
    ):
        light = emulator_devices[0]
        async with light:
            await light.set_power(True)
            await light.set_color(DIM_BLUE)
            clock = _Clock()
            manager = DeviceStateManager(clock=clock)
            first = await manager.capture_state(light)
            await manager.restore_state(light, first)
            reads = _count_state_reads(light)

            clock.now += 1.0
            second = await manager.capture_state(light)

            assert second == first
            assert reads == []

    async def test_a_second_capture_past_the_window_reads_the_device(
        self, emulator_devices
    ):
        light = emulator_devices[0]
        async with light:
            await light.set_power(True)
            await light.set_color(DIM_BLUE)
            clock = _Clock()
            manager = DeviceStateManager(clock=clock)
            await manager.restore_state(light, await manager.capture_state(light))
            reads = _count_state_reads(light)

            clock.now += 5.0
            await manager.capture_state(light)

            assert reads != []


def _strip_pattern(count: int) -> list[HSBK]:
    return [
        HSBK.from_protocol(HSBK((i * 23) % 360, 1, 0.5, 3500).to_protocol())
        for i in range(count)
    ]


async def _run_twice(light: Light) -> None:
    """Start, stop, start and stop again with no pause between the stops."""
    for _ in range(2):
        await light.start_effect(_Solid())
        await asyncio.sleep(0.4)
        await light.stop_effect()


@pytest.mark.emulator
class TestConductorCycleWithinTheWindow:
    async def test_a_multizone_light_ends_with_its_original_zones(
        self, emulator_devices
    ):
        light = emulator_devices[4]
        assert isinstance(light, MultiZoneLight)
        async with light:
            await light.set_power(True)
            count = await light.get_zone_count()
            before = _strip_pattern(count)
            await light.set_all_color_zones(before, duration=0.0)
            await asyncio.sleep(0.3)
            before = await light.get_extended_color_zones()

            await _run_twice(light)

            assert await light.get_extended_color_zones() == before

    async def test_a_matrix_light_ends_with_its_original_tiles(self, emulator_devices):
        light = emulator_devices[6]
        assert isinstance(light, MatrixLight)
        async with light:
            await light.set_power(True)
            await light.set_matrix_colors(0, _strip_pattern(64), duration=0)
            await asyncio.sleep(0.5)
            before = [list(t) for t in await light.get_all_tile_colors()]

            await _run_twice(light)

            assert [list(t) for t in await light.get_all_tile_colors()] == before
