"""Tests for the product kelvin range on caller writes and library colors.

A caller-supplied colour outside the product's range fails at the call site;
colours the library generates (themes, moods, effects, firmware palettes) are
clamped into the range instead.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.api import DeviceGroup
from lifx.color import HSBK
from lifx.const import KELVIN_SATURATED
from lifx.devices.ceiling import CeilingLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.pulse import EffectPulse
from lifx.effects.state_manager import DeviceStateManager
from lifx.products.registry import (
    ProductCapability,
    ProductInfo,
    TemperatureRange,
    TemperatureRangeUpgrade,
)
from lifx.protocol import packets
from lifx.protocol.protocol_types import FirmwareEffect, LightWaveform
from lifx.theme import Theme

SERIAL = "d073d5010203"
LOW = HSBK(hue=0, saturation=0, brightness=1.0, kelvin=1500)
HIGH = HSBK(hue=0, saturation=0, brightness=1.0, kelvin=9500)
OK = HSBK(hue=0, saturation=0, brightness=1.0, kelvin=3500)


def _product(low: int = 2500, high: int = 9000, *, caps: int = 0) -> ProductInfo:
    return ProductInfo(
        pid=1,
        name="Test",
        vendor=1,
        capabilities=ProductCapability.COLOR | caps,
        temperature_range=TemperatureRange(min=low, max=high),
        min_ext_mz_firmware=None,
    )


def _ranged(device: Any, low: int = 2500, high: int = 9000, *, caps: int = 0) -> Any:
    """Give a mocked-connection device a firmware-resolved kelvin range."""
    device._capabilities = _product(low, high, caps=caps)
    device.connection.request.return_value = True
    return device


@pytest.fixture
def ranged_light(light: Light) -> Light:
    return _ranged(light)


class TestLightCallerWrites:
    """Caller writes on a Light are checked against the product range."""

    @pytest.mark.parametrize("color", [LOW, HIGH])
    async def test_set_color_rejects(self, ranged_light: Light, color: HSBK) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000") as raised:
            await ranged_light.set_color(color)
        assert SERIAL in str(raised.value)
        ranged_light.connection.request.assert_not_called()

    @pytest.mark.parametrize("kelvin", [2500, 9000, KELVIN_SATURATED])
    async def test_set_color_accepts_range_edges_and_zero(
        self, ranged_light: Light, kelvin: int
    ) -> None:
        await ranged_light.set_color(HSBK(0, 0, 1.0, kelvin))
        ranged_light.connection.request.assert_called_once()

    async def test_set_kelvin_rejects(self, ranged_light: Light) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await ranged_light.set_kelvin(1500)
        ranged_light.connection.request.assert_not_called()

    async def test_set_kelvin_keeps_global_check_when_range_unknown(
        self, light: Light
    ) -> None:
        with pytest.raises(ValueError, match="1000"):
            await light.set_kelvin(500)
        light.connection.request.assert_not_called()

    async def test_unknown_range_accepts_global_range(self, light: Light) -> None:
        light.connection.request.return_value = True
        await light.set_color(LOW)
        light.connection.request.assert_called_once()

    async def test_set_waveform_rejects(self, ranged_light: Light) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await ranged_light.set_waveform(LOW, 1.0, 1, LightWaveform.SINE)
        ranged_light.connection.request.assert_not_called()

    async def test_pulse_and_breathe_reject(self, ranged_light: Light) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await ranged_light.pulse(LOW)
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await ranged_light.breathe(HIGH)
        ranged_light.connection.request.assert_not_called()

    async def test_waveform_optional_checks_kelvin_only_when_applied(
        self, ranged_light: Light
    ) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await ranged_light.set_waveform_optional(
                LOW, 1.0, 1, LightWaveform.SINE, set_kelvin=True
            )
        ranged_light.connection.request.assert_not_called()
        # The kelvin is not applied, so it never reaches the device
        await ranged_light.set_waveform_optional(
            LOW, 1.0, 1, LightWaveform.SINE, set_kelvin=False
        )
        ranged_light.connection.request.assert_called_once()

    async def test_wider_range_after_firmware_upgrade(self, light: Light) -> None:
        product = ProductInfo(
            pid=1,
            name="Test",
            vendor=1,
            capabilities=ProductCapability.COLOR,
            temperature_range=TemperatureRange(min=2500, max=9000),
            min_ext_mz_firmware=None,
            temperature_range_upgrades=(
                TemperatureRangeUpgrade(
                    min_firmware=(4 << 16) | 0,
                    temperature_range=TemperatureRange(min=1500, max=9000),
                ),
            ),
        )
        light.connection.request.return_value = True
        light._capabilities = product.for_firmware((3 << 16) | 0)
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await light.set_color(LOW)
        light._capabilities = product.for_firmware((4 << 16) | 0)
        await light.set_color(LOW)
        light.connection.request.assert_called_once()


class TestLightThemeClamps:
    """A Light's theme colour is clamped into range, never rejected."""

    async def test_apply_theme_clamps(self, ranged_light: Light) -> None:
        ranged_light.get_power = AsyncMock(return_value=True)  # type: ignore[method-assign]
        await ranged_light.apply_theme(Theme([LOW]))
        sent = ranged_light.connection.request.call_args[0][0]
        assert sent.color.kelvin == 2500

    async def test_apply_theme_clamps_high(self, ranged_light: Light) -> None:
        ranged_light.get_power = AsyncMock(return_value=True)  # type: ignore[method-assign]
        await ranged_light.apply_theme(Theme([HIGH]))
        sent = ranged_light.connection.request.call_args[0][0]
        assert sent.color.kelvin == 9000

    async def test_clamp_leaves_zero_and_in_range_alone(
        self, ranged_light: Light
    ) -> None:
        zero = HSBK(120, 1.0, 1.0, KELVIN_SATURATED)
        assert ranged_light._clamp_color(zero) is zero
        assert ranged_light._clamp_color(OK) is OK

    async def test_clamp_unknown_range_is_noop(self, light: Light) -> None:
        assert light._clamp_color(LOW) is LOW


