# Effects Port Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port 18 non-audio visual effects from pkivolowitz/lifx into lifx-async as `FrameEffect` subclasses.

**Architecture:** Each effect is a `FrameEffect` subclass implementing `generate_frame(ctx) -> list[HSBK]`. Foundation utilities (Oklab interpolation on HSBK, palette themes in ThemeLibrary) are built first. Effects register in `EffectRegistry` and export from `effects/__init__.py`.

**Tech Stack:** Python 3.11+, asyncio, pytest, lifx-async `FrameEffect`/`Conductor`/`EffectRegistry`

**Spec:** `.claude/superpowers/specs/2026-03-18-effects-port-design.md`

**Source effects directory:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/`

**Source colorspace module:** `/Volumes/External/Developer/pkivolowitz/lifx/colorspace.py`

---

## File Map

### Foundation (must complete before effects)

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/lifx/color.py` | Add `lerp_oklab()`, `lerp_hsb()` methods + private Oklab pipeline functions |
| Modify | `src/lifx/theme/library.py` | Add palette themes from pkivolowitz palettes |
| Modify | `tests/test_color.py` | Add lerp tests |
| Modify | `tests/test_theme.py` | Add palette theme tests |

### Effects (independent of each other, depend on foundation)

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/lifx/effects/cylon.py` | Larson scanner effect |
| Create | `src/lifx/effects/wave.py` | Standing wave effect |
| Create | `src/lifx/effects/sine.py` | Traveling ease wave effect |
| Create | `src/lifx/effects/spectrum_sweep.py` | Three-phase rainbow sweep |
| Create | `src/lifx/effects/pendulum_wave.py` | Phase-drifting pendulums |
| Create | `src/lifx/effects/double_slit.py` | Wave interference effect |
| Create | `src/lifx/effects/twinkle.py` | Random sparkle effect |
| Create | `src/lifx/effects/spin.py` | Color migration through zones |
| Create | `src/lifx/effects/rule30.py` | 1D cellular automaton |
| Create | `src/lifx/effects/rule_trio.py` | Three CAs blended |
| Create | `src/lifx/effects/embers.py` | Heat diffusion fire |
| Create | `src/lifx/effects/fireworks.py` | Rocket bursts |
| Create | `src/lifx/effects/plasma.py` | Electric tendrils |
| Create | `src/lifx/effects/ripple.py` | Water drop waves |
| Create | `src/lifx/effects/jacobs_ladder.py` | Rising electric arcs |
| Create | `src/lifx/effects/newtons_cradle.py` | Phong-shaded pendulum balls |
| Create | `src/lifx/effects/sonar.py` | Radar pulses with obstacles |
| Create | `src/lifx/effects/plasma2d.py` | 2D plasma for matrix devices |
| Create | `tests/test_effects/test_cylon.py` | Cylon tests |
| Create | `tests/test_effects/test_wave.py` | Wave tests |
| Create | `tests/test_effects/test_sine.py` | Sine tests |
| Create | `tests/test_effects/test_spectrum_sweep.py` | Spectrum sweep tests |
| Create | `tests/test_effects/test_pendulum_wave.py` | Pendulum wave tests |
| Create | `tests/test_effects/test_double_slit.py` | Double slit tests |
| Create | `tests/test_effects/test_twinkle.py` | Twinkle tests |
| Create | `tests/test_effects/test_spin.py` | Spin tests |
| Create | `tests/test_effects/test_rule30.py` | Rule 30 tests |
| Create | `tests/test_effects/test_rule_trio.py` | Rule trio tests |
| Create | `tests/test_effects/test_embers.py` | Embers tests |
| Create | `tests/test_effects/test_fireworks.py` | Fireworks tests |
| Create | `tests/test_effects/test_plasma.py` | Plasma tests |
| Create | `tests/test_effects/test_ripple.py` | Ripple tests |
| Create | `tests/test_effects/test_jacobs_ladder.py` | Jacob's ladder tests |
| Create | `tests/test_effects/test_newtons_cradle.py` | Newton's cradle tests |
| Create | `tests/test_effects/test_sonar.py` | Sonar tests |
| Create | `tests/test_effects/test_plasma2d.py` | Plasma2D tests |

### Integration (after all effects complete)

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/lifx/effects/registry.py` | Register all 18 effects |
| Modify | `src/lifx/effects/__init__.py` | Export all 18 effect classes |
| Modify | `tests/test_effects/test_registry.py` | Test all effects are registered |

