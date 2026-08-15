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

# Precompiled because this is no longer a build-time-only rule: the library
# calls it on every category lookup, matching the module-level pattern
# constants in lifx/protocol/base.py.
_NON_SLUG_RUN = re.compile(r"[^a-z0-9]+")


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
    return _NON_SLUG_RUN.sub("_", name.lower()).strip("_")
