"""lifx-async

Modern, type-safe async library for controlling LIFX devices.
"""

from __future__ import annotations

from importlib.metadata import version as get_version

from lifx.animation import Animator, AnimatorStats
from lifx.api import (
    DeviceGroup,
    discover,
    discover_mdns,
    find_by_ip,
    find_by_label,
    find_by_serial,
)
from lifx.color import HSBK, Colors
from lifx.const import INVALID_AMBIENT_LIGHT_RESPONSE, STATE_REFRESH_DEBOUNCE_MS
from lifx.devices import (
    CeilingLight,
    CeilingLightState,
    CollectionInfo,
    Device,
    DeviceCapabilities,
    DeviceInfo,
    DeviceVersion,
    FirmwareInfo,
    HevLight,
    HevLightState,
    InfraredLight,
    InfraredLightState,
    Light,
    LightState,
    MatrixEffect,
    MatrixLight,
    MatrixLightState,
    MultiZoneEffect,
    MultiZoneLight,
    MultiZoneLightState,
    TileInfo,
    WifiInfo,
)
from lifx.effects import (
    Conductor,
    DeviceSupport,
    DeviceType,
    EffectAurora,
    EffectColorloop,
    EffectFlame,
    EffectInfo,
    EffectProgress,
    EffectPulse,
    EffectRainbow,
    EffectRegistry,
    EffectSunrise,
    EffectSunset,
    FrameContext,
    FrameEffect,
    LIFXEffect,
    SunOrigin,
    get_effect_registry,
)
from lifx.exceptions import (
    LifxConnectionError,
    LifxDeviceNotFoundError,
    LifxError,
    LifxNetworkError,
    LifxProtocolError,
    LifxTimeoutError,
    LifxUnsupportedCommandError,
    LifxUnsupportedDeviceError,
)
from lifx.network.discovery import DiscoveredDevice, discover_devices
from lifx.products import ProductCapability, ProductInfo, ProductRegistry
from lifx.protocol.models import HevConfig, HevCycleState, mac_candidates_for_serial
from lifx.protocol.protocol_types import (
    Direction,
    FirmwareEffect,
    LightLastHevCycleResult,
    LightWaveform,
    TileEffectSkyType,
)
from lifx.theme import Theme, ThemeLibrary, get_theme

__version__ = get_version("lifx-async")  # type: ignore

__all__ = [
    # Version
    "__version__",
    # Core classes
    "Device",
    "Light",
    "LightState",
    "HevLight",
    "HevLightState",
    "InfraredLight",
    "InfraredLightState",
    "MultiZoneLight",
    "MultiZoneLightState",
    "MatrixLight",
    "MatrixLightState",
    "CeilingLight",
    "CeilingLightState",
    # Color
    "HSBK",
    "Colors",
    # Device info
    "CollectionInfo",
    "DeviceCapabilities",
    "DeviceInfo",
    "DeviceVersion",
    "FirmwareInfo",
    "WifiInfo",
    "mac_candidates_for_serial",
    # HEV
    "HevConfig",
    "HevCycleState",
    "LightLastHevCycleResult",
    # MultiZone
    "MultiZoneEffect",
    # Matrix (Tile)
    "MatrixEffect",
    "TileEffectSkyType",
    "TileInfo",
    # Effects
    "Conductor",
    "DeviceSupport",
    "DeviceType",
    "EffectAurora",
    "EffectColorloop",
    "EffectFlame",
    "EffectInfo",
    "EffectProgress",
    "EffectPulse",
    "EffectRainbow",
    "EffectRegistry",
    "EffectSunrise",
    "EffectSunset",
    "FrameContext",
    "FrameEffect",
    "LIFXEffect",
    "SunOrigin",
    "get_effect_registry",
    # Animation
    "Animator",
    "AnimatorStats",
    # Themes
    "Theme",
    "ThemeLibrary",
    "get_theme",
    # High-level API
    "DeviceGroup",
    "discover",
    "discover_mdns",
    "find_by_serial",
    "find_by_label",
    "find_by_ip",
    # Discovery (low-level)
    "discover_devices",
    "DiscoveredDevice",
    # Products
    "ProductInfo",
    "ProductRegistry",
    "ProductCapability",
    # Protocol types
    "LightWaveform",
    "FirmwareEffect",
    "Direction",
    # State management
    "INVALID_AMBIENT_LIGHT_RESPONSE",
    "STATE_REFRESH_DEBOUNCE_MS",
    # Exceptions
    "LifxError",
    "LifxDeviceNotFoundError",
    "LifxTimeoutError",
    "LifxProtocolError",
    "LifxConnectionError",
    "LifxNetworkError",
    "LifxUnsupportedCommandError",
    "LifxUnsupportedDeviceError",
]
