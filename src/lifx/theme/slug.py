"""The single D-09 slug-derivation rule for the theme layer.

This module is the one home of the slug rule shared by the theme-data
generator (``scripts/generate_theme_data.py``, slug validation) and
:class:`lifx.theme.library.ThemeLibrary` (category-name normalisation) —
one rule, stated once, so the two sides cannot drift apart. It is a leaf
module by design: its only import is ``re``, never anything from ``lifx``.

The D-09 rule has three passes, applied in order: drop apostrophes and
quotation marks outright, expand ``&`` to the word ``and``, then lowercase
and collapse every remaining run of non-alphanumeric characters to a single
underscore before stripping the edges. An apostrophe sits inside a word, so
collapsing it to a separator would split one word into two; ``&`` reads as
the word "and" wherever it appears, so it is substituted rather than
dropped or collapsed. Every other separator, including ``/`` and other
``Po``-category punctuation, keeps the plain collapse behaviour: the drop
and expand sets are deliberately explicit characters, not a Unicode
category, because ``/`` and ``&`` are both category ``Po`` alongside the
apostrophe yet need different treatment (collapse, expand, drop). Full
stop, comma, question mark and exclamation mark were considered and
deliberately left out of the drop set: every occurrence in the shipped
catalogue is either terminal (already stripped by the edge-strip) or
followed by a space (so the run collapses to one underscore either way),
so dropping them would change nothing today while opening a judgement call
for names like "Version 2.0". Widen this rule only with the same kind of
catalogue-wide evidence, not by inference from category membership.

Internal machinery: :func:`derive_slug` is deliberately absent from
``lifx.theme.__all__``.
"""

from __future__ import annotations

import re

#: Characters removed outright rather than treated as separators: an
#: apostrophe or quotation mark sits inside a word, so collapsing it to an
#: underscore would split one word into two. Both ASCII and curly forms are
#: included because curly apostrophes reach this function directly from
#: display names, never pre-stripped to ASCII.
_DROPPED = re.compile(r"['‘’ʼ`\"“”]+")

#: The literal replaced by `_AMPERSAND_WORD`. `&` is not a separator: it
#: reads as the word "and" wherever it appears in a name, so it is expanded
#: rather than dropped or collapsed.
_AMPERSAND_WORD = "and"

# Precompiled because this is no longer a build-time-only rule: the library
# calls it on every category lookup, matching the module-level pattern
# constants in lifx/protocol/base.py.
_NON_SLUG_RUN = re.compile(r"[^a-z0-9]+")


def derive_slug(name: str) -> str:
    """Derive the canonical slug from a name.

    The D-09 derivation over ASCII input — stored, emoji-stripped display
    names in the generator, and caller-supplied category names in the
    library: drop apostrophes and quotation marks outright, expand ``&`` to
    the word ``and``, then lowercase and collapse every run of remaining
    non-alphanumeric characters to a single underscore, and strip leading
    and trailing underscores.

    Args:
        name: ASCII name to normalise.

    Returns:
        The derived slug.
    """
    without_quotes = _DROPPED.sub("", name)
    expanded = without_quotes.replace("&", _AMPERSAND_WORD)
    # One pass suffices for the collapse: `[^a-z0-9]+` already matches `_`
    # itself and collapses runs greedily, so two adjacent replacement
    # underscores cannot survive it.
    return _NON_SLUG_RUN.sub("_", expanded.lower()).strip("_")
