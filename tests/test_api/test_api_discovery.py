"""Tests for high-level API discovery helper functions.

This module tests:
- discover() - Async generator for device discovery
- discover_mdns() - Async generator for mDNS-based discovery
- find_by_serial() - Find specific device by serial number
- find_by_ip() - Find device by IP address
- find_by_label() - Find device by exact label match
"""

from __future__ import annotations

import asyncio
import inspect
import ipaddress
import logging
from collections.abc import AsyncGenerator, Callable
from types import SimpleNamespace
from typing import ClassVar, cast
from unittest.mock import AsyncMock, patch

import pytest

import lifx
import lifx.api
import lifx.network.discovery.mdns.discovery as mdns_discovery
from lifx.api import (
    discover,
    discover_mdns,
    discover_udp,
    find_by_ip,
    find_by_label,
    find_by_serial,
)
from lifx.devices import Light
from lifx.exceptions import LifxNetworkError, LifxTimeoutError
from lifx.network.address import SocketAddress
from lifx.network.discovery import DiscoveredDevice, DiscoveryResponse, discover_devices
from lifx.network.discovery.mdns.discovery import (
    _MdnsCandidateFailure,
    _MdnsSweepFailure,
)
from lifx.network.discovery.mdns.dns import DnsResourceRecord, SrvData, TxtData
from lifx.network.discovery.udp import _DiscoveryObserver
from lifx.network.message import create_message
from lifx.network.transport import UdpTransport
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Device as DevicePackets
from lifx.protocol.packets import Light as LightPackets
from lifx.protocol.protocol_types import DeviceService, LightHsbk
from tests.conftest import get_free_port
from tests.test_discovery_observation import (
    _capture_discovery_observations,
)


