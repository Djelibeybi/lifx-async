# Theme Taxonomy Changes (6.4.0)

This document describes changes to the theme category taxonomy introduced in 6.4.0.

!!! note "As of the 6.4.0 migration (2026-08-15)"

    The tables on this page record the library **as of the 6.4.0 migration** and are
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
3. **Legacy names**: the six pre-6.4.0 category names are retired, and the error
   lists the categories that exist
4. **Dispositions**: every theme records its fate as queryable data —
   `Theme.disposition` and `Theme.replaced_by` — including the two rename aliases

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

## Retired Category Names

All six pre-6.4.0 category names are retired. Each now raises `ValueError`
listing the nine categories that exist:

```python
ThemeLibrary.get_by_category("holiday")
# ValueError: Category 'holiday' is not recognised. Available categories:
# Archives, Art Series, Holidays, Library, Moods, Music, Nature, Play, Space
```

No legacy name is redirected, because no honest redirect exists. Not one of the
six mapped onto a single app category, and the `Closest` column below is the
share of each name's old result set that the nearest single category actually
holds, measured against the 6.4.0 data:

| Retired name | Nearest category | Closest |
|--------------|------------------|--------:|
| `holiday`    | `Holidays`       |    7/12 |
| `mood`       | `Moods`          |   10/16 |
| `seasonal`   | `Library`        |     2/2 |
| `ambient`    | `Play`           |     5/6 |
| `functional` | `Library`        |     3/3 |
| `atmosphere` | `Library`        |     2/3 |

Redirecting `holiday` to `Holidays` would have silently dropped five themes and
added ten, with no exception and no warning to say so. Raising is the only
behaviour that tells you your grouping changed. Read the table, pick the category
you meant, and call it by its current name.

Every theme any of these names used to return still resolves through
`ThemeLibrary.get()` — nothing was deleted, only regrouped. Use
`Theme.category` to see where a given theme now sits.

Three theme names the old hardcoded lists carried — `winter`, `romantic` and
`dramatic` — never resolved to real themes and were silently filtered out of
results. The hardcoded lists are gone, so nothing is silently filtered any more.

## Deprecated Keys

Nine of those library keys are recorded as deprecated in 6.4.0, each with a replacement that
is both palette-close and semantically the same idea:

| Deprecated key | Replacement        |
|----------------|--------------------|
| `focusing`     | `gentle`           |
| `intense`      | `fantasy`          |
| `shamrock`     | `st_patricks_day`  |
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
used. The remaining 19 orphan keys are recorded as `library-only` and stay.

## Rename Aliases

Two keys are a theme's former name, kept resolvable since 6.3.0. They now report
the rename instead of the target's fate:

| Old key            | Current key | `disposition` | `replaced_by` |
|--------------------|-------------|---------------|---------------|
| `forest`           | `forrest`   | `renamed`     | `forrest`     |
| `aurora_borealis`  | `aurora`    | `renamed`     | `aurora`      |

Before 6.4.0 an alias key bound its target's own record, so the only two keys
whose name had actually changed were the two claiming a clean `lifx-app` fate
with no successor. A migration audit keyed off `replaced_by` saw nothing to do
for exactly the keys that had moved. Both now answer:

```python
theme = ThemeLibrary.get("forest")
print(theme.disposition)  # renamed
print(theme.replaced_by)  # forrest
```

An alias still returns its target's palette, display name and category, so
existing code that only reads colours is unaffected. What changed is `slug`,
which is now the key you asked for rather than the target's, and the pair no
longer double-counts in `get_by_category()` — a category lists each theme once,
under its current key.

## Before and After

**Before** — historical pre-6.4.0 behaviour, shown for context:

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

`get_by_category("holiday")` and `get_by_category("mood")` were the only two
legacy names any published example used, and both now raise. The nearest
equivalents are `"Holidays"` and `"Moods"`, but they are not the same sets — the
table below lists what each legacy call returned that its nearest category does
not. Every one of these themes still resolves through `ThemeLibrary.get()`; each
has simply moved to a category the legacy name never pointed at.

| Legacy call | Themes the nearest category does not return | Where they are now |
|-------------|---------------------------------------------|--------------------|
| `get_by_category("holiday")` | `holly`, `proud`, `pumpkin`, `santa`, `shamrock` | `Library` (all five are deprecated keys) |
| `get_by_category("mood")` | `epic`, `exciting`, `intense`, `love`, `relaxing`, `serene` | `Library`, except `exciting` (`Play`) |

`Holidays` and `Moods` also each contain themes the legacy names never returned,
so review the full category rather than assuming a superset.
