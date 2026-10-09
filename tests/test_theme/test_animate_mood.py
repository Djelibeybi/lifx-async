"""Tests for animate_mood() and the apply_mood() restart rule."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.const import MOOD_MORPH_SPEED_SECONDS
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight
from lifx.effects import EffectColorloop, EffectScroll
from lifx.exceptions import LifxUnsupportedCommandError
from lifx.products import moves_as_morph
from lifx.protocol.protocol_types import Direction, FirmwareEffect
from lifx.theme import Theme

RED = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
GREEN = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
MOVE_THEME = Theme([RED, GREEN], static_mode="solid_static")  # resolves to move
GRID_THEME = Theme([RED, GREEN], static_mode="grid_static")  # resolves to move
MORPH_THEME = Theme([RED, GREEN], static_mode="blended")  # resolves to morph


def prime(light: Light) -> Light:
    light._paints_moods = AsyncMock(return_value=True)
    light._mood_reading = AsyncMock(return_value=(True, 1.0))
    light._paint_mood = AsyncMock(return_value=[[RED] * 4])
    light.start_effect = AsyncMock()
    return light


class TestBulb:
    async def test_runs_a_palette_colour_loop(self, mock_device_factory) -> None:
        light = prime(mock_device_factory(Light))
        await light.animate_mood(MORPH_THEME)
        effect = light.start_effect.await_args.args[0]
        assert isinstance(effect, EffectColorloop)
        assert effect.palette == [RED, GREEN]
        assert effect.transition == 0.5

    async def test_skips_a_light_without_colour(self, mock_device_factory) -> None:
        light = prime(mock_device_factory(Light))
        light._paints_moods = AsyncMock(return_value=False)
        await light.animate_mood(MORPH_THEME)
        light.start_effect.assert_not_awaited()


class TestStrip:
    @pytest.mark.parametrize("theme", [MOVE_THEME, MORPH_THEME])
    async def test_paints_then_starts_firmware_move(
        self, mock_device_factory, theme
    ) -> None:
        strip = prime(mock_device_factory(MultiZoneLight, product=32))
        strip.get_zone_count = AsyncMock(return_value=32)
        strip.set_effect = AsyncMock()
        await strip.animate_mood(theme)
        strip._paint_mood.assert_awaited_once()
        effect = strip.set_effect.await_args.args[0]
        assert effect == MultiZoneEffect.move(Direction.FORWARD, 40.0)

    async def test_skips_a_strip_without_colour(self, mock_device_factory) -> None:
        strip = prime(mock_device_factory(MultiZoneLight, product=32))
        strip._paints_moods = AsyncMock(return_value=False)
        strip.set_effect = AsyncMock()
        await strip.animate_mood(MOVE_THEME)
        strip.set_effect.assert_not_awaited()


class TestMatrix:
    async def test_morph_sends_the_theme_palette(self, mock_device_factory) -> None:
        light = prime(mock_device_factory(MatrixLight))
        light.set_effect = AsyncMock()
        await light.animate_mood(MORPH_THEME)
        light._paint_mood.assert_not_awaited()
        light.set_effect.assert_awaited_once_with(
            FirmwareEffect.MORPH, speed=MOOD_MORPH_SPEED_SECONDS, palette=[RED, GREEN]
        )

    async def test_move_paints_then_scrolls_the_painted_frame(
        self, mock_device_factory
    ) -> None:
        light = prime(mock_device_factory(MatrixLight))
        light._stop_firmware_effect = AsyncMock()
        await light.animate_mood(MOVE_THEME)
        effect = light.start_effect.await_args.args[0]
        assert isinstance(effect, EffectScroll)
        assert effect.frame == [[RED] * 4]

    async def test_skips_a_matrix_light_without_colour(
        self, mock_device_factory
    ) -> None:
        light = prime(mock_device_factory(MatrixLight))
        light._paints_moods = AsyncMock(return_value=False)
        light.set_effect = AsyncMock()
        await light.animate_mood(MORPH_THEME)
        light.set_effect.assert_not_awaited()
        light.start_effect.assert_not_awaited()

    @pytest.mark.parametrize("product", [267, 171])
    async def test_mirror_and_spot_substitute_morph(
        self, mock_device_factory, product
    ) -> None:
        cls = MirrorLight if product == 267 else MatrixLight
        light = prime(mock_device_factory(cls, product=product))
        light.set_effect = AsyncMock()
        await light.animate_mood(MOVE_THEME)
        assert light.set_effect.await_args.args[0] == FirmwareEffect.MORPH

    @pytest.mark.parametrize(
        ("theme", "vertical"), [(MOVE_THEME, True), (GRID_THEME, False)]
    )
    async def test_tube_scrolls_stripes_vertically(
        self, mock_device_factory, theme, vertical
    ) -> None:
        tube = prime(mock_device_factory(MatrixLight, product=217))
        tube._stop_firmware_effect = AsyncMock()
        await tube.animate_mood(theme)
        effect = tube.start_effect.await_args.args[0]
        assert isinstance(effect, EffectScroll)
        assert effect.vertical is vertical

    def test_moves_as_morph(self) -> None:
        assert moves_as_morph(267)
        assert not moves_as_morph(217)


class TestColorloopPowerOn:
    async def test_palette_starts_on_its_first_colour_dark(self) -> None:
        effect = EffectColorloop(palette=[GREEN, RED])
        start = await effect.from_poweroff_hsbk(MagicMock())
        assert (start.hue, start.saturation, start.brightness) == (120, 1.0, 0.0)
        assert start.kelvin == GREEN.kelvin

    async def test_without_a_palette_starts_dark(self) -> None:
        start = await EffectColorloop().from_poweroff_hsbk(MagicMock())
        assert start.brightness == 0.8


class TestRestart:
    async def test_running_firmware_morph_restarts(self, mock_device_factory) -> None:
        light = mock_device_factory(MatrixLight)
        light._paints_moods = AsyncMock(return_value=True)
        light.get_effect = AsyncMock(
            return_value=MagicMock(effect_type=FirmwareEffect.MORPH)
        )
        light.animate_mood = AsyncMock()
        light._paint_mood = AsyncMock()
        await light.apply_mood(MORPH_THEME)
        light.animate_mood.assert_awaited_once_with(MORPH_THEME)
        light._paint_mood.assert_not_awaited()

    async def test_running_strip_move_restarts(self, mock_device_factory) -> None:
        strip = mock_device_factory(MultiZoneLight, product=32)
        strip._paints_moods = AsyncMock(return_value=True)
        strip.get_effect = AsyncMock(
            return_value=MagicMock(effect_type=FirmwareEffect.MOVE)
        )
        strip.animate_mood = AsyncMock()
        await strip.apply_mood(MOVE_THEME)
        strip.animate_mood.assert_awaited_once()

    async def test_strip_without_move_is_not_running(self, mock_device_factory) -> None:
        strip = mock_device_factory(MultiZoneLight, product=32)
        strip.get_effect = AsyncMock(
            return_value=MagicMock(effect_type=FirmwareEffect.OFF)
        )
        assert not await strip._mood_effect_running()

    async def test_idle_light_paints(self, mock_device_factory) -> None:
        light = mock_device_factory(MatrixLight)
        light._paints_moods = AsyncMock(return_value=True)
        light.get_effect = AsyncMock(
            return_value=MagicMock(effect_type=FirmwareEffect.OFF)
        )
        light._mood_reading = AsyncMock(return_value=(True, 1.0))
        light._paint_mood = AsyncMock()
        await light.apply_mood(MORPH_THEME)
        light._paint_mood.assert_awaited_once()

    @pytest.mark.emulator
    async def test_software_mood_effect_is_seen(self, emulator_devices) -> None:
        bulb = emulator_devices[0]
        async with bulb:
            await bulb.animate_mood(MORPH_THEME)
            try:
                assert await bulb._mood_effect_running()
            finally:
                await bulb.stop_effect()
            assert not await bulb._mood_effect_running()


class TestRejectedGetEffect:
    async def test_strip_treats_it_as_no_effect(self, mock_device_factory) -> None:
        strip = mock_device_factory(MultiZoneLight, product=32)
        strip.get_effect = AsyncMock(side_effect=LifxUnsupportedCommandError("no"))
        assert not await strip._mood_effect_running()

    async def test_matrix_treats_it_as_no_effect(self, mock_device_factory) -> None:
        light = mock_device_factory(MatrixLight)
        light.get_effect = AsyncMock(side_effect=LifxUnsupportedCommandError("no"))
        assert not await light._mood_effect_running()
