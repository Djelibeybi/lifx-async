"""Process-wide active-only coordination for UDP discovery sweeps."""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import os
import threading
import time
import weakref
from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import aclosing
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, cast

_COORDINATOR_SHUTDOWN_TIMEOUT = 2.0
_DiscoveryObserver = Callable[[str, str, str, int | None, int | None, str | None], None]


class _DiscoveryRecord(Protocol):
    """Minimum record surface used by the coordinator."""

    serial: str


_DiscoveryRecordT = TypeVar("_DiscoveryRecordT", bound=_DiscoveryRecord)


@dataclass(frozen=True)
class _UdpSweepKey:
    """Wire and timing arguments that decide whether callers may share."""

    broadcast_address: str
    port: int
    timeout: float
    max_response_time: float
    idle_timeout_multiplier: float


@dataclass(frozen=True)
class _SubscriptionToken:
    """Opaque identity for one coordinator subscription."""

    value: int


@dataclass(frozen=True)
class _RecordEvent:
    """One accepted raw response delivered to a caller loop."""

    record: _DiscoveryRecord


@dataclass(frozen=True)
class _TerminalEvent:
    """Normal or exceptional completion of one active sweep."""

    error: BaseException | None = None


@dataclass
class _Subscriber:
    """Coordinator-owned routing information for one caller."""

    token: _SubscriptionToken
    caller_loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[_RecordEvent | _TerminalEvent]
    caller_deadline: float
    observer: _DiscoveryObserver | None


@dataclass
class _ActiveUdpSweep:
    """Active producer state, retained only until its terminal outcome."""

    key: _UdpSweepKey
    producer_factory: Callable[[], AsyncGenerator[_DiscoveryRecord, None]]
    records: list[_DiscoveryRecord] = field(default_factory=list)
    subscribers: dict[_SubscriptionToken, _Subscriber] = field(default_factory=dict)
    producer_task: asyncio.Task[None] | None = None


@dataclass
class _SubscriptionHandle:
    """Weak-reference target used to detach an abandoned async generator."""

    key: _UdpSweepKey
    token: _SubscriptionToken


def _completed_future() -> concurrent.futures.Future[None]:
    """Return an already-resolved cross-thread future."""
    future: concurrent.futures.Future[None] = concurrent.futures.Future()
    future.set_result(None)
    return future


