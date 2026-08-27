# Themes Quick Start

Themes apply professionally-curated color palettes to your LIFX devices with a single command. The library carries 166 themes — 138 from the LIFX app plus 28 carried over from earlier versions of this library — resolvable under 169 names once rename aliases are counted.

## Apply a Theme

```python
from lifx import discover, DeviceGroup, ThemeLibrary

devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

# Get a theme by name and apply it
theme = ThemeLibrary.get("evening")
await group.apply_theme(theme, power_on=True, duration=1.5)
```

## Browse Built-in Themes

The [Built-in Theme Catalogue](built-in-themes.md) is the live owner of available categories,
counts, compatibility notes and executable enumeration examples.

## Next Steps

- **[Built-in Theme Catalogue](built-in-themes.md)** — Every category, count and enumeration example
- **[Themes Guide](../user-guide/themes.md)** — Practical examples: time-based lighting, holiday decorations, custom themes, room coordination
- **[Themes API Reference](../api/themes.md)** — Complete API documentation
- **[Color Utilities](../api/colors.md)** — HSBK color representation
