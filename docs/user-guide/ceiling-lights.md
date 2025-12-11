# Ceiling Lights

LIFX Ceiling lights are unique fixtures that combine two lighting components in one device:

- **Downlight**: Main illumination with multiple addressable zones (63 or 127 zones)
- **Uplight**: Ambient/indirect lighting via a single zone

The `CeilingLight` class provides high-level control over these components while inheriting full matrix functionality from `MatrixLight`.

## Supported Devices

| Product | Zones | Layout |
|---------|-------|--------|
| LIFX Ceiling (US/Intl) | 64 | 8x8 grid, zone 63 = uplight |
| LIFX Ceiling Capsule (US/Intl) | 128 | 16x8 grid, zone 127 = uplight |

## Quick Start

```python
from lifx import CeilingLight
from lifx.color import HSBK

async def main():
    async with await CeilingLight.from_ip("192.168.1.100") as ceiling:
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
from lifx import CeilingLight, CeilingLightState

async with await CeilingLight.from_ip("192.168.1.100") as ceiling:
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

Plus all attributes inherited from `MatrixLightState`: `chain`, `tile_colors`, `tile_count`, `effect`, and from `LightState`: `color`, `power`, `label`, `model`, `serial`, `mac_address`, `capabilities`, etc.

## Zone Layout

Access the component zone indices directly:

```python
async with await CeilingLight.from_ip("192.168.1.100") as ceiling:
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

CeilingLight supports optional state persistence to preserve component colors across sessions:

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

## MatrixLight Compatibility

CeilingLight extends `MatrixLight`, so all matrix operations are available:

```python
async with await CeilingLight.from_ip("192.168.1.100") as ceiling:
    # Use MatrixLight methods directly
    all_colors = await ceiling.get_all_tile_colors()
    tile_chain = await ceiling.get_tile_chain()

    # Set raw matrix colors (bypasses component abstraction)
    await ceiling.set_matrix_colors(0, colors)

    # Apply effects
    from lifx.protocol.protocol_types import TileEffectType
    await ceiling.set_tile_effect(
        effect_type=TileEffectType.MORPH,
        speed=5000,
    )
```

## Example: Night Mode

Create a subtle night light with dim uplight and downlight off:

```python
from lifx import CeilingLight
from lifx.color import HSBK

async def night_mode(ip: str):
    async with await CeilingLight.from_ip(ip) as ceiling:
        # Store current colors before turning off
        await ceiling.turn_downlight_off()

        # Set uplight to very dim warm glow
        await ceiling.set_uplight_color(
            HSBK(hue=30, saturation=0.3, brightness=0.05, kelvin=2200),
            duration=2.0
        )
```

## Example: Daytime Productivity

Bright, cool white for focus:

```python
async def daytime_mode(ip: str):
    async with await CeilingLight.from_ip(ip) as ceiling:
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
    async with await CeilingLight.from_ip(ip) as ceiling:
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

## API Reference

See [CeilingLight API Reference](../api/devices.md#ceiling-light) for complete method documentation.
