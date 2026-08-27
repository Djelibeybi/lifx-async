"""Publication contract for the built-in theme catalogue page.

`docs/getting-started/built-in-themes.md` is the live public catalogue: it owns the
category/count table, the executable enumeration examples and the fidelity boundary.
The page claims to match the shipped library, so the claim is enforced here rather
than left to a resync reviewer's memory.

The equivalent contract for the maintainer resync runbook lives in the separate
`lifx-theme-resync` repository; only the library-facing page is checked here.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from lifx.const import MAX_PALETTE_COLORS
from lifx.theme import ThemeLibrary
from lifx.theme.data import THEMES

CATALOGUE = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "getting-started"
    / "built-in-themes.md"
)

_ROW = re.compile(r"^\| (?P<category>[^|]+?) \| (?P<count>\d+) \|$", re.MULTILINE)


@pytest.fixture(scope="module")
def page() -> str:
    """The page with its line wrapping collapsed.

    The prose contracts below are about wording, not layout, so reflowing a
    paragraph must not fail the suite.
    """
    return " ".join(CATALOGUE.read_text(encoding="utf-8").split())


@pytest.fixture(scope="module")
def documented_counts() -> dict[str, int]:
    """The category table, parsed from the page's own rows."""
    source = CATALOGUE.read_text(encoding="utf-8")
    counts = {match["category"]: int(match["count"]) for match in _ROW.finditer(source)}
    assert counts, "no category rows parsed from the catalogue table"
    return counts


def test_table_matches_live_categories(documented_counts: dict[str, int]) -> None:
    """The table's categories are exactly the library's categories."""
    assert sorted(documented_counts) == ThemeLibrary.get_categories()


def test_table_matches_live_counts(documented_counts: dict[str, int]) -> None:
    """Each documented count is the category's live membership."""
    live = {
        category: len(ThemeLibrary.get_by_category(category))
        for category in ThemeLibrary.get_categories()
    }
    assert documented_counts == live


def test_documented_totals_hold(page: str, documented_counts: dict[str, int]) -> None:
    """The prose totals are derived from the same records as the table."""
    dispositions = Counter(record.disposition for record in THEMES.values())
    aliases = dispositions["renamed"]
    records = len(THEMES) - aliases

    assert sum(documented_counts.values()) == records
    assert f"{records} theme records" in page
    assert f"resolvable under {len(THEMES)} names" in page
    assert f"{aliases} rename aliases" in page
    assert f"{dispositions['lifx-app']} records come from the LIFX app" in page
    assert f"{dispositions['library-only']} with no app counterpart" in page
    assert f"plus {dispositions['deprecated']} deprecated keys" in page


def test_enumeration_examples_execute() -> None:
    """The page's three code blocks are executable against the shipped library."""
    theme_names = ThemeLibrary.get_available_themes()
    assert theme_names == sorted(theme_names)
    assert "evening" in theme_names

    categories = ThemeLibrary.get_categories()
    assert categories == sorted(categories)
    assert "Holidays" in categories

    holidays = ThemeLibrary.get_by_category("Holidays")
    assert holidays
    assert all(theme.category == "Holidays" for theme in holidays.values())


def test_long_palette_claims_hold(page: str) -> None:
    """The fidelity section's untruncated-palette figures are measured, not asserted."""
    lengths = {slug: len(record.colors) for slug, record in THEMES.items()}
    over_limit = [n for n in lengths.values() if n > MAX_PALETTE_COLORS]
    longest = max(lengths, key=lambda slug: lengths[slug])

    assert f"{len(over_limit)} themes are longer than" in page
    assert f"{MAX_PALETTE_COLORS} colours" in page
    assert f"`{longest}` at {lengths[longest]}" in page


def test_retirement_statement_present(page: str) -> None:
    """DOCS-03: the page states the pre-6.4.0 palettes were not carried forward."""
    assert "were not carried forward" in page
    assert "migration/theme-taxonomy-6.4.0.md" in page
