"""Effect registry for discovering and querying available effects.

This module provides a central registry for effect discovery, enabling
consumers like Home Assistant to dynamically find and present available
effects based on device type.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lifx.devices.component.participant import LightComponent
    from lifx.devices.light import Light
    from lifx.effects.base import LIFXEffect


class DeviceType(Enum):
    """Device categories for effect compatibility classification."""

    LIGHT = "light"
    MULTIZONE = "multizone"
    MATRIX = "matrix"
    MIRROR = "mirror"


class DeviceSupport(Enum):
    """How well an effect supports a device type."""

    RECOMMENDED = "recommended"
    COMPATIBLE = "compatible"
    NOT_SUPPORTED = "not_supported"


@dataclass(frozen=True)
class EffectInfo:
    """Metadata about a registered effect.

    Attributes:
        name: Effect name (e.g. "flicker")
        effect_class: The effect class (e.g. EffectFlicker)
        description: Human-readable one-liner
        device_support: Per-device-type support level
    """

    name: str
    effect_class: type[LIFXEffect]
    description: str
    device_support: dict[DeviceType, DeviceSupport]


def _classify_device(device: Light | LightComponent) -> DeviceType:
    """Classify a light, or a light component, into a DeviceType category.

    Uses isinstance checks with lazy imports to avoid circular dependencies.
    A Mirror is checked before a matrix light, so it never classifies as
    ``MATRIX``. A light component classifies the same as its light, so a
    Mirror ring is a Mirror and a Ceiling uplight or downlight is a matrix.

    Args:
        device: The light, or light component, to classify

    Returns:
        DeviceType classification for the device
    """
    from lifx.devices.component.participant import LightComponent
    from lifx.devices.matrix import MatrixLight
    from lifx.devices.mirror import MirrorLight
    from lifx.devices.multizone import MultiZoneLight

    if isinstance(device, LightComponent):
        device = device.light
    if isinstance(device, MirrorLight):
        return DeviceType.MIRROR
    if isinstance(device, MatrixLight):
        return DeviceType.MATRIX
    if isinstance(device, MultiZoneLight):
        return DeviceType.MULTIZONE
    return DeviceType.LIGHT


class EffectRegistry:
    """Central registry for discovering and querying available effects.

    Example:
        ```python
        registry = get_effect_registry()
        for info in registry.effects:
            print(f"{info.name}: {info.description}")

        # Get effects for a specific device
        for info, support in registry.get_effects_for_device(my_light):
            print(f"{info.name}: {support.value}")
        ```
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._effects: dict[str, EffectInfo] = {}
        self._deprecated_names: dict[str, str] = {}

    def register(self, info: EffectInfo) -> None:
        """Register an effect.

        Args:
            info: Effect metadata to register
        """
        self._effects[info.name] = info

    def register_deprecated_name(self, old_name: str, new_name: str) -> None:
        """Register a deprecated alias for a currently registered effect name.

        A deprecated name is resolved by :meth:`get_effect` (with a
        ``DeprecationWarning``) but never appears in :attr:`effects` or the
        results of :meth:`get_effects_for_device` /
        :meth:`get_effects_for_device_type`, so UIs such as Home Assistant
        never list it alongside its replacement.

        Args:
            old_name: The deprecated effect name
            new_name: The current effect name it now resolves to
        """
        self._deprecated_names[old_name] = new_name

    @property
    def effects(self) -> list[EffectInfo]:
        """Return all registered effects.

        Returns:
            List of all registered EffectInfo entries
        """
        return list(self._effects.values())

    def get_effect(self, name: str) -> EffectInfo | None:
        """Look up an effect by name.

        A deprecated name registered via :meth:`register_deprecated_name`
        resolves to its replacement's :class:`EffectInfo` and emits a
        ``DeprecationWarning`` naming that replacement. An unknown name
        returns None without warning.

        Args:
            name: Effect name to look up

        Returns:
            EffectInfo if found, None otherwise
        """
        new_name = self._deprecated_names.get(name)
        if new_name is not None:
            warnings.warn(
                f'Effect name "{name}" is deprecated; use "{new_name}" instead',
                DeprecationWarning,
                stacklevel=2,
            )
            return self._effects.get(new_name)
        return self._effects.get(name)

    def get_effects_for_device(
        self, device: Light | LightComponent
    ) -> list[tuple[EffectInfo, DeviceSupport]]:
        """Get effects compatible with a specific light or light component.

        Classifies the device and returns effects that are RECOMMENDED
        or COMPATIBLE, sorted with RECOMMENDED first. A light component
        classifies as its light: a Mirror ring (``mirror.front`` or
        ``mirror.back``) as a Mirror, and a Ceiling uplight or downlight as a
        matrix. A light component can only be an effect participant for an
        effect that draws frames, so effects such as pulse are left out for
        a light component.

        Args:
            device: The light, or light component, to check

        Returns:
            List of (EffectInfo, DeviceSupport) tuples, sorted by support level
        """
        from lifx.devices.component.participant import LightComponent
        from lifx.effects.frame_effect import FrameEffect

        results = self.get_effects_for_device_type(_classify_device(device))
        if isinstance(device, LightComponent):
            results = [
                (info, support)
                for info, support in results
                if issubclass(info.effect_class, FrameEffect)
            ]
        return results

    def get_effects_for_device_type(
        self, device_type: DeviceType
    ) -> list[tuple[EffectInfo, DeviceSupport]]:
        """Get effects compatible with a device type.

        Returns effects that are RECOMMENDED or COMPATIBLE for the given
        device type, sorted with RECOMMENDED first.

        Args:
            device_type: The device type to filter for

        Returns:
            List of (EffectInfo, DeviceSupport) tuples, sorted by support level
        """
        results: list[tuple[EffectInfo, DeviceSupport]] = []
        for info in self._effects.values():
            support = info.device_support.get(device_type, DeviceSupport.NOT_SUPPORTED)
            if support is not DeviceSupport.NOT_SUPPORTED:
                results.append((info, support))

        # Sort: RECOMMENDED first, then COMPATIBLE
        results.sort(key=lambda x: 0 if x[1] is DeviceSupport.RECOMMENDED else 1)
        return results


