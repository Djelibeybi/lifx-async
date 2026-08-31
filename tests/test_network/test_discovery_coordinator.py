"""Deterministic tests for process-wide UDP discovery coordination."""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import AsyncGenerator, Callable, Generator
from types import SimpleNamespace

import pytest

import lifx.network.discovery.coordinator as discovery_coordinator
from lifx.network.discovery import DiscoveryResponse
from lifx.network.discovery.coordinator import (
    _shutdown_udp_coordinator_at_exit,
    _UdpSweepKey,
    subscribe_udp_sweep,
)
from lifx.network.discovery.udp import discover_devices_shared
from tests.test_discovery_observation import _DiscoveryObservationSink


def _response(serial: str, ordinal: int) -> DiscoveryResponse:
    """Build one synthetic accepted UDP response."""
    return DiscoveryResponse(
        serial=serial,
        ip=f"192.0.2.{ordinal}",
        port=56700,
        response_time=float(ordinal),
        response_payload={"port": 56700},
    )


def _key(*, port: int = 56700) -> _UdpSweepKey:
    """Build a compatibility key with synthetic values."""
    return _UdpSweepKey(
        broadcast_address="192.0.2.255",
        port=port,
        timeout=10.0,
        max_response_time=2.0,
        idle_timeout_multiplier=2.0,
    )


class _GatedDiscoveryProducer:
    """Controllable producer whose gates work across event-loop threads."""

    def __init__(
        self,
        prefix: tuple[DiscoveryResponse, ...],
        suffix: tuple[DiscoveryResponse, ...] = (),
    ) -> None:
        self.prefix = prefix
        self.suffix = suffix
        self.started = threading.Event()
        self.release = threading.Event()
        self.closed = threading.Event()
        self.calls = 0

    def factory(self) -> AsyncGenerator[DiscoveryResponse, None]:
        """Return one fresh producer invocation."""

        async def _produce() -> AsyncGenerator[DiscoveryResponse, None]:
            self.calls += 1
            try:
                for record in self.prefix:
                    yield record
                self.started.set()
                while not self.release.is_set():
                    await asyncio.sleep(0.001)
                for record in self.suffix:
                    yield record
            finally:
                self.closed.set()

        return _produce()


@pytest.fixture(autouse=True)
def _clean_coordinator() -> Generator[None, None, None]:
    """Leave no worker thread or active registry between tests."""
    _shutdown_udp_coordinator_at_exit()
    yield
    _shutdown_udp_coordinator_at_exit()


async def _collect(
    key: _UdpSweepKey,
    factory: Callable[[], AsyncGenerator[DiscoveryResponse, None]],
    *,
    sink: _DiscoveryObservationSink | None = None,
    caller_deadline: float | None = None,
) -> list[DiscoveryResponse]:
    """Collect one subscription using a caller-owned deadline and sink."""
    deadline = caller_deadline if caller_deadline is not None else time.monotonic() + 5
    return [
        record
        async for record in subscribe_udp_sweep(
            key,
            factory,
            caller_deadline=deadline,
            observer=None if sink is None else sink.observe,
        )
    ]


async def test_compatible_subscribers_share_one_active_producer() -> None:
    """Equal keys join one producer and both receive the accepted records."""
    producer = _GatedDiscoveryProducer((_response("d073d5000001", 1),))

    first = asyncio.create_task(_collect(_key(), producer.factory))
    assert await asyncio.to_thread(producer.started.wait, 2)
    second = subscribe_udp_sweep(
        _key(),
        producer.factory,
        caller_deadline=time.monotonic() + 5,
        observer=None,
    )
    second_prefix = await anext(second)
    producer.release.set()

    first_records = await first
    second_records = [second_prefix, *[record async for record in second]]

    assert producer.calls == 1
    assert [record.serial for record in first_records] == ["d073d5000001"]
    assert [record.serial for record in second_records] == ["d073d5000001"]


async def test_incompatible_keys_start_independent_producers() -> None:
    """A wire-key difference prevents sharing."""
    first_producer = _GatedDiscoveryProducer(())
    second_producer = _GatedDiscoveryProducer(())

    first = asyncio.create_task(_collect(_key(port=56700), first_producer.factory))
    second = asyncio.create_task(_collect(_key(port=56701), second_producer.factory))
    assert await asyncio.to_thread(first_producer.started.wait, 2)
    assert await asyncio.to_thread(second_producer.started.wait, 2)
    first_producer.release.set()
    second_producer.release.set()
    await asyncio.gather(first, second)

    assert first_producer.calls == 1
    assert second_producer.calls == 1


async def test_late_subscriber_receives_prefix_then_suffix_once() -> None:
    """Registration schedules the accepted prefix before future records."""
    producer = _GatedDiscoveryProducer(
        (_response("d073d5000001", 1),),
        (_response("d073d5000002", 2),),
    )

    first = asyncio.create_task(_collect(_key(), producer.factory))
    assert await asyncio.to_thread(producer.started.wait, 2)
    late = subscribe_udp_sweep(
        _key(),
        producer.factory,
        caller_deadline=time.monotonic() + 5,
        observer=None,
    )
    late_prefix = await anext(late)
    producer.release.set()

    first_records = await first
    late_records = [late_prefix, *[record async for record in late]]

    expected = ["d073d5000001", "d073d5000002"]
    assert [record.serial for record in first_records] == expected
    assert [record.serial for record in late_records] == expected


