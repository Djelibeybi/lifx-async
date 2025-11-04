# Color Utilities

lifx-async provides comprehensive color utilities for working with LIFX's HSBK color model and
converting to/from RGB.

## HSBK Class

The `HSBK` class represents colors in the Hue, Saturation, Brightness, Kelvin color model used by
LIFX devices.

::: lifx.color.HSBK
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Colors Class

The `Colors` class provides convenient color presets for common colors.

::: lifx.color.Colors
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Examples

### Creating Colors

```python
from lifx import HSBK, Colors

# Use built-in color presets
color = Colors.BLUE

# Create custom colors
custom = HSBK(hue=180.0, saturation=1.0, brightness=0.8, kelvin=3500)

# Create from RGB
red = HSBK.from_rgb(255, 0, 0, kelvin=3500)

# Convert to RGB
r, g, b = Colors.BLUE.to_rgb()
print(f"RGB: ({r}, {g}, {b})")
```

### Color Components

```python
from lifx import HSBK

color = HSBK(hue=240.0, saturation=1.0, brightness=0.5, kelvin=3500)

# Hue: 0-360 degrees (0=red, 120=green, 240=blue)
print(f"Hue: {color.hue}°")

# Saturation: 0.0-1.0 (0=white, 1=full color)
print(f"Saturation: {color.saturation * 100}%")

# Brightness: 0.0-1.0 (0=off, 1=full brightness)
print(f"Brightness: {color.brightness * 100}%")

# Kelvin: 1500-9000 (warm white to cool white)
print(f"Temperature: {color.kelvin}K")
```

### Color Manipulation

```python
from lifx import HSBK, Light


async def cycle_hue(light: Light):
    """Cycle through the color spectrum"""
    for hue in range(0, 360, 10):
        color = HSBK(hue=float(hue), saturation=1.0, brightness=0.8, kelvin=3500)
        await light.set_color(color, duration=0.1)
```

### White Balance

```python
from lifx import HSBK

# Warm white (sunset, candlelight)
warm = HSBK(hue=0, saturation=0, brightness=1.0, kelvin=2500)

# Neutral white (daylight)
neutral = HSBK(hue=0, saturation=0, brightness=1.0, kelvin=4000)

# Cool white (overcast, shade)
cool = HSBK(hue=0, saturation=0, brightness=1.0, kelvin=6500)
```

## Available Color Presets

The `Colors` class provides these preset colors:

- `Colors.WHITE` - Pure white (3500K)
- `Colors.RED` - Red
- `Colors.ORANGE` - Orange
- `Colors.YELLOW` - Yellow
- `Colors.GREEN` - Green
- `Colors.CYAN` - Cyan
- `Colors.BLUE` - Blue
- `Colors.PURPLE` - Purple
- `Colors.PINK` - Pink
- `Colors.WARM_WHITE` - Warm white (2500K)
- `Colors.COOL_WHITE` - Cool white (6500K)

## Color Conversion Notes

### RGB to HSBK

When converting from RGB to HSBK, note that:

- RGB values are 0-255
- The Kelvin value must be specified (default: 3500K)
- Some RGB colors may not have exact HSBK equivalents
- Conversion uses standard HSV formulas with brightness mapping

### HSBK to RGB

When converting from HSBK to RGB:

- Returns tuple of (r, g, b) with values 0-255
- Kelvin temperature is not represented in RGB
- White colors (saturation=0) will be pure gray values
- Conversion is lossy - converting back may not yield the same HSBK
