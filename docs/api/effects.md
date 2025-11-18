# Effects Reference

This reference guide provides comprehensive documentation for all built-in effect classes in the Light Effects Framework.

## Table of Contents

- [Conductor](#conductor)
- [EffectPulse](#effectpulse)
- [EffectColorloop](#effectcolorloop)
- [LIFXEffect (Base Class)](#lifxeffect-base-class)

## Conductor

The `Conductor` class is the central orchestrator for managing light effects across multiple devices.

### Class Definition

```python
from lifx import Conductor

conductor = Conductor()
```

### Methods

#### `effect(light: Light) -> LIFXEffect | None`

Return the effect currently running on a device, or None if idle.

**Parameters:**

- `light` (Light): The device to check

**Returns:**

- `LIFXEffect | None`: Currently running effect instance, or None

**Example:**

```python
current_effect = conductor.effect(light)
if current_effect:
    print(f"Running: {type(current_effect).__name__}")
else:
    print("No effect running")
```

#### `start(effect: LIFXEffect, participants: list[Light]) -> None`

Start an effect on one or more lights.

Captures current light state, powers on if needed, and launches the effect. State is automatically restored when effect completes or `stop()` is called.

**Parameters:**

- `effect` (LIFXEffect): The effect instance to execute
- `participants` (list[Light]): List of Light instances to apply effect to

**Raises:**

- `LifxTimeoutError`: If light state capture times out
- `LifxDeviceNotFoundError`: If light becomes unreachable

**Example:**

```python
effect = EffectPulse(mode='blink', cycles=5)
await conductor.start(effect, [light1, light2])
```

#### `stop(lights: list[Light]) -> None`

Stop effects and restore light state.

Halts any running effects on the specified lights and restores them to their pre-effect state (power, color, zones).

**Parameters:**

- `lights` (list[Light]): List of lights to stop

**Example:**

```python
# Stop specific lights
await conductor.stop([light1, light2])

# Stop all lights in a group
await conductor.stop(group.lights)
```

### State Management

The conductor automatically handles:

1. **State Capture**: Power state, current color (HSBK), and multizone colors (if applicable)
2. **Power Management**: Powers on devices if needed for effect visibility
3. **Effect Execution**: Runs effect logic on all participants
4. **State Restoration**: Restores all captured state after effect completes

### Timing Considerations

- State capture: <1 second per device (mostly network I/O)
- State restoration: 0.6-1.0 seconds per device (includes required 0.3s delays)
- All operations use concurrent execution for multiple devices

---

## EffectPulse

Pulse/blink/breathe effects using LIFX waveform modes. Supports five distinct modes with configurable timing and colors.

### Class Definition

```python
from lifx import EffectPulse, HSBK

effect = EffectPulse(
    power_on=True,
    mode='blink',
    period=None,
    cycles=None,
    hsbk=None
)
```

### Parameters

#### `power_on` (bool, default: `True`)

Whether to power on devices during effect. If `True`, devices that are off will be powered on before the effect starts.

#### `mode` (str, default: `'blink'`)

Pulse mode to use. Must be one of:

- `'blink'`: Standard on/off toggle
- `'strobe'`: Rapid flashing
- `'breathe'`: Smooth breathing effect
- `'ping'`: Single pulse with asymmetric duty cycle
- `'solid'`: Minimal brightness variation

#### `period` (float | None, default: mode-dependent)

Effect period in seconds. If not specified, uses mode default:

- `'strobe'`: 0.1 seconds
- All others: 1.0 second

#### `cycles` (int | None, default: mode-dependent)

Number of cycles to execute. If not specified, uses mode default:

- `'strobe'`: 10 cycles
- All others: 1 cycle

#### `hsbk` (HSBK | None, default: `None`)

Optional color override. If provided, this color is used instead of automatic color selection. If `None`, the effect intelligently selects colors based on mode and device capabilities.

### Pulse Modes

#### Blink Mode

Standard on/off toggle effect.

**Defaults:**

- Period: 1.0 second
- Cycles: 1
- Waveform: PULSE
- Behavior: Toggles between current color and off

**Example:**

```python
# Basic blink - 5 cycles
effect = EffectPulse(mode='blink', cycles=5)
await conductor.start(effect, lights)
await asyncio.sleep(6)  # 5 cycles * 1s + buffer
```

**Best for:** Notifications, alerts, attention-getting

#### Strobe Mode

Rapid flashing effect.

**Defaults:**

- Period: 0.1 second
- Cycles: 10
- Waveform: PULSE
- Behavior: Rapid flashing from dark (cold white)

**Example:**

```python
# Rapid strobe - 20 flashes
effect = EffectPulse(mode='strobe', cycles=20)
await conductor.start(effect, lights)
await asyncio.sleep(3)  # 20 * 0.1s + buffer
```

**Best for:** Emergency notifications, dramatic effects

**Note:** Strobe mode starts from dark (0 brightness, cold white) for maximum impact.

#### Breathe Mode

Smooth, gentle breathing effect using SINE waveform.

**Defaults:**

- Period: 1.0 second
- Cycles: 1
- Waveform: SINE (smooth)
- Behavior: Smooth fade in and out

**Example:**

```python
# Slow breathing effect
effect = EffectPulse(mode='breathe', period=2.0, cycles=5)
await conductor.start(effect, lights)
await asyncio.sleep(11)  # 5 * 2s + buffer
```

**Best for:** Relaxation, meditation, ambient effects

#### Ping Mode

Single pulse with asymmetric duty cycle.

**Defaults:**

- Period: 1.0 second
- Cycles: 1
- Waveform: PULSE
- Skew: 0.1 (10% on, 90% off)
- Behavior: Quick flash followed by longer off period

**Example:**

```python
# Quick ping notification
red = HSBK.from_rgb(255, 0, 0)
effect = EffectPulse(mode='ping', color=red)
await conductor.start(effect, lights)
await asyncio.sleep(2)
```

**Best for:** Quick notifications, heartbeat effects

#### Solid Mode

Minimal brightness variation, almost solid color.

**Defaults:**

- Period: 1.0 second
- Cycles: 1
- Waveform: PULSE
- Skew: 0.0 (minimum variation)
- Behavior: Very subtle brightness change

**Example:**

```python
# Subtle solid pulse
green = HSBK.from_rgb(0, 255, 0)
effect = EffectPulse(mode='solid', period=3.0, cycles=2, color=green)
await conductor.start(effect, lights)
await asyncio.sleep(7)
```

**Best for:** Subtle ambient effects, status indicators

### Color Selection

#### With `color` Parameter

When you provide a `color` parameter, that exact color is used:

```python
# Always use red
red = HSBK.from_rgb(255, 0, 0)
effect = EffectPulse(mode='blink', color=red)
```

#### Without `color` Parameter (Automatic)

The effect intelligently selects colors based on mode and device:

- **Strobe mode**: Starts from dark (cold white, 0 brightness)
- **Other modes**: Preserves current device color
- **Color devices**: Full HSBK color used
- **Monochrome devices**: Brightness toggled, kelvin preserved

### Device Type Behavior

#### Color Lights

All modes work as expected with full color support.

#### Multizone Lights

Pulse effects apply to entire device, not individual zones. All zones pulse together.

#### Tile Devices

Pulse effects apply to all tiles uniformly.

#### Monochrome/White Lights

Effects adapt to brightness changes only:

- Color components are ignored
- Brightness is toggled or faded
- Kelvin temperature is preserved

### Examples

#### Custom Color Pulse

```python
from lifx import HSBK

# Purple breathe effect
purple = HSBK.from_rgb(128, 0, 128)
effect = EffectPulse(
    mode='breathe',
    period=2.0,
    cycles=3,
    hsbk=purple
)
await conductor.start(effect, lights)
await asyncio.sleep(7)
```

#### Emergency Alert

```python
# Rapid red strobe
red = HSBK.from_rgb(255, 0, 0)
effect = EffectPulse(
    mode='strobe',
    period=0.1,
    cycles=30,
    hsbk=red
)
await conductor.start(effect, lights)
await asyncio.sleep(4)
```

#### Meditation Breathing

```python
# Slow blue breathing
blue = HSBK.from_rgb(0, 50, 200)
effect = EffectPulse(
    mode='breathe',
    period=4.0,  # 4 second cycle
    cycles=10,
    hsbk=blue
)
await conductor.start(effect, lights)
await asyncio.sleep(42)  # 10 * 4s + buffer
```

### Performance Notes

- Effect starts within 100ms
- Duration is precisely `period * cycles`
- State restoration adds 0.6-1.0 seconds after completion
- Multiple devices execute concurrently

---

## EffectColorloop

Continuous color rotation effect cycling through the hue spectrum. Runs indefinitely until manually stopped.

### Class Definition

```python
from lifx import EffectColorloop

effect = EffectColorloop(
    power_on=True,
    period=60,
    change=20,
    spread=30,
    brightness=None,
    saturation_min=0.8,
    saturation_max=1.0,
    transition=None
)
```

### Parameters

#### `power_on` (bool, default: `True`)

Whether to power on devices if they're off.

#### `period` (float, default: `60`)

Seconds per full 360-degree hue cycle. Lower values = faster color changes.

**Range:** Must be positive

**Examples:**

- `period=60`: One full rainbow per minute (slow)
- `period=30`: Two full rainbows per minute (medium)
- `period=15`: Four full rainbows per minute (fast)

#### `change` (float, default: `20`)

Hue degrees to shift per iteration. Larger values = larger color jumps.

**Range:** 0-360 degrees

**Examples:**

- `change=10`: Small, smooth color transitions
- `change=20`: Medium color steps (default)
- `change=45`: Large, dramatic color jumps

**Calculation:** iterations_per_cycle = 360 / change

#### `spread` (float, default: `30`)

Hue degrees spread across devices. Creates rainbow effect across multiple lights.

**Range:** 0-360 degrees

**Examples:**

- `spread=0`: All lights same color
- `spread=30`: Slight color variation (default)
- `spread=60`: Rainbow spread across devices
- `spread=120`: Wide spectrum spread

#### `brightness` (float | None, default: `None`)

Fixed brightness level. If `None`, preserves current brightness for each device.

**Range:** 0.0-1.0

**Examples:**

- `brightness=None`: Keeps original brightness (default)
- `brightness=0.5`: Locks to 50% brightness
- `brightness=1.0`: Full brightness

#### `saturation_min` (float, default: `0.8`)

Minimum saturation for random saturation selection.

**Range:** 0.0-1.0

Must be ≤ `saturation_max`

#### `saturation_max` (float, default: `1.0`)

Maximum saturation for random saturation selection.

**Range:** 0.0-1.0

Must be ≥ `saturation_min`

**Note:** Each iteration randomly selects saturation within this range.

#### `transition` (float | None, default: `None`)

Color transition time in seconds. If `None`, uses random transition time per device.

**Range:** Non-negative

**Examples:**

- `transition=None`: Random transitions (0 to 2x iteration period)
- `transition=0.5`: Quick 0.5-second transitions
- `transition=2.0`: Slow 2-second transitions

### Behavior

#### Continuous Operation

ColorLoop effects run **indefinitely** until explicitly stopped:

```python
effect = EffectColorloop(period=30)
await conductor.start(effect, lights)

# Runs forever until you call:
await conductor.stop(lights)
```

#### Random Elements

For visual variety, ColorLoop randomizes:

1. **Initial direction**: Forward or backward through hue spectrum
2. **Device order**: Shuffled each cycle
3. **Saturation**: Random value between saturation_min and saturation_max
4. **Transition time**: Random if `transition=None`

#### Hue Calculation

For each device at each iteration:

```python
new_hue = (base_hue + iteration_offset + device_spread_offset) % 360

# Where:
# - base_hue: Initial hue when effect started
# - iteration_offset: iteration * change * direction
# - device_spread_offset: device_index * spread
```

### Device Type Behavior

#### Color Lights

Full color cycling with all parameters supported.

#### Multizone Lights

Entire device cycles as one unit (all zones same color at each iteration).

#### Tile Devices

All tiles cycle together with same color.

#### Monochrome/White Lights

- Hue changes are ignored (monochrome devices can't display colors)
- Brightness and saturation parameters are ignored
- Effect still runs but with no visible changes
- **Recommendation**: Don't use ColorLoop on monochrome devices

### Examples

#### Classic Rainbow

```python
# Slow rainbow across multiple lights
effect = EffectColorloop(
    period=60,      # Full rainbow per minute
    change=20,      # Smooth color steps
    spread=60       # Spread colors across devices
)
await conductor.start(effect, lights)
await asyncio.sleep(120)  # Run for 2 minutes
await conductor.stop(lights)
```

#### Fast Party Mode

```python
# Fast, dramatic color changes
effect = EffectColorloop(
    period=15,          # Fast rotation
    change=45,          # Large color jumps
    spread=120,         # Wide spread
    brightness=0.8,     # Fixed brightness
    saturation_min=0.9, # High saturation only
    transition=0.5      # Quick transitions
)
await conductor.start(effect, lights)
await asyncio.sleep(60)
await conductor.stop(lights)
```

#### Ambient Pastels

```python
# Subtle pastel color cycling
effect = EffectColorloop(
    period=90,          # Very slow
    change=15,          # Small steps
    spread=30,          # Slight variation
    brightness=0.4,     # Dim
    saturation_min=0.3, # Low saturation (pastels)
    saturation_max=0.6,
    transition=3.0      # Very slow transitions
)
await conductor.start(effect, lights)
# Let it run indefinitely
```

### Stopping ColorLoop

Always explicitly stop ColorLoop effects:

```python
# Start effect
effect = EffectColorloop(period=30)
await conductor.start(effect, lights)

# Do other things...
await asyncio.sleep(60)

# Must stop manually
await conductor.stop(lights)
```

The `conductor.stop()` call will:

1. Signal the effect to stop
2. Wait for current iteration to complete
3. Restore all lights to pre-effect state (power, color, zones)

### Prestate Inheritance

ColorLoop effects support state inheritance optimization. If you start a ColorLoop while another ColorLoop is already running, the new effect inherits the existing prestate instead of resetting:

```python
# Start first colorloop
effect1 = EffectColorloop(period=30, change=20)
await conductor.start(effect1, lights)
await asyncio.sleep(10)

# Switch to different colorloop - no reset, seamless transition
effect2 = EffectColorloop(period=20, change=30)
await conductor.start(effect2, lights)  # Inherits state, no flash
```

This prevents the lights from briefly returning to their original state between consecutive ColorLoop effects.

### Performance Notes

- Iteration period: `period / (360 / change)`
- State capture: <1 second per device
- Effect startup: <100ms
- Multiple devices update concurrently
- No cycle limit - runs until stopped

---

## LIFXEffect (Base Class)

Abstract base class for all light effects. Subclass this to create custom effects.

### Class Definition

```python
from lifx import LIFXEffect

class MyEffect(LIFXEffect):
    def __init__(self, power_on: bool = True):
        super().__init__(power_on=power_on)

    async def async_play(self) -> None:
        # Custom effect logic here
        pass
```

### Attributes

#### `power_on` (bool)

Whether to power on devices during effect.

#### `conductor` (Conductor | None)

Reference to the conductor managing this effect. Set automatically by conductor.

#### `participants` (list[Light])

List of lights participating in the effect. Set automatically by conductor.

### Methods

#### `async_perform(participants: list[Light]) -> None`

Perform common setup and play the effect. Called by conductor.

**Do not override this method.** Override `async_play()` instead.

#### `async_play() -> None` (abstract)

Play the effect logic. **Override this in subclasses.**

This is where you implement your custom effect behavior.

**Example:**

```python
async def async_play(self) -> None:
    # Flash all lights 3 times
    for _ in range(3):
        await asyncio.gather(*[
            light.set_brightness(1.0) for light in self.participants
        ])
        await asyncio.sleep(0.3)
        await asyncio.gather(*[
            light.set_brightness(0.0) for light in self.participants
        ])
        await asyncio.sleep(0.3)

    # Restore via conductor
    if self.conductor:
        await self.conductor.stop(self.participants)
```

#### `from_poweroff_hsbk(light: Light) -> HSBK`

Return startup color when light is powered off.

**Override this** to customize the color used when powering on a light.

**Default behavior:** Returns random hue, full saturation, zero brightness, neutral white.

**Example:**

```python
async def from_poweroff_hsbk(self, light: Light) -> HSBK:
    # Always start with red
    return HSBK.from_rgb(255, 0, 0, kelvin=KELVIN_NEUTRAL)
```

#### `inherit_prestate(other: LIFXEffect) -> bool`

Whether this effect can skip device state restoration.

**Override this** if your effect can run without resetting when following certain other effects.

**Default behavior:** Returns `False` (always reset)

**Example:**

```python
def inherit_prestate(self, other: LIFXEffect) -> bool:
    # Can inherit from same effect type
    return type(self) == type(other)
```

### Creating Custom Effects

See the [Custom Effects Guide](../user-guide/effects-custom.md) for detailed instructions on creating your own effects.

---

## See Also

- [Getting Started](../getting-started/effects.md) - Basic usage and common patterns
- [Custom Effects](../user-guide/effects-custom.md) - Creating your own effects
- [Architecture](../architecture/effects-architecture.md) - How the system works
- [Troubleshooting](../user-guide/effects-troubleshooting.md) - Common issues and solutions
