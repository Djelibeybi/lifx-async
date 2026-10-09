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

The `ThemeLibrary` provides access to 378 themes, resolvable under 381 names.

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

Colours are stored in source order, which matters most for `grid_static`
themes and other non-`blended` static modes: there the order is the layout.

Tags are spelt as the app spells them (for example `Cozy`). Tag matching
ignores case and punctuation, so `"calm"` finds `Calm`.

Only the LIFX app's own themes carry tags; library-only and deprecated themes
have none and use the `blended` static mode. An unknown tag, category or static
mode raises `ValueError`, so check `ThemeLibrary.get_tags()` first.

Find themes with `ThemeLibrary.get_tags()`, `ThemeLibrary.get_by_tag()` and
`ThemeLibrary.find()`:

```python
from lifx.theme import ThemeLibrary

tags = ThemeLibrary.get_tags()

if "Calm" in tags:
    calm = ThemeLibrary.get_by_tag("calm")

if {"Calm", "Cozy"} <= set(tags):
    calm_or_cosy = ThemeLibrary.find(tags=["Calm", "Cozy"], match="any")
```

## Moods

`apply_mood()` paints a theme the way the LIFX app paints a mood, and
`animate_mood()` starts the effect the app's Dynamic toggle starts. Both take
only the theme and use the app's own timings: a 0.3 second fade, power on
only when every targeted light is off, and the mood rescaled so its brightest
colour matches the light's brightness.

| Light | Still image (`apply_mood`) | Effect (`animate_mood`) |
|---|---|---|
| Bulb | One of the theme's colours; a `DeviceGroup` deals them one per bulb | `EffectColorloop` through the theme's colours; bulbs in one `DeviceGroup` share one loop |
| Strip | The mood across the zones | Firmware MOVE, after painting the still image |
| Matrix light | The mood's image, by `static_mode` | Firmware MORPH for a MORPH mood; `EffectScroll` for a MOVE mood |
| Spot, Path and Mirror | The mood's image, painted like any other matrix light | Firmware MORPH for every mood |
| Candle and Tube | Stripe moods paint as bands along the long axis, first colour at the bottom | A MOVE stripe mood scrolls the bands down the light; other moods as for a matrix light |

The Mirror's still image is painted over its 4x13 buffer as a single matrix
light, not ring by ring. The app runs a firmware effect on Spot and Path that
this library does not send, so MORPH stands in for it.

A Tile chain is painted as one image in chain order, as the app does, so tiles
arranged in an L or a stack show the image in chain order rather than
following their arrangement. A Tile whose accelerometer reports a rotation
(left, right or upside down) is remapped; FaceUp and FaceDown are not. A
chain scrolls as one canvas, in chain order.

If a light is already running a mood effect, `apply_mood()` restarts that
effect with the new theme instead of painting a still image.

`apply_theme()` is unchanged; use it for the library's own gradients.

::: lifx.theme.MoodGenerator
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
