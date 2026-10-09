"""Tests for apply_mood() on each device class."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.const import MOOD_FADE_SECONDS
from lifx.devices.ceiling import CeilingLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight
from lifx.protocol.protocol_types import FirmwareEffect
from lifx.theme import MoodGenerator, Theme
from tests.test_theme.conftest import make_tile

RED = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
GREEN = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
STRIPES = Theme([RED, GREEN], static_mode="solid_static")


def reading(
    light: Light, *, on: bool, brightness: float, shown: float | None = None
) -> None:
    """Mock what the light reports.

    ``brightness`` is GetColor's reading. A zoned light also reads its zones,
    which show ``shown`` (default: the same brightness), as GetColor alone
    reports zone 0.
    """
    light.get_color = AsyncMock(
        return_value=(
            HSBK(hue=0, saturation=0.0, brightness=brightness, kelvin=3500),
            65535 if on else 0,
            "Test",
        )
    )
    zone = HSBK(
        hue=0,
        saturation=1.0,
        brightness=brightness if shown is None else shown,
        kelvin=3500,
    )
    if isinstance(light, MultiZoneLight):
        light.get_all_color_zones = AsyncMock(return_value=[zone] * 4)
    elif isinstance(light, MatrixLight):

        async def tile_colors() -> list[list[HSBK]]:
            chain = await light.get_device_chain()
            light._device_chain = chain
            return [[zone] * (tile.width * tile.height) for tile in chain]

        light.get_all_tile_colors = AsyncMock(side_effect=tile_colors)


def peak(colors: list[HSBK]) -> float:
    return max(color.brightness for color in colors)


def idle(light: MultiZoneLight) -> None:
    """No firmware effect runs, so the mood paints rather than restarts."""
    light.get_effect = AsyncMock(return_value=MagicMock(effect_type=FirmwareEffect.OFF))


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
        idle(multizone_light)
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
        idle(multizone_light)
        multizone_light.set_all_color_zones = AsyncMock()
        await multizone_light.apply_mood(STRIPES)
        assert multizone_light.set_all_color_zones.await_args.kwargs["duration"] == 0.0
        multizone_light.set_power.assert_awaited_once_with(
            True, duration=MOOD_FADE_SECONDS
        )


GRID = Theme([RED, GREEN], static_mode="grid_static")


class TestMatrixApplyMood:
    async def test_single_tile_grid(self, matrix_light: MatrixLight) -> None:
        reading(matrix_light, on=True, brightness=1.0)
        matrix_light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=2, height=2)]
        )
        await matrix_light.apply_mood(GRID)
        args = matrix_light.set_matrix_colors.await_args
        assert args.args[0] == 0
        assert [c.hue for c in args.args[1]] == [0, 0, 120, 120]
        assert args.kwargs["duration"] == round(MOOD_FADE_SECONDS * 1000)

    async def test_candle_uses_reported_geometry(
        self, matrix_light: MatrixLight
    ) -> None:
        reading(matrix_light, on=True, brightness=1.0)
        matrix_light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=5, height=6)]
        )
        await matrix_light.apply_mood(GRID)
        assert len(matrix_light.set_matrix_colors.await_args.args[1]) == 30

    async def test_chain_is_painted_in_chain_order(
        self, tile_light: MatrixLight
    ) -> None:
        reading(tile_light, on=True, brightness=1.0)
        # Tile 1 sits left of tile 0 physically; the mood ignores that.
        tile_light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, user_x=1.0), make_tile(1, user_x=0.0)]
        )
        await tile_light.apply_mood(Theme([RED, GREEN], static_mode="solid_static"))
        calls = tile_light.set_matrix_colors.await_args_list
        assert [call.args[0] for call in calls] == [0, 1]
        assert {c.hue for c in calls[0].args[1]} == {0}
        assert {c.hue for c in calls[1].args[1]} == {120}

    async def test_no_tiles_paints_nothing(self, matrix_light: MatrixLight) -> None:
        reading(matrix_light, on=True, brightness=1.0)
        await matrix_light.apply_mood(GRID)
        matrix_light.set_matrix_colors.assert_not_awaited()

    async def test_off_matrix_fades_on(self, matrix_light: MatrixLight) -> None:
        reading(matrix_light, on=False, brightness=1.0)
        matrix_light.get_device_chain = AsyncMock(return_value=[make_tile(0)])
        await matrix_light.apply_mood(GRID)
        assert matrix_light.set_matrix_colors.await_args.kwargs["duration"] == 0
        matrix_light.set_power.assert_awaited_once_with(
            True, duration=MOOD_FADE_SECONDS
        )


class TestZonedMoodBrightness:
    async def test_matrix_uses_its_brightest_zone(
        self, matrix_light: MatrixLight
    ) -> None:
        # Zone 0 is black, so GetColor reads 0 while the tile shows 40%.
        reading(matrix_light, on=True, brightness=0.0, shown=0.4)
        matrix_light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=2, height=2)]
        )
        await matrix_light.apply_mood(GRID)
        painted = matrix_light.set_matrix_colors.await_args.args[1]
        assert peak(painted) == pytest.approx(0.4, abs=1e-4)

    async def test_multizone_uses_its_brightest_zone(
        self, multizone_light: MultiZoneLight
    ) -> None:
        reading(multizone_light, on=True, brightness=0.0, shown=0.4)
        idle(multizone_light)
        multizone_light.set_all_color_zones = AsyncMock()
        multizone_light.get_zone_count = AsyncMock(return_value=4)
        await multizone_light.apply_mood(STRIPES)
        painted = multizone_light.set_all_color_zones.await_args.args[0]
        assert peak(painted) == pytest.approx(0.4, abs=1e-4)

    async def test_mixed_zones_take_the_maximum(
        self, matrix_light: MatrixLight
    ) -> None:
        chain = [make_tile(0, width=2, height=2)]
        matrix_light.get_device_chain = AsyncMock(return_value=chain)
        matrix_light._device_chain = chain
        dark, dim = HSBK(0, 1.0, 0.0, 3500), HSBK(0, 1.0, 0.4, 3500)
        matrix_light.get_all_tile_colors = AsyncMock(
            return_value=[[dark, dim, HSBK(0, 1.0, 0.1, 3500), dark]]
        )
        assert await matrix_light._shown_brightness(0.0) == pytest.approx(0.4)

    async def test_matrix_with_every_zone_dark_falls_back_to_getcolor(
        self, matrix_light: MatrixLight
    ) -> None:
        reading(matrix_light, on=True, brightness=0.6, shown=0.0)
        matrix_light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=2, height=2)]
        )
        await matrix_light.apply_mood(GRID)
        painted = matrix_light.set_matrix_colors.await_args.args[1]
        assert peak(painted) == pytest.approx(0.6, abs=1e-4)

    async def test_bulb_uses_getcolor_alone(self, light: Light) -> None:
        reading(light, on=True, brightness=0.5)
        await light.apply_mood(STRIPES)
        assert light.set_color.await_args.args[0].brightness == pytest.approx(
            0.5, abs=1e-4
        )
        assert not hasattr(light, "get_all_color_zones")
        assert not hasattr(light, "get_all_tile_colors")

    async def test_mirror_ignores_its_buffer_padding(self, mock_device_factory) -> None:
        mirror = mock_device_factory(MirrorLight)
        mirror.set_power = AsyncMock()
        mirror._write_tile = AsyncMock()
        mirror._power_for_update = AsyncMock(return_value=65535)
        reading(mirror, on=True, brightness=0.3)
        chain = [make_tile(0, width=4, height=13)]
        mirror.get_device_chain = AsyncMock(return_value=chain)
        mirror._device_chain = chain
        dark = HSBK(0, 1.0, 0.0, 3500)
        bright = HSBK(0, 1.0, 1.0, 3500)
        mirror.get_all_tile_colors = AsyncMock(
            return_value=[[dark] * 52 + [bright] * 12]
        )
        await mirror.apply_mood(GRID)
        painted = mirror._write_tile.await_args.args[0]
        assert peak(painted) == pytest.approx(0.3, abs=1e-4)


class TestCeilingApplyMood:
    async def test_writes_one_tile_through_the_component_path(
        self, ceiling_light: CeilingLight
    ) -> None:
        reading(ceiling_light, on=True, brightness=1.0)
        ceiling_light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=16, height=8)]
        )
        ceiling_light._write_tile = AsyncMock()
        ceiling_light._power_for_update = AsyncMock(return_value=65535)
        await ceiling_light.apply_mood(GRID)
        tile_colors, duration = ceiling_light._write_tile.await_args.args
        assert len(tile_colors) == 128
        assert duration == MOOD_FADE_SECONDS


@pytest.mark.emulator
async def test_chain_emulator_paints_every_tile(tile_chain_light: MatrixLight) -> None:
    async with tile_chain_light:
        await tile_chain_light.apply_mood(
            Theme([RED, GREEN], static_mode="grid_static")
        )
        colors = await tile_chain_light.get_all_tile_colors()
    assert len(colors) == 5
    assert all(len(tile) == 64 for tile in colors)


BLUE = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)
YELLOW = HSBK(hue=60, saturation=1.0, brightness=1.0, kelvin=3500)
QUADS = Theme([RED, GREEN, BLUE, YELLOW], static_mode="grid_static")


class TestCeilingMoodReading:
    async def test_brightness_comes_from_the_zones_and_power_from_the_write(
        self, ceiling_light: CeilingLight
    ) -> None:
        reading(ceiling_light, on=False, brightness=0.0, shown=0.4)
        ceiling_light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=16, height=8)]
        )
        ceiling_light._write_tile = AsyncMock()
        ceiling_light._power_for_update = AsyncMock(return_value=65535)
        await ceiling_light.apply_mood(GRID)
        painted = ceiling_light._write_tile.await_args.args[0]
        assert peak(painted) == pytest.approx(0.4, abs=1e-4)
        assert ceiling_light._write_tile.await_args.args[1] == MOOD_FADE_SECONDS
        ceiling_light.set_power.assert_not_awaited()

    async def test_recent_power_write_wins_over_a_stale_off_reading(
        self, ceiling_light: CeilingLight
    ) -> None:
        # get_color still reports off; _power_for_update knows of a recent
        # power-on write, so the mood must fade rather than preload dark.
        reading(ceiling_light, on=False, brightness=1.0)
        ceiling_light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=16, height=8)]
        )
        ceiling_light._write_tile = AsyncMock()
        ceiling_light._power_for_update = AsyncMock(return_value=65535)
        await ceiling_light.apply_mood(GRID)
        assert ceiling_light._write_tile.await_args.args[1] == MOOD_FADE_SECONDS
        ceiling_light.set_power.assert_not_awaited()


class TestMoodOrientation:
    async def test_rotated_tile_is_remapped_on_a_chain(
        self, tile_light: MatrixLight
    ) -> None:
        reading(tile_light, on=True, brightness=1.0)
        tiles = [make_tile(0), make_tile(1, accel=(1, 0, 0))]
        tile_light.get_device_chain = AsyncMock(return_value=tiles)
        frames = await tile_light._paint_mood(QUADS, power_on=False, brightness=1.0)
        calls = tile_light.set_matrix_colors.await_args_list
        assert calls[0].args[1] == frames[0]
        sent = calls[1].args[1]
        assert sent != frames[1]
        assert sent == MatrixLight._orient_tile_colors(tiles[1], frames[1])

    async def test_rotation_is_ignored_without_a_chain(
        self, matrix_light: MatrixLight
    ) -> None:
        tile = make_tile(0, accel=(1, 0, 0))
        matrix_light.get_device_chain = AsyncMock(return_value=[tile])
        frames = await matrix_light._paint_mood(QUADS, power_on=False, brightness=1.0)
        assert matrix_light.set_matrix_colors.await_args.args[1] == frames[0]


class TestVerticalApplyMood:
    async def test_candle_paints_stripe_moods_as_bands(
        self, mock_device_factory
    ) -> None:
        candle = mock_device_factory(MatrixLight, product=57)
        candle.set_matrix_colors = AsyncMock()
        candle.set_power = AsyncMock()
        reading(candle, on=True, brightness=1.0)
        candle.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=5, height=6)]
        )
        await candle.apply_mood(Theme([RED, GREEN], static_mode="solid_static"))
        colors = candle.set_matrix_colors.await_args.args[1]
        rows = [colors[i : i + 5] for i in range(0, 30, 5)]
        assert all(len({c.hue for c in row}) == 1 for row in rows)
        assert rows[-1][0].hue == 0  # first colour on the bottom row


@pytest.mark.emulator
async def test_mirror_paints_bands_over_its_buffer(mirror_device) -> None:
    async with mirror_device:
        await mirror_device.apply_mood(Theme([RED, GREEN], static_mode="solid_static"))
        buffer = (await mirror_device.get_all_tile_colors())[0][:52]
    rows = [buffer[i : i + 4] for i in range(0, 52, 4)]
    band = MoodGenerator._stretch([RED, GREEN], 13)
    assert [round(row[0].hue) for row in rows] == [round(c.hue) for c in reversed(band)]
    assert all(len({round(c.hue) for c in row}) == 1 for row in rows)
