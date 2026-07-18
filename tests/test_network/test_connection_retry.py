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

from lifx.exceptions import LifxProtocolError, LifxTimeoutError
from lifx.network.connection import DeviceConnection
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Device

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
    *, source: int, sequence: int, target: bytes, pkt_type: int, payload_len: int
) -> LifxHeader:
    """Build a valid header for direct queue injection.

    Mirrors ``TestRequestStreamDebugLogging._header`` in test_connection.py,
    parameterised on source/sequence/target/pkt_type so mismatch variants
    can be constructed for the correlation branch matrix.
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
            assert 0.03 <= gap <= 0.2

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
