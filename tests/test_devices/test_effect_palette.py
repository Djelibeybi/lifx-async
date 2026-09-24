"""Tests for the shared firmware-effect palette rule.

Covers ``derive_effect_palette()`` and ``validate_effect_palette()`` in
``lifx.devices.component_state``, and the MORPH-only default-palette
derivation wired into ``MatrixLight.set_effect()``.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.color import HSBK, Colors
from lifx.devices.base import FirmwareInfo
from lifx.devices.component_state import (
    derive_effect_palette,
    sample_effect_palette,
    validate_effect_palette,
)
from lifx.devices.matrix import MatrixEffect, MatrixLight
from lifx.exceptions import LifxProtocolError, LifxTimeoutError
from lifx.products import get_product
from lifx.protocol.protocol_types import FirmwareEffect, TileEffectSkyType

#: Product with the matrix capability and SKY firmware support, matching
#: TestSkyEffectFirmwareGate.MATRIX_PRODUCT in tests/test_devices/test_matrix.py.
_MATRIX_PRODUCT = 176


def _matrix_light() -> MatrixLight:
    """Build a mocked MatrixLight the way test_matrix.py's ``_matrix_light`` does.

    A SKY-capable matrix product on host firmware 4.4, with
    ``connection.send_packet`` mocked so a test can capture the emitted
    ``Tile.SetEffect`` packet with no network I/O.
    """
    matrix = MatrixLight(
        serial="d073d5010203",
        ip="192.168.1.100",
        port=56700,
    )
    mock_conn = MagicMock()
    mock_conn.request = AsyncMock()
    mock_conn.request_ack = AsyncMock()
    mock_conn.thread_connection = None
    matrix.connection = mock_conn
    matrix._capabilities = get_product(_MATRIX_PRODUCT)
    matrix.get_host_firmware = AsyncMock(
        return_value=FirmwareInfo(build=0, version_major=4, version_minor=4)
    )
    matrix.connection.send_packet = AsyncMock()
    return matrix


# Golden Tile.SetEffect payloads, captured with `uv run --frozen python` against
# the unmodified `set_effect()` (before any MORPH default-palette derivation was
# added). Never edit these constants after this capture commit: they pin every
# path the derivation must not change.
_GOLDEN_FLAME_NO_PALETTE = (
    "00000000000003b80b00000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000"
    "00000000000000000000ac0d000000000000ac0d000000000000ac0d"
    "000000000000ac0d000000000000ac0d000000000000ac0d00000000"
    "0000ac0d000000000000ac0d000000000000ac0d000000000000ac0d"
    "000000000000ac0d000000000000ac0d000000000000ac0d00000000"
    "0000ac0d000000000000ac0d000000000000ac0d"
)
_GOLDEN_SKY_NO_PALETTE = (
    "00000000000005b80b00000000000000000000000000000000000002"
    "00000032000000b40000000000000000000000000000000000000000"
    "00000000000000000000ac0d000000000000ac0d000000000000ac0d"
    "000000000000ac0d000000000000ac0d000000000000ac0d00000000"
    "0000ac0d000000000000ac0d000000000000ac0d000000000000ac0d"
    "000000000000ac0d000000000000ac0d000000000000ac0d00000000"
    "0000ac0d000000000000ac0d000000000000ac0d"
)
_GOLDEN_MORPH_EXPLICIT = (
    "00000000000002881300000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000"
    "000000020000ffffffffac0dabaaffffffffac0d000000000000ac0d"
    "000000000000ac0d000000000000ac0d000000000000ac0d00000000"
    "0000ac0d000000000000ac0d000000000000ac0d000000000000ac0d"
    "000000000000ac0d000000000000ac0d000000000000ac0d00000000"
    "0000ac0d000000000000ac0d000000000000ac0d"
)
_GOLDEN_FLAME_EXPLICIT = (
    "00000000000003b80b00000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000"
    "000000020000ffffffffac0d9c1bffffffffac0d000000000000ac0d"
    "000000000000ac0d000000000000ac0d000000000000ac0d00000000"
    "0000ac0d000000000000ac0d000000000000ac0d000000000000ac0d"
    "000000000000ac0d000000000000ac0d000000000000ac0d00000000"
    "0000ac0d000000000000ac0d000000000000ac0d"
)
_GOLDEN_MORPH_NO_PALETTE_BEFORE = (
    "00000000000002b80b00000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000"
    "00000000000000000000ac0d000000000000ac0d000000000000ac0d"
    "000000000000ac0d000000000000ac0d000000000000ac0d00000000"
    "0000ac0d000000000000ac0d000000000000ac0d000000000000ac0d"
    "000000000000ac0d000000000000ac0d000000000000ac0d00000000"
    "0000ac0d000000000000ac0d000000000000ac0d"
)


class TestTileSetEffectGoldens:
    """Pin Tile.SetEffect payloads for every path MORPH derivation must not change."""

    async def test_flame_no_palette(self) -> None:
        """FLAME with no palette is byte-identical to before the change."""
        matrix = _matrix_light()
        await matrix.set_effect(effect_type=FirmwareEffect.FLAME, speed=3.0)
        packet = matrix.connection.send_packet.call_args[0][0]
        assert packet.pack().hex() == _GOLDEN_FLAME_NO_PALETTE

    async def test_sky_no_palette(self) -> None:
        """SKY with no palette is byte-identical to before the change."""
        matrix = _matrix_light()
        await matrix.set_effect(
            effect_type=FirmwareEffect.SKY,
            speed=3.0,
            sky_type=TileEffectSkyType.CLOUDS,
        )
        packet = matrix.connection.send_packet.call_args[0][0]
        assert packet.pack().hex() == _GOLDEN_SKY_NO_PALETTE

    async def test_morph_explicit_palette(self) -> None:
        """MORPH with an explicit palette is byte-identical to before the change."""
        matrix = _matrix_light()
        await matrix.set_effect(
            effect_type=FirmwareEffect.MORPH,
            speed=5.0,
            palette=[Colors.RED, Colors.BLUE],
        )
        packet = matrix.connection.send_packet.call_args[0][0]
        assert packet.pack().hex() == _GOLDEN_MORPH_EXPLICIT

    async def test_flame_explicit_palette(self) -> None:
        """FLAME with an explicit palette is byte-identical to before the change."""
        matrix = _matrix_light()
        await matrix.set_effect(
            effect_type=FirmwareEffect.FLAME,
            speed=3.0,
            palette=[Colors.RED, Colors.ORANGE],
        )
        packet = matrix.connection.send_packet.call_args[0][0]
        assert packet.pack().hex() == _GOLDEN_FLAME_EXPLICIT

    async def test_morph_no_palette_never_sends_the_empty_palette(self) -> None:
        """MORPH with no palette on a multi-colour device never sends palette_count 0.

        The constant now pins the bytes MORPH must never send again (D-24):
        real firmware does not start MORPH when Tile.SetEffect carries
        palette_count=0, so the derivation sends the device's own colours
        instead.
        """
        matrix = _matrix_light()
        matrix.get_all_tile_colors = AsyncMock(return_value=[[Colors.RED, Colors.BLUE]])
        await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)
        matrix.get_all_tile_colors.assert_awaited_once()
        packet = matrix.connection.send_packet.call_args[0][0]
        assert packet.pack().hex() != _GOLDEN_MORPH_NO_PALETTE_BEFORE
        assert packet.settings.palette_count == 2

    async def test_morph_no_palette_matches_explicit_palette_bytes(self) -> None:
        """A red-and-blue device with no palette sends the explicit-palette bytes.

        Proves the sampled palette is byte-identical to passing
        ``palette=[Colors.RED, Colors.BLUE]`` explicitly.
        """
        matrix = _matrix_light()
        matrix.get_all_tile_colors = AsyncMock(return_value=[[Colors.RED, Colors.BLUE]])
        await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=5.0)
        packet = matrix.connection.send_packet.call_args[0][0]
        assert packet.pack().hex() == _GOLDEN_MORPH_EXPLICIT


class TestMorphDefaultPaletteEmulator:
    """MORPH default-palette derivation against a real emulated matrix."""

    @pytest.mark.emulator
    async def test_single_hued_colour_sends_three_generated_colours(
        self, emulator_devices
    ) -> None:
        """A single hued colour on the tile gets a generated three-colour palette."""
        matrix = emulator_devices[6]
        async with matrix:
            color = HSBK(hue=200, saturation=1.0, brightness=0.6, kelvin=3500)

            device_chain = await matrix.get_device_chain()
            zones = device_chain[0].total_zones
            await matrix.set_matrix_colors(0, [color] * zones)

            tile_colors = await matrix.get_all_tile_colors()
            distinct = {c for tile in tile_colors for c in tile}
            assert len(distinct) == 1

            await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

            effect = await matrix.get_effect()
            expected = [
                color,
                HSBK(
                    (color.hue + 45) % 360,
                    color.saturation,
                    color.brightness,
                    color.kelvin,
                ),
                HSBK(
                    (color.hue - 45) % 360,
                    color.saturation,
                    color.brightness,
                    color.kelvin,
                ),
            ]
            assert effect.palette is not None
            assert len(effect.palette) == 3
            assert effect.palette == expected

    @pytest.mark.emulator
    async def test_multi_colour_chain_sends_its_own_colours(
        self, tile_chain_light
    ) -> None:
        """A multi-tile chain showing several colours gets those colours as the palette.

        Real firmware does not start MORPH with an empty palette (D-24), so
        a device already showing several distinct colours now gets its own
        colours back as the MORPH palette instead of palette_count=0.
        """
        matrix = tile_chain_light
        async with matrix:
            chain = await matrix.get_device_chain()
            for i, tile in enumerate(chain):
                color = Colors.RED if i == 0 else Colors.BLUE
                await matrix.set_matrix_colors(i, [color] * tile.total_zones)

            tile_colors = await matrix.get_all_tile_colors()
            flattened = [color for tile in tile_colors for color in tile]
            distinct = list(dict.fromkeys(flattened))
            assert distinct == [Colors.RED, Colors.BLUE]

            await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

            effect = await matrix.get_effect()
            assert effect.effect_type == FirmwareEffect.MORPH
            assert effect.palette == [Colors.RED, Colors.BLUE]

    @pytest.mark.emulator
    async def test_single_white_sends_device_kelvin_range(
        self, emulator_devices
    ) -> None:
        """A single white colour gets whites at the device's own kelvin range."""
        matrix = emulator_devices[6]
        async with matrix:
            device_chain = await matrix.get_device_chain()
            zones = device_chain[0].total_zones
            white = HSBK(hue=0, saturation=0.0, brightness=0.6, kelvin=4000)
            await matrix.set_matrix_colors(0, [white] * zones)

            tile_colors = await matrix.get_all_tile_colors()
            assert len({color for tile in tile_colors for color in tile}) == 1

            await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

            effect = await matrix.get_effect()
            assert effect.palette is not None
            assert len(effect.palette) == 3
            assert [color.kelvin for color in effect.palette] == [
                4000,
                matrix.min_kelvin,
                matrix.max_kelvin,
            ]

    @pytest.mark.emulator
    async def test_colour_read_timeout_raises_and_sends_nothing(
        self, emulator_devices, scenario_manager
    ) -> None:
        """A dropped Get64 raises and leaves the device on OFF."""
        matrix = emulator_devices[6]
        async with matrix:
            await matrix.set_effect(effect_type=FirmwareEffect.OFF, speed=3.0)
            effect = await matrix.get_effect()
            assert effect.effect_type == FirmwareEffect.OFF

            with scenario_manager(
                "devices", "d073d5000007", {"drop_packets": {707: 1.0}}
            ):
                with pytest.raises(LifxTimeoutError):
                    await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

            effect = await matrix.get_effect()
            assert effect.effect_type == FirmwareEffect.OFF

    @pytest.mark.emulator
    async def test_more_than_sixteen_colours_sends_sixteen_evenly_sampled(
        self, emulator_devices
    ) -> None:
        """A 64-colour tile samples 16 pixels evenly spaced across the device."""
        matrix = emulator_devices[6]
        async with matrix:
            device_chain = await matrix.get_device_chain()
            assert device_chain[0].total_zones == 64

            colors = [
                HSBK(hue=i * 360 / 64, saturation=1.0, brightness=0.6, kelvin=3500)
                for i in range(64)
            ]
            await matrix.set_matrix_colors(0, colors)

            tile_colors = await matrix.get_all_tile_colors()
            flattened = [color for tile in tile_colors for color in tile]
            assert len(set(flattened)) == 64

            await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

            effect = await matrix.get_effect()
            assert effect.effect_type == FirmwareEffect.MORPH
            assert effect.palette is not None
            assert len(effect.palette) in range(2, 17)
            assert effect.palette == [flattened[i] for i in range(0, 64, 4)]


