"""The single-device onboarding sequence.

``onboard()`` takes a device from its SoftAP onto the home network: resolve
the target, scan, join, wait for the control socket, dial, configure, return
the host to its own network and (ticket #331) verify the device on the LAN.
Each phase emits events, every failure is a typed ``LifxOnboardError`` whose
``result`` describes the run, and once the host has joined the SoftAP any
failure or cancellation runs host recovery so the machine is never left on
the device's network.

The timing defaults are lifx-onboard's, tuned on hardware. The password is
never logged; SSIDs and phases are.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, TypeVar

from lifx.onboard.errors import (
    HostLeftSoftApError,
    HostRejoinError,
    InvalidSoftApTargetError,
    LifxOnboardError,
    OnboardPhase,
    SoftApDialError,
    SoftApJoinError,
    SoftApNotFoundError,
    SoftApUnreachableError,
    SoftApWaitTimeoutError,
)
from lifx.onboard.events import OnboardEvent, OnboardEventQueue, OnboardEventType
from lifx.onboard.models import HomeNetwork, SoftApNetwork
from lifx.onboard.protocols import (
    CurrentNetworkReporter,
    Disassociator,
    Joiner,
    NetworkForgetter,
    Scanner,
)
from lifx.onboard.result import Result
from lifx.onboard.serials import parse_serial
from lifx.onboard.softap import (
    SOFTAP_ADDRESS,
    SOFTAP_PORT,
    SoftApClient,
    SoftApConnection,
)
from lifx.protocol.models import Serial
from lifx.watcher import DeviceWatcher

__all__ = [
    "AUTO_JOIN_WAIT",
    "DIAL_TIMEOUT",
    "FIND_POLL",
    "FIND_TIMEOUT",
    "REJOIN_POLL",
    "REJOIN_TIMEOUT",
    "VERIFY_POLL",
    "VERIFY_TIMEOUT",
    "WAIT_POLL",
    "WAIT_TIMEOUT",
    "onboard",
]

_LOGGER = logging.getLogger(__name__)

#: Seconds to keep scanning for, and then joining, the SoftAP.
FIND_TIMEOUT = 30.0
#: Seconds between scan attempts and between join attempts.
FIND_POLL = 2.0
#: Seconds to wait for the SoftAP to accept a TCP probe after joining.
WAIT_TIMEOUT = 30.0
#: Seconds between probes; each probe is also bounded by this.
WAIT_POLL = 1.0
#: Seconds allowed for the TCP connect plus TLS handshake.
DIAL_TIMEOUT = 10.0
#: Seconds to spend returning the host to each rejoin target.
REJOIN_TIMEOUT = 30.0
#: Seconds between rejoin attempts and between host network polls.
REJOIN_POLL = 2.0
#: Seconds to give the OS auto-join once the host has left the SoftAP.
AUTO_JOIN_WAIT = 10.0
#: Seconds to wait for the device to appear on the LAN.
VERIFY_TIMEOUT = 60.0
#: Seconds between LAN discovery sweeps while verifying.
VERIFY_POLL = 1.0

_MACOS_HINT = (
    "On macOS an empty scan usually means the OS redacted the results; "
    "pass the full SoftAP name as the target to skip the scan."
)

_T = TypeVar("_T")
_Capability = TypeVar("_Capability")

EventCallback = Callable[[OnboardEvent], None]


@dataclass(frozen=True)
class _RejoinTarget:
    """One network the host may be returned to."""

    ssid: str
    password: str = field(repr=False)
    auto_join: bool = False


def _name(error: BaseException) -> str:
    """The only part of a caller-supplied exception the library repeats.

    A Scanner or Joiner backend may put the password into an error message
    or traceback (a subprocess echoing its argv, for example), so neither is
    ever logged or chained; the type name is.
    """
    return type(error).__name__


def _is_softap_name(ssid: str) -> bool:
    try:
        Serial.from_softap_ssid(ssid)
    except ValueError:
        return False
    return True


async def _await_shielded(
    coro: Coroutine[Any, Any, _T],
) -> asyncio.CancelledError | None:
    """Run ``coro`` to completion even if the current task is cancelled.

    Returns a cancellation that arrived while waiting, if any, so the caller
    can re-raise it once the shielded work is done.
    """
    task = asyncio.create_task(coro)
    cancellation: asyncio.CancelledError | None = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as error:
            cancellation = error
    task.result()
    return cancellation


class _Run:
    """One execution of the onboarding sequence."""

    def __init__(
        self,
        network: HomeNetwork,
        *,
        scanner: Scanner | None,
        joiner: Joiner,
        softap: SoftApClient,
        verify: DeviceWatcher | bool,
        on_event: EventCallback | None,
        events: OnboardEventQueue | None,
        rejoin_ssid: str | None,
        rejoin_password: str,
        min_rssi: float,
        include_non_lifx: bool,
        find_timeout: float,
        find_poll: float,
        wait_timeout: float,
        wait_poll: float,
        dial_timeout: float,
        rejoin_timeout: float,
        rejoin_poll: float,
        auto_join_wait: float,
        verify_timeout: float,
        verify_poll: float,
    ) -> None:
        self._network = network
        self._scanner = scanner
        self._joiner = joiner
        self._softap = softap
        self._verify = verify
        self._on_event = on_event
        self._events = events
        self._rejoin_ssid = rejoin_ssid
        self._rejoin_password = rejoin_password
        self._min_rssi = min_rssi
        self._include_non_lifx = include_non_lifx
        self._find_timeout = find_timeout
        self._find_poll = find_poll
        self._wait_timeout = wait_timeout
        self._wait_poll = wait_poll
        self._dial_timeout = dial_timeout
        self._rejoin_timeout = rejoin_timeout
        self._rejoin_poll = rejoin_poll
        self._auto_join_wait = auto_join_wait
        self._verify_timeout = verify_timeout
        self._verify_poll = verify_poll

        self._reporter = self._capability(CurrentNetworkReporter)
        self._forgetter = self._capability(NetworkForgetter)
        self._disassociator = self._capability(Disassociator)

        self._started = time.monotonic()
        self._serial: Serial | None = None
        self._softap_network: SoftApNetwork | None = None
        self._original_ssid: str | None = None
        self._host_network: str | None = None

    # ---- helpers --------------------------------------------------------

    def _capability(self, protocol: type[_Capability]) -> _Capability | None:
        """Find an optional capability, consulting the Joiner before the Scanner."""
        for candidate in (self._joiner, self._scanner):
            if isinstance(candidate, protocol):
                return candidate
        return None

    def _emit(
        self,
        event_type: OnboardEventType,
        phase: OnboardPhase | None,
        **fields: Any,
    ) -> None:
        event = OnboardEvent(type=event_type, phase=phase, **fields)
        _LOGGER.debug(
            "onboarding %s in phase %s (ssid=%s)", event_type.value, phase, event.ssid
        )
        if self._events is not None:
            self._events.put(event)
        if self._on_event is not None:
            try:
                self._on_event(event)
            except Exception as error:
                _LOGGER.error(
                    "onboarding event callback failed for %s: %s",
                    event_type.value,
                    _name(error),
                )

    def _elapsed(self) -> float:
        return time.monotonic() - self._started

    async def _current_ssid(self) -> str | None:
        if self._reporter is None:
            return None
        return await self._reporter.current_ssid()

    @property
    def _softap_ssid(self) -> str:
        assert self._softap_network is not None
        return self._softap_network.ssid

    # ---- the sequence ---------------------------------------------------

    def _resolve_target(self, target: str | Serial | None) -> None:
        """Set the serial and, for a full SoftAP name, the network to join."""
        if isinstance(target, str) and target.startswith("LIFX"):
            try:
                self._softap_network = SoftApNetwork.from_ssid(target)
            except ValueError as error:
                raise InvalidSoftApTargetError(
                    f"{target!r} is not a LIFX SoftAP name"
                ) from error
            self._serial = self._softap_network.serial
        elif target is not None:
            try:
                self._serial = parse_serial(target)
            except (ValueError, TypeError) as error:
                raise InvalidSoftApTargetError(
                    f"{target!r} is not a LIFX SoftAP name, serial or serial suffix"
                ) from error
        if self._softap_network is None and self._scanner is None:
            raise ValueError("A scanner is required unless target is a SoftAP name")

    async def run(self, target: str | Serial | None) -> Result:
        self._resolve_target(target)
        original = await self._current_ssid()
        if original is not None and not _is_softap_name(original):
            self._original_ssid = original
        _LOGGER.debug("onboarding starts on host network %r", self._original_ssid)

        joined = False
        try:
            if self._softap_network is None:
                self._softap_network = await self._scan_phase()
                self._serial = self._softap_network.serial
            await self._join_phase()
            joined = True
            await self._wait_phase()
            await self._dial_phase()
            await self._configure_phase()
            self._host_network = await self._rejoin_phase()
            verified = await self._verify_phase()
        except BaseException as error:
            cancellation = None
            if joined:
                cancellation = await _await_shielded(self._recover_host())
            if isinstance(error, LifxOnboardError):
                error.result = self._result(phase=error.phase, error=error)
                self._emit(
                    OnboardEventType.FAILED,
                    error.phase,
                    serial=self._serial,
                    error=error,
                )
            if cancellation is not None and not isinstance(
                error, asyncio.CancelledError
            ):
                raise cancellation from error
            raise
        return self._result(verified=verified)

    def _result(
        self,
        *,
        verified: bool = False,
        phase: OnboardPhase | None = None,
        error: LifxOnboardError | None = None,
    ) -> Result:
        return Result(
            serial=self._serial,
            verified=verified,
            took=self._elapsed(),
            phase=phase,
            error=error,
            host_network=self._host_network,
        )

    def _matches(self, network: SoftApNetwork) -> bool:
        if network.serial is None:
            return False
        return self._serial is None or network.serial == self._serial

    async def _scan_phase(self) -> SoftApNetwork:
        assert self._scanner is not None
        self._emit(
            OnboardEventType.SCANNING,
            OnboardPhase.SCAN,
            serial=self._serial,
            timeout=self._find_timeout,
        )
        deadline = time.monotonic() + self._find_timeout
        completed = 0
        saw_networks = False
        last_error: str | None = None
        while True:
            try:
                networks = await self._scanner.scan(
                    min_rssi=self._min_rssi, include_non_lifx=self._include_non_lifx
                )
            except Exception as error:
                last_error = _name(error)
                _LOGGER.warning(
                    "scan on %s failed: %s", self._scanner.interface, last_error
                )
            else:
                completed += 1
                saw_networks = saw_networks or bool(networks)
                for network in networks:
                    if self._matches(network):
                        self._emit(
                            OnboardEventType.DISCOVERED,
                            OnboardPhase.SCAN,
                            serial=network.serial,
                            ssid=network.ssid,
                            networks=tuple(networks),
                        )
                        return network
            if time.monotonic() >= deadline:
                break
            await asyncio.sleep(self._find_poll)
        wanted = f"for {self._serial}" if self._serial is not None else "at all"
        message = f"No LIFX SoftAP {wanted} found within {self._find_timeout}s"
        if completed and not saw_networks:
            message = f"{message}. {_MACOS_HINT}"
        if last_error is not None:
            message = f"{message} (the last scan raised {last_error})"
        raise SoftApNotFoundError(message) from None

    async def _join_phase(self) -> None:
        network = self._softap_network
        assert network is not None
        self._emit(
            OnboardEventType.JOINING,
            OnboardPhase.JOIN,
            serial=self._serial,
            ssid=network.ssid,
            timeout=self._find_timeout,
        )
        started = time.monotonic()
        deadline = started + self._find_timeout
        while True:
            try:
                await self._joiner.join(network)
            except Exception as error:
                _LOGGER.warning("joining %r failed: %s", network.ssid, _name(error))
                if time.monotonic() >= deadline:
                    raise SoftApJoinError(
                        f"Could not join {network.ssid!r} within "
                        f"{self._find_timeout}s: {_name(error)}"
                    ) from None
                await asyncio.sleep(self._find_poll)
            else:
                break
        self._emit(
            OnboardEventType.JOINED,
            OnboardPhase.JOIN,
            serial=self._serial,
            ssid=network.ssid,
            took=time.monotonic() - started,
        )

    async def _wait_phase(self) -> None:
        address = self._softap.address
        self._emit(
            OnboardEventType.WAITING_FOR_SOFTAP,
            OnboardPhase.WAIT,
            serial=self._serial,
            ssid=self._softap_ssid,
            address=address,
            timeout=self._wait_timeout,
        )
        started = time.monotonic()
        deadline = started + self._wait_timeout
        last_error: SoftApUnreachableError | None = None
        while True:
            current = await self._current_ssid()
            if current is not None and current != self._softap_ssid:
                raise HostLeftSoftApError(
                    f"Host left {self._softap_ssid!r} for {current!r} while waiting "
                    f"for the SoftAP at {address}"
                )
            attempt = time.monotonic()
            try:
                await self._softap.probe(timeout=self._wait_poll)
            except SoftApUnreachableError as error:
                last_error = error
            else:
                break
            if time.monotonic() >= deadline:
                raise SoftApWaitTimeoutError(
                    f"SoftAP at {address} did not accept a connection within "
                    f"{self._wait_timeout}s"
                ) from last_error
            await asyncio.sleep(
                max(0.0, self._wait_poll - (time.monotonic() - attempt))
            )
        self._emit(
            OnboardEventType.ON_SOFTAP,
            OnboardPhase.WAIT,
            serial=self._serial,
            ssid=self._softap_ssid,
            address=address,
            took=time.monotonic() - started,
        )

    async def _dial_phase(self) -> None:
        address = self._softap.address
        self._emit(
            OnboardEventType.DIALING,
            OnboardPhase.DIAL,
            serial=self._serial,
            address=address,
            timeout=self._dial_timeout,
        )
        try:
            await asyncio.wait_for(self._softap.open(), self._dial_timeout)
        except asyncio.TimeoutError as error:
            raise SoftApDialError(
                f"Dialing the SoftAP at {address} took longer than "
                f"{self._dial_timeout}s"
            ) from error

    async def _configure_phase(self) -> None:
        assert self._serial is not None
        try:
            await self._softap.send_access_point(self._serial, self._network)
        finally:
            await self._softap.close()
        self._emit(
            OnboardEventType.CONFIGURED,
            OnboardPhase.CONFIGURE,
            serial=self._serial,
            ssid=self._network.ssid,
            address=self._softap.address,
        )

    # ---- rejoin and recovery ---------------------------------------------

    def _rejoin_targets(self) -> list[_RejoinTarget]:
        """The networks to return the host to, best first, without duplicates."""
        home = self._network
        candidates: list[_RejoinTarget] = []
        if self._rejoin_ssid is not None:
            password = self._rejoin_password
            if self._rejoin_ssid == home.ssid and not password:
                password = home.password
            candidates.append(
                _RejoinTarget(self._rejoin_ssid, password, auto_join=False)
            )
        if self._original_ssid is not None and self._original_ssid != home.ssid:
            candidates.append(_RejoinTarget(self._original_ssid, "", auto_join=True))
        candidates.append(_RejoinTarget(home.ssid, home.password, auto_join=False))
        targets: list[_RejoinTarget] = []
        for candidate in candidates:
            if all(candidate.ssid != target.ssid for target in targets):
                targets.append(candidate)
        return targets

    async def _leave_softap(self) -> None:
        """Forget the SoftAP and drop the association so auto-join moves on."""
        ssid = self._softap_ssid
        if self._forgetter is not None:
            try:
                await self._forgetter.forget(ssid)
            except Exception as error:
                _LOGGER.warning("forgetting %r failed: %s", ssid, _name(error))
        if self._disassociator is not None:
            try:
                current = await self._current_ssid()
                if current is None or current == ssid:
                    await self._disassociator.disassociate()
            except Exception as error:
                _LOGGER.warning("leaving %r failed: %s", ssid, _name(error))

    async def _rejoin_phase(self) -> str:
        targets = self._rejoin_targets()
        await self._leave_softap()
        started = time.monotonic()
        for target in targets:
            self._emit(
                OnboardEventType.REJOINING,
                OnboardPhase.REJOIN,
                serial=self._serial,
                ssid=target.ssid,
                timeout=self._rejoin_timeout,
            )
            try:
                landed = await self._rejoin_target(target)
            except Exception as error:
                _LOGGER.warning("could not rejoin %r: %s", target.ssid, _name(error))
                continue
            self._emit(
                OnboardEventType.REJOINED,
                OnboardPhase.REJOIN,
                serial=self._serial,
                ssid=landed,
                took=time.monotonic() - started,
            )
            return landed
        raise HostRejoinError(
            "Could not return the host to any of "
            + ", ".join(repr(target.ssid) for target in targets)
        )

    async def _rejoin_target(self, target: _RejoinTarget) -> str:
        """Return the host to ``target``, returning the SSID it landed on.

        Raises:
            HostRejoinError: If the rejoin budget runs out.
        """
        deadline = time.monotonic() + self._rejoin_timeout
        if target.auto_join:
            landed = await self._await_auto_join(deadline)
            if landed is not None:
                return landed
        while True:
            try:
                await self._joiner.rejoin(target.ssid, target.password)
            except Exception as error:
                # The Joiner was handed the password, so its message and
                # traceback are never logged or chained: only its type is.
                if await self._current_ssid() == target.ssid:
                    _LOGGER.debug("already on %r despite %s", target.ssid, _name(error))
                    return target.ssid
                _LOGGER.warning("rejoining %r failed: %s", target.ssid, _name(error))
                if time.monotonic() >= deadline:
                    raise HostRejoinError(
                        f"Could not rejoin {target.ssid!r} within "
                        f"{self._rejoin_timeout}s: {_name(error)}"
                    ) from None
                await asyncio.sleep(self._rejoin_poll)
            else:
                return target.ssid

    async def _await_auto_join(self, deadline: float) -> str | None:
        """Give the OS auto-join a chance before forcing a join.

        The ``auto_join_wait`` budget starts only once the host has left the
        SoftAP, bounded overall by ``deadline``. Whatever known network the OS
        picks is accepted and returned; ``None`` means auto-join did not land.
        """
        # The original network is only ever known through a reporter.
        assert self._reporter is not None
        softap_ssid = self._softap_ssid
        auto_join_deadline: float | None = None
        while True:
            current = await self._reporter.current_ssid()
            if current is not None and current != softap_ssid:
                _LOGGER.debug("auto-join landed on %r", current)
                return current
            now = time.monotonic()
            if current is None and auto_join_deadline is None:
                auto_join_deadline = now + self._auto_join_wait
            if now >= deadline or (
                auto_join_deadline is not None and now >= auto_join_deadline
            ):
                return None
            await asyncio.sleep(self._rejoin_poll)

    async def _recover_host(self) -> None:
        """Return the host to a network after a failure, best effort."""
        targets = self._rejoin_targets()
        budget = self._rejoin_timeout * len(targets) + self._auto_join_wait
        _LOGGER.info("recovering host network within %.1fs", budget)
        try:
            await asyncio.wait_for(self._recover_targets(targets), budget)
        except asyncio.TimeoutError:
            _LOGGER.warning("host recovery gave up after %.1fs", budget)

    async def _recover_targets(self, targets: list[_RejoinTarget]) -> None:
        await self._leave_softap()
        for target in targets:
            try:
                self._host_network = await self._rejoin_target(target)
            except Exception as error:
                _LOGGER.warning(
                    "recovery could not rejoin %r: %s", target.ssid, _name(error)
                )
                continue
            _LOGGER.info("host recovered to %r", self._host_network)
            return
        _LOGGER.warning("host recovery exhausted every target")

    # ---- verification (ticket #331) -------------------------------------

    async def _verify_phase(self) -> bool:
        """Confirm the device on the LAN; replaced by ticket #331."""
        if not self._verify:
            return False
        raise NotImplementedError("LAN verification lands in ticket #331")


