"""Tests for CeilingLight device class."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.devices.ceiling import CeilingLight
from lifx.products import get_ceiling_layout


class TestCeilingLightComponentDetection:
    """Tests for component detection and configuration."""

    def test_create_ceiling_light_176(self) -> None:
        """Test creating Ceiling light (product 176 - US)."""
        ceiling = CeilingLight(
            serial="d073d5010203",
            ip="192.168.1.100",
        )
        assert ceiling.serial == "d073d5010203"
        assert ceiling.ip == "192.168.1.100"

        # Verify component layout for 8x8 ceiling (product 176)
        layout = get_ceiling_layout(176)
        assert layout is not None
        assert layout.uplight_zone == 63
        assert layout.downlight_zones == slice(0, 63)

    def test_create_ceiling_light_177(self) -> None:
        """Test creating Ceiling light (product 177 - Intl)."""
        ceiling = CeilingLight(
            serial="d073d5010204",
            ip="192.168.1.101",
        )
        assert ceiling.serial == "d073d5010204"
        assert ceiling.ip == "192.168.1.101"

        # Verify component layout for 8x8 ceiling (product 177)
        layout = get_ceiling_layout(177)
        assert layout is not None
        assert layout.uplight_zone == 63
        assert layout.downlight_zones == slice(0, 63)

    def test_create_ceiling_light_201(self) -> None:
        """Test creating Ceiling Capsule (product 201 - US)."""
        ceiling = CeilingLight(
            serial="d073d5010205",
            ip="192.168.1.102",
        )
        assert ceiling.serial == "d073d5010205"
        assert ceiling.ip == "192.168.1.102"

        # Verify component layout for 16x8 ceiling (product 201)
        layout = get_ceiling_layout(201)
        assert layout is not None
        assert layout.uplight_zone == 127
        assert layout.downlight_zones == slice(0, 127)

    def test_create_ceiling_light_202(self) -> None:
        """Test creating Ceiling Capsule (product 202 - Intl)."""
        ceiling = CeilingLight(
            serial="d073d5010206",
            ip="192.168.1.103",
        )
        assert ceiling.serial == "d073d5010206"
        assert ceiling.ip == "192.168.1.103"

        # Verify component layout for 16x8 ceiling (product 202)
        layout = get_ceiling_layout(202)
        assert layout is not None
        assert layout.uplight_zone == 127
        assert layout.downlight_zones == slice(0, 127)

    def test_uplight_zone_property(self) -> None:
        """Test uplight_zone property returns correct zone index."""
        ceiling_176 = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        # Mock version property
        ceiling_176._version = MagicMock()
        ceiling_176._version.product = 176

        ceiling_201 = CeilingLight(serial="d073d5010205", ip="192.168.1.102")
        ceiling_201._version = MagicMock()
        ceiling_201._version.product = 201

        assert ceiling_176.uplight_zone == 63
        assert ceiling_201.uplight_zone == 127

    def test_downlight_zones_property(self) -> None:
        """Test downlight_zones property returns correct slice."""
        ceiling_176 = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling_176._version = MagicMock()
        ceiling_176._version.product = 176

        ceiling_201 = CeilingLight(serial="d073d5010205", ip="192.168.1.102")
        ceiling_201._version = MagicMock()
        ceiling_201._version.product = 201

        assert ceiling_176.downlight_zones == slice(0, 63)
        assert ceiling_201.downlight_zones == slice(0, 127)


class TestCeilingLightGetMethods:
    """Tests for getting component colors."""

    @pytest.fixture
    def ceiling_176(self) -> CeilingLight:
        """Create a Ceiling product 176 (8x8) instance with mocked connection."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling.connection = AsyncMock()
        # Mock version for product detection
        ceiling._version = MagicMock()
        ceiling._version.product = 176
        return ceiling

    async def test_get_uplight_color(self, ceiling_176: CeilingLight) -> None:
        """Test getting uplight component color."""
        # Mock get_all_tile_colors to return list[list[HSBK]] (tiles -> colors per tile)
        expected_uplight = HSBK(hue=30, saturation=0.2, brightness=0.3, kelvin=2700)
        white = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500)
        downlight_colors = [white] * 63
        tile_colors = downlight_colors + [expected_uplight]  # 64 colors for 8x8 tile
        all_colors = [tile_colors]  # Wrap in list to represent single tile

        ceiling_176.get_all_tile_colors = AsyncMock(return_value=all_colors)

        # Get uplight color
        result = await ceiling_176.get_uplight_color()

        assert result == expected_uplight
        ceiling_176.get_all_tile_colors.assert_called_once()

    async def test_get_downlight_colors(self, ceiling_176: CeilingLight) -> None:
        """Test getting downlight component colors."""
        # Mock get_all_tile_colors to return list[list[HSBK]] (tiles -> colors per tile)
        expected_downlight = [
            HSBK(hue=i * 5, saturation=1.0, brightness=1.0, kelvin=3500)
            for i in range(63)
        ]
        uplight_color = HSBK(hue=200, saturation=0.5, brightness=0.5, kelvin=2700)
        tile_colors = expected_downlight + [uplight_color]  # 64 colors for 8x8 tile
        all_colors = [tile_colors]  # Wrap in list to represent single tile

        ceiling_176.get_all_tile_colors = AsyncMock(return_value=all_colors)

        # Get downlight colors
        result = await ceiling_176.get_downlight_colors()

        assert len(result) == 63
        assert result == expected_downlight
        ceiling_176.get_all_tile_colors.assert_called_once()


