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
from lifx.protocol.protocol_types import FirmwareEffect, LightWaveform
from lifx.theme import Theme, get_theme

pytestmark = pytest.mark.emulator

STRIP_SERIAL = "d073d5000005"

RED = HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500)
GREEN = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
# Values that no uint16 holds exactly, so every write is rounded.
AWKWARD = HSBK(hue=33.3333, saturation=0.33333, brightness=0.77777, kelvin=3500)


def themed(slug: str | None = "unit_test_a", *colours: HSBK) -> Theme:
    """A caller-built theme carrying a slug, never a library theme."""
    return Theme(
        list(colours) or [RED, GREEN, AWKWARD],
        slug=slug,
        static_mode="solid_static",
    )


@pytest.fixture
async def strip(emulator_server) -> AsyncIterator[MultiZoneLight]:
    """A connected strip, painted plain so no earlier test leaks a theme."""
    port, _, _ = emulator_server
    async with MultiZoneLight(
        serial=STRIP_SERIAL, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2
    ) as light:
        await light.set_power(True)
        yield light


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
        await strip.apply_theme(themed("unit_test_a"))
        assert strip.current_theme == "unit_test_a"
        assert strip.current_mood is None

    async def test_apply_mood_records_mood(self, strip: MultiZoneLight) -> None:
        await strip.apply_mood(themed("unit_test_a"))
        assert strip.current_mood == "unit_test_a"
        assert strip.current_theme is None

    async def test_mood_replaces_theme_and_back(self, strip: MultiZoneLight) -> None:
        await strip.apply_theme(themed("unit_test_a"))
        await strip.apply_mood(themed("unit_test_b"))
        assert (strip.current_theme, strip.current_mood) == (None, "unit_test_b")
        await strip.apply_theme(themed("unit_test_c"))
        assert (strip.current_theme, strip.current_mood) == ("unit_test_c", None)

    async def test_slugless_theme_leaves_both_none(self, strip: MultiZoneLight) -> None:
        await strip.apply_theme(themed("unit_test_a"))
        await strip.apply_theme(themed(None))
        assert (strip.current_theme, strip.current_mood) == (None, None)
        await strip.apply_mood(themed("unit_test_a"))
        await strip.apply_mood(themed(None))
        assert (strip.current_theme, strip.current_mood) == (None, None)

    async def test_second_object_starts_empty(
        self, strip: MultiZoneLight, app: MultiZoneLight
    ) -> None:
        await strip.apply_theme(themed())
        assert app.current_theme is None


class TestVerification:
    async def test_unchanged_strip_confirms(self, strip: MultiZoneLight) -> None:
        await strip.apply_theme(themed("unit_test_a"))
        assert await strip.get_current_theme() == "unit_test_a"
        assert await strip.get_current_mood() is None
        assert strip.current_theme == "unit_test_a"

    async def test_unchanged_mood_confirms(self, strip: MultiZoneLight) -> None:
        await strip.apply_mood(themed("unit_test_a"))
        assert await strip.get_current_mood() == "unit_test_a"
        assert await strip.get_current_theme() is None
        assert strip.current_mood == "unit_test_a"

    async def test_nothing_recorded_reads_nothing(self, strip: MultiZoneLight) -> None:
        assert await strip.get_current_theme() is None
        assert await strip.get_current_mood() is None

    async def test_rounding_is_not_a_change(self, strip: MultiZoneLight) -> None:
        await strip.apply_theme(themed("unit_test_a", AWKWARD))
        assert await strip.get_current_theme() == "unit_test_a"

    async def test_external_zone_change_clears(
        self, strip: MultiZoneLight, app: MultiZoneLight
    ) -> None:
        await strip.apply_theme(themed("unit_test_a"))
        await app.set_color_zones(0, 0, HSBK(240, 1.0, 1.0, 3500))
        assert await strip.get_current_theme() is None
        assert strip.current_theme is None

    async def test_external_dimming_clears(
        self, strip: MultiZoneLight, app: MultiZoneLight
    ) -> None:
        await strip.apply_mood(themed("unit_test_a"))
        zones = await app.get_all_color_zones()
        await app.set_all_color_zones(
            [HSBK(z.hue, z.saturation, z.brightness * 0.5, z.kelvin) for z in zones]
        )
        assert await strip.get_current_mood() is None
        assert strip.current_mood is None

    async def test_refresh_state_clears_stale_record(
        self, strip: MultiZoneLight, app: MultiZoneLight
    ) -> None:
        await strip.apply_theme(themed("unit_test_a"))
        await app.set_color_zones(1, 1, HSBK(240, 1.0, 1.0, 3500))
        await strip.refresh_state()
        assert strip.current_theme is None

    async def test_refresh_state_keeps_matching_record(
        self, strip: MultiZoneLight
    ) -> None:
        await strip.apply_theme(themed("unit_test_a"))
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
        await strip.apply_theme(themed("unit_test_a"))
        real_read = strip.get_all_color_zones

        async def read_then_repaint() -> list[HSBK]:
            stale = await real_read()
            await strip.apply_theme(themed("unit_test_b", GREEN))
            return stale

        monkeypatch.setattr(strip, "get_all_color_zones", read_then_repaint)
        await strip.get_current_theme()
        assert strip.current_theme == "unit_test_b"


