"""The outcome of one onboarding run."""

from __future__ import annotations

from dataclasses import dataclass

from lifx.onboard.errors import LifxOnboardError, OnboardPhase
from lifx.protocol.models import Serial

__all__ = ["Result"]


@dataclass(frozen=True)
class Result:
    """What one onboarding run achieved.

    ``onboard()`` returns a ``Result`` on success and raises on failure; the
    raised error carries the same ``Result`` as its ``result`` attribute.

    Attributes:
        serial: The device onboarded, once known.
        verified: Whether the device was seen on the LAN afterwards.
        took: Seconds the run took.
        phase: The phase that failed; ``None`` on success.
        error: The failure; ``None`` on success.
        host_network: The network the host ended on, when known.
    """

    serial: Serial | None
    verified: bool
    took: float
    phase: OnboardPhase | None = None
    error: LifxOnboardError | None = None
    host_network: str | None = None
