"""Device watcher: continuous discovery, change events and liveness.

A :class:`DeviceWatcher` is the long-lived object an integration opens once.
It hands out one device object per serial, keeps those objects current as
devices move, and reports when a device is added, changes or goes silent.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import AsyncGenerator, Callable, Mapping
from contextlib import aclosing
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType, TracebackType
from typing import TYPE_CHECKING, Any

from lifx.api import discover_mdns, discover_udp
from lifx.const import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DISCOVERY_TIMEOUT,
    IDLE_TIMEOUT_MULTIPLIER,
    LIFX_UDP_PORT,
)
from lifx.devices.base import Connectivity
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.network import connection as _connection
from lifx.protocol.models import Serial

if TYPE_CHECKING:
    from typing_extensions import Self

    from lifx.devices.base import Device

_LOGGER = logging.getLogger(__name__)

# Seconds between discovery sweeps.
DEFAULT_SWEEP_INTERVAL = 30.0

# Floor of the default silence threshold, in seconds.
MIN_SILENCE_THRESHOLD = 30.0

# Sweep intervals of silence in the default threshold.
SILENCE_INTERVALS = 5

# Seconds between high-frequency polls (color, power, zones, tiles).
DEFAULT_HIGH_FREQUENCY_INTERVAL = 10.0

# Seconds between low-frequency polls (label, firmware, group, location).
DEFAULT_LOW_FREQUENCY_INTERVAL = 300.0

# Events held for the async iterator before the oldest is dropped.
DEFAULT_MAX_QUEUE_SIZE = 256

_DEFAULT_BROADCAST = "255.255.255.255"

# Names reported in a change set, in the order they are checked.
_TRACKED_FIELDS = (
    "address",
    "label",
    "group",
    "location",
    "host_firmware",
    "wifi_firmware",
)

# Names that exist only once polling has read them. The first reading sets the
# baseline silently; later readings that differ are reported.
_POLLED_FIELDS = ("color", "power", "zones", "tiles")


class DeviceEventType(str, Enum):
    """What happened to a device."""

    ADDED = "added"
    """First seen, or answering again after a ``REMOVED``."""

    UPDATED = "updated"
    """A tracked field changed; see :attr:`DeviceEvent.changes`."""

    REMOVED = "removed"
    """Silent for longer than the silence threshold. The object is kept."""


@dataclass(frozen=True)
class DeviceEvent:
    """One change reported by a :class:`DeviceWatcher`.

    Attributes:
        type: What happened.
        serial: The device serial, 12 lowercase hex digits.
        device: The device object. It is the same object on every event for
            this serial.
        changes: For ``UPDATED``, a read-only mapping from each changed field
            (``address``, ``label``, ``group``, ``location``,
            ``host_firmware``, ``wifi_firmware``) to its ``(old, new)``
            values. The address is an ``(ip, port)`` tuple. Empty for
            ``ADDED`` and ``REMOVED``.
    """

    type: DeviceEventType
    serial: str
    device: Device[Any]
    changes: Mapping[str, tuple[object, object]] = field(
        default_factory=lambda: MappingProxyType({})
    )


EventListener = Callable[[DeviceEvent], None]


def _normalise(serial: str) -> str:
    return Serial.from_string(serial).to_string()


def _snapshot(
    device: Device[Any], polled: Mapping[str, object] | None = None
) -> dict[str, object]:
    """The tracked fields of ``device`` as they stand now (no network I/O).

    ``polled`` holds the readings polling has taken so far.
    """
    return {
        **(polled or {}),
        "address": (device.ip, device.port),
        "label": device.label,
        "group": device.group,
        "location": device.location,
        "host_firmware": device.host_firmware,
        "wifi_firmware": device.wifi_firmware,
    }


class DeviceWatcher:
    """Track LIFX devices continuously and report what changes.

    On entry the watcher runs an initial discovery. After that it sweeps every
    ``sweep_interval`` seconds through the process-wide sweep coordinator,
    optionally with an mDNS leg for Thread and IPv6 devices. It builds each
    device through the normal discovery path and returns the same object for
    a serial every time. A device that reappears at another address is moved
    in place (see :meth:`lifx.devices.base.Device.update_address`) and
    reported as one ``UPDATED`` event.

    Events are read as an async iterator (``async for event in watcher``) or
    through callbacks registered with :meth:`add_listener`. The iterator's
    queue is bounded: when it is full the oldest event is dropped and
    :attr:`dropped_events` increments, so a slow consumer never blocks a
    sweep. Callbacks see every event, in order, at the moment it happens.

    A device is silent, and ``REMOVED`` is emitted, once it has answered
    nothing (a discovery reply or any request on its connection) for longer
    than ``silence_threshold``. The device object is kept; when it answers
    again ``ADDED`` is emitted for the same object.

    The watcher listens, discovers and, only when asked, reads. It never
    writes color or power. Two optional polls are off by default:

    - High-frequency polling reads color and power, plus zones on a multizone
      light and tiles on a matrix light. A device evidenced as Thread is not
      polled this way unless ``enable_thread`` is True, the same opt-in the
      software effect path uses.
    - Low-frequency polling reads label, host firmware, wifi firmware (not on
      a Thread device, which cannot answer it), group and location.

    Each poll refreshes the device's cached state and is reported as
    ``UPDATED`` with the changed fields. A poll that fails is logged and does
    not stop other devices or mark the device silent; silence still comes only
    from the liveness threshold. The first reading of a field is a baseline
    and is not reported.

    Example:
        ```python
        async with DeviceWatcher() as watcher:
            async for event in watcher:
                print(event.type, event.serial)
        ```

    Args:
        sweep_interval: Seconds between sweeps. Must be positive.
        silence_threshold: Seconds of silence before a device is removed.
            Defaults to the larger of 30 and five sweep intervals.
        mdns: Also discover through mDNS on each sweep.
        broadcast_address: Broadcast address for UDP discovery. May be
            reassigned; the new value applies from the next sweep.
        port: UDP port for discovery. May be reassigned like
            ``broadcast_address``.
        discovery_timeout: Overall timeout of each sweep, in seconds.
        idle_timeout_multiplier: Idle timeout multiplier for each sweep.
        device_timeout: Request timeout set on devices the watcher builds.
        max_retries: Max retries per request set on those devices.
        max_queue_size: Events held for the iterator. Must be positive.
        high_frequency_polling: Poll color, power, zones and tiles.
        high_frequency_interval: Seconds between those polls. Must be positive.
        low_frequency_polling: Poll label, firmware, group and location.
        low_frequency_interval: Seconds between those polls. Must be positive.
        enable_thread: Also poll Thread devices at high frequency.
    """

    def __init__(
        self,
        *,
        sweep_interval: float = DEFAULT_SWEEP_INTERVAL,
        silence_threshold: float | None = None,
        mdns: bool = False,
        broadcast_address: str = _DEFAULT_BROADCAST,
        port: int = LIFX_UDP_PORT,
        discovery_timeout: float = DISCOVERY_TIMEOUT,
        idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
        device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int | None = DEFAULT_MAX_RETRIES,
        max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE,
        high_frequency_polling: bool = False,
        high_frequency_interval: float = DEFAULT_HIGH_FREQUENCY_INTERVAL,
        low_frequency_polling: bool = False,
        low_frequency_interval: float = DEFAULT_LOW_FREQUENCY_INTERVAL,
        enable_thread: bool = False,
    ) -> None:
        if sweep_interval <= 0:
            raise ValueError("sweep_interval must be positive")
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be at least 1")
        if high_frequency_interval <= 0:
            raise ValueError("high_frequency_interval must be positive")
        if low_frequency_interval <= 0:
            raise ValueError("low_frequency_interval must be positive")
        self.sweep_interval = sweep_interval
        self.high_frequency_polling = high_frequency_polling
        self.high_frequency_interval = high_frequency_interval
        self.low_frequency_polling = low_frequency_polling
        self.low_frequency_interval = low_frequency_interval
        self.enable_thread = enable_thread
        self.silence_threshold = (
            max(MIN_SILENCE_THRESHOLD, SILENCE_INTERVALS * sweep_interval)
            if silence_threshold is None
            else silence_threshold
        )
        self.mdns = mdns
        self.broadcast_address = broadcast_address
        self.port = port
        self.discovery_timeout = discovery_timeout
        self.idle_timeout_multiplier = idle_timeout_multiplier
        self.device_timeout = device_timeout
        self.max_retries = max_retries
        self.max_queue_size = max_queue_size

        self._devices: dict[str, Device[Any]] = {}
        self._snapshots: dict[str, dict[str, object]] = {}
        self._heard: dict[str, float] = {}
        self._polled: dict[str, dict[str, object]] = {}
        self._next_high: dict[str, float] = {}
        self._next_low: dict[str, float] = {}
        self._polled_now: set[str] = set()
        self._silent: set[str] = set()
        self._queue: deque[DeviceEvent] = deque()
        self._wakeup = asyncio.Event()
        self._listeners: list[EventListener] = []
        self._dropped = 0
        self._sweeps = 0
        self._sweep_lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._poll_task: asyncio.Task[None] | None = None
        self._open = False
        self._closed = False

    # ---- lookup -------------------------------------------------------

    @property
    def devices(self) -> list[Device[Any]]:
        """The devices that are currently answering, one object per serial."""
        return [d for s, d in self._devices.items() if s not in self._silent]

    def get(self, serial: str) -> Device[Any] | None:
        """Return the object for ``serial``, silent or not, or ``None``.

        Args:
            serial: Device serial, with or without separators, any case.
        """
        try:
            return self._devices.get(_normalise(serial))
        except ValueError:
            return None

    @property
    def running(self) -> bool:
        """Whether the periodic sweep task is alive."""
        return self._task is not None and not self._task.done()

    @property
    def sweep_count(self) -> int:
        """How many sweeps have completed."""
        return self._sweeps

    @property
    def dropped_events(self) -> int:
        """Events dropped from the iterator queue because it was full."""
        return self._dropped

    # ---- events -------------------------------------------------------

    def add_listener(self, listener: EventListener) -> Callable[[], None]:
        """Call ``listener(event)`` for every event from now on.

        The callback runs synchronously inside the sweep, so keep it quick. An
        exception it raises is logged and does not stop other consumers.

        Returns:
            A function that removes the listener.
        """
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    def get_event_nowait(self) -> DeviceEvent | None:
        """Pop the oldest queued event, or ``None`` if there is none."""
        if self._queue:
            return self._queue.popleft()
        return None

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> DeviceEvent:
        while True:
            event = self.get_event_nowait()
            if event is not None:
                return event
            if self._closed:
                raise StopAsyncIteration
            self._wakeup.clear()
            await self._wakeup.wait()

    def _emit(
        self,
        event_type: DeviceEventType,
        serial: str,
        changes: Mapping[str, tuple[object, object]] | None = None,
    ) -> None:
        event = DeviceEvent(
            type=event_type,
            serial=serial,
            device=self._devices[serial],
            changes=MappingProxyType(dict(changes or {})),
        )
        if len(self._queue) >= self.max_queue_size:
            self._queue.popleft()
            self._dropped += 1
        self._queue.append(event)
        self._wakeup.set()
        for listener in tuple(self._listeners):
            try:
                listener(event)
            except Exception:
                _LOGGER.exception(
                    "device watcher listener failed for %s %s", event_type.value, serial
                )

    # ---- lifecycle ----------------------------------------------------

    async def __aenter__(self) -> Self:
        if self._open or self._closed:
            raise RuntimeError("a DeviceWatcher can be entered only once")
        self._open = True
        await self.sweep()
        self._task = asyncio.ensure_future(self._run())
        if self.high_frequency_polling or self.low_frequency_polling:
            self._poll_task = asyncio.ensure_future(self._run_polls())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Stop sweeping. Device objects stay open for whoever holds them."""
        self._closed = True
        tasks = [t for t in (self._task, self._poll_task) if t is not None]
        self._task = self._poll_task = None
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._wakeup.set()

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.sweep_interval)
            try:
                await self.sweep()
            except Exception:
                _LOGGER.warning("device watcher sweep failed", exc_info=True)

    async def _run_polls(self) -> None:
        """Poll between sweeps, so a poll interval shorter than a sweep holds."""
        intervals = []
        if self.high_frequency_polling:
            intervals.append(self.high_frequency_interval)
        if self.low_frequency_polling:
            intervals.append(self.low_frequency_interval)
        tick = min(intervals)
        while True:
            await asyncio.sleep(tick)
            try:
                async with self._sweep_lock:
                    await self._poll_devices()
                    self._reconcile()
            except Exception:
                _LOGGER.warning("device watcher poll failed", exc_info=True)

    # ---- sweeping -----------------------------------------------------

    async def sweep(self) -> None:
        """Run one discovery sweep now and update liveness.

        The periodic task calls this; call it yourself to force a sweep. Sweeps
        never overlap.
        """
        if not self._open:
            raise RuntimeError("the DeviceWatcher is not open")
        async with self._sweep_lock:
            legs = [self._udp_leg()]
            if self.mdns:
                legs.append(self._mdns_leg())
            for result in await asyncio.gather(*legs, return_exceptions=True):
                if isinstance(result, BaseException):
                    _LOGGER.warning(
                        "device watcher discovery leg failed", exc_info=result
                    )
            await self._poll_devices()
            self._reconcile()
            self._sweeps += 1

    def _discovery_kwargs(self) -> dict[str, Any]:
        return {
            "timeout": self.discovery_timeout,
            "idle_timeout_multiplier": self.idle_timeout_multiplier,
            "device_timeout": self.device_timeout,
            "max_retries": self.max_retries,
            "known_devices": list(self._devices.values()),
        }

    async def _udp_leg(self) -> None:
        stream = discover_udp(
            broadcast_address=self.broadcast_address,
            port=self.port,
            **self._discovery_kwargs(),
        )
        await self._consume(stream)

    async def _mdns_leg(self) -> None:
        await self._consume(discover_mdns(**self._discovery_kwargs()))

    async def _consume(self, stream: AsyncGenerator[Device[Any], None]) -> None:
        async with aclosing(stream):
            async for device in stream:
                self._ingest(device)

    def _ingest(self, device: Device[Any]) -> None:
        """Record a discovery result. Known serials arrive as the held object."""
        serial = _normalise(device.serial)
        self._heard[serial] = self._now()
        if serial not in self._devices:
            self._devices[serial] = device
            self._snapshots[serial] = _snapshot(device, self._polled.get(serial))
            self._emit(DeviceEventType.ADDED, serial)

    async def _poll_devices(self) -> None:
        """Read the state the caller asked to keep fresh, for devices that are due.

        Runs once per sweep, after discovery and before change detection, so
        whatever it refreshes on a held device is reported as ``UPDATED`` by
        the same sweep. With both polls off it sends nothing. Devices are
        polled concurrently; a failure on one never reaches the others.
        """
        if not (self.high_frequency_polling or self.low_frequency_polling):
            return
        now = self._now()
        jobs = []
        for serial, device in self._devices.items():
            if serial in self._silent:
                continue
            if self.high_frequency_polling and now >= self._next_high.get(
                serial, float("-inf")
            ):
                self._next_high[serial] = now + self.high_frequency_interval
                self._polled_now.add(serial)
                jobs.append(self._poll_high(serial, device))
            if self.low_frequency_polling and now >= self._next_low.get(
                serial, float("-inf")
            ):
                self._next_low[serial] = now + self.low_frequency_interval
                self._polled_now.add(serial)
                jobs.append(self._poll_low(device))
        for result in await asyncio.gather(*jobs, return_exceptions=True):
            if isinstance(result, BaseException):
                _LOGGER.warning("device watcher poll failed", exc_info=result)
        for serial in self._polled_now:
            self._baseline_unread_fields(serial)
        self._polled_now.clear()

    def _baseline_unread_fields(self, serial: str) -> None:
        """Adopt first readings silently.

        A field that was never read (``None``) and is read by a poll for the
        first time has no previous value to change from, so it is a baseline
        and not an update.
        """
        current = _snapshot(self._devices[serial], self._polled.get(serial))
        snapshot = self._snapshots[serial]
        for name, value in snapshot.items():
            if value is None:
                snapshot[name] = current[name]

    async def _poll_high(self, serial: str, device: Device[Any]) -> None:
        """Read color and power, plus zones or tiles, and record the readings."""
        if (
            device._evidenced_connectivity() is Connectivity.THREAD
            and not self.enable_thread
        ):
            return
        if not isinstance(device, Light):
            return
        polled = self._polled.setdefault(serial, {})
        color, power, _label = await device.get_color()
        polled["color"] = color
        polled["power"] = power
        if isinstance(device, MultiZoneLight):
            polled["zones"] = tuple(await device.get_all_color_zones())
        elif isinstance(device, MatrixLight):
            polled["tiles"] = tuple(
                tuple(tile) for tile in await device.get_all_tile_colors()
            )

    async def _poll_low(self, device: Device[Any]) -> None:
        """Refresh label, firmware, group and location in the device's cache."""
        queries = [
            device.get_label(),
            device.get_host_firmware(),
            device.get_group(),
            device.get_location(),
        ]
        if device._evidenced_connectivity() is not Connectivity.THREAD:
            queries.append(device.get_wifi_firmware())
        for result in await asyncio.gather(*queries, return_exceptions=True):
            if isinstance(result, BaseException):
                _LOGGER.warning("device watcher poll failed", exc_info=result)

    def _now(self) -> float:
        return _connection.monotonic_now()

    def _last_heard(self, serial: str) -> float:
        device = self._devices[serial]
        answered = device.connection.last_response_at
        return max(self._heard.get(serial, float("-inf")), answered or float("-inf"))

    def _reconcile(self) -> None:
        """Diff every device's tracked fields and settle who is silent."""
        now = self._now()
        for serial in self._devices:
            silent = now - self._last_heard(serial) > self.silence_threshold
            if serial in self._silent:
                if not silent:
                    self._silent.discard(serial)
                    self._snapshots[serial] = _snapshot(
                        self._devices[serial], self._polled.get(serial)
                    )
                    self._emit(DeviceEventType.ADDED, serial)
                continue
            if silent:
                self._silent.add(serial)
                self._emit(DeviceEventType.REMOVED, serial)
                continue
            self._report_changes(serial)

    def _report_changes(self, serial: str) -> None:
        old = self._snapshots[serial]
        new = _snapshot(self._devices[serial], self._polled.get(serial))
        changes = {
            name: (old[name], new[name])
            for name in (*_TRACKED_FIELDS, *_POLLED_FIELDS)
            if name in old and name in new and old[name] != new[name]
        }
        self._snapshots[serial] = new
        if changes:
            self._emit(DeviceEventType.UPDATED, serial, changes)
