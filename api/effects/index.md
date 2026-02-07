# Effects Reference

This reference guide provides comprehensive documentation for all built-in effect classes in the Light Effects Framework.

## Table of Contents

- [Conductor](#conductor)
- [EffectPulse](#effectpulse)
- [EffectColorloop](#effectcolorloop)
- [EffectRainbow](#effectrainbow)
- [EffectFlame](#effectflame)
- [EffectAurora](#effectaurora)
- [EffectProgress](#effectprogress)
- [EffectSunrise](#effectsunrise)
- [EffectSunset](#effectsunset)
- [EffectRegistry](#effectregistry)
- [FrameEffect (Base Class)](#frameeffect-base-class)
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

#### `add_lights(effect: LIFXEffect, lights: list[Light]) -> None`

Add lights to a running effect without restarting it. Captures state, creates animators (for FrameEffects), and registers lights as participants. Incompatible or already-running lights are skipped.

**Parameters:**

- `effect` (LIFXEffect): The effect to add lights to (must already be running)
- `lights` (list[Light]): List of lights to add

**Example:**

```python
await conductor.add_lights(effect, [new_light])
```

#### `remove_lights(lights: list[Light], restore_state: bool = True) -> None`

Remove lights from their running effect without stopping other participants. Closes animators, optionally restores state, and deregisters lights. If the last participant is removed, cancels the background task.

**Parameters:**

- `lights` (list[Light]): List of lights to remove
- `restore_state` (bool): Whether to restore pre-effect state (default `True`)

**Example:**

```python
# Remove and restore state
await conductor.remove_lights([light1])

# Remove without restoring
await conductor.remove_lights([light2], restore_state=False)
```

#### `get_last_frame(light: Light) -> list[HSBK] | None`

Return the most recent HSBK frame sent to a device. For frame-based effects, returns the list of HSBK colors from the most recent `generate_frame()` call. Returns `None` if no frame-based effect is running on the device.

**Parameters:**

- `light` (Light): The device to query

**Returns:**

- `list[HSBK] | None`: Most recent frame colors, or None

**Example:**

```python
colors = conductor.get_last_frame(light)
if colors:
    avg_brightness = sum(c.brightness for c in colors) / len(colors)
    print(f"Average brightness: {avg_brightness:.1%}")
```

### State Management

The conductor automatically handles:

1. **State Capture**: Power state, current color (HSBK), and multizone colors (if applicable)
1. **Power Management**: Powers on devices if needed for effect visibility
1. **Effect Execution**: Runs effect logic on all participants
1. **State Restoration**: Restores all captured state after effect completes

### Timing Considerations

- State capture: \<1 second per device (mostly network I/O)
- State restoration: 0.6-1.0 seconds per device (includes required 0.3s delays)
- All operations use concurrent execution for multiple devices

______________________________________________________________________

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

______________________________________________________________________

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
    synchronized=False
)
```

EffectColorloop is a [FrameEffect](#frameeffect-base-class) that uses the animation module for high-performance direct UDP frame delivery. The Conductor automatically creates Animators for each participant device (Light, MultiZoneLight, or MatrixLight) and drives the frame loop.

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

#### `synchronized` (bool, default: `False`)

If `True`, all lights display the same color simultaneously with consistent transitions. When `False`, lights are spread across the hue spectrum based on the `spread` parameter.

**Examples:**

- `synchronized=False`: Lights show different colors based on spread (default)
- `synchronized=True`: All lights change together in unison

#### `transition` (float | None, default: `None`)

**Deprecated.** This parameter is accepted for backward compatibility but has no effect. Frame timing is now handled automatically by the animation module, which calculates smooth firmware-level interpolation between frames based on the effect's FPS.

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
1. **Saturation**: Random value between saturation_min and saturation_max (spread mode only; synchronized mode uses midpoint)

#### Hue Calculation

Hue rotation is time-based, computed from elapsed time:

```python
degrees_rotated = (elapsed_s / period) * 360.0 * direction

# Spread mode (per device):
new_hue = (base_hue + degrees_rotated + device_index * spread) % 360

# Synchronized mode (all devices):
new_hue = (base_hue + degrees_rotated) % 360
```

The FPS is automatically calculated from `period` and `change`: `fps = max(1.0, (360 / change) / period)`

### Device Type Behavior

As a FrameEffect, ColorLoop works across all device types via the animation module:

#### Color Lights

Full color cycling with all parameters supported. Uses `LightPacketGenerator` for direct UDP delivery.

#### Multizone Lights

Entire device cycles as one unit (all zones set to same color per frame). Uses `MultiZonePacketGenerator`.

#### Matrix Lights (Tile/Candle/Path)

All pixels cycle together with same color per frame. Uses `MatrixPacketGenerator` for multi-tile canvas delivery.

#### Monochrome/White Lights

- Filtered out by `is_light_compatible()` — ColorLoop requires color capability
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
1. Wait for current iteration to complete
1. Restore all lights to pre-effect state (power, color, zones)

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

- Frame interval: `1 / fps` where `fps = max(1.0, (360 / change) / period)`
- Frame delivery: Direct UDP via animation module (no connection overhead)
- Smooth transitions: Firmware interpolates between frames using `duration_ms = 1000 / fps`
- State capture: \<1 second per device
- Effect startup: \<100ms
- Multiple devices update concurrently
- No cycle limit - runs until stopped

______________________________________________________________________

## EffectRainbow

Animated rainbow effect that spreads a full 360-degree rainbow across device pixels and scrolls it over time. Best on multizone strips and matrix lights where per-pixel variation creates a beautiful scrolling rainbow. Runs indefinitely until stopped.

### Class Definition

```python
from lifx import EffectRainbow

effect = EffectRainbow(
    power_on=True,
    period=10.0,
    brightness=0.8,
    saturation=1.0,
    spread=0.0
)
```

EffectRainbow is a [FrameEffect](#frameeffect-base-class) that generates per-pixel rainbow colors.

### Parameters

| Parameter    | Type    | Default | Description                                        |
| ------------ | ------- | ------- | -------------------------------------------------- |
| `power_on`   | `bool`  | `True`  | Power on devices if off                            |
| `period`     | `float` | `10.0`  | Seconds per full rainbow scroll. Must be positive. |
| `brightness` | `float` | `0.8`   | Fixed brightness 0.0-1.0                           |
| `saturation` | `float` | `1.0`   | Fixed saturation 0.0-1.0                           |
| `spread`     | `float` | `0.0`   | Hue degrees offset between devices 0-360           |

### Device Compatibility

- **Color Lights**: Cycles through hue (similar to a simpler colorloop)
- **Multizone Lights**: Full rainbow spread across all zones, scrolling
- **Matrix Lights**: Full rainbow spread across all pixels, scrolling

Requires color capability. Monochrome lights are filtered out by `is_light_compatible()`.

### Examples

```python
# Slow rainbow on a strip
effect = EffectRainbow(period=20, brightness=0.6)
await conductor.start(effect, lights)

# Multiple devices offset by 90 degrees
effect = EffectRainbow(period=10, spread=90)
await conductor.start(effect, lights)

await asyncio.sleep(60)
await conductor.stop(lights)
```

______________________________________________________________________

## EffectFlame

Fire/candle flicker effect using layered sine waves for organic brightness variation. Produces warm colors from deep red to yellow. On matrix devices, applies vertical brightness falloff so bottom rows glow hotter. Runs indefinitely until stopped.

### Class Definition

```python
from lifx import EffectFlame

effect = EffectFlame(
    power_on=True,
    intensity=0.7,
    speed=1.0,
    kelvin_min=1500,
    kelvin_max=2500,
    brightness=0.8
)
```

### Parameters

| Parameter    | Type    | Default | Description                                                              |
| ------------ | ------- | ------- | ------------------------------------------------------------------------ |
| `power_on`   | `bool`  | `True`  | Power on devices if off                                                  |
| `intensity`  | `float` | `0.7`   | Flicker intensity 0.0-1.0. Higher values create more dramatic variation. |
| `speed`      | `float` | `1.0`   | Animation speed multiplier. Must be positive.                            |
| `kelvin_min` | `int`   | `1500`  | Minimum color temperature (>= 1500)                                      |
| `kelvin_max` | `int`   | `2500`  | Maximum color temperature (\<= 9000, >= kelvin_min)                      |
| `brightness` | `float` | `0.8`   | Base brightness 0.0-1.0                                                  |

### Device Compatibility

- **Color Lights**: Flickering candle effect (single pixel)
- **Multizone Lights**: Fire along the strip with per-zone variation
- **Matrix Lights**: 2D fire with vertical gradient — bottom rows are hotter

Requires color capability.

### Examples

```python
# Gentle candle on a single bulb
effect = EffectFlame(intensity=0.5, speed=0.8)
await conductor.start(effect, lights)

# Intense bonfire on matrix tiles
effect = EffectFlame(intensity=1.0, speed=2.0, brightness=1.0)
await conductor.start(effect, [tile_light])

await asyncio.sleep(60)
await conductor.stop(lights)
```

______________________________________________________________________

## EffectAurora

Northern lights simulation with flowing colored bands. Uses palette interpolation and sine waves to create flowing aurora-like patterns. Best on multizone strips and matrix lights. Runs indefinitely until stopped.

### Class Definition

```python
from lifx import EffectAurora

effect = EffectAurora(
    power_on=True,
    speed=1.0,
    brightness=0.8,
    palette=None,       # defaults to green/cyan/blue/purple/magenta
    spread=0.0
)
```

### Parameters

| Parameter    | Type                | Default | Description                                                                                                                                       |
| ------------ | ------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `power_on`   | `bool`              | `True`  | Power on devices if off                                                                                                                           |
| `speed`      | `float`             | `1.0`   | Animation speed multiplier. Must be positive.                                                                                                     |
| `brightness` | `float`             | `0.8`   | Base brightness 0.0-1.0                                                                                                                           |
| `palette`    | `list[int] \| None` | `None`  | List of hue values (0-360) defining aurora colors. Must have >= 2 entries. Default: `[120, 160, 200, 260, 290]` (green/cyan/blue/purple/magenta). |
| `spread`     | `float`             | `0.0`   | Hue degrees offset between devices 0-360                                                                                                          |

### Device Compatibility

- **Color Lights**: Slow color drift (underwhelming on single pixel)
- **Multizone Lights**: Flowing colored bands across the strip
- **Matrix Lights**: Flowing bands with vertical brightness gradient (brightest in middle rows, like aurora hanging from the sky)

Requires color capability.

### Examples

```python
# Default aurora
effect = EffectAurora()
await conductor.start(effect, lights)

# Custom warm palette (magenta/pink tones)
effect = EffectAurora(palette=[280, 300, 320, 340])
await conductor.start(effect, lights)

# Multi-device with spread
effect = EffectAurora(spread=45, brightness=0.6)
await conductor.start(effect, lights)

await asyncio.sleep(120)
await conductor.stop(lights)
```

______________________________________________________________________

## EffectProgress

Animated progress bar for multizone lights (strips/beams). Displays a filled/unfilled bar where the filled region has a traveling bright spot. The `position` attribute is mutable — update it at any time and the bar grows/shrinks on the next frame. Runs indefinitely until stopped.

**Multizone only** — requires `has_multizone` capability.

### Class Definition

```python
from lifx import EffectProgress, HSBK, Colors

effect = EffectProgress(
    power_on=True,
    start_value=0.0,
    end_value=100.0,
    position=0.0,
    foreground=Colors.GREEN,
    background=HSBK(0, 0.0, 0.05, 3500),
    spot_brightness=1.0,
    spot_width=0.15,
    spot_speed=1.0
)
```

### Parameters

| Parameter         | Type                         | Default        | Description                                                                                                    |
| ----------------- | ---------------------------- | -------------- | -------------------------------------------------------------------------------------------------------------- |
| `power_on`        | `bool`                       | `True`         | Power on devices if off                                                                                        |
| `start_value`     | `float`                      | `0.0`          | Start of value range (must be < end_value)                                                                     |
| `end_value`       | `float`                      | `100.0`        | End of value range (must be > start_value)                                                                     |
| `position`        | `float`                      | `0.0`          | Initial progress position (mutable at runtime)                                                                 |
| `foreground`      | `HSBK \| list[HSBK] \| None` | `Colors.GREEN` | Color or gradient of filled region. Pass a single HSBK for solid, or a list of >= 2 HSBK stops for a gradient. |
| `background`      | `HSBK \| None`               | dim neutral    | Color of unfilled region                                                                                       |
| `spot_brightness` | `float`                      | `1.0`          | Peak brightness of traveling spot 0.0-1.0                                                                      |
| `spot_width`      | `float`                      | `0.15`         | Spot width as fraction of bar 0.0-1.0                                                                          |
| `spot_speed`      | `float`                      | `1.0`          | Spot oscillation speed in cycles/sec. Must be positive.                                                        |

### Dynamic Position Update

Since `generate_frame()` reads `self.position` each frame, changes are picked up immediately (asyncio single-threaded safety):

```python
effect = EffectProgress(foreground=Colors.BLUE, end_value=100)
await conductor.start(effect, [strip])

# Update from your application
effect.position = 45.0   # 45% complete
await asyncio.sleep(5)
effect.position = 80.0   # 80% complete
```

### Gradient Foreground

Pass a list of HSBK stops for a gradient that reveals progressively as the bar grows:

```python
gradient = [
    HSBK(hue=240, saturation=1.0, brightness=0.8, kelvin=3500),  # blue
    HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),  # green
    HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500),    # red
]
effect = EffectProgress(foreground=gradient, end_value=100)
```

### Device Compatibility

- **Multizone Lights**: Full progress bar with traveling spot
- **Color Lights / Matrix Lights**: Not supported

______________________________________________________________________

## EffectSunrise

Sunrise effect that transitions from night to daylight over a configurable duration. Simulates a radial sun expansion from a configurable origin point, progressing through night, dawn, golden hour, morning, and daylight phases.

**Matrix only** — requires `has_matrix` capability (tiles, candles, Ceiling lights).

### Class Definition

```python
from lifx import EffectSunrise

effect = EffectSunrise(
    power_on=True,
    duration=60.0,
    brightness=1.0,
    origin="bottom"
)
```

### Parameters

| Parameter    | Type        | Default    | Description                                                                                                                               |
| ------------ | ----------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `power_on`   | `bool`      | `True`     | Power on devices if off                                                                                                                   |
| `duration`   | `float`     | `60.0`     | Effect duration in seconds. Must be positive.                                                                                             |
| `brightness` | `float`     | `1.0`      | Peak brightness at full daylight 0.0-1.0                                                                                                  |
| `origin`     | `SunOrigin` | `"bottom"` | Sun origin point — `"bottom"` for center of bottom row (rectangular tiles) or `"center"` for middle of canvas (round/oval Ceiling lights) |

### Behavior

- **Duration-based**: Completes automatically after `duration` seconds
- **No state restoration**: Light stays at daylight after completion (the whole point of a sunrise)
- **Color phases**: Night (deep navy) → Dawn (purple/magenta) → Golden hour (orange/gold) → Morning (yellow) → Daylight (warm white)
- **Radial wavefront**: Pixels near the origin transition first, creating a sun expanding outward

### Origin Parameter

The `origin` parameter controls where the sun rises from:

- `"bottom"` (default): Center of the bottom row. Ideal for **rectangular tile arrays** where the sun rises from the horizon.
- `"center"`: Middle of the canvas. Ideal for **round or oval LIFX Ceiling lights** where the sun expands outward from the center.

### Examples

```python
# 30-minute sunrise for rectangular tiles
effect = EffectSunrise(duration=1800, brightness=1.0)
await conductor.start(effect, [tile_light])

# Sunrise from center for Ceiling lights
effect = EffectSunrise(duration=1800, origin="center")
await conductor.start(effect, [ceiling_light])
```

______________________________________________________________________

## EffectSunset

Sunset effect that transitions from daylight to night over a configurable duration. Reverses the sunrise progression — daylight through golden hour to night. Optionally powers off the light when complete.

**Matrix only** — requires `has_matrix` capability.

### Class Definition

```python
from lifx import EffectSunset

effect = EffectSunset(
    power_on=False,
    duration=60.0,
    brightness=1.0,
    power_off=True,
    origin="bottom"
)
```

### Parameters

| Parameter    | Type        | Default    | Description                                                          |
| ------------ | ----------- | ---------- | -------------------------------------------------------------------- |
| `power_on`   | `bool`      | `False`    | Power on devices if off (default False — light should already be on) |
| `duration`   | `float`     | `60.0`     | Effect duration in seconds. Must be positive.                        |
| `brightness` | `float`     | `1.0`      | Starting brightness at daylight 0.0-1.0                              |
| `power_off`  | `bool`      | `True`     | Power off lights when sunset completes                               |
| `origin`     | `SunOrigin` | `"bottom"` | Sun origin point — `"bottom"` or `"center"`                          |

### Behavior

- **Duration-based**: Completes automatically after `duration` seconds
- **Power off**: When `power_off=True`, all participant lights are powered off after the last frame
- **State restoration**: Skipped when `power_off=True` (light is off). When `power_off=False`, state is restored normally.
- **Color phases**: Daylight → Morning → Golden hour → Dusk → Night

### Examples

```python
# 30-minute sunset that powers off the light
effect = EffectSunset(duration=1800, power_off=True)
await conductor.start(effect, [tile_light])

# Sunset from center for Ceiling lights, no power off
effect = EffectSunset(duration=1800, origin="center", power_off=False)
await conductor.start(effect, [ceiling_light])
```

______________________________________________________________________

## EffectRegistry

Central registry for discovering and querying available effects. Enables consumers like Home Assistant to dynamically find and present available effects based on device type.

### Usage

```python
from lifx import get_effect_registry, DeviceType, DeviceSupport

registry = get_effect_registry()
```

### `get_effect_registry() -> EffectRegistry`

Returns the default registry pre-populated with all built-in effects. Lazily initialized on first call.

### EffectRegistry Methods

#### `effects -> list[EffectInfo]`

Property returning all registered effects.

#### `get_effect(name: str) -> EffectInfo | None`

Look up an effect by name.

#### `get_effects_for_device(device: Light) -> list[tuple[EffectInfo, DeviceSupport]]`

Get effects compatible with a specific device instance. Classifies the device automatically and returns RECOMMENDED + COMPATIBLE entries, sorted with RECOMMENDED first.

#### `get_effects_for_device_type(device_type: DeviceType) -> list[tuple[EffectInfo, DeviceSupport]]`

Get effects compatible with a device type category.

### DeviceType Enum

| Value       | Description                                     |
| ----------- | ----------------------------------------------- |
| `LIGHT`     | Single bulb (Light, InfraredLight, HevLight)    |
| `MULTIZONE` | Strip/beam (MultiZoneLight)                     |
| `MATRIX`    | Tile/candle/ceiling (MatrixLight, CeilingLight) |

### DeviceSupport Enum

| Value           | Description                                             |
| --------------- | ------------------------------------------------------- |
| `RECOMMENDED`   | Optimal visual experience for this device type          |
| `COMPATIBLE`    | Works, but may not showcase the effect's full potential |
| `NOT_SUPPORTED` | Filtered out (not useful on this device type)           |

### EffectInfo Dataclass

```python
@dataclass(frozen=True)
class EffectInfo:
    name: str                                        # e.g. "flame"
    effect_class: type[LIFXEffect]                   # e.g. EffectFlame
    description: str                                 # Human-readable one-liner
    device_support: dict[DeviceType, DeviceSupport]  # Per-type support
```

### Built-in Effect Support Matrix

| Effect    | Light         | MultiZone     | Matrix        |
| --------- | ------------- | ------------- | ------------- |
| pulse     | RECOMMENDED   | RECOMMENDED   | RECOMMENDED   |
| colorloop | RECOMMENDED   | COMPATIBLE    | COMPATIBLE    |
| rainbow   | COMPATIBLE    | RECOMMENDED   | RECOMMENDED   |
| flame     | RECOMMENDED   | RECOMMENDED   | RECOMMENDED   |
| aurora    | COMPATIBLE    | RECOMMENDED   | RECOMMENDED   |
| progress  | NOT_SUPPORTED | RECOMMENDED   | NOT_SUPPORTED |
| sunrise   | NOT_SUPPORTED | NOT_SUPPORTED | RECOMMENDED   |
| sunset    | NOT_SUPPORTED | NOT_SUPPORTED | RECOMMENDED   |

### Examples

```python
from lifx import get_effect_registry, DeviceType

registry = get_effect_registry()

# List all effects
for info in registry.effects:
    print(f"{info.name}: {info.description}")

# Get effects for multizone strips
for info, support in registry.get_effects_for_device_type(DeviceType.MULTIZONE):
    print(f"{info.name} ({support.value})")

# Get effects for a specific device
for info, support in registry.get_effects_for_device(my_light):
    print(f"{info.name}: {support.value}")
```

______________________________________________________________________

## FrameEffect (Base Class)

Abstract base class for frame-generator effects. Extends [LIFXEffect](#lifxeffect-base-class) with a frame loop driven by the animation module. Subclass this to create effects that generate color frames at a fixed FPS.

### Class Definition

```python
from lifx import FrameEffect, FrameContext, HSBK

class MyEffect(FrameEffect):
    def __init__(self, power_on: bool = True):
        super().__init__(power_on=power_on, fps=30.0, duration=None)

    @property
    def name(self) -> str:
        return "my_effect"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        # Return pixel_count colors
        hue = (ctx.elapsed_s * 60) % 360
        return [HSBK(hue=hue, saturation=1.0, brightness=0.8, kelvin=3500)] * ctx.pixel_count
```

### Parameters

#### `power_on` (bool, default: `True`)

Whether to power on devices during effect.

#### `fps` (float, default: `30.0`)

Frames per second. Must be positive. Higher FPS means smoother animation but more network traffic. The Conductor passes `duration_ms = 1500 / fps` to the Animator so devices smoothly interpolate between frames.

#### `duration` (float | None, default: `None`)

Effect duration in seconds. If `None`, runs indefinitely until stopped. Must be positive if set.

### FrameContext

Frozen dataclass passed to `generate_frame()` with timing and layout info:

```python
@dataclass(frozen=True)
class FrameContext:
    elapsed_s: float    # Seconds since effect started
    device_index: int   # Index in participants list
    pixel_count: int    # Number of pixels (1 for light, N for zones, W*H for matrix)
    canvas_width: int   # Width (pixel_count for 1D, W for matrix)
    canvas_height: int  # Height (1 for 1D, H for matrix)
```

### Methods

#### `generate_frame(ctx: FrameContext) -> list[HSBK]` (abstract)

Generate a frame of colors for one device. Called once per device per frame. **Override this in subclasses.**

**Parameters:**

- `ctx` (FrameContext): Frame context with timing and layout info

**Returns:**

- `list[HSBK]`: Colors matching `ctx.pixel_count`

#### `async_setup(participants: list[Light]) -> None`

Optional hook called before the frame loop starts. Override to perform async setup like fetching initial colors.

#### `async_play() -> None`

Runs the frame loop. **Do not override** — implement `generate_frame()` instead.

#### `stop() -> None`

Signal the frame loop to stop.

#### `close_animators() -> None`

Close all animators and clear the list. Called by the Conductor during cleanup.

### Device Type Support

FrameEffect works across all device types via the animation module:

- **Light**: `Animator.for_light()` — 1 pixel via SetColor packets
- **MultiZoneLight**: `Animator.for_multizone()` — N pixels via SetExtendedColorZones
- **MatrixLight**: `Animator.for_matrix()` — W×H pixels via Set64 packets

### Creating Custom FrameEffects

See the [Custom Effects Guide](https://djelibeybi.github.io/lifx-async/user-guide/effects-custom/#frame-based-effects-frameeffect) for detailed instructions.

______________________________________________________________________

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

See the [Custom Effects Guide](https://djelibeybi.github.io/lifx-async/user-guide/effects-custom/index.md) for detailed instructions on creating your own effects.

______________________________________________________________________

## See Also

- [Getting Started](https://djelibeybi.github.io/lifx-async/getting-started/effects/index.md) - Basic usage and common patterns
- [Custom Effects](https://djelibeybi.github.io/lifx-async/user-guide/effects-custom/index.md) - Creating your own effects
- [Architecture](https://djelibeybi.github.io/lifx-async/architecture/effects-architecture/index.md) - How the system works
- [Troubleshooting](https://djelibeybi.github.io/lifx-async/user-guide/effects-troubleshooting/index.md) - Common issues and solutions
