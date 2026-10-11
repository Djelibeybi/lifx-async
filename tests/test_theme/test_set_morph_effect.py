"""Tests for MatrixLight.set_morph_effect().

Public device API against the embedded emulator. A second device object for
the same light stands in for the LIFX app.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from lifx.color import HSBK
from lifx.devices.matrix import MatrixLight
from lifx.protocol.protocol_types import FirmwareEffect
from lifx.theme import Theme
from lifx.theme.library import ThemeLibrary

pytestmark = pytest.mark.emulator

TILE_SERIAL = "d073d5000007"

RED = HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500)
GREEN = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
BLUE = HSBK(hue=240, saturation=1.0, brightness=0.8, kelvin=3500)


def themed(slug: str | None = "unit_test_m") -> Theme:
    """A caller-built slugged theme."""
    return Theme([RED, GREEN, BLUE], slug=slug, static_mode="blended")


@pytest.fixture
async def matrix(emulator_server) -> AsyncIterator[MatrixLight]:
    port, _, _ = emulator_server
    async with MatrixLight(
        serial=TILE_SERIAL, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2
    ) as light:
        await light.set_power(True)
        yield light
        await light.stop_effect()


@pytest.fixture
async def app(emulator_server) -> AsyncIterator[MatrixLight]:
    port, _, _ = emulator_server
    async with MatrixLight(
        serial=TILE_SERIAL, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2
    ) as light:
        yield light


class TestTheme:
    async def test_sends_the_theme_colours_and_records_a_theme(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        await matrix.set_morph_effect(themed())
        effect = await app.get_effect()
        assert effect.effect_type == FirmwareEffect.MORPH
        assert effect.palette is not None
        assert sorted(c.hue for c in effect.palette) == pytest.approx(
            [0, 120, 240], abs=0.01
        )
        assert matrix.current_theme == "unit_test_m"
        assert matrix.current_mood is None
        assert await matrix.get_current_theme() == "unit_test_m"

    async def test_accepts_a_library_slug(self, matrix: MatrixLight) -> None:
        slug = ThemeLibrary.get_available_themes()[0]
        await matrix.set_morph_effect(slug)
        assert matrix.current_theme == ThemeLibrary.get(slug).slug

    async def test_unknown_slug_raises(self, matrix: MatrixLight) -> None:
        with pytest.raises(KeyError):
            await matrix.set_morph_effect("unit_test_no_such_theme")
        assert matrix.current_theme is None

    async def test_speed_is_passed_on(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        await matrix.set_morph_effect(
            themed(), speed=7.0, duration=5_000_000_000
        )  # emulator drops duration
        effect = await app.get_effect()
        assert effect.speed == 7000

    async def test_does_not_paint_tiles_first(
        self, matrix: MatrixLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def refuse(*args: object, **kwargs: object) -> None:
            raise AssertionError("tiles were painted")

        monkeypatch.setattr(matrix, "apply_theme", refuse)
        monkeypatch.setattr(matrix, "set64", refuse, raising=False)
        await matrix.set_morph_effect(themed())

    async def test_slugless_theme_records_nothing(self, matrix: MatrixLight) -> None:
        await matrix.set_morph_effect(themed(None))
        assert (matrix.current_theme, matrix.current_mood) == (None, None)

    async def test_another_palette_ends_the_record(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        await matrix.set_morph_effect(themed())
        await app.set_effect(FirmwareEffect.MORPH, speed=3.0, palette=[RED, RED])
        assert await matrix.get_current_theme() is None


class TestMood:
    async def test_records_a_mood(self, matrix: MatrixLight) -> None:
        await matrix.set_morph_effect(themed(), mood=True)
        assert matrix.current_mood == "unit_test_m"
        assert matrix.current_theme is None
        assert await matrix.get_current_mood() == "unit_test_m"

    async def test_morphs_even_for_a_move_mood(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        theme = Theme(
            [RED, GREEN, BLUE], slug="unit_test_s", static_mode="solid_static"
        )
        await matrix.set_morph_effect(theme, mood=True)
        assert (await app.get_effect()).effect_type == FirmwareEffect.MORPH
        assert matrix.current_mood == "unit_test_s"

    async def test_turns_an_off_light_on(self, matrix: MatrixLight) -> None:
        await matrix.set_power(False)
        await matrix.set_morph_effect(themed(), mood=True)
        assert await matrix.get_power() > 0

    async def test_stop_restores_the_prior_theme(self, matrix: MatrixLight) -> None:
        await matrix.apply_theme(themed("unit_test_before"))
        await matrix.set_morph_effect(themed(), mood=True)
        await matrix.stop_effect()
        assert matrix.current_theme == "unit_test_before"
        assert matrix.current_mood is None
