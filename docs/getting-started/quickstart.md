# Quick Start

Get up and running with lifx-async in minutes!

## Basic Usage

### 1. Discover Lights

The simplest way to find and control LIFX lights:

```python
import asyncio
from lifx import discover


async def main():
    count = 0
    async for device in discover():
        count += 1
        print(f"Found: {device.serial}")
    print(f"Total: {count} lights")


asyncio.run(main())
```

**Alternative: mDNS Discovery**

For faster discovery with device type detection in a single query:

```python
import asyncio
from lifx import discover_mdns


async def main():
    async for device in discover_mdns():
        async with device:
            color, power, label = await device.get_color()
            print(f"{label}: {type(device).__name__}")


asyncio.run(main())
```

mDNS discovery is faster because it gets device type information directly from the mDNS response, eliminating extra network queries.

### 2. Control a Light

Turn on the first discovered light, then change its color:

```python
import asyncio
from lifx import discover, Colors


async def main():
    async for light in discover():
        await light.set_power(True)
        await light.set_color(Colors.BLUE, duration=1.0)
        break


asyncio.run(main())
```

### 3. Batch Operations

Control multiple lights as a group:

```python
import asyncio
from lifx import discover, DeviceGroup, Colors


async def main():
    devices = []
    async for device in discover():
        devices.append(device)

    # Create DeviceGroup for batch operations
    group = DeviceGroup(devices)
    await group.set_power(True)
    await group.set_color(Colors.BLUE, duration=1.0)
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

### Find Specific Devices

Find devices by label, IP, or serial:

```python
import asyncio
from lifx import find_by_label, find_by_ip, find_by_serial, Colors


async def main():
    # Find by label (substring match)
    async for device in find_by_label("Bedroom"):  # Matches "Bedroom", "Master Bedroom", etc.
        await device.set_color(Colors.WARM_WHITE)

    # Find by exact label
    async for device in find_by_label("Master Bedroom", exact_match=True):
        await device.set_brightness(0.8)
        break  # exact_match returns at most one device

    # Find by IP address (fastest if you only know the IP)
    device = await find_by_ip("192.168.1.100")
    if device:
        await device.set_power(True)

    # Find by serial number
    device = await find_by_serial("d073d5123456")
    if device:
        await device.set_color(Colors.BLUE)


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
from lifx import discover, Colors, LifxError


async def main():
    try:
        async for device in discover():
            await device.set_color(Colors.GREEN)
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
