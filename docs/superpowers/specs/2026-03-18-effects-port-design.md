# Effects Port Design: pkivolowitz/lifx Effects to lifx-async

## Overview

Port 18 non-audio visual effects from the pkivolowitz/lifx project into lifx-async as `FrameEffect` subclasses, integrating with the existing Conductor, EffectRegistry, and Theme infrastructure.

## Source Project

- Repository: pkivolowitz/lifx (local: `/Volumes/External/Developer/pkivolowitz/lifx/`)
- Effects location: `effects/` directory
- Color utilities: `colorspace.py` (Oklab/CIELAB interpolation)

## Shared Utilities

### Color Interpolation — `HSBK` methods in `src/lifx/color.py`

Add two interpolation methods to the `HSBK` class:

- `lerp_oklab(other: HSBK, blend: float) -> HSBK` — perceptual interpolation via Oklab color space. Produces smooth transitions without muddy intermediates or brightness dips.
- `lerp_hsb(other: HSBK, blend: float) -> HSBK` — simple shortest-path HSB interpolation. Faster but lower quality for large hue jumps.

The Oklab math pipeline (sRGB <-> linear <-> LMS <-> Oklab) lives as private module-level functions in `color.py`. The HSBK methods are the public API.

### Palettes — New entries in `ThemeLibrary`

The pkivolowitz palette presets (aurora, forest, ocean, fire, sunset, van_gogh, monet, klimt, etc.) are added as new themes in `ThemeLibrary._THEMES` in `src/lifx/theme/library.py`. Effects that accept a palette parameter use `Theme` objects.

```python
class EffectSpin(FrameEffect):
    def __init__(self, theme: Theme | None = None, ...):
        self.theme = theme or ThemeLibrary.get("exciting")
```

## Effects List (18 Total)

### Simple Periodic Effects

#### 1. Cylon (Larson Scanner)
- **File:** `src/lifx/effects/cylon.py`
- **Source:** `effects/cylon.py`
- **Algorithm:** Sine-eased position sweeps back and forth; cosine-shaped brightness falloff around the "eye"
- **Params:** `speed`, `width`, `hue`, `brightness`, `background_brightness`, `trail`
- **Device Support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

#### 2. Wave (Standing Wave)
- **File:** `src/lifx/effects/wave.py`
- **Source:** `effects/wave.py`
- **Algorithm:** `sin(nodes*pi*x/L) * sin(2pi*t/speed)` maps to blend factor between two colors
- **Params:** `speed`, `nodes`, `hue1`, `hue2`, `saturation1`, `saturation2`, `brightness`, `drift`
- **Device Support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

#### 3. Sine (Traveling Ease Wave)
- **File:** `src/lifx/effects/sine.py`
- **Source:** `effects/sine.py`
- **Algorithm:** Positive half of sine remapped through smoothstep `3x^2 - 2x^3` for flicker-free brightness humps
- **Params:** `speed`, `wavelength`, `hue`, `brightness`, `floor`, `hue2` (optional gradient)
- **Device Support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

#### 4. Spectrum Sweep
- **File:** `src/lifx/effects/spectrum_sweep.py`
- **Source:** `effects/spectrum_sweep.py`
- **Algorithm:** Three 120-degree-apart sine waves sweep a traveling rainbow, blended via Oklab
- **Params:** `speed`, `waves`, `brightness`
- **Device Support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

#### 5. Pendulum Wave
- **File:** `src/lifx/effects/pendulum_wave.py`
- **Source:** `effects/pendulum_wave.py`
- **Algorithm:** Each zone is a pendulum with linearly varying period. Drifts from traveling waves to chaos to realignment.
- **Params:** `speed`, `cycles`, `hue1`, `hue2`, `brightness`
- **Device Support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

#### 6. Double Slit (Wave Interference)
- **File:** `src/lifx/effects/double_slit.py`
- **Source:** `effects/double_slit.py`
- **Algorithm:** Two-source wave interference. Superposition of sinusoidal point sources creates fringe pattern. Optional wavelength breathing.
- **Params:** `speed`, `wavelength`, `separation`, `breathe`, `hue1`, `hue2`, `brightness`
- **Device Support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

### Sparkle/Pattern Effects

#### 7. Twinkle
- **File:** `src/lifx/effects/twinkle.py`
- **Source:** `effects/twinkle.py`
- **Algorithm:** Per-pixel independent sparkle timers. Random trigger, quadratic brightness decay.
- **Params:** `speed`, `density`, `hue`, `saturation`, `brightness`, `background_hue`, `background_brightness`
- **Device Support:** LIGHT=RECOMMENDED, MULTIZONE=RECOMMENDED, MATRIX=RECOMMENDED

