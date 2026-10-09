"""Tests for the effect runner's mood seam."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.devices.effect_runner import effect_runner
from lifx.devices.light import Light
from lifx.effects import EffectColorloop, EffectPulse, EffectScroll
from lifx.effects.base import LIFXEffect
from lifx.effects.conductor import Conductor, own_conductor
from lifx.effects.models import PreState
from lifx.effects.state_manager import DeviceStateManager

RED = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
GREEN = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)


def light(serial: str = "d073d5000b01") -> Light:
    return Light(serial=serial, ip="127.0.0.1")


def running(conductor: Conductor, target: Light, effect: object) -> None:
    conductor._running[target.serial] = MagicMock(effect=effect)


class TestWholeLightEffect:
    def test_none_when_nothing_runs(self) -> None:
        assert Conductor._whole_light_effect(light("d073d5000b09")) is None

    def test_found_on_any_conductor(self) -> None:
        target, effect = light(), EffectPulse()
        conductor = Conductor()
        running(conductor, target, effect)
        assert Conductor._whole_light_effect(target) is effect


class TestRunsMoodEffect:
    @pytest.mark.parametrize(
        ("effect", "expected"),
        [
            (EffectScroll(), True),
            (EffectColorloop(palette=[RED, GREEN]), True),
            (EffectColorloop(), False),
            (EffectPulse(), False),
        ],
    )
    def test_by_effect(self, effect, expected) -> None:
        target = light()
        conductor = Conductor()
        running(conductor, target, effect)
        assert effect_runner().runs_mood_effect(target) is expected

    def test_false_when_idle(self) -> None:
        assert not effect_runner().runs_mood_effect(light("d073d5000b08"))


class TestBuilders:
    def test_scroll_effect(self) -> None:
        effect = effect_runner().scroll_effect([[RED]], True)
        assert isinstance(effect, EffectScroll)
        assert effect.frame == [[RED]]
        assert effect.vertical is True

    def test_palette_effect_steps_at_the_app_pace(self) -> None:
        effect = effect_runner().palette_effect([RED, GREEN])
        assert isinstance(effect, EffectColorloop)
        assert effect.palette == [RED, GREEN]
        assert effect.period == 2.5
        assert effect.transition == 0.5


class TestStartTogether:
    async def test_no_lights_is_a_no_op(self) -> None:
        await effect_runner().start_together([], EffectColorloop(), prestates=[])

    async def test_starts_one_run_with_each_lights_prior_state(self) -> None:
        a, b = light("d073d5000b02"), light("d073d5000b03")
        before_a, before_b = prior(RED), prior(GREEN)
        conductor = MagicMock(_start=AsyncMock())
        runner = effect_runner()
        runner.conductor_for = MagicMock(return_value=conductor)  # type: ignore[attr-defined]
        try:
            effect = EffectColorloop()
            await runner.start_together([a, b], effect, prestates=[before_a, before_b])
        finally:
            del runner.conductor_for  # type: ignore[attr-defined]
        conductor._start.assert_awaited_once_with(
            effect,
            [a, b],
            enable_thread=False,
            supplied={a.serial: before_a, b.serial: before_b},
        )


def prior(colour: HSBK, *, power: bool = True) -> PreState:
    return PreState(power=power, color=colour)


class _Hold(LIFXEffect):
    """Runs until stopped, drawing nothing."""

    @property
    def name(self) -> str:
        return "hold"

    async def async_play(self) -> None:
        await asyncio.Event().wait()


def recording(serial: str) -> tuple[Light, DeviceStateManager]:
    """A light whose state manager records captures and restores."""
    target = light(serial)
    target.get_power = AsyncMock(return_value=65535)  # type: ignore[method-assign]
    manager = MagicMock(
        capture_state=AsyncMock(return_value=prior(GREEN)),
        restore_state=AsyncMock(),
    )
    return target, manager


class TestPriorStates:
    async def test_take_captures_a_light_in_no_run(self) -> None:
        target, manager = recording("d073d5000b04")
        conductor = own_conductor(target)
        conductor._state_manager = manager
        assert await effect_runner().take_prestate(target) == prior(GREEN)
        manager.capture_state.assert_awaited_once_with(target)

    async def test_take_inherits_a_runs_original_state_unrestored(self) -> None:
        target, manager = recording("d073d5000b05")
        conductor = own_conductor(target)
        conductor._state_manager = manager
        original = prior(RED, power=False)
        await effect_runner().start(target, _Hold(), prestate=original)
        manager.capture_state.assert_not_awaited()
        assert await effect_runner().take_prestate(target) is original
        assert conductor.effect(target) is None
        manager.restore_state.assert_not_awaited()
        manager.capture_state.assert_not_awaited()

    async def test_a_supplied_state_gives_way_to_an_inherited_one(self) -> None:
        target, manager = recording("d073d5000b06")
        conductor = own_conductor(target)
        conductor._state_manager = manager
        await effect_runner().start(target, _Hold())
        first = conductor._running[target.serial].prestate
        await effect_runner().start(target, _Hold(), prestate=prior(RED))
        assert conductor._running[target.serial].prestate is first
        await target.stop_effect()
        manager.restore_state.assert_awaited_once_with(target, first)

    async def test_restore_puts_the_state_back(self) -> None:
        target, manager = recording("d073d5000b07")
        own_conductor(target)._state_manager = manager
        original = prior(RED)
        await effect_runner().restore_prestate(target, original)
        manager.restore_state.assert_awaited_once_with(target, original)
