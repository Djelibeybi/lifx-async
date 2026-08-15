"""Tests for the theme library."""

from __future__ import annotations

from collections import Counter

import pytest

from lifx.const import KELVIN_SATURATED, MAX_KELVIN, MIN_KELVIN
from lifx.theme import Theme, ThemeLibrary, get_theme
from lifx.theme.data import THEMES, ThemeRecord
from lifx.theme.library import _LEGACY_CATEGORIES

# Every key the pre-6.3.0 hand-written library resolved, captured as a
# LITERAL fixture (measured 2026-08-14) so an empty or incorrect derivation
# of the new library cannot vacuously pass (COMPAT-01 empty edge).
PRE_V12_KEYS = (
    "arctic",
    "aurora_borealis",
    "autumn",
    "bias_lighting",
    "blissful",
    "calaveras",
    "cheerful",
    "cherry_blossom",
    "christmas",
    "coral_reef",
    "cyberpunk",
    "deep_sea",
    "desert",
    "dream",
    "earth",
    "energizing",
    "epic",
    "evening",
    "exciting",
    "fantasy",
    "fire",
    "focusing",
    "forest",
    "galaxy",
    "gentle",
    "halloween",
    "hanukkah",
    "holly",
    "hygge",
    "independence",
    "intense",
    "kwanzaa",
    "love",
    "mellow",
    "neon",
    "party",
    "peaceful",
    "powerful",
    "proud",
    "pumpkin",
    "relaxing",
    "romance",
    "santa",
    "serene",
    "shamrock",
    "soothing",
    "spacey",
    "sports",
    "spring",
    "stardust",
    "thanksgiving",
    "tranquil",
    "tropical",
    "vaporwave",
    "warming",
    "water",
    "zombie",
)

# The app's 8 categories (D-10) plus Library for the pre-6.3.0 orphans.
LIBRARY_CATEGORIES = frozenset(
    {
        "Moods",
        "Art Series",
        "Music",
        "Nature",
        "Space",
        "Play",
        "Holidays",
        "Archives",
        "Library",
    }
)


def _palette_multiset(theme: Theme) -> Counter[tuple[int, int, int, int]]:
    """Unordered palette multiset at protocol (uint16) precision."""
    return Counter(color.as_tuple() for color in theme.colors)


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
        assert "get_available_themes" in str(exc_info.value)

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
        themes_to_test = ["christmas", "halloween", "evening", "relaxing", "dream"]

        for theme_name in themes_to_test:
            theme = ThemeLibrary.get(theme_name)
            assert len(theme) >= 1
            assert theme.slug == theme_name
            assert theme.name is not None
            assert theme.category is not None


class TestThemeLibraryList:
    """Tests for ThemeLibrary.get_available_themes() method."""

    def test_list_returns_sorted_list(self) -> None:
        """Test that get_available_themes() returns a sorted list of theme names."""
        themes = ThemeLibrary.get_available_themes()

        assert isinstance(themes, list)
        assert len(themes) > 0
        assert themes == sorted(themes)  # Should be sorted

    def test_list_contains_well_known_themes(self) -> None:
        """Test that list includes well-known themes."""
        themes = ThemeLibrary.get_available_themes()
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
        """Test that the listing is non-empty (no count pin, D-23)."""
        themes = ThemeLibrary.get_available_themes()
        assert len(themes) > 0


