"""Pendulum wave and double slit on a Mirror, with the ``seamless`` option.

Both effects already run on any colour light, so the Mirror work here is the
registry level and the ``seamless`` keyword: on a wrapping canvas each pixel
is drawn at its ring distance from zone 0, so the pattern meets itself with
no jump. The tests sit at the three seams: the registry, a Conductor start
on the emulated Mirror, and the frames the effect draws.
"""

from __future__ import annotations

import logging

import pytest

from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects import EffectDoubleSlit, EffectPendulumWave
from lifx.effects.conductor import Conductor
from lifx.effects.registry import DeviceSupport, DeviceType, get_effect_registry
from tests.test_effects.test_ring_helpers import RING, strip_digest, tuple_frames

EFFECTS = [
    pytest.param(EffectPendulumWave, "pendulum_wave", id="pendulum_wave"),
    pytest.param(EffectDoubleSlit, "double_slit", id="double_slit"),
]

# Digest of 120 strip frames of each effect, pinned before ``seamless`` existed.
_STRIP_DIGEST = {
    "pendulum_wave": "6bb23025fddbc4ed57130580edc653e0cbc48293ba2e38813056243a7b9b2bec",
    "double_slit": "53dbd2359b77815009ded5eea7606d89f925d9e8da87174a2f811c54f9a16ad1",
}


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
        assert tuple_frames(cls(), wraps=True) == tuple_frames(
            cls(seamless=False), wraps=True
        )

    def test_a_ring_frame_equals_a_strip_frame_when_not_seamless(
        self, cls, name
    ) -> None:
        assert tuple_frames(cls(), wraps=True) == tuple_frames(cls(), wraps=False)

    @pytest.mark.parametrize("pixels", [RING, 24])
    def test_a_seamless_ring_mirrors_about_zone_zero(self, cls, name, pixels) -> None:
        for frame in tuple_frames(cls(seamless=True), wraps=True, pixels=pixels):
            for i in range(1, pixels):
                assert frame[i] == frame[pixels - i]

    def test_a_seamless_ring_is_not_the_strip_pattern(self, cls, name) -> None:
        seamless = tuple_frames(cls(seamless=True), wraps=True)
        assert seamless != tuple_frames(cls(), wraps=True)

    def test_a_seamless_ring_draws_each_pixel_at_its_ring_distance(
        self, cls, name
    ) -> None:
        # Pixel i takes the colour the strip draws at min(i, n - i).
        strip = tuple_frames(cls(), wraps=False)
        ring = tuple_frames(cls(seamless=True), wraps=True)
        for strip_frame, ring_frame in zip(strip, ring, strict=True):
            for i in range(RING):
                assert ring_frame[i] == strip_frame[min(i, RING - i)]

    def test_seamless_is_ignored_on_a_canvas_that_does_not_wrap(
        self, cls, name, caplog
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            seamless = tuple_frames(cls(seamless=True), wraps=False)
        assert seamless == tuple_frames(cls(), wraps=False)
        assert caplog.records == []

    def test_a_strip_frame_is_unchanged(self, cls, name) -> None:
        assert strip_digest(cls(), 120) == _STRIP_DIGEST[name]

    def test_repr_names_the_option(self, cls, name) -> None:
        assert "seamless=True" in repr(cls(seamless=True))
