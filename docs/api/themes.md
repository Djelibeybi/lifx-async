# Themes API Reference

The theme system provides professionally-curated color palettes for coordinated lighting across LIFX devices.

## Theme Class

The `Theme` class represents a collection of HSBK colors forming a coordinated palette.

::: lifx.theme.Theme
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## ThemeLibrary Class

The `ThemeLibrary` provides access to 166 themes, resolvable under 168 names.

::: lifx.theme.ThemeLibrary
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Convenience Function

::: lifx.theme.get_theme
    options:
      show_root_heading: true
      heading_level: 3

## Available Themes

The library carries **166 themes**, resolvable under **168 names** (the extra two are the
`forest` and `aurora_borealis` rename aliases). 138 are captured from the LIFX app and carry
the app's own display name and category; the remaining 28 have no app counterpart and sit
under the `Library` category.

Rather than reproduce the inventory here — where it rots on every resync — ask the library:

```python
from lifx import ThemeLibrary

names = ThemeLibrary.get_available_themes()   # every resolvable name

theme = ThemeLibrary.get("evening")
print(theme.slug, theme.name, theme.category)  # evening Evening Moods
```

Each theme carries its ASCII `slug`, the app's `name` (which may contain spaces and
punctuation) and its `category`. The categories and their theme counts are:

| Category | Themes |
| --- | ---: |
| Archives | 60 |
| Library | 28 |
| Holidays | 15 |
| Music | 14 |
| Moods | 13 |
| Space | 11 |
| Art Series | 10 |
| Nature | 8 |
| Play | 7 |

`ThemeLibrary.get_by_category()` takes the categories in the table above, matched
case- and punctuation-insensitively (`Art Series`, `art series` and `art_series` all
resolve), and `ThemeLibrary.get_categories()` lists them. The two pre-v1.2 names
`holiday` and `mood` still map to Holidays and Moods; the remaining pre-v1.2 names
raise `ValueError` naming their closest replacement — see
[Theme Taxonomy Changes](../migration/theme-taxonomy-v1.2.md). `Theme.disposition`
and `Theme.replaced_by` record each theme's v1.2 fate, documented on the same page.
