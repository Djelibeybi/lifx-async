# Creating Custom Effects

This guide shows you how to create your own light effects by subclassing the `LIFXEffect` base class. You'll learn the required methods, common patterns, and best practices for building custom effects.

## Table of Contents

- [Overview](#overview)
- [Basic Structure](#basic-structure)
- [Required Methods](#required-methods)
- [Optional Methods](#optional-methods)
- [Common Patterns](#common-patterns)
- [Complete Examples](#complete-examples)
- [Best Practices](#best-practices)

## Overview

Creating a custom effect involves:

1. Subclass `LIFXEffect`
2. Implement `async_play()` with your effect logic
3. Optionally override `from_poweroff_hsbk()` for custom startup colors
4. Optionally override `inherit_prestate()` for state inheritance optimization

The conductor handles all state management automatically - you just focus on the visual effect.

## Basic Structure

Every custom effect follows this pattern:

```python
from lifx import LIFXEffect, Light

class MyCustomEffect(LIFXEffect):
    """Brief description of what this effect does."""

    def __init__(self, param1, param2, power_on: bool = True):
        """Initialize the effect with custom parameters.

        Args:
            param1: Description of parameter 1
            param2: Description of parameter 2
            power_on: Whether to power on devices (default True)
        """
        super().__init__(power_on=power_on)
        self.param1 = param1
        self.param2 = param2

    async def async_play(self) -> None:
        """Execute the effect logic."""
        # Your effect implementation here
        pass
```

### Minimal Example

Here's the simplest possible custom effect:

```python
from lifx.effects import LIFXEffect
import asyncio

class FlashEffect(LIFXEffect):
    """Flash all lights once."""

    async def async_play(self) -> None:
        # Turn all lights on
        tasks = [light.set_brightness(1.0) for light in self.participants]
        await asyncio.gather(*tasks)
        await asyncio.sleep(0.5)

        # Turn all lights off
        tasks = [light.set_brightness(0.0) for light in self.participants]
        await asyncio.gather(*tasks)
        await asyncio.sleep(0.5)

        # Restore state
        if self.conductor:
            await self.conductor.stop(self.participants)
```

Usage:

```python
conductor = Conductor()
effect = FlashEffect()
await conductor.start(effect, lights)
await asyncio.sleep(2)
```

## Required Methods

### `async_play() -> None`

This is the **only required method** you must implement. This is where your effect logic lives.

**Important:** This method is `async` - use `await` for all async operations.

**Available attributes:**

- `self.participants`: List of `Light` instances to apply effect to
- `self.conductor`: Reference to the `Conductor` managing this effect
- `self.power_on`: Whether devices should be powered on (already handled)

**When called:**

After the conductor has:

1. Captured device state
2. Powered on devices (if `power_on=True`)

**Example:**

```python
async def async_play(self) -> None:
    """Cycle through red, green, blue."""
    from lifx import HSBK

    colors = [
        HSBK.from_rgb(255, 0, 0),    # Red
        HSBK.from_rgb(0, 255, 0),    # Green
        HSBK.from_rgb(0, 0, 255),    # Blue
    ]

    for color in colors:
        # Apply color to all lights concurrently
        tasks = [
            light.set_color(color, duration=0.5)
            for light in self.participants
        ]
        await asyncio.gather(*tasks)
        await asyncio.sleep(1.0)

    # Restore original state
    if self.conductor:
        await self.conductor.stop(self.participants)
```

**Key Points:**

- Use `asyncio.gather()` to apply operations to multiple devices concurrently
- Call `self.conductor.stop(self.participants)` when effect is complete to restore state
- Don't forget `await` on async operations

## Optional Methods

### `from_poweroff_hsbk(light: Light) -> HSBK`

Override this to customize the color used when powering on a device.

**Default behavior:** Returns random hue, full saturation, zero brightness, neutral white.

**When called:** When a device needs to be powered on for the effect (if it was off when effect started).

**Example:**

```python
async def from_poweroff_hsbk(self, light: Light) -> HSBK:
    """Always start with soft blue."""
    return HSBK.from_rgb(0, 50, 200, kelvin=KELVIN_NEUTRAL)
```

**Use cases:**

- Effect always starts with specific color
- Effect wants coordinated startup across devices
- Effect wants device-specific startup colors

### `inherit_prestate(other: LIFXEffect) -> bool`

Override this to enable state inheritance optimization.

**Default behavior:** Returns `False` (always capture fresh state).

**When called:** Before starting effect, to check if previous effect's state can be reused.

**Example:**

```python
def inherit_prestate(self, other: LIFXEffect) -> bool:
    """Can inherit from same effect type."""
    return type(self) == type(other)
```

**Returns:**

- `True`: Skip state capture/restore, reuse existing `PreState`
- `False`: Capture fresh state as normal

**Benefits:**

- Faster effect transitions
- No visible reset between compatible effects
- Reduces network traffic

**Use with caution:** Only return `True` if the incoming effect is truly compatible (won't cause visual artifacts).

## Common Patterns

### Pattern 1: Synchronized Actions

All devices do the same thing at the same time:

```python
async def async_play(self) -> None:
    """Pulse all devices together."""
    for cycle in range(self.cycles):
        # All bright
        await asyncio.gather(*[
            light.set_brightness(1.0, duration=0.3)
            for light in self.participants
        ])
        await asyncio.sleep(0.5)

        # All dim
        await asyncio.gather(*[
            light.set_brightness(0.2, duration=0.3)
            for light in self.participants
        ])
        await asyncio.sleep(0.5)

    if self.conductor:
        await self.conductor.stop(self.participants)
```

### Pattern 2: Sequential Actions

Devices act one after another (wave effect):

```python
async def async_play(self) -> None:
    """Light up devices sequentially."""
    for light in self.participants:
        await light.set_color(self.color, duration=0.5)
        await asyncio.sleep(self.delay)

    if self.conductor:
        await self.conductor.stop(self.participants)
```

### Pattern 3: Continuous Loop Until Stopped

Effect runs indefinitely (like ColorLoop):

```python
async def async_play(self) -> None:
    """Continuous random color changes."""
    import random

    self._running = True
    while self._running:
        # Random color for each device
        tasks = []
        for light in self.participants:
            hue = random.randint(0, 360)
            color = HSBK(hue, 1.0, 1.0, KELVIN_NEUTRAL)
            tasks.append(light.set_color(color, duration=1.0))

        await asyncio.gather(*tasks)
        await asyncio.sleep(self.interval)

    if self.conductor:
        await self.conductor.stop(self.participants)

def stop(self) -> None:
    """Stop the effect."""
    self._running = False
```

**Usage:**

```python
effect = RandomColorEffect(interval=2.0)
await conductor.start(effect, lights)
await asyncio.sleep(30)
effect.stop()  # Signal to stop
```

### Pattern 4: Device-Specific Behavior

Different actions based on device properties:

```python
async def async_play(self) -> None:
    """Different colors based on device label."""
    tasks = []
    for light in self.participants:
        label = await light.get_label()

        if "Bedroom" in label:
            color = HSBK.from_rgb(0, 0, 255)  # Blue
        elif "Kitchen" in label:
            color = HSBK.from_rgb(255, 255, 255)  # White
        else:
            color = HSBK.from_rgb(255, 0, 0)  # Red

        tasks.append(light.set_color(color, duration=1.0))

    await asyncio.gather(*tasks)
    await asyncio.sleep(2.0)

    if self.conductor:
        await self.conductor.stop(self.participants)
```

### Pattern 5: State Access

Access current device state during effect:

```python
async def async_play(self) -> None:
    """Pulse brighter than current brightness."""
    for light in self.participants:
        # Get current state
        current_color, _, _ = await light.get_color()

        # Create brighter version
        bright_color = current_color.with_brightness(1.0)

        # Pulse
        await light.set_color(bright_color, duration=0.3)
        await asyncio.sleep(0.5)
        await light.set_color(current_color, duration=0.3)
        await asyncio.sleep(0.5)

    if self.conductor:
        await self.conductor.stop(self.participants)
```

**Note:** Conductor already captured state, so you can also access it via the prestate (though this requires conductor internals access).

## Complete Examples

### Example 1: Flash Effect

Flash all lights in unison with configurable count and duration:

```python
from lifx import LIFXEffect
import asyncio

class FlashEffect(LIFXEffect):
    """Flash all lights in unison.

    Simple effect that demonstrates basic synchronization across devices.
    """

    def __init__(
        self,
        flash_count: int = 5,
        duration: float = 0.5,
        power_on: bool = True
    ) -> None:
        """Initialize flash effect.

        Args:
            flash_count: Number of flashes
            duration: Duration of each flash in seconds
            power_on: Whether to power on lights if off
        """
        super().__init__(power_on=power_on)
        self.flash_count = flash_count
        self.duration = duration

    async def async_play(self) -> None:
        """Execute the flash effect on all participants."""
        for i in range(self.flash_count):
            # All devices on
            tasks = [light.set_brightness(1.0) for light in self.participants]
            await asyncio.gather(*tasks)
            await asyncio.sleep(self.duration / 2)

            # All devices off
            tasks = [light.set_brightness(0.0) for light in self.participants]
            await asyncio.gather(*tasks)
            await asyncio.sleep(self.duration / 2)

        # Restore state
        if self.conductor:
            await self.conductor.stop(self.participants)
```

**Usage:**

```python
conductor = Conductor()
effect = FlashEffect(flash_count=10, duration=0.3)
await conductor.start(effect, lights)
await asyncio.sleep(4)
```

### Example 2: Wave Effect

Sequential color wave across multiple lights:

```python
from lifx.effects import LIFXEffect
from lifx import HSBK
import asyncio

class WaveEffect(LIFXEffect):
    """Create a color wave across multiple lights.

    More complex example showing sequential color updates across devices.
    """

    def __init__(
        self,
        wave_count: int = 3,
        wave_speed: float = 0.3,
        power_on: bool = True
    ) -> None:
        """Initialize wave effect.

        Args:
            wave_count: Number of waves to run
            wave_speed: Speed of wave in seconds per light
            power_on: Whether to power on lights if off
        """
        super().__init__(power_on=power_on)
        self.wave_count = wave_count
        self.wave_speed = wave_speed

    async def async_play(self) -> None:
        """Execute the wave effect."""
        # Define wave colors
        colors = [
            HSBK.from_rgb(255, 0, 0),      # Red
            HSBK.from_rgb(255, 127, 0),    # Orange
            HSBK.from_rgb(255, 255, 0),    # Yellow
            HSBK.from_rgb(0, 255, 0),      # Green
            HSBK.from_rgb(0, 0, 255),      # Blue
        ]

        for wave in range(self.wave_count):
            # Wave forward
            for i, light in enumerate(self.participants):
                color = colors[i % len(colors)]
                await light.set_color(color, duration=self.wave_speed)
                await asyncio.sleep(self.wave_speed)

            await asyncio.sleep(0.5)  # Pause between waves

        # Restore state
        if self.conductor:
            await self.conductor.stop(self.participants)
```

**Usage:**

```python
conductor = Conductor()
effect = WaveEffect(wave_count=3, wave_speed=0.4)
await conductor.start(effect, lights)
total_time = 3 * (len(lights) * 0.4 + 0.5)
await asyncio.sleep(total_time + 1)
```

### Example 3: Random Color Effect

Continuous random color changes until stopped:

```python
from lifx.effects import LIFXEffect
from lifx import HSBK
import asyncio
import random

class RandomColorEffect(LIFXEffect):
    """Continuously change to random colors.

    Example of continuous effect that runs until stopped.
    """

    def __init__(
        self,
        interval: float = 2.0,
        saturation_min: float = 0.7,
        saturation_max: float = 1.0,
        power_on: bool = True
    ) -> None:
        """Initialize random color effect.

        Args:
            interval: Seconds between color changes
            saturation_min: Minimum saturation (0.0-1.0)
            saturation_max: Maximum saturation (0.0-1.0)
            power_on: Whether to power on lights if off
        """
        super().__init__(power_on=power_on)
        self.interval = interval
        self.saturation_min = saturation_min
        self.saturation_max = saturation_max
        self._running = False

    async def async_play(self) -> None:
        """Execute random color changes continuously."""
        self._running = True

        while self._running:
            # Random color for each device
            tasks = []
            for light in self.participants:
                color = HSBK(
                    hue=random.randint(0, 360),
                    saturation=random.uniform(self.saturation_min, self.saturation_max),
                    brightness=1.0,
                    kelvin=KELVIN_NEUTRAL
                )
                tasks.append(light.set_color(color, duration=self.interval * 0.8))

            await asyncio.gather(*tasks)
            await asyncio.sleep(self.interval)

        # Restore state when stopped
        if self.conductor:
            await self.conductor.stop(self.participants)

    def stop(self) -> None:
        """Stop the continuous effect."""
        self._running = False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Can inherit from other RandomColorEffect instances."""
        return isinstance(other, RandomColorEffect)
```

**Usage:**

```python
conductor = Conductor()
effect = RandomColorEffect(interval=3.0, saturation_min=0.8)
await conductor.start(effect, lights)
await asyncio.sleep(30)
effect.stop()  # Signal to stop
await asyncio.sleep(3)  # Wait for current iteration to finish
```

### Example 4: Notification Effect

Different visual patterns based on notification level:

```python
from lifx.effects import LIFXEffect
from lifx import HSBK
import asyncio

class NotificationEffect(LIFXEffect):
    """Visual notification with different levels.

    Example showing how to implement different behaviors in one effect class.
    """

    def __init__(
        self,
        level: str = 'info',
        power_on: bool = True
    ) -> None:
        """Initialize notification effect.

        Args:
            level: Notification level ('info', 'warning', 'error')
            power_on: Whether to power on lights if off
        """
        super().__init__(power_on=power_on)
        if level not in ('info', 'warning', 'error'):
            raise ValueError(f"Invalid level: {level}")
        self.level = level

    async def async_play(self) -> None:
        """Execute notification based on level."""
        if self.level == 'info':
            await self._info_notification()
        elif self.level == 'warning':
            await self._warning_notification()
        elif self.level == 'error':
            await self._error_notification()

        # Restore state
        if self.conductor:
            await self.conductor.stop(self.participants)

    async def _info_notification(self) -> None:
        """Blue breathe - calm information."""
        blue = HSBK.from_rgb(0, 0, 255)
        for _ in range(2):
            await asyncio.gather(*[
                light.set_color(blue, duration=0.5)
                for light in self.participants
            ])
            await asyncio.sleep(0.7)
            await asyncio.gather(*[
                light.set_brightness(0.3, duration=0.5)
                for light in self.participants
            ])
            await asyncio.sleep(0.7)

    async def _warning_notification(self) -> None:
        """Orange blink - attention needed."""
        orange = HSBK.from_rgb(255, 165, 0)
        for _ in range(3):
            await asyncio.gather(*[
                light.set_color(orange, duration=0.1)
                for light in self.participants
            ])
            await asyncio.sleep(0.5)
            await asyncio.gather(*[
                light.set_brightness(0.0, duration=0.1)
                for light in self.participants
            ])
            await asyncio.sleep(0.5)

    async def _error_notification(self) -> None:
        """Red strobe - urgent."""
        red = HSBK.from_rgb(255, 0, 0)
        for _ in range(10):
            await asyncio.gather(*[
                light.set_color(red, duration=0.0)
                for light in self.participants
            ])
            await asyncio.sleep(0.1)
            await asyncio.gather(*[
                light.set_brightness(0.0, duration=0.0)
                for light in self.participants
            ])
            await asyncio.sleep(0.1)

    async def from_poweroff_hsbk(self, light: Light) -> HSBK:
        """Return appropriate startup color based on level."""
        if self.level == 'info':
            return HSBK.from_rgb(0, 0, 255)  # Blue
        elif self.level == 'warning':
            return HSBK.from_rgb(255, 165, 0)  # Orange
        else:
            return HSBK.from_rgb(255, 0, 0)  # Red
```

**Usage:**

```python
conductor = Conductor()

# Different notification levels
await conductor.start(NotificationEffect(level='info'), lights)
await asyncio.sleep(3)

await conductor.start(NotificationEffect(level='warning'), lights)
await asyncio.sleep(3)

await conductor.start(NotificationEffect(level='error'), lights)
await asyncio.sleep(3)
```

## Best Practices

### 1. Always Restore State

Call `conductor.stop()` when your effect is complete:

```python
async def async_play(self) -> None:
    # Effect logic here
    ...

    # Always restore at the end
    if self.conductor:
        await self.conductor.stop(self.participants)
```

### 2. Use Concurrent Operations

Use `asyncio.gather()` for operations on multiple devices:

```python
# Good - concurrent
await asyncio.gather(*[
    light.set_color(color) for light in self.participants
])

# Bad - sequential (much slower)
for light in self.participants:
    await light.set_color(color)
```

### 3. Validate Parameters

Validate constructor parameters early:

```python
def __init__(self, count: int, power_on: bool = True):
    super().__init__(power_on=power_on)

    if count < 1:
        raise ValueError(f"Count must be positive, got {count}")

    self.count = count
```

### 4. Add Type Hints

Full type hints improve IDE support and catch bugs:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lifx import Light

class MyEffect(LIFXEffect):
    def __init__(self, duration: float, power_on: bool = True) -> None:
        super().__init__(power_on=power_on)
        self.duration: float = duration

    async def async_play(self) -> None:
        ...

    async def from_poweroff_hsbk(self, light: Light) -> HSBK:
        ...
```

### 5. Document Your Effect

Clear docstrings help users understand your effect:

```python
class MyEffect(LIFXEffect):
    """Brief one-line description.

    Longer description explaining:
    - What the effect does
    - When to use it
    - Any important behavior

    Example:
        ```python
        conductor = Conductor()
        effect = MyEffect(duration=2.0)
        await conductor.start(effect, lights)
        await asyncio.sleep(3)
        ```
    """
```

### 6. Handle Errors Gracefully

Catch and log errors, don't let one device break the effect:

```python
import logging

_LOGGER = logging.getLogger(__name__)

async def async_play(self) -> None:
    for light in self.participants:
        try:
            await light.set_color(self.color)
        except Exception as e:
            _LOGGER.error(f"Failed to set color on {light.serial}: {e}")
            # Continue with other lights
```

### 7. Timing Considerations

Add small buffers to timing for reliability:

```python
# Good - includes buffer
total_duration = self.count * self.period
await asyncio.sleep(total_duration + 0.5)

# Better - exact but requires careful calculation
await asyncio.sleep(self.count * self.period)
```

### 8. Test with Different Device Types

Test your effect with:

- Single color light
- Multiple color lights
- Multizone light (if applicable)
- Powered-off devices
- Mix of on/off devices

### 9. Consider Rate Limiting

For effects with many rapid commands, consider rate limiting:

```python
async def async_play(self) -> None:
    for iteration in range(self.iterations):
        # Send commands
        await self._apply_colors()

        # Rate limit: max 20 messages/second
        await asyncio.sleep(0.05)
```

### 10. Use Descriptive Names

Choose clear, descriptive names for effects and parameters:

```python
# Good
class PulseWaveEffect(LIFXEffect):
    def __init__(self, wave_count: int, wave_period: float):
        ...

# Less clear
class Effect1(LIFXEffect):
    def __init__(self, n: int, t: float):
        ...
```

## See Also

- [Getting Started](../getting-started/effects.md) - Basic usage of built-in effects
- [Effects Reference](../api/effects.md) - Detailed API documentation
- [Architecture](../architecture/effects-architecture.md) - How the system works internally
- [Troubleshooting](effects-troubleshooting.md) - Common issues and solutions
- [Examples](../../examples/) - Full working examples including `08_custom_effect.py`
