# Getting Started with Light Effects

The Light Effects Framework provides a comprehensive system for creating and managing visual effects on LIFX devices. This guide will help you get started with the built-in effects and show you common patterns for using the effects system.

## Overview

The effects framework consists of three main components:

- **Conductor**: Central orchestrator that manages effect lifecycle and state
- **Effects**: Pre-built effect classes (Pulse, ColorLoop, Rainbow, Flame, Aurora, Progress, Sunrise/Sunset) and base class for custom effects
- **Effect Registry**: Central discovery mechanism for querying available effects by device type
- **State Management**: Automatic capture and restoration of device state before and after effects

## Installation

The effects framework is included with lifx-async 1.3.0+. No additional installation is required:

```bash
# Using uv (recommended)
uv pip install lifx-async

# Or using pip
pip install lifx-async
```

## Basic Usage

### Your First Pulse Effect

The simplest way to use the effects framework is with the `EffectPulse` class:

```python
import asyncio
from lifx import discover, DeviceGroup
from lifx.effects import Conductor, EffectPulse

async def main():
    # Discover lights on your network
    devices = []
    async for device in discover():
        devices.append(device)
    group = DeviceGroup(devices)

    if not group.lights:
        print("No lights found")
        return

    # Create a conductor to manage effects
    conductor = Conductor()

    # Create a blink effect
    effect = EffectPulse(mode='blink', cycles=5)

    # Start the effect on all lights
    await conductor.start(effect, group.lights)

    # Wait for effect to complete (5 cycles * 1 second)
    await asyncio.sleep(6)

    print("Effect complete - lights restored to original state")

asyncio.run(main())
```

### Your First ColorLoop Effect

The `EffectColorloop` creates a continuous rainbow effect:

```python
import asyncio
from lifx import discover, DeviceGroup
from lifx.effects import Conductor, EffectColorloop

async def main():
    devices = []
    async for device in discover():
        devices.append(device)
    group = DeviceGroup(devices)

    if not group.lights:
        print("No lights found")
        return

    conductor = Conductor()

        # Create a rainbow effect
        effect = EffectColorloop(
            period=30,      # 30 seconds per full cycle
            change=20,      # Change hue by 20 degrees each step
            spread=60       # Spread colors across devices
        )

        # Start the effect
        await conductor.start(effect, group.lights)

        # Let it run for 2 minutes
        await asyncio.sleep(120)

        # Stop and restore lights to original state
        await conductor.stop(group.lights)

asyncio.run(main())
```

### Rainbow Effect

The `EffectRainbow` spreads a full 360-degree rainbow across device pixels and scrolls it over time. Best on multizone strips and matrix lights:

```python
import asyncio
from lifx import discover, DeviceGroup
from lifx.effects import Conductor, EffectRainbow

async def main():
    devices = []
    async for device in discover():
        devices.append(device)
    group = DeviceGroup(devices)

    if not group.lights:
        print("No lights found")
        return

    conductor = Conductor()

    # Rainbow that scrolls every 10 seconds
    effect = EffectRainbow(period=10, brightness=0.8)
    await conductor.start(effect, group.lights)

    await asyncio.sleep(30)
    await conductor.stop(group.lights)

asyncio.run(main())
```

### Flame Effect

The `EffectFlame` creates a warm fire/candle flicker using layered sine waves. On matrix devices, bottom rows glow hotter:

```python
from lifx.effects import EffectFlame

# Default candle flicker
effect = EffectFlame()
await conductor.start(effect, lights)

# Intense fast fire with wide temperature range
effect = EffectFlame(intensity=1.0, speed=2.0, brightness=1.0)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

### Aurora Effect

The `EffectAurora` simulates northern lights with flowing colored bands. Best on multizone strips and matrix lights:

```python
from lifx.effects import EffectAurora

# Default aurora (green/cyan/blue/purple)
effect = EffectAurora()
await conductor.start(effect, lights)

# Custom warm palette
effect = EffectAurora(palette=[280, 300, 320, 340], brightness=0.6)
await conductor.start(effect, lights)

await asyncio.sleep(60)
await conductor.stop(lights)
```

### Progress Bar Effect

The `EffectProgress` creates an animated progress bar on multizone lights (strips/beams). The filled region has a traveling bright spot, and you update the position at any time:

```python
from lifx.effects import EffectProgress

effect = EffectProgress(end_value=100)
await conductor.start(effect, [strip_light])

# Update progress from your application logic
for i in range(0, 101, 10):
    effect.position = float(i)
    await asyncio.sleep(2)

await conductor.stop([strip_light])
```

### Sunrise and Sunset Effects

`EffectSunrise` and `EffectSunset` are duration-based effects for matrix devices (tiles, candles, Ceiling lights) that simulate natural light transitions:

```python
from lifx.effects import EffectSunrise, EffectSunset

