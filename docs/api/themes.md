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

!!! note "`get_by_category()` still uses the older grouping"

    `ThemeLibrary.get_by_category()` predates this data and takes the legacy names
    (`seasonal`, `holiday`, `mood`, `ambient`, `functional`, `atmosphere`), not the
    categories above. Reconciling the two is tracked for a following release; read
    `Theme.category` for the app's own grouping.
