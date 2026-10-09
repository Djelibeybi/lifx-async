# Moods: apply_mood() and animate_mood() design

Date: 2026-10-09
Status: draft, awaiting review
Scope: restructure `src/lifx/theme/` into a `generators` package (new
`generators/mood.py`); new `apply_mood()` and `animate_mood()` on `Light`,
`MultiZoneLight`, `MatrixLight`, the component lights and `DeviceGroup`
(`devices/light.py`, `devices/multizone.py`, `devices/matrix.py`,
`devices/component/light.py`, `api.py`); `devices/matrix.py` MORPH palette
handling; `effects/colorloop.py`; new `src/lifx/effects/scroll.py`

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
5. A matrix light's MOVE is app-driven: the new `EffectScroll` moves the
   painted image. The Mirror gets firmware MORPH instead of MOVE, as in the
   app. Spot and Path (171, 173, 174, 221, 222) also get firmware MORPH: the
   app runs an undocumented firmware COLOR_CYCLE there, which this library
   does not send. Both sets live in `lifx/products/quirks.py`.
6. Strips have no firmware MORPH, so MORPH on a strip runs firmware MOVE.
7. Bulbs have no firmware effects. Both modes run `EffectColorloop` limited to
   the theme's colours.
8. The Mirror, Tube and Tile chain recipes were checked against the 4.100 app
   on hardware (section 6) and match it.

## Design

### 0. Restructure (a pure move, landed first)

`src/lifx/theme/` gains a `generators` package:

| Today | After |
|---|---|
| `theme/generators.py` | `theme/generators/theme.py` |
| `theme/canvas.py` | `theme/generators/canvas.py` |
| (new) | `theme/generators/mood.py` |

`generators/__init__.py` re-exports `SingleZoneGenerator`,
`MultiZoneGenerator` and `MatrixGenerator`, so `lifx.theme.generators` and
`lifx.theme` imports keep working, and `from lifx.theme import Canvas` keeps
its current unadvertised re-export. The `lifx.theme.canvas` path goes away;
`Canvas` is internal, so that needs no major version. Every in-repo reference
(`geometry.py`, `schema.py`, devices, tests, `docs/architecture/overview.md`)
moves in the same commit. No behaviour changes, and the existing suite passes
untouched apart from import paths.

### 1. Renderer: `MoodGenerator` (`generators/mood.py`)

A generator class shaped like its siblings, no I/O, exported from
`lifx.theme` beside them. Public methods:

- `MoodGenerator(theme)`: the recipe comes from `theme.static_mode`; `None`
  and any mode with no recipe use `blended`.
- `get_matrix_colors(width, height, brightness, *, vertical=False) ->
  list[HSBK]`: one matrix device: every `has_matrix` light except a
  multi-tile Tile chain. Today that is Ceiling (every size), Candle, Spot,
  Path, Tube, Luna, Mirror and a single Tile. `vertical` turns the stripe
  modes into bands along the long axis (section 2).
- `get_chain_colors(tile_count, width, height, brightness) ->
  list[list[HSBK]]`: a Tile chain, one canvas in chain order, sliced per tile.
- `get_multizone_colors(zone_count, brightness) -> list[HSBK]`: a strip.
- `get_bulb_colors(count) -> list[HSBK]`: the distinct colours, shuffled,
  dealt one per bulb.
- `morph_palette(colors) -> list[HSBK]` (static): the app's run-weighted
  reduction to `MAX_PALETTE_COLORS` for the MORPH wire path; unchanged when
  there are 16 or fewer. Selection is deterministic.

Private methods, the recipe steps:

- `_stretch(colors, n)`: the app's run-weighted fit. Return the list unchanged
  if it already has `n` entries. Otherwise group consecutive equal colours
  into runs, give each run `ceil(n * len(run) / len(colors))` copies of its
  colour, then walk the runs in order removing one copy from the front of each
  non-empty run until exactly `n` remain.
- `_rescale(colors, brightness)`: scale so the brightest entry equals
  `brightness`; entries at or above 0.01 stay at least 0.01.
- `_gradient(colors, cells)`: `min(cells, len(colors) - 1)` segments, the
  remainder going one extra cell each to the last segments, each filled by
  interpolation with a circular hue mean (a white carries no hue) and hue
  steps clamped to 90 degrees. A straight interpolation is acceptable where
  it looks the same on a diffused light.
- `_blended_matrix(colors, width, height)`: a shuffled gradient of
  `2 * (width - 2) + 2 * height` cells laid along the top row left to right,
  down both side edges together (left then right on each middle row), then
  the bottom row from the far end. Each interior cell is the circular mean of
  its five nearest edge cells, each repeated `floor(total distance / its
  distance)` times.
- `_grid(colors, width, height)`: `_stretch` to `width * height`, rows laid
  out serpentine (even rows left to right, odd rows right to left).
- `_stripes(colors, width, height)`: `_stretch` to `width`, the same row on
  every row.

Moods do not go through `MatrixGenerator` or `Canvas`, because the app's
recipes differ from the interpolated gradient those build. Tile positions
only matter on a multi-tile Tile chain, the one device with more than one
tile; there a mood follows chain order, as the app does (section 2).

New public API: `apply_mood()`, `animate_mood()`, `MoodGenerator` (its public
methods only), `EffectScroll` (with `frame=`) and
`EffectColorloop(palette=...)`.

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
| `blended` | `_blended_matrix` | shuffled `_gradient` over the zone count | distinct colours, shuffled, one per light |
| `grid_static` | `_grid` | `_stretch` to the zone count | as above |
| `solid_static` | `_stripes` | `_stretch` to the zone count | as above |
| `solid_loop` | `_stripes` | `_stretch` to the zone count | as above |
| `solid` | `_stripes` over the distinct colours, shuffled each call | same, over the zone count | as above |

