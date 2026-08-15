# Themes Quick Start

Themes apply professionally-curated color palettes to your LIFX devices with a single command. The library carries 166 themes — 138 captured from the LIFX app plus 28 carried over from earlier versions of this library — resolvable under 168 names once rename aliases are counted.

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

## List Available Themes

```python
from lifx import ThemeLibrary

# Get every resolvable theme name
themes = ThemeLibrary.get_available_themes()
print(len(themes))  # 168 (166 themes plus 2 rename aliases)

# Get themes by category
holidays = ThemeLibrary.get_by_category("holiday")
moods = ThemeLibrary.get_by_category("mood")
```

## Next Steps

- **[Themes Guide](../user-guide/themes.md)** — Practical examples: time-based lighting, holiday decorations, custom themes, room coordination
- **[Themes API Reference](../api/themes.md)** — Complete API documentation
- **[Color Utilities](../api/colors.md)** — HSBK color representation
