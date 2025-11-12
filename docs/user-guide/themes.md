# Using Themes: Practical Examples

Themes enable coordinated color schemes across your LIFX devices. This guide covers practical examples and patterns.

## Basic Usage

### Apply Theme to All Devices

```python
from lifx import discover, ThemeLibrary

async def apply_evening_mode():
    async with discover() as lights:
        theme = ThemeLibrary.get("evening")
        await lights.apply_theme(theme, power_on=True, duration=2.0)
```

### Apply Different Themes to Different Device Types

```python
from lifx import discover, ThemeLibrary

async def themed_lighting():
    async with discover() as lights:
        theme = ThemeLibrary.get("christmas")

        # Single-zone lights get a random color
        for light in lights.lights:
            await light.apply_theme(theme)

        # Multi-zone lights get distributed colors
        for strip in lights.multizone_lights:
            await strip.apply_theme(theme)

        # Tile devices get smooth interpolation
        for tile in lights.tiles:
            await tile.apply_theme(theme)
```

## Time-Based Lighting

### Morning to Night Transition

```python
from lifx import discover, ThemeLibrary
import asyncio

async def daily_lighting_schedule():
    async with discover() as lights:
        schedule = [
            ("06:00", "energizing"),   # Morning
            ("12:00", "focusing"),     # Afternoon
            ("18:00", "evening"),      # Early evening
            ("21:00", "relaxing"),     # Night
            ("23:00", "peaceful"),     # Bedtime
        ]

        for time_str, theme_name in schedule:
            theme = ThemeLibrary.get(theme_name)
            await lights.apply_theme(theme, duration=2.0)
            # In production, schedule this with APScheduler or similar
            await asyncio.sleep(2.0)  # Demo delay
```

## Holiday Decorations

### Holiday Mode Manager

```python
from lifx import discover, ThemeLibrary
from datetime import datetime

async def activate_holiday_theme():
    """Apply appropriate holiday theme based on current month."""
    month = datetime.now().month

    holiday_map = {
        3: "shamrock",        # March: St. Patrick's Day
        10: "halloween",      # October
        11: "thanksgiving",   # November
        12: "christmas",      # December
    }

    theme_name = holiday_map.get(month)
    if not theme_name:
        return

    async with discover() as lights:
        theme = ThemeLibrary.get(theme_name)
        await lights.apply_theme(theme, power_on=True)
```

### Multi-Room Holiday Setup

```python
from lifx import discover, ThemeLibrary

async def decorate_house_for_christmas():
    """Apply Christmas theme throughout the house."""
    async with discover() as lights:
        theme = ThemeLibrary.get("christmas")

        # Living room: full brightness
        for light in lights.lights:
            if "living" in light.label.lower():
                await light.apply_theme(theme, power_on=True, duration=1.0)

        # Bedroom: dimmer
        for light in lights.lights:
            if "bedroom" in light.label.lower():
                dim_theme = ThemeLibrary.get("peaceful")
                await light.apply_theme(dim_theme, power_on=True, duration=1.0)

        # Strips and tiles throughout
        for strip in lights.multizone_lights:
            await strip.apply_theme(theme, power_on=True, duration=1.5)

        for tile in lights.tiles:
            await tile.apply_theme(theme, power_on=True, duration=1.5)
```

## Dynamic Theme Transitions

### Smooth Theme Cycling

```python
from lifx import discover, ThemeLibrary
import asyncio

async def cycle_moods():
    """Smoothly transition between mood themes."""
    mood_themes = [
        "peaceful",
        "relaxing",
        "mellow",
        "cheerful",
        "energizing",
    ]

    async with discover() as lights:
        for theme_name in mood_themes:
            theme = ThemeLibrary.get(theme_name)
            await lights.apply_theme(theme, duration=2.0)
            await asyncio.sleep(2.5)  # Wait for transition + 0.5s delay
```

### Theme Playlist

```python
from lifx import discover, ThemeLibrary
import asyncio

async def theme_playlist(themes: list[str], duration: float = 5.0):
    """Apply a sequence of themes with configurable timing."""
    async with discover() as lights:
        for theme_name in themes:
            try:
                theme = ThemeLibrary.get(theme_name)
                await lights.apply_theme(theme, duration=1.0)
                await asyncio.sleep(duration)
            except KeyError:
                print(f"Theme '{theme_name}' not found, skipping")

# Usage:
# await theme_playlist(["evening", "relaxing", "peaceful"], duration=10.0)
```

## Room-Specific Themes

### Multi-Room Coordination

