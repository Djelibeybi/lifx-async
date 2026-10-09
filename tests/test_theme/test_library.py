"""Tests for the theme library."""

from __future__ import annotations

from collections import Counter

import pytest

from lifx.color import HSBK
from lifx.const import KELVIN_SATURATED, MAX_KELVIN, MIN_KELVIN
from lifx.theme import Theme, ThemeLibrary, get_theme
from lifx.theme.data import THEMES, ThemeRecord
from lifx.theme.slug import derive_slug
from tests.test_theme.conftest import SOURCE_ALIASES, SOURCE_RECORDS

# Every key the pre-6.3.0 hand-written library resolved, captured as a
# LITERAL fixture (measured 2026-08-14) so an empty or incorrect derivation
# of the new library cannot vacuously pass.
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

# Read from the source data: LIFX add and remove app categories, and the
# library follows them on the next resync.
LIBRARY_CATEGORIES = frozenset(record["category"] for record in SOURCE_RECORDS)

# Any current app theme that is not also a pre-6.3.0 key.
APP_SLUG = next(
    record["slug"]
    for record in SOURCE_RECORDS
    if record["disposition"] == "lifx-app" and record["slug"] not in PRE_V12_KEYS
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
        assert len(evening_theme) > 0

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
        """Test that the listing is non-empty (no count pin)."""
        themes = ThemeLibrary.get_available_themes()
        assert len(themes) > 0


class EmptyLibrary(ThemeLibrary):
    """A ThemeLibrary subclass rebinding _THEMES to nothing.

    The class comment on ThemeLibrary._THEMES documents subclass rebinding
    as a supported seam; this exercises the empty edge of every lookup.
    """

    _THEMES: dict[str, ThemeRecord] = {}


class TestGetCategories:
    """Tests for ThemeLibrary.get_categories()."""

    def test_empty_library_returns_empty_list(self) -> None:
        """A library with no records has no categories."""
        assert EmptyLibrary.get_categories() == []

    def test_empty_library_lookup_raises_unknown(self) -> None:
        """get_by_category() on an empty library raises the unknown error."""
        with pytest.raises(ValueError, match="Available categories"):
            EmptyLibrary.get_by_category("anything")

    def test_empty_library_never_returns_empty_dict(self) -> None:
        """A library with no records raises for every name, never returns {}.

        An empty dict reads as "this category exists and has no themes",
        which is never true here: the category does not exist.
        """
        for category in ("Holidays", "holiday", ""):
            with pytest.raises(ValueError, match="not recognised"):
                EmptyLibrary.get_by_category(category)


class TestThemeLibraryGetByCategory:
    """Tests for ThemeLibrary.get_by_category() over the app taxonomy."""

    def test_every_record_reachable_by_its_own_category(self) -> None:
        """record.slug is a key of get_by_category(record.category) for all names.

        Membership is asserted by slug key, never by Theme object equality,
        because Theme ``==`` is identity. The lookup is hoisted per
        category rather than per record, since every record in a category
        would otherwise repeat the same answer.

        Rename aliases are excluded: they are a theme's dead key, not a
        theme, so listing one in its target's category would show that
        theme twice. Their reachability is asserted through ``replaced_by``
        in ``TestRenameAliases`` instead.
        """
        by_category = {
            category: ThemeLibrary.get_by_category(category)
            for category in ThemeLibrary.get_categories()
        }

        for record in THEMES.values():
            if record.disposition == "renamed":
                continue
            assert record.slug in by_category[record.category]

    @pytest.mark.parametrize("category", sorted(LIBRARY_CATEGORIES))
    def test_keyed_and_sorted_by_slug(self, category: str) -> None:
        """The returned dict is keyed and sorted by slug."""
        themes = ThemeLibrary.get_by_category(category)

        assert list(themes) == sorted(themes)
        assert all(theme.slug == slug for slug, theme in themes.items())

    def test_normalised_forms_agree(self) -> None:
        """Both sides pass through the same slug normalisation rule."""
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
        """'' falls through to the unknown-category error."""
        with pytest.raises(ValueError) as exc_info:
            ThemeLibrary.get_by_category("")

        message = str(exc_info.value)
        assert "Available categories" in message
        assert "Archives" in message
        assert "replacement" not in message

    @pytest.mark.parametrize("category", [None, 123, ["Holidays"]])
    def test_non_string_raises_value_error(self, category: object) -> None:
        """A non-string argument raises ValueError, not AttributeError.

        The slug rule calls str methods, so an unguarded non-string would
        surface as an AttributeError from inside the library and read as a
        bug rather than a bad argument.
        """
        with pytest.raises(ValueError, match="must be a string"):
            ThemeLibrary.get_by_category(category)  # pyright: ignore[reportArgumentType]

    def test_results_carry_disposition(self) -> None:
        """get() threading survives the rewrite — a Library result has a fate."""
        library_themes = ThemeLibrary.get_by_category("Library")

        assert library_themes["hygge"].disposition is not None


class TestRetiredCategoryNames:
    """The 6 pre-6.4.0 category names are gone, with no shim.

    The old hand-made taxonomy (``seasonal``, ``holiday``, ``mood``,
    ``ambient``, ``functional``, ``atmosphere``) never matched the data:
    no name mapped 1:1 to an app category, and only ``holiday`` and
    ``mood`` were ever shown in the published docs, on a page that told
    readers to use ``Theme.category`` instead. Rather than redirect six
    names to categories holding as little as 0/2 of what each returned,
    they are unrecognised and the error lists what does exist.
    """

    @pytest.mark.parametrize(
        "retired",
        ["seasonal", "holiday", "mood", "ambient", "functional", "atmosphere"],
    )
    def test_retired_name_is_unrecognised(self, retired: str) -> None:
        """Each retired name raises the generic unknown-category error."""
        with pytest.raises(ValueError) as exc_info:
            ThemeLibrary.get_by_category(retired)

        message = str(exc_info.value)
        assert retired in message
        assert "not recognised" in message
        assert "Available categories" in message

    def test_retired_names_do_not_shadow_a_live_category(self) -> None:
        """No live category normalises onto a retired name.

        A category named "Mood" or "Holiday" would resolve one of these
        and quietly reintroduce the old spelling as a supported argument.
        """
        live = {derive_slug(category) for category in ThemeLibrary.get_categories()}
        retired = {
            "seasonal",
            "holiday",
            "mood",
            "ambient",
            "functional",
            "atmosphere",
        }

        assert live.isdisjoint(retired)


class TestRenameAliases:
    """Every rename-alias key reports the rename rather than inheriting."""

    @pytest.mark.parametrize(("alias", "target"), SOURCE_ALIASES)
    def test_alias_reports_renamed_and_names_its_target(
        self, alias: str, target: str
    ) -> None:
        """An alias carries disposition 'renamed' and its live key.

        Before this, an alias bound the target's own record, so the only
        keys whose name actually changed were the ones reporting a clean
        ``lifx-app`` fate with no successor: a migration audit keying off
        ``replaced_by`` saw nothing to do.
        """
        theme = ThemeLibrary.get(alias)

        assert theme.slug == alias
        assert theme.disposition == "renamed"
        assert theme.replaced_by == target

    @pytest.mark.parametrize(("alias", "target"), SOURCE_ALIASES)
    def test_following_replaced_by_reaches_the_live_theme(
        self, alias: str, target: str
    ) -> None:
        """One hop along replaced_by lands on the theme, which terminates."""
        theme = ThemeLibrary.get(alias)
        successor = ThemeLibrary.get(theme.replaced_by or "")

        assert successor.slug == target
        assert successor.replaced_by is None
        assert successor.disposition != "renamed"
        assert theme.palette_equals(successor)

    @pytest.mark.parametrize(("alias", "target"), SOURCE_ALIASES)
    def test_alias_absent_from_its_category_listing(
        self, alias: str, target: str
    ) -> None:
        """A category lists the theme once, under its live slug only."""
        listing = ThemeLibrary.get_by_category(ThemeLibrary.get(alias).category)

        assert target in listing
        assert alias not in listing


class TestGetThemeConvenienceFunction:
    """Tests for the get_theme() convenience function."""

    def test_get_theme_basic(self) -> None:
        """Test getting a theme using convenience function."""
        evening = get_theme("evening")
        assert isinstance(evening, Theme)
        assert len(evening) > 0

    def test_get_theme_is_equivalent_to_library(self) -> None:
        """Test that get_theme() is equivalent to ThemeLibrary.get()."""
        evening1 = get_theme("evening")
        evening2 = ThemeLibrary.get("evening")

        assert len(evening1) == len(evening2)

    def test_get_theme_invalid(self) -> None:
        """Test that invalid theme raises KeyError."""
        with pytest.raises(KeyError):
            get_theme("nonexistent")


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


class TestPreV12Compatibility:
    """Every pre-6.3.0 theme name still resolves."""

    @pytest.mark.parametrize("key", PRE_V12_KEYS)
    def test_pre_v12_key_resolves(self, key: str) -> None:
        """Every pre-6.3.0 key resolves without raising."""
        theme = ThemeLibrary.get(key)
        assert isinstance(theme, Theme)
        assert len(theme) >= 1

    def test_no_legacy_suffixed_key(self) -> None:
        """No key ends with the retired legacy suffix."""
        for name in ThemeLibrary.get_available_themes():
            assert not name.endswith("_legacy")


class TestRenamePairs:
    """Renamed themes answer to both names, with the old key carrying the

    target's palette, display name and category but its own slug, the one
    piece of identity that actually changed.
    """

    @pytest.mark.parametrize(("alias", "target"), SOURCE_ALIASES)
    def test_alias_resolves_to_target(self, alias: str, target: str) -> None:
        """The old key returns the target's palette under its own slug."""
        old = ThemeLibrary.get(alias)
        new = ThemeLibrary.get(target)

        assert _palette_multiset(old) == _palette_multiset(new)
        assert old.slug == alias
        assert old.name == new.name
        assert old.category == new.category


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
    """The shortened KeyError."""

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
    """Invariant sweeps over the runtime listing."""

    def test_every_key_is_identifier(self) -> None:
        """Every key in get_available_themes() passes str.isidentifier()."""
        for name in ThemeLibrary.get_available_themes():
            assert name.isidentifier()

    def test_every_listed_key_resolves(self) -> None:
        """The listing names exactly what get() accepts."""
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
        """Every theme's category is one the source data declares."""
        for key in ThemeLibrary.get_available_themes():
            assert ThemeLibrary.get(key).category in LIBRARY_CATEGORIES


class TestDispositionSurfacing:
    """Dispositions surface on get() and the shipped data holds its shape

    invariants (shape sweeps, never count pins).
    """

    def test_every_disposition_is_allowed(self) -> None:
        """Every shipped record's disposition is one of the four values."""
        allowed = {"lifx-app", "library-only", "deprecated", "renamed"}
        for record in THEMES.values():
            assert record.disposition in allowed, record.slug

    def test_replaced_by_only_where_a_successor_exists(self) -> None:
        """Only a deprecated or renamed record carries a replaced_by.

        Both directions are enforced at generation time: a deprecated
        record without a successor aborts, and an authored record that is
        not deprecated may not carry one at all. Renamed records are
        synthesised by the generator, never authored, and always carry
        their target. This sweep pins the shipped result.
        """
        for record in THEMES.values():
            if record.disposition in ("deprecated", "renamed"):
                assert record.replaced_by is not None, record.slug
            else:
                assert record.replaced_by is None, record.slug

    def test_every_replaced_by_resolves(self) -> None:
        """Every non-None replaced_by resolves as a key of THEMES."""
        for record in THEMES.values():
            if record.replaced_by is not None:
                assert record.replaced_by in THEMES, record.slug

    def test_alias_is_its_own_record_sharing_the_palette(self) -> None:
        """Each alias is a distinct record over the target's palette.

        A shared record would make the alias report the target's fate, so
        the two keys whose name actually changed would be the only ones
        claiming nothing changed. The palette object is still shared, so
        the two keys cannot drift apart.
        """
        for alias, target in SOURCE_ALIASES:
            assert THEMES[alias] is not THEMES[target]
            assert THEMES[alias].colors is THEMES[target].colors


class TestNewSlugBehaviour:
    """House-style behaviours over the new app slugs."""

    def test_get_case_insensitive_for_app_slug(self) -> None:
        """get() keeps lowercasing its input for a new app slug."""
        theme = ThemeLibrary.get(APP_SLUG.upper())
        assert theme.slug == APP_SLUG

    def test_consecutive_gets_carry_the_same_palette(self) -> None:
        """Two gets of one slug are distinct objects over one palette."""
        first = ThemeLibrary.get(APP_SLUG)
        second = ThemeLibrary.get(APP_SLUG)

        assert first is not second
        assert first.palette_equals(second)


class TestEffectModesOnGet:
    """ThemeLibrary.get() carries a record's modes and tags."""

    def test_library_theme_always_has_a_static_mode(self) -> None:
        for key in ThemeLibrary.get_available_themes():
            assert ThemeLibrary.get(key).static_mode is not None, key

    def test_get_passes_the_record_fields_through(self) -> None:
        for key, record in THEMES.items():
            theme = ThemeLibrary.get(key)
            assert theme.static_mode == record.static_mode, key
            assert theme.dynamic_mode == record.dynamic_mode, key
            assert theme.tags == record.tags, key


_BLUE = (HSBK(hue=210, saturation=1.0, brightness=1.0, kelvin=3500),)


class AccentedLibrary(ThemeLibrary):
    """A synthetic library with one accented theme and one plain theme."""

    _THEMES: dict[str, ThemeRecord] = {
        "curacao": ThemeRecord(
            slug="curacao",
            name="Curacao",
            unicode_name="Cura\u00e7ao",
            category="Worldly",
            disposition="lifx-app",
            colors=_BLUE,
            static_mode="blended",
        ),
        "plain": ThemeRecord(
            slug="plain",
            name="Plain",
            category="Library",
            disposition="library-only",
            colors=_BLUE,
            static_mode="blended",
        ),
    }


class TestUnicodeName:
    """Theme.unicode_name is the stored spelling, else the ASCII name."""

    def test_accented_theme_reports_its_unicode_name(self) -> None:
        theme = AccentedLibrary.get("curacao")
        assert theme.unicode_name == "Cura\u00e7ao"
        assert theme.name == "Curacao"

    def test_plain_theme_falls_back_to_name(self) -> None:
        assert AccentedLibrary.get("plain").unicode_name == "Plain"

    def test_shipped_themes_always_have_a_display_string(self) -> None:
        for slug in ThemeLibrary.get_available_themes():
            theme = ThemeLibrary.get(slug)
            assert theme.unicode_name


class TaggedLibrary(ThemeLibrary):
    """A synthetic library with tags, modes and a tagged rename alias."""

    _THEMES: dict[str, ThemeRecord] = {
        "calm_sea": ThemeRecord(
            slug="calm_sea",
            name="Calm Sea",
            category="Moods",
            disposition="lifx-app",
            colors=_BLUE,
            static_mode="blended",
            tags=("Blue", "Calm"),
        ),
        "date_night": ThemeRecord(
            slug="date_night",
            name="Date Night",
            category="Moods",
            disposition="lifx-app",
            colors=_BLUE,
            static_mode="blended",
            dynamic_mode="morph",
            tags=("Date night", "Romantic"),
        ),
        "grid_art": ThemeRecord(
            slug="grid_art",
            name="Grid Art",
            category="Art Series",
            disposition="lifx-app",
            colors=_BLUE,
            static_mode="grid_static",
            tags=("Multicolour",),
        ),
        "plain": ThemeRecord(
            slug="plain",
            name="Plain",
            category="Library",
            disposition="library-only",
            colors=_BLUE,
            static_mode="blended",
        ),
        "old_calm": ThemeRecord(
            slug="old_calm",
            name="Calm Sea",
            category="Moods",
            disposition="renamed",
            colors=_BLUE,
            static_mode="blended",
            tags=("Blue", "Calm"),
            replaced_by="calm_sea",
        ),
    }


class TestTagDiscovery:
    """get_tags() and get_by_tag()."""

    def test_get_tags_lists_every_tag_case_insensitively(self) -> None:
        assert TaggedLibrary.get_tags() == [
            "Blue",
            "Calm",
            "Date night",
            "Multicolour",
            "Romantic",
        ]

    def test_get_tags_on_an_empty_library(self) -> None:
        assert EmptyLibrary.get_tags() == []

    def test_unknown_tag_on_an_empty_library_says_none(self) -> None:
        with pytest.raises(ValueError, match=r"Available tags: \(none\)$"):
            EmptyLibrary.get_by_tag("calm")

    def test_non_string_tag_on_an_empty_library_says_none(self) -> None:
        with pytest.raises(ValueError, match=r"Available tags: \(none\)$"):
            EmptyLibrary.get_by_tag(3)  # type: ignore[arg-type]

    def test_unknown_static_mode_on_an_empty_library_says_none(self) -> None:
        with pytest.raises(ValueError, match=r"Available static modes: \(none\)$"):
            EmptyLibrary.find(static_mode="blended")

    @pytest.mark.parametrize(
        "tag", ["Date night", "date night", "DATE NIGHT", "date_night"]
    )
    def test_get_by_tag_matches_normalised(self, tag: str) -> None:
        themes = TaggedLibrary.get_by_tag(tag)

        assert list(themes) == ["date_night"]
        assert themes["date_night"].tags == ("Date night", "Romantic")
        assert themes["date_night"].dynamic_mode == "morph"

    def test_get_by_tag_excludes_rename_aliases(self) -> None:
        assert list(TaggedLibrary.get_by_tag("Calm")) == ["calm_sea"]

    def test_get_by_tag_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="'Spooky' is not recognised.*Blue"):
            TaggedLibrary.get_by_tag("Spooky")

    def test_get_by_tag_non_string_raises(self) -> None:
        with pytest.raises(ValueError, match="Tag must be a string, got int"):
            TaggedLibrary.get_by_tag(3)  # type: ignore[arg-type]


