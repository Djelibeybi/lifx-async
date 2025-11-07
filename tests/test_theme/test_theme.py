"""Tests for Theme class."""

from __future__ import annotations

import pytest

from lifx.color import HSBK, Colors
from lifx.theme import Theme


class TestThemeCreation:
    """Tests for Theme creation."""

    def test_create_with_colors(self) -> None:
        """Test creating a theme with a list of colors."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)

        theme = Theme([red, green, blue])

        assert len(theme) == 3
        assert theme[0].hue == 0
        assert theme[1].hue == 120
        assert theme[2].hue == 240

    def test_create_with_empty_list(self) -> None:
        """Test creating a theme with empty list defaults to white."""
        theme = Theme([])

        assert len(theme) == 1
        assert theme[0].saturation == 0.0
        assert theme[0].brightness == 1.0

    def test_create_with_none(self) -> None:
        """Test creating a theme with None defaults to white."""
        theme = Theme(None)

        assert len(theme) == 1
        assert theme[0].saturation == 0.0
        assert theme[0].brightness == 1.0

    def test_create_default(self) -> None:
        """Test creating a theme with no arguments."""
        theme = Theme()

        assert len(theme) == 1
        assert theme[0].saturation == 0.0


class TestThemeColorManagement:
    """Tests for color management in themes."""

    def test_add_color(self) -> None:
        """Test adding a color to a theme."""
        theme = Theme()
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)

        theme.add_color(red)

        assert len(theme) == 2  # Default white + red

    def test_add_multiple_colors(self) -> None:
        """Test adding multiple colors."""
        theme = Theme()
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)

        theme.add_color(red)
        theme.add_color(green)

        assert len(theme) == 3


class TestThemeIterationAndAccess:
    """Tests for iteration and access patterns."""

    def test_len(self) -> None:
        """Test len() function."""
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])
        assert len(theme) == 3

    def test_getitem(self) -> None:
        """Test accessing colors by index."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)

        theme = Theme([red, green])

        assert theme[0].hue == 0
        assert theme[1].hue == 120

    def test_getitem_out_of_bounds(self) -> None:
        """Test accessing index out of bounds."""
        theme = Theme([Colors.RED])

        with pytest.raises(IndexError):
            _ = theme[5]

    def test_iter(self) -> None:
        """Test iterating over theme colors."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)

        theme = Theme([red, green])

        hues = [color.hue for color in theme]
        assert hues == [0, 120]

    def test_contains(self) -> None:
        """Test checking if color is in theme."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)

        theme = Theme([red, green])

        assert red in theme
        assert green in theme
        assert blue not in theme

    def test_contains_by_value_not_reference(self) -> None:
        """Test that contains checks by value, not reference."""
        red1 = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        red2 = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)

        theme = Theme([red1])

        # red2 is not the same object but has same values
        assert red2 in theme


class TestThemeRandomization:
    """Tests for random color selection."""

    def test_random(self) -> None:
        """Test getting a random color."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)

        theme = Theme([red, green, blue])
        color = theme.random()

        # Color should be one of the theme colors
        assert color in theme

    def test_shuffled(self) -> None:
        """Test creating a shuffled copy."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)

        theme = Theme([red, green, blue])
        shuffled = theme.shuffled()

        # Should have same colors but different order (likely)
        assert len(shuffled) == 3
        assert red in shuffled
        assert green in shuffled
        assert blue in shuffled

    def test_shuffled_returns_new_instance(self) -> None:
        """Test that shuffled() returns a new Theme instance."""
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])
        shuffled = theme.shuffled()

        assert shuffled is not theme
        assert len(shuffled) == len(theme)


class TestThemeWraparound:
    """Tests for wraparound indexing."""

    def test_get_next_bounds_checked(self) -> None:
        """Test getting next color after index."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)

        theme = Theme([red, green, blue])

        # Get next color after each index
        assert theme.get_next_bounds_checked(0).hue == 120  # next after red is green
        assert theme.get_next_bounds_checked(1).hue == 240  # next after green is blue
        assert (
            theme.get_next_bounds_checked(2).hue == 240
        )  # at end, returns last color (blue)

    def test_get_next_bounds_checked_at_end(self) -> None:
        """Test behavior at end of theme."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)

        theme = Theme([red, green])

        # At or past end should return last color
        assert theme.get_next_bounds_checked(1).hue == 120  # next after green (at end)
        assert (
            theme.get_next_bounds_checked(2).hue == 120
        )  # past end, returns last color
        assert (
            theme.get_next_bounds_checked(10).hue == 120
        )  # way past end, still last color

    def test_get_next_bounds_checked_large_index(self) -> None:
        """Test with large index (returns last color)."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)

        theme = Theme([red, green])

        # Any index past the end returns the last color
        assert theme.get_next_bounds_checked(100).hue == 120
        assert theme.get_next_bounds_checked(101).hue == 120


class TestThemeRepresentation:
    """Tests for string representation."""

    def test_repr(self) -> None:
        """Test string representation."""
        theme = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])
        repr_str = repr(theme)

        assert "Theme" in repr_str
        assert "3 colors" in repr_str