# 30-minute sunrise from bottom edge (rectangular tiles)
effect = EffectSunrise(duration=1800, brightness=1.0)
await conductor.start(effect, [matrix_light])

# Sunrise from center (round/oval Ceiling lights)
effect = EffectSunrise(duration=1800, brightness=1.0, origin="center")
await conductor.start(effect, [ceiling_light])

# Sunset that powers off when done
effect = EffectSunset(duration=1800, power_off=True)
await conductor.start(effect, [matrix_light])
```

Sunrise and sunset effects complete automatically after their duration — no need to call `conductor.stop()`. Sunrise leaves the light at full daylight. Sunset can optionally power off the light.

## Key Concepts

### Conductor

The `Conductor` is the central orchestrator that:

- Captures device state before effects run
- Powers on devices if needed
- Executes effects
- Restores devices to original state when done

You typically create one conductor instance and reuse it for multiple effects.

### Effect State Management

The effects framework automatically:

1. **Captures** current state (power, color, zones) before effect starts
1. **Powers on** devices if they're off (configurable)
1. **Executes** the effect
1. **Restores** all devices to their pre-effect state

This happens completely automatically - you don't need to manage state yourself.

### Effect Completion

Effects complete in different ways:

1. **Cycle-based** — Pulse effects complete after their configured cycles finish
1. **Duration-based** — Sunrise and sunset effects complete after their duration expires
1. **Manual** — Continuous effects (ColorLoop, Rainbow, Flame, Aurora, Progress) run until `conductor.stop()` is called

## Common Patterns

### Using Specific Lights

You can apply effects to specific lights instead of all discovered devices:

```python
from lifx import discover, DeviceGroup

devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

conductor = Conductor()

# Get lights by label
bedroom_lights = [
    light for light in group.lights
    if "Bedroom" in await light.get_label()
]

# Apply effect only to bedroom lights
effect = EffectPulse(mode='breathe', cycles=3)
await conductor.start(effect, bedroom_lights)
await asyncio.sleep(4)
```

### Sequential Effects

You can run multiple effects one after another:

```python
conductor = Conductor()

# First effect: blink
effect1 = EffectPulse(mode='blink', cycles=3)
await conductor.start(effect1, group.lights)
await asyncio.sleep(4)

# Second effect: breathe
effect2 = EffectPulse(mode='breathe', cycles=2)
await conductor.start(effect2, group.lights)
await asyncio.sleep(5)
```

Note: The conductor automatically restores state between effects, so each effect starts with the original device state.

### Concurrent Effects on Different Devices

You can run different effects on different groups of lights simultaneously:

```python
conductor = Conductor()

