"""Tests for DeviceGroup.apply_mood()."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from lifx.api import DeviceGroup
from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.devices.multizone import MultiZoneLight
from lifx.theme import Theme

RED = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
GREEN = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
THEME = Theme([RED, GREEN], static_mode="solid")


def fake(light: Light, *, on: bool, colour: bool = True) -> Light:
    light._paints_moods = AsyncMock(return_value=colour)  # type: ignore[method-assign]
    light._mood_effect_running = AsyncMock(return_value=False)  # type: ignore[method-assign]
    light._mood_reading = AsyncMock(return_value=(on, 1.0))  # type: ignore[method-assign]
    light._paint_mood = AsyncMock(return_value=[])  # type: ignore[method-assign]
    return light


def bulb(serial: str, **kw) -> Light:
    return fake(Light(serial=serial, ip="127.0.0.1"), **kw)


async def test_group_deals_distinct_colours_to_bulbs() -> None:
    a, b = bulb("d073d5000a01", on=True), bulb("d073d5000a02", on=True)
    await DeviceGroup([a, b]).apply_mood(THEME)
    dealt = {
        a._paint_mood.await_args.kwargs["bulb_color"].hue,  # type: ignore[attr-defined]
        b._paint_mood.await_args.kwargs["bulb_color"].hue,  # type: ignore[attr-defined]
    }
    assert dealt == {0, 120}


async def test_group_powers_on_only_when_every_light_is_off() -> None:
    a, b = bulb("d073d5000a01", on=False), bulb("d073d5000a02", on=True)
    await DeviceGroup([a, b]).apply_mood(THEME)
    assert a._paint_mood.await_args.kwargs["power_on"] is False  # type: ignore[attr-defined]
    assert b._paint_mood.await_args.kwargs["power_on"] is False  # type: ignore[attr-defined]


async def test_group_all_off_powers_everything_on() -> None:
    a, b = bulb("d073d5000a01", on=False), bulb("d073d5000a02", on=False)
    await DeviceGroup([a, b]).apply_mood(THEME)
    assert a._paint_mood.await_args.kwargs["power_on"] is True  # type: ignore[attr-defined]
    assert b._paint_mood.await_args.kwargs["power_on"] is True  # type: ignore[attr-defined]


async def test_group_apply_mood_skips_non_colour_light() -> None:
    white = bulb("d073d5000a01", on=True, colour=False)
    colour = bulb("d073d5000a02", on=False)
    await DeviceGroup([white, colour]).apply_mood(THEME)
    white._paint_mood.assert_not_awaited()  # type: ignore[attr-defined]
    assert colour._paint_mood.await_args.kwargs["power_on"] is True  # type: ignore[attr-defined]


async def test_strips_get_no_bulb_colour() -> None:
    strip = fake(MultiZoneLight(serial="d073d5000a03", ip="127.0.0.1"), on=True)
    await DeviceGroup([strip]).apply_mood(THEME)
    assert strip._paint_mood.await_args.kwargs["bulb_color"] is None  # type: ignore[attr-defined]


async def test_empty_group_does_nothing() -> None:
    await DeviceGroup([]).apply_mood(THEME)


async def test_running_mood_effect_restarts_instead_of_painting() -> None:
    busy = bulb("d073d5000a01", on=True)
    busy._mood_effect_running = AsyncMock(return_value=True)  # type: ignore[method-assign]
    idle = bulb("d073d5000a02", on=True)
    with patch("lifx.api.effect_runner") as runner:
        runner.return_value.start_together = AsyncMock()
        await DeviceGroup([busy, idle]).apply_mood(THEME)
    assert runner.return_value.start_together.await_args.args[0] == [busy]
    busy._paint_mood.assert_not_awaited()  # type: ignore[attr-defined]
    idle._paint_mood.assert_awaited_once()  # type: ignore[attr-defined]


@pytest.mark.emulator
async def test_emulator_group_apply_mood(emulator_devices: DeviceGroup) -> None:
    await emulator_devices.apply_mood(THEME)


async def test_group_bulbs_share_one_colour_loop() -> None:
    a, b = bulb("d073d5000a01", on=True), bulb("d073d5000a02", on=True)
    with patch("lifx.api.effect_runner") as runner:
        runner.return_value.start_together = AsyncMock()
        await DeviceGroup([a, b]).animate_mood(THEME)
    lights = runner.return_value.start_together.await_args.args[0]
    assert lights == [a, b]


async def test_group_animate_mood_starts_other_lights_alone() -> None:
    strip = fake(MultiZoneLight(serial="d073d5000a03", ip="127.0.0.1"), on=True)
    strip.animate_mood = AsyncMock()  # type: ignore[method-assign]
    white = bulb("d073d5000a04", on=True, colour=False)
    with patch("lifx.api.effect_runner") as runner:
        runner.return_value.start_together = AsyncMock()
        await DeviceGroup([strip, white]).animate_mood(THEME)
    strip.animate_mood.assert_awaited_once_with(THEME)  # type: ignore[attr-defined]
    assert runner.return_value.start_together.await_args.args[0] == []


async def test_group_restart_keeps_one_shared_colour_loop() -> None:
    a, b = bulb("d073d5000a01", on=True), bulb("d073d5000a02", on=True)
    a._mood_effect_running = AsyncMock(return_value=True)  # type: ignore[method-assign]
    b._mood_effect_running = AsyncMock(return_value=True)  # type: ignore[method-assign]
    with patch("lifx.api.effect_runner") as runner:
        runner.return_value.start_together = AsyncMock()
        await DeviceGroup([a, b]).apply_mood(THEME)
    runner.return_value.start_together.assert_awaited_once()
    assert runner.return_value.start_together.await_args.args[0] == [a, b]
