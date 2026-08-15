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
            ("Valentine's", "valentine_s"),
            ("St Patrick's Day", "st_patrick_s_day"),
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
