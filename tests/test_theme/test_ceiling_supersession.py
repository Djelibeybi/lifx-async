"""Guard for the 25 themes whose palettes were once truncated by the device ceiling.

Phase 8 determined a protocol-ceiling answer for 25 shipped `lifx-app` themes by
reading palettes back off a device. A device readback cannot reveal a seventeenth
source colour, so every one of those palettes arrived clipped to exactly
`MAX_PALETTE_COLORS`, and the recorded determination could only be
"device-ceiling-unresolvable".

The Phase 9 resync then obtained the true palettes for exactly these 25 themes from
an internal LIFX HTTP API endpoint, a non-device method the ceiling does not bind.
They now ship at their real lengths, well above the ceiling.

That supersession is what this module pins. A future resync that regressed any of
these back to a clipped 16-colour palette would silently reintroduce the truncation
Phase 9 removed, and nothing else in the suite would notice: the Phase 8 harness
that first found them is archived planning material, pinned to a capture directory
and hardware setup that no longer exist, and `testpaths` deliberately excludes it.

The slug list is therefore an explicit literal rather than a re-derivation. Its
source of truth is the historical record in the Phase 8 archive
(`08-CEILING-DETERMINATIONS.json`), which this file deliberately does not read,
because phase directories move into `.planning/milestones/` at milestone close.
"""

from __future__ import annotations

import pytest

from lifx.const import MAX_PALETTE_COLORS
from lifx.theme.data import THEMES

# The exact set Phase 8 recorded, verified equal in both directions against the
# pre-resync blob (`data/themes.jsonl@291e7e6~1`) during the v1.2 milestone audit.
DEVICE_CEILING_TRUNCATED_SLUGS = (
    "baubles",
    "bijutsukai",
    "candy_cane",
    "clouds",
    "deck_the_halls",
    "disco",
    "earth",
    "festive",
    "gauguin",
    "hokusai",
    "independence",
    "kandinsky",
    "klimt",
    "mars",
    "matisse",
    "memorial_day",
    "mistletoe",
    "mondrian",
    "monet",
    "moon",
    "oktoberfest",
    "old_glory",
    "rousseau",
    "sun",
    "van_gogh",
)


def test_the_recorded_set_is_the_25_phase_8_determined() -> None:
    """The literal above is a fixed historical set, not a moving derivation."""
    assert len(DEVICE_CEILING_TRUNCATED_SLUGS) == 25
    assert len(set(DEVICE_CEILING_TRUNCATED_SLUGS)) == 25
    assert list(DEVICE_CEILING_TRUNCATED_SLUGS) == sorted(
        DEVICE_CEILING_TRUNCATED_SLUGS
    )
    assert "carlton" not in DEVICE_CEILING_TRUNCATED_SLUGS


@pytest.mark.parametrize("slug", DEVICE_CEILING_TRUNCATED_SLUGS)
def test_truncated_theme_still_resolves_as_an_app_theme(slug: str) -> None:
    """Each stays a shipped app theme; none was dropped or reclassified."""
    assert slug in THEMES
    assert THEMES[slug].disposition == "lifx-app"


@pytest.mark.parametrize("slug", DEVICE_CEILING_TRUNCATED_SLUGS)
def test_truncated_theme_ships_its_full_palette(slug: str) -> None:
    """The resync lifted each above the ceiling; a regression would clip it back."""
    assert len(THEMES[slug].colors) > MAX_PALETTE_COLORS