```python
from lifx import discover, ThemeLibrary
import asyncio

async def set_room_theme(room_name: str, theme_name: str):
    """Apply theme to all lights in a specific room (group)."""
    async with discover() as lights:
        theme = ThemeLibrary.get(theme_name)
        groups = await lights.organize_by_group()

        if room_name in groups:
            room_lights = groups["room_name"]

        for light in room_lights.lights:
            await light.apply_theme(theme, power_on=True)

        for strip in room_lights.multizone_lights:
            await strip.apply_theme(theme, power_on=True)

# Usage:
# await set_room_theme("bedroom", "peaceful")
# await set_room_theme("kitchen", "focusing")
```

### Home Scene Presets

```python
from lifx import discover, ThemeLibrary

async def activate_scene(scene: str):
    """Activate a pre-defined home scene."""
    scenes = {
        "movie_night": {
            "living_room": "stardust",
            "kitchen": "evening",
            "bedroom": "peaceful",
        },
        "date_night": {
            "living_room": "romantic",
            "bedroom": "romance",
        },
        "party": {
            "living_room": "party",
            "kitchen": "energizing",
        },
        "focus": {
            "home_office": "focusing",
            "kitchen": "energizing",
        },
    }

    if scene not in scenes:
        print(f"Scene '{scene}' not found")
        return

    async with discover() as lights:

        groups = lights.organize_by_group()

        for room, theme_name in scenes[scene].items():
            if room not in groups:
                continue

            room_lights = groups["room"]
            theme = ThemeLibrary.get(theme_name)

            for light in room_lights.lights:
                await light.apply_theme(theme, power_on=True, duration=1.5)

            for strip in room_lights.multizone_lights:
                await strip.apply_theme(theme, power_on=True, duration=1.5)

# Usage:
# await activate_scene("movie_night")
# await activate_scene("party")
```

## Custom Themes

### Create Branded Theme

```python
from lifx import HSBK, Theme, discover

# Create corporate branding theme
corporate_theme = Theme([
    HSBK(hue=220, saturation=0.8, brightness=0.9, kelvin=4000),  # Professional blue
    HSBK(hue=0, saturation=0.7, brightness=0.8, kelvin=4000),     # Corporate red
    HSBK(hue=200, saturation=0.5, brightness=0.7, kelvin=4000),   # Light blue
])

async with discover() as lights:
    await lights.apply_theme(corporate_theme)
```

### Sunset Gradient

```python
from lifx import HSBK, Theme, discover

# Create sunset-inspired gradient
sunset_theme = Theme([
    HSBK(hue=45, saturation=1.0, brightness=1.0, kelvin=3000),   # Orange
    HSBK(hue=15, saturation=0.9, brightness=0.9, kelvin=2700),   # Deep orange
    HSBK(hue=0, saturation=0.8, brightness=0.8, kelvin=2500),    # Red
    HSBK(hue=320, saturation=0.7, brightness=0.7, kelvin=2400),  # Deep red
])

async with discover() as lights:
    await lights.apply_theme(sunset_theme, duration=3.0)
```

## Error Handling

### Robust Theme Application

```python
from lifx import discover, ThemeLibrary, LifxTimeoutError, LifxDeviceNotFoundError

async def safe_apply_theme(theme_name: str):
    """Apply theme with comprehensive error handling."""
    try:
        # Validate theme exists
        theme = ThemeLibrary.get(theme_name)
    except KeyError as e:
        print(f"Theme error: {e}")
        return False

    try:
        async with discover() as lights:
            if not lights:
                print("No lights found")
                return False

            await lights.apply_theme(theme, power_on=True, duration=1.5)
            print(f"Successfully applied '{theme_name}' theme")
            return True

    except LifxTimeoutError:
        print("Timeout: Devices did not respond in time")
        return False
    except LifxDeviceNotFoundError:
        print("Device error: Could not reach device")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
```

## Performance Tips

### Batch Operations

When applying themes to many devices, use `DeviceGroup.apply_theme()` for concurrent execution:

```python
from lifx import discover, ThemeLibrary

async with discover() as lights:
    theme = ThemeLibrary.get("evening")
    # All devices updated concurrently
    await lights.apply_theme(theme)
```

### Avoid Rapid Transitions

```python
from lifx import discover, ThemeLibrary
import asyncio

async with discover() as lights:
    themes = ["evening", "relaxing", "peaceful"]

    for theme_name in themes:
        theme = ThemeLibrary.get(theme_name)
        await lights.apply_theme(theme, duration=2.0)
        # Wait for transition to complete
        await asyncio.sleep(2.5)
```

## See Also

- [Themes API Reference](../api/themes.md) - Complete API documentation
- [Quick Start: Themes](../getting-started/themes.md) - Simple examples
- [Colors Guide](../api/colors.md) - Working with HSBK colors
- [Device Classes](../api/devices.md) - Device-specific documentation