---

## Task 1: HSBK Color Interpolation (Foundation)

**Files:**
- Modify: `src/lifx/color.py`
- Modify: `tests/test_color.py`

**Source reference:** `/Volumes/External/Developer/pkivolowitz/lifx/colorspace.py` — port the Oklab pipeline functions, adapted to work with HSBK's user-friendly ranges (hue 0-360, sat/bri 0.0-1.0) instead of uint16 tuples.

- [ ] **Step 1: Write failing tests for `lerp_hsb`**

Add to `tests/test_color.py`:

```python
class TestHSBKLerpHsb:
    """Tests for HSBK.lerp_hsb()."""

    def test_blend_zero_returns_self(self) -> None:
        """blend=0.0 returns the start color."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)
        result = red.lerp_hsb(blue, 0.0)
        assert result.hue == red.hue
        assert result.saturation == red.saturation
        assert result.brightness == red.brightness
        assert result.kelvin == red.kelvin

    def test_blend_one_returns_other(self) -> None:
        """blend=1.0 returns the end color."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)
        result = red.lerp_hsb(blue, 1.0)
        assert result.hue == blue.hue
        assert result.saturation == blue.saturation
        assert result.brightness == blue.brightness

    def test_midpoint_blends_saturation_and_brightness(self) -> None:
        """blend=0.5 averages saturation and brightness."""
        c1 = HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=3500)
        c2 = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        result = c1.lerp_hsb(c2, 0.5)
        assert abs(result.saturation - 0.5) < 0.02
        assert abs(result.brightness - 0.5) < 0.02

    def test_shortest_path_hue_wraps(self) -> None:
        """Hue interpolation takes shortest path around the wheel."""
        c1 = HSBK(hue=350, saturation=1.0, brightness=1.0, kelvin=3500)
        c2 = HSBK(hue=10, saturation=1.0, brightness=1.0, kelvin=3500)
        result = c1.lerp_hsb(c2, 0.5)
        # Midpoint of 350->10 via shortest path is 0 (wraps via % 360)
        assert result.hue == 0

    def test_preserves_kelvin_from_self(self) -> None:
        """Kelvin is always taken from self (start color)."""
        c1 = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=2500)
        c2 = HSBK(hue=180, saturation=1.0, brightness=1.0, kelvin=6500)
        result = c1.lerp_hsb(c2, 0.5)
        assert result.kelvin == 2500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_color.py::TestHSBKLerpHsb -v`
Expected: FAIL — `HSBK` has no `lerp_hsb` attribute

- [ ] **Step 3: Write failing tests for `lerp_oklab`**

Add to `tests/test_color.py`:

```python
class TestHSBKLerpOklab:
    """Tests for HSBK.lerp_oklab()."""

    def test_blend_zero_returns_self(self) -> None:
        """blend=0.0 returns the start color."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)
        result = red.lerp_oklab(blue, 0.0)
        assert abs(result.hue - red.hue) <= 1
        assert abs(result.saturation - red.saturation) < 0.02
        assert abs(result.brightness - red.brightness) < 0.02

    def test_blend_one_returns_other(self) -> None:
        """blend=1.0 returns the end color."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)
        result = red.lerp_oklab(blue, 1.0)
        assert abs(result.hue - blue.hue) <= 1
        assert abs(result.brightness - blue.brightness) < 0.02

    def test_midpoint_maintains_brightness(self) -> None:
        """Oklab midpoint should maintain perceived brightness better than HSB."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
        result = red.lerp_oklab(green, 0.5)
        # Oklab maintains brightness — should not dip below 0.5
        assert result.brightness >= 0.5

    def test_preserves_kelvin_from_self(self) -> None:
        """Kelvin is always taken from self (start color)."""
        c1 = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=2500)
        c2 = HSBK(hue=180, saturation=1.0, brightness=1.0, kelvin=6500)
        result = c1.lerp_oklab(c2, 0.5)
        assert result.kelvin == 2500

    def test_black_to_color(self) -> None:
        """Interpolating from black to color should work."""
        black = HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=3500)
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        result = black.lerp_oklab(red, 0.5)
        assert 0.0 < result.brightness < 1.0
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_color.py::TestHSBKLerpOklab -v`
Expected: FAIL — `HSBK` has no `lerp_oklab` attribute

