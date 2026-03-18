"""Fireworks effect for multizone LIFX devices.

Rockets launch from both ends of the strip via a Poisson process. Each
rocket has an ease-out ascent phase with a bright head and fading exhaust
trail. At the apex, a burst creates a gaussian brightness bloom that
expands over time. Color evolves: white-hot flash, peak chemical color
(random hue), then cooling toward warm orange.

Overlapping bursts use additive RGB blending for physically correct
color mixing (red + green = yellow, two reds = brighter red).

This effect is designed for multizone (strip/beam) LIFX devices.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import MAX_KELVIN, MIN_KELVIN
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect

if TYPE_CHECKING:
    from lifx.devices.light import Light

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Easing exponent applied to the ascent fraction.
# Higher = sharper deceleration as the rocket approaches zenith.
_EASE_EXPONENT: float = 2.0

# Quadratic decay exponent for the exhaust trail falloff.
_TRAIL_EXPONENT: float = 2.0

# Fade exponent for the burst brightness over time.
# Lowered from 2.0 to 1.4 so the burst lingers near full brightness
# for longer before dropping off.
_BURST_FADE_EXPONENT: float = 1.4

# Saturation of the rocket head (low = white-hot).
_HEAD_SATURATION: float = 0.10

# Saturation of the exhaust trail (slightly warmer than the head).
_TRAIL_SATURATION: float = 0.25

# Saturation of the burst at peak chemical color.
_BURST_SATURATION: float = 1.0

# Brightness multiplier applied to burst zones before clamping.
# Values > 1.0 over-drive the gaussian so even the fringes appear bright.
_BURST_BRIGHTNESS_BOOST: float = 2.5

# Initial gaussian sigma for the burst bloom (in zones).
_BURST_SIGMA_START: float = 5.0
_BURST_SIGMA_DIVISOR: float = 2.0

# Temporal color evolution of a burst (simulates star cooling).
_BURST_WHITE_PHASE: float = 0.08
_BURST_COLOR_PEAK: float = 0.35
_BURST_COOL_HUE: float = 25.0
_BURST_COOL_START: float = 0.6

# Brightness threshold below which we skip writing a zone.
_BURST_MIN_BRIGHTNESS: float = 0.005

# Fraction of strip length off-limits as zenith from each end.
_ZENITH_MARGIN: float = 0.25

# Minimum zenith travel distance in zones.
_MIN_ZENITH_ZONES: int = 3

# Trail length in zones for the rocket exhaust.
_TRAIL_LENGTH: int = 8


# ---------------------------------------------------------------------------
# Rocket state
# ---------------------------------------------------------------------------


@dataclass
class _Rocket:
    """Complete state for one rocket from launch through burst-fade.

    Attributes:
        origin: Zone index from which the rocket launches (0 or end).
        direction: Travel direction: +1 = rightward, -1 = leftward.
        zenith: Zone index at which the rocket peaks and bursts.
        launch_t: Global effect-time at the moment of launch.
        ascent_dur: Seconds from launch to zenith.
        burst_hue: Hue of the explosion in degrees (0-360).
        burst_dur: Seconds for the burst to fade completely to black.
    """

    origin: int
    direction: int
    zenith: int
    launch_t: float
    ascent_dur: float
    burst_hue: float
    burst_dur: float

    def is_done(self, t: float) -> bool:
        """Return True once the burst has fully faded.

        Args:
            t: Current global effect-time.

        Returns:
            True if this rocket has no further contribution.
        """
        return (t - self.launch_t) >= (self.ascent_dur + self.burst_dur)


# ---------------------------------------------------------------------------
# HSB <-> RGB helpers for additive compositing
# ---------------------------------------------------------------------------

_HUE_SEXTANTS: int = 6


def _hsb_to_rgb(h_deg: float, s: float, b: float) -> tuple[float, float, float]:
    """Convert HSB (hue degrees, sat 0-1, bri 0-1) to RGB 0-1.

    Uses the standard sextant algorithm.

    Args:
        h_deg: Hue in degrees (0-360).
        s: Saturation (0.0-1.0).
        b: Brightness (0.0-1.0).

    Returns:
        Tuple of (r, g, b) each in 0.0-1.0.
    """
    h = (h_deg / 360.0) * _HUE_SEXTANTS
    c = b * s
    x = c * (1.0 - abs(h % 2.0 - 1.0))
    m = b - c

    sextant = int(h) % _HUE_SEXTANTS
    if sextant == 0:
        return (c + m, x + m, m)
    elif sextant == 1:
        return (x + m, c + m, m)
    elif sextant == 2:
        return (m, c + m, x + m)
    elif sextant == 3:
        return (m, x + m, c + m)
    elif sextant == 4:
        return (x + m, m, c + m)
    else:
        return (c + m, m, x + m)


def _rgb_to_hsb(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Convert RGB (0-1) to HSB (hue degrees, sat 0-1, bri 0-1).

    Args:
        r: Red (0.0-1.0).
        g: Green (0.0-1.0).
        b: Blue (0.0-1.0).

    Returns:
        Tuple of (hue_degrees, saturation, brightness).
    """
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    delta = max_c - min_c

    bri = max_c

    if delta == 0.0:
        return (0.0, 0.0, bri)

    sat = delta / max_c

    if max_c == r:
        hue = 60.0 * (((g - b) / delta) % 6.0)
    elif max_c == g:
        hue = 60.0 * (((b - r) / delta) + 2.0)
    else:
        hue = 60.0 * (((r - g) / delta) + 4.0)

    return (hue % 360.0, sat, bri)