class TestMultiZoneWrites:
    @pytest.fixture
    def strip(self, multizone_light: MultiZoneLight) -> MultiZoneLight:
        return _ranged(multizone_light, caps=ProductCapability.MULTIZONE)

    async def test_set_color_zones_rejects(self, strip: MultiZoneLight) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await strip.set_color_zones(0, 3, LOW)
        strip.connection.request.assert_not_called()

    async def test_set_color_zones_rejects_an_invalid_range(
        self, strip: MultiZoneLight
    ) -> None:
        with pytest.raises(ValueError, match="Invalid zone range"):
            await strip.set_color_zones(3, 1, OK)
        strip.connection.request.assert_not_called()

    async def test_set_extended_color_zones_rejects(
        self, strip: MultiZoneLight
    ) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await strip.set_extended_color_zones(0, [OK, HIGH])
        strip.connection.request.assert_not_called()

    async def test_set_all_color_zones_rejects_before_any_send(
        self, strip: MultiZoneLight
    ) -> None:
        strip._zone_count = 4
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await strip.set_all_color_zones([OK, OK, OK, LOW])
        strip.connection.request.assert_not_called()

    async def test_apply_theme_clamps(self, strip: MultiZoneLight) -> None:
        strip.get_zone_count = AsyncMock(return_value=4)  # type: ignore[method-assign]
        strip.get_power = AsyncMock(return_value=True)  # type: ignore[method-assign]
        await strip.apply_theme(Theme([LOW, HIGH]))
        kelvins = {
            call[0][0].color.kelvin for call in strip.connection.request.call_args_list
        }
        assert kelvins
        assert all(2500 <= k <= 9000 for k in kelvins)


def _tile() -> MagicMock:
    tile = MagicMock()
    tile.tile_index = 0
    tile.width = 8
    tile.height = 8
    tile.total_zones = 64
    tile.requires_frame_buffer = False
    tile.user_x = 0.0
    tile.user_y = 0.0
    return tile


