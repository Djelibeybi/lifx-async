"""Tests for the current mood a matrix light keeps while a mood animation runs.

Public device API against the embedded emulator. A second device object for
the same light stands in for the LIFX app.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from lifx_emulator.factories import create_device

from lifx.devices.ceiling import CeilingLight
from lifx.devices.effect_runner import _Registry, effect_runner
from lifx.devices.matrix import MatrixLight
from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects import EffectColorloop
from lifx.exceptions import LifxUnsupportedCommandError
from lifx.protocol.protocol_types import FirmwareEffect
from lifx.theme import Theme
from tests.conftest import remove_emulated_device
from tests.test_theme.conftest import (
    BLUE,
    GREEN,
    RED,
    make_theme,
    morphing,
)

pytestmark = pytest.mark.emulator


def scrolling(slug: str | None = "unit_test_s") -> Theme:
    """A caller-built slugged theme whose mood scrolls (a MOVE mood)."""
    return make_theme(slug, RED, GREEN, BLUE)


class TestMorph:
    async def test_morph_mood_is_current(self, matrix: MatrixLight) -> None:
        await matrix.animate_mood(morphing())
        assert matrix.current_mood == "unit_test_m"
        assert matrix.current_theme is None
        assert await matrix.get_current_mood() == "unit_test_m"

    async def test_palette_order_does_not_matter(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        await matrix.animate_mood(morphing())
        sent = (await app.get_effect()).palette
        assert sent is not None
        await app.set_effect(
            FirmwareEffect.MORPH, speed=3.0, palette=list(reversed(sent))
        )
        assert await matrix.get_current_mood() == "unit_test_m"

    async def test_a_different_palette_clears(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        await matrix.animate_mood(morphing())
        await app.set_effect(FirmwareEffect.MORPH, speed=3.0, palette=[RED, RED])
        assert await matrix.get_current_mood() is None
        assert matrix.current_mood is None

    async def test_morph_stopped_clears(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        await matrix.animate_mood(morphing())
        await app.set_effect(FirmwareEffect.OFF)
        assert await matrix.get_current_mood() is None

    async def test_a_different_effect_clears(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        await matrix.animate_mood(morphing())
        await app.set_effect(FirmwareEffect.FLAME, speed=3.0)
        assert await matrix.get_current_mood() is None

    async def test_refresh_state_verifies(
        self, matrix: MatrixLight, app: MatrixLight
    ) -> None:
        await matrix.animate_mood(morphing())
        await matrix.refresh_state()
        assert matrix.current_mood == "unit_test_m"
        await app.set_effect(FirmwareEffect.OFF)
        await matrix.refresh_state()
        assert matrix.current_mood is None

    async def test_a_light_rejecting_effect_queries_clears(
        self, matrix: MatrixLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await matrix.animate_mood(morphing())

        async def reject() -> None:
            raise LifxUnsupportedCommandError("no effects")

        monkeypatch.setattr(matrix, "get_effect", reject)
        assert await matrix.get_current_mood() is None

    async def test_slugless_theme_records_nothing(self, matrix: MatrixLight) -> None:
        await matrix.animate_mood(morphing(None))
        assert matrix.current_mood is None


class TestRestore:
    async def test_stop_restores_the_prior_theme_after_morph(
        self, matrix: MatrixLight
    ) -> None:
        await matrix.apply_theme(scrolling("unit_test_before"))
        await matrix.animate_mood(morphing())
        assert matrix.current_mood == "unit_test_m"
        await matrix.stop_effect()
        assert matrix.current_theme == "unit_test_before"
        assert await matrix.get_current_theme() == "unit_test_before"

    async def test_stop_restores_the_prior_mood_after_morph(
        self, matrix: MatrixLight
    ) -> None:
        await matrix.apply_mood(scrolling("unit_test_before"))
        await matrix.animate_mood(morphing())
        await matrix.stop_effect()
        assert matrix.current_mood == "unit_test_before"
        assert matrix.current_theme is None

    async def test_stop_with_no_prior_record_leaves_none(
        self, matrix: MatrixLight
    ) -> None:
        await matrix.animate_mood(morphing())
        await matrix.stop_effect()
        assert (matrix.current_theme, matrix.current_mood) == (None, None)

    async def test_restart_keeps_the_first_prior_record(
        self, matrix: MatrixLight
    ) -> None:
        await matrix.apply_theme(scrolling("unit_test_before"))
        await matrix.animate_mood(morphing("unit_test_one"))
        await matrix.animate_mood(morphing("unit_test_two"))
        assert matrix.current_mood == "unit_test_two"
        await matrix.stop_effect()
        assert matrix.current_theme == "unit_test_before"

    async def test_stop_restores_the_prior_record_after_a_scroll(
        self, matrix: MatrixLight
    ) -> None:
        await matrix.apply_theme(morphing("unit_test_before"))
        await matrix.animate_mood(scrolling())
        await matrix.stop_effect()
        assert matrix.current_theme == "unit_test_before"
        assert await matrix.get_current_theme() == "unit_test_before"

    async def test_apply_mood_restarts_a_running_morph(
        self, matrix: MatrixLight
    ) -> None:
        await matrix.animate_mood(morphing("unit_test_one"))
        await matrix.apply_mood(morphing("unit_test_two"))
        assert matrix.current_mood == "unit_test_two"
        assert await matrix.get_current_mood() == "unit_test_two"


class TestScroll:
    async def test_scroll_mood_is_current_while_it_runs(
        self, matrix: MatrixLight
    ) -> None:
        await matrix.animate_mood(scrolling())
        assert matrix.current_mood == "unit_test_s"
        assert await matrix.get_current_mood() == "unit_test_s"
        assert await matrix.get_current_theme() is None

    async def test_stopping_the_run_ends_the_record(self, matrix: MatrixLight) -> None:
        await matrix.animate_mood(scrolling())
        await matrix.stop_effect()
        assert await matrix.get_current_mood() is None

    async def test_replacing_the_run_ends_the_record(self, matrix: MatrixLight) -> None:
        await matrix.animate_mood(scrolling())
        await matrix.start_effect(EffectColorloop())
        assert matrix.current_mood is None
        assert await matrix.get_current_mood() is None

    async def test_apply_mood_restarts_a_running_scroll(
        self, matrix: MatrixLight
    ) -> None:
        await matrix.animate_mood(scrolling("unit_test_one"))
        await matrix.apply_mood(scrolling("unit_test_two"))
        assert matrix.current_mood == "unit_test_two"
        assert await matrix.get_current_mood() == "unit_test_two"

    async def test_refresh_state_confirms_a_live_run(self, matrix: MatrixLight) -> None:
        await matrix.animate_mood(scrolling())
        await matrix.refresh_state()
        assert matrix.current_mood == "unit_test_s"


@dataclass
class IdleRunner:
    """Wraps the real runner but reports an effect other than the scroll."""

    real: Any
    other: object | None = None
    log: list[Any] = field(default_factory=list)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.real, name)

    def mood_run(self, light: object) -> object | None:
        return self.other


class TestRunNotInCharge:
    async def test_no_record_when_the_runner_does_not_run_it(
        self, matrix: MatrixLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_Registry, "runner", IdleRunner(effect_runner()))
        await matrix.animate_mood(scrolling())
        assert matrix.current_mood is None


class TestMirror:
    async def test_mirror_scroll_mood_runs_morph_and_is_tracked(
        self, mirror_device: MirrorLight
    ) -> None:
        async with mirror_device:
            await mirror_device.set_power(True)
            await mirror_device.animate_mood(scrolling())
            effect = await mirror_device.get_effect()
            assert effect.effect_type == FirmwareEffect.MORPH
            assert mirror_device.current_mood == "unit_test_s"
            assert await mirror_device.get_current_mood() == "unit_test_s"
            await mirror_device.stop_effect()


@pytest.fixture(params=[171, 173], ids=["spot", "path"])
async def morph_only_light(
    request: pytest.FixtureRequest, emulator_server
) -> AsyncIterator[MatrixLight]:
    """A Spot or a Path, which run firmware MORPH for every mood."""
    port, server, scenario_manager = emulator_server
    if server is None:
        pytest.skip("Cannot create devices with an external emulator")
    serial = f"d073d5000{request.param:03x}"
    server.add_device(
        create_device(
            product_id=request.param, serial=serial, scenario_manager=scenario_manager
        )
    )
    try:
        async with MatrixLight(
            serial=serial, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2
        ) as light:
            await light.set_power(True)
            yield light
            await light.stop_effect()
    finally:
        remove_emulated_device(server, serial)


class TestMorphOnlyProducts:
    async def test_scroll_mood_runs_morph_and_is_tracked(
        self, morph_only_light: MatrixLight
    ) -> None:
        await morph_only_light.animate_mood(scrolling())
        effect = await morph_only_light.get_effect()
        assert effect.effect_type == FirmwareEffect.MORPH
        assert morph_only_light.current_mood == "unit_test_s"
        assert await morph_only_light.get_current_mood() == "unit_test_s"


class TestCeiling:
    async def test_scroll_mood_stays_current_while_it_writes(
        self, ceiling_device: CeilingLight
    ) -> None:
        async with ceiling_device:
            await ceiling_device.set_power(True)
            try:
                await ceiling_device.animate_mood(scrolling())
                # Let the scroll write a few frames.
                await asyncio.sleep(0.5)
                assert ceiling_device.current_mood == "unit_test_s"
                assert await ceiling_device.get_current_mood() == "unit_test_s"
            finally:
                await ceiling_device.stop_effect()


@dataclass
class ControlledRunner:
    """Wraps the real runner but lets a test say which run is active."""

    real: Any
    active: object | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.real, name)

    def mood_run(self, light: object) -> object | None:
        return self.active


@pytest.fixture
def controlled(monkeypatch: pytest.MonkeyPatch) -> ControlledRunner:
    """The real runner, with the scroll it starts reported as the active run."""
    fake = ControlledRunner(effect_runner())
    monkeypatch.setattr(_Registry, "runner", fake)
    real_scroll = fake.real.scroll_effect

    def scroll(frame: Any, vertical: bool) -> Any:
        fake.active = real_scroll(frame, vertical)
        return fake.active

    fake.scroll_effect = scroll  # type: ignore[method-assign]
    return fake


class TestRunLifetime:
    async def test_record_follows_the_run_not_the_colors(
        self, matrix: MatrixLight, controlled: ControlledRunner
    ) -> None:
        fake = controlled
        await matrix.animate_mood(scrolling())
        await asyncio.sleep(0.3)  # several frames: they must not end the record
        assert await matrix.get_current_mood() == "unit_test_s"
        fake.active = object()  # replaced by some other run
        assert await matrix.get_current_mood() is None
        assert matrix.current_mood is None

    async def test_stopped_run_ends_the_record(
        self, matrix: MatrixLight, controlled: ControlledRunner
    ) -> None:
        await matrix.animate_mood(scrolling())
        controlled.active = None
        await matrix.refresh_state()
        assert matrix.current_mood is None


class TestStrip:
    async def test_stop_restores_the_prior_record_on_a_strip(
        self, emulator_server
    ) -> None:
        port, _, _ = emulator_server
        async with MultiZoneLight(
            serial="d073d5000005", ip="127.0.0.1", port=port, timeout=2.0
        ) as strip:
            await strip.set_power(True)
            await strip.apply_theme(scrolling("unit_test_before"))
            await strip.animate_mood(scrolling("unit_test_s"))
            assert strip.current_mood is None
            await strip.stop_effect()
            assert strip.current_theme == "unit_test_before"
            assert await strip.get_current_theme() == "unit_test_before"
