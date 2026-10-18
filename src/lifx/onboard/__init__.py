"""Onboarding of LIFX devices onto a Wi-Fi network.

Import explicitly: ``import lifx.onboard``. Nothing here is exported from the
top-level ``lifx`` namespace. Standard library only.
"""

from lifx.onboard.errors import LifxOnboardError, MissingCredentialsError, OnboardPhase
from lifx.onboard.models import HomeNetwork, SoftApNetwork
from lifx.onboard.serials import LIFX_OUI, parse_serial, serial_from_softap_ssid

__all__ = [
    "LIFX_OUI",
    "HomeNetwork",
    "LifxOnboardError",
    "MissingCredentialsError",
    "OnboardPhase",
    "SoftApNetwork",
    "parse_serial",
    "serial_from_softap_ssid",
]
