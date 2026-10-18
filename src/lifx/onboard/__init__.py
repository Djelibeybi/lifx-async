"""Onboarding of LIFX devices onto a Wi-Fi network.

Import explicitly: ``import lifx.onboard``. Nothing here is exported from the
top-level ``lifx`` namespace. Standard library only.
"""

from lifx.onboard.errors import (
    HostLeftSoftApError,
    HostRejoinError,
    InvalidSoftApTargetError,
    LegacyTlsUnavailableError,
    LifxOnboardError,
    MissingCredentialsError,
    OnboardPhase,
    SoftApDialError,
    SoftApJoinError,
    SoftApNotFoundError,
    SoftApSendError,
    SoftApUnreachableError,
    SoftApWaitTimeoutError,
    VerifyTimeoutError,
)
from lifx.onboard.events import OnboardEvent, OnboardEventQueue, OnboardEventType
from lifx.onboard.models import HomeNetwork, SoftApNetwork
from lifx.onboard.result import Result
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
    "HostLeftSoftApError",
    "HostRejoinError",
    "InvalidSoftApTargetError",
    "LegacyTlsUnavailableError",
    "LifxOnboardError",
    "MissingCredentialsError",
    "OnboardEvent",
    "OnboardEventQueue",
    "OnboardEventType",
    "OnboardPhase",
    "Result",
    "SoftApClient",
    "SoftApConnection",
    "SoftApDialError",
    "SoftApJoinError",
    "SoftApNetwork",
    "SoftApNotFoundError",
    "SoftApSendError",
    "SoftApUnreachableError",
    "SoftApWaitTimeoutError",
    "VerifyTimeoutError",
    "WifiInterface",
    "WifiSecurity",
    "build_access_point_message",
    "parse_serial",
    "serial_from_softap_ssid",
]
