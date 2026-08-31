"""Low-level discovery compatibility umbrella.

Canonical implementations live in :mod:`lifx.network.discovery.udp`,
:mod:`lifx.network.discovery.coordinator`, and
:mod:`lifx.network.discovery.mdns`.
"""

from lifx.network.discovery.udp import (
    DiscoveredDevice,
    DiscoveryResponse,
    discover_devices,
)

__all__ = ["DiscoveredDevice", "DiscoveryResponse", "discover_devices"]