async def test_slow_subscriber_does_not_block_other_delivery() -> None:
    """An unread caller queue cannot backpressure producer progress."""
    producer = _GatedDiscoveryProducer(
        (_response("d073d5000001", 1),),
        (_response("d073d5000002", 2),),
    )
    slow = subscribe_udp_sweep(
        _key(),
        producer.factory,
        caller_deadline=time.monotonic() + 5,
        observer=None,
    )
    slow_first = asyncio.create_task(anext(slow))
    assert await asyncio.to_thread(producer.started.wait, 2)
    assert (await slow_first).serial == "d073d5000001"

    fast = asyncio.create_task(_collect(_key(), producer.factory))
    producer.release.set()
    fast_records = await fast

    assert [record.serial for record in fast_records] == [
        "d073d5000001",
        "d073d5000002",
    ]
    await slow.aclose()
    assert producer.closed.wait(2)


async def test_non_last_detach_preserves_producer_and_last_detach_reaps_it() -> None:
    """Only the last subscriber waits for producer-generator closure."""
    producer = _GatedDiscoveryProducer((_response("d073d5000001", 1),))
    first = subscribe_udp_sweep(
        _key(),
        producer.factory,
        caller_deadline=time.monotonic() + 5,
        observer=None,
    )
    second = subscribe_udp_sweep(
        _key(),
        producer.factory,
        caller_deadline=time.monotonic() + 5,
        observer=None,
    )

    assert (await anext(first)).serial == "d073d5000001"
    assert (await anext(second)).serial == "d073d5000001"
    await first.aclose()
    assert not producer.closed.is_set()

    await second.aclose()
    assert not producer.release.is_set()
    assert producer.closed.is_set()
    assert producer.calls == 1


async def test_expired_caller_deadline_starts_no_producer() -> None:
    """Registration after the caller wall deadline completes without replay."""
    producer = _GatedDiscoveryProducer((_response("d073d5000001", 1),))

    records = await _collect(
        _key(), producer.factory, caller_deadline=time.monotonic() - 1
    )

    assert records == []
    assert producer.calls == 0


async def test_active_silent_producer_returns_when_queue_wait_times_out() -> None:
    """An active silent sweep ends when its subscriber's queue wait expires."""
    producer = _GatedDiscoveryProducer(())

    records = await _collect(
        _key(), producer.factory, caller_deadline=time.monotonic() + 1
    )

    assert records == []
    assert producer.started.is_set()
    assert producer.closed.is_set()
    assert producer.calls == 1


async def test_each_subscription_observes_only_its_delivered_records() -> None:
    """Replay and suffix observations use the explicit caller-owned sink."""
    producer = _GatedDiscoveryProducer(
        (_response("d073d5000001", 1),),
        (_response("d073d5000002", 2),),
    )
    first_sink = _DiscoveryObservationSink()
    late_sink = _DiscoveryObservationSink()

    first = asyncio.create_task(_collect(_key(), producer.factory, sink=first_sink))
    assert await asyncio.to_thread(producer.started.wait, 2)
    late = asyncio.create_task(_collect(_key(), producer.factory, sink=late_sink))
    producer.release.set()
    await asyncio.gather(first, late)

    assert [event.raw_identity for event in first_sink.observations] == [
        "d073d5000001",
        "d073d5000002",
    ]
    assert [event.raw_identity for event in late_sink.observations] == [
        "d073d5000001",
        "d073d5000002",
    ]


async def test_completed_sweep_is_not_replayed() -> None:
    """A positive terminal outcome leaves no completed cache."""
    serials = iter(("d073d5000001", "d073d5000002"))
    calls = 0

    def factory() -> AsyncGenerator[DiscoveryResponse, None]:
        async def _produce() -> AsyncGenerator[DiscoveryResponse, None]:
            nonlocal calls
            calls += 1
            yield _response(next(serials), calls)

        return _produce()

    first = await _collect(_key(), factory)
    second = await _collect(_key(), factory)

    assert calls == 2
    assert first[0].serial == "d073d5000001"
    assert second[0].serial == "d073d5000002"


async def test_failed_sweep_is_removed_before_next_call() -> None:
    """A producer failure is delivered once and cannot poison a later call."""
    calls = 0

    def factory() -> AsyncGenerator[DiscoveryResponse, None]:
        async def _produce() -> AsyncGenerator[DiscoveryResponse, None]:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("synthetic producer failure")
            yield _response("d073d5000001", 1)

        return _produce()

    with pytest.raises(RuntimeError, match="synthetic producer failure"):
        await _collect(_key(), factory)

    records = await _collect(_key(), factory)
    assert calls == 2
    assert [record.serial for record in records] == ["d073d5000001"]


def test_compatible_cross_loop_subscribers_share_one_producer() -> None:
    """Separate OS-thread event loops still share the process-wide sweep."""
    producer = _GatedDiscoveryProducer((_response("d073d5000001", 1),))
    ready = threading.Barrier(3)
    subscription_lock = threading.Lock()
    both_subscribed = threading.Event()
    subscription_count = 0
    results: list[list[DiscoveryResponse]] = []
    failures: list[BaseException] = []

    def _run_subscriber_loop() -> None:
        try:
            ready.wait()
            records = asyncio.run(_collect_after_prefix())
            results.append(records)
        except BaseException as error:
            failures.append(error)

    async def _collect_after_prefix() -> list[DiscoveryResponse]:
        nonlocal subscription_count
        subscription = subscribe_udp_sweep(
            _key(),
            producer.factory,
            caller_deadline=time.monotonic() + 5,
            observer=None,
        )
        first = await anext(subscription)
        with subscription_lock:
            subscription_count += 1
            if subscription_count == 2:
                both_subscribed.set()
        assert await asyncio.to_thread(both_subscribed.wait, 2)
        return [first, *[record async for record in subscription]]

    threads = [threading.Thread(target=_run_subscriber_loop) for _ in range(2)]
    for thread in threads:
        thread.start()
    ready.wait()
    assert producer.started.wait(2)
    subscribers_ready = both_subscribed.wait(2)
    producer.release.set()
    for thread in threads:
        thread.join(2)

    assert failures == []
    assert subscribers_ready
    assert all(not thread.is_alive() for thread in threads)
    assert producer.calls == 1
    assert [[record.serial for record in records] for records in results] == [
        ["d073d5000001"],
        ["d073d5000001"],
    ]


