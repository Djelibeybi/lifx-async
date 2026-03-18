"""Newton's Cradle pendulum simulation with Phong-shaded spheres.

Models the classic Newton's Cradle: a row of steel balls suspended side by
side on strings. The outermost balls swing alternately -- the right ball
swings out and returns, strikes the row, and the left ball swings out in
turn. Middle balls remain stationary throughout.

Each ball is rendered as a 3-D sphere using a Phong illumination model:

    I = ambient
      + diffuse * max(0, N . L)              (Lambertian diffuse)
      + specular * max(0, R . V)^shininess    (Phong specular)

The light source is fixed at 25 degrees from vertical toward the left
(upper-left illumination), so the specular highlight sits on the
left-of-centre of each ball. The specular bloom blends toward pure
white via HSB interpolation for a smooth colour transition from ball
surface to hot-spot.
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Light source direction -- unit vector FROM surface point TO light.
# 25 degrees from vertical toward the left gives a classic upper-left
# studio look.
_LIGHT_ANGLE_RAD: float = math.radians(25.0)
LIGHT_X: float = -math.sin(_LIGHT_ANGLE_RAD)  # ~ -0.423 (leftward)
LIGHT_Y: float = math.cos(_LIGHT_ANGLE_RAD)  # ~ 0.906 (upward)

# View direction: viewer is directly in front (0, 1).
VIEW_Y: float = 1.0

# Phong illumination weights.
AMBIENT_FACTOR: float = 0.10
DIFFUSE_FACTOR: float = 0.65
SPECULAR_FACTOR: float = 0.80

# Skip the blend call for near-zero specular (hot-path optimisation).
SPECULAR_THRESHOLD: float = 0.02

# Minimum ball width in zones.
MIN_BALL_WIDTH: int = 3

# Sentinel value meaning "compute automatically".
AUTO: int = 0


class EffectNewtonsCradle(FrameEffect):
    """Newton's Cradle -- alternating pendulum balls with Phong sphere shading.

    Five steel-coloured balls hang in a row separated by gaps. The
    rightmost and leftmost balls swing alternately; the middle balls
    stay still. Each ball is rendered as a 3-D sphere so the specular
    highlight glides across its surface as it swings.

    Attributes:
        num_balls: Number of balls in the cradle (2-10)
        ball_width: Zones per ball; 0 = auto-size to fit strip
        speed: Full period in seconds (left-swing + right-swing)
        hue: Ball base hue in degrees (0-360)
        saturation: Ball base saturation (0.0-1.0)
        brightness: Maximum ball brightness (0.0-1.0)
        shininess: Phong specular exponent (1-100)
        kelvin: Color temperature (1500-9000)
        zones_per_bulb: Physical zones per logical bulb

    Example:
        ```python
        effect = EffectNewtonsCradle(num_balls=5, speed=2.0)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        num_balls: int = 5,
        ball_width: int = 0,
        speed: float = 2.0,
        hue: int = 0,
        saturation: float = 0.0,
        brightness: float = 0.8,
        shininess: int = 60,
        kelvin: int = 4500,
        zones_per_bulb: int = 1,
    ) -> None:
        """Initialize Newton's Cradle effect.

        Args:
            power_on: Power on devices if off (default True)
            num_balls: Number of balls (2-10, default 5)
            ball_width: Zones per ball; 0 = auto-size (default 0)
            speed: Full cycle period in seconds, must be > 0 (default 2.0)
            hue: Ball base hue 0-360 degrees (default 0)
            saturation: Ball base saturation 0.0-1.0 (default 0.0, steel)
            brightness: Maximum ball brightness 0.0-1.0 (default 0.8)
            shininess: Phong specular exponent 1-100 (default 60)
            kelvin: Color temperature 1500-9000 (default 4500)
            zones_per_bulb: Physical zones per logical bulb (default 1)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if not (2 <= num_balls <= 10):
            raise ValueError(f"num_balls must be 2-10, got {num_balls}")
        if ball_width < 0 or ball_width > 30:
            raise ValueError(f"ball_width must be 0-30, got {ball_width}")
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if not (0 <= hue <= 360):
            raise ValueError(f"Hue must be 0-360, got {hue}")
        if not (0.0 <= saturation <= 1.0):
            raise ValueError(f"Saturation must be 0.0-1.0, got {saturation}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (1 <= shininess <= 100):
            raise ValueError(f"Shininess must be 1-100, got {shininess}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.num_balls = num_balls
        self.ball_width = ball_width
        self.speed = speed
        self.hue = hue
        self.saturation = saturation
        self.brightness = brightness
        self.shininess = shininess
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "newtons_cradle"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of the Newton's Cradle.

        Computes ball positions from the pendulum phase, then for each
        zone determines which ball (if any) covers it and applies Phong
        shading in the ball's local coordinate frame.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        # Compute logical bulb count
        bulb_count = max(ctx.pixel_count // self.zones_per_bulb, 1)

        n = self.num_balls

        # Resolve layout -- may depend on zone_count.
        bw, amp = self._resolve_layout(bulb_count, n)

        # At-rest ball centres (float zone positions).
        rest = self._rest_centres(bulb_count, n, bw)

        # --- Pendulum phase ---
        # Phase 0 -> 0.5: rightmost ball swings rightward and returns.
        # Phase 0.5 -> 1.0: leftmost ball swings leftward and returns.
        phase = (ctx.elapsed_s % self.speed) / self.speed

        centres = list(rest)
        if phase < 0.5:
            # Right ball swinging out to the right.
            centres[-1] = rest[-1] + amp * math.sin(phase * 2.0 * math.pi)
        else:
            # Left ball swinging out to the left.
            centres[0] = rest[0] - amp * math.sin((phase - 0.5) * 2.0 * math.pi)

        # --- Rasterise to logical bulbs ---
        half = bw / 2.0
        dead = HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=self.kelvin)
        bulb_colors: list[HSBK] = [dead] * bulb_count

        for cx in centres:
            lo = max(0, int(math.floor(cx - half)))
            hi = min(bulb_count, int(math.ceil(cx + half)) + 1)

            for z in range(lo, hi):
                # Normalised horizontal position: -1 (left) to +1 (right).
                x_rel = (z - cx) / half
                if abs(x_rel) >= 1.0:
                    continue
                shaded = self._shade(x_rel)
                # Keep the brighter color when balls overlap.
                if shaded.brightness > bulb_colors[z].brightness:
                    bulb_colors[z] = shaded

        # Expand logical bulbs to physical zones
        if self.zones_per_bulb == 1:
            colors = bulb_colors
        else:
            colors = []
            for color in bulb_colors:
                colors.extend([color] * self.zones_per_bulb)

        # Trim or pad to exact pixel_count
        if len(colors) < ctx.pixel_count:
            colors.extend([colors[-1]] * (ctx.pixel_count - len(colors)))
        elif len(colors) > ctx.pixel_count:
            colors = colors[: ctx.pixel_count]

        return colors

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_layout(self, zone_count: int, n: int) -> tuple[int, float]:
        """Compute ball width and swing amplitude, resolving AUTO values.

        When ball_width is AUTO, the layout divides the strip evenly
        between balls and two swing arms (treating swing = ball_width):

            bw = zone_count / (n + 2)

        Leftover zones are distributed to the swing arms.

        Args:
            zone_count: Total zones available.
            n: Number of balls.

        Returns:
            (ball_width_zones, swing_amplitude_zones)
        """
        bw = self.ball_width

        if bw == AUTO:
            # Allocate equal space to each ball and each swing arm.
            bw = max(MIN_BALL_WIDTH, zone_count // (n + 2))
            # Distribute leftover zones to swing arms.
            leftover = zone_count - (n * bw + 2 * bw)
            sw = float(bw) + max(0, leftover) // 2
        else:
            # Explicit ball width -- swing amplitude equals ball width.
            sw = float(bw)

        return bw, sw

    def _rest_centres(self, zone_count: int, n: int, bw: int) -> list[float]:
        """Return the at-rest centre position for each ball.

        The cradle is centred within the strip.

        Args:
            zone_count: Total zones.
            n: Number of balls.
            bw: Ball width in zones.

        Returns:
            List of n float centre positions.
        """
        total = n * bw
        origin = (zone_count - total) / 2.0
        return [origin + i * bw + bw / 2.0 for i in range(n)]

    def _shade(self, x_rel: float) -> HSBK:
        """Compute a Phong-shaded HSBK for one zone on a ball.

        The sphere surface normal at horizontal position x_rel is derived
        from the unit-circle cross-section: N = (x_rel, sqrt(1 - x_rel^2)).

        Args:
            x_rel: Normalised horizontal position on the ball (-1 to +1).

        Returns:
            HSBK for this zone.
        """
        # Sphere surface normal at this horizontal slice.
        y = math.sqrt(max(0.0, 1.0 - x_rel * x_rel))

        # --- Lambertian diffuse ---
        n_dot_l = x_rel * LIGHT_X + y * LIGHT_Y
        diffuse = max(0.0, n_dot_l)

        # --- Phong specular ---
        # R = 2(N.L)N - L; since V = (0,1), R.V = R_y.
        r_y = 2.0 * n_dot_l * y - LIGHT_Y
        specular = max(0.0, r_y) ** self.shininess

        # --- Ambient + diffuse brightness ---
        intensity = AMBIENT_FACTOR + DIFFUSE_FACTOR * diffuse
        bri = min(intensity, 1.0) * self.brightness

        base = HSBK(
            hue=self.hue,
            saturation=self.saturation,
            brightness=bri,
            kelvin=self.kelvin,
        )

        # --- Specular bloom: blend toward white ---
        if specular >= SPECULAR_THRESHOLD:
            spec_bri = min(specular * SPECULAR_FACTOR, 1.0) * self.brightness
            white = HSBK(
                hue=0,
                saturation=0.0,
                brightness=spec_bri,
                kelvin=self.kelvin,
            )
            blend = min(1.0, specular * SPECULAR_FACTOR)
            return base.lerp_hsb(white, blend)

        return base

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        Args:
            _light: The device being powered on (unused)

        Returns:
            Ball color at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=self.hue,
            saturation=self.saturation,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with Newton's Cradle effect.

        Newton's Cradle requires multizone capability for meaningful
        rendering across multiple zones.

        Args:
            light: The light device to check

        Returns:
            True if light has multizone support, False otherwise
        """
        if light.capabilities is None:
            await light.ensure_capabilities()
        return light.capabilities.has_multizone if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Newton's Cradle can inherit prestate from another instance.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectNewtonsCradle, False otherwise
        """
        return isinstance(other, EffectNewtonsCradle)

    def __repr__(self) -> str:
        """String representation of Newton's Cradle effect."""
        return (
            f"EffectNewtonsCradle(num_balls={self.num_balls}, "
            f"ball_width={self.ball_width}, speed={self.speed}, "
            f"hue={self.hue}, saturation={self.saturation}, "
            f"brightness={self.brightness}, shininess={self.shininess}, "
            f"kelvin={self.kelvin}, zones_per_bulb={self.zones_per_bulb}, "
            f"power_on={self.power_on})"
        )
