"""Tests for the escalating GetService re-broadcast schedule (DISC-01, DISC-02).

Covers the behavioural branch matrix from 02-RESEARCH.md Validation Architecture:
schedule timing, window capping, schedule exhaustion, quiet-slice continue with
both idle and overall exits, no-mark_response-on-send, multi-send loop passes,
message/source reuse across re-sends, and dedup across broadcasts.
"""

from __future__ import annotations

import asyncio
import sys
import time
from unittest.mock import AsyncMock, patch

import pytest

from lifx.exceptions import LifxTimeoutError
from lifx.network.discovery import _discover_with_packet, discover_devices
from lifx.protocol.packets import Device as DevicePackets
from tests.test_network.test_discovery_errors import _build_state_service_packet


def _make_quiet_receive() -> AsyncMock:
    """Build a receive mock that honours the requested slice before timing out.

    Must sleep for the requested timeout before raising — with the new
    continue-on-timeout loop, an instantly-raising receive would hot-spin
    the loop until a deadline fires (02-RESEARCH.md Pitfall 6).
    """

    async def _quiet_receive(timeout: float = 2.0):
        await asyncio.sleep(timeout)
        raise LifxTimeoutError("timeout")

    return _quiet_receive


def _make_recording_send(send_times: list[float]) -> AsyncMock:
    """Build a send mock that records the monotonic time of every call."""

    async def _recording_send(data: bytes, address: tuple[str, int]) -> None:
        send_times.append(time.monotonic())

    return _recording_send


def _build_mock_transport(send: AsyncMock, receive: AsyncMock) -> AsyncMock:
    """Build an AsyncMock UdpTransport with the given send/receive callables."""
    mock_transport = AsyncMock()
    mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
    mock_transport.__aexit__ = AsyncMock(return_value=False)
    mock_transport.send = send
    mock_transport.receive = receive
    return mock_transport


class TestRebroadcastSchedule:
    """Schedule mechanics: timing, window capping, exhaustion, exits, reuse."""

    @pytest.mark.asyncio
    async def test_two_sends_at_first_gap_within_window(self) -> None:
        """Real (unpatched) gaps: a 1.0 s window yields exactly 2 sends,
        the second at ~0.6 s after the first (DISC-01 schedule timing)."""
        send_times: list[float] = []

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.allocate_source", return_value=42),
        ):
            mock_transport_cls.return_value = _build_mock_transport(
                _make_recording_send(send_times), _make_quiet_receive()
            )

            _ = [d async for d in discover_devices(timeout=1.0)]

        assert len(send_times) == 2
        gap = send_times[1] - send_times[0]
        assert 0.4 <= gap <= 0.9

    @pytest.mark.asyncio
    async def test_window_caps_schedule_single_send(self) -> None:
        """timeout=0.3 < first offset (0.6) => exactly 1 send."""
        send_times: list[float] = []

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.allocate_source", return_value=42),
        ):
            mock_transport_cls.return_value = _build_mock_transport(
                _make_recording_send(send_times), _make_quiet_receive()
            )

            _ = [d async for d in discover_devices(timeout=0.3)]

        assert len(send_times) == 1

    @pytest.mark.asyncio
    async def test_schedule_exhaustion_falls_back_to_remaining(self) -> None:
        """Patched gaps (0.05, 0.05) with timeout=0.5: all 3 sends fire
        (t=0, 0.05, 0.10), schedule exhausts, receive slice falls back to
        deadline.remaining() until the overall deadline fires at ~0.5s."""
        send_times: list[float] = []

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.allocate_source", return_value=42),
            patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", (0.05, 0.05)),
        ):
            mock_transport_cls.return_value = _build_mock_transport(
                _make_recording_send(send_times), _make_quiet_receive()
            )

            start = time.monotonic()
            _ = [d async for d in discover_devices(timeout=0.5)]
            elapsed = time.monotonic() - start

        assert len(send_times) == 3
        assert 0.5 <= elapsed <= 1.0

    @pytest.mark.asyncio
    async def test_quiet_slice_rebroadcast_then_idle_exit(self) -> None:
        """Patched gaps (0.1,), idle window 0.4s (max_response_time=0.2 x
        idle_timeout_multiplier=2.0), timeout=5.0: 2 sends, zero yields,
        exits via idle deadline; elapsed in [0.4, 1.0)."""
        send_times: list[float] = []

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.allocate_source", return_value=42),
            patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", (0.1,)),
        ):
            mock_transport_cls.return_value = _build_mock_transport(
                _make_recording_send(send_times), _make_quiet_receive()
            )

            start = time.monotonic()
            devices = [
                d
                async for d in discover_devices(
                    timeout=5.0,
                    max_response_time=0.2,
                    idle_timeout_multiplier=2.0,
                )
            ]
            elapsed = time.monotonic() - start

        assert devices == []
        assert len(send_times) == 2
        assert 0.4 <= elapsed < 1.0

    @pytest.mark.asyncio
    async def test_quiet_slice_rebroadcast_then_overall_exit(self) -> None:
        """Patched gaps (0.1,), default idle, timeout=0.5: 2 sends, zero
        yields, exits via overall deadline; elapsed in [0.5, 1.0)."""
        send_times: list[float] = []

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.allocate_source", return_value=42),
            patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", (0.1,)),
        ):
            mock_transport_cls.return_value = _build_mock_transport(
                _make_recording_send(send_times), _make_quiet_receive()
            )

            start = time.monotonic()
            devices = [d async for d in discover_devices(timeout=0.5)]
            elapsed = time.monotonic() - start

        assert devices == []
        assert len(send_times) == 2
        assert 0.5 <= elapsed < 1.0

    @pytest.mark.asyncio
    async def test_send_does_not_reset_idle_window(self) -> None:
        """A send at t=0.35s must not reset the idle deadline. Patched gaps
        (0.35,), idle window 0.5s (max_response_time=0.25 x
        idle_timeout_multiplier=2.0), timeout=5.0: 2 sends; elapsed in
        [0.45, 0.75) -- an idle reset from the t=0.35 send would push exit
        to ~0.85, which the upper bound excludes."""
        send_times: list[float] = []

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.allocate_source", return_value=42),
            patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", (0.35,)),
        ):
            mock_transport_cls.return_value = _build_mock_transport(
                _make_recording_send(send_times), _make_quiet_receive()
            )

            start = time.monotonic()
            devices = [
                d
                async for d in discover_devices(
                    timeout=5.0,
                    max_response_time=0.25,
                    idle_timeout_multiplier=2.0,
                )
            ]
            elapsed = time.monotonic() - start

        assert devices == []
        assert len(send_times) == 2
        assert 0.45 <= elapsed < 0.75

    @pytest.mark.asyncio
    async def test_multiple_sends_due_in_one_loop_pass(self) -> None:
        """Patched gaps (0.05, 0.05): the first receive call ignores its
        requested slice and sleeps ~0.3s before timing out (simulating a
        slow wake-up past both offsets); subsequent receives sleep their
        requested slice. timeout=0.6 => 3 sends total, with the 2nd and 3rd
        firing within 0.05s of each other (both in one due-send pass)."""
        send_times: list[float] = []
        call_count = 0

        async def mock_receive(timeout: float = 2.0):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(0.3)
            else:
                await asyncio.sleep(timeout)
            raise LifxTimeoutError("timeout")

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", (0.05, 0.05)),
            patch("lifx.network.discovery.allocate_source", return_value=42),
        ):
            mock_transport_cls.return_value = _build_mock_transport(
                _make_recording_send(send_times), mock_receive
            )

            _ = [d async for d in discover_devices(timeout=0.6)]

        assert len(send_times) == 3
        assert abs(send_times[2] - send_times[1]) < 0.05

    @pytest.mark.asyncio
    async def test_rebroadcast_reuses_identical_message(self) -> None:
        """Every re-send reuses the identical message bytes and destination
        (same source, same sequence) -- proves the source-validation guard
        accepts responses to any broadcast in the session."""
        send_mock = AsyncMock()

        async def quiet_receive(timeout: float = 2.0):
            await asyncio.sleep(timeout)
            raise LifxTimeoutError("timeout")

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", (0.1, 0.1)),
            patch("lifx.network.discovery.allocate_source", return_value=42),
        ):
            mock_transport_cls.return_value = _build_mock_transport(
                send_mock, quiet_receive
            )

            _ = [d async for d in discover_devices(timeout=0.5)]

        assert send_mock.call_count == 3
        first_call = send_mock.call_args_list[0]
        for call in send_mock.call_args_list[1:]:
            assert call == first_call