- [ ] **Step 5: Implement Oklab pipeline and lerp methods**

Add private Oklab functions to `src/lifx/color.py` (before the `HSBK` class), ported from `/Volumes/External/Developer/pkivolowitz/lifx/colorspace.py`. The key pipeline is:

1. `_srgb_to_linear(c)` / `_linear_to_srgb(c)` — sRGB gamma
2. `_srgb_to_oklab(r, g, b)` / `_oklab_to_srgb(L, a, b)` — via LMS cone responses + M1/M2 matrices
3. `_hsv_to_srgb(h, s, v)` / `_srgb_to_hsv(r, g, b)` — standard HSV conversion

Then add methods to `HSBK`:

```python
def lerp_hsb(self, other: HSBK, blend: float) -> HSBK:
    """Interpolate to another color via shortest-path HSB blending.

    Fast but can produce muddy intermediates for large hue jumps.

    Args:
        other: Target color
        blend: 0.0 (self) to 1.0 (other)

    Returns:
        Interpolated HSBK color. Kelvin is taken from self.
    """
    # Shortest-path hue interpolation
    diff = other._hue - self._hue
    if diff > 180:
        diff -= 360
    elif diff < -180:
        diff += 360
    hue = round(self._hue + diff * blend) % 360

    sat = self._saturation + (other._saturation - self._saturation) * blend
    bri = self._brightness + (other._brightness - self._brightness) * blend

    return HSBK(hue=hue, saturation=round(sat, 2), brightness=round(bri, 2), kelvin=self._kelvin)

def lerp_oklab(self, other: HSBK, blend: float) -> HSBK:
    """Interpolate to another color through Oklab perceptual color space.

    Produces smooth transitions without muddy intermediates or brightness
    dips, even for large hue jumps. More expensive than lerp_hsb.

    Args:
        other: Target color
        blend: 0.0 (self) to 1.0 (other)

    Returns:
        Interpolated HSBK color. Kelvin is taken from self.
    """
    # Convert both to sRGB via HSV
    r1, g1, b1 = _hsv_to_srgb(self._hue / 360.0, self._saturation, self._brightness)
    r2, g2, b2 = _hsv_to_srgb(other._hue / 360.0, other._saturation, other._brightness)

    # Convert to Oklab
    L1, a1, ob1 = _srgb_to_oklab(r1, g1, b1)
    L2, a2, ob2 = _srgb_to_oklab(r2, g2, b2)

    # Linear interpolation in Oklab space
    L = L1 + (L2 - L1) * blend
    a = a1 + (a2 - a1) * blend
    ob = ob1 + (ob2 - ob1) * blend

    # Convert back to sRGB then HSV
    r, g, b = _oklab_to_srgb(L, a, ob)
    h, s, v = _srgb_to_hsv(r, g, b)

    return HSBK(
        hue=round(h * 360) % 360,
        saturation=round(s, 2),
        brightness=round(v, 2),
        kelvin=self._kelvin,
    )
```

Port the Oklab matrix constants and conversion functions from the source `colorspace.py`. For the HSV↔sRGB step, use `colorsys.hsv_to_rgb` / `colorsys.rgb_to_hsv` (already imported in `color.py`) as the private `_hsv_to_srgb` / `_srgb_to_hsv` implementations — these are just thin wrappers.

- [ ] **Step 6: Run all lerp tests**

Run: `uv run pytest tests/test_color.py::TestHSBKLerpHsb tests/test_color.py::TestHSBKLerpOklab -v`
Expected: ALL PASS

- [ ] **Step 7: Run full test suite to verify no regressions**

Run: `uv run pytest tests/test_color.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/lifx/color.py tests/test_color.py
git commit -s -m "feat(color): add lerp_oklab and lerp_hsb methods to HSBK

Oklab interpolation produces perceptually uniform color transitions
without brightness dips or muddy intermediates. HSB interpolation
provides a fast fallback using shortest-path hue blending."
```

---

## Task 2: Palette Themes (Foundation)

**Files:**
- Modify: `src/lifx/theme/library.py`
- Modify: `tests/test_theme.py`

