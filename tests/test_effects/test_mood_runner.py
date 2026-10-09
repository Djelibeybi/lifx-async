"""Tests for the effect runner's mood seam."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.devices.effect_runner import effect_runner
from lifx.devices.light import Light
from lifx.effects import EffectColorloop, EffectPulse, EffectScroll
from lifx.effects.conductor import Conductor

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
        await effect_runner().start_together([], EffectColorloop())

    async def test_refuses_a_non_effect(self) -> None:
        with pytest.raises(TypeError, match="software effect"):
            await effect_runner().start_together([light()], object())

    async def test_starts_one_run_on_the_first_lights_conductor(self) -> None:
        a, b = light("d073d5000b02"), light("d073d5000b03")
        conductor = MagicMock(start=AsyncMock())
        runner = effect_runner()
        runner.conductor_for = MagicMock(return_value=conductor)  # type: ignore[attr-defined]
        try:
            effect = EffectColorloop()
            await runner.start_together([a, b], effect)
        finally:
            del runner.conductor_for  # type: ignore[attr-defined]
        conductor.start.assert_awaited_once_with(effect, [a, b])
