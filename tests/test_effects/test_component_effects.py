"""Software effects on one light component of a Ceiling."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

from lifx.color import HSBK
from lifx.devices.ceiling import CeilingLight
from lifx.effects import EffectPulse
from lifx.effects.conductor import Conductor
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.models import PreState
from lifx.effects.registry import get_effect_registry
from lifx.effects.state_manager import DeviceStateManager
from lifx.exceptions import LifxTimeoutError
from tests.test_devices.test_component_transitions import Rig, build_rig

RED = HSBK.from_protocol(HSBK(0, 1, 1, 3500).to_protocol())
GREEN = HSBK.from_protocol(HSBK(120, 1, 1, 3500).to_protocol())
WHITE = HSBK.from_protocol(HSBK(0, 0, 1, 4000).to_protocol())
DIM_BLUE = HSBK.from_protocol(HSBK(240, 1, 0.3, 3500).to_protocol())
AMBER = HSBK.from_protocol(HSBK(40, 0.8, 0.6, 2700).to_protocol())

UPLIGHT = 127
DOWNLIGHT = 127  # zones 0-126 of the 16x8 tile


class _SolidFrames(FrameEffect):
    """Frame effect painting every pixel one colour, recording each context."""

    def __init__(
        self,
        colour: HSBK,
        *,
        power_on: bool = True,
        duration: float | None = None,
    ) -> None:
        super().__init__(power_on=power_on, fps=20.0, duration=duration)
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

    async def test_a_write_to_the_animating_component_stops_its_effect_first(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            conductor = Conductor()
            effect = _SolidFrames(RED)
            await conductor.start(effect, [ceiling.downlight])

            async def downlight_red() -> bool:
                return (await _tile(ceiling))[:DOWNLIGHT] == [RED] * DOWNLIGHT

            await _eventually(downlight_red)

            await ceiling.set_downlight_colors(WHITE)

            assert conductor.effect(ceiling.downlight) is None
            for _ in range(5):  # no later frame overwrites the write
                assert (await _tile(ceiling))[:DOWNLIGHT] == [WHITE] * DOWNLIGHT
                await asyncio.sleep(0.05)
            assert await ceiling.get_downlight_colors() == [WHITE] * DOWNLIGHT
            assert await ceiling.get_uplight_color() == DIM_BLUE
            assert ceiling.state.stored_downlight_colors == [WHITE] * DOWNLIGHT

    async def test_turning_the_animating_component_off_stops_its_effect_first(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            conductor = Conductor()
            await conductor.start(_SolidFrames(RED), [ceiling.uplight])

            async def uplight_red() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == RED

            await _eventually(uplight_red)

            await ceiling.turn_uplight_off()

            assert conductor.effect(ceiling.uplight) is None
            assert (await _tile(ceiling))[UPLIGHT].brightness == 0
            assert not ceiling.uplight_is_on
            assert await ceiling.get_power() == 65535
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT

            await ceiling.turn_uplight_on()

            assert await ceiling.get_uplight_color() == DIM_BLUE

    async def test_a_write_to_one_participant_leaves_the_rest_of_the_run(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            conductor = Conductor()
            effect = _SolidFrames(RED)
            await conductor.start(effect, [ceiling.uplight, ceiling.downlight])

            async def all_red() -> bool:
                return (await _tile(ceiling)) == [RED] * 128

            await _eventually(all_red)

            await ceiling.set_uplight_color(AMBER)

            assert conductor.effect(ceiling.uplight) is None
            assert conductor.effect(ceiling.downlight) is effect

            async def uplight_amber() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == AMBER

            await _eventually(uplight_amber)
            for _ in range(5):  # the downlight keeps drawing, the uplight keeps amber
                tile = await _tile(ceiling)
                assert tile[UPLIGHT] == AMBER
                assert tile[:DOWNLIGHT] == [RED] * DOWNLIGHT
                await asyncio.sleep(0.05)

            await conductor.stop([ceiling.downlight])

            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT
            assert await ceiling.get_uplight_color() == AMBER

    async def test_stopping_one_participant_leaves_the_rest_of_the_run(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            conductor = Conductor()
            effect = _SolidFrames(RED)
            await conductor.start(effect, [ceiling.uplight, ceiling.downlight])

            async def all_red() -> bool:
                return (await _tile(ceiling)) == [RED] * 128

            await _eventually(all_red)

            await conductor.stop([ceiling.uplight])

            assert conductor.effect(ceiling.uplight) is None
            assert conductor.effect(ceiling.downlight) is effect

            async def uplight_back() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == DIM_BLUE

            await _eventually(uplight_back)
            drawn = len(effect.contexts)
            for _ in range(5):  # the downlight keeps drawing, the uplight is back
                tile = await _tile(ceiling)
                assert tile[UPLIGHT] == DIM_BLUE
                assert tile[:DOWNLIGHT] == [RED] * DOWNLIGHT
                await asyncio.sleep(0.05)
            assert len(effect.contexts) > drawn

            await conductor.stop([ceiling.downlight])

            assert conductor.effect(ceiling.downlight) is None
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT
            assert await ceiling.get_uplight_color() == DIM_BLUE

    async def test_a_component_dark_before_its_effect_goes_dark_again(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.turn_downlight_off()
            effect = _SolidFrames(RED)
            await ceiling.downlight.start_effect(effect)

            async def downlight_red() -> bool:
                return (await _tile(ceiling))[:DOWNLIGHT] == [RED] * DOWNLIGHT

            await _eventually(downlight_red)

            await ceiling.downlight.stop_effect()

            tile = await _tile(ceiling)
            assert all(colour.brightness == 0 for colour in tile[:DOWNLIGHT])
            assert not ceiling.downlight_is_on
            assert ceiling.uplight_is_on
            assert await ceiling.get_power() == 65535
            assert await ceiling.get_uplight_color() == DIM_BLUE
            assert ceiling.state.stored_downlight_colors == [GREEN] * DOWNLIGHT

            await ceiling.turn_downlight_on()

            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT

    async def test_a_component_effect_on_a_light_that_is_off_lights_only_it(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.set_power(False)
            effect = _SolidFrames(RED)

            await ceiling.uplight.start_effect(effect)

            assert await ceiling.get_power() == 65535
            assert ceiling.uplight_is_on
            assert not ceiling.downlight_is_on
            assert all(
                colour.brightness == 0 for colour in (await _tile(ceiling))[:DOWNLIGHT]
            )

            async def uplight_red() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == RED

            await _eventually(uplight_red)
            for _ in range(5):  # the downlight stays dark under the frames
                tile = await _tile(ceiling)
                assert all(colour.brightness == 0 for colour in tile[:DOWNLIGHT])
                await asyncio.sleep(0.05)

            await ceiling.uplight.stop_effect()

            assert await ceiling.get_power() == 0
            assert not ceiling.uplight_is_on
            assert not ceiling.downlight_is_on
            assert ceiling.state.stored_uplight_color == DIM_BLUE
            assert ceiling.state.stored_downlight_colors == [GREEN] * DOWNLIGHT

    async def test_a_light_powered_off_by_a_restore_keeps_no_effect_frame(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.set_power(False)
            await ceiling.uplight.start_effect(_SolidFrames(RED))

            async def uplight_red() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == RED

            await _eventually(uplight_red)

            await ceiling.uplight.stop_effect()

            assert await ceiling.get_power() == 0
            assert not ceiling.uplight_is_on
            assert ceiling.state.stored_uplight_color == DIM_BLUE

            await ceiling.set_power(True)

            assert (await _tile(ceiling))[UPLIGHT] == DIM_BLUE
            assert await ceiling.get_uplight_color() == DIM_BLUE

    async def test_powering_on_after_a_restore_shows_the_whole_earlier_picture(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.set_power(False)
            await ceiling.uplight.start_effect(_SolidFrames(RED))

            async def uplight_red() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == RED

            await _eventually(uplight_red)

            await ceiling.uplight.stop_effect()

            assert await ceiling.get_power() == 0
            assert not ceiling.uplight_is_on
            assert not ceiling.downlight_is_on
            assert ceiling.state.stored_uplight_color == DIM_BLUE
            assert ceiling.state.stored_downlight_colors == [GREEN] * DOWNLIGHT

            await ceiling.set_power(True)

            tile = await _tile(ceiling)
            assert tile[UPLIGHT] == DIM_BLUE
            assert tile[:DOWNLIGHT] == [GREEN] * DOWNLIGHT
            assert ceiling.state.stored_uplight_color == DIM_BLUE
            assert ceiling.state.stored_downlight_colors == [GREEN] * DOWNLIGHT

    async def test_a_restore_that_powers_off_writes_colours_only_once_dark(
        self, ceiling_device, monkeypatch: pytest.MonkeyPatch
    ):
        """The earlier picture goes back only after the light reports off.

        Real firmware keeps reporting power on for a few hundred milliseconds
        after an acknowledged power-off. Writing the earlier colours in that
        window flashes them, so the write waits until the light is dark.
        """
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.set_power(False)
            await ceiling.uplight.start_effect(_SolidFrames(RED))

            async def uplight_red() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == RED

            await _eventually(uplight_red)

            events: list[str] = []
            real_get_power = ceiling.get_power
            still_on = [2]

            async def lagging_get_power() -> int:
                power = await real_get_power()
                if power == 0 and still_on[0]:
                    still_on[0] -= 1
                    events.append("reports on")
                    return 65535
                events.append(f"reports {power}")
                return power

            real_write_tile = ceiling._write_tile

            async def recording_write_tile(tile: list[HSBK], duration: float) -> None:
                events.append("write")
                await real_write_tile(tile, duration)

            monkeypatch.setattr(ceiling, "get_power", lagging_get_power)
            monkeypatch.setattr(ceiling, "_write_tile", recording_write_tile)

            await ceiling.uplight.stop_effect()

            last_write = len(events) - 1 - events[::-1].index("write")
            assert events[:last_write].count("reports on") == 2
            assert "reports 0" in events[:last_write]
            await ceiling.set_power(True)
            tile = await _tile(ceiling)
            assert tile[UPLIGHT] == DIM_BLUE
            assert tile[:DOWNLIGHT] == [GREEN] * DOWNLIGHT

    @pytest.mark.parametrize("failure", ["never-reports-off", "power-read-fails"])
    async def test_a_restore_writes_no_colours_unless_off_is_confirmed(
        self, ceiling_device, monkeypatch: pytest.MonkeyPatch, failure: str
    ):
        """Without a confirmed off, the earlier picture is not written."""
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.set_power(False)
            await ceiling.uplight.start_effect(_SolidFrames(RED))

            async def uplight_red() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == RED

            await _eventually(uplight_red)

            async def failing_get_power() -> int:
                if failure == "power-read-fails":
                    raise LifxTimeoutError("no reply")
                return 65535

            writes: list[list[HSBK]] = []
            real_write_tile = ceiling._write_tile

            async def recording_write_tile(tile: list[HSBK], duration: float) -> None:
                writes.append(list(tile))
                await real_write_tile(tile, duration)

            monkeypatch.setattr("lifx.devices.light.POWER_OFF_WAIT_SECONDS", 0.05)
            monkeypatch.setattr(ceiling, "get_power", failing_get_power)
            monkeypatch.setattr(ceiling, "_write_tile", recording_write_tile)

            await ceiling.uplight.stop_effect()

            assert not any(
                tile[UPLIGHT] == DIM_BLUE and tile[:DOWNLIGHT] == [GREEN] * DOWNLIGHT
                for tile in writes
            )
            assert ceiling.state.stored_uplight_color == DIM_BLUE
            assert ceiling.state.stored_downlight_colors == [GREEN] * DOWNLIGHT

    @pytest.mark.parametrize("how", ["stop_effect", "caller_write"])
    async def test_darkening_after_an_effect_keeps_the_frames_colour(
        self, ceiling_device, monkeypatch: pytest.MonkeyPatch, how: str
    ):
        """A component that goes dark after its effect keeps the frame's hue.

        Dropping only brightness keeps the firmware out of white mode; a dark
        target with saturation 0 under a saturated frame showed as a white
        flash on real hardware.
        """
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.turn_downlight_off()
            await asyncio.sleep(0.6)
            await ceiling.downlight.start_effect(_SolidFrames(RED))

            async def downlight_red() -> bool:
                return (await _tile(ceiling))[0] == RED

            await _eventually(downlight_red)

            writes: list[list[HSBK]] = []
            real_write_tile = ceiling._write_tile

            async def recording_write_tile(tile: list[HSBK], duration: float) -> None:
                writes.append(list(tile))
                await real_write_tile(tile, duration)

            monkeypatch.setattr(ceiling, "_write_tile", recording_write_tile)

            if how == "stop_effect":
                await ceiling.downlight.stop_effect()
            else:
                await ceiling.turn_downlight_off()

            darkening = [t for t in writes if t[0].brightness == 0]
            assert darkening
            for tile in darkening:
                assert (tile[0].hue, tile[0].saturation, tile[0].kelvin) == (
                    RED.hue,
                    RED.saturation,
                    RED.kelvin,
                )
            assert (await _tile(ceiling))[0].brightness == 0
            assert ceiling.state.stored_downlight_colors == [GREEN] * DOWNLIGHT

    async def test_a_restore_keeps_the_other_components_change_during_the_effect(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.set_power(False)
            await ceiling.uplight.start_effect(_SolidFrames(RED))
            await ceiling.set_downlight_colors([AMBER] * DOWNLIGHT)
            await ceiling.turn_downlight_off()

            await ceiling.uplight.stop_effect()

            assert await ceiling.get_power() == 0
            assert ceiling.state.stored_downlight_colors == [AMBER] * DOWNLIGHT

            await ceiling.set_power(True)

            tile = await _tile(ceiling)
            assert tile[UPLIGHT] == DIM_BLUE
            assert all(colour.brightness == 0 for colour in tile[:DOWNLIGHT])

    async def test_a_component_effect_without_power_on_leaves_the_light_off(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.set_power(False)

            await ceiling.uplight.start_effect(_SolidFrames(RED, power_on=False))
            await asyncio.sleep(0.2)

            assert await ceiling.get_power() == 0

            await ceiling.uplight.stop_effect()

            assert await ceiling.get_power() == 0
            assert ceiling.state.stored_uplight_color == DIM_BLUE

    async def test_a_component_effect_infers_brightness_from_the_other_side(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.turn_uplight_off()
            ceiling.state.stored_uplight_color = None
            await ceiling.set_power(False)
            ceiling.state.stored_uplight_color = None

            await ceiling.uplight.start_effect(_SolidFrames(RED))

            assert await ceiling.get_power() == 65535
            assert ceiling.state.last_uplight_color.brightness == pytest.approx(
                GREEN.brightness, abs=0.01
            )

            await ceiling.uplight.stop_effect()

            assert await ceiling.get_power() == 0

    async def test_stopping_a_component_keeps_its_stored_colour_unset(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            ceiling.state.stored_uplight_color = None
            await ceiling.uplight.start_effect(_SolidFrames(RED))

            async def uplight_red() -> bool:
                return (await _tile(ceiling))[UPLIGHT] == RED

            await _eventually(uplight_red)

            await ceiling.uplight.stop_effect()

            assert await ceiling.get_uplight_color() == DIM_BLUE
            assert ceiling.state.stored_uplight_color is None
            assert ceiling.state.stored_downlight_colors == [GREEN] * DOWNLIGHT

    async def test_a_finished_component_effect_keeps_its_stored_colour_unset(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            ceiling.state.stored_uplight_color = None
            conductor = Conductor()
            await conductor.start(_SolidFrames(RED, duration=0.3), [ceiling.uplight])

            async def finished() -> bool:
                return conductor.effect(ceiling.uplight) is None

            await _eventually(finished)

            assert await ceiling.get_uplight_color() == DIM_BLUE
            assert ceiling.state.stored_uplight_color is None
            assert ceiling.state.stored_downlight_colors == [GREEN] * DOWNLIGHT

    async def test_a_finished_effect_without_power_on_keeps_stored_colour_unset(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.set_power(False)
            ceiling.state.stored_uplight_color = None
            conductor = Conductor()
            await conductor.start(
                _SolidFrames(RED, power_on=False, duration=0.3), [ceiling.uplight]
            )

            async def finished() -> bool:
                return conductor.effect(ceiling.uplight) is None

            await _eventually(finished)

            assert await ceiling.get_power() == 0
            assert ceiling.state.stored_uplight_color is None
            assert ceiling.state.stored_downlight_colors == [GREEN] * DOWNLIGHT

    async def test_restoring_one_component_leaves_the_animating_other(
        self, ceiling_device
    ):
        ceiling = ceiling_device
        async with ceiling:
            await _prepare(ceiling)
            await ceiling.uplight.start_effect(_SolidFrames(RED))
            await ceiling.downlight.start_effect(_SolidFrames(WHITE))

            async def both_drawn() -> bool:
                tile = await _tile(ceiling)
                return tile[UPLIGHT] == RED and tile[:DOWNLIGHT] == [WHITE] * DOWNLIGHT

            await _eventually(both_drawn)

            await ceiling.downlight.stop_effect()

            async def downlight_back() -> bool:
                return (await _tile(ceiling))[:DOWNLIGHT] == [GREEN] * DOWNLIGHT

            await _eventually(downlight_back)
            for _ in range(5):  # the uplight effect carries on
                tile = await _tile(ceiling)
                assert tile[UPLIGHT] == RED
                assert tile[:DOWNLIGHT] == [GREEN] * DOWNLIGHT
                await asyncio.sleep(0.05)

            await ceiling.uplight.stop_effect()

            assert await ceiling.get_uplight_color() == DIM_BLUE
            assert await ceiling.get_downlight_colors() == [GREEN] * DOWNLIGHT

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


async def test_a_component_of_a_light_that_was_off_goes_dark_without_a_tile(
    monkeypatch: pytest.MonkeyPatch,
):
    rig = build_rig(176, monkeypatch)
    before = list(rig.wire.colours)

    await DeviceStateManager().restore_component(
        rig.light, "uplight", PreState(power=False, color=RED)
    )

    # The downlight is lit, so turning the uplight off leaves the light on.
    assert rig.wire.power == 65535
    assert rig.wire.colours[63].brightness == 0
    assert rig.wire.colours[:63] == before[:63]


async def test_a_lit_component_without_a_captured_tile_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
):
    rig = build_rig(176, monkeypatch)
    before = list(rig.wire.colours)

    await DeviceStateManager().restore_component(
        rig.light, "uplight", PreState(power=True, color=RED)
    )

    assert rig.wire.power == 65535
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


BLUE = HSBK.from_protocol(HSBK(240, 1, 1, 3500).to_protocol())
OTHER_LIGHT = {"d073d5000002": {"uplight": {"hue": 1}}}


def _saved_rig(
    product: int, monkeypatch: pytest.MonkeyPatch, state_file: Path
) -> tuple[Rig, dict[str, list[HSBK] | None]]:
    """A light with both components' stored colours saved beside another light.

    Returns the rig and a snapshot in which the first component had no
    stored colours and the second had the colours it shows.
    """
    # The rig freezes the component clock, so settle delays must not wait on it.
    for name in ("COLOR_UPDATE_SETTLE_DELAY", "ZONE_UPDATE_SETTLE_DELAY"):
        monkeypatch.setattr(f"lifx.effects.state_manager.{name}", 0)
    rig = build_rig(product, monkeypatch)
    state_file.write_text(json.dumps(OTHER_LIGHT))
    rig.light._state_file = str(state_file)
    first, second = rig.names
    shown = [rig.wire.colours[p] for p in rig.positions[1]]
    rig.light._set_stored_colors(first, [BLUE] * len(rig.positions[0]))
    rig.light._set_stored_colors(second, shown)
    return rig, {first: None, second: shown}


async def _assert_first_unset_on_disk(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, state_file: Path, product: int
) -> None:
    first, second = rig.names
    data = json.loads(state_file.read_text())
    assert data["d073d5000002"] == OTHER_LIGHT["d073d5000002"]
    assert first not in data[rig.light.serial]
    assert second in data[rig.light.serial]
    assert rig.colours(1, "stored_") == [rig.wire.colours[p] for p in rig.positions[1]]

    fresh = build_rig(product, monkeypatch)
    fresh.light._state_file = str(state_file)
    await fresh.light._load_state_from_file()
    assert fresh.colours(0, "stored_") is None
    assert fresh.colours(1, "stored_") == rig.colours(1, "stored_")


@pytest.mark.parametrize("product", [176, 267], ids=["ceiling", "mirror"])
async def test_a_component_restore_saves_its_unset_stored_colours(
    product: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    state_file = tmp_path / "state.json"
    rig, snapshot = _saved_rig(product, monkeypatch, state_file)
    await rig.light._save_state_to_file()
    tile = list(rig.wire.colours)

    await DeviceStateManager().restore_component(
        rig.light,
        rig.names[0],
        PreState(power=True, color=RED, tile_colors=[tile], stored_colors=snapshot),
    )

    assert rig.colours(0, "stored_") is None
    await _assert_first_unset_on_disk(rig, monkeypatch, state_file, product)


@pytest.mark.parametrize("product", [176, 267], ids=["ceiling", "mirror"])
async def test_a_whole_light_restore_saves_unset_stored_colours(
    product: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    state_file = tmp_path / "state.json"
    rig, snapshot = _saved_rig(product, monkeypatch, state_file)
    await rig.light._save_state_to_file()
    tile = list(rig.wire.colours)

    await DeviceStateManager().restore_state(
        rig.light,
        PreState(power=True, color=RED, tile_colors=[tile], stored_colors=snapshot),
    )

    assert rig.colours(0, "stored_") is None
    await _assert_first_unset_on_disk(rig, monkeypatch, state_file, product)


@pytest.mark.parametrize("product", [176, 267], ids=["ceiling", "mirror"])
async def test_stored_colours_set_after_an_unset_restore_are_saved(
    product: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    state_file = tmp_path / "state.json"
    rig, snapshot = _saved_rig(product, monkeypatch, state_file)
    tile = list(rig.wire.colours)
    rig.light._state_file = None  # the reset is not saved before the next set
    await DeviceStateManager().restore_component(
        rig.light,
        rig.names[0],
        PreState(power=True, color=RED, tile_colors=[tile], stored_colors=snapshot),
    )

    rig.light._set_stored_colors(rig.names[0], [BLUE] * len(rig.positions[0]))
    rig.light._state_file = str(state_file)
    await rig.light._save_state_to_file()

    data = json.loads(state_file.read_text())
    assert rig.names[0] in data[rig.light.serial]