_default_registry: EffectRegistry | None = None


def get_effect_registry() -> EffectRegistry:
    """Return the default registry pre-populated with all software effects.

    The registry is lazily initialized on first call.

    Returns:
        The default EffectRegistry instance
    """
    global _default_registry  # noqa: PLW0603
    if _default_registry is None:
        _default_registry = _build_default_registry()
    return _default_registry


def _build_default_registry() -> EffectRegistry:
    """Build and populate the default registry with software effects."""
    from lifx.effects.aurora import EffectAurora
    from lifx.effects.colorloop import EffectColorloop
    from lifx.effects.cylon import EffectCylon
    from lifx.effects.double_slit import EffectDoubleSlit
    from lifx.effects.embers import EffectEmbers
    from lifx.effects.fireworks import EffectFireworks
    from lifx.effects.flicker import EffectFlicker
    from lifx.effects.jacobs_ladder import EffectJacobsLadder
    from lifx.effects.newtons_cradle import EffectNewtonsCradle
    from lifx.effects.pendulum_wave import EffectPendulumWave
    from lifx.effects.plasma import EffectPlasma
    from lifx.effects.plasma2d import EffectPlasma2D
    from lifx.effects.progress import EffectProgress
    from lifx.effects.pulse import EffectPulse
    from lifx.effects.rainbow import EffectRainbow
    from lifx.effects.ripple import EffectRipple
    from lifx.effects.rule30 import EffectRule30
    from lifx.effects.rule_trio import EffectRuleTrio
    from lifx.effects.sine import EffectSine
    from lifx.effects.sonar import EffectSonar
    from lifx.effects.spectrum_sweep import EffectSpectrumSweep
    from lifx.effects.spin import EffectSpin
    from lifx.effects.sunrise import EffectSunrise, EffectSunset
    from lifx.effects.twinkle import EffectTwinkle
    from lifx.effects.wave import EffectWave

    registry = EffectRegistry()

    registry.register(
        EffectInfo(
            name="pulse",
            effect_class=EffectPulse,
            description="Pulse, blink, or breathe; sends one waveform to each light",
            device_support={
                DeviceType.LIGHT: DeviceSupport.RECOMMENDED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.RECOMMENDED,
                DeviceType.MIRROR: DeviceSupport.RECOMMENDED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="colorloop",
            effect_class=EffectColorloop,
            description="Continuous hue rotation cycling through the color spectrum",
            device_support={
                DeviceType.LIGHT: DeviceSupport.RECOMMENDED,
                DeviceType.MULTIZONE: DeviceSupport.COMPATIBLE,
                DeviceType.MATRIX: DeviceSupport.COMPATIBLE,
                DeviceType.MIRROR: DeviceSupport.COMPATIBLE,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="rainbow",
            effect_class=EffectRainbow,
            description="Animated rainbow spread across device pixels",
            device_support={
                DeviceType.LIGHT: DeviceSupport.COMPATIBLE,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.RECOMMENDED,
                DeviceType.MIRROR: DeviceSupport.RECOMMENDED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="flicker",
            effect_class=EffectFlicker,
            description="Fire/candle flicker with warm organic brightness variation",
            device_support={
                DeviceType.LIGHT: DeviceSupport.RECOMMENDED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.RECOMMENDED,
                DeviceType.MIRROR: DeviceSupport.RECOMMENDED,
            },
        )
    )
    registry.register_deprecated_name("flame", "flicker")

    registry.register(
        EffectInfo(
            name="cylon",
            effect_class=EffectCylon,
            description="Larson scanner — a bright eye sweeps back and forth",
            device_support={
                DeviceType.LIGHT: DeviceSupport.COMPATIBLE,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.RECOMMENDED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="aurora",
            effect_class=EffectAurora,
            description="Northern lights simulation with flowing colored bands",
            device_support={
                DeviceType.LIGHT: DeviceSupport.COMPATIBLE,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.RECOMMENDED,
                DeviceType.MIRROR: DeviceSupport.RECOMMENDED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="progress",
            effect_class=EffectProgress,
            description="Animated progress bar with traveling bright spot",
            device_support={
                DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="sunrise",
            effect_class=EffectSunrise,
            description="Sunrise color transition from night to daylight",
            device_support={
                DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MULTIZONE: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MATRIX: DeviceSupport.RECOMMENDED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="sunset",
            effect_class=EffectSunset,
            description="Sunset color transition from daylight to night",
            device_support={
                DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MULTIZONE: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MATRIX: DeviceSupport.RECOMMENDED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="wave",
            effect_class=EffectWave,
            description="Smooth color wave sweeping across zones",
            device_support={
                DeviceType.LIGHT: DeviceSupport.COMPATIBLE,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.RECOMMENDED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="sine",
            effect_class=EffectSine,
            description="Sinusoidal color wave oscillating across zones",
            device_support={
                DeviceType.LIGHT: DeviceSupport.COMPATIBLE,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.RECOMMENDED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="spectrum_sweep",
            effect_class=EffectSpectrumSweep,
            description="Full spectrum hue sweep across zones",
            device_support={
                DeviceType.LIGHT: DeviceSupport.COMPATIBLE,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.RECOMMENDED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="pendulum_wave",
            effect_class=EffectPendulumWave,
            description="Pendulum wave with phase-shifted oscillators",
            device_support={
                DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="double_slit",
            effect_class=EffectDoubleSlit,
            description="Double-slit interference pattern simulation",
            device_support={
                DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="twinkle",
            effect_class=EffectTwinkle,
            description="Random twinkling sparkle effect",
            device_support={
                DeviceType.LIGHT: DeviceSupport.RECOMMENDED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.COMPATIBLE,
                DeviceType.MIRROR: DeviceSupport.RECOMMENDED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="spin",
            effect_class=EffectSpin,
            description="Rotating color pattern spinning around zones",
            device_support={
                DeviceType.LIGHT: DeviceSupport.COMPATIBLE,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.RECOMMENDED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="rule30",
            effect_class=EffectRule30,
            description="Cellular automaton Rule 30 pattern generator",
            device_support={
                DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="rule_trio",
            effect_class=EffectRuleTrio,
            description="Three-state cellular automaton pattern generator",
            device_support={
                DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="embers",
            effect_class=EffectEmbers,
            description="Glowing embers fading in and out",
            device_support={
                DeviceType.LIGHT: DeviceSupport.COMPATIBLE,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="fireworks",
            effect_class=EffectFireworks,
            description="Fireworks bursts with expanding trails",
            device_support={
                DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="plasma",
            effect_class=EffectPlasma,
            description="1D plasma effect with sinusoidal color blending",
            device_support={
                DeviceType.LIGHT: DeviceSupport.COMPATIBLE,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="ripple",
            effect_class=EffectRipple,
            description="Expanding ripple waves from random origins",
            device_support={
                DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="jacobs_ladder",
            effect_class=EffectJacobsLadder,
            description="Electric arc climbing upward like a Jacob's ladder",
            device_support={
                DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="newtons_cradle",
            effect_class=EffectNewtonsCradle,
            description="Newton's cradle momentum transfer simulation",
            device_support={
                DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="sonar",
            effect_class=EffectSonar,
            description="Sonar ping sweeping outward from one end",
            device_support={
                DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    registry.register(
        EffectInfo(
            name="plasma2d",
            effect_class=EffectPlasma2D,
            description="2D plasma effect with flowing color patterns",
            device_support={
                DeviceType.LIGHT: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MULTIZONE: DeviceSupport.NOT_SUPPORTED,
                DeviceType.MATRIX: DeviceSupport.RECOMMENDED,
                DeviceType.MIRROR: DeviceSupport.NOT_SUPPORTED,
            },
        )
    )

    return registry