Device specifics:

- **Ceiling.** The uplight (zone 63) is grid cell (row 7, column 7) on every
  path. It is not special.
- **Tile chain.** One canvas `8 * tile_count` wide and 8 tall, ordered by
  chain index, sliced per tile. This is the app's behaviour and is chosen
  deliberately: tiles arranged in an L or a stack show the image in chain
  order, not following their physical arrangement.
  For `blended` each tile is shuffled and blended on its own. A tile whose
  accelerometer reports a rotation (left, right or upside down) is remapped,
  as the app does; a tile reporting FaceUp or FaceDown is not.
  *Verified against the app on two Tile chains.*
- **Mirror.** The app has no Mirror-specific paint path: it paints the Mirror
  as any other single matrix light, over its 4x13 Set64 buffer, with one
  shuffle and one brightness rescale for the whole light. The front and back
  rings play no part. The app reads the buffer as 16 rows (64 colours / 4)
  and may fit stripe moods to 16; this library uses the real 13 rows.
  *Traced in the 4.100 app and verified on hardware; the 13-row bands match
  the app.*
- **Vertical-theme products.** The app gives every Candle, the Tube and the
  Mirror a vertical-theme capability that is not in the products registry:
  product ids 57, 68, 137, 138, 185, 186, 215, 216, 217, 218, 267 and 268,
  kept as a hand-maintained set in `lifx/products/quirks.py`. On these, the
  stripe modes (`solid`, `solid_static`, `solid_loop`) run along the long
  axis: the colours are stretched to the row count, every row is one colour,
  and the first colour is on the bottom row. `blended` and `grid_static`
  ignore the flag. *Verified against the app on a Tube and a Mirror.*
- **Candle, Spot, Path, Tube, Luna and the 13x26 Ceiling.** The matrix
  recipe over the geometry the device reports, never an assumed 8x8.
  *Tube verified; Candle, Spot, Path, Luna and the 13x26 Ceiling not checked
  on hardware. Luna's known mismatch stands.*
- **Bulb.** `DeviceGroup.apply_mood()` deals the theme's distinct colours,
  shuffled, one per bulb in turn. A lone `Light.apply_mood()` takes the
  first colour of a shuffle.

The app's tap rules, all fixed:

- **Brightness.** Read each light's current brightness and `_rescale` to it.
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
| Matrix (every `has_matrix` light but the Mirror, chains included) | mood still, then `EffectScroll(frame=<that still>)` | firmware MORPH, 3 s, no pre-paint |
| Mirror, Spot, Path | firmware MORPH | firmware MORPH |
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
  with `MoodGenerator.morph_palette()` and the result is shuffled; selection
  is deterministic,
  only the order is random. Today a palette over 16 raises `ValueError`; this
  is the one behaviour change to an existing API. Other effect types keep the
  16-colour limit, and `validate_effect_palette()` is unchanged for them.
- **`EffectScroll`** (new, registry name `"scroll"`). Matrix lights only.
  Every 1250 ms it moves the image one cell and writes one Set64 per tile
  with the step as the fade (capped at 2 s). On a vertical-theme light (every
  Candle, the Tube) it moves whole rows one row toward higher row numbers,
  down the light, the last row wrapping to the top; on every other matrix
  light it rotates every row one cell toward higher column numbers. The
  vertical scroll was observed on a Tube against the app: 5x11, effect OFF
  (app-driven), one row per ~1.25 s, fading for most of each step. It writes one Set64 per tile with the step as the fade (capped at 2 s). It
  paints nothing itself. Its optional `frame=` keyword takes the per-tile
  colours to scroll; `animate_mood()` passes the `get_matrix_colors()` or
  `get_chain_colors()` output it has just painted, so nothing is read back.
  Without `frame=`, it reads the tiles once when it starts. Readback is the
  fallback only: Get64 trails a Set64 by roughly 130 to 225 ms and reports
  in-flight colours during a fade, which the emulator does not reproduce.
  It streams no frames, so like `EffectColorloop` it runs on Thread lights
  without `enable_thread`.
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
  run counts and trimming in `_stretch`, the 0.01 floor in `_rescale`,
  segment allocation in `_gradient`, edge order in `_blended_matrix`,
  serpentine rows in `_grid`, repeated rows in `_stripes`, and
  `morph_palette()`. Private steps are tested through the public methods
  where that pins the behaviour, directly where it does not. Nothing is
  pinned to live catalogue data.
- **apply_mood().** Emulator tests per device kind and `static_mode`, a lone
  bulb and a `DeviceGroup` of bulbs, the power rule, the 300 ms fade,
  brightness rescale and the restart rule. Chains use the `tile_chain_light`
  fixture, because the emulator's Tile has one tile.
- **animate_mood().** Each row of the table in section 3, including Mirror's
  substitution and the strip MORPH-to-MOVE path.
- **Restructure.** The existing suite passes with only import paths changed.
- **Effects.** MORPH reduction of a 64-entry grid to 16; `EffectScroll`'s
  step, its `frame=` path, its readback fallback and rejection of non-matrix
  participants; Colour Loop with a palette.
- **apply_theme().** Existing tests pass unchanged.
- **Coverage.** 100% branch patch coverage.
