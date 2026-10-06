"""Fireworks, rule30, rule trio, plasma and embers on a Mirror.

Follows the pattern set by ``test_ripple_mirror.py``, at three seams: the
registry, a Conductor start on the emulated Mirror, and the frames each
effect draws on a wrapping 25-pixel ring and on a strip.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable

import pytest

from lifx.devices.light import Light
from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects import (
    EffectEmbers,
    EffectFireworks,
    EffectPlasma,
    EffectRule30,
    EffectRuleTrio,
)
from lifx.effects.base import LIFXEffect
from lifx.effects.conductor import Conductor
from lifx.effects.frame_effect import FrameContext
from lifx.effects.registry import DeviceSupport, DeviceType, get_effect_registry

_RING = 25

EffectFactory = Callable[[], LIFXEffect]

# Each effect, built so its frames show plenty of activity in a short run.
FACTORIES: dict[str, EffectFactory] = {
    "fireworks": lambda: EffectFireworks(launch_rate=2.0, burst_spread=20.0),
    "rule30": lambda: EffectRule30(seed="random", speed=5.0),
    "rule_trio": lambda: EffectRuleTrio(speed=5.0),
    "plasma": lambda: EffectPlasma(tendril_rate=2.0),
    "embers": lambda: EffectEmbers(),
}

# Plasma and embers are refused by every matrix light except a Mirror.
REFUSE_MATRIX = ("plasma", "embers")


def _ctx(elapsed_s: float, wraps: bool, pixels: int = _RING) -> FrameContext:
    return FrameContext(
        elapsed_s=elapsed_s,
        device_index=0,
        pixel_count=pixels,
        canvas_width=pixels,
        canvas_height=1,
        wraps=wraps,
    )


def _frames(effect, count: int, wraps: bool, step: float = 0.05):
    return [effect.generate_frame(_ctx(f * step, wraps)) for f in range(count)]


def _brightness(frames) -> list[list[float]]:
    return [[c.brightness for c in frame] for frame in frames]


@pytest.mark.parametrize("name", FACTORIES)
class TestRegistry:
    def test_the_mirror_level_equals_the_multizone_level(self, name: str) -> None:
        info = get_effect_registry().get_effect(name)
        assert info is not None
        mirror = info.device_support[DeviceType.MIRROR]
        assert mirror is info.device_support[DeviceType.MULTIZONE]
        assert mirror is not DeviceSupport.NOT_SUPPORTED
        listed = get_effect_registry().get_effects_for_device_type(DeviceType.MIRROR)
        assert name in {i.name for i, _ in listed}


@pytest.mark.parametrize("name", FACTORIES)
class TestCompatibility:
    async def test_a_mirror_is_compatible(self, name: str) -> None:
        mirror = MirrorLight(serial="d073d5000300", ip="192.0.2.30")
        assert await FACTORIES[name]().is_light_compatible(mirror) is True


@pytest.mark.emulator
@pytest.mark.parametrize("name", FACTORIES)
class TestConductor:
    async def test_it_admits_a_whole_mirror(self, mirror_device, name: str):
        mirror = mirror_device
        async with mirror:
            effect = FACTORIES[name]()
            conductor = Conductor()
            await conductor.start(effect, [mirror])
            try:
                assert conductor.effect(mirror) is effect
            finally:
                await conductor.stop([mirror])

    @pytest.mark.parametrize("ring", ["front", "back"])
    async def test_it_admits_each_ring_alone(self, mirror_device, name: str, ring):
        mirror = mirror_device
        async with mirror:
            participant = getattr(mirror, ring)
            other = mirror.back if ring == "front" else mirror.front
            effect = FACTORIES[name]()
            conductor = Conductor()
            await conductor.start(effect, [participant])
            try:
                assert conductor.effect(participant) is effect
                assert conductor.effect(other) is None
            finally:
                await conductor.stop([participant])

    async def test_a_non_mirror_matrix_light_is_still_refused(
        self, emulator_devices, name: str
    ):
        tile = emulator_devices[6]
        async with tile:
            assert await FACTORIES[name]().is_light_compatible(tile) is False

    async def test_a_ceiling_is_still_refused(self, ceiling_device, name: str):
        ceiling = ceiling_device
        async with ceiling:
            assert await FACTORIES[name]().is_light_compatible(ceiling) is False

    async def test_a_mixed_run_admits_a_ring_and_a_strip_but_not_a_bulb(
        self, mirror_device, emulator_devices, name: str
    ):
        mirror = mirror_device
        bulb = emulator_devices[0]
        strip = emulator_devices[4]
        assert isinstance(strip, MultiZoneLight)
        assert isinstance(bulb, Light)
        async with mirror:
            effect = FACTORIES[name]()
            conductor = Conductor()
            await conductor.start(effect, [mirror.front, strip, bulb])
            try:
                assert conductor.effect(mirror.front) is effect
                assert conductor.effect(strip) is effect
                # Plasma and embers suit a single colour light; the rest do not.
                if name in REFUSE_MATRIX:
                    assert conductor.effect(bulb) is effect
                else:
                    assert conductor.effect(bulb) is None
            finally:
                await conductor.stop([mirror.front, strip, bulb])


class TestStripFramesAreUnchanged:
    @pytest.mark.parametrize("name", FACTORIES)
    def test_a_non_wrapping_frame_matches_the_strip_rendering(self, name: str) -> None:
        random.seed(7)
        effect = FACTORIES[name]()
        digest = hashlib.sha256()
        for f in range(240):
            frame = effect.generate_frame(_ctx(f / 20, wraps=False))
            digest.update(
                repr(
                    [(c.hue, c.saturation, c.brightness, c.kelvin) for c in frame]
                ).encode()
            )
        # Pinned from the strip rendering before the Mirror port.
        assert digest.hexdigest() == _STRIP_DIGESTS[name]


class TestAutomataTreatTheRingAsPeriodic:
    """Rule 170 shifts every cell one place left per generation."""

    def test_rule30_carries_the_pattern_across_zones_24_and_0(self) -> None:
        random.seed(2)
        effect = EffectRule30(rule=170, seed="random", speed=1.0)
        first = effect.generate_frame(_ctx(0.0, wraps=True))
        second = effect.generate_frame(_ctx(1.0, wraps=True))
        assert second[_RING - 1].brightness == first[0].brightness
        assert second[:-1] == first[1:]

    def test_rule_trio_carries_the_pattern_across_zones_24_and_0(self) -> None:
        random.seed(2)
        effect = EffectRuleTrio(
            rule_a=170, rule_b=170, rule_c=170, speed=1.0, drift_b=1.0, drift_c=1.0
        )
        first = effect.generate_frame(_ctx(0.0, wraps=True))
        second = effect.generate_frame(_ctx(1.0, wraps=True))
        assert second[_RING - 1] == first[0]
        assert second[:-1] == first[1:]

    def test_rule30_and_rule_trio_frames_are_identical_on_a_ring_and_a_strip(
        self,
    ) -> None:
        for name in ("rule30", "rule_trio"):
            random.seed(9)
            ring = _frames(FACTORIES[name](), 60, wraps=True)
            random.seed(9)
            strip = _frames(FACTORIES[name](), 60, wraps=False)
            assert ring == strip


class TestEmbersCloseOnThemselves:
    def test_heat_injected_at_zone_0_spills_onto_zone_24_as_onto_zone_1(self) -> None:
        random.seed(4)
        effect = EffectEmbers(intensity=1.0, turbulence=0.0)
        ring = effect.generate_frame(_ctx(0.0, wraps=True))
        assert ring[_RING - 1].brightness == pytest.approx(ring[1].brightness)
        assert ring[_RING - 1].brightness > ring[2].brightness

    def test_a_strip_keeps_zone_24_cold(self) -> None:
        random.seed(4)
        effect = EffectEmbers(intensity=1.0, turbulence=0.0)
        strip = effect.generate_frame(_ctx(0.0, wraps=False))
        assert strip[_RING - 1].brightness < strip[1].brightness


_STRIP_DIGESTS = {
    "fireworks": "d1a4c7933930ea223f79b6643151a390797223db15d175099a86e843aec97c5a",
    "rule30": "adcfd3d6d3a426ef66ab9e84b4ff93f7a89ab985cb7fb227ac987b7fce6705a1",
    "rule_trio": "86a7d3805c843a32de6c49e476b07c6b4f2414994f4494a498ff0fbc1cf8db5a",
    "plasma": "7c2681bf163fefb04fb39dada0efc270364d7c9a4bc3fb5b95c26222bb93c1ff",
    "embers": "fa235448e9c81f63ce2f96dde5345edcfad1756a698cb00677220e768a736b78",
}


class TestFireworksSpreadAcrossTheJoin:
    @staticmethod
    def _cuts(wraps: bool) -> int:
        """Frames where one side of zones 24 and 0 is lit and the other dark."""
        cuts = 0
        for seed in (1, 2, 3):
            random.seed(seed)
            effect = FACTORIES["fireworks"]()
            for frame in _brightness(_frames(effect, 600, wraps)):
                if max(frame[0], frame[_RING - 1]) > 0.2 and (
                    min(frame[0], frame[_RING - 1]) == 0.0
                ):
                    cuts += 1
        return cuts

    def test_a_ring_never_cuts_a_burst_or_trail_at_the_join(self) -> None:
        assert self._cuts(wraps=True) == 0

    def test_a_strip_does_stop_at_its_ends(self) -> None:
        assert self._cuts(wraps=False) > 0


class TestPlasmaCarriesAcrossTheJoin:
    @staticmethod
    def _runs(seed: int) -> tuple[list[list[float]], list[list[float]]]:
        results = []
        for wraps in (False, True):
            random.seed(seed)
            effect = EffectPlasma(tendril_rate=5.0)
            results.append(_brightness(_frames(effect, 400, wraps)))
        return results[0], results[1]

    def test_a_tendril_reaching_one_end_lights_the_other_side_of_the_join(
        self,
    ) -> None:
        lit_zone_0 = lit_zone_24 = 0
        for seed in range(1, 6):
            strip, ring = self._runs(seed)
            for flat, closed in zip(strip, ring):
                lit_zone_0 += flat[0] == 0.0 and closed[0] > 0.0
                lit_zone_24 += flat[_RING - 1] == 0.0 and closed[_RING - 1] > 0.0
        assert lit_zone_0 > 0
        assert lit_zone_24 > 0


class TestEmbersRunOnARing:
    @staticmethod
    def _mean_zone_24(wraps: bool) -> float:
        random.seed(6)
        effect = EffectEmbers(intensity=1.0)
        frames = _brightness(_frames(effect, 400, wraps))
        return sum(f[_RING - 1] for f in frames) / len(frames)

    def test_a_ring_keeps_zone_24_as_warm_as_the_zones_beside_zone_0(self) -> None:
        assert self._mean_zone_24(wraps=True) > 2 * self._mean_zone_24(wraps=False)
