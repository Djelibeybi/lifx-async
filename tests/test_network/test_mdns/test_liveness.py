"""Tests for current-call mDNS candidate liveness verification."""

from __future__ import annotations

import asyncio
import ipaddress
from collections.abc import AsyncGenerator, Callable
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

import lifx.network.utils as network_utils
from lifx.devices.base import Device
from lifx.devices.ceiling import CeilingLight
from lifx.devices.hev import HevLight
from lifx.devices.infrared import InfraredLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.exceptions import (
    LifxConnectionError,
    LifxNetworkError,
    LifxProtocolError,
    LifxTimeoutError,
    LifxUnsupportedCommandError,
)
from lifx.network.discovery.mdns import discovery as mdns_discovery
from lifx.network.discovery.mdns.discovery import _LifxRecordCache
from lifx.network.discovery.mdns.dns import DnsResourceRecord, SrvData, TxtData
from lifx.network.discovery.mdns.transport import MdnsTransport
from lifx.network.discovery.mdns.types import _LifxServiceRecord
from lifx.protocol import packets
from lifx.protocol.protocol_types import LightHsbk
from tests.test_discovery_observation import _capture_discovery_observations

_FIRST_SERIAL = "d073d5123456"
_SECOND_SERIAL = "d073d5123458"


def _record(
    serial: str = _FIRST_SERIAL,
    *,
    product_id: int = 27,
    firmware: str = "3.70",
    connectivity: str = "thread",
) -> _LifxServiceRecord:
    """Build one complete synthetic private mDNS record."""
    return _LifxServiceRecord(
        serial=serial,
        ip="192.0.2.20" if serial == _FIRST_SERIAL else "192.0.2.21",
        port=56700,
        product_id=product_id,
        firmware=firmware,
        connectivity=connectivity,  # type: ignore[arg-type]
        service_instance=f"{serial}._lifx._udp.local",
    )


def _state_color(label: str = "Verified") -> packets.Light.StateColor:
    """Build the exact response required by a current supported light."""
    return packets.Light.StateColor(
        color=LightHsbk(
            hue=21845,
            saturation=32768,
            brightness=49151,
            kelvin=4000,
        ),
        power=65535,
        label=label,  # type: ignore[arg-type]
    )


def _source(
    records: list[_LifxServiceRecord],
    *,
    closed: list[bool] | None = None,
) -> Callable[[], AsyncGenerator[_LifxServiceRecord, None]]:
    """Return a fresh invocation-local record source."""

    async def generate() -> AsyncGenerator[_LifxServiceRecord, None]:
        try:
            for record in records:
                yield record
        finally:
            if closed is not None:
                closed.append(True)

    return generate


def _connection_factory(
    responder: Callable[[str, object, float | None], Any],
    ledger: list[SimpleNamespace],
) -> type:
    """Build a bounded fake at the external UDP request boundary."""

    class FakeConnection:
        def __init__(
            self,
            serial: str,
            ip: str,
            port: int,
            max_retries: int,
            timeout: float,
        ) -> None:
            self.serial = serial
            self.ip = ip
            self.port = port
            self.max_retries = max_retries
            self.timeout = timeout
            self.closed = False
            self.requests: list[tuple[object, float | None]] = []
            ledger.append(self)

        async def request(self, packet: object, timeout: float | None = None) -> object:
            self.requests.append((packet, timeout))
            result = responder(self.serial, packet, timeout)
            if asyncio.iscoroutine(result):
                return await result
            if isinstance(result, BaseException):
                raise result
            return result

        async def close(self) -> None:
            self.closed = True

    return FakeConnection


async def _collect_verified(**kwargs: Any) -> list[Device]:
    """Collect the private verified generator without leaking ownership."""
    generator = mdns_discovery._discover_verified_devices_mdns(**kwargs)
    try:
        return [device async for device in generator]
    finally:
        await generator.aclose()


