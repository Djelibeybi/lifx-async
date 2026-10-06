"""Ripple on a Mirror: registry level, Conductor admission and ring frames.

Ripple is the first effect ported to the Mirror, so these tests set the
pattern the other ports follow, at the three seams: the registry, a
Conductor start on the emulated Mirror, and the frames the effect draws.
"""

from __future__ import annotations

import random

import pytest

from lifx.devices.light import Light
from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects import EffectRipple
from lifx.effects.conductor import Conductor
from lifx.effects.registry import DeviceSupport, DeviceType, get_effect_registry
from tests.test_effects.test_ring_helpers import (
    RING,
    brightness,
    draw_frames,
    ring_ctx,
    strip_digest,
)

# Perceptual brightness of a pixel the surface has left untouched.
_FLOOR = 0.8 * 0.02


class TestRegistry:
    def test_ripple_is_listed_for_a_mirror_at_its_multizone_level(self) -> None:
        info = get_effect_registry().get_effect("ripple")
        assert info is not None
        assert info.device_support[DeviceType.MIRROR] is DeviceSupport.RECOMMENDED
        assert (
            info.device_support[DeviceType.MIRROR]
            is info.device_support[DeviceType.MULTIZONE]
        )
        listed = get_effect_registry().get_effects_for_device_type(DeviceType.MIRROR)
        assert "ripple" in {i.name for i, _ in listed}


class TestCompatibility:
    async def test_a_mirror_is_compatible_without_multizone_capability(self) -> None:
        mirror = MirrorLight(serial="d073d5000300", ip="192.0.2.30")
        assert await EffectRipple().is_light_compatible(mirror) is True

    async def test_a_bulb_is_still_refused_on_the_emulator(self, emulator_devices):
        bulb = emulator_devices[0]
        assert isinstance(bulb, Light)
        async with bulb:
            assert await EffectRipple().is_light_compatible(bulb) is False


@pytest.mark.emulator
class TestConductor:
    async def test_it_admits_a_whole_mirror(self, mirror_device):
        mirror = mirror_device
        async with mirror:
            effect = EffectRipple()
            conductor = Conductor()
            await conductor.start(effect, [mirror])
            try:
                assert conductor.effect(mirror) is effect
            finally:
                await conductor.stop([mirror])

    @pytest.mark.parametrize("ring", ["front", "back"])
    async def test_it_admits_each_ring_alone(self, mirror_device, ring):
        mirror = mirror_device
        async with mirror:
            participant = getattr(mirror, ring)
            other = mirror.back if ring == "front" else mirror.front
            effect = EffectRipple()
            conductor = Conductor()
            await conductor.start(effect, [participant])
            try:
                assert conductor.effect(participant) is effect
                assert conductor.effect(other) is None
            finally:
                await conductor.stop([participant])

    async def test_a_mixed_run_admits_a_ring_and_a_strip_but_not_a_bulb(
        self, mirror_device, emulator_devices
    ):
        mirror = mirror_device
        bulb = emulator_devices[0]
        strip = emulator_devices[4]
        assert isinstance(strip, MultiZoneLight)
        async with mirror:
            effect = EffectRipple()
            conductor = Conductor()
            await conductor.start(effect, [mirror.front, strip, bulb])
            try:
                assert conductor.effect(mirror.front) is effect
                assert conductor.effect(strip) is effect
                assert conductor.effect(bulb) is None
            finally:
                await conductor.stop([mirror.front, strip])


class TestFrames:
    def test_a_ring_ripple_lights_both_sides_of_the_closing_zone(self) -> None:
        random.seed(11)
        frames = brightness(draw_frames(EffectRipple(drop_rate=2.0), 600, wraps=True))
        peak = 0.8
        # Waves cross zone 24 to 0 as freely as any other pair of zones.
        assert max(f[0] for f in frames) > peak / 2
        assert max(f[RING - 1] for f in frames) > peak / 2

    def test_a_strip_ripple_keeps_its_ends_still(self) -> None:
        random.seed(11)
        frames = brightness(draw_frames(EffectRipple(drop_rate=2.0), 600, wraps=False))
        assert max(f[0] for f in frames) == pytest.approx(_FLOOR)
        assert max(f[RING - 1] for f in frames) == pytest.approx(_FLOOR)

    def test_a_strip_frame_is_unchanged(self) -> None:
        random.seed(7)
        effect = EffectRipple(drop_rate=2.0)
        # Pinned from the strip rendering before the Mirror port.
        assert strip_digest(effect, 120) == _STRIP_DIGEST

    def test_a_ring_and_a_strip_do_not_share_one_surface(self) -> None:
        random.seed(5)
        effect = EffectRipple(drop_rate=2.0)
        for f in range(200):
            effect.generate_frame(ring_ctx(f / 20, wraps=True))
        # Moving to a strip canvas restarts the surface: the ends are fixed.
        for f in range(200):
            strip = effect.generate_frame(ring_ctx(10 + f / 20, wraps=False))
            assert strip[0].brightness == pytest.approx(_FLOOR)
            assert strip[RING - 1].brightness == pytest.approx(_FLOOR)


_STRIP_DIGEST = "20c7c6c9712c0bc946e225d842c95a128db34141b624edce7a344d74dbc02409"