**Source reference:** The palette definitions in `/Volumes/External/Developer/pkivolowitz/lifx/effects/rule_trio.py` (search for `PALETTES: dict`). Each palette is a tuple of `(hue_a, hue_b, hue_c, saturation)` where hues are in degrees 0-360 and saturation is 0-100. Convert to HSBK with brightness=1.0 and kelvin=3500.

- [ ] **Step 1: Write failing tests for new palette themes**

Add to `tests/test_theme.py`:

```python
class TestPaletteThemes:
    """Tests for palette themes ported from pkivolowitz/lifx."""

    PALETTE_NAMES = [
        "fire", "water", "forest", "earth", "neon",
        "aurora_borealis", "tropical", "arctic", "galaxy",
        "deep_sea", "coral_reef", "desert",
        "vaporwave", "cyberpunk", "cherry_blossom",
    ]

    @pytest.mark.parametrize("name", PALETTE_NAMES)
    def test_palette_theme_exists(self, name: str) -> None:
        """Each palette theme should be retrievable."""
        theme = ThemeLibrary.get(name)
        assert theme is not None

    @pytest.mark.parametrize("name", PALETTE_NAMES)
    def test_palette_theme_has_colors(self, name: str) -> None:
        """Each palette theme should have at least 3 colors."""
        theme = ThemeLibrary.get(name)
        assert len(theme) >= 3

    @pytest.mark.parametrize("name", PALETTE_NAMES)
    def test_palette_theme_colors_are_valid_hsbk(self, name: str) -> None:
        """Each color in a palette theme should be a valid HSBK."""
        theme = ThemeLibrary.get(name)
        for color in theme:
            assert isinstance(color, HSBK)
            assert 0 <= color.hue <= 360
            assert 0.0 <= color.saturation <= 1.0
            assert 0.0 <= color.brightness <= 1.0
            assert 1500 <= color.kelvin <= 9000

    def test_palette_names_dont_collide_with_existing(self) -> None:
        """Palette names should not collide with existing themes."""
        all_names = ThemeLibrary.list()
        # Just verify no duplicates in the list
        assert len(all_names) == len(set(all_names))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_theme.py::TestPaletteThemes -v`
Expected: FAIL — `KeyError: Theme 'fire' not found`

- [ ] **Step 3: Add palette themes to ThemeLibrary**

Add new entries to `ThemeLibrary._THEMES` in `src/lifx/theme/library.py`. Read the palettes from `/Volumes/External/Developer/pkivolowitz/lifx/effects/rule_trio.py` (the `PALETTES` dict, line 130). Convert each `(hue_a, hue_b, hue_c, saturation)` tuple to 3 HSBK colors: `HSBK(hue=round(hue_x), saturation=sat/100, brightness=1.0, kelvin=3500)`.

Use disambiguated names where collisions exist with existing ThemeLibrary entries (e.g., "autumn" and "halloween" already exist — skip those). Use underscores for multi-word names (e.g., "deep sea" → "deep_sea", "coral reef" → "coral_reef"). The exact names listed in the test should be used.

- [ ] **Step 4: Run palette theme tests**

Run: `uv run pytest tests/test_theme.py::TestPaletteThemes -v`
Expected: ALL PASS

- [ ] **Step 5: Run full theme test suite**

Run: `uv run pytest tests/test_theme.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/lifx/theme/library.py tests/test_theme.py
git commit -s -m "feat(theme): add palette themes from pkivolowitz/lifx

Adds palette themes from pkivolowitz/lifx (fire, water, forest, earth,
neon, aurora_borealis, tropical, arctic, galaxy, etc.) for use with
effects like Spin and Rule Trio."
```

---

## Tasks 3-20: Individual Effects

Each effect task follows the same pattern. Tasks 3-20 are **independent of each other** (all depend only on Tasks 1-2) and can be executed in parallel by subagents.

### Common Pattern for All Effect Tasks

Every effect task has these steps:

1. **Read the source effect** at `/Volumes/External/Developer/pkivolowitz/lifx/effects/<name>.py`
2. **Write failing tests** following the pattern from `tests/test_effects/test_flame.py`:
   - Test default parameters and name property
   - Test custom parameters
   - Test parameter validation (ValueError for out-of-range)
   - Test `generate_frame()` returns correct length for various pixel counts
   - Test output values are valid HSBK (hue 0-360, sat/bri 0.0-1.0, kelvin 1500-9000)
   - Test frames change over time (different `elapsed_s` → different output)
   - Test pixels vary across strip (not all identical) for multizone effects
   - Test `from_poweroff_hsbk()` returns appropriate dim color
   - Test `is_light_compatible()` returns True for color-capable lights
   - Test `inherit_prestate()` returns True for same class
   - Test edge cases: `pixel_count=1`, large `pixel_count` (82), `elapsed_s=0.0`
   - For deterministic effects: same `elapsed_s` + same params = same output
   - For stateful effects: test state evolves across multiple frames
