"""Rule 30 (1D Cellular Automaton) effect.

A 1D elementary cellular automaton runs across the strip zones. Each zone
is one cell. Each generation, the 3-cell neighborhood (left, center, right)
maps to a bit in the 8-bit rule number. The simulation advances at a
configurable rate (generations per second). Boundary conditions are
periodic (the strip wraps left-to-right).

Rule 30  -- chaotic / pseudo-random; great for organic, unpredictable animation.
Rule 90  -- Sierpinski fractal triangle; self-similar nested pattern.
Rule 110 -- Turing-complete; rich structured behaviour.
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

# Number of distinct 3-bit neighborhood patterns (2^3).
_PATTERN_COUNT: int = 8

# Valid seed mode identifiers.
_VALID_SEEDS: frozenset[str] = frozenset({"center", "random", "all"})


class EffectRule30(FrameEffect):
    """Wolfram elementary 1D cellular automaton on the zone strip.

    Each zone is a cell; alive cells are shown at the configured hue and
    brightness, dead cells at the background brightness. The CA rule is
    applied once per generation; generation rate is set by ``speed``.

    This is a stateful effect: the cell array and generation counter
    persist across frames and are initialized lazily on the first
    ``generate_frame`` call.

    Attributes:
        speed: Generations per second
        rule: Wolfram elementary CA rule number (0-255)
        hue: Alive-cell hue in degrees (0-360)
        brightness: Alive-cell brightness (0.0-1.0)
        background_brightness: Dead-cell brightness (0.0-1.0)
        seed: Initial seed mode ("center", "random", "all")
        kelvin: Color temperature (1500-9000)
        zones_per_bulb: Number of physical zones per logical bulb

    Example:
        ```python
        effect = EffectRule30(speed=5.0, rule=30, hue=120)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        speed: float = 5.0,
        rule: int = 30,
        hue: int = 120,
        brightness: float = 0.8,
        background_brightness: float = 0.05,
        seed: str = "center",
        kelvin: int = 3500,
        zones_per_bulb: int = 1,
    ) -> None:
        """Initialize Rule 30 cellular automaton effect.

        Args:
            power_on: Power on devices if off (default True)
            speed: Generations per second, must be > 0 (default 5.0)
            rule: Wolfram elementary CA rule number 0-255 (default 30)
            hue: Alive-cell hue 0-360 degrees (default 120, green)
            brightness: Alive-cell brightness 0.0-1.0 (default 0.8)
            background_brightness: Dead-cell brightness 0.0-1.0 (default 0.05)
            seed: Initial seed mode: "center", "random", or "all" (default "center")
            kelvin: Color temperature 1500-9000 (default 3500)
            zones_per_bulb: Physical zones per logical bulb (default 1)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if not (0 <= rule <= 255):
            raise ValueError(f"Rule must be 0-255, got {rule}")
        if not (0 <= hue <= 360):
            raise ValueError(f"Hue must be 0-360, got {hue}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (0.0 <= background_brightness <= 1.0):
            raise ValueError(
                f"Background brightness must be 0.0-1.0, got {background_brightness}"
            )
        if seed not in _VALID_SEEDS:
            raise ValueError(
                f"Seed must be one of {sorted(_VALID_SEEDS)}, got {seed!r}"
            )
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.speed = speed
        self.rule = rule
        self.hue = hue
        self.brightness = brightness
        self.background_brightness = background_brightness
        self.seed = seed
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb

        # CA state: list of 0/1 ints, one per logical bulb.
        self._state: list[int] = []

        # How many generations have elapsed since the effect started.
        self._generation: int = 0

        # Lookup table: index = 3-bit neighbourhood, value = next cell state.
        self._rule_table: list[int] = self._build_rule_table(rule)

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "rule30"

    def _build_rule_table(self, rule: int) -> list[int]:
        """Build the lookup table for the given Wolfram rule number.

        Each of the 8 possible (L, C, R) neighborhoods maps to one bit of
        the rule number. Neighborhood encoded as (L<<2 | C<<1 | R).

        Args:
            rule: Wolfram rule number (0-255)

        Returns:
            List of 8 ints (0 or 1), indexed by neighborhood pattern.
        """
        return [(rule >> i) & 1 for i in range(_PATTERN_COUNT)]

    def _make_seed(self, cell_count: int) -> list[int]:
        """Create the initial cell array.

        Args:
            cell_count: Number of cells.

        Returns:
            A list of 0/1 ints representing the initial generation.
        """
        if self.seed == "random":
            return [random.randint(0, 1) for _ in range(cell_count)]
        if self.seed == "all":
            return [1] * cell_count
        # "center": single alive cell in the middle.
        state: list[int] = [0] * cell_count
        if cell_count > 0:
            state[cell_count // 2] = 1
        return state

    def _step(self) -> None:
        """Advance the CA by one generation with periodic boundary conditions.

        The strip is treated as a ring: the leftmost cell's left neighbor
        is the rightmost cell and vice versa.
        """
        n = len(self._state)
        if n == 0:
            return

        new_state: list[int] = [0] * n
        for i in range(n):
            left = self._state[(i - 1) % n]
            center = self._state[i]
            right = self._state[(i + 1) % n]
            neighborhood = (left << 2) | (center << 1) | right
            new_state[i] = self._rule_table[neighborhood]

        self._state = new_state
        self._generation += 1

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of the cellular automaton.

        Lazily initializes state on first call. Advances the simulation
        to the generation corresponding to the elapsed time, then maps
        alive/dead cells to HSBK colors.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        # Compute logical bulb count
        bulb_count = max(ctx.pixel_count // self.zones_per_bulb, 1)

        # Lazy initialization: seed state on first call or if bulb count changed
        if len(self._state) != bulb_count:
            self._state = self._make_seed(bulb_count)
            self._generation = 0

        # Advance the CA to the generation matching elapsed time
        target_gen = int(ctx.elapsed_s * self.speed)
        while self._generation < target_gen:
            self._step()

        # Map cell states to HSBK colors
        bulb_colors: list[HSBK] = []
        for cell in self._state:
            if cell:
                bulb_colors.append(
                    HSBK(
                        hue=self.hue,
                        saturation=1.0,
                        brightness=self.brightness,
                        kelvin=self.kelvin,
                    )
                )
            else:
                bulb_colors.append(
                    HSBK(
                        hue=self.hue,
                        saturation=1.0,
                        brightness=self.background_brightness,
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
            Effect hue at zero brightness for smooth fade-in
        """
        return HSBK(
            hue=self.hue,
            saturation=1.0,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with Rule 30 effect.

        Rule 30 requires multizone capability (strips/beams). Single lights
        are not supported; matrix devices are not supported.

        Args:
            light: The light device to check

        Returns:
            True if light has multizone support, False otherwise
        """
        if light.capabilities is None:
            await light._ensure_capabilities()
        return light.capabilities.has_multizone if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Rule 30 can inherit prestate from another Rule 30 effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectRule30, False otherwise
        """
        return isinstance(other, EffectRule30)

    def __repr__(self) -> str:
        """String representation of Rule 30 effect."""
        return (
            f"EffectRule30(speed={self.speed}, rule={self.rule}, "
            f"hue={self.hue}, brightness={self.brightness}, "
            f"background_brightness={self.background_brightness}, "
            f"seed={self.seed!r}, kelvin={self.kelvin}, "
            f"zones_per_bulb={self.zones_per_bulb}, power_on={self.power_on})"
        )
