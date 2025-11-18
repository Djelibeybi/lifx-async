"""Device abstractions for LIFX products."""

from __future__ import annotations

from lifx.devices.base import (
    Device,
    DeviceInfo,
    DeviceVersion,
    FirmwareInfo,
    GroupInfo,
    LocationInfo,
    WifiInfo,
)
from lifx.devices.hev import HevLight
from lifx.devices.infrared import InfraredLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixEffect, MatrixLight, TileInfo
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight

__all__ = [
    "Device",
    "DeviceInfo",
    "DeviceVersion",
    "FirmwareInfo",
    "GroupInfo",
    "HevLight",
    "InfraredLight",
    "Light",
    "LocationInfo",
    "MatrixEffect",
    "MatrixLight",
    "MultiZoneEffect",
    "MultiZoneLight",
    "TileInfo",
    "WifiInfo",
]