@pytest.mark.asyncio
async def test_supported_light_requires_get_color_and_adopts_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing GetColor verification or pre-yield adoption must fail."""
    connections: list[SimpleNamespace] = []
    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(lambda *_args: _state_color(), connections),
        raising=False,
    )
    monkeypatch.setattr(
        mdns_discovery,
        "_discover_lifx_services",
        lambda **_kwargs: _source([_record()])(),
    )

    devices = await _collect_verified(
        timeout=2.0,
        device_timeout=0.75,
        max_retries=3,
    )

    assert len(devices) == 1
    device = devices[0]
    assert type(device) is Light
    assert device.connectivity == "thread"
    assert device.label == "Verified"
    assert device._state is None
    assert device._discovery_snapshot is not None
    assert device._discovery_snapshot.power == 65535
    assert device._discovery_snapshot.label == "Verified"
    assert isinstance(connections[0].requests[0][0], packets.Light.GetColor)
    assert 0 < connections[0].requests[0][1] <= 0.75
    assert connections[0].max_retries == 3
    assert connections[0].closed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("product_id", "expected_type"),
    [
        (27, Light),
        (29, InfraredLight),
        (31, MultiZoneLight),
        (55, MatrixLight),
        (90, HevLight),
        (176, CeilingLight),
    ],
)
async def test_every_current_supported_class_uses_get_color(
    monkeypatch: pytest.MonkeyPatch,
    product_id: int,
    expected_type: type[Light],
) -> None:
    """Every shipping supported classifier outcome uses StateColor liveness."""
    connections: list[SimpleNamespace] = []
    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(lambda *_args: _state_color(), connections),
    )
    monkeypatch.setattr(
        mdns_discovery,
        "_discover_lifx_services",
        lambda **_kwargs: _source([_record(product_id=product_id)])(),
    )

    devices = await _collect_verified(timeout=1.0)

    assert len(devices) == 1
    assert type(devices[0]) is expected_type
    assert isinstance(connections[0].requests[0][0], packets.Light.GetColor)


@pytest.mark.asyncio
async def test_unsupported_classifier_is_candidate_local_and_next_yields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A relay advertisement cannot end verification of later lights."""
    events: list[object] = []
    connections: list[SimpleNamespace] = []
    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(lambda *_args: _state_color("Later"), connections),
        raising=False,
    )
    monkeypatch.setattr(
        mdns_discovery,
        "_discover_lifx_services",
        lambda **_kwargs: _source([_record(product_id=70), _record(_SECOND_SERIAL)])(),
    )

    devices = await _collect_verified(timeout=1.0, failure_sink=events.append)

    assert [device.serial for device in devices] == [_SECOND_SERIAL]
    assert len(connections) == 1
    assert events == [
        mdns_discovery._MdnsCandidateFailure(
            stage="classify",
            reason="candidate_unsupported",
            error_type="LifxUnsupportedDeviceError",
        )
    ]
    assert _FIRST_SERIAL not in repr(events)


@pytest.mark.asyncio
async def test_state_unhandled_rejects_light_without_echo_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A purported light that rejects GetColor must not fall back to Echo."""
    events: list[object] = []
    connections: list[SimpleNamespace] = []
    response = packets.Device.StateUnhandled(unhandled_type=101)
    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(lambda *_args: response, connections),
        raising=False,
    )
    monkeypatch.setattr(
        mdns_discovery,
        "_discover_lifx_services",
        lambda **_kwargs: _source([_record()])(),
    )

    assert await _collect_verified(timeout=1.0, failure_sink=events.append) == []
    assert len(connections[0].requests) == 1
    assert isinstance(connections[0].requests[0][0], packets.Light.GetColor)
    assert events == [
        mdns_discovery._MdnsCandidateFailure(
            stage="request",
            reason="candidate_unsupported",
            error_type="LifxUnsupportedCommandError",
        )
    ]


@pytest.mark.asyncio
async def test_synthetic_future_non_light_uses_exact_echo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The future classifier branch must use one exact 64-byte echo payload."""
    connections: list[SimpleNamespace] = []

    def respond(_serial: str, packet: object, _timeout: float | None) -> object:
        assert isinstance(packet, packets.Device.EchoRequest)
        assert len(packet.payload) == 64
        return packets.Device.EchoResponse(payload=packet.payload)

    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(respond, connections),
        raising=False,
    )
    monkeypatch.setattr(
        mdns_discovery,
        "get_device_class_for_product",
        lambda _pid, _product: Device,
        raising=False,
    )
    monkeypatch.setattr(
        mdns_discovery,
        "_discover_lifx_services",
        lambda **_kwargs: _source([_record()])(),
    )

    devices = await _collect_verified(timeout=1.0)

    assert len(devices) == 1
    assert type(devices[0]) is Device
    assert connections[0].closed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (LifxTimeoutError("private timeout"), "candidate_timeout"),
        (LifxConnectionError("private connection"), "candidate_connect"),
        (LifxNetworkError("private network"), "candidate_connect"),
        (LifxProtocolError("private protocol"), "candidate_protocol"),
        (
            LifxUnsupportedCommandError("private unsupported"),
            "candidate_unsupported",
        ),
    ],
)
async def test_expected_candidate_failure_emits_once_and_closes(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    reason: str,
) -> None:
    """Every absorbed request failure has one bounded event and cleanup."""
    events: list[object] = []
    connections: list[SimpleNamespace] = []
    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(lambda *_args: error, connections),
        raising=False,
    )
    monkeypatch.setattr(
        mdns_discovery,
        "_discover_lifx_services",
        lambda **_kwargs: _source([_record()])(),
    )

    assert await _collect_verified(timeout=1.0, failure_sink=events.append) == []
    assert events == [
        mdns_discovery._MdnsCandidateFailure(
            stage="request",
            reason=reason,
            error_type=type(error).__name__,
        )
    ]
    assert "private" not in repr(events)
    assert connections[0].closed is True