@pytest.mark.emulator
class TestDiscover:
    """Test discover() async generator."""

    async def test_discover_basic(self, emulator_port: int):
        """Test basic discovery with async generator."""
        async for device in discover(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            assert isinstance(device, Light)

    async def test_discover_with_timeout(self, emulator_port: int):
        """Test discovery with custom timeout."""
        async for device in discover(
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            assert device is not None
            break

    async def test_discover_empty_network(self):
        """Test discovery when no devices are present."""
        async for device in discover(
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=get_free_port(),
        ):
            pytest.fail(f"Unexpected yield of {device} from discover.")


class TestDiscoverUdpEntryGate:
    """Freeze the source-specific public contract while discovery is merged."""

    def test_public_signatures_and_exports_are_source_specific(self) -> None:
        """UDP enumeration retains the old signature without a source selector."""
        assert inspect.signature(discover_udp) == inspect.signature(discover)
        assert "transport" not in inspect.signature(discover).parameters
        assert "transport" not in inspect.signature(discover_udp).parameters
        assert lifx.discover_udp is discover_udp
        assert lifx.api.discover_udp is discover_udp
        assert {"discover", "discover_udp", "discover_mdns"} <= set(lifx.__all__)
        assert {"discover", "discover_udp", "discover_mdns"} <= set(lifx.api.__all__)

    async def test_completed_calls_have_fresh_udp_state(self) -> None:
        """A completed public call never replays a prior device."""
        serials = iter(("d073d5123456", "d073d5123457"))

        async def _discover_devices(*args, **kwargs):
            yield DiscoveredDevice(next(serials), "192.0.2.10")

        async def _create_device(discovered: DiscoveredDevice) -> Light:
            return Light(discovered.serial, discovered.ip)

        with (
            patch("lifx.api.discover_devices_shared", side_effect=_discover_devices),
            patch.object(DiscoveredDevice, "create_device", _create_device),
        ):
            first = [device.serial async for device in discover_udp()]
            second = [device.serial async for device in discover_udp()]

        assert first == ["d073d5123456"]
        assert second == ["d073d5123457"]

    async def test_close_synchronously_finalises_udp_delegate(self) -> None:
        """Closing UDP enumeration closes its owned lower-level generator."""
        finalised = False
        discovered = DiscoveredDevice("d073d5123456", "192.0.2.10")
        expected = Light(discovered.serial, discovered.ip)

        async def _discover_devices(*args, **kwargs):
            nonlocal finalised
            try:
                yield discovered
            finally:
                finalised = True

        async def _create_device(_discovered: DiscoveredDevice) -> Light:
            return expected

        with (
            patch("lifx.api.discover_devices_shared", side_effect=_discover_devices),
            patch.object(DiscoveredDevice, "create_device", _create_device),
        ):
            generator = discover_udp()
            assert await anext(generator) is expected
            await generator.aclose()

        assert finalised is True

    async def test_validation_dedup_and_observation_share_one_boundary(self) -> None:
        """Only the first source- and serial-valid response is observed."""
        known_source = 42
        valid_target = b"\x02\x00\x00\x00\x00\x01\x00\x00"
        responses = iter(
            (
                (
                    _build_state_service_packet(known_source + 1, valid_target),
                    ("192.0.2.10", 56700),
                ),
                (
                    _build_state_service_packet(known_source, b"\xff" * 8),
                    ("192.0.2.11", 56700),
                ),
                (
                    _build_state_service_packet(known_source, valid_target),
                    ("192.0.2.12", 56700),
                ),
                (
                    _build_state_service_packet(known_source, valid_target),
                    ("192.0.2.13", 56700),
                ),
            )
        )

        async def _receive(timeout: float = 2.0):
            try:
                return next(responses)
            except StopIteration:
                raise LifxTimeoutError("synthetic completion") from None

        transport = AsyncMock()
        transport.__aenter__ = AsyncMock(return_value=transport)
        transport.__aexit__ = AsyncMock(return_value=False)
        transport.send = AsyncMock()
        transport.receive = _receive

        async def _create_device(discovered: DiscoveredDevice) -> Light:
            return Light(discovered.serial, discovered.ip)

        with (
            patch("lifx.network.discovery.udp.UdpTransport", return_value=transport),
            patch(
                "lifx.network.discovery.udp.allocate_source", return_value=known_source
            ),
            patch.object(DiscoveredDevice, "create_device", _create_device),
            _capture_discovery_observations() as sink,
        ):
            devices = [
                device
                async for device in discover_udp(
                    timeout=0.3,
                    max_response_time=0.01,
                    idle_timeout_multiplier=1.0,
                )
            ]

        assert [device.serial for device in devices] == ["020000000001"]
        assert [(event.source, event.stage) for event in sink.observations] == [
            ("udp", "accepted")
        ]
        assert "020000000001" not in repr(sink)

    async def test_device_construction_cannot_exceed_caller_deadline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Awaited cancellation cleanup cannot extend the UDP call budget."""
        cleanup_started = asyncio.Event()
        cleanup_finished = asyncio.Event()
        force_close = asyncio.Event()
        construction_tasks: list[asyncio.Task[object]] = []

        async def udp_source(*_args: object, **_kwargs: object):
            yield DiscoveredDevice("d073d5123456", "192.0.2.10")

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            try:
                task = asyncio.current_task()
                assert task is not None
                construction_tasks.append(task)
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cleanup_started.set()
                while not force_close.is_set():
                    try:
                        await asyncio.sleep(0.08)
                    except asyncio.CancelledError:
                        continue
                cleanup_finished.set()
                raise
            raise AssertionError("construction resumed")

        def force_close_construction(
            _discovered: DiscoveredDevice,
            _construction: asyncio.Task[object],
        ) -> None:
            force_close.set()

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)
        monkeypatch.setattr(
            DiscoveredDevice,
            "_force_close_construction",
            force_close_construction,
        )

        started = asyncio.get_running_loop().time()
        assert [device async for device in discover_udp(timeout=0.03)] == []
        elapsed = asyncio.get_running_loop().time() - started

        assert cleanup_started.is_set()
        assert cleanup_finished.is_set()
        assert construction_tasks and all(task.done() for task in construction_tasks)
        assert elapsed <= 0.3

    async def test_expired_deadline_skips_device_construction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No product request starts after the public call budget expires."""
        called = False

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            nonlocal called
            called = True
            return Light("d073d5123456", "192.0.2.10")

        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        device = await lifx.api._create_discovered_device(
            DiscoveredDevice("d073d5123456", "192.0.2.10"),
            method="discover_udp",
            deadline=lifx.api.time.monotonic() - 1,
        )

        assert device is None
        assert called is False

    async def test_unbounded_construction_propagates_cancellation_before_task_ownership(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cancellation remains transparent when no deadline task was created."""
        construction_started = asyncio.Event()

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            construction_started.set()
            await asyncio.Event().wait()
            raise AssertionError("construction resumed")

        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)
        construction = asyncio.create_task(
            lifx.api._create_discovered_device(
                DiscoveredDevice("d073d5123456", "192.0.2.10"),
                method="test",
            )
        )
        await asyncio.wait_for(construction_started.wait(), timeout=0.1)

        construction.cancel()

        with pytest.raises(asyncio.CancelledError):
            await construction

    @pytest.mark.parametrize("fails_after_force_close", [False, True])
    async def test_construction_reaper_force_closes_and_consumes_result(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fails_after_force_close: bool,
    ) -> None:
        """Force-close makes cancellation-resistant construction reapable."""
        force_close = asyncio.Event()
        finished = asyncio.Event()

        async def stubborn_construction() -> None:
            try:
                while not force_close.is_set():
                    try:
                        await asyncio.sleep(0.08)
                    except asyncio.CancelledError:
                        continue
                if fails_after_force_close:
                    raise RuntimeError("synthetic late construction failure")
            finally:
                finished.set()

        discovered = DiscoveredDevice("d073d5123456", "192.0.2.10")
        construction = asyncio.create_task(stubborn_construction())
        await asyncio.sleep(0)

        def force_close_construction(_construction: asyncio.Task[object]) -> None:
            assert _construction is construction
            force_close.set()

        monkeypatch.setattr(
            discovered,
            "_force_close_construction",
            force_close_construction,
        )

        await lifx.api._cancel_device_construction(
            discovered,
            construction,  # type: ignore[arg-type]
        )

        assert finished.is_set()
        assert construction.done()


class TestDiscoverMerged:
    """Default discovery merges fully valid UDP and mDNS results per call."""

    @pytest.mark.parametrize(
        "endpoint",
        [
            pytest.param(
                {"broadcast_address": "not-an-address"},
                id="address",
            ),
            pytest.param({"port": 70000}, id="port"),
        ],
    )
    async def test_invalid_udp_endpoint_starts_neither_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
        endpoint: dict[str, object],
    ) -> None:
        """Permanent UDP input errors fail before mDNS or UDP source work."""
        entered: list[str] = []

        async def udp_source(*_args: object, **_kwargs: object):
            entered.append("udp")
            yield DiscoveredDevice("d073d5123456", "192.0.2.10")

        async def mdns_source(*_args: object, **_kwargs: object):
            entered.append("mdns")
            yield Light("d073d5123456", "192.0.2.10")

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)

        with pytest.raises((ValueError, LifxNetworkError)):
            assert [device async for device in discover(**endpoint)] == []

        assert entered == []

    @pytest.mark.parametrize("first_source", ["udp", "mdns"])
    async def test_first_fully_valid_duplicate_wins_without_source_priority(
        self,
        monkeypatch: pytest.MonkeyPatch,
        first_source: str,
    ) -> None:
        """Reversing completion order reverses the retained duplicate instance."""
        serial = "d0:73:d5:12:34:56"
        udp_ready = asyncio.Event()
        mdns_ready = asyncio.Event()
        udp_discovered = DiscoveredDevice(serial, "192.0.2.10")
        udp_device = Light("d073d5123456", udp_discovered.ip)
        mdns_device = Light("D073D5123456", "192.0.2.20")

        async def udp_source(*_args: object, **_kwargs: object):
            await udp_ready.wait()
            yield udp_discovered

        async def mdns_source(*_args: object, **_kwargs: object):
            await mdns_ready.wait()
            yield mdns_device

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            return udp_device

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(
            lifx.api, "_discover_verified_devices_mdns", mdns_source, raising=False
        )
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        generator = discover(timeout=1.0)
        first = asyncio.create_task(anext(generator))
        (udp_ready if first_source == "udp" else mdns_ready).set()
        assert await asyncio.wait_for(first, timeout=0.1) is (
            udp_device if first_source == "udp" else mdns_device
        )
        (mdns_ready if first_source == "udp" else udp_ready).set()
        assert [device async for device in generator] == []

    async def test_empty_leg_does_not_end_the_other_and_results_stream(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty mDNS leg cannot suppress a later productive UDP leg."""
        release_udp = asyncio.Event()
        udp_device = Light("d073d5123456", "192.0.2.10")

        async def udp_source(*_args: object, **_kwargs: object):
            await release_udp.wait()
            yield DiscoveredDevice(udp_device.serial, udp_device.ip)

        async def mdns_source(*_args: object, **_kwargs: object):
            return
            yield  # noqa: B901

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            return udp_device

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(
            lifx.api, "_discover_verified_devices_mdns", mdns_source, raising=False
        )
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        generator = discover(timeout=1.0)
        result = asyncio.create_task(anext(generator))
        await asyncio.sleep(0)
        assert not result.done()
        release_udp.set()
        assert await result is udp_device
        await generator.aclose()

    async def test_observations_are_call_scoped_and_record_merge_disposition(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One call records both contributions and one winner/duplicate pair."""
        serial = "d073d5123456"
        udp_device = Light(serial, "192.0.2.10")
        mdns_device = Light(serial, "192.0.2.20")

        async def udp_source(*_args: object, **kwargs: object):
            observer = cast(
                _DiscoveryObserver | None,
                kwargs.get("_observer"),
            )
            assert observer is not None
            observer("udp", "accepted", serial, None, None, None)
            yield DiscoveredDevice(serial, udp_device.ip)

        async def mdns_source(*_args: object, **kwargs: object):
            observer = cast(
                _DiscoveryObserver | None,
                kwargs.get("_observer"),
            )
            assert observer is not None
            observer("mdns", "accepted", serial, None, None, None)
            yield mdns_device

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            return udp_device

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(
            lifx.api, "_discover_verified_devices_mdns", mdns_source, raising=False
        )
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        with _capture_discovery_observations() as sink:
            assert len([device async for device in discover(timeout=1.0)]) == 1

        observations = [(event.source, event.stage) for event in sink.observations]
        assert set(observations[:2]) == {
            ("udp", "accepted"),
            ("mdns", "accepted"),
        }
        assert {source for source, _stage in observations[2:]} == {"udp", "mdns"}
        assert {stage for _source, stage in observations[2:]} == {
            "winner",
            "duplicate",
        }

        with _capture_discovery_observations() as unrelated:
            assert unrelated.observations == ()

    async def test_one_caller_deadline_bounds_udp_construction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pre-deadline raw record finishing after the deadline is discarded."""
        clock = SimpleNamespace(now=10.0)
        seen_deadlines: list[float] = []

        async def udp_source(*_args: object, **kwargs: object):
            seen_deadlines.append(cast(float, kwargs["_caller_deadline"]))
            yield DiscoveredDevice("d073d5123456", "192.0.2.10")

        async def mdns_source(*_args: object, **_kwargs: object):
            return
            yield  # noqa: B901

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            clock.now = 12.0
            return Light("d073d5123456", "192.0.2.10")

        monkeypatch.setattr(
            lifx.api,
            "time",
            SimpleNamespace(monotonic=lambda: clock.now),
            raising=False,
        )
        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(
            lifx.api, "_discover_verified_devices_mdns", mdns_source, raising=False
        )
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        assert [device async for device in discover(timeout=1.0)] == []
        assert seen_deadlines == [11.0]

    async def test_udp_construction_remains_sequential_while_mdns_is_productive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The UDP pump never fans device construction across the fleet."""
        active = 0
        maximum_active = 0
        mdns_yielded = asyncio.Event()

        async def udp_source(*_args: object, **_kwargs: object):
            for index in range(73):
                yield DiscoveredDevice(f"d073d512{index:04x}", "192.0.2.10")

        async def mdns_source(*_args: object, **_kwargs: object):
            mdns_yielded.set()
            yield Light("020000000001", "192.0.2.20")

        async def create_device(discovered: DiscoveredDevice) -> Light:
            nonlocal active, maximum_active
            active += 1
            maximum_active = max(maximum_active, active)
            await mdns_yielded.wait()
            active -= 1
            return Light(discovered.serial, discovered.ip)

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(
            lifx.api, "_discover_verified_devices_mdns", mdns_source, raising=False
        )
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        devices = [device async for device in discover(timeout=1.0)]

        assert len(devices) == 74
        assert maximum_active == 1

    async def test_each_default_call_starts_fresh_mdns_work(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Success and empty completion retain no mDNS source state."""
        calls = 0

        async def udp_source(*_args: object, **_kwargs: object):
            return
            yield  # noqa: B901

        async def mdns_source(*_args: object, **_kwargs: object):
            nonlocal calls
            calls += 1
            if calls == 1:
                yield Light("d073d5123456", "192.0.2.20")

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(
            lifx.api, "_discover_verified_devices_mdns", mdns_source, raising=False
        )

        assert len([device async for device in discover(timeout=1.0)]) == 1
        assert [device async for device in discover(timeout=1.0)] == []
        assert calls == 2

    async def test_close_reaps_both_owned_source_generators(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Consumer early-close synchronously finalises both source pumps."""
        closed: set[str] = set()

        async def udp_source(*_args: object, **_kwargs: object):
            try:
                await asyncio.Event().wait()
                yield
            finally:
                closed.add("udp")

        async def mdns_source(*_args: object, **_kwargs: object):
            try:
                yield Light("d073d5123456", "192.0.2.20")
                await asyncio.Event().wait()
            finally:
                closed.add("mdns")

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(
            lifx.api, "_discover_verified_devices_mdns", mdns_source, raising=False
        )

        generator = discover(timeout=1.0)
        assert (await anext(generator)).serial == "d073d5123456"
        await generator.aclose()

        assert closed == {"udp", "mdns"}

    async def test_missing_device_payload_fails_after_both_pumps_finish(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A malformed internal device event is an invariant failure, not a skip."""

        async def udp_pump(
            _devices: object,
            queue: asyncio.Queue[object],
            **_kwargs: object,
        ) -> None:
            queue.put_nowait(lifx.api._DiscoveryEvent(kind="device", source="udp"))

        async def mdns_pump(
            _source_factory: object,
            queue: asyncio.Queue[object],
            **_kwargs: object,
        ) -> None:
            queue.put_nowait(lifx.api._DiscoveryEvent(kind="leg_done", source="mdns"))

        monkeypatch.setattr(lifx.api, "_pump_udp_discovery", udp_pump)
        monkeypatch.setattr(lifx.api, "_pump_mdns_discovery", mdns_pump)

        with pytest.raises(RuntimeError, match="contained no device"):
            await anext(discover(timeout=1.0))


class TestMergedDiscoveryFailures:
    """Expected mDNS failures degrade once; defects and cancellation do not."""

    async def test_typed_failure_cannot_also_take_outer_degradation_route(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """One expected failure produces one bounded diagnostic, never two."""
        private_error = LifxNetworkError("private endpoint 192.0.2.99")

        async def udp_source(*_args: object, **_kwargs: object):
            return
            yield  # noqa: B901

        async def mdns_source(*_args: object, **kwargs: object):
            failure_sink = kwargs["failure_sink"]
            failure_sink(
                _MdnsSweepFailure(
                    stage="receive",
                    reason="sweep_receive_network",
                    error_type="LifxNetworkError",
                )
            )
            raise private_error
            yield  # noqa: B901

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)

        with caplog.at_level(logging.DEBUG, logger="lifx.api"):
            assert [device async for device in discover(timeout=1.0)] == []

        diagnostics = [
            record.msg
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("action") == "mdns_unavailable"
        ]
        assert diagnostics == [
            {
                "module": "lifx.api",
                "method": "discover",
                "action": "mdns_unavailable",
                "stage": "receive",
                "reason": "sweep_receive_network",
                "error_type": "LifxNetworkError",
            }
        ]
        assert "private endpoint" not in repr(caplog.records)
        assert "192.0.2.99" not in repr(caplog.records)

    async def test_repeated_cancellation_waits_for_both_source_finalisers(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A second cancellation cannot interrupt owned generator cleanup."""
        cleanup_started = {"udp": asyncio.Event(), "mdns": asyncio.Event()}
        release_cleanup = asyncio.Event()
        closed: set[str] = set()

        async def source(name: str) -> AsyncGenerator[object, None]:
            try:
                await asyncio.Event().wait()
                yield
            finally:
                cleanup_started[name].set()
                await release_cleanup.wait()
                closed.add(name)

        async def udp_source(*_args: object, **_kwargs: object):
            async for value in source("udp"):
                yield value

        async def mdns_source(*_args: object, **_kwargs: object):
            async for value in source("mdns"):
                yield value

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)

        async def collect() -> list[Light]:
            return [device async for device in discover(timeout=10.0)]

        with caplog.at_level(logging.DEBUG, logger="lifx.api"):
            task = asyncio.create_task(collect())
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.wait_for(
                asyncio.gather(
                    cleanup_started["udp"].wait(),
                    cleanup_started["mdns"].wait(),
                ),
                timeout=0.1,
            )
            task.cancel()
            release_cleanup.set()
            with pytest.raises(asyncio.CancelledError):
                await task

        assert closed == {"udp", "mdns"}
        assert not any(
            isinstance(record.msg, dict)
            and record.msg.get("action") == "mdns_unavailable"
            for record in caplog.records
        )

    @pytest.mark.parametrize("failure_point", ["open", "receive"])
    async def test_live_sweep_failure_degrades_to_unchanged_udp_once(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        _allow_public_mdns_discovery: None,
        failure_point: str,
    ) -> None:
        """The real sweep catch reports once while the UDP leg remains productive."""
        private_error = LifxNetworkError("private endpoint 192.0.2.99")
        instances: list[SimpleNamespace] = []

        class FakeTransport:
            def __init__(self, *, log_failure_details: bool = True) -> None:
                self.log_failure_details = log_failure_details
                self.closed = False
                instances.append(self)  # type: ignore[arg-type]

            async def __aenter__(self):
                if failure_point == "open":
                    raise private_error
                return self

            async def __aexit__(self, *_args: object) -> None:
                self.closed = True

            async def send(self, _data: bytes, _address: object = None) -> None:
                return None

            async def receive(self, timeout: float = 5.0):
                del timeout
                raise private_error

        udp_device = Light("d073d5123456", "192.0.2.10")

        async def udp_source(*_args: object, **_kwargs: object):
            yield DiscoveredDevice(udp_device.serial, udp_device.ip)

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            return udp_device

        monkeypatch.setattr(mdns_discovery, "MdnsTransport", FakeTransport)
        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        with caplog.at_level(logging.DEBUG):
            assert [device async for device in discover(timeout=0.3)] == [udp_device]

        diagnostics = [
            record.msg
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("action") == "mdns_unavailable"
        ]
        assert len(diagnostics) == 1
        assert diagnostics[0]["reason"] in {
            "sweep_open_network",
            "sweep_receive_network",
        }
        assert diagnostics[0]["error_type"] == "LifxNetworkError"
        assert instances[0].log_failure_details is False
        if failure_point == "receive":
            assert instances[0].closed is True
        assert "private endpoint" not in repr(caplog.records)
        assert "192.0.2.99" not in repr(caplog.records)

    async def test_live_receive_failure_after_partial_preserves_verified_device(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        _allow_public_mdns_discovery: None,
    ) -> None:
        """A receive failure cannot retract an already verified mDNS result."""
        serial = "d073d5123456"
        instance = "synthetic._lifx._udp.local"
        host = "synthetic-host.local"
        txt = TxtData(
            strings=[f"id={serial}", "p=27", "fw=3.70", "tm=2"],
            pairs={"id": serial, "p": "27", "fw": "3.70", "tm": "2"},
        )
        response = SimpleNamespace(
            header=SimpleNamespace(is_response=True),
            records=[
                DnsResourceRecord(instance, 16, 1, 120, b"txt", txt),
                DnsResourceRecord(
                    instance,
                    33,
                    1,
                    120,
                    b"srv",
                    SrvData(priority=0, weight=0, port=56700, target=host),
                ),
                DnsResourceRecord(
                    host,
                    1,
                    1,
                    120,
                    ipaddress.ip_address("192.0.2.20").packed,
                    "192.0.2.20",
                ),
            ],
        )

        class FakeTransport:
            def __init__(self, *, log_failure_details: bool = True) -> None:
                self.log_failure_details = log_failure_details
                self.receives: list[object] = [
                    (b"packet", ("192.0.2.1", 5353)),
                    LifxNetworkError("private post-result endpoint"),
                ]

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args: object) -> None:
                return None

            async def send(self, _data: bytes, _address: object = None) -> None:
                return None

            async def receive(self, timeout: float = 5.0):
                del timeout
                result = self.receives.pop(0)
                if isinstance(result, BaseException):
                    raise result
                return result

        class FakeConnection:
            def __init__(self, **kwargs: object) -> None:
                self.serial = cast(str, kwargs["serial"])

            async def request(self, _packet: object, timeout: float | None = None):
                del timeout
                return LightPackets.StateColor(
                    color=LightHsbk(
                        hue=21845,
                        saturation=32768,
                        brightness=49151,
                        kelvin=4000,
                    ),
                    power=65535,
                    label="Verified",  # type: ignore[arg-type]
                )

            async def close(self) -> None:
                return None

        async def udp_source(*_args: object, **_kwargs: object):
            return
            yield  # noqa: B901

        monkeypatch.setattr(mdns_discovery, "MdnsTransport", FakeTransport)
        monkeypatch.setattr(
            mdns_discovery, "parse_dns_response", lambda _data: response
        )
        monkeypatch.setattr(mdns_discovery, "DeviceConnection", FakeConnection)
        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)

        with caplog.at_level(logging.DEBUG):
            devices = [device async for device in discover(timeout=0.3)]

        assert [device.serial for device in devices] == [serial]
        diagnostics = [
            record.msg
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("action") == "mdns_unavailable"
        ]
        assert len(diagnostics) == 1
        assert diagnostics[0]["reason"] == "sweep_receive_network"
        assert "private post-result endpoint" not in repr(caplog.records)

    @pytest.mark.parametrize(
        ("reason", "error_type"),
        [
            ("candidate_connect", "LifxConnectionError"),
            ("candidate_timeout", "LifxTimeoutError"),
            ("candidate_protocol", "LifxProtocolError"),
            ("candidate_unsupported", "LifxUnsupportedDeviceError"),
            ("candidate_identity", "_MdnsCandidateIdentityError"),
            ("candidate_response", "_MdnsCandidateResponseError"),
        ],
    )
    async def test_candidate_failure_logs_once_and_later_candidate_survives(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        reason: str,
        error_type: str,
    ) -> None:
        """Every expected candidate drop stays local and value-suppressed."""
        expected = Light("d073d5123456", "192.0.2.20")

        async def udp_source(*_args: object, **_kwargs: object):
            return
            yield  # noqa: B901

        async def mdns_source(*_args: object, **kwargs: object):
            kwargs["failure_sink"](
                _MdnsCandidateFailure(
                    stage="request",
                    reason=reason,
                    error_type=error_type,
                )
            )
            yield expected

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)

        with caplog.at_level(logging.DEBUG, logger="lifx.api"):
            assert [device async for device in discover(timeout=1.0)] == [expected]

        diagnostics = [
            record.msg
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("action") == "mdns_unavailable"
        ]
        assert len(diagnostics) == 1
        assert diagnostics[0]["reason"] == reason
        assert diagnostics[0]["error_type"] == error_type

    async def test_unexpected_mdns_error_fails_fast_after_udp_cleanup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A programming error propagates only after the UDP source closes."""
        udp_closed = asyncio.Event()

        async def udp_source(*_args: object, **_kwargs: object):
            try:
                await asyncio.Event().wait()
                yield
            finally:
                udp_closed.set()

        async def mdns_source(*_args: object, **_kwargs: object):
            raise RuntimeError("synthetic invariant failure")
            yield  # noqa: B901

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)

        with pytest.raises(RuntimeError, match="synthetic invariant failure"):
            await asyncio.wait_for(
                anext(discover(timeout=10.0)),
                timeout=0.1,
            )
        assert udp_closed.is_set()


class TestFindBySerialRace:
    """Serial lookup races exact shared-UDP and verified-mDNS matches."""

    @pytest.mark.parametrize(
        "endpoint",
        [
            pytest.param(
                {"broadcast_address": "not-an-address"},
                id="address",
            ),
            pytest.param({"port": 70000}, id="port"),
        ],
    )
    async def test_valid_serial_with_invalid_udp_endpoint_starts_neither_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
        endpoint: dict[str, object],
    ) -> None:
        """Endpoint validation precedes both legs of a valid serial race."""
        entered: list[str] = []

        async def udp_source(*_args: object, **_kwargs: object):
            entered.append("udp")
            yield DiscoveredDevice("d073d5123456", "192.0.2.10")

        async def mdns_source(*_args: object, **_kwargs: object):
            entered.append("mdns")
            yield Light("d073d5123456", "192.0.2.10")

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)

        with pytest.raises((ValueError, LifxNetworkError)):
            await find_by_serial("d073d5123456", **endpoint)

        assert entered == []

    async def test_udp_winner_construction_cannot_exceed_caller_deadline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Awaited cancellation cleanup cannot extend the serial race budget."""
        cleanup_started = asyncio.Event()
        cleanup_finished = asyncio.Event()
        force_close = asyncio.Event()
        construction_tasks: list[asyncio.Task[object]] = []

        async def udp_source(*_args: object, **_kwargs: object):
            yield DiscoveredDevice("d073d5123456", "192.0.2.10")

        async def mdns_source(*_args: object, **_kwargs: object):
            return
            yield  # noqa: B901

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            try:
                task = asyncio.current_task()
                assert task is not None
                construction_tasks.append(task)
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cleanup_started.set()
                while not force_close.is_set():
                    try:
                        await asyncio.sleep(0.08)
                    except asyncio.CancelledError:
                        continue
                cleanup_finished.set()
                raise
            raise AssertionError("construction resumed")

        def force_close_construction(
            _discovered: DiscoveredDevice,
            _construction: asyncio.Task[object],
        ) -> None:
            force_close.set()

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)
        monkeypatch.setattr(
            DiscoveredDevice,
            "_force_close_construction",
            force_close_construction,
        )

        started = asyncio.get_running_loop().time()
        assert await find_by_serial("d073d5123456", timeout=0.03) is None
        elapsed = asyncio.get_running_loop().time() - started

        assert cleanup_started.is_set()
        assert cleanup_finished.is_set()
        assert construction_tasks and all(task.done() for task in construction_tasks)
        assert elapsed <= 0.3

    @pytest.mark.parametrize("winner_source", ["udp", "mdns"])
    async def test_find_by_serial_either_source_wins_after_both_close(
        self,
        monkeypatch: pytest.MonkeyPatch,
        winner_source: str,
    ) -> None:
        """Literal source completion order selects the fully reaped winner."""
        serial = "d073d5123456"
        started = {"udp": asyncio.Event(), "mdns": asyncio.Event()}
        release = {"udp": asyncio.Event(), "mdns": asyncio.Event()}
        closed: set[str] = set()
        udp_discovered = DiscoveredDevice(serial, "192.0.2.10")
        udp_device = Light(serial, udp_discovered.ip)
        mdns_device = Light(serial, "192.0.2.20")

        async def udp_source(*_args: object, **_kwargs: object):
            started["udp"].set()
            try:
                await release["udp"].wait()
                yield udp_discovered
                await asyncio.Event().wait()
            finally:
                closed.add("udp")

        async def mdns_source(*_args: object, **_kwargs: object):
            started["mdns"].set()
            try:
                await release["mdns"].wait()
                yield mdns_device
                await asyncio.Event().wait()
            finally:
                closed.add("mdns")

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            return udp_device

        monkeypatch.setattr(lifx.api, "discover_devices", udp_source)
        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        lookup = asyncio.create_task(find_by_serial(serial, timeout=1.0))
        await asyncio.wait_for(
            asyncio.gather(started["udp"].wait(), started["mdns"].wait()),
            timeout=0.1,
        )
        release[winner_source].set()

        assert await asyncio.wait_for(lookup, timeout=0.1) is (
            udp_device if winner_source == "udp" else mdns_device
        )
        assert closed == {"udp", "mdns"}

    async def test_find_by_serial_failed_leg_cannot_mask_udp_match(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An expected mDNS failure is terminal only for the mDNS leg."""
        serial = "d073d5123456"
        release_udp = asyncio.Event()
        mdns_failed = asyncio.Event()
        udp_device = Light(serial, "192.0.2.10")

        async def udp_source(*_args: object, **_kwargs: object):
            await release_udp.wait()
            yield DiscoveredDevice(serial, udp_device.ip)

        async def mdns_source(*_args: object, **kwargs: object):
            mdns_failed.set()
            failure_sink = cast(Callable[[object], None], kwargs["failure_sink"])
            failure_sink(
                _MdnsSweepFailure(
                    stage="receive",
                    reason="sweep_receive_network",
                    error_type="LifxNetworkError",
                )
            )
            raise LifxNetworkError("synthetic expected failure")
            yield  # noqa: B901

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            return udp_device

        monkeypatch.setattr(lifx.api, "discover_devices", udp_source)
        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        lookup = asyncio.create_task(find_by_serial(serial, timeout=1.0))
        await asyncio.wait_for(mdns_failed.wait(), timeout=0.1)
        assert not lookup.done()
        release_udp.set()
        assert await lookup is udp_device

    @pytest.mark.parametrize(
        "serial",
        ["", ":-:", "not-a-serial", "d073d512345", "d073d51234567"],
    )
    async def test_find_by_serial_malformed_input_starts_no_network_work(
        self,
        monkeypatch: pytest.MonkeyPatch,
        serial: str,
    ) -> None:
        """Malformed serials preserve the public no-network ``None`` result."""

        async def unexpected_source(*_args: object, **_kwargs: object):
            pytest.fail("serial validation must precede source creation")
            yield

        monkeypatch.setattr(lifx.api, "discover_devices", unexpected_source)
        monkeypatch.setattr(lifx.api, "discover_devices_shared", unexpected_source)
        monkeypatch.setattr(
            lifx.api, "_discover_verified_devices_mdns", unexpected_source
        )

        assert await find_by_serial(serial, timeout=1.0) is None

    async def test_find_by_serial_intentionally_normalises_ascii_spaces(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Serial.from_string's ASCII-space stripping reaches the exact race."""
        serial = "d073d5123456"
        expected = Light(serial, "192.0.2.20")

        async def udp_source(*_args: object, **_kwargs: object):
            return
            yield  # noqa: B901

        async def mdns_source(*_args: object, **_kwargs: object):
            yield expected

        monkeypatch.setattr(lifx.api, "discover_devices", udp_source)
        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)

        assert await find_by_serial("d0 73 d5 12 34 56", timeout=1.0) is expected

    async def test_find_by_serial_unexpected_failure_reaps_other_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Programming errors fail fast only after loser cleanup."""
        udp_closed = asyncio.Event()

        async def udp_source(*_args: object, **_kwargs: object):
            try:
                await asyncio.Event().wait()
                yield
            finally:
                udp_closed.set()

        async def mdns_source(*_args: object, **_kwargs: object):
            raise RuntimeError("synthetic lookup invariant failure")
            yield  # noqa: B901

        monkeypatch.setattr(lifx.api, "discover_devices", udp_source)
        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)

        with pytest.raises(RuntimeError, match="synthetic lookup invariant failure"):
            await asyncio.wait_for(find_by_serial("d073d5123456"), timeout=0.1)
        assert udp_closed.is_set()

    async def test_find_by_serial_construction_crossing_deadline_returns_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Replay and construction remain bounded by the lookup's wall deadline."""
        clock = SimpleNamespace(now=10.0)
        seen_deadlines: list[float] = []

        async def udp_source(*_args: object, **kwargs: object):
            seen_deadlines.append(cast(float, kwargs["_caller_deadline"]))
            yield DiscoveredDevice("d073d5123456", "192.0.2.10")

        async def mdns_source(*_args: object, **_kwargs: object):
            return
            yield  # noqa: B901

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            clock.now = 12.0
            return Light("d073d5123456", "192.0.2.10")

        monkeypatch.setattr(
            lifx.api,
            "time",
            SimpleNamespace(monotonic=lambda: clock.now),
            raising=False,
        )
        monkeypatch.setattr(lifx.api, "discover_devices", udp_source)
        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        assert await find_by_serial("d073d5123456", timeout=1.0) is None
        assert seen_deadlines == [11.0]

    def test_find_by_serial_signature_has_no_source_selector(self) -> None:
        """Serial lookup remains dual-source without caller routing control."""
        assert "transport" not in inspect.signature(find_by_serial).parameters
        assert "source" not in inspect.signature(find_by_serial).parameters

    async def test_zero_timeout_starts_no_serial_source_work(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An exhausted caller deadline returns before consuming either source."""
        consumed = False

        async def source(*_args: object, **_kwargs: object):
            nonlocal consumed
            consumed = True
            yield DiscoveredDevice("d073d5123456", "192.0.2.10")

        monkeypatch.setattr(lifx.api, "discover_devices_shared", source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", source)

        assert await find_by_serial("d073d5123456", timeout=0.0) is None
        assert consumed is False

    @pytest.mark.parametrize(
        ("source", "message"),
        [
            ("mdns", "mDNS serial lookup event contained no device"),
            ("udp", "UDP serial lookup event contained no discovery record"),
        ],
    )
    async def test_serial_winner_requires_its_source_payload(
        self,
        monkeypatch: pytest.MonkeyPatch,
        source: str,
        message: str,
    ) -> None:
        """Each race winner must carry the payload promised by its source."""

        async def udp_pump(
            _devices: object,
            queue: asyncio.Queue[object],
            **_kwargs: object,
        ) -> None:
            kind = "device" if source == "udp" else "leg_done"
            queue.put_nowait(lifx.api._DiscoveryEvent(kind=kind, source="udp"))

        async def mdns_pump(
            _source_factory: object,
            queue: asyncio.Queue[object],
            **_kwargs: object,
        ) -> None:
            kind = "device" if source == "mdns" else "leg_done"
            queue.put_nowait(lifx.api._DiscoveryEvent(kind=kind, source="mdns"))

        monkeypatch.setattr(lifx.api, "_pump_udp_serial_lookup", udp_pump)
        monkeypatch.setattr(lifx.api, "_pump_mdns_serial_lookup", mdns_pump)

        with pytest.raises(RuntimeError, match=message):
            await find_by_serial("d073d5123456", timeout=1.0)


class TestDiscoveryPumpBoundaries:
    """Directly prove deadline and failure behaviour at source-pump seams."""

    async def test_cancel_and_reap_accepts_no_owned_tasks(self) -> None:
        """An empty aggregate cleanup is an immediate no-op."""
        await lifx.api._cancel_and_reap([])

    async def test_udp_enumeration_pump_surfaces_unexpected_failure(self) -> None:
        """A UDP producer defect becomes one fatal event before completion."""
        queue: asyncio.Queue[object] = asyncio.Queue()
        fatal_errors: dict[object, BaseException] = {}

        async def records():
            raise RuntimeError("synthetic UDP invariant failure")
            yield  # noqa: B901

        await lifx.api._pump_udp_discovery(
            records(),
            queue,
            deadline=float("inf"),
            fatal_errors=fatal_errors,
        )

        fatal = queue.get_nowait()
        done = queue.get_nowait()
        assert isinstance(fatal, lifx.api._DiscoveryEvent)
        assert (fatal.kind, fatal.source, fatal.error_type) == (
            "fatal",
            "udp",
            "RuntimeError",
        )
        assert isinstance(fatal_errors["udp"], RuntimeError)
        assert isinstance(done, lifx.api._DiscoveryEvent)
        assert done.kind == "leg_done"

    async def test_udp_pump_discards_device_constructed_after_deadline(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A construction completing after the wall deadline is never queued."""
        clock = SimpleNamespace(now=10.0)
        queue: asyncio.Queue[object] = asyncio.Queue()
        fatal_errors: dict[object, BaseException] = {}

        async def records():
            yield DiscoveredDevice("d073d5123456", "192.0.2.10")

        async def create_device(
            _discovered: DiscoveredDevice,
            *,
            method: str,
            deadline: float,
        ) -> Light:
            assert method == "discover"
            assert deadline == 11.0
            clock.now = 12.0
            return Light("d073d5123456", "192.0.2.10")

        monkeypatch.setattr(
            lifx.api,
            "time",
            SimpleNamespace(monotonic=lambda: clock.now),
        )
        monkeypatch.setattr(lifx.api, "_create_discovered_device", create_device)

        await lifx.api._pump_udp_discovery(
            records(),
            queue,
            deadline=11.0,
            fatal_errors=fatal_errors,
        )

        event = queue.get_nowait()
        assert isinstance(event, lifx.api._DiscoveryEvent)
        assert (event.kind, event.source) == ("leg_done", "udp")
        assert queue.empty()
        assert fatal_errors == {}

    @pytest.mark.parametrize("source", ["udp", "mdns"])
    async def test_enumeration_pump_rejects_records_after_deadline(
        self, source: str
    ) -> None:
        """Neither enumeration leg may enqueue a candidate after its deadline."""
        queue: asyncio.Queue[object] = asyncio.Queue()
        fatal_errors: dict[object, BaseException] = {}

        if source == "udp":

            async def udp_records():
                yield DiscoveredDevice("d073d5123456", "192.0.2.10")

            await lifx.api._pump_udp_discovery(
                udp_records(),
                queue,
                deadline=0.0,
                fatal_errors=fatal_errors,
            )
        else:

            async def mdns_records(_failure_sink: object):
                yield Light("d073d5123456", "192.0.2.20")

            await lifx.api._pump_mdns_discovery(
                mdns_records,
                queue,
                deadline=0.0,
                fatal_errors=fatal_errors,
            )

        event = queue.get_nowait()
        assert isinstance(event, lifx.api._DiscoveryEvent)
        assert (event.kind, event.source) == ("leg_done", source)
        assert queue.empty()
        assert fatal_errors == {}

    @pytest.mark.parametrize("source", ["udp", "mdns"])
    async def test_serial_pump_rejects_records_after_deadline(
        self, source: str
    ) -> None:
        """Neither serial leg may compare a record after its deadline."""
        queue: asyncio.Queue[object] = asyncio.Queue()
        fatal_errors: dict[object, BaseException] = {}

        if source == "udp":

            async def udp_records():
                yield DiscoveredDevice("d073d5123456", "192.0.2.10")

            await lifx.api._pump_udp_serial_lookup(
                udp_records(),
                queue,
                serial="d073d5123456",
                deadline=0.0,
                fatal_errors=fatal_errors,
            )
        else:

            async def mdns_records(_failure_sink: object):
                yield Light("d073d5123456", "192.0.2.20")

            await lifx.api._pump_mdns_serial_lookup(
                mdns_records,
                queue,
                serial="d073d5123456",
                deadline=0.0,
                fatal_errors=fatal_errors,
            )

        event = queue.get_nowait()
        assert isinstance(event, lifx.api._DiscoveryEvent)
        assert (event.kind, event.source) == ("leg_done", source)
        assert queue.empty()
        assert fatal_errors == {}

    async def test_udp_serial_pump_surfaces_malformed_identity(self) -> None:
        """A malformed validated UDP identity remains a fatal invariant error."""
        queue: asyncio.Queue[object] = asyncio.Queue()
        fatal_errors: dict[object, BaseException] = {}

        async def records():
            yield DiscoveredDevice("malformed", "192.0.2.10")

        await lifx.api._pump_udp_serial_lookup(
            records(),
            queue,
            serial="d073d5123456",
            deadline=float("inf"),
            fatal_errors=fatal_errors,
        )

        fatal = queue.get_nowait()
        done = queue.get_nowait()
        assert isinstance(fatal, lifx.api._DiscoveryEvent)
        assert (fatal.kind, fatal.source, fatal.error_type) == (
            "fatal",
            "udp",
            "ValueError",
        )
        assert isinstance(fatal_errors["udp"], ValueError)
        assert isinstance(done, lifx.api._DiscoveryEvent)
        assert done.kind == "leg_done"

    async def test_udp_serial_pump_ignores_a_valid_non_match(self) -> None:
        """A valid non-matching UDP record completes without a winner."""
        queue: asyncio.Queue[object] = asyncio.Queue()

        async def records():
            yield DiscoveredDevice("d073d5123457", "192.0.2.10")

        await lifx.api._pump_udp_serial_lookup(
            records(),
            queue,
            serial="d073d5123456",
            deadline=float("inf"),
            fatal_errors={},
        )

        event = queue.get_nowait()
        assert isinstance(event, lifx.api._DiscoveryEvent)
        assert event.kind == "leg_done"
        assert queue.empty()

    async def test_mdns_serial_pump_ignores_a_valid_non_match(self) -> None:
        """A valid non-matching mDNS record completes without a winner."""
        queue: asyncio.Queue[object] = asyncio.Queue()

        async def records(_failure_sink: object):
            yield Light("d073d5123457", "192.0.2.20")

        await lifx.api._pump_mdns_serial_lookup(
            records,
            queue,
            serial="d073d5123456",
            deadline=float("inf"),
            fatal_errors={},
        )

        event = queue.get_nowait()
        assert isinstance(event, lifx.api._DiscoveryEvent)
        assert event.kind == "leg_done"
        assert queue.empty()

    @pytest.mark.parametrize("serial_lookup", [False, True])
    async def test_mdns_pump_converts_unreported_network_failure_once(
        self, serial_lookup: bool
    ) -> None:
        """An untyped mDNS network failure becomes one bounded absorbed event."""
        queue: asyncio.Queue[object] = asyncio.Queue()

        async def source(_failure_sink: object):
            raise LifxNetworkError("synthetic endpoint")
            yield  # noqa: B901

        if serial_lookup:
            await lifx.api._pump_mdns_serial_lookup(
                source,
                queue,
                serial="d073d5123456",
                deadline=float("inf"),
                fatal_errors={},
            )
        else:
            await lifx.api._pump_mdns_discovery(
                source,
                queue,
                deadline=float("inf"),
                fatal_errors={},
            )

        absorbed = queue.get_nowait()
        done = queue.get_nowait()
        assert isinstance(absorbed, lifx.api._DiscoveryEvent)
        assert (
            absorbed.kind,
            absorbed.source,
            absorbed.reason,
            absorbed.error_type,
        ) == ("absorbed", "mdns", "sweep_receive_network", "LifxNetworkError")
        assert isinstance(done, lifx.api._DiscoveryEvent)
        assert done.kind == "leg_done"


class TestFindBySerialRaceLifecycle:
    """Repeated and concurrent serial races retain no per-call state."""

    async def test_find_by_serial_both_no_match_reaps_both_sources(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``None`` is returned only after both empty legs finalise."""
        closed: set[str] = set()

        async def source(name: str) -> AsyncGenerator[object, None]:
            try:
                return
                yield
            finally:
                closed.add(name)

        async def udp_source(*_args: object, **_kwargs: object):
            async for value in source("udp"):
                yield value

        async def mdns_source(*_args: object, **_kwargs: object):
            async for value in source("mdns"):
                yield value

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)

        assert await find_by_serial("d073d5123456", timeout=1.0) is None
        assert closed == {"udp", "mdns"}

    async def test_find_by_serial_repeated_outcomes_start_fresh_sources(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Winner, failure, and no-match outcomes are never retained."""
        serial = "d073d5123456"
        udp_calls = 0
        mdns_calls = 0
        udp_winner = Light(serial, "192.0.2.10")
        mdns_winner = Light(serial, "192.0.2.20")

        async def udp_source(*_args: object, **_kwargs: object):
            nonlocal udp_calls
            udp_calls += 1
            if udp_calls in {1, 4}:
                yield DiscoveredDevice(serial, udp_winner.ip)

        async def mdns_source(*_args: object, **kwargs: object):
            nonlocal mdns_calls
            mdns_calls += 1
            if mdns_calls == 2:
                yield mdns_winner
            elif mdns_calls == 3:
                failure_sink = cast(Callable[[object], None], kwargs["failure_sink"])
                failure_sink(
                    _MdnsSweepFailure(
                        stage="receive",
                        reason="sweep_receive_network",
                        error_type="LifxNetworkError",
                    )
                )
                raise LifxNetworkError("synthetic expected failure")

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            return udp_winner

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        results = [
            await find_by_serial(serial, timeout=1.0),
            await find_by_serial(serial, timeout=1.0),
            await find_by_serial(serial, timeout=1.0),
            await find_by_serial(serial, timeout=1.0),
        ]

        assert results == [udp_winner, mdns_winner, None, udp_winner]
        assert (udp_calls, mdns_calls) == (4, 4)

    @pytest.mark.parametrize(
        "targets",
        [
            ("d073d5123456", "d073d5123456"),
            ("d073d5123456", "d073d5123457"),
        ],
    )
    async def test_find_by_serial_concurrent_calls_keep_results_isolated(
        self,
        monkeypatch: pytest.MonkeyPatch,
        targets: tuple[str, str],
    ) -> None:
        """Same- and different-serial callers cannot exchange winners."""
        udp_calls = 0
        mdns_calls = 0

        async def udp_source(*_args: object, **_kwargs: object):
            nonlocal udp_calls
            udp_calls += 1
            invocation = udp_calls
            for index, serial in enumerate(("d073d5123456", "d073d5123457")):
                yield DiscoveredDevice(serial, f"192.0.2.{invocation * 10 + index}")

        async def mdns_source(*_args: object, **_kwargs: object):
            nonlocal mdns_calls
            mdns_calls += 1
            return
            yield  # noqa: B901

        async def create_device(discovered: DiscoveredDevice) -> Light:
            return Light(discovered.serial, discovered.ip)

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        results = await asyncio.gather(
            *(find_by_serial(target, timeout=1.0) for target in targets)
        )

        assert [
            result.serial if result is not None else None for result in results
        ] == [*targets]
        assert (udp_calls, mdns_calls) == (2, 2)
        if targets[0] == targets[1]:
            assert results[0] is not None and results[1] is not None
            assert results[0].ip != results[1].ip

    async def test_find_by_serial_cancellation_reaps_blocked_sources(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Caller cancellation propagates only after both blocked legs close."""
        started = {"udp": asyncio.Event(), "mdns": asyncio.Event()}
        closed: set[str] = set()

        async def source(name: str) -> AsyncGenerator[object, None]:
            started[name].set()
            try:
                await asyncio.Event().wait()
                yield
            finally:
                closed.add(name)

        async def udp_source(*_args: object, **_kwargs: object):
            async for value in source("udp"):
                yield value

        async def mdns_source(*_args: object, **_kwargs: object):
            async for value in source("mdns"):
                yield value

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)

        lookup = asyncio.create_task(find_by_serial("d073d5123456", timeout=10.0))
        await asyncio.gather(started["udp"].wait(), started["mdns"].wait())
        lookup.cancel()
        with pytest.raises(asyncio.CancelledError):
            await lookup

        assert closed == {"udp", "mdns"}

    async def test_find_by_serial_cancellation_after_match_waits_for_cleanup(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Cancellation after a queued match cannot interrupt finalisers."""
        cleanup_started = {"udp": asyncio.Event(), "mdns": asyncio.Event()}
        release_cleanup = asyncio.Event()
        closed: set[str] = set()
        serial = "d073d5123456"

        async def udp_source(*_args: object, **_kwargs: object):
            try:
                yield DiscoveredDevice(serial, "192.0.2.10")
            finally:
                cleanup_started["udp"].set()
                await release_cleanup.wait()
                closed.add("udp")

        async def mdns_source(*_args: object, **_kwargs: object):
            try:
                await asyncio.Event().wait()
                yield
            finally:
                cleanup_started["mdns"].set()
                await release_cleanup.wait()
                closed.add("mdns")

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)

        lookup = asyncio.create_task(find_by_serial(serial, timeout=10.0))
        await asyncio.wait_for(
            asyncio.gather(
                cleanup_started["udp"].wait(),
                cleanup_started["mdns"].wait(),
            ),
            timeout=0.1,
        )
        lookup.cancel()
        release_cleanup.set()
        with pytest.raises(asyncio.CancelledError):
            await lookup

        assert closed == {"udp", "mdns"}

    async def test_find_by_serial_construction_failure_follows_source_teardown(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A failed UDP construction runs only after both legs are closed."""
        serial = "d073d5123456"
        closed: set[str] = set()

        async def udp_source(*_args: object, **_kwargs: object):
            try:
                yield DiscoveredDevice(serial, "192.0.2.10")
            finally:
                closed.add("udp")

        async def mdns_source(*_args: object, **_kwargs: object):
            try:
                await asyncio.Event().wait()
                yield
            finally:
                closed.add("mdns")

        async def create_device(_discovered: DiscoveredDevice) -> Light:
            assert closed == {"udp", "mdns"}
            raise TypeError("synthetic constructor failure")

        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        with caplog.at_level(logging.ERROR, logger="lifx.api"):
            assert await find_by_serial(serial, timeout=1.0) is None

        diagnostic = next(
            record.msg
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("action") == "device_construction_failed"
        )
        assert diagnostic["method"] == "find_by_serial"

    async def test_find_by_serial_late_replay_uses_original_caller_deadline(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A late replay exposes less than a fresh window and cannot extend it."""
        clock = SimpleNamespace(now=10.0)
        remaining_windows: list[float] = []
        serial = "d073d5123456"

        async def udp_source(*_args: object, **kwargs: object):
            deadline = cast(float, kwargs["_caller_deadline"])
            clock.now = 10.75
            remaining_windows.append(deadline - clock.now)
            yield DiscoveredDevice(serial, "192.0.2.10")

        async def mdns_source(*_args: object, **_kwargs: object):
            return
            yield  # noqa: B901

        async def create_device(discovered: DiscoveredDevice) -> Light:
            return Light(discovered.serial, discovered.ip)

        monkeypatch.setattr(
            lifx.api,
            "time",
            SimpleNamespace(monotonic=lambda: clock.now),
            raising=False,
        )
        monkeypatch.setattr(lifx.api, "discover_devices_shared", udp_source)
        monkeypatch.setattr(lifx.api, "_discover_verified_devices_mdns", mdns_source)
        monkeypatch.setattr(DiscoveredDevice, "create_device", create_device)

        result = await find_by_serial(serial, timeout=1.0)

        assert result is not None
        assert remaining_windows == [0.25]


@pytest.mark.emulator
class TestFindBySerial:
    """Test find_by_serial() helper function."""

    async def test_find_by_serial_found_string(self, emulator_port: int):
        """Test finding device by serial number (string format)."""
        # First discover a device to get a real serial number
        target_serial = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            target_serial = disc.serial
            break

        assert target_serial is not None

        # Use the first discovered device's serial
        device = await find_by_serial(
            target_serial,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        assert device.serial == target_serial
        assert isinstance(device, Light)

    async def test_find_by_serial_with_colons(self, emulator_port: int):
        """Test finding device by serial with colon separators."""
        # Discover first device
        target_serial = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            target_serial = disc.serial
            break
        assert target_serial is not None

        # Format with colons
        serial_with_colons = ":".join(
            [target_serial[i : i + 2] for i in range(0, 12, 2)]
        )

        device = await find_by_serial(
            serial_with_colons,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        assert device.serial == target_serial

    async def test_find_by_serial_not_found(self, emulator_port: int):
        """Test finding device with non-existent serial."""
        device = await find_by_serial(
            "d073d5999999",
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        # Should return None
        assert device is None

    async def test_find_by_serial_case_insensitive(self, emulator_port: int):
        """Test that serial matching is case-insensitive."""
        # Discover first device
        target_serial = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            target_serial = disc.serial
            break
        assert target_serial is not None

        # Use uppercase version of serial
        uppercase_serial = target_serial.upper()

        device = await find_by_serial(
            uppercase_serial,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        assert device.serial.lower() == target_serial.lower()

    async def test_find_by_serial_timeout(self):
        """Test find_by_serial with empty network (timeout scenario)."""
        # Use a port with no emulator running
        device = await find_by_serial(
            "d073d5999999",
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=get_free_port(),
        )
        assert device is None


@pytest.mark.emulator
class TestFindByIp:
    """Tests for find_by_ip function."""

    async def test_find_by_ip_found(self, emulator_port: int):
        """Test find_by_ip returns device when IP matches."""
        # Emulator devices are all at 127.0.0.1
        device = await find_by_ip(
            "127.0.0.1",
            timeout=1.0,
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        # Should get one of the emulator devices (d073d5000001-d073d5000007)
        assert device.serial.startswith("d073d5")

    async def test_find_by_ip_not_found(self, emulator_port: int):
        """Test find_by_ip returns None when IP doesn't match any device."""
        # Use an IP that's definitely not the emulator (192.168.200.254)
        device = await find_by_ip(
            "192.168.200.254",
            timeout=1.0,
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is None

    async def test_find_by_ip_timeout(self):
        """Test find_by_ip with no emulator running (timeout scenario)."""
        device = await find_by_ip(
            "127.0.0.1",
            timeout=0.5,
            port=get_free_port(),
            idle_timeout_multiplier=0.5,
        )
        assert device is None


@pytest.mark.emulator
class TestFindByLabel:
    """Tests for find_by_label function."""

    async def test_find_by_label_found(self, emulator_port: int):
        """Test find_by_label can find devices by label."""
        # First discover a device and get its label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        # Get the label of the first device
        device = await first_disc.create_device()
        assert device is not None, "Supported emulator product must construct a device"

        async with device:
            device_label = await device.get_label()

        # Now search for that device by label using find_by_label
        found_devices = []
        async for d in find_by_label(
            device_label,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            found_devices.append(d)

        try:
            assert len(found_devices) >= 1
            assert any(d.serial == first_disc.serial for d in found_devices)
        finally:
            # Close all found device connections
            for d in found_devices:
                await d.connection.close()

    async def test_find_by_label_case_insensitive(self, emulator_port: int):
        """Test find_by_label is case-insensitive."""
        # Get a device label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        device = await first_disc.create_device()
        assert device is not None, "Supported emulator product must construct a device"

        async with device:
            device_label = await device.get_label()

        # Search with different case
        found_devices = []
        async for d in find_by_label(
            device_label.upper(),
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            found_devices.append(d)

        try:
            assert len(found_devices) >= 1
            assert any(d.serial == first_disc.serial for d in found_devices)
        finally:
            # Close all found device connections
            for d in found_devices:
                await d.connection.close()

    async def test_find_by_label_not_found(self, emulator_port: int):
        """Test find_by_label returns empty list when label doesn't match any device."""
        # Use a label that definitely doesn't exist
        async for d in find_by_label(
            "Nonexistent Device Label XYZ999",
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            pytest.fail(f"Unexpected yield of {d} from find_by_label()")

    async def test_find_by_label_timeout(self):
        """Test find_by_label with no emulator running (timeout scenario)."""
        async for d in find_by_label(
            "Test Device",
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=get_free_port(),
            idle_timeout_multiplier=0.5,
        ):
            pytest.fail(f"Unexpected yield of {d} from find_by_label()")

    async def test_find_by_label_substring_match(self, emulator_port: int):
        """Test find_by_label substring matching (default behavior)."""
        # Get a device label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        device = await first_disc.create_device()
        assert device is not None, "Supported emulator product must construct a device"

        async with device:
            device_label = await device.get_label()

        # Search with partial label (should match if label contains the substring)
        # E.g., if label is "LIFX Color 000001", search for "Color"
        if len(device_label) > 4:
            partial_label = device_label[5:9]  # Get a middle substring
            async for d in find_by_label(
                partial_label,
                exact_match=False,
                timeout=1.0,
                broadcast_address="127.0.0.1",
                port=emulator_port,
                idle_timeout_multiplier=0.5,
            ):
                assert d is not None
                await d.connection.close()
                break

    async def test_find_by_label_exact_match(self, emulator_port: int):
        """Test find_by_label exact matching."""
        # Get a device label
        first_disc = None
        async for disc in discover_devices(
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            first_disc = disc
            break

        assert first_disc is not None

        device = await first_disc.create_device()
        assert device is not None, "Supported emulator product must construct a device"

        async with device:
            device_label = await device.get_label()

        # Exact match should work
        async for d in find_by_label(
            device_label,
            exact_match=True,
            timeout=1.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        ):
            assert d.serial == first_disc.serial
            await d.connection.close()

        # Partial label with exact_match=True should NOT match
        if len(device_label) > 4:
            partial_label = device_label[5:9]
            async for d in find_by_label(
                partial_label,
                exact_match=True,
                timeout=1.0,
                broadcast_address="127.0.0.1",
                port=emulator_port,
                idle_timeout_multiplier=0.5,
            ):
                pytest.fail(f"Unexpected yield of {d} from find_by_label()")


class TestDiscoveryDelegateLifecycle:
    """Public helpers synchronously close their socket-owning delegates."""

    async def test_discover_skips_unsupported_device(self) -> None:
        """Discovery continues when capability detection rejects a responder."""
        discovered = DiscoveredDevice("d073d5123456", "192.0.2.10")

        async def _discover_devices(*args, **kwargs):
            yield discovered

        async def _create_device(_discovered: DiscoveredDevice) -> None:
            return None

        with (
            patch("lifx.api.discover_devices_shared", side_effect=_discover_devices),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _create_device,
            ),
        ):
            assert [device async for device in discover()] == []

    async def test_discover_logs_constructor_bug_and_continues(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """One broken product class cannot abort the remaining public sweep."""
        broken = DiscoveredDevice("d073d5123456", "192.0.2.10")
        healthy = DiscoveredDevice("d073d5123457", "192.0.2.11")
        expected = Light(healthy.serial, healthy.ip)

        async def _discover_devices(*args, **kwargs):
            yield broken
            yield healthy

        async def _create_device(discovered: DiscoveredDevice) -> Light:
            if discovered is broken:
                raise TypeError("broken concrete constructor")
            return expected

        with (
            caplog.at_level(logging.ERROR, logger="lifx.api"),
            patch("lifx.api.discover_devices_shared", side_effect=_discover_devices),
            patch.object(DiscoveredDevice, "create_device", _create_device),
        ):
            devices = [device async for device in discover()]

        assert devices == [expected]
        diagnostic = next(
            record.msg
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("action") == "device_construction_failed"
        )
        assert diagnostic["method"] == "discover"
        assert diagnostic["error_type"] == "TypeError"

    async def test_discover_close_finalises_device_discovery(self) -> None:
        """Closing ``discover`` immediately closes ``discover_devices``."""
        finalised = False
        discovered = DiscoveredDevice("d073d5123456", "192.0.2.10")
        device = Light("d073d5123456", "192.0.2.10")

        async def _discover_devices(*args, **kwargs):
            nonlocal finalised
            try:
                yield discovered
            finally:
                finalised = True

        async def _create_device(_discovered: DiscoveredDevice) -> Light:
            return device

        with (
            patch("lifx.api.discover_devices_shared", side_effect=_discover_devices),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _create_device,
            ),
        ):
            generator = discover()
            assert await anext(generator) is device
            await generator.aclose()

        assert finalised is True

    async def test_find_by_serial_return_finalises_device_discovery(self) -> None:
        """An early matching return does not leave the delegate suspended."""
        finalised = False
        discovered = DiscoveredDevice("d073d5123456", "192.0.2.10")
        device = Light("d073d5123456", "192.0.2.10")

        async def _discover_devices(*args, **kwargs):
            nonlocal finalised
            try:
                yield discovered
            finally:
                finalised = True

        async def _create_device(_discovered: DiscoveredDevice) -> Light:
            return device

        with (
            patch("lifx.api.discover_devices_shared", side_effect=_discover_devices),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _create_device,
            ),
        ):
            assert await find_by_serial(discovered.serial) is device

        assert finalised is True

    async def test_find_by_label_close_finalises_packet_discovery(self) -> None:
        """A consumer break closes the packet-discovery delegate immediately."""
        finalised = False
        response = DiscoveryResponse(
            serial="d073d5123456",
            ip="192.0.2.10",
            port=56700,
            response_time=0.01,
            response_payload={"label": "Synthetic Light"},
        )
        device = Light(response.serial, response.ip)

        async def _discover_packets(*args, **kwargs):
            nonlocal finalised
            try:
                yield response
            finally:
                finalised = True

        async def _create_device(_discovered: DiscoveredDevice) -> Light:
            return device

        with (
            patch("lifx.api._discover_with_packet", side_effect=_discover_packets),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _create_device,
            ),
        ):
            generator = find_by_label("Synthetic", exact_match=False)
            assert await anext(generator) is device
            await generator.aclose()

        assert finalised is True

    async def test_find_by_label_exact_match_stops_after_first_device(self) -> None:
        """The exact-match contract yields at most one matching device."""
        finalised = False
        responses = [
            DiscoveryResponse(
                serial=f"d073d51234{suffix}",
                ip=f"192.0.2.{index}",
                port=56700,
                response_time=0.01,
                response_payload={"label": "Synthetic Light"},
            )
            for index, suffix in enumerate(("56", "57"), start=10)
        ]

        async def _discover_packets(*args, **kwargs):
            nonlocal finalised
            try:
                for response in responses:
                    yield response
            finally:
                finalised = True

        async def _create_device(discovered: DiscoveredDevice) -> Light:
            return Light(discovered.serial, discovered.ip)

        with (
            patch("lifx.api._discover_with_packet", side_effect=_discover_packets),
            patch.object(DiscoveredDevice, "create_device", _create_device),
        ):
            devices = [
                device
                async for device in find_by_label("Synthetic Light", exact_match=True)
            ]

        assert len(devices) == 1
        assert devices[0].serial == responses[0].serial
        assert finalised is True

    async def test_find_by_label_skips_unsupported_device(self) -> None:
        """A matching label is ignored when its device type is unsupported."""
        response = DiscoveryResponse(
            serial="d073d5123456",
            ip="192.0.2.10",
            port=56700,
            response_time=0.01,
            response_payload={"label": "Synthetic Light"},
        )

        async def _discover_packets(*args, **kwargs):
            yield response

        async def _create_device(_discovered: DiscoveredDevice) -> None:
            return None

        with (
            patch("lifx.api._discover_with_packet", side_effect=_discover_packets),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _create_device,
            ),
        ):
            assert [
                device async for device in find_by_label("Synthetic", exact_match=False)
            ] == []


@pytest.mark.usefixtures("_allow_public_mdns_discovery")
class TestDiscoverMdns:
    """Tests for discover_mdns() high-level API function."""

    @pytest.mark.asyncio
    async def test_close_synchronously_finalises_device_discovery(self) -> None:
        """Closing the public generator closes its socket-owning delegate."""
        finalised = False
        device = Light("d073d5123456", "192.0.2.10")

        async def mock_discover_devices(*args, **kwargs):
            nonlocal finalised
            try:
                yield device
            finally:
                finalised = True

        with patch(
            "lifx.network.discovery.mdns.discovery.discover_devices_mdns",
            side_effect=mock_discover_devices,
        ):
            generator = discover_mdns(timeout=0.1)
            assert await anext(generator) is device
            await generator.aclose()

        assert finalised is True

    @pytest.mark.asyncio
    async def test_discover_mdns_yields_devices(self) -> None:
        """Test that discover_mdns() yields device instances."""
        from lifx.network.discovery.mdns.types import _LifxServiceRecord

        mock_record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.0.2.10",
            port=56700,
            product_id=27,  # LIFX A19
            firmware="4.112",
            connectivity="thread",
            service_instance="device._lifx._udp.local",
        )

        async def mock_discover_services(*args, **kwargs):
            yield mock_record

        with patch(
            "lifx.network.discovery.mdns.discovery._discover_lifx_services",
            side_effect=mock_discover_services,
        ):
            devices = []
            async for device in discover_mdns(timeout=0.1):
                devices.append(device)

            assert len(devices) == 1
            assert isinstance(devices[0], Light)
            assert devices[0].serial == "d073d5123456"
            assert devices[0].connectivity == "thread"

    @pytest.mark.asyncio
    async def test_discover_mdns_filters_relay_devices(self) -> None:
        """Test that discover_mdns() filters out relay-only devices."""
        from lifx.network.discovery.mdns.types import _LifxServiceRecord

        mock_record = _LifxServiceRecord(
            serial="d073d5123456",
            ip="192.168.1.100",
            port=56700,
            product_id=70,  # LIFX Switch - relay only
            firmware="4.112",
            service_instance="device._lifx._udp.local",
        )

        async def mock_discover_services(*args, **kwargs):
            yield mock_record

        with patch(
            "lifx.network.discovery.mdns.discovery._discover_lifx_services",
            side_effect=mock_discover_services,
        ):
            devices = []
            async for device in discover_mdns(timeout=0.1):
                devices.append(device)

            # Relay devices should be filtered out
            assert len(devices) == 0

    @pytest.mark.asyncio
    async def test_discover_mdns_empty_network(self) -> None:
        """Test discover_mdns() with no devices."""

        async def mock_discover_services(*args, **kwargs):
            return
            yield  # noqa: B901 - makes this an async generator

        with patch(
            "lifx.network.discovery.mdns.discovery._discover_lifx_services",
            side_effect=mock_discover_services,
        ):
            devices = []
            async for device in discover_mdns(timeout=0.1):
                devices.append(device)

            assert len(devices) == 0


class _ObservedNoResponseDiscoveryTransport(UdpTransport):
    """Record a discovery boundary, then cooperatively time out."""

    latest: ClassVar[_ObservedNoResponseDiscoveryTransport | None] = None
    destinations: list[SocketAddress]

    @property
    def ip_address(self) -> str:
        """Expose the configured bind address for boundary assertions."""
        return self._ip_address

    @property
    def broadcast(self) -> bool:
        """Expose the configured broadcast flag for boundary assertions."""
        return self._broadcast

    async def __aenter__(self) -> _ObservedNoResponseDiscoveryTransport:
        self.destinations = []
        _ObservedNoResponseDiscoveryTransport.latest = self
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def send(self, data: bytes, address: SocketAddress) -> None:
        self.destinations.append(address)

    async def receive(self, timeout: float = 2.0) -> tuple[bytes, SocketAddress]:
        await asyncio.sleep(timeout)
        raise LifxTimeoutError("synthetic discovery timeout")


def _build_state_service_packet(
    source: int,
    target: bytes = b"\x02\x00\x00\x00\x00\x01\x00\x00",
) -> bytes:
    """Build one valid response for a clearly synthetic device identity."""
    return create_message(
        DevicePackets.StateService(service=DeviceService.UDP, port=56700),
        source=source,
        target=target,
        ack_required=False,
        res_required=False,
        sequence=0,
    )


class _SplitScopeResponseDiscoveryTransport(_ObservedNoResponseDiscoveryTransport):
    """Return an IPv6 sockaddr whose numeric scope is separate from its host."""

    _response: bytes | None = None

    async def send(self, data: bytes, address: SocketAddress) -> None:
        await super().send(data, address)
        request_header = LifxHeader.unpack(data[: LifxHeader.HEADER_SIZE])
        self._response = _build_state_service_packet(request_header.source)

    async def receive(self, timeout: float = 2.0) -> tuple[bytes, SocketAddress]:
        if self._response is not None:
            response, self._response = self._response, None
            return response, ("fe80::1", 56700, 0, 7)
        await super().receive(timeout)
        raise AssertionError("the no-response transport should time out")


class _UnicastResponseDiscoveryTransport(_SplitScopeResponseDiscoveryTransport):
    """Return a unicast responder after a multi-responder target was queried."""

    async def receive(self, timeout: float = 2.0) -> tuple[bytes, SocketAddress]:
        if self._response is not None:
            response, self._response = self._response, None
            return response, ("192.0.2.10", 56700)
        await super().receive(timeout)
        raise AssertionError("the no-response transport should time out")


class _FailOnUseDiscoveryTransport:
    """Fail immediately if rejected input reaches transport construction."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("rejected input constructed a discovery transport")


class TestFindByIpAddressGate:
    """Public targeted lookup canonicalises accepted text at its send boundary."""

    @pytest.mark.parametrize(
        ("literal", "expected_sockaddr"),
        [
            pytest.param(
                "2001:db8::1",
                ("2001:db8::1", 56700, 0, 0),
                id="compressed-representation",
            ),
            pytest.param(
                "2001:0db8:0000:0000:0000:0000:0000:0001",
                ("2001:db8::1", 56700, 0, 0),
                id="expanded-representation",
            ),
            pytest.param("fd00::1", ("fd00::1", 56700, 0, 0), id="ula-representation"),
            pytest.param(
                "2001:db8:1::1",
                ("2001:db8:1::1", 56700, 0, 0),
                id="gua-representation",
            ),
            pytest.param("::1", ("::1", 56700, 0, 0), id="loopback-representation"),
            pytest.param(
                "fe80::1%7",
                ("fe80::1", 56700, 0, 7),
                id="zoned-link-local-representation",
            ),
        ],
    )
    async def test_ipv6_representation_reaches_transport_boundary(
        self, literal: str, expected_sockaddr: tuple[str, int, int, int]
    ) -> None:
        """Every accepted spelling reaches the canonical IPv6 send boundary."""
        _ObservedNoResponseDiscoveryTransport.latest = None

        with patch(
            "lifx.network.discovery.udp.UdpTransport",
            _ObservedNoResponseDiscoveryTransport,
        ):
            result = await find_by_ip(
                literal,
                port=56700,
                timeout=0.05,
                max_response_time=0.01,
                idle_timeout_multiplier=1.0,
            )

        observation = _ObservedNoResponseDiscoveryTransport.latest
        assert observation is not None
        assert result is None
        assert observation.ip_address == "::"
        assert observation.broadcast is False
        assert observation.destinations == [expected_sockaddr]

    async def test_split_response_scope_reaches_product_construction(self) -> None:
        """Discovery reconstructs the responder's zone without caller rewriting."""
        captured: list[DiscoveredDevice] = []

        async def _capture_create_device(discovered: DiscoveredDevice) -> None:
            captured.append(discovered)
            return None

        with (
            patch(
                "lifx.network.discovery.udp.UdpTransport",
                _SplitScopeResponseDiscoveryTransport,
            ),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _capture_create_device,
            ),
        ):
            result = await find_by_ip(
                "fe80::1%11",
                port=56700,
                timeout=0.05,
                max_response_time=0.01,
                idle_timeout_multiplier=1.0,
            )

        assert result is None
        assert len(captured) == 1
        assert captured[0].ip == "fe80::1%7"

    async def test_multi_responder_target_keeps_the_unicast_responder(self) -> None:
        """A broadcast lookup never becomes a Device at the broadcast address."""
        captured: list[DiscoveredDevice] = []

        async def _capture_create_device(discovered: DiscoveredDevice) -> None:
            captured.append(discovered)
            return None

        with (
            patch(
                "lifx.network.discovery.udp.UdpTransport",
                _UnicastResponseDiscoveryTransport,
            ),
            patch.object(
                DiscoveredDevice,
                "create_device",
                _capture_create_device,
            ),
        ):
            result = await find_by_ip(
                "255.255.255.255",
                port=56700,
                timeout=0.05,
                max_response_time=0.01,
                idle_timeout_multiplier=1.0,
            )

        assert result is None
        assert len(captured) == 1
        assert captured[0].ip == "192.0.2.10"

    async def test_unzoned_link_local_discovery_fails_before_transport(self) -> None:
        """Every public discovery entry point shares the immediate address gate."""
        with patch(
            "lifx.network.discovery.udp.UdpTransport",
            _FailOnUseDiscoveryTransport,
        ):
            generator = discover(broadcast_address="fe80::1")
            with pytest.raises(ValueError, match="zone identifier"):
                await anext(generator)

    @pytest.mark.parametrize(
        ("literal", "message"),
        [
            pytest.param("", "No IP address provided", id="empty-representation"),
            pytest.param(
                "definitely-not-an-ip-address",
                "Invalid IP address format",
                id="malformed-representation",
            ),
            pytest.param(
                "fe80::1",
                "zone identifier",
                id="bare-link-local-representation",
            ),
            pytest.param(
                "fe80::1%0",
                "zone identifier",
                id="zero-scope-link-local-representation",
            ),
        ],
    )
    async def test_invalid_representation_fails_before_transport(
        self, literal: str, message: str
    ) -> None:
        """Permanent input errors cannot acquire a discovery transport."""
        with patch(
            "lifx.network.discovery.udp.UdpTransport",
            _FailOnUseDiscoveryTransport,
        ):
            with pytest.raises(ValueError, match=message):
                await find_by_ip(literal)

    async def test_invalid_port_fails_before_transport(self) -> None:
        """A permanent endpoint error cannot acquire a discovery socket."""
        with patch(
            "lifx.network.discovery.udp.UdpTransport",
            _FailOnUseDiscoveryTransport,
        ):
            with pytest.raises(LifxNetworkError, match="Port must be between"):
                await find_by_ip("192.0.2.1", port=70000)

    async def test_loopback_advisory_is_emitted_once(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Public validation owns the one advisory for a targeted lookup."""
        with (
            patch(
                "lifx.network.discovery.udp.UdpTransport",
                _ObservedNoResponseDiscoveryTransport,
            ),
            caplog.at_level(logging.WARNING, logger="lifx.network.address"),
        ):
            result = await find_by_ip(
                "::1",
                timeout=0.05,
                max_response_time=0.01,
                idle_timeout_multiplier=1.0,
            )

        assert result is None
        advisories = [
            record
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("action") == "is_loopback"
        ]
        assert len(advisories) == 1
