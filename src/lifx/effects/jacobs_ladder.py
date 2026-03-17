"""Jacob's Ladder (electric arcs) effect.

Arc pairs drift along the strip. Each arc has two electrodes (bright
blue-white spots) separated by a gap. Between the electrodes, a flickering
arc appears with crackle spikes. Arcs break off at strip ends and reform
at the entry. At least one arc is always visible.

Inspired by the classic Frankenstein laboratory prop.
"""

from __future__ import annotations

import math
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

# Arc color: electric blue-white.
_ARC_HUE_DEG: int = 220
_ARC_SAT_FRAC: float = 0.45
_ELECTRODE_SAT_FRAC: float = 0.15

# Noise: smooth random walk for gap modulation.
_NOISE_STEP: float = 0.12

# Minimum gap between electrodes in bulbs.
_GAP_MIN_BULBS: int = 2
# Maximum gap as fraction of string length.
_GAP_MAX_FRAC: float = 0.4

# Flicker: per-frame random brightness variation for the arc.
_FLICKER_MIN: float = 0.15
_FLICKER_MAX: float = 0.85

# Surge: probability per arc per frame of a full-intensity blaze.
_SURGE_PROBABILITY: float = 0.10
_SURGE_INTENSITY: float = 1.0

# Crackle: probability per bulb per frame of a bright white spike.
_CRACKLE_PROBABILITY: float = 0.12
_CRACKLE_SAT_FRAC: float = 0.05

# Per-bulb flicker range within the arc body.
_BULB_FLICKER_MIN: float = 0.25
_BULB_FLICKER_MAX: float = 1.0

# Electrode glow radius in bulbs.
_ELECTRODE_RADIUS: float = 1.5


class _ArcPair:
    """State for one pair of electrodes with an arc between them."""

    __slots__ = ("position", "gap", "gap_target", "speed", "direction")

    def __init__(
        self,
        position: float,
        gap: float,
        speed: float,
        direction: int,
    ) -> None:
        """Create an arc pair.

        Args:
            position: Center position in bulb units.
            gap: Current gap between electrodes in bulb units.
            speed: Drift speed in bulbs per frame.
            direction: +1 = drift toward high end, -1 = drift toward low end.
        """
        self.position: float = position
        self.gap: float = gap
        self.gap_target: float = gap
        self.speed: float = speed
        self.direction: int = direction

    def step(self, gap_min: int, gap_max: float) -> None:
        """Advance the arc one frame.

        Args:
            gap_min: Minimum electrode gap in bulbs.
            gap_max: Maximum electrode gap in bulbs.
        """
        self.position += self.speed * self.direction

        # Smooth random walk for gap: pick a new target occasionally,
        # then ease toward it.
        if random.random() < 0.08:
            self.gap_target = random.uniform(gap_min, gap_max)
        self.gap += (self.gap_target - self.gap) * _NOISE_STEP
        self.gap = max(gap_min, min(gap_max, self.gap))

    def is_off_string(self, bulb_count: int) -> bool:
        """Return True if the entire arc has scrolled off the string."""
        half: float = self.gap / 2.0
        if self.direction > 0:
            return (self.position - half) >= bulb_count
        return (self.position + half) < 0

    def left_edge(self) -> float:
        """Left electrode position in bulb units."""
        return self.position - self.gap / 2.0

    def right_edge(self) -> float:
        """Right electrode position in bulb units."""
        return self.position + self.gap / 2.0


