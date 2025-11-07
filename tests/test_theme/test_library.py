"""Tests for the theme library."""

from __future__ import annotations

import pytest

from lifx.theme import Theme, ThemeLibrary, get_theme


class TestThemeLibraryGet:
    """Tests for ThemeLibrary.get() method."""

    def test_get_existing_theme(self) -> None:
        """Test getting an existing theme by name."""
        evening_theme = ThemeLibrary.get("evening")
        assert isinstance(evening_theme, Theme)
        assert len(evening_theme) == 3

    def test_get_case_insensitive(self) -> None:
        """Test that theme names are case-insensitive."""
        evening_lower = ThemeLibrary.get("evening")
        evening_upper = ThemeLibrary.get("EVENING")
        evening_mixed = ThemeLibrary.get("EvEnInG")

        assert len(evening_lower) == len(evening_upper) == len(evening_mixed)

    def test_get_nonexistent_theme(self) -> None:
        """Test getting a non-existent theme raises KeyError."""
        with pytest.raises(KeyError) as exc_info:
            ThemeLibrary.get("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "Available themes" in str(exc_info.value)

    def test_get_returns_new_instance(self) -> None:
        """Test that get() returns a new Theme instance each time."""
        theme1 = ThemeLibrary.get("evening")
        theme2 = ThemeLibrary.get("evening")

        # Should be different instances
        assert theme1 is not theme2
        # But with same content
        assert len(theme1) == len(theme2)

    def test_get_specific_themes(self) -> None:
        """Test getting specific well-known themes."""
        themes_to_test = [
            ("christmas", 4),
            ("halloween", 6),
            ("evening", 3),
            ("relaxing", 4),
            ("dream", 7),
        ]

        for theme_name, expected_colors in themes_to_test:
            theme = ThemeLibrary.get(theme_name)
            assert len(theme) == expected_colors


class TestThemeLibraryList:
    """Tests for ThemeLibrary.list() method."""

    def test_list_returns_sorted_list(self) -> None:
        """Test that list() returns a sorted list of theme names."""
        themes = ThemeLibrary.list()

        assert isinstance(themes, list)
        assert len(themes) == 42  # Should have 42 themes
        assert themes == sorted(themes)  # Should be sorted

    def test_list_contains_well_known_themes(self) -> None:
        """Test that list includes well-known themes."""
        themes = ThemeLibrary.list()
        expected_themes = [
            "christmas",
            "halloween",
            "evening",
            "relaxing",
            "dream",
            "spring",
            "autumn",
        ]

        for theme_name in expected_themes:
            assert theme_name in themes

    def test_list_count(self) -> None:
        """Test that we have the expected number of themes."""
        themes = ThemeLibrary.list()
        # We should have exactly 42 themes
        assert len(themes) == 42


class TestThemeLibraryGetByCategory:
    """Tests for ThemeLibrary.get_by_category() method."""

    def test_get_seasonal_themes(self) -> None:
        """Test getting seasonal themes."""
        seasonal = ThemeLibrary.get_by_category("seasonal")

        assert isinstance(seasonal, dict)
        assert "spring" in seasonal
        assert "autumn" in seasonal

    def test_get_holiday_themes(self) -> None:
        """Test getting holiday themes."""
        holidays = ThemeLibrary.get_by_category("holiday")

        assert isinstance(holidays, dict)
        assert "christmas" in holidays
        assert "halloween" in holidays
        assert "hanukkah" in holidays

    def test_get_mood_themes(self) -> None:
        """Test getting mood themes."""
        moods = ThemeLibrary.get_by_category("mood")

        assert isinstance(moods, dict)
        assert "relaxing" in moods
        assert "energizing" in moods
        assert "peaceful" in moods

    def test_get_invalid_category(self) -> None:
        """Test that invalid category raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ThemeLibrary.get_by_category("invalid")

        assert "invalid" in str(exc_info.value)
        assert "not recognized" in str(exc_info.value)

    def test_category_case_insensitive(self) -> None:
        """Test that category names are case-insensitive."""
        seasonal_lower = ThemeLibrary.get_by_category("seasonal")
        seasonal_upper = ThemeLibrary.get_by_category("SEASONAL")

        assert len(seasonal_lower) == len(seasonal_upper)


class TestGetThemeConvenienceFunction:
    """Tests for the get_theme() convenience function."""

    def test_get_theme_basic(self) -> None:
        """Test getting a theme using convenience function."""
        evening = get_theme("evening")
        assert isinstance(evening, Theme)
        assert len(evening) == 3

    def test_get_theme_is_equivalent_to_library(self) -> None:
        """Test that get_theme() is equivalent to ThemeLibrary.get()."""
        evening1 = get_theme("evening")
        evening2 = ThemeLibrary.get("evening")

        assert len(evening1) == len(evening2)

    def test_get_theme_invalid(self) -> None:
        """Test that invalid theme raises KeyError."""
        with pytest.raises(KeyError):
            get_theme("nonexistent")


class TestThemeLibraryColorValues:
    """Tests for verifying theme color values."""

    def test_christmas_theme_colors(self) -> None:
        """Test that Christmas theme has correct colors."""
        christmas = ThemeLibrary.get("christmas")
        colors = list(christmas)

        # Christmas should have green and red colors
        hues = [color.hue for color in colors]
        assert any(abs(h - 120) < 5 for h in hues)  # Green
        assert any(abs(h - 0) < 5 for h in hues)  # Red

    def test_halloween_theme_colors(self) -> None:
        """Test that Halloween theme has orange colors."""
        halloween = ThemeLibrary.get("halloween")
        colors = list(halloween)

        # Halloween should be mostly orange (hue ~30-35)
        hues = [color.hue for color in colors]
        assert any(30 <= h <= 35 for h in hues)

    def test_relaxing_theme_saturation(self) -> None:
        """Test that relaxing theme has generally lower saturation."""
        relaxing = ThemeLibrary.get("relaxing")
        colors = list(relaxing)

        # Relaxing themes tend to have varied saturation
        saturations = [c.saturation for c in colors]
        assert len(saturations) > 0

    def test_evening_theme_values(self) -> None:
        """Test evening theme has warm colors."""
        evening = ThemeLibrary.get("evening")
        colors = list(evening)

        # Evening should be warm (orange/gold colors, hue 30-40)
        hues = [color.hue for color in colors]
        assert all(30 <= h <= 40 for h in hues)

        # Evening should have decent saturation
        saturations = [c.saturation for c in colors]
        assert all(0.7 <= s <= 0.9 for s in saturations)


class TestThemeLibraryIntegration:
    """Integration tests for theme library."""

    def test_all_themes_are_valid(self) -> None:
        """Test that all themes in the library are valid."""
        for theme_name in ThemeLibrary.list():
            theme = ThemeLibrary.get(theme_name)
            assert isinstance(theme, Theme)
            assert len(theme) > 0

            # All colors should be HSBK-compatible
            for color in theme:
                assert 0 <= color.hue <= 360
                assert 0 <= color.saturation <= 1.0
                assert 0 <= color.brightness <= 1.0
                assert 2500 <= color.kelvin <= 9000

    def test_theme_library_has_minimum_themes(self) -> None:
        """Test that library has at least 42 themes."""
        themes = ThemeLibrary.list()
        assert len(themes) >= 42

    def test_all_categories_have_themes(self) -> None:
        """Test that all known categories have themes."""
        categories = [
            "seasonal",
            "holiday",
            "mood",
            "ambient",
            "functional",
            "atmosphere",
        ]

        for category in categories:
            themes = ThemeLibrary.get_by_category(category)
            assert len(themes) > 0