#### 8. Spin (Color Migration)
- **File:** `src/lifx/effects/spin.py`
- **Source:** `effects/spin.py`
- **Algorithm:** Colors from a Theme migrate through zones. Each bulb offset slightly by hue for shimmer.
- **Params:** `speed`, `theme`, `bulb_offset`, `brightness`
- **Device Support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

### Cellular Automata

#### 9. Rule 30 (1D Cellular Automaton)
- **File:** `src/lifx/effects/rule30.py`
- **Source:** `effects/rule30.py`
- **Algorithm:** 1D elementary cellular automaton. 8-bit rule lookup, periodic boundaries.
- **Params:** `speed`, `rule` (0-255, default 30), `hue`, `brightness`, `background_brightness`, `seed` (center/random/all)
- **Device Support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

#### 10. Rule Trio (Three CAs Blended)
- **File:** `src/lifx/effects/rule_trio.py`
- **Source:** `effects/rule_trio.py`
- **Algorithm:** Three independent CAs running at different speeds, blended via Oklab.
- **Params:** `rule_a`, `rule_b`, `rule_c`, `speed`, `drift_b`, `drift_c`, `theme`, `brightness`
- **Device Support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

### Physical Simulations

#### 11. Embers (Fire Simulation)
- **File:** `src/lifx/effects/embers.py`
- **Source:** `effects/embers.py`
- **Algorithm:** Heat diffusion: convection + diffusion + cooling + random turbulence. Color gradient: black to red to orange to yellow.
- **Params:** `intensity`, `cooling`, `turbulence`, `brightness`
- **Stateful:** Heat buffer maintained across frames
- **Device Support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

#### 12. Fireworks
- **File:** `src/lifx/effects/fireworks.py`
- **Source:** `effects/fireworks.py`
- **Algorithm:** Poisson-timed rocket launches with ease-out ascent, gaussian burst bloom, temporal color evolution (white to chemical color to cool orange). Additive RGB blending.
- **Params:** `max_rockets`, `launch_rate`, `ascent_speed`, `burst_spread`, `burst_duration`
- **Stateful:** Active rockets and burst particles tracked across frames
- **Device Support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

#### 13. Plasma (Electric Tendrils)
- **File:** `src/lifx/effects/plasma.py`
- **Source:** `effects/plasma.py`
- **Algorithm:** Pulsing core with random-walk tendrils that fork and crackle.
- **Params:** `speed`, `tendril_rate`, `hue`, `hue_spread`, `brightness`
- **Stateful:** Tendril positions and states tracked across frames
- **Device Support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

#### 14. Ripple (Water Drops)
- **File:** `src/lifx/effects/ripple.py`
- **Source:** `effects/ripple.py`
- **Algorithm:** 1D wave equation with damping. Random drops inject impulses; wavefronts reflect at boundaries.
- **Params:** `speed`, `damping`, `drop_rate`, `hue1`, `hue2`, `brightness`
- **Stateful:** Wave displacement and velocity arrays maintained across frames
- **Device Support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

#### 15. Jacob's Ladder (Electric Arcs)
- **File:** `src/lifx/effects/jacobs_ladder.py`
- **Source:** `effects/jacobs_ladder.py`
- **Algorithm:** Arc pairs drift along strip. Electrode gap modulated by smooth noise. Blue-white electrodes with flickering arc and crackle spikes.
- **Params:** `speed`, `arcs`, `gap`, `brightness`
- **Stateful:** Arc positions and flicker state tracked across frames
- **Device Support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

#### 16. Newton's Cradle (Phong-Shaded Balls)
- **File:** `src/lifx/effects/newtons_cradle.py`
- **Source:** `effects/newtons_cradle.py`
- **Algorithm:** 5 Phong-shaded balls; left/right swing alternately. Full Phong illumination (ambient + diffuse + specular).
- **Params:** `num_balls`, `ball_width`, `speed`, `hue`, `brightness`, `shininess`
- **Device Support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

#### 17. Sonar (Radar Pulses)
- **File:** `src/lifx/effects/sonar.py`
- **Source:** `effects/sonar.py`
- **Algorithm:** Wavefronts emit from sources, reflect off drifting obstacles, absorbed on return. Decaying tails.
- **Params:** `speed`, `decay`, `pulse_interval`, `obstacle_speed`, `brightness`
- **Stateful:** Wavefront positions, obstacle drift, and pulse timing tracked across frames
- **Device Support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

### 2D Matrix