class TestRebroadcastDedup:
    """DISC-02: duplicate StateService responses across re-broadcasts dedup."""

    @pytest.mark.asyncio
    async def test_same_serial_across_broadcasts_yields_once(self) -> None:
        """Same serial answers twice, spanning a re-broadcast boundary:
        exactly 1 yield, exactly 2 sends."""
        known_source = 42
        valid_serial = b"\xd0\x73\xd5\x01\x02\x03\x00\x00"
        packet = _build_state_service_packet(source=known_source, target=valid_serial)
        send_times: list[float] = []
        call_count = 0

        async def mock_receive(timeout: float = 2.0):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return packet, ("192.168.1.100", 56700)
            if call_count == 2:
                await asyncio.sleep(0.2)
                return packet, ("192.168.1.100", 56700)
            await asyncio.sleep(timeout)
            raise LifxTimeoutError("timeout")

        with (
            patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
            patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", (0.15,)),
            patch("lifx.network.discovery.allocate_source", return_value=known_source),
        ):
            mock_transport_cls.return_value = _build_mock_transport(
                _make_recording_send(send_times), mock_receive
            )

            responses = [
                r
                async for r in _discover_with_packet(
                    DevicePackets.GetService(), timeout=0.8
                )
            ]

        assert len(responses) == 1
        assert len(send_times) == 2


@pytest.mark.emulator
@pytest.mark.flaky(retries=2, delay=1, condition=sys.platform.startswith("win32"))
class TestRebroadcastEmulator:
    """DISC-02 integration: dedup holds across a real re-broadcast window."""

    @pytest.mark.asyncio
    async def test_emulator_dedup_across_rebroadcast_window(
        self, emulator_port: int
    ) -> None:
        """A 2.0s window spans sends at t=0, 0.6, 1.8. At least one device is
        found and no serial is yielded twice."""
        seen_serials: set[str] = set()
        found_any = False
        async for disc in discover_devices(
            timeout=2.0,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            found_any = True
            assert disc.serial not in seen_serials, f"Duplicate serial: {disc.serial}"
            seen_serials.add(disc.serial)

        assert found_any