class TestMatrixWrites:
    @pytest.fixture
    def matrix(self, matrix_light: MatrixLight) -> MatrixLight:
        matrix_light = _ranged(matrix_light, caps=ProductCapability.MATRIX)
        matrix_light._device_chain = [_tile()]
        return matrix_light

    async def test_set_matrix_colors_rejects(self, matrix: MatrixLight) -> None:
        colors = [OK] * 63 + [LOW]
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await matrix.set_matrix_colors(0, colors)
        matrix.connection.request.assert_not_called()

    async def test_set_matrix_colors_uniform_rejects(self, matrix: MatrixLight) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await matrix.set_matrix_colors(0, [HIGH] * 64)
        matrix.connection.request.assert_not_called()

    async def test_set64_rejects(self, matrix: MatrixLight) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await matrix.set64(0, 1, 0, 0, 8, 0, [LOW] * 64)
        matrix.connection.request.assert_not_called()

    async def test_set64_accepts_in_range(self, matrix: MatrixLight) -> None:
        await matrix.set64(0, 1, 0, 0, 8, 0, [OK] * 64)
        matrix.connection.request.assert_called_once()

    async def test_apply_theme_clamps(self, matrix: MatrixLight) -> None:
        matrix.get_device_chain = AsyncMock(return_value=[_tile()])  # type: ignore[method-assign]
        matrix.ensure_capabilities = AsyncMock()  # type: ignore[method-assign]
        matrix.get_power = AsyncMock(return_value=True)  # type: ignore[method-assign]
        await matrix.apply_theme(Theme([LOW, HIGH]))
        sent = [call[0][0] for call in matrix.connection.request.call_args_list]
        assert sent
        for packet in sent:
            assert all(2500 <= c.kelvin <= 9000 for c in packet.colors)

    async def test_firmware_effect_palette_clamps(self, matrix: MatrixLight) -> None:
        await matrix.set_effect(FirmwareEffect.MORPH, palette=[LOW, HIGH], speed=1.0)
        sent = matrix.connection.request.call_args[0][0]
        assert isinstance(sent, packets.Tile.SetEffect)
        kelvins = {c.kelvin for c in sent.settings.palette[:2]}
        assert kelvins == {2500, 9000}


def _component(device: Any, product: int, size: int) -> Any:
    _ranged(device, caps=ProductCapability.MATRIX)
    device._version = MagicMock()
    device._version.product = product
    device._state = MagicMock()
    device._state.power = 65535
    for name in (
        "stored_uplight_color",
        "stored_downlight_colors",
        "stored_front_colors",
        "stored_back_colors",
        "last_uplight_color",
        "last_downlight_colors",
        "last_front_colors",
        "last_back_colors",
    ):
        setattr(device._state, name, None)
    device.set_matrix_colors = AsyncMock()
    device.get_power = AsyncMock(return_value=65535)
    device._save_state_to_file = AsyncMock()
    white = HSBK(0, 0, 1.0, 3500)
    device.get_all_tile_colors = AsyncMock(return_value=[[white] * size])
    return device


class TestComponentWrites:
    @pytest.fixture
    def ceiling(self) -> CeilingLight:
        ceiling = CeilingLight(serial=SERIAL, ip="192.0.2.10")
        ceiling.connection = AsyncMock()
        return _component(ceiling, 176, 64)

    @pytest.fixture
    def mirror(self) -> MirrorLight:
        mirror = MirrorLight(serial=SERIAL, ip="192.0.2.10")
        mirror.connection = AsyncMock()
        return _component(mirror, 267, 52)

    async def test_uplight_rejects(self, ceiling: CeilingLight) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await ceiling.set_uplight_color(LOW)
        ceiling.set_matrix_colors.assert_not_called()

    async def test_downlight_list_rejects(self, ceiling: CeilingLight) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await ceiling.set_downlight_colors([OK] * 62 + [HIGH])
        ceiling.set_matrix_colors.assert_not_called()

    async def test_ceiling_set_color_rejects(self, ceiling: CeilingLight) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await ceiling.set_color(LOW)
        ceiling.connection.request.assert_not_called()

    async def test_mirror_front_rejects(self, mirror: MirrorLight) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await mirror.set_front_colors(LOW)
        mirror.set_matrix_colors.assert_not_called()

    async def test_turn_on_with_colour_rejects(self, mirror: MirrorLight) -> None:
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await mirror.turn_back_on(HIGH)
        mirror.set_matrix_colors.assert_not_called()

    async def test_in_range_component_write_goes_out(
        self, ceiling: CeilingLight
    ) -> None:
        await ceiling.set_uplight_color(OK)
        ceiling.set_matrix_colors.assert_awaited_once()

    async def test_composed_tile_is_clamped(self, ceiling: CeilingLight) -> None:
        """Preserved colours read from the device are library colours."""
        stale = HSBK(0, 0, 1.0, 1200)
        ceiling.get_all_tile_colors = AsyncMock(return_value=[[stale] * 64])
        await ceiling.set_uplight_color(OK)
        written = ceiling.set_matrix_colors.call_args[0][1]
        assert min(c.kelvin for c in written) == 2500