class TestDeriveEffectPalette:
    """Unit tests for derive_effect_palette()."""

    def test_hued_colour_generates_plus_and_minus_45_degrees(self) -> None:
        """A hued colour generates hue +45 and -45, keeping sat/bri/kelvin."""
        color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
        palette = derive_effect_palette([color] * 3, None, None)
        assert palette is not None
        assert [round(c.hue) for c in palette] == [120, 165, 75]
        assert all(c.saturation == 1.0 for c in palette)
        assert all(c.brightness == 0.8 for c in palette)
        assert all(c.kelvin == 3500 for c in palette)

    def test_hued_colour_wraps_below_zero(self) -> None:
        """Hue 10 minus 45 wraps modulo 360 to 325."""
        color = HSBK(hue=10, saturation=1.0, brightness=1.0, kelvin=3500)
        palette = derive_effect_palette([color], None, None)
        assert palette is not None
        assert [round(c.hue) for c in palette] == [10, 55, 325]

    def test_white_uses_known_temperature_range(self) -> None:
        """A white with a known range gets whites at both endpoints."""
        color = HSBK(hue=0, saturation=0.0, brightness=0.5, kelvin=2500)
        palette = derive_effect_palette([color], 2500, 9000)
        assert palette is not None
        assert [c.kelvin for c in palette] == [2500, 2500, 9000]
        assert all(c.brightness == 0.5 for c in palette)
        assert all(c.saturation == 0.0 for c in palette)

    def test_white_falls_back_only_for_the_unknown_endpoint(self) -> None:
        """A known min with an unknown max falls back only for the max."""
        color = HSBK(hue=0, saturation=0.0, brightness=0.5, kelvin=2700)
        palette = derive_effect_palette([color], 2700, None)
        assert palette is not None
        assert [c.kelvin for c in palette] == [2700, 2700, 9000]

    def test_empty_colours_derive_nothing(self) -> None:
        """An empty colour sequence derives no palette."""
        assert derive_effect_palette([], None, None) is None

    def test_two_colours_one_wire_step_apart_derive_nothing(self) -> None:
        """Two colours a single uint16 brightness step apart are multi-colour."""
        a = HSBK(hue=0, saturation=1.0, brightness=0.5, kelvin=3500)
        b = HSBK(
            hue=0,
            saturation=1.0,
            brightness=(round(0xFFFF * 0.5) + 1) / 0xFFFF,
            kelvin=3500,
        )
        assert a != b
        assert derive_effect_palette([a, b], None, None) is None

    def test_two_colours_with_identical_wire_encoding_derive_a_palette(self) -> None:
        """Two colours that encode identically on the wire count as one colour."""
        a = HSBK(hue=0.0, saturation=1.0, brightness=1.0, kelvin=3500)
        b = HSBK(hue=0.0000001, saturation=1.0, brightness=1.0, kelvin=3500)
        assert a == b
        assert derive_effect_palette([a, b], None, None) is not None

    def test_tiny_saturation_counts_as_white(self) -> None:
        """A saturation that rounds to 0 on the wire is treated as white."""
        color = HSBK(hue=90, saturation=0.000001, brightness=0.4, kelvin=3500)
        palette = derive_effect_palette([color], None, None)
        assert palette is not None
        assert [c.kelvin for c in palette] == [3500, 1500, 9000]


