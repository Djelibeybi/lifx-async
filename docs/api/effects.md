# Effects Reference

> **Looking for usage examples?** See the [Light Effects Guide](../user-guide/effects.md) for tutorials, common patterns, and best practices. This page covers the API surface only.

This reference guide provides comprehensive documentation for all effect classes in the Light Effects Framework.

## Table of Contents

- [Conductor](#conductor)
- [LIFXEffect (Base Class)](#lifxeffect-base-class)
- [FrameEffect (Base Class)](#frameeffect-base-class)
- [EffectRegistry](#effectregistry)
- [Effects](#effects) — all built-in effects listed alphabetically

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
2. **Power Management**: Powers on devices if needed for effect visibility
3. **Effect Execution**: Runs effect logic on all participants
4. **State Restoration**: Restores all captured state after effect completes

### Timing Considerations

- State capture: <1 second per device (mostly network I/O)
- State restoration: 0.6-1.0 seconds per device (includes required 0.3s delays)
- All operations use concurrent execution for multiple devices

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
    return HSBK.from_rgb(1.0, 0.0, 0.0)
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

See the [Custom Effects Guide](../user-guide/effects-custom.md#frame-based-effects-frameeffect) for detailed instructions.

---

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

| Value | Description |
|-------|-------------|
| `LIGHT` | Single bulb (Light, InfraredLight, HevLight) |
| `MULTIZONE` | Strip/beam (MultiZoneLight) |
| `MATRIX` | Tile/candle/ceiling (MatrixLight, CeilingLight) |

### DeviceSupport Enum

| Value | Description |
|-------|-------------|
| `RECOMMENDED` | Optimal visual experience for this device type |
| `COMPATIBLE` | Works, but may not showcase the effect's full potential |
| `NOT_SUPPORTED` | Filtered out (not useful on this device type) |

### EffectInfo Dataclass

```python
@dataclass(frozen=True)
class EffectInfo:
    name: str                                        # e.g. "flame"
    effect_class: type[LIFXEffect]                   # e.g. EffectFlame
    description: str                                 # Human-readable one-liner
    device_support: dict[DeviceType, DeviceSupport]  # Per-type support
```

### Effect Support Matrix

| Effect | Light | MultiZone | Matrix |
|--------|-------|-----------|--------|
| aurora | COMPATIBLE | RECOMMENDED | RECOMMENDED |
| colorloop | RECOMMENDED | COMPATIBLE | COMPATIBLE |
| cylon | COMPATIBLE | RECOMMENDED | — |
| double_slit | — | RECOMMENDED | — |
| embers | COMPATIBLE | RECOMMENDED | — |
| fireworks | — | RECOMMENDED | — |
| flame | RECOMMENDED | RECOMMENDED | RECOMMENDED |
| jacobs_ladder | — | RECOMMENDED | — |
| newtons_cradle | — | RECOMMENDED | — |
| pendulum_wave | — | RECOMMENDED | — |
| plasma | COMPATIBLE | RECOMMENDED | — |
| plasma2d | — | — | RECOMMENDED |
| progress | — | RECOMMENDED | — |
| pulse | RECOMMENDED | RECOMMENDED | RECOMMENDED |
| rainbow | COMPATIBLE | RECOMMENDED | RECOMMENDED |
| ripple | — | RECOMMENDED | — |
| rule30 | — | RECOMMENDED | — |
| rule_trio | — | RECOMMENDED | — |
| sine | COMPATIBLE | RECOMMENDED | — |
| sonar | — | RECOMMENDED | — |
| spectrum_sweep | COMPATIBLE | RECOMMENDED | — |
| spin | COMPATIBLE | RECOMMENDED | — |
| sunrise | — | — | RECOMMENDED |
| sunset | — | — | RECOMMENDED |
| twinkle | RECOMMENDED | RECOMMENDED | COMPATIBLE |
| wave | COMPATIBLE | RECOMMENDED | — |

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

---

## Effects

All built-in effect classes, listed alphabetically. Effects adapted from [pkivolowitz/lifx](https://github.com/pkivolowitz/lifx) by Perry Kivolowitz are noted in their docstrings.

### EffectAurora

::: lifx.effects.EffectAurora
    options:
      show_source: false
      heading_level: 4

---

### EffectColorloop

::: lifx.effects.EffectColorloop
    options:
      show_source: false
      heading_level: 4

---

### EffectCylon

::: lifx.effects.EffectCylon
    options:
      show_source: false
      heading_level: 4

---

### EffectDoubleSlit

::: lifx.effects.EffectDoubleSlit
    options:
      show_source: false
      heading_level: 4

---

### EffectEmbers

::: lifx.effects.EffectEmbers
    options:
      show_source: false
      heading_level: 4

---

### EffectFireworks

::: lifx.effects.EffectFireworks
    options:
      show_source: false
      heading_level: 4

---

### EffectFlame

::: lifx.effects.EffectFlame
    options:
      show_source: false
      heading_level: 4

---

### EffectJacobsLadder

::: lifx.effects.EffectJacobsLadder
    options:
      show_source: false
      heading_level: 4

---

### EffectNewtonsCradle

::: lifx.effects.EffectNewtonsCradle
    options:
      show_source: false
      heading_level: 4

---

### EffectPendulumWave

::: lifx.effects.EffectPendulumWave
    options:
      show_source: false
      heading_level: 4

---

### EffectPlasma

::: lifx.effects.EffectPlasma
    options:
      show_source: false
      heading_level: 4

---

### EffectPlasma2D

::: lifx.effects.EffectPlasma2D
    options:
      show_source: false
      heading_level: 4

---

### EffectProgress

::: lifx.effects.EffectProgress
    options:
      show_source: false
      heading_level: 4

---

### EffectPulse

::: lifx.effects.EffectPulse
    options:
      show_source: false
      heading_level: 4

---

### EffectRainbow

::: lifx.effects.EffectRainbow
    options:
      show_source: false
      heading_level: 4

---

### EffectRipple

::: lifx.effects.EffectRipple
    options:
      show_source: false
      heading_level: 4

---

### EffectRule30

::: lifx.effects.EffectRule30
    options:
      show_source: false
      heading_level: 4

---

### EffectRuleTrio

::: lifx.effects.EffectRuleTrio
    options:
      show_source: false
      heading_level: 4

---

### EffectSine

::: lifx.effects.EffectSine
    options:
      show_source: false
      heading_level: 4

---

### EffectSonar

::: lifx.effects.EffectSonar
    options:
      show_source: false
      heading_level: 4

---

### EffectSpectrumSweep

::: lifx.effects.EffectSpectrumSweep
    options:
      show_source: false
      heading_level: 4

---

### EffectSpin

::: lifx.effects.EffectSpin
    options:
      show_source: false
      heading_level: 4

---

### EffectSunrise

::: lifx.effects.EffectSunrise
    options:
      show_source: false
      heading_level: 4

---

### EffectSunset

::: lifx.effects.EffectSunset
    options:
      show_source: false
      heading_level: 4

---

### EffectTwinkle

::: lifx.effects.EffectTwinkle
    options:
      show_source: false
      heading_level: 4

---

### EffectWave

::: lifx.effects.EffectWave
    options:
      show_source: false
      heading_level: 4

---

## See Also

- [Light Effects Guide](../user-guide/effects.md) — Usage examples, common patterns, and best practices
- [Effects Gallery](../user-guide/effects-gallery.md) — Animated previews of all effects
- [Custom Effects](../user-guide/effects-custom.md) — Creating your own effects
- [Effect API Changes](../migration/effect-api-changes.md) — Migration guide for breaking changes
- [Architecture](../architecture/effects-architecture.md) — How the system works
- [Troubleshooting](../user-guide/effects-troubleshooting.md) — Common issues and solutions
