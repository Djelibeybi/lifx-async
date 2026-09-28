"""Guard for the 25 themes whose palettes were once truncated by the device ceiling.

A protocol-ceiling answer was determined for 25 shipped `lifx-app` themes by
reading palettes back off a device. A device readback cannot reveal a seventeenth
source colour, so every one of those palettes arrived clipped to exactly
`MAX_PALETTE_COLORS`, and the recorded determination could only be
"device-ceiling-unresolvable".

A later resync then obtained the true palettes for exactly these 25 themes from
an internal LIFX HTTP API endpoint, a non-device method the ceiling does not bind.
They now ship at their real lengths, well above the ceiling.

That supersession is what this module pins. A future resync that regressed any of
these back to a clipped 16-colour palette would silently reintroduce the
truncation, and nothing else in the suite would notice: the original
device-readback harness that first found them relied on a capture directory and
hardware setup that no longer exist, and it has since left the repository.

The slug list is therefore an explicit literal rather than a re-derivation. Its
source of truth was the historical record of that determination, which left the
repository along with the harness.
"""

from __future__ import annotations

import pytest

from lifx.const import MAX_PALETTE_COLORS
from lifx.theme.data import THEMES

# The exact set originally recorded, verified equal in both directions against
# the pre-resync blob (`data/themes.jsonl@291e7e6~1`).
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


@pytest.mark.parametrize("slug", DEVICE_CEILING_TRUNCATED_SLUGS)
def test_truncated_theme_still_resolves_as_an_app_theme(slug: str) -> None:
    """Each stays a shipped app theme; none was dropped or reclassified."""
    assert slug in THEMES
    assert THEMES[slug].disposition == "lifx-app"


@pytest.mark.parametrize("slug", DEVICE_CEILING_TRUNCATED_SLUGS)
def test_truncated_theme_ships_its_full_palette(slug: str) -> None:
    """The resync lifted each above the ceiling; a regression would clip it back."""
    assert len(THEMES[slug].colors) > MAX_PALETTE_COLORS