class TestGetCategories:
    """Tests for ThemeLibrary.get_categories() (SPEC R1)."""

    def test_exact_sorted_list(self) -> None:
        """Exactly the 9 category names, plain codepoint-sorted."""
        assert ThemeLibrary.get_categories() == [
            "Archives",
            "Art Series",
            "Holidays",
            "Library",
            "Moods",
            "Music",
            "Nature",
            "Play",
            "Space",
        ]

    def test_empty_library_returns_empty_list(self) -> None:
        """A library with no records has no categories (SPEC R1 empty edge)."""

        class EmptyLibrary(ThemeLibrary):
            _THEMES: dict[str, ThemeRecord] = {}

        assert EmptyLibrary.get_categories() == []

    def test_empty_library_lookup_raises_unknown(self) -> None:
        """get_by_category() on an empty library raises the unknown error."""

        class EmptyLibrary(ThemeLibrary):
            _THEMES: dict[str, ThemeRecord] = {}

        with pytest.raises(ValueError, match="Available categories"):
            EmptyLibrary.get_by_category("anything")


class TestThemeLibraryGetByCategory:
    """Tests for ThemeLibrary.get_by_category() over the app taxonomy (SPEC R2)."""

    def test_every_record_reachable_by_its_own_category(self) -> None:
        """record.slug is a key of get_by_category(record.category) for all names.

        Membership is asserted by slug key, never by Theme object equality,
        because Theme ``==`` is identity (WR-02 closure sweep).
        """
        for record in THEMES.values():
            assert record.slug in ThemeLibrary.get_by_category(record.category)

    def test_holidays_count_and_slug_sorted(self) -> None:
        """Holidays has 15 themes; the returned dict is keyed and sorted by slug."""
        holidays = ThemeLibrary.get_by_category("Holidays")

        assert len(holidays) == 15
        assert list(holidays) == sorted(holidays)
        assert all(theme.slug == slug for slug, theme in holidays.items())

    def test_normalised_forms_agree(self) -> None:
        """Both sides pass through the D-09 slug rule (SPEC R2 encoding edge)."""
        canonical = ThemeLibrary.get_by_category("Art Series").keys()

        assert ThemeLibrary.get_by_category("art_series").keys() == canonical
        assert ThemeLibrary.get_by_category("ART SERIES").keys() == canonical

    def test_concatenated_form_raises(self) -> None:
        """'artseries' is not a normalised form of 'Art Series' and raises."""
        with pytest.raises(ValueError, match="artseries"):
            ThemeLibrary.get_by_category("artseries")

    def test_unknown_category_lists_available(self) -> None:
        """An unknown category raises ValueError listing the categories."""
        with pytest.raises(ValueError) as exc_info:
            ThemeLibrary.get_by_category("invalid")

        message = str(exc_info.value)
        assert "invalid" in message
        assert "not recognised" in message
        assert "Available categories" in message
        assert "Archives" in message

    def test_empty_string_gets_generic_error(self) -> None:
        """'' falls through to the unknown-category error (SPEC R3 empty edge)."""
        with pytest.raises(ValueError) as exc_info:
            ThemeLibrary.get_by_category("")

        message = str(exc_info.value)
        assert "Available categories" in message
        assert "Archives" in message
        assert "replacement" not in message

    def test_results_carry_disposition(self) -> None:
        """get() threading survives the rewrite — a Library result has a fate."""
        library_themes = ThemeLibrary.get_by_category("Library")

        assert library_themes["hygge"].disposition is not None


