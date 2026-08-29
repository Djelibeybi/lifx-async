"""Tests for the IPv6/Thread hardware probe's UAT harness.

`scripts/ipv6_thread_probe.py` talks to real Thread devices, so none of its
network stages can be tested here. What *is* testable is everything the UAT
harness added around them: target selection, full-state capture and restore,
the record's shape, and the rule that streaming never gates. Every test below
drives a fake device or a fake animator, and none of them opens a socket.

The probe is imported by module name because `pyproject.toml` puts `scripts`
on `pythonpath`, the same route `tests/test_theme/test_theme_generator.py`
uses for `scripts/generate_theme_data.py`.
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lifx.animation.animator import AnimatorStats
from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixEffect, MatrixLight
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight
from lifx.exceptions import LifxNetworkError, LifxTimeoutError
from lifx.network.mdns.dns import DnsResourceRecord, SrvData, TxtData
from lifx.network.mdns.types import _LifxServiceRecord
from lifx.products import get_product
from lifx.protocol.protocol_types import FirmwareEffect, MultiZoneApplicationRequest
from scripts import ipv6_thread_probe as probe

# A matrix product (LIFX Candle C), a plain colour bulb, and a switch, so that
# _create_device_from_record() returns a MatrixLight, a Light and None
# respectively without any of the three being invented.
MATRIX_PRODUCT_ID = 57
LIGHT_PRODUCT_ID = 27
SWITCH_PRODUCT_ID = 70

# A Thread-shaped ULA literal. Deliberately NOT read as a record of the live
# fleet: an OMR prefix is auto-generated and re-derives whenever the border
# router re-forms the mesh, so no test should encode one as a fact. These
# tests only need an address that parses as a routable IPv6 ULA.
ULA_ADDRESS = "fd00:1::"
TARGET_SERIAL = "d073d5aa11bb"
TARGET_ALIAS = "thread-target-alpha"

TILE_COLOURS = [
    [HSBK(10.0, 1.0, 1.0, 3500), HSBK(20.0, 0.5, 0.5, 4000)],
    [HSBK(30.0, 0.25, 0.75, 2700), HSBK(40.0, 0.0, 1.0, 6500)],
]

ZONE_COLOURS = [HSBK(float(index % 360), 0.5, 0.75, 3500) for index in range(170)]


class FakeClock:
    """Monotonic clock advanced only by the scripted transport."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        """Return the current synthetic monotonic time."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Advance by a non-negative interval."""
        assert seconds >= 0
        self.now += seconds


@dataclass(frozen=True)
class ReceiveEvent:
    """One packet or exception scheduled on the fake clock."""

    at: float
    outcome: bytes | BaseException


class FakeSweepTransport:
    """Scripted transport that records waits, sends, and cleanup."""

    def __init__(self, clock: FakeClock, *events: ReceiveEvent) -> None:
        self.clock = clock
        self.events = list(events)
        self.receive_timeouts: list[float] = []
        self.sent: list[bytes] = []
        self.closed = 0
        self._socket = SimpleNamespace(getsockname=lambda: ("0.0.0.0", 49152))

    async def __aenter__(self) -> FakeSweepTransport:
        """Return this already-open synthetic transport."""
        return self

    async def __aexit__(self, *args: object) -> bool:
        """Record cleanup without suppressing terminal exceptions."""
        self.closed += 1
        return False

    async def send(self, data: bytes) -> None:
        """Record one outbound query."""
        self.sent.append(data)

    async def receive(self, timeout: float = 5.0) -> tuple[bytes, tuple[str, int]]:
        """Deliver the next due event or advance to the requested deadline."""
        self.receive_timeouts.append(timeout)
        if self.events and self.events[0].at <= self.clock.now + timeout:
            event = self.events.pop(0)
            self.clock.now = max(self.clock.now, event.at)
            if isinstance(event.outcome, BaseException):
                raise event.outcome
            return event.outcome, ("192.0.2.1", 5353)

        self.clock.advance(timeout)
        raise LifxTimeoutError("synthetic timeout")


def _cache_chain(
    *,
    instance: str = "synthetic._lifx._udp.local",
    target: str = "synthetic-host.local",
    address: str = "192.0.2.20",
    ttl: int = 120,
) -> list[DnsResourceRecord]:
    """Build a complete synthetic TXT/SRV/A chain."""
    txt = TxtData(
        strings=["id=d073d5aa11bb", "p=57", "fw=4.10"],
        pairs={"id": "d073d5aa11bb", "p": "57", "fw": "4.10"},
    )
    srv = SrvData(priority=0, weight=0, port=56700, target=target)
    return [
        DnsResourceRecord(
            instance,
            16,
            1,
            ttl,
            b"\x0fid=d073d5aa11bb\x04p=57\x07fw=4.10",
            txt,
        ),
        DnsResourceRecord(instance, 33, 1, ttl, b"synthetic-srv", srv),
        DnsResourceRecord(
            target,
            1,
            1,
            ttl,
            ipaddress.ip_address(address).packed,
            address,
        ),
    ]


def _address_record(*, ttl: int, address: str = "192.0.2.20") -> DnsResourceRecord:
    """Build the exact address RR used for goodbye and rescue sequences."""
    return DnsResourceRecord(
        "synthetic-host.local",
        1,
        1,
        ttl,
        ipaddress.ip_address(address).packed,
        address,
    )