3. **Run tests to verify they fail**
4. **Implement the effect** as a `FrameEffect` subclass adapting the source algorithm:
   - Port the `render(t, zone_count)` logic into `generate_frame(ctx: FrameContext)`
   - Replace `t` → `ctx.elapsed_s`, `zone_count` → `ctx.pixel_count`
   - Replace uint16 HSBK tuples → user-friendly `HSBK` objects
   - Replace `hue_to_u16()` / `pct_to_u16()` → direct HSBK constructor
   - Replace `lerp_color()` → `HSBK.lerp_oklab()`
   - Add parameter validation in `__init__`
   - Implement `from_poweroff_hsbk`, `is_light_compatible`, `inherit_prestate`
5. **Run tests to verify they pass**
6. **Run `uv run ruff check . --fix && uv run ruff format .`**
7. **Run `uv run pyright`** to check types
8. **Commit** with `git commit -s`

### Task 3: Cylon Effect

**Files:**
- Create: `src/lifx/effects/cylon.py`
- Create: `tests/test_effects/test_cylon.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/cylon.py`

**Key algorithm:** Sine-eased position sweeps back and forth across the strip. A cosine-shaped brightness falloff creates the "eye" profile. Trail factor controls decay behind the eye.

**Constructor:** `EffectCylon(speed=2.0, width=3, hue=0, brightness=0.8, background_brightness=0.0, trail=0.5, kelvin=3500, zones_per_bulb=1)`

**Device support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

Follow the common pattern above. Port the source `render()` method into `generate_frame()`.

---

### Task 4: Wave Effect

**Files:**
- Create: `src/lifx/effects/wave.py`
- Create: `tests/test_effects/test_wave.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/wave.py`

**Key algorithm:** Standing wave: `sin(nodes*pi*x/L) * sin(2*pi*t/speed)` maps to blend factor between two colors via `HSBK.lerp_oklab()`. Optional spatial drift adds traveling wave component.

**Constructor:** `EffectWave(speed=4.0, nodes=2, hue1=0, hue2=240, saturation1=1.0, saturation2=1.0, brightness=0.8, drift=0.0, kelvin=3500, zones_per_bulb=1)`

**Device support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 5: Sine Effect

**Files:**
- Create: `src/lifx/effects/sine.py`
- Create: `tests/test_effects/test_sine.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/sine.py`

**Key algorithm:** Traveling wave where positive half-cycle is remapped through smoothstep `3x²-2x³` for flicker-free brightness humps. Negative half-cycle shows floor brightness. Optional second hue creates gradient along the wave via `HSBK.lerp_oklab()`.

**Constructor:** `EffectSine(speed=4.0, wavelength=0.5, hue=200, saturation=1.0, brightness=0.8, floor=0.02, hue2=None, kelvin=3500, zones_per_bulb=1, reverse=False)`

**Device support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 6: Spectrum Sweep Effect

**Files:**
- Create: `src/lifx/effects/spectrum_sweep.py`
- Create: `tests/test_effects/test_spectrum_sweep.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/spectrum_sweep.py`

**Key algorithm:** Three sine waves 120° apart sweep along the strip. Each wave controls the brightness of its respective primary color (R/G/B). Improvement over source: use `HSBK.lerp_oklab()` for smooth color blending between the three phases.

**Constructor:** `EffectSpectrumSweep(speed=6.0, waves=1.0, brightness=0.8, kelvin=3500, zones_per_bulb=1)`

**Device support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 7: Pendulum Wave Effect

**Files:**
- Create: `src/lifx/effects/pendulum_wave.py`
- Create: `tests/test_effects/test_pendulum_wave.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/pendulum_wave.py`

**Key algorithm:** Each zone is a pendulum with a linearly varying period. Zone 0 has the most oscillations per cycle, last zone has the fewest. The displacement maps to blend factor between two colors. The system drifts from traveling waves → standing waves → chaos → perfect realignment after one `speed` cycle.