class TestDeviceGroup:
    @staticmethod
    def _group(
        mock_device_factory: Callable[..., Any],
    ) -> tuple[DeviceGroup, Light, Light]:
        narrow = _ranged(mock_device_factory(Light, serial="d073d5000001"))
        wide = _ranged(mock_device_factory(Light, serial="d073d5000002"), 1500, 9000)
        return DeviceGroup([narrow, wide]), narrow, wide

    async def test_set_color_sends_nothing_when_one_light_rejects(
        self, mock_device_factory: Callable[..., Any]
    ) -> None:
        group, narrow, wide = self._group(mock_device_factory)
        with pytest.raises(ValueError, match=r"2500-9000.*d073d5000001"):
            await group.set_color(LOW)
        narrow.connection.request.assert_not_called()
        wide.connection.request.assert_not_called()

    async def test_pulse_sends_nothing_when_one_light_rejects(
        self, mock_device_factory: Callable[..., Any]
    ) -> None:
        group, narrow, wide = self._group(mock_device_factory)
        with pytest.raises(ValueError, match=r"2500.*9000"):
            await group.pulse(LOW)
        narrow.connection.request.assert_not_called()
        wide.connection.request.assert_not_called()

    async def test_in_range_group_write_reaches_every_light(
        self, mock_device_factory: Callable[..., Any]
    ) -> None:
        group, narrow, wide = self._group(mock_device_factory)
        await group.set_color(OK)
        narrow.connection.request.assert_called_once()
        wide.connection.request.assert_called_once()


class TestSoftwareEffectsClamp:
    """Software effect colours are clamped into the product's range."""

    def test_frame_is_clamped_keeping_kelvin_zero(self, ranged_light: Light) -> None:
        frame = [(1, 2, 3, 1500), (4, 5, 6, 9500), (7, 8, 9, 0), (1, 1, 1, 3500)]
        assert ranged_light._clamp_frame(frame) == [
            (1, 2, 3, 2500),
            (4, 5, 6, 9000),
            (7, 8, 9, 0),
            (1, 1, 1, 3500),
        ]

    def test_in_range_frame_is_returned_as_is(self, ranged_light: Light) -> None:
        frame = [(1, 2, 3, 2500), (4, 5, 6, 0)]
        assert ranged_light._clamp_frame(frame) is frame

    def test_frame_untouched_when_range_unknown(self, light: Light) -> None:
        frame = [(1, 2, 3, 1500)]
        assert light._clamp_frame(frame) is frame

    async def test_frame_effect_sends_clamped_frame(self, ranged_light: Light) -> None:
        class Warm(FrameEffect):
            @property
            def name(self) -> str:
                return "warm"

            def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
                return [LOW] * ctx.pixel_count

        effect = Warm(fps=30.0, duration=0.05)
        animator = MagicMock()
        animator.pixel_count = 2
        animator.canvas_width = 2
        animator.canvas_height = 1
        animator.wraps = False
        effect.participants = [ranged_light]
        effect._animators = [animator]

        await asyncio.wait_for(effect.async_play(), timeout=2.0)

        sent = animator.send_frame.call_args_list[0][0][0]
        assert {k for _, _, _, k in sent} == {2500}

    async def test_pulse_waveform_is_clamped(self, ranged_light: Light) -> None:
        ranged_light.set_waveform = AsyncMock()  # type: ignore[method-assign]
        effect = EffectPulse(color=LOW)
        await effect._apply_waveform(ranged_light, LOW)
        assert ranged_light.set_waveform.call_args.kwargs["color"].kelvin == 2500

    async def test_restore_color_is_clamped(self, ranged_light: Light) -> None:
        ranged_light.set_color = AsyncMock()  # type: ignore[method-assign]
        await DeviceStateManager()._restore_color(ranged_light, HIGH)
        assert ranged_light.set_color.call_args.args[0].kelvin == 9000


class TestMoodClamps:
    async def test_bulb_mood_colour_is_clamped(self, ranged_light: Light) -> None:
        ranged_light.set_color = AsyncMock()  # type: ignore[method-assign]
        ranged_light.set_power = AsyncMock()  # type: ignore[method-assign]
        await ranged_light._paint_mood(
            Theme([OK]), power_on=False, brightness=1.0, bulb_color=LOW
        )
        assert ranged_light.set_color.call_args.args[0].kelvin == 2500
