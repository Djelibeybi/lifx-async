"""Tests for the current theme and current mood a strip remembers.

Everything goes through the public device API against the embedded emulator.
A second device object for the same strip stands in for the LIFX app: it
changes the light behind the first object's back.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

import pytest

from lifx.color import HSBK
from lifx.devices.multizone import Direction, MultiZoneEffect, MultiZoneLight
from lifx.effects import Conductor, EffectColorloop
from lifx.protocol.protocol_types import FirmwareEffect
from lifx.theme import get_theme
from lifx.theme.library import ThemeLibrary
from tests.test_theme.conftest import (
    AWKWARD,
    COMMON_CLEARING_WRITES,
    GREEN,
    RED,
    STRIP_SERIAL,
    assert_power_keeps,
    assert_write_clears,
    make_theme,
)

pytestmark = pytest.mark.emulator


@pytest.fixture
async def app(emulator_server) -> AsyncIterator[MultiZoneLight]:
    """Another client of the same strip: what the LIFX app does."""
    port, _, _ = emulator_server
    async with MultiZoneLight(
        serial=STRIP_SERIAL, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2
    ) as light:
        yield light


class TestRecord:
    async def test_new_object_has_nothing(self, strip: MultiZoneLight) -> None:
        assert strip.current_theme is None
        assert strip.current_mood is None

    async def test_apply_theme_records_theme(self, strip: MultiZoneLight) -> None:
        await strip.apply_theme(make_theme("unit_test_a"))
        assert strip.current_theme == "unit_test_a"
        assert strip.current_mood is None

    async def test_apply_mood_records_mood(self, strip: MultiZoneLight) -> None:
        await strip.apply_mood(make_theme("unit_test_a"))
        assert strip.current_mood == "unit_test_a"
        assert strip.current_theme is None

    async def test_mood_replaces_theme_and_back(self, strip: MultiZoneLight) -> None:
        await strip.apply_theme(make_theme("unit_test_a"))
        await strip.apply_mood(make_theme("unit_test_b"))
        assert (strip.current_theme, strip.current_mood) == (None, "unit_test_b")
        await strip.apply_theme(make_theme("unit_test_c"))
        assert (strip.current_theme, strip.current_mood) == ("unit_test_c", None)

    async def test_slugless_theme_leaves_both_none(self, strip: MultiZoneLight) -> None:
        await strip.apply_theme(make_theme("unit_test_a"))
        await strip.apply_theme(make_theme(None))
        assert (strip.current_theme, strip.current_mood) == (None, None)
        await strip.apply_mood(make_theme("unit_test_a"))
        await strip.apply_mood(make_theme(None))
        assert (strip.current_theme, strip.current_mood) == (None, None)

    async def test_second_object_starts_empty(
        self, strip: MultiZoneLight, app: MultiZoneLight
    ) -> None:
        await strip.apply_theme(make_theme())
        assert app.current_theme is None


class TestVerification:
    async def test_unchanged_strip_confirms(self, strip: MultiZoneLight) -> None:
        await strip.apply_theme(make_theme("unit_test_a"))
        assert await strip.get_current_theme() == "unit_test_a"
        assert await strip.get_current_mood() is None
        assert strip.current_theme == "unit_test_a"

    async def test_unchanged_mood_confirms(self, strip: MultiZoneLight) -> None:
        await strip.apply_mood(make_theme("unit_test_a"))
        assert await strip.get_current_mood() == "unit_test_a"
        assert await strip.get_current_theme() is None
        assert strip.current_mood == "unit_test_a"

    async def test_nothing_recorded_reads_nothing(self, strip: MultiZoneLight) -> None:
        assert await strip.get_current_theme() is None
        assert await strip.get_current_mood() is None

    async def test_rounding_is_not_a_change(self, strip: MultiZoneLight) -> None:
        await strip.apply_theme(make_theme("unit_test_a", AWKWARD))
        assert await strip.get_current_theme() == "unit_test_a"

    async def test_external_zone_change_clears(
        self, strip: MultiZoneLight, app: MultiZoneLight
    ) -> None:
        await strip.apply_theme(make_theme("unit_test_a"))
        await app.set_color_zones(0, 0, HSBK(240, 1.0, 1.0, 3500))
        assert await strip.get_current_theme() is None
        assert strip.current_theme is None

    async def test_external_dimming_clears(
        self, strip: MultiZoneLight, app: MultiZoneLight
    ) -> None:
        await strip.apply_mood(make_theme("unit_test_a"))
        zones = await app.get_all_color_zones()
        await app.set_all_color_zones(
            [HSBK(z.hue, z.saturation, z.brightness * 0.5, z.kelvin) for z in zones]
        )
        assert await strip.get_current_mood() is None
        assert strip.current_mood is None

    async def test_refresh_state_clears_stale_record(
        self, strip: MultiZoneLight, app: MultiZoneLight
    ) -> None:
        await strip.apply_theme(make_theme("unit_test_a"))
        await app.set_color_zones(1, 1, HSBK(240, 1.0, 1.0, 3500))
        await strip.refresh_state()
        assert strip.current_theme is None

    async def test_refresh_state_keeps_matching_record(
        self, strip: MultiZoneLight
    ) -> None:
        await strip.apply_theme(make_theme("unit_test_a"))
        await strip.refresh_state()
        assert strip.current_theme == "unit_test_a"

    async def test_refresh_state_with_no_record(self, strip: MultiZoneLight) -> None:
        await strip.refresh_state()
        assert strip.current_theme is None
        assert strip.current_mood is None

    async def test_verification_does_not_clear_a_newer_record(
        self, strip: MultiZoneLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A paint made while the read is in flight is not the stale one."""
        await strip.apply_theme(make_theme("unit_test_a"))
        real_read = strip.get_all_color_zones

        async def read_then_repaint() -> list[HSBK]:
            stale = await real_read()
            await strip.apply_theme(make_theme("unit_test_b", GREEN))
            return stale

        monkeypatch.setattr(strip, "get_all_color_zones", read_then_repaint)
        await strip.get_current_theme()
        assert strip.current_theme == "unit_test_b"