def test_abandoned_subscription_does_not_delay_interpreter_exit() -> None:
    """The atexit path bounds cleanup of an unclosed active subscription."""
    script = textwrap.dedent(
        """
        import asyncio
        import gc
        import time

        from lifx.network.discovery import DiscoveryResponse
        from lifx.network.discovery.coordinator import _UdpSweepKey, subscribe_udp_sweep

        async def producer():
            yield DiscoveryResponse(
                serial="d073d5000001",
                ip="192.0.2.1",
                port=56700,
                response_time=0.0,
                response_payload={"port": 56700},
            )
            await asyncio.Event().wait()

        async def main():
            subscription = subscribe_udp_sweep(
                _UdpSweepKey("192.0.2.255", 56700, 10.0, 2.0, 2.0),
                producer,
                caller_deadline=time.monotonic() + 10,
                observer=None,
            )
            assert (await anext(subscription)).serial == "d073d5000001"
            del subscription
            gc.collect()

        asyncio.run(main())
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert completed.returncode == 0, completed.stderr


def test_forked_child_lazily_starts_a_fresh_coordinator() -> None:
    """A child reset starts fresh, including through a real fork when available."""
    if (
        sys.platform != "linux"
        or not hasattr(os, "fork")
        or not hasattr(os, "register_at_fork")
    ):

        async def producer():
            yield _response("d073d5000002", 1)

        discovery_coordinator._reset_udp_coordinator_after_fork()
        records = asyncio.run(_collect(_key(), producer))
        assert [record.serial for record in records] == ["d073d5000002"]
        return

    script = textwrap.dedent(
        """
        import asyncio
        import os
        import threading
        import time

        from lifx.network.discovery import DiscoveryResponse
        from lifx.network.discovery.coordinator import _UdpSweepKey, subscribe_udp_sweep

        key = _UdpSweepKey("192.0.2.255", 56700, 10.0, 2.0, 2.0)
        started = threading.Event()
        release = threading.Event()

        def response(serial):
            return DiscoveryResponse(
                serial=serial,
                ip="192.0.2.1",
                port=56700,
                response_time=0.0,
                response_payload={"port": 56700},
            )

        async def parent_producer():
            yield response("d073d5000001")
            started.set()
            await asyncio.to_thread(release.wait)

        async def child_producer():
            yield response("d073d5000002")

        async def collect(factory):
            return [
                record.serial
                async for record in subscribe_udp_sweep(
                    key,
                    factory,
                    caller_deadline=time.monotonic() + 5,
                    observer=None,
                )
            ]

        parent_records = []
        parent_errors = []

        def run_parent():
            try:
                parent_records.extend(asyncio.run(collect(parent_producer)))
            except BaseException as error:
                parent_errors.append(repr(error))

        parent_thread = threading.Thread(target=run_parent)
        parent_thread.start()
        assert started.wait(2)

        pid = os.fork()
        if pid == 0:
            try:
                records = asyncio.run(collect(child_producer))
                os._exit(0 if records == ["d073d5000002"] else 2)
            except BaseException:
                os._exit(3)

        release.set()
        parent_thread.join(5)
        assert not parent_thread.is_alive()
        assert parent_errors == []
        assert parent_records == ["d073d5000001"]
        _, status = os.waitpid(pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr


async def test_shared_facade_preserves_subscriber_device_settings() -> None:
    """Caller-only timeout and retry values do not split the wire sweep."""
    producer = _GatedDiscoveryProducer((_response("d073d5000001", 1),))

    async def _discover_with_packet(*args, **kwargs):
        async for record in producer.factory():
            yield record

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "lifx.network.discovery.udp._discover_with_packet", _discover_with_packet
        )
        first = discover_devices_shared(
            timeout=5,
            broadcast_address="192.0.2.255",
            device_timeout=0.25,
            max_retries=1,
        )
        second = discover_devices_shared(
            timeout=5,
            broadcast_address="192.0.2.255",
            device_timeout=4.0,
            max_retries=7,
        )

        first_record = await anext(first)
        second_record = await anext(second)

        assert producer.calls == 1
        assert (first_record.timeout, first_record.max_retries) == (0.25, 1)
        assert (second_record.timeout, second_record.max_retries) == (4.0, 7)
        await first.aclose()
        await second.aclose()


async def test_shared_facade_transfers_explicit_observer() -> None:
    """The producer emits no ambient event and fan-out emits one caller event."""
    response = _response("d073d5000001", 1)
    seen_observers: list[object | None] = []

    async def _discover_with_packet(*args, **kwargs):
        seen_observers.append(kwargs.get("_observer"))
        yield response

    sink = _DiscoveryObservationSink()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "lifx.network.discovery.udp._discover_with_packet", _discover_with_packet
        )
        monkeypatch.setattr(
            "lifx.network.discovery.udp._current_discovery_observer",
            lambda: sink.observe,
        )
        records = [
            record
            async for record in discover_devices_shared(
                timeout=5,
                broadcast_address="192.0.2.255",
            )
        ]

    assert [record.serial for record in records] == ["d073d5000001"]
    assert seen_observers == [None]
    assert [event.raw_identity for event in sink.observations] == ["d073d5000001"]


