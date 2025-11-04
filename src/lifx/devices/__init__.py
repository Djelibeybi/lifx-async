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
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight
from lifx.devices.tile import TileDevice, TileEffect, TileInfo, TileRect

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
    "MultiZoneEffect",
    "MultiZoneLight",
    "TileDevice",
    "TileEffect",
    "TileInfo",
    "TileRect",
    "WifiInfo",
]