async def _set_color(light: MultiZoneLight) -> None:
    await light.set_color(RED)


async def _set_brightness(light: MultiZoneLight) -> None:
    await light.set_brightness(0.5)


async def _set_waveform(light: MultiZoneLight) -> None:
    await light.set_waveform(RED, 1.0, 1, LightWaveform.SINE)


async def _pulse(light: MultiZoneLight) -> None:
    await light.pulse(RED, period=0.1, cycles=1)


async def _breathe(light: MultiZoneLight) -> None:
    await light.breathe(RED, period=0.1, cycles=1)


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


async def _start_effect(light: MultiZoneLight) -> None:
    try:
        await light.start_effect(EffectColorloop())
    finally:
        await light.stop_effect()


CLEARING_WRITES: dict[str, Callable[[MultiZoneLight], Awaitable[None]]] = {
    "set_color": _set_color,
    "set_brightness": _set_brightness,
    "set_waveform": _set_waveform,
    "pulse": _pulse,
    "breathe": _breathe,
    "set_color_zones": _set_color_zones,
    "set_extended_color_zones": _set_extended_color_zones,
    "set_extended_color_zones_fast": _set_extended_color_zones_fast,
    "set_all_color_zones": _set_all_color_zones,
    "set_effect": _set_effect,
    "start_effect": _start_effect,
}


class TestWritesClearTheRecord:
    @pytest.mark.parametrize("name", sorted(CLEARING_WRITES))
    @pytest.mark.parametrize("kind", ["theme", "mood"])
    async def test_write_clears(
        self, strip: MultiZoneLight, name: str, kind: str
    ) -> None:
        if kind == "theme":
            await strip.apply_theme(themed("unit_test_a"))
        else:
            await strip.apply_mood(themed("unit_test_a"))
        assert (strip.current_theme or strip.current_mood) == "unit_test_a"

        await CLEARING_WRITES[name](strip)

        assert strip.current_theme is None
        assert strip.current_mood is None

    @pytest.mark.parametrize("on", [False, True])
    async def test_set_power_keeps_the_record(
        self, strip: MultiZoneLight, on: bool
    ) -> None:
        await strip.apply_theme(themed("unit_test_a"))
        await strip.set_power(on)
        assert strip.current_theme == "unit_test_a"
        await strip.set_power(not on, duration=0.0)
        assert strip.current_theme == "unit_test_a"


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
        await paint(themed("unit_test_a"))
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
            await strip.animate_mood(themed("unit_test_a"))
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
        await paint(themed("unit_test_a"))
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
        theme = get_theme("evening") if by_slug else themed("unit_test_a", RED, GREEN)
        await strip.set_color_zones(0, 0, AWKWARD)  # something to repaint
        try:
            await strip.set_move_effect(
                Direction.FORWARD, 5.0, theme="evening" if by_slug else theme
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
        theme = themed("unit_test_a", RED, GREEN)
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
                Direction.FORWARD, 5.0, theme=themed("unit_test_a"), mood=True
            )
            assert await strip.get_power()
        finally:
            await self._stop(strip)

    async def test_mood_captures_no_prior_state(self, strip: MultiZoneLight) -> None:
        """Unlike animate_mood(), stopping has nothing to put back."""
        try:
            await strip.set_move_effect(
                Direction.FORWARD, 5.0, theme=themed("unit_test_a"), mood=True
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
                Direction.FORWARD, 5.0, palette=[RED], theme=themed()
            )

    async def test_mood_without_a_theme_raises(self, strip: MultiZoneLight) -> None:
        with pytest.raises(ValueError, match="mood requires a theme"):
            await strip.set_move_effect(Direction.FORWARD, 5.0, mood=True)

    async def test_unknown_slug_raises(self, strip: MultiZoneLight) -> None:
        with pytest.raises(KeyError):
            await strip.set_move_effect(
                Direction.FORWARD, 5.0, theme="no_such_theme_exists"
            )
