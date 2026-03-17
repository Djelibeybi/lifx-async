"""Sonar / radar pulses effect.

Obstacles meander around the middle of the strip. Sources at each end
and between obstacles emit wavefronts that travel outward. Wavefronts
reflect off obstacles and are absorbed on return to their source.
The wavefront head stamps bright white; stamped bulbs decay over time
producing fading tails. STATEFUL.

Obstacle count scales with string length: 1 obstacle per 24 bulbs,
minimum 1. Each source is limited to one live (non-absorbed) pulse
at a time; a new wavefront is emitted only after the previous one
from that source has been absorbed or has died.
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum bulbs before adding a second obstacle.
_BULBS_PER_OBSTACLE: int = 24

# Obstacle width in bulbs (visual thickness).
_OBSTACLE_WIDTH_BULBS: int = 1

# Minimum gap in bulbs between obstacle and edge/other obstacle.
_MIN_GAP_BULBS: int = 3

# How often obstacle changes drift direction (seconds).
_OBSTACLE_DIRECTION_INTERVAL: float = 4.0

# Minimum number of obstacles.
_MIN_OBSTACLES: int = 1


class _Wavefront:
    """A traveling wavefront that stamps bulbs as it passes.

    Attributes:
        pos: Current position in bulb units.
        direction: +1 (rightward) or -1 (leftward).
        source: Bulb position of the emitting source.
        speed: Travel speed in bulbs per second.
        alive: False once fully absorbed or off-string.
        reflected: True after bouncing off an obstacle.
        absorbed: True after returning to source post-reflection.
        last_bulb: Last integer bulb index stamped (prevents re-stamping).
    """

    def __init__(self, source: float, direction: int, speed: float) -> None:
        self.pos: float = source
        self.direction: int = direction
        self.source: float = source
        self.speed: float = speed
        self.alive: bool = True
        self.reflected: bool = False
        self.absorbed: bool = False
        self.last_bulb: int = -1


class _Obstacle:
    """A drifting obstacle that reflects wavefronts.

    Attributes:
        pos: Current center position in bulb units.
        drift_dir: Current drift direction (+1 or -1).
        next_turn: Time at which drift direction changes.
    """

    def __init__(self, pos: float) -> None:
        self.pos: float = pos
        self.drift_dir: int = random.choice([-1, 1])
        self.next_turn: float = 0.0


class EffectSonar(FrameEffect):
    """Sonar pulses bounce off drifting obstacles.

    Wavefronts emit from sources positioned at the string ends and
    between obstacles. Each wavefront travels outward, reflects off
    the nearest obstacle, and is absorbed when it returns to its source.
    The wavefront head is bright white; the tail fades to black.

    Attributes:
        speed: Wavefront travel speed in bulbs per second
        decay: Particle decay time in seconds (tail lifetime)
        pulse_interval: Seconds between pulse emissions
        obstacle_speed: Obstacle drift speed in bulbs per second
        obstacle_hue: Obstacle color hue in degrees (0-360)
        obstacle_brightness: Obstacle brightness (0.0-1.0)
        brightness: Wavefront peak brightness (0.0-1.0)
        kelvin: Wavefront color temperature (1500-9000)
        zones_per_bulb: Number of physical zones per logical bulb

    Example:
        ```python
        effect = EffectSonar(speed=8.0, decay=2.0, pulse_interval=2.0)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 8.0,
        decay: float = 2.0,
        pulse_interval: float = 2.0,
        obstacle_speed: float = 0.5,
        obstacle_hue: int = 15,
        obstacle_brightness: float = 0.8,
        brightness: float = 1.0,
        kelvin: int = 6500,
        zones_per_bulb: int = 1,
    ) -> None:
        """Initialize Sonar radar pulses effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Wavefront travel speed in bulbs/s, must be > 0 (default 8.0)
            decay: Particle decay time in seconds, must be > 0 (default 2.0)
            pulse_interval: Seconds between emissions, must be > 0 (default 2.0)
            obstacle_speed: Obstacle drift speed in bulbs/s, >= 0 (default 0.5)
            obstacle_hue: Obstacle hue 0-360 degrees (default 15)
            obstacle_brightness: Obstacle brightness 0.0-1.0 (default 0.8)
            brightness: Wavefront peak brightness 0.0-1.0 (default 1.0)
            kelvin: Color temperature 1500-9000 (default 6500)
            zones_per_bulb: Physical zones per logical bulb (default 1)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if decay <= 0:
            raise ValueError(f"Decay must be positive, got {decay}")
        if pulse_interval <= 0:
            raise ValueError(f"Pulse interval must be positive, got {pulse_interval}")
        if obstacle_speed < 0:
            raise ValueError(
                f"Obstacle speed must be non-negative, got {obstacle_speed}"
            )
        if not (0 <= obstacle_hue <= 360):
            raise ValueError(f"Obstacle hue must be 0-360, got {obstacle_hue}")
        if not (0.0 <= obstacle_brightness <= 1.0):
            raise ValueError(
                f"Obstacle brightness must be 0.0-1.0, got {obstacle_brightness}"
            )
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.decay = decay
        self.pulse_interval = pulse_interval
        self.obstacle_speed = obstacle_speed
        self.obstacle_hue = obstacle_hue
        self.obstacle_brightness = obstacle_brightness
        self.brightness = brightness
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb

        # Stateful internals -- initialized lazily on first frame.
        self._obstacles: list[_Obstacle] = []
        self._wavefronts: list[_Wavefront] = []
        self._bulb_brightness: dict[int, float] = {}
        self._sources: list[float] = []
        self._last_pulse_t: float = -999.0
        self._initialized: bool = False
        self._prev_t: float = 0.0

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "sonar"

    # ------------------------------------------------------------------
    # State initialization
    # ------------------------------------------------------------------

    def _init_state(self, zone_count: int) -> None:
        """Set up obstacles and sources for the given zone count.

        Args:
            zone_count: Total number of zones across all devices.
        """
        zpb = max(1, self.zones_per_bulb)
        bulb_count = max(1, zone_count // zpb)

        # Determine obstacle count.
        num_obstacles = max(_MIN_OBSTACLES, bulb_count // _BULBS_PER_OBSTACLE)

        # Place obstacles evenly across the middle region.
        self._obstacles = []
        for i in range(num_obstacles):
            frac = (i + 1) / (num_obstacles + 1)
            center = 0.2 + frac * 0.6
            pos = center * bulb_count
            obs = _Obstacle(pos)
            obs.next_turn = random.uniform(
                _OBSTACLE_DIRECTION_INTERVAL * 0.5,
                _OBSTACLE_DIRECTION_INTERVAL * 1.5,
            )
            self._obstacles.append(obs)

        self._update_sources(bulb_count)
        self._initialized = True

    def _update_sources(self, bulb_count: int) -> None:
        """Recompute source positions based on current obstacle positions.

        Sources sit at each end and midway between adjacent obstacles.

        Args:
            bulb_count: Total number of bulbs.
        """
        obs_positions = sorted(o.pos for o in self._obstacles)

        self._sources = []
        # Source at the left end.
        self._sources.append(0.0)
        # Sources between adjacent obstacles.
        for i in range(len(obs_positions) - 1):
            mid = (obs_positions[i] + obs_positions[i + 1]) / 2.0
            self._sources.append(mid)
        # Source at the right end.
        self._sources.append(float(bulb_count - 1))

    # ------------------------------------------------------------------
    # Obstacle drift
    # ------------------------------------------------------------------

    def _drift_obstacles(self, t: float, dt: float, bulb_count: int) -> None:
        """Update obstacle positions with meandering drift.

        Args:
            t: Current time in seconds.
            dt: Time delta since last frame.
            bulb_count: Total number of bulbs.
        """
        obs_sorted = sorted(self._obstacles, key=lambda o: o.pos)

        for idx, obs in enumerate(obs_sorted):
            # Change direction periodically.
            if t >= obs.next_turn:
                obs.drift_dir = -obs.drift_dir
                obs.next_turn = t + random.uniform(
                    _OBSTACLE_DIRECTION_INTERVAL * 0.5,
                    _OBSTACLE_DIRECTION_INTERVAL * 1.5,
                )

            # Compute movement.
            move = obs.drift_dir * self.obstacle_speed * dt
            new_pos = obs.pos + move

            # Clamp to valid range, respecting min gap from edges and
            # other obstacles.
            left_limit = float(_MIN_GAP_BULBS)
            right_limit = float(bulb_count - 1 - _MIN_GAP_BULBS)

            if idx > 0:
                left_limit = max(
                    left_limit,
                    obs_sorted[idx - 1].pos + _MIN_GAP_BULBS,
                )
            if idx < len(obs_sorted) - 1:
                right_limit = min(
                    right_limit,
                    obs_sorted[idx + 1].pos - _MIN_GAP_BULBS,
                )

            if new_pos < left_limit:
                new_pos = left_limit
                obs.drift_dir = 1
            elif new_pos > right_limit:
                new_pos = right_limit
                obs.drift_dir = -1

            obs.pos = new_pos

    # ------------------------------------------------------------------
    # Pulse emission
    # ------------------------------------------------------------------

    def _source_has_live_pulse(self, src: float) -> bool:
        """Check whether a source already has a live (non-absorbed) wavefront.

        Args:
            src: Source position in bulb units.

        Returns:
            True if src already owns a non-absorbed wavefront.
        """
        for wf in self._wavefronts:
            if wf.alive and not wf.absorbed and wf.source == src:
                return True
        return False

    def _emit_pulses(self, t: float, bulb_count: int) -> None:
        """Emit new wavefronts from sources that have no live pulse.

        Each source is limited to one active (non-absorbed) wavefront at a
        time. A new pulse is emitted only when the previous one from that
        source has been absorbed or has died, and the pulse interval has
        elapsed since the last global emission check.

        Args:
            t: Current time in seconds.
            bulb_count: Total number of bulbs.
        """
        if t - self._last_pulse_t < self.pulse_interval:
            return

        self._last_pulse_t = t

        for src in self._sources:
            if self._source_has_live_pulse(src):
                continue

            if src <= 0.5:
                # Left end -- emit rightward only.
                self._wavefronts.append(_Wavefront(src, +1, self.speed))
            elif src >= bulb_count - 1.5:
                # Right end -- emit leftward only.
                self._wavefronts.append(_Wavefront(src, -1, self.speed))
            else:
                # Middle source -- emit both directions.
                self._wavefronts.append(_Wavefront(src, +1, self.speed))
                self._wavefronts.append(_Wavefront(src, -1, self.speed))

    # ------------------------------------------------------------------
    # Wavefront update
    # ------------------------------------------------------------------

    def _update_wavefronts(self, dt: float, bulb_count: int) -> None:
        """Move wavefronts, stamp bulbs, handle reflection/absorption.

        When a wavefront enters a new bulb, that bulb's brightness is
        reset to 1.0. This is the only place bulbs get stamped.

        Args:
            dt: Time delta since last frame.
            bulb_count: Total number of bulbs.
        """
        obs_positions = sorted(o.pos for o in self._obstacles)
        half_obs = _OBSTACLE_WIDTH_BULBS / 2.0

        for wf in self._wavefronts:
            if not wf.alive:
                continue

            # Move.
            wf.pos += wf.direction * wf.speed * dt

            # Stamp the bulb under the wavefront head.
            bulb_idx = int(wf.pos)
            if not wf.absorbed and 0 <= bulb_idx < bulb_count:
                if bulb_idx != wf.last_bulb:
                    self._bulb_brightness[bulb_idx] = 1.0
                    wf.last_bulb = bulb_idx

            if wf.absorbed:
                wf.alive = False
                continue

            # Check reflection off obstacles.
            if not wf.reflected:
                for obs_pos in obs_positions:
                    if (
                        wf.direction > 0
                        and wf.pos >= obs_pos - half_obs
                        and wf.source < obs_pos
                    ):
                        wf.pos = obs_pos - half_obs
                        wf.direction = -1
                        wf.reflected = True
                        break
                    elif (
                        wf.direction < 0
                        and wf.pos <= obs_pos + half_obs
                        and wf.source > obs_pos
                    ):
                        wf.pos = obs_pos + half_obs
                        wf.direction = +1
                        wf.reflected = True
                        break

            # Check absorption at source (only after reflecting).
            if wf.reflected:
                if wf.direction < 0 and wf.pos <= wf.source:
                    wf.absorbed = True
                elif wf.direction > 0 and wf.pos >= wf.source:
                    wf.absorbed = True

            # Kill if off the string entirely.
            if wf.pos < -2 or wf.pos > bulb_count + 2:
                wf.alive = False

        # Prune dead wavefronts.
        self._wavefronts = [wf for wf in self._wavefronts if wf.alive]

    # ------------------------------------------------------------------
    # Bulb decay
    # ------------------------------------------------------------------

    def _decay_bulbs(self, dt: float) -> None:
        """Decay all stamped bulbs and remove dead ones.

        Args:
            dt: Time delta since last frame.
        """
        decay_rate = dt / max(0.01, self.decay)
        dead: list[int] = []
        for bulb_idx, bri in self._bulb_brightness.items():
            bri -= decay_rate
            if bri <= 0.0:
                dead.append(bulb_idx)
            else:
                self._bulb_brightness[bulb_idx] = bri
        for bulb_idx in dead:
            del self._bulb_brightness[bulb_idx]

    # ------------------------------------------------------------------
    # Frame generation
    # ------------------------------------------------------------------

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of the sonar effect.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        zone_count = ctx.pixel_count
        zpb = max(1, self.zones_per_bulb)
        bulb_count = max(1, zone_count // zpb)

        if not self._initialized:
            self._init_state(zone_count)
            self._prev_t = ctx.elapsed_s

        dt = ctx.elapsed_s - self._prev_t
        self._prev_t = ctx.elapsed_s

        # Clamp dt to avoid huge jumps on first frame or lag spikes.
        if dt > 0.5:
            dt = 0.05

        # Drift obstacles.
        self._drift_obstacles(ctx.elapsed_s, dt, bulb_count)

        # Recompute source positions after obstacle drift.
        self._update_sources(bulb_count)

        # Emit new pulses.
        self._emit_pulses(ctx.elapsed_s, bulb_count)

        # Advance wavefronts and decay bulbs.
        self._update_wavefronts(dt, bulb_count)
        self._decay_bulbs(dt)

        # --- Render to zone buffer ---
        brightness_buf: list[float] = [0.0] * zone_count

        # Paint wavefront heads at full brightness.
        for wf in self._wavefronts:
            zone_start = int(wf.pos * zpb)
            zone_end = zone_start + zpb
            for z in range(max(0, zone_start), min(zone_count, zone_end)):
                brightness_buf[z] = min(1.0, brightness_buf[z] + self.brightness)

        # Paint decaying bulbs.
        for bulb_idx, bri_frac in self._bulb_brightness.items():
            bri = bri_frac * self.brightness
            zone_start = bulb_idx * zpb
            zone_end = zone_start + zpb
            for z in range(max(0, zone_start), min(zone_count, zone_end)):
                brightness_buf[z] = min(1.0, brightness_buf[z] + bri)

        # Build the output color buffer.
        colors: list[HSBK] = []
        half_obs_zones = max(1, (_OBSTACLE_WIDTH_BULBS * zpb) // 2)

        # Pre-compute obstacle zone ranges for painting.
        obs_zones: set[int] = set()
        for obs in self._obstacles:
            center_zone = int(obs.pos * zpb)
            for z in range(
                center_zone - half_obs_zones, center_zone + half_obs_zones + 1
            ):
                if 0 <= z < zone_count:
                    obs_zones.add(z)

        for z in range(zone_count):
            if z in obs_zones:
                # Obstacle zone -- colored marker.
                colors.append(
                    HSBK(
                        hue=round(self.obstacle_hue),
                        saturation=1.0,
                        brightness=self.obstacle_brightness,
                        kelvin=self.kelvin,
                    )
                )
            else:
                # Wavefront / background zone.
                colors.append(
                    HSBK(
                        hue=0,
                        saturation=0.0,
                        brightness=max(0.0, min(1.0, brightness_buf[z])),
                        kelvin=self.kelvin,
                    )
                )

        return colors

    # ------------------------------------------------------------------
    # Effect protocol
    # ------------------------------------------------------------------

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        Args:
            _light: The device being powered on (unused)

        Returns:
            White at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=0,
            saturation=0.0,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with Sonar effect.

        Sonar requires multizone capability for zone-based animation.

        Args:
            light: The light device to check

        Returns:
            True if light has multizone support, False otherwise
        """
        if light.capabilities is None:
            await light._ensure_capabilities()
        return light.capabilities.has_multizone if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Sonar can inherit prestate from another Sonar effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectSonar, False otherwise
        """
        return isinstance(other, EffectSonar)

    def __repr__(self) -> str:
        """String representation of Sonar effect."""
        return (
            f"EffectSonar(speed={self.speed}, decay={self.decay}, "
            f"pulse_interval={self.pulse_interval}, "
            f"obstacle_speed={self.obstacle_speed}, "
            f"obstacle_hue={self.obstacle_hue}, "
            f"obstacle_brightness={self.obstacle_brightness}, "
            f"brightness={self.brightness}, kelvin={self.kelvin}, "
            f"zones_per_bulb={self.zones_per_bulb}, power_on={self.power_on})"
        )
