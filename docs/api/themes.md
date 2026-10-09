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

The `ThemeLibrary` provides access to 166 themes, resolvable under 169 names.

::: lifx.theme.ThemeLibrary
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Effect Modes and Tags

Every library theme records how the LIFX app shows it:

- `Theme.static_mode` is the still image the app paints, such as `blended` (a
  gradient from the palette) or `grid_static` (the colours are an ordered grid).
  A theme you build yourself has none and is treated as `blended`.
- `Theme.dynamic_mode` is the effect the app's Dynamic toggle starts, when the
  theme names one. `Theme.resolved_dynamic_mode` gives the effect either way:
  MORPH for `blended` themes and MOVE for the rest, unless the theme says
  otherwise.
- `Theme.tags` holds the app's search tags, such as `Calm`.

`StaticMode` and `DynamicMode` are the matching `Literal` types. They list
every mode the library's data contains, so a new release can widen them.

Colours are stored in source order. For grid and stripe themes the order is
the layout.

Find themes with `ThemeLibrary.get_tags()`, `ThemeLibrary.get_by_tag()` and
`ThemeLibrary.find()`:

```python
from lifx.theme import ThemeLibrary

calm = ThemeLibrary.get_by_tag("calm")
calm_or_cosy_grids = ThemeLibrary.find(
    tags=["Calm", "Cozy"], match="any", static_mode="grid_static"
)
```

## Convenience Function

::: lifx.theme.get_theme
    options:
      show_root_heading: true
      heading_level: 3

## Built-in Theme Catalogue

For the live category/count table, executable enumeration examples, compatibility notes and
fidelity boundary, see the [Built-in Theme Catalogue](../getting-started/built-in-themes.md).

`Theme.disposition` and `Theme.replaced_by` record each theme's fate; the six pre-6.4.0
category names are retired and raise `ValueError`. Both are documented on the
[Theme Taxonomy Changes](../migration/theme-taxonomy-6.4.0.md) page.
