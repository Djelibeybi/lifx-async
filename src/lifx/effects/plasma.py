"""Plasma ball effect -- electric tendrils reaching from a central point.

Simulates a Van de Graaff / plasma globe where bright arcs extend from a
central hot core toward both ends of the strip. Each tendril is a random
walk biased toward the endpoints, forking occasionally. Brightness follows
a 1/r falloff from the core, with stochastic flicker on each tendril.

The core sits at the center of the strip and pulses slowly. Tendrils are
regenerated frequently -- they flash into existence, crackle outward, then
die -- giving the characteristic plasma ball look of constantly shifting
discharge paths.

This effect is STATEFUL: it maintains an active tendrils list and core
phase across frames. State is lazily initialized on the first frame.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
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

_TWO_PI: float = 2.0 * math.pi

# Core glow radius as fraction of strip length.
_CORE_RADIUS_FRAC: float = 0.08

# Core pulse frequency multiplier (pulses per speed cycle).
_CORE_PULSE_FREQ: float = 3.0

# Core brightness range (fraction of max).
_CORE_BRI_MIN: float = 0.6
_CORE_BRI_MAX: float = 1.0

# Tendril brightness decay exponent (higher = faster falloff from core).
_TENDRIL_DECAY_EXP: float = 1.5

# Probability of a tendril crackling bright at any given frame.
_CRACKLE_PROB: float = 0.15

# Minimum and maximum tendril flicker multiplier.
_FLICKER_MIN: float = 0.3
_FLICKER_MAX: float = 1.0

# Tendril fork probability per regeneration.
_FORK_PROB: float = 0.3

# Maximum number of simultaneous tendrils.
_MAX_TENDRILS: int = 8

# Minimum tendril reach as fraction of half-strip.
_MIN_REACH_FRAC: float = 0.3

# Maximum tendril reach as fraction of half-strip.
_MAX_REACH_FRAC: float = 1.0

# Tendril lifetime range in seconds.
_TENDRIL_LIFE_MIN: float = 0.08
_TENDRIL_LIFE_MAX: float = 0.4

# Neighbor brightness contribution factor.
_NEIGHBOR_BRI_FACTOR: float = 0.4

# Minimum bulb count required for tendril spawning.
_MIN_BULB_COUNT: int = 3


@dataclass
class _Tendril:
    """State for one electric arc from core to endpoint.

    Attributes:
        zones: List of zone indices this tendril passes through.
        birth_t: Time of creation.
        lifetime: How long this tendril lives before dying.
        hue_off: Hue offset from the base hue (adds variety).
    """

    zones: list[int] = field(default_factory=list)
    birth_t: float = 0.0
    lifetime: float = 0.2
    hue_off: float = 0.0

    def is_alive(self, t: float) -> bool:
        """Return True if this tendril is still active.

        Args:
            t: Current time.

        Returns:
            True if the tendril hasn't expired.
        """
        return (t - self.birth_t) < self.lifetime

    def age_frac(self, t: float) -> float:
        """Return normalized age [0, 1] where 1 = about to die.

        Args:
            t: Current time.

        Returns:
            Normalized age.
        """
        if self.lifetime <= 0:
            return 1.0
        return min(1.0, (t - self.birth_t) / self.lifetime)


class EffectPlasma(FrameEffect):
    """Plasma ball -- electric tendrils from a pulsing central core.

    A bright core sits at the center of the strip, pulsing slowly.
    Electric tendrils crackle outward toward the ends, flickering and
    forking. Brightness falls off with distance from the core. The
    constantly regenerating tendrils give the characteristic look of
    a plasma globe.

    Compatible with single lights and multizone (strip/beam) devices.
    Not supported on matrix devices.

    Attributes:
        speed: Core pulse period in seconds
        tendril_rate: Average new tendrils spawned per second
        hue: Base tendril hue in degrees (0-360)
        hue_spread: Random hue variation in degrees
        brightness: Peak brightness (0.0-1.0)
        kelvin: Color temperature (1500-9000)
        zones_per_bulb: Number of physical zones per logical bulb

    Example:
        ```python
        effect = EffectPlasma(speed=3.0, hue=270, brightness=0.8)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 3.0,
        tendril_rate: float = 0.5,
        hue: int = 270,
        hue_spread: float = 60.0,
        brightness: float = 0.8,
        kelvin: int = 3500,
        zones_per_bulb: int = 1,
    ) -> None:
        """Initialize plasma effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Core pulse period in seconds, must be > 0 (default 3.0)
            tendril_rate: Average tendrils spawned per second, must be > 0 (default 0.5)
            hue: Base tendril hue 0-360 degrees (default 270, violet)
            hue_spread: Random hue variation 0-180 degrees (default 60)
            brightness: Peak brightness 0.0-1.0 (default 0.8)
            kelvin: Color temperature 1500-9000 (default 3500)
            zones_per_bulb: Physical zones per logical bulb (default 1)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if tendril_rate <= 0:
            raise ValueError(f"Tendril rate must be positive, got {tendril_rate}")
        if not (0 <= hue <= 360):
            raise ValueError(f"Hue must be 0-360, got {hue}")
        if not (0.0 <= hue_spread <= 180.0):
            raise ValueError(f"Hue spread must be 0.0-180.0, got {hue_spread}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.tendril_rate = tendril_rate
        self.hue = hue
        self.hue_spread = hue_spread
        self.brightness = brightness
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb

        # Stateful: tendril tracking
        self._tendrils: list[_Tendril] = []
        self._next_spawn_t: float = 0.0
        self._initialized: bool = False

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "plasma"

    def _reset_state(self) -> None:
        """Reset all stateful data for a fresh start."""
        self._tendrils.clear()
        self._next_spawn_t = 0.0
        self._initialized = False

    def _spawn_tendril(self, t: float, bulb_count: int) -> None:
        """Create a new tendril reaching from center toward an end.

        The tendril path is a biased random walk from the core outward.
        It may fork once, creating a second branch.

        Args:
            t: Current time.
            bulb_count: Number of bulbs (for positional math).
        """
        if bulb_count < _MIN_BULB_COUNT:
            return

        center: int = bulb_count // 2
        half: int = bulb_count - center

        # Pick direction: left or right.
        direction: int = -1 if random.random() < 0.5 else 1

        # How far this tendril reaches (fraction of half-strip).
        reach_frac: float = random.uniform(_MIN_REACH_FRAC, _MAX_REACH_FRAC)
        reach: int = max(2, int(half * reach_frac))

        # Build path via biased random walk.
        zones: list[int] = [center]
        pos: float = float(center)
        for _ in range(reach):
            # Bias toward the endpoint, with random jitter.
            step: float = direction * random.uniform(0.5, 1.5)
            jitter: float = random.uniform(-0.3, 0.3)
            pos += step + jitter
            zone: int = max(0, min(bulb_count - 1, int(pos)))
            if zone not in zones:
                zones.append(zone)

        hue_off: float = random.uniform(-self.hue_spread, self.hue_spread)
        lifetime: float = random.uniform(_TENDRIL_LIFE_MIN, _TENDRIL_LIFE_MAX)

        self._tendrils.append(
            _Tendril(
                zones=zones,
                birth_t=t,
                lifetime=lifetime,
                hue_off=hue_off,
            )
        )

        # Possible fork -- a shorter branch splitting off partway.
        if random.random() < _FORK_PROB and len(zones) > 3:
            fork_start: int = random.randint(1, len(zones) // 2)
            fork_zones: list[int] = list(zones[:fork_start])
            pos = float(zones[fork_start - 1])
            fork_dir: int = direction * (-1 if random.random() < 0.5 else 1)
            fork_reach: int = max(1, reach // 3)
            for _ in range(fork_reach):
                pos += fork_dir * random.uniform(0.5, 1.5)
                zone = max(0, min(bulb_count - 1, int(pos)))
                if zone not in fork_zones:
                    fork_zones.append(zone)

            self._tendrils.append(
                _Tendril(
                    zones=fork_zones,
                    birth_t=t,
                    lifetime=lifetime * 0.7,
                    hue_off=hue_off + random.uniform(-10.0, 10.0),
                )
            )

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate one frame of the plasma ball.

        Manages tendril lifecycle, computes core glow, and composites
        all active tendrils onto the zone array.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        zpb: int = self.zones_per_bulb
        bulb_count: int = max(1, ctx.pixel_count // zpb)
        center: int = bulb_count // 2

        t = ctx.elapsed_s

        # Lazy initialization on first frame.
        if not self._initialized:
            self._tendrils.clear()
            self._next_spawn_t = t
            self._initialized = True

        # Spawn new tendrils.
        if t >= self._next_spawn_t and len(self._tendrils) < _MAX_TENDRILS:
            self._spawn_tendril(t, bulb_count)
            # Exponential inter-arrival time based on tendril_rate.
            if self.tendril_rate > 0:
                self._next_spawn_t = t + random.expovariate(self.tendril_rate)
            else:
                self._next_spawn_t = t + 1.0

        # Expire dead tendrils.
        self._tendrils = [td for td in self._tendrils if td.is_alive(t)]

        # Per-bulb accumulators.
        bulb_bri: list[float] = [0.0] * bulb_count
        bulb_hue: list[float] = [float(self.hue)] * bulb_count

        # Core glow -- pulsing brightness at the center.
        core_pulse: float = _CORE_BRI_MIN + (_CORE_BRI_MAX - _CORE_BRI_MIN) * (
            0.5 + 0.5 * math.sin(_TWO_PI * _CORE_PULSE_FREQ * t / self.speed)
        )
        core_radius: int = max(1, int(bulb_count * _CORE_RADIUS_FRAC))
        for b in range(bulb_count):
            dist: int = abs(b - center)
            if dist <= core_radius:
                # Gaussian core glow.
                sigma: float = max(0.5, core_radius / 2.0)
                glow: float = core_pulse * math.exp(-0.5 * (dist / sigma) ** 2)
                bulb_bri[b] = max(bulb_bri[b], glow)

        # Composite tendrils.
        for tendril in self._tendrils:
            age: float = tendril.age_frac(t)
            # Fade out as tendril dies.
            life_fade: float = 1.0 - age * age  # quadratic fade

            # Per-tendril flicker.
            if random.random() < _CRACKLE_PROB:
                flicker: float = 1.0  # crackle = full brightness
            else:
                flicker = random.uniform(_FLICKER_MIN, _FLICKER_MAX)

            for idx, zone in enumerate(tendril.zones):
                if zone < 0 or zone >= bulb_count:
                    continue

                # Distance from core along the tendril path (normalized).
                path_frac: float = idx / max(1, len(tendril.zones) - 1)

                # Brightness decays with distance from core.
                dist_decay: float = (1.0 - path_frac) ** _TENDRIL_DECAY_EXP

                bri_contrib: float = dist_decay * life_fade * flicker

                if bri_contrib > bulb_bri[zone]:
                    bulb_bri[zone] = bri_contrib
                    bulb_hue[zone] = self.hue + tendril.hue_off

                # Also illuminate neighboring zones (tendril width).
                for offset in (-1, 1):
                    neighbor: int = zone + offset
                    if 0 <= neighbor < bulb_count:
                        neighbor_bri: float = bri_contrib * _NEIGHBOR_BRI_FACTOR
                        if neighbor_bri > bulb_bri[neighbor]:
                            bulb_bri[neighbor] = neighbor_bri
                            bulb_hue[neighbor] = self.hue + tendril.hue_off

        # Convert to HSBK.
        bulb_colors: list[HSBK] = []
        for i in range(bulb_count):
            bri_frac: float = min(1.0, bulb_bri[i])
            bri: float = self.brightness * bri_frac if bri_frac > 0.01 else 0.0
            h: float = bulb_hue[i] % 360.0
            bulb_colors.append(
                HSBK(
                    hue=round(h),
                    saturation=1.0,
                    brightness=max(0.0, min(1.0, bri)),
                    kelvin=self.kelvin,
                )
            )

        # Expand logical bulbs to physical zones.
        if zpb == 1:
            colors = bulb_colors
        else:
            colors = []
            for color in bulb_colors:
                colors.extend([color] * zpb)

        # Trim or pad to exact pixel_count.
        if len(colors) < ctx.pixel_count:
            colors.extend([colors[-1]] * (ctx.pixel_count - len(colors)))
        elif len(colors) > ctx.pixel_count:
            colors = colors[: ctx.pixel_count]

        return colors

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        Args:
            _light: The device being powered on (unused)

        Returns:
            Violet color at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=self.hue,
            saturation=1.0,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with plasma effect.

        Plasma requires color capability. Works best on multizone devices
        but is compatible with single lights. Not supported on matrix devices.

        Args:
            light: The light device to check

        Returns:
            True if light has color support and is not a matrix device
        """
        if light.capabilities is None:
            await light.ensure_capabilities()
        if light.capabilities is None:
            return False
        if light.capabilities.has_matrix:
            return False
        return light.capabilities.has_color

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Plasma can inherit prestate from another plasma effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectPlasma, False otherwise
        """
        return isinstance(other, EffectPlasma)

    def __repr__(self) -> str:
        """String representation of plasma effect."""
        return (
            f"EffectPlasma(speed={self.speed}, tendril_rate={self.tendril_rate}, "
            f"hue={self.hue}, hue_spread={self.hue_spread}, "
            f"brightness={self.brightness}, kelvin={self.kelvin}, "
            f"zones_per_bulb={self.zones_per_bulb}, power_on={self.power_on})"
        )
