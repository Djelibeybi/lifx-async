"""Tests for Theme class."""

from __future__ import annotations

from typing import get_args

import pytest

import lifx.theme
from lifx.color import HSBK, Colors
from lifx.theme import DynamicMode, StaticMode, Theme
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

    def test_constructor_copies_the_caller_list(self) -> None:
        """add_color() on the Theme must not reach the caller's list."""
        colors = [Colors.RED]

        theme = Theme(colors)
        theme.add_color(Colors.BLUE)

        assert len(colors) == 1
        assert len(theme) == 2

    def test_constructor_does_not_alias_the_caller_list(self) -> None:
        """Appending to the caller's list must not reach the Theme."""
        colors = [Colors.RED]

        theme = Theme(colors)
        colors.append(Colors.GREEN)

        assert len(theme) == 1


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


class TestThemeDisposition:
    """Tests for the optional disposition attributes."""

    def test_disposition_defaults_none(self) -> None:
        """No-keyword construction stays additive: both default None."""
        theme = Theme([Colors.RED])

        assert theme.disposition is None
        assert theme.replaced_by is None

    def test_disposition_kwarg_stored(self) -> None:
        """disposition is stored; replaced_by stays None when not given."""
        theme = Theme([Colors.RED], disposition="library-only")

        assert theme.disposition == "library-only"
        assert theme.replaced_by is None

    def test_palette_equals_ignores_disposition(self) -> None:
        """Equal palettes with differing dispositions still match."""
        a = Theme([Colors.RED, Colors.GREEN], disposition="deprecated")
        b = Theme([Colors.GREEN, Colors.RED], disposition="lifx-app")

        assert a.palette_equals(b)

    def test_hashable_and_identity_equality_unchanged(self) -> None:
        """hash() works and == stays identity with both fields set."""
        a = Theme([Colors.RED], disposition="deprecated", replaced_by="x")
        b = Theme([Colors.RED], disposition="deprecated", replaced_by="x")

        assert isinstance(hash(a), int)
        assert a == a
        assert a != b


class TestThemePaletteEquals:
    """Tests for the explicit palette multiset comparison."""

    def test_same_colors_different_order_match(self) -> None:
        """Palettes with the same colours in different orders match."""
        a = Theme([Colors.RED, Colors.GREEN, Colors.BLUE])
        b = Theme([Colors.BLUE, Colors.RED, Colors.GREEN])

        assert a.palette_equals(b)

    def test_different_duplicate_counts_do_not_match(self) -> None:
        """Palettes differing only in duplicate counts do not match."""
        a = Theme([Colors.RED, Colors.RED, Colors.GREEN])
        b = Theme([Colors.RED, Colors.GREEN, Colors.GREEN])

        assert not a.palette_equals(b)

    def test_multiset_not_set(self) -> None:
        """Same distinct colour set but different multiplicities does not match."""
        a = Theme([Colors.RED, Colors.RED])
        b = Theme([Colors.RED])

        assert not a.palette_equals(b)

    def test_identity_ignored(self) -> None:
        """A library theme and a caller-built theme match on palette alone."""
        library_theme = ThemeLibrary.get("evening")
        caller_theme = Theme(list(library_theme.colors))

        assert caller_theme.slug is None
        assert library_theme.palette_equals(caller_theme)

    def test_distinct_themes_with_identical_palettes_match(self) -> None:
        """Themes with different identities over one palette match.

        Identity is excluded, so two themes that differ in every identity
        field but share their colours compare equal on palette alone.
        """
        colors = list(ThemeLibrary.get("evening").colors)
        a = Theme(colors, slug="a", name="A", category="Moods")
        b = Theme(list(reversed(colors)), slug="b", name="B", category="Play")

        assert a.palette_equals(b)

    def test_different_palettes_do_not_match(self) -> None:
        """Themes with different palettes do not match."""
        a = Theme([Colors.RED])
        b = Theme([Colors.GREEN])

        assert not a.palette_equals(b)

    def test_non_theme_argument_raises(self) -> None:
        """A non-Theme argument is a caller error, not a silent False."""
        theme = Theme([Colors.RED])

        with pytest.raises(TypeError, match="expects a Theme, got int"):
            theme.palette_equals(3)  # type: ignore[arg-type]


