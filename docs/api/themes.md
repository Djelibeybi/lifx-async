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

The `ThemeLibrary` provides access to 42 official LIFX app themes organized into 6 categories.

::: lifx.theme.ThemeLibrary
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Canvas Class

The `Canvas` class provides 2D sparse grid functionality for tile device color interpolation.

::: lifx.theme.Canvas
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

## Available Themes (42 Total)

### Seasonal (3 themes)
- spring, autumn, winter

### Holiday (9 themes)
- christmas, halloween, hanukkah, kwanzaa, shamrock, thanksgiving, calaveras, pumpkin, santa

### Mood (16 themes)
- peaceful, serene, relaxing, mellow, gentle, soothing, blissful, cheerful, romantic, romance, love, energizing, exciting, epic, intense, powerful, warming

### Ambient (6 themes)
- dream, fantasy, spacey, stardust, zombie, party

### Functional (3 themes)
- focusing, evening, bias_lighting

### Atmosphere (3 themes)
- hygge, tranquil, sports