**Constructor:** `EffectPendulumWave(speed=30.0, cycles=8, hue1=0, hue2=240, saturation1=1.0, saturation2=1.0, brightness=0.8, kelvin=3500, zones_per_bulb=1)`

**Device support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 8: Double Slit Effect

**Files:**
- Create: `src/lifx/effects/double_slit.py`
- Create: `tests/test_effects/test_double_slit.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/double_slit.py`

**Key algorithm:** Two point sources emit sinusoidal waves; superposition creates constructive/destructive interference. The amplitude at each zone maps to blend factor between two colors. Optional `breathe` parameter slowly modulates the wavelength, shifting the fringe pattern.

**Constructor:** `EffectDoubleSlit(speed=4.0, wavelength=0.3, separation=0.2, breathe=0.0, hue1=0, hue2=240, saturation=1.0, brightness=0.8, kelvin=3500, zones_per_bulb=1)`

**Device support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 9: Twinkle Effect

**Files:**
- Create: `src/lifx/effects/twinkle.py`
- Create: `tests/test_effects/test_twinkle.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/twinkle.py`

**Key algorithm:** Each pixel has an independent sparkle timer. Per frame, each non-sparkling pixel has a `density` chance of triggering. Active sparkles decay via quadratic falloff over `speed` seconds. Background color shows when not sparkling.

**Constructor:** `EffectTwinkle(speed=1.0, density=0.05, hue=0, saturation=0.0, brightness=1.0, background_hue=0, background_saturation=0.0, background_brightness=0.0, kelvin=3500)`

**Stateful:** Maintains per-pixel sparkle start times.

**Device support:** LIGHT=RECOMMENDED, MULTIZONE=RECOMMENDED, MATRIX=COMPATIBLE

---

### Task 10: Spin Effect

**Files:**
- Create: `src/lifx/effects/spin.py`
- Create: `tests/test_effects/test_spin.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/spin.py`

**Key algorithm:** Theme colors cycle through zones. Each zone is assigned a color from the theme based on its position plus a time-varying offset. `bulb_offset` adds a small hue shift per bulb for shimmer. Uses `HSBK.lerp_oklab()` for smooth inter-color transitions.

**Constructor:** `EffectSpin(speed=10.0, theme=None, bulb_offset=5, brightness=0.8, kelvin=3500, zones_per_bulb=1)`

Default theme: `ThemeLibrary.get("exciting")` (set in `__init__` if None).

**Device support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 11: Rule 30 Effect

**Files:**
- Create: `src/lifx/effects/rule30.py`
- Create: `tests/test_effects/test_rule30.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/rule30.py`

**Key algorithm:** 1D elementary cellular automaton with periodic (wraparound) boundaries. Each generation, the 3-cell neighborhood (left, center, right) is looked up in the 8-bit rule number. New generation displayed at `speed` generations per second. Alive cells show `hue` at `brightness`; dead cells show `hue` at `background_brightness`.

**Constructor:** `EffectRule30(speed=5.0, rule=30, hue=120, brightness=0.8, background_brightness=0.05, seed="center", kelvin=3500, zones_per_bulb=1)`

`seed` is one of `"center"`, `"random"`, `"all"`.

**Stateful:** Current cell state array, generation timer.

**Device support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

**Additional test:** Test rule=90 produces different pattern than rule=30. Test seed modes produce different initial states.

---

### Task 12: Rule Trio Effect

**Files:**
- Create: `src/lifx/effects/rule_trio.py`
- Create: `tests/test_effects/test_rule_trio.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/rule_trio.py`

**Key algorithm:** Three independent 1D CAs run at different speeds (base speed × drift multipliers). Each CA maps alive/dead to one of three theme colors. The three layers blend via `HSBK.lerp_oklab()`. Irrational drift values (1.31, 1.73) prevent phase lock-in.

**Constructor:** `EffectRuleTrio(rule_a=30, rule_b=90, rule_c=110, speed=5.0, drift_b=1.31, drift_c=1.73, theme=None, brightness=0.8, kelvin=3500, zones_per_bulb=1)`

Default theme: `ThemeLibrary.get("exciting")`.

**Stateful:** Three cell state arrays, three generation timers.