class TestValidateEffectPalette:
    """Unit tests for validate_effect_palette(), shared by matrix and multizone."""

    def test_empty_palette_raises(self) -> None:
        """An empty palette raises the existing message."""
        with pytest.raises(ValueError, match="at least one color"):
            validate_effect_palette([])

    def test_oversized_palette_raises(self) -> None:
        """A 17-colour palette raises the existing message."""
        with pytest.raises(ValueError, match="at most 16 colors"):
            validate_effect_palette([Colors.RED] * 17)

    def test_sixteen_colours_accepted(self) -> None:
        """A 16-colour palette is accepted."""
        validate_effect_palette([Colors.RED] * 16)

    def test_matrix_effect_still_raises_for_empty_palette(self) -> None:
        """MatrixEffect's own construction still raises for an empty palette."""
        with pytest.raises(ValueError, match="at least one color"):
            MatrixEffect(effect_type=FirmwareEffect.MORPH, speed=3000, palette=[])


class TestSampleEffectPalette:
    """Unit tests for sample_effect_palette(), Morph's multi-colour rule (D-25).

    Every expected list below is written out by hand from pixel indices,
    never recomputed with the ``i * n // 16`` formula, so these tests pin
    the maintainer's rule rather than restate it.
    """

    def test_first_seen_order_is_preserved(self) -> None:
        """Up to 16 distinct colours are returned in first-seen order."""
        blue = HSBK(hue=240, saturation=1.0, brightness=0.5, kelvin=3500)
        red = HSBK(hue=0, saturation=1.0, brightness=0.5, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=0.5, kelvin=3500)
        assert sample_effect_palette([blue, red, blue, green, red]) == [
            blue,
            red,
            green,
        ]

    def test_colours_with_identical_wire_encoding_count_once(self) -> None:
        """Two colours that encode identically on the wire count as one."""
        a = HSBK(hue=0.0, saturation=1.0, brightness=0.5, kelvin=3500)
        b = HSBK(hue=0.0000001, saturation=1.0, brightness=0.5, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=0.5, kelvin=3500)
        assert a == b
        assert sample_effect_palette([a, b, green]) == [a, green]

    def test_exactly_sixteen_distinct_colours_returns_all_of_them(self) -> None:
        """16 distinct colours, each repeated, are returned with no sampling."""
        colors = [
            HSBK(hue=i * 22.5, saturation=1.0, brightness=0.5, kelvin=3500)
            for i in range(16)
        ]
        pixels = colors + colors
        assert sample_effect_palette(pixels) == colors

    def test_seventeen_distinct_colours_drops_the_last_pixel(self) -> None:
        """17 distinct colours over 17 pixels sample pixels 0 to 15."""
        colors = [
            HSBK(hue=i * 21.0, saturation=1.0, brightness=0.5, kelvin=3500)
            for i in range(17)
        ]
        assert sample_effect_palette(colors) == colors[:16]

    def test_forty_pixels_sample_the_literal_indices(self) -> None:
        """40 distinct pixels sample the maintainer's literal pixel indices."""
        colors = [
            HSBK(hue=i * 9.0, saturation=1.0, brightness=0.5, kelvin=3500)
            for i in range(40)
        ]
        indices = (0, 2, 5, 7, 10, 12, 15, 17, 20, 22, 25, 27, 30, 32, 35, 37)
        assert sample_effect_palette(colors) == [colors[i] for i in indices]

    def test_duplicate_sampled_pixel_is_removed_in_sample_order(self) -> None:
        """A sampled pixel equal to an earlier sample is removed, not re-added."""
        colors = [
            HSBK(hue=i * 11.0, saturation=1.0, brightness=0.5, kelvin=3500)
            for i in range(32)
        ]
        colors[2] = colors[0]
        result = sample_effect_palette(colors)
        expected_indices = [0, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30]
        assert result == [colors[i] for i in expected_indices]
        assert len(result) == 15

    def test_sampling_can_collapse_to_one_colour(self) -> None:
        """Even pixels sampled as red, though 17 hues show, give just red."""
        non_red_hues = [i * 22.0 + 10.0 for i in range(16)]
        colors: list[HSBK] = []
        for i in range(32):
            if i % 2 == 0:
                colors.append(Colors.RED)
            else:
                colors.append(
                    HSBK(
                        hue=non_red_hues[i // 2],
                        saturation=1.0,
                        brightness=0.5,
                        kelvin=3500,
                    )
                )
        assert sample_effect_palette(colors) == [Colors.RED]

    def test_empty_input_returns_empty_list(self) -> None:
        """An empty input returns an empty list."""
        assert sample_effect_palette([]) == []


class TestMorphDerivationMock:
    """Mock-based tests for the MORPH default-palette derivation in set_effect()."""

    async def test_derived_palette_passes_through_shared_validator(self) -> None:
        """The rebuilt effect's derived palette is validated the same way."""
        matrix = _matrix_light()
        color = HSBK(hue=10, saturation=1.0, brightness=1.0, kelvin=3500)
        matrix.get_all_tile_colors = AsyncMock(return_value=[[color]])

        with patch(
            "lifx.devices.matrix.validate_effect_palette",
            wraps=validate_effect_palette,
        ) as mock_validate:
            await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

        expected = derive_effect_palette([color], matrix.min_kelvin, matrix.max_kelvin)
        mock_validate.assert_called_once_with(expected)

    async def test_oversized_derivation_raises_before_send(self) -> None:
        """A patched oversized derivation raises before any packet is sent."""
        matrix = _matrix_light()
        matrix.get_all_tile_colors = AsyncMock(return_value=[[Colors.RED]])
        oversized = [Colors.RED] * 17

        with patch("lifx.devices.matrix.derive_effect_palette", return_value=oversized):
            with pytest.raises(ValueError, match="at most 16 colors"):
                await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

        matrix.connection.send_packet.assert_not_awaited()

    async def test_single_white_with_unknown_range_falls_back_to_constants(
        self,
    ) -> None:
        """Unknown device capabilities fall back to the 1500/9000 constants."""
        matrix = _matrix_light()
        matrix._capabilities = None
        white = HSBK(hue=0, saturation=0.0, brightness=0.7, kelvin=4000)
        matrix.get_all_tile_colors = AsyncMock(return_value=[[white]])

        await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

        packet = matrix.connection.send_packet.call_args[0][0]
        palette = [
            HSBK.from_protocol(c)
            for c in packet.settings.palette[: packet.settings.palette_count]
        ]
        assert packet.settings.palette_count == 3
        assert [color.kelvin for color in palette] == [4000, 1500, 9000]

    @pytest.mark.parametrize(
        "error", [LifxTimeoutError("timeout"), LifxProtocolError("malformed")]
    )
    async def test_failed_colour_read_raises_before_send(
        self, caplog, error: Exception
    ) -> None:
        """A timeout or malformed reply while reading colours raises, not sends."""
        matrix = _matrix_light()
        matrix.get_all_tile_colors = AsyncMock(side_effect=error)

        with caplog.at_level(logging.DEBUG):
            with pytest.raises(type(error)):
                await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

        palette_records = [r for r in caplog.records if "palette" in r.getMessage()]
        assert palette_records == []

        matrix.connection.send_packet.assert_not_awaited()

    async def test_negative_speed_raises_before_any_read(self) -> None:
        """Argument validation runs before the device's colours are read."""
        matrix = _matrix_light()
        matrix.get_all_tile_colors = AsyncMock(return_value=[[Colors.RED]])

        with pytest.raises(ValueError, match="must be positive"):
            await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=-1.0)

        matrix.get_all_tile_colors.assert_not_awaited()
        matrix.connection.send_packet.assert_not_awaited()

    async def test_flame_sky_and_explicit_palette_never_read_colours(self) -> None:
        """Only palette-less MORPH reads the device's colours."""
        cases = [
            (FirmwareEffect.FLAME, 3.0, {}, _GOLDEN_FLAME_NO_PALETTE),
            (
                FirmwareEffect.SKY,
                3.0,
                {"sky_type": TileEffectSkyType.CLOUDS},
                _GOLDEN_SKY_NO_PALETTE,
            ),
            (
                FirmwareEffect.MORPH,
                5.0,
                {"palette": [Colors.RED, Colors.BLUE]},
                _GOLDEN_MORPH_EXPLICIT,
            ),
        ]
        for effect_type, speed, kwargs, expected_hex in cases:
            matrix = _matrix_light()
            matrix.get_all_tile_colors = AsyncMock(return_value=[[Colors.RED]])

            await matrix.set_effect(effect_type=effect_type, speed=speed, **kwargs)

            matrix.get_all_tile_colors.assert_not_awaited()
            packet = matrix.connection.send_packet.call_args[0][0]
            assert packet.pack().hex() == expected_hex

    async def test_empty_colour_result_raises_before_send(self) -> None:
        """An empty tile-colour result ([] or [[]]) raises before any send."""
        for tile_colors in ([], [[]]):
            matrix = _matrix_light()
            matrix.get_all_tile_colors = AsyncMock(return_value=tile_colors)

            with pytest.raises(LifxProtocolError, match=matrix.serial):
                await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

            matrix.get_all_tile_colors.assert_awaited_once()
            matrix.connection.send_packet.assert_not_awaited()

    async def test_two_tile_device_samples_across_the_flattened_chain(self) -> None:
        """A two-tile device's sample spans both tiles when flattened."""
        matrix = _matrix_light()
        tile_a = [
            HSBK(hue=i * 5.0, saturation=1.0, brightness=0.5, kelvin=3500)
            for i in range(32)
        ]
        tile_b = [
            HSBK(hue=180 + i * 5.0, saturation=1.0, brightness=0.5, kelvin=3500)
            for i in range(32)
        ]
        matrix.get_all_tile_colors = AsyncMock(return_value=[tile_a, tile_b])
        flattened = tile_a + tile_b

        await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

        packet = matrix.connection.send_packet.call_args[0][0]
        assert packet.settings.palette_count in range(2, 17)
        assert packet.settings.palette_count == 16
        palette = [
            HSBK.from_protocol(c)
            for c in packet.settings.palette[: packet.settings.palette_count]
        ]
        assert palette == [flattened[i] for i in range(0, 64, 4)]

    async def test_three_tile_device_flattens_in_tile_order(self) -> None:
        """Flattening happens in tile order, with duplicates across tiles removed."""
        matrix = _matrix_light()
        a = HSBK(hue=0, saturation=1.0, brightness=0.5, kelvin=3500)
        b = HSBK(hue=90, saturation=1.0, brightness=0.5, kelvin=3500)
        c = HSBK(hue=180, saturation=1.0, brightness=0.5, kelvin=3500)
        d = HSBK(hue=270, saturation=1.0, brightness=0.5, kelvin=3500)
        matrix.get_all_tile_colors = AsyncMock(return_value=[[a, b], [b, c], [d]])

        await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

        packet = matrix.connection.send_packet.call_args[0][0]
        assert packet.settings.palette_count == 4
        palette = [
            HSBK.from_protocol(cc)
            for cc in packet.settings.palette[: packet.settings.palette_count]
        ]
        assert palette == [a, b, c, d]

    async def test_single_colour_never_calls_the_sampler(self) -> None:
        """A single colour uses derive_effect_palette() and never samples."""
        matrix = _matrix_light()
        color = HSBK(hue=10, saturation=1.0, brightness=1.0, kelvin=3500)
        matrix.get_all_tile_colors = AsyncMock(return_value=[[color]])

        with patch(
            "lifx.devices.matrix.sample_effect_palette",
            wraps=sample_effect_palette,
        ) as mock_sample:
            await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

        mock_sample.assert_not_called()
        packet = matrix.connection.send_packet.call_args[0][0]
        assert packet.settings.palette_count == 3

    async def test_multi_colour_device_calls_the_sampler_once(self) -> None:
        """A multi-colour device calls sample_effect_palette() once, flattened."""
        matrix = _matrix_light()
        matrix.get_all_tile_colors = AsyncMock(return_value=[[Colors.RED, Colors.BLUE]])

        with patch(
            "lifx.devices.matrix.sample_effect_palette",
            wraps=sample_effect_palette,
        ) as mock_sample:
            await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

        mock_sample.assert_called_once_with([Colors.RED, Colors.BLUE])

    async def test_oversized_sample_raises_before_send(self) -> None:
        """A patched 17-colour sample raises through the shared size rule."""
        matrix = _matrix_light()
        matrix.get_all_tile_colors = AsyncMock(return_value=[[Colors.RED, Colors.BLUE]])
        oversized = [Colors.RED] * 17

        with patch("lifx.devices.matrix.sample_effect_palette", return_value=oversized):
            with pytest.raises(ValueError, match="at most 16 colors"):
                await matrix.set_effect(effect_type=FirmwareEffect.MORPH, speed=3.0)

        matrix.connection.send_packet.assert_not_awaited()
