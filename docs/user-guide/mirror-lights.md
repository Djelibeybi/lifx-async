# LIFX Mirror

The LIFX Mirror is a capsule-shaped Matrix device that exposes three light
entities:

- **Front LEDs**: Zones facing the room, for task lighting
- **Back LEDs**: Zones facing the wall, for indirect backwash lighting
- **Mirror LEDs**: All zones, facing the front and rear of the room

Unlike [Ceiling lights](ceiling-lights.md), whose uplight is a single zone,
**both Mirror components span multiple zones**, so each one can carry its own
gradient, theme, or software effect. Firmware effects run across both sets
of LEDs by default.

The `MirrorLight` class provides high-level control over these components while
inheriting full matrix functionality from `MatrixLight`.

## Supported Devices

| Product | Matrix | Zones | Layout |
|---------|--------|-------|--------|
| LIFX Mirror (US/Intl) | 4×13 | 50 | Front ring zones 0–24, back ring zones 25–49 |

The fixture is a 36×22 capsule, intended to be hung in portrait orientation
by default. Each component is a closed ring tracing the perimeter, so its
first and last zones are physically adjacent.

The two rings run in opposite directions: viewed in the default
portrait orientation, the front ring starts at the lower left and runs
clockwise, while the back ring starts at the lower left and runs anticlockwise.
Three Matter-enabled buttons sit just above the bottom half-circle endpoint,
between front zones 21 and 22. The fourth button controls the power for the
anti-fog endpoints.

### Zone Map

The device is driven as a 4×13 matrix, so a single Set64 packet is sufficient to
update both front and back LEDs. **Zone numbering does not match zone
order.** Columns 0–1 carry the front ring and columns 2–3 carry the back ring,
each running bottom to top:

```
  9  --  40  --
  8  10  41  39
  7  11  42  38
  6  12  43  37
  5  13  44  36
  4  14  45  35
  3  15  46  34
  2  16  47  33
  1  17  48  32
  0  18  49  31
 24  19  25  30
 23  20  26  29
 22  21  27  28
```

`MirrorLight` handles the translation: component methods take and return
colors in zone order, and gather from or scatter to the correct physical
zones. The whole matrix fits in a single `Set64` packet, so any component
write is one packet on the wire, and the unused positions are never touched.

!!! note
    The zone map comes from the LIFX firmware team and has not yet been
    verified against hardware.

## Quick Start

```python
from lifx import MirrorLight
from lifx.color import HSBK

async def main():
    async with await MirrorLight.from_ip("192.168.1.100") as mirror:
        # Bright task light on the front
        await mirror.set_front_colors(
            HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=4500)
        )

        # Warm backwash behind
        await mirror.set_back_colors(
            HSBK(hue=30, saturation=0.4, brightness=0.3, kelvin=2700)
        )
```

## Component Control

Each component accepts either a single color, applied to every zone, or one
color per zone:

```python
# Single color across the whole front ring
await mirror.set_front_colors(HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=4500))

# A gradient around the back ring (25 colors)
gradient = [
    HSBK(hue=i * 360 / 25, saturation=1.0, brightness=0.5, kelvin=3500)
    for i in range(25)
]
await mirror.set_back_colors(gradient, duration=2.0)
```

Reading works the same way:

```python
front_colors = await mirror.get_front_colors()  # 25 colors, in zone order
back_colors = await mirror.get_back_colors()    # 25 colors, in zone order
```

The buffer positions behind each component are available if you need to address
the matrix directly:

```python
mirror.front_positions   # Buffer positions of zones 0-24, in zone order
mirror.back_positions    # Buffer positions of zones 25-49, in zone order
mirror.front_zone_count  # 25
mirror.back_zone_count   # 25
mirror.layout.width, mirror.layout.height  # (4, 13) — zones across, down
```

## Turning Components On and Off

Turning a component off zeroes its brightness while preserving hue, saturation
and kelvin, so the colors can be restored later:

```python
await mirror.turn_back_off()   # Front stays lit
await mirror.turn_back_on()    # Restores the stored colors
```

If the whole light is off, `turn_front_on()` and `turn_back_on()` set the target
zone colors instantly while the light is dark, then fade the power up over the
given `duration`, so the light fades in to the new colors instead of flashing
to its previous state. The other component is left dark.

When no colour is supplied, brightness is determined in this order:

1. Stored colours from a previous turn-off, if any zone was lit
2. The average brightness of the other component
3. A default of 0.8

Turning off the last lit component powers the whole device off, rather than
leaving it on with every zone at zero brightness. The component's zones keep
their brightness on the device, so a plain `set_power(True)` brings it back:

```python
await mirror.turn_back_off()
await mirror.turn_front_off(duration=1.0)  # Last lit component: power fades off
await mirror.set_power(True)               # Front comes back on
```

### Switching Between Components

Both components live on one matrix, and the firmware runs one transition per
matrix: any new write stops a fade that is still running, even in zones it does
not touch. `MirrorLight` works around this so that calls made back to back
behave:

```python
# The front fades out while the back fades in, both over one second
await mirror.turn_front_off(duration=1.0)
await mirror.turn_back_on(duration=1.0)
```

While a fade is still running, each component write carries the other
component's *target* colors rather than the half-faded ones the device
reports, so both finish where they were headed. The same applies to power: the
device keeps reporting its old power level for a moment after a change, so a
turn-on straight after the last component was turned off still powers the
light back up. Once the fade has finished, the device is read again, so changes
made in the LIFX app are picked up.

This is best effort. The second write restarts both components' transitions
with its own duration, and running component calls concurrently on one device
(for example with `asyncio.gather()`) is not supported: await each call in
turn.

## Per-Component Themes

Because both components are multi-zone, each can hold a different theme:

```python
from lifx.theme import get_theme

await mirror.apply_front_theme(get_theme("evening"), power_on=True)
await mirror.apply_back_theme(get_theme("galaxy"), duration=2.0)
```

The theme is rendered over the full 4×13 matrix using the matrix generator —
the same Canvas splotch rendering every other matrix device gets — and then the
component's zones are picked out of the result. The other component keeps
whatever it was showing.

## State Persistence

Like `CeilingLight`, `MirrorLight` accepts a `state_file` so stored component
colours survive a restart:

```python
async with await MirrorLight.from_ip(
    "192.168.1.100", state_file="~/.lifx/mirror.json"
) as mirror:
    await mirror.turn_back_off()
# Stored colours are written on exit
```

The file is keyed by device serial and written atomically, so several devices
can share one file.

## Whole-Device Operations

`set_power()` and `set_color()` still act on the entire fixture. Both keep the
component caches in sync: `set_power(False)` captures the current front and
back colours first, so a later `turn_front_on()` restores what was showing
before.

## See Also

- [Ceiling Lights](ceiling-lights.md) — the single-zone uplight equivalent
- [Themes](themes.md) — palette definitions and the built-in library
- [Device Classes](../api/devices.md) — full `MirrorLight` API reference