@pytest.mark.asyncio
async def test_candidate_expired_before_validation_needs_no_failure_sink() -> None:
    """An already-expired candidate is discarded without requiring diagnostics."""
    assert (
        await mdns_discovery._verify_mdns_candidate(
            _record(),
            deadline=0.0,
            device_timeout=1.0,
            max_retries=1,
        )
        is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "record",
    [
        replace(_record(), ip="not-an-address"),
        replace(_record(), port=0),
    ],
)
async def test_candidate_rejects_invalid_advertised_endpoint(
    record: object,
) -> None:
    """Malformed advertised endpoints fail locally before opening a connection."""
    events: list[object] = []

    assert (
        await mdns_discovery._verify_mdns_candidate(
            record,  # type: ignore[arg-type]
            deadline=mdns_discovery.time.monotonic() + 1.0,
            device_timeout=1.0,
            max_retries=1,
            failure_sink=events.append,
        )
        is None
    )
    assert events == [
        mdns_discovery._MdnsCandidateFailure(
            stage="record",
            reason="candidate_response",
            error_type="_MdnsCandidateResponseError",
        )
    ]


@pytest.mark.asyncio
async def test_candidate_deadline_can_expire_after_connection_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Connection construction cannot grant a candidate a fresh request window."""
    events: list[object] = []
    connections: list[SimpleNamespace] = []
    clock = iter((0.0, 2.0))
    monkeypatch.setattr(
        mdns_discovery,
        "time",
        SimpleNamespace(monotonic=lambda: next(clock)),
    )
    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(
            lambda *_args: pytest.fail("request must not start"), connections
        ),
    )

    assert (
        await mdns_discovery._verify_mdns_candidate(
            _record(),
            deadline=1.0,
            device_timeout=1.0,
            max_retries=1,
            failure_sink=events.append,
        )
        is None
    )
    assert events == [
        mdns_discovery._MdnsCandidateFailure(
            stage="request",
            reason="candidate_timeout",
            error_type="LifxTimeoutError",
        )
    ]
    assert connections[0].requests == []
    assert connections[0].closed is True


@pytest.mark.asyncio
async def test_wrong_response_type_is_bounded_and_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed correlated reply must not become device state."""
    events: list[object] = []
    connections: list[SimpleNamespace] = []
    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(
            lambda *_args: packets.Device.StatePower(level=65535), connections
        ),
        raising=False,
    )
    monkeypatch.setattr(
        mdns_discovery,
        "_discover_lifx_services",
        lambda **_kwargs: _source([_record()])(),
    )

    assert await _collect_verified(timeout=1.0, failure_sink=events.append) == []
    assert events == [
        mdns_discovery._MdnsCandidateFailure(
            stage="response",
            reason="candidate_response",
            error_type="_MdnsCandidateResponseError",
        )
    ]
    assert _FIRST_SERIAL not in repr(events)
    assert connections[0].closed is True


