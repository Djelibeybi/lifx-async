"""Tests for CeilingLight device class."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.devices.ceiling import CeilingLight
from lifx.exceptions import LifxError
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

    async def test_ceiling_from_ip(self, ceiling_device: CeilingLight) -> None:
        """Test CeilingLight.from_ip() factory method with emulator."""
        # Use the port and serial from the fixture's device
        port = ceiling_device.port
        serial = ceiling_device.serial

        # Create CeilingLight using from_ip() - must provide serial to target
        # the correct device in the session-scoped emulator
        ceiling = await CeilingLight.from_ip(
            ip="127.0.0.1",
            port=port,
            serial=serial,
            timeout=2.0,
            max_retries=2,
        )

        async with ceiling:
            # Verify it's properly initialized
            assert isinstance(ceiling, CeilingLight)
            assert ceiling.serial == serial
            assert ceiling.ip == "127.0.0.1"

            # Verify component layout (product 201 = 16x8 ceiling)
            assert ceiling.uplight_zone == 127
            assert ceiling.downlight_zones == slice(0, 127)

    async def test_ceiling_from_ip_with_state_file(
        self, ceiling_device: CeilingLight
    ) -> None:
        """Test CeilingLight.from_ip() with state_file parameter."""
        port = ceiling_device.port
        serial = ceiling_device.serial

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "ceiling_state.json"

            # Create CeilingLight using from_ip() with state_file
            ceiling = await CeilingLight.from_ip(
                ip="127.0.0.1",
                port=port,
                serial=serial,
                timeout=2.0,
                max_retries=2,
                state_file=str(state_file),
            )

            async with ceiling:
                # Verify state_file is set
                assert ceiling._state_file == str(state_file)

                # Set uplight color (should persist to state file)
                uplight_color = HSBK(
                    hue=45, saturation=0.3, brightness=0.6, kelvin=3000
                )
                await ceiling.set_uplight_color(uplight_color)

                # Verify state file was created
                assert state_file.exists()

                # Verify state file contents
                with state_file.open("r") as f:
                    data = json.load(f)

                assert ceiling.serial in data
                assert "uplight" in data[ceiling.serial]

    async def test_ceiling_state_persistence_turn_off(
        self, ceiling_device: CeilingLight
    ) -> None:
        """Test state persistence when turning components off with emulator."""
        port = ceiling_device.port

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "ceiling_state.json"

            ceiling = CeilingLight(
                serial="d073d5000100",
                ip="127.0.0.1",
                port=port,
                timeout=2.0,
                max_retries=2,
                state_file=str(state_file),
            )

            async with ceiling:
                # Set uplight color first
                uplight_color = HSBK(
                    hue=60, saturation=0.4, brightness=0.7, kelvin=3200
                )
                await ceiling.set_uplight_color(uplight_color)

                # Turn uplight off (should persist stored state)
                await ceiling.turn_uplight_off()

                # Verify state file has stored color
                with state_file.open("r") as f:
                    data = json.load(f)

                uplight_data = data[ceiling.serial]["uplight"]
                assert uplight_data["hue"] == pytest.approx(60, abs=1)
                assert uplight_data["brightness"] == pytest.approx(0.7, abs=0.01)

    async def test_ceiling_state_persistence_downlight(
        self, ceiling_device: CeilingLight
    ) -> None:
        """Test downlight state persistence with emulator."""
        port = ceiling_device.port

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "ceiling_state.json"

            ceiling = CeilingLight(
                serial="d073d5000100",
                ip="127.0.0.1",
                port=port,
                timeout=2.0,
                max_retries=2,
                state_file=str(state_file),
            )

            async with ceiling:
                # Set downlight color
                downlight_color = HSBK(
                    hue=180, saturation=0.5, brightness=0.8, kelvin=4000
                )
                await ceiling.set_downlight_colors(downlight_color)

                # Verify state file has downlight colors
                with state_file.open("r") as f:
                    data = json.load(f)

                assert "downlight" in data[ceiling.serial]
                downlight_data = data[ceiling.serial]["downlight"]
                assert len(downlight_data) == 127  # Product 201 has 127 downlight zones

                # Turn downlight off (should persist)
                await ceiling.turn_downlight_off()

                # Verify state still persisted
                with state_file.open("r") as f:
                    data = json.load(f)

                assert "downlight" in data[ceiling.serial]


class TestCeilingLightErrorHandling:
    """Tests for error handling paths."""

    def test_uplight_zone_no_version_raises(self) -> None:
        """Test uplight_zone raises when version not available."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        # No version set (version is None by default)

        with pytest.raises(LifxError, match="Device version not available"):
            _ = ceiling.uplight_zone

    def test_uplight_zone_invalid_product_raises(self) -> None:
        """Test uplight_zone raises for non-ceiling product."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling._version = MagicMock()
        ceiling._version.product = 1  # Not a ceiling product

        with pytest.raises(LifxError, match="is not a Ceiling light"):
            _ = ceiling.uplight_zone

    def test_downlight_zones_no_version_raises(self) -> None:
        """Test downlight_zones raises when version not available."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        # No version set

        with pytest.raises(LifxError, match="Device version not available"):
            _ = ceiling.downlight_zones

    def test_downlight_zones_invalid_product_raises(self) -> None:
        """Test downlight_zones raises for non-ceiling product."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling._version = MagicMock()
        ceiling._version.product = 1  # Not a ceiling product

        with pytest.raises(LifxError, match="is not a Ceiling light"):
            _ = ceiling.downlight_zones

    def test_uplight_is_on_returns_false_when_state_none(self) -> None:
        """Test uplight_is_on returns False when _state is None."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling._state = None
        ceiling._last_uplight_color = HSBK(
            hue=30, saturation=0.2, brightness=0.5, kelvin=2700
        )

        assert ceiling.uplight_is_on is False

    def test_downlight_is_on_returns_false_when_state_none(self) -> None:
        """Test downlight_is_on returns False when _state is None."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling._state = None
        white = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500)
        ceiling._last_downlight_colors = [white] * 63

        assert ceiling.downlight_is_on is False


class TestCeilingLightIsStoredStateValid:
    """Tests for _is_stored_state_valid method."""

    @pytest.fixture
    def ceiling_176(self) -> CeilingLight:
        """Create a Ceiling product 176 instance."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling._version = MagicMock()
        ceiling._version.product = 176
        return ceiling

    def test_uplight_valid_match(self, ceiling_176: CeilingLight) -> None:
        """Test uplight stored state matches current (ignoring brightness)."""
        ceiling_176._stored_uplight_state = HSBK(
            hue=30, saturation=0.2, brightness=0.8, kelvin=2700
        )
        current = HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)

        assert ceiling_176._is_stored_state_valid("uplight", current) is True

    def test_uplight_no_stored_state(self, ceiling_176: CeilingLight) -> None:
        """Test uplight returns False when no stored state."""
        ceiling_176._stored_uplight_state = None
        current = HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)

        assert ceiling_176._is_stored_state_valid("uplight", current) is False

    def test_uplight_wrong_type(self, ceiling_176: CeilingLight) -> None:
        """Test uplight returns False when current is not HSBK."""
        ceiling_176._stored_uplight_state = HSBK(
            hue=30, saturation=0.2, brightness=0.8, kelvin=2700
        )
        # Pass a list instead of HSBK
        current = [HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)]

        assert ceiling_176._is_stored_state_valid("uplight", current) is False

    def test_uplight_hue_mismatch(self, ceiling_176: CeilingLight) -> None:
        """Test uplight returns False when hue doesn't match."""
        ceiling_176._stored_uplight_state = HSBK(
            hue=30, saturation=0.2, brightness=0.8, kelvin=2700
        )
        current = HSBK(hue=60, saturation=0.2, brightness=0.5, kelvin=2700)

        assert ceiling_176._is_stored_state_valid("uplight", current) is False

    def test_downlight_valid_match(self, ceiling_176: CeilingLight) -> None:
        """Test downlight stored state matches current (ignoring brightness)."""
        ceiling_176._stored_downlight_state = [
            HSBK(hue=i * 5, saturation=0.8, brightness=0.9, kelvin=3500)
            for i in range(63)
        ]
        current = [
            HSBK(hue=i * 5, saturation=0.8, brightness=0.3, kelvin=3500)
            for i in range(63)
        ]

        assert ceiling_176._is_stored_state_valid("downlight", current) is True

    def test_downlight_no_stored_state(self, ceiling_176: CeilingLight) -> None:
        """Test downlight returns False when no stored state."""
        ceiling_176._stored_downlight_state = None
        current = [
            HSBK(hue=0, saturation=0, brightness=1.0, kelvin=3500) for _ in range(63)
        ]

        assert ceiling_176._is_stored_state_valid("downlight", current) is False

    def test_downlight_wrong_type(self, ceiling_176: CeilingLight) -> None:
        """Test downlight returns False when current is not list."""
        ceiling_176._stored_downlight_state = [
            HSBK(hue=0, saturation=0, brightness=0.9, kelvin=3500) for _ in range(63)
        ]
        # Pass HSBK instead of list
        current = HSBK(hue=0, saturation=0, brightness=0.5, kelvin=3500)

        assert ceiling_176._is_stored_state_valid("downlight", current) is False

    def test_downlight_length_mismatch(self, ceiling_176: CeilingLight) -> None:
        """Test downlight returns False when lengths don't match."""
        ceiling_176._stored_downlight_state = [
            HSBK(hue=0, saturation=0, brightness=0.9, kelvin=3500) for _ in range(63)
        ]
        current = [
            HSBK(hue=0, saturation=0, brightness=0.5, kelvin=3500)
            for _ in range(10)  # Wrong length
        ]

        assert ceiling_176._is_stored_state_valid("downlight", current) is False

    def test_downlight_saturation_mismatch(self, ceiling_176: CeilingLight) -> None:
        """Test downlight returns False when saturation doesn't match."""
        ceiling_176._stored_downlight_state = [
            HSBK(hue=0, saturation=0.8, brightness=0.9, kelvin=3500) for _ in range(63)
        ]
        current = [
            HSBK(
                hue=0, saturation=0.5, brightness=0.5, kelvin=3500
            )  # Different saturation
            for _ in range(63)
        ]

        assert ceiling_176._is_stored_state_valid("downlight", current) is False

    def test_unknown_component_returns_false(self, ceiling_176: CeilingLight) -> None:
        """Test unknown component name returns False."""
        current = HSBK(hue=0, saturation=0, brightness=0.5, kelvin=3500)

        assert ceiling_176._is_stored_state_valid("unknown", current) is False


