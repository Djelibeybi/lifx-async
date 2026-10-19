"""The single-device onboarding sequence.

``onboard()`` takes a device from its SoftAP onto the home network: resolve
the target, scan, join, wait for the control socket, dial, configure, return
the host to its own network and verify the device on the LAN.
Each phase emits events, every failure is a typed ``LifxOnboardError`` whose
``result`` describes the run, and from the first attempt to join the SoftAP
until the host has rejoined its own network, any failure or cancellation runs
host recovery so the machine is never left on the device's network.

The timing defaults are unchanged from the reference tool they were tuned
in, on hardware. The password is never logged; SSIDs and phases are.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, TypeVar

from lifx.onboard._aio import BoundedTimeoutError, bounded
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
    _name,
)
from lifx.onboard.events import (
    EventCallback,
    OnboardEventQueue,
    OnboardEventType,
    _EventSink,
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
from lifx.onboard.serials import parse_serial
from lifx.onboard.softap import (
    SOFTAP_ADDRESS,
    SOFTAP_PORT,
    SoftApClient,
    SoftApConnection,
)
from lifx.onboard.verify import LanVerification
from lifx.protocol.models import _SOFTAP_PREFIX, Serial
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


@dataclass(frozen=True)
class _RejoinTarget:
    """One network the host may be returned to."""

    ssid: str
    password: str = field(repr=False)
    auto_join: bool = False


def _default_softap(
    address: str, port: int, *, dial_timeout: float, legacy_tls: bool
) -> SoftApConnection:
    """The control channel both entry points build when the caller gives none."""
    return SoftApConnection(
        address, port, dial_timeout=dial_timeout, legacy_tls=legacy_tls
    )


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
        on_configured: Callable[[], None] | None = None,
    ) -> None:
        self._network = network
        self._scanner = scanner
        self._joiner = joiner
        self._softap = softap
        self._verify = verify
        self._sink = _EventSink(on_event, events, logger=_LOGGER, label="onboarding")
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
        self._on_configured = on_configured

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

    def _elapsed(self) -> float:
        return time.monotonic() - self._started

    async def _current_ssid(
        self, phase: OnboardPhase | None, *, timeout: float | None = None
    ) -> str | None:
        """Ask the reporter which network the host is on; ``None`` is unknown.

        Every poll of the reporter goes through here, bounded by ``timeout``
        (the remaining budget of the step that asks) or ``rejoin_timeout``, so
        a stalled backend cannot hang a phase. A reporter backend may put the
        password into an error message, so a failing poll is logged by type
        only, with the phase it happened in (``None`` before the first
        phase), and reads as unknown.
        """
        if self._reporter is None:
            return None
        if timeout is None:
            timeout = self._rejoin_timeout
        failed: str | None = None
        try:
            return await bounded(self._reporter.current_ssid(), timeout)
        except Exception as error:
            failed = _name(error)
        _LOGGER.warning(
            "current network unknown %s: %s",
            "before onboarding" if phase is None else f"during {phase.value}",
            failed,
        )
        return None

    @property
    def _softap_ssid(self) -> str:
        assert self._softap_network is not None
        return self._softap_network.ssid

    # ---- the sequence ---------------------------------------------------

    def _resolve_target(self, target: str | Serial | None) -> None:
        """Set the serial and, for a full SoftAP name, the network to join."""
        if isinstance(target, str) and target.startswith(_SOFTAP_PREFIX):
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

    async def _record_original_network(self) -> None:
        """Remember the host's own network, if a reporter can name it."""
        original = await self._current_ssid(None)
        if original is not None and not _is_softap_name(original):
            self._original_ssid = original
        _LOGGER.debug("onboarding starts on host network %r", self._original_ssid)

    async def run(self, target: str | Serial | None) -> Result:
        self._resolve_target(target)
        await self._record_original_network()
        return await self._execute()

    async def run_network(self, network: SoftApNetwork) -> Result:
        """Join, wait, dial, configure and rejoin for an already-scanned SoftAP.

        Bulk mode's entry point: the scan and verification phases belong to
        the bulk loop, so this skips the first and the run must have been
        built with ``verify=False`` to skip the second. Unlike :meth:`run` it
        returns the failing ``Result`` instead of raising the onboarding
        error, after host recovery has run; cancellation still propagates.
        """
        assert network.serial is not None
        self._softap_network = network
        self._serial = network.serial
        await self._record_original_network()
        try:
            return await self._execute()
        except LifxOnboardError as error:
            result = error.result
            assert isinstance(result, Result)
            return result

    async def _execute(self) -> Result:
        join_started = False
        rejoined = False
        verified = False
        # Nothing is awaited inside the handler: an exception raised while
        # recovering would otherwise chain the failure as its __context__.
        failure: BaseException | None = None
        try:
            if self._softap_network is None:
                self._softap_network = await self._scan_phase()
                self._serial = self._softap_network.serial
            # A backend can change the host's association and then keep
            # waiting (DHCP, a subprocess), so recovery is owed from the
            # moment the first join attempt starts, not once join() returns.
            join_started = True
            await self._join_phase()
            await self._wait_phase()
            await self._dial_phase()
            await self._configure_phase()
            self._host_network = await self._rejoin_phase()
            rejoined = True
            verified = await self._verify_phase()
        except BaseException as error:
            failure = error
        if failure is None:
            return self._result(verified=verified)
        cancellation = None
        # Once the rejoin has succeeded the host is home; a verify failure or
        # a cancellation during verification leaves nothing to recover.
        if join_started and not rejoined:
            cancellation = await _await_shielded(self._recover_host())
        if isinstance(failure, LifxOnboardError):
            failure.result = self._result(phase=failure.phase, error=failure)
            self._sink.emit(
                OnboardEventType.FAILED,
                failure.phase,
                serial=self._serial,
                error=failure,
            )
        if cancellation is not None and not isinstance(failure, asyncio.CancelledError):
            _LOGGER.info("cancelled while recovering from %s", _name(failure))
            raise cancellation from None
        raise failure

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
        self._sink.emit(
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
            remaining = max(deadline - time.monotonic(), 0.0)
            try:
                networks = await bounded(
                    self._scanner.scan(
                        min_rssi=self._min_rssi,
                        include_non_lifx=self._include_non_lifx,
                    ),
                    remaining,
                )
            except BoundedTimeoutError:
                last_error = "the last scan did not return in time"
                _LOGGER.warning("scan on %s did not return", self._scanner.interface)
                break
            except Exception as error:
                last_error = f"the last scan raised {_name(error)}"
                _LOGGER.warning(
                    "scan on %s failed: %s", self._scanner.interface, _name(error)
                )
            else:
                completed += 1
                saw_networks = saw_networks or bool(networks)
                for network in networks:
                    if self._matches(network):
                        self._sink.emit(
                            OnboardEventType.DISCOVERED,
                            OnboardPhase.SCAN,
                            serial=network.serial,
                            ssid=network.ssid,
                            networks=tuple(networks),
                        )
                        return network
            if time.monotonic() >= deadline:
                break
            await asyncio.sleep(
                min(self._find_poll, max(deadline - time.monotonic(), 0.0))
            )
        wanted = f"for {self._serial}" if self._serial is not None else "at all"
        message = f"No LIFX SoftAP {wanted} found within {self._find_timeout}s"
        if completed and not saw_networks:
            message = f"{message}. {_MACOS_HINT}"
        if last_error is not None:
            message = f"{message} ({last_error})"
        raise SoftApNotFoundError(message) from None

    async def _join_phase(self) -> None:
        network = self._softap_network
        assert network is not None
        self._sink.emit(
            OnboardEventType.JOINING,
            OnboardPhase.JOIN,
            serial=self._serial,
            ssid=network.ssid,
            timeout=self._find_timeout,
        )
        started = time.monotonic()
        deadline = started + self._find_timeout
        while True:
            # Each attempt is bounded by what is left of find_timeout: a
            # backend that associates and then stalls must fail the phase,
            # which starts host recovery, rather than wait to be cancelled.
            remaining = max(deadline - time.monotonic(), 0.0)
            failed: str | None = None
            try:
                await bounded(self._joiner.join(network), remaining)
            except BoundedTimeoutError:
                raise SoftApJoinError(
                    f"Could not join {network.ssid!r} within "
                    f"{self._find_timeout}s: join() did not return in time"
                ) from None
            except Exception as error:
                failed = _name(error)
            if failed is None:
                break
            _LOGGER.warning("joining %r failed: %s", network.ssid, failed)
            if time.monotonic() >= deadline:
                raise SoftApJoinError(
                    f"Could not join {network.ssid!r} within "
                    f"{self._find_timeout}s: {failed}"
                )
            await asyncio.sleep(
                min(self._find_poll, max(deadline - time.monotonic(), 0.0))
            )
        self._sink.emit(
            OnboardEventType.JOINED,
            OnboardPhase.JOIN,
            serial=self._serial,
            ssid=network.ssid,
            took=time.monotonic() - started,
        )

    async def _wait_phase(self) -> None:
        address = self._softap.address
        self._sink.emit(
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
        timed_out = SoftApWaitTimeoutError(
            f"SoftAP at {address} did not accept a connection within "
            f"{self._wait_timeout}s"
        )
        while True:
            # The reporter poll and the probe both draw on wait_timeout, and
            # a probe that only succeeds once the budget is gone counts for
            # nothing: the phase ends where its deadline says.
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise timed_out from last_error
            current = await self._current_ssid(OnboardPhase.WAIT, timeout=remaining)
            if current is not None and current != self._softap_ssid:
                raise HostLeftSoftApError(
                    f"Host left {self._softap_ssid!r} for {current!r} while waiting "
                    f"for the SoftAP at {address}"
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise timed_out from last_error
            attempt = time.monotonic()
            try:
                await self._softap.probe(timeout=min(self._wait_poll, remaining))
            except SoftApUnreachableError as error:
                last_error = error
            else:
                if time.monotonic() >= deadline:
                    raise timed_out from last_error
                break
            # The sleep is capped by the deadline; the next iteration's budget
            # check ends the phase.
            await asyncio.sleep(
                min(
                    max(0.0, self._wait_poll - (time.monotonic() - attempt)),
                    max(0.0, deadline - time.monotonic()),
                )
            )
        self._sink.emit(
            OnboardEventType.ON_SOFTAP,
            OnboardPhase.WAIT,
            serial=self._serial,
            ssid=self._softap_ssid,
            address=address,
            took=time.monotonic() - started,
        )

    async def _dial_phase(self) -> None:
        address = self._softap.address
        self._sink.emit(
            OnboardEventType.DIALING,
            OnboardPhase.DIAL,
            serial=self._serial,
            address=address,
            timeout=self._dial_timeout,
        )
        try:
            await bounded(self._softap.open(), self._dial_timeout)
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
        if self._on_configured is not None:
            self._on_configured()
        self._sink.emit(
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
        """Forget the SoftAP and drop the association so auto-join moves on.

        The association is dropped only while the host is still on the
        SoftAP. A reporter that names another network, or no network at all
        (the host already left, or the reporter failed) means there is
        nothing to leave; without a reporter the host is assumed still on it.
        Both calls are best effort and bounded by ``rejoin_timeout``, so a
        stalled backend never keeps the rejoin from starting.
        """
        ssid = self._softap_ssid
        if self._forgetter is not None:
            try:
                await bounded(self._forgetter.forget(ssid), self._rejoin_timeout)
            except Exception as error:
                _LOGGER.warning("forgetting %r failed: %s", ssid, _name(error))
        if self._disassociator is None:
            return
        if self._reporter is not None:
            if await self._current_ssid(OnboardPhase.REJOIN) != ssid:
                _LOGGER.debug("not disassociating: host is no longer on %r", ssid)
                return
        try:
            await bounded(self._disassociator.disassociate(), self._rejoin_timeout)
        except Exception as error:
            _LOGGER.warning("leaving %r failed: %s", ssid, _name(error))

    async def _rejoin_phase(self) -> str:
        targets = self._rejoin_targets()
        await self._leave_softap()
        started = time.monotonic()
        for target in targets:
            self._sink.emit(
                OnboardEventType.REJOINING,
                OnboardPhase.REJOIN,
                serial=self._serial,
                ssid=target.ssid,
                timeout=self._rejoin_timeout,
            )
            try:
                landed = await self._rejoin_target(
                    target, auto_join_bound=self._rejoin_timeout
                )
            except Exception as error:
                _LOGGER.warning("could not rejoin %r: %s", target.ssid, _name(error))
                continue
            self._sink.emit(
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

    async def _rejoin_target(
        self, target: _RejoinTarget, *, auto_join_bound: float
    ) -> str:
        """Return the host to ``target``, returning the SSID it landed on.

        For the original network the OS auto-join is awaited first, for at
        most ``auto_join_bound`` seconds in case the host never leaves the
        SoftAP. The forced ``rejoin()`` retries that follow then get exactly
        ``rejoin_timeout``: every ``rejoin()`` call, every reporter poll and
        the sleeps between attempts draw on that one remaining budget, so a
        backend that never returns costs this target's budget and no more
        before the next target is tried.

        Raises:
            HostRejoinError: If the rejoin budget runs out.
        """
        if target.auto_join:
            landed = await self._await_auto_join(time.monotonic() + auto_join_bound)
            if landed is not None:
                return landed
        deadline = time.monotonic() + self._rejoin_timeout
        failed = "auto-join did not land"
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise HostRejoinError(
                    f"Could not rejoin {target.ssid!r} within "
                    f"{self._rejoin_timeout}s: {failed}"
                )
            # The Joiner was handed the password, so its error is never
            # logged, chained or kept alive across an await: only its type is.
            failed = ""
            budget_spent = False
            try:
                await bounded(
                    self._joiner.rejoin(target.ssid, target.password), remaining
                )
            except BoundedTimeoutError:
                failed = "rejoin() did not return in time"
                budget_spent = True
            except Exception as error:
                failed = _name(error)
            if not failed:
                return target.ssid
            if not budget_spent:
                remaining = max(deadline - time.monotonic(), 0.0)
                current = await self._current_ssid(
                    OnboardPhase.REJOIN, timeout=remaining
                )
                if current == target.ssid:
                    _LOGGER.debug("already on %r despite %s", target.ssid, failed)
                    return target.ssid
            _LOGGER.warning("rejoining %r failed: %s", target.ssid, failed)
            if budget_spent:
                raise HostRejoinError(
                    f"Could not rejoin {target.ssid!r} within "
                    f"{self._rejoin_timeout}s: {failed}"
                )
            await asyncio.sleep(
                min(self._rejoin_poll, max(deadline - time.monotonic(), 0.0))
            )

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
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            current = await self._current_ssid(OnboardPhase.REJOIN, timeout=remaining)
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
            await asyncio.sleep(min(self._rejoin_poll, max(deadline - now, 0.0)))

    async def _recover_host(self) -> None:
        """Return the host to a network after a failure, best effort.

        Leaving the SoftAP comes first, each of its calls bounded by
        ``rejoin_timeout`` on its own, so a stalled forget or disassociate
        never eats into the rejoin budget. That budget then allots
        ``rejoin_timeout`` per target plus one ``auto_join_wait``, so the
        auto-join wait is bounded by the latter here and every fallback
        target still receives its attempt.
        """
        targets = self._rejoin_targets()
        await self._leave_softap()
        budget = self._rejoin_timeout * len(targets) + self._auto_join_wait
        _LOGGER.info("recovering host network within %.1fs", budget)
        try:
            await bounded(self._recover_targets(targets), budget)
        except asyncio.TimeoutError:
            _LOGGER.warning("host recovery gave up after %.1fs", budget)

    async def _recover_targets(self, targets: list[_RejoinTarget]) -> None:
        for target in targets:
            try:
                self._host_network = await self._rejoin_target(
                    target, auto_join_bound=self._auto_join_wait
                )
            except Exception as error:
                _LOGGER.warning(
                    "recovery could not rejoin %r: %s", target.ssid, _name(error)
                )
                continue
            _LOGGER.info("host recovered to %r", self._host_network)
            return
        _LOGGER.warning("host recovery exhausted every target")

    # ---- verification ----------------------------------------------------

    async def _verify_phase(self) -> bool:
        """Wait for the device to answer discovery off the SoftAP address.

        ``verify`` is a caller's running watcher, used as is, or ``True`` for
        a library-owned watcher that lives for this phase only. The listener
        is registered before ``VERIFYING`` is emitted and before the owned
        watcher's initial sweep, so a device that is already answering on
        the LAN verifies at once, while whatever a caller's watcher recorded
        before this moment is never consulted.
        """
        if not self._verify:
            return False
        assert self._serial is not None
        if self._verify is True:
            owned = True
            watcher: DeviceWatcher = DeviceWatcher(
                sweep_interval=self._verify_poll, mdns=False
            )
        else:
            owned = False
            watcher = self._verify
        verification = LanVerification(
            watcher, self._serial, softap_address=self._softap.address
        )
        self._sink.emit(
            OnboardEventType.VERIFYING,
            OnboardPhase.VERIFY,
            serial=self._serial,
            timeout=self._verify_timeout,
        )
        sighting = await verification.wait(self._verify_timeout, open_watcher=owned)
        self._sink.emit(
            OnboardEventType.VERIFIED,
            OnboardPhase.VERIFY,
            serial=self._serial,
            address=sighting.address,
            took=sighting.took,
        )
        return True


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
        softap = _default_softap(
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