@pytest.mark.asyncio
async def test_connection_identity_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A response cannot be adopted after the connection identity changes."""
    events: list[object] = []
    connections: list[SimpleNamespace] = []

    def respond(*_args: object) -> object:
        connections[0].serial = _SECOND_SERIAL
        return _state_color()

    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(respond, connections),
    )
    monkeypatch.setattr(
        mdns_discovery,
        "_discover_lifx_services",
        lambda **_kwargs: _source([_record()])(),
    )

    assert await _collect_verified(timeout=1.0, failure_sink=events.append) == []
    assert events == [
        mdns_discovery._MdnsCandidateFailure(
            stage="response",
            reason="candidate_identity",
            error_type="_MdnsCandidateIdentityError",
        )
    ]
    assert connections[0].closed is True


@pytest.mark.asyncio
async def test_wrong_echo_payload_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Echo proves liveness only when all 64 response bytes are identical."""
    events: list[object] = []
    connections: list[SimpleNamespace] = []
    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(
            lambda *_args: packets.Device.EchoResponse(payload=b"x" * 64),
            connections,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        mdns_discovery,
        "get_device_class_for_product",
        lambda _pid, _product: Device,
        raising=False,
    )
    monkeypatch.setattr(
        mdns_discovery,
        "_discover_lifx_services",
        lambda **_kwargs: _source([_record()])(),
    )

    assert await _collect_verified(timeout=1.0, failure_sink=events.append) == []
    assert events[0].reason == "candidate_response"
    assert connections[0].closed is True


@pytest.mark.asyncio
async def test_unexpected_error_propagates_without_absorbed_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Programming defects must fail fast after connection and source cleanup."""
    events: list[object] = []
    closed: list[bool] = []
    connections: list[SimpleNamespace] = []
    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(lambda *_args: RuntimeError("sentinel"), connections),
        raising=False,
    )
    monkeypatch.setattr(
        mdns_discovery,
        "_discover_lifx_services",
        lambda **_kwargs: _source([_record()], closed=closed)(),
    )

    with pytest.raises(RuntimeError, match="sentinel"):
        await _collect_verified(timeout=1.0, failure_sink=events.append)

    assert events == []
    assert closed == [True]
    assert connections[0].closed is True


@pytest.mark.asyncio
async def test_cancellation_reaps_source_workers_and_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caller cancellation propagates only after all private work is reaped."""
    events: list[object] = []
    closed: list[bool] = []
    connections: list[SimpleNamespace] = []
    request_started = asyncio.Event()

    async def respond(*_args: object) -> object:
        request_started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(respond, connections),
    )
    monkeypatch.setattr(
        mdns_discovery,
        "_discover_lifx_services",
        lambda **_kwargs: _source([_record()], closed=closed)(),
    )
    generator = mdns_discovery._discover_verified_devices_mdns(
        timeout=5.0, failure_sink=events.append
    )
    task = asyncio.create_task(anext(generator))
    await request_started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await generator.aclose()

    assert events == []
    assert closed == [True]
    assert connections[0].closed is True


@pytest.mark.asyncio
async def test_early_close_reaps_remaining_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closing after one yield cancels later probes and closes their sockets."""
    source_closed: list[bool] = []
    connections: list[SimpleNamespace] = []

    async def respond(serial: str, *_args: object) -> object:
        if serial == _FIRST_SERIAL:
            return _state_color("First")
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(respond, connections),
    )
    monkeypatch.setattr(
        mdns_discovery,
        "_discover_lifx_services",
        lambda **_kwargs: _source(
            [_record(), _record(_SECOND_SERIAL)], closed=source_closed
        )(),
    )
    generator = mdns_discovery._discover_verified_devices_mdns(timeout=5.0)

    assert (await anext(generator)).serial == _FIRST_SERIAL
    await generator.aclose()

    assert source_closed == [True]
    assert connections
    assert all(connection.closed for connection in connections)


@pytest.mark.asyncio
async def test_probe_cap_and_original_deadline_include_queue_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queued candidates cannot exceed the cap or gain a fresh timeout."""
    active = 0
    maximum_active = 0
    connections: list[SimpleNamespace] = []

    async def respond(*_args: object) -> object:
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        try:
            await asyncio.sleep(0.05)
            return _state_color()
        finally:
            active -= 1

    monkeypatch.setattr(mdns_discovery, "_MAX_MDNS_LIVENESS_PROBES", 2, raising=False)
    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(respond, connections),
        raising=False,
    )
    monkeypatch.setattr(
        mdns_discovery,
        "_discover_lifx_services",
        lambda **_kwargs: _source(
            [_record(f"d073d51234{index:02x}") for index in range(6)]
        )(),
    )

    assert await _collect_verified(timeout=0.02) == []
    assert maximum_active == 2
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)