**Device support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 13: Embers Effect

**Files:**
- Create: `src/lifx/effects/embers.py`
- Create: `tests/test_effects/test_embers.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/embers.py`

**Key algorithm:** Heat diffusion simulation. Each frame: (1) convection shifts heat upward, (2) diffusion averages neighbors, (3) cooling decays all values, (4) turbulence randomly injects heat at bottom zones. Heat value maps to color gradient: 0.0→black, 0.33→red, 0.66→orange, 1.0→yellow.

**Constructor:** `EffectEmbers(intensity=0.5, cooling=0.15, turbulence=0.3, brightness=0.8, kelvin=3500, zones_per_bulb=1)`

**Stateful:** Heat buffer array, previous timestamp.

**Device support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 14: Fireworks Effect

**Files:**
- Create: `src/lifx/effects/fireworks.py`
- Create: `tests/test_effects/test_fireworks.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/fireworks.py`

**Key algorithm:** Rockets launch from both ends via Poisson process. Each rocket has ease-out ascent physics. At apex, burst creates gaussian brightness bloom that expands over time. Color evolves: white → chemical color (random hue) → cool orange. Overlapping bursts use additive RGB blending via `HSBK.to_rgb()` / `HSBK.from_rgb()`.

**Constructor:** `EffectFireworks(max_rockets=3, launch_rate=0.5, ascent_speed=0.3, burst_spread=5.0, burst_duration=2.0, brightness=0.8, kelvin=3500)`

**Stateful:** Active rockets list, burst particles.

**Device support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 15: Plasma Effect

**Files:**
- Create: `src/lifx/effects/plasma.py`
- Create: `tests/test_effects/test_plasma.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/plasma.py`

**Key algorithm:** Central core pulses slowly via sine wave. Tendrils are biased random walks from center outward, occasionally forking. Each tendril has a flicker cycle. Core and tendrils rendered with brightness falloff.

**Constructor:** `EffectPlasma(speed=3.0, tendril_rate=0.5, hue=270, hue_spread=60, brightness=0.8, kelvin=3500, zones_per_bulb=1)`

**Stateful:** Active tendrils list, core phase.

**Device support:** LIGHT=COMPATIBLE, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 16: Ripple Effect

**Files:**
- Create: `src/lifx/effects/ripple.py`
- Create: `tests/test_effects/test_ripple.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/ripple.py`

**Key algorithm:** 1D wave equation with damping. Two arrays: displacement and velocity. Each frame: velocity += (neighbor_average - displacement) * speed², displacement += velocity, both *= damping. Random drops inject impulse at random positions. Displacement maps to blend factor between two colors.

**Constructor:** `EffectRipple(speed=1.0, damping=0.98, drop_rate=0.3, hue1=200, hue2=240, saturation=1.0, brightness=0.8, kelvin=3500)`

**Stateful:** Displacement and velocity arrays, previous timestamp.

**Device support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 17: Jacob's Ladder Effect

**Files:**
- Create: `src/lifx/effects/jacobs_ladder.py`
- Create: `tests/test_effects/test_jacobs_ladder.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/jacobs_ladder.py`

**Key algorithm:** Arc pairs drift along the strip. Each arc has two electrodes (bright blue-white spots) separated by a gap. Between the electrodes, a flickering arc appears with crackle spikes. Arcs break off at strip ends and reform at the entry. At least one arc is always visible.

**Constructor:** `EffectJacobsLadder(speed=0.5, arcs=2, gap=5, brightness=0.8, kelvin=6500, zones_per_bulb=1)`

**Stateful:** Arc positions, flicker timers.

**Device support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 18: Newton's Cradle Effect

**Files:**
- Create: `src/lifx/effects/newtons_cradle.py`
- Create: `tests/test_effects/test_newtons_cradle.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/newtons_cradle.py`

**Key algorithm:** N balls rendered with Phong shading (ambient + diffuse + specular). Left and right end balls alternate swinging via sinusoidal motion. Light source at 25° from vertical. Specular highlight glides across the ball surface as it swings.

**Constructor:** `EffectNewtonsCradle(num_balls=5, ball_width=0, speed=2.0, hue=0, saturation=0.0, brightness=0.8, shininess=60, kelvin=4500, zones_per_bulb=1)`

`ball_width=0` means auto-compute to fit swing arc within strip.