class TestCeilingLightStateFileEdgeCases:
    """Tests for state file edge cases."""

    def test_load_state_no_state_file(self) -> None:
        """Test _load_state_from_file does nothing when no state file."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling._state_file = None

        # Should not raise
        ceiling._load_state_from_file()
        assert ceiling._stored_uplight_state is None
        assert ceiling._stored_downlight_state is None

    def test_load_state_file_not_exists(self) -> None:
        """Test _load_state_from_file handles non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ceiling = CeilingLight(
                serial="d073d5010203",
                ip="192.168.1.100",
                state_file=str(Path(tmpdir) / "nonexistent.json"),
            )

            # Should not raise
            ceiling._load_state_from_file()
            assert ceiling._stored_uplight_state is None

    def test_load_state_no_device_state(self) -> None:
        """Test _load_state_from_file handles file without device state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            # Write state for a different device
            with state_file.open("w") as f:
                json.dump({"different_serial": {"uplight": {}}}, f)

            ceiling = CeilingLight(
                serial="d073d5010203",
                ip="192.168.1.100",
                state_file=str(state_file),
            )

            ceiling._load_state_from_file()
            assert ceiling._stored_uplight_state is None

    def test_load_state_invalid_json(self) -> None:
        """Test _load_state_from_file handles invalid JSON gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            with state_file.open("w") as f:
                f.write("not valid json {{{")

            ceiling = CeilingLight(
                serial="d073d5010203",
                ip="192.168.1.100",
                state_file=str(state_file),
            )

            # Should not raise, just log warning
            ceiling._load_state_from_file()
            assert ceiling._stored_uplight_state is None

    def test_save_state_no_state_file(self) -> None:
        """Test _save_state_to_file does nothing when no state file."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling._state_file = None
        ceiling._stored_uplight_state = HSBK(
            hue=30, saturation=0.2, brightness=0.5, kelvin=2700
        )

        # Should not raise
        ceiling._save_state_to_file()

    def test_save_state_creates_directory(self) -> None:
        """Test _save_state_to_file creates parent directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "subdir" / "nested" / "state.json"
            ceiling = CeilingLight(
                serial="d073d5010203",
                ip="192.168.1.100",
                state_file=str(state_file),
            )
            ceiling._stored_uplight_state = HSBK(
                hue=30, saturation=0.2, brightness=0.5, kelvin=2700
            )

            ceiling._save_state_to_file()

            assert state_file.exists()
            with state_file.open("r") as f:
                data = json.load(f)
            assert "d073d5010203" in data

    def test_save_state_merges_with_existing(self) -> None:
        """Test _save_state_to_file merges with existing file data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            # Pre-populate with another device
            with state_file.open("w") as f:
                json.dump(
                    {
                        "other_device": {
                            "uplight": {
                                "hue": 100,
                                "saturation": 0.5,
                                "brightness": 0.5,
                                "kelvin": 4000,
                            }
                        }
                    },
                    f,
                )

            ceiling = CeilingLight(
                serial="d073d5010203",
                ip="192.168.1.100",
                state_file=str(state_file),
            )
            ceiling._stored_uplight_state = HSBK(
                hue=30, saturation=0.2, brightness=0.5, kelvin=2700
            )

            ceiling._save_state_to_file()

            with state_file.open("r") as f:
                data = json.load(f)

            # Both devices should be present
            assert "other_device" in data
            assert "d073d5010203" in data

    def test_save_state_handles_write_error(self) -> None:
        """Test _save_state_to_file handles write errors gracefully."""
        ceiling = CeilingLight(
            serial="d073d5010203",
            ip="192.168.1.100",
            state_file="/nonexistent/path/that/cannot/be/created/state.json",
        )
        ceiling._stored_uplight_state = HSBK(
            hue=30, saturation=0.2, brightness=0.5, kelvin=2700
        )

        # Should not raise, just log warning
        ceiling._save_state_to_file()


class TestCeilingLightTurnDownlightOffWithList:
    """Tests for turn_downlight_off with list of colors."""

    @pytest.fixture
    def ceiling_176(self) -> CeilingLight:
        """Create a Ceiling product 176 instance with mocked connection."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling.connection = AsyncMock()
        ceiling.set_matrix_colors = AsyncMock()
        ceiling._save_state_to_file = MagicMock()

        # Mock get_all_tile_colors
        white = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500)
        default_tile_colors = [white] * 64
        ceiling.get_all_tile_colors = AsyncMock(return_value=[default_tile_colors])

        ceiling._version = MagicMock()
        ceiling._version.product = 176
        return ceiling

    async def test_turn_downlight_off_with_list_stores_provided(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turning downlight off with list of colors stores all colors."""
        provided_colors = [
            HSBK(hue=i * 5, saturation=0.9, brightness=0.6, kelvin=4500)
            for i in range(63)
        ]

        await ceiling_176.turn_downlight_off(provided_colors)

        # Should store provided colors
        assert ceiling_176._stored_downlight_state is not None
        assert len(ceiling_176._stored_downlight_state) == 63
        assert ceiling_176._stored_downlight_state == provided_colors

        # Should set device to brightness=0
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        result_colors = call_args.args[1]
        assert all(result_colors[i].brightness == 0.0 for i in range(63))

    async def test_turn_downlight_off_list_invalid_length_raises(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turn_downlight_off with wrong number of colors raises ValueError."""
        invalid_colors = [
            HSBK(hue=0, saturation=0.9, brightness=0.6, kelvin=4500)
            for _ in range(10)  # Wrong count
        ]

        with pytest.raises(ValueError, match="Expected 63 colors"):
            await ceiling_176.turn_downlight_off(invalid_colors)

    async def test_turn_downlight_off_list_all_zero_brightness_raises(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turn_downlight_off with all zero brightness raises ValueError."""
        invalid_colors = [
            HSBK(hue=0, saturation=0, brightness=0.0, kelvin=3500) for _ in range(63)
        ]

        with pytest.raises(ValueError, match="brightness"):
            await ceiling_176.turn_downlight_off(invalid_colors)


class TestCeilingLightBrightnessInference:
    """Tests for brightness inference edge cases."""

    @pytest.fixture
    def ceiling_176(self) -> CeilingLight:
        """Create a Ceiling product 176 instance with mocked connection."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling.connection = AsyncMock()
        ceiling.set_matrix_colors = AsyncMock()
        ceiling._save_state_to_file = MagicMock()

        ceiling._version = MagicMock()
        ceiling._version.product = 176
        return ceiling

    async def test_determine_uplight_brightness_exception_fallback(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test _determine_uplight_brightness falls back to default on exception."""
        ceiling_176._stored_uplight_state = None

        # First call returns current uplight, second call raises
        uplight_color = HSBK(hue=30, saturation=0.2, brightness=0.0, kelvin=2700)
        call_count = 0

        async def mock_get_all_tile_colors() -> list[list[HSBK]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Return current state for get_uplight_color
                white = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500)
                return [[white] * 63 + [uplight_color]]
            else:
                # Raise exception on second call (get_downlight_colors)
                raise Exception("Network error")

        ceiling_176.get_all_tile_colors = mock_get_all_tile_colors

        result = await ceiling_176._determine_uplight_brightness()

        # Should fall back to default brightness (0.8)
        assert result.brightness == pytest.approx(0.8, abs=0.01)
        assert result.hue == pytest.approx(30, abs=1)
        assert result.kelvin == 2700

    async def test_determine_downlight_brightness_exception_fallback(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test _determine_downlight_brightness falls back to default on exception."""
        ceiling_176._stored_downlight_state = None

        # Create downlight colors
        downlight_colors = [
            HSBK(hue=i * 5, saturation=0.8, brightness=0.0, kelvin=3500)
            for i in range(63)
        ]
        uplight_color = HSBK(hue=30, saturation=0.2, brightness=0.0, kelvin=2700)
        call_count = 0

        async def mock_get_all_tile_colors() -> list[list[HSBK]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Return current state for get_downlight_colors
                return [downlight_colors + [uplight_color]]
            else:
                # Raise exception on second call (get_uplight_color)
                raise Exception("Network error")

        ceiling_176.get_all_tile_colors = mock_get_all_tile_colors

        result = await ceiling_176._determine_downlight_brightness()

        # Should fall back to default brightness (0.8) for all zones
        assert len(result) == 63
        assert all(c.brightness == pytest.approx(0.8, abs=0.01) for c in result)

    async def test_turn_downlight_on_default_brightness_when_uplight_off(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test turn_downlight_on uses default when uplight is off (brightness=0)."""
        ceiling_176._stored_downlight_state = None

        # Mock uplight with brightness 0 and downlight with brightness 0
        uplight_color = HSBK(hue=30, saturation=0.2, brightness=0.0, kelvin=2700)
        downlight_colors = [
            HSBK(hue=i * 5, saturation=0.8, brightness=0.0, kelvin=3500)
            for i in range(63)
        ]
        tile_colors = downlight_colors + [uplight_color]
        ceiling_176.get_all_tile_colors = AsyncMock(return_value=[tile_colors])

        await ceiling_176.turn_downlight_on()

        # Should use default brightness (0.8)
        ceiling_176.set_matrix_colors.assert_called_once()
        call_args = ceiling_176.set_matrix_colors.call_args
        result_colors = call_args.args[1]
        assert all(
            result_colors[i].brightness == pytest.approx(0.8, abs=0.01)
            for i in range(63)
        )


class TestCeilingLightContextManager:
    """Tests for async context manager behavior."""

    async def test_aenter_validates_ceiling_product(self) -> None:
        """Test __aenter__ raises for non-ceiling product."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling.connection = AsyncMock()

        # Mock parent __aenter__ to set version
        async def mock_parent_aenter() -> CeilingLight:
            ceiling._version = MagicMock()
            ceiling._version.product = 1  # Not a ceiling product
            ceiling._state = MagicMock()
            ceiling._state.power = 65535
            return ceiling

        # Patch the super().__aenter__ call
        import lifx.devices.matrix as matrix_module

        original_aenter = matrix_module.MatrixLight.__aenter__

        async def patched_aenter(self: CeilingLight) -> CeilingLight:
            self._version = MagicMock()
            self._version.product = 1  # Not a ceiling product
            self._state = MagicMock()
            self._state.power = 65535
            return self

        matrix_module.MatrixLight.__aenter__ = patched_aenter

        try:
            with pytest.raises(LifxError, match="not a supported Ceiling light"):
                await ceiling.__aenter__()
        finally:
            matrix_module.MatrixLight.__aenter__ = original_aenter

    async def test_aenter_loads_state_file(self) -> None:
        """Test __aenter__ loads state from file when configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            # Pre-populate state file
            state_data = {
                "d073d5010203": {
                    "uplight": {
                        "hue": 60.0,
                        "saturation": 0.5,
                        "brightness": 0.7,
                        "kelvin": 4000,
                    }
                }
            }
            with state_file.open("w") as f:
                json.dump(state_data, f)

            ceiling = CeilingLight(
                serial="d073d5010203",
                ip="192.168.1.100",
                state_file=str(state_file),
            )
            ceiling.connection = AsyncMock()

            # Mock parent __aenter__ to set version
            import lifx.devices.matrix as matrix_module

            async def patched_aenter(self: CeilingLight) -> CeilingLight:
                self._version = MagicMock()
                self._version.product = 176  # Valid ceiling product
                self._state = MagicMock()
                self._state.power = 65535
                return self

            original_aenter = matrix_module.MatrixLight.__aenter__
            matrix_module.MatrixLight.__aenter__ = patched_aenter

            try:
                await ceiling.__aenter__()

                # Verify state was loaded
                assert ceiling._stored_uplight_state is not None
                assert ceiling._stored_uplight_state.hue == pytest.approx(60, abs=1)
                assert ceiling._stored_uplight_state.brightness == pytest.approx(
                    0.7, abs=0.01
                )
            finally:
                matrix_module.MatrixLight.__aenter__ = original_aenter


class TestCeilingLightSetDownlightSingleZeroBrightness:
    """Tests for set_downlight_colors edge cases."""

    @pytest.fixture
    def ceiling_176(self) -> CeilingLight:
        """Create a Ceiling product 176 instance with mocked connection."""
        ceiling = CeilingLight(serial="d073d5010203", ip="192.168.1.100")
        ceiling.connection = AsyncMock()
        ceiling.set_matrix_colors = AsyncMock()
        ceiling._save_state_to_file = MagicMock()

        white = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500)
        default_tile_colors = [white] * 64
        ceiling.get_all_tile_colors = AsyncMock(return_value=[default_tile_colors])

        ceiling._version = MagicMock()
        ceiling._version.product = 176
        return ceiling

    async def test_set_downlight_single_color_zero_brightness_raises(
        self, ceiling_176: CeilingLight
    ) -> None:
        """Test set_downlight_colors with single color brightness=0 raises."""
        invalid_color = HSBK(hue=0, saturation=0, brightness=0.0, kelvin=3500)

        with pytest.raises(ValueError, match="brightness"):
            await ceiling_176.set_downlight_colors(invalid_color)
