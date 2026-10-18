"""Tests for Device.ping(), a state-free reachability probe over echo."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest
from lifx_emulator.handlers.device_handlers import EchoRequestHandler

from lifx.devices.light import Light
from lifx.exceptions import LifxTimeoutError
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Device as DevicePackets

SERIAL = "d073d5000001"


def _echo_header(payload: bytes) -> LifxHeader:
    return LifxHeader(
        size=36 + 64,
        protocol=1024,
        source=1,
        target=bytes.fromhex(SERIAL) + b"\x00\x00",
        tagged=False,
        ack_required=False,
        res_required=False,
        sequence=0,
        pkt_type=DevicePackets.EchoResponse.PKT_TYPE,
    )


@pytest.fixture
def echo_payloads() -> Any:
    """Record the payload of every echo request the emulator handles."""
    seen: list[bytes] = []
    original = EchoRequestHandler.handle

    def recording(self: Any, device_state: Any, packet: Any, res_required: bool):
        seen.append(packet.payload)
        return original(self, device_state, packet, res_required)

    with patch.object(EchoRequestHandler, "handle", recording):
        yield seen


@pytest.mark.emulator
class TestPingEmulated:
    async def test_returns_positive_rtt_with_one_request(
        self, emulator_port: int, echo_payloads: list[bytes]
    ) -> None:
        async with Light(SERIAL, "127.0.0.1", port=emulator_port, timeout=2.0) as d:
            rtt = await d.ping()

        assert isinstance(rtt, float)
        assert rtt > 0
        assert len(echo_payloads) == 1
        assert len(echo_payloads[0]) == 64

    async def test_payload_has_counter_and_random_bytes(
        self, emulator_port: int, echo_payloads: list[bytes]
    ) -> None:
        async with Light(SERIAL, "127.0.0.1", port=emulator_port, timeout=2.0) as d:
            await d.ping()
            await d.ping()

        first, second = echo_payloads
        assert int.from_bytes(first[:8], "big") + 1 == int.from_bytes(second[:8], "big")
        assert first[8:] != second[8:]

    async def test_concurrent_pings_each_get_their_own_response(
        self, emulator_port: int, echo_payloads: list[bytes]
    ) -> None:
        async with Light(SERIAL, "127.0.0.1", port=emulator_port, timeout=2.0) as d:
            rtts = await asyncio.gather(d.ping(), d.ping(), d.ping())

        assert all(r > 0 for r in rtts)
        assert len(set(echo_payloads)) == 3

    async def test_silent_device_raises_timeout(
        self, emulator_port: int, scenario_manager: Any
    ) -> None:
        with scenario_manager("devices", SERIAL, {"drop_packets": {58: 1.0}}):
            async with Light(
                SERIAL, "127.0.0.1", port=emulator_port, timeout=0.5, max_retries=1
            ) as d:
                with pytest.raises(LifxTimeoutError):
                    await d.ping()


class TestPingCorrelation:
    """A response carrying a different payload never satisfies the ping."""

    @staticmethod
    def _stream(light: Light, payloads_for: Any) -> Any:
        async def fake(packet: Any, timeout: Any = None, max_retries: Any = None):
            for payload in payloads_for(packet.payload):
                yield _echo_header(payload), payload

        return patch.object(light.connection, "_request_stream_impl", fake)

    async def test_mismatched_payload_is_ignored(self) -> None:
        light = Light(SERIAL, "127.0.0.1", timeout=0.5)

        def only_wrong(sent: bytes) -> list[bytes]:
            return [bytes(64)]

        with (
            self._stream(light, only_wrong),
            patch.object(light.connection, "_ensure_open", return_value=None),
        ):
            with pytest.raises(LifxTimeoutError):
                await light.ping()

    async def test_matching_payload_after_mismatch_succeeds(self) -> None:
        light = Light(SERIAL, "127.0.0.1", timeout=0.5)

        def wrong_then_right(sent: bytes) -> list[bytes]:
            return [bytes(64), sent]

        with (
            self._stream(light, wrong_then_right),
            patch.object(light.connection, "_ensure_open", return_value=None),
        ):
            assert await light.ping() > 0