@pytest.mark.asyncio
async def test_worker_discards_candidate_after_shared_deadline_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A queued record is not probed after the invocation deadline is signalled."""
    real_event = asyncio.Event
    deadline_events: list[asyncio.Event] = []

    def event_factory() -> asyncio.Event:
        event = real_event()
        deadline_events.append(event)
        return event

    async def source(**_kwargs: object):
        deadline_events[0].set()
        yield _record()

    async def unexpected_verify(*_args: object, **_kwargs: object) -> None:
        pytest.fail("expired queued candidate must not be verified")

    monkeypatch.setattr(mdns_discovery.asyncio, "Event", event_factory)
    monkeypatch.setattr(mdns_discovery, "_discover_lifx_services", source)
    monkeypatch.setattr(mdns_discovery, "_verify_mdns_candidate", unexpected_verify)

    assert await _collect_verified(timeout=1.0) == []


@pytest.mark.asyncio
async def test_observation_is_current_call_only_and_malformed_firmware_is_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raw identity metadata is scoped in memory and malformed fw stays absent."""
    connections: list[SimpleNamespace] = []
    calls = 0

    def fresh_source(**_kwargs: object) -> AsyncGenerator[_LifxServiceRecord, None]:
        nonlocal calls
        calls += 1
        return _source([_record(firmware="not-private-version")])()

    monkeypatch.setattr(
        mdns_discovery,
        "DeviceConnection",
        _connection_factory(lambda *_args: _state_color(), connections),
        raising=False,
    )
    monkeypatch.setattr(mdns_discovery, "_discover_lifx_services", fresh_source)

    with _capture_discovery_observations() as sink:
        first = await _collect_verified(timeout=1.0)
        observation = sink.observations[0]
        assert repr(observation) == (
            "_DiscoveryObservation(source='mdns', stage='accepted')"
        )
        assert observation.source == "mdns"
        assert observation.stage == "accepted"
        assert observation.raw_identity == _FIRST_SERIAL
        assert observation.firmware_major is None
        assert observation.firmware_minor is None
        assert observation.connectivity == "thread"
        assert "not-private-version" not in repr(sink)

    second = await _collect_verified(timeout=1.0)

    assert len(first) == len(second) == 1
    assert calls == 2


