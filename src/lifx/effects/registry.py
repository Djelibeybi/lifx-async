"""Effect registry for discovering and querying available effects.

This module provides a central registry for effect discovery, enabling
consumers like Home Assistant to dynamically find and present available
effects based on device type.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lifx.devices.light import Light
    from lifx.effects.base import LIFXEffect


class DeviceType(Enum):
    """Device categories for effect compatibility classification."""

    LIGHT = "light"
    MULTIZONE = "multizone"
    MATRIX = "matrix"


class DeviceSupport(Enum):
    """How well an effect supports a device type."""

    RECOMMENDED = "recommended"
    COMPATIBLE = "compatible"
    NOT_SUPPORTED = "not_supported"


@dataclass(frozen=True)
class EffectInfo:
    """Metadata about a registered effect.

    Attributes:
        name: Effect name (e.g. "flame")
        effect_class: The effect class (e.g. EffectFlame)
        description: Human-readable one-liner
        device_support: Per-device-type support level
    """

    name: str
    effect_class: type[LIFXEffect]
    description: str
    device_support: dict[DeviceType, DeviceSupport]


def _classify_device(device: Light) -> DeviceType:
    """Classify a device into a DeviceType category.

    Uses isinstance checks with lazy imports to avoid circular dependencies.

    Args:
        device: The light device to classify

    Returns:
        DeviceType classification for the device
    """
    from lifx.devices.matrix import MatrixLight
    from lifx.devices.multizone import MultiZoneLight

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

    def register(self, info: EffectInfo) -> None:
        """Register an effect.

        Args:
            info: Effect metadata to register
        """
        self._effects[info.name] = info

    @property
    def effects(self) -> list[EffectInfo]:
        """Return all registered effects.

        Returns:
            List of all registered EffectInfo entries
        """
        return list(self._effects.values())

    def get_effect(self, name: str) -> EffectInfo | None:
        """Look up an effect by name.

        Args:
            name: Effect name to look up

        Returns:
            EffectInfo if found, None otherwise
        """
        return self._effects.get(name)

    def get_effects_for_device(
        self, device: Light
    ) -> list[tuple[EffectInfo, DeviceSupport]]:
        """Get effects compatible with a specific device.

        Classifies the device and returns effects that are RECOMMENDED
        or COMPATIBLE, sorted with RECOMMENDED first.

        Args:
            device: The light device to check

        Returns:
            List of (EffectInfo, DeviceSupport) tuples, sorted by support level
        """
        device_type = _classify_device(device)
        return self.get_effects_for_device_type(device_type)

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
    """Return the default registry pre-populated with all built-in effects.

    The registry is lazily initialized on first call.

    Returns:
        The default EffectRegistry instance
    """
    global _default_registry  # noqa: PLW0603
    if _default_registry is None:
        _default_registry = _build_default_registry()
    return _default_registry


def _build_default_registry() -> EffectRegistry:
    """Build and populate the default registry with built-in effects."""
    from lifx.effects.aurora import EffectAurora
    from lifx.effects.colorloop import EffectColorloop
    from lifx.effects.flame import EffectFlame
    from lifx.effects.progress import EffectProgress
    from lifx.effects.pulse import EffectPulse
    from lifx.effects.rainbow import EffectRainbow
    from lifx.effects.sunrise import EffectSunrise, EffectSunset

    registry = EffectRegistry()

    registry.register(
        EffectInfo(
            name="pulse",
            effect_class=EffectPulse,
            description="Pulse, blink, or breathe effect using firmware waveforms",
            device_support={
                DeviceType.LIGHT: DeviceSupport.RECOMMENDED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.RECOMMENDED,
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
            },
        )
    )

    registry.register(
        EffectInfo(
            name="flame",
            effect_class=EffectFlame,
            description="Fire/candle flicker with warm organic brightness variation",
            device_support={
                DeviceType.LIGHT: DeviceSupport.RECOMMENDED,
                DeviceType.MULTIZONE: DeviceSupport.RECOMMENDED,
                DeviceType.MATRIX: DeviceSupport.RECOMMENDED,
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
            },
        )
    )

    return registry
