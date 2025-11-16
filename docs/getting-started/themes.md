# Themes Quick Start

Themes allow you to apply professionally-curated color palettes to your LIFX devices with a single command.

## Apply a Theme

```python
from lifx import discover, DeviceGroup, ThemeLibrary

devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

# Get a theme by name
theme = ThemeLibrary.get("evening")

# Apply to all devices
await group.apply_theme(theme)
```

## List Available Themes

```python
from lifx import ThemeLibrary

# Get all 42 theme names
themes = ThemeLibrary.list()
print(themes)

# Get themes by category
seasonal = ThemeLibrary.get_by_category("seasonal")
holidays = ThemeLibrary.get_by_category("holiday")
moods = ThemeLibrary.get_by_category("mood")
```

## Theme Categories

The library includes 42 official LIFX app themes:

- **Seasonal** (3): spring, autumn, winter
- **Holiday** (9): christmas, halloween, hanukkah, kwanzaa, shamrock, thanksgiving, calaveras, pumpkin, santa
- **Mood** (16): peaceful, serene, relaxing, mellow, gentle, soothing, blissful, cheerful, romantic, romance, love, energizing, exciting, epic, intense, powerful
- **Ambient** (6): dream, fantasy, spacey, stardust, zombie, party
- **Functional** (3): focusing, evening, bias_lighting
- **Atmosphere** (3): hygge, tranquil, sports

## Common Options

```python
from lifx import discover, DeviceGroup, ThemeLibrary

devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

theme = ThemeLibrary.get("christmas")

# Apply with options
await group.apply_theme(
    theme,
    power_on=True,      # Turn on lights before applying
    duration=1.5        # Transition duration in seconds
)
```

## Create a Custom Theme

```python
from lifx import HSBK, Theme, discover

# Create custom theme with specific colors
custom_theme = Theme([
    HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),      # Red
    HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500),    # Green
    HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500),    # Blue
])

devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

await group.apply_theme(custom_theme, power_on=True)
```

## Next Steps

- See [Themes API Reference](../api/themes.md) for detailed API documentation
- See [Device Classes](../api/devices.md) for device-specific `apply_theme()` methods
- See [Color Utilities](../api/colors.md) for HSBK color representation