class TestFind:
    """ThemeLibrary.find()."""

    def test_no_criteria_returns_every_non_alias_theme(self) -> None:
        assert list(TaggedLibrary.find()) == [
            "calm_sea",
            "date_night",
            "grid_art",
            "plain",
        ]

    def test_tags_all(self) -> None:
        assert list(TaggedLibrary.find(tags=["Calm", "Blue"])) == ["calm_sea"]
        assert TaggedLibrary.find(tags=["Calm", "Romantic"]) == {}

    def test_tags_any(self) -> None:
        found = TaggedLibrary.find(tags=["Calm", "Romantic"], match="any")

        assert list(found) == ["calm_sea", "date_night"]

    def test_empty_tags_with_any_selects_everything(self) -> None:
        assert len(TaggedLibrary.find(tags=(), match="any")) == 4

    def test_category_is_normalised(self) -> None:
        assert list(TaggedLibrary.find(category="art series")) == ["grid_art"]

    def test_static_mode(self) -> None:
        assert list(TaggedLibrary.find(static_mode="grid_static")) == ["grid_art"]

    def test_criteria_combine_with_and(self) -> None:
        found = TaggedLibrary.find(
            tags=["Calm", "Multicolour"],
            match="any",
            category="Moods",
            static_mode="blended",
        )

        assert list(found) == ["calm_sea"]

    def test_a_bare_string_for_tags_raises(self) -> None:
        with pytest.raises(TypeError, match="not a single string"):
            TaggedLibrary.find(tags="Calm")

    def test_unknown_tag_raises(self) -> None:
        with pytest.raises(ValueError, match="'Spooky' is not recognised"):
            TaggedLibrary.find(tags=["Spooky"])

    def test_unknown_category_raises(self) -> None:
        with pytest.raises(ValueError, match="Category 'Sport' is not recognised"):
            TaggedLibrary.find(category="Sport")

    def test_unknown_static_mode_raises(self) -> None:
        with pytest.raises(
            ValueError, match="'solid' is not recognised.*blended, grid_static"
        ):
            TaggedLibrary.find(static_mode="solid")

    def test_invalid_match_raises(self) -> None:
        with pytest.raises(ValueError, match="match must be 'all' or 'any'"):
            TaggedLibrary.find(tags=["Calm"], match="some")  # type: ignore[arg-type]

    def test_get_by_category_behaviour_is_unchanged(self) -> None:
        assert list(TaggedLibrary.get_by_category("moods")) == [
            "calm_sea",
            "date_night",
        ]
        with pytest.raises(ValueError, match="Category must be a string"):
            TaggedLibrary.get_by_category(3)  # type: ignore[arg-type]
