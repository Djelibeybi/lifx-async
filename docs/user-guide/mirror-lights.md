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
update both front and back LEDs. **Zone numbering does not match buffer
order.** Each ring occupies two columns: column 0 holds the front ring's left
half and column 1 its right half, with columns 2 and 3 doing the same for the
back. Row 0 is the top of the fixture and row 12 the bottom, so each column
reads downwards:

```
          col 0    col 1    col 2    col 3
         front L  front R   back L   back R
row  0      9       --        40       --     top centre
row  1      8       10        41       39
row  2      7       11        42       38
row  3      6       12        43       37
row  4      5       13        44       36
row  5      4       14        45       35
row  6      3       15        46       34
row  7      2       16        47       33
row  8      1       17        48       32
row  9      0       18        49       31
row 10     24       19        25       30
row 11     23       20        26       29
row 12     22       21        27       28     bottom centre
```

The two `--` cells carry no LED: the chip at the top centre of each ring sits in
the left column, so the right column starts one row down. That is why the buffer
holds 52 positions but only 50 zones.

Each ring is a single LED strip. The front starts at zone 0 on the lower left,
runs up the left side to zone 9 at the top centre, down the right side to zone
21 at the bottom centre, then back along the lower left through zones 22–24,
ending beside zone 0 with the strip gap between them. The back ring follows the
same path anticlockwise, from zone 25 on the lower left round to zone 49.

`MirrorLight` handles the translation: component methods take and return
colors in zone order, and gather from or scatter to the correct physical
zones. The whole matrix fits in a single `Set64` packet, so any component
write is one packet on the wire, and the unused positions are never touched.

!!! note
    This map was supplied by the LIFX firmware team and has since been verified
    against hardware: the column assignment, the orientation of the rows, the
    left and right halves, the two chipless buffer positions, the bottom split
    and the position of zones 0, 9 and 24 all match the fixture.

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
made in the LIFX app are picked up. A colour change made through an inherited
`MatrixLight` method (`set_matrix_colors()`, `apply_theme()`, a firmware effect
or a waveform) resets this tracking, so the next component call starts from
what the device reports rather than undoing that change. Starting an
`Animator` (which the effects `Conductor` does for every frame effect) resets it
too. Frames sent while an animation runs bypass the component methods
entirely, so a component call made during an animation writes over the
current frame: stop the animation before switching components.

The second write restarts both components' transitions with its own duration.
Concurrent component operations on the same `MirrorLight` instance serialise
their shared state handling, including whole-light `set_color()` and `set_power()`.
They do not wait for fades to finish. Raw matrix writes, Animator frames and
commands from other controllers keep their existing behaviour.

Received tile colours update component colour fields and `last_*` tracking for
the reported zones. Once every zone of a component has been observed, changed
colours outside our pending transition also update restoration colours. A fully
dark component keeps its remembered brightness while adopting changed hue,
saturation and kelvin. In-flight reports during our own fades update observed
colours without replacing the fade target or restoration colours. No polling is
added.

Completed write stages remain reflected in local state if a later stage fails;
errors and cancellation propagate so the caller can decide how to recover.
Timeouts do not prove that the device rejected a write, and tile sends retain
their existing unacknowledged packet behaviour.

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

## Firmware Effects

The Mirror is the only product that runs the COLOR_SWEEP firmware effect,
alongside MORPH and FLAME. With no palette, COLOR_SWEEP sweeps through
colour temperatures, which is intended for checking makeup; with a palette
it sweeps through the palette colours instead. While it runs, `get_effect()`
reports COLOR_SWEEP with the speed and palette sent, but the device keeps
reporting its underlying tile colours from `get_all_tile_colors()`, not the
colours it is actually displaying. See [`MatrixLight.set_effect()`](../api/devices.md#matrix-light)
for details.

To sweep once, as the Mirror's button does, pass `speed=0` with a duration.
The button-started sweep runs once over 30 seconds. Without a duration,
`speed=0` means the 3 second default, because the Mirror would otherwise repeat
the sweep every second or two:

```python
from lifx import FirmwareEffect

await mirror.set_effect(
    FirmwareEffect.COLOR_SWEEP,
    speed=0,
    duration=30_000_000_000,  # nanoseconds
)
```

## Software Effects

A software effect started on the whole Mirror, for example with `Conductor.start()`, draws on
a ring: the effect sees 25 pixels in zone order, and each frame is shown on both the front and
back rings. The frame context's `wraps` flag is `True`, so effects such as Rainbow, Spin, Cylon
and Colorloop run continuously round the ring with no seam. Zone order runs clockwise round the
front ring and anticlockwise round the back ring, both from the lower left as seen from the
front, so the same frame appears to move in opposite directions on the two rings.

```python
from lifx import Conductor, EffectRainbow

conductor = Conductor()
await conductor.start(EffectRainbow(period=10), [mirror])
```

## Whole-Device Operations

`set_power()` and `set_color()` still act on the entire fixture. Both keep the
component caches in sync: `set_power(False)` captures the current front and
back colours first, so a later `turn_front_on()` restores what was showing
before.

## See Also

- [Ceiling Lights](ceiling-lights.md) — the single-zone uplight equivalent
- [Themes](themes.md) — palette definitions and the built-in library
- [Device Classes](../api/devices.md) — full `MirrorLight` API reference
