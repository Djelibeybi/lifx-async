"""Exceptions and phases shared by the onboarding state machine."""

from __future__ import annotations

from enum import Enum
from typing import Any

from lifx.exceptions import LifxError


class OnboardPhase(Enum):
    """The phase of the onboarding sequence an event or error belongs to."""

    SCAN = "scan"
    JOIN = "join"
    WAIT = "wait"
    DIAL = "dial"
    CONFIGURE = "configure"
    REJOIN = "rejoin"
    VERIFY = "verify"


class LifxOnboardError(LifxError):
    """Base class for every error raised while onboarding a device.

    Messages never contain the home network password.

    Attributes:
        phase: The phase that failed, when known.
        result: The onboarding result describing the failure, when one exists.
    """

    def __init__(
        self,
        message: str,
        *,
        phase: OnboardPhase | None = None,
        result: Any = None,
    ) -> None:
        super().__init__(message)
        self.phase = phase
        self.result = result


class MissingCredentialsError(LifxOnboardError, ValueError):
    """Raised when a secured home network is given without a password."""


class _PhasedOnboardError(LifxOnboardError):
    """An onboarding error that knows which phase it normally belongs to."""

    default_phase: OnboardPhase | None = None

    def __init__(
        self,
        message: str,
        *,
        phase: OnboardPhase | None = None,
        result: Any = None,
    ) -> None:
        super().__init__(
            message,
            phase=self.default_phase if phase is None else phase,
            result=result,
        )


class SoftApUnreachableError(_PhasedOnboardError):
    """Raised when a plain TCP probe of the SoftAP address does not connect.

    The message names the address and port; it never carries credentials.
    """

    default_phase = OnboardPhase.DIAL


class SoftApDialError(_PhasedOnboardError):
    """Raised when the TCP connect or TLS handshake to the SoftAP fails.

    The message names the address and port; it never carries credentials.
    """

    default_phase = OnboardPhase.DIAL


class SoftApSendError(_PhasedOnboardError):
    """Raised when writing the credential message to the SoftAP fails.

    The message names the address and port; it never carries credentials.
    """

    default_phase = OnboardPhase.CONFIGURE


class LegacyTlsUnavailableError(_PhasedOnboardError):
    """Raised when the host's OpenSSL refuses the TLS 1.0 legacy configuration.

    The message includes ``ssl.OPENSSL_VERSION`` so the failure is attributed
    to the host rather than the device.
    """
