"""Software effects on one light component of a Ceiling."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from lifx.color import HSBK
from lifx.devices.ceiling import CeilingLight
from lifx.effects import EffectPulse
from lifx.effects.conductor import Conductor
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.models import PreState
from lifx.effects.registry import get_effect_registry
from lifx.effects.state_manager import DeviceStateManager
from lifx.exceptions import LifxError, LifxTimeoutError
from tests.test_devices.test_component_transitions import build_rig

RED = HSBK.from_protocol(HSBK(0, 1, 1, 3500).to_protocol())
GREEN = HSBK.from_protocol(HSBK(120, 1, 1, 3500).to_protocol())
WHITE = HSBK.from_protocol(HSBK(0, 0, 1, 4000).to_protocol())
DIM_BLUE = HSBK.from_protocol(HSBK(240, 1, 0.3, 3500).to_protocol())
AMBER = HSBK.from_protocol(HSBK(40, 0.8, 0.6, 2700).to_protocol())

UPLIGHT = 127
DOWNLIGHT = 127  # zones 0-126 of the 16x8 tile


class _SolidFrames(FrameEffect):
    """Frame effect painting every pixel one colour, recording each context."""

    def __init__(self, colour: HSBK) -> None:
        super().__init__(power_on=True, fps=20.0)
        self.colour = colour
        self.contexts: list[FrameContext] = []

    @property
    def name(self) -> str:
        return "solid"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        self.contexts.append(ctx)
        return [self.colour] * ctx.pixel_count


async def _eventually(check: Callable[[], Awaitable[bool]]) -> None:
    for _ in range(50):
        if await check():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("condition never held")


async def _tile(ceiling: CeilingLight) -> list[HSBK]:
    return (await ceiling.get_all_tile_colors())[0]


async def _prepare(ceiling: CeilingLight) -> None:
    """Both components lit in known colours, settled."""
    await ceiling.stop_effect()
    await ceiling.set_power(True)
    await ceiling.set_uplight_color(DIM_BLUE)
    await ceiling.set_downlight_colors([GREEN] * DOWNLIGHT)
    await asyncio.sleep(0.6)  # let the pending write settle


@pytest.mark.emulator
class TestCeilingComponentEffects:
    async def test_components_offer_effects_beside_the_existing_methods(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            uplight, downlight = ceiling.uplight, ceiling.downlight

            assert ceiling.uplight is uplight
            assert ceiling.downlight is downlight
            for component in (uplight, downlight):
                assert callable(component.start_effect)
                assert callable(component.stop_effect)
                assert component.animator is ceiling.animator

            await ceiling.set_uplight_color(AMBER)
            assert await ceiling.get_uplight_color() == AMBER
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT

    async def test_a_downlight_effect_draws_the_grid_and_leaves_the_uplight(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            effect = _SolidFrames(RED)

            await ceiling.downlight.start_effect(effect)

            async def downlight_red() -> bool:
                return (await _tile(ceiling))[:DOWNLIGHT] == [RED] * DOWNLIGHT

            await _eventually(downlight_red)
            assert (await _tile(ceiling))[UPLIGHT] == DIM_BLUE
            ctx = effect.contexts[-1]
            assert (ctx.canvas_width, ctx.canvas_height) == (16, 8)
            assert ctx.pixel_count == 128

            await ceiling.downlight.stop_effect()

            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT
            assert await ceiling.get_uplight_color() == DIM_BLUE

    async def test_an_uplight_effect_draws_one_pixel(self, ceiling_device):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            effect = _SolidFrames(RED)

            await ceiling.uplight.start_effect(effect)

            async def uplight_red() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == RED

            await _eventually(uplight_red)
            assert (await _tile(ceiling))[:DOWNLIGHT] == [GREEN] * DOWNLIGHT
            ctx = effect.contexts[-1]
            assert (ctx.pixel_count, ctx.canvas_width, ctx.canvas_height) == (1, 1, 1)

            await ceiling.uplight.stop_effect()

            assert await ceiling.get_uplight_color() == DIM_BLUE

    async def test_the_idle_component_stays_under_the_callers_control(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            effect = _SolidFrames(RED)
            await ceiling.downlight.start_effect(effect)

            async def downlight_red() -> bool:
                return (await _tile(ceiling))[:DOWNLIGHT] == [RED] * DOWNLIGHT

            await _eventually(downlight_red)

            await ceiling.set_uplight_color(AMBER)

            async def uplight_amber() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == AMBER

            await _eventually(uplight_amber)
            for _ in range(10):  # later frames keep it
                tile = await _tile(ceiling)
                assert tile[UPLIGHT] == AMBER
                assert tile[:DOWNLIGHT] == [RED] * DOWNLIGHT
                await asyncio.sleep(0.05)

            await ceiling.turn_uplight_off()

            async def uplight_dark() -> bool:
                return (await _tile(ceiling))[UPLIGHT].brightness == 0

            await _eventually(uplight_dark)
            assert not ceiling.uplight_is_on
            assert (await ceiling.get_power()) == 65535
            assert (await _tile(ceiling))[:DOWNLIGHT] == [RED] * DOWNLIGHT

            await ceiling.turn_uplight_on()
            await _eventually(uplight_amber)

            await ceiling.downlight.stop_effect()

            assert await ceiling.get_uplight_color() == AMBER
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT
            assert ceiling.state.stored_uplight_color == AMBER

    async def test_the_animating_component_refuses_its_own_methods(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.downlight.start_effect(_SolidFrames(RED))

            with pytest.raises(LifxError, match="downlight"):
                await ceiling.set_downlight_colors(WHITE)
            with pytest.raises(LifxError, match="downlight"):
                await ceiling.turn_downlight_off()

            await ceiling.downlight.stop_effect()
            await ceiling.set_downlight_colors(WHITE)
            assert await ceiling.get_downlight_colors() == [WHITE] * DOWNLIGHT

    async def test_stopping_the_light_stops_its_component_effects(self, ceiling_device):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            effect = _SolidFrames(RED)
            await ceiling.downlight.start_effect(effect)

            await ceiling.stop_effect()

            assert effect.participants == []
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT

    async def test_a_conductor_runs_and_stops_a_component(self, ceiling_device):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            effect = _SolidFrames(RED)
            conductor = Conductor()

            await conductor.start(effect, [ceiling.uplight])

            assert conductor.effect(ceiling.uplight) is effect
            assert conductor.effect(ceiling) is None
            assert conductor.effect(ceiling.downlight) is None

            async def uplight_red() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == RED

            await _eventually(uplight_red)
            assert conductor.get_last_frame(ceiling.uplight) == [RED]

            await conductor.stop([ceiling.uplight])

            assert conductor.effect(ceiling.uplight) is None
            assert await ceiling.get_uplight_color() == DIM_BLUE


async def test_a_component_takes_frame_effects_only():
    ceiling = CeilingLight(serial="d073d5000176", ip="192.0.2.10")

    with pytest.raises(TypeError, match="frame"):
        await ceiling.uplight.start_effect(EffectPulse())


async def test_a_conductor_leaves_out_a_component_for_an_effect_without_frames():
    ceiling = CeilingLight(serial="d073d5000176", ip="192.0.2.10")
    conductor = Conductor()

    await conductor.start(EffectPulse(), [ceiling.downlight])

    assert conductor.effect(ceiling.downlight) is None


@pytest.mark.parametrize("shape", [(1, 1), (16, 8)], ids=["uplight", "downlight"])
def test_every_frame_effect_draws_on_both_component_shapes(shape):
    width, height = shape
    for info in get_effect_registry().effects:
        effect = info.effect_class()
        if not isinstance(effect, FrameEffect):
            continue
        for elapsed in (0.0, 0.5, 3.0):
            frame = effect.generate_frame(
                FrameContext(
                    elapsed_s=elapsed,
                    device_index=0,
                    pixel_count=width * height,
                    canvas_width=width,
                    canvas_height=height,
                )
            )
            assert len(frame) == width * height, info.name


async def test_a_component_restore_without_a_captured_tile_restores_power(
    monkeypatch: pytest.MonkeyPatch,
):
    rig = build_rig(176, monkeypatch)
    before = list(rig.wire.colours)

    await DeviceStateManager().restore_component(
        rig.light, "uplight", PreState(power=False, color=RED)
    )

    assert rig.wire.power == 0
    assert rig.wire.colours == before


async def test_a_failed_component_restore_is_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    rig = build_rig(176, monkeypatch)
    rig.light.connection.request.side_effect = LifxTimeoutError("no reply")

    await DeviceStateManager().restore_component(
        rig.light,
        "uplight",
        PreState(power=True, color=RED, tile_colors=[[RED] * 64]),
    )

    assert "restore_component" in caplog.text
