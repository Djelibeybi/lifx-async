"""Tests for animate_mood() and the apply_mood() restart rule."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.api import DeviceGroup
from lifx.color import HSBK
from lifx.const import MOOD_FADE_SECONDS, MOOD_MORPH_SPEED_SECONDS
from lifx.devices.effect_runner import _Registry, effect_runner
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight
from lifx.effects import EffectColorloop, EffectScroll
from lifx.effects.models import PreState
from lifx.exceptions import LifxTimeoutError, LifxUnsupportedCommandError
from lifx.products import moves_as_morph
from lifx.protocol.protocol_types import Direction, FirmwareEffect
from lifx.theme import Theme
from tests.test_theme.conftest import make_tile

RED = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
GREEN = HSBK(hue=120, saturation=1.0, brightness=0.5, kelvin=3500)
MOVE_THEME = Theme([RED, GREEN], static_mode="solid_static")  # resolves to move
GRID_THEME = Theme([RED, GREEN], static_mode="grid_static")  # resolves to move
MORPH_THEME = Theme([RED, GREEN], static_mode="blended")  # resolves to morph


def dim(brightness: float) -> HSBK:
    return HSBK(hue=240, saturation=1.0, brightness=brightness, kelvin=3500)


def prior(
    brightness: float = 1.0,
    *,
    power: bool = True,
    zones: list[HSBK] | None = None,
    tiles: list[list[HSBK]] | None = None,
) -> PreState:
    return PreState(
        power=power, color=dim(brightness), zone_colors=zones, tile_colors=tiles
    )


@dataclass
class FakeRunner:
    """Records what lights ask of the effects package."""

    prestate: PreState = field(default_factory=prior)
    mood_running: bool = False
    log: list[Any] = field(default_factory=list)

    async def start(
        self,
        participant: object,
        effect: object,
        *,
        enable_thread: bool = False,
        prestate: object = None,
    ) -> None:
        self.log.append(("start", effect, prestate))

    async def leave_every_run(
        self, participant: object, *, restore_state: bool = True
    ) -> None:
        self.log.append(("leave", restore_state))

    async def take_prestate(self, light: object) -> PreState:
        self.log.append("take")
        return self.prestate

    async def restore_prestate(self, light: object, prestate: object) -> None:
        self.log.append(("restore", prestate))

    def runs_whole_light(self, light: object) -> bool:
        return False

    def runs_mood_effect(self, light: object) -> bool:
        return self.mood_running

    def scroll_effect(self, frame: list[list[HSBK]], vertical: bool) -> EffectScroll:
        return EffectScroll(frame=frame, vertical=vertical)

    def palette_effect(self, colors: list[HSBK]) -> EffectColorloop:
        return EffectColorloop(palette=colors)

    async def start_together(
        self, lights: list[Light], effect: object, *, prestates: list[object]
    ) -> None:
        self.log.append(("together", list(lights), effect, list(prestates)))

    def started(self) -> tuple[Any, Any]:
        """The effect and prior state of the last start."""
        _, effect, prestate = next(e for e in reversed(self.log) if e[0] == "start")
        return effect, prestate


@pytest.fixture
def runner(monkeypatch) -> FakeRunner:
    fake = FakeRunner()
    monkeypatch.setattr(_Registry, "runner", fake)
    return fake


def prime(light: Light, runner: FakeRunner, *, on: bool = True) -> Any:
    light._paints_moods = AsyncMock(return_value=True)
    light.get_power = AsyncMock(return_value=65535 if on else 0)
    light.set_power = AsyncMock(
        side_effect=lambda *a, **k: runner.log.append(("power", a, k))
    )
    light.set_effect = AsyncMock(side_effect=lambda *a, **k: runner.log.append("fx"))
    light._stop_firmware_effect = AsyncMock(
        side_effect=lambda: runner.log.append("stop-fx")
    )

    async def paint(theme: Theme, **kwargs: Any) -> list[list[HSBK]]:
        runner.log.append(("paint", kwargs))
        return [[RED] * 4]

    light._paint_mood = AsyncMock(side_effect=paint)
    light.get_effect = AsyncMock(return_value=MagicMock(effect_type=FirmwareEffect.OFF))
    return light


def painted(runner: FakeRunner) -> dict[str, Any]:
    return next(e[1] for e in runner.log if e[0] == "paint")


class TestBulb:
    async def test_runs_a_palette_colour_loop(
        self, mock_device_factory, runner
    ) -> None:
        light = prime(mock_device_factory(Light), runner)
        await light.animate_mood(MORPH_THEME)
        effect, prestate = runner.started()
        assert isinstance(effect, EffectColorloop)
        assert effect.palette == [RED, GREEN]
        assert prestate is runner.prestate
        assert runner.log[0] == "take"

    async def test_palette_is_rescaled_to_the_bulb(
        self, mock_device_factory, runner
    ) -> None:
        runner.prestate = prior(0.2)
        light = prime(mock_device_factory(Light), runner)
        await light.animate_mood(MORPH_THEME)
        effect, _ = runner.started()
        assert max(c.brightness for c in effect.palette) == pytest.approx(0.2)

    async def test_skips_a_light_without_colour(
        self, mock_device_factory, runner
    ) -> None:
        light = prime(mock_device_factory(Light), runner)
        light._paints_moods = AsyncMock(return_value=False)
        await light.animate_mood(MORPH_THEME)
        assert runner.log == []


class TestStrip:
    @pytest.mark.parametrize("theme", [MOVE_THEME, MORPH_THEME])
    async def test_paints_then_starts_firmware_move(
        self, mock_device_factory, runner, theme
    ) -> None:
        strip = prime(mock_device_factory(MultiZoneLight, product=32), runner)
        strip.get_zone_count = AsyncMock(return_value=32)
        await strip.animate_mood(theme)
        assert runner.log == ["take", ("paint", painted(runner)), "fx"]
        effect = strip.set_effect.await_args.args[0]
        assert effect == MultiZoneEffect.move(Direction.FORWARD, 40.0)
        assert strip._mood_prestate is runner.prestate

    async def test_paints_at_the_brightest_zone_before_the_animation(
        self, mock_device_factory, runner
    ) -> None:
        runner.prestate = prior(0.1, zones=[dim(0.3), dim(0.6)])
        strip = prime(mock_device_factory(MultiZoneLight, product=32), runner)
        strip.get_zone_count = AsyncMock(return_value=2)
        await strip.animate_mood(MOVE_THEME)
        assert painted(runner)["brightness"] == pytest.approx(0.6)

    @pytest.mark.parametrize("on", [True, False])
    async def test_an_off_strip_is_painted_on(
        self, mock_device_factory, runner, on
    ) -> None:
        strip = prime(mock_device_factory(MultiZoneLight, product=32), runner, on=on)
        strip.get_zone_count = AsyncMock(return_value=2)
        await strip.animate_mood(MOVE_THEME)
        assert painted(runner)["power_on"] is not on

    async def test_skips_a_strip_without_colour(
        self, mock_device_factory, runner
    ) -> None:
        strip = prime(mock_device_factory(MultiZoneLight, product=32), runner)
        strip._paints_moods = AsyncMock(return_value=False)
        await strip.animate_mood(MOVE_THEME)
        strip.set_effect.assert_not_awaited()


class TestMatrixMorph:
    async def test_sends_the_theme_palette(self, mock_device_factory, runner) -> None:
        light = prime(mock_device_factory(MatrixLight), runner)
        await light.animate_mood(MORPH_THEME)
        light._paint_mood.assert_not_awaited()
        light.set_effect.assert_awaited_once_with(
            FirmwareEffect.MORPH, speed=MOOD_MORPH_SPEED_SECONDS, palette=[RED, GREEN]
        )
        assert light._mood_prestate is runner.prestate

    async def test_palette_is_rescaled_to_the_brightest_pixel(
        self, mock_device_factory, runner
    ) -> None:
        runner.prestate = prior(0.1, tiles=[[dim(0.2), dim(0.4), dim(0.0), dim(0.1)]])
        light = prime(mock_device_factory(MatrixLight), runner)
        light._device_chain = [make_tile(0, width=2, height=2)]
        await light.animate_mood(MORPH_THEME)
        palette = light.set_effect.await_args.kwargs["palette"]
        assert max(c.brightness for c in palette) == pytest.approx(0.4)

    async def test_an_off_light_powers_on_after_the_effect(
        self, mock_device_factory, runner
    ) -> None:
        light = prime(mock_device_factory(MatrixLight), runner, on=False)
        await light.animate_mood(MORPH_THEME)
        assert runner.log == [
            "take",
            "fx",
            ("power", (True,), {"duration": MOOD_FADE_SECONDS}),
        ]

    async def test_an_on_light_is_not_powered(
        self, mock_device_factory, runner
    ) -> None:
        light = prime(mock_device_factory(MatrixLight), runner)
        await light.animate_mood(MORPH_THEME)
        light.set_power.assert_not_awaited()

    @pytest.mark.parametrize("product", [267, 171])
    async def test_mirror_and_spot_substitute_morph(
        self, mock_device_factory, runner, product
    ) -> None:
        cls = MirrorLight if product == 267 else MatrixLight
        light = prime(mock_device_factory(cls, product=product), runner)
        await light.animate_mood(MOVE_THEME)
        assert light.set_effect.await_args.args[0] == FirmwareEffect.MORPH

    def test_moves_as_morph(self) -> None:
        assert moves_as_morph(267)
        assert not moves_as_morph(217)


class TestMatrixMove:
    async def test_captures_before_painting_then_scrolls_the_frame(
        self, mock_device_factory, runner
    ) -> None:
        light = prime(mock_device_factory(MatrixLight), runner, on=False)
        await light.animate_mood(MOVE_THEME)
        assert [e if isinstance(e, str) else e[0] for e in runner.log] == [
            "take",
            "stop-fx",
            "paint",
            "start",
        ]
        assert painted(runner)["power_on"] is True
        effect, prestate = runner.started()
        assert isinstance(effect, EffectScroll)
        assert effect.frame == [[RED] * 4]
        assert prestate is runner.prestate
        # The scroll's run holds the prior state, not the light.
        assert light._mood_prestate is None

    async def test_paints_at_the_brightness_before_the_animation(
        self, mock_device_factory, runner
    ) -> None:
        runner.prestate = prior(0.1, tiles=[[dim(0.3)] * 4])
        light = prime(mock_device_factory(MatrixLight), runner)
        light._device_chain = [make_tile(0, width=2, height=2)]
        await light.animate_mood(MOVE_THEME)
        assert painted(runner)["brightness"] == pytest.approx(0.3)

    @pytest.mark.parametrize("on", [True, False])
    async def test_no_tiles_starts_no_scroll(
        self, mock_device_factory, runner, on
    ) -> None:
        light = prime(mock_device_factory(MatrixLight), runner, on=on)
        light._paint_mood = AsyncMock(return_value=[])
        await light.animate_mood(MOVE_THEME)
        assert not any(e[0] == "start" for e in runner.log if isinstance(e, tuple))
        assert light._mood_prestate is runner.prestate
        if on:
            light.set_power.assert_not_awaited()
        else:
            light.set_power.assert_awaited_once_with(True, duration=MOOD_FADE_SECONDS)

    async def test_skips_a_matrix_light_without_colour(
        self, mock_device_factory, runner
    ) -> None:
        light = prime(mock_device_factory(MatrixLight), runner)
        light._paints_moods = AsyncMock(return_value=False)
        await light.animate_mood(MORPH_THEME)
        assert runner.log == []

    @pytest.mark.parametrize(
        ("theme", "vertical"), [(MOVE_THEME, True), (GRID_THEME, False)]
    )
    async def test_tube_scrolls_stripes_vertically(
        self, mock_device_factory, runner, theme, vertical
    ) -> None:
        tube = prime(mock_device_factory(MatrixLight, product=217), runner)
        await tube.animate_mood(theme)
        effect, _ = runner.started()
        assert isinstance(effect, EffectScroll)
        assert effect.vertical is vertical


class TestPriorStateOwnership:
    async def test_a_restart_keeps_the_held_state(
        self, mock_device_factory, runner
    ) -> None:
        light = prime(mock_device_factory(MatrixLight), runner)
        original = prior(0.7)
        light._mood_prestate = original
        light.get_effect = AsyncMock(
            return_value=MagicMock(effect_type=FirmwareEffect.MORPH)
        )
        await light.animate_mood(MORPH_THEME)
        assert "take" not in runner.log
        assert runner.log[0] == ("leave", False)
        assert light._mood_prestate is original

    async def test_morph_to_move_hands_the_held_state_to_the_scroll(
        self, mock_device_factory, runner
    ) -> None:
        light = prime(mock_device_factory(MatrixLight), runner)
        original = prior(0.7)
        light._mood_prestate = original
        light.get_effect = AsyncMock(
            return_value=MagicMock(effect_type=FirmwareEffect.MORPH)
        )
        await light.animate_mood(MOVE_THEME)
        _, prestate = runner.started()
        assert prestate is original
        assert light._mood_prestate is None

    async def test_a_held_state_without_a_running_mood_is_recaptured(
        self, mock_device_factory, runner
    ) -> None:
        light = prime(mock_device_factory(MatrixLight), runner)
        light._mood_prestate = prior(0.7)
        await light.animate_mood(MORPH_THEME)
        assert runner.log[0] == "take"
        assert light._mood_prestate is runner.prestate


class TestStopRestores:
    async def test_restores_the_held_state_once(
        self, mock_device_factory, runner
    ) -> None:
        light = prime(mock_device_factory(MatrixLight), runner)
        original = prior(0.7, power=False)
        light._mood_prestate = original
        await light.stop_effect()
        assert runner.log == ["stop-fx", ("leave", False), ("restore", original)]
        runner.log.clear()
        await light.stop_effect()
        assert runner.log == ["stop-fx", ("leave", True)]

    async def test_a_failed_firmware_stop_keeps_the_state(
        self, mock_device_factory, runner
    ) -> None:
        light = prime(mock_device_factory(MatrixLight), runner)
        original = prior(0.7)
        light._mood_prestate = original
        light._stop_firmware_effect = AsyncMock(side_effect=LifxTimeoutError("no"))
        with pytest.raises(LifxTimeoutError):
            await light.stop_effect()
        assert runner.log == [("leave", False)]
        assert light._mood_prestate is original


class TestGroupAnimate:
    async def test_bulbs_share_one_loop_at_the_brightest_bulb(self, runner) -> None:
        a = prime(Light(serial="d073d5000a01", ip="127.0.0.1"), runner)
        b = prime(Light(serial="d073d5000a02", ip="127.0.0.1"), runner)
        prestates = {a.serial: prior(0.2), b.serial: prior(0.5)}

        async def take(light: Light) -> PreState:
            return prestates[light.serial]

        runner.take_prestate = take  # type: ignore[method-assign]
        await DeviceGroup([a, b]).animate_mood(MORPH_THEME)
        (_, lights, effect, given) = next(e for e in runner.log if e[0] == "together")
        assert lights == [a, b]
        assert given == [prestates[a.serial], prestates[b.serial]]
        assert max(c.brightness for c in effect.palette) == pytest.approx(0.5)

    async def test_an_off_light_powers_on_beside_lights_that_are_on(
        self, runner
    ) -> None:
        on = prime(MatrixLight(serial="d073d5000a03", ip="127.0.0.1"), runner)
        off = prime(
            MatrixLight(serial="d073d5000a04", ip="127.0.0.1"), runner, on=False
        )
        await DeviceGroup([on, off]).animate_mood(MORPH_THEME)
        on.set_power.assert_not_awaited()
        off.set_power.assert_awaited_once_with(True, duration=MOOD_FADE_SECONDS)

    async def test_starts_other_lights_alone(self, runner) -> None:
        strip = MultiZoneLight(serial="d073d5000a05", ip="127.0.0.1")
        strip._paints_moods = AsyncMock(return_value=True)  # type: ignore[method-assign]
        strip.animate_mood = AsyncMock()  # type: ignore[method-assign]
        white = Light(serial="d073d5000a06", ip="127.0.0.1")
        white._paints_moods = AsyncMock(return_value=False)  # type: ignore[method-assign]
        await DeviceGroup([strip, white]).animate_mood(MORPH_THEME)
        strip.animate_mood.assert_awaited_once_with(MORPH_THEME)
        assert next(e for e in runner.log if e[0] == "together")[1] == []


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


class TestSoftwareMoodEffectFirst:
    """A running mood software effect answers before any GetEffect is sent."""

    @pytest.mark.parametrize(
        ("cls", "product"), [(MultiZoneLight, 32), (MatrixLight, 55)]
    )
    async def test_skips_get_effect(self, mock_device_factory, cls, product) -> None:
        light = mock_device_factory(cls, product=product)
        light.get_effect = AsyncMock()
        runner = MagicMock()
        runner.runs_mood_effect.return_value = True
        with patch("lifx.devices.light.effect_runner", return_value=runner):
            assert await light._mood_effect_running()
        runner.runs_mood_effect.assert_called_once_with(light)
        light.get_effect.assert_not_awaited()


def test_the_registered_runner_is_back() -> None:
    """The fake runner fixture leaves the real runner registered."""
    assert not isinstance(effect_runner(), FakeRunner)
