"""The effect registry on a Mirror: device type, rings and support levels."""

from __future__ import annotations

import pytest

from lifx.devices.ceiling import CeilingLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects import EffectSunrise, EffectSunset
from lifx.effects.conductor import Conductor
from lifx.effects.plasma2d import EffectPlasma2D
from lifx.effects.registry import (
    DeviceSupport,
    DeviceType,
    get_effect_registry,
)

# Effects that already run on a Mirror ring, and the level they start from.
RING_EFFECTS = (
    "wave",
    "sine",
    "spin",
    "cylon",
    "spectrum_sweep",
    "twinkle",
    "aurora",
    "flicker",
    "rainbow",
    "colorloop",
    "ripple",
)

# Effects still to be ported: the registry must not advertise them.
TO_BE_PORTED = (
    "sonar",
    "rule30",
    "rule_trio",
    "fireworks",
    "progress",
    "jacobs_ladder",
    "newtons_cradle",
    "pendulum_wave",
    "double_slit",
    "plasma",
    "embers",
)

TWO_D = ("sunrise", "sunset", "plasma2d")


def _names(pairs) -> set[str]:
    return {info.name for info, _ in pairs}


@pytest.fixture
def mirror() -> MirrorLight:
    return MirrorLight(serial="d073d5000300", ip="192.0.2.30")


class TestMirrorDeviceType:
    def test_device_type_has_a_mirror_member(self) -> None:
        assert DeviceType.MIRROR.value == "mirror"

    def test_a_mirror_is_a_mirror_not_a_matrix(self, mirror: MirrorLight) -> None:
        registry = get_effect_registry()
        assert registry.get_effects_for_device(
            mirror
        ) == registry.get_effects_for_device_type(DeviceType.MIRROR)
        assert registry.get_effects_for_device(
            mirror
        ) != registry.get_effects_for_device_type(DeviceType.MATRIX)

    @pytest.mark.parametrize("ring", ["front", "back"])
    def test_a_ring_is_a_mirror_without_effects_that_draw_no_frames(
        self, mirror: MirrorLight, ring: str
    ) -> None:
        registry = get_effect_registry()
        listed = registry.get_effects_for_device(getattr(mirror, ring))

        assert "pulse" not in _names(listed)
        whole = registry.get_effects_for_device(mirror)
        assert "pulse" in _names(whole)
        assert _names(listed) == _names(whole) - {"pulse"}

    def test_the_two_rings_list_the_same_effects(self, mirror: MirrorLight) -> None:
        registry = get_effect_registry()
        assert registry.get_effects_for_device(
            mirror.front
        ) == registry.get_effects_for_device(mirror.back)

    def test_a_ceiling_component_is_not_classified(self) -> None:
        ceiling = CeilingLight(serial="d073d5000301", ip="192.0.2.31")
        with pytest.raises(TypeError, match="Mirror"):
            get_effect_registry().get_effects_for_device(ceiling.downlight)


class TestMirrorSupportLevels:
    def test_every_effect_has_an_explicit_mirror_level(self) -> None:
        for info in get_effect_registry().effects:
            assert DeviceType.MIRROR in info.device_support, info.name

    @pytest.mark.parametrize("name", RING_EFFECTS)
    def test_ring_effects_start_from_their_multizone_level(self, name: str) -> None:
        info = get_effect_registry().get_effect(name)
        assert info is not None
        mirror_level = info.device_support[DeviceType.MIRROR]
        assert mirror_level is info.device_support[DeviceType.MULTIZONE]
        assert mirror_level is not DeviceSupport.NOT_SUPPORTED

    def test_pulse_stays_supported_for_the_whole_mirror(
        self, mirror: MirrorLight
    ) -> None:
        listed = {
            info.name: support
            for info, support in get_effect_registry().get_effects_for_device(mirror)
        }
        assert listed["pulse"] is not DeviceSupport.NOT_SUPPORTED

    @pytest.mark.parametrize("name", TWO_D + TO_BE_PORTED)
    def test_effects_that_do_not_run_on_a_mirror_are_not_listed(
        self, name: str
    ) -> None:
        info = get_effect_registry().get_effect(name)
        assert info is not None
        assert info.device_support[DeviceType.MIRROR] is DeviceSupport.NOT_SUPPORTED
        assert name not in _names(
            get_effect_registry().get_effects_for_device_type(DeviceType.MIRROR)
        )

    def test_the_mirror_list_is_exactly_the_ring_effects_and_pulse(
        self, mirror: MirrorLight
    ) -> None:
        listed = _names(get_effect_registry().get_effects_for_device(mirror))
        assert listed == {*RING_EFFECTS, "pulse"}


class TestOtherDeviceTypesUnchanged:
    def test_a_ceiling_is_still_a_matrix(self) -> None:
        registry = get_effect_registry()
        ceiling = CeilingLight(serial="d073d5000301", ip="192.0.2.31")
        assert registry.get_effects_for_device(
            ceiling
        ) == registry.get_effects_for_device_type(DeviceType.MATRIX)

    def test_a_tile_is_still_a_matrix(self) -> None:
        registry = get_effect_registry()
        tile = MatrixLight(serial="d073d5000302", ip="192.0.2.32")
        listed = registry.get_effects_for_device(tile)
        assert listed == registry.get_effects_for_device_type(DeviceType.MATRIX)
        assert {"sunrise", "sunset", "plasma2d"} <= _names(listed)

    def test_a_strip_and_a_bulb_are_unchanged(self) -> None:
        registry = get_effect_registry()
        strip = MultiZoneLight(serial="d073d5000303", ip="192.0.2.33")
        bulb = Light(serial="d073d5000304", ip="192.0.2.34")
        assert registry.get_effects_for_device(
            strip
        ) == registry.get_effects_for_device_type(DeviceType.MULTIZONE)
        assert registry.get_effects_for_device(
            bulb
        ) == registry.get_effects_for_device_type(DeviceType.LIGHT)
        assert "sunrise" not in _names(registry.get_effects_for_device(strip))


@pytest.mark.emulator
class TestConductorRefusesTwoDimensionalEffectsOnAMirror:
    @pytest.mark.parametrize(
        "make_effect", [EffectSunrise, EffectSunset, EffectPlasma2D]
    )
    async def test_a_mirror_and_its_rings_are_refused(
        self, mirror_device, make_effect
    ) -> None:
        mirror = mirror_device
        async with mirror:
            conductor = Conductor()
            for participant in (mirror, mirror.front, mirror.back):
                await conductor.start(make_effect(), [participant])
                assert conductor.effect(participant) is None
