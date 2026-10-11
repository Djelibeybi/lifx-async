"""Tests for the current theme and mood on Ceiling and Mirror lights.

Only whole-light paints are tracked. Any write to one light component (its
colors, its apparent on/off state or an effect on it) ends the record, while
whole-light power keeps it. Everything goes through the public device API
against the embedded emulator.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from functools import partial

import pytest

from lifx.color import HSBK
from lifx.devices.ceiling import CeilingLight
from lifx.devices.component.light import ComponentMatrixLight
from lifx.devices.mirror import MirrorLight
from lifx.effects.frame_effect import FrameContext, FrameEffect
from tests.test_theme.conftest import make_theme

pytestmark = pytest.mark.emulator

AMBER = HSBK(hue=40, saturation=1.0, brightness=0.6, kelvin=3500)
DARK = HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=3500)

Operation = Callable[[ComponentMatrixLight], Awaitable[None]]


themed = partial(make_theme, static_mode="grid_static")


class _Solid(FrameEffect):
    """Frame effect painting every pixel one color."""

    def __init__(self) -> None:
        super().__init__(power_on=True, fps=20.0)

    @property
    def name(self) -> str:
        return "solid"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        return [AMBER] * ctx.pixel_count


def _ceiling(light: ComponentMatrixLight) -> CeilingLight:
    assert isinstance(light, CeilingLight)
    return light


def _mirror(light: ComponentMatrixLight) -> MirrorLight:
    assert isinstance(light, MirrorLight)
    return light


async def _uplight_color(light: ComponentMatrixLight) -> None:
    await _ceiling(light).set_uplight_color(AMBER)


async def _downlight_colors(light: ComponentMatrixLight) -> None:
    await _ceiling(light).set_downlight_colors(AMBER)


async def _uplight_off(light: ComponentMatrixLight) -> None:
    await _ceiling(light).turn_uplight_off()


async def _uplight_on(light: ComponentMatrixLight) -> None:
    await _ceiling(light).turn_uplight_on()


async def _downlight_off(light: ComponentMatrixLight) -> None:
    await _ceiling(light).turn_downlight_off()


async def _downlight_on(light: ComponentMatrixLight) -> None:
    await _ceiling(light).turn_downlight_on()


async def _front_colors(light: ComponentMatrixLight) -> None:
    await _mirror(light).set_front_colors(AMBER)


async def _back_colors(light: ComponentMatrixLight) -> None:
    await _mirror(light).set_back_colors(AMBER)


async def _front_off(light: ComponentMatrixLight) -> None:
    await _mirror(light).turn_front_off()


async def _front_on(light: ComponentMatrixLight) -> None:
    await _mirror(light).turn_front_on()


async def _back_off(light: ComponentMatrixLight) -> None:
    await _mirror(light).turn_back_off()


async def _back_on(light: ComponentMatrixLight) -> None:
    await _mirror(light).turn_back_on()


async def _front_theme(light: ComponentMatrixLight) -> None:
    await _mirror(light).apply_front_theme(themed("unit_test_b"))


async def _back_theme(light: ComponentMatrixLight) -> None:
    await _mirror(light).apply_back_theme(themed("unit_test_b"), power_on=True)


COMPONENT_WRITES = [
    pytest.param("ceiling", _uplight_color, id="ceiling-uplight-color"),
    pytest.param("ceiling", _downlight_colors, id="ceiling-downlight-colors"),
    pytest.param("ceiling", _uplight_off, id="ceiling-uplight-off"),
    pytest.param("ceiling", _uplight_on, id="ceiling-uplight-on"),
    pytest.param("ceiling", _downlight_off, id="ceiling-downlight-off"),
    pytest.param("ceiling", _downlight_on, id="ceiling-downlight-on"),
    pytest.param("mirror", _front_colors, id="mirror-front-colors"),
    pytest.param("mirror", _back_colors, id="mirror-back-colors"),
    pytest.param("mirror", _front_off, id="mirror-front-off"),
    pytest.param("mirror", _front_on, id="mirror-front-on"),
    pytest.param("mirror", _back_off, id="mirror-back-off"),
    pytest.param("mirror", _back_on, id="mirror-back-on"),
    pytest.param("mirror", _front_theme, id="mirror-front-theme"),
    pytest.param("mirror", _back_theme, id="mirror-back-theme"),
]


@pytest.fixture(params=["ceiling", "mirror"])
async def light(request: pytest.FixtureRequest) -> AsyncIterator[ComponentMatrixLight]:
    """Each component light, connected and powered on."""
    device = request.getfixturevalue(f"{request.param}_device")
    async with device:
        await device.stop_effect()
        await device.set_power(True)
        yield device


async def paint(light: ComponentMatrixLight, kind: str) -> None:
    """Paint the whole light with a caller-built theme, as a theme or a mood."""
    if kind == "theme":
        await light.apply_theme(themed("unit_test_a"))
    else:
        await light.apply_mood(themed("unit_test_a"))
    assert (light.current_theme or light.current_mood) == "unit_test_a"


def components(light: ComponentMatrixLight) -> tuple[object, Operation]:
    """One light component to run an effect on, and a write to the other."""

    async def other_ceiling(target: ComponentMatrixLight) -> None:
        await _ceiling(target).set_uplight_color(AMBER)

    async def other_mirror(target: ComponentMatrixLight) -> None:
        await _mirror(target).set_back_colors(AMBER)

    if isinstance(light, CeilingLight):
        return light.downlight, other_ceiling
    return _mirror(light).front, other_mirror


class TestWholeLightPaints:
    async def test_apply_theme_is_tracked(self, light: ComponentMatrixLight) -> None:
        await light.apply_theme(themed("unit_test_a"))
        assert light.current_theme == "unit_test_a"
        assert light.current_mood is None
        assert await light.get_current_theme() == "unit_test_a"

    async def test_apply_mood_is_tracked(self, light: ComponentMatrixLight) -> None:
        await light.apply_mood(themed("unit_test_a"))
        assert light.current_mood == "unit_test_a"
        assert light.current_theme is None
        assert await light.get_current_mood() == "unit_test_a"

    async def test_apply_theme_power_on_is_tracked(
        self, light: ComponentMatrixLight
    ) -> None:
        await light.set_power(False)
        await light.apply_theme(themed("unit_test_a"), power_on=True)
        assert light.current_theme == "unit_test_a"

    @pytest.mark.parametrize("level", [False, True])
    async def test_whole_light_power_keeps_the_record(
        self, light: ComponentMatrixLight, level: bool
    ) -> None:
        await light.apply_theme(themed("unit_test_a"))
        await light.set_power(level)
        assert light.current_theme == "unit_test_a"
        await light.set_power(True)
        await light.apply_mood(themed("unit_test_b"))
        await light.set_power(level)
        assert light.current_mood == "unit_test_b"


class TestComponentWritesEndTheRecord:
    @pytest.mark.parametrize("kind, write", COMPONENT_WRITES)
    @pytest.mark.parametrize("paint_kind", ["theme", "mood"])
    async def test_component_write_clears(
        self,
        request: pytest.FixtureRequest,
        kind: str,
        write: Operation,
        paint_kind: str,
    ) -> None:
        device = request.getfixturevalue(f"{kind}_device")
        async with device:
            await device.stop_effect()
            await device.set_power(True)
            await paint(device, paint_kind)
            await write(device)
            assert device.current_theme is None
            assert device.current_mood is None
            assert await device.get_current_theme() is None
            assert await device.get_current_mood() is None

    @pytest.mark.parametrize("kind", ["ceiling", "mirror"])
    async def test_turning_the_last_lit_component_off_powers_the_light_off(
        self, request: pytest.FixtureRequest, kind: str
    ) -> None:
        # A dark theme leaves both components dark, so turning one "off"
        # powers the whole light off without writing any colors.
        device = request.getfixturevalue(f"{kind}_device")
        async with device:
            await device.stop_effect()
            await device.set_power(True)
            await device.apply_theme(themed("unit_test_a", DARK))
            assert device.current_theme == "unit_test_a"
            if kind == "ceiling":
                await _uplight_off(device)
            else:
                await _front_off(device)
            assert device.current_theme is None

    async def test_write_to_the_other_component_during_an_effect_clears(
        self, light: ComponentMatrixLight
    ) -> None:
        # While an effect draws on one light component, a write to the other
        # goes to the Animator's held tile rather than the wire.
        component, other = components(light)
        await component.start_effect(_Solid())  # type: ignore[attr-defined]
        try:
            await asyncio.sleep(0.2)
            await paint(light, "theme")
            await other(light)
            assert light.current_theme is None
        finally:
            await light.stop_effect()

    @pytest.mark.parametrize("paint_kind", ["theme", "mood"])
    async def test_starting_a_component_effect_clears(
        self, light: ComponentMatrixLight, paint_kind: str
    ) -> None:
        await paint(light, paint_kind)
        component, _ = components(light)
        await component.start_effect(_Solid())  # type: ignore[attr-defined]
        try:
            assert light.current_theme is None
            assert light.current_mood is None
        finally:
            await light.stop_effect()
