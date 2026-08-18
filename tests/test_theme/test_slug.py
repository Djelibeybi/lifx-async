"""Tests for the shared slug-derivation rule (`lifx.theme.slug`).

The rule was build-time-only until 6.4.0, so its original tests (in
``test_theme_generator.py``) cover only well-formed stored display names.
``ThemeLibrary.get_by_category()`` now feeds it arbitrary caller input, and
this module covers that wider domain: empty and punctuation-only strings,
non-ASCII, and idempotence.
"""

from __future__ import annotations

import pytest

from lifx.theme import ThemeLibrary
from lifx.theme.slug import derive_slug


class TestDeriveSlugDisplayNames:
    """The original domain: stored, ASCII, emoji-stripped display names."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Forrest", "forrest"),
            ("Art Series", "art_series"),
            ("Valentine's", "valentines"),
            ("St Patrick's Day", "st_patricks_day"),
            ("Dance/Pop", "dance_pop"),
            ("  Padded  ", "padded"),
            ("Multi - Punct!", "multi_punct"),
        ],
    )
    def test_derivation(self, name: str, expected: str) -> None:
        """Lowercase, collapse non-alphanumeric runs, strip the edges."""
        assert derive_slug(name) == expected

    def test_every_shipped_name_derives_to_its_slug(self) -> None:
        """The rule reproduces every shipped slug from its display name.

        The generator asserts this per record at build time; asserting it
        against the shipped data proves the runtime copy agrees.
        """
        for name in ThemeLibrary.get_available_themes():
            theme = ThemeLibrary.get(name)
            assert theme.name is not None and theme.slug is not None
            if theme.disposition == "renamed":
                # A rename alias is the theme's former key paired with its
                # current display name, so the rule cannot reproduce it by
                # construction — that mismatch is the rename. The name
                # derives to the successor the alias points at.
                assert derive_slug(theme.name) == theme.replaced_by
                continue
            assert derive_slug(theme.name) == theme.slug


class TestDeriveSlugCallerInput:
    """The domain the rule acquired when get_by_category() started calling it."""

    @pytest.mark.parametrize("value", ["", "_", "___", "!!!", "   ", "-.-"])
    def test_degenerate_input_collapses_to_empty(self, value: str) -> None:
        """Anything with no alphanumeric character derives to the empty slug.

        No category can derive to ``""``, so every one of these falls
        through to the unknown-category error rather than matching.
        """
        assert derive_slug(value) == ""

        with pytest.raises(ValueError, match="not recognised"):
            ThemeLibrary.get_by_category(value)

    def test_idempotent(self) -> None:
        """Re-deriving an already-derived slug is a no-op.

        get_by_category() normalises both sides, so a caller passing a slug
        straight back in must land on the same key.
        """
        for name in ("Art Series", "Moods", "st_patrick_s_day", "  Multi - Punct!  "):
            once = derive_slug(name)
            assert derive_slug(once) == once

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            # Non-ASCII is not transliterated: the character is simply not in
            # [a-z0-9], so it collapses like any other punctuation. The
            # docstring's "over ASCII input" is a precondition, not a check.
            ("Musik", "musik"),
            ("Musik!", "musik"),
            ("Musique Series", "musique_series"),
            ("Ärt Series", "rt_series"),
            ("Müsic", "m_sic"),
        ],
    )
    def test_non_ascii_collapses_rather_than_transliterating(
        self, value: str, expected: str
    ) -> None:
        """A non-ASCII letter is dropped, not folded to its ASCII base."""
        assert derive_slug(value) == expected

    def test_non_ascii_category_does_not_resolve(self) -> None:
        """A non-ASCII spelling of a real category raises, never mismatches."""
        with pytest.raises(ValueError, match="not recognised"):
            ThemeLibrary.get_by_category("Ärt Series")


class TestDeriveSlugApostrophesAndAmpersand:
    """An apostrophe sits inside a word; a separator sits between words.

    Covers the rule this module documents: apostrophes and quotation marks
    are dropped outright rather than collapsed to a separator, ``&`` expands
    to the word ``and`` before the collapse pass, and every other separator
    keeps its existing collapse-to-one-underscore behaviour.
    """

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Valentine's", "valentines"),
            ("St Patrick's Day", "st_patricks_day"),
            ("What’s the craic?", "whats_the_craic"),  # curly apostrophe
            ("Witch’s Ritual", "witchs_ritual"),  # curly apostrophe
        ],
    )
    def test_apostrophe_dropped_not_collapsed(self, name: str, expected: str) -> None:
        """An apostrophe is removed outright, not turned into a separator."""
        assert derive_slug(name) == expected

    @pytest.mark.parametrize(
        "character",
        [
            "'",  # U+0027 APOSTROPHE
            "’",  # RIGHT SINGLE QUOTATION MARK
            "‘",  # LEFT SINGLE QUOTATION MARK
            "ʼ",  # MODIFIER LETTER APOSTROPHE
            "`",  # U+0060 GRAVE ACCENT
            '"',  # U+0022 QUOTATION MARK
            "“",  # LEFT DOUBLE QUOTATION MARK
            "”",  # RIGHT DOUBLE QUOTATION MARK
        ],
    )
    def test_each_dropped_character_mid_word(self, character: str) -> None:
        """Each of the eight dropped characters disappears mid-word."""
        assert derive_slug(f"wo{character}rd") == "word"

    def test_doubled_apostrophe_collapses_to_nothing(self) -> None:
        """A run of dropped characters is removed as one run, not per-character."""
        assert derive_slug("can''t") == "cant"

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Sage & Cedar", "sage_and_cedar"),
            # No spaces around the ampersand, so no underscores appear: the
            # underscores in "sage_and_cedar" above come from the spaces
            # either side of "&", via the collapse pass, not from the word
            # expansion itself. This is the intended consequence of a plain
            # substitution, not an oversight to "fix" into rock_and_roll.
            ("Rock&Roll", "rockandroll"),
            ("& Co", "and_co"),
        ],
    )
    def test_ampersand_expands_to_and(self, name: str, expected: str) -> None:
        """``&`` becomes the word ``and``, contributing no separator itself."""
        assert derive_slug(name) == expected

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Dance/Pop", "dance_pop"),
            ("Hip Hop/ Rap", "hip_hop_rap"),
        ],
    )
    def test_other_separators_unaffected(self, name: str, expected: str) -> None:
        """Separators outside the dropped set keep collapsing as before."""
        assert derive_slug(name) == expected

    def test_only_apostrophes_derives_to_empty_string(self) -> None:
        """A name that is only dropped characters can never fail validate_key.

        ``validate_key`` requires a non-empty string, and this proves the
        drop pass cannot itself violate that: nothing survives to strip.
        """
        assert derive_slug("'''") == ""
