"""Onboarding of LIFX devices onto a Wi-Fi network.

Import explicitly: ``import lifx.onboard``. Nothing here is exported from the
top-level ``lifx`` namespace. Standard library only.
"""

from lifx.onboard.errors import (
    LegacyTlsUnavailableError,
    LifxOnboardError,
    MissingCredentialsError,
    OnboardPhase,
    SoftApDialError,
    SoftApSendError,
    SoftApUnreachableError,
)
from lifx.onboard.models import HomeNetwork, SoftApNetwork
from lifx.onboard.serials import LIFX_OUI, parse_serial, serial_from_softap_ssid
from lifx.onboard.softap import (
    SOFTAP_ADDRESS,
    SOFTAP_PORT,
    SoftApClient,
    SoftApConnection,
    build_access_point_message,
)
from lifx.protocol.protocol_types import WifiInterface, WifiSecurity

__all__ = [
    "LIFX_OUI",
    "SOFTAP_ADDRESS",
    "SOFTAP_PORT",
    "HomeNetwork",
    "LegacyTlsUnavailableError",
    "LifxOnboardError",
    "MissingCredentialsError",
    "OnboardPhase",
    "SoftApClient",
    "SoftApConnection",
    "SoftApDialError",
    "SoftApNetwork",
    "SoftApSendError",
    "SoftApUnreachableError",
    "WifiInterface",
    "WifiSecurity",
    "build_access_point_message",
    "parse_serial",
    "serial_from_softap_ssid",
]
