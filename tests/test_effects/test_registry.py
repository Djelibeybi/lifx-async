"""Tests for EffectRegistry."""

from unittest.mock import MagicMock

from lifx.devices.light import Light
from lifx.effects.colorloop import EffectColorloop
from lifx.effects.pulse import EffectPulse
from lifx.effects.rainbow import EffectRainbow
from lifx.effects.registry import (
    DeviceSupport,
    DeviceType,
    EffectInfo,
    EffectRegistry,
    _classify_device,
    get_effect_registry,
)


class TestEffectRegistry:
    """Tests for the EffectRegistry class."""

    def test_register_and_retrieve(self) -> None:
        """Test registering an effect and retrieving it by name."""
        registry = EffectRegistry()
        info = EffectInfo(
            name="test",
            effect_class=EffectPulse,
            description="Test effect",
            device_support={DeviceType.LIGHT: DeviceSupport.RECOMMENDED},
        )
        registry.register(info)

        result = registry.get_effect("test")
        assert result is info

    def test_effects_property_lists_all(self) -> None:
        """Test .effects returns all registered effects."""
        registry = EffectRegistry()
        info1 = EffectInfo(
            name="a",
            effect_class=EffectPulse,
            description="A",
            device_support={DeviceType.LIGHT: DeviceSupport.RECOMMENDED},
        )
        info2 = EffectInfo(
            name="b",
            effect_class=EffectRainbow,
            description="B",
            device_support={DeviceType.LIGHT: DeviceSupport.COMPATIBLE},
        )
        registry.register(info1)
        registry.register(info2)

        effects = registry.effects
        assert len(effects) == 2
        assert info1 in effects
        assert info2 in effects

    def test_get_effect_unknown_returns_none(self) -> None:
        """Test looking up an unknown effect returns None."""
        registry = EffectRegistry()
        assert registry.get_effect("nonexistent") is None

    def test_get_effects_for_device_type_light(self) -> None:
        """Test filtering effects for LIGHT device type."""
        registry = EffectRegistry()
        registry.register(
            EffectInfo(
                name="light_only",
                effect_class=EffectPulse,
                description="Light only",
                device_support={
                    DeviceType.LIGHT: DeviceSupport.RECOMMENDED,
                    DeviceType.MULTIZONE: DeviceSupport.NOT_SUPPORTED,
                },
            )
        )
        registry.register(
            EffectInfo(
                name="multizone_only",
                effect_class=EffectRainbow,
                description="Multizone only",
                device_support={
                    DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                    DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                },
            )
        )

        results = registry.get_effects_for_device_type(DeviceType.LIGHT)
        names = [info.name for info, _ in results]
        assert "light_only" in names
        assert "multizone_only" not in names

    def test_get_effects_for_device_type_multizone(self) -> None:
        """Test filtering effects for MULTIZONE device type."""
        registry = EffectRegistry()
        registry.register(
            EffectInfo(
                name="mz_effect",
                effect_class=EffectRainbow,
                description="MZ",
                device_support={
                    DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                },
            )
        )

        results = registry.get_effects_for_device_type(DeviceType.MULTIZONE)
        assert len(results) == 1
        assert results[0][0].name == "mz_effect"

    def test_get_effects_for_device_type_matrix(self) -> None:
        """Test filtering effects for MATRIX device type."""
        registry = EffectRegistry()
        registry.register(
            EffectInfo(
                name="matrix_effect",
                effect_class=EffectRainbow,
                description="Matrix",
                device_support={
                    DeviceType.MATRIX: DeviceSupport.RECOMMENDED,
                },
            )
        )

        results = registry.get_effects_for_device_type(DeviceType.MATRIX)
        assert len(results) == 1
        assert results[0][0].name == "matrix_effect"

    def test_results_sorted_recommended_first(self) -> None:
        """Test that RECOMMENDED effects come before COMPATIBLE."""
        registry = EffectRegistry()
        registry.register(
            EffectInfo(
                name="compatible_one",
                effect_class=EffectPulse,
                description="Compatible",
                device_support={DeviceType.LIGHT: DeviceSupport.COMPATIBLE},
            )
        )
        registry.register(
            EffectInfo(
                name="recommended_one",
                effect_class=EffectRainbow,
                description="Recommended",
                device_support={DeviceType.LIGHT: DeviceSupport.RECOMMENDED},
            )
        )

        results = registry.get_effects_for_device_type(DeviceType.LIGHT)
        assert len(results) == 2
        assert results[0][1] is DeviceSupport.RECOMMENDED
        assert results[1][1] is DeviceSupport.COMPATIBLE

    def test_not_supported_excluded(self) -> None:
        """Test that NOT_SUPPORTED entries are excluded from results."""
        registry = EffectRegistry()
        registry.register(
            EffectInfo(
                name="unsupported",
                effect_class=EffectPulse,
                description="Unsupported",
                device_support={DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED},
            )
        )

        results = registry.get_effects_for_device_type(DeviceType.LIGHT)
        assert len(results) == 0


