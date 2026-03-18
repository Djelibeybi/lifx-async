"""Embers effect -- fire simulation via heat diffusion.

A 1D heat buffer simulates rising embers. Each frame:

1. **Convection** -- heat shifts upward by one cell periodically,
   simulating buoyancy.
2. **Diffusion + cooling** -- each cell averages with its neighbours
   and is multiplied by a cooling factor.
3. **Turbulence** -- random per-cell flicker adds variation.
4. **Heat injection** -- random heat is injected at the bottom zones,
   with occasional larger bursts.

Heat (0.0-1.0) maps to a color gradient:
    0.0  -> black (cold/dead)
    0.33 -> deep red
    0.66 -> orange
    1.0  -> bright yellow
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
# Color gradient waypoints (temperature -> hue in degrees)
# ---------------------------------------------------------------------------
_HUE_RED: float = 0.0
_HUE_ORANGE: float = 30.0
_HUE_YELLOW: float = 50.0

# Temperature thresholds for gradient mapping.
_THRESH_BLACK: float = 0.05  # Below this -> black (invisible)
_THRESH_RED: float = 0.33  # Below this -> black-to-red ramp
_THRESH_ORANGE: float = 0.66  # Below this -> red-to-orange ramp
# Above _THRESH_ORANGE -> orange-to-yellow ramp

# ---------------------------------------------------------------------------
# Simulation constants
# ---------------------------------------------------------------------------

# Convection: shift the heat buffer upward every N frames.
_CONVECTION_FRAMES: int = 3

# Burst: probability per frame of a large heat injection (a visible puff).
_BURST_PROBABILITY: float = 0.06
_BURST_HEAT: float = 0.9
_BURST_RADIUS: int = 2

# Maximum dt clamp to avoid huge jumps after pauses.
_MAX_DT: float = 0.5


def _heat_to_hsbk(heat: float, brightness: float, kelvin: int) -> HSBK:
    """Map a heat value (0.0-1.0) to an HSBK color on the ember gradient.

    The gradient proceeds: black -> deep red -> orange -> bright yellow.

    Args:
        heat: Normalised heat, clamped to [0, 1].
        brightness: Maximum brightness (0.0-1.0).
        kelvin: Color temperature in Kelvin.

    Returns:
        An HSBK color.
    """
    if heat < _THRESH_BLACK:
        return HSBK(hue=0, saturation=1.0, brightness=0.0, kelvin=kelvin)

    if heat < _THRESH_RED:
        # Black -> deep red.
        frac = (heat - _THRESH_BLACK) / (_THRESH_RED - _THRESH_BLACK)
        hue = int(_HUE_RED)
        sat = 1.0
        bri = brightness * 0.4 * frac
    elif heat < _THRESH_ORANGE:
        # Deep red -> orange.
        frac = (heat - _THRESH_RED) / (_THRESH_ORANGE - _THRESH_RED)
        hue_deg = _HUE_RED + (_HUE_ORANGE - _HUE_RED) * frac
        hue = int(hue_deg)
        sat = 1.0
        bri = brightness * (0.4 + 0.3 * frac)
    else:
        # Orange -> bright yellow-white.
        frac = min((heat - _THRESH_ORANGE) / (1.0 - _THRESH_ORANGE), 1.0)
        hue_deg = _HUE_ORANGE + (_HUE_YELLOW - _HUE_ORANGE) * frac
        hue = int(hue_deg)
        # Saturation drops toward white at peak temperature.
        sat = 1.0 - 0.3 * frac
        bri = brightness * (0.7 + 0.3 * frac)

    bri = max(0.0, min(1.0, bri))

    return HSBK(hue=hue, saturation=sat, brightness=bri, kelvin=kelvin)


class EffectEmbers(FrameEffect):
    """Embers -- fire simulation via heat diffusion.

    Heat is injected randomly at the bottom of the strip each frame.
    A 1D diffusion kernel with a cooling factor makes heat drift upward,
    dim, and die -- like glowing embers in a chimney.

    Attributes:
        intensity: Probability of heat injection per frame (0.0-1.0)
        cooling: Cooling factor per diffusion step (0.0-1.0)
        turbulence: Random per-cell flicker amplitude (0.0-0.3)
        brightness: Overall brightness (0.0-1.0)
        kelvin: Color temperature (1500-9000)
        zones_per_bulb: Number of physical zones per logical bulb

    Example:
        ```python
        effect = EffectEmbers(intensity=0.7, cooling=0.15, brightness=0.8)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        intensity: float = 0.5,
        cooling: float = 0.15,
        turbulence: float = 0.3,
        brightness: float = 0.8,
        kelvin: int = 3500,
        zones_per_bulb: int = 1,
    ) -> None:
        """Initialize Embers fire simulation effect.

        Args:
            power_on: Power on devices if off (default True)
            intensity: Probability of heat injection per frame, 0.0-1.0
                (default 0.5)
            cooling: Cooling factor per diffusion step, 0.80-0.999. Higher
                values mean slower cooling (default 0.15, mapped to 0.85
                internally as 1-cooling)
            turbulence: Random per-cell flicker amplitude, 0.0-0.3
                (default 0.3)
            brightness: Overall brightness, 0.0-1.0 (default 0.8)
            kelvin: Color temperature 1500-9000 (default 3500)
            zones_per_bulb: Physical zones per logical bulb (default 1)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if not (0.0 <= intensity <= 1.0):
            raise ValueError(f"Intensity must be 0.0-1.0, got {intensity}")
        if not (0.0 <= cooling <= 1.0):
            raise ValueError(f"Cooling must be 0.0-1.0, got {cooling}")
        if not (0.0 <= turbulence <= 0.3):
            raise ValueError(f"Turbulence must be 0.0-0.3, got {turbulence}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.intensity = intensity
        self.cooling = cooling
        self.turbulence = turbulence
        self.brightness = brightness
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb

        # Stateful simulation buffers (lazily initialized)
        self._heat: list[float] = []
        self._frame_count: int = 0
        self._last_elapsed: float | None = None

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "embers"

    @property
    def _cooling_factor(self) -> float:
        """Derive the cooling multiplier from the user-facing cooling param.

        cooling=0.0 means no cooling (factor=1.0), cooling=1.0 means
        maximum cooling (factor=0.0). The default 0.15 gives factor=0.85.
        """
        return 1.0 - self.cooling

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate one frame of the embers fire simulation.

        Performs convection, diffusion with cooling, turbulence, and heat
        injection, then maps temperature values to the ember color gradient.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        zpb = self.zones_per_bulb
        bulb_count = max(ctx.pixel_count // zpb, 1)
        self._frame_count += 1

        # Lazily initialise or resize the heat buffer to match bulb count.
        if len(self._heat) != bulb_count:
            self._heat = [0.0] * bulb_count

        heat = self._heat

        # --- 1. Convection: shift heat upward periodically ----------------
        if self._frame_count % _CONVECTION_FRAMES == 0:
            for i in range(bulb_count - 1, 0, -1):
                heat[i] = heat[i - 1]
            heat[0] = 0.0

        # --- 2. Inject heat at the bottom ---------------------------------
        if random.random() < self.intensity:
            heat[0] = min(heat[0] + random.uniform(0.5, 1.0), 1.0)

        # --- 3. Occasional burst: a puff of heat at a random low position -
        if random.random() < _BURST_PROBABILITY:
            center = random.randint(0, max(0, bulb_count // 3))
            for j in range(
                max(0, center - _BURST_RADIUS),
                min(bulb_count, center + _BURST_RADIUS + 1),
            ):
                heat[j] = min(heat[j] + _BURST_HEAT, 1.0)

        # --- 4. Diffusion + cooling: smooth and decay ---------------------
        cooling_factor = self._cooling_factor
        new_heat: list[float] = [0.0] * bulb_count
        for i in range(bulb_count):
            below = heat[i - 1] if i > 0 else 0.0
            above = heat[i + 1] if i < bulb_count - 1 else 0.0
            new_heat[i] = (below + heat[i] + above) / 3.0 * cooling_factor

        # --- 5. Turbulence: random per-cell flicker -----------------------
        turb = self.turbulence
        if turb > 0.0:
            for i in range(bulb_count):
                new_heat[i] += random.uniform(-turb, turb)

        # Clamp to [0, 1].
        self._heat = [max(0.0, min(1.0, h)) for h in new_heat]

        # --- 6. Map temperature to color and expand to zones --------------
        bulb_colors: list[HSBK] = []
        for i in range(bulb_count):
            bulb_colors.append(
                _heat_to_hsbk(self._heat[i], self.brightness, self.kelvin)
            )

        # Expand logical bulbs to physical zones
        if zpb == 1:
            colors = bulb_colors
        else:
            colors = []
            for color in bulb_colors:
                colors.extend([color] * zpb)

        # Trim or pad to exact pixel_count
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
            Deep red at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=0,
            saturation=1.0,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with Embers effect.

        Embers requires color capability. Works on single lights and
        multizone strips. Matrix devices are not supported.

        Args:
            light: The light device to check

        Returns:
            True if light has color support and is not a matrix device
        """
        if light.capabilities is None:
            await light.ensure_capabilities()
        if light.capabilities is None:
            return False
        # Embers does not support matrix devices
        if light.capabilities.has_matrix:
            return False
        return light.capabilities.has_color

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Embers can inherit prestate from another Embers effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectEmbers, False otherwise
        """
        return isinstance(other, EffectEmbers)

    def __repr__(self) -> str:
        """String representation of Embers effect."""
        return (
            f"EffectEmbers(intensity={self.intensity}, cooling={self.cooling}, "
            f"turbulence={self.turbulence}, brightness={self.brightness}, "
            f"kelvin={self.kelvin}, zones_per_bulb={self.zones_per_bulb}, "
            f"power_on={self.power_on})"
        )
