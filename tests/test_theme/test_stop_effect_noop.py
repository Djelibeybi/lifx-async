"""Tests that stop_effect() does nothing unless an effect is running.

Public device API against the embedded emulator. Packets are recorded on the
light's connection: the effect query a stop makes is allowed, a write is not.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from lifx.const import MOOD_FADE_SECONDS
from lifx.devices.ceiling import CeilingLight
from lifx.devices.effect_runner import effect_runner
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight
from lifx.effects import EffectColorloop
from lifx.protocol.protocol_types import FirmwareEffect
from tests.test_theme.conftest import (
    RED,
    make_theme,
    morphing,
)

pytestmark = pytest.mark.emulator


def record_packets(light: Light, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Names of every packet the light's connection sends from now on."""
    sent: list[str] = []
    connection = light.connection
    request_stream = connection.request_stream
    send_packet = connection.send_packet

    def spy_stream(packet: Any, *args: Any, **kwargs: Any) -> Any:
        sent.append(type(packet).__name__)
        return request_stream(packet, *args, **kwargs)

    async def spy_send(packet: Any, *args: Any, **kwargs: Any) -> None:
        sent.append(type(packet).__name__)
        await send_packet(packet, *args, **kwargs)

    monkeypatch.setattr(connection, "request_stream", spy_stream)
    monkeypatch.setattr(connection, "send_packet", spy_send)
    return sent


def writes(sent: list[str]) -> list[str]:
    """The packets that are not reads."""
    return [name for name in sent if ".Get" not in name and not name.startswith("Get")]


class TestNothingRunning:
    async def test_strip_keeps_its_theme_and_colors(
        self, strip: MultiZoneLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await strip.apply_theme(make_theme("unit_test_a"))
        before = await strip.get_all_color_zones()
        sent = record_packets(strip, monkeypatch)
        await strip.stop_effect()
        assert sent  # the effect query was made, and only that
        assert writes(sent) == []
        assert strip.current_theme == "unit_test_a"
        assert await strip.get_all_color_zones() == before

    async def test_matrix_keeps_its_mood_and_colors(
        self, matrix: MatrixLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await matrix.apply_mood(make_theme("unit_test_a", static_mode="grid_static"))
        await asyncio.sleep(MOOD_FADE_SECONDS)  # the mood fades in
        before = await matrix.get_all_tile_colors()
        sent = record_packets(matrix, monkeypatch)
        await matrix.stop_effect()
        assert writes(sent) == []
        assert matrix.current_mood == "unit_test_a"
        assert await matrix.get_all_tile_colors() == before

    async def test_ceiling_and_its_light_components_keep_the_theme(
        self, ceiling_device: CeilingLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with ceiling_device:
            await ceiling_device.set_power(True)
            await ceiling_device.apply_theme(
                make_theme("unit_test_a", static_mode="grid_static")
            )
            sent = record_packets(ceiling_device, monkeypatch)
            await ceiling_device.stop_effect()
            await ceiling_device.uplight.stop_effect()
            await ceiling_device.downlight.stop_effect()
            assert writes(sent) == []
            assert ceiling_device.current_theme == "unit_test_a"


class TestSomethingRunning:
    async def test_firmware_effect_on_a_strip_is_stopped(
        self, strip: MultiZoneLight
    ) -> None:
        await strip.apply_theme(make_theme("unit_test_a"))
        await strip.set_effect(MultiZoneEffect.move("forward", 5.0))
        await strip.stop_effect()
        assert (await strip.get_effect()).effect_type == FirmwareEffect.OFF

    async def test_firmware_morph_on_a_matrix_is_stopped_and_prior_state_returns(
        self, matrix: MatrixLight
    ) -> None:
        await matrix.apply_theme(make_theme("unit_test_a", static_mode="grid_static"))
        await matrix.animate_mood(morphing())
        assert matrix.current_mood == "unit_test_m"
        await matrix.stop_effect()
        assert (await matrix.get_effect()).effect_type == FirmwareEffect.OFF
        assert matrix.current_mood is None
        assert matrix.current_theme == "unit_test_a"

    async def test_software_effect_is_stopped_and_colors_come_back(
        self, strip: MultiZoneLight
    ) -> None:
        await strip.set_all_color_zones([RED] * await strip.get_zone_count())
        before = await strip.get_all_color_zones()
        await strip.start_effect(EffectColorloop())
        assert effect_runner().runs_any(strip)
        await strip.stop_effect()
        assert not effect_runner().runs_any(strip)
        assert await strip.get_all_color_zones() == before

    async def test_software_effect_on_a_light_component_is_stopped(
        self, ceiling_device: CeilingLight
    ) -> None:
        async with ceiling_device:
            await ceiling_device.set_power(True)
            await ceiling_device.uplight.start_effect(EffectColorloop())
            assert effect_runner().runs_any(ceiling_device.uplight)
            await ceiling_device.uplight.stop_effect()
            assert not effect_runner().runs_any(ceiling_device.uplight)