async def test_shared_facade_drops_record_when_construction_crosses_deadline() -> None:
    """A record accepted in time cannot be yielded after caller construction."""
    response = _response("d073d5000001", 1)
    base = time.monotonic()
    clock_values = iter((base, base + 1, base + 6))

    class _Clock:
        @staticmethod
        def monotonic() -> float:
            return next(clock_values)

    async def _discover_with_packet(*args, **kwargs):
        yield response

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "lifx.network.discovery.udp._discover_with_packet", _discover_with_packet
        )
        monkeypatch.setattr("lifx.network.discovery.udp.time", _Clock)
        records = [
            record
            async for record in discover_devices_shared(
                timeout=5,
                broadcast_address="192.0.2.255",
            )
        ]

    assert records == []


async def test_shared_facade_drops_record_received_after_deadline() -> None:
    """A shared response delivered after the caller deadline is never constructed."""
    response = _response("d073d5000001", 1)
    base = time.monotonic()
    clock_values = iter((base, base + 6))

    class _Clock:
        @staticmethod
        def monotonic() -> float:
            return next(clock_values)

    async def _discover_with_packet(*args, **kwargs):
        yield response

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "lifx.network.discovery.udp._discover_with_packet", _discover_with_packet
        )
        monkeypatch.setattr("lifx.network.discovery.udp.time", _Clock)
        records = [
            record
            async for record in discover_devices_shared(
                timeout=5,
                broadcast_address="192.0.2.255",
            )
        ]

    assert records == []


class _FakeThread:
    """Minimal lifecycle double for coordinator thread decisions."""

    def __init__(self, *, stop_on_join: bool = False, **_kwargs: object) -> None:
        self.alive = True
        self.stop_on_join = stop_on_join
        self.join_calls = 0

    def start(self) -> None:
        """Keep synthetic thread work under explicit test control."""

    def is_alive(self) -> bool:
        """Report the configured synthetic liveness state."""
        return self.alive

    def join(self, _timeout: float) -> None:
        """Optionally model a thread that finishes during its join window."""
        self.join_calls += 1
        if self.stop_on_join:
            self.alive = False


class _FakeReady:
    """Deterministic replacement for the coordinator readiness event."""

    def __init__(self, result: bool) -> None:
        self.result = result
        self.set_calls = 0

    def wait(self, _timeout: float) -> bool:
        """Return the configured readiness result."""
        return self.result

    def set(self) -> None:
        """Record readiness publication."""
        self.set_calls += 1


class _FakeLoop:
    """Minimal closed/open event-loop double for lifecycle error handling."""

    def __init__(self, *, closed: bool = False) -> None:
        self.closed = closed
        self.stop_calls = 0
        self.closed_calls = 0

    def is_closed(self) -> bool:
        """Return the configured loop state."""
        return self.closed

    def stop(self) -> None:
        """Record a forced stop request."""
        self.stop_calls += 1

    def call_soon_threadsafe(
        self, callback: Callable[..., object], *args: object
    ) -> None:
        """Run a lifecycle callback immediately."""
        callback(*args)

    def run_forever(self) -> None:
        """Return immediately for direct worker-loop teardown tests."""

    async def shutdown_asyncgens(self) -> None:
        """Provide the coroutine expected by the worker teardown path."""

    def run_until_complete(self, coroutine: object) -> None:
        """Close the synthetic coroutine without running another event loop."""
        coroutine.close()  # type: ignore[attr-defined]

    def close(self) -> None:
        """Record deterministic worker-loop closure."""
        self.closed_calls += 1
        self.closed = True


class _ClosingDuringShutdownLoop(_FakeLoop):
    """Loop that closes after shutdown submission but before forced stop."""

    def __init__(self) -> None:
        super().__init__()
        self.is_closed_calls = 0

    def is_closed(self) -> bool:
        """Model the loop closing while the shutdown future times out."""
        self.is_closed_calls += 1
        return self.is_closed_calls > 1


def test_existing_worker_without_loop_times_out_readiness() -> None:
    """A live worker that never publishes its loop fails within the bound."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    coordinator._thread = _FakeThread()  # type: ignore[assignment]
    coordinator._ready = _FakeReady(False)  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="did not start"):
        coordinator._ensure_started()


@pytest.mark.parametrize("expired", [False, True])
def test_existing_worker_readiness_respects_caller_deadline(expired: bool) -> None:
    """A caller budget bounds both readiness precheck and event wait."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    coordinator._thread = _FakeThread()  # type: ignore[assignment]
    coordinator._ready = _FakeReady(False)  # type: ignore[assignment]
    deadline = time.monotonic() + (-1 if expired else 1)

    with pytest.raises(TimeoutError, match="caller deadline expired"):
        coordinator._ensure_started(deadline)