class _FakeMdnsTransport:
    """Scriptable transport exercising the real sweep catch boundaries."""

    instances: list[_FakeMdnsTransport] = []
    open_error: Exception | None = None
    send_errors: dict[int, Exception] = {}
    receives: list[object] = []

    def __init__(self, *, log_failure_details: bool = True) -> None:
        self.log_failure_details = log_failure_details
        self.send_count = 0
        self.closed = False
        type(self).instances.append(self)

    async def __aenter__(self) -> _FakeMdnsTransport:
        try:
            await self.open()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.close()

    async def open(self) -> None:
        if self.open_error is not None:
            raise self.open_error

    async def send(self, _data: bytes, _address: object = None) -> None:
        self.send_count += 1
        error = self.send_errors.get(self.send_count)
        if error is not None:
            raise error

    async def receive(self, timeout: float = 5.0) -> tuple[bytes, tuple[str, int]]:
        del timeout
        if not self.receives:
            raise LifxTimeoutError("ordinary completion")
        result = self.receives.pop(0)
        if callable(result):
            result = result()
        if isinstance(result, BaseException):
            raise result
        return result  # type: ignore[return-value]

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_mdns_transport(monkeypatch: pytest.MonkeyPatch) -> type[_FakeMdnsTransport]:
    """Reset and install the scriptable sweep transport."""
    _FakeMdnsTransport.instances = []
    _FakeMdnsTransport.open_error = None
    _FakeMdnsTransport.send_errors = {}
    _FakeMdnsTransport.receives = []
    monkeypatch.setattr(mdns_discovery, "MdnsTransport", _FakeMdnsTransport)
    return _FakeMdnsTransport


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_point", "stage", "reason"),
    [
        ("open", "open", "sweep_open_network"),
        ("initial_send", "initial_send", "sweep_send_network"),
        ("receive", "receive", "sweep_receive_network"),
    ],
)
async def test_real_sweep_catches_emit_one_private_failure_and_close(
    fake_mdns_transport: type[_FakeMdnsTransport],
    failure_point: str,
    stage: str,
    reason: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Open, first-send, and receive failures cross as one bounded event."""
    error = LifxNetworkError("private endpoint 192.0.2.99")
    if failure_point == "open":
        fake_mdns_transport.open_error = error
    elif failure_point == "initial_send":
        fake_mdns_transport.send_errors = {1: error}
    else:
        fake_mdns_transport.receives = [error]
    events: list[object] = []

    with caplog.at_level("DEBUG"):
        results = [
            record
            async for record in mdns_discovery._discover_lifx_services_sweep(
                _LifxRecordCache(), timeout=0.01, failure_sink=events.append
            )
        ]

    assert results == []
    assert events == [
        mdns_discovery._MdnsSweepFailure(
            stage=stage,
            reason=reason,
            error_type="LifxNetworkError",
        )
    ]
    assert "private endpoint" not in caplog.text
    assert "192.0.2.99" not in caplog.text
    assert fake_mdns_transport.instances[0].log_failure_details is False
    assert fake_mdns_transport.instances[0].closed is True


@pytest.mark.asyncio
async def test_receive_failure_after_record_preserves_partial_output(
    monkeypatch: pytest.MonkeyPatch,
    fake_mdns_transport: type[_FakeMdnsTransport],
) -> None:
    """A later receive failure cannot retract an already emitted record."""
    instance = "synthetic._lifx._udp.local"
    host = "synthetic-host.local"
    txt = TxtData(
        strings=[f"id={_FIRST_SERIAL}", "p=27", "fw=3.70", "tm=2"],
        pairs={"id": _FIRST_SERIAL, "p": "27", "fw": "3.70", "tm": "2"},
    )
    records = [
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
    ]
    response = SimpleNamespace(
        header=SimpleNamespace(is_response=True), records=records
    )
    monkeypatch.setattr(mdns_discovery, "parse_dns_response", lambda _data: response)
    fake_mdns_transport.receives = [
        (b"packet", ("192.0.2.1", 5353)),
        LifxNetworkError("private post-result endpoint"),
    ]
    events: list[object] = []

    results = [
        record
        async for record in mdns_discovery._discover_lifx_services_sweep(
            _LifxRecordCache(), timeout=0.1, failure_sink=events.append
        )
    ]

    assert [record.serial for record in results] == [_FIRST_SERIAL]
    assert events == [
        mdns_discovery._MdnsSweepFailure(
            stage="receive",
            reason="sweep_receive_network",
            error_type="LifxNetworkError",
        )
    ]


@pytest.mark.asyncio
async def test_retransmit_send_failure_is_typed_once(
    monkeypatch: pytest.MonkeyPatch,
    fake_mdns_transport: type[_FakeMdnsTransport],
) -> None:
    """A due retransmit failure ends only the merged mDNS leg."""
    clock = SimpleNamespace(value=0.0)
    clock.monotonic = lambda: clock.value

    def advance_to_retransmit() -> LifxTimeoutError:
        clock.value = 1.1
        return LifxTimeoutError("ordinary wake")

    monkeypatch.setattr(mdns_discovery.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(network_utils.time, "monotonic", clock.monotonic)
    fake_mdns_transport.receives = [advance_to_retransmit]
    fake_mdns_transport.send_errors = {2: LifxNetworkError("private retransmit")}
    events: list[object] = []

    results = [
        record
        async for record in mdns_discovery._discover_lifx_services_sweep(
            _LifxRecordCache(), timeout=2.0, failure_sink=events.append
        )
    ]

    assert results == []
    assert events == [
        mdns_discovery._MdnsSweepFailure(
            stage="retransmit_send",
            reason="sweep_send_network",
            error_type="LifxNetworkError",
        )
    ]


@pytest.mark.asyncio
async def test_retransmit_send_failure_propagates_without_failure_sink(
    monkeypatch: pytest.MonkeyPatch,
    fake_mdns_transport: type[_FakeMdnsTransport],
) -> None:
    """Standalone mDNS preserves the original retransmit network exception."""
    clock = SimpleNamespace(value=0.0)
    clock.monotonic = lambda: clock.value

    def advance_to_retransmit() -> LifxTimeoutError:
        clock.value = 1.1
        return LifxTimeoutError("ordinary wake")

    monkeypatch.setattr(mdns_discovery.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(network_utils.time, "monotonic", clock.monotonic)
    fake_mdns_transport.receives = [advance_to_retransmit]
    expected = LifxNetworkError("synthetic retransmit")
    fake_mdns_transport.send_errors = {2: expected}

    with pytest.raises(LifxNetworkError) as caught:
        _ = [
            record
            async for record in mdns_discovery._discover_lifx_services_sweep(
                _LifxRecordCache(), timeout=2.0
            )
        ]

    assert caught.value is expected


@pytest.mark.asyncio
async def test_address_followup_failure_is_typed_and_suppresses_target(
    monkeypatch: pytest.MonkeyPatch,
    fake_mdns_transport: type[_FakeMdnsTransport],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed A/AAAA follow-up emits once without target or error detail."""
    clock = SimpleNamespace(value=0.0)
    clock.monotonic = lambda: clock.value
    instance = "synthetic._lifx._udp.local"
    target = "private-target.local"
    txt = TxtData(
        strings=[f"id={_FIRST_SERIAL}", "p=27", "fw=3.70"],
        pairs={"id": _FIRST_SERIAL, "p": "27", "fw": "3.70"},
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
                SrvData(priority=0, weight=0, port=56700, target=target),
            ),
        ],
    )

    def finish() -> LifxTimeoutError:
        clock.value = 0.02
        return LifxTimeoutError("ordinary completion")

    monkeypatch.setattr(mdns_discovery.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(network_utils.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(mdns_discovery, "parse_dns_response", lambda _data: response)
    fake_mdns_transport.receives = [
        (b"packet", ("192.0.2.1", 5353)),
        finish,
    ]
    fake_mdns_transport.send_errors = {2: LifxNetworkError("private followup")}
    events: list[object] = []

    with caplog.at_level("DEBUG"):
        _ = [
            record
            async for record in mdns_discovery._discover_lifx_services_sweep(
                _LifxRecordCache(), timeout=0.01, failure_sink=events.append
            )
        ]

    assert events == [
        mdns_discovery._MdnsSweepFailure(
            stage="address_followup",
            reason="sweep_address_followup_network",
            error_type="LifxNetworkError",
        )
    ]
    assert target not in caplog.text
    assert "private followup" not in caplog.text


@pytest.mark.asyncio
async def test_ordinary_receive_timeout_is_clean_completion(
    fake_mdns_transport: type[_FakeMdnsTransport],
) -> None:
    """The existing receive timeout wake-up must not become a diagnostic."""
    events: list[object] = []

    results = [
        record
        async for record in mdns_discovery._discover_lifx_services_sweep(
            _LifxRecordCache(), timeout=0.001, failure_sink=events.append
        )
    ]

    assert results == []
    assert events == []
    assert fake_mdns_transport.instances[0].closed is True


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["open", "initial_send"])
async def test_no_sink_preserves_open_and_initial_send_propagation(
    fake_mdns_transport: type[_FakeMdnsTransport], failure_point: str
) -> None:
    """Standalone discovery still receives uncaught open/first-send errors."""
    error = LifxNetworkError("standalone detail")
    if failure_point == "open":
        fake_mdns_transport.open_error = error
    else:
        fake_mdns_transport.send_errors = {1: error}

    with pytest.raises(LifxNetworkError, match="standalone detail"):
        _ = [
            record
            async for record in mdns_discovery._discover_lifx_services_sweep(
                _LifxRecordCache(), timeout=0.01
            )
        ]

    assert fake_mdns_transport.instances[0].log_failure_details is True
    assert fake_mdns_transport.instances[0].closed is True


def test_transport_detail_logging_flag_defaults_to_standalone_compatibility() -> None:
    """The private suppression switch must be opt-in for merged discovery."""
    assert MdnsTransport()._log_failure_details is True
    assert MdnsTransport(log_failure_details=False)._log_failure_details is False
