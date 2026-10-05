"""Tests for waiting until a light reports that it is off."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from lifx.devices.light import wait_until_off


async def test_waits_until_the_light_reports_off() -> None:
    light = MagicMock()
    light.get_power = AsyncMock(side_effect=[65535, 65535, 0])

    assert await wait_until_off(light, timeout=1.0, interval=0.0) is True
    assert light.get_power.await_count == 3


async def test_gives_up_when_the_light_never_reports_off() -> None:
    light = MagicMock()
    light.get_power = AsyncMock(return_value=65535)

    assert await wait_until_off(light, timeout=0.05, interval=0.01) is False
