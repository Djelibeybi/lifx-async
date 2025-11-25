"""Tests for apply_theme methods on device classes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.api import DeviceGroup
from lifx.color import HSBK, Colors
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.theme import Theme


@pytest.mark.emulator
class TestLightApplyTheme:
    """Tests for Light.apply_theme method."""

    async def test_apply_theme_selects_random_color(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test that apply_theme selects a random color from theme."""
        light = emulator_devices[0]

        light.set_color = AsyncMock()
        light.set_power = AsyncMock()
        light.get_power = AsyncMock(return_value=False)
        theme = Theme([Colors.RED, Colors.BLUE, Colors.GREEN])

        await light.apply_theme(theme)

        # Verify set_color was called
        light.set_color.assert_called_once()
        args, kwargs = light.set_color.call_args
        assert isinstance(args[0], HSBK)
        assert kwargs.get("duration", 0.0) == 0.0

        # Verify set_power was not called
        light.set_power.assert_not_called()

        light.set_color.reset_mock()
        light.set_power.reset_mock()
        light.get_power.reset_mock()

    async def test_apply_theme_with_duration(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test apply_theme with transition duration."""
        light = emulator_devices[0]

        light.get_power = AsyncMock(return_value=True)
        theme = Theme([Colors.RED, Colors.BLUE])

        await light.apply_theme(theme, duration=1.5)

        light.set_color.assert_called_once()
        args, kwargs = light.set_color.call_args
        assert kwargs.get("duration", 0.0) == 1.5

        light.set_color.reset_mock()
        light.set_power.reset_mock()
        light.get_power.reset_mock()

    async def test_apply_theme_with_power_on(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test apply_theme with power_on=True."""
        light = emulator_devices[0]
        light.get_power = AsyncMock(return_value=False)

        theme = Theme([Colors.RED])

        await light.apply_theme(theme, power_on=True)

        light.set_color.assert_called_once()
        light.set_power.assert_called_once()
        # Check that set_power was called with True (and default duration)
        args, kwargs = light.set_power.call_args
        assert args[0] is True

        light.set_color.reset_mock()
        light.set_power.reset_mock()
        light.get_power.reset_mock()

    async def test_apply_theme_color_from_theme(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test that apply_theme receives a color from the theme."""
        light = emulator_devices[0]

        original_color = HSBK(hue=45, saturation=0.8, brightness=0.9, kelvin=4000)
        theme = Theme([original_color])

        await light.apply_theme(theme)

        # Get the color that was passed to set_color
        args, _ = light.set_color.call_args
        applied_color = args[0]

        # Should have same values as the color in the theme
        assert applied_color.hue == original_color.hue
        assert applied_color.saturation == original_color.saturation
        assert applied_color.brightness == original_color.brightness
        assert applied_color.kelvin == original_color.kelvin

        light.set_color.reset_mock()
        light.set_power.reset_mock()
        light.get_power.reset_mock()


class TestMultiZoneLightApplyTheme:
    """Tests for MultiZoneLight.apply_theme method."""

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

        # Create mock tile info
        tile_info = MagicMock()
        tile_info.width = 8
        tile_info.height = 8
        tile_info.tile_index = 0

        # Mock methods
        matrix_light.get_device_chain = AsyncMock(return_value=[tile_info])

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

        tile_info = MagicMock()
        tile_info.width = 8
        tile_info.height = 8
        tile_info.tile_index = 0

        matrix_light.get_device_chain = AsyncMock(return_value=[tile_info])

        await matrix_light.apply_theme(theme, duration=3.0)

        args, kwargs = matrix_light.set_matrix_colors.call_args
        # Duration should be converted to milliseconds
        assert kwargs.get("duration", 0) == 3000

    async def test_apply_theme_with_power_on(self, matrix_light: MatrixLight) -> None:
        """Test apply_theme with power_on=True."""
        theme = Theme([Colors.RED])

        tile_info = MagicMock()
        tile_info.width = 8
        tile_info.height = 8
        tile_info.tile_index = 0

        matrix_light.get_device_chain = AsyncMock(return_value=[tile_info])

        await matrix_light.apply_theme(theme, power_on=True)

        matrix_light.set_matrix_colors.assert_called_once()
        matrix_light.set_power.assert_called_once()
        # Check that set_power was called with True (and default duration)
        args, kwargs = matrix_light.set_power.call_args
        assert args[0] is True

    async def test_apply_theme_multiple_tiles(self, matrix_light: MatrixLight) -> None:
        """Test apply_theme with multiple tiles in chain."""
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])

        # Create multiple mock tile infos
        tile_info1 = MagicMock()
        tile_info1.width = 8
        tile_info1.height = 8
        tile_info1.tile_index = 0

        tile_info2 = MagicMock()
        tile_info2.width = 8
        tile_info2.height = 8
        tile_info2.tile_index = 1

        matrix_light.get_device_chain = AsyncMock(return_value=[tile_info1, tile_info2])

        await matrix_light.apply_theme(theme)

        # Should call set_matrix_colors twice (once per tile)
        assert matrix_light.set_matrix_colors.call_count == 2

        # Check that tile indices are correct
        calls = matrix_light.set_matrix_colors.call_args_list
        assert calls[0][0][0] == 0  # First call uses tile index 0
        assert calls[1][0][0] == 1  # Second call uses tile index 1