class TestThemeEquality:
    """Tests for identity ``==`` and hashability.

    ``==`` deliberately stays identity comparison. A Theme's palette is
    mutable via ``add_color()``, so value equality could not be paired
    with a stable ``__hash__`` — defining ``__eq__`` alone would make
    Theme unhashable, breaking ``set(themes)``, ``{theme: config}`` and
    ``functools.lru_cache`` over a Theme argument for every downstream
    caller. Palette comparison is spelled ``palette_equals()`` instead.
    """

    def test_distinct_instances_with_same_palette_are_unequal(self) -> None:
        """Two Themes over one palette are distinct objects, so ``!=``."""
        a = Theme([Colors.RED, Colors.GREEN])
        b = Theme([Colors.RED, Colors.GREEN])

        assert a != b
        assert a == a
        assert a.palette_equals(b)

    def test_non_theme_comparison_false_without_raising(self) -> None:
        """Comparing a Theme with a non-Theme is False, never an exception."""
        theme = Theme([Colors.RED])

        assert (theme == 3) is False
        assert (theme != 3) is True
        assert theme != object()

    def test_hashable(self) -> None:
        """hash(theme) works: Theme keeps the inherited identity hash."""
        theme = Theme([Colors.RED])

        assert isinstance(hash(theme), int)
        assert Theme.__hash__ is not None

    def test_usable_as_dict_key_and_set_member(self) -> None:
        """The container use cases an unhashable Theme would break."""
        a = Theme([Colors.RED])
        b = Theme([Colors.GREEN])

        assert len({a, b}) == 2
        assert {a: "first", b: "second"}[a] == "first"

    def test_list_membership_is_identity(self) -> None:
        """``in``/``index``/``remove`` match the object, not the palette."""
        a = Theme([Colors.RED])
        same_palette = Theme([Colors.RED])
        themes = [a]

        assert a in themes
        assert same_palette not in themes

    def test_existing_behaviour_unchanged(self) -> None:
        """Iteration, indexing, len() and add_color() behave exactly as before."""
        theme = Theme([Colors.RED, Colors.GREEN])

        assert len(theme) == 2
        assert theme[0] == Colors.RED
        assert list(theme) == [Colors.RED, Colors.GREEN]

        theme.add_color(Colors.BLUE)
        assert len(theme) == 3


class TestPaletteThemes:
    """Every key ported from pkivolowitz/lifx still resolves.

    Some of these keys now return an app theme or a rename alias rather
    than the ported palette, so only the key itself is asserted here; the
    palettes are checked against the source data in ``test_data_parity``
    (attribution in ``lifx/theme/library.py``).
    """

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

    def test_palette_names_dont_collide_with_existing(self) -> None:
        """Palette names should not collide with existing themes."""
        all_names = ThemeLibrary.get_available_themes()
        assert len(all_names) == len(set(all_names))


class TestThemeEffectModesAndTags:
    """Effect modes and tags on Theme."""

    def test_defaults_for_a_caller_theme(self) -> None:
        theme = Theme([Colors.RED])

        assert theme.static_mode is None
        assert theme.dynamic_mode is None
        assert theme.tags == ()

    def test_fields_are_stored(self) -> None:
        theme = Theme(
            [Colors.RED],
            static_mode="grid_static",
            dynamic_mode="morph",
            tags=["Calm", "Blue"],
        )

        assert theme.static_mode == "grid_static"
        assert theme.dynamic_mode == "morph"
        assert theme.tags == ("Calm", "Blue")

    @pytest.mark.parametrize("field", ["static_mode", "dynamic_mode"])
    @pytest.mark.parametrize("value", ["Blended", "grid-static", ""])
    def test_a_malformed_mode_raises(self, field: str, value: str) -> None:
        with pytest.raises(ValueError, match=f"{field} .* is not a canonical"):
            Theme([Colors.RED], **{field: value})

    def test_a_bare_string_for_tags_raises(self) -> None:
        with pytest.raises(TypeError, match="not a single string"):
            Theme([Colors.RED], tags="Calm")

    @pytest.mark.parametrize("tags", [[1, 2], ["Calm", None], [b"Calm"]])
    def test_non_string_tags_raise(self, tags: list[object]) -> None:
        with pytest.raises(TypeError, match="only strings"):
            Theme([Colors.RED], tags=tags)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("static_mode", "dynamic_mode", "expected"),
        [
            (None, None, "morph"),
            ("blended", None, "morph"),
            ("grid_static", None, "move"),
            ("solid_loop", None, "move"),
            ("blended", "twinkle", "twinkle"),
            ("grid_static", "morph", "morph"),
        ],
    )
    def test_resolved_dynamic_mode(
        self, static_mode: str | None, dynamic_mode: str | None, expected: str
    ) -> None:
        theme = Theme([Colors.RED], static_mode=static_mode, dynamic_mode=dynamic_mode)

        assert theme.resolved_dynamic_mode == expected

    def test_shuffled_drops_modes_and_tags(self) -> None:
        theme = Theme(
            [Colors.RED, Colors.BLUE],
            static_mode="grid_static",
            dynamic_mode="move",
            tags=["Calm"],
        )

        shuffled = theme.shuffled()

        assert shuffled.static_mode is None
        assert shuffled.dynamic_mode is None
        assert shuffled.tags == ()

    def test_palette_equals_ignores_modes_and_tags(self) -> None:
        a = Theme([Colors.RED], static_mode="grid_static", tags=["Calm"])
        b = Theme([Colors.RED])

        assert a.palette_equals(b)


class TestModeTypeExports:
    """The generated mode types are part of the public theme API."""

    def test_mode_types_are_exported(self) -> None:
        assert "StaticMode" in lifx.theme.__all__
        assert "DynamicMode" in lifx.theme.__all__
        assert "blended" in get_args(StaticMode)
        assert {"morph", "move"} <= set(get_args(DynamicMode))


def test_caller_constructed_theme_has_no_unicode_name() -> None:
    assert Theme().unicode_name is None
    assert Theme(name="Mine", unicode_name="M\u00efne").unicode_name == "M\u00efne"
