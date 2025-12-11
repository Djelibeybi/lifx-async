"""Device abstractions for LIFX products."""

from __future__ import annotations

from lifx.devices.base import (
    CollectionInfo,
    Device,
    DeviceInfo,
    DeviceVersion,
    FirmwareInfo,
    WifiInfo,
)
from lifx.devices.ceiling import CeilingLight, CeilingLightState
from lifx.devices.hev import HevLight, HevLightState
from lifx.devices.infrared import InfraredLight, InfraredLightState
from lifx.devices.light import Light, LightState
from lifx.devices.matrix import MatrixEffect, MatrixLight, MatrixLightState, TileInfo
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight, MultiZoneLightState

__all__ = [
    "CeilingLight",
    "CeilingLightState",
    "CollectionInfo",
    "Device",
    "DeviceInfo",
    "DeviceVersion",
    "FirmwareInfo",
    "HevLight",
    "HevLightState",
    "InfraredLight",
    "InfraredLightState",
    "Light",
    "LightState",
    "MatrixEffect",
    "MatrixLight",
    "MatrixLightState",
    "MultiZoneEffect",
    "MultiZoneLight",
    "MultiZoneLightState",
    "TileInfo",
    "WifiInfo",
]
