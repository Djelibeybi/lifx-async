"""Tests for apply_theme methods on device classes."""

from __future__ import annotations

import random
from unittest.mock import AsyncMock, patch

import pytest

from lifx.animation.orientation import Orientation, build_orientation_lut
from lifx.api import DeviceGroup
from lifx.color import HSBK, Colors
from lifx.devices.ceiling import CeilingLight
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.theme import MatrixGenerator, Theme
from tests.test_theme.conftest import make_tile


@pytest.mark.emulator
class TestLightApplyTheme:
    """Tests for Light.apply_theme method."""

    async def test_apply_theme_selects_random_color(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test that apply_theme selects a random color from theme."""
        light = emulator_devices[0]
        theme = Theme([Colors.RED, Colors.BLUE, Colors.GREEN])

        with (
            patch.object(light, "set_color", new_callable=AsyncMock) as mock_set_color,
            patch.object(light, "set_power", new_callable=AsyncMock) as mock_set_power,
            patch.object(
                light, "get_power", new_callable=AsyncMock, return_value=False
            ),
        ):
            await light.apply_theme(theme)

            # Verify set_color was called
            mock_set_color.assert_called_once()
            args, kwargs = mock_set_color.call_args
            assert isinstance(args[0], HSBK)
            assert kwargs.get("duration", 0.0) == 0.0

            # Verify set_power was not called
            mock_set_power.assert_not_called()

    async def test_apply_theme_with_duration(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test apply_theme with transition duration."""
        light = emulator_devices[0]
        theme = Theme([Colors.RED, Colors.BLUE])

        with (
            patch.object(light, "set_color", new_callable=AsyncMock) as mock_set_color,
            patch.object(light, "set_power", new_callable=AsyncMock),
            patch.object(light, "get_power", new_callable=AsyncMock, return_value=True),
        ):
            await light.apply_theme(theme, duration=1.5)

            mock_set_color.assert_called_once()
            args, kwargs = mock_set_color.call_args
            assert kwargs.get("duration", 0.0) == 1.5

    async def test_apply_theme_with_power_on(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test apply_theme with power_on=True."""
        light = emulator_devices[0]
        theme = Theme([Colors.RED])

        with (
            patch.object(light, "set_color", new_callable=AsyncMock) as mock_set_color,
            patch.object(light, "set_power", new_callable=AsyncMock) as mock_set_power,
            patch.object(
                light, "get_power", new_callable=AsyncMock, return_value=False
            ),
        ):
            await light.apply_theme(theme, power_on=True)

            mock_set_color.assert_called_once()
            mock_set_power.assert_called_once()
            # Check that set_power was called with True (and default duration)
            args, kwargs = mock_set_power.call_args
            assert args[0] is True

    async def test_apply_theme_color_from_theme(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test that apply_theme receives a color from the theme."""
        light = emulator_devices[0]
        original_color = HSBK(hue=45, saturation=0.8, brightness=0.9, kelvin=4000)
        theme = Theme([original_color])

        with (
            patch.object(light, "set_color", new_callable=AsyncMock) as mock_set_color,
            patch.object(light, "set_power", new_callable=AsyncMock),
            patch.object(
                light, "get_power", new_callable=AsyncMock, return_value=False
            ),
        ):
            await light.apply_theme(theme)

            # Get the color that was passed to set_color
            args, _ = mock_set_color.call_args
            applied_color = args[0]

            # Should have same values as the color in the theme
            assert applied_color.hue == original_color.hue
            assert applied_color.saturation == original_color.saturation
            assert applied_color.brightness == original_color.brightness
            assert applied_color.kelvin == original_color.kelvin


class TestMultiZoneLightApplyTheme:
    """Tests for MultiZoneLight.apply_theme method."""

    async def test_apply_theme_chunks_past_82_zones(self, mock_device_factory) -> None:
        """Test a strip longer than one extended packet is chunked, not rejected."""
        light = mock_device_factory(MultiZoneLight, product=32)
        light.set_extended_color_zones = AsyncMock()
        light.set_power = AsyncMock()
        light.get_power = AsyncMock(return_value=True)
        light.get_zone_count = AsyncMock(return_value=128)

        await light.apply_theme(Theme([Colors.RED, Colors.GREEN, Colors.BLUE]))

        calls = light.set_extended_color_zones.await_args_list
        assert [call.args[0] for call in calls] == [0, 82]
        assert [len(call.args[1]) for call in calls] == [82, 46]

    async def test_apply_theme_falls_back_to_legacy_zones(
        self, mock_device_factory
    ) -> None:
        """Test firmware without extended multizone uses SetColorZones."""
        light = mock_device_factory(MultiZoneLight, product=31)
        light.set_color_zones = AsyncMock()
        light.set_extended_color_zones = AsyncMock()
        light.set_power = AsyncMock()
        light.get_power = AsyncMock(return_value=True)
        light.get_zone_count = AsyncMock(return_value=16)

        await light.apply_theme(Theme([Colors.RED, Colors.GREEN, Colors.BLUE]))

        assert light.set_color_zones.await_count > 0
        light.set_extended_color_zones.assert_not_awaited()

    def test_apply_theme_basic(self, multizone_light: MultiZoneLight) -> None:
        """Test creating a multizone light for apply_theme tests."""
        assert multizone_light.serial == "d073d5010203"

    async def test_apply_theme_distributes_colors(
        self, multizone_light: MultiZoneLight
    ) -> None:
        """Test that apply_theme distributes colors across zones."""
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])
        multizone_light.get_zone_count = AsyncMock(return_value=6)

        await multizone_light.apply_theme(theme)

        # Verify set_extended_color_zones was called
        multizone_light.set_extended_color_zones.assert_called_once()
        args, kwargs = multizone_light.set_extended_color_zones.call_args

        # First arg should be start index (0)
        assert args[0] == 0

        # Second arg should be colors list
        colors = args[1]
        assert len(colors) == 6
        assert all(isinstance(c, HSBK) for c in colors)

        # Duration should be 0 by default
        assert kwargs.get("duration", 0) == 0

        # set_power should not be called
        multizone_light.set_power.assert_not_called()

    async def test_apply_theme_with_duration(
        self, multizone_light: MultiZoneLight
    ) -> None:
        """Test apply_theme with transition duration."""
        multizone_light.get_power = AsyncMock(return_value=True)
        multizone_light.get_zone_count = AsyncMock(return_value=4)
        theme = Theme([Colors.RED, Colors.BLUE])

        await multizone_light.apply_theme(theme, duration=2.0)

        args, kwargs = multizone_light.set_extended_color_zones.call_args
        assert kwargs.get("duration", 0) == 2.0

    async def test_apply_theme_with_power_on(
        self, multizone_light: MultiZoneLight
    ) -> None:
        """Test apply_theme with power_on=True."""
        multizone_light.get_zone_count = AsyncMock(return_value=4)
        theme = Theme([Colors.RED])

        await multizone_light.apply_theme(theme, power_on=True)

        multizone_light.set_extended_color_zones.assert_called_once()
        multizone_light.set_power.assert_called_once()
        # Check that set_power was called with True (and default duration)
        args, kwargs = multizone_light.set_power.call_args
        assert args[0] is True

    async def test_apply_theme_color_distribution(
        self, multizone_light: MultiZoneLight
    ) -> None:
        """Test that colors are distributed evenly across zones."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)
        theme = Theme([red, green, blue])

        multizone_light.get_zone_count = AsyncMock(return_value=9)

        await multizone_light.apply_theme(theme)

        args, _ = multizone_light.set_extended_color_zones.call_args
        colors = args[1]

        # With 3 colors and 9 zones, each color should appear 3 times
        assert len(colors) == 9

        # Check that we got a distribution of the theme colors
        hues = [c.hue for c in colors]
        assert 0 in hues or any(abs(h - 0) < 1 for h in hues)  # Red or similar
        assert 120 in hues or any(abs(h - 120) < 1 for h in hues)  # Green or similar
        assert 240 in hues or any(abs(h - 240) < 1 for h in hues)  # Blue or similar


class TestMatrixLightApplyTheme:
    """Tests for MatrixLight.apply_theme method."""

    def test_apply_theme_basic(self, matrix_light: MatrixLight) -> None:
        """Test creating a tile device for apply_theme tests."""
        assert matrix_light.serial == "d073d5010203"

    async def test_apply_theme_uses_canvas(self, matrix_light: MatrixLight) -> None:
        """Test that apply_theme uses Canvas for interpolation."""
        theme = Theme([Colors.RED, Colors.BLUE])

        # Mock methods
        matrix_light.get_device_chain = AsyncMock(return_value=[make_tile(0)])

        await matrix_light.apply_theme(theme)

        # Verify set_matrix_colors was called
        matrix_light.set_matrix_colors.assert_called_once()
        args, kwargs = matrix_light.set_matrix_colors.call_args

        # First arg should be tile index (0)
        assert args[0] == 0

        # Second arg should be 1D list of colors (8x8=64)
        colors = args[1]
        assert len(colors) == 64
        assert all(isinstance(c, HSBK) for c in colors)

    async def test_apply_theme_with_no_tiles(self, matrix_light: MatrixLight) -> None:
        """Test apply_theme when no tiles are available."""
        theme = Theme([Colors.RED])
        matrix_light.get_device_chain = AsyncMock(return_value=[])

        await matrix_light.apply_theme(theme)

        # Should not call set_matrix_colors
        matrix_light.set_matrix_colors.assert_not_called()
        matrix_light.set_power.assert_not_called()

    async def test_apply_theme_with_duration(self, matrix_light: MatrixLight) -> None:
        """Test apply_theme with transition duration."""
        theme = Theme([Colors.RED, Colors.BLUE])

        matrix_light.get_device_chain = AsyncMock(return_value=[make_tile(0)])

        await matrix_light.apply_theme(theme, duration=3.0)

        args, kwargs = matrix_light.set_matrix_colors.call_args
        # Duration should be converted to milliseconds
        assert kwargs.get("duration", 0) == 3000

    async def test_apply_theme_with_power_on(self, matrix_light: MatrixLight) -> None:
        """Test apply_theme with power_on=True."""
        theme = Theme([Colors.RED])

        matrix_light.get_device_chain = AsyncMock(return_value=[make_tile(0)])

        await matrix_light.apply_theme(theme, power_on=True)

        matrix_light.set_matrix_colors.assert_called_once()
        matrix_light.set_power.assert_called_once()
        # Check that set_power was called with True (and default duration)
        args, kwargs = matrix_light.set_power.call_args
        assert args[0] is True

    async def test_apply_theme_multiple_tiles(self, matrix_light: MatrixLight) -> None:
        """Test apply_theme with multiple tiles in chain."""
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        matrix_light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, user_x=0.0), make_tile(1, user_x=1.0)]
        )

        await matrix_light.apply_theme(theme)

        # Should call set_matrix_colors twice (once per tile)
        assert matrix_light.set_matrix_colors.call_count == 2

        # Check that tile indices are correct
        calls = matrix_light.set_matrix_colors.call_args_list
        assert calls[0][0][0] == 0  # First call uses tile index 0
        assert calls[1][0][0] == 1  # Second call uses tile index 1

    async def test_apply_theme_candle_geometry(self, matrix_light: MatrixLight) -> None:
        """Test a 5x6 Candle gets 30 colours, not 64.

        The Candle is the counter-example to the old hardcoded 8x8 assumption.
        """
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        matrix_light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=5, height=6)]
        )

        await matrix_light.apply_theme(theme)

        colors = matrix_light.set_matrix_colors.call_args[0][1]
        assert len(colors) == 30
        assert all(isinstance(c, HSBK) for c in colors)

    async def test_apply_theme_chain_tiles_get_distinct_colours(
        self, tile_light: MatrixLight
    ) -> None:
        """Test a 5-tile chain renders a different slice of canvas per tile.

        With user_x treated as pixels, every tile landed within a few pixels of
        the origin and read back nearly the same colours. Set inequality alone
        cannot see that: the buggy origins (0, 1, 2, 3, 4) also produced five
        distinct windows, just overlapping ones. So this pins apply_theme to the
        colours MatrixGenerator.from_tiles() produces — from_tiles is separately
        pinned to 8-pixel spacing by
        TestMatrixThemeGeometry.test_chain_tile_origins_are_eight_pixels_apart —
        and additionally requires adjacent tiles to share almost nothing.
        """
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])
        tiles = [make_tile(i, user_x=float(i)) for i in range(5)]

        random.seed(20260731)
        expected = MatrixGenerator.from_tiles(tiles).get_theme_colors(theme)

        random.seed(20260731)
        tile_light.get_device_chain = AsyncMock(return_value=tiles)
        await tile_light.apply_theme(theme)

        assert tile_light.set_matrix_colors.call_count == 5

        sent = [call[0][1] for call in tile_light.set_matrix_colors.call_args_list]
        assert sent == expected

        # Tiles 8 pixels apart read disjoint canvas windows. Under the old
        # one-pixel-apart origins adjacent tiles shared most of their colours.
        colour_sets = [
            {(c.hue, c.saturation, c.brightness, c.kelvin) for c in colors}
            for colors in sent
        ]
        for first, second in zip(colour_sets, colour_sets[1:], strict=False):
            overlap = len(first & second) / len(first | second)
            assert overlap < 0.25

    async def test_apply_theme_remaps_a_rotated_tile(
        self, tile_light: MatrixLight
    ) -> None:
        """Test a physically rotated Tile gets its colours remapped.

        The canvas renders in row-major screen order. FrameBuffer applies an
        orientation LUT for the animation path; apply_theme must do the same or
        a rotated panel renders its slice of the theme sideways.
        """
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])
        tiles = [make_tile(0, accel=(1, 0, 0))]  # RotatedRight

        assert tiles[0].nearest_orientation == "RotatedRight"

        random.seed(20260801)
        expected_canvas = MatrixGenerator.from_tiles(tiles).get_theme_colors(theme)[0]
        lut = build_orientation_lut(8, 8, Orientation.ROTATED_90)

        random.seed(20260801)
        tile_light.get_device_chain = AsyncMock(return_value=tiles)
        await tile_light.apply_theme(theme)

        sent = tile_light.set_matrix_colors.call_args[0][1]
        assert sent == [expected_canvas[src_idx] for src_idx in lut]
        assert sent != expected_canvas

    async def test_apply_theme_leaves_an_upright_tile_alone(
        self, tile_light: MatrixLight
    ) -> None:
        """Test an upright Tile is sent the canvas order unchanged."""
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])
        tiles = [make_tile(0)]

        random.seed(20260801)
        expected = MatrixGenerator.from_tiles(tiles).get_theme_colors(theme)[0]

        random.seed(20260801)
        tile_light.get_device_chain = AsyncMock(return_value=tiles)
        await tile_light.apply_theme(theme)

        assert tile_light.set_matrix_colors.call_args[0][1] == expected

    async def test_apply_theme_ignores_orientation_without_a_chain(
        self, ceiling_light: CeilingLight
    ) -> None:
        """Test a fixed device is never remapped, whatever its accel fields say.

        Only the LIFX Tile has an accelerometer. Every other matrix device is
        mounted in one position and returns whatever its firmware leaves in the
        accel fields; reading that as a rotation would scramble the output.
        """
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])
        # accel reads as UpsideDown, which would reverse all 128 colours
        tiles = [make_tile(0, width=16, height=8, accel=(0, 1, 0))]

        assert tiles[0].nearest_orientation == "UpsideDown"

        random.seed(20260801)
        expected = MatrixGenerator.from_tiles(tiles).get_theme_colors(theme)[0]

        random.seed(20260801)
        ceiling_light.get_device_chain = AsyncMock(return_value=tiles)
        await ceiling_light.apply_theme(theme)

        assert ceiling_light.set_matrix_colors.call_args[0][1] == expected

    async def test_apply_theme_ceiling_uses_reported_geometry(
        self, ceiling_light: CeilingLight
    ) -> None:
        """Test CeilingLight inherits apply_theme and keeps its own geometry.

        A Ceiling reports a single 16x8 tile covering both the downlight pixels
        and the uplight zone, so the colour list must match the reported
        width * height exactly.
        """
        theme = Theme([Colors.RED, Colors.BLUE])

        ceiling_light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=16, height=8)]
        )

        await ceiling_light.apply_theme(theme)

        colors = ceiling_light.set_matrix_colors.call_args[0][1]
        assert len(colors) == 128


class TestMatrixThemeGeometry:
    """Tests for how tile positions map onto the theme canvas."""

    def test_chain_tile_origins_are_eight_pixels_apart(self) -> None:
        """Test user_x 0.0..4.0 produces origins 8 pixels apart."""
        tiles = [make_tile(i, user_x=float(i)) for i in range(5)]

        generator = MatrixGenerator.from_tiles(tiles)

        assert generator.coords_and_sizes == [
            ((0, 0), (8, 8)),
            ((8, 0), (8, 8)),
            ((16, 0), (8, 8)),
            ((24, 0), (8, 8)),
            ((32, 0), (8, 8)),
        ]

    def test_mixed_geometry_chain_keeps_the_same_scale(self) -> None:
        """Test a mixed-geometry chain still advances 8 pixels per unit.

        Real chains ship as one product type, but the protocol reports width
        and height per tile, and photons lays parts out with
        ``user_x += part.width / 8`` — so the scale is the constant 8 and only
        the region size varies per tile.
        """
        tiles = [
            make_tile(0, user_x=0.0),
            make_tile(1, user_x=1.0, width=5, height=6),
            make_tile(2, user_x=1.625),
        ]

        generator = MatrixGenerator.from_tiles(tiles)

        assert generator.coords_and_sizes == [
            ((0, 0), (8, 8)),
            ((8, 0), (5, 6)),
            ((13, 0), (8, 8)),
        ]

    def test_vertical_positions_are_inverted(self) -> None:
        """Test a tile higher in the chain sits higher on the canvas."""
        tiles = [make_tile(0, user_y=0.0), make_tile(1, user_y=1.0)]

        generator = MatrixGenerator.from_tiles(tiles)

        assert generator.coords_and_sizes == [
            ((0, 0), (8, 8)),
            ((0, -8), (8, 8)),
        ]

    def test_generated_tiles_match_reported_geometry(self) -> None:
        """Test each rendered tile holds width * height colours."""
        random.seed(20260731)
        tiles = [make_tile(0), make_tile(1, user_x=1.0, width=5, height=6)]

        rendered = MatrixGenerator.from_tiles(tiles).get_theme_colors(
            Theme([Colors.RED, Colors.GREEN])
        )

        assert [len(colors) for colors in rendered] == [64, 30]