class EffectJacobsLadder(FrameEffect):
    """Jacob's Ladder -- rising electric arcs between electrode pairs.

    Arc pairs drift along the strip, break off at the end, and reform.
    The electrode gap breathes with smooth noise. Multiple arcs can
    coexist, and at least one is always visible.

    Attributes:
        speed: Arc drift speed in bulbs per frame (0.02-1.0)
        arcs: Target number of simultaneous arc pairs (1-5)
        gap: Base gap between electrodes in bulbs (2-12)
        brightness: Overall brightness 0.0-1.0
        kelvin: Color temperature 1500-9000
        zones_per_bulb: Physical zones per logical bulb

    Example:
        ```python
        effect = EffectJacobsLadder(speed=0.5, arcs=2, gap=5)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 0.5,
        arcs: int = 2,
        gap: int = 5,
        brightness: float = 0.8,
        kelvin: int = 6500,
        zones_per_bulb: int = 1,
    ) -> None:
        """Initialize Jacob's Ladder effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Arc drift speed in bulbs per frame, must be 0.02-1.0 (default 0.5)
            arcs: Target number of simultaneous arc pairs, must be 1-5 (default 2)
            gap: Base gap between electrodes in bulbs, must be 2-12 (default 5)
            brightness: Overall brightness 0.0-1.0 (default 0.8)
            kelvin: Color temperature 1500-9000 (default 6500)
            zones_per_bulb: Physical zones per logical bulb, must be >= 1 (default 1)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if not (0.02 <= speed <= 1.0):
            raise ValueError(f"Speed must be 0.02-1.0, got {speed}")
        if not (1 <= arcs <= 5):
            raise ValueError(f"Arcs must be 1-5, got {arcs}")
        if not (2 <= gap <= 12):
            raise ValueError(f"Gap must be 2-12, got {gap}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.arcs = arcs
        self.gap = gap
        self.brightness = brightness
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb

        # Stateful: arc positions and flicker state, lazily initialized.
        self._arc_pairs: list[_ArcPair] = []
        self._initialized: bool = False

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "jacobs_ladder"

    def _spawn_arc(self, bulb_count: int) -> _ArcPair:
        """Create a new arc pair at the entry end of the string.

        Args:
            bulb_count: Total bulbs on the string.

        Returns:
            A new _ArcPair positioned at the entry edge.
        """
        gap_val: float = float(self.gap) + random.uniform(-1.0, 1.0)
        gap_val = max(_GAP_MIN_BULBS, gap_val)
        half: float = gap_val / 2.0

        # Arcs always drift forward (toward high end).
        pos: float = -half + 1.0

        return _ArcPair(pos, gap_val, self.speed, 1)

    def _ensure_initialized(self, bulb_count: int) -> None:
        """Lazily initialize arc state on first frame.

        Args:
            bulb_count: Total logical bulbs on the string.
        """
        if self._initialized:
            return
        self._initialized = True

        # Spawn initial arc partway onto the string so it's immediately visible.
        arc = self._spawn_arc(bulb_count)
        arc.position = float(bulb_count) * 0.3
        self._arc_pairs.append(arc)

        # Spawn remaining arcs at the entry edge.
        while len(self._arc_pairs) < self.arcs:
            self._arc_pairs.append(self._spawn_arc(bulb_count))

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of the Jacob's Ladder effect.

        Renders electrode glows, flickering arcs, surges, and crackle
        spikes across the strip.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        zpb: int = self.zones_per_bulb
        bulb_count: int = max(ctx.pixel_count // zpb, 1)

        self._ensure_initialized(bulb_count)

        gap_max: float = min(
            float(bulb_count) * _GAP_MAX_FRAC,
            float(self.gap) * 2.0,
        )

        # Ensure minimum arc count.
        while len(self._arc_pairs) < self.arcs:
            self._arc_pairs.append(self._spawn_arc(bulb_count))

        # Step each arc and remove dead ones.
        for arc in self._arc_pairs:
            arc.step(_GAP_MIN_BULBS, gap_max)

        self._arc_pairs = [
            a for a in self._arc_pairs if not a.is_off_string(bulb_count)
        ]

        # Guarantee at least one arc is always visible.
        if not self._arc_pairs:
            self._arc_pairs.append(self._spawn_arc(bulb_count))

        # Render bulb brightness buffer. Start with black.
        bulb_hue: list[int] = [0] * bulb_count
        bulb_sat: list[float] = [0.0] * bulb_count
        bulb_bri: list[float] = [0.0] * bulb_count

        for arc in self._arc_pairs:
            left: float = arc.left_edge()
            right: float = arc.right_edge()

            # Per-arc flicker: random brightness multiplier.
            is_surge: bool = random.random() < _SURGE_PROBABILITY
            if is_surge:
                flicker: float = _SURGE_INTENSITY
            else:
                flicker = random.uniform(_FLICKER_MIN, _FLICKER_MAX)

            for b in range(bulb_count):
                fb: float = float(b)

                # Distance from left and right electrodes.
                d_left: float = abs(fb - left)
                d_right: float = abs(fb - right)

                # Electrode glow: bright within ~1.5 bulbs of each electrode.
                electrode_intensity: float = 0.0
                if d_left < _ELECTRODE_RADIUS:
                    electrode_intensity = max(
                        electrode_intensity, 1.0 - d_left / _ELECTRODE_RADIUS
                    )
                if d_right < _ELECTRODE_RADIUS:
                    electrode_intensity = max(
                        electrode_intensity, 1.0 - d_right / _ELECTRODE_RADIUS
                    )
                if electrode_intensity > 0 and is_surge:
                    electrode_intensity = 1.0

                # Arc glow: between the two electrodes.
                arc_intensity: float = 0.0
                is_crackle: bool = False
                if left <= fb <= right:
                    span: float = right - left
                    if span > 0:
                        normalized: float = (fb - left) / span
                        # Sine-shaped profile: bright in center, dim at edges.
                        arc_intensity = math.sin(normalized * math.pi)
                        arc_intensity *= flicker
                        # Per-bulb flicker for organic look.
                        arc_intensity *= random.uniform(
                            _BULB_FLICKER_MIN, _BULB_FLICKER_MAX
                        )
                        # Crackle: random bright white spike.
                        if random.random() < _CRACKLE_PROBABILITY:
                            arc_intensity = 1.0
                            is_crackle = True

                # Combine: electrodes are brighter and whiter than the arc.
                if electrode_intensity > 0:
                    intensity: float = electrode_intensity
                    sat: float = _ELECTRODE_SAT_FRAC
                elif arc_intensity > 0:
                    intensity = arc_intensity * 0.85
                    sat = _CRACKLE_SAT_FRAC if is_crackle else _ARC_SAT_FRAC
                else:
                    continue

                # Additive blend with existing buffer.
                bulb_bri[b] = min(1.0, bulb_bri[b] + intensity)
                if intensity > bulb_sat[b]:
                    bulb_hue[b] = _ARC_HUE_DEG
                    bulb_sat[b] = sat

        # Map bulb buffer to zone colors.
        bulb_colors: list[HSBK] = []
        for b in range(bulb_count):
            bri_val: float = bulb_bri[b]
            if bri_val < 0.01:
                bulb_colors.append(
                    HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=self.kelvin)
                )
            else:
                bulb_colors.append(
                    HSBK(
                        hue=bulb_hue[b],
                        saturation=bulb_sat[b],
                        brightness=min(self.brightness * bri_val, 1.0),
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
            Arc color at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=_ARC_HUE_DEG,
            saturation=_ARC_SAT_FRAC,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with Jacob's Ladder effect.

        Jacob's Ladder requires multizone capability (strips/beams).

        Args:
            light: The light device to check

        Returns:
            True if light has multizone support, False otherwise
        """
        if light.capabilities is None:
            await light._ensure_capabilities()
        return light.capabilities.has_multizone if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Jacob's Ladder can inherit prestate from another Jacob's Ladder.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectJacobsLadder, False otherwise
        """
        return isinstance(other, EffectJacobsLadder)

    def __repr__(self) -> str:
        """String representation of Jacob's Ladder effect."""
        return (
            f"EffectJacobsLadder(speed={self.speed}, arcs={self.arcs}, "
            f"gap={self.gap}, brightness={self.brightness}, "
            f"kelvin={self.kelvin}, zones_per_bulb={self.zones_per_bulb}, "
            f"power_on={self.power_on})"
        )
