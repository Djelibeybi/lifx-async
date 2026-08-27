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
