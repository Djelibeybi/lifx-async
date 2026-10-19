"""LAN verification: confirm an onboarded device through a ``DeviceWatcher``.

A device that has accepted its credentials reboots onto the home network and
answers discovery there. Verification waits for the watcher to report it at
an address other than the SoftAP's. Only events emitted after verification
begins count: the watcher's existing record for the serial may date from
before the device was reset, so it is never consulted.

Several verifications may share one watcher. Each registers its own listener
and resolves independently, so one device's sighting never consumes another's
event; bulk onboarding relies on this to verify devices while it keeps
scanning.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol

from lifx.onboard._aio import bounded
from lifx.onboard.errors import VerifyTimeoutError
from lifx.protocol.models import Serial
from lifx.watcher import DeviceEvent, DeviceEventType, EventListener

__all__ = ["LanSighting", "LanVerification", "VerificationWatcher", "verify_on_lan"]

_LOGGER = logging.getLogger(__name__)


class VerificationWatcher(Protocol):
    """The part of a ``DeviceWatcher`` verification uses.

    A fake implementing these three members can stand in for the real
    watcher, which is how bulk onboarding's interleaving is tested.
    """

    def add_listener(self, listener: EventListener) -> Callable[[], None]:
        """Call ``listener`` for every event from now on; returns the remover."""
        ...

    async def __aenter__(self) -> object:
        """Start watching; the initial sweep runs before this returns."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> object:
        """Stop watching."""
        ...


@dataclass(frozen=True)
class LanSighting:
    """The event that verified a device.

    Attributes:
        address: The IP address the device answered from.
        port: The UDP port it answered from.
        took: Seconds from the start of verification to the sighting.
    """

    address: str
    port: int
    took: float


def _same_host(address: str, other: str) -> bool:
    """Whether two address strings name the same IP.

    An IPv6 zone suffix (``%en0``) is ignored. An address that does not parse
    cannot be the SoftAP, so it compares unequal.
    """
    try:
        return ipaddress.ip_address(address.split("%", 1)[0]) == ipaddress.ip_address(
            other.split("%", 1)[0]
        )
    except ValueError:
        return False


def _timed_out(serial: str, timeout: float) -> str:
    return f"{serial} was not seen on the LAN within {timeout}s"


class LanVerification:
    """One device's pending verification on a shared watcher.

    Constructing it registers a listener, so from that moment the first
    ``ADDED`` or ``UPDATED`` event for ``serial`` whose address is not
    ``softap_address`` resolves it. Await :meth:`wait` for the result; it
    removes the listener on every way out. Call :meth:`close` instead to
    abandon a verification that was never awaited.

    Args:
        watcher: The watcher to listen to. It need not be open yet: a watcher
            entered after construction has its initial sweep counted.
        serial: The device expected to appear.
        softap_address: The SoftAP address a sighting is ignored at.
    """

    def __init__(
        self,
        watcher: VerificationWatcher,
        serial: Serial,
        *,
        softap_address: str,
    ) -> None:
        self._watcher = watcher
        self._serial = str(serial)
        self._softap_address = softap_address
        self._started = time.monotonic()
        self._sighting: LanSighting | None = None
        self._seen = asyncio.Event()
        self._remove = watcher.add_listener(self._on_event)

    @property
    def sighting(self) -> LanSighting | None:
        """The verifying sighting, once there is one."""
        return self._sighting

    def close(self) -> None:
        """Stop listening. Safe to call more than once."""
        self._remove()

    def _on_event(self, event: DeviceEvent) -> None:
        if self._sighting is not None or event.type is DeviceEventType.REMOVED:
            return
        if event.serial != self._serial:
            return
        address, port = event.device.ip, event.device.port
        if _same_host(address, self._softap_address):
            _LOGGER.debug("%s seen at the SoftAP address %s", self._serial, address)
            return
        self._sighting = LanSighting(
            address=address, port=port, took=time.monotonic() - self._started
        )
        self._seen.set()

    async def wait(self, timeout: float, *, open_watcher: bool = False) -> LanSighting:
        """Wait up to ``timeout`` seconds for the verifying sighting.

        Args:
            timeout: Seconds to wait, including the watcher's initial sweep
                when ``open_watcher`` is set.
            open_watcher: Enter the watcher first, so its initial sweep
                counts, and exit it on every way out. Otherwise the watcher is
                used as is and left running.

        Raises:
            VerifyTimeoutError: If the device is not seen off the SoftAP in time.
        """
        if not open_watcher:
            return await self._wait(timeout)
        deadline = time.monotonic() + timeout
        try:
            try:
                await bounded(self._watcher.__aenter__(), timeout)
            except asyncio.TimeoutError:
                raise VerifyTimeoutError(_timed_out(self._serial, timeout)) from None
            return await self._wait(max(0.0, deadline - time.monotonic()))
        finally:
            self.close()
            await self._watcher.__aexit__(None, None, None)

    async def _wait(self, timeout: float) -> LanSighting:
        try:
            await bounded(self._seen.wait(), timeout)
        except asyncio.TimeoutError:
            raise VerifyTimeoutError(_timed_out(self._serial, timeout)) from None
        finally:
            self.close()
        assert self._sighting is not None
        return self._sighting


async def verify_on_lan(
    watcher: VerificationWatcher,
    serial: Serial,
    *,
    softap_address: str,
    timeout: float,
    open_watcher: bool = False,
) -> LanSighting:
    """Wait for ``serial`` to be seen on the LAN through ``watcher``.

    A convenience over :class:`LanVerification` for a verification that
    starts and finishes in one call.

    Args:
        watcher: A ``DeviceWatcher``. With ``open_watcher`` it is entered after
            the listener is registered, so its initial sweep counts, and
            exited on every exit; otherwise it is used as is and left running.
        serial: The device expected to appear.
        softap_address: The SoftAP address a sighting is ignored at.
        timeout: Seconds to wait, including the watcher's initial sweep when
            ``open_watcher`` is set.

    Raises:
        VerifyTimeoutError: If the device is not seen off the SoftAP in time.
    """
    verification = LanVerification(watcher, serial, softap_address=softap_address)
    return await verification.wait(timeout, open_watcher=open_watcher)