async def _set_color_zones(light: MultiZoneLight) -> None:
    await light.set_color_zones(0, 1, RED)


async def _set_extended_color_zones(light: MultiZoneLight) -> None:
    await light.set_extended_color_zones(0, [RED, GREEN])


async def _set_extended_color_zones_fast(light: MultiZoneLight) -> None:
    await light.set_extended_color_zones(0, [RED, GREEN], fast=True)


async def _set_all_color_zones(light: MultiZoneLight) -> None:
    await light.set_all_color_zones([RED, GREEN])


async def _set_effect(light: MultiZoneLight) -> None:
    await light.set_effect(
        MultiZoneEffect(effect_type=FirmwareEffect.OFF, speed=0, duration=0)
    )


CLEARING_WRITES: dict[str, Callable[[MultiZoneLight], Awaitable[None]]] = {
    **COMMON_CLEARING_WRITES,
    "set_color_zones": _set_color_zones,
    "set_extended_color_zones": _set_extended_color_zones,
    "set_extended_color_zones_fast": _set_extended_color_zones_fast,
    "set_all_color_zones": _set_all_color_zones,
    "set_effect": _set_effect,
}


class TestWritesClearTheRecord:
    @pytest.mark.parametrize("name", sorted(CLEARING_WRITES))
    @pytest.mark.parametrize("kind", ["theme", "mood"])
    async def test_write_clears(
        self, strip: MultiZoneLight, name: str, kind: str
    ) -> None:
        await assert_write_clears(
            strip, make_theme("unit_test_a"), kind, CLEARING_WRITES[name]
        )

    @pytest.mark.parametrize("on", [False, True])
    async def test_set_power_keeps_the_record(
        self, strip: MultiZoneLight, on: bool
    ) -> None:
        await assert_power_keeps(strip, make_theme("unit_test_a"), on)


