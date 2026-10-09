"""Tests for apply_mood() on each device class."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from lifx.color import HSBK
from lifx.const import MOOD_FADE_SECONDS
from lifx.devices.light import Light
from lifx.devices.multizone import MultiZoneLight
from lifx.theme import Theme

RED = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
GREEN = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
STRIPES = Theme([RED, GREEN], static_mode="solid_static")


def reading(light: Light, *, on: bool, brightness: float) -> None:
    light.get_color = AsyncMock(
        return_value=(
            HSBK(hue=0, saturation=0.0, brightness=brightness, kelvin=3500),
            65535 if on else 0,
            "Test",
        )
    )


class TestBulbApplyMood:
    async def test_paints_with_the_app_fade(self, light: Light) -> None:
        reading(light, on=True, brightness=0.5)
        await light.apply_mood(STRIPES)
        color = light.set_color.await_args.args[0]
        assert color.brightness == pytest.approx(0.5, abs=1e-4)
        assert light.set_color.await_args.kwargs["duration"] == MOOD_FADE_SECONDS
        light.set_power.assert_not_awaited()

    async def test_off_light_paints_then_fades_on(self, light: Light) -> None:
        reading(light, on=False, brightness=0.5)
        await light.apply_mood(STRIPES)
        assert light.set_color.await_args.kwargs["duration"] == 0.0
        light.set_power.assert_awaited_once_with(True, duration=MOOD_FADE_SECONDS)

    async def test_non_colour_light_is_ignored(self, mock_device_factory) -> None:
        white = mock_device_factory(Light, product=10)  # a white-only product
        white.set_color = AsyncMock()
        await white.apply_mood(STRIPES)
        white.set_color.assert_not_awaited()


class TestMultiZoneApplyMood:
    async def test_stripes_fill_the_zones(
        self, multizone_light: MultiZoneLight
    ) -> None:
        reading(multizone_light, on=True, brightness=1.0)
        multizone_light.set_all_color_zones = AsyncMock()
        multizone_light.get_zone_count = AsyncMock(return_value=4)
        await multizone_light.apply_mood(STRIPES)
        colors = multizone_light.set_all_color_zones.await_args.args[0]
        assert [c.hue for c in colors] == [0, 0, 120, 120]
        assert (
            multizone_light.set_all_color_zones.await_args.kwargs["duration"]
            == MOOD_FADE_SECONDS
        )

    async def test_off_strip_fades_on(self, multizone_light: MultiZoneLight) -> None:
        reading(multizone_light, on=False, brightness=1.0)
        multizone_light.set_all_color_zones = AsyncMock()
        await multizone_light.apply_mood(STRIPES)
        assert multizone_light.set_all_color_zones.await_args.kwargs["duration"] == 0.0
        multizone_light.set_power.assert_awaited_once_with(
            True, duration=MOOD_FADE_SECONDS
        )