class TestCeilingLightSetMethods:
    """Tests for setting component colors."""

    @pytest.fixture
    def ceiling_176(self) -> CeilingLight:
        """Create a Ceiling product 176 (8x8) instance with mocked connection."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling.connection = AsyncMock()
        ceiling.set_matrix_colors = AsyncMock()
        ceiling._save_state_to_file = MagicMock()

        # Mock get_all_tile_colors to return current state (64 zones for 8x8 tile)
        # Default to all white zones
        white = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500)
        default_tile_colors = [white] * 64
        ceiling.get_all_tile_colors = AsyncMock(return_value=[default_tile_colors])

        # Mock version for product detection
        ceiling._version = MagicMock()
        ceiling._version.product = 176
        return ceiling

    async def test_set_uplight_color(self, ceiling_176: CeilingLight) -> None:
        """Test setting uplight component color."""
        color = HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)

        await ceiling_176.set_uplight_color(color, duration=1.0)

        # Verify set_matrix_colors was called correctly
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        assert call_args.args[0] == 0  # tile_index
        assert len(call_args.args[1]) == 64  # colors list (all zones)
        assert call_args.args[1][63] == color  # uplight zone (last zone)
        assert call_args.kwargs.get("duration") == 1000  # duration in milliseconds

        # Verify stored state was updated
        assert ceiling_176._stored_uplight_state == color

    async def test_set_uplight_color_zero_brightness_raises(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test setting uplight with brightness=0 raises ValueError."""
        invalid_color = HSBK(hue=0, saturation=0, brightness=0.0, kelvin=3500)

        with pytest.raises(ValueError, match="brightness"):
            await ceiling_176.set_uplight_color(invalid_color)

    async def test_set_downlight_colors_single_hsbk(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test setting downlight to single color."""
        color = HSBK(hue=0, saturation=0, brightness=1.0, kelvin=3500)

        await ceiling_176.set_downlight_colors(color, duration=0.5)

        # Verify set_matrix_colors was called correctly
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        assert call_args.args[0] == 0  # tile_index
        assert len(call_args.args[1]) == 64  # colors list (all zones)
        # Check downlight zones (0-62) are set to the color
        assert all(call_args.args[1][i] == color for i in range(63))
        assert call_args.kwargs.get("duration") == 500  # duration in milliseconds

        # Verify stored state was updated
        assert len(ceiling_176._stored_downlight_state) == 63
        assert all(c == color for c in ceiling_176._stored_downlight_state)

    async def test_set_downlight_colors_list_hsbk(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test setting downlight to list of colors."""
        # Create colors with hue values 0-310 (step of 5) to stay under 360
        colors = [
            HSBK(hue=i * 5, saturation=1.0, brightness=1.0, kelvin=3500)
            for i in range(63)
        ]

        await ceiling_176.set_downlight_colors(colors)

        # Verify set_matrix_colors was called correctly
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        assert call_args.args[0] == 0  # tile_index
        assert len(call_args.args[1]) == 64  # colors list (all zones)
        # Check downlight zones (0-62) are set to the provided colors
        assert call_args.args[1][0:63] == colors

        # Verify stored state was updated
        assert ceiling_176._stored_downlight_state == colors

    async def test_set_downlight_colors_invalid_length_raises(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test setting downlight with wrong number of colors raises ValueError."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        invalid_colors = [red] * 10  # Wrong number

        with pytest.raises(ValueError, match="Expected 63 colors"):
            await ceiling_176.set_downlight_colors(invalid_colors)

    async def test_set_downlight_colors_all_zero_brightness_raises(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test setting downlight with all brightness=0 raises ValueError."""
        invalid_colors = [HSBK(hue=0, saturation=0, brightness=0.0, kelvin=3500)] * 63

        with pytest.raises(ValueError, match="brightness"):
            await ceiling_176.set_downlight_colors(invalid_colors)

    async def test_set_downlight_colors_some_zero_brightness_allowed(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test setting downlight with some brightness=0 is allowed."""
        # Some zones can be brightness=0, just not all
        colors = [
            HSBK(hue=0, saturation=0, brightness=0.0 if i < 10 else 1.0, kelvin=3500)
            for i in range(63)
        ]

        await ceiling_176.set_downlight_colors(colors)

        # Should succeed - verify it was called
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        assert call_args.args[0] == 0  # tile_index
        assert len(call_args.args[1]) == 64  # colors list (all zones)


class TestCeilingLightTurnOnOff:
    """Tests for turning components on and off."""

    @pytest.fixture
    def ceiling_176(self) -> CeilingLight:
        """Create a Ceiling product 176 (8x8) instance with mocked connection."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling.connection = AsyncMock()
        ceiling.set_matrix_colors = AsyncMock()
        ceiling._save_state_to_file = MagicMock()

        # Mock get_all_tile_colors to return current state (64 zones for 8x8 tile)
        # Default to all white zones
        white = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500)
        default_tile_colors = [white] * 64
        ceiling.get_all_tile_colors = AsyncMock(return_value=[default_tile_colors])

        # Mock version for product detection
        ceiling._version = MagicMock()
        ceiling._version.product = 176
        return ceiling

    async def test_turn_uplight_on_with_color(self, ceiling_176: CeilingLight) -> None:
        """Test turning uplight on with explicit color."""
        color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)

        await ceiling_176.turn_uplight_on(color)

        # Verify set_matrix_colors was called
        ceiling_176.set_matrix_colors.assert_called_once()
        # Verify stored state was updated
        assert ceiling_176._stored_uplight_state == color

    async def test_turn_uplight_on_without_color_uses_stored(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turning uplight on without color uses stored state."""
        stored_color = HSBK(hue=60, saturation=0.5, brightness=0.7, kelvin=4000)
        ceiling_176._stored_uplight_state = stored_color

        await ceiling_176.turn_uplight_on()

        # Should use stored state
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        assert call_args.args[0] == 0  # tile_index
        assert call_args.args[1][63] == stored_color  # uplight zone

    async def test_turn_uplight_on_infers_from_downlight(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turning uplight on infers brightness from downlight average."""
        # No stored state
        ceiling_176._stored_uplight_state = None

        # Mock downlight colors with average brightness 0.6
        downlight_colors = [
            HSBK(hue=0, saturation=0, brightness=0.6, kelvin=3500) for _ in range(63)
        ]
        uplight_color = HSBK(
            hue=30, saturation=0.2, brightness=0.0, kelvin=2700
        )  # Currently off
        tile_colors = downlight_colors + [uplight_color]  # 64 colors for 8x8 tile
        ceiling_176.get_all_tile_colors = AsyncMock(return_value=[tile_colors])

        await ceiling_176.turn_uplight_on()

        # Should infer brightness (0.6) from downlight
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        result_color = call_args.args[1][63]  # uplight zone
        assert result_color.brightness == pytest.approx(0.6, abs=0.01)
        assert result_color.hue == pytest.approx(30, abs=1)
        assert result_color.kelvin == 2700

    async def test_turn_uplight_on_uses_default_brightness(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turn uplight on uses default brightness when no stored state."""
        # No stored state
        ceiling_176._stored_uplight_state = None

        # Mock current uplight color (off) and downlight colors (all off too)
        uplight_color = HSBK(hue=30, saturation=0.2, brightness=0.0, kelvin=2700)
        downlight_colors = [
            HSBK(hue=0, saturation=0, brightness=0.0, kelvin=3500) for _ in range(63)
        ]
        tile_colors = downlight_colors + [uplight_color]  # 64 colors for 8x8 tile
        ceiling_176.get_all_tile_colors = AsyncMock(return_value=[tile_colors])

        await ceiling_176.turn_uplight_on()

        # Should use default brightness (0.8)
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        result_color = call_args.args[1][63]  # uplight zone
        assert result_color.brightness == pytest.approx(0.8, abs=0.01)

    async def test_turn_uplight_off_stores_current_color(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turning uplight off stores current color."""
        current_uplight = HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)
        white = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500)
        downlight_colors = [white] * 63
        tile_colors = downlight_colors + [current_uplight]  # 64 colors for 8x8 tile
        ceiling_176.get_all_tile_colors = AsyncMock(return_value=[tile_colors])

        await ceiling_176.turn_uplight_off()

        # Should store current color (with brightness preserved)
        assert ceiling_176._stored_uplight_state is not None
        assert ceiling_176._stored_uplight_state.brightness == pytest.approx(
            0.5, abs=0.01
        )

        # Should set device to brightness=0
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        result_color = call_args.args[1][63]  # uplight zone
        assert result_color.brightness == 0.0

    async def test_turn_uplight_off_with_color_stores_provided(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turning uplight off with explicit color stores that color."""
        provided_color = HSBK(hue=120, saturation=0.8, brightness=0.6, kelvin=4000)

        await ceiling_176.turn_uplight_off(provided_color)

        # Should store provided color
        assert ceiling_176._stored_uplight_state == provided_color

        # Should set device to brightness=0 (with provided H, S, K)
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        result_color = call_args.args[1][63]  # uplight zone
        assert result_color.brightness == 0.0
        assert result_color.hue == pytest.approx(120, abs=1)
        assert result_color.kelvin == 4000

    async def test_turn_downlight_on_with_single_color(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turning downlight on with single color."""
        color = HSBK(hue=180, saturation=0.8, brightness=1.0, kelvin=5000)

        await ceiling_176.turn_downlight_on(color)

        # Should expand to all 63 zones (plus uplight zone = 64 total)
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        assert len(call_args.args[1]) == 64  # all zones
        # Check downlight zones (0-62) are set to color
        assert all(call_args.args[1][i] == color for i in range(63))

    async def test_turn_downlight_on_with_list_colors(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turning downlight on with list of colors."""
        # Create colors with hue values 0-310 (step of 5) to stay under 360
        colors = [
            HSBK(hue=i * 5, saturation=1.0, brightness=1.0, kelvin=3500)
            for i in range(63)
        ]

        await ceiling_176.turn_downlight_on(colors)

        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        assert len(call_args.args[1]) == 64  # all zones
        # Check downlight zones (0-62) match provided colors
        assert call_args.args[1][0:63] == colors

    async def test_turn_downlight_on_without_color_uses_stored(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turning downlight on without color uses stored state."""
        # Create colors with hue values 0-310 (step of 5) to stay under 360
        stored_colors = [
            HSBK(hue=i * 5, saturation=1.0, brightness=0.7, kelvin=3500)
            for i in range(63)
        ]
        ceiling_176._stored_downlight_state = stored_colors

        await ceiling_176.turn_downlight_on()

        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        assert len(call_args.args[1]) == 64  # all zones
        # Check downlight zones (0-62) match stored colors
        assert call_args.args[1][0:63] == stored_colors

    async def test_turn_downlight_on_infers_from_uplight(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turning downlight on infers brightness from uplight."""
        # No stored state
        ceiling_176._stored_downlight_state = None

        # Mock uplight with brightness 0.5
        uplight_color = HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)
        # Mock current downlight colors (off, but with different H, S, K)
        # Create colors with hue values 0-310 (step of 5) to stay under 360
        downlight_colors = [
            HSBK(hue=i * 5, saturation=0.8, brightness=0.0, kelvin=3500)
            for i in range(63)
        ]
        tile_colors = downlight_colors + [uplight_color]  # 64 colors for 8x8 tile
        ceiling_176.get_all_tile_colors = AsyncMock(return_value=[tile_colors])

        await ceiling_176.turn_downlight_on()

        # Should use uplight brightness (0.5) for all downlight zones
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        result_colors = call_args.args[1]  # all zones
        # Check downlight zones (0-62) have brightness from uplight
        assert all(
            result_colors[i].brightness == pytest.approx(0.5, abs=0.01)
            for i in range(63)
        )
        # H, S, K should be preserved from current downlight
        assert result_colors[0].hue == pytest.approx(0, abs=1)
        assert result_colors[0].kelvin == 3500

    async def test_turn_downlight_off_stores_current_colors(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turning downlight off stores current colors."""
        # Create colors with hue values 0-310 (step of 5) to stay under 360
        current_downlight = [
            HSBK(hue=i * 5, saturation=1.0, brightness=0.8, kelvin=3500)
            for i in range(63)
        ]
        uplight_color = HSBK(hue=30, saturation=0.2, brightness=0.3, kelvin=2700)
        tile_colors = current_downlight + [uplight_color]  # 64 colors for 8x8 tile
        ceiling_176.get_all_tile_colors = AsyncMock(return_value=[tile_colors])

        await ceiling_176.turn_downlight_off()

        # Should store current colors (with brightness preserved)
        assert ceiling_176._stored_downlight_state is not None
        assert len(ceiling_176._stored_downlight_state) == 63
        assert all(
            c.brightness == pytest.approx(0.8, abs=0.01)
            for c in ceiling_176._stored_downlight_state
        )

        # Should set device to brightness=0
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        result_colors = call_args.args[1]  # all zones
        # Check downlight zones (0-62) have brightness=0
        assert all(result_colors[i].brightness == 0.0 for i in range(63))

    async def test_turn_downlight_off_with_color_stores_provided(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turning downlight off with explicit color stores that color."""
        provided_color = HSBK(hue=240, saturation=0.9, brightness=0.6, kelvin=4500)

        await ceiling_176.turn_downlight_off(provided_color)

        # Should store provided color for all zones
        assert ceiling_176._stored_downlight_state is not None
        assert len(ceiling_176._stored_downlight_state) == 63
        assert all(c == provided_color for c in ceiling_176._stored_downlight_state)

        # Should set device to brightness=0
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        # Args: (tile_index, colors, duration=...)
        result_colors = call_args.args[1]  # all zones
        # Check downlight zones (0-62) have brightness=0
        assert all(result_colors[i].brightness == 0.0 for i in range(63))

    async def test_validation_turn_on_with_zero_brightness_raises(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turn_on methods reject brightness=0."""
        invalid_color = HSBK(hue=0, saturation=0, brightness=0.0, kelvin=3500)

        with pytest.raises(ValueError, match="brightness"):
            await ceiling_176.turn_uplight_on(invalid_color)

        with pytest.raises(ValueError, match="brightness"):
            await ceiling_176.turn_downlight_on(invalid_color)

    async def test_validation_turn_off_with_zero_brightness_raises(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turn_off methods reject brightness=0."""
        invalid_color = HSBK(hue=0, saturation=0, brightness=0.0, kelvin=3500)

        with pytest.raises(ValueError, match="brightness"):
            await ceiling_176.turn_uplight_off(invalid_color)

        with pytest.raises(ValueError, match="brightness"):
            await ceiling_176.turn_downlight_off(invalid_color)


class TestCeilingLightProperties:
    """Tests for component state properties."""

    @pytest.fixture
    def ceiling_176(self) -> CeilingLight:
        """Create a Ceiling product 176 (8x8) instance."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling.connection = AsyncMock()
        # Mock cached power state
        ceiling._state = MagicMock()
        ceiling._state.power = 65535  # Power on
        # Mock version for product detection
        ceiling._version = MagicMock()
        ceiling._version.product = 176
        return ceiling

    def test_uplight_is_on_when_on(self, ceiling_176: CeilingLight) -> None:
        """Test uplight_is_on returns True when uplight is on."""
        # Set cached uplight color with brightness > 0
        ceiling_176._last_uplight_color = HSBK(
            hue=30, saturation=0.2, brightness=0.5, kelvin=2700
        )

        assert ceiling_176.uplight_is_on is True

    def test_uplight_is_on_when_off(self, ceiling_176: CeilingLight) -> None:
        """Test uplight_is_on returns False when uplight is off."""
        # Set cached uplight color with brightness = 0
        ceiling_176._last_uplight_color = HSBK(
            hue=30, saturation=0.2, brightness=0.0, kelvin=2700
        )

        assert ceiling_176.uplight_is_on is False

    def test_uplight_is_on_when_power_off(self, ceiling_176: CeilingLight) -> None:
        """Test uplight_is_on returns False when device power is off."""
        ceiling_176._state.power = 0  # Power off
        ceiling_176._last_uplight_color = HSBK(
            hue=30, saturation=0.2, brightness=0.5, kelvin=2700
        )

        assert ceiling_176.uplight_is_on is False

    def test_uplight_is_on_when_no_cached_data(self, ceiling_176: CeilingLight) -> None:
        """Test uplight_is_on returns False when no cached data."""
        ceiling_176._last_uplight_color = None

        assert ceiling_176.uplight_is_on is False

    def test_downlight_is_on_when_on(self, ceiling_176: CeilingLight) -> None:
        """Test downlight_is_on returns True when any downlight zone is on."""
        # Set some zones with brightness > 0
        ceiling_176._last_downlight_colors = [
            HSBK(hue=0, saturation=0, brightness=0.0 if i < 10 else 1.0, kelvin=3500)
            for i in range(63)
        ]

        assert ceiling_176.downlight_is_on is True

    def test_downlight_is_on_when_all_off(self, ceiling_176: CeilingLight) -> None:
        """Test downlight_is_on returns False when all zones are off."""
        # All zones with brightness = 0
        ceiling_176._last_downlight_colors = [
            HSBK(hue=0, saturation=0, brightness=0.0, kelvin=3500) for _ in range(63)
        ]

        assert ceiling_176.downlight_is_on is False

    def test_downlight_is_on_when_power_off(self, ceiling_176: CeilingLight) -> None:
        """Test downlight_is_on returns False when device power is off."""
        ceiling_176._state.power = 0  # Power off
        white = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500)
        ceiling_176._last_downlight_colors = [white] * 63

        assert ceiling_176.downlight_is_on is False

    def test_downlight_is_on_when_no_cached_data(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test downlight_is_on returns False when no cached data."""
        ceiling_176._last_downlight_colors = None

        assert ceiling_176.downlight_is_on is False


class TestCeilingLightStatePersistence:
    """Tests for state persistence to JSON file."""

    @pytest.fixture
    def ceiling_176(self) -> CeilingLight:
        """Create a Ceiling product 176 with temporary state file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "ceiling_state.json"
            ceiling = CeilingLight(
                serial="d073d5010203",
                ip="192.168.1.100",
                state_file=str(state_file),
            )
            ceiling.connection = AsyncMock()
            ceiling.set_matrix_colors = AsyncMock()
            ceiling.get_all_tile_colors = AsyncMock()

            # Mock version for product detection
            ceiling._version = MagicMock()
            ceiling._version.product = 176
            yield ceiling

    async def test_state_file_created_on_save(self, ceiling_176: CeilingLight) -> None:
        """Test state file is created when saving state."""
        # Set some state
        uplight_color = HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)
        ceiling_176._stored_uplight_state = uplight_color

        white = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500)
        downlight_colors = [white] * 63
        ceiling_176._stored_downlight_state = downlight_colors

        # Save to file
        ceiling_176._save_state_to_file()

        # Verify file exists
        assert Path(ceiling_176._state_file).exists()

        # Verify content
        with open(ceiling_176._state_file) as f:
            data = json.load(f)

        assert "d073d5010203" in data
        assert "uplight" in data["d073d5010203"]
        assert "downlight" in data["d073d5010203"]

    async def test_state_loaded_from_file(self, ceiling_176: CeilingLight) -> None:
        """Test state is loaded from file on initialization."""
        # Create state file manually
        state_data = {
            "d073d5010203": {
                "uplight": {
                    "hue": 30.0,
                    "saturation": 0.2,
                    "brightness": 0.5,
                    "kelvin": 2700,
                },
                "downlight": [
                    {"hue": 0.0, "saturation": 0.0, "brightness": 1.0, "kelvin": 3500}
                ]
                * 63,
            }
        }

        with open(ceiling_176._state_file, "w") as f:
            json.dump(state_data, f)

        # Load state
        ceiling_176._load_state_from_file()

        # Verify loaded state
        assert ceiling_176._stored_uplight_state is not None
        assert ceiling_176._stored_uplight_state.hue == pytest.approx(30, abs=1)
        assert ceiling_176._stored_uplight_state.brightness == pytest.approx(
            0.5, abs=0.01
        )

        assert ceiling_176._stored_downlight_state is not None
        assert len(ceiling_176._stored_downlight_state) == 63
        assert all(
            c.brightness == pytest.approx(1.0, abs=0.01)
            for c in ceiling_176._stored_downlight_state
        )

    async def test_state_persistence_across_operations(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test state persists across set and turn_off operations."""
        # Set uplight color
        uplight_color = HSBK(hue=60, saturation=0.5, brightness=0.7, kelvin=4000)
        await ceiling_176.set_uplight_color(uplight_color)

        # Verify state was saved
        assert Path(ceiling_176._state_file).exists()

        # Create new instance with same state file
        ceiling_new = CeilingLight(
            serial="d073d5010203",
            ip="192.168.1.100",
            state_file=ceiling_176._state_file,
        )
        ceiling_new._load_state_from_file()

        # Verify state was loaded
        assert ceiling_new._stored_uplight_state is not None
        assert ceiling_new._stored_uplight_state.hue == pytest.approx(60, abs=1)
        assert ceiling_new._stored_uplight_state.brightness == pytest.approx(
            0.7, abs=0.01
        )


class TestCeilingLightBackwardCompatibility:
    """Tests for backward compatibility with MatrixLight."""

    @pytest.fixture
    def ceiling_176(self) -> CeilingLight:
        """Create a Ceiling product 176 instance with mocked connection."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling.connection = AsyncMock()
        return ceiling

    async def test_set_color_affects_both_components(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test inherited set_color affects both uplight and downlight."""
        color = HSBK(hue=180, saturation=0.8, brightness=1.0, kelvin=5000)

        # Mock the parent set_color method
        ceiling_176.set_matrix_colors = AsyncMock()

        await ceiling_176.set_color(color)

        # Verify set_color was called (from parent class)
        # This would set all zones including both components
        assert ceiling_176.connection.request.called

    async def test_matrixlight_methods_still_work(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test that MatrixLight methods are still available."""
        # Verify MatrixLight methods exist
        assert hasattr(ceiling_176, "get_device_chain")
        assert hasattr(ceiling_176, "get64")
        assert hasattr(ceiling_176, "set64")
        assert hasattr(ceiling_176, "set_matrix_colors")
        assert hasattr(ceiling_176, "get_all_tile_colors")


# Integration tests with emulator
@pytest.mark.emulator
class TestCeilingLightIntegration:
    """Integration tests with lifx-emulator-core."""

    async def test_ceiling_device_discovery(self, ceiling_device: CeilingLight) -> None:
        """Test that ceiling device fixture is created correctly."""
        async with ceiling_device:
            # Verify it's a MatrixLight (CeilingLight inherits from MatrixLight)
            assert isinstance(ceiling_device, CeilingLight)

            # Verify component layout
            assert ceiling_device.uplight_zone == 127  # Product 201
            assert ceiling_device.downlight_zones == slice(0, 127)

    async def test_ceiling_component_control(
        self, ceiling_device: CeilingLight
    ) -> None:
        """Test controlling uplight and downlight independently."""
        async with ceiling_device:
            # Set uplight to warm white
            uplight_color = HSBK(hue=30, saturation=0.2, brightness=0.3, kelvin=2700)
            await ceiling_device.set_uplight_color(uplight_color)

            # Set downlight to cool white
            downlight_color = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=5000)
            await ceiling_device.set_downlight_colors(downlight_color)

            # Read back and verify
            uplight = await ceiling_device.get_uplight_color()
            downlight = await ceiling_device.get_downlight_colors()

            # Verify uplight (allow protocol conversion tolerance)
            assert uplight.hue == pytest.approx(30, abs=5)
            assert uplight.saturation == pytest.approx(0.2, abs=0.05)
            assert uplight.brightness == pytest.approx(0.3, abs=0.05)
            assert uplight.kelvin == pytest.approx(2700, abs=100)

            # Verify downlight
            assert len(downlight) == 127
            assert all(c.brightness == pytest.approx(1.0, abs=0.05) for c in downlight)

    async def test_ceiling_turn_components_on_off(
        self, ceiling_device: CeilingLight
    ) -> None:
        """Test turning components on and off independently."""
        async with ceiling_device:
            # Turn both on with specific colors
            uplight_color = HSBK(hue=120, saturation=0.8, brightness=0.5, kelvin=3500)
            downlight_color = HSBK(hue=240, saturation=0.6, brightness=0.7, kelvin=4000)

            await ceiling_device.turn_uplight_on(uplight_color)
            await ceiling_device.turn_downlight_on(downlight_color)

            # Turn uplight off (should preserve color in stored state)
            await ceiling_device.turn_uplight_off()

            # Verify uplight is off but downlight is still on
            uplight = await ceiling_device.get_uplight_color()
            downlight = await ceiling_device.get_downlight_colors()

            assert uplight.brightness == pytest.approx(0.0, abs=0.01)
            assert all(c.brightness == pytest.approx(0.7, abs=0.05) for c in downlight)

            # Turn uplight back on (should restore from stored state)
            await ceiling_device.turn_uplight_on()

            uplight = await ceiling_device.get_uplight_color()
            assert uplight.brightness == pytest.approx(0.5, abs=0.05)
