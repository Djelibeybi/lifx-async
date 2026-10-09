# Effects Gallery

Animated previews of all effects available in lifx-async, captured from the [LIFX Emulator](https://github.com/Djelibeybi/lifx-emulator) dashboard. Effects adapted from [pkivolowitz/lifx](https://github.com/pkivolowitz/lifx) by Perry Kivolowitz are noted below.

## Multizone Effects

These effects are designed for LED strips and beams. Most also work on single-bulb lights.

<div class="grid cards" markdown>

-   ### Aurora

    ![Aurora](../assets/effects/aurora.gif)

    Flowing northern lights with palette interpolation and sine waves.

    **Class:** `EffectAurora` · **Best on:** Multizone, Matrix

-   ### Colorloop

    ![Colorloop](../assets/effects/colorloop.gif)

    Continuous hue rotation through the colour spectrum, or through your own `palette=`.

    **Class:** `EffectColorloop` · **Best on:** Light

-   ### Cylon

    ![Cylon](../assets/effects/cylon_zpb3.gif)

    Larson scanner — bright eye sweeps back and forth with fading trail.

    **Class:** `EffectCylon` · **Best on:** Multizone

-   ### Double Slit

    ![Double Slit](../assets/effects/double_slit_zpb3.gif)

    Young's double slit interference with shifting fringe patterns.

    **Class:** `EffectDoubleSlit` · **Best on:** Multizone, Mirror (`seamless` option)

-   ### Embers

    ![Embers](../assets/effects/embers_zpb3.gif)

    1D heat diffusion — rising embers with cooling and turbulence.

    **Class:** `EffectEmbers` · **Best on:** Multizone, Mirror (seamless on the ring)

-   ### Fireworks

    ![Fireworks](../assets/effects/fireworks.gif)

    Rockets launch, ascend, and burst into expanding color halos.

    **Class:** `EffectFireworks` · **Best on:** Multizone, Mirror (seamless on the ring)

-   ### Flicker

    ![Flicker](../assets/effects/flame.gif)

    Fire/candle flicker with layered sine waves and warm colors. Renamed from `EffectFlame`,
    which remains as a deprecated alias.

    **Class:** `EffectFlicker` · **Best on:** Light, Multizone, Matrix

-   ### Jacob's Ladder

    ![Jacob's Ladder](../assets/effects/jacobs_ladder_zpb3.gif)

    Electric arcs drift along the strip with flickering and crackling.

    **Class:** `EffectJacobsLadder` · **Best on:** Multizone, Mirror (seam at the ring origin)

-   ### Newton's Cradle

    ![Newton's Cradle](../assets/effects/newtons_cradle_zpb3.gif)

    Steel balls swing alternately with Phong sphere shading.

    **Class:** `EffectNewtonsCradle` · **Best on:** Multizone, Mirror (seam at the ring origin)

-   ### Pendulum Wave

    ![Pendulum Wave](../assets/effects/pendulum_wave_zpb3.gif)

    Pendulums with varying periods drift in and out of phase.

    **Class:** `EffectPendulumWave` · **Best on:** Multizone, Mirror (`seamless` option)

-   ### Plasma

    ![Plasma](../assets/effects/plasma_zpb3.gif)

    Plasma ball — electric tendrils crackle from a pulsing core.

    **Class:** `EffectPlasma` · **Best on:** Multizone, Mirror (seamless on the ring)

-   ### Progress

    ![Progress](../assets/effects/progress.gif)

    Animated progress bar with traveling bright spot.

    **Class:** `EffectProgress` · **Best on:** Multizone, Mirror (seam at the ring origin)

-   ### Rainbow

    ![Rainbow](../assets/effects/rainbow.gif)

    Full 360° rainbow spread across pixels, scrolling over time.

    **Class:** `EffectRainbow` · **Best on:** Multizone, Matrix

-   ### Ripple

    ![Ripple](../assets/effects/ripple.gif)

    Raindrops on water — wavefronts propagate, reflect, and interfere.

    **Class:** `EffectRipple` · **Best on:** Multizone, Mirror (seamless on the ring)

-   ### Rule 30

    ![Rule 30](../assets/effects/rule30_zpb3.gif)

    Wolfram's Rule 30 cellular automaton — chaotic organic patterns.

    **Class:** `EffectRule30` · **Best on:** Multizone, Mirror (seamless on the ring)

-   ### Rule Trio

    ![Rule Trio](../assets/effects/rule_trio_zpb3.gif)

    Three cellular automata at irrational speed ratios, blended via Oklab.

    **Class:** `EffectRuleTrio` · **Best on:** Multizone, Mirror (seamless on the ring)

-   ### Sine

    ![Sine](../assets/effects/sine_zpb3.gif)

    Traveling ease wave — bright humps roll with smooth cubic transitions.

    **Class:** `EffectSine` · **Best on:** Multizone

-   ### Sonar

    ![Sonar](../assets/effects/sonar_zpb3.gif)

    Sonar pulses bounce off drifting obstacles with decay tails.

    **Class:** `EffectSonar` · **Best on:** Multizone, Mirror (seam at the ring origin)

-   ### Spectrum Sweep

    ![Spectrum Sweep](../assets/effects/spectrum_sweep_zpb3.gif)

    Three sine waves 120° out of phase sweep through zones like a spectrum analyzer.

    **Class:** `EffectSpectrumSweep` · **Best on:** Multizone

-   ### Spin

    ![Spin](../assets/effects/spin_zpb3.gif)

    Theme colors rotate through zones with Oklab interpolation.

    **Class:** `EffectSpin` · **Best on:** Multizone

-   ### Twinkle

    ![Twinkle](../assets/effects/twinkle.gif)

    Random pixels sparkle and fade like Christmas lights.

    **Class:** `EffectTwinkle` · **Best on:** Light, Multizone

-   ### Wave

    ![Wave](../assets/effects/wave_zpb3.gif)

    Standing wave — zones vibrate between two colors with fixed nodes.

    **Class:** `EffectWave` · **Best on:** Multizone

</div>

## Matrix Effects

These effects are designed for LIFX Tile, Candle, and Ceiling devices.

<div class="grid cards" markdown>

-   ### Plasma 2D (single tile)

    ![Plasma 2D](../assets/effects/plasma2d.gif)

    2D plasma — four sine waves create flowing interference patterns.

    **Class:** `EffectPlasma2D` · **Best on:** Matrix

-   ### Plasma 2D (5-tile canvas)

    ![Plasma 2D 5-tile](../assets/effects/plasma2d_5tile.gif)

    Same effect spanning a 40×8 multi-tile canvas — each tile shows a different part of the continuous pattern.

    **Class:** `EffectPlasma2D` · **Best on:** Matrix

-   ### Scroll

    Moves a painted image one column every 1.25 seconds, as the LIFX app does for a MOVE mood. Pass `vertical=True` to move whole rows down the light instead.

    **Class:** `EffectScroll` · **Best on:** Matrix (not the Mirror)

</div>

---

See [Light Effects](effects.md) for usage examples and code, or [Effects Reference](../api/effects.md) for full API documentation.
