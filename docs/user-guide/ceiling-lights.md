# Ceiling Lights

LIFX Ceiling lights are unique fixtures that combine two lighting components in one device:

- **Downlight**: Main illumination with multiple addressable zones (63 or 127 zones)
- **Uplight**: Ambient/indirect lighting via a single zone

The `CeilingLight` class provides high-level control over these components while inheriting full matrix functionality from `MatrixLight`.

## Supported Devices

| Product | Zones | Layout |
|---------|-------|--------|
| LIFX Ceiling (US/Intl) | 64 | 8x8 grid, zone 63 = uplight |
| LIFX Ceiling 13x26 (US/Intl) | 128 | 16x8 grid, zone 127 = uplight |
| LIFX Ceiling 13" (US/Intl) | 64 | 8x8 grid, zone 63 = uplight |

All LIFX Ceiling devices are gen4, so the first command after a period of idle may
arrive with a short wake-up delay — see
[Gen4 Power-Save Wake Tail](troubleshooting.md#gen4-power-save-wake-tail) for details.

## Quick Start

```python
from lifx import CeilingLight, Device
from lifx.color import HSBK

async def main():
    async with await Device.connect("192.168.1.100") as ceiling:
        assert isinstance(ceiling, CeilingLight)
        # Set downlight to warm white
        await ceiling.set_downlight_colors(
            HSBK(hue=0, saturation=0, brightness=1.0, kelvin=3000)
        )

        # Set uplight to a dim, warm ambient glow
        await ceiling.set_uplight_color(
            HSBK(hue=30, saturation=0.2, brightness=0.3, kelvin=2700)
        )
```

## Component Control

### Setting Colors

#### Downlight

Set all downlight zones to the same color:

```python
# Single color for all zones
await ceiling.set_downlight_colors(
    HSBK(hue=0, saturation=0, brightness=0.8, kelvin=4000)
)
```

Or set each zone individually:

```python
# Create a gradient across all zones
zone_count = len(range(*ceiling.downlight_zones.indices(256)))
colors = [
    HSBK(hue=(i * 360 / zone_count), saturation=1.0, brightness=0.5, kelvin=3500)
    for i in range(zone_count)
]
await ceiling.set_downlight_colors(colors)
```

#### Uplight

```python
await ceiling.set_uplight_color(
    HSBK(hue=30, saturation=0.1, brightness=0.4, kelvin=2700)
)
```

### Reading Current Colors

```python
# Get current uplight color
uplight_color = await ceiling.get_uplight_color()
print(f"Uplight: H={uplight_color.hue}, B={uplight_color.brightness}")

# Get all downlight colors
downlight_colors = await ceiling.get_downlight_colors()
print(f"Downlight zones: {len(downlight_colors)}")
```

### Turning Components On/Off

The `turn_*_on()` and `turn_*_off()` methods provide smart state management:

```python
# Turn off uplight (stores current color for later restoration)
await ceiling.turn_uplight_off()

# Turn uplight back on (restores previous color)
await ceiling.turn_uplight_on()

# Turn on with a specific color
await ceiling.turn_uplight_on(
    color=HSBK(hue=0, saturation=0, brightness=1.0, kelvin=3500)
)
```

The same pattern works for downlights:

```python
# Turn off downlight
await ceiling.turn_downlight_off()

# Turn downlight back on
await ceiling.turn_downlight_on()

# Turn on with specific colors
await ceiling.turn_downlight_on(
    colors=HSBK(hue=0, saturation=0, brightness=0.8, kelvin=4000)
)
```

Turning off the last lit component powers the whole device off, rather than
leaving it on with every zone at zero brightness:

```python
await ceiling.turn_uplight_off()

# The uplight is now off, so turning the downlight off — the last lit
# component — powers the device off entirely
await ceiling.turn_downlight_off()

assert await ceiling.get_power() == 0
```

Pass a `duration` and it is applied to the power transition, so the light still
fades out. `get_power()` reads the device directly, and the device keeps
reporting the light as on until the fade has finished, so only expect `0` once
it has.

The component's zones keep their brightness on the device rather than being
zeroed, so a plain power-on brings that component back:

```python
await ceiling.set_power(True)  # Downlight comes back on
```

Both component colours also remain stored, so `turn_uplight_on()` and
`turn_downlight_on()` restore them as usual. Use those rather than
`set_uplight_color()` / `set_downlight_colors()` when the device may be off:
the setters change zone colours only and never power the device on.

### Checking Component State

```python
# Check if components are on
if ceiling.uplight_is_on:
    print("Uplight is on")

if ceiling.downlight_is_on:
    print("Downlight is on")
```

!!! note "State Properties Require Recent Data"
    The `uplight_is_on` and `downlight_is_on` properties rely on cached data.
    Call `get_uplight_color()` or `get_downlight_colors()` first to ensure
    accurate state.

## Device State

After connecting to a CeilingLight, you can access the complete device state via the `state` property, which returns a `CeilingLightState` dataclass:

```python
from lifx import CeilingLight, CeilingLightState, Device

async with await Device.connect("192.168.1.100") as ceiling:
    assert isinstance(ceiling, CeilingLight)
    state: CeilingLightState = ceiling.state

    # Access ceiling-specific state
    print(f"Uplight color: {state.uplight_color}")
    print(f"Uplight is on: {state.uplight_is_on}")
    print(f"Downlight zones: {len(state.downlight_colors)}")
    print(f"Downlight is on: {state.downlight_is_on}")

    # Access inherited state from MatrixLightState/LightState
    print(f"Device label: {state.label}")
    print(f"Power: {'on' if state.power else 'off'}")
    print(f"Model: {state.model}")
```

### CeilingLightState Attributes

`CeilingLightState` extends `MatrixLightState` with ceiling-specific attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `uplight_color` | `HSBK` | Current color of the uplight component |
| `downlight_colors` | `list[HSBK]` | Colors for each downlight zone (63 or 127) |
| `uplight_is_on` | `bool` | True if uplight brightness > 0 |
| `downlight_is_on` | `bool` | True if any downlight zone brightness > 0 |
| `uplight_zone` | `int` | Zone index for uplight (63 or 127) |
| `downlight_zones` | `slice` | Slice for downlight zones |

Plus all attributes inherited from `MatrixLightState`: `chain`, `tile_orientations`, `tile_colors`, `tile_count`, `effect`, and from `LightState`: `color`, `power`, `label`, `model`, `serial`, `mac_address`, `capabilities`, etc.

## Zone Layout

Access the component zone indices directly:

```python
async with await Device.connect("192.168.1.100") as ceiling:
    assert isinstance(ceiling, CeilingLight)
    # Get uplight zone index (63 or 127 depending on model)
    uplight_idx = ceiling.uplight_zone
    print(f"Uplight zone: {uplight_idx}")

    # Get downlight zones as a slice
    downlight_slice = ceiling.downlight_zones
    print(f"Downlight zones: {downlight_slice}")  # slice(0, 63) or slice(0, 127)

    # Calculate number of downlight zones
    zone_count = len(range(*downlight_slice.indices(256)))
    print(f"Number of downlight zones: {zone_count}")
```

## State Persistence

CeilingLight supports optional state persistence to preserve component colors across sessions.
The state file is set through `CeilingLight.from_ip()`, which is the one case where naming the
class directly is required — `Device.connect()` has no `state_file` parameter:

```python
async with await CeilingLight.from_ip(
    "192.168.1.100",
    state_file="~/.lifx/ceiling_state.json"
) as ceiling:
    # Colors are automatically loaded from file on connection
    # and saved when using turn_*_off() methods

    await ceiling.turn_uplight_off()  # Saves current color to file
    # ... later ...
    await ceiling.turn_uplight_on()   # Restores from file if available
```

All state file reads and writes run in a worker thread, so they never block the
event loop — safe to use inside an async application such as Home Assistant.
Saving is a read-merge-write cycle serialised per file, so several devices in
the same process can share one state file without dropping each other's
entries. That lock is process-local: point two separate processes at one state
file and the later write will drop the earlier process's entries.

The state file stores colors per device serial number, supporting multiple devices:

```json
{
  "d073d5123456": {
    "uplight": {
      "hue": 30.0,
      "saturation": 0.2,
      "brightness": 0.4,
      "kelvin": 2700
    },
    "downlight": [
      {"hue": 0.0, "saturation": 0.0, "brightness": 0.8, "kelvin": 4000}
    ]
  }
}
```

## Brightness Determination

When calling `turn_uplight_on()` or `turn_downlight_on()` without a color parameter, CeilingLight uses the following priority to determine brightness:

1. **Stored state**: If a color was previously saved (via `turn_*_off()` or `set_*_color()`)
2. **Infer from other component**: Average brightness of the other component
3. **Default**: 80% brightness

This ensures a reasonable brightness level even when no state is available.

Received tile colours update the component colour fields and `last_*` tracking
without requiring a full `refresh_state()`. Partial responses update only the
zones they report. Restoration colours are reconciled once all zones of that
component have been observed; a Ceiling 13x26 downlight requires two responses.
Outside this instance's pending transition, changed lit colours become the new
restoration colours. If the whole component is dark, its remembered brightness
is retained while externally changed hue, saturation and kelvin are adopted.
Intermediate reports during our own fade update observed colours without
discarding the fade target or restoration colours. This adds no polling.

## Transition Duration

All color-setting methods support smooth transitions:

```python
# 2-second transition to new color
await ceiling.set_uplight_color(
    HSBK(hue=0, saturation=0, brightness=1.0, kelvin=3500),
    duration=2.0  # seconds
)

# Instant change (default)
await ceiling.set_downlight_colors(
    HSBK(hue=240, saturation=1.0, brightness=0.5, kelvin=3500),
    duration=0.0
)
```

### Switching Between Components

The uplight and downlight live on one matrix, and the firmware runs one
transition per matrix: any new write stops a fade that is still running, even
in zones it does not touch. `CeilingLight` works around this so that calls made
back to back behave:

```python
# The downlight fades out while the uplight fades in, both over one second
await ceiling.turn_downlight_off(duration=1.0)
await ceiling.turn_uplight_on(duration=1.0)
```

While a fade is still running, each component write carries the other
component's *target* colors rather than the half-faded ones the device
reports, so both finish where they were headed. The same applies to power: the
device keeps reporting its old power level for a moment after a change, so a
turn-on straight after the last component was turned off still powers the
light back up. Once the fade has finished, the device is read again, so changes
made in the LIFX app are picked up. A colour change made through an inherited
`MatrixLight` method (`set_matrix_colors()`, `apply_theme()`, a firmware effect
or a waveform) resets this tracking, so the next component call starts from
what the device reports rather than undoing that change. Starting an
`Animator` (which the effects `Conductor` does for every frame effect) resets it
too. Frames you send directly through the light's `Animator` bypass the
component methods entirely, so a component call made while they run writes over
the current frame: stop sending them before switching components. Software
effects need no such care. A component call made during a whole-light software
effect moves the effect onto the other light component, and while a software
effect runs on one light component, the other light component's methods keep
working (see [Effects on one light component](#effects-on-one-light-component)).

The second write restarts both components' transitions with its own duration.
Concurrent component operations on the same `CeilingLight` instance serialise
their shared state handling, including whole-light `set_color()` and `set_power()`.
They do not wait for fades to finish. This does not schedule raw matrix writes,
Animator frames or commands from other controllers.

If a later write fails, completed stages remain reflected in local state and the
exception propagates. A timeout can mean a command was applied but its reply was
lost; it is not a rollback. The caller decides whether to continue, retry or read
the device. Tile sends retain their existing unacknowledged packet behaviour.

## MatrixLight Compatibility

CeilingLight extends `MatrixLight`, so all matrix operations are available:

```python
async with await Device.connect("192.168.1.100") as ceiling:
    assert isinstance(ceiling, CeilingLight)
    # Use MatrixLight methods directly
    all_colors = await ceiling.get_all_tile_colors()
    device_chain = await ceiling.get_device_chain()

    # Set raw matrix colors (bypasses component abstraction)
    await ceiling.set_matrix_colors(0, colors)

    # Apply effects
    from lifx.protocol.protocol_types import FirmwareEffect
    await ceiling.set_effect(
        effect_type=FirmwareEffect.MORPH,
        speed=5.0,  # seconds
    )
```

## Example: Night Mode

Create a subtle night light with dim uplight and downlight off:

```python
from lifx import CeilingLight, Device
from lifx.color import HSBK

async def night_mode(ip: str):
    async with await Device.connect(ip) as ceiling:
        assert isinstance(ceiling, CeilingLight)
        # Store current colors before turning off. If the uplight is already
        # off this powers the whole device down, so bring the uplight back
        # with turn_uplight_on() rather than set_uplight_color(), which
        # changes zone colours without powering the device on.
        await ceiling.turn_downlight_off()

        # Set uplight to very dim warm glow
        await ceiling.turn_uplight_on(
            color=HSBK(hue=30, saturation=0.3, brightness=0.05, kelvin=2200),
            duration=2.0
        )
```

## Example: Daytime Productivity

Bright, cool white for focus:

```python
async def daytime_mode(ip: str):
    async with await Device.connect(ip) as ceiling:
        assert isinstance(ceiling, CeilingLight)
        # Bright cool downlight for task lighting
        await ceiling.set_downlight_colors(
            HSBK(hue=0, saturation=0, brightness=1.0, kelvin=5500),
            duration=1.0
        )

        # Turn off uplight during the day
        await ceiling.turn_uplight_off(duration=1.0)
```

## Example: Evening Ambiance

Warm tones with accent uplight:

```python
async def evening_mode(ip: str):
    async with await Device.connect(ip) as ceiling:
        assert isinstance(ceiling, CeilingLight)
        # Dimmed warm downlight
        await ceiling.set_downlight_colors(
            HSBK(hue=30, saturation=0.1, brightness=0.4, kelvin=2700),
            duration=2.0
        )

        # Colorful uplight accent
        await ceiling.set_uplight_color(
            HSBK(hue=280, saturation=0.6, brightness=0.3, kelvin=3500),
            duration=2.0
        )
```

## Effects on One Light Component

`ceiling.uplight` and `ceiling.downlight` are light components that can each be
an effect participant. They carry `start_effect()`, `stop_effect()` and
`animator`, and nothing else: colours and power stay on the methods above.

```python
from lifx.effects import EffectFlicker

async with await Device.connect("192.0.2.10") as ceiling:
    await ceiling.downlight.start_effect(EffectFlicker())

    # The uplight is not animating, so its methods work as usual
    await ceiling.set_uplight_color(HSBK(hue=30, saturation=0.2, brightness=0.3, kelvin=2700))
    await ceiling.turn_uplight_off(duration=2.0)

    await asyncio.sleep(10)
    await ceiling.downlight.stop_effect()
```

A software effect on the downlight draws on the full grid, 16x8 on a Ceiling
13x26 or 8x8 on the others, and the uplight cell of each frame is dropped. On
the uplight it draws on a single pixel. Any effect that draws frames can run on
either light component, whether or not it suits the shape; an effect that draws
no frames, such as `EffectPulse`, cannot.

The light component with no effect keeps its colours. Its colour and power
methods change what it shows on the next frame, fades included, and later
frames do not overwrite the change. Calling the animating light component's
own colour or power methods stops its effect first, with no restore in
between, and then applies the change; if it was one participant of a larger
run, only it leaves and the others carry on. Light components also take part
in a `Conductor` run like whole lights:
`await conductor.start(effect, [ceiling.uplight])`.

Starting an effect on a light component of a light that is off turns on only
that light component, at its stored colours or a brightness inferred from the
other light component, which stays dark. Stopping it returns the light
component to its colours from before the effect, or turns it off again if it
was dark or the light was off, which powers the light off when the other light
component is dark too. The other light component is left as it is, even while
its own effect runs, and stored colours are those from before the effect.

Both light components draw through the light's one `Animator`
(`ceiling.animator`): each light component is a slot on it, and every frame
sends one tile composed from both slots. `ceiling.stop_effect()` stops the
effects on both light components as well as any whole-light effect.

### Whole-Light and Light Component Effects Together

The newest instruction wins, and nothing is restored in between:

- A whole-light effect started while effects run on the light components
  replaces them. Stopping it restores what was there before any of those
  effects started: each light component's colours, the light's power and the
  stored colours.
- A light component effect started while a whole-light effect runs moves the
  whole-light effect onto the other light component, where it carries on with
  the same parameters. Stopping a light component's effect, or calling its
  colour or power methods, during a whole-light effect does the same.
- The moved effect stays on its light component, even after the other light
  component's effect stops, and stopping it restores that light component's
  colours from before the whole-light effect started, not a frame of it.

A moved effect keeps the canvas it started with: it goes on drawing the full
grid, and only its light component's cells reach the light. On the uplight
that is the uplight cell, so an effect such as a rainbow shows the colour of that
one cell rather than restarting on a single pixel.

```python
from lifx.effects import EffectAurora, EffectFlicker

await ceiling.start_effect(EffectAurora())
# Aurora moves onto the uplight; Flicker draws on the downlight
await ceiling.downlight.start_effect(EffectFlicker())
```

An effect that draws no frames, such as `EffectPulse`, cannot move onto a light
component: a light component effect started during it takes the light from it,
and a light component's colour or power call leaves it running.

## Sunrise and Sunset Effects

LIFX Ceiling lights have a round or oval shape, making them ideal candidates for the sunrise and sunset effects with the `origin="center"` setting. This makes the sun expand outward from the center of the light rather than rising from the bottom edge.

```python
from lifx import CeilingLight, Device
from lifx.effects import Conductor, EffectSunrise, EffectSunset

async def wake_up_light(ip: str):
    """Simulate a sunrise on a Ceiling light."""
    async with await Device.connect(ip) as ceiling:
        assert isinstance(ceiling, CeilingLight)
        conductor = Conductor()

        # 30-minute sunrise expanding from the center
        effect = EffectSunrise(
            duration=1800,
            brightness=1.0,
            origin="center"
        )
        await conductor.start(effect, [ceiling])
        # Effect completes automatically — light stays at daylight


async def goodnight_light(ip: str):
    """Simulate a sunset on a Ceiling light, then power off."""
    async with await Device.connect(ip) as ceiling:
        assert isinstance(ceiling, CeilingLight)
        conductor = Conductor()

        # 30-minute sunset contracting to center, then off
        effect = EffectSunset(
            power_on=True,
            duration=1800,
            brightness=1.0,
            power_off=True,
            origin="center"
        )
        await conductor.start(effect, [ceiling])
        # Effect completes automatically — light powers off
```

The `origin` parameter accepts two values:

- `"bottom"` (default): Center of the bottom row — designed for rectangular tile arrays
- `"center"`: Middle of the canvas — designed for round/oval Ceiling lights

!!! tip "Choosing the right origin"
    For **LIFX Ceiling** and **LIFX Ceiling 13x26** devices, always use `origin="center"` for the most natural-looking sunrise and sunset transitions.

## API Reference

See [CeilingLight API Reference](../api/devices.md#ceiling-light) for complete method documentation.