def _script_probe_responses(
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
    responses: dict[bytes, list[DnsResourceRecord]],
) -> None:
    """Install a fake monotonic clock and parser for opaque packet tokens."""
    monkeypatch.setattr(probe.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(
        probe,
        "parse_dns_response",
        lambda data: SimpleNamespace(
            header=SimpleNamespace(is_response=True),
            records=responses[data],
        ),
    )


class TestSweepClockParity:
    """The diagnostic sweep mirrors production lifetime and clock semantics."""

    @pytest.mark.asyncio
    async def test_probe_rejects_dns_queries_before_counters_and_cache(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """QR=0 authority/additional data is not discovery evidence."""
        clock = FakeClock()
        monkeypatch.setattr(probe.time, "monotonic", clock.monotonic)
        monkeypatch.setattr(
            probe,
            "parse_dns_response",
            lambda _data: SimpleNamespace(
                header=SimpleNamespace(is_response=False),
                records=_cache_chain(),
            ),
        )
        transport = FakeSweepTransport(clock, ReceiveEvent(0.0, b"query"))

        result = await probe.sweep(2.0, transport)

        assert result.packet_count == 0
        assert result.lifx_packet_count == 0
        assert result.malformed_count == 0
        assert result.sources == set()
        assert result.cache.owners_for(16) == ()
        assert result.resolved == []

    @pytest.mark.asyncio
    async def test_probe_goodbye_removes_record_before_report(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A goodbye removes its exact RR only after the one-second grace."""
        clock = FakeClock()
        _script_probe_responses(
            monkeypatch,
            clock,
            {b"positive": _cache_chain(), b"goodbye": [_address_record(ttl=0)]},
        )
        transport = FakeSweepTransport(
            clock,
            ReceiveEvent(0.0, b"positive"),
            ReceiveEvent(0.2, b"goodbye"),
        )

        result = await probe.sweep(2.0, transport)

        assert result.resolved == []
        assert result.cache.addresses_for("synthetic-host.local") == frozenset()

    @pytest.mark.asyncio
    async def test_probe_goodbye_expires_during_receive_wait(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The expiry deadline wakes an otherwise quiet receive wait."""
        clock = FakeClock()
        retained = _cache_chain(
            instance="retained._lifx._udp.local",
            target="retained-host.local",
            address="192.0.2.21",
        )
        _script_probe_responses(
            monkeypatch,
            clock,
            {
                b"chains": [*_cache_chain(), *retained],
                b"goodbye": [_address_record(ttl=0)],
            },
        )
        transport = FakeSweepTransport(
            clock,
            ReceiveEvent(0.0, b"chains"),
            ReceiveEvent(0.25, b"goodbye"),
        )

        result = await probe.sweep(2.0, transport)

        assert [record.serial for record in result.resolved] == [TARGET_SERIAL]
        assert result.resolved[0].ip == "192.0.2.21"
        assert any(
            timeout == pytest.approx(0.75) for timeout in transport.receive_timeouts
        )

    @pytest.mark.asyncio
    async def test_probe_goodbye_rescue_keeps_record_visible(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A positive reannouncement clears the pending exact-RR expiry."""
        clock = FakeClock()
        _script_probe_responses(
            monkeypatch,
            clock,
            {
                b"positive": _cache_chain(),
                b"goodbye": [_address_record(ttl=0)],
                b"rescue": [_address_record(ttl=120)],
            },
        )
        transport = FakeSweepTransport(
            clock,
            ReceiveEvent(0.0, b"positive"),
            ReceiveEvent(0.2, b"goodbye"),
            ReceiveEvent(0.8, b"rescue"),
        )

        result = await probe.sweep(2.0, transport)

        assert [record.ip for record in result.resolved] == ["192.0.2.20"]

    @pytest.mark.asyncio
    async def test_probe_receive_timeout_is_minimum_of_all_four_deadlines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each wait stops at the nearest overall, idle, goodbye, or PTR event."""
        clock = FakeClock()
        _script_probe_responses(
            monkeypatch,
            clock,
            {b"positive": _cache_chain(), b"goodbye": [_address_record(ttl=0)]},
        )
        transport = FakeSweepTransport(
            clock,
            ReceiveEvent(0.0, b"positive"),
            ReceiveEvent(0.25, b"goodbye"),
        )

        await probe.sweep(5.0, transport)

        assert transport.receive_timeouts[:4] == pytest.approx([1.0, 1.0, 0.75, 0.25])
        assert all(timeout >= 0 for timeout in transport.receive_timeouts)

    @pytest.mark.asyncio
    async def test_probe_ptr_retransmits_at_one_and_three_seconds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The initial PTR send has exactly the production one/three repeats."""
        clock = FakeClock()
        _script_probe_responses(monkeypatch, clock, {})
        transport = FakeSweepTransport(clock)

        await probe.sweep(5.0, transport)

        ptr_query = probe.build_ptr_query(probe.LIFX_MDNS_SERVICE)
        assert transport.sent == [ptr_query, ptr_query, ptr_query]

    @pytest.mark.asyncio
    async def test_probe_stops_when_deadline_has_no_remaining_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-positive remaining duration terminates before receive."""

        class ExhaustedDeadline:
            idle_expired = False
            overall_expired = False

            def remaining(self) -> float:
                return 0.0

        clock = FakeClock()
        monkeypatch.setattr(probe.time, "monotonic", clock.monotonic)
        monkeypatch.setattr(probe, "IdleDeadline", lambda *_args: ExhaustedDeadline())
        transport = FakeSweepTransport(clock)

        await probe.sweep(5.0, transport)

        assert transport.receive_timeouts == []

    @pytest.mark.asyncio
    async def test_probe_rechecks_due_cache_cause_without_positive_wait(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A due cache wake-up returns directly to ordered clock handling."""

        class DueCache(probe._LifxRecordCache):
            def next_expiry_delay(self, now: float) -> float:
                return 0.0

        class SecondLoopDeadline:
            idle_expired = False

            def __init__(self) -> None:
                self.checks = 0

            @property
            def overall_expired(self) -> bool:
                self.checks += 1
                return self.checks > 1

            def remaining(self) -> float:
                return 1.0

        clock = FakeClock()
        monkeypatch.setattr(probe.time, "monotonic", clock.monotonic)
        monkeypatch.setattr(probe, "_LifxRecordCache", DueCache)
        monkeypatch.setattr(
            probe,
            "IdleDeadline",
            lambda *_args: SecondLoopDeadline(),
        )
        transport = FakeSweepTransport(clock)

        await probe.sweep(5.0, transport)

        assert transport.receive_timeouts == []

    @pytest.mark.asyncio
    async def test_probe_simultaneous_expiry_and_ptr_retransmit_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Expiry is processed before one due retransmission at the same instant."""
        clock = FakeClock()
        events: list[str] = []

        class OrderedCache(probe._LifxRecordCache):
            def expire(self, now: float) -> int:
                events.append(f"expire:{now}")
                return super().expire(now)

        class OrderedTransport(FakeSweepTransport):
            async def send(self, data: bytes) -> None:
                events.append(f"send:{clock.now}")
                await super().send(data)

        monkeypatch.setattr(probe, "_LifxRecordCache", OrderedCache)
        _script_probe_responses(
            monkeypatch,
            clock,
            {
                b"positive-goodbye": [*_cache_chain(), _address_record(ttl=0)],
            },
        )
        transport = OrderedTransport(clock, ReceiveEvent(0.0, b"positive-goodbye"))

        await probe.sweep(1.5, transport)

        assert events.count("expire:1.0") == 1
        assert events.index("expire:1.0") < events.index("send:1.0")
        assert transport.sent.count(probe.build_ptr_query(probe.LIFX_MDNS_SERVICE)) == 2

    @pytest.mark.asyncio
    async def test_probe_valid_packet_resets_idle_deadline_after_consumer_work(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Parser/cache work is excluded from the measured network silence."""
        clock = FakeClock()
        monkeypatch.setattr(probe.time, "monotonic", clock.monotonic)

        def parse_after_work(data: bytes) -> SimpleNamespace:
            clock.advance(2.0)
            return SimpleNamespace(
                header=SimpleNamespace(is_response=True),
                records=_cache_chain(),
            )

        monkeypatch.setattr(probe, "parse_dns_response", parse_after_work)
        transport = FakeSweepTransport(clock, ReceiveEvent(0.0, b"packet"))

        await probe.sweep(10.0, transport)

        assert clock.now == pytest.approx(6.0)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "terminal",
        [LifxTimeoutError("done"), asyncio.CancelledError(), RuntimeError("boom")],
    )
    async def test_probe_closes_transport_on_timeout_cancellation_and_exception(
        self,
        monkeypatch: pytest.MonkeyPatch,
        terminal: BaseException,
    ) -> None:
        """Every normal or exceptional terminal path leaves the context."""
        clock = FakeClock()
        _script_probe_responses(monkeypatch, clock, {})
        transport = FakeSweepTransport(clock, ReceiveEvent(0.0, terminal))

        if isinstance(terminal, LifxTimeoutError):
            await probe.sweep(1.0, transport)
        else:
            with pytest.raises(type(terminal)):
                await probe.sweep(1.0, transport)

        assert transport.closed == 1


class ScriptedPendingCache:
    """Minimal cache double exposing successive SRV target reports."""

    def __init__(self, *reports: list[str]) -> None:
        self.reports = list(reports)

    def expire(self, now: float) -> int:
        """No synthetic goodbye is pending in follow-up ledger tests."""
        return 0

    def next_expiry_delay(self, now: float) -> None:
        """Report no scheduled cache wake-up."""
        return None

    def add_packet(self, records: list[DnsResourceRecord], source_ip: str) -> bool:
        """Treat every scripted packet as valid LIFX activity."""
        return True

    def pending_targets(self) -> list[str]:
        """Return the next deterministic cache-owned target report."""
        return self.reports.pop(0) if self.reports else []

    def resolve(self) -> list[_LifxServiceRecord]:
        """These tests exercise outbound work, not record construction."""
        return []


class FailingAddressTransport(FakeSweepTransport):
    """Transport that can fail selected address-query payloads."""

    def __init__(
        self,
        clock: FakeClock,
        *events: ReceiveEvent,
        failures: dict[bytes, int] | None = None,
    ) -> None:
        super().__init__(clock, *events)
        self.failures = dict(failures or {})

    async def send(self, data: bytes) -> None:
        """Record every attempt and raise for configured address queries."""
        await super().send(data)
        remaining = self.failures.get(data, 0)
        if remaining:
            self.failures[data] = remaining - 1
            raise LifxNetworkError("synthetic follow-up failure")


async def _run_follow_up_sweep(
    monkeypatch: pytest.MonkeyPatch,
    cache: ScriptedPendingCache,
    transport: FakeSweepTransport,
    *,
    verbose: bool = False,
) -> probe.SweepResult:
    """Run one probe sweep around a cache-owned pending-target script."""
    monkeypatch.setattr(probe.time, "monotonic", transport.clock.monotonic)
    monkeypatch.setattr(probe, "_LifxRecordCache", lambda: cache)
    monkeypatch.setattr(
        probe,
        "parse_dns_response",
        lambda data: SimpleNamespace(
            header=SimpleNamespace(is_response=True),
            records=[],
        ),
    )
    return await probe.sweep(2.0, transport, verbose=verbose)


class TestSweepFollowUpLedger:
    """The diagnostic probe carries production's bounded send ledgers."""

    @pytest.mark.asyncio
    async def test_probe_successful_follow_up_is_sent_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Repeated pending reports cannot repeat a successful send."""
        clock = FakeClock()
        query = probe.build_address_query("host.local")
        cache = ScriptedPendingCache(*([["host.local"]] * 3))
        transport = FakeSweepTransport(
            clock,
            ReceiveEvent(0.0, b"one"),
            ReceiveEvent(0.1, b"two"),
            ReceiveEvent(0.2, b"three"),
        )

        await _run_follow_up_sweep(monkeypatch, cache, transport)

        assert transport.sent.count(query) == 1

    @pytest.mark.asyncio
    async def test_probe_verbose_follow_up_reports_safe_action(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verbose mode identifies the synthetic follow-up action."""
        clock = FakeClock()
        cache = ScriptedPendingCache(["synthetic-host.local"])
        transport = FakeSweepTransport(clock, ReceiveEvent(0.0, b"packet"))

        await _run_follow_up_sweep(
            monkeypatch,
            cache,
            transport,
            verbose=True,
        )

        assert "follow-up A/AAAA query" in capsys.readouterr().out

    @pytest.mark.asyncio
    async def test_probe_failed_follow_up_retries_exactly_twice(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed case-folded target receives two attempts and no third."""
        clock = FakeClock()
        query = probe.build_address_query("host.local")
        cache = ScriptedPendingCache(*([["host.local"]] * 3))
        transport = FailingAddressTransport(
            clock,
            ReceiveEvent(0.0, b"one"),
            ReceiveEvent(0.1, b"two"),
            ReceiveEvent(0.2, b"three"),
            failures={query: 3},
        )

        await _run_follow_up_sweep(monkeypatch, cache, transport)

        assert transport.sent.count(query) == 2

    @pytest.mark.asyncio
    async def test_probe_follow_up_failure_isolated_from_other_targets(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One failed target neither aborts nor suppresses a later target."""
        clock = FakeClock()
        failed = probe.build_address_query("failed.local")
        successful = probe.build_address_query("successful.local")
        cache = ScriptedPendingCache(["failed.local", "successful.local"])
        transport = FailingAddressTransport(
            clock,
            ReceiveEvent(0.0, b"packet"),
            failures={failed: 1},
        )

        await _run_follow_up_sweep(monkeypatch, cache, transport)

        assert transport.sent.count(failed) == 1
        assert transport.sent.count(successful) == 1

    @pytest.mark.asyncio
    async def test_probe_follow_up_tracks_target_identity_case_insensitively(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Case variants share one admission, attempt, and success identity."""
        clock = FakeClock()
        cache = ScriptedPendingCache(["Host.Local"], ["host.local"], ["HOST.LOCAL"])
        transport = FakeSweepTransport(
            clock,
            ReceiveEvent(0.0, b"one"),
            ReceiveEvent(0.1, b"two"),
            ReceiveEvent(0.2, b"three"),
        )

        await _run_follow_up_sweep(monkeypatch, cache, transport)

        address_queries = [
            data
            for data in transport.sent
            if data != probe.build_ptr_query(probe.LIFX_MDNS_SERVICE)
        ]
        assert address_queries == [probe.build_address_query("Host.Local")]

    @pytest.mark.asyncio
    async def test_probe_follow_up_sends_64th_target_and_rejects_65th(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Failed sends still consume admission and stop after target 64."""
        clock = FakeClock()
        targets = [f"host{index}.local" for index in range(65)]
        queries = {probe.build_address_query(target): 1 for target in targets}
        cache = ScriptedPendingCache(targets)
        transport = FailingAddressTransport(
            clock,
            ReceiveEvent(0.0, b"packet"),
            failures=queries,
        )

        await _run_follow_up_sweep(monkeypatch, cache, transport)

        assert probe.build_address_query("host63.local") in transport.sent
        assert probe.build_address_query("host64.local") not in transport.sent
        assert len([data for data in transport.sent if data in queries]) == 64

    @pytest.mark.asyncio
    async def test_probe_follow_up_uses_srv_target_not_packet_source(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only the cache's SRV-derived target becomes a query name."""
        clock = FakeClock()
        cache = ScriptedPendingCache(["srv-target.local"])
        transport = FakeSweepTransport(clock, ReceiveEvent(0.0, b"packet"))

        await _run_follow_up_sweep(monkeypatch, cache, transport)

        assert probe.build_address_query("srv-target.local") in transport.sent
        assert probe.build_address_query("192.0.2.1") not in transport.sent

    @pytest.mark.asyncio
    async def test_probe_follow_up_completion_stops_retries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Once the cache stops reporting a target, no retry is invented."""
        clock = FakeClock()
        query = probe.build_address_query("host.local")
        cache = ScriptedPendingCache(["host.local"], [], [])
        transport = FailingAddressTransport(
            clock,
            ReceiveEvent(0.0, b"pending"),
            ReceiveEvent(0.1, b"resolved"),
            ReceiveEvent(0.2, b"duplicate"),
            failures={query: 1},
        )

        await _run_follow_up_sweep(monkeypatch, cache, transport)

        assert transport.sent.count(query) == 1


def make_record(
    serial: str = TARGET_SERIAL,
    ip: str = ULA_ADDRESS,
    product_id: int = MATRIX_PRODUCT_ID,
) -> _LifxServiceRecord:
    """Build a service record the way a resolved mDNS sweep would."""
    return _LifxServiceRecord(
        serial=serial, ip=ip, port=56700, product_id=product_id, firmware="4.10"
    )


class FakeMatrix(MatrixLight):
    """A MatrixLight that answers from memory and records every write.

    Subclasses the real class rather than duck-typing it, because the probe
    branches on `isinstance(device, MatrixLight)` to decide which state shape
    to capture. A duck would take the plain-light path and prove nothing.
    """

    def __init__(
        self,
        *,
        power: int = 0,
        effect_type: FirmwareEffect = FirmwareEffect.MORPH,
        applies_writes: bool = True,
        colour: HSBK | None = None,
    ) -> None:
        super().__init__(serial=TARGET_SERIAL, ip=ULA_ADDRESS)
        self.calls: list[tuple[str, Any]] = []
        self.applies_writes = applies_writes
        self._effect_type = effect_type
        self._power_level = power
        self._colour = colour if colour is not None else HSBK(10.0, 1.0, 1.0, 3500)

    async def __aenter__(self) -> FakeMatrix:
        """Enter without opening a connection."""
        return self

    async def __aexit__(self, *args: object) -> bool:
        """Exit without closing anything."""
        return False

    async def get_all_tile_colors(self) -> list[list[HSBK]]:
        """Return the captured per-tile image."""
        self.calls.append(("get_all_tile_colors", None))
        return [list(tile) for tile in TILE_COLOURS]

    async def get_power(self) -> int:
        """Return the current power level."""
        self.calls.append(("get_power", None))
        return self._power_level

    async def set_power(self, level: bool | int) -> None:
        """Record the write, applying it only when this fake obeys writes."""
        self.calls.append(("set_power", level))
        if self.applies_writes:
            self._power_level = 65535 if level in (True, 65535) else 0

    async def get_effect(self) -> MatrixEffect:
        """Return the running firmware effect."""
        self.calls.append(("get_effect", None))
        return MatrixEffect(
            effect_type=self._effect_type, speed=5000, duration=0, from_device=True
        )

    async def set_effect(self, *args: object, **kwargs: object) -> None:
        """Record a firmware effect re-application."""
        self.calls.append(("set_effect", kwargs))

    async def set_matrix_colors(
        self, tile_index: int, colors: list[HSBK], duration: int = 0
    ) -> None:
        """Record a per-tile restore."""
        self.calls.append(("set_matrix_colors", (tile_index, list(colors))))

    async def get_color(self) -> tuple[HSBK, int, str]:
        """Return the colour, power and label triple."""
        self.calls.append(("get_color", None))
        return (self._colour, self._power_level, "Test Candle")

    async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
        """Record the write, applying it only when this fake obeys writes."""
        self.calls.append(("set_color", color))
        if self.applies_writes:
            self._colour = color


class RampingMatrix(FakeMatrix):
    """A FakeMatrix whose power readback ramps, the way real firmware does.

    `get_power()` yields each value in `ramp` once before it starts reporting
    what the last write actually set. This is the shape measured against the
    Thread Tube on 2026-08-28: 4980 at t+0.098s, 65535 at t+0.525s. Without a
    double of this shape the settle loop cannot be shown to do anything.
    """

    def __init__(self, *, ramp: list[int], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.ramp = list(ramp)
        self._ramping = False

    async def set_power(self, level: bool | int) -> None:
        """Apply the write and start reporting the ramp, as firmware does."""
        await super().set_power(level)
        self._ramping = True

    async def get_power(self) -> int:
        """Yield the next ramp reading, then defer to the settled level.

        Reads taken before any power write report the resting level, so the
        stage's pre-write capture sees the truth and the ramp only stands
        between the write and its result, which is where it sits in reality.
        """
        if self._ramping and self.ramp:
            self.calls.append(("get_power", None))
            return self.ramp.pop(0)
        return await super().get_power()


class StuckPowerMatrix(FakeMatrix):
    """A FakeMatrix whose power never leaves the ramp.

    Stands for a light that acknowledges the write and then never gets there,
    which is the failure the settle loop must still catch rather than paper
    over.
    """

    async def get_power(self) -> int:
        """Report the same mid-ramp level forever."""
        self.calls.append(("get_power", None))
        return 5242


class LaggingColourMatrix(FakeMatrix):
    """A FakeMatrix that applies colour writes but reports them late."""

    def __init__(self, *, lag: int = 1, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.lag = lag
        self._stale: HSBK | None = None

    async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
        """Apply the write, remembering what the device showed before it."""
        self._stale = self._colour
        await super().set_color(color, duration)

    async def get_color(self) -> tuple[HSBK, int, str]:
        """Report the pre-write colour until the lag is spent."""
        if self._stale is not None and self.lag > 0:
            self.lag -= 1
            self.calls.append(("get_color", None))
            return (self._stale, self._power_level, "Test Candle")
        return await super().get_color()


class FakeLight(Light):
    """A plain Light that answers from memory."""

    def __init__(self) -> None:
        super().__init__(serial=TARGET_SERIAL, ip=ULA_ADDRESS)
        self.calls: list[tuple[str, Any]] = []
        self._colour = HSBK(200.0, 0.4, 0.6, 3000)

    async def get_color(self) -> tuple[HSBK, int, str]:
        """Return the colour, power and label triple."""
        self.calls.append(("get_color", None))
        return (self._colour, 65535, "Desk Lamp")

    async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
        """Record the write."""
        self.calls.append(("set_color", color))

    async def set_power(self, level: bool | int) -> None:
        """Record the write."""
        self.calls.append(("set_power", level))


class FakeMultiZone(MultiZoneLight):
    """A MultiZoneLight with a non-uniform 170-zone image and MOVE effect."""

    def __init__(self, *, extended: bool = True, power: int = 65535) -> None:
        super().__init__(serial=TARGET_SERIAL, ip=ULA_ADDRESS)
        capabilities = get_product(32 if extended else 31)
        assert capabilities is not None
        self._capabilities = capabilities
        self._zone_count = len(ZONE_COLOURS)
        self.calls: list[tuple[str, Any]] = []
        self._power_level = power
        self._colour = HSBK(25.0, 0.8, 0.6, 3500)
        self._zones = list(ZONE_COLOURS)
        self.saved_effect = MultiZoneEffect(
            effect_type=FirmwareEffect.MOVE,
            speed=4321,
            duration=9876,
            parameters=[7, 1, 2, 3, 4, 5, 6, 8],
        )

    async def __aenter__(self) -> FakeMultiZone:
        """Enter without opening a connection."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit without closing anything."""

    async def get_all_color_zones(self) -> list[HSBK]:
        """Return a copy of the non-uniform zone image."""
        self.calls.append(("get_all_color_zones", None))
        return list(self._zones)

    async def get_power(self) -> int:
        """Return the current power level."""
        self.calls.append(("get_power", None))
        return self._power_level

    async def get_effect(self) -> MultiZoneEffect:
        """Return the complete running MOVE configuration."""
        self.calls.append(("get_effect", None))
        return self.saved_effect

    async def get_color(self) -> tuple[HSBK, int, str]:
        """Return the representative colour used by the control stage."""
        self.calls.append(("get_color", None))
        return self._colour, self._power_level, "Test Strip"

    async def set_power(self, level: bool | int, duration: float = 0.0) -> None:
        """Record and apply a power write."""
        self.calls.append(("set_power", level))
        self._power_level = 65535 if level in (True, 65535) else 0

    async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
        """Record and apply the representative control colour."""
        self.calls.append(("set_color", color))
        self._colour = color

    async def set_all_color_zones(
        self,
        colors: list[HSBK],
        start: int = 0,
        end: int | None = None,
        duration: float = 0.0,
        apply: MultiZoneApplicationRequest = MultiZoneApplicationRequest.APPLY,
    ) -> None:
        """Record use of the capability-aware public restoration contract."""
        self.calls.append(("set_all_color_zones", list(colors)))
        await super().set_all_color_zones(colors, start, end, duration, apply)

    async def set_color_zones(
        self,
        start: int,
        end: int,
        color: HSBK,
        duration: float = 0.0,
        apply: MultiZoneApplicationRequest = MultiZoneApplicationRequest.APPLY,
    ) -> None:
        """Record and apply one legacy zone run."""
        self.calls.append(("set_color_zones", (start, end, color, apply)))
        self._zones[start : end + 1] = [color] * (end - start + 1)

    async def set_extended_color_zones(
        self,
        zone_index: int,
        colors: list[HSBK],
        duration: float = 0.0,
        apply: MultiZoneApplicationRequest = MultiZoneApplicationRequest.APPLY,
        *,
        fast: bool = False,
    ) -> None:
        """Record one protocol-sized zone restoration chunk."""
        self.calls.append(
            ("set_extended_color_zones", (zone_index, list(colors), apply))
        )
        self._zones[zone_index : zone_index + len(colors)] = colors

    async def set_effect(self, effect: MultiZoneEffect) -> None:
        """Record the exact firmware-effect configuration."""
        self.calls.append(("set_effect", effect))
        self.saved_effect = effect


class FakeAnimator:
    """An Animator double that counts frames and close() calls."""

    def __init__(self, *, raises: bool = False) -> None:
        self.pixel_count = 4
        self.frames = 0
        self.closed = 0
        self.raises = raises

    def send_frame(self, hsbk: list[tuple[int, int, int, int]]) -> AnimatorStats:
        """Count the frame, or blow up if this double is the failing one."""
        self.frames += 1
        if self.raises:
            raise OSError("radio went away mid-frame")
        return AnimatorStats(packets_sent=2, total_time_ms=0.5)

    def close(self) -> None:
        """Record that the socket was released."""
        self.closed += 1


@pytest.fixture
def fast_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink the streaming run to a single frame so tests stay quick."""
    monkeypatch.setattr(probe, "_STREAM_SECONDS", 0.05)
    monkeypatch.setattr(probe, "_STREAM_FPS", 20.0)


@pytest.fixture(autouse=True)
def fast_settle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink the control stage's settle window so tests stay quick.

    `run_control_stage` reads these two at call time instead of binding them
    as default arguments, precisely so they can be shrunk here. Without this
    every test driving a device that refuses a write would wait out the real
    two second deadline twice over.
    """
    monkeypatch.setattr(probe, "_SETTLE_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(probe, "_SETTLE_POLL_SECONDS", 0.005)


def use_animator(monkeypatch: pytest.MonkeyPatch, animator: FakeAnimator) -> None:
    """Point the streaming stage at a double instead of the real factories."""

    async def _factory(device: Light) -> Any:
        return animator

    monkeypatch.setattr(probe, "_build_animator", _factory)


class TestSyntheticCacheReporting:
    """The probe's private reporting seam follows the live-RR cache model."""

    def test_instance_view_retains_unordered_advertised_addresses(self) -> None:
        """Synthetic inspection needs no socket, daemon, or hardware access."""
        instance = "synthetic._lifx._udp.local"
        host = "synthetic-host.local"
        txt = TxtData(
            strings=["id=d073d5aa11bb", "p=57", "fw=4.10"],
            pairs={"id": "d073d5aa11bb", "p": "57", "fw": "4.10"},
        )
        txt_rdata = b"\x0fid=d073d5aa11bb\x04p=57\x07fw=4.10"
        srv = SrvData(priority=0, weight=0, port=56700, target=host)
        cache = probe._LifxRecordCache()
        cache.add_packet(
            [
                DnsResourceRecord(instance, 16, 1, 120, txt_rdata, txt),
                DnsResourceRecord(instance, 33, 1, 120, b"srv", srv),
                DnsResourceRecord(host, 1, 1, 120, b"\xc0\x00\x02\x14", "192.0.2.20"),
                DnsResourceRecord(
                    host,
                    28,
                    1,
                    120,
                    b"\xfd" + (b"\x00" * 13) + b"\x00\x20",
                    "fd00::20",
                ),
            ],
            "192.0.2.10",
        )

        [(reported_instance, view)] = probe._instance_view(cache)

        assert reported_instance == instance
        assert view["addresses"] == frozenset({"192.0.2.20", "fd00::20"})
        assert view["chosen"] == "192.0.2.20"
        assert view["fallback"] == "192.0.2.10"


class TestSelectTarget:
    """_select_target() resolves --serial to exactly one device, or explains."""

    def test_returns_the_device_matching_the_requested_serial(self) -> None:
        """A serial present in the sweep yields the right device class."""
        records = [make_record(serial="d073d5000001"), make_record()]

        target = probe._select_target(records, TARGET_SERIAL)

        assert isinstance(target, MatrixLight)
        assert target.serial == TARGET_SERIAL
        assert target.ip == ULA_ADDRESS

    def test_tolerates_colons_hyphens_and_upper_case_in_the_serial(self) -> None:
        """Operators paste serials in whatever shape their notes hold."""
        target = probe._select_target([make_record()], "D0:73-D5:AA:11:BB")

        assert isinstance(target, MatrixLight)
        assert target.serial == TARGET_SERIAL

    def test_returns_not_found_for_a_serial_no_record_carries(self) -> None:
        """A mistyped serial is a recorded failure, not a traceback."""
        result = probe._select_target([make_record()], "d073d5ffffff")

        assert isinstance(result, probe.TargetNotFound)
        assert result.serial == "d073d5ffffff"
        assert "no discovered device carries that serial" in result.reason

    def test_returns_not_found_when_the_sweep_found_nothing(self) -> None:
        """An empty record set cannot produce a target."""
        result = probe._select_target([], TARGET_SERIAL)

        assert isinstance(result, probe.TargetNotFound)
        assert "no discovered device carries that serial" in result.reason

    def test_returns_not_found_for_a_zoneless_link_local_address(self) -> None:
        """A link-local literal with no zone ID cannot be routed to."""
        result = probe._select_target([make_record(ip="fe80::1")], TARGET_SERIAL)

        assert isinstance(result, probe.TargetNotFound)
        assert "no zone ID" in result.reason

    def test_returns_not_found_for_a_relay_only_product(self) -> None:
        """A switch has nothing to control, so there is no target."""
        record = make_record(product_id=SWITCH_PRODUCT_ID)

        result = probe._select_target([record], TARGET_SERIAL)

        assert isinstance(result, probe.TargetNotFound)
        assert "relay/button-only" in result.reason


class TestStageResult:
    """_stage_result() maps an observed outcome onto the record's vocabulary."""

    def test_a_successful_stage_is_passed(self) -> None:
        """True means the stage ran and every operation held."""
        assert probe._stage_result(True) == "passed"

    def test_a_stage_that_ran_and_failed_is_failed(self) -> None:
        """False means the stage ran and something did not hold."""
        assert probe._stage_result(False) == "failed"

    def test_a_stage_that_raised_is_failed(self) -> None:
        """An exception is an observed failure, not an absence of evidence."""
        assert probe._stage_result(OSError("boom")) == "failed"

    def test_a_stage_never_attempted_is_not_run(self) -> None:
        """None is the honest "we never got there" value."""
        assert probe._stage_result(None) == "not_run"


class TestBuildUatRecord:
    """_build_uat_record() assembles sanitised machine-checkable evidence."""

    def test_carries_every_field_the_phase_11_contract_checks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The full key set, with the stages exactly as observed."""
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/git")
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args, returncode=0, stdout="abc1234\n", stderr=""
            ),
        )
        outcome = probe.TargetOutcome(
            connect="passed", control="passed", streaming="failed", restored=True
        )

        record = probe._build_uat_record(TARGET_ALIAS, "ipv6", "thread", outcome)

        assert set(record) == {
            "schema_version",
            "kind",
            "phase",
            "device_alias",
            "network",
            "timestamp",
            "library_head",
            "stages",
            "restored",
        }
        assert record["schema_version"] == 2
        assert record["kind"] == "thread-hardware-uat-sanitised"
        assert record["phase"] == "11"
        assert record["device_alias"] == TARGET_ALIAS
        assert record["network"] == {
            "address_family": "ipv6",
            "connectivity": "thread",
        }
        assert record["library_head"] == "abc1234"
        assert record["stages"] == {
            "connect": "passed",
            "control": "passed",
            "streaming": "failed",
        }
        assert record["restored"] is True

    def test_timestamp_is_iso_8601_with_a_timezone(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A naive timestamp cannot be checked against the phase window."""
        from datetime import datetime

        monkeypatch.setattr(shutil, "which", lambda name: None)

        record = probe._build_uat_record(
            TARGET_ALIAS, None, None, probe.TargetOutcome()
        )

        stamp = record["timestamp"]
        assert isinstance(stamp, str)
        assert datetime.fromisoformat(stamp).tzinfo is not None

    def test_library_head_is_none_when_git_is_not_on_the_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No git means no head SHA, recorded honestly as null."""
        monkeypatch.setattr(shutil, "which", lambda name: None)

        record = probe._build_uat_record(
            TARGET_ALIAS, "ipv6", "thread", probe.TargetOutcome()
        )

        assert record["library_head"] is None

    def test_library_head_is_none_when_git_rev_parse_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A git that exists but cannot answer is not a reason to crash."""
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/git")

        def _boom(*args: object, **kwargs: object) -> None:
            raise subprocess.CalledProcessError(128, "git")

        monkeypatch.setattr(subprocess, "run", _boom)

        record = probe._build_uat_record(
            TARGET_ALIAS, "ipv6", "thread", probe.TargetOutcome()
        )

        assert record["library_head"] is None

    def test_serialised_record_omits_raw_serial_and_ip(self) -> None:
        """Evidence contains only the alias and non-identifying network facts."""
        record = probe._build_uat_record(
            TARGET_ALIAS, "ipv6", "thread", probe.TargetOutcome()
        )

        serialised = json.dumps(record)

        assert TARGET_SERIAL not in serialised
        assert ULA_ADDRESS not in serialised
        assert "device_serial" not in serialised
        assert "device_ip" not in serialised


class TestWriteUatRecord:
    """_write_uat_record() puts valid JSON on disk."""

    def test_writes_json_that_round_trips(self, tmp_path: Path) -> None:
        """A produced record passes the exact Phase 11 consumer after JSON."""
        outcome = probe.TargetOutcome(connect="passed", control="passed")
        record = probe._build_uat_record(TARGET_ALIAS, "ipv6", "thread", outcome)
        path = tmp_path / "nested" / "11-UAT-RESULTS.json"

        probe._write_uat_record(record, path, raw_serial=TARGET_SERIAL)

        loaded = json.loads(path.read_text(encoding="utf-8"))
        probe._validate_uat_record(loaded, raw_serial=TARGET_SERIAL)
        assert loaded["stages"]["control"] == "passed"
        assert loaded["kind"] == "thread-hardware-uat-sanitised"

    def test_rejects_the_immutable_phase_10_contract(self, tmp_path: Path) -> None:
        """Schema v2 cannot masquerade as or overwrite historical Phase 10 UAT."""
        record = probe._build_uat_record(
            TARGET_ALIAS, "ipv6", "thread", probe.TargetOutcome()
        )
        record.update(
            schema_version=1,
            kind="thread-hardware-uat",
            phase="10",
        )
        path = tmp_path / "record.json"

        with pytest.raises(ValueError, match="schema version"):
            probe._write_uat_record(record, path, raw_serial=TARGET_SERIAL)

        assert not path.exists()

    @pytest.mark.parametrize(
        "location", ["library_head", "nested_dict", "nested_key", "list"]
    )
    def test_rejects_raw_serial_anywhere_in_the_complete_record(
        self, tmp_path: Path, location: str
    ) -> None:
        """Privacy scanning precedes and complements field-shape validation."""
        record = probe._build_uat_record(
            TARGET_ALIAS, "ipv6", "thread", probe.TargetOutcome()
        )
        if location == "library_head":
            record["library_head"] = TARGET_SERIAL
        elif location == "nested_dict":
            record["network"] = {
                "address_family": "ipv6",
                "connectivity": {"detail": f"raw-{TARGET_SERIAL.upper()}"},
            }
        elif location == "nested_key":
            record["network"] = {
                "address_family": "ipv6",
                TARGET_SERIAL: "thread",
            }
        else:
            separated_serial = ".".join(
                TARGET_SERIAL[index : index + 2]
                for index in range(0, len(TARGET_SERIAL), 2)
            )
            record["stages"] = {
                "connect": "passed",
                "control": "passed",
                "streaming": [separated_serial],
            }
        path = tmp_path / "record.json"

        with pytest.raises(ValueError, match="contains the raw device serial"):
            probe._validate_uat_record(record, raw_serial=TARGET_SERIAL)
        with pytest.raises(ValueError, match="contains the raw device serial"):
            probe._write_uat_record(record, path, raw_serial=TARGET_SERIAL)

        assert not path.exists()

    def test_retains_field_specific_validation_after_privacy_scan(
        self, tmp_path: Path
    ) -> None:
        """Non-sensitive malformed fields still receive their specific error."""
        record = probe._build_uat_record(
            TARGET_ALIAS, "ipv6", "thread", probe.TargetOutcome()
        )
        record["library_head"] = "not-a-git-object"
        path = tmp_path / "record.json"

        with pytest.raises(ValueError, match="library head"):
            probe._validate_uat_record(record, raw_serial=TARGET_SERIAL)
        with pytest.raises(ValueError, match="library head"):
            probe._write_uat_record(record, path, raw_serial=TARGET_SERIAL)

        assert not path.exists()

    @pytest.mark.parametrize(
        ("malformation", "message"),
        [
            ("record-fields", "record fields"),
            ("kind", "contract identity"),
            ("phase", "contract identity"),
            ("alias-type", "device alias"),
            ("network-type", "network properties"),
            ("network-fields", "network properties"),
            ("address-family", "address family"),
            ("connectivity", "connectivity"),
            ("timestamp-type", "timestamp"),
            ("timestamp-format", "timestamp"),
            ("timestamp-timezone", "timestamp"),
            ("stages-type", "stages"),
            ("stage-fields", "stages"),
            ("stage-result", "stage result"),
            ("restored-type", "restoration result"),
        ],
    )
    def test_rejects_every_malformed_schema_v2_contract_shape(
        self, malformation: str, message: str
    ) -> None:
        """Every schema-v2 structural rejection remains executable evidence."""
        record = probe._build_uat_record(
            TARGET_ALIAS, "ipv6", "thread", probe.TargetOutcome()
        )

        if malformation == "record-fields":
            record["unexpected"] = True
        elif malformation == "kind":
            record["kind"] = "thread-diagnostic"
        elif malformation == "phase":
            record["phase"] = "12"
        elif malformation == "alias-type":
            record["device_alias"] = 1
        elif malformation == "network-type":
            record["network"] = []
        elif malformation == "network-fields":
            record["network"] = {"address_family": "ipv6"}
        elif malformation == "address-family":
            record["network"] = {
                "address_family": "bluetooth",
                "connectivity": "thread",
            }
        elif malformation == "connectivity":
            record["network"] = {
                "address_family": "ipv6",
                "connectivity": "ethernet",
            }
        elif malformation == "timestamp-type":
            record["timestamp"] = 1
        elif malformation == "timestamp-format":
            record["timestamp"] = "not-a-timestamp"
        elif malformation == "timestamp-timezone":
            record["timestamp"] = "2026-08-29T12:00:00"
        elif malformation == "stages-type":
            record["stages"] = []
        elif malformation == "stage-fields":
            record["stages"] = {"connect": "passed"}
        elif malformation == "stage-result":
            record["stages"] = {
                "connect": "unknown",
                "control": "not_run",
                "streaming": "not_run",
            }
        elif malformation == "restored-type":
            record["restored"] = "yes"
        else:
            pytest.fail(f"unhandled malformation: {malformation}")

        with pytest.raises(ValueError, match=message):
            probe._validate_uat_record(record, raw_serial=TARGET_SERIAL)

    @pytest.mark.parametrize(
        "record",
        [
            {"device_serial": TARGET_SERIAL, "device_ip": ULA_ADDRESS},
            {"stages": [{"ip": ULA_ADDRESS}]},
        ],
        ids=["top-level", "nested-list"],
    )
    def test_rejects_legacy_raw_identifier_fields(
        self, tmp_path: Path, record: dict[str, object]
    ) -> None:
        """No output path may receive the old raw-identifier record shape."""
        path = tmp_path / "record.json"

        with pytest.raises(ValueError, match="raw identifiers"):
            probe._write_uat_record(record, path, raw_serial=TARGET_SERIAL)

        assert not path.exists()

    @pytest.mark.parametrize(
        "alias",
        [
            "target-192.0.2.20",
            "target-fd00:1::20",
            "target-fe80::20%en0",
            "target-d073.d5aa.11bb",
            "Target-FD00:1::20",
            f"target-{TARGET_SERIAL}",
        ],
        ids=[
            "embedded-ipv4",
            "embedded-ipv6",
            "scoped-ipv6",
            "dotted-serial",
            "mixed-case-ipv6",
            "compact-serial",
        ],
    )
    def test_revalidates_unsafe_final_alias_before_writing(
        self, tmp_path: Path, alias: str
    ) -> None:
        """A constructed final record cannot bypass the CLI alias check."""
        record = probe._build_uat_record(alias, "ipv6", "thread", probe.TargetOutcome())
        path = tmp_path / "record.json"

        with pytest.raises(ValueError, match="--device-alias|raw device serial"):
            probe._write_uat_record(record, path, raw_serial=TARGET_SERIAL)

        assert not path.exists()

    async def test_main_writes_no_raw_target_identifier(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Raw selection inputs are reduced before evidence is assembled."""
        path = tmp_path / "record.json"
        args = argparse.Namespace(
            stage="connect",
            timeout=0.1,
            verbose=False,
            serial=TARGET_SERIAL,
            device_alias=TARGET_ALIAS,
            stream=False,
            uat_output=path,
        )

        async def collect(_timeout: float) -> list[_LifxServiceRecord]:
            return [make_record()]

        async def stage_target(
            _device: Light, outcome: probe.TargetOutcome, *, stream: bool
        ) -> None:
            outcome.connect = "passed"
            outcome.control = "passed"

        monkeypatch.setattr(probe, "_collect", collect)
        monkeypatch.setattr(probe, "stage_target", stage_target)

        assert await probe.main_async(args) == 0

        serialised = path.read_text(encoding="utf-8")
        assert TARGET_SERIAL not in serialised
        assert ULA_ADDRESS not in serialised
        assert TARGET_ALIAS in serialised
        loaded = json.loads(serialised)
        assert loaded["network"] == {
            "address_family": "ipv6",
            "connectivity": "wifi",
        }


class TestEvidenceAlias:
    """Operator aliases remain stable without repeating target identifiers."""

    def test_help_names_only_the_phase_11_sanitised_contract(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The current producer must not claim to feed the historical gate."""
        monkeypatch.setattr(sys, "argv", ["ipv6_thread_probe.py", "--help"])

        with pytest.raises(SystemExit) as raised:
            probe.main()

        assert raised.value.code == 0
        help_text = " ".join(capsys.readouterr().out.split())
        assert "Phase 11 schema-v2 diagnostic record" in help_text
        assert "does not replace the Phase 10 merge-gate artefact" in help_text

    def test_accepts_and_trims_a_non_identifying_alias(self) -> None:
        """Whitespace is presentation noise, not part of the stable alias."""
        assert (
            probe._validate_device_alias(f"  {TARGET_ALIAS}  ", TARGET_SERIAL)
            == TARGET_ALIAS
        )

    @pytest.mark.parametrize(
        ("alias", "raw_serial"),
        [
            (TARGET_SERIAL, TARGET_SERIAL),
            (f"target-{TARGET_SERIAL}", "D0:73:D5:AA:11:BB"),
            (f"target-{TARGET_SERIAL}", "d0.73/d5_aa 11-bb"),
        ],
    )
    def test_rejects_an_alias_containing_the_raw_serial(
        self, alias: str, raw_serial: str
    ) -> None:
        """Formatting cannot disguise the selected device's raw identifier."""
        with pytest.raises(ValueError, match="raw device serial"):
            probe._validate_device_alias(alias, raw_serial)

    @pytest.mark.parametrize(
        "alias",
        [
            "target-192.0.2.20",
            "target-fd00:1::20",
            "target-fe80::20%en0",
            "target-d073.d5aa.11bb",
            "Target-FD00:1::20",
        ],
    )
    def test_rejects_aliases_outside_the_safe_grammar(self, alias: str) -> None:
        """Address punctuation, scopes, and mixed case cannot reach evidence."""
        with pytest.raises(ValueError, match="lowercase letter"):
            probe._validate_device_alias(alias, TARGET_SERIAL)

    def test_rejects_an_empty_alias(self) -> None:
        """Whitespace alone cannot correlate evidence across runs."""
        with pytest.raises(ValueError, match="must not be empty"):
            probe._validate_device_alias("   ", TARGET_SERIAL)

    @pytest.mark.parametrize(
        "alias",
        [
            "target-192.0.2.20",
            "target-fd00:1::20",
            "target-fe80::20%en0",
            "target-d073.d5aa.11bb",
            "Target-FD00:1::20",
            f"target-{TARGET_SERIAL}",
        ],
    )
    def test_cli_rejects_unsafe_alias_before_creating_output(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, alias: str
    ) -> None:
        """Every raw-identifier bypass stops before the output path exists."""
        path = tmp_path / "record.json"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "ipv6_thread_probe.py",
                "--serial",
                TARGET_SERIAL,
                "--device-alias",
                alias,
                "--uat-output",
                str(path),
            ],
        )

        with pytest.raises(SystemExit) as raised:
            probe.main()

        assert raised.value.code == 2
        assert not path.exists()

    @pytest.mark.parametrize(
        ("address", "expected"),
        [("192.0.2.20", "ipv4"), (ULA_ADDRESS, "ipv6"), ("invalid", None)],
    )
    def test_address_family_discards_the_live_route(
        self, address: str, expected: str | None
    ) -> None:
        """Only the non-identifying protocol family reaches evidence."""
        assert probe._address_family(address) == expected

    def test_requires_an_alias_when_writing_uat_evidence(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The CLI refuses to create evidence under only a raw serial."""
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "ipv6_thread_probe.py",
                "--serial",
                TARGET_SERIAL,
                "--uat-output",
                str(tmp_path / "record.json"),
            ],
        )

        with pytest.raises(SystemExit) as raised:
            probe.main()

        assert raised.value.code == 2

    def test_an_alias_without_a_target_serial_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An alias cannot turn a non-targeted fleet sweep into UAT evidence."""
        monkeypatch.setattr(
            sys,
            "argv",
            ["ipv6_thread_probe.py", "--device-alias", TARGET_ALIAS],
        )

        with pytest.raises(SystemExit) as raised:
            probe.main()

        assert raised.value.code == 2

    def test_cli_without_evidence_alias_runs_the_probe(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ordinary diagnostic runs do not require an evidence alias."""
        monkeypatch.setattr(sys, "argv", ["ipv6_thread_probe.py"])

        def run(coroutine: Any) -> int:
            coroutine.close()
            return 0

        monkeypatch.setattr(asyncio, "run", run)

        assert probe.main() == 0


class TestCaptureDeviceState:
    """_capture_device_state() reads the shape the device actually holds."""

    async def test_a_matrix_capture_reads_tiles_power_and_effect(self) -> None:
        """get_color() cannot represent a per-pixel image or a running effect."""
        device = FakeMatrix(power=65535, effect_type=FirmwareEffect.MORPH)

        state = await probe._capture_device_state(device)

        called = [name for name, _ in device.calls]
        assert "get_all_tile_colors" in called
        assert "get_power" in called
        assert "get_effect" in called
        assert state.kind == "matrix"
        assert state.tiles == TILE_COLOURS
        assert state.power == 65535
        assert state.effect is not None
        assert state.effect.effect_type is FirmwareEffect.MORPH

    async def test_a_matrix_with_no_running_effect_captures_none(self) -> None:
        """OFF is not an effect to put back, so nothing is recorded."""
        device = FakeMatrix(effect_type=FirmwareEffect.OFF)

        state = await probe._capture_device_state(device)

        assert state.effect is None

    async def test_a_plain_light_capture_takes_the_get_color_path(self) -> None:
        """A bulb holds one colour, and get_color() carries its power too."""
        device = FakeLight()

        state = await probe._capture_device_state(device)

        assert [name for name, _ in device.calls] == ["get_color"]
        assert state.kind == "light"
        assert state.color == HSBK(200.0, 0.4, 0.6, 3000)
        assert state.power == 65535

    async def test_a_multizone_capture_reads_zones_power_and_effect(self) -> None:
        """A representative colour cannot encode a strip's full state."""
        device = FakeMultiZone()

        state = await probe._capture_device_state(device)

        assert [name for name, _ in device.calls] == [
            "get_all_color_zones",
            "get_power",
            "get_effect",
        ]
        assert state.kind == "multizone"
        assert state.zones == ZONE_COLOURS
        assert state.power == 65535
        assert state.multizone_effect == device.saved_effect


class TestRestoreDeviceState:
    """_restore_device_state() puts a device back exactly as it was found."""

    async def test_restores_each_tile_then_power_then_the_effect(self) -> None:
        """Order matters: paint, then power, then re-arm the firmware effect."""
        device = FakeMatrix(power=65535, effect_type=FirmwareEffect.MORPH)
        state = await probe._capture_device_state(device)
        device.calls.clear()

        restored = await probe._restore_device_state(device, state)

        assert restored is True
        names = [name for name, _ in device.calls]
        assert names == [
            "set_matrix_colors",
            "set_matrix_colors",
            "set_power",
            "set_effect",
        ]
        writes = [
            payload for name, payload in device.calls if name == "set_matrix_colors"
        ]
        assert writes == [(0, TILE_COLOURS[0]), (1, TILE_COLOURS[1])]
        assert device.calls[2][1] == 65535

    async def test_speed_is_converted_back_to_seconds_for_set_effect(self) -> None:
        """get_effect() reports milliseconds; set_effect() takes seconds."""
        device = FakeMatrix(effect_type=FirmwareEffect.MORPH)
        state = await probe._capture_device_state(device)
        device.calls.clear()

        await probe._restore_device_state(device, state)

        kwargs = next(payload for name, payload in device.calls if name == "set_effect")
        assert kwargs["speed"] == 5.0
        assert kwargs["effect_type"] is FirmwareEffect.MORPH

    async def test_no_effect_is_reapplied_when_none_was_running(self) -> None:
        """Arming an effect the device never had would not be a restore."""
        device = FakeMatrix(effect_type=FirmwareEffect.OFF)
        state = await probe._capture_device_state(device)
        device.calls.clear()

        await probe._restore_device_state(device, state)

        assert "set_effect" not in [name for name, _ in device.calls]

    async def test_a_plain_light_is_restored_by_colour_and_power(self) -> None:
        """The light path writes the captured triple back."""
        device = FakeLight()
        state = await probe._capture_device_state(device)
        device.calls.clear()

        restored = await probe._restore_device_state(device, state)

        assert restored is True
        assert [name for name, _ in device.calls] == ["set_color", "set_power"]
        assert device.calls[0][1] == HSBK(200.0, 0.4, 0.6, 3000)
        assert device.calls[1][1] == 65535

    @pytest.mark.parametrize("extended", [True, False], ids=["extended", "legacy"])
    async def test_restores_multizone_through_public_capability_path(
        self, extended: bool
    ) -> None:
        """The public setter selects the protocol supported by the product."""
        device = FakeMultiZone(extended=extended)
        state = await probe._capture_device_state(device)
        device._zones = list(reversed(ZONE_COLOURS))
        device.saved_effect = MultiZoneEffect(effect_type=FirmwareEffect.OFF, speed=0)
        device._power_level = 0
        device.calls.clear()

        restored = await probe._restore_device_state(device, state)

        assert restored is True
        called = [name for name, _ in device.calls]
        assert called[0] == "set_all_color_zones"
        assert ("set_extended_color_zones" in called) is extended
        assert ("set_color_zones" in called) != extended
        assert device._zones == ZONE_COLOURS
        assert device.saved_effect == state.multizone_effect
        assert device._power_level == 65535

    async def test_restores_multizone_without_rearming_an_absent_effect(self) -> None:
        """A capture without a firmware effect restores zones and power only."""
        device = FakeMultiZone()
        state = probe.CapturedState(
            kind="multizone",
            power=65535,
            zones=ZONE_COLOURS,
            multizone_effect=None,
        )

        restored = await probe._restore_device_state(device, state)

        assert restored is True
        assert "set_effect" not in [name for name, _ in device.calls]
        assert [name for name, _ in device.calls][-1] == "set_power"

    async def test_power_alone_is_restored_when_no_colour_was_captured(self) -> None:
        """The defensive arm: a colourless capture still restores power.

        `_capture_device_state()` never produces this today, so the guard is
        purely defensive. Covering it here keeps the helper free of partial
        branches, which is the standard the rest of this project holds
        (auto-memory project_codecov_branch_patch).
        """
        device = FakeLight()
        state = probe.CapturedState(kind="light", power=0, color=None)

        restored = await probe._restore_device_state(device, state)

        assert restored is True
        assert [name for name, _ in device.calls] == ["set_power"]

    async def test_a_failing_restore_is_reported_and_returns_false(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A device left mid-run must be visible, never silently swallowed."""
        device = FakeMatrix()
        state = await probe._capture_device_state(device)

        async def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("device stopped answering")

        device.set_matrix_colors = _boom  # type: ignore[method-assign]

        restored = await probe._restore_device_state(device, state)

        assert restored is False
        printed = capsys.readouterr().out
        assert "could not restore" in printed
        assert TARGET_SERIAL in printed
        assert "by hand" in printed


class TestSettle:
    """_settle() waits out a ramp without ever relaxing the predicate."""

    async def test_an_already_correct_reading_costs_no_extra_polling(self) -> None:
        """The happy path must not add latency to a device that is ready."""
        reads = 0

        async def read() -> int:
            nonlocal reads
            reads += 1
            return 65535

        settled, value = await probe._settle(read, lambda v: v == 65535, 1.0, 0.001)

        assert settled is True
        assert value == 65535
        assert reads == 1

    async def test_a_late_value_inside_the_deadline_is_accepted(self) -> None:
        """The ramp shape measured on real hardware has to pass."""
        values = iter([4980, 20000, 65535])

        async def read() -> int:
            return next(values)

        settled, value = await probe._settle(read, lambda v: v == 65535, 1.0, 0.001)

        assert settled is True
        assert value == 65535

    async def test_a_value_that_never_arrives_fails_and_names_what_it_saw(self) -> None:
        """A real failure must stay diagnosable, not collapse into a timeout."""

        async def read() -> int:
            return 5242

        settled, value = await probe._settle(read, lambda v: v == 65535, 0.02, 0.001)

        assert settled is False
        assert value == 5242


class TestStageTarget:
    """The mutating section always restores and always records honestly."""

    async def test_a_device_that_applies_writes_passes_control(self) -> None:
        """The happy path: both roundtrips read back as asked."""
        device = FakeMatrix()
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.connect == "passed"
        assert outcome.control == "passed"
        assert outcome.streaming == "not_run"
        assert outcome.restored is True
        assert probe._exit_code(outcome) == 0

    async def test_a_device_that_ignores_writes_fails_control(self) -> None:
        """The readback assertion must be able to fail, or it proves nothing."""
        device = FakeMatrix(applies_writes=False)
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.control == "failed"
        assert probe._exit_code(outcome) == 1

    async def test_a_ramping_power_readback_still_passes(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The regression this fix exists for.

        Against the real Tube on 2026-08-28 the probe read 5242 one round trip
        after `set_power(True)` and failed the stage, even though the device
        reached 65535 a few hundred milliseconds later. Before the settle loop
        this test fails with exactly that reading.
        """
        device = RampingMatrix(ramp=[4980, 20000], power=0)
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.control == "passed"
        assert device.ramp == []
        assert "moved power 0 -> 65535" in capsys.readouterr().out

    async def test_power_that_never_settles_fails_with_the_last_reading(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Waiting longer must not become waiting forever, or passing anyway."""
        device = StuckPowerMatrix(power=0)
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.control == "failed"
        assert "never reached 65535" in capsys.readouterr().out

    async def test_an_already_on_light_is_driven_off_first(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Turning an on light on again would assert nothing.

        The stage drives it off first so the on-write is an observable
        transition, mirroring how the colour target is derived from the
        pre-write reading rather than hardcoded.
        """
        device = FakeMatrix(power=65535)
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.control == "passed"
        assert ("set_power", False) in device.calls
        assert "moved power 0 -> 65535" in capsys.readouterr().out

    async def test_an_on_light_that_ignores_the_off_write_is_not_a_pass(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A level the device already held cannot count as a successful write."""
        device = FakeMatrix(power=65535, applies_writes=False)
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        out = capsys.readouterr().out
        assert outcome.control == "failed"
        assert "never reached 0" in out
        assert "already held" in out

    async def test_a_lagging_colour_readback_still_passes(self) -> None:
        """Colour is polled for the same reason as power.

        The colour readback won the race on the 2026-08-28 hardware run, but
        winning once is not evidence that it cannot lose, so the same settle
        loop covers it and this pins the behaviour.
        """
        device = LaggingColourMatrix(lag=2, power=0)
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.control == "passed"
        assert device.lag == 0

    async def test_restoration_runs_after_an_injected_control_failure(self) -> None:
        """A raising set_color must not skip the restore."""
        device = FakeMatrix()

        async def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("set_color went nowhere")

        device.set_color = _boom  # type: ignore[method-assign]
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.control == "failed"
        assert outcome.restored is True
        assert "set_matrix_colors" in [name for name, _ in device.calls]

    @pytest.mark.parametrize("extended", [True, False], ids=["extended", "legacy"])
    async def test_multizone_control_failure_always_restores_full_state(
        self, extended: bool
    ) -> None:
        """A control exception cannot skip either multizone protocol path."""
        device = FakeMultiZone(extended=extended)
        original_effect = device.saved_effect

        async def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("set_color went nowhere")

        device.set_color = _boom  # type: ignore[method-assign]
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        called = [name for name, _ in device.calls]
        assert outcome.control == "failed"
        assert outcome.restored is True
        assert "set_all_color_zones" in called
        assert ("set_extended_color_zones" in called) is extended
        assert ("set_color_zones" in called) != extended
        assert device._zones == ZONE_COLOURS
        assert device.saved_effect == original_effect
        assert device._power_level == 65535

    @pytest.mark.parametrize("extended", [True, False], ids=["extended", "legacy"])
    @pytest.mark.parametrize("stream_raises", [False, True], ids=["success", "failure"])
    async def test_multizone_streaming_always_restores_full_state(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fast_stream: None,
        stream_raises: bool,
        extended: bool,
    ) -> None:
        """Both capability paths restore after clean and failed frame runs."""
        animator = FakeAnimator(raises=stream_raises)
        use_animator(monkeypatch, animator)
        device = FakeMultiZone(extended=extended)
        original_effect = device.saved_effect
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome, stream=True)

        assert outcome.streaming == ("failed" if stream_raises else "passed")
        assert outcome.restored is True
        called = [name for name, _ in device.calls]
        assert "set_all_color_zones" in called
        assert ("set_extended_color_zones" in called) is extended
        assert ("set_color_zones" in called) != extended
        assert device._zones == ZONE_COLOURS
        assert device.saved_effect == original_effect
        assert device.calls[-1] == ("set_power", 65535)

    async def test_restoration_runs_after_a_keyboard_interrupt(self) -> None:
        """An interrupt must not leave a production light mid-run.

        A KeyboardInterrupt is a BaseException, so it slips past the per-stage
        `except Exception` handlers and is the only thing that actually
        exercises the outer `finally`. Without this test a mutation moving the
        restore out of that `finally` and onto the happy path passes the whole
        suite, which is how this case was found.
        """
        device = FakeMatrix()

        async def _interrupt(*args: object, **kwargs: object) -> None:
            raise KeyboardInterrupt

        device.set_color = _interrupt  # type: ignore[method-assign]
        outcome = probe.TargetOutcome()

        with pytest.raises(KeyboardInterrupt):
            await probe.stage_target(device, outcome)

        assert outcome.restored is True
        assert "set_matrix_colors" in [name for name, _ in device.calls]
        assert outcome.control == "not_run"

    async def test_a_failing_restore_lands_in_the_record(self) -> None:
        """`restored: false` is how the operator learns to fix it by hand."""
        device = FakeMatrix()

        async def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("no route to host")

        device.set_matrix_colors = _boom  # type: ignore[method-assign]
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.restored is False
        record = probe._build_uat_record(TARGET_ALIAS, "ipv6", "thread", outcome)
        assert record["restored"] is False

    async def test_a_capture_failure_is_recorded_as_a_failed_connect(self) -> None:
        """If the pre-run state cannot be read, nothing may be written."""
        device = FakeMatrix()

        async def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("timed out reading tiles")

        device.get_all_tile_colors = _boom  # type: ignore[method-assign]
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.connect == "failed"
        assert outcome.control == "not_run"
        assert "set_matrix_colors" not in [name for name, _ in device.calls]
        assert probe._exit_code(outcome) == 1


class TestStreamingStage:
    """Streaming is an artefact: it is recorded, and it gates nothing."""

    async def test_frames_are_delivered_and_the_socket_is_closed(
        self, monkeypatch: pytest.MonkeyPatch, fast_stream: None
    ) -> None:
        """A clean run sends frames and releases the animator's socket."""
        animator = FakeAnimator()
        use_animator(monkeypatch, animator)

        result = await probe.run_streaming_stage(FakeMatrix())

        assert result is True
        assert animator.frames >= 1
        assert animator.closed == 1

    async def test_close_runs_even_when_the_frame_run_raises(
        self, monkeypatch: pytest.MonkeyPatch, fast_stream: None
    ) -> None:
        """A streaming exception must not strand the raw UDP socket."""
        animator = FakeAnimator(raises=True)
        use_animator(monkeypatch, animator)

        with pytest.raises(OSError):
            await probe.run_streaming_stage(FakeMatrix())

        assert animator.closed == 1

    async def test_a_failed_stream_does_not_change_the_exit_code(
        self, monkeypatch: pytest.MonkeyPatch, fast_stream: None
    ) -> None:
        """Control passing while streaming fails is an allowed outcome."""
        animator = FakeAnimator(raises=True)
        use_animator(monkeypatch, animator)
        outcome = probe.TargetOutcome()

        await probe.stage_target(FakeMatrix(), outcome, stream=True)

        assert outcome.control == "passed"
        assert outcome.streaming == "failed"
        assert outcome.restored is True
        assert probe._exit_code(outcome) == 0

    async def test_streaming_is_not_run_when_the_flag_is_absent(
        self, monkeypatch: pytest.MonkeyPatch, fast_stream: None
    ) -> None:
        """Without --stream no animator is built at all."""
        animator = FakeAnimator()
        use_animator(monkeypatch, animator)
        outcome = probe.TargetOutcome()

        await probe.stage_target(FakeMatrix(), outcome)

        assert outcome.streaming == "not_run"
        assert animator.frames == 0
        record = probe._build_uat_record(TARGET_ALIAS, "ipv6", "thread", outcome)
        stages = record["stages"]
        assert isinstance(stages, dict)
        assert stages["streaming"] == "not_run"


class TestExitCode:
    """_exit_code() reads the gating stages and only those."""

    def test_a_clean_control_run_exits_zero(self) -> None:
        """Both gating stages passed."""
        outcome = probe.TargetOutcome(connect="passed", control="passed")

        assert probe._exit_code(outcome) == 0

    def test_a_failed_connect_exits_non_zero(self) -> None:
        """Connect gates: nothing downstream can be trusted without it."""
        outcome = probe.TargetOutcome(connect="failed")

        assert probe._exit_code(outcome) == 1

    def test_a_failed_restoration_exits_non_zero(self) -> None:
        """Leaving a physical device mutated is always a failed run."""
        outcome = probe.TargetOutcome(
            connect="passed", control="passed", restored=False
        )

        assert probe._exit_code(outcome) == 1

    def test_a_failed_stream_alone_exits_zero(self) -> None:
        """SPEC Requirement 9: the streaming run does not gate."""
        outcome = probe.TargetOutcome(
            connect="passed", control="passed", streaming="failed"
        )

        assert probe._exit_code(outcome) == 0
