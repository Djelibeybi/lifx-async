"""The host Wi-Fi interface a caller supplies to the onboarding state machine.

lifx-async ships no implementation of these protocols: scanning and joining
Wi-Fi networks needs subprocesses, ``ctypes`` or an app bundle, none of which
belongs in a zero-dependency library. A caller supplies a :class:`Scanner` and
a :class:`Joiner`; the three optional capabilities are discovered at runtime
with ``isinstance``, the ``Joiner`` being consulted before the ``Scanner``
because the ``Joiner`` owns the association.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from lifx.onboard.models import SoftApNetwork

__all__ = [
    "CurrentNetworkReporter",
    "Disassociator",
    "Joiner",
    "NetworkForgetter",
    "Scanner",
]


class Scanner(Protocol):
    """Lists the Wi-Fi networks the host can see."""

    @property
    def interface(self) -> str:
        """The host interface scanned, for diagnostics."""
        ...

    async def scan(
        self, *, min_rssi: float = 0.0, include_non_lifx: bool = False
    ) -> list[SoftApNetwork]:
        """Return the networks currently visible.

        Only LIFX SoftAPs are returned unless ``include_non_lifx`` is set.
        An empty list with no error is a valid result.
        """
        ...


class Joiner(Protocol):
    """Joins the host to a Wi-Fi network."""

    async def join(self, network: SoftApNetwork) -> None:
        """Join ``network``; a no-op when already joined."""
        ...

    async def rejoin(self, ssid: str, password: str = "") -> None:
        """Join the network named ``ssid`` with ``password``."""
        ...


@runtime_checkable
class CurrentNetworkReporter(Protocol):
    """Optional capability: reports the network the host is on."""

    async def current_ssid(self) -> str | None:
        """The SSID the host is associated with, or ``None`` when it is not."""
        ...


@runtime_checkable
class NetworkForgetter(Protocol):
    """Optional capability: removes a network from the host's saved networks."""

    async def forget(self, ssid: str) -> None:
        """Forget the saved network named ``ssid``."""
        ...


@runtime_checkable
class Disassociator(Protocol):
    """Optional capability: drops the host's current association."""

    async def disassociate(self) -> None:
        """Leave the current network without joining another."""
        ...