**Device support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 19: Sonar Effect

**Files:**
- Create: `src/lifx/effects/sonar.py`
- Create: `tests/test_effects/test_sonar.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/sonar.py`

**Key algorithm:** Obstacles meander around the middle of the strip. Sources at each end and between obstacles emit wavefronts. Wavefronts travel outward, reflect off obstacles, and are absorbed on return to source. The wavefront head stamps bright white; stamped bulbs decay over time producing fading tails.

**Constructor:** `EffectSonar(speed=8.0, decay=2.0, pulse_interval=2.0, obstacle_speed=0.5, obstacle_hue=15, obstacle_brightness=0.8, brightness=1.0, kelvin=6500, zones_per_bulb=1)`

**Stateful:** Obstacles, wavefronts, bulb brightness map, sources, previous timestamp.

**Device support:** LIGHT=NOT_SUPPORTED, MULTIZONE=RECOMMENDED, MATRIX=NOT_SUPPORTED

---

### Task 20: Plasma2D Effect

**Files:**
- Create: `src/lifx/effects/plasma2d.py`
- Create: `tests/test_effects/test_plasma2d.py`

**Source:** `/Volumes/External/Developer/pkivolowitz/lifx/effects/plasma2d.py`

**Key algorithm:** 2D plasma using layered sine functions. For each pixel at (x, y), compute multiple overlapping sine waves with different frequencies and phases driven by time. The combined value maps to a blend factor between two colors via `HSBK.lerp_oklab()`. Grid dimensions come from `ctx.canvas_width` and `ctx.canvas_height`.

**Constructor:** `EffectPlasma2D(speed=1.0, scale=1.0, hue1=270, hue2=180, brightness=0.8, kelvin=3500)`

**Device support:** LIGHT=NOT_SUPPORTED, MULTIZONE=NOT_SUPPORTED, MATRIX=RECOMMENDED

**Additional tests:** Test with matrix context (canvas_width=8, canvas_height=8, pixel_count=64).

---

## Task 21: Registry and Exports (Integration)

**Files:**
- Modify: `src/lifx/effects/registry.py`
- Modify: `src/lifx/effects/__init__.py`
- Modify: `tests/test_effects/test_registry.py`

**Depends on:** Tasks 3-20 all complete

- [ ] **Step 1: Add all 18 effects to registry**

Add imports and `registry.register()` calls for all 18 effects in `_build_default_registry()` in `src/lifx/effects/registry.py`. Use the device support levels from each effect's task description.

- [ ] **Step 2: Add all 18 effects to `__init__.py` exports**

Add imports and `__all__` entries for all 18 effect classes in `src/lifx/effects/__init__.py`.

- [ ] **Step 3: Write registry test**

Add to `tests/test_effects/test_registry.py`:

```python
PORTED_EFFECTS = [
    "cylon", "wave", "sine", "spectrum_sweep", "pendulum_wave",
    "double_slit", "twinkle", "spin", "rule30", "rule_trio",
    "embers", "fireworks", "plasma", "ripple", "jacobs_ladder",
    "newtons_cradle", "sonar", "plasma2d",
]

@pytest.mark.parametrize("name", PORTED_EFFECTS)
def test_ported_effect_registered(name: str) -> None:
    """Each ported effect should be registered."""
    registry = get_effect_registry()
    info = registry.get_effect(name)
    assert info is not None, f"Effect '{name}' not registered"
    assert info.name == name
```

- [ ] **Step 4: Run registry tests**

Run: `uv run pytest tests/test_effects/test_registry.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 6: Run linting and type checking**

Run: `uv run ruff check . --fix && uv run ruff format . && uv run pyright`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add src/lifx/effects/registry.py src/lifx/effects/__init__.py tests/test_effects/test_registry.py
git commit -s -m "feat(effects): register and export all 18 ported effects

All effects are now discoverable via EffectRegistry and importable
from lifx.effects."
```

---

## Parallelism Guide

```
Task 1 (HSBK lerp) ──┐
                      ├── Tasks 3-20 (18 effects, all parallel) ── Task 21 (integration)
Task 2 (palettes)  ───┘
```

- Tasks 1 and 2 can run in parallel (no dependencies between them)
- Tasks 3-20 can ALL run in parallel once Tasks 1 and 2 are complete
- Task 21 runs after all of Tasks 3-20 are complete