class TestLegacyCategoryNames:
    """The 6 pre-6.3.0 category names have their locked fates (SPEC R3)."""

    def test_holiday_resolves_to_holidays(self) -> None:
        """'holiday' returns the 15 Holidays themes."""
        holiday = ThemeLibrary.get_by_category("holiday")

        assert len(holiday) == 15
        assert all(theme.category == "Holidays" for theme in holiday.values())
        assert holiday.keys() == ThemeLibrary.get_by_category("Holidays").keys()

    def test_mood_resolves_to_moods(self) -> None:
        """'mood' returns the 13 Moods themes."""
        mood = ThemeLibrary.get_by_category("mood")

        assert len(mood) == 13
        assert all(theme.category == "Moods" for theme in mood.values())

    def test_legacy_resolve_case_insensitive(self) -> None:
        """'HOLIDAY' behaves identically to 'holiday' (SPEC R3 encoding edge)."""
        assert (
            ThemeLibrary.get_by_category("HOLIDAY").keys()
            == ThemeLibrary.get_by_category("holiday").keys()
        )

    @pytest.mark.parametrize(
        ("legacy", "replacement"),
        [
            ("seasonal", "Nature"),
            ("ambient", "Play"),
            ("functional", "Library"),
            ("atmosphere", "Moods"),
        ],
    )
    def test_retired_names_raise_naming_replacement(
        self, legacy: str, replacement: str
    ) -> None:
        """Each retired name raises ValueError naming its replacement (D-02)."""
        with pytest.raises(ValueError) as exc_info:
            ThemeLibrary.get_by_category(legacy)

        message = str(exc_info.value)
        assert legacy in message
        assert replacement in message
        assert "pre-6.3.0" in message

    def test_every_replacement_is_a_real_category(self) -> None:
        """Every _LEGACY_CATEGORIES replacement names a listable category.

        Guards the shim against future taxonomy drift (review F4): a
        replacement that stops existing would raise a message pointing at
        nothing, and a resolving entry would silently return an empty dict.
        """
        categories = set(ThemeLibrary.get_categories())

        for replacement, _resolves in _LEGACY_CATEGORIES.values():
            assert replacement in categories


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

    def test_christmas_theme_identity(self) -> None:
        """Test that christmas resolves to the app's Holidays record."""
        christmas = ThemeLibrary.get("christmas")

        assert christmas.category == "Holidays"
        assert len(christmas) >= 1

    def test_christmas_theme_colors(self) -> None:
        """Christmas carries green and red.

        A semantic pin, not a count or a full-palette literal: it survives a
        legitimate resync that adds or reorders colours, and fails a
        regeneration that inverts the palette or drops a primary. Without
        it nothing in CI asserts a real colour value — `data.py` is in the
        coverage omit list and the generator suite runs only against
        fixtures (D-23).
        """
        hues = [color.hue for color in ThemeLibrary.get("christmas")]

        assert any(abs(hue - 120) < 5 for hue in hues), hues
        assert any(abs(hue - 0) < 5 for hue in hues), hues

    def test_halloween_theme_resolves(self) -> None:
        """Test that halloween resolves with a non-empty palette."""
        halloween = ThemeLibrary.get("halloween")

        assert halloween.slug == "halloween"
        assert len(halloween) >= 1

    def test_halloween_theme_colors(self) -> None:
        """Halloween carries an orange."""
        hues = [color.hue for color in ThemeLibrary.get("halloween")]

        assert any(30 <= hue <= 35 for hue in hues), hues

    @pytest.mark.parametrize(
        ("slug", "hue_range"),
        [
            ("shamrock", (100, 160)),
            ("hanukkah", (200, 260)),
            ("pumpkin", (15, 45)),
        ],
    )
    def test_category_golden_hue_pins(
        self, slug: str, hue_range: tuple[float, float]
    ) -> None:
        """One golden hue pin per shipped palette family.

        Each asserts the defining colour of a theme whose identity is
        unambiguous — shamrock is green, hanukkah is blue, pumpkin is
        orange — so a data regression that scrambles hues is visible in CI
        rather than reaching users' lights.
        """
        low, high = hue_range
        hues = [color.hue for color in ThemeLibrary.get(slug)]

        assert any(low <= hue <= high for hue in hues), hues

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
        for theme_name in ThemeLibrary.get_available_themes():
            theme = ThemeLibrary.get(theme_name)
            assert isinstance(theme, Theme)
            assert len(theme) > 0

            # All colors should be HSBK-compatible. Kelvin 0 is
            # KELVIN_SATURATED — a legitimate wire value HSBK's own
            # validator accepts alongside the 1500-9000 white-mode range.
            for color in theme:
                assert 0 <= color.hue <= 360
                assert 0 <= color.saturation <= 1.0
                assert 0 <= color.brightness <= 1.0
                assert (
                    color.kelvin == KELVIN_SATURATED
                    or MIN_KELVIN <= color.kelvin <= MAX_KELVIN
                )

    def test_theme_library_has_minimum_themes(self) -> None:
        """Test that library has at least 42 themes."""
        themes = ThemeLibrary.get_available_themes()
        assert len(themes) >= 42


