# Moods: apply_mood() and animate_mood() design

Date: 2026-10-09
Status: draft, awaiting review
Scope: new `src/lifx/theme/mood.py`; new `apply_mood()` and `animate_mood()` on
`Light`, `MultiZoneLight`, `MatrixLight`, the component lights and
`DeviceGroup` (`devices/light.py`, `devices/multizone.py`,
`devices/matrix.py`, `devices/component/light.py`, `api.py`);
`devices/matrix.py` MORPH palette handling; `effects/colorloop.py`; new
`src/lifx/effects/scroll.py`

## Problem

Since 7.9.0 every library theme carries the LIFX app's `static_mode` and
`dynamic_mode`, but nothing renders them. `apply_theme()` paints every theme
as a palette (a random colour on a bulb, a shuffled blend on a strip, an
interpolated gradient across a matrix), so a grid mood such as Van Gogh or
Mondrian never looks like the picture the app shows, and a stripe mood such
as Germany never shows stripes. There is also no one-call way to start the
effect a mood's Dynamic toggle starts in the app.

Home Assistant is the main consumer. It calls `device.apply_theme()` today and
wants a mood to look and feel like the app.

## Goals

1. `apply_mood(theme)`: paint a theme the way the LIFX app paints a mood,
   chosen by `static_mode`.
2. `animate_mood(theme)`: start the effect the app's Dynamic toggle starts,
   with the theme's colours. The effects do the work.
3. `apply_theme()` is untouched.

Both methods take only the theme. Everything else (fade, power, effect choice,
speed, direction) is the app's own value. The bar is "looks and feels like the
app", not pixel identity.

## Decisions

1. Two new methods on every colour light and on `DeviceGroup`:
   `apply_mood(theme)` and `animate_mood(theme)`. No keyword on
   `apply_theme()`, no `Theme.animate()`, no `ThemePainter` class.
2. Neither method takes options. `apply_mood()` copies all of the app's tap
   rules: brightness rescale, the power rule, the 300 ms fade, and restarting
   a running mood effect with the new theme.
3. `animate_mood()` runs `theme.resolved_dynamic_mode`. MOVE paints the mood's
   still first, then starts the effect. MORPH starts from whatever is on the
   light, as the app does.
4. Firmware does the work wherever the light has the effect. Every multizone
   light has firmware MOVE. Matrix lights have firmware MORPH and no MOVE.
5. A matrix light's MOVE is app-driven: the new `EffectScroll` rotates the
   painted rows. The Mirror gets firmware MORPH instead of MOVE, as in the app.
6. Strips have no firmware MORPH, so MORPH on a strip runs firmware MOVE.
7. Bulbs have no firmware effects. Both modes run `EffectColorloop` limited to
   the theme's colours.
8. Mirror and multi-tile chain recipes are unverified until the hardware check
   in section 6 passes; they ship with their best-traced recipe and are listed
   as unverified until then.

## Design

### 1. Renderer (`src/lifx/theme/mood.py`)

Pure functions, no I/O. Each takes colours and a geometry and returns colours.
Every device path and `EffectScroll` render through this module.

- `stretch(colors, n)`: the app's run-weighted fit. Return the list unchanged
  if it already has `n` entries. Otherwise group consecutive equal colours
  into runs, give each run `ceil(n * len(run) / len(colors))` copies of its
  colour, then walk the runs in order removing one copy from the front of each
  non-empty run until exactly `n` remain.
- `rescale(colors, brightness)`: scale so the brightest entry equals
  `brightness`; entries at or above 0.01 stay at least 0.01.
- `gradient(colors, cells)`: `min(cells, len(colors) - 1)` segments, the
  remainder going one extra cell each to the last segments, each filled by
  interpolation with a circular hue mean (a white carries no hue) and hue
  steps clamped to 90 degrees. A straight interpolation is acceptable where
  it looks the same on a diffused light.
- `blended_matrix(colors, width, height)`: a shuffled gradient of
  `2 * (width - 2) + 2 * height` cells laid along the top row left to right,
  down both side edges together (left then right on each middle row), then
  the bottom row from the far end. Each interior cell is the circular mean of
  its five nearest edge cells, each repeated `floor(total distance / its
  distance)` times.
- `grid(colors, width, height)`: `stretch` to `width * height`, rows laid out
  serpentine (even rows left to right, odd rows right to left).
- `stripes(colors, width, height)`: `stretch` to `width`, the same row on
  every row.
- `palette_16(colors)`: the run-weighted reduction to `MAX_PALETTE_COLORS`
  (`stretch` with `n = 16` when there are more than 16 entries), used only on
  the MORPH wire path.

`Canvas` and `lifx.geometry` stay untouched; moods deliberately do not use
`user_x`/`user_y`.

The module is internal: importable, absent from `lifx.theme.__all__` and from
the published API docs, like `Canvas`.

### 2. `apply_mood(theme)`

```python
async def apply_mood(self, theme: Theme) -> None
```

On `Light` (and so every subclass, with overrides where the geometry differs)
and on `DeviceGroup`.

The recipe is chosen by `theme.static_mode`. `None`, and any mode with no
recipe, render as `blended`.

| static_mode | Matrix | Strip | Bulb |
|---|---|---|---|
| `blended` | `blended_matrix` | shuffled `gradient` over the zone count | distinct colours, shuffled, one per light |
| `grid_static` | `grid` | `stretch` to the zone count | as above |
| `solid_static` | `stripes` | `stretch` to the zone count | as above |
| `solid_loop` | `stripes` | `stretch` to the zone count | as above |
| `solid` | `stripes` over the distinct colours, shuffled each call | same, over the zone count | as above |

