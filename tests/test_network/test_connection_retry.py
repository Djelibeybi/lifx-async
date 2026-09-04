"""Tests for the reshaped request retransmit schedule (RETRY-01/02/04).

Wave-0 RED suite for the Phase 3 retry reshape (03-RESEARCH.md). Covers the
behavioural branch matrix rows B2-B13, B15-B16: floored first window and
escalating retransmit gaps (RETRY-01), retransmit-while-listening with no
blind sleeps (RETRY-02), and shared-queue correlation with late-reply
acceptance on both GET and ACK paths (RETRY-04).

These tests are written against the FINAL contract (D3-01, D3-02, D3-04):
a runtime-read ``REQUEST_RETRANSMIT_GAPS`` tuple and ``_STREAM_IDLE_TIMEOUT``
float, both module attributes of ``lifx.network.connection``. At this
commit neither exists, so most tests fail with ``AttributeError`` when the
schedule/idle-window patch targets are entered -- that is the expected RED
state for plan 03-02 to turn GREEN. See 03-01-SUMMARY.md for the recorded
per-test RED/coincidental-pass breakdown.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import patch

import pytest

from lifx.exceptions import LifxConnectionError, LifxProtocolError, LifxTimeoutError
from lifx.network.connection import DeviceConnection, _current_request_observer
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Device
from scripts.measurement_support import (
    _capture_request_observations,
    _RequestObservationSink,
)

_STATE_POWER_PKT_TYPE = 22
_ACKNOWLEDGEMENT_PKT_TYPE = 45
_STATE_POWER_PAYLOAD = b"\x00\x00"

# Existing no-server convention (see test_concurrent_requests.py): sends to
# this address vanish and no responses ever arrive.
_OFFLINE_IP = "192.168.1.100"
_OFFLINE_SERIAL = "d073d5001234"


def _send_spy(
    conn: DeviceConnection, send_times: list[float]
) -> Callable[..., Awaitable[None]]:
    """Wrap the real bound ``send_packet``, recording send times.

    Appends ``time.monotonic()`` to ``send_times`` before delegating to the
    real implementation (03-RESEARCH.md Code Examples).
    """
    real_send = conn.send_packet

    async def _spy(*args: Any, **kwargs: Any) -> None:
        send_times.append(time.monotonic())
        await real_send(*args, **kwargs)

    return _spy


def _header(
    *,
    source: int,
    sequence: int,
    target: bytes,
    pkt_type: int,
    payload_len: int,
    thread_connection: bool = False,
) -> LifxHeader:
    """Build a valid header for direct queue injection.

    Mirrors ``TestRequestStreamDebugLogging._header`` in test_connection.py,
    parameterised on source/sequence/target/pkt_type so mismatch variants
    can be constructed for the correlation branch matrix. ``thread_connection``
    defaults to ``False`` (the dataclass default) and is exposed so Phase 14
    THREAD-02 observer tests can construct a Thread-flagged reply.
    """
    return LifxHeader(
        size=36 + payload_len,
        protocol=1024,
        source=source,
        target=target,
        tagged=False,
        ack_required=False,
        res_required=False,
        sequence=sequence,
        pkt_type=pkt_type,
        thread_connection=thread_connection,
    )


async def _wait_for_keys(
    conn: DeviceConnection, count: int, deadline: float = 2.0
) -> None:
    """Poll ``conn._pending_requests`` until at least ``count`` keys exist.

    A bounded wait loop -- never an unbounded spin (03-RESEARCH.md
    Pitfall 5). Raises if the keys never appear within ``deadline``.
    """
    start = time.monotonic()
    while len(conn._pending_requests) < count:
        if time.monotonic() - start > deadline:
            raise AssertionError(
                f"Timed out waiting for {count} pending request key(s); "
                f"got {len(conn._pending_requests)}"
            )
        await asyncio.sleep(0.001)


class TestRetransmitSchedule:
    """RETRY-01 (D3-01): floored first window, escalating retransmit gaps."""

    @pytest.mark.emulator
    async def test_healthy_network_single_transmission(
        self, emulator_server_with_scenarios: Any
    ) -> None:
        """Healthy network, real gaps: exactly 1 transmission (B6b False)."""
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={},
        )
        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=2.0,
            max_retries=2,
        )
        send_times: list[float] = []
        try:
            await conn.open()
            with patch.object(
                conn, "send_packet", side_effect=_send_spy(conn, send_times)
            ):
                response = await conn.request(Device.GetPower(), timeout=2.0)
            assert hasattr(response, "level")
        finally:
            await conn.close()
        assert len(send_times) == 1

    async def test_no_retransmit_before_first_gap_floor(self) -> None:
        """Real gaps, timeout below the 0.2s floor: exactly 1 send raised
        offline (RETRY-01 floor; B4 raise arm offline)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=0.15, max_retries=2
        )
        send_times: list[float] = []
        try:
            await conn.open()
            start = time.monotonic()
            with (
                patch.object(
                    conn, "send_packet", side_effect=_send_spy(conn, send_times)
                ),
                pytest.raises(LifxTimeoutError),
            ):
                await conn.request(Device.GetPower(), timeout=0.15)
            elapsed = time.monotonic() - start
        finally:
            await conn.close()
        assert len(send_times) == 1
        assert 0.15 <= elapsed < 0.45

    async def test_escalating_gaps_drive_retransmits(self) -> None:
        """Patched gaps (0.05, 0.05): 3 sends at ~0, 0.05, 0.10s, then the
        wall deadline raises (B6/B6b True, B7 True->False, B10 raised arm)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=0.5, max_retries=2
        )
        send_times: list[float] = []
        try:
            await conn.open()
            start = time.monotonic()
            with (
                patch.object(
                    conn, "send_packet", side_effect=_send_spy(conn, send_times)
                ),
                patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.05, 0.05)),
                pytest.raises(LifxTimeoutError, match="after 3 attempts"),
            ):
                await conn.request(Device.GetPower(), timeout=0.5)
            elapsed = time.monotonic() - start
        finally:
            await conn.close()
        assert len(send_times) == 3
        assert 0.5 <= elapsed < 0.8

    async def test_retransmit_cap_then_keeps_listening(self) -> None:
        """Patched gaps (0.05,), max_retries=1: exactly 2 sends, then the
        request keeps listening to the wall deadline instead of failing
        early at the retransmit cap (B6 False post-cap, B7 False)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=0.4, max_retries=1
        )
        send_times: list[float] = []
        try:
            await conn.open()
            start = time.monotonic()
            with (
                patch.object(
                    conn, "send_packet", side_effect=_send_spy(conn, send_times)
                ),
                patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.05,)),
                pytest.raises(LifxTimeoutError),
            ):
                await conn.request(Device.GetPower(), timeout=0.4)
            elapsed = time.monotonic() - start
        finally:
            await conn.close()
        assert len(send_times) == 2
        assert 0.4 <= elapsed < 0.7

    async def test_gap_exhaustion_repeats_final_gap(self) -> None:
        """Patched gaps (0.05,), max_retries=3: the single gap repeats after
        exhaustion, giving 4 sends at ~0.05s spacing (B16)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=0.5, max_retries=3
        )
        send_times: list[float] = []
        try:
            await conn.open()
            with (
                patch.object(
                    conn, "send_packet", side_effect=_send_spy(conn, send_times)
                ),
                patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.05,)),
                pytest.raises(LifxTimeoutError),
            ):
                await conn.request(Device.GetPower(), timeout=0.5)
        finally:
            await conn.close()
        assert len(send_times) == 4
        for i in range(1, len(send_times)):
            gap = send_times[i] - send_times[i - 1]
            assert 0.03 <= gap <= 0.3

    async def test_direct_impl_call_explicit_max_retries_zero(self) -> None:
        """Direct ``_request_stream_impl`` call with ``max_retries=0``:
        exactly 1 send, single-shot semantics (B2 False, B3 False)."""
        conn = DeviceConnection(serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP)
        send_times: list[float] = []
        try:
            await conn.open()
            with (
                patch.object(
                    conn, "send_packet", side_effect=_send_spy(conn, send_times)
                ),
                pytest.raises(LifxTimeoutError),
            ):
                async for _ in conn._request_stream_impl(
                    Device.GetPower(), timeout=0.2, max_retries=0
                ):
                    pass
        finally:
            await conn.close()
        assert len(send_times) == 1


class TestListenDuringBackoff:
    """RETRY-02 (D3-02): retransmit-while-listening, no blind sleeps."""

    async def test_response_between_retransmits_completes_immediately(self) -> None:
        """Patched gaps (0.5,): a response injected right after the first
        transmission completes the request immediately -- well under the
        first retransmit gap, with exactly 1 send (RETRY-02 core; B10 not
        raised)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=5.0, max_retries=8
        )
        send_times: list[float] = []
        task: asyncio.Task[Any] | None = None
        try:
            await conn.open()
            start = time.monotonic()
            with (
                patch.object(
                    conn, "send_packet", side_effect=_send_spy(conn, send_times)
                ),
                patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.5,)),
            ):
                task = asyncio.create_task(conn.request(Device.GetPower(), timeout=5.0))
                await _wait_for_keys(conn, 1)
                (key,) = conn._pending_requests.keys()
                source, sequence, _serial = key
                header = _header(
                    source=source,
                    sequence=sequence,
                    target=bytes.fromhex(conn.serial) + b"\x00\x00",
                    pkt_type=_STATE_POWER_PKT_TYPE,
                    payload_len=len(_STATE_POWER_PAYLOAD),
                )
                conn._pending_requests[key].put_nowait((header, _STATE_POWER_PAYLOAD))
                response = await asyncio.wait_for(task, timeout=1.0)
                task = None
            elapsed = time.monotonic() - start
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert hasattr(response, "level")
        assert elapsed < 0.3
        assert len(send_times) == 1

    async def test_no_retransmit_after_first_response(self) -> None:
        """Patched gaps (0.1, 0.1), idle window patched to 0.3s: a response
        injected immediately is the only yield; the generator idle-exits
        ~0.3s later with exactly 1 send -- no retransmit fires once a
        response has been yielded (B5 True, B6a False, B9 True)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=5.0, max_retries=8
        )
        send_times: list[float] = []
        yields: list[tuple[LifxHeader, bytes]] = []
        task: asyncio.Task[None] | None = None
        try:
            await conn.open()
            start = time.monotonic()
            with (
                patch.object(
                    conn, "send_packet", side_effect=_send_spy(conn, send_times)
                ),
                patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.1, 0.1)),
                patch("lifx.network.connection._STREAM_IDLE_TIMEOUT", 0.3),
            ):

                async def _drive() -> None:
                    async for header, payload in conn._request_stream_impl(
                        Device.GetPower(), timeout=5.0
                    ):
                        yields.append((header, payload))

                task = asyncio.create_task(_drive())
                await _wait_for_keys(conn, 1)
                (key,) = conn._pending_requests.keys()
                source, sequence, _serial = key
                header = _header(
                    source=source,
                    sequence=sequence,
                    target=bytes.fromhex(conn.serial) + b"\x00\x00",
                    pkt_type=_STATE_POWER_PKT_TYPE,
                    payload_len=len(_STATE_POWER_PAYLOAD),
                )
                conn._pending_requests[key].put_nowait((header, _STATE_POWER_PAYLOAD))
                await asyncio.wait_for(task, timeout=1.0)
                task = None
            elapsed = time.monotonic() - start
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert len(yields) == 1
        assert len(send_times) == 1
        assert 0.25 <= elapsed < 0.6

    async def test_second_response_before_idle_extends_stream(self) -> None:
        """Real gaps, idle window patched to 0.4s: a second response
        injected ~0.15s after the first resets the idle clock, giving
        exactly 2 yields (B5 False idle-not-elapsed, B9)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=5.0, max_retries=8
        )
        yields: list[tuple[LifxHeader, bytes]] = []
        task: asyncio.Task[None] | None = None
        try:
            await conn.open()
            with patch("lifx.network.connection._STREAM_IDLE_TIMEOUT", 0.4):

                async def _drive() -> None:
                    async for header, payload in conn._request_stream_impl(
                        Device.GetPower(), timeout=5.0
                    ):
                        yields.append((header, payload))

                task = asyncio.create_task(_drive())
                await _wait_for_keys(conn, 1)
                (key,) = conn._pending_requests.keys()
                source, sequence, _serial = key
                target = bytes.fromhex(conn.serial) + b"\x00\x00"

                def _inject() -> None:
                    header = _header(
                        source=source,
                        sequence=sequence,
                        target=target,
                        pkt_type=_STATE_POWER_PKT_TYPE,
                        payload_len=len(_STATE_POWER_PAYLOAD),
                    )
                    conn._pending_requests[key].put_nowait(
                        (header, _STATE_POWER_PAYLOAD)
                    )

                _inject()
                await asyncio.sleep(0.15)
                _inject()
                await asyncio.wait_for(task, timeout=1.0)
                task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert len(yields) == 2

    async def test_deadline_return_after_yield_no_raise(self) -> None:
        """Idle window patched to 10.0s, timeout=0.3s: one response injected
        immediately; the generator completes WITHOUT raising at ~0.3s with
        exactly 1 yield (B4 True + yielded -> return, B15 not-reached arm)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=0.3, max_retries=8
        )
        yields: list[tuple[LifxHeader, bytes]] = []
        task: asyncio.Task[None] | None = None
        try:
            await conn.open()
            start = time.monotonic()
            with patch("lifx.network.connection._STREAM_IDLE_TIMEOUT", 10.0):

                async def _drive() -> None:
                    async for header, payload in conn._request_stream_impl(
                        Device.GetPower(), timeout=0.3
                    ):
                        yields.append((header, payload))

                task = asyncio.create_task(_drive())
                await _wait_for_keys(conn, 1)
                (key,) = conn._pending_requests.keys()
                source, sequence, _serial = key
                header = _header(
                    source=source,
                    sequence=sequence,
                    target=bytes.fromhex(conn.serial) + b"\x00\x00",
                    pkt_type=_STATE_POWER_PKT_TYPE,
                    payload_len=len(_STATE_POWER_PAYLOAD),
                )
                conn._pending_requests[key].put_nowait((header, _STATE_POWER_PAYLOAD))
                await asyncio.wait_for(task, timeout=1.0)
                task = None
            elapsed = time.monotonic() - start
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert len(yields) == 1
        assert 0.25 <= elapsed < 0.6


class TestCorrelationContract:
    """RETRY-04 (D3-04): shared-queue correlation, late replies accepted."""

    async def test_late_reply_to_earlier_sequence_accepted(self) -> None:
        """Patched gaps (0.05,): once >=2 transmissions are in flight, a
        reply to sequence 0 (the FIRST transmission) still satisfies the
        request (B13 in-range; the RETRY-04 acceptance case)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=3
        )
        task: asyncio.Task[Any] | None = None
        try:
            await conn.open()
            with patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.05,)):
                task = asyncio.create_task(conn.request(Device.GetPower(), timeout=2.0))
                await _wait_for_keys(conn, 2)
                key0 = min(conn._pending_requests, key=lambda k: k[1])
                source = key0[0]
                header = _header(
                    source=source,
                    sequence=0,
                    target=bytes.fromhex(conn.serial) + b"\x00\x00",
                    pkt_type=_STATE_POWER_PKT_TYPE,
                    payload_len=len(_STATE_POWER_PAYLOAD),
                )
                conn._pending_requests[key0].put_nowait((header, _STATE_POWER_PAYLOAD))
                response = await asyncio.wait_for(task, timeout=1.0)
                task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert hasattr(response, "level")

    async def test_late_ack_to_earlier_sequence_accepted(self) -> None:
        """Same shape for the ACK path with an Acknowledgement injected
        against sequence 0 after >=2 transmissions are in flight -- the
        D3-04-mandated ACK-path behaviour change (today's per-attempt queue
        discards it)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=3
        )
        task: asyncio.Task[Any] | None = None
        try:
            await conn.open()
            with patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.05,)):
                task = asyncio.create_task(
                    conn.request(Device.SetPower(level=65535), timeout=2.0)
                )
                await _wait_for_keys(conn, 2)
                key0 = min(conn._pending_requests, key=lambda k: k[1])
                source = key0[0]
                header = _header(
                    source=source,
                    sequence=0,
                    target=bytes.fromhex(conn.serial) + b"\x00\x00",
                    pkt_type=_ACKNOWLEDGEMENT_PKT_TYPE,
                    payload_len=0,
                )
                conn._pending_requests[key0].put_nowait((header, b""))
                result = await asyncio.wait_for(task, timeout=1.0)
                task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert result is True

    async def test_ack_wrapper_direct_call_completes_naturally(self) -> None:
        """Driving ``_request_ack_stream_impl`` directly with a full,
        non-early-return consuming loop reaches its own ``return``
        statement (immediately after ``yield True``) via a second
        ``__anext__()`` call, exercising natural generator exhaustion
        rather than the caller abandoning it after the first item (as
        ``conn.request()`` does)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=2
        )
        results: list[bool] = []
        task: asyncio.Task[None] | None = None
        try:
            await conn.open()

            async def _drive() -> None:
                async for result in conn._request_ack_stream_impl(
                    Device.SetPower(level=65535), timeout=2.0
                ):
                    results.append(result)

            task = asyncio.create_task(_drive())
            await _wait_for_keys(conn, 1)
            (key,) = conn._pending_requests.keys()
            source, sequence, _serial = key
            header = _header(
                source=source,
                sequence=sequence,
                target=bytes.fromhex(conn.serial) + b"\x00\x00",
                pkt_type=_ACKNOWLEDGEMENT_PKT_TYPE,
                payload_len=0,
            )
            conn._pending_requests[key].put_nowait((header, b""))
            await asyncio.wait_for(task, timeout=1.0)
            task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert results == [True]
        assert conn._pending_requests == {}

    async def test_wrong_source_raises_protocol_error(self) -> None:
        """A response with a mismatched source raises LifxProtocolError
        (B12)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=2
        )
        task: asyncio.Task[Any] | None = None
        try:
            await conn.open()
            task = asyncio.create_task(conn.request(Device.GetPower(), timeout=2.0))
            await _wait_for_keys(conn, 1)
            (key,) = conn._pending_requests.keys()
            source, sequence, _serial = key
            header = _header(
                source=source + 1,
                sequence=sequence,
                target=bytes.fromhex(conn.serial) + b"\x00\x00",
                pkt_type=_STATE_POWER_PKT_TYPE,
                payload_len=len(_STATE_POWER_PAYLOAD),
            )
            conn._pending_requests[key].put_nowait((header, _STATE_POWER_PAYLOAD))
            with pytest.raises(LifxProtocolError):
                await asyncio.wait_for(task, timeout=1.0)
            task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()

    async def test_out_of_range_sequence_raises_protocol_error(self) -> None:
        """A response with a never-issued sequence raises LifxProtocolError
        (B13 out-of-range)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=2
        )
        task: asyncio.Task[Any] | None = None
        try:
            await conn.open()
            task = asyncio.create_task(conn.request(Device.GetPower(), timeout=2.0))
            await _wait_for_keys(conn, 1)
            (key,) = conn._pending_requests.keys()
            source, _sequence, _serial = key
            header = _header(
                source=source,
                sequence=99,
                target=bytes.fromhex(conn.serial) + b"\x00\x00",
                pkt_type=_STATE_POWER_PKT_TYPE,
                payload_len=len(_STATE_POWER_PAYLOAD),
            )
            conn._pending_requests[key].put_nowait((header, _STATE_POWER_PAYLOAD))
            with pytest.raises(LifxProtocolError):
                await asyncio.wait_for(task, timeout=1.0)
            task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()

    async def test_serial_mismatch_raises_protocol_error(self) -> None:
        """A response targeting a different serial raises LifxProtocolError
        (B11 mismatch)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=2
        )
        task: asyncio.Task[Any] | None = None
        try:
            await conn.open()
            task = asyncio.create_task(conn.request(Device.GetPower(), timeout=2.0))
            await _wait_for_keys(conn, 1)
            (key,) = conn._pending_requests.keys()
            source, sequence, _serial = key
            header = _header(
                source=source,
                sequence=sequence,
                target=bytes.fromhex("d073d5009999") + b"\x00\x00",
                pkt_type=_STATE_POWER_PKT_TYPE,
                payload_len=len(_STATE_POWER_PAYLOAD),
            )
            conn._pending_requests[key].put_nowait((header, _STATE_POWER_PAYLOAD))
            with pytest.raises(LifxProtocolError):
                await asyncio.wait_for(task, timeout=1.0)
            task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()

    async def test_discovery_connection_accepts_any_target(self) -> None:
        """A discovery connection (serial "000000000000") yields a response
        regardless of its target -- serial validation is skipped (B11
        False).

        Idle window patched to 0.3s (matching this file's other _drive()
        streaming tests): this is a multi-response streaming consumer that
        never breaks early, so it genuinely waits out the post-yield idle
        window before returning -- an unpatched 2.0s default idle window
        would exceed the 1.0s wait_for bound below.
        """
        conn = DeviceConnection(
            serial="000000000000", ip=_OFFLINE_IP, timeout=2.0, max_retries=2
        )
        yields: list[tuple[LifxHeader, bytes]] = []
        task: asyncio.Task[None] | None = None
        try:
            await conn.open()
            with patch("lifx.network.connection._STREAM_IDLE_TIMEOUT", 0.3):

                async def _drive() -> None:
                    async for header, payload in conn._request_stream_impl(
                        Device.GetPower(), timeout=2.0
                    ):
                        yields.append((header, payload))

                task = asyncio.create_task(_drive())
                await _wait_for_keys(conn, 1)
                (key,) = conn._pending_requests.keys()
                source, sequence, _serial = key
                header = _header(
                    source=source,
                    sequence=sequence,
                    target=bytes.fromhex("d073d5001234") + b"\x00\x00",
                    pkt_type=_STATE_POWER_PKT_TYPE,
                    payload_len=len(_STATE_POWER_PAYLOAD),
                )
                conn._pending_requests[key].put_nowait((header, _STATE_POWER_PAYLOAD))
                await asyncio.wait_for(task, timeout=1.0)
                task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert len(yields) == 1

    async def test_duplicate_response_discarded_silently(self) -> None:
        """Two identical responses queued before the consumer runs:
        ``request()`` returns the first with no exception, and all
        correlation keys are cleaned up afterwards."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=2
        )
        task: asyncio.Task[Any] | None = None
        try:
            await conn.open()
            task = asyncio.create_task(conn.request(Device.GetPower(), timeout=2.0))
            await _wait_for_keys(conn, 1)
            (key,) = conn._pending_requests.keys()
            source, sequence, _serial = key
            queue = conn._pending_requests[key]
            header = _header(
                source=source,
                sequence=sequence,
                target=bytes.fromhex(conn.serial) + b"\x00\x00",
                pkt_type=_STATE_POWER_PKT_TYPE,
                payload_len=len(_STATE_POWER_PAYLOAD),
            )
            queue.put_nowait((header, _STATE_POWER_PAYLOAD))
            queue.put_nowait((header, _STATE_POWER_PAYLOAD))
            response = await asyncio.wait_for(task, timeout=1.0)
            task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert hasattr(response, "level")
        assert conn._pending_requests == {}


