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
