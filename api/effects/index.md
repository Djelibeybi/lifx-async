# Effects Reference

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
1. **Power Management**: Powers on devices if needed for effect visibility
1. **Effect Execution**: Runs effect logic on all participants
1. **State Restoration**: Restores all captured state after effect completes

### Timing Considerations

- State capture: \<1 second per device (mostly network I/O)
- State restoration: 0.6-1.0 seconds per device (includes required 0.3s delays)
- All operations use concurrent execution for multiple devices

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

See the [Custom Effects Guide](https://djelibeybi.github.io/lifx-async/user-guide/effects-custom/index.md) for detailed instructions on creating your own effects.

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

### Effect Support Matrix

| Effect         | Light       | MultiZone   | Matrix      |
| -------------- | ----------- | ----------- | ----------- |
| aurora         | COMPATIBLE  | RECOMMENDED | RECOMMENDED |
| colorloop      | RECOMMENDED | COMPATIBLE  | COMPATIBLE  |
| cylon          | COMPATIBLE  | RECOMMENDED | —           |
| double_slit    | —           | RECOMMENDED | —           |
| embers         | COMPATIBLE  | RECOMMENDED | —           |
| fireworks      | —           | RECOMMENDED | —           |
| flame          | RECOMMENDED | RECOMMENDED | RECOMMENDED |
| jacobs_ladder  | —           | RECOMMENDED | —           |
| newtons_cradle | —           | RECOMMENDED | —           |
| pendulum_wave  | —           | RECOMMENDED | —           |
| plasma         | COMPATIBLE  | RECOMMENDED | —           |
| plasma2d       | —           | —           | RECOMMENDED |
| progress       | —           | RECOMMENDED | —           |
| pulse          | RECOMMENDED | RECOMMENDED | RECOMMENDED |
| rainbow        | COMPATIBLE  | RECOMMENDED | RECOMMENDED |
| ripple         | —           | RECOMMENDED | —           |
| rule30         | —           | RECOMMENDED | —           |
| rule_trio      | —           | RECOMMENDED | —           |
| sine           | COMPATIBLE  | RECOMMENDED | —           |
| sonar          | —           | RECOMMENDED | —           |
| spectrum_sweep | COMPATIBLE  | RECOMMENDED | —           |
| spin           | COMPATIBLE  | RECOMMENDED | —           |
| sunrise        | —           | —           | RECOMMENDED |
| sunset         | —           | —           | RECOMMENDED |
| twinkle        | RECOMMENDED | RECOMMENDED | COMPATIBLE  |
| wave           | COMPATIBLE  | RECOMMENDED | —           |

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

## Effects

All built-in effect classes, listed alphabetically. Effects adapted from [pkivolowitz/lifx](https://github.com/pkivolowitz/lifx) by Perry Kivolowitz are noted in their docstrings.

### EffectAurora

#### EffectAurora

```python
EffectAurora(
    power_on: bool = True,
    speed: float = 1.0,
    brightness: float = 0.8,
    palette: list[int] | None = None,
    spread: float = 0.0,
)
```

Bases: `FrameEffect`

Northern lights effect with flowing colored bands.

Uses palette interpolation and sine waves to create flowing aurora-like patterns. Best on multizone strips and matrix lights where per-pixel color variation creates beautiful flowing colored bands.

| ATTRIBUTE    | DESCRIPTION                        |
| ------------ | ---------------------------------- |
| `speed`      | Animation speed multiplier         |
| `brightness` | Base brightness level              |
| `spread`     | Hue degrees offset between devices |

Example

```python
# Default aurora
effect = EffectAurora()
await conductor.start(effect, lights)

# Custom palette with magenta/pink tones
effect = EffectAurora(palette=[280, 300, 320, 340])
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER    | DESCRIPTION                                                                                                                              |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `power_on`   | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                                                              |
| `speed`      | Animation speed multiplier, must be > 0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                                               |
| `brightness` | Base brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                                                               |
| `palette`    | List of hue values (0-360) defining the aurora colors. Must have >= 2 entries. Defaults to green/cyan/blue/purple. **TYPE:** \`list[int] |
| `spread`     | Hue degrees offset between devices 0-360 (default 0) **TYPE:** `float` **DEFAULT:** `0.0`                                                |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                             |
| --------------------- | ------------------------------------------------------- |
| `generate_frame`      | Generate a frame of aurora colors for one device.       |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.         |
| `is_light_compatible` | Check if light is compatible with aurora effect.        |
| `inherit_prestate`    | Aurora can inherit prestate from another aurora effect. |
| `__repr__`            | String representation of aurora effect.                 |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of aurora colors for one device.

Creates flowing colored bands with brightness modulation. Matrix devices get a vertical brightness gradient with the brightest band in the middle rows.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                              |
| ------- | -------------------------------------------------------- |
| `HSBK`  | Green aurora color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with aurora effect.

Aurora requires color capability to manipulate hue/saturation.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `bool`  | True if light has color support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Aurora can inherit prestate from another aurora effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                         |
| ------- | --------------------------------------------------- |
| `bool`  | True if other is also EffectAurora, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of aurora effect.

______________________________________________________________________

### EffectColorloop

#### EffectColorloop

```python
EffectColorloop(
    power_on: bool = True,
    period: float = 60,
    change: float = 20,
    spread: float = 30,
    brightness: float | None = None,
    saturation_min: float = 0.8,
    saturation_max: float = 1.0,
    transition: float | None = None,
    synchronized: bool = False,
)
```

Bases: `FrameEffect`

Continuous color rotation effect cycling through hue spectrum.

Perpetually cycles through hues with configurable speed, spread, and color constraints. Continues until stopped.

| ATTRIBUTE        | DESCRIPTION                                                        |
| ---------------- | ------------------------------------------------------------------ |
| `period`         | Seconds per full cycle (default 60)                                |
| `change`         | Hue degrees to shift per iteration (default 20)                    |
| `spread`         | Hue degrees spread across devices (default 30)                     |
| `brightness`     | Fixed brightness, or None to preserve (default None)               |
| `saturation_min` | Minimum saturation (0.0-1.0, default 0.8)                          |
| `saturation_max` | Maximum saturation (0.0-1.0, default 1.0)                          |
| `transition`     | Color transition time in seconds, or None for random               |
| `synchronized`   | If True, all lights show same color simultaneously (default False) |

Example

```python
# Rainbow effect with spread
effect = EffectColorloop(period=30, change=30, spread=60)
await conductor.start(effect, lights)

# Synchronized colorloop - all lights same color
effect = EffectColorloop(period=30, change=30, synchronized=True)
await conductor.start(effect, lights)

# Wait then stop
await asyncio.sleep(120)
await conductor.stop(lights)

# Colorloop with fixed brightness
effect = EffectColorloop(
    period=20, change=15, brightness=0.7, saturation_min=0.9
)
await conductor.start(effect, lights)
```

| PARAMETER        | DESCRIPTION                                                                                                                                                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `power_on`       | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                                                                                                                                                     |
| `period`         | Seconds per full cycle (default 60) **TYPE:** `float` **DEFAULT:** `60`                                                                                                                                                         |
| `change`         | Hue degrees to shift per iteration (default 20) **TYPE:** `float` **DEFAULT:** `20`                                                                                                                                             |
| `spread`         | Hue degrees spread across devices (default 30). Ignored if synchronized=True. **TYPE:** `float` **DEFAULT:** `30`                                                                                                               |
| `brightness`     | Fixed brightness, or None to preserve (default None) **TYPE:** \`float                                                                                                                                                          |
| `saturation_min` | Minimum saturation (0.0-1.0, default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                                                                                                                                                  |
| `saturation_max` | Maximum saturation (0.0-1.0, default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                                                                                                                                                  |
| `transition`     | Color transition time in seconds, or None for random per device (default None). When synchronized=True and transition=None, uses iteration_period as transition. **TYPE:** \`float                                              |
| `synchronized`   | If True, all lights display the same color simultaneously with consistent transitions. When False, lights are spread across the hue spectrum based on 'spread' parameter (default False). **TYPE:** `bool` **DEFAULT:** `False` |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                                        |
| --------------------- | ------------------------------------------------------------------ |
| `async_setup`         | Fetch initial colors and pick rotation direction.                  |
| `generate_frame`      | Generate a frame of colors for one device.                         |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.                    |
| `inherit_prestate`    | Colorloop can run without reset if switching to another colorloop. |
| `is_light_compatible` | Check if light is compatible with colorloop effect.                |
| `__repr__`            | String representation of colorloop effect.                         |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

| RETURNS | DESCRIPTION                 |
| ------- | --------------------------- |
| `str`   | The effect name 'colorloop' |

##### Functions

###### async_setup

```python
async_setup(participants: list[Light]) -> None
```

Fetch initial colors and pick rotation direction.

| PARAMETER      | DESCRIPTION                                                        |
| -------------- | ------------------------------------------------------------------ |
| `participants` | List of lights participating in the effect **TYPE:** `list[Light]` |

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of colors for one device.

All pixels on a device receive the same color. For multizone/matrix devices that need per-pixel rainbow effects, use EffectRainbow instead.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

For colorloop, start with random hue and target brightness.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                        |
| ------- | ---------------------------------- |
| `HSBK`  | HSBK color to use as startup color |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Colorloop can run without reset if switching to another colorloop.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                            |
| ------- | ------------------------------------------------------ |
| `bool`  | True if other is also EffectColorloop, False otherwise |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with colorloop effect.

Colorloop requires color capability to manipulate hue/saturation.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `bool`  | True if light has color support, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of colorloop effect.

______________________________________________________________________

### EffectCylon

#### EffectCylon

```python
EffectCylon(
    power_on: bool = True,
    speed: float = 2.0,
    width: int = 3,
    hue: int = 0,
    brightness: float = 0.8,
    background_brightness: float = 0.0,
    trail: float = 0.5,
    kelvin: int = 3500,
    zones_per_bulb: int = 1,
)
```

Bases: `FrameEffect`

Larson scanner -- a bright eye sweeps back and forth.

The eye has a cosine-shaped brightness profile so it tapers smoothly on both sides. Eye width, color, speed, and trail are all tunable.

| ATTRIBUTE               | DESCRIPTION                                      |
| ----------------------- | ------------------------------------------------ |
| `speed`                 | Seconds per full sweep (there and back)          |
| `width`                 | Width of the eye in logical bulbs                |
| `hue`                   | Eye color hue in degrees (0-360)                 |
| `brightness`            | Peak eye brightness (0.0-1.0)                    |
| `background_brightness` | Background brightness (0.0-1.0)                  |
| `trail`                 | Trail decay factor (0.0=no trail, 1.0=max trail) |
| `kelvin`                | Color temperature (1500-9000)                    |
| `zones_per_bulb`        | Number of physical zones per logical bulb        |

Example

```python
effect = EffectCylon(speed=2.0, hue=0, width=3)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER               | DESCRIPTION                                                                                  |
| ----------------------- | -------------------------------------------------------------------------------------------- |
| `power_on`              | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                  |
| `speed`                 | Seconds per full sweep, must be > 0 (default 2.0) **TYPE:** `float` **DEFAULT:** `2.0`       |
| `width`                 | Width of the eye in logical bulbs, must be >= 1 (default 3) **TYPE:** `int` **DEFAULT:** `3` |
| `hue`                   | Eye color hue 0-360 degrees (default 0, red) **TYPE:** `int` **DEFAULT:** `0`                |
| `brightness`            | Peak eye brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`               |
| `background_brightness` | Background brightness 0.0-1.0 (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`             |
| `trail`                 | Trail decay factor 0.0-1.0 (default 0.5) **TYPE:** `float` **DEFAULT:** `0.5`                |
| `kelvin`                | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`               |
| `zones_per_bulb`        | Physical zones per logical bulb (default 1) **TYPE:** `int` **DEFAULT:** `1`                 |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                           |
| --------------------- | ----------------------------------------------------- |
| `generate_frame`      | Generate a frame of the Cylon scanner.                |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.       |
| `is_light_compatible` | Check if light is compatible with Cylon effect.       |
| `inherit_prestate`    | Cylon can inherit prestate from another Cylon effect. |
| `__repr__`            | String representation of Cylon effect.                |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of the Cylon scanner.

The eye position is computed via sinusoidal easing across the zone range. Each zone's brightness is the cosine falloff from the eye center, floored at the background brightness. When trail > 0, previous frame brightness decays and blends with the current frame to create a glowing tail behind the eye.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                     |
| ------- | ----------------------------------------------- |
| `HSBK`  | Eye color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with Cylon effect.

Cylon requires color capability to manipulate hue/saturation.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `bool`  | True if light has color support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Cylon can inherit prestate from another Cylon effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                        |
| ------- | -------------------------------------------------- |
| `bool`  | True if other is also EffectCylon, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Cylon effect.

______________________________________________________________________

### EffectDoubleSlit

#### EffectDoubleSlit

```python
EffectDoubleSlit(
    power_on: bool = True,
    speed: float = 4.0,
    wavelength: float = 0.3,
    separation: float = 0.2,
    breathe: float = 0.0,
    hue1: int = 0,
    hue2: int = 240,
    saturation: float = 1.0,
    brightness: float = 0.8,
    kelvin: int = 3500,
    zones_per_bulb: int = 1,
)
```

Bases: `FrameEffect`

Double slit interference -- two coherent wave sources.

Two point sources at configurable positions emit sinusoidal waves. The combined amplitude at each zone determines brightness and color: constructive interference is bright, destructive is dark. An optional breathe parameter modulates wavelength over time, making the fringe pattern shift and evolve.

| ATTRIBUTE        | DESCRIPTION                                             |
| ---------------- | ------------------------------------------------------- |
| `speed`          | Wave propagation period in seconds                      |
| `wavelength`     | Base wavelength as fraction of strip length (0.0-1.0)   |
| `separation`     | Source separation as fraction of strip length (0.0-1.0) |
| `breathe`        | Wavelength modulation period in seconds (0 = off)       |
| `hue1`           | Color for positive displacement (0-360 degrees)         |
| `hue2`           | Color for negative displacement (0-360 degrees)         |
| `saturation`     | Wave color saturation (0.0-1.0)                         |
| `brightness`     | Peak brightness (0.0-1.0)                               |
| `kelvin`         | Color temperature (1500-9000)                           |
| `zones_per_bulb` | Number of physical zones per logical bulb               |

Example

```python
effect = EffectDoubleSlit(speed=4.0, wavelength=0.3, separation=0.2)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER        | DESCRIPTION                                                                                                |
| ---------------- | ---------------------------------------------------------------------------------------------------------- |
| `power_on`       | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                                |
| `speed`          | Wave propagation period in seconds, must be > 0 (default 4.0) **TYPE:** `float` **DEFAULT:** `4.0`         |
| `wavelength`     | Base wavelength as fraction of strip length, 0.05-2.0 (default 0.3) **TYPE:** `float` **DEFAULT:** `0.3`   |
| `separation`     | Source separation as fraction of strip length, 0.05-0.9 (default 0.2) **TYPE:** `float` **DEFAULT:** `0.2` |
| `breathe`        | Wavelength modulation period in seconds, 0 = off (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`        |
| `hue1`           | Color 1 hue 0-360 degrees (default 0, red) **TYPE:** `int` **DEFAULT:** `0`                                |
| `hue2`           | Color 2 hue 0-360 degrees (default 240, blue) **TYPE:** `int` **DEFAULT:** `240`                           |
| `saturation`     | Wave color saturation 0.0-1.0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                           |
| `brightness`     | Peak brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                                 |
| `kelvin`         | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`                             |
| `zones_per_bulb` | Physical zones per logical bulb (default 1) **TYPE:** `int` **DEFAULT:** `1`                               |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                                      |
| --------------------- | ---------------------------------------------------------------- |
| `generate_frame`      | Generate a frame of double slit interference.                    |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.                  |
| `is_light_compatible` | Check if light is compatible with double slit effect.            |
| `inherit_prestate`    | Double slit can inherit prestate from another DoubleSlit effect. |
| `__repr__`            | String representation of DoubleSlit effect.                      |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of double slit interference.

Two sinusoidal waves propagate from point sources. Their sum creates an interference pattern that shifts as the wavelength breathes.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `HSBK`  | Midpoint color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with double slit effect.

Double slit requires color capability to manipulate hue/saturation.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `bool`  | True if light has color support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Double slit can inherit prestate from another DoubleSlit effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                             |
| ------- | ------------------------------------------------------- |
| `bool`  | True if other is also EffectDoubleSlit, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of DoubleSlit effect.

______________________________________________________________________

### EffectEmbers

#### EffectEmbers

```python
EffectEmbers(
    power_on: bool = True,
    intensity: float = 0.5,
    cooling: float = 0.15,
    turbulence: float = 0.3,
    brightness: float = 0.8,
    kelvin: int = 3500,
    zones_per_bulb: int = 1,
)
```

Bases: `FrameEffect`

Embers -- fire simulation via heat diffusion.

Heat is injected randomly at the bottom of the strip each frame. A 1D diffusion kernel with a cooling factor makes heat drift upward, dim, and die -- like glowing embers in a chimney.

| ATTRIBUTE        | DESCRIPTION                                       |
| ---------------- | ------------------------------------------------- |
| `intensity`      | Probability of heat injection per frame (0.0-1.0) |
| `cooling`        | Cooling factor per diffusion step (0.0-1.0)       |
| `turbulence`     | Random per-cell flicker amplitude (0.0-0.3)       |
| `brightness`     | Overall brightness (0.0-1.0)                      |
| `kelvin`         | Color temperature (1500-9000)                     |
| `zones_per_bulb` | Number of physical zones per logical bulb         |

Example

```python
effect = EffectEmbers(intensity=0.7, cooling=0.15, brightness=0.8)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER        | DESCRIPTION                                                                                                                                                                   |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `power_on`       | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                                                                                                   |
| `intensity`      | Probability of heat injection per frame, 0.0-1.0 (default 0.5) **TYPE:** `float` **DEFAULT:** `0.5`                                                                           |
| `cooling`        | Cooling factor per diffusion step, 0.80-0.999. Higher values mean slower cooling (default 0.15, mapped to 0.85 internally as 1-cooling) **TYPE:** `float` **DEFAULT:** `0.15` |
| `turbulence`     | Random per-cell flicker amplitude, 0.0-0.3 (default 0.3) **TYPE:** `float` **DEFAULT:** `0.3`                                                                                 |
| `brightness`     | Overall brightness, 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                                                                                                |
| `kelvin`         | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`                                                                                                |
| `zones_per_bulb` | Physical zones per logical bulb (default 1) **TYPE:** `int` **DEFAULT:** `1`                                                                                                  |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                             |
| --------------------- | ------------------------------------------------------- |
| `generate_frame`      | Generate one frame of the embers fire simulation.       |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.         |
| `is_light_compatible` | Check if light is compatible with Embers effect.        |
| `inherit_prestate`    | Embers can inherit prestate from another Embers effect. |
| `__repr__`            | String representation of Embers effect.                 |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate one frame of the embers fire simulation.

Performs convection, diffusion with cooling, turbulence, and heat injection, then maps temperature values to the ember color gradient.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                    |
| ------- | ---------------------------------------------- |
| `HSBK`  | Deep red at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with Embers effect.

Embers requires color capability. Works on single lights and multizone strips. Matrix devices are not supported.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                                |
| ------- | ---------------------------------------------------------- |
| `bool`  | True if light has color support and is not a matrix device |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Embers can inherit prestate from another Embers effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                         |
| ------- | --------------------------------------------------- |
| `bool`  | True if other is also EffectEmbers, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Embers effect.

______________________________________________________________________

### EffectFireworks

#### EffectFireworks

```python
EffectFireworks(
    power_on: bool = True,
    max_rockets: int = 3,
    launch_rate: float = 0.5,
    ascent_speed: float = 0.3,
    burst_spread: float = 5.0,
    burst_duration: float = 2.0,
    brightness: float = 0.8,
    kelvin: int = 3500,
)
```

Bases: `FrameEffect`

Rockets from both ends burst into spreading color halos.

Each rocket:

1. Launches from zone 0 or the last zone (chosen at random).
1. Decelerates as it approaches a random zenith in the middle section of the strip, producing a bright head and fading exhaust trail.
1. Detonates at zenith: a gaussian bloom of color expands outward and fades to black. Color evolves from white-hot through peak chemical color to warm orange.

Multiple rockets overlap additively in RGB space for physically correct color mixing.

| ATTRIBUTE        | DESCRIPTION                               |
| ---------------- | ----------------------------------------- |
| `max_rockets`    | Maximum simultaneous rockets in flight    |
| `launch_rate`    | Average new rockets launched per second   |
| `ascent_speed`   | Rocket travel speed in zones per second   |
| `burst_spread`   | Maximum burst radius in zones from zenith |
| `burst_duration` | Seconds for the burst to fade to black    |
| `brightness`     | Peak brightness multiplier (0.0-1.0)      |
| `kelvin`         | Color temperature (1500-9000)             |

Example

```python
effect = EffectFireworks(max_rockets=5, launch_rate=1.0)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER        | DESCRIPTION                                                                                |
| ---------------- | ------------------------------------------------------------------------------------------ |
| `power_on`       | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                |
| `max_rockets`    | Maximum simultaneous rockets, 1-20 (default 3) **TYPE:** `int` **DEFAULT:** `3`            |
| `launch_rate`    | Average launches per second, 0.05-5.0 (default 0.5) **TYPE:** `float` **DEFAULT:** `0.5`   |
| `ascent_speed`   | Zones per second travel speed, 0.1-60.0 (default 0.3) **TYPE:** `float` **DEFAULT:** `0.3` |
| `burst_spread`   | Max burst radius in zones, 2.0-60.0 (default 5.0) **TYPE:** `float` **DEFAULT:** `5.0`     |
| `burst_duration` | Seconds for burst fade, 0.2-8.0 (default 2.0) **TYPE:** `float` **DEFAULT:** `2.0`         |
| `brightness`     | Peak brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                 |
| `kelvin`         | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`             |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                                   |
| --------------------- | ------------------------------------------------------------- |
| `generate_frame`      | Generate one frame of fireworks.                              |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.               |
| `is_light_compatible` | Check if light is compatible with Fireworks effect.           |
| `inherit_prestate`    | Fireworks can inherit prestate from another Fireworks effect. |
| `__repr__`            | String representation of Fireworks effect.                    |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate one frame of fireworks.

Manages the rocket lifecycle (spawn / expire), then composites all active rockets onto the zone array using additive RGB blending.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                   |
| ------- | --------------------------------------------- |
| `HSBK`  | Black at configured kelvin for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with Fireworks effect.

Fireworks requires multizone capability (strips/beams). Single lights are not supported; matrix devices are not supported.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `bool`  | True if light has multizone support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Fireworks can inherit prestate from another Fireworks effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                            |
| ------- | ------------------------------------------------------ |
| `bool`  | True if other is also EffectFireworks, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Fireworks effect.

______________________________________________________________________

### EffectFlame

#### EffectFlame

```python
EffectFlame(
    power_on: bool = True,
    intensity: float = 0.7,
    speed: float = 1.0,
    kelvin_min: int = 1500,
    kelvin_max: int = 2500,
    brightness: float = 0.8,
)
```

Bases: `FrameEffect`

Fire/candle flicker effect using layered sine waves.

Creates organic brightness variation with warm colors ranging from deep red to yellow. On matrix devices, applies vertical brightness falloff so bottom rows are hotter.

| ATTRIBUTE    | DESCRIPTION                                          |
| ------------ | ---------------------------------------------------- |
| `intensity`  | Flicker intensity 0.0-1.0 (higher = more variation)  |
| `speed`      | Animation speed multiplier (higher = faster flicker) |
| `kelvin_min` | Minimum color temperature                            |
| `kelvin_max` | Maximum color temperature                            |
| `brightness` | Base brightness level                                |

Example

```python
# Default candle flicker
effect = EffectFlame()
await conductor.start(effect, lights)

# Intense fast fire
effect = EffectFlame(intensity=1.0, speed=2.0, brightness=1.0)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER    | DESCRIPTION                                                                                |
| ------------ | ------------------------------------------------------------------------------------------ |
| `power_on`   | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                |
| `intensity`  | Flicker intensity 0.0-1.0 (default 0.7) **TYPE:** `float` **DEFAULT:** `0.7`               |
| `speed`      | Animation speed multiplier, must be > 0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0` |
| `kelvin_min` | Minimum color temperature (default 1500) **TYPE:** `int` **DEFAULT:** `1500`               |
| `kelvin_max` | Maximum color temperature (default 2500) **TYPE:** `int` **DEFAULT:** `2500`               |
| `brightness` | Base brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                 |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                           |
| --------------------- | ----------------------------------------------------- |
| `generate_frame`      | Generate a frame of flame colors for one device.      |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.       |
| `is_light_compatible` | Check if light is compatible with flame effect.       |
| `inherit_prestate`    | Flame can inherit prestate from another flame effect. |
| `__repr__`            | String representation of flame effect.                |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of flame colors for one device.

Each pixel gets a unique flicker pattern based on its spatial position. Matrix devices get vertical brightness falloff.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                            |
| ------- | ------------------------------------------------------ |
| `HSBK`  | Warm amber color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with flame effect.

Flame requires color capability to manipulate hue/saturation.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `bool`  | True if light has color support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Flame can inherit prestate from another flame effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                        |
| ------- | -------------------------------------------------- |
| `bool`  | True if other is also EffectFlame, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of flame effect.

______________________________________________________________________

### EffectJacobsLadder

#### EffectJacobsLadder

```python
EffectJacobsLadder(
    power_on: bool = True,
    speed: float = 0.5,
    arcs: int = 2,
    gap: int = 5,
    brightness: float = 0.8,
    kelvin: int = 6500,
    zones_per_bulb: int = 1,
)
```

Bases: `FrameEffect`

Jacob's Ladder -- rising electric arcs between electrode pairs.

Arc pairs drift along the strip, break off at the end, and reform. The electrode gap breathes with smooth noise. Multiple arcs can coexist, and at least one is always visible.

| ATTRIBUTE        | DESCRIPTION                                   |
| ---------------- | --------------------------------------------- |
| `speed`          | Arc drift speed in bulbs per frame (0.02-1.0) |
| `arcs`           | Target number of simultaneous arc pairs (1-5) |
| `gap`            | Base gap between electrodes in bulbs (2-12)   |
| `brightness`     | Overall brightness 0.0-1.0                    |
| `kelvin`         | Color temperature 1500-9000                   |
| `zones_per_bulb` | Physical zones per logical bulb               |

Example

```python
effect = EffectJacobsLadder(speed=0.5, arcs=2, gap=5)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER        | DESCRIPTION                                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| `power_on`       | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                             |
| `speed`          | Arc drift speed in bulbs per frame, must be 0.02-1.0 (default 0.5) **TYPE:** `float` **DEFAULT:** `0.5` |
| `arcs`           | Target number of simultaneous arc pairs, must be 1-5 (default 2) **TYPE:** `int` **DEFAULT:** `2`       |
| `gap`            | Base gap between electrodes in bulbs, must be 2-12 (default 5) **TYPE:** `int` **DEFAULT:** `5`         |
| `brightness`     | Overall brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                           |
| `kelvin`         | Color temperature 1500-9000 (default 6500) **TYPE:** `int` **DEFAULT:** `6500`                          |
| `zones_per_bulb` | Physical zones per logical bulb, must be >= 1 (default 1) **TYPE:** `int` **DEFAULT:** `1`              |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                                      |
| --------------------- | ---------------------------------------------------------------- |
| `generate_frame`      | Generate a frame of the Jacob's Ladder effect.                   |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.                  |
| `is_light_compatible` | Check if light is compatible with Jacob's Ladder effect.         |
| `inherit_prestate`    | Jacob's Ladder can inherit prestate from another Jacob's Ladder. |
| `__repr__`            | String representation of Jacob's Ladder effect.                  |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of the Jacob's Ladder effect.

Renders electrode glows, flickering arcs, surges, and crackle spikes across the strip.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                     |
| ------- | ----------------------------------------------- |
| `HSBK`  | Arc color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with Jacob's Ladder effect.

Jacob's Ladder requires multizone capability (strips/beams).

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `bool`  | True if light has multizone support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Jacob's Ladder can inherit prestate from another Jacob's Ladder.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                               |
| ------- | --------------------------------------------------------- |
| `bool`  | True if other is also EffectJacobsLadder, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Jacob's Ladder effect.

______________________________________________________________________

### EffectNewtonsCradle

#### EffectNewtonsCradle

```python
EffectNewtonsCradle(
    power_on: bool = True,
    num_balls: int = 5,
    ball_width: int = 0,
    speed: float = 2.0,
    hue: int = 0,
    saturation: float = 0.0,
    brightness: float = 0.8,
    shininess: int = 60,
    kelvin: int = 4500,
    zones_per_bulb: int = 1,
)
```

Bases: `FrameEffect`

Newton's Cradle -- alternating pendulum balls with Phong sphere shading.

Five steel-coloured balls hang in a row separated by gaps. The rightmost and leftmost balls swing alternately; the middle balls stay still. Each ball is rendered as a 3-D sphere so the specular highlight glides across its surface as it swings.

| ATTRIBUTE        | DESCRIPTION                                       |
| ---------------- | ------------------------------------------------- |
| `num_balls`      | Number of balls in the cradle (2-10)              |
| `ball_width`     | Zones per ball; 0 = auto-size to fit strip        |
| `speed`          | Full period in seconds (left-swing + right-swing) |
| `hue`            | Ball base hue in degrees (0-360)                  |
| `saturation`     | Ball base saturation (0.0-1.0)                    |
| `brightness`     | Maximum ball brightness (0.0-1.0)                 |
| `shininess`      | Phong specular exponent (1-100)                   |
| `kelvin`         | Color temperature (1500-9000)                     |
| `zones_per_bulb` | Physical zones per logical bulb                   |

Example

```python
effect = EffectNewtonsCradle(num_balls=5, speed=2.0)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER        | DESCRIPTION                                                                                  |
| ---------------- | -------------------------------------------------------------------------------------------- |
| `power_on`       | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                  |
| `num_balls`      | Number of balls (2-10, default 5) **TYPE:** `int` **DEFAULT:** `5`                           |
| `ball_width`     | Zones per ball; 0 = auto-size (default 0) **TYPE:** `int` **DEFAULT:** `0`                   |
| `speed`          | Full cycle period in seconds, must be > 0 (default 2.0) **TYPE:** `float` **DEFAULT:** `2.0` |
| `hue`            | Ball base hue 0-360 degrees (default 0) **TYPE:** `int` **DEFAULT:** `0`                     |
| `saturation`     | Ball base saturation 0.0-1.0 (default 0.0, steel) **TYPE:** `float` **DEFAULT:** `0.0`       |
| `brightness`     | Maximum ball brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`           |
| `shininess`      | Phong specular exponent 1-100 (default 60) **TYPE:** `int` **DEFAULT:** `60`                 |
| `kelvin`         | Color temperature 1500-9000 (default 4500) **TYPE:** `int` **DEFAULT:** `4500`               |
| `zones_per_bulb` | Physical zones per logical bulb (default 1) **TYPE:** `int` **DEFAULT:** `1`                 |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                                 |
| --------------------- | ----------------------------------------------------------- |
| `generate_frame`      | Generate a frame of the Newton's Cradle.                    |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.             |
| `is_light_compatible` | Check if light is compatible with Newton's Cradle effect.   |
| `inherit_prestate`    | Newton's Cradle can inherit prestate from another instance. |
| `__repr__`            | String representation of Newton's Cradle effect.            |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of the Newton's Cradle.

Computes ball positions from the pendulum phase, then for each zone determines which ball (if any) covers it and applies Phong shading in the ball's local coordinate frame.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `HSBK`  | Ball color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with Newton's Cradle effect.

Newton's Cradle requires multizone capability for meaningful rendering across multiple zones.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `bool`  | True if light has multizone support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Newton's Cradle can inherit prestate from another instance.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                                |
| ------- | ---------------------------------------------------------- |
| `bool`  | True if other is also EffectNewtonsCradle, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Newton's Cradle effect.

______________________________________________________________________

### EffectPendulumWave

#### EffectPendulumWave

```python
EffectPendulumWave(
    power_on: bool = True,
    speed: float = 30.0,
    cycles: int = 8,
    hue1: int = 0,
    hue2: int = 240,
    saturation1: float = 1.0,
    saturation2: float = 1.0,
    brightness: float = 0.8,
    kelvin: int = 3500,
    zones_per_bulb: int = 1,
)
```

Bases: `FrameEffect`

Pendulum wave -- a row of pendulums drifting in and out of phase.

Each zone is a pendulum with a slightly different frequency. Over one full cycle (`speed` seconds) the ensemble passes through traveling waves, standing waves, and chaos before all pendulums realign perfectly.

Displacement maps to a color blend between two hues and to brightness modulation -- pendulums at the extremes of their swing are brightest, pendulums passing through center are dimmest.

| ATTRIBUTE        | DESCRIPTION                                              |
| ---------------- | -------------------------------------------------------- |
| `speed`          | Seconds for one full realignment cycle                   |
| `cycles`         | Number of oscillations of the slowest pendulum per cycle |
| `hue1`           | Color 1 hue in degrees (0-360, negative displacement)    |
| `hue2`           | Color 2 hue in degrees (0-360, positive displacement)    |
| `saturation1`    | Color 1 saturation (0.0-1.0)                             |
| `saturation2`    | Color 2 saturation (0.0-1.0)                             |
| `brightness`     | Overall brightness (0.0-1.0)                             |
| `kelvin`         | Color temperature (1500-9000)                            |
| `zones_per_bulb` | Number of physical zones per logical bulb                |

Example

```python
effect = EffectPendulumWave(speed=30.0, cycles=8, hue1=0, hue2=240)
await conductor.start(effect, lights)

await asyncio.sleep(60)
await conductor.stop(lights)
```

| PARAMETER        | DESCRIPTION                                                                                           |
| ---------------- | ----------------------------------------------------------------------------------------------------- |
| `power_on`       | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                           |
| `speed`          | Seconds for full realignment cycle, must be > 0 (default 30.0) **TYPE:** `float` **DEFAULT:** `30.0`  |
| `cycles`         | Oscillations of slowest pendulum per cycle, must be >= 1 (default 8) **TYPE:** `int` **DEFAULT:** `8` |
| `hue1`           | Color 1 hue 0-360 degrees (default 0, red) **TYPE:** `int` **DEFAULT:** `0`                           |
| `hue2`           | Color 2 hue 0-360 degrees (default 240, blue) **TYPE:** `int` **DEFAULT:** `240`                      |
| `saturation1`    | Color 1 saturation 0.0-1.0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                         |
| `saturation2`    | Color 2 saturation 0.0-1.0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                         |
| `brightness`     | Overall brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                         |
| `kelvin`         | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`                        |
| `zones_per_bulb` | Physical zones per logical bulb (default 1) **TYPE:** `int` **DEFAULT:** `1`                          |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                                          |
| --------------------- | -------------------------------------------------------------------- |
| `generate_frame`      | Generate a frame of the pendulum wave.                               |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.                      |
| `is_light_compatible` | Check if light is compatible with pendulum wave effect.              |
| `inherit_prestate`    | Pendulum wave can inherit prestate from another PendulumWave effect. |
| `__repr__`            | String representation of PendulumWave effect.                        |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of the pendulum wave.

Each zone computes a displacement from its individual pendulum frequency, then maps that to a color blend and brightness level.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `HSBK`  | Midpoint color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with pendulum wave effect.

Pendulum wave requires color capability to manipulate hue/saturation.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `bool`  | True if light has color support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Pendulum wave can inherit prestate from another PendulumWave effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                               |
| ------- | --------------------------------------------------------- |
| `bool`  | True if other is also EffectPendulumWave, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of PendulumWave effect.

______________________________________________________________________

### EffectPlasma

#### EffectPlasma

```python
EffectPlasma(
    power_on: bool = True,
    speed: float = 3.0,
    tendril_rate: float = 0.5,
    hue: int = 270,
    hue_spread: float = 60.0,
    brightness: float = 0.8,
    kelvin: int = 3500,
    zones_per_bulb: int = 1,
)
```

Bases: `FrameEffect`

Plasma ball -- electric tendrils from a pulsing central core.

A bright core sits at the center of the strip, pulsing slowly. Electric tendrils crackle outward toward the ends, flickering and forking. Brightness falls off with distance from the core. The constantly regenerating tendrils give the characteristic look of a plasma globe.

Compatible with single lights and multizone (strip/beam) devices. Not supported on matrix devices.

| ATTRIBUTE        | DESCRIPTION                               |
| ---------------- | ----------------------------------------- |
| `speed`          | Core pulse period in seconds              |
| `tendril_rate`   | Average new tendrils spawned per second   |
| `hue`            | Base tendril hue in degrees (0-360)       |
| `hue_spread`     | Random hue variation in degrees           |
| `brightness`     | Peak brightness (0.0-1.0)                 |
| `kelvin`         | Color temperature (1500-9000)             |
| `zones_per_bulb` | Number of physical zones per logical bulb |

Example

```python
effect = EffectPlasma(speed=3.0, hue=270, brightness=0.8)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER        | DESCRIPTION                                                                                         |
| ---------------- | --------------------------------------------------------------------------------------------------- |
| `power_on`       | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                         |
| `speed`          | Core pulse period in seconds, must be > 0 (default 3.0) **TYPE:** `float` **DEFAULT:** `3.0`        |
| `tendril_rate`   | Average tendrils spawned per second, must be > 0 (default 0.5) **TYPE:** `float` **DEFAULT:** `0.5` |
| `hue`            | Base tendril hue 0-360 degrees (default 270, violet) **TYPE:** `int` **DEFAULT:** `270`             |
| `hue_spread`     | Random hue variation 0-180 degrees (default 60) **TYPE:** `float` **DEFAULT:** `60.0`               |
| `brightness`     | Peak brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                          |
| `kelvin`         | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`                      |
| `zones_per_bulb` | Physical zones per logical bulb (default 1) **TYPE:** `int` **DEFAULT:** `1`                        |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                             |
| --------------------- | ------------------------------------------------------- |
| `generate_frame`      | Generate one frame of the plasma ball.                  |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.         |
| `is_light_compatible` | Check if light is compatible with plasma effect.        |
| `inherit_prestate`    | Plasma can inherit prestate from another plasma effect. |
| `__repr__`            | String representation of plasma effect.                 |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate one frame of the plasma ball.

Manages tendril lifecycle, computes core glow, and composites all active tendrils onto the zone array.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                        |
| ------- | -------------------------------------------------- |
| `HSBK`  | Violet color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with plasma effect.

Plasma requires color capability. Works best on multizone devices but is compatible with single lights. Not supported on matrix devices.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                                |
| ------- | ---------------------------------------------------------- |
| `bool`  | True if light has color support and is not a matrix device |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Plasma can inherit prestate from another plasma effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                         |
| ------- | --------------------------------------------------- |
| `bool`  | True if other is also EffectPlasma, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of plasma effect.

______________________________________________________________________

### EffectPlasma2D

#### EffectPlasma2D

```python
EffectPlasma2D(
    power_on: bool = True,
    speed: float = 1.0,
    scale: float = 1.0,
    hue1: int = 270,
    hue2: int = 180,
    brightness: float = 0.8,
    kelvin: int = 3500,
)
```

Bases: `FrameEffect`

2D plasma -- sine-wave interference color field for matrix devices.

Sums four sine waves with different spatial frequencies and directions (horizontal, vertical, diagonal, radial) to produce a complex interference pattern. The combined value maps to a blend factor between two configurable colors using Oklab perceptual interpolation.

Compatible only with matrix devices (LIFX Tile, Candle, Path). Not supported on single lights or multizone strips.

| ATTRIBUTE    | DESCRIPTION                              |
| ------------ | ---------------------------------------- |
| `speed`      | Animation speed multiplier               |
| `scale`      | Spatial scale (larger = coarser pattern) |
| `hue1`       | First color hue in degrees (0-360)       |
| `hue2`       | Second color hue in degrees (0-360)      |
| `brightness` | Peak brightness (0.0-1.0)                |
| `kelvin`     | Color temperature (1500-9000)            |

Example

```python
effect = EffectPlasma2D(speed=1.0, hue1=270, hue2=180)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER    | DESCRIPTION                                                                                |
| ------------ | ------------------------------------------------------------------------------------------ |
| `power_on`   | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                |
| `speed`      | Animation speed multiplier, must be > 0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0` |
| `scale`      | Spatial scale, must be > 0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`              |
| `hue1`       | First color hue 0-360 degrees (default 270, violet) **TYPE:** `int` **DEFAULT:** `270`     |
| `hue2`       | Second color hue 0-360 degrees (default 180, cyan) **TYPE:** `int` **DEFAULT:** `180`      |
| `brightness` | Peak brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                 |
| `kelvin`     | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`             |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                                 |
| --------------------- | ----------------------------------------------------------- |
| `generate_frame`      | Generate one frame of the 2D plasma.                        |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.             |
| `is_light_compatible` | Check if light is compatible with 2D plasma effect.         |
| `inherit_prestate`    | Plasma2D can inherit prestate from another Plasma2D effect. |
| `__repr__`            | String representation of Plasma2D effect.                   |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate one frame of the 2D plasma.

Evaluates four sine functions per pixel to build a complex interference pattern. The combined value maps to a blend factor between the two configured colors via Oklab interpolation.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                              |
| ------- | -------------------------------------------------------- |
| `HSBK`  | First plasma color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with 2D plasma effect.

Plasma2D requires matrix capability. Not supported on single lights or multizone strips.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                       |
| ------- | ------------------------------------------------- |
| `bool`  | True if light has matrix support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Plasma2D can inherit prestate from another Plasma2D effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                           |
| ------- | ----------------------------------------------------- |
| `bool`  | True if other is also EffectPlasma2D, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Plasma2D effect.

______________________________________________________________________

### EffectProgress

#### EffectProgress

```python
EffectProgress(
    power_on: bool = True,
    start_value: float = 0.0,
    end_value: float = 100.0,
    position: float = 0.0,
    foreground: HSBK | list[HSBK] | None = None,
    background: HSBK | None = None,
    spot_brightness: float = 1.0,
    spot_width: float = 0.15,
    spot_speed: float = 1.0,
)
```

Bases: `FrameEffect`

Animated progress bar for multizone lights.

Displays a filled/unfilled bar where the filled region has a traveling bright spot that animates along it. The user can update the position value at any time and the bar grows/shrinks accordingly.

The foreground can be a single color or a gradient (list of HSBK stops). When a gradient is used, each pixel's color is determined by its position across the full bar — so the gradient reveals progressively as the bar grows, like a thermometer.

Multizone only — `is_light_compatible()` checks for `has_multizone`.

| ATTRIBUTE         | DESCRIPTION                                                       |
| ----------------- | ----------------------------------------------------------------- |
| `start_value`     | Start of the value range                                          |
| `end_value`       | End of the value range                                            |
| `position`        | Current progress position (mutable)                               |
| `foreground`      | Color or gradient of the filled region (mutable) **TYPE:** \`HSBK |
| `background`      | Color of the unfilled region                                      |
| `spot_brightness` | Peak brightness of the traveling spot                             |
| `spot_width`      | Width of the spot as fraction of filled bar                       |
| `spot_speed`      | Spot oscillation speed in cycles per second                       |

Example

```python
# Single color progress bar
effect = EffectProgress(foreground=Colors.BLUE, end_value=100)
await conductor.start(effect, [strip])
effect.position = 45.0

# Gradient progress bar (blue -> cyan -> green -> yellow -> red)
gradient = [
    HSBK(hue=240, saturation=1.0, brightness=0.8, kelvin=3500),
    HSBK(hue=180, saturation=1.0, brightness=0.8, kelvin=3500),
    HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),
    HSBK(hue=60, saturation=1.0, brightness=0.8, kelvin=3500),
    HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500),
]
effect = EffectProgress(foreground=gradient, end_value=100)
await conductor.start(effect, [strip])
```

| PARAMETER         | DESCRIPTION                                                                                                                                                     |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `power_on`        | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                                                                                     |
| `start_value`     | Start of value range (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`                                                                                         |
| `end_value`       | End of value range (default 100.0) **TYPE:** `float` **DEFAULT:** `100.0`                                                                                       |
| `position`        | Initial progress position (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`                                                                                    |
| `foreground`      | Color or gradient of filled region. Pass a single HSBK for a solid bar, or a list of >= 2 HSBK stops for a gradient. Defaults to Colors.GREEN. **TYPE:** \`HSBK |
| `background`      | Color of unfilled region (default dim neutral) **TYPE:** \`HSBK                                                                                                 |
| `spot_brightness` | Peak brightness of traveling spot 0.0-1.0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                                                                    |
| `spot_width`      | Spot width as fraction of bar 0.0-1.0 (default 0.15) **TYPE:** `float` **DEFAULT:** `0.15`                                                                      |
| `spot_speed`      | Spot cycles per second, must be > 0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                                                                          |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                                 |
| --------------------- | ----------------------------------------------------------- |
| `generate_frame`      | Generate a frame of progress bar colors for one device.     |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.             |
| `is_light_compatible` | Check if light is compatible with progress effect.          |
| `inherit_prestate`    | Progress can inherit prestate from another progress effect. |
| `__repr__`            | String representation of progress effect.                   |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of progress bar colors for one device.

Divides pixels into filled (foreground) and unfilled (background) regions. A bright spot oscillates within the filled region.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                            |
| ------- | -------------------------------------- |
| `HSBK`  | The background color (bar starts dark) |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with progress effect.

Progress requires multizone capability for a meaningful bar display.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `bool`  | True if light has multizone support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Progress can inherit prestate from another progress effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                           |
| ------- | ----------------------------------------------------- |
| `bool`  | True if other is also EffectProgress, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of progress effect.

______________________________________________________________________

### EffectPulse

#### EffectPulse

```python
EffectPulse(
    power_on: bool = True,
    mode: str = "blink",
    period: float | None = None,
    cycles: int | None = None,
    color: HSBK | None = None,
)
```

Bases: `LIFXEffect`

Pulse/blink/breathe effects using waveform modes.

Supports multiple pulse modes: blink, strobe, breathe, ping, solid. Each mode has different timing defaults and waveform behavior.

| ATTRIBUTE    | DESCRIPTION                                                |
| ------------ | ---------------------------------------------------------- |
| `mode`       | Pulse mode ('blink', 'strobe', 'breathe', 'ping', 'solid') |
| `period`     | Effect period in seconds                                   |
| `cycles`     | Number of cycles to execute                                |
| `color`      | Optional color override                                    |
| `waveform`   | Waveform type to use                                       |
| `skew_ratio` | Waveform skew ratio (0.0-1.0)                              |

Example

```python
# Blink effect
effect = EffectPulse(mode="blink", cycles=5)
await conductor.start(effect, [light])

# Strobe with custom color
effect = EffectPulse(
    mode="strobe", cycles=20, color=HSBK.from_rgb(1.0, 0.0, 0.0)
)
await conductor.start(effect, [light])

# Breathe effect
effect = EffectPulse(mode="breathe", period=2.0, cycles=3)
await conductor.start(effect, [light])
```

| PARAMETER  | DESCRIPTION                                                                                                        |
| ---------- | ------------------------------------------------------------------------------------------------------------------ |
| `power_on` | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                                        |
| `mode`     | Pulse mode: 'blink', 'strobe', 'breathe', 'ping', 'solid' (default 'blink') **TYPE:** `str` **DEFAULT:** `'blink'` |
| `period`   | Effect period in seconds. Defaults depend on mode: - strobe: 0.1s, others: 1.0s **TYPE:** \`float                  |
| `cycles`   | Number of cycles. Defaults: - strobe: 10, others: 1 **TYPE:** \`int                                                |
| `color`    | Optional color override. If provided, this color overrides the automatic color selection logic. **TYPE:** \`HSBK   |

| RAISES       | DESCRIPTION        |
| ------------ | ------------------ |
| `ValueError` | If mode is invalid |

| METHOD               | DESCRIPTION                                     |
| -------------------- | ----------------------------------------------- |
| `async_play`         | Execute the pulse effect on all participants.   |
| `from_poweroff_hsbk` | Return startup color when light is powered off. |
| `__repr__`           | String representation of pulse effect.          |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

| RETURNS | DESCRIPTION             |
| ------- | ----------------------- |
| `str`   | The effect name 'pulse' |

##### Functions

###### async_play

```python
async_play() -> None
```

Execute the pulse effect on all participants.

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

For pulse effects, we want a sensible startup color based on mode.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                        |
| ------- | ---------------------------------- |
| `HSBK`  | HSBK color to use as startup color |

###### __repr__

```python
__repr__() -> str
```

String representation of pulse effect.

______________________________________________________________________

### EffectRainbow

#### EffectRainbow

```python
EffectRainbow(
    power_on: bool = True,
    period: float = 10.0,
    brightness: float = 0.8,
    saturation: float = 1.0,
    spread: float = 0.0,
)
```

Bases: `FrameEffect`

Animated rainbow effect that spreads colors across device pixels.

For multizone strips and matrix lights, displays a full 360-degree rainbow spread across all pixels that scrolls over time. For single lights, cycles through the hue spectrum (similar to colorloop but simpler).

| ATTRIBUTE    | DESCRIPTION                                    |
| ------------ | ---------------------------------------------- |
| `period`     | Seconds per full rainbow scroll (default 10)   |
| `brightness` | Fixed brightness (default 0.8)                 |
| `saturation` | Fixed saturation (default 1.0)                 |
| `spread`     | Hue degrees offset between devices (default 0) |

Example

```python
# Rainbow on a multizone strip — scrolls every 10 seconds
effect = EffectRainbow(period=10)
await conductor.start(effect, lights)

# Fast rainbow with lower brightness
effect = EffectRainbow(period=3, brightness=0.5)
await conductor.start(effect, lights)

# Multiple devices offset by 90 degrees
effect = EffectRainbow(period=10, spread=90)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER    | DESCRIPTION                                                                                                                                                                  |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `power_on`   | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                                                                                                  |
| `period`     | Seconds per full rainbow scroll (default 10.0) **TYPE:** `float` **DEFAULT:** `10.0`                                                                                         |
| `brightness` | Fixed brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                                                                                                  |
| `saturation` | Fixed saturation 0.0-1.0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                                                                                                  |
| `spread`     | Hue degrees offset between devices (default 0). When running on multiple devices, each device's rainbow is offset by this many degrees. **TYPE:** `float` **DEFAULT:** `0.0` |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD               | DESCRIPTION                                        |
| -------------------- | -------------------------------------------------- |
| `generate_frame`     | Generate a frame of rainbow colors for one device. |
| `from_poweroff_hsbk` | Return startup color when light is powered off.    |
| `__repr__`           | String representation of rainbow effect.           |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of rainbow colors for one device.

For multi-pixel devices, spreads a full 360-degree rainbow across all pixels. The entire pattern scrolls as time passes. For single lights, cycles through hues over time.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                        |
| ------- | ---------------------------------- |
| `HSBK`  | HSBK color to use as startup color |

###### __repr__

```python
__repr__() -> str
```

String representation of rainbow effect.

______________________________________________________________________

### EffectRipple

#### EffectRipple

```python
EffectRipple(
    power_on: bool = True,
    speed: float = 1.0,
    damping: float = 0.98,
    drop_rate: float = 0.3,
    hue1: int = 200,
    hue2: int = 240,
    saturation: float = 1.0,
    brightness: float = 0.8,
    kelvin: int = 3500,
)
```

Bases: `FrameEffect`

Ripple tank -- raindrops on a 1D water surface.

Random drops hit the surface, launching wavefronts that propagate, reflect off the ends, and interfere. Displacement maps to a blend between two colors using Oklab perceptual interpolation.

This is a stateful effect: it maintains displacement and velocity arrays that evolve over time via the 1D wave equation.

| ATTRIBUTE    | DESCRIPTION                                     |
| ------------ | ----------------------------------------------- |
| `speed`      | Wave propagation speed (higher = faster waves)  |
| `damping`    | Wave damping factor (higher = faster fade)      |
| `drop_rate`  | Average drops per second                        |
| `hue1`       | Color for positive displacement (0-360 degrees) |
| `hue2`       | Color for negative displacement (0-360 degrees) |
| `saturation` | Wave color saturation (0.0-1.0)                 |
| `brightness` | Peak brightness (0.0-1.0)                       |
| `kelvin`     | Color temperature (1500-9000)                   |

Example

```python
effect = EffectRipple(speed=1.0, hue1=200, hue2=240)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER    | DESCRIPTION                                                                                   |
| ------------ | --------------------------------------------------------------------------------------------- |
| `power_on`   | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                   |
| `speed`      | Wave propagation speed, must be > 0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`        |
| `damping`    | Damping factor 0.0-1.0, applied per step (default 0.98) **TYPE:** `float` **DEFAULT:** `0.98` |
| `drop_rate`  | Average drops per second, must be > 0 (default 0.3) **TYPE:** `float` **DEFAULT:** `0.3`      |
| `hue1`       | Color hue for positive displacement 0-360 (default 200) **TYPE:** `int` **DEFAULT:** `200`    |
| `hue2`       | Color hue for negative displacement 0-360 (default 240) **TYPE:** `int` **DEFAULT:** `240`    |
| `saturation` | Color saturation 0.0-1.0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                   |
| `brightness` | Peak brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                    |
| `kelvin`     | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`                |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                             |
| --------------------- | ------------------------------------------------------- |
| `generate_frame`      | Generate a frame of the ripple tank.                    |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.         |
| `is_light_compatible` | Check if light is compatible with ripple effect.        |
| `inherit_prestate`    | Ripple can inherit prestate from another ripple effect. |
| `__repr__`            | String representation of ripple effect.                 |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of the ripple tank.

Advances the wave simulation to match the current time, then maps displacement to color via Oklab interpolation.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                             |
| ------- | ------------------------------------------------------- |
| `HSBK`  | Blue-tinted color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with ripple effect.

Ripple requires multizone capability (LED strips/beams).

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `bool`  | True if light has multizone support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Ripple can inherit prestate from another ripple effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                         |
| ------- | --------------------------------------------------- |
| `bool`  | True if other is also EffectRipple, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of ripple effect.

______________________________________________________________________

### EffectRule30

#### EffectRule30

```python
EffectRule30(
    power_on: bool = True,
    speed: float = 5.0,
    rule: int = 30,
    hue: int = 120,
    brightness: float = 0.8,
    background_brightness: float = 0.05,
    seed: str = "center",
    kelvin: int = 3500,
    zones_per_bulb: int = 1,
)
```

Bases: `FrameEffect`

Wolfram elementary 1D cellular automaton on the zone strip.

Each zone is a cell; alive cells are shown at the configured hue and brightness, dead cells at the background brightness. The CA rule is applied once per generation; generation rate is set by `speed`.

This is a stateful effect: the cell array and generation counter persist across frames and are initialized lazily on the first `generate_frame` call.

| ATTRIBUTE               | DESCRIPTION                                   |
| ----------------------- | --------------------------------------------- |
| `speed`                 | Generations per second                        |
| `rule`                  | Wolfram elementary CA rule number (0-255)     |
| `hue`                   | Alive-cell hue in degrees (0-360)             |
| `brightness`            | Alive-cell brightness (0.0-1.0)               |
| `background_brightness` | Dead-cell brightness (0.0-1.0)                |
| `seed`                  | Initial seed mode ("center", "random", "all") |
| `kelvin`                | Color temperature (1500-9000)                 |
| `zones_per_bulb`        | Number of physical zones per logical bulb     |

Example

```python
effect = EffectRule30(speed=5.0, rule=30, hue=120)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER               | DESCRIPTION                                                                                                |
| ----------------------- | ---------------------------------------------------------------------------------------------------------- |
| `power_on`              | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                                |
| `speed`                 | Generations per second, must be > 0 (default 5.0) **TYPE:** `float` **DEFAULT:** `5.0`                     |
| `rule`                  | Wolfram elementary CA rule number 0-255 (default 30) **TYPE:** `int` **DEFAULT:** `30`                     |
| `hue`                   | Alive-cell hue 0-360 degrees (default 120, green) **TYPE:** `int` **DEFAULT:** `120`                       |
| `brightness`            | Alive-cell brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                           |
| `background_brightness` | Dead-cell brightness 0.0-1.0 (default 0.05) **TYPE:** `float` **DEFAULT:** `0.05`                          |
| `seed`                  | Initial seed mode: "center", "random", or "all" (default "center") **TYPE:** `str` **DEFAULT:** `'center'` |
| `kelvin`                | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`                             |
| `zones_per_bulb`        | Physical zones per logical bulb (default 1) **TYPE:** `int` **DEFAULT:** `1`                               |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                               |
| --------------------- | --------------------------------------------------------- |
| `generate_frame`      | Generate a frame of the cellular automaton.               |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.           |
| `is_light_compatible` | Check if light is compatible with Rule 30 effect.         |
| `inherit_prestate`    | Rule 30 can inherit prestate from another Rule 30 effect. |
| `__repr__`            | String representation of Rule 30 effect.                  |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of the cellular automaton.

Lazily initializes state on first call. Advances the simulation to the generation corresponding to the elapsed time, then maps alive/dead cells to HSBK colors.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `HSBK`  | Effect hue at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with Rule 30 effect.

Rule 30 requires multizone capability (strips/beams). Single lights are not supported; matrix devices are not supported.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `bool`  | True if light has multizone support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Rule 30 can inherit prestate from another Rule 30 effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                         |
| ------- | --------------------------------------------------- |
| `bool`  | True if other is also EffectRule30, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Rule 30 effect.

______________________________________________________________________

### EffectRuleTrio

#### EffectRuleTrio

```python
EffectRuleTrio(
    power_on: bool = True,
    rule_a: int = 30,
    rule_b: int = 90,
    rule_c: int = 110,
    speed: float = 5.0,
    drift_b: float = 1.31,
    drift_c: float = 1.73,
    theme: list[HSBK] | None = None,
    brightness: float = 0.8,
    kelvin: int = 3500,
    zones_per_bulb: int = 1,
)
```

Bases: `FrameEffect`

Three independent cellular automata with perceptual Oklab colour blending.

Each CA runs its own Wolfram rule at its own speed. At each zone the outputs of the three automata are combined using `HSBK.lerp_oklab()` so colour mixes are perceptually uniform.

The slight speed differences (controlled by *drift_b* and *drift_c*) cause the three patterns to slide relative to one another, producing slowly evolving macro-scale colour structures.

This is a stateful effect: three cell state arrays and three generation counters persist across frames and are initialized lazily on the first `generate_frame` call.

| ATTRIBUTE        | DESCRIPTION                                  |
| ---------------- | -------------------------------------------- |
| `rule_a`         | Wolfram rule for CA A (default 30: chaotic)  |
| `rule_b`         | Wolfram rule for CA B (default 90: fractal)  |
| `rule_c`         | Wolfram rule for CA C (default 110: complex) |
| `speed`          | Base generations per second for CA A         |
| `drift_b`        | Speed multiplier for CA B relative to A      |
| `drift_c`        | Speed multiplier for CA C relative to A      |
| `theme`          | Theme providing three colors for the CAs     |
| `brightness`     | Alive-cell brightness (0.0-1.0)              |
| `kelvin`         | Color temperature (1500-9000)                |
| `zones_per_bulb` | Physical zones per logical bulb              |

Example

```python
effect = EffectRuleTrio(speed=5.0, rule_a=30, rule_b=90, rule_c=110)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER        | DESCRIPTION                                                                                                                    |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `power_on`       | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                                                    |
| `rule_a`         | Wolfram rule for CA A, 0-255 (default 30) **TYPE:** `int` **DEFAULT:** `30`                                                    |
| `rule_b`         | Wolfram rule for CA B, 0-255 (default 90) **TYPE:** `int` **DEFAULT:** `90`                                                    |
| `rule_c`         | Wolfram rule for CA C, 0-255 (default 110) **TYPE:** `int` **DEFAULT:** `110`                                                  |
| `speed`          | Base generations per second, must be > 0 (default 5.0) **TYPE:** `float` **DEFAULT:** `5.0`                                    |
| `drift_b`        | Speed multiplier for CA B (default 1.31, irrational) **TYPE:** `float` **DEFAULT:** `1.31`                                     |
| `drift_c`        | Speed multiplier for CA C (default 1.73, irrational) **TYPE:** `float` **DEFAULT:** `1.73`                                     |
| `theme`          | List of 3+ HSBK colors; first three used as CA primaries. When None, uses ThemeLibrary.get("exciting"). **TYPE:** \`list[HSBK] |
| `brightness`     | Alive-cell brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                                               |
| `kelvin`         | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`                                                 |
| `zones_per_bulb` | Physical zones per logical bulb (default 1) **TYPE:** `int` **DEFAULT:** `1`                                                   |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                                   |
| --------------------- | ------------------------------------------------------------- |
| `generate_frame`      | Generate a frame by blending three CA outputs.                |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.               |
| `is_light_compatible` | Check if light is compatible with Rule Trio effect.           |
| `inherit_prestate`    | Rule Trio can inherit prestate from another Rule Trio effect. |
| `__repr__`            | String representation of Rule Trio effect.                    |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame by blending three CA outputs.

Each zone's colour is determined by which CAs have a live cell there: 0 alive -> background; 1 alive -> that primary; 2 alive -> Oklab midpoint; 3 alive -> Oklab centroid of all three.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                             |
| ------- | ------------------------------------------------------- |
| `HSBK`  | First theme color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with Rule Trio effect.

Rule Trio requires multizone capability (strips/beams). Single lights are not supported; matrix devices are not supported.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `bool`  | True if light has multizone support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Rule Trio can inherit prestate from another Rule Trio effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                           |
| ------- | ----------------------------------------------------- |
| `bool`  | True if other is also EffectRuleTrio, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Rule Trio effect.

______________________________________________________________________

### EffectSine

#### EffectSine

```python
EffectSine(
    power_on: bool = True,
    speed: float = 4.0,
    wavelength: float = 0.5,
    hue: int = 200,
    saturation: float = 1.0,
    brightness: float = 0.8,
    floor: float = 0.02,
    hue2: int | None = None,
    kelvin: int = 3500,
    zones_per_bulb: int = 1,
    reverse: bool = False,
)
```

Bases: `FrameEffect`

Traveling ease wave -- bright humps roll along the strip.

Each zone computes a traveling wave phase, then the positive half-cycle is remapped through cubic ease-in-ease-out (smoothstep). The negative half-cycle shows floor brightness, creating distinct bright humps separated by dim gaps that scroll continuously.

| ATTRIBUTE        | DESCRIPTION                                                       |
| ---------------- | ----------------------------------------------------------------- |
| `speed`          | Seconds per full wave cycle (travel speed)                        |
| `wavelength`     | Wavelength as fraction of strip length                            |
| `hue`            | Wave color hue in degrees (0-360)                                 |
| `saturation`     | Wave color saturation (0.0-1.0)                                   |
| `brightness`     | Peak brightness (0.0-1.0)                                         |
| `floor`          | Minimum brightness (0.0-1.0, must be < brightness)                |
| `hue2`           | Optional second hue for gradient along the wave (None = disabled) |
| `kelvin`         | Color temperature (1500-9000)                                     |
| `zones_per_bulb` | Number of physical zones per logical bulb                         |
| `reverse`        | Reverse wave travel direction                                     |

Example

```python
effect = EffectSine(speed=4.0, hue=200, wavelength=0.5)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER        | DESCRIPTION                                                                                            |
| ---------------- | ------------------------------------------------------------------------------------------------------ |
| `power_on`       | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                            |
| `speed`          | Seconds per full wave cycle, must be > 0 (default 4.0) **TYPE:** `float` **DEFAULT:** `4.0`            |
| `wavelength`     | Wavelength as fraction of strip length, must be > 0 (default 0.5) **TYPE:** `float` **DEFAULT:** `0.5` |
| `hue`            | Wave color hue 0-360 degrees (default 200) **TYPE:** `int` **DEFAULT:** `200`                          |
| `saturation`     | Wave color saturation 0.0-1.0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                       |
| `brightness`     | Peak brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                             |
| `floor`          | Minimum brightness 0.0-1.0, must be < brightness (default 0.02) **TYPE:** `float` **DEFAULT:** `0.02`  |
| `hue2`           | Optional second hue 0-360 for gradient (default None, disabled) **TYPE:** \`int                        |
| `kelvin`         | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`                         |
| `zones_per_bulb` | Physical zones per logical bulb (default 1) **TYPE:** `int` **DEFAULT:** `1`                           |
| `reverse`        | Reverse wave direction (default False) **TYPE:** `bool` **DEFAULT:** `False`                           |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                         |
| --------------------- | --------------------------------------------------- |
| `generate_frame`      | Generate a frame of the traveling ease wave.        |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.     |
| `is_light_compatible` | Check if light is compatible with sine effect.      |
| `inherit_prestate`    | Sine can inherit prestate from another Sine effect. |
| `__repr__`            | String representation of Sine effect.               |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of the traveling ease wave.

Each zone computes a traveling-wave phase. The positive half-cycle is remapped through smoothstep for flicker-free brightness; the negative half-cycle holds at floor brightness.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `HSBK`  | Wave color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with sine effect.

Sine requires color capability to manipulate hue/saturation.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `bool`  | True if light has color support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Sine can inherit prestate from another Sine effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                       |
| ------- | ------------------------------------------------- |
| `bool`  | True if other is also EffectSine, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Sine effect.

______________________________________________________________________

### EffectSonar

#### EffectSonar

```python
EffectSonar(
    power_on: bool = True,
    speed: float = 8.0,
    decay: float = 2.0,
    pulse_interval: float = 2.0,
    obstacle_speed: float = 0.5,
    obstacle_hue: int = 15,
    obstacle_brightness: float = 0.8,
    brightness: float = 1.0,
    kelvin: int = 6500,
    zones_per_bulb: int = 1,
)
```

Bases: `FrameEffect`

Sonar pulses bounce off drifting obstacles.

Wavefronts emit from sources positioned at the string ends and between obstacles. Each wavefront travels outward, reflects off the nearest obstacle, and is absorbed when it returns to its source. The wavefront head is bright white; the tail fades to black.

| ATTRIBUTE             | DESCRIPTION                                    |
| --------------------- | ---------------------------------------------- |
| `speed`               | Wavefront travel speed in bulbs per second     |
| `decay`               | Particle decay time in seconds (tail lifetime) |
| `pulse_interval`      | Seconds between pulse emissions                |
| `obstacle_speed`      | Obstacle drift speed in bulbs per second       |
| `obstacle_hue`        | Obstacle color hue in degrees (0-360)          |
| `obstacle_brightness` | Obstacle brightness (0.0-1.0)                  |
| `brightness`          | Wavefront peak brightness (0.0-1.0)            |
| `kelvin`              | Wavefront color temperature (1500-9000)        |
| `zones_per_bulb`      | Number of physical zones per logical bulb      |

Example

```python
effect = EffectSonar(speed=8.0, decay=2.0, pulse_interval=2.0)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER             | DESCRIPTION                                                                                       |
| --------------------- | ------------------------------------------------------------------------------------------------- |
| `power_on`            | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                       |
| `speed`               | Wavefront travel speed in bulbs/s, must be > 0 (default 8.0) **TYPE:** `float` **DEFAULT:** `8.0` |
| `decay`               | Particle decay time in seconds, must be > 0 (default 2.0) **TYPE:** `float` **DEFAULT:** `2.0`    |
| `pulse_interval`      | Seconds between emissions, must be > 0 (default 2.0) **TYPE:** `float` **DEFAULT:** `2.0`         |
| `obstacle_speed`      | Obstacle drift speed in bulbs/s, >= 0 (default 0.5) **TYPE:** `float` **DEFAULT:** `0.5`          |
| `obstacle_hue`        | Obstacle hue 0-360 degrees (default 15) **TYPE:** `int` **DEFAULT:** `15`                         |
| `obstacle_brightness` | Obstacle brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                    |
| `brightness`          | Wavefront peak brightness 0.0-1.0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`              |
| `kelvin`              | Color temperature 1500-9000 (default 6500) **TYPE:** `int` **DEFAULT:** `6500`                    |
| `zones_per_bulb`      | Physical zones per logical bulb (default 1) **TYPE:** `int` **DEFAULT:** `1`                      |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                           |
| --------------------- | ----------------------------------------------------- |
| `generate_frame`      | Generate a frame of the sonar effect.                 |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.       |
| `is_light_compatible` | Check if light is compatible with Sonar effect.       |
| `inherit_prestate`    | Sonar can inherit prestate from another Sonar effect. |
| `__repr__`            | String representation of Sonar effect.                |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of the sonar effect.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                 |
| ------- | ------------------------------------------- |
| `HSBK`  | White at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with Sonar effect.

Sonar requires multizone capability for zone-based animation.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `bool`  | True if light has multizone support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Sonar can inherit prestate from another Sonar effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                        |
| ------- | -------------------------------------------------- |
| `bool`  | True if other is also EffectSonar, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Sonar effect.

______________________________________________________________________

### EffectSpectrumSweep

#### EffectSpectrumSweep

```python
EffectSpectrumSweep(
    power_on: bool = True,
    speed: float = 6.0,
    waves: float = 1.0,
    brightness: float = 0.8,
    kelvin: int = 3500,
    zones_per_bulb: int = 1,
)
```

Bases: `FrameEffect`

Three-phase sine sweep across zones -- synthetic spectrum analyzer.

Three sine waves at 120-degree phase separation travel along the strip. Each wave's amplitude controls brightness at its hue anchor. Where waves overlap, colors blend through Oklab for perceptually smooth transitions. The result is a smooth, continuously shifting rainbow that wraps and travels.

| ATTRIBUTE        | DESCRIPTION                               |
| ---------------- | ----------------------------------------- |
| `speed`          | Seconds per full sweep cycle              |
| `waves`          | Number of wave periods across the strip   |
| `brightness`     | Peak brightness (0.0-1.0)                 |
| `kelvin`         | Color temperature (1500-9000)             |
| `zones_per_bulb` | Number of physical zones per logical bulb |

Example

```python
effect = EffectSpectrumSweep(speed=6.0, waves=1.0)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER        | DESCRIPTION                                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| `power_on`       | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                             |
| `speed`          | Seconds per full sweep cycle, must be > 0 (default 6.0) **TYPE:** `float` **DEFAULT:** `6.0`            |
| `waves`          | Number of wave periods across the strip, must be > 0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0` |
| `brightness`     | Peak brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                              |
| `kelvin`         | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`                          |
| `zones_per_bulb` | Physical zones per logical bulb (default 1) **TYPE:** `int` **DEFAULT:** `1`                            |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                                      |
| --------------------- | ---------------------------------------------------------------- |
| `generate_frame`      | Generate a frame of the spectrum sweep.                          |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.                  |
| `is_light_compatible` | Check if light is compatible with Spectrum Sweep effect.         |
| `inherit_prestate`    | Spectrum Sweep can inherit prestate from another Spectrum Sweep. |
| `__repr__`            | String representation of Spectrum Sweep effect.                  |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of the spectrum sweep.

For each zone, compute three sine wave amplitudes (120 degrees apart), use them as brightness weights for red, green, blue hue anchors, and blend the dominant two through Oklab interpolation.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                               |
| ------- | ----------------------------------------- |
| `HSBK`  | Red at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with Spectrum Sweep effect.

Spectrum Sweep requires color capability to manipulate hue/saturation.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `bool`  | True if light has color support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Spectrum Sweep can inherit prestate from another Spectrum Sweep.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                                |
| ------- | ---------------------------------------------------------- |
| `bool`  | True if other is also EffectSpectrumSweep, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Spectrum Sweep effect.

______________________________________________________________________

### EffectSpin

#### EffectSpin

```python
EffectSpin(
    power_on: bool = True,
    speed: float = 10.0,
    theme: Theme | None = None,
    bulb_offset: float = 5.0,
    brightness: float = 0.8,
    kelvin: int = 3500,
    zones_per_bulb: int = 1,
)
```

Bases: `FrameEffect`

Cycle theme colors through device zones.

Colors from the theme are spread across the strip and scroll over time. Adjacent zones interpolate smoothly via Oklab, and each zone receives a tiny hue offset (`bulb_offset`) to add visual shimmer.

| ATTRIBUTE        | DESCRIPTION                               |
| ---------------- | ----------------------------------------- |
| `speed`          | Seconds per full color rotation           |
| `theme`          | Theme providing the palette colors        |
| `bulb_offset`    | Per-zone hue shift in degrees for shimmer |
| `brightness`     | Zone brightness 0.0-1.0                   |
| `kelvin`         | Color temperature 1500-9000               |
| `zones_per_bulb` | Physical zones per logical bulb           |

Example

```python
effect = EffectSpin(speed=10.0)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER        | DESCRIPTION                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------------- |
| `power_on`       | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                       |
| `speed`          | Seconds per full color rotation, must be > 0 (default 10.0) **TYPE:** `float` **DEFAULT:** `10.0` |
| `theme`          | Theme providing palette colors (defaults to "exciting") **TYPE:** \`Theme                         |
| `bulb_offset`    | Per-zone hue shift in degrees 0-360 (default 5.0) **TYPE:** `float` **DEFAULT:** `5.0`            |
| `brightness`     | Zone brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                        |
| `kelvin`         | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`                    |
| `zones_per_bulb` | Physical zones per logical bulb (default 1) **TYPE:** `int` **DEFAULT:** `1`                      |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                         |
| --------------------- | --------------------------------------------------- |
| `generate_frame`      | Generate a frame of cycling theme colors.           |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.     |
| `is_light_compatible` | Check if light is compatible with Spin effect.      |
| `inherit_prestate`    | Spin can inherit prestate from another Spin effect. |
| `__repr__`            | String representation of Spin effect.               |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of cycling theme colors.

Each zone's position (0.0-1.0) plus a time offset determines which pair of theme colors it falls between. `HSBK.lerp_oklab` interpolates smoothly between those neighbors. A small hue shift per zone (`bulb_offset`) adds visual shimmer.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

Uses the first theme color at zero brightness for a smooth fade-in.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                          |
| ------- | ------------------------------------ |
| `HSBK`  | First theme color at zero brightness |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with Spin effect.

Spin requires color capability to manipulate hue/saturation.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `bool`  | True if light has color support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Spin can inherit prestate from another Spin effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                       |
| ------- | ------------------------------------------------- |
| `bool`  | True if other is also EffectSpin, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Spin effect.

______________________________________________________________________

### EffectSunrise

#### EffectSunrise

```python
EffectSunrise(
    power_on: bool = True,
    duration: float = 60.0,
    brightness: float = 1.0,
    origin: SunOrigin = "bottom",
)
```

Bases: `FrameEffect`

Sunrise effect transitioning from night to daylight.

Matrix only — simulates a sunrise with a radial expansion from a configurable origin point, progressing through night, dawn, golden hour, morning, and daylight. The sun grows outward from the origin, with nearby pixels transitioning first.

Use `origin="bottom"` (default) for rectangular tiles where the sun rises from the bottom edge, or `origin="center"` for round/oval Ceiling lights where the sun expands from the middle.

| ATTRIBUTE    | DESCRIPTION                                                   |
| ------------ | ------------------------------------------------------------- |
| `brightness` | Peak brightness at full daylight                              |
| `origin`     | Sun origin point ("bottom" or "center") **TYPE:** `SunOrigin` |

Example

```python
# 60-second sunrise from bottom (rectangular tiles)
effect = EffectSunrise(duration=60)
await conductor.start(effect, [matrix_light])

# Sunrise from center (round Ceiling lights)
effect = EffectSunrise(duration=60, origin="center")
await conductor.start(effect, [ceiling_light])
```

| PARAMETER    | DESCRIPTION                                                                                                                                                                                            |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `power_on`   | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                                                                                                                            |
| `duration`   | Effect duration in seconds (default 60.0) **TYPE:** `float` **DEFAULT:** `60.0`                                                                                                                        |
| `brightness` | Peak brightness 0.0-1.0 at full day (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                                                                                                                 |
| `origin`     | Sun origin point — "bottom" for center of bottom row (rectangular tiles) or "center" for middle of canvas (round/oval Ceiling lights). Default "bottom". **TYPE:** `SunOrigin` **DEFAULT:** `'bottom'` |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                        |
| --------------------- | -------------------------------------------------- |
| `generate_frame`      | Generate a frame of sunrise colors.                |
| `from_poweroff_hsbk`  | Return startup color for sunrise (deep navy).      |
| `is_light_compatible` | Check if light is compatible with sunrise effect.  |
| `inherit_prestate`    | Sunrise can inherit prestate from another sunrise. |
| `__repr__`            | String representation of sunrise effect.           |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

###### restore_on_complete

```python
restore_on_complete: bool
```

Skip state restoration so light stays at daylight.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of sunrise colors.

Progress goes from 0 (night) to 1 (day) over the duration.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color for sunrise (deep navy).

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                       |
| ------- | --------------------------------- |
| `HSBK`  | Deep navy blue at zero brightness |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with sunrise effect.

Sunrise requires matrix capability for 2D gradient simulation.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                       |
| ------- | ------------------------------------------------- |
| `bool`  | True if light has matrix support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Sunrise can inherit prestate from another sunrise.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `bool`  | True if other is also EffectSunrise, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of sunrise effect.

______________________________________________________________________

### EffectSunset

#### EffectSunset

```python
EffectSunset(
    power_on: bool = False,
    duration: float = 60.0,
    brightness: float = 1.0,
    power_off: bool = True,
    origin: SunOrigin = "bottom",
)
```

Bases: `FrameEffect`

Sunset effect transitioning from daylight to night.

Matrix only — simulates a sunset with a radial contraction toward a configurable origin point, progressing from daylight through golden hour to night. The sun shrinks inward toward the origin, with distant pixels darkening first. Optionally powers off the light when complete.

Use `origin="bottom"` (default) for rectangular tiles where the sun sets toward the bottom edge, or `origin="center"` for round/oval Ceiling lights where the sun contracts to the middle.

| ATTRIBUTE    | DESCRIPTION                                                   |
| ------------ | ------------------------------------------------------------- |
| `brightness` | Starting brightness at daylight                               |
| `power_off`  | Whether to power off lights after sunset completes            |
| `origin`     | Sun origin point ("bottom" or "center") **TYPE:** `SunOrigin` |

Example

```python
# 60-second sunset that powers off the light
effect = EffectSunset(duration=60, power_off=True)
await conductor.start(effect, [matrix_light])

# Sunset from center (round Ceiling lights)
effect = EffectSunset(duration=60, origin="center")
await conductor.start(effect, [ceiling_light])
```

| PARAMETER    | DESCRIPTION                                                                                                                                                                                            |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `power_on`   | Power on devices if off (default False) **TYPE:** `bool` **DEFAULT:** `False`                                                                                                                          |
| `duration`   | Effect duration in seconds (default 60.0) **TYPE:** `float` **DEFAULT:** `60.0`                                                                                                                        |
| `brightness` | Starting brightness 0.0-1.0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                                                                                                                         |
| `power_off`  | Power off lights when sunset completes (default True) **TYPE:** `bool` **DEFAULT:** `True`                                                                                                             |
| `origin`     | Sun origin point — "bottom" for center of bottom row (rectangular tiles) or "center" for middle of canvas (round/oval Ceiling lights). Default "bottom". **TYPE:** `SunOrigin` **DEFAULT:** `'bottom'` |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                           |
| --------------------- | ----------------------------------------------------- |
| `generate_frame`      | Generate a frame of sunset colors.                    |
| `async_play`          | Run the sunset frame loop, then optionally power off. |
| `from_poweroff_hsbk`  | Return startup color for sunset (warm daylight).      |
| `is_light_compatible` | Check if light is compatible with sunset effect.      |
| `inherit_prestate`    | Sunset can inherit prestate from another sunset.      |
| `__repr__`            | String representation of sunset effect.               |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

###### restore_on_complete

```python
restore_on_complete: bool
```

Skip state restoration when sunset powers off lights.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of sunset colors.

Progress goes from 1 (day) to 0 (night) over the duration.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### async_play

```python
async_play() -> None
```

Run the sunset frame loop, then optionally power off.

Calls the parent frame loop and, if power_off is True, powers off all participant lights after the last frame.

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color for sunset (warm daylight).

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                  |
| ------- | -------------------------------------------- |
| `HSBK`  | Warm daylight color at configured brightness |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with sunset effect.

Sunset requires matrix capability for 2D gradient simulation.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                       |
| ------- | ------------------------------------------------- |
| `bool`  | True if light has matrix support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Sunset can inherit prestate from another sunset.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                         |
| ------- | --------------------------------------------------- |
| `bool`  | True if other is also EffectSunset, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of sunset effect.

______________________________________________________________________

### EffectTwinkle

#### EffectTwinkle

```python
EffectTwinkle(
    power_on: bool = True,
    speed: float = 1.0,
    density: float = 0.05,
    hue: int = 0,
    saturation: float = 0.0,
    brightness: float = 1.0,
    background_hue: int = 0,
    background_saturation: float = 0.0,
    background_brightness: float = 0.0,
    kelvin: int = 3500,
)
```

Bases: `FrameEffect`

Random pixels sparkle and fade like Christmas lights.

Each pixel maintains an independent sparkle timer. When it triggers, the pixel flashes to peak brightness then decays via quadratic falloff (fast flash, slow tail) back to the background color.

| ATTRIBUTE               | DESCRIPTION                                     |
| ----------------------- | ----------------------------------------------- |
| `speed`                 | Sparkle fade duration in seconds                |
| `density`               | Probability a pixel sparks per frame (0.0-1.0)  |
| `hue`                   | Sparkle hue in degrees (0-360)                  |
| `saturation`            | Sparkle saturation (0.0-1.0, 0.0=white sparkle) |
| `brightness`            | Peak sparkle brightness (0.0-1.0)               |
| `background_hue`        | Background hue in degrees (0-360)               |
| `background_saturation` | Background saturation (0.0-1.0)                 |
| `background_brightness` | Background brightness (0.0-1.0)                 |
| `kelvin`                | Color temperature (1500-9000)                   |

Example

```python
# White sparkles on dark background
effect = EffectTwinkle()
await conductor.start(effect, lights)

# Colored sparkles on blue background
effect = EffectTwinkle(
    hue=60,
    saturation=1.0,
    brightness=1.0,
    background_hue=240,
    background_saturation=0.8,
    background_brightness=0.1,
)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER               | DESCRIPTION                                                                                      |
| ----------------------- | ------------------------------------------------------------------------------------------------ |
| `power_on`              | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                      |
| `speed`                 | Sparkle fade duration in seconds, must be > 0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0` |
| `density`               | Per-frame sparkle probability 0.0-1.0 (default 0.05) **TYPE:** `float` **DEFAULT:** `0.05`       |
| `hue`                   | Sparkle hue 0-360 degrees (default 0) **TYPE:** `int` **DEFAULT:** `0`                           |
| `saturation`            | Sparkle saturation 0.0-1.0 (default 0.0, white) **TYPE:** `float` **DEFAULT:** `0.0`             |
| `brightness`            | Peak sparkle brightness 0.0-1.0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`               |
| `background_hue`        | Background hue 0-360 degrees (default 0) **TYPE:** `int` **DEFAULT:** `0`                        |
| `background_saturation` | Background saturation 0.0-1.0 (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`                 |
| `background_brightness` | Background brightness 0.0-1.0 (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`                 |
| `kelvin`                | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`                   |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                               |
| --------------------- | --------------------------------------------------------- |
| `generate_frame`      | Generate a frame of twinkling sparkles.                   |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.           |
| `is_light_compatible` | Check if light is compatible with Twinkle effect.         |
| `inherit_prestate`    | Twinkle can inherit prestate from another Twinkle effect. |
| `__repr__`            | String representation of Twinkle effect.                  |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of twinkling sparkles.

On each frame, every pixel has a random chance of triggering a new sparkle. Active sparkles decay quadratically toward the background color.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                            |
| ------- | ------------------------------------------------------ |
| `HSBK`  | Background color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with Twinkle effect.

Twinkle works with any light that has color capability.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `bool`  | True if light has color support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Twinkle can inherit prestate from another Twinkle effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `bool`  | True if other is also EffectTwinkle, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Twinkle effect.

______________________________________________________________________

### EffectWave

#### EffectWave

```python
EffectWave(
    power_on: bool = True,
    speed: float = 4.0,
    nodes: int = 2,
    hue1: int = 0,
    hue2: int = 240,
    saturation1: float = 1.0,
    saturation2: float = 1.0,
    brightness: float = 0.8,
    drift: float = 0.0,
    kelvin: int = 3500,
    zones_per_bulb: int = 1,
)
```

Bases: `FrameEffect`

Standing wave -- bulbs vibrate between two colors with fixed nodes.

The spatial component `sin(nodes * pi * x / L)` creates fixed zero-crossing points (nodes) along the string. The temporal component `sin(2pi * t / speed)` makes segments between nodes swing back and forth in alternating directions.

| ATTRIBUTE        | DESCRIPTION                                                  |
| ---------------- | ------------------------------------------------------------ |
| `speed`          | Seconds per oscillation cycle                                |
| `nodes`          | Number of stationary nodes along the string                  |
| `hue1`           | Color 1 hue in degrees (0-360, negative displacement)        |
| `hue2`           | Color 2 hue in degrees (0-360, positive displacement)        |
| `saturation1`    | Color 1 saturation (0.0-1.0)                                 |
| `saturation2`    | Color 2 saturation (0.0-1.0)                                 |
| `brightness`     | Overall brightness (0.0-1.0)                                 |
| `drift`          | Spatial drift in degrees per second (0 = pure standing wave) |
| `kelvin`         | Color temperature (1500-9000)                                |
| `zones_per_bulb` | Number of physical zones per logical bulb                    |

Example

```python
effect = EffectWave(speed=4.0, nodes=3, hue1=0, hue2=240)
await conductor.start(effect, lights)

await asyncio.sleep(30)
await conductor.stop(lights)
```

| PARAMETER        | DESCRIPTION                                                                                   |
| ---------------- | --------------------------------------------------------------------------------------------- |
| `power_on`       | Power on devices if off (default True) **TYPE:** `bool` **DEFAULT:** `True`                   |
| `speed`          | Seconds per oscillation cycle, must be > 0 (default 4.0) **TYPE:** `float` **DEFAULT:** `4.0` |
| `nodes`          | Number of stationary nodes, must be >= 1 (default 2) **TYPE:** `int` **DEFAULT:** `2`         |
| `hue1`           | Color 1 hue 0-360 degrees (default 0, red) **TYPE:** `int` **DEFAULT:** `0`                   |
| `hue2`           | Color 2 hue 0-360 degrees (default 240, blue) **TYPE:** `int` **DEFAULT:** `240`              |
| `saturation1`    | Color 1 saturation 0.0-1.0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                 |
| `saturation2`    | Color 2 saturation 0.0-1.0 (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                 |
| `brightness`     | Overall brightness 0.0-1.0 (default 0.8) **TYPE:** `float` **DEFAULT:** `0.8`                 |
| `drift`          | Spatial drift degrees/second (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`               |
| `kelvin`         | Color temperature 1500-9000 (default 3500) **TYPE:** `int` **DEFAULT:** `3500`                |
| `zones_per_bulb` | Physical zones per logical bulb (default 1) **TYPE:** `int` **DEFAULT:** `1`                  |

| RAISES       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `ValueError` | If parameters are out of valid ranges |

| METHOD                | DESCRIPTION                                         |
| --------------------- | --------------------------------------------------- |
| `generate_frame`      | Generate a frame of the standing wave.              |
| `from_poweroff_hsbk`  | Return startup color when light is powered off.     |
| `is_light_compatible` | Check if light is compatible with wave effect.      |
| `inherit_prestate`    | Wave can inherit prestate from another Wave effect. |
| `__repr__`            | String representation of Wave effect.               |

##### Attributes

###### name

```python
name: str
```

Return the name of the effect.

##### Functions

###### generate_frame

```python
generate_frame(ctx: FrameContext) -> list[HSBK]
```

Generate a frame of the standing wave.

Each zone computes a displacement from the product of spatial and temporal sine waves, then maps that to a color blend and brightness level.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `ctx`     | Frame context with timing and layout info **TYPE:** `FrameContext` |

| RETURNS      | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors (length equals ctx.pixel_count) |

###### from_poweroff_hsbk

```python
from_poweroff_hsbk(_light: Light) -> HSBK
```

Return startup color when light is powered off.

| PARAMETER | DESCRIPTION                                            |
| --------- | ------------------------------------------------------ |
| `_light`  | The device being powered on (unused) **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `HSBK`  | Midpoint color at zero brightness for smooth fade-in |

###### is_light_compatible

```python
is_light_compatible(light: Light) -> bool
```

Check if light is compatible with wave effect.

Wave requires color capability to manipulate hue/saturation.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `light`   | The light device to check **TYPE:** `Light` |

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `bool`  | True if light has color support, False otherwise |

###### inherit_prestate

```python
inherit_prestate(other: LIFXEffect) -> bool
```

Wave can inherit prestate from another Wave effect.

| PARAMETER | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `other`   | The incoming effect **TYPE:** `LIFXEffect` |

| RETURNS | DESCRIPTION                                       |
| ------- | ------------------------------------------------- |
| `bool`  | True if other is also EffectWave, False otherwise |

###### __repr__

```python
__repr__() -> str
```

String representation of Wave effect.

______________________________________________________________________

## See Also

- [Getting Started](https://djelibeybi.github.io/lifx-async/getting-started/effects/index.md) - Basic usage and common patterns
- [Custom Effects](https://djelibeybi.github.io/lifx-async/user-guide/effects-custom/index.md) - Creating your own effects
- [Architecture](https://djelibeybi.github.io/lifx-async/architecture/effects-architecture/index.md) - How the system works
- [Troubleshooting](https://djelibeybi.github.io/lifx-async/user-guide/effects-troubleshooting/index.md) - Common issues and solutions
