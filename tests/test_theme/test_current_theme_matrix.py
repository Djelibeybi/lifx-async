"""Tests for the current theme and current mood a matrix light remembers.

Everything goes through the public device API against the embedded emulator.
A second device object for the same light stands in for the LIFX app: it
changes the light behind the first object's back.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import replace

import pytest

from lifx.color import HSBK
from lifx.devices.matrix import MatrixLight, TileInfo
from lifx.effects import EffectColorloop
from lifx.protocol.protocol_types import FirmwareEffect, LightWaveform
from lifx.theme import Theme

pytestmark = pytest.mark.emulator

TILE_SERIAL = "d073d5000007"

RED = HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500)
GREEN = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
BLUE = HSBK(hue=240, saturation=1.0, brightness=0.8, kelvin=3500)
# Values that no uint16 holds exactly, so every write is rounded.
AWKWARD = HSBK(hue=33.3333, saturation=0.33333, brightness=0.77777, kelvin=3500)


def themed(slug: str | None = "unit_test_a", *colours: HSBK) -> Theme:
    """A caller-built theme carrying a slug, never a library theme."""
    return Theme(
        list(colours) or [RED, GREEN, AWKWARD],
        slug=slug,
        static_mode="grid_static",
    )


@pytest.fixture
async def matrix(emulator_server) -> AsyncIterator[MatrixLight]:
    """A connected matrix light, powered on."""
    port, _, _ = emulator_server
    async with MatrixLight(
        serial=TILE_SERIAL, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2
    ) as light:
        await light.set_power(True)
        yield light


@pytest.fixture
async def app(emulator_server) -> AsyncIterator[MatrixLight]:
    """Another client of the same light: what the LIFX app does."""
    port, _, _ = emulator_server
    async with MatrixLight(
        serial=TILE_SERIAL, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2
    ) as light:
        yield light


def one_pixel_off(colours: list[HSBK]) -> list[HSBK]:
    """The same frame with the last pixel changed."""
    return [*colours[:-1], HSBK(300, 1.0, 1.0, 3500)]


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


async def _set_color(light: MatrixLight) -> None:
    await light.set_color(RED)


async def _set_brightness(light: MatrixLight) -> None:
    await light.set_brightness(0.5)


async def _set_waveform(light: MatrixLight) -> None:
    await light.set_waveform(RED, 1.0, 1, LightWaveform.SINE)


async def _pulse(light: MatrixLight) -> None:
    await light.pulse(RED, period=0.1, cycles=1)


async def _breathe(light: MatrixLight) -> None:
    await light.breathe(RED, period=0.1, cycles=1)


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


async def _start_effect(light: MatrixLight) -> None:
    try:
        await light.start_effect(EffectColorloop())
    finally:
        await light.stop_effect()


CLEARING_WRITES: dict[str, Callable[[MatrixLight], Awaitable[None]]] = {
    "set_color": _set_color,
    "set_brightness": _set_brightness,
    "set_waveform": _set_waveform,
    "pulse": _pulse,
    "breathe": _breathe,
    "set_matrix_colors": _set_matrix_colors,
    "set_matrix_colors_uniform": _set_matrix_colors_uniform,
    "set64": _set64,
    "copy_frame_buffer": _copy_frame_buffer,
    "set_effect": _set_effect,
    "start_effect": _start_effect,
}


class TestWritesClearTheRecord:
    @pytest.mark.parametrize("name", sorted(CLEARING_WRITES))
    @pytest.mark.parametrize("kind", ["theme", "mood"])
    async def test_write_clears(
        self, matrix: MatrixLight, name: str, kind: str
    ) -> None:
        if kind == "theme":
            await matrix.apply_theme(themed("unit_test_a"))
        else:
            await matrix.apply_mood(themed("unit_test_a"))
        assert (matrix.current_theme or matrix.current_mood) == "unit_test_a"

        await CLEARING_WRITES[name](matrix)

        assert matrix.current_theme is None
        assert matrix.current_mood is None

    @pytest.mark.parametrize("on", [False, True])
    async def test_set_power_keeps_the_record(
        self, matrix: MatrixLight, on: bool
    ) -> None:
        await matrix.apply_theme(themed("unit_test_a"))
        await matrix.set_power(on)
        assert matrix.current_theme == "unit_test_a"
        await matrix.set_power(not on, duration=0.0)
        assert matrix.current_theme == "unit_test_a"


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