class TestPreV12Compatibility:
    """COMPAT-01: every pre-6.3.0 theme name still resolves."""

    @pytest.mark.parametrize("key", PRE_V12_KEYS)
    def test_pre_v12_key_resolves(self, key: str) -> None:
        """Every pre-6.3.0 key resolves without raising."""
        theme = ThemeLibrary.get(key)
        assert isinstance(theme, Theme)
        assert len(theme) >= 1

    def test_no_legacy_suffixed_key(self) -> None:
        """No key ends with the retired legacy suffix (COMPAT-02 retired)."""
        for name in ThemeLibrary.get_available_themes():
            assert not name.endswith("_legacy")


class TestRenamePairs:
    """COMPAT-03: renamed themes answer to both names with target identity."""

    def test_aurora_borealis_resolves_to_aurora(self) -> None:
        """aurora_borealis returns aurora's palette and identity (D-14)."""
        alias = ThemeLibrary.get("aurora_borealis")
        target = ThemeLibrary.get("aurora")

        assert _palette_multiset(alias) == _palette_multiset(target)
        assert alias.slug == "aurora"
        assert alias.name == "Aurora"
        assert alias.category == "Nature"

    def test_forest_resolves_to_forrest(self) -> None:
        """forest returns forrest's palette and identity (D-14)."""
        alias = ThemeLibrary.get("forest")
        target = ThemeLibrary.get("forrest")

        assert _palette_multiset(alias) == _palette_multiset(target)
        assert alias.slug == "forrest"
        assert alias.name == "Forrest"
        assert alias.category == "Nature"


class TestResyncedPalettes:
    """THEME-03: the resynced shared slugs carry app values."""

    def test_soothing_contains_kelvin_8000(self) -> None:
        """soothing carries kelvin 8000 (pre-6.3.0 was uniformly 3500)."""
        soothing = ThemeLibrary.get("soothing")
        assert 8000 in {color.kelvin for color in soothing}


class TestMutationIsolation:
    """The mutation-leak fix: get() returns a Theme over a fresh list."""

    def test_add_color_does_not_leak_into_library(self) -> None:
        """Mutating a returned Theme leaves the next get() unchanged."""
        first = ThemeLibrary.get("evening")
        original_length = len(first)
        first.add_color(first[0])

        second = ThemeLibrary.get("evening")
        assert len(second) == original_length


class TestKeyErrorMessage:
    """The shortened KeyError (THEME-01 empty edge)."""

    def test_unknown_name_and_pointer_present(self) -> None:
        """The error carries the requested name and the listing pointer."""
        with pytest.raises(KeyError) as exc_info:
            ThemeLibrary.get("no_such_theme")

        message = str(exc_info.value)
        assert "no_such_theme" in message
        assert "get_available_themes" in message

    def test_full_listing_dropped(self) -> None:
        """The error no longer embeds the full theme listing."""
        with pytest.raises(KeyError) as exc_info:
            ThemeLibrary.get("no_such_theme")

        message = str(exc_info.value)
        for name in ThemeLibrary.get_available_themes():
            assert name not in message