class TestDefaultRegistry:
    """Tests for the default registry returned by get_effect_registry()."""

    def test_default_registry_has_all_builtin_effects(self) -> None:
        """Test that default registry has all 8 built-in effects."""
        registry = get_effect_registry()
        names = {info.name for info in registry.effects}
        expected = {
            "pulse",
            "colorloop",
            "rainbow",
            "flame",
            "aurora",
            "progress",
            "sunrise",
            "sunset",
        }
        assert names == expected

    def test_builtin_effect_names(self) -> None:
        """Test all expected effect names are present."""
        registry = get_effect_registry()
        names = [info.name for info in registry.effects]
        for name in [
            "pulse",
            "colorloop",
            "rainbow",
            "flame",
            "aurora",
            "progress",
            "sunrise",
            "sunset",
        ]:
            assert name in names

    def test_builtin_effect_classes(self) -> None:
        """Test that built-in effects reference the correct classes."""
        from lifx.effects.aurora import EffectAurora
        from lifx.effects.flame import EffectFlame
        from lifx.effects.progress import EffectProgress
        from lifx.effects.sunrise import EffectSunrise, EffectSunset

        registry = get_effect_registry()
        assert registry.get_effect("pulse").effect_class is EffectPulse
        assert registry.get_effect("colorloop").effect_class is EffectColorloop
        assert registry.get_effect("rainbow").effect_class is EffectRainbow
        assert registry.get_effect("flame").effect_class is EffectFlame
        assert registry.get_effect("aurora").effect_class is EffectAurora
        assert registry.get_effect("progress").effect_class is EffectProgress
        assert registry.get_effect("sunrise").effect_class is EffectSunrise
        assert registry.get_effect("sunset").effect_class is EffectSunset

    def test_colorloop_recommended_on_light(self) -> None:
        """Test colorloop is RECOMMENDED for Light devices."""
        registry = get_effect_registry()
        info = registry.get_effect("colorloop")
        assert info.device_support[DeviceType.LIGHT] is DeviceSupport.RECOMMENDED

    def test_rainbow_recommended_on_multizone(self) -> None:
        """Test rainbow is RECOMMENDED for MultiZone devices."""
        registry = get_effect_registry()
        info = registry.get_effect("rainbow")
        assert info.device_support[DeviceType.MULTIZONE] is DeviceSupport.RECOMMENDED

    def test_rainbow_compatible_on_light(self) -> None:
        """Test rainbow is COMPATIBLE for Light devices."""
        registry = get_effect_registry()
        info = registry.get_effect("rainbow")
        assert info.device_support[DeviceType.LIGHT] is DeviceSupport.COMPATIBLE

    def test_aurora_compatible_on_light(self) -> None:
        """Test aurora is COMPATIBLE for Light devices."""
        registry = get_effect_registry()
        info = registry.get_effect("aurora")
        assert info.device_support[DeviceType.LIGHT] is DeviceSupport.COMPATIBLE

    def test_aurora_recommended_on_multizone(self) -> None:
        """Test aurora is RECOMMENDED for MultiZone devices."""
        registry = get_effect_registry()
        info = registry.get_effect("aurora")
        assert info.device_support[DeviceType.MULTIZONE] is DeviceSupport.RECOMMENDED

    def test_flame_recommended_on_all(self) -> None:
        """Test flame is RECOMMENDED for all device types."""
        registry = get_effect_registry()
        info = registry.get_effect("flame")
        assert info.device_support[DeviceType.LIGHT] is DeviceSupport.RECOMMENDED
        assert info.device_support[DeviceType.MULTIZONE] is DeviceSupport.RECOMMENDED
        assert info.device_support[DeviceType.MATRIX] is DeviceSupport.RECOMMENDED

    def test_progress_multizone_only(self) -> None:
        """Test progress is only RECOMMENDED on multizone."""
        registry = get_effect_registry()
        info = registry.get_effect("progress")
        assert info.device_support[DeviceType.MULTIZONE] is DeviceSupport.RECOMMENDED
        assert info.device_support[DeviceType.LIGHT] is DeviceSupport.NOT_SUPPORTED
        assert info.device_support[DeviceType.MATRIX] is DeviceSupport.NOT_SUPPORTED

    def test_sunrise_matrix_only(self) -> None:
        """Test sunrise is only RECOMMENDED on matrix."""
        registry = get_effect_registry()
        info = registry.get_effect("sunrise")
        assert info.device_support[DeviceType.MATRIX] is DeviceSupport.RECOMMENDED
        assert info.device_support[DeviceType.LIGHT] is DeviceSupport.NOT_SUPPORTED
        assert info.device_support[DeviceType.MULTIZONE] is DeviceSupport.NOT_SUPPORTED


class TestDeviceClassification:
    """Tests for _classify_device helper."""

    def test_classify_light(self) -> None:
        """Test that a basic Light is classified as LIGHT."""
        light = MagicMock(spec=Light)
        assert _classify_device(light) is DeviceType.LIGHT

    def test_classify_multizone(self) -> None:
        """Test that a MultiZoneLight is classified as MULTIZONE."""
        from lifx.devices.multizone import MultiZoneLight

        light = MagicMock(spec=MultiZoneLight)
        assert _classify_device(light) is DeviceType.MULTIZONE

    def test_classify_matrix(self) -> None:
        """Test that a MatrixLight is classified as MATRIX."""
        from lifx.devices.matrix import MatrixLight

        light = MagicMock(spec=MatrixLight)
        assert _classify_device(light) is DeviceType.MATRIX

    def test_classify_infrared_as_light(self) -> None:
        """Test that an InfraredLight is classified as LIGHT."""
        from lifx.devices.infrared import InfraredLight

        light = MagicMock(spec=InfraredLight)
        assert _classify_device(light) is DeviceType.LIGHT

    def test_get_effects_for_device_integration(self) -> None:
        """Test get_effects_for_device with a mock device."""
        from lifx.devices.multizone import MultiZoneLight

        registry = get_effect_registry()
        device = MagicMock(spec=MultiZoneLight)
        results = registry.get_effects_for_device(device)

        names = [info.name for info, _ in results]
        assert "rainbow" in names
        assert "pulse" in names
