# Theme Taxonomy Changes (6.3.0)

This document describes changes to the theme category taxonomy introduced in 6.3.0.

!!! note "As of the 6.3.0 migration (2026-08-15)"

    The tables on this page record the library **as of the 6.3.0 migration** and are
    deliberately not updated as the library changes. This is a dated migration record,
    not a live reference — the values may change over time, but this page will not be
    updated to reflect current status. For current data, ask the library itself:
    `ThemeLibrary.get_categories()` lists the categories and
    `ThemeLibrary.get_by_category()` fetches one.

## Overview

The theme library's category navigation was rewritten over the LIFX app's own taxonomy:

1. **App taxonomy**: `get_by_category()` now reads the nine categories from the
   generated theme records instead of a hand-made six-name grouping over hardcoded
   theme lists
2. **Category discovery**: the new `ThemeLibrary.get_categories()` class method lists
   every category present in the data
3. **Legacy names**: every pre-6.3.0 category name either maps to an app category or
   raises `ValueError` naming its closest replacement
4. **Dispositions**: every theme records its 6.3.0 fate as queryable data —
   `Theme.disposition` and `Theme.replaced_by`

## The Nine Categories

Eight of the nine categories are the LIFX app's own. **Library is defined by this
library, not the app**: it holds the 28 pre-6.3.0 keys that have no app counterpart.
The app's three sport categories (AUSSIE RULES, LEAGUE and UNION) are not carried —
they have been out of scope since the library was first generated from app data.

| Category   | Themes | Defined by   |
|------------|-------:|--------------|
| Archives   |     60 | LIFX app     |
| Art Series |     10 | LIFX app     |
| Holidays   |     15 | LIFX app     |
| Library    |     28 | This library |
| Moods      |     13 | LIFX app     |
| Music      |     14 | LIFX app     |
| Nature     |      8 | LIFX app     |
| Play       |      7 | LIFX app     |
| Space      |     11 | LIFX app     |

Category matching is case- and punctuation-insensitive: `Art Series`, `art series`
and `art_series` all resolve to the same category, while `artseries` does not.

## Legacy Category Names

Each of the six pre-6.3.0 category names has a recorded fate. Two map to the app
category that absorbed most of their themes; the other four raise `ValueError` with
a message naming the closest replacement.

| Legacy name  | Fate                    | What to call now               |
|--------------|-------------------------|--------------------------------|
| `holiday`    | Maps to an app category | `get_by_category("Holidays")`  |
| `mood`       | Maps to an app category | `get_by_category("Moods")`     |
| `seasonal`   | Raises `ValueError`     | Closest replacement: `Nature`  |
| `ambient`    | Raises `ValueError`     | Closest replacement: `Play`    |
| `functional` | Raises `ValueError`     | Closest replacement: `Library` |
| `atmosphere` | Raises `ValueError`     | Closest replacement: `Moods`   |

Three theme names the old hardcoded lists carried — `winter`, `romantic` and
`dramatic` — never resolved to real themes and were silently filtered out of
results. The hardcoded lists are gone, so nothing is silently filtered any more.

## Deprecated Keys

Nine pre-6.3.0 theme keys are recorded as deprecated, each with a replacement that
is both palette-close and semantically the same idea:

| Deprecated key | Replacement        |
|----------------|--------------------|
| `focusing`     | `gentle`           |
| `intense`      | `fantasy`          |
| `shamrock`     | `st_patrick_s_day` |
| `love`         | `romance`          |
| `holly`        | `christmas`        |
| `fire`         | `warm_ember`       |
| `proud`        | `pride`            |
| `pumpkin`      | `pumpkin_spice`    |
| `santa`        | `candy_cane`       |

A deprecated key still resolves: deprecation records a fate, it never deletes, and
removing a key would be a major-version decision. The disposition is queryable data —
`Theme.disposition` and `Theme.replaced_by` on the object `ThemeLibrary.get()`
returns — and no warning is emitted and nothing is logged when a deprecated key is
used. The remaining 19 pre-6.3.0 orphan keys are recorded as `library-only` and stay.

## Before and After

**Before** — historical pre-6.3.0 behaviour, shown for context:

```python
from lifx import ThemeLibrary


# The old hand-made grouping: a hand-picked, mixed list of themes
holidays = ThemeLibrary.get_by_category("holiday")
```

**After:**

```python
from lifx import ThemeLibrary


# Discover the categories, then fetch one
categories = ThemeLibrary.get_categories()
holidays = ThemeLibrary.get_by_category("Holidays")

# Read a deprecated theme's recorded fate
theme = ThemeLibrary.get("fire")
print(theme.disposition)  # deprecated
print(theme.replaced_by)  # warm_ember
```

Note that `get_by_category("holiday")` and `get_by_category("mood")` **still
resolve** after 6.3.0 — what changed is the result set, not the call's validity.
The old hand-built mixed grouping is replaced by the complete Holidays and Moods
app categories, so the same call now returns a different (and complete) set of
themes. Neither of the two mapped names was removed.