async def onboard(
    network: HomeNetwork,
    *,
    scanner: Scanner | None,
    joiner: Joiner,
    target: str | Serial | None = None,
    softap: SoftApClient | None = None,
    verify: DeviceWatcher | bool = True,
    on_event: EventCallback | None = None,
    events: OnboardEventQueue | None = None,
    rejoin_ssid: str | None = None,
    rejoin_password: str = "",
    min_rssi: float = 0.0,
    include_non_lifx: bool = False,
    legacy_tls: bool = False,
    softap_address: str = SOFTAP_ADDRESS,
    softap_port: int = SOFTAP_PORT,
    find_timeout: float = FIND_TIMEOUT,
    find_poll: float = FIND_POLL,
    wait_timeout: float = WAIT_TIMEOUT,
    wait_poll: float = WAIT_POLL,
    dial_timeout: float = DIAL_TIMEOUT,
    rejoin_timeout: float = REJOIN_TIMEOUT,
    rejoin_poll: float = REJOIN_POLL,
    auto_join_wait: float = AUTO_JOIN_WAIT,
    verify_timeout: float = VERIFY_TIMEOUT,
    verify_poll: float = VERIFY_POLL,
) -> Result:
    """Onboard one device from its SoftAP onto ``network``.

    The sequence is scan, join, wait, dial, configure, rejoin and verify.
    Progress is reported through ``on_event`` (called synchronously) and
    ``events`` (a bounded queue that never blocks the sequence).

    Args:
        network: The home network to hand the device.
        scanner: Lists visible networks; may be ``None`` only when ``target``
            is a full SoftAP name, which skips the scan.
        joiner: Joins the host to networks. Its optional capabilities
            (``CurrentNetworkReporter``, ``NetworkForgetter``,
            ``Disassociator``) are used when present and win over the
            scanner's.
        target: A SoftAP name such as ``"LIFX Candle Color 8274eb"``, a
            serial, its six-hex suffix, or ``None`` for the first LIFX SoftAP
            seen.
        softap: The control channel; a ``SoftApConnection`` is built from
            ``softap_address``, ``softap_port``, ``dial_timeout`` and
            ``legacy_tls`` when omitted.
        verify: A running ``DeviceWatcher`` to verify through, ``True`` to
            open one for the verification window, ``False`` to skip it.
        on_event: Called with each ``OnboardEvent``; exceptions are logged.
        events: A queue every event is put on.
        rejoin_ssid: A network to return the host to in preference to the
            one it was on; ``rejoin_password`` defaults to the home password
            when this is the home SSID.
        rejoin_password: The password for ``rejoin_ssid``.
        min_rssi: Passed to the scanner.
        include_non_lifx: Passed to the scanner.
        legacy_tls: Pin TLS 1.0 for pre-2020 firmware.
        softap_address: Where the device's SoftAP listens.
        softap_port: The port it listens on.
        find_timeout: Budget for the scan, and separately for the join.
        find_poll: Interval between scan attempts and between join attempts.
        wait_timeout: Budget for the SoftAP to accept a probe.
        wait_poll: Interval between probes; each probe is bounded by it.
        dial_timeout: Budget for the TLS dial.
        rejoin_timeout: Budget per rejoin target.
        rejoin_poll: Interval between rejoin attempts and host network polls.
        auto_join_wait: How long the OS auto-join gets once the host has
            left the SoftAP.
        verify_timeout: Budget for the device to appear on the LAN.
        verify_poll: Discovery sweep interval while verifying.

    Returns:
        The ``Result`` of a successful run.

    Raises:
        InvalidSoftApTargetError: If ``target`` is none of the accepted forms.
        ValueError: If ``scanner`` is ``None`` and a scan is needed.
        LifxOnboardError: The typed error of the phase that failed; its
            ``result`` carries the same fields a success would.
        asyncio.CancelledError: After host recovery, when cancelled.
    """
    if softap is None:
        softap = SoftApConnection(
            softap_address,
            softap_port,
            dial_timeout=dial_timeout,
            legacy_tls=legacy_tls,
        )
    run = _Run(
        network,
        scanner=scanner,
        joiner=joiner,
        softap=softap,
        verify=verify,
        on_event=on_event,
        events=events,
        rejoin_ssid=rejoin_ssid,
        rejoin_password=rejoin_password,
        min_rssi=min_rssi,
        include_non_lifx=include_non_lifx,
        find_timeout=find_timeout,
        find_poll=find_poll,
        wait_timeout=wait_timeout,
        wait_poll=wait_poll,
        dial_timeout=dial_timeout,
        rejoin_timeout=rejoin_timeout,
        rejoin_poll=rejoin_poll,
        auto_join_wait=auto_join_wait,
        verify_timeout=verify_timeout,
        verify_poll=verify_poll,
    )
    return await run.run(target)