Device specifics:

- **Ceiling.** The uplight (zone 63) is grid cell (row 7, column 7) on every
  path. It is not special.
- **Tile chain.** One canvas `8 * tile_count` wide and 8 tall, ordered by
  chain index, sliced per tile; `user_x`/`user_y` are ignored, as the app does.
  For `blended` each tile is shuffled and blended on its own. *Unverified.*
- **Mirror.** Best-traced recipe: each ring painted as a 25-zone strip in zone
  order, through the existing component gather and scatter. *Unverified;
  section 6 decides.*
- **Candle (5x6), Luna (7x5).** The matrix recipe over the reported geometry.
  *Unverified; Luna's known mismatch stands.*
- **Bulb.** `DeviceGroup.apply_mood()` deals the theme's distinct colours,
  shuffled, one per bulb in turn. A lone `Light.apply_mood()` takes the
  first colour of a shuffle.

The app's tap rules, all fixed:

- **Brightness.** Read each light's current brightness and `rescale` to it.
- **Power.** Power on only when every targeted light is off.
  `DeviceGroup` checks all its lights; a single light checks itself.
- **Fade.** 300 ms.
- **Restart.** If a mood effect is running on the light, call
  `animate_mood()` with the new theme instead of painting. A mood effect is
  firmware MORPH on a matrix light, firmware MOVE on a strip, or
  `EffectScroll` or the palette Colour Loop on the light's Conductor. It is
  read from the device and the Conductor, not remembered, so the rule
  survives a process restart.

### 3. `animate_mood(theme)`

```python
async def animate_mood(self, theme: Theme) -> None
```

On the same classes as `apply_mood()`. It runs `theme.resolved_dynamic_mode`
at the app's own speed and direction. Stopping is the existing
`stop_effect()`.

| Light | MOVE | MORPH |
|---|---|---|
| Strip (any multizone) | mood still, then firmware MOVE, FORWARD, `20 s * zones / 16` | same as MOVE |
| Matrix (Ceiling, Tile, chain, Candle, Luna) | mood still, then `EffectScroll` | firmware MORPH, 3 s, no pre-paint |
| Mirror | firmware MORPH | firmware MORPH |
| Bulb | `EffectColorloop(palette=theme.colors)` | same |

The strip path paints with `apply_mood()` then sends the raw
`set_effect(MultiZoneEffect)`, which never paints. `set_move_effect()` is not
used, because with no palette it may repaint a single-colour strip with a
derived palette.

`DeviceGroup.animate_mood()` runs one Colour Loop across all its bulbs, so
`spread` offsets each bulb's starting colour; every other light runs its own
path.

### 4. Effects

- **MORPH palettes over 16 colours.** `MatrixLight.set_effect(MORPH,
  palette=...)` accepts any non-empty palette. More than 16 colours are reduced
  with `palette_16` and the result is shuffled; selection is deterministic,
  only the order is random. Today a palette over 16 raises `ValueError`; this
  is the one behaviour change to an existing API. Other effect types keep the
  16-colour limit, and `validate_effect_palette()` is unchanged for them.
- **`EffectScroll`** (new, registry name `"scroll"`). Matrix lights only.
  Every 1250 ms it rotates every row one cell toward higher column numbers and
  writes one Set64 per tile with the step as the fade (capped at 2 s). It
  rotates whatever is painted and paints nothing itself. It streams no frames,
  so like `EffectColorloop` it runs on Thread lights without `enable_thread`.
  A strip or bulb participant is rejected. The step is the effect's own,
  matching the app; the frame-paced 1500/fps transition of other frame effects
  is not changed.
- **`EffectColorloop(palette=...)`** (new keyword, default `None`). With a
  palette, each step moves to the next palette colour instead of turning the
  hue, and `spread` offsets each light's starting index. With no palette,
  behaviour is unchanged.

### 5. Errors

- A non-colour light ignores both methods, as `apply_theme()` does today.
- An empty `DeviceGroup` does nothing.

### 6. Hardware verification

Before the Mirror and chain recipes are called verified:

1. Trace the Mirror paint path and its MOVE-to-MORPH substitution in the 4.100
   app.
2. Side by side, app against this recipe, on the Mirror and on both product
   55 Tiles on the operator's network, for one mood of each `static_mode`.
   The probe reads each Tile's chain length rather than assuming it.
3. The probe script stays local and is never committed. Every write is
   snapshotted and restored. Committed evidence carries only pseudonymised
   identifiers.

If the hardware disagrees, the recipe changes before release.

### 7. Testing

- **Renderer.** Unit tests on small hand-built palettes for every function:
  run counts and trimming in `stretch`, the 0.01 floor in `rescale`, segment
  allocation in `gradient`, edge order in `blended_matrix`, serpentine rows in
  `grid`, repeated rows in `stripes`. Nothing pinned to live catalogue data.
- **apply_mood().** Emulator tests per device kind and `static_mode`, a lone
  bulb and a `DeviceGroup` of bulbs, the power rule, the 300 ms fade,
  brightness rescale and the restart rule. Chains use the `tile_chain_light`
  fixture, because the emulator's Tile has one tile.
- **animate_mood().** Each row of the table in section 3, including Mirror's
  substitution and the strip MORPH-to-MOVE path.
- **Effects.** MORPH reduction of a 64-entry grid to 16; `EffectScroll`'s
  step and rejection of non-matrix participants; Colour Loop with a palette.
- **apply_theme().** Existing tests pass unchanged.
- **Coverage.** 100% branch patch coverage.
