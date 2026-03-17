"""Standing wave effect -- simulates a vibrating string.

Bulbs oscillate between two colors in a standing wave pattern with fixed
nodes. Adjacent segments swing in opposite directions, just like a real
vibrating string.

displacement(x, t) = sin(nodes * pi * x / L) * sin(2pi * t / speed)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import MAX_KELVIN, MIN_KELVIN
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect

if TYPE_CHECKING:
    from lifx.devices.light import Light

# Full cycle constant for temporal oscillation.
_TWO_PI: float = 2.0 * math.pi

# Brightness split: nodes dim to this fraction of max, antinodes add the rest.
# 30% base + 70% displacement-scaled = 100% at full displacement.
_BRI_BASE_FRAC: float = 0.3
_BRI_DISP_FRAC: float = 0.7


class EffectWave(FrameEffect):
    """Standing wave -- bulbs vibrate between two colors with fixed nodes.

    The spatial component ``sin(nodes * pi * x / L)`` creates fixed
    zero-crossing points (nodes) along the string.  The temporal
    component ``sin(2pi * t / speed)`` makes segments between nodes
    swing back and forth in alternating directions.

    Attributes:
        speed: Seconds per oscillation cycle
        nodes: Number of stationary nodes along the string
        hue1: Color 1 hue in degrees (0-360, negative displacement)
        hue2: Color 2 hue in degrees (0-360, positive displacement)
        saturation1: Color 1 saturation (0.0-1.0)
        saturation2: Color 2 saturation (0.0-1.0)
        brightness: Overall brightness (0.0-1.0)
        drift: Spatial drift in degrees per second (0 = pure standing wave)
        kelvin: Color temperature (1500-9000)
        zones_per_bulb: Number of physical zones per logical bulb

    Example:
        ```python
        effect = EffectWave(speed=4.0, nodes=3, hue1=0, hue2=240)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 4.0,
        nodes: int = 2,
        hue1: int = 0,
        hue2: int = 240,
        saturation1: float = 1.0,
        saturation2: float = 1.0,
        brightness: float = 0.8,
        drift: float = 0.0,
        kelvin: int = 3500,
        zones_per_bulb: int = 1,
    ) -> None:
        """Initialize standing wave effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Seconds per oscillation cycle, must be > 0 (default 4.0)
            nodes: Number of stationary nodes, must be >= 1 (default 2)
            hue1: Color 1 hue 0-360 degrees (default 0, red)
            hue2: Color 2 hue 0-360 degrees (default 240, blue)
            saturation1: Color 1 saturation 0.0-1.0 (default 1.0)
            saturation2: Color 2 saturation 0.0-1.0 (default 1.0)
            brightness: Overall brightness 0.0-1.0 (default 0.8)
            drift: Spatial drift degrees/second (default 0.0)
            kelvin: Color temperature 1500-9000 (default 3500)
            zones_per_bulb: Physical zones per logical bulb (default 1)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if nodes < 1:
            raise ValueError(f"Nodes must be >= 1, got {nodes}")
        if not (0 <= hue1 <= 360):
            raise ValueError(f"hue1 must be 0-360, got {hue1}")
        if not (0 <= hue2 <= 360):
            raise ValueError(f"hue2 must be 0-360, got {hue2}")
        if not (0.0 <= saturation1 <= 1.0):
            raise ValueError(f"saturation1 must be 0.0-1.0, got {saturation1}")
        if not (0.0 <= saturation2 <= 1.0):
            raise ValueError(f"saturation2 must be 0.0-1.0, got {saturation2}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.nodes = nodes
        self.hue1 = hue1
        self.hue2 = hue2
        self.saturation1 = saturation1
        self.saturation2 = saturation2
        self.brightness = brightness
        self.drift = drift
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "wave"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of the standing wave.

        Each zone computes a displacement from the product of spatial
        and temporal sine waves, then maps that to a color blend and
        brightness level.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        # Build endpoint HSBK colors for the two wave extremes.
        color1 = HSBK(
            hue=self.hue1,
            saturation=self.saturation1,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )
        color2 = HSBK(
            hue=self.hue2,
            saturation=self.saturation2,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )

        # Temporal oscillation swings the entire pattern between -1 and +1.
        temporal: float = math.sin(_TWO_PI * ctx.elapsed_s / self.speed)

        # Spatial drift: convert degrees/second to radians accumulated so far.
        drift_rad: float = math.radians(self.drift) * ctx.elapsed_s

        # Compute logical bulb count
        bulb_count = max(ctx.pixel_count // self.zones_per_bulb, 1)

        # Render to logical bulbs
        bulb_colors: list[HSBK] = []
        for i in range(bulb_count):
            # Use bulb index so all zones within a polychrome bulb share
            # the same wave position (zones_per_bulb awareness).
            # Normalized position along the string (0.0 to 1.0).
            x: float = i / (bulb_count - 1) if bulb_count > 1 else 0.0

            # Spatial component: sin(nodes * pi * x) creates fixed nodes
            # where the string doesn't move. For a single-bulb device
            # x=0 is always a node (sin(0)=0), so force full antinode
            # amplitude so the temporal oscillation drives the output.
            spatial: float = (
                1.0
                if bulb_count == 1
                else math.sin(self.nodes * math.pi * x + drift_rad)
            )

            # Combined displacement: -1.0 to +1.0.
            displacement: float = spatial * temporal

            # Map displacement to color blend factor.
            # -1 = pure color1, 0 = midpoint, +1 = pure color2.
            blend: float = (displacement + 1.0) / 2.0

            # Interpolate through Oklab perceptual color space.
            blended = color1.lerp_oklab(color2, blend)

            # Brightness peaks at antinodes (large displacement), dims at
            # nodes where displacement is near zero. Override the blended
            # brightness with displacement-based modulation.
            disp_abs = abs(displacement)
            bri = self.brightness * (_BRI_BASE_FRAC + _BRI_DISP_FRAC * disp_abs)

            bulb_colors.append(
                HSBK(
                    hue=blended.hue,
                    saturation=blended.saturation,
                    brightness=bri,
                    kelvin=self.kelvin,
                )
            )

        # Expand logical bulbs to physical zones
        if self.zones_per_bulb == 1:
            return bulb_colors

        colors: list[HSBK] = []
        for color in bulb_colors:
            colors.extend([color] * self.zones_per_bulb)

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
            Midpoint color at zero brightness for smooth fade-in
        """
        color1 = HSBK(
            hue=self.hue1,
            saturation=self.saturation1,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )
        color2 = HSBK(
            hue=self.hue2,
            saturation=self.saturation2,
            brightness=self.brightness,
            kelvin=self.kelvin,
        )
        midpoint = color1.lerp_oklab(color2, 0.5)
        return HSBK(
            hue=midpoint.hue,
            saturation=midpoint.saturation,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with wave effect.

        Wave requires color capability to manipulate hue/saturation.

        Args:
            light: The light device to check

        Returns:
            True if light has color support, False otherwise
        """
        if light.capabilities is None:
            await light._ensure_capabilities()
        return light.capabilities.has_color if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Wave can inherit prestate from another Wave effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectWave, False otherwise
        """
        return isinstance(other, EffectWave)

    def __repr__(self) -> str:
        """String representation of Wave effect."""
        return (
            f"EffectWave(speed={self.speed}, nodes={self.nodes}, "
            f"hue1={self.hue1}, hue2={self.hue2}, "
            f"saturation1={self.saturation1}, saturation2={self.saturation2}, "
            f"brightness={self.brightness}, drift={self.drift}, "
            f"kelvin={self.kelvin}, zones_per_bulb={self.zones_per_bulb}, "
            f"power_on={self.power_on})"
        )
