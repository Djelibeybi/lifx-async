"""Bulk onboarding: scan repeatedly and onboard every new SoftAP, one at a time.

``bulk_onboard()`` is the single-device sequence in a loop. Each scan round
that shows a LIFX SoftAP not yet attempted runs join, wait, dial, configure
and rejoin for it exactly as ``onboard()`` does, with host recovery on
failure, and never two at once: the host has one WiFi interface. What differs
is verification. A configured device is handed to a background task that
waits for it on the LAN through one ``DeviceWatcher`` shared by the whole run,
so the loop is back to scanning while the slowest device reboots, and
results are yielded in the order they complete.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Iterable
from dataclasses import replace
from typing import Any

from lifx.onboard.errors import (
    InvalidSoftApTargetError,
    OnboardPhase,
    SoftApNotFoundError,
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
    EventCallback,
    _name,
    _Run,
)
from lifx.onboard.models import HomeNetwork, SoftApNetwork
from lifx.onboard.protocols import Joiner, Scanner
from lifx.onboard.result import Result
from lifx.onboard.serials import parse_serial
from lifx.onboard.softap import (
    SOFTAP_ADDRESS,
    SOFTAP_PORT,
    SoftApClient,
    SoftApConnection,
)
from lifx.onboard.verify import LanVerification, VerificationWatcher
from lifx.protocol.models import Serial
from lifx.watcher import DeviceWatcher

__all__ = ["SCAN_INTERVAL", "bulk_onboard"]

_LOGGER = logging.getLogger(__name__)

#: Seconds between scan rounds that found nothing new.
SCAN_INTERVAL = 2.0


def _parse_targets(targets: Iterable[Serial | str]) -> set[Serial]:
    wanted: set[Serial] = set()
    for target in targets:
        try:
            wanted.add(parse_serial(target))
        except (ValueError, TypeError) as error:
            raise InvalidSoftApTargetError(
                f"{target!r} is not a LIFX serial or serial suffix"
            ) from error
    return wanted


class _BulkRun:
    """The state one ``bulk_onboard()`` call carries between scan rounds."""

    def __init__(
        self,
        network: HomeNetwork,
        *,
        scanner: Scanner,
        joiner: Joiner,
        targets: Iterable[Serial | str],
        max_devices: int | None,
        scan_interval: float,
        stop_when_idle_for: float | None,
        softap: SoftApClient,
        verify: VerificationWatcher | bool,
        on_event: EventCallback | None,
        events: OnboardEventQueue | None,
        min_rssi: float,
        include_non_lifx: bool,
        verify_timeout: float,
        verify_poll: float,
        run_kwargs: dict[str, Any],
    ) -> None:
        self._network = network
        self._scanner = scanner
        self._joiner = joiner
        self._wanted = _parse_targets(targets)
        self._remaining = set(self._wanted)
        self._max_devices = max_devices
        self._scan_interval = scan_interval
        self._stop_when_idle_for = stop_when_idle_for
        self._softap = softap
        self._on_event = on_event
        self._events = events
        self._min_rssi = min_rssi
        self._include_non_lifx = include_non_lifx
        self._verify_timeout = verify_timeout
        self._run_kwargs = run_kwargs

        self._owned_watcher: DeviceWatcher | None = None
        self._watcher: VerificationWatcher | None = None
        if verify is True:
            self._owned_watcher = DeviceWatcher(sweep_interval=verify_poll, mdns=False)
            self._watcher = self._owned_watcher
        elif verify:
            self._watcher = verify
        self._watcher_open = False

        self._started = time.monotonic()
        self._idle_since = self._started
        self._seen: set[Serial] = set()
        self._attempts = 0
        # Creation order, so verifications finishing together yield in order.
        self._pending: list[asyncio.Task[Result]] = []

    # ---- events --------------------------------------------------------------

    def _emit(
        self,
        event_type: OnboardEventType,
        phase: OnboardPhase | None,
        **fields: Any,
    ) -> None:
        event = OnboardEvent(type=event_type, phase=phase, **fields)
        _LOGGER.debug("bulk onboarding %s in phase %s", event_type.value, phase)
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

    # ---- the loop ------------------------------------------------------------

    def _finished(self) -> bool:
        if self._wanted and not self._remaining:
            return True
        if self._max_devices is not None and self._attempts >= self._max_devices:
            return True
        return (
            self._stop_when_idle_for is not None
            and time.monotonic() - self._idle_since >= self._stop_when_idle_for
        )

    def _wants(self, network: SoftApNetwork) -> bool:
        serial = network.serial
        if serial is None or serial in self._seen:
            return False
        return not self._wanted or serial in self._wanted

    async def _scan_round(self) -> SoftApNetwork | None:
        """One scan; the first LIFX SoftAP not yet attempted, if any."""
        try:
            networks = await self._scanner.scan(
                min_rssi=self._min_rssi, include_non_lifx=self._include_non_lifx
            )
        except Exception as error:
            _LOGGER.warning(
                "scan on %s failed: %s", self._scanner.interface, _name(error)
            )
            return None
        for network in networks:
            if self._wants(network):
                self._emit(
                    OnboardEventType.DISCOVERED,
                    OnboardPhase.SCAN,
                    serial=network.serial,
                    ssid=network.ssid,
                    networks=tuple(networks),
                )
                return network
        return None

    def _completed(self) -> list[Result]:
        """Pop the results of every verification that has finished."""
        done = [task for task in self._pending if task.done()]
        self._pending = [task for task in self._pending if not task.done()]
        return [task.result() for task in done]

    async def _idle(self) -> None:
        """Sleep ``scan_interval``, or less if a verification completes first."""
        if self._pending:
            await asyncio.wait(
                self._pending,
                timeout=self._scan_interval,
                return_when=asyncio.FIRST_COMPLETED,
            )
        else:
            await asyncio.sleep(self._scan_interval)

    async def _ensure_watcher(self) -> None:
        if self._owned_watcher is not None and not self._watcher_open:
            await self._owned_watcher.__aenter__()
            self._watcher_open = True

    async def _attempt(self, network: SoftApNetwork) -> Result | None:
        """Onboard ``network``; the final Result now, or ``None`` if verifying."""
        serial = network.serial
        assert serial is not None
        self._seen.add(serial)
        self._remaining.discard(serial)
        self._attempts += 1
        verification: LanVerification | None = None

        def on_configured() -> None:
            nonlocal verification
            if self._watcher is not None:
                verification = LanVerification(
                    self._watcher, serial, softap_address=self._softap.address
                )

        await self._ensure_watcher()
        run = _Run(
            self._network,
            scanner=self._scanner,
            joiner=self._joiner,
            softap=self._softap,
            verify=False,
            on_event=self._on_event,
            events=self._events,
            min_rssi=self._min_rssi,
            include_non_lifx=self._include_non_lifx,
            verify_timeout=self._verify_timeout,
            verify_poll=VERIFY_POLL,
            on_configured=on_configured,
            **self._run_kwargs,
        )
        started = time.monotonic()
        try:
            result = await run.run_network(network)
        except BaseException:
            if verification is not None:
                verification.close()
            raise
        if verification is None:
            return result
        if result.error is not None:
            # Configured but the host never got home: the device may still
            # appear, but the run is a failure and is reported as one.
            verification.close()
            return result
        self._emit(
            OnboardEventType.VERIFYING,
            OnboardPhase.VERIFY,
            serial=serial,
            timeout=self._verify_timeout,
        )
        task = asyncio.create_task(self._verify(result, verification, started))
        self._pending.append(task)
        return None

    async def _verify(
        self, result: Result, verification: LanVerification, started: float
    ) -> Result:
        serial = result.serial
        try:
            sighting = await verification.wait(self._verify_timeout)
        except VerifyTimeoutError as error:
            failed = replace(
                result,
                verified=False,
                took=time.monotonic() - started,
                phase=OnboardPhase.VERIFY,
                error=error,
            )
            error.result = failed
            self._emit(
                OnboardEventType.FAILED, OnboardPhase.VERIFY, serial=serial, error=error
            )
            return failed
        self._emit(
            OnboardEventType.VERIFIED,
            OnboardPhase.VERIFY,
            serial=serial,
            address=sighting.address,
            took=sighting.took,
        )
        return replace(result, verified=True, took=time.monotonic() - started)

    def _not_found(self, serial: Serial) -> Result:
        error = SoftApNotFoundError(f"No LIFX SoftAP for {serial} was seen")
        result = Result(
            serial=serial,
            verified=False,
            took=time.monotonic() - self._started,
            phase=OnboardPhase.SCAN,
            error=error,
        )
        error.result = result
        self._emit(
            OnboardEventType.FAILED, OnboardPhase.SCAN, serial=serial, error=error
        )
        return result

    async def results(self) -> AsyncIterator[Result]:
        try:
            while True:
                self._emit(
                    OnboardEventType.SCANNING,
                    OnboardPhase.SCAN,
                    timeout=self._stop_when_idle_for,
                )
                network: SoftApNetwork | None = None
                while network is None and not self._finished():
                    for result in self._completed():
                        yield result
                    network = await self._scan_round()
                    if network is None:
                        await self._idle()
                if network is None:
                    break
                result = await self._attempt(network)
                self._idle_since = time.monotonic()
                for completed in self._completed():
                    yield completed
                if result is not None:
                    yield result
            while self._pending:
                await asyncio.wait(self._pending, return_when=asyncio.FIRST_COMPLETED)
                for result in self._completed():
                    yield result
            for serial in sorted(self._remaining, key=str):
                yield self._not_found(serial)
        finally:
            await self._close()

    async def _close(self) -> None:
        for task in self._pending:
            task.cancel()
        if self._pending:
            await asyncio.wait(self._pending)
            self._pending.clear()
        if self._watcher_open:
            assert self._owned_watcher is not None
            self._watcher_open = False
            await self._owned_watcher.__aexit__(None, None, None)


async def bulk_onboard(
    network: HomeNetwork,
    *,
    scanner: Scanner,
    joiner: Joiner,
    targets: Iterable[Serial | str] = (),
    max_devices: int | None = None,
    scan_interval: float = SCAN_INTERVAL,
    stop_when_idle_for: float | None = None,
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
) -> AsyncIterator[Result]:
    """Onboard every new LIFX SoftAP the scanner sees, one device at a time.

    Scans every ``scan_interval`` seconds. Each round that shows a LIFX SoftAP
    not yet attempted (and, when ``targets`` is given, on the allow-list)
    runs join, wait, dial, configure and rejoin for it exactly as
    ``onboard()`` does, with host recovery on failure, then scans again. A
    serial is attempted once however often it recurs. A failed attempt yields
    a ``Result`` with ``phase`` and ``error`` set; the loop goes on.

    Verification is interleaved. With ``verify`` set, one watcher serves the
    whole run: a caller's ``DeviceWatcher`` is used as is and left running,
    while ``True`` opens a library-owned watcher (``sweep_interval`` of
    ``verify_poll``, UDP only) before the first attempt and closes it when
    the run ends, also on cancellation. As soon as a device is configured it
    starts listening for that serial on the LAN, and once the host has
    rejoined its network the wait of up to ``verify_timeout`` runs in the
    background while the loop scans for the next device. Results are
    therefore yielded in completion order: a device verified while a later
    one was being configured is yielded as soon as the generator is resumed,
    and every pending verification is drained after the loop ends. With
    ``verify=False`` each ``Result`` is yielded right after its rejoin.

    The loop ends when every allow-listed target has been attempted, when
    ``max_devices`` attempts (successful or not) have been made, when
    ``stop_when_idle_for`` seconds of scanning have passed without a new
    serial (the clock restarts when a device is attempted and again when
    scanning resumes after it, so time spent onboarding never counts as
    idle, while a scan that shows nothing new does not reset it), or when
    the consumer's task is cancelled,
    in which case host recovery runs for the device in flight, pending
    verifications are cancelled, the owned watcher is closed and the
    ``CancelledError`` propagates. Allow-listed targets never seen are
    yielded last as ``SCAN``-phase ``SoftApNotFoundError`` results. Without
    ``targets``, ``max_devices`` or ``stop_when_idle_for`` the loop runs
    until cancelled.

    Events reach ``on_event`` and ``events`` as they do from ``onboard()``.
    ``SCANNING`` is emitted when scanning starts and again after each
    attempt, not on every round; ``DISCOVERED`` once per device attempted,
    carrying every network that round's scan returned; the per-device
    events are those of ``onboard()``.

    Early exit: an ``async for`` that ``break``s leaves the generator open
    until it is garbage collected; wrap it in ``contextlib.aclosing()`` to
    close the owned watcher and cancel pending verifications at once.

    Args:
        network: The home network to hand every device.
        scanner: Lists visible networks; required, since every device is
            found by scanning.
        joiner: Joins the host to networks, as for ``onboard()``.
        targets: Serials or six-hex suffixes to onboard; every other LIFX
            SoftAP is ignored. Empty means every LIFX SoftAP seen.
        max_devices: Stop after this many attempts.
        scan_interval: Seconds between scan rounds that found nothing new.
        stop_when_idle_for: Stop once this many seconds of scanning have
            passed without a new serial being seen.
        softap: The control channel, reused for every device; a
            ``SoftApConnection`` is built when omitted.
        verify: A running ``DeviceWatcher`` to verify through, ``True`` to
            open one for the run, ``False`` to skip verification.
        on_event: Called with each ``OnboardEvent``; exceptions are logged.
        events: A queue every event is put on.
        rejoin_ssid: As for ``onboard()``.
        rejoin_password: As for ``onboard()``.
        min_rssi: Passed to the scanner.
        include_non_lifx: Passed to the scanner.
        legacy_tls: Pin TLS 1.0 for pre-2020 firmware.
        softap_address: Where each device's SoftAP listens.
        softap_port: The port it listens on.
        find_timeout: Budget for each join.
        find_poll: Interval between join attempts.
        wait_timeout: Budget for the SoftAP to accept a probe.
        wait_poll: Interval between probes; each probe is bounded by it.
        dial_timeout: Budget for the TLS dial.
        rejoin_timeout: Budget per rejoin target.
        rejoin_poll: Interval between rejoin attempts and host network polls.
        auto_join_wait: How long the OS auto-join gets once the host has
            left the SoftAP.
        verify_timeout: Budget for each device to appear on the LAN.
        verify_poll: Discovery sweep interval of the owned watcher.

    Yields:
        One ``Result`` per attempted device, in completion order, then one
        per allow-listed target never seen.

    Raises:
        InvalidSoftApTargetError: If a target is neither a serial nor a suffix.
        asyncio.CancelledError: After host recovery, when cancelled.
    """
    if softap is None:
        softap = SoftApConnection(
            softap_address,
            softap_port,
            dial_timeout=dial_timeout,
            legacy_tls=legacy_tls,
        )
    run = _BulkRun(
        network,
        scanner=scanner,
        joiner=joiner,
        targets=targets,
        max_devices=max_devices,
        scan_interval=scan_interval,
        stop_when_idle_for=stop_when_idle_for,
        softap=softap,
        verify=verify,
        on_event=on_event,
        events=events,
        min_rssi=min_rssi,
        include_non_lifx=include_non_lifx,
        verify_timeout=verify_timeout,
        verify_poll=verify_poll,
        run_kwargs={
            "rejoin_ssid": rejoin_ssid,
            "rejoin_password": rejoin_password,
            "find_timeout": find_timeout,
            "find_poll": find_poll,
            "wait_timeout": wait_timeout,
            "wait_poll": wait_poll,
            "dial_timeout": dial_timeout,
            "rejoin_timeout": rejoin_timeout,
            "rejoin_poll": rejoin_poll,
            "auto_join_wait": auto_join_wait,
        },
    )
    async for result in run.results():
        yield result