class _UdpSweepCoordinator:
    """Own a lazy worker loop and active sweep registry."""

    def __init__(self) -> None:
        self._lifecycle_lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready: threading.Event | None = None
        self._stopping = False
        self._pending_registrations = 0
        self._active: dict[_UdpSweepKey, _ActiveUdpSweep] = {}
        self._stop_task: asyncio.Task[None] | None = None

    @staticmethod
    def _lifecycle_wait_timeout(caller_deadline: float | None) -> float:
        """Cap one blocking lifecycle wait by the caller's remaining budget."""
        if caller_deadline is None:
            return _COORDINATOR_SHUTDOWN_TIMEOUT
        return max(
            0.0,
            min(
                _COORDINATOR_SHUTDOWN_TIMEOUT,
                caller_deadline - time.monotonic(),
            ),
        )

    def _ensure_started(
        self,
        caller_deadline: float | None = None,
    ) -> asyncio.AbstractEventLoop:
        """Start the coordinator thread after installing process hooks."""
        while True:
            thread_to_join: threading.Thread | None = None
            ready_to_wait: threading.Event | None = None
            with self._lifecycle_lock:
                if self._thread is not None and self._thread.is_alive():
                    if not self._stopping:
                        if self._loop is not None:
                            return self._loop
                        ready_to_wait = self._ready
                    else:
                        thread_to_join = self._thread
                else:
                    _register_process_hooks()
                    self._ready = threading.Event()
                    self._stopping = False
                    thread = threading.Thread(
                        target=self._run,
                        name="lifx-udp-discovery-coordinator",
                        daemon=True,
                    )
                    self._thread = thread
                    thread.start()
                    ready = self._ready
                    break
            if ready_to_wait is not None:
                wait_timeout = self._lifecycle_wait_timeout(caller_deadline)
                if wait_timeout <= 0:
                    raise TimeoutError("UDP discovery caller deadline expired")
                if not ready_to_wait.wait(wait_timeout):
                    if caller_deadline is not None:
                        raise TimeoutError("UDP discovery caller deadline expired")
                    raise RuntimeError("UDP discovery coordinator did not start")
                continue
            # The ready-wait branch continues above and the fresh-worker branch
            # breaks from the loop, so only a stopping worker can reach here.
            assert thread_to_join is not None
            wait_timeout = self._lifecycle_wait_timeout(caller_deadline)
            if wait_timeout <= 0:
                raise TimeoutError("UDP discovery caller deadline expired")
            thread_to_join.join(wait_timeout)
            if thread_to_join.is_alive():
                if caller_deadline is not None:
                    raise TimeoutError("UDP discovery caller deadline expired")
                raise RuntimeError("UDP discovery coordinator did not stop")

        wait_timeout = self._lifecycle_wait_timeout(caller_deadline)
        if wait_timeout <= 0:
            raise TimeoutError("UDP discovery caller deadline expired")
        if ready is None or not ready.wait(wait_timeout):
            if caller_deadline is not None:
                raise TimeoutError("UDP discovery caller deadline expired")
            raise RuntimeError("UDP discovery coordinator did not start")
        with self._lifecycle_lock:
            if self._loop is None:
                raise RuntimeError("UDP discovery coordinator started without a loop")
            return self._loop

    def _run(self) -> None:
        """Run and deterministically close the coordinator-owned event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._lifecycle_lock:
            self._loop = loop
            ready = self._ready
        if ready is not None:
            ready.set()
        try:
            loop.run_forever()
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()
            with self._lifecycle_lock:
                self._loop = None
                self._thread = None
                self._ready = None
                self._stopping = False
                self._pending_registrations = 0

    def register(
        self,
        key: _UdpSweepKey,
        token: _SubscriptionToken,
        producer_factory: Callable[[], AsyncGenerator[_DiscoveryRecord, None]],
        caller_loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue[_RecordEvent | _TerminalEvent],
        caller_deadline: float,
        observer: _DiscoveryObserver | None,
    ) -> concurrent.futures.Future[None]:
        """Submit serialised prefix registration to the worker loop."""
        for attempt in range(2):
            loop = self._ensure_started(caller_deadline)
            with self._lifecycle_lock:
                if loop is not self._loop or self._stopping or loop.is_closed():
                    continue
                self._pending_registrations += 1
                registration = self._register(
                    key,
                    token,
                    producer_factory,
                    caller_loop,
                    queue,
                    caller_deadline,
                    observer,
                )
                acknowledged = self._acknowledge_registration(registration)
                try:
                    return asyncio.run_coroutine_threadsafe(acknowledged, loop)
                except RuntimeError:
                    self._pending_registrations -= 1
                    registration.close()
                    acknowledged.close()
                    if self._loop is loop:
                        self._stopping = True
            self._request_loop_stop(loop)
            if attempt:
                raise RuntimeError("UDP discovery registration could not be submitted")
        raise RuntimeError("UDP discovery coordinator stopped during registration")

    async def _acknowledge_registration(
        self,
        registration: Coroutine[Any, Any, None],
    ) -> None:
        """Release the idle-stop guard when a submitted registration starts."""
        with self._lifecycle_lock:
            self._pending_registrations -= 1
        await registration

    async def _register(
        self,
        key: _UdpSweepKey,
        token: _SubscriptionToken,
        producer_factory: Callable[[], AsyncGenerator[_DiscoveryRecord, None]],
        caller_loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue[_RecordEvent | _TerminalEvent],
        caller_deadline: float,
        observer: _DiscoveryObserver | None,
    ) -> None:
        """Attach a caller, scheduling its prefix before future suffixes."""
        if time.monotonic() >= caller_deadline:
            caller_loop.call_soon_threadsafe(queue.put_nowait, _TerminalEvent())
            self._schedule_stop_if_idle()
            return

        active = self._active.get(key)
        if active is None:
            active = _ActiveUdpSweep(key=key, producer_factory=producer_factory)
            self._active[key] = active

        subscriber = _Subscriber(
            token=token,
            caller_loop=caller_loop,
            queue=queue,
            caller_deadline=caller_deadline,
            observer=observer,
        )
        for record in active.records:
            if not self._schedule_record(subscriber, record):
                self._schedule_stop_if_idle()
                return
        active.subscribers[token] = subscriber

        if active.producer_task is None:
            active.producer_task = asyncio.create_task(self._run_producer(active))

    def detach(
        self, key: _UdpSweepKey, token: _SubscriptionToken
    ) -> concurrent.futures.Future[None]:
        """Submit an idempotent detach without starting an idle worker."""
        with self._lifecycle_lock:
            loop = self._loop
            thread = self._thread
            stopping = self._stopping
        if (
            loop is None
            or thread is None
            or not thread.is_alive()
            or loop.is_closed()
            or stopping
        ):
            return _completed_future()
        try:
            return asyncio.run_coroutine_threadsafe(self._detach(key, token), loop)
        except RuntimeError:
            return _completed_future()

    async def _detach(self, key: _UdpSweepKey, token: _SubscriptionToken) -> None:
        """Remove a subscriber and reap the producer when it was last."""
        active = self._active.get(key)
        if active is None or active.subscribers.pop(token, None) is None:
            return
        if active.subscribers:
            return

        producer_task = active.producer_task
        if producer_task is not None and not producer_task.done():
            producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass
        self._active.pop(key, None)
        self._schedule_stop_if_idle()

    async def _run_producer(self, active: _ActiveUdpSweep) -> None:
        """Drain one validated producer independently of every subscriber."""
        terminal_error: BaseException | None = None
        try:
            producer = active.producer_factory()
            async with aclosing(producer):
                async for record in producer:
                    active.records.append(record)
                    abandoned: list[_SubscriptionToken] = []
                    for token, subscriber in active.subscribers.items():
                        if not self._schedule_record(subscriber, record):
                            abandoned.append(token)
                    for token in abandoned:
                        active.subscribers.pop(token, None)
                    if not active.subscribers:
                        return
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            terminal_error = error
        finally:
            if self._active.get(active.key) is active:
                self._active.pop(active.key, None)
            subscribers = tuple(active.subscribers.values())
            active.subscribers.clear()
            for subscriber in subscribers:
                self._schedule_terminal(subscriber, terminal_error)
            self._schedule_stop_if_idle()

    @staticmethod
    def _schedule_record(subscriber: _Subscriber, record: _DiscoveryRecord) -> bool:
        """Schedule one deadline-checked record and observation as one turn."""

        def _deliver() -> None:
            if time.monotonic() >= subscriber.caller_deadline:
                return
            if subscriber.observer is not None:
                subscriber.observer(
                    "udp",
                    "accepted",
                    record.serial,
                    None,
                    None,
                    None,
                )
            subscriber.queue.put_nowait(_RecordEvent(record))

        try:
            subscriber.caller_loop.call_soon_threadsafe(_deliver)
        except RuntimeError:
            return False
        return True

    @staticmethod
    def _schedule_terminal(
        subscriber: _Subscriber, error: BaseException | None
    ) -> None:
        """Schedule one terminal event without touching a closed caller loop."""
        try:
            subscriber.caller_loop.call_soon_threadsafe(
                subscriber.queue.put_nowait, _TerminalEvent(error)
            )
        except RuntimeError:
            pass

    def _schedule_stop_if_idle(self) -> None:
        """Stop after pending future callbacks observe completed operations."""
        if self._active or self._stopping:
            return
        if self._stop_task is None or self._stop_task.done():
            self._stop_task = asyncio.create_task(self._stop_after_turn())

    async def _stop_after_turn(self) -> None:
        """Yield once before stopping so cross-thread futures resolve first."""
        await asyncio.sleep(0)
        if self._active:
            self._stop_task = None
            return
        loop = asyncio.get_running_loop()
        with self._lifecycle_lock:
            if self._pending_registrations:
                self._stop_task = None
                return
            self._stopping = True
        self._stop_task = None
        loop.stop()

    @staticmethod
    def _request_loop_stop(loop: asyncio.AbstractEventLoop) -> None:
        """Best-effort stop for a worker loop that may be closing concurrently."""
        if loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(loop.stop)
        except RuntimeError:
            pass

    def shutdown(self) -> None:
        """Request cancellation and join the worker with a bounded wait."""
        with self._lifecycle_lock:
            loop = self._loop
            thread = self._thread
            if loop is None or thread is None or not thread.is_alive():
                return
            join_only = self._stopping or loop.is_closed()
            self._stopping = True
        if join_only:
            thread.join(_COORDINATOR_SHUTDOWN_TIMEOUT)
            return
        shutdown = self._shutdown()
        try:
            future = asyncio.run_coroutine_threadsafe(shutdown, loop)
            future.result(_COORDINATOR_SHUTDOWN_TIMEOUT)
        except RuntimeError:
            shutdown.close()
        except concurrent.futures.TimeoutError:
            pass
        finally:
            self._request_loop_stop(loop)
        thread.join(_COORDINATOR_SHUTDOWN_TIMEOUT)

    async def _shutdown(self) -> None:
        """Cancel every active producer before stopping the worker loop."""
        tasks = [
            active.producer_task
            for active in self._active.values()
            if active.producer_task is not None and not active.producer_task.done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._active.clear()


_PROCESS_HOOK_LOCK = threading.Lock()
_TOKEN_LOCK = threading.Lock()
_FORK_HOOK_REGISTERED = False
_ATEXIT_HOOK_REGISTERED = False
_NEXT_TOKEN = 0
_UDP_SWEEP_COORDINATOR = _UdpSweepCoordinator()


def _register_process_hooks() -> None:
    """Install lifecycle hooks once, immediately before the first thread."""
    global _ATEXIT_HOOK_REGISTERED, _FORK_HOOK_REGISTERED
    with _PROCESS_HOOK_LOCK:
        if not _ATEXIT_HOOK_REGISTERED:
            atexit.register(_shutdown_udp_coordinator_at_exit)
            _ATEXIT_HOOK_REGISTERED = True
        if hasattr(os, "register_at_fork") and not _FORK_HOOK_REGISTERED:
            os.register_at_fork(after_in_child=_reset_udp_coordinator_after_fork)
            _FORK_HOOK_REGISTERED = True


def _allocate_subscription_token() -> _SubscriptionToken:
    """Allocate a process-local subscription identity before registration."""
    global _NEXT_TOKEN
    with _TOKEN_LOCK:
        _NEXT_TOKEN += 1
        return _SubscriptionToken(_NEXT_TOKEN)


def _detach_abandoned_subscription(
    key: _UdpSweepKey, token: _SubscriptionToken
) -> None:
    """Request best-effort idempotent detach for a collected subscription."""
    _UDP_SWEEP_COORDINATOR.detach(key, token)


def _shutdown_udp_coordinator_at_exit() -> None:
    """Bound interpreter-exit cleanup without application signal handlers."""
    _UDP_SWEEP_COORDINATOR.shutdown()


def _reset_udp_coordinator_after_fork() -> None:
    """Discard inherited parent thread/loop state in a forked child."""
    global _PROCESS_HOOK_LOCK, _TOKEN_LOCK, _UDP_SWEEP_COORDINATOR
    _PROCESS_HOOK_LOCK = threading.Lock()
    _TOKEN_LOCK = threading.Lock()
    _UDP_SWEEP_COORDINATOR = _UdpSweepCoordinator()


async def _await_cross_thread_future(
    future: concurrent.futures.Future[None],
) -> None:
    """Await a coordinator operation without propagating caller cancellation."""
    await asyncio.shield(asyncio.wrap_future(future))


async def subscribe_udp_sweep(
    key: _UdpSweepKey,
    producer_factory: Callable[[], AsyncGenerator[_DiscoveryRecordT, None]],
    *,
    caller_deadline: float,
    observer: _DiscoveryObserver | None,
) -> AsyncGenerator[_DiscoveryRecordT, None]:
    """Yield one active producer's accepted records on the caller's loop."""
    caller_loop = asyncio.get_running_loop()
    queue: asyncio.Queue[_RecordEvent | _TerminalEvent] = asyncio.Queue()
    token = _allocate_subscription_token()
    handle = _SubscriptionHandle(key=key, token=token)
    finalizer = weakref.finalize(
        handle, _detach_abandoned_subscription, handle.key, handle.token
    )
    registered = False
    terminal_received = False

    try:
        try:
            registration = _UDP_SWEEP_COORDINATOR.register(
                key,
                token,
                producer_factory,
                caller_loop,
                queue,
                caller_deadline,
                observer,
            )
        except TimeoutError:
            return
        try:
            remaining = caller_deadline - time.monotonic()
            if remaining <= 0:
                registration.add_done_callback(
                    lambda _future: _detach_abandoned_subscription(key, token)
                )
                return
            await asyncio.wait_for(
                _await_cross_thread_future(registration),
                timeout=remaining,
            )
            registered = True
        except asyncio.TimeoutError:
            registration.add_done_callback(
                lambda _future: _detach_abandoned_subscription(key, token)
            )
            return
        except asyncio.CancelledError:
            registration.add_done_callback(
                lambda _future: _detach_abandoned_subscription(key, token)
            )
            raise

        while True:
            remaining = caller_deadline - time.monotonic()
            if remaining <= 0:
                return
            try:
                event = await asyncio.wait_for(queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                return

            if isinstance(event, _TerminalEvent):
                terminal_received = True
                if event.error is not None:
                    raise event.error
                return
            yield cast(_DiscoveryRecordT, event.record)
    finally:
        finalizer.detach()
        if registered and not terminal_received:
            detach = _UDP_SWEEP_COORDINATOR.detach(key, token)
            try:
                await _await_cross_thread_future(detach)
            except asyncio.CancelledError:
                detach.add_done_callback(
                    lambda _future: _detach_abandoned_subscription(key, token)
                )
                raise
