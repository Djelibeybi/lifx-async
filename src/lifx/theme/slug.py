"""The single D-09 slug-derivation rule for the theme layer.

This module is the one home of the slug rule shared by the theme-data
generator (``scripts/generate_theme_data.py``, slug validation) and
:class:`lifx.theme.library.ThemeLibrary` (category-name normalisation) —
one rule, stated once, so the two sides cannot drift apart. It is a leaf
module by design: its only import is ``re``, never anything from ``lifx``.

Internal machinery: :func:`derive_slug` is deliberately absent from
``lifx.theme.__all__``.
"""

from __future__ import annotations

import re


def derive_slug(name: str) -> str:
    """Derive the canonical slug from a name.

    The D-09 derivation over ASCII input — stored, emoji-stripped display
    names in the generator, and caller-supplied category names in the
    library: lowercase, collapse every run of non-alphanumeric characters
    to a single underscore, strip leading and trailing underscores.

    Args:
        name: ASCII name to normalise.

    Returns:
        The derived slug.
    """
    # One pass suffices: `[^a-z0-9]+` already matches `_` itself and collapses
    # runs greedily, so two adjacent replacement underscores cannot survive it.
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