class TestStripEffectsEndTracking:
    """Starting any effect on a strip ends the tracked theme or mood."""

    @pytest.mark.parametrize("kind", ["theme", "mood"])
    @pytest.mark.parametrize(
        "effect_type",
        [FirmwareEffect.OFF, FirmwareEffect.MOVE, FirmwareEffect.MORPH],
    )
    async def test_set_effect_of_any_type_clears(
        self, strip: MultiZoneLight, kind: str, effect_type: FirmwareEffect
    ) -> None:
        paint = strip.apply_theme if kind == "theme" else strip.apply_mood
        await paint(make_theme("unit_test_a"))
        try:
            await strip.set_effect(
                MultiZoneEffect(effect_type=effect_type, speed=5000, duration=0)
            )
            assert strip.current_theme is None
            assert strip.current_mood is None
            assert await strip.get_current_theme() is None
            assert await strip.get_current_mood() is None
        finally:
            await strip.set_effect(
                MultiZoneEffect(effect_type=FirmwareEffect.OFF, speed=0, duration=0)
            )

    async def test_animate_mood_leaves_no_record(self, strip: MultiZoneLight) -> None:
        try:
            await strip.animate_mood(make_theme("unit_test_a"))
            assert strip.current_mood is None
            assert strip.current_theme is None
            assert await strip.get_current_mood() is None
        finally:
            await strip.stop_effect()

    @pytest.mark.parametrize("kind", ["theme", "mood"])
    async def test_conductor_start_clears_at_once(
        self, strip: MultiZoneLight, kind: str
    ) -> None:
        """Before the effect's own first write, not only once it has drawn."""
        paint = strip.apply_theme if kind == "theme" else strip.apply_mood
        await paint(make_theme("unit_test_a"))
        conductor = Conductor()
        try:
            await conductor.start(EffectColorloop(), [strip])
            assert strip.current_theme is None
            assert strip.current_mood is None
        finally:
            await conductor.stop([strip])


class TestMoveEffectPaintsATheme:
    """set_move_effect(theme=...) paints, then Move ends the record."""

    async def _stop(self, strip: MultiZoneLight) -> None:
        await strip.set_effect(
            MultiZoneEffect(effect_type=FirmwareEffect.OFF, speed=0, duration=0)
        )

    @pytest.mark.parametrize("by_slug", [False, True])
    async def test_theme_is_painted_then_move_runs(
        self, strip: MultiZoneLight, by_slug: bool
    ) -> None:
        # A library theme is looked up at test time; nothing about it is asserted.
        slug = ThemeLibrary.get_available_themes()[0]
        theme = get_theme(slug) if by_slug else make_theme("unit_test_a", RED, GREEN)
        await strip.set_color_zones(0, 0, AWKWARD)  # something to repaint
        try:
            await strip.set_move_effect(
                Direction.FORWARD, 5.0, theme=slug if by_slug else theme
            )
            assert (await strip.get_effect()).effect_type == FirmwareEffect.MOVE
            assert (await strip.get_all_color_zones())[0] != AWKWARD
            assert strip.current_theme is None
            assert strip.current_mood is None
        finally:
            await self._stop(strip)

    async def test_mood_is_painted_at_current_brightness(
        self, strip: MultiZoneLight
    ) -> None:
        theme = make_theme("unit_test_a", RED, GREEN)
        await strip.set_color_zones(0, 0, AWKWARD)  # something to repaint
        try:
            await strip.set_move_effect(Direction.FORWARD, 5.0, theme=theme, mood=True)
            assert (await strip.get_effect()).effect_type == FirmwareEffect.MOVE
            assert (await strip.get_all_color_zones())[0] != AWKWARD
            assert strip.current_mood is None
            assert strip.current_theme is None
        finally:
            await self._stop(strip)

    async def test_mood_turns_an_off_strip_on(self, strip: MultiZoneLight) -> None:
        await strip.set_power(False, duration=0.0)
        try:
            await strip.set_move_effect(
                Direction.FORWARD, 5.0, theme=make_theme("unit_test_a"), mood=True
            )
            assert await strip.get_power()
        finally:
            await self._stop(strip)

    async def test_mood_captures_no_prior_state(self, strip: MultiZoneLight) -> None:
        """Unlike animate_mood(), stopping has nothing to put back."""
        try:
            await strip.set_move_effect(
                Direction.FORWARD, 5.0, theme=make_theme("unit_test_a"), mood=True
            )
            await strip.stop_effect()
            assert (await strip.get_effect()).effect_type == FirmwareEffect.OFF
        finally:
            await self._stop(strip)

    async def test_theme_and_palette_together_raise(
        self, strip: MultiZoneLight
    ) -> None:
        with pytest.raises(ValueError, match="theme or palette"):
            await strip.set_move_effect(
                Direction.FORWARD, 5.0, palette=[RED], theme=make_theme()
            )

    async def test_mood_without_a_theme_raises(self, strip: MultiZoneLight) -> None:
        with pytest.raises(ValueError, match="mood requires a theme"):
            await strip.set_move_effect(Direction.FORWARD, 5.0, mood=True)

    async def test_unknown_slug_raises(self, strip: MultiZoneLight) -> None:
        with pytest.raises(KeyError):
            await strip.set_move_effect(
                Direction.FORWARD, 5.0, theme="no_such_theme_exists"
            )