def test_existing_worker_returns_loop_after_readiness_is_published(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller waiting on a starting worker retries after readiness is set."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    loop = _FakeLoop()
    ready = _FakeReady(True)
    coordinator._thread = _FakeThread()  # type: ignore[assignment]
    coordinator._ready = ready  # type: ignore[assignment]

    def publish_loop(_timeout: float) -> bool:
        coordinator._loop = loop  # type: ignore[assignment]
        return True

    monkeypatch.setattr(ready, "wait", publish_loop)

    assert coordinator._ensure_started() is loop


def test_stopping_worker_that_cannot_join_fails_boundedly() -> None:
    """A stuck prior worker cannot be silently replaced by another thread."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    coordinator._thread = _FakeThread()  # type: ignore[assignment]
    coordinator._stopping = True

    with pytest.raises(RuntimeError, match="did not stop"):
        coordinator._ensure_started()


def test_stopping_worker_rejects_expired_caller_before_join() -> None:
    """An expired caller never waits for a stopping worker."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    thread = _FakeThread()
    coordinator._thread = thread  # type: ignore[assignment]
    coordinator._stopping = True

    with pytest.raises(TimeoutError, match="caller deadline expired"):
        coordinator._ensure_started(time.monotonic() - 1)

    assert thread.join_calls == 0


def test_stopped_worker_is_replaced_before_returning_a_loop() -> None:
    """A prior stopping worker is joined before one fresh worker starts."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    prior_thread = _FakeThread(stop_on_join=True)
    coordinator._thread = prior_thread  # type: ignore[assignment]
    coordinator._stopping = True

    try:
        loop = coordinator._ensure_started()
        assert loop is coordinator._loop
        assert prior_thread.join_calls == 1
    finally:
        coordinator.shutdown()


@pytest.mark.parametrize(
    ("ready_result", "message"),
    [(False, "did not start"), (True, "started without a loop")],
)
def test_fresh_worker_must_publish_readiness_and_loop(
    monkeypatch: pytest.MonkeyPatch,
    ready_result: bool,
    message: str,
) -> None:
    """Starting a thread is insufficient until readiness and loop are published."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    ready = _FakeReady(ready_result)
    monkeypatch.setattr(discovery_coordinator.threading, "Event", lambda: ready)
    monkeypatch.setattr(discovery_coordinator.threading, "Thread", _FakeThread)

    with pytest.raises(RuntimeError, match=message):
        coordinator._ensure_started()


def test_fresh_worker_readiness_respects_caller_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh worker's readiness wait uses the public caller budget."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    ready = _FakeReady(False)
    monkeypatch.setattr(discovery_coordinator.threading, "Event", lambda: ready)
    monkeypatch.setattr(discovery_coordinator.threading, "Thread", _FakeThread)

    with pytest.raises(TimeoutError, match="caller deadline expired"):
        coordinator._ensure_started(time.monotonic() + 1)


def test_worker_loop_tolerates_missing_readiness_waiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The worker still closes cleanly if no readiness event is installed."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    loop = _FakeLoop()
    monkeypatch.setattr(discovery_coordinator.asyncio, "new_event_loop", lambda: loop)
    monkeypatch.setattr(
        discovery_coordinator.asyncio, "set_event_loop", lambda _loop: None
    )

    coordinator._run()

    assert loop.closed_calls == 1
    assert coordinator._loop is None
    assert coordinator._thread is None


async def test_prefix_delivery_failure_rejects_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A closed late-subscriber loop cannot join after prefix delivery fails."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    key = _key()
    active = discovery_coordinator._ActiveUdpSweep(
        key=key,
        producer_factory=lambda: _GatedDiscoveryProducer(()).factory(),
        records=[_response("d073d5000001", 1)],
    )
    coordinator._active[key] = active
    stop_checks = 0

    def schedule_stop() -> None:
        nonlocal stop_checks
        stop_checks += 1

    monkeypatch.setattr(coordinator, "_schedule_record", lambda *_args: False)
    monkeypatch.setattr(coordinator, "_schedule_stop_if_idle", schedule_stop)

    await coordinator._register(
        key,
        discovery_coordinator._SubscriptionToken(1),
        active.producer_factory,
        asyncio.get_running_loop(),
        asyncio.Queue(),
        time.monotonic() + 1,
        None,
    )

    assert active.subscribers == {}
    assert stop_checks == 1


def test_detach_submission_race_returns_completed_future(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loop closure between the lifecycle check and submission is harmless."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    coordinator._loop = _FakeLoop()  # type: ignore[assignment]
    coordinator._thread = _FakeThread()  # type: ignore[assignment]

    def fail_submission(coroutine: object, _loop: object) -> object:
        coroutine.close()  # type: ignore[attr-defined]
        raise RuntimeError("synthetic closed loop")

    monkeypatch.setattr(
        discovery_coordinator.asyncio,
        "run_coroutine_threadsafe",
        fail_submission,
    )

    assert (
        coordinator.detach(_key(), discovery_coordinator._SubscriptionToken(1)).result()
        is None
    )


async def test_unknown_and_last_inactive_detach_are_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown tokens and a last subscriber without a producer both detach cleanly."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    key = _key()
    token = discovery_coordinator._SubscriptionToken(1)
    await coordinator._detach(key, token)

    subscriber = discovery_coordinator._Subscriber(
        token=token,
        caller_loop=asyncio.get_running_loop(),
        queue=asyncio.Queue(),
        caller_deadline=time.monotonic() + 1,
        observer=None,
    )
    active = discovery_coordinator._ActiveUdpSweep(
        key=key,
        producer_factory=lambda: _GatedDiscoveryProducer(()).factory(),
        subscribers={token: subscriber},
    )
    coordinator._active[key] = active
    stop_checks = 0

    def schedule_stop() -> None:
        nonlocal stop_checks
        stop_checks += 1

    monkeypatch.setattr(coordinator, "_schedule_stop_if_idle", schedule_stop)
    await coordinator._detach(key, token)

    assert coordinator._active == {}
    assert stop_checks == 1


async def test_closed_subscriber_is_removed_during_production() -> None:
    """A caller-loop closure removes that subscriber without poisoning the sweep."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    key = _key()
    token = discovery_coordinator._SubscriptionToken(1)

    class ClosedLoop:
        def call_soon_threadsafe(self, *_args: object) -> None:
            raise RuntimeError("synthetic closed loop")

    subscriber = discovery_coordinator._Subscriber(
        token=token,
        caller_loop=ClosedLoop(),  # type: ignore[arg-type]
        queue=asyncio.Queue(),
        caller_deadline=time.monotonic() + 1,
        observer=None,
    )

    async def producer():
        yield _response("d073d5000001", 1)

    active = discovery_coordinator._ActiveUdpSweep(
        key=key,
        producer_factory=producer,
        subscribers={token: subscriber},
    )
    coordinator._active[key] = active

    await coordinator._run_producer(active)

    assert active.records == [_response("d073d5000001", 1)]
    assert active.subscribers == {}
    assert key not in coordinator._active


async def test_producer_finaliser_does_not_remove_replacement_sweep() -> None:
    """An obsolete producer cannot delete a newer sweep with the same key."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    key = _key()

    async def producer():
        return
        yield  # noqa: B901

    obsolete = discovery_coordinator._ActiveUdpSweep(
        key=key,
        producer_factory=producer,
    )
    replacement = discovery_coordinator._ActiveUdpSweep(
        key=key,
        producer_factory=producer,
    )
    coordinator._active[key] = replacement

    await coordinator._run_producer(obsolete)

    assert coordinator._active[key] is replacement


async def test_record_delivery_honours_subscriber_deadline() -> None:
    """A scheduled callback rechecks the caller deadline before queueing."""
    token = discovery_coordinator._SubscriptionToken(1)
    queue: asyncio.Queue[object] = asyncio.Queue()
    subscriber = discovery_coordinator._Subscriber(
        token=token,
        caller_loop=asyncio.get_running_loop(),
        queue=queue,  # type: ignore[arg-type]
        caller_deadline=0.0,
        observer=None,
    )

    assert discovery_coordinator._UdpSweepCoordinator._schedule_record(
        subscriber, _response("d073d5000001", 1)
    )
    await asyncio.sleep(0)
    assert queue.empty()


def test_closed_loop_suppresses_terminal_delivery() -> None:
    """Terminal notification is best-effort after a caller loop closes."""

    class ClosedLoop:
        def call_soon_threadsafe(self, *_args: object) -> None:
            raise RuntimeError("synthetic closed loop")

    subscriber = discovery_coordinator._Subscriber(
        token=discovery_coordinator._SubscriptionToken(1),
        caller_loop=ClosedLoop(),  # type: ignore[arg-type]
        queue=asyncio.Queue(),
        caller_deadline=time.monotonic() + 1,
        observer=None,
    )

    discovery_coordinator._UdpSweepCoordinator._schedule_terminal(subscriber, None)


async def test_pending_stop_is_cancelled_by_new_active_sweep() -> None:
    """A sweep appearing during the deferred turn prevents worker shutdown."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    key = _key()
    coordinator._active[key] = discovery_coordinator._ActiveUdpSweep(
        key=key,
        producer_factory=lambda: _GatedDiscoveryProducer(()).factory(),
    )
    coordinator._stop_task = asyncio.current_task()

    await coordinator._stop_after_turn()

    assert coordinator._stop_task is None


async def test_pending_registration_defers_idle_worker_stop() -> None:
    """An accepted cross-thread submission keeps the worker loop alive."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    coordinator._pending_registrations = 1
    coordinator._stop_task = asyncio.current_task()

    await coordinator._stop_after_turn()

    assert coordinator._stopping is False
    assert coordinator._stop_task is None


async def test_registration_acknowledgement_respects_caller_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A queued registration cannot strand a caller past its wall deadline."""
    registration: concurrent.futures.Future[None] = concurrent.futures.Future()
    detach_calls: list[tuple[_UdpSweepKey, object]] = []

    monkeypatch.setattr(
        discovery_coordinator._UDP_SWEEP_COORDINATOR,
        "register",
        lambda *_args, **_kwargs: registration,
    )
    monkeypatch.setattr(
        discovery_coordinator,
        "_detach_abandoned_subscription",
        lambda key, token: detach_calls.append((key, token)),
    )

    started = asyncio.get_running_loop().time()
    records = await _collect(
        _key(),
        _GatedDiscoveryProducer(()).factory,
        caller_deadline=time.monotonic() + 0.03,
    )
    elapsed = asyncio.get_running_loop().time() - started

    assert records == []
    assert elapsed <= 0.3
    registration.set_result(None)
    assert len(detach_calls) == 1


async def test_stopping_worker_join_respects_subscription_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker replacement cannot consume a fixed two-second caller wait."""
    join_timeouts: list[float] = []

    class SlowStoppingThread:
        def is_alive(self) -> bool:
            return True

        def join(self, timeout: float) -> None:
            join_timeouts.append(timeout)
            time.sleep(timeout)

    coordinator = discovery_coordinator._UdpSweepCoordinator()
    coordinator._loop = _FakeLoop()  # type: ignore[assignment]
    coordinator._thread = SlowStoppingThread()  # type: ignore[assignment]
    coordinator._stopping = True

    with monkeypatch.context() as patcher:
        patcher.setattr(
            discovery_coordinator,
            "_UDP_SWEEP_COORDINATOR",
            coordinator,
        )
        started = asyncio.get_running_loop().time()
        records = await _collect(
            _key(),
            _GatedDiscoveryProducer(()).factory,
            caller_deadline=time.monotonic() + 0.03,
        )
        elapsed = asyncio.get_running_loop().time() - started

    assert records == []
    assert elapsed <= 0.3
    assert len(join_timeouts) == 1
    assert 0 < join_timeouts[0]
    assert join_timeouts[0] <= 0.03 or join_timeouts[0] == pytest.approx(
        0.03, abs=0.0002
    )


def test_registration_submission_retries_on_fresh_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loop closure after the guard retries once on a fresh worker."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    loops = [_FakeLoop(), _FakeLoop()]
    submissions = 0
    scheduled: list[object] = []
    submitted: concurrent.futures.Future[None] = concurrent.futures.Future()

    def ensure_started(_caller_deadline: float | None = None) -> _FakeLoop:
        loop = loops[min(submissions, 1)]
        coordinator._loop = loop  # type: ignore[assignment]
        coordinator._stopping = False
        return loop

    def submit(coroutine: object, _loop: object) -> concurrent.futures.Future[None]:
        nonlocal submissions
        submissions += 1
        if submissions == 1:
            raise RuntimeError("synthetic closed loop")
        scheduled.append(coroutine)
        return submitted

    monkeypatch.setattr(coordinator, "_ensure_started", ensure_started)
    monkeypatch.setattr(
        discovery_coordinator.asyncio,
        "run_coroutine_threadsafe",
        submit,
    )

    registration = coordinator.register(
        _key(),
        discovery_coordinator._SubscriptionToken(1),
        _GatedDiscoveryProducer(()).factory,
        _FakeLoop(),  # type: ignore[arg-type]
        asyncio.Queue(),
        0.0,
        None,
    )

    assert registration is submitted
    assert len(scheduled) == 1
    asyncio.run(scheduled[0])  # type: ignore[arg-type]
    submitted.set_result(None)
    assert registration.result() is None
    assert submissions == 2
    assert loops[0].stop_calls == 1
    assert coordinator._pending_registrations == 0


def test_registration_submission_fails_after_bounded_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two loop-closure races fail explicitly without leaking coroutines."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    loops = [_FakeLoop(), _FakeLoop()]
    attempts = 0

    def ensure_started(_caller_deadline: float | None = None) -> _FakeLoop:
        loop = loops[min(attempts, 1)]
        coordinator._loop = loop  # type: ignore[assignment]
        coordinator._stopping = False
        return loop

    def fail_submission(
        _coroutine: object, _loop: object
    ) -> concurrent.futures.Future[None]:
        nonlocal attempts
        attempts += 1
        coordinator._loop = _FakeLoop()  # type: ignore[assignment]
        raise RuntimeError("synthetic closed loop")

    monkeypatch.setattr(coordinator, "_ensure_started", ensure_started)
    monkeypatch.setattr(
        discovery_coordinator.asyncio,
        "run_coroutine_threadsafe",
        fail_submission,
    )

    with pytest.raises(RuntimeError, match="could not be submitted"):
        coordinator.register(
            _key(),
            discovery_coordinator._SubscriptionToken(1),
            _GatedDiscoveryProducer(()).factory,
            _FakeLoop(),  # type: ignore[arg-type]
            asyncio.Queue(),
            0.0,
            None,
        )

    assert attempts == 2
    assert coordinator._pending_registrations == 0


def test_registration_rejects_two_stale_worker_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A loop replaced before submission is never used for registration."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    stale_loop = _FakeLoop()
    current_loop = _FakeLoop()

    def ensure_started(_caller_deadline: float | None = None) -> _FakeLoop:
        coordinator._loop = current_loop  # type: ignore[assignment]
        return stale_loop

    monkeypatch.setattr(coordinator, "_ensure_started", ensure_started)

    with pytest.raises(RuntimeError, match="stopped during registration"):
        coordinator.register(
            _key(),
            discovery_coordinator._SubscriptionToken(1),
            _GatedDiscoveryProducer(()).factory,
            _FakeLoop(),  # type: ignore[arg-type]
            asyncio.Queue(),
            0.0,
            None,
        )


async def test_deadline_expiry_before_registration_ack_detaches_later(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expiry before acknowledgement arranges eventual detachment."""
    registration = discovery_coordinator._completed_future()
    detach_calls: list[tuple[_UdpSweepKey, object]] = []

    monkeypatch.setattr(
        discovery_coordinator._UDP_SWEEP_COORDINATOR,
        "register",
        lambda *_args, **_kwargs: registration,
    )
    monkeypatch.setattr(
        discovery_coordinator,
        "_detach_abandoned_subscription",
        lambda key, token: detach_calls.append((key, token)),
    )
    monkeypatch.setattr(
        discovery_coordinator,
        "time",
        SimpleNamespace(monotonic=lambda: 3.0),
    )

    assert (
        await _collect(
            _key(),
            _GatedDiscoveryProducer(()).factory,
            caller_deadline=2.0,
        )
        == []
    )
    assert len(detach_calls) == 1


async def test_deadline_expiry_after_registration_skips_queue_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Registration delay consumes the same deadline as result delivery."""
    registration = discovery_coordinator._completed_future()
    detach = discovery_coordinator._completed_future()
    detach_calls = 0
    clock = iter((1.0, 3.0))

    monkeypatch.setattr(
        discovery_coordinator._UDP_SWEEP_COORDINATOR,
        "register",
        lambda *_args, **_kwargs: registration,
    )

    def detach_subscription(*_args: object, **_kwargs: object):
        nonlocal detach_calls
        detach_calls += 1
        return detach

    monkeypatch.setattr(
        discovery_coordinator._UDP_SWEEP_COORDINATOR,
        "detach",
        detach_subscription,
    )
    monkeypatch.setattr(
        discovery_coordinator,
        "time",
        SimpleNamespace(monotonic=lambda: next(clock)),
    )

    assert (
        await _collect(
            _key(),
            _GatedDiscoveryProducer(()).factory,
            caller_deadline=2.0,
        )
        == []
    )
    assert detach_calls == 1


async def test_cancellation_during_final_detach_arranges_idempotent_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation while detaching leaves an eventual cleanup callback."""
    registration = discovery_coordinator._completed_future()
    detach: concurrent.futures.Future[None] = concurrent.futures.Future()
    detach_started = asyncio.Event()
    abandoned: list[tuple[_UdpSweepKey, object]] = []
    clock = iter((1.0, 3.0))

    monkeypatch.setattr(
        discovery_coordinator._UDP_SWEEP_COORDINATOR,
        "register",
        lambda *_args, **_kwargs: registration,
    )

    def detach_subscription(*_args: object, **_kwargs: object):
        detach_started.set()
        return detach

    monkeypatch.setattr(
        discovery_coordinator._UDP_SWEEP_COORDINATOR,
        "detach",
        detach_subscription,
    )
    monkeypatch.setattr(
        discovery_coordinator,
        "_detach_abandoned_subscription",
        lambda key, token: abandoned.append((key, token)),
    )
    monkeypatch.setattr(
        discovery_coordinator,
        "time",
        SimpleNamespace(monotonic=lambda: next(clock)),
    )

    collection = asyncio.create_task(
        _collect(
            _key(),
            _GatedDiscoveryProducer(()).factory,
            caller_deadline=2.0,
        )
    )
    await detach_started.wait()
    collection.cancel()

    with pytest.raises(asyncio.CancelledError):
        await collection

    assert abandoned == []
    detach.set_result(None)
    await asyncio.sleep(0)
    assert len(abandoned) == 1


async def test_explicit_shutdown_owns_stop_scheduling() -> None:
    """An explicit shutdown cannot race an independently scheduled idle stop."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    coordinator._stopping = True

    coordinator._schedule_stop_if_idle()

    try:
        assert coordinator._stop_task is None
    finally:
        if coordinator._stop_task is not None:
            coordinator._stop_task.cancel()
            await asyncio.gather(coordinator._stop_task, return_exceptions=True)


@pytest.mark.parametrize(
    ("outcome", "loop_closed", "expected_stop_calls"),
    [
        ("success", False, 1),
        ("runtime", False, 1),
        ("timeout", False, 1),
        ("timeout", True, 0),
        ("stop_runtime", False, 0),
    ],
)
def test_shutdown_bounds_submission_and_completion_failures(
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    loop_closed: bool,
    expected_stop_calls: int,
) -> None:
    """Shutdown closes or force-stops the loop for every submission outcome."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    loop = _FakeLoop(closed=loop_closed)
    thread = _FakeThread()
    coordinator._loop = loop  # type: ignore[assignment]
    coordinator._thread = thread  # type: ignore[assignment]

    class Future:
        def result(self, _timeout: float) -> None:
            if outcome == "timeout":
                raise concurrent.futures.TimeoutError

    def submit(coroutine: object, _loop: object) -> Future:
        if outcome == "runtime":
            coroutine.close()  # type: ignore[attr-defined]
            raise RuntimeError("synthetic closed loop")
        coroutine.close()  # type: ignore[attr-defined]
        return Future()

    monkeypatch.setattr(
        discovery_coordinator.asyncio, "run_coroutine_threadsafe", submit
    )
    if outcome == "stop_runtime":

        def fail_stop(*_args: object) -> None:
            raise RuntimeError("synthetic closed loop")

        monkeypatch.setattr(loop, "call_soon_threadsafe", fail_stop)

    coordinator.shutdown()

    assert loop.stop_calls == expected_stop_calls
    assert thread.join_calls == 1


def test_shutdown_joins_an_already_stopping_worker() -> None:
    """An already-stopping worker is only joined, never resubmitted."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    thread = _FakeThread()
    loop = _FakeLoop()
    coordinator._loop = loop  # type: ignore[assignment]
    coordinator._thread = thread  # type: ignore[assignment]
    coordinator._stopping = True

    coordinator.shutdown()

    assert loop.stop_calls == 0
    assert thread.join_calls == 1


def test_shutdown_explicitly_stops_worker_without_idle_scheduler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synchronous shutdown owns loop stop rather than an idle-task race."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    loop = coordinator._ensure_started()
    thread = coordinator._thread
    assert thread is not None
    monkeypatch.setattr(coordinator, "_schedule_stop_if_idle", lambda: None)

    try:
        coordinator.shutdown()
        assert not thread.is_alive()
    finally:
        if thread.is_alive():
            loop.call_soon_threadsafe(loop.stop)
            thread.join(2)


def test_shutdown_timeout_accepts_loop_that_closed_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A concurrently closed loop needs no redundant forced-stop callback."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    loop = _ClosingDuringShutdownLoop()
    thread = _FakeThread()
    coordinator._loop = loop  # type: ignore[assignment]
    coordinator._thread = thread  # type: ignore[assignment]

    class Future:
        def result(self, _timeout: float) -> None:
            raise concurrent.futures.TimeoutError

    def submit(coroutine: object, _loop: object) -> Future:
        coroutine.close()  # type: ignore[attr-defined]
        return Future()

    monkeypatch.setattr(
        discovery_coordinator.asyncio, "run_coroutine_threadsafe", submit
    )

    coordinator.shutdown()

    assert loop.is_closed_calls == 2
    assert loop.stop_calls == 0
    assert thread.join_calls == 1


async def test_shutdown_coroutine_cancels_tasks_without_scheduling_loop_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation completes before synchronous shutdown owns loop stopping."""
    coordinator = discovery_coordinator._UdpSweepCoordinator()
    key = _key()

    async def wait_forever() -> None:
        await asyncio.Event().wait()

    producer_task = asyncio.create_task(wait_forever())
    active = discovery_coordinator._ActiveUdpSweep(
        key=key,
        producer_factory=lambda: _GatedDiscoveryProducer(()).factory(),
        producer_task=producer_task,
    )
    coordinator._active[key] = active
    stop_checks = 0

    def schedule_stop() -> None:
        nonlocal stop_checks
        stop_checks += 1

    monkeypatch.setattr(coordinator, "_schedule_stop_if_idle", schedule_stop)

    await coordinator._shutdown()
    await coordinator._shutdown()

    assert producer_task.cancelled()
    assert coordinator._active == {}
    assert stop_checks == 0


def test_after_fork_reset_replaces_process_local_state() -> None:
    """The child reset discards inherited coordinator and lock identities."""
    discovery_coordinator._shutdown_udp_coordinator_at_exit()
    previous = discovery_coordinator._UDP_SWEEP_COORDINATOR

    discovery_coordinator._reset_udp_coordinator_after_fork()

    assert discovery_coordinator._UDP_SWEEP_COORDINATOR is not previous
