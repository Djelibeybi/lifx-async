"""Pendulum wave and double slit on a Mirror, with the ``seamless`` option.

Both effects already run on any colour light, so the Mirror work here is the
registry level and the ``seamless`` keyword: on a wrapping canvas each pixel
is drawn at its ring distance from zone 0, so the pattern meets itself with
no jump. The tests sit at the three seams: the registry, a Conductor start
on the emulated Mirror, and the frames the effect draws.
"""

from __future__ import annotations

import hashlib
import logging

import pytest

from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects import EffectDoubleSlit, EffectPendulumWave
from lifx.effects.conductor import Conductor
from lifx.effects.frame_effect import FrameContext
from lifx.effects.registry import DeviceSupport, DeviceType, get_effect_registry

_RING = 25

EFFECTS = [
    pytest.param(EffectPendulumWave, "pendulum_wave", id="pendulum_wave"),
    pytest.param(EffectDoubleSlit, "double_slit", id="double_slit"),
]

# Digest of 120 strip frames of each effect, pinned before ``seamless`` existed.
_STRIP_DIGEST = {
    "pendulum_wave": "4c28f8764c892b5bdb17033d50655c961218bbd2d88c49b5521f4dff43b3a9e0",
    "double_slit": "a293db59c3955261e761a4d54b93bee5252abb0ef0fb447845db1bb771f32968",
}


def _ctx(elapsed_s: float, wraps: bool, pixels: int = _RING) -> FrameContext:
    return FrameContext(
        elapsed_s=elapsed_s,
        device_index=0,
        pixel_count=pixels,
        canvas_width=pixels,
        canvas_height=1,
        wraps=wraps,
    )


def _frames(effect, wraps: bool, count: int = 60, pixels: int = _RING):
    return [
        [
            (c.hue, c.saturation, c.brightness, c.kelvin)
            for c in effect.generate_frame(_ctx(f / 20, wraps, pixels))
        ]
        for f in range(count)
    ]


@pytest.mark.parametrize(("cls", "name"), EFFECTS)
class TestRegistry:
    def test_the_mirror_level_equals_the_multizone_level(self, cls, name) -> None:
        info = get_effect_registry().get_effect(name)
        assert info is not None
        assert info.device_support[DeviceType.MIRROR] is DeviceSupport.RECOMMENDED
        assert (
            info.device_support[DeviceType.MIRROR]
            is info.device_support[DeviceType.MULTIZONE]
        )
        listed = get_effect_registry().get_effects_for_device_type(DeviceType.MIRROR)
        assert name in {i.name for i, _ in listed}


@pytest.mark.emulator
@pytest.mark.parametrize(("cls", "name"), EFFECTS)
class TestConductor:
    async def test_it_admits_a_whole_mirror(self, mirror_device, cls, name):
        mirror = mirror_device
        async with mirror:
            effect = cls()
            conductor = Conductor()
            await conductor.start(effect, [mirror])
            try:
                assert conductor.effect(mirror) is effect
            finally:
                await conductor.stop([mirror])

    @pytest.mark.parametrize("ring", ["front", "back"])
    async def test_it_admits_each_ring_alone(self, mirror_device, cls, name, ring):
        mirror = mirror_device
        async with mirror:
            participant = getattr(mirror, ring)
            other = mirror.back if ring == "front" else mirror.front
            effect = cls()
            conductor = Conductor()
            await conductor.start(effect, [participant])
            try:
                assert conductor.effect(participant) is effect
                assert conductor.effect(other) is None
            finally:
                await conductor.stop([participant])

    async def test_a_seamless_run_admits_a_ring_and_a_strip(
        self, mirror_device, emulator_devices, cls, name
    ):
        mirror = mirror_device
        strip = emulator_devices[4]
        assert isinstance(strip, MultiZoneLight)
        assert isinstance(mirror, MirrorLight)
        async with mirror:
            effect = cls(seamless=True)
            conductor = Conductor()
            await conductor.start(effect, [mirror.front, strip])
            try:
                assert conductor.effect(mirror.front) is effect
                assert conductor.effect(strip) is effect
            finally:
                await conductor.stop([mirror.front, strip])


@pytest.mark.parametrize(("cls", "name"), EFFECTS)
class TestFrames:
    def test_it_is_not_seamless_by_default(self, cls, name) -> None:
        assert _frames(cls(), wraps=True) == _frames(cls(seamless=False), wraps=True)

    def test_a_ring_frame_equals_a_strip_frame_when_not_seamless(
        self, cls, name
    ) -> None:
        assert _frames(cls(), wraps=True) == _frames(cls(), wraps=False)

    @pytest.mark.parametrize("pixels", [_RING, 24])
    def test_a_seamless_ring_mirrors_about_zone_zero(self, cls, name, pixels) -> None:
        for frame in _frames(cls(seamless=True), wraps=True, pixels=pixels):
            for i in range(1, pixels):
                assert frame[i] == frame[pixels - i]

    def test_a_seamless_ring_is_not_the_strip_pattern(self, cls, name) -> None:
        seamless = _frames(cls(seamless=True), wraps=True)
        assert seamless != _frames(cls(), wraps=True)

    def test_a_seamless_ring_draws_each_pixel_at_its_ring_distance(
        self, cls, name
    ) -> None:
        # Pixel i takes the colour the strip draws at min(i, n - i).
        strip = _frames(cls(), wraps=False)
        ring = _frames(cls(seamless=True), wraps=True)
        for strip_frame, ring_frame in zip(strip, ring, strict=True):
            for i in range(_RING):
                assert ring_frame[i] == strip_frame[min(i, _RING - i)]

    def test_seamless_is_ignored_on_a_canvas_that_does_not_wrap(
        self, cls, name, caplog
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            seamless = _frames(cls(seamless=True), wraps=False)
        assert seamless == _frames(cls(), wraps=False)
        assert caplog.records == []

    def test_a_strip_frame_is_unchanged(self, cls, name) -> None:
        digest = hashlib.sha256()
        effect = cls()
        for f in range(120):
            frame = effect.generate_frame(_ctx(f / 20, wraps=False))
            digest.update(
                repr(
                    [(c.hue, c.saturation, c.brightness, c.kelvin) for c in frame]
                ).encode()
            )
        assert digest.hexdigest() == _STRIP_DIGEST[name]

    def test_repr_names_the_option(self, cls, name) -> None:
        assert "seamless=True" in repr(cls(seamless=True))