# Split lights into two groups
group1 = group.lights[:len(group.lights)//2]
group2 = group.lights[len(group.lights)//2:]

# Start both effects concurrently
effect1 = EffectPulse(mode='blink')
effect2 = EffectColorloop(period=20)

await conductor.start(effect1, group1)
await conductor.start(effect2, group2)

# Let them run
await asyncio.sleep(30)

# Stop all
await conductor.stop(group.lights)
```

### Custom Colors

Both pulse and colorloop effects support custom colors:

```python
from lifx import HSBK

# Create custom color
red = HSBK.from_rgb(255, 0, 0)
blue = HSBK.from_rgb(0, 0, 255)

# Pulse with custom color
effect = EffectPulse(mode='breathe', cycles=5, color=red)
await conductor.start(effect, group.lights)
await asyncio.sleep(6)
```

### Checking Running Effects

You can check what effect is currently running on a device:

```python
conductor = Conductor()
effect = EffectColorloop(period=30)
await conductor.start(effect, group.lights)

# Check what's running
for light in group.lights:
    current = conductor.effect(light)
    if current:
        print(f"{light.label}: {type(current).__name__}")
    else:
        print(f"{light.label}: idle")
```

### Effect Registry

The `EffectRegistry` lets you discover available effects and filter by device type — useful for building UIs or integrations like Home Assistant:

```python
from lifx import get_effect_registry, DeviceType

registry = get_effect_registry()

# List all built-in effects
for info in registry.effects:
    print(f"{info.name}: {info.description}")

# Get effects recommended for multizone strips
for info, support in registry.get_effects_for_device_type(DeviceType.MULTIZONE):
    print(f"{info.name} ({support.value})")

# Filter by actual device instance
for info, support in registry.get_effects_for_device(my_light):
    print(f"{info.name}: {support.value}")
```

### Dynamic Light Management

You can add or remove lights from a running effect without restarting it:

```python
# Start effect on initial lights
effect = EffectRainbow(period=10)
await conductor.start(effect, [light1, light2])

# Later, add a new light to the running effect
await conductor.add_lights(effect, [light3])

# Remove a light (restores its state by default)
await conductor.remove_lights([light2])

# Remove without restoring state
await conductor.remove_lights([light1], restore_state=False)
```

### Monitoring Frame Data

For frame-based effects, you can read the most recent HSBK values sent to a device:

```python
colors = conductor.get_last_frame(light)
if colors:
    avg_brightness = sum(c.brightness for c in colors) / len(colors)
    print(f"Average brightness: {avg_brightness:.1%}")
```

## Best Practices

### 1. Use a Single Conductor

Create one conductor instance and reuse it throughout your application:

```python
# Good
conductor = Conductor()
await conductor.start(effect1, lights)
await conductor.start(effect2, lights)

# Not recommended - creates unnecessary overhead
conductor1 = Conductor()
await conductor1.start(effect1, lights)
conductor2 = Conductor()
await conductor2.start(effect2, lights)
```

### 2. Always Wait for Completion

For pulse effects, wait for the effect duration before starting another:

```python
effect = EffectPulse(mode='blink', period=1.0, cycles=5)
await conductor.start(effect, lights)
# Wait for effect to complete
await asyncio.sleep(5 * 1.0 + 0.5)  # cycles * period + buffer
```

### 3. Stop ColorLoop Effects Explicitly

ColorLoop effects run indefinitely, so always call `conductor.stop()`:

```python
effect = EffectColorloop(period=30)
await conductor.start(effect, lights)
await asyncio.sleep(60)
# Must explicitly stop
await conductor.stop(lights)
```

### 4. Handle Discovery Failures

Always check if lights were found before attempting effects:

```python
from lifx import discover, DeviceGroup

devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

if not group.lights:
    print("No lights found on network")
    return

# Safe to use effects
conductor = Conductor()
# ...
```

### 5. Use DeviceGroup for Organization

The DeviceGroup provides convenient access to device collections:

```python
from lifx import discover, DeviceGroup

# Discover devices
devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

conductor = Conductor()
await conductor.start(effect, group.lights)
```

## Complete Examples

### Notification Effect

Use effects to create a notification system:

```python
async def notify(lights: list, level: str = 'info'):
    """Flash lights to indicate a notification."""
    conductor = Conductor()

    if level == 'info':
        # Blue breathe
        color = HSBK.from_rgb(0, 0, 255)
        effect = EffectPulse(mode='breathe', cycles=2, color=color)
    elif level == 'warning':
        # Orange blink
        color = HSBK.from_rgb(255, 165, 0)
        effect = EffectPulse(mode='blink', cycles=3, color=color)
    elif level == 'error':
        # Red strobe
        color = HSBK.from_rgb(255, 0, 0)
        effect = EffectPulse(mode='strobe', cycles=10, color=color)

    await conductor.start(effect, lights)
    await asyncio.sleep(4)  # Wait for completion

# Usage
from lifx import discover, DeviceGroup

devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

await notify(group.lights, level='warning')
```

### Party Mode

Cycle through different effects:

```python
async def party_mode(lights: list, duration: int = 60):
    """Run various effects for a party."""
    conductor = Conductor()
    end_time = asyncio.get_event_loop().time() + duration

    effects = [
        EffectColorloop(period=20, change=30, spread=60),
        EffectPulse(mode='strobe', cycles=20),
        EffectColorloop(period=15, change=45, brightness=0.8),
    ]

    effect_idx = 0
    while asyncio.get_event_loop().time() < end_time:
        effect = effects[effect_idx % len(effects)]

        if isinstance(effect, EffectColorloop):
            await conductor.start(effect, lights)
            await asyncio.sleep(20)
            await conductor.stop(lights)
        else:
            await conductor.start(effect, lights)
            await asyncio.sleep(3)

        effect_idx += 1

    # Ensure everything is stopped and restored
    await conductor.stop(lights)

# Usage
from lifx import discover, DeviceGroup

devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

await party_mode(group.lights, duration=120)
```

## Next Steps

- See [Effects Reference](https://djelibeybi.github.io/lifx-async/api/effects/index.md) for detailed documentation on all effect parameters
- See [Custom Effects](https://djelibeybi.github.io/lifx-async/user-guide/effects-custom/index.md) to learn how to create your own effects
- See [Effects Architecture](https://djelibeybi.github.io/lifx-async/architecture/effects-architecture/index.md) to understand how the system works internally
- See [Troubleshooting](https://djelibeybi.github.io/lifx-async/user-guide/effects-troubleshooting/index.md) for common issues and solutions
