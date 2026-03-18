"""Ripple tank effect -- raindrops on a 1D water surface.

Simulates a one-dimensional wave equation with damping. Drops fall at
random positions, each injecting a sharp impulse into the surface.
Wavefronts propagate outward in both directions at the configured speed,
reflect off the strip endpoints, and interfere with one another.

The displacement at each zone is mapped to a blend factor between two
colors via ``HSBK.lerp_oklab()`` for perceptually smooth transitions.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import MAX_KELVIN, MIN_KELVIN
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect

if TYPE_CHECKING:
    from lifx.devices.light import Light

# Physics timestep for the wave equation (seconds).
# 60 Hz is sufficient for LED animation while keeping CPU load low.
_PHYSICS_DT: float = 1.0 / 60.0

# Maximum simulation steps per render call to prevent runaway on lag spikes.
_MAX_STEPS_PER_FRAME: int = 10

# Impulse amplitude when a drop hits the surface.
_DROP_IMPULSE: float = 1.0

# Floor brightness fraction to avoid LIFX flicker near true black.
_FLOOR_FRAC: float = 0.02

# Minimum displacement threshold for normalization.  Below this, the
# surface is considered calm and normalization uses 1.0 to avoid
# amplifying residual noise.
_CALM_THRESHOLD: float = 0.05


class EffectRipple(FrameEffect):
    """Ripple tank -- raindrops on a 1D water surface.

    Random drops hit the surface, launching wavefronts that propagate,
    reflect off the ends, and interfere. Displacement maps to a blend
    between two colors using Oklab perceptual interpolation.

    This is a stateful effect: it maintains displacement and velocity
    arrays that evolve over time via the 1D wave equation.

    Attributes:
        speed: Wave propagation speed (higher = faster waves)
        damping: Wave damping factor (higher = faster fade)
        drop_rate: Average drops per second
        hue1: Color for positive displacement (0-360 degrees)
        hue2: Color for negative displacement (0-360 degrees)
        saturation: Wave color saturation (0.0-1.0)
        brightness: Peak brightness (0.0-1.0)
        kelvin: Color temperature (1500-9000)

    Example:
        ```python
        effect = EffectRipple(speed=1.0, hue1=200, hue2=240)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 1.0,
        damping: float = 0.98,
        drop_rate: float = 0.3,
        hue1: int = 200,
        hue2: int = 240,
        saturation: float = 1.0,
        brightness: float = 0.8,
        kelvin: int = 3500,
    ) -> None:
        """Initialize ripple effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Wave propagation speed, must be > 0 (default 1.0)
            damping: Damping factor 0.0-1.0, applied per step (default 0.98)
            drop_rate: Average drops per second, must be > 0 (default 0.3)
            hue1: Color hue for positive displacement 0-360 (default 200)
            hue2: Color hue for negative displacement 0-360 (default 240)
            saturation: Color saturation 0.0-1.0 (default 1.0)
            brightness: Peak brightness 0.0-1.0 (default 0.8)
            kelvin: Color temperature 1500-9000 (default 3500)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if not (0.0 <= damping <= 1.0):
            raise ValueError(f"Damping must be 0.0-1.0, got {damping}")
        if drop_rate <= 0:
            raise ValueError(f"Drop rate must be positive, got {drop_rate}")
        if not (0 <= hue1 <= 360):
            raise ValueError(f"hue1 must be 0-360, got {hue1}")
        if not (0 <= hue2 <= 360):
            raise ValueError(f"hue2 must be 0-360, got {hue2}")
        if not (0.0 <= saturation <= 1.0):
            raise ValueError(f"Saturation must be 0.0-1.0, got {saturation}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.damping = damping
        self.drop_rate = drop_rate
        self.hue1 = hue1
        self.hue2 = hue2
        self.saturation = saturation
        self.brightness = brightness
        self.kelvin = kelvin

        # Wave simulation state -- initialized lazily on first frame.
        self._displacement: list[float] = []
        self._velocity: list[float] = []
        self._sim_time: float = 0.0
        self._last_t: float | None = None
        self._next_drop_t: float = 0.0
        self._n_cells: int = 0

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "ripple"

    def _init_state(self, n_cells: int) -> None:
        """Initialize or reinitialize wave simulation arrays.

        Args:
            n_cells: Number of simulation cells
        """
        self._n_cells = n_cells
        self._displacement = [0.0] * n_cells
        self._velocity = [0.0] * n_cells
        self._sim_time = 0.0
        self._last_t = None
        self._next_drop_t = 0.0

    def _step(self) -> None:
        """Advance the wave equation by one timestep.

        Uses a velocity-based formulation with damping:
          velocity[i] += (neighbor_avg - displacement[i]) * speed^2
          displacement[i] += velocity[i]
          both *= damping

        Boundary conditions are fixed endpoints (displacement = 0).
        """
        n = self._n_cells
        if n < 3:
            return

        speed_sq = self.speed * self.speed

        for i in range(1, n - 1):
            # Average of neighbors minus current position
            neighbor_avg = (self._displacement[i - 1] + self._displacement[i + 1]) / 2.0
            self._velocity[i] += (neighbor_avg - self._displacement[i]) * speed_sq

        for i in range(1, n - 1):
            self._displacement[i] += self._velocity[i]

        # Apply damping to both arrays
        for i in range(n):
            self._displacement[i] *= self.damping
            self._velocity[i] *= self.damping

        # Fixed boundary conditions
        self._displacement[0] = 0.0
        self._displacement[n - 1] = 0.0
        self._velocity[0] = 0.0
        self._velocity[n - 1] = 0.0

    def _maybe_drop(self) -> None:
        """Inject a drop impulse if the schedule says it is time."""
        if self._sim_time >= self._next_drop_t:
            if self._n_cells > 2:
                # Drop lands at a random interior position.
                pos = random.randint(1, self._n_cells - 2)
                self._displacement[pos] += _DROP_IMPULSE
            # Schedule next drop (Poisson process).
            self._next_drop_t = self._sim_time + random.expovariate(self.drop_rate)

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of the ripple tank.

        Advances the wave simulation to match the current time, then
        maps displacement to color via Oklab interpolation.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        n_cells = max(ctx.pixel_count, 1)

        # Lazy initialization or reinitialize on zone count change.
        if n_cells != self._n_cells:
            self._init_state(n_cells)

        # First-frame initialization.
        if self._last_t is None:
            self._last_t = ctx.elapsed_s
            self._sim_time = ctx.elapsed_s

        # How much real time has elapsed since last render.
        dt_real = ctx.elapsed_s - self._last_t
        self._last_t = ctx.elapsed_s

        # Advance simulation in fixed timesteps.
        steps = min(_MAX_STEPS_PER_FRAME, int(dt_real / _PHYSICS_DT))
        for _ in range(max(1, steps)):
            self._maybe_drop()
            self._step()
            self._sim_time += _PHYSICS_DT

        # Find maximum displacement for normalization.
        max_disp = 0.0
        for u in self._displacement:
            a = abs(u)
            if a > max_disp:
                max_disp = a
        # Avoid amplifying tiny residual waves.
        if max_disp < _CALM_THRESHOLD:
            max_disp = 1.0

        # Build the two endpoint colors for lerp.
        color_pos = HSBK(
            hue=self.hue1,
            saturation=self.saturation,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )
        color_neg = HSBK(
            hue=self.hue2,
            saturation=self.saturation,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )

        min_bri = self.brightness * _FLOOR_FRAC

        colors: list[HSBK] = []
        for i in range(ctx.pixel_count):
            cell_idx = min(i, n_cells - 1)

            # Normalized displacement in [-1, 1].
            disp = self._displacement[cell_idx] / max_disp
            disp = max(-1.0, min(1.0, disp))

            # Blend factor: 0.0 = full hue2 (negative), 1.0 = full hue1 (positive).
            blend = (disp + 1.0) / 2.0

            # Perceptual color interpolation via Oklab.
            blended = color_neg.lerp_oklab(color_pos, blend)

            # Brightness proportional to |displacement|, with floor.
            bri = min_bri + (self.brightness - min_bri) * abs(disp)
            bri = max(0.0, min(1.0, bri))

            colors.append(
                HSBK(
                    hue=blended.hue,
                    saturation=blended.saturation,
                    brightness=bri,
                    kelvin=self.kelvin,
                )
            )

        return colors

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        Args:
            _light: The device being powered on (unused)

        Returns:
            Blue-tinted color at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=self.hue1,
            saturation=self.saturation,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with ripple effect.

        Ripple requires multizone capability (LED strips/beams).

        Args:
            light: The light device to check

        Returns:
            True if light has multizone support, False otherwise
        """
        if light.capabilities is None:
            await light.ensure_capabilities()
        return light.capabilities.has_multizone if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Ripple can inherit prestate from another ripple effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectRipple, False otherwise
        """
        return isinstance(other, EffectRipple)

    def __repr__(self) -> str:
        """String representation of ripple effect."""
        return (
            f"EffectRipple(speed={self.speed}, damping={self.damping}, "
            f"drop_rate={self.drop_rate}, hue1={self.hue1}, hue2={self.hue2}, "
            f"saturation={self.saturation}, brightness={self.brightness}, "
            f"kelvin={self.kelvin}, power_on={self.power_on})"
        )
