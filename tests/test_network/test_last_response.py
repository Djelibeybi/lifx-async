"""The connection records when it last received a correlated response."""

from __future__ import annotations

from unittest.mock import patch

from lifx.devices import Light
from lifx.network.connection import DeviceConnection
from tests.test_network.test_endpoint_migration import (
    LOOPBACK,
    SERIAL,
    _emulator_on_new_port,
)


def test_no_response_yet() -> None:
    assert DeviceConnection(SERIAL, "192.0.2.10", 56700).last_response_at is None


async def test_correlated_response_is_stamped_with_the_connection_clock() -> None:
    with _emulator_on_new_port() as port:
        light = Light(serial=SERIAL, ip=LOOPBACK, port=port, timeout=2.0)
        async with light:
            with patch("lifx.network.connection.monotonic_now", return_value=1234.5):
                await light.get_label()
            assert light.connection.last_response_at == 1234.5
