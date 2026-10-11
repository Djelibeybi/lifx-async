"""Tests for the current theme and current mood a matrix light remembers.

Everything goes through the public device API against the embedded emulator.
A second device object for the same light stands in for the LIFX app: it
changes the light behind the first object's back.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from functools import partial

import pytest

from lifx.color import HSBK
from lifx.devices.matrix import MatrixLight, TileInfo
from lifx.protocol.protocol_types import FirmwareEffect
from tests.test_theme.conftest import (
    AWKWARD,
    BLUE,
    COMMON_CLEARING_WRITES,
    GREEN,
    RED,
    assert_power_keeps,
    assert_write_clears,
    make_theme,
)

pytestmark = pytest.mark.emulator

themed = partial(make_theme, static_mode="grid_static")


def one_pixel_off(colors: list[HSBK]) -> list[HSBK]:
    """The same frame with the last pixel changed."""
    return [*colors[:-1], HSBK(300, 1.0, 1.0, 3500)]


class TestRecord:
    async def test_new_object_has_nothing(self, matrix: MatrixLight) -> None:
        assert matrix.current_theme is None
        assert matrix.current_mood is None

    async def test_apply_theme_records_theme(self, matrix: MatrixLight) -> None:
        await matrix.apply_theme(themed("unit_test_a"))
        assert matrix.current_theme == "unit_test_a"
        assert matrix.current_mood is None

    async def test_apply_mood_records_mood(self, matrix: MatrixLight) -> None:
        await matrix.apply_mood(themed("unit_test_a"))
        assert matrix.current_mood == "unit_test_a"
        assert matrix.current_theme is None

    async def test_mood_replaces_theme_and_back(self, matrix: MatrixLight) -> None:
        await matrix.apply_theme(themed("unit_test_a"))
        await matrix.apply_mood(themed("unit_test_b"))
        assert (matrix.current_theme, matrix.current_mood) == (None, "unit_test_b")
        await matrix.apply_theme(themed("unit_test_c"))
        assert (matrix.current_theme, matrix.current_mood) == ("unit_test_c", None)

    async def test_slugless_theme_leaves_both_none(self, matrix: MatrixLight) -> None:
        await matrix.apply_theme(themed("unit_test_a"))
        await matrix.apply_theme(themed(None))
        assert (matrix.current_theme, matrix.current_mood) == (None, None)
        await matrix.apply_mood(themed("unit_test_a"))
        await matrix.apply_mood(themed(None))
        assert (matrix.current_theme, matrix.current_mood) == (None, None)

    async def test_apply_theme_with_power_on_keeps_the_record(
        self, matrix: MatrixLight
    ) -> None:
        await matrix.set_power(False)
        await matrix.apply_theme(themed("unit_test_a"), power_on=True)
        assert matrix.current_theme == "unit_test_a"

    async def test_second_object_starts_empty(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        await matrix.apply_theme(themed())
        assert app.current_theme is None


class TestVerification:
    async def test_unchanged_light_confirms(self, matrix: MatrixLight) -> None:
        await matrix.apply_theme(themed("unit_test_a"))
        assert await matrix.get_current_theme() == "unit_test_a"
        assert await matrix.get_current_mood() is None
        assert matrix.current_theme == "unit_test_a"

    async def test_unchanged_mood_confirms(self, matrix: MatrixLight) -> None:
        await matrix.apply_mood(themed("unit_test_a"))
        assert await matrix.get_current_mood() == "unit_test_a"
        assert await matrix.get_current_theme() is None

    async def test_nothing_recorded_reads_nothing(self, matrix: MatrixLight) -> None:
        assert await matrix.get_current_theme() is None
        assert await matrix.get_current_mood() is None

    async def test_rounding_is_not_a_change(self, matrix: MatrixLight) -> None:
        await matrix.apply_theme(themed("unit_test_a", AWKWARD, AWKWARD))
        assert await matrix.get_current_theme() == "unit_test_a"

    async def test_external_pixel_change_clears(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        await matrix.apply_theme(themed("unit_test_a"))
        shown = (await app.get_all_tile_colors())[0]
        await app.set_matrix_colors(0, one_pixel_off(shown))
        assert await matrix.get_current_theme() is None
        assert matrix.current_theme is None

    async def test_external_dimming_clears(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        await matrix.apply_mood(themed("unit_test_a"))
        shown = (await app.get_all_tile_colors())[0]
        await app.set_matrix_colors(
            0, [HSBK(c.hue, c.saturation, c.brightness * 0.5, c.kelvin) for c in shown]
        )
        assert await matrix.get_current_mood() is None
        assert matrix.current_mood is None

    async def test_refresh_state_clears_stale_record(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        await matrix.apply_theme(themed("unit_test_a"))
        shown = (await app.get_all_tile_colors())[0]
        await app.set_matrix_colors(0, one_pixel_off(shown))
        await matrix.refresh_state()
        assert matrix.current_theme is None

    async def test_refresh_state_keeps_matching_record(
        self, matrix: MatrixLight
    ) -> None:
        await matrix.apply_theme(themed("unit_test_a"))
        await matrix.refresh_state()
        assert matrix.current_theme == "unit_test_a"

    async def test_refresh_state_with_no_record(self, matrix: MatrixLight) -> None:
        await matrix.refresh_state()
        assert matrix.current_theme is None

    async def test_verification_does_not_clear_a_newer_record(
        self, matrix: MatrixLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A paint made while the read is in flight is not the stale one."""
        await matrix.apply_theme(themed("unit_test_a"))
        real_read = matrix.get_all_tile_colors

        async def read_then_repaint() -> list[list[HSBK]]:
            stale = await real_read()
            await matrix.apply_theme(themed("unit_test_b", GREEN, BLUE))
            return stale

        monkeypatch.setattr(matrix, "get_all_tile_colors", read_then_repaint)
        await matrix.get_current_theme()
        assert matrix.current_theme == "unit_test_b"

    async def test_a_chain_that_changed_length_does_not_match(
        self, matrix: MatrixLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await matrix.apply_theme(themed("unit_test_a"))
        real_read = matrix.get_all_tile_colors

        async def two_tiles() -> list[list[HSBK]]:
            tiles = await real_read()
            return [*tiles, *tiles]

        monkeypatch.setattr(matrix, "get_all_tile_colors", two_tiles)
        assert await matrix.get_current_theme() is None


async def _set_matrix_colors(light: MatrixLight) -> None:
    await light.set_matrix_colors(0, [RED, GREEN, BLUE, AWKWARD] * 16)


async def _set_matrix_colors_uniform(light: MatrixLight) -> None:
    await light.set_matrix_colors(0, [RED] * 64)


async def _set64(light: MatrixLight) -> None:
    await light.set64(0, 1, 0, 0, 8, 0, [RED] * 8)


async def _copy_frame_buffer(light: MatrixLight) -> None:
    await light.copy_frame_buffer(0, 1, 0)


async def _set_effect(light: MatrixLight) -> None:
    await light.set_effect(FirmwareEffect.OFF)


CLEARING_WRITES: dict[str, Callable[[MatrixLight], Awaitable[None]]] = {
    **COMMON_CLEARING_WRITES,
    "set_matrix_colors": _set_matrix_colors,
    "set_matrix_colors_uniform": _set_matrix_colors_uniform,
    "set64": _set64,
    "copy_frame_buffer": _copy_frame_buffer,
    "set_effect": _set_effect,
}


class TestWritesClearTheRecord:
    @pytest.mark.parametrize("name", sorted(CLEARING_WRITES))
    @pytest.mark.parametrize("kind", ["theme", "mood"])
    async def test_write_clears(
        self, matrix: MatrixLight, name: str, kind: str
    ) -> None:
        await assert_write_clears(
            matrix, themed("unit_test_a"), kind, CLEARING_WRITES[name]
        )

    @pytest.mark.parametrize("on", [False, True])
    async def test_set_power_keeps_the_record(
        self, matrix: MatrixLight, on: bool
    ) -> None:
        await assert_power_keeps(matrix, themed("unit_test_a"), on)


class TestChain:
    """A LIFX Tile chain, one tile of which is physically rotated."""

    @staticmethod
    def rotate_tile_two(light: MatrixLight, monkeypatch: pytest.MonkeyPatch) -> None:
        real = light.get_device_chain

        async def rotated() -> list[TileInfo]:
            chain = await real()
            chain[2] = replace(chain[2], accel_meas_x=1, accel_meas_y=0)
            light._device_chain = chain
            return chain

        monkeypatch.setattr(light, "get_device_chain", rotated)

    @pytest.mark.parametrize("kind", ["theme", "mood"])
    async def test_rotated_tile_verifies(
        self,
        tile_chain_light: MatrixLight,
        monkeypatch: pytest.MonkeyPatch,
        kind: str,
    ) -> None:
        async with tile_chain_light:
            self.rotate_tile_two(tile_chain_light, monkeypatch)
            theme = themed("unit_test_a", RED, GREEN, BLUE, AWKWARD)
            if kind == "theme":
                await tile_chain_light.apply_theme(theme)
                assert await tile_chain_light.get_current_theme() == "unit_test_a"
            else:
                await tile_chain_light.apply_mood(theme)
                assert await tile_chain_light.get_current_mood() == "unit_test_a"

    async def test_changing_one_tile_clears(
        self,
        tile_chain_light: MatrixLight,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async with tile_chain_light:
            self.rotate_tile_two(tile_chain_light, monkeypatch)
            await tile_chain_light.apply_theme(
                themed("unit_test_a", RED, GREEN, BLUE, AWKWARD)
            )
            shown = (await tile_chain_light.get_all_tile_colors())[2]
            await tile_chain_light.set_matrix_colors(2, one_pixel_off(shown))
            # The write itself already ends the record; a second object would
            # find the same through verification.
            assert await tile_chain_light.get_current_theme() is None
