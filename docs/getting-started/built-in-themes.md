# Built-in Theme Catalogue

`ThemeLibrary` ships the library's built-in colour palettes. This page is the live public
catalogue: it owns category membership, counts, executable enumeration examples, and the
compatibility and fidelity boundary. Category order is not semantic.

## Available categories

| Category | Themes |
| --- | ---: |
| Archives | 60 |
| Art Series | 13 |
| Holidays | 16 |
| Library | 28 |
| Moods | 15 |
| Music | 14 |
| Nature | 9 |
| Play | 7 |
| Space | 11 |
| Worldly | 205 |

That is 378 theme records, resolvable under 381 names once the 3 rename aliases are
counted. 290 records are the themes the LIFX app ships, sport themes excluded, and carry the
app's own display name and category. The 60 `Archives` themes are no longer offered by the
app but keep their palettes as library-only themes. The remaining 28 sit under `Library`:
19 with no app counterpart, plus 9 deprecated keys retained so no pre-6.4.0 name stops
resolving.

The table is authored from the shipped library. A resync review must update it when category
membership changes.

### List resolvable themes

```python
from lifx import ThemeLibrary

theme_names = ThemeLibrary.get_available_themes()
assert theme_names == sorted(theme_names)
assert "evening" in theme_names
```

`get_available_themes()` includes every resolvable key, including supported rename aliases.

### List categories

```python
from lifx import ThemeLibrary

categories = ThemeLibrary.get_categories()
assert categories == sorted(categories)
assert "Holidays" in categories
```

### List one category

```python
from lifx import ThemeLibrary

holidays = ThemeLibrary.get_by_category("Holidays")
assert holidays
assert all(theme.category == "Holidays" for theme in holidays.values())
```

`get_by_category()` accepts category punctuation and case insensitively, while returning each
canonical primary once. Use `get_categories()` rather than assuming the table's display order.

### Find themes by tag or effect mode

```python
from lifx.theme import ThemeLibrary

for tag in ThemeLibrary.get_tags():
    print(tag, sorted(ThemeLibrary.get_by_tag(tag)))

blended = ThemeLibrary.find(static_mode="blended")
```

Tags and effect modes come from the LIFX app. Themes the app does not ship
carry no tags and use the `blended` static mode. The app's themes use the
`solid_static`, `blended`, `grid_static`, `solid_loop` and `solid` static modes,
and 18 of them name a Dynamic effect (MORPH or MOVE). An unknown tag, category or
static mode raises `ValueError`, so check `get_tags()` for tags or
`get_categories()` for categories first. Tags are spelt as the app spells them
(for example `Cozy`) and are matched ignoring case and punctuation.

## Compatibility and fidelity

The redefined pre-6.4.0 palettes were not carried forward. Their historical taxonomy and
migration guidance remain in [Theme Taxonomy Changes](../migration/theme-taxonomy-6.4.0.md);
use the current category methods above instead of redirecting a retired category name.

Palettes are stored as the app authors them — user-facing `HSBK` floats, converted to wire
values at runtime — and are not truncated to the 16 palette slots a firmware effect packet
carries. 28 themes are longer than 16 colours, up to 68 for `independence`,
`memorial_day` and `old_glory`.

That length is available to `apply_theme()`, which renders the whole palette across a
device's zones or pixels. It is *not* available to the firmware effect API: `MatrixEffect`
rejects a palette above `MAX_PALETTE_COLORS` (16), so a long theme must be reduced before it
can drive MORPH. Choosing which 16 is the caller's decision, not the library's.
