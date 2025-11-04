# Quick Start

Get up and running with lifx-async in minutes!

## Basic Usage

### 1. Discover Lights

The simplest way to find and control LIFX lights:

```python
import asyncio
from lifx import discover


async def main():
    async with discover(timeout=3.0) as group:
        print(f"Found {len(group)} lights")


asyncio.run(main())
```

### 2. Control a Light

Turn on a light and change its color:

```python
import asyncio
from lifx import discover, Colors


async def main():
    async with discover() as group:
        if group.lights:
            light = group.lights[0]
            await light.set_power(True)
            await light.set_color(Colors.BLUE, duration=1.0)


asyncio.run(main())
```

### 3. Batch Operations

Control multiple lights at once:

```python
import asyncio
from lifx import discover, Colors


async def main():
    async with discover() as group:
        # Turn all lights on and blue
        await group.set_power(True)
        await group.set_color(Colors.BLUE, duration=1.0)

        # Set brightness
        await group.set_brightness(0.5)


asyncio.run(main())
```

## Common Patterns

### Direct Connection (No Discovery)

If you know the IP:

```python
import asyncio
from lifx import Light, Colors


async def main():
    async with await Light.from_ip("192.168.1.100") as light:
        await light.set_color(Colors.RED)


asyncio.run(main())
```

### Find Specific Device

Find a device by label:

```python
import asyncio
from lifx import find_lights


async def main():
    lights = await find_lights(label_contains="Bedroom")
    if lights:
        async with lights[0] as light:
            await light.set_color(Colors.WARM_WHITE)


asyncio.run(main())
```

### Color Presets

Use built-in color presets:

```python
from lifx import Colors

# Primary colors
Colors.RED
Colors.GREEN
Colors.BLUE

# White variants
Colors.WARM_WHITE
Colors.COOL_WHITE
Colors.DAYLIGHT

# Pastels
Colors.PASTEL_BLUE
Colors.PASTEL_PINK
```

### RGB to HSBK

Convert RGB values to HSBK:

```python
from lifx import HSBK

# Create color from RGB
purple = HSBK.from_rgb(128, 0, 128)
await light.set_color(purple)
```

### Effects

Create visual effects:

```python
import asyncio
from lifx import Light, Colors


async def main():
    async with await Light.from_ip("192.168.1.100") as light:
        # Pulse effect
        await light.pulse(Colors.RED, period=1.0, cycles=5)

        # Breathe effect (infinite)
        await light.breathe(Colors.BLUE, period=2.0, cycles=0)


asyncio.run(main())
```

## Error Handling

Always use proper error handling:

```python
import asyncio
from lifx import discover, LifxError


async def main():
    try:
        async with discover(timeout=3.0) as group:
            if not group:
                print("No devices found")
                return

            await group.set_color(Colors.GREEN)
    except LifxError as e:
        print(f"LIFX error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


asyncio.run(main())
```

## Next Steps

- [API Reference](../api/index.md) - Complete API documentation
- [Architecture](../architecture/overview.md) - How lifx-async works
- [FAQ](../faq.md) - Frequently asked questions
