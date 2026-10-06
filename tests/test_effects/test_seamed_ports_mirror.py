"""Progress, sonar, Jacob's ladder and Newton's cradle on a Mirror.

These effects keep their seam at zone 0, because their meaning needs a start
and an end. On a wrapping ring they draw exactly what they draw on a strip of
the same length. Tests sit at three seams: the registry, a Conductor start on
the emulated Mirror, and the frames each effect draws.
"""

from __future__ import annotations

import random
from collections.abc import Callable

import pytest

from lifx.devices.light import Light
from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects import (
    EffectJacobsLadder,
    EffectNewtonsCradle,
    EffectProgress,
    EffectSonar,
)
from lifx.effects.conductor import Conductor
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.registry import DeviceSupport, DeviceType, get_effect_registry

_RING = 25

_FACTORIES: dict[str, Callable[[], FrameEffect]] = {
    "progress": lambda: EffectProgress(end_value=100, position=40.0),
    "sonar": lambda: EffectSonar(),
    "jacobs_ladder": lambda: EffectJacobsLadder(),
    "newtons_cradle": lambda: EffectNewtonsCradle(),
}
_NAMES = tuple(_FACTORIES)


def _ctx(elapsed_s: float, wraps: bool) -> FrameContext:
    return FrameContext(
        elapsed_s=elapsed_s,
        device_index=0,
        pixel_count=_RING,
        canvas_width=_RING,
        canvas_height=1,
        wraps=wraps,
    )


def _frames(name: str, wraps: bool, count: int = 120) -> list[list[tuple]]:
    random.seed(23)
    effect = _FACTORIES[name]()
    return [
        [
            (c.hue, c.saturation, c.brightness, c.kelvin)
            for c in effect.generate_frame(_ctx(f / 20, wraps))
        ]
        for f in range(count)
    ]


class TestRegistry:
    @pytest.mark.parametrize("name", _NAMES)
    def test_the_mirror_level_equals_the_multizone_level(self, name: str) -> None:
        info = get_effect_registry().get_effect(name)
        assert info is not None
        assert info.device_support[DeviceType.MIRROR] is DeviceSupport.RECOMMENDED
        assert (
            info.device_support[DeviceType.MIRROR]
            is info.device_support[DeviceType.MULTIZONE]
        )
        listed = get_effect_registry().get_effects_for_device_type(DeviceType.MIRROR)
        assert name in {i.name for i, _ in listed}


class TestCompatibility:
    @pytest.mark.parametrize("name", _NAMES)
    async def test_a_mirror_is_compatible_without_multizone_capability(
        self, name: str
    ) -> None:
        mirror = MirrorLight(serial="d073d5000300", ip="192.0.2.30")
        assert await _FACTORIES[name]().is_light_compatible(mirror) is True

    @pytest.mark.parametrize("name", _NAMES)
    async def test_a_bulb_is_still_refused_on_the_emulator(
        self, name: str, emulator_devices
    ) -> None:
        bulb = emulator_devices[0]
        assert isinstance(bulb, Light)
        async with bulb:
            assert await _FACTORIES[name]().is_light_compatible(bulb) is False


@pytest.mark.emulator
class TestConductor:
    @pytest.mark.parametrize("name", _NAMES)
    async def test_it_admits_a_whole_mirror(self, name: str, mirror_device) -> None:
        mirror = mirror_device
        async with mirror:
            effect = _FACTORIES[name]()
            conductor = Conductor()
            await conductor.start(effect, [mirror])
            try:
                assert conductor.effect(mirror) is effect
            finally:
                await conductor.stop([mirror])

    @pytest.mark.parametrize("ring", ["front", "back"])
    @pytest.mark.parametrize("name", _NAMES)
    async def test_it_admits_each_ring_alone(
        self, name: str, ring: str, mirror_device
    ) -> None:
        mirror = mirror_device
        async with mirror:
            participant = getattr(mirror, ring)
            other = mirror.back if ring == "front" else mirror.front
            effect = _FACTORIES[name]()
            conductor = Conductor()
            await conductor.start(effect, [participant])
            try:
                assert conductor.effect(participant) is effect
                assert conductor.effect(other) is None
            finally:
                await conductor.stop([participant])

    @pytest.mark.parametrize("name", _NAMES)
    async def test_a_mixed_run_admits_a_ring_and_a_strip_but_not_a_bulb(
        self, name: str, mirror_device, emulator_devices
    ) -> None:
        mirror = mirror_device
        bulb = emulator_devices[0]
        strip = emulator_devices[4]
        assert isinstance(strip, MultiZoneLight)
        async with mirror:
            effect = _FACTORIES[name]()
            conductor = Conductor()
            await conductor.start(effect, [mirror.front, strip, bulb])
            try:
                assert conductor.effect(mirror.front) is effect
                assert conductor.effect(strip) is effect
                assert conductor.effect(bulb) is None
            finally:
                await conductor.stop([mirror.front, strip])


class TestFrames:
    @pytest.mark.parametrize("name", _NAMES)
    def test_a_ring_draws_exactly_what_a_strip_draws(self, name: str) -> None:
        assert _frames(name, wraps=True) == _frames(name, wraps=False)

    @pytest.mark.parametrize("name", _NAMES)
    def test_the_ring_frames_are_not_blank(self, name: str) -> None:
        frames = _frames(name, wraps=True)
        assert any(pixel[2] > 0.1 for frame in frames for pixel in frame)

    def test_progress_fills_from_zone_zero_and_leaves_the_end_empty(self) -> None:
        effect = EffectProgress(end_value=100, position=40.0)
        frame = effect.generate_frame(_ctx(0.0, wraps=True))
        assert frame[0].brightness > frame[_RING - 1].brightness
        assert frame[_RING - 1] == effect.background
