"""lifx-async

Modern, type-safe async library for controlling LIFX devices.
"""

from __future__ import annotations

from importlib.metadata import version as get_version

from lifx.api import (
    DeviceGroup,
    discover,
    find_by_ip,
    find_by_label,
    find_by_serial,
)
from lifx.color import HSBK, Colors
from lifx.devices import (
    Device,
    DeviceInfo,
    DeviceVersion,
    FirmwareInfo,
    HevLight,
    InfraredLight,
    Light,
    MatrixEffect,
    MatrixLight,
    MultiZoneEffect,
    MultiZoneLight,
    TileInfo,
    WifiInfo,
)
from lifx.effects import Conductor, EffectColorloop, EffectPulse, LIFXEffect
from lifx.exceptions import (
    LifxConnectionError,
    LifxDeviceNotFoundError,
    LifxError,
    LifxNetworkError,
    LifxProtocolError,
    LifxTimeoutError,
    LifxUnsupportedCommandError,
)
from lifx.network.discovery import DiscoveredDevice, discover_devices
from lifx.products import ProductCapability, ProductInfo, ProductRegistry
from lifx.protocol.protocol_types import (
    LightWaveform,
    MultiZoneEffectType,
    TileEffectType,
)
from lifx.theme import Theme, ThemeLibrary, get_theme

__version__ = get_version("lifx-async")  # type: ignore

__all__ = [
    # Version
    "__version__",
    # Core classes
    "Device",
    "Light",
    "HevLight",
    "InfraredLight",
    "MultiZoneLight",
    "MatrixLight",
    # Color
    "HSBK",
    "Colors",
    # Device info
    "DeviceInfo",
    "DeviceVersion",
    "FirmwareInfo",
    "WifiInfo",
    # MultiZone
    "MultiZoneEffect",
    # Matrix (Tile)
    "MatrixEffect",
    "TileInfo",
    # Effects
    "Conductor",
    "LIFXEffect",
    "EffectPulse",
    "EffectColorloop",
    # Themes
    "Theme",
    "ThemeLibrary",
    "get_theme",
    # High-level API
    "DeviceGroup",
    "discover",
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
    "MultiZoneEffectType",
    "TileEffectType",
    # Exceptions
    "LifxError",
    "LifxDeviceNotFoundError",
    "LifxTimeoutError",
    "LifxProtocolError",
    "LifxConnectionError",
    "LifxNetworkError",
    "LifxUnsupportedCommandError",
]
