"""Streaming animation frames to a light evidenced as Thread needs an opt-in.

A Thread mesh is not built for the steady stream of frames a software effect
or a direct frame sender produces. Every frame-streaming entry point refuses a
light evidenced as Thread, by an observed frame-address report or an mDNS
record, unless the call passes ``enable_thread=True``. The WiFi default a
never-contacted light carries is not evidence, so it is not refused.
"""

from __future__ import annotations

import logging
import warnings
from typing import TypeVar
from unittest.mock import AsyncMock

import pytest

from lifx.animation.animator import Animator
from lifx.devices.ceiling import CeilingLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects import EffectPulse, EffectRainbow
from lifx.effects.conductor import Conductor
from lifx.exceptions import LifxUnsupportedCommandError

WIFI_SERIAL = "d073d5e00101"
THREAD_SERIAL = "d073d5e00102"

L = TypeVar("L", bound=Light)


def _observed(light: L, *, thread: bool) -> L:
    """A light whose replies reported the given transport."""
    light.connection._adopt_thread_connection(thread)
    return light


def _thread_light() -> Light:
    return _observed(Light(THREAD_SERIAL, "192.0.2.2"), thread=True)


def _wifi_light() -> Light:
    return _observed(Light(WIFI_SERIAL, "192.0.2.1"), thread=False)


@pytest.fixture
def filtered(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Stop a start just past the guard: no participant is compatible."""
    check = AsyncMock(return_value=[])
    monkeypatch.setattr(Conductor, "_filter_compatible_lights", check)
    return check


class TestEvidence:
    async def test_an_observed_thread_light_is_refused(self, filtered: AsyncMock):
        with pytest.raises(LifxUnsupportedCommandError, match="enable_thread=True"):
            await _thread_light().start_effect(EffectRainbow())

    async def test_the_refusal_names_the_method_the_caller_used(
        self, filtered: AsyncMock
    ):
        with pytest.raises(LifxUnsupportedCommandError, match=r"^start_effect\(\)"):
            await _thread_light().start_effect(EffectRainbow())
        with pytest.raises(LifxUnsupportedCommandError, match=r"^Conductor\.start\(\)"):
            await Conductor().start(EffectRainbow(), [_thread_light()])
        with pytest.raises(
            LifxUnsupportedCommandError, match=r"^Conductor\.add_lights\(\)"
        ):
            await Conductor().add_lights(EffectRainbow(), [_thread_light()])

        filtered.assert_not_awaited()

    async def test_an_mdns_thread_record_is_evidence(self, filtered: AsyncMock):
        light = Light(THREAD_SERIAL, "192.0.2.2")
        light._set_connectivity("thread")

        with pytest.raises(LifxUnsupportedCommandError, match="enable_thread=True"):
            await light.start_effect(EffectRainbow())

    async def test_an_observed_wifi_report_outranks_an_mdns_thread_record(
        self, filtered: AsyncMock
    ):
        light = Light(WIFI_SERIAL, "192.0.2.1")
        light._set_connectivity("thread")
        _observed(light, thread=False)

        await light.start_effect(EffectRainbow())

        filtered.assert_awaited_once()

    async def test_a_never_contacted_light_is_not_refused(self, filtered: AsyncMock):
        await Light(WIFI_SERIAL, "192.0.2.1").start_effect(EffectRainbow())

        filtered.assert_awaited_once()

    async def test_an_observed_wifi_light_is_not_refused(self, filtered: AsyncMock):
        await _wifi_light().start_effect(EffectRainbow())

        filtered.assert_awaited_once()


class TestOptIn:
    async def test_a_thread_light_streams_with_the_keyword(
        self, filtered: AsyncMock, caplog: pytest.LogCaptureFixture
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with caplog.at_level(logging.WARNING, logger="lifx.effects.conductor"):
                await Conductor().start(
                    EffectRainbow(), [_thread_light()], enable_thread=True
                )

        filtered.assert_awaited_once()
        assert not [r for r in caplog.records if "thread" in r.getMessage().lower()]

    async def test_light_start_effect_passes_the_keyword_on(self, filtered: AsyncMock):
        await _thread_light().start_effect(EffectRainbow(), enable_thread=True)

        filtered.assert_awaited_once()

    async def test_a_light_component_is_refused_without_the_keyword(
        self, filtered: AsyncMock
    ):
        ceiling = CeilingLight(THREAD_SERIAL, "192.0.2.2")
        _observed(ceiling, thread=True)

        with pytest.raises(LifxUnsupportedCommandError, match="enable_thread=True"):
            await ceiling.uplight.start_effect(EffectRainbow())

        await ceiling.uplight.start_effect(EffectRainbow(), enable_thread=True)
        filtered.assert_awaited_once()


class TestConductor:
    async def test_one_thread_light_refuses_the_whole_start(self, filtered: AsyncMock):
        conductor = Conductor()

        with pytest.raises(LifxUnsupportedCommandError, match=THREAD_SERIAL):
            await conductor.start(EffectRainbow(), [_wifi_light(), _thread_light()])

        filtered.assert_not_awaited()
        assert conductor.effect(_wifi_light()) is None

    async def test_add_lights_refuses_a_thread_light(self, filtered: AsyncMock):
        conductor = Conductor()

        with pytest.raises(LifxUnsupportedCommandError, match="enable_thread=True"):
            await conductor.add_lights(EffectRainbow(), [_thread_light()])

        filtered.assert_not_awaited()

        await conductor.add_lights(
            EffectRainbow(), [_thread_light()], enable_thread=True
        )
        filtered.assert_awaited_once()

    async def test_an_effect_that_streams_no_frames_is_not_guarded(
        self, filtered: AsyncMock
    ):
        await Conductor().start(EffectPulse(), [_thread_light()])

        filtered.assert_awaited_once()


class TestAnimator:
    async def test_prepare_refuses_an_observed_thread_light(self):
        with pytest.raises(LifxUnsupportedCommandError, match="enable_thread=True"):
            await _thread_light().animator.prepare()

    async def test_prepare_streams_to_a_thread_light_with_the_keyword(self):
        light = _thread_light()

        assert await light.animator.prepare(enable_thread=True) is light.animator

    async def test_prepare_does_not_refuse_a_never_contacted_light(self):
        light = Light(WIFI_SERIAL, "192.0.2.1")

        assert await light.animator.prepare() is light.animator

    async def test_prepare_refuses_before_querying_the_geometry(self):
        matrix = MatrixLight(THREAD_SERIAL, "192.0.2.2")
        _observed(matrix, thread=True)
        matrix.connection.request = AsyncMock()  # type: ignore[method-assign]

        with pytest.raises(LifxUnsupportedCommandError):
            await matrix.animator.prepare()

        matrix.connection.request.assert_not_awaited()

    async def test_the_deprecated_factories_take_the_keyword(self):
        light = _thread_light()
        matrix = _observed(MatrixLight(THREAD_SERIAL, "192.0.2.2"), thread=True)
        strip = _observed(MultiZoneLight(THREAD_SERIAL, "192.0.2.3"), thread=True)

        with pytest.warns(DeprecationWarning):
            with pytest.raises(LifxUnsupportedCommandError):
                Animator.for_light(light)
        with pytest.warns(DeprecationWarning):
            assert Animator.for_light(light, enable_thread=True) is light.animator
        with pytest.warns(DeprecationWarning):
            with pytest.raises(LifxUnsupportedCommandError):
                await Animator.for_matrix(matrix)
        with pytest.warns(DeprecationWarning):
            with pytest.raises(LifxUnsupportedCommandError):
                await Animator.for_multizone(strip)