class TestRequestObservation:
    """Phase 14 THREAD-02 (D-07/D-17/D-19): private request-observer seam.

    No observer is attached by any test elsewhere in this file or in the
    rest of the suite, so every pre-existing test in this module already
    proves the no-observer path is unaffected byte-for-byte. These tests
    cover the opt-in observer itself.
    """

    async def test_no_observer_outside_capture_context(self) -> None:
        """The selector returns None on every ordinary call (no-observer arm)."""
        assert _current_request_observer() is None

    async def test_observes_logical_start_sent_and_accepted_in_order(self) -> None:
        """A single successful GET response observes logical_start, sent(0)
        and accepted(0) in that order, with accepted_ns >= sent_ns >=
        logical_start_ns and the device's unflagged Thread report carried."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=5.0, max_retries=8
        )
        sink: _RequestObservationSink | None = None
        task: asyncio.Task[Any] | None = None
        try:
            await conn.open()
            with patch("lifx.network.connection._STREAM_IDLE_TIMEOUT", 0.2):

                async def _drive() -> None:
                    nonlocal sink
                    with _capture_request_observations() as active_sink:
                        sink = active_sink
                        async for _ in conn._request_stream_impl(
                            Device.GetPower(), timeout=5.0
                        ):
                            pass

                task = asyncio.create_task(_drive())
                await _wait_for_keys(conn, 1)
                (key,) = conn._pending_requests.keys()
                source, sequence, _serial = key
                header = _header(
                    source=source,
                    sequence=sequence,
                    target=bytes.fromhex(conn.serial) + b"\x00\x00",
                    pkt_type=_STATE_POWER_PKT_TYPE,
                    payload_len=len(_STATE_POWER_PAYLOAD),
                )
                conn._pending_requests[key].put_nowait((header, _STATE_POWER_PAYLOAD))
                await asyncio.wait_for(task, timeout=1.0)
                task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert sink is not None
        categories = [obs.category for obs in sink.observations]
        assert categories == ["logical_start", "sent", "accepted", "cleanup"]
        logical_start, sent, accepted, cleanup = sink.observations
        assert sent.sequence == 0
        assert accepted.sequence == 0
        assert accepted.thread_connection is False
        assert (
            logical_start.timestamp_ns
            <= sent.timestamp_ns
            <= accepted.timestamp_ns
            <= cleanup.timestamp_ns
        )

    async def test_observes_thread_flagged_accepted_response(self) -> None:
        """A Thread-flagged reply is distinguished from an unflagged one, and
        the flag changes nothing about correlation or timing (T-14 scope)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=5.0, max_retries=8
        )
        sink: _RequestObservationSink | None = None
        task: asyncio.Task[Any] | None = None
        try:
            await conn.open()
            with patch("lifx.network.connection._STREAM_IDLE_TIMEOUT", 0.2):

                async def _drive() -> None:
                    nonlocal sink
                    with _capture_request_observations() as active_sink:
                        sink = active_sink
                        async for _ in conn._request_stream_impl(
                            Device.GetPower(), timeout=5.0
                        ):
                            pass

                task = asyncio.create_task(_drive())
                await _wait_for_keys(conn, 1)
                (key,) = conn._pending_requests.keys()
                source, sequence, _serial = key
                header = _header(
                    source=source,
                    sequence=sequence,
                    target=bytes.fromhex(conn.serial) + b"\x00\x00",
                    pkt_type=_STATE_POWER_PKT_TYPE,
                    payload_len=len(_STATE_POWER_PAYLOAD),
                    thread_connection=True,
                )
                conn._pending_requests[key].put_nowait((header, _STATE_POWER_PAYLOAD))
                await asyncio.wait_for(task, timeout=1.0)
                task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert sink is not None
        accepted = next(o for o in sink.observations if o.category == "accepted")
        assert accepted.thread_connection is True
        assert conn.thread_connection is True

    async def test_retransmission_yields_distinct_logical_and_ack_rtt(self) -> None:
        """The winning (retransmitted) sequence's sent_ns, not the first
        transmission's, is what the accepted event's sequence resolves to --
        proving logical_latency_ns and ack_rtt_ns are computable as distinct
        values (D-07 acceptance criterion)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=3
        )
        sink: _RequestObservationSink | None = None
        task: asyncio.Task[Any] | None = None
        try:
            await conn.open()
            with patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.05,)):

                async def _drive() -> None:
                    nonlocal sink
                    with _capture_request_observations() as active_sink:
                        sink = active_sink
                        await conn.request(Device.GetPower(), timeout=2.0)

                task = asyncio.create_task(_drive())
                await _wait_for_keys(conn, 2)
                key1 = max(conn._pending_requests, key=lambda k: k[1])
                source, sequence, _serial = key1
                assert sequence == 1
                header = _header(
                    source=source,
                    sequence=sequence,
                    target=bytes.fromhex(conn.serial) + b"\x00\x00",
                    pkt_type=_STATE_POWER_PKT_TYPE,
                    payload_len=len(_STATE_POWER_PAYLOAD),
                )
                conn._pending_requests[key1].put_nowait((header, _STATE_POWER_PAYLOAD))
                await asyncio.wait_for(task, timeout=1.0)
                task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert sink is not None
        logical_start = next(
            o for o in sink.observations if o.category == "logical_start"
        )
        sent_events = {
            o.sequence: o.timestamp_ns
            for o in sink.observations
            if o.category == "sent"
        }
        accepted = next(o for o in sink.observations if o.category == "accepted")
        assert set(sent_events) == {0, 1}
        assert accepted.sequence == 1
        logical_latency_ns = accepted.timestamp_ns - logical_start.timestamp_ns
        ack_rtt_ns = accepted.timestamp_ns - sent_events[1]
        assert ack_rtt_ns < logical_latency_ns
        assert ack_rtt_ns >= 0

    async def test_late_ack_to_earlier_sequence_uses_matching_sent(self) -> None:
        """A reply accepted against the FIRST transmission after a second
        has already gone out still resolves ack_rtt_ns from sequence 0's
        sent_ns, not sequence 1's (RETRY-04 correlation contract preserved
        under observation)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=3
        )
        sink: _RequestObservationSink | None = None
        task: asyncio.Task[Any] | None = None
        try:
            await conn.open()
            with patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.05,)):

                async def _drive() -> None:
                    nonlocal sink
                    with _capture_request_observations() as active_sink:
                        sink = active_sink
                        await conn.request(Device.GetPower(), timeout=2.0)

                task = asyncio.create_task(_drive())
                await _wait_for_keys(conn, 2)
                key0 = min(conn._pending_requests, key=lambda k: k[1])
                source, sequence, _serial = key0
                assert sequence == 0
                header = _header(
                    source=source,
                    sequence=sequence,
                    target=bytes.fromhex(conn.serial) + b"\x00\x00",
                    pkt_type=_STATE_POWER_PKT_TYPE,
                    payload_len=len(_STATE_POWER_PAYLOAD),
                )
                conn._pending_requests[key0].put_nowait((header, _STATE_POWER_PAYLOAD))
                await asyncio.wait_for(task, timeout=1.0)
                task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert sink is not None
        accepted = next(o for o in sink.observations if o.category == "accepted")
        assert accepted.sequence == 0

    async def test_timeout_observes_timeout_and_no_accepted(self) -> None:
        """No response ever arrives: exactly one send, no accepted event,
        and a terminal timeout + cleanup pair."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=0.15, max_retries=2
        )
        sink: _RequestObservationSink | None = None
        try:
            await conn.open()

            async def _drive() -> None:
                nonlocal sink
                with _capture_request_observations() as active_sink:
                    sink = active_sink
                    with pytest.raises(LifxTimeoutError):
                        await conn.request(Device.GetPower(), timeout=0.15)

            await asyncio.wait_for(asyncio.create_task(_drive()), timeout=1.0)
        finally:
            await conn.close()
        assert sink is not None
        categories = [obs.category for obs in sink.observations]
        assert categories == ["logical_start", "sent", "timeout", "cleanup"]
        assert not any(o.category == "accepted" for o in sink.observations)

    async def test_send_error_observes_send_error_not_sent(self) -> None:
        """A ``send_packet()`` failure on the initial transmission emits
        send_error (not sent) and no exception text is ever captured -- the
        observation carries only the bounded category, sequence and
        timestamp (T-14-02)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=2
        )
        sink: _RequestObservationSink | None = None
        try:
            await conn.open()

            async def _boom(*args: Any, **kwargs: Any) -> None:
                raise LifxConnectionError("boom -- must never reach the observation")

            async def _drive() -> None:
                nonlocal sink
                with _capture_request_observations() as active_sink:
                    sink = active_sink
                    with (
                        patch.object(conn, "send_packet", side_effect=_boom),
                        pytest.raises(LifxConnectionError),
                    ):
                        await conn.request(Device.GetPower(), timeout=2.0)

            await asyncio.wait_for(asyncio.create_task(_drive()), timeout=1.0)
        finally:
            await conn.close()
        assert sink is not None
        categories = [obs.category for obs in sink.observations]
        assert categories == ["logical_start", "send_error", "cleanup"]
        send_error = next(o for o in sink.observations if o.category == "send_error")
        assert send_error.sequence == 0
        assert "boom" not in repr(send_error)
        assert "boom" not in repr(sink)

    async def test_cancellation_observes_cancelled_then_cleanup(self) -> None:
        """Cancelling the awaiting task mid-wait emits cancelled then
        cleanup, and CancelledError still propagates."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=5.0, max_retries=8
        )
        sink: _RequestObservationSink | None = None
        task: asyncio.Task[Any] | None = None
        try:
            await conn.open()

            async def _drive() -> None:
                nonlocal sink
                with _capture_request_observations() as active_sink:
                    sink = active_sink
                    await conn.request(Device.GetPower(), timeout=5.0)

            task = asyncio.create_task(_drive())
            await _wait_for_keys(conn, 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert sink is not None
        categories = [obs.category for obs in sink.observations]
        assert categories == ["logical_start", "sent", "cancelled", "cleanup"]

    def test_sink_repr_suppresses_observation_values(self) -> None:
        """The sink's repr exposes a count only -- never category, sequence
        or timestamp values, even after several observations (T-14-02)."""
        sink = _RequestObservationSink()
        sink.observe("logical_start", None, 1_000, None)
        sink.observe("sent", 0, 1_500, None)
        sink.observe("accepted", 0, 2_000, True)
        rendered = repr(sink)
        assert rendered == "_RequestObservationSink(count=3)"
        assert "1000" not in rendered
        assert "1500" not in rendered
        assert "sent" not in rendered
        assert "accepted" not in rendered

    def test_no_running_loop_returns_none(self) -> None:
        """``_current_request_observer()`` is safe to call with no running
        event loop at all -- the RuntimeError arm of the selector."""
        assert _current_request_observer() is None

    async def test_send_error_without_observer_is_a_noop(self) -> None:
        """No observer attached: a send failure on the initial transmission
        still propagates normally (the "observer is None" arm of the
        send_error branch, exercised with nothing listening)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=2
        )

        async def _boom(*args: Any, **kwargs: Any) -> None:
            raise LifxConnectionError("boom")

        try:
            await conn.open()
            with (
                patch.object(conn, "send_packet", side_effect=_boom),
                pytest.raises(LifxConnectionError),
            ):
                await conn.request(Device.GetPower(), timeout=2.0)
        finally:
            await conn.close()
        assert _current_request_observer() is None

    async def test_retransmit_send_error_observes_send_error(self) -> None:
        """The initial send succeeds (observed: sent(0)); the retransmitted
        send then fails, observing send_error(1) -- not sent(1) -- and no
        accepted event (the retransmit branch's send_error arm, distinct
        from the initial-send arm covered above)."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=3
        )
        sink: _RequestObservationSink | None = None
        real_send = conn.send_packet
        call_count = 0

        async def _flaky(*args: Any, **kwargs: Any) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await real_send(*args, **kwargs)
                return
            raise LifxConnectionError("retransmit boom")

        try:
            await conn.open()
            with patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.05,)):

                async def _drive() -> None:
                    nonlocal sink
                    with _capture_request_observations() as active_sink:
                        sink = active_sink
                        with (
                            patch.object(conn, "send_packet", side_effect=_flaky),
                            pytest.raises(LifxConnectionError),
                        ):
                            await conn.request(Device.GetPower(), timeout=2.0)

                await asyncio.wait_for(asyncio.create_task(_drive()), timeout=1.0)
        finally:
            await conn.close()
        assert sink is not None
        categories = [obs.category for obs in sink.observations]
        assert categories == ["logical_start", "sent", "send_error", "cleanup"]
        send_error = next(o for o in sink.observations if o.category == "send_error")
        assert send_error.sequence == 1
        assert not any(o.category == "accepted" for o in sink.observations)

    async def test_cancellation_without_observer_is_a_noop(self) -> None:
        """No observer attached: cancelling mid-wait still raises
        CancelledError normally -- the "observer is None" arm of the
        cancellation handler."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=5.0, max_retries=8
        )
        task: asyncio.Task[Any] | None = None
        try:
            await conn.open()
            task = asyncio.create_task(conn.request(Device.GetPower(), timeout=5.0))
            await _wait_for_keys(conn, 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            task = None
        finally:
            if task is not None and not task.done():
                task.cancel()
            await conn.close()
        assert _current_request_observer() is None

    async def test_retransmit_send_error_without_observer_is_a_noop(self) -> None:
        """No observer attached: a retransmitted send failure still
        propagates normally -- the "observer is None" arm of the
        retransmit-branch send_error handler."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=2.0, max_retries=3
        )
        real_send = conn.send_packet
        call_count = 0

        async def _flaky(*args: Any, **kwargs: Any) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await real_send(*args, **kwargs)
                return
            raise LifxConnectionError("retransmit boom")

        try:
            await conn.open()
            with (
                patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.05,)),
                patch.object(conn, "send_packet", side_effect=_flaky),
                pytest.raises(LifxConnectionError),
            ):
                await conn.request(Device.GetPower(), timeout=2.0)
        finally:
            await conn.close()
        assert call_count == 2
        assert _current_request_observer() is None

    def test_observer_insertion_leaves_public_surface_unchanged(self) -> None:
        """Regression gate (T-14-03): the observer seam must never appear on
        a public signature, and the retransmit schedule constant is
        untouched by this plan (source-level anti-weakening check for the
        Task 2 coverage/estimate concern in 14-REVIEWS.md)."""
        import inspect

        from lifx.const import REQUEST_RETRANSMIT_GAPS

        assert REQUEST_RETRANSMIT_GAPS == (
            0.2,
            0.3,
            0.4,
            0.5,
            0.7,
            0.9,
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
        )

        request_params = list(inspect.signature(DeviceConnection.request).parameters)
        assert request_params == ["self", "packet", "timeout"]
        request_stream_params = list(
            inspect.signature(DeviceConnection.request_stream).parameters
        )
        assert request_stream_params == ["self", "packet", "timeout"]
        for params in (request_params, request_stream_params):
            assert "observer" not in params

        # observer is keyword-only with a None default -- every existing
        # caller of _transmit_and_listen() (both thin wrappers) keeps
        # working with no source change if this default were ever removed.
        transmit_params = inspect.signature(
            DeviceConnection._transmit_and_listen
        ).parameters
        assert transmit_params["observer"].default is None
        assert transmit_params["observer"].kind == inspect.Parameter.KEYWORD_ONLY

    def test_observe_rejects_an_unknown_category(self) -> None:
        """`_RequestObservationSink.observe()` validates every category it
        receives -- a defensive gate against a future production caller
        passing a value outside the seven bounded categories."""
        sink = _RequestObservationSink()

        with pytest.raises(ValueError, match="unknown request observation category"):
            sink.observe("not_a_real_category", None, 0, None)

    async def test_capture_outside_a_task_raises_when_current_task_is_none(
        self,
    ) -> None:
        """`asyncio.current_task()` can return `None` from inside a running
        loop when the calling code is not itself a Task (rather than raising
        `RuntimeError` outright, which only happens with no loop at all)."""
        import scripts.measurement_support as measurement_support

        with patch.object(
            measurement_support.asyncio, "current_task", return_value=None
        ):
            with pytest.raises(
                RuntimeError, match="request observation capture requires an asyncio"
            ):
                with _capture_request_observations():
                    pass

    async def test_nested_capture_restores_the_outer_observer(self) -> None:
        """A second, nested capture must not clobber the first one's selection
        once it exits -- the `finally` block's `had_previous` restore arm."""
        from lifx.network.connection import _REQUEST_OBSERVER_TASK_ATTRIBUTE

        task = asyncio.current_task()
        assert task is not None

        with _capture_request_observations() as outer:
            outer_observer = getattr(task, _REQUEST_OBSERVER_TASK_ATTRIBUTE)
            with _capture_request_observations() as inner:
                inner_observer = getattr(task, _REQUEST_OBSERVER_TASK_ATTRIBUTE)
                assert inner_observer is not outer_observer
                inner_observer("logical_start", None, 1, None)
            restored_observer = getattr(task, _REQUEST_OBSERVER_TASK_ATTRIBUTE)
            assert restored_observer is outer_observer
            outer_observer("logical_start", None, 2, None)

        assert [obs.timestamp_ns for obs in inner.observations] == [1]
        assert [obs.timestamp_ns for obs in outer.observations] == [2]
