"""A paint record survives capture and restore only when it is still true.

stop_effect() after animate_mood() restores the colors captured beforehand and
puts back the theme the light was painted with, but only when the capture saw
that theme and the restore wrote it back exactly. Public device API against
the embedded emulator; a second device object stands in for the LIFX app.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from lifx.color import HSBK
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.exceptions import LifxTimeoutError
from lifx.protocol.protocol_types import FirmwareEffect
from tests.test_theme.conftest import (
    GREEN,
    RED,
    STRIP_SERIAL,
    make_theme,
    morphing,
)

pytestmark = pytest.mark.emulator

BLOCKED = LifxTimeoutError("no reply")


@pytest.fixture
async def strip_app(emulator_server) -> AsyncIterator[MultiZoneLight]:
    """Another client of the same strip: what the LIFX app does."""
    port, _, _ = emulator_server
    async with MultiZoneLight(
        serial=STRIP_SERIAL, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2
    ) as light:
        yield light


def refuse(*_args: Any, **_kwargs: Any) -> None:
    raise BLOCKED


class TestExternalChange:
    async def test_strip_changed_by_another_client_is_not_restored_as_current(
        self, strip: MultiZoneLight, strip_app: MultiZoneLight
    ) -> None:
        await strip.apply_theme(make_theme("unit_test_a"))
        zones = await strip_app.get_all_color_zones()
        await strip_app.set_all_color_zones([*zones[:-1], HSBK(300, 1.0, 1.0, 3500)])
        await strip.animate_mood(morphing())
        await strip.stop_effect()
        assert strip.current_theme is None
        assert strip.current_mood is None

    async def test_matrix_changed_by_another_client_is_not_restored_as_current(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        await matrix.apply_theme(make_theme("unit_test_a", static_mode="grid_static"))
        shown = (await app.get_all_tile_colors())[0]
        await app.set_matrix_colors(0, [*shown[:-1], HSBK(300, 1.0, 1.0, 3500)])
        await matrix.animate_mood(morphing())
        await matrix.stop_effect()
        assert matrix.current_theme is None
        assert matrix.current_mood is None

    async def test_write_during_capture_drops_the_record(
        self, strip: MultiZoneLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A repaint with the same theme is a new record; the old one is stale."""
        theme = make_theme("unit_test_a")
        await strip.apply_theme(theme)
        real_get_color = strip.get_color

        async def read_then_repaint() -> Any:
            result = await real_get_color()
            await strip.apply_theme(theme)
            return result

        monkeypatch.setattr(strip, "get_color", read_then_repaint)
        await strip.animate_mood(morphing())
        monkeypatch.undo()
        await strip.stop_effect()
        assert strip.current_theme is None


class TestPriorRecordKind:
    async def test_morph_record_is_not_restored_as_current(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        """Restoring still colors does not resume a Morph the app ended."""
        await matrix.animate_mood(morphing("unit_test_m"))
        assert matrix.current_mood == "unit_test_m"
        await app.set_effect(FirmwareEffect.OFF)
        await matrix.animate_mood(morphing("unit_test_n", GREEN, RED))
        await matrix.stop_effect()
        assert matrix.current_mood is None
        assert matrix.current_theme is None


class TestRestoreFailure:
    async def test_failed_tile_write_clears_the_record(
        self, matrix: MatrixLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await matrix.apply_theme(make_theme("unit_test_a", static_mode="grid_static"))
        await matrix.animate_mood(morphing())
        monkeypatch.setattr(matrix, "set_matrix_colors", refuse)
        await matrix.stop_effect()
        assert matrix.current_theme is None

    async def test_zone_restore_falling_back_to_color_clears_the_record(
        self, strip: MultiZoneLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await strip.apply_theme(make_theme("unit_test_a"))
        await strip.animate_mood(morphing())
        monkeypatch.setattr(strip, "set_all_color_zones", refuse)
        await strip.stop_effect()
        assert strip.current_theme is None


class TestHappyPath:
    async def test_strip_theme_returns_after_a_mood(
        self, strip: MultiZoneLight
    ) -> None:
        await strip.apply_theme(make_theme("unit_test_a", RED, GREEN))
        await strip.animate_mood(morphing())
        await strip.stop_effect()
        assert strip.current_theme == "unit_test_a"

    async def test_matrix_theme_returns_after_a_mood(self, matrix: MatrixLight) -> None:
        await matrix.apply_theme(make_theme("unit_test_a", static_mode="grid_static"))
        await matrix.animate_mood(morphing())
        await matrix.stop_effect()
        assert matrix.current_theme == "unit_test_a"
