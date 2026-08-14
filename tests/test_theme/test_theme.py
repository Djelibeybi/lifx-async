"""Tests for Theme class."""

from __future__ import annotations

import pytest

from lifx.color import HSBK, Colors
from lifx.theme import Theme
from lifx.theme.library import ThemeLibrary


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


class TestThemeIdentity:
    """Tests for the optional identity attributes (slug, name, category)."""

    def test_identity_kwargs_stored(self) -> None:
        """Identity kwargs are stored on the instance."""
        theme = Theme([Colors.RED], slug="red", name="Red", category="Test")

        assert theme.slug == "red"
        assert theme.name == "Red"
        assert theme.category == "Test"

    def test_identity_defaults_none(self) -> None:
        """Identity fields default to None for caller-constructed themes."""
        theme = Theme([Colors.RED])

        assert theme.slug is None
        assert theme.name is None
        assert theme.category is None

    def test_positional_construction_unchanged(self) -> None:
        """Positional colour-list construction behaves exactly as before."""
        theme = Theme([Colors.RED, Colors.GREEN])

        assert len(theme) == 2
        assert theme.slug is None

    def test_default_construction_identity_none(self) -> None:
        """Theme() still defaults to white with no identity."""
        theme = Theme()

        assert len(theme) == 1
        assert theme.slug is None
        assert theme.name is None
        assert theme.category is None


class TestThemeEquality:
    """Tests for palette-only multiset equality (D-19) and unhashability (D-20)."""

    def test_same_colors_different_order_equal(self) -> None:
        """Themes with the same colours in different orders compare equal."""
        a = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])
        b = Theme([Colors.BLUE, Colors.RED, Colors.GREEN])

        assert a == b

    def test_different_duplicate_counts_unequal(self) -> None:
        """Themes differing only in duplicate counts compare unequal."""
        a = Theme([Colors.RED, Colors.RED, Colors.GREEN])
        b = Theme([Colors.RED, Colors.GREEN, Colors.GREEN])

        assert a != b

    def test_multiset_not_set(self) -> None:
        """Same distinct colour set but different multiplicities is unequal."""
        a = Theme([Colors.RED, Colors.RED])
        b = Theme([Colors.RED])

        assert a != b

    def test_identity_ignored(self) -> None:
        """A library theme and a caller-built theme with the same palette are equal."""
        library_theme = ThemeLibrary.get("evening")
        caller_theme = Theme(list(library_theme.colors))

        assert caller_theme.slug is None
        assert library_theme == caller_theme

    def test_distinct_themes_with_identical_palettes_compare_equal(self) -> None:
        """Distinct library themes sharing a palette compare equal (D-19).

        The app ships memorial_day, independence and old_glory with one
        identical palette; identity is excluded from equality, so they
        compare equal. (Pre-v1.2 the example pair was love/romance, but
        the resync gave romance its own app palette.)
        """
        assert ThemeLibrary.get("independence") == ThemeLibrary.get("old_glory")
        assert ThemeLibrary.get("memorial_day") == ThemeLibrary.get("old_glory")

    def test_different_palettes_unequal(self) -> None:
        """Themes with different palettes compare unequal."""
        a = Theme([Colors.RED])
        b = Theme([Colors.GREEN])

        assert a != b

    def test_non_theme_comparison_false_without_raising(self) -> None:
        """Comparing a Theme with a non-Theme is False, never an exception."""
        theme = Theme([Colors.RED])

        assert (theme == 3) is False
        assert (theme != 3) is True
        assert theme != object()

    def test_unhashable(self) -> None:
        """hash(theme) raises TypeError — Theme is deliberately unhashable."""
        theme = Theme([Colors.RED])

        with pytest.raises(TypeError):
            hash(theme)

    def test_hash_slot_is_none(self) -> None:
        """Defining __eq__ without __hash__ sets Theme.__hash__ to None."""
        assert Theme.__hash__ is None

    def test_existing_behaviour_unchanged(self) -> None:
        """Iteration, indexing, len() and add_color() behave exactly as before."""
        theme = Theme([Colors.RED, Colors.GREEN])

        assert len(theme) == 2
        assert theme[0] == Colors.RED
        assert list(theme) == [Colors.RED, Colors.GREEN]

        theme.add_color(Colors.BLUE)
        assert len(theme) == 3


class TestPaletteThemes:
    """Tests for palette themes ported from pkivolowitz/lifx."""

    PALETTE_NAMES = [
        "fire",
        "water",
        "forest",
        "earth",
        "neon",
        "aurora_borealis",
        "tropical",
        "arctic",
        "galaxy",
        "deep_sea",
        "coral_reef",
        "desert",
        "vaporwave",
        "cyberpunk",
        "cherry_blossom",
    ]

    @pytest.mark.parametrize("name", PALETTE_NAMES)
    def test_palette_theme_exists(self, name: str) -> None:
        """Each palette theme should be retrievable."""
        theme = ThemeLibrary.get(name)
        assert theme is not None

    @pytest.mark.parametrize("name", PALETTE_NAMES)
    def test_palette_theme_has_colors(self, name: str) -> None:
        """Each palette theme should have at least 3 colors."""
        theme = ThemeLibrary.get(name)
        assert len(theme) >= 3

    @pytest.mark.parametrize("name", PALETTE_NAMES)
    def test_palette_theme_colors_are_valid_hsbk(self, name: str) -> None:
        """Each color in a palette theme should be a valid HSBK."""
        theme = ThemeLibrary.get(name)
        for color in theme:
            assert isinstance(color, HSBK)
            assert 0 <= color.hue <= 360
            assert 0.0 <= color.saturation <= 1.0
            assert 0.0 <= color.brightness <= 1.0
            assert 1500 <= color.kelvin <= 9000

    def test_palette_names_dont_collide_with_existing(self) -> None:
        """Palette names should not collide with existing themes."""
        all_names = ThemeLibrary.get_available_themes()
        assert len(all_names) == len(set(all_names))
