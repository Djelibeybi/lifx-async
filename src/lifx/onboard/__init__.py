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
from lifx.onboard.machine import (
    AUTO_JOIN_WAIT,
    DIAL_TIMEOUT,
    FIND_POLL,
    FIND_TIMEOUT,
    REJOIN_POLL,
    REJOIN_TIMEOUT,
    VERIFY_POLL,
    VERIFY_TIMEOUT,
    WAIT_POLL,
    WAIT_TIMEOUT,
    onboard,
)
from lifx.onboard.models import HomeNetwork, SoftApNetwork
from lifx.onboard.protocols import (
    CurrentNetworkReporter,
    Disassociator,
    Joiner,
    NetworkForgetter,
    Scanner,
)
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
    "AUTO_JOIN_WAIT",
    "DIAL_TIMEOUT",
    "FIND_POLL",
    "FIND_TIMEOUT",
    "LIFX_OUI",
    "REJOIN_POLL",
    "REJOIN_TIMEOUT",
    "SOFTAP_ADDRESS",
    "SOFTAP_PORT",
    "VERIFY_POLL",
    "VERIFY_TIMEOUT",
    "WAIT_POLL",
    "WAIT_TIMEOUT",
    "CurrentNetworkReporter",
    "Disassociator",
    "HomeNetwork",
    "HostLeftSoftApError",
    "HostRejoinError",
    "InvalidSoftApTargetError",
    "Joiner",
    "LegacyTlsUnavailableError",
    "LifxOnboardError",
    "MissingCredentialsError",
    "NetworkForgetter",
    "OnboardEvent",
    "OnboardEventQueue",
    "OnboardEventType",
    "OnboardPhase",
    "Result",
    "Scanner",
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
    "onboard",
    "parse_serial",
    "serial_from_softap_ssid",
]