class TestLibrarySweeps:
    """Invariant sweeps over the runtime listing (D-15, META-01, META-02)."""

    def test_every_key_is_identifier(self) -> None:
        """Every key in get_available_themes() passes str.isidentifier()."""
        for name in ThemeLibrary.get_available_themes():
            assert name.isidentifier()

    def test_every_listed_key_resolves(self) -> None:
        """The listing names exactly what get() accepts (D-15)."""
        for name in ThemeLibrary.get_available_themes():
            assert isinstance(ThemeLibrary.get(name), Theme)

    def test_identity_metadata_ascii_and_distinct(self) -> None:
        """Every name and category is pure ASCII, non-None and not the slug."""
        for key in ThemeLibrary.get_available_themes():
            theme = ThemeLibrary.get(key)
            assert theme.name is not None
            assert theme.category is not None
            assert theme.name.isascii()
            assert theme.category.isascii()
            assert theme.name != theme.slug
            assert theme.category != theme.slug

    def test_every_category_is_known(self) -> None:
        """Every theme's category is one of the 9 library categories."""
        for key in ThemeLibrary.get_available_themes():
            assert ThemeLibrary.get(key).category in LIBRARY_CATEGORIES

    def test_canonical_palette_order(self) -> None:
        """Every served palette is sorted by its uint16 tuple (D-24)."""
        for key in ThemeLibrary.get_available_themes():
            palette = [color.as_tuple() for color in ThemeLibrary.get(key)]
            assert palette == sorted(palette)


class TestDispositionSurfacing:
    """COMPAT-04: dispositions surface on get() and the shipped data holds
    its shape invariants (shape sweeps, never count pins — D-08/D-23)."""

    def test_fire_is_deprecated_with_replacement(self) -> None:
        """get('fire') carries the SPEC R5 pinned deprecation triple."""
        fire = ThemeLibrary.get("fire")

        assert fire.disposition == "deprecated"
        assert fire.replaced_by == "warm_ember"

    def test_hygge_is_library_only(self) -> None:
        """get('hygge') is library-only with no successor."""
        hygge = ThemeLibrary.get("hygge")

        assert hygge.disposition == "library-only"
        assert hygge.replaced_by is None

    def test_christmas_is_lifx_app(self) -> None:
        """get('christmas') is a lifx-app theme with no successor."""
        christmas = ThemeLibrary.get("christmas")

        assert christmas.disposition == "lifx-app"
        assert christmas.replaced_by is None

    def test_every_disposition_is_allowed(self) -> None:
        """Every shipped record's disposition is one of the three values."""
        allowed = {"lifx-app", "library-only", "deprecated"}
        for record in THEMES.values():
            assert record.disposition in allowed, record.slug

    def test_replaced_by_only_on_deprecated_records(self) -> None:
        """A non-deprecated record never carries a replaced_by (SPEC R5).

        This sweep is the sole enforcement of the invariant: the generator
        deliberately does not reject a replaced_by on a non-deprecated
        record (R2-05, D-08 held), so a bad data edit is caught here at
        test time rather than at generation time.
        """
        for record in THEMES.values():
            if record.disposition != "deprecated":
                assert record.replaced_by is None, record.slug

    def test_every_replaced_by_resolves(self) -> None:
        """Every non-None replaced_by resolves as a key of THEMES."""
        for record in THEMES.values():
            if record.replaced_by is not None:
                assert record.replaced_by in THEMES, record.slug

    def test_alias_identity_survives_new_fields(self) -> None:
        """Both rename aliases still bind their target's own record (R7)."""
        assert THEMES["forest"] is THEMES["forrest"]
        assert THEMES["aurora_borealis"] is THEMES["aurora"]


class TestNewSlugBehaviour:
    """House-style behaviours over the new app slugs."""

    def test_get_case_insensitive_for_app_slug(self) -> None:
        """get() keeps lowercasing its input for a new app slug."""
        theme = ThemeLibrary.get("MONDRIAN")
        assert theme.slug == "mondrian"

    def test_consecutive_gets_carry_the_same_palette(self) -> None:
        """Two gets of one slug are distinct objects over one palette."""
        first = ThemeLibrary.get("mondrian")
        second = ThemeLibrary.get("mondrian")

        assert first is not second
        assert first.palette_equals(second)