# ---------------------------------------------------------------------------
# Effect
# ---------------------------------------------------------------------------


class EffectFireworks(FrameEffect):
    """Rockets from both ends burst into spreading color halos.

    Each rocket:

    1. Launches from zone 0 or the last zone (chosen at random).
    2. Decelerates as it approaches a random zenith in the middle
       section of the strip, producing a bright head and fading
       exhaust trail.
    3. Detonates at zenith: a gaussian bloom of color expands outward
       and fades to black. Color evolves from white-hot through peak
       chemical color to warm orange.

    Multiple rockets overlap additively in RGB space for physically
    correct color mixing.

    Attributes:
        max_rockets: Maximum simultaneous rockets in flight
        launch_rate: Average new rockets launched per second
        ascent_speed: Rocket travel speed in zones per second
        burst_spread: Maximum burst radius in zones from zenith
        burst_duration: Seconds for the burst to fade to black
        brightness: Peak brightness multiplier (0.0-1.0)
        kelvin: Color temperature (1500-9000)

    Example:
        ```python
        effect = EffectFireworks(max_rockets=5, launch_rate=1.0)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        max_rockets: int = 3,
        launch_rate: float = 0.5,
        ascent_speed: float = 0.3,
        burst_spread: float = 5.0,
        burst_duration: float = 2.0,
        brightness: float = 0.8,
        kelvin: int = 3500,
    ) -> None:
        """Initialize Fireworks effect.

        Args:
            power_on: Power on devices if off (default True)
            max_rockets: Maximum simultaneous rockets, 1-20 (default 3)
            launch_rate: Average launches per second, 0.05-5.0 (default 0.5)
            ascent_speed: Zones per second travel speed, 0.1-60.0 (default 0.3)
            burst_spread: Max burst radius in zones, 2.0-60.0 (default 5.0)
            burst_duration: Seconds for burst fade, 0.2-8.0 (default 2.0)
            brightness: Peak brightness 0.0-1.0 (default 0.8)
            kelvin: Color temperature 1500-9000 (default 3500)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if not (1 <= max_rockets <= 20):
            raise ValueError(f"max_rockets must be 1-20, got {max_rockets}")
        if not (0.05 <= launch_rate <= 5.0):
            raise ValueError(f"launch_rate must be 0.05-5.0, got {launch_rate}")
        if not (0.1 <= ascent_speed <= 60.0):
            raise ValueError(f"ascent_speed must be 0.1-60.0, got {ascent_speed}")
        if not (2.0 <= burst_spread <= 60.0):
            raise ValueError(f"burst_spread must be 2.0-60.0, got {burst_spread}")
        if not (0.2 <= burst_duration <= 8.0):
            raise ValueError(f"burst_duration must be 0.2-8.0, got {burst_duration}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"brightness must be 0.0-1.0, got {brightness}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.max_rockets = max_rockets
        self.launch_rate = launch_rate
        self.ascent_speed = ascent_speed
        self.burst_spread = burst_spread
        self.burst_duration = burst_duration
        self.brightness = brightness
        self.kelvin = kelvin

        # Internal state (lazily initialized)
        self._rockets: list[_Rocket] = []
        self._next_launch_t: float = 0.0
        self._initialized: bool = False

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "fireworks"

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _ensure_initialized(self) -> None:
        """Lazily initialize state on first frame."""
        if not self._initialized:
            self._rockets.clear()
            self._next_launch_t = 0.0
            self._initialized = True

    # ------------------------------------------------------------------
    # Rocket management
    # ------------------------------------------------------------------

    def _spawn_rocket(self, t: float, zone_count: int) -> None:
        """Create and register a new rocket from a randomly chosen end.

        The zenith is chosen randomly within the middle portion of the
        strip, keeping clear of the margin at each end so every rocket
        has a visible ascent phase.

        Args:
            t: Current global effect-time.
            zone_count: Number of zones (used for bounds).
        """
        from_left = random.random() < 0.5
        origin = 0 if from_left else zone_count - 1
        direction = 1 if from_left else -1

        min_travel = max(_MIN_ZENITH_ZONES, int(zone_count * _ZENITH_MARGIN))
        max_travel = int(zone_count * (1.0 - _ZENITH_MARGIN))

        if max_travel <= min_travel:
            max_travel = min_travel + 1

        zenith_dist = random.randint(min_travel, max_travel)
        zenith = max(0, min(zone_count - 1, origin + direction * zenith_dist))

        actual_dist = abs(zenith - origin)
        ascent_dur = actual_dist / max(self.ascent_speed, 0.1)

        self._rockets.append(
            _Rocket(
                origin=origin,
                direction=direction,
                zenith=zenith,
                launch_t=t,
                ascent_dur=ascent_dur,
                burst_hue=random.uniform(0.0, 360.0),
                burst_dur=self.burst_duration,
            )
        )

    # ------------------------------------------------------------------
    # Per-rocket rendering
    # ------------------------------------------------------------------

    def _contribution(
        self,
        rocket: _Rocket,
        t: float,
        zone_count: int,
    ) -> list[tuple[float, float, float]]:
        """Compute this rocket's (hue_deg, sat_01, bri_01) for every zone.

        Zones not affected by this rocket have brightness 0.0.

        Args:
            rocket: The rocket to evaluate.
            t: Current global effect-time.
            zone_count: Total number of zones.

        Returns:
            List of (hue_deg, sat_01, bri_01) per zone.
        """
        contrib: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)] * zone_count

        age = t - rocket.launch_t
        if age < 0:
            return contrib

        if age < rocket.ascent_dur:
            # Ascent phase
            frac = age / rocket.ascent_dur if rocket.ascent_dur > 0 else 1.0
            eased = 1.0 - (1.0 - frac) ** _EASE_EXPONENT

            dist_to_zenith = abs(rocket.zenith - rocket.origin)
            head_pos = rocket.origin + rocket.direction * dist_to_zenith * eased

            for z in range(zone_count):
                behind = rocket.direction * (head_pos - z)

                if -0.5 <= behind <= 0.5:
                    contrib[z] = (rocket.burst_hue, _HEAD_SATURATION, 1.0)
                elif 0.5 < behind <= _TRAIL_LENGTH:
                    trail_frac = (behind - 0.5) / _TRAIL_LENGTH
                    bri = (1.0 - trail_frac) ** _TRAIL_EXPONENT
                    contrib[z] = (rocket.burst_hue, _TRAIL_SATURATION, bri)

        else:
            burst_age = age - rocket.ascent_dur
            if burst_age < rocket.burst_dur:
                # Burst phase
                burst_frac = burst_age / rocket.burst_dur
                fade = (1.0 - burst_frac) ** _BURST_FADE_EXPONENT

                sigma = (
                    _BURST_SIGMA_START
                    + burst_frac * self.burst_spread / _BURST_SIGMA_DIVISOR
                )
                two_sigma_sq = 2.0 * sigma * sigma

                # Temporal color evolution
                if burst_frac < _BURST_WHITE_PHASE:
                    zone_hue = rocket.burst_hue
                    zone_sat = _HEAD_SATURATION
                elif burst_frac < _BURST_COLOR_PEAK:
                    ramp = (burst_frac - _BURST_WHITE_PHASE) / (
                        _BURST_COLOR_PEAK - _BURST_WHITE_PHASE
                    )
                    zone_hue = rocket.burst_hue
                    zone_sat = (
                        _HEAD_SATURATION + (_BURST_SATURATION - _HEAD_SATURATION) * ramp
                    )
                elif burst_frac < _BURST_COOL_START:
                    zone_hue = rocket.burst_hue
                    zone_sat = _BURST_SATURATION
                else:
                    cool_frac = (burst_frac - _BURST_COOL_START) / (
                        1.0 - _BURST_COOL_START
                    )
                    diff = _BURST_COOL_HUE - rocket.burst_hue
                    if diff < -180.0:
                        diff += 360.0
                    zone_hue = (rocket.burst_hue + diff * cool_frac) % 360.0
                    zone_sat = _BURST_SATURATION * (1.0 - 0.5 * cool_frac)

                for z in range(zone_count):
                    dist_sq = float(z - rocket.zenith) ** 2
                    gaussian = math.exp(-dist_sq / two_sigma_sq)
                    bri = min(1.0, fade * gaussian * _BURST_BRIGHTNESS_BOOST)

                    if bri < _BURST_MIN_BRIGHTNESS:
                        continue

                    contrib[z] = (zone_hue, zone_sat, bri)

        return contrib

    # ------------------------------------------------------------------
    # Frame generation
    # ------------------------------------------------------------------

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate one frame of fireworks.

        Manages the rocket lifecycle (spawn / expire), then composites
        all active rockets onto the zone array using additive RGB blending.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        self._ensure_initialized()

        t = ctx.elapsed_s
        zone_count = ctx.pixel_count

        # Spawn a new rocket when the schedule says so and capacity allows.
        if t >= self._next_launch_t and len(self._rockets) < self.max_rockets:
            self._spawn_rocket(t, zone_count)
            self._next_launch_t = t + random.expovariate(self.launch_rate)

        # Remove fully-faded rockets.
        self._rockets = [r for r in self._rockets if not r.is_done(t)]

        # Per-zone RGB accumulators for additive blending.
        zone_r: list[float] = [0.0] * zone_count
        zone_g: list[float] = [0.0] * zone_count
        zone_b: list[float] = [0.0] * zone_count

        for rocket in self._rockets:
            for z, (h_deg, s_01, b_01) in enumerate(
                self._contribution(rocket, t, zone_count)
            ):
                if b_01 <= 0.0:
                    continue
                # Scale by effect brightness
                b_scaled = b_01 * self.brightness
                r, g, bl = _hsb_to_rgb(h_deg, s_01, b_scaled)
                zone_r[z] += r
                zone_g[z] += g
                zone_b[z] += bl

        # Convert accumulated RGB back to HSBK.
        colors: list[HSBK] = []
        for z in range(zone_count):
            r_val = min(1.0, zone_r[z])
            g_val = min(1.0, zone_g[z])
            b_val = min(1.0, zone_b[z])

            if r_val + g_val + b_val <= 0.0:
                colors.append(
                    HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=self.kelvin)
                )
            else:
                h_deg, s_01, b_01 = _rgb_to_hsb(r_val, g_val, b_val)
                colors.append(
                    HSBK(
                        hue=round(h_deg) % 360,
                        saturation=round(s_01, 2),
                        brightness=round(min(1.0, b_01), 2),
                        kelvin=self.kelvin,
                    )
                )

        return colors

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        Args:
            _light: The device being powered on (unused)

        Returns:
            Black at configured kelvin for smooth fade-in
        """
        return HSBK(
            hue=0,
            saturation=0.0,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with Fireworks effect.

        Fireworks requires multizone capability (strips/beams). Single
        lights are not supported; matrix devices are not supported.

        Args:
            light: The light device to check

        Returns:
            True if light has multizone support, False otherwise
        """
        if light.capabilities is None:
            await light.ensure_capabilities()
        return light.capabilities.has_multizone if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Fireworks can inherit prestate from another Fireworks effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectFireworks, False otherwise
        """
        return isinstance(other, EffectFireworks)

    def __repr__(self) -> str:
        """String representation of Fireworks effect."""
        return (
            f"EffectFireworks(max_rockets={self.max_rockets}, "
            f"launch_rate={self.launch_rate}, "
            f"ascent_speed={self.ascent_speed}, "
            f"burst_spread={self.burst_spread}, "
            f"burst_duration={self.burst_duration}, "
            f"brightness={self.brightness}, "
            f"kelvin={self.kelvin}, "
            f"power_on={self.power_on})"
        )
