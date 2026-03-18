# Themes Quick Start

Themes apply professionally-curated color palettes to your LIFX devices with a single command. The library includes 42 built-in themes across seasonal, holiday, mood, ambient, and functional categories.

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

# Get all 42 theme names
themes = ThemeLibrary.get_available_themes()
print(themes)

# Get themes by category
seasonal = ThemeLibrary.get_by_category("seasonal")
moods = ThemeLibrary.get_by_category("mood")
```

## Next Steps

- **[Themes Guide](../user-guide/themes.md)** — Practical examples: time-based lighting, holiday decorations, custom themes, room coordination
- **[Themes API Reference](../api/themes.md)** — Complete API documentation
- **[Color Utilities](../api/colors.md)** — HSBK color representation
