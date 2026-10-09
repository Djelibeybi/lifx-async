"""The generated theme module matches its source data.

``src/lifx/theme/data.py`` is regenerated from ``data/themes.jsonl`` whenever
LIFX add, remove or change a theme in the app, so no test here pins a count,
a category name or a colour. Every expected value is read from the JSONL file
and compared with what the generated module and ``ThemeLibrary`` report, so a
stale or hand-edited ``data.py`` fails while a legitimate resync passes.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from lifx.color import HSBK
from lifx.theme import ThemeLibrary
from lifx.theme.data import THEMES
from tests.test_theme.conftest import SOURCE_ALIASES, SOURCE_RECORDS

_BY_SLUG = {record["slug"]: record for record in SOURCE_RECORDS}


def _source_colors(record: dict[str, Any]) -> tuple[HSBK, ...]:
    return tuple(
        HSBK(
            hue=color["hue"],
            saturation=color["saturation"],
            brightness=color["brightness"],
            kelvin=color["kelvin"],
        )
        for color in record["colors"]
    )


class TestCounts:
    """The numbers agree between the source data and the generated module."""

    def test_every_source_slug_and_alias_is_generated(self) -> None:
        expected = set(_BY_SLUG) | {alias for alias, _ in SOURCE_ALIASES}

        assert set(THEMES) == expected

    def test_theme_count(self) -> None:
        themes = [r for r in THEMES.values() if r.disposition != "renamed"]

        assert len(themes) == len(SOURCE_RECORDS)

    def test_alias_count(self) -> None:
        aliases = [r for r in THEMES.values() if r.disposition == "renamed"]

        assert len(aliases) == len(SOURCE_ALIASES)

    def test_available_themes_count(self) -> None:
        assert len(ThemeLibrary.get_available_themes()) == len(SOURCE_RECORDS) + len(
            SOURCE_ALIASES
        )

    def test_categories(self) -> None:
        expected = sorted({record["category"] for record in SOURCE_RECORDS})

        assert ThemeLibrary.get_categories() == expected

    def test_themes_per_category(self) -> None:
        expected = Counter(record["category"] for record in SOURCE_RECORDS)

        for category, count in expected.items():
            assert len(ThemeLibrary.get_by_category(category)) == count, category

    def test_disposition_counts(self) -> None:
        expected = Counter(record["disposition"] for record in SOURCE_RECORDS)
        generated = Counter(
            r.disposition for r in THEMES.values() if r.disposition != "renamed"
        )

        assert generated == expected


@pytest.mark.parametrize("slug", sorted(_BY_SLUG))
def test_record_matches_source(slug: str) -> None:
    """Each generated record carries exactly what its source line says."""
    source = _BY_SLUG[slug]
    record = THEMES[slug]

    assert record.name == source["name"]
    assert record.category == source["category"]
    assert record.disposition == source["disposition"]
    assert record.replaced_by == source.get("replaced_by")
    assert record.static_mode == source["static_mode"]
    assert record.dynamic_mode == source.get("dynamic_mode")
    assert sorted(record.tags) == sorted(source.get("tags", []))
    # Colour order is source data, so the comparison is ordered.
    assert record.colors == _source_colors(source)


@pytest.mark.parametrize(("alias", "target"), SOURCE_ALIASES)
def test_alias_matches_source(alias: str, target: str) -> None:
    """Each source alias is generated as a rename pointing at its target."""
    record = THEMES[alias]

    assert record.disposition == "renamed"
    assert record.replaced_by == target
    assert record.colors == _source_colors(_BY_SLUG[target])


@pytest.mark.parametrize("slug", sorted(_BY_SLUG))
def test_library_get_matches_source(slug: str) -> None:
    """ThemeLibrary.get() hands back the source palette and identity."""
    source = _BY_SLUG[slug]
    theme = ThemeLibrary.get(slug)

    assert theme.slug == slug
    assert theme.name == source["name"]
    assert theme.category == source["category"]
    assert theme.disposition == source["disposition"]
    assert theme.replaced_by == source.get("replaced_by")
    assert tuple(theme.colors) == _source_colors(source)