#### 18. Plasma2D
- **File:** `src/lifx/effects/plasma2d.py`
- **Source:** `effects/plasma2d.py`
- **Algorithm:** 2D plasma using layered sine functions across x,y grid, mapped through Oklab color space.
- **Params:** `speed`, `scale`, `hue1`, `hue2`, `brightness`
- **Device Support:** LIGHT=NOT_SUPPORTED, MULTIZONE=NOT_SUPPORTED, MATRIX=RECOMMENDED

## Effect Architecture

### Base Class

All effects subclass `FrameEffect` from `src/lifx/effects/frame_effect.py`:

```python
class EffectCylon(FrameEffect):
    def __init__(self, speed: float = 2.0, width: int = 3, ...):
        super().__init__(power_on=True, fps=20.0, duration=None)
        # Store params, initialize state

    @property
    def name(self) -> str:
        return "cylon"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        # Return list of pixel_count HSBK colors
        ...

    async def from_poweroff_hsbk(self, light: Light) -> HSBK:
        # Color for power-on transition
        ...

    async def is_light_compatible(self, light: Light) -> bool:
        # Check device capabilities
        ...
```

### zones_per_bulb Support

Effects supporting `zones_per_bulb` accept it as a constructor parameter (default 1). Inside `generate_frame`, they compute `bulb_count = ctx.pixel_count // zones_per_bulb` and render to logical bulbs, then expand to fill physical zones.

### Stateful Effects

Stateful effects (Sonar, Embers, Fireworks, Plasma, Ripple, Jacob's Ladder, Rule 30, Rule Trio) store state as instance attributes. State is initialized in `__init__` or lazily on first `generate_frame` call. Frame-to-frame delta is computed from `ctx.elapsed_s`.

### Registry Integration

Each effect registers in `_build_default_registry()` in `src/lifx/effects/registry.py` with appropriate device support levels.

### Module Exports

Each effect class is exported from `src/lifx/effects/__init__.py` and added to `__all__`.

## Testing Strategy

### Test Structure

Each effect gets a test file in `tests/test_effects/` following existing patterns.

### Test Coverage Per Effect

1. **Construction** — default params, custom params, validation errors
2. **Frame generation** — verify output length matches `pixel_count`, all values are valid HSBK
3. **Determinism** — same inputs produce same output (non-stochastic effects)
4. **Edge cases** — `pixel_count=1`, large `pixel_count`, `elapsed_s=0.0`
5. **Name property** — returns expected string
6. **Registry** — effect is registered and discoverable

### Stateful Effect Tests

- Verify state evolves across multiple frames with increasing `elapsed_s`
- Verify output changes over time

### Shared Utility Tests

- `HSBK.lerp_oklab` / `HSBK.lerp_hsb` — endpoints, midpoint, known pairs, symmetry
- New `ThemeLibrary` entries — retrievable, each has >= 3 colors

### Test Files

```
tests/
├── test_color.py                    # lerp_oklab/lerp_hsb tests
├── test_theme.py                    # New palette theme tests
└── test_effects/
    ├── test_cylon.py
    ├── test_twinkle.py
    ├── test_spin.py
    ├── test_embers.py
    ├── test_fireworks.py
    ├── test_plasma.py
    ├── test_ripple.py
    ├── test_jacobs_ladder.py
    ├── test_wave.py
    ├── test_double_slit.py
    ├── test_pendulum_wave.py
    ├── test_newtons_cradle.py
    ├── test_spectrum_sweep.py
    ├── test_rule30.py
    ├── test_rule_trio.py
    ├── test_sine.py
    ├── test_sonar.py
    └── test_plasma2d.py
```

## Future Work

After the initial port, revisit `zones_per_bulb`-capable effects for compatibility with smaller matrix devices (Candle, Path, Spot, Luna) where the 2D grid is small enough that 1D zone-based rendering could work well.

## Implementation Order

### Phase 1: Foundation
1. Add `lerp_oklab` and `lerp_hsb` methods to `HSBK` class
2. Add palette themes to `ThemeLibrary`
3. Tests for both

### Phase 2: Simple Periodic Effects
4. Cylon, Wave, Sine, Spectrum Sweep, Pendulum Wave, Double Slit

### Phase 3: Sparkle/Pattern Effects
5. Twinkle, Spin

### Phase 4: Cellular Automata
6. Rule 30, Rule Trio

### Phase 5: Physical Simulations
7. Embers, Fireworks, Plasma, Ripple, Jacob's Ladder, Newton's Cradle, Sonar

### Phase 6: 2D Matrix
8. Plasma2D

### Phase 7: Integration
9. Registry registration for all effects
10. Module exports
11. Final test pass
