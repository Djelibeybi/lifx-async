"""Rule Trio (Three CAs Blended) effect.

Three independent 1D elementary cellular automata run across the strip zones
at different speeds. Each CA maps alive/dead cells to one of three theme
colors. The three layers blend via ``HSBK.lerp_oklab()`` for perceptually
uniform color mixing.

Blend logic per zone:

* 0 CAs alive: background (dim/black).
* 1 CA alive: pure primary of that CA.
* 2 CAs alive: ``color_x.lerp_oklab(color_y, 0.5)`` (equal mix).
* 3 CAs alive: ``color_a.lerp_oklab(color_b, 0.5).lerp_oklab(color_c, 1/3)``
  (algebraically equal 1/3 weight to each primary).

The slight speed differences (controlled by *drift_b* and *drift_c*, using
irrational default values 1.31 and 1.73) cause the three patterns to slide
relative to one another, preventing phase lock-in and producing slowly
shifting macro-scale colour interference patterns.
"""

# Originally derived from https://github.com/pkivolowitz/lifx
#
# MIT License
#
# Copyright (c) 2026 Perry Kivolowitz
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import MAX_KELVIN, MIN_KELVIN
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.theme.library import ThemeLibrary

if TYPE_CHECKING:
    from lifx.devices.light import Light

# Number of distinct 3-bit neighborhood patterns (2^3).
_PATTERN_COUNT: int = 8

# Blend factor for equal two-colour mix.
_BLEND_HALF: float = 0.5

# Blend factor that gives equal 1/3 weight when nested with _BLEND_HALF.
# lerp(lerp(A, B, 0.5), C, 1/3) = 1/3 A + 1/3 B + 1/3 C.
_BLEND_THIRD: float = 1.0 / 3.0


class _CA:
    """Lightweight single-track Wolfram elementary cellular automaton.

    Not an Effect subclass -- used solely as a helper inside
    :class:`EffectRuleTrio` to avoid repeating CA machinery three times.
    """

    __slots__ = ("state", "generation", "_rule_table", "_built_rule")

    def __init__(self) -> None:
        self.state: list[int] = []
        self.generation: int = 0
        self._rule_table: list[int] = []
        self._built_rule: int = -1

    def seed(self, cell_count: int, rule: int) -> None:
        """Seed with a random initial state and build the rule table.

        A random seed fills the strip immediately with complex state
        rather than requiring dozens of generations to propagate from a
        single centre cell.

        Args:
            cell_count: Number of cells (zones).
            rule: Wolfram elementary rule number 0-255.
        """
        self.generation = 0
        self.state = [random.randint(0, 1) for _ in range(cell_count)]
        self._ensure_table(rule)

    def advance_to(self, target_gen: int, rule: int) -> None:
        """Step the CA forward until generation equals *target_gen*.

        Args:
            target_gen: Target generation index.
            rule: Current rule (table rebuilt on change).
        """
        self._ensure_table(rule)
        while self.generation < target_gen:
            self._step()

    def _ensure_table(self, rule: int) -> None:
        """Rebuild the lookup table only if *rule* has changed.

        Args:
            rule: Wolfram elementary rule number 0-255.
        """
        if rule == self._built_rule:
            return
        self._rule_table = [(rule >> i) & 1 for i in range(_PATTERN_COUNT)]
        self._built_rule = rule

    def _step(self) -> None:
        """Advance one generation with periodic (wrap-around) boundary conditions.

        The strip is treated as a ring: leftmost cell's left neighbour is
        the rightmost cell and vice versa.
        """
        n = len(self.state)
        new: list[int] = [0] * n
        for i in range(n):
            left = self.state[(i - 1) % n]
            center = self.state[i]
            right = self.state[(i + 1) % n]
            new[i] = self._rule_table[(left << 2) | (center << 1) | right]
        self.state = new
        self.generation += 1


class EffectRuleTrio(FrameEffect):
    """Three independent cellular automata with perceptual Oklab colour blending.

    Each CA runs its own Wolfram rule at its own speed. At each zone the
    outputs of the three automata are combined using ``HSBK.lerp_oklab()``
    so colour mixes are perceptually uniform.

    The slight speed differences (controlled by *drift_b* and *drift_c*)
    cause the three patterns to slide relative to one another, producing
    slowly evolving macro-scale colour structures.

    This is a stateful effect: three cell state arrays and three generation
    counters persist across frames and are initialized lazily on the first
    ``generate_frame`` call.

    Attributes:
        rule_a: Wolfram rule for CA A (default 30: chaotic)
        rule_b: Wolfram rule for CA B (default 90: fractal)
        rule_c: Wolfram rule for CA C (default 110: complex)
        speed: Base generations per second for CA A
        drift_b: Speed multiplier for CA B relative to A
        drift_c: Speed multiplier for CA C relative to A
        theme: Theme providing three colors for the CAs
        brightness: Alive-cell brightness (0.0-1.0)
        kelvin: Color temperature (1500-9000)
        zones_per_bulb: Physical zones per logical bulb

    Example:
        ```python
        effect = EffectRuleTrio(speed=5.0, rule_a=30, rule_b=90, rule_c=110)
        await conductor.start(effect, lights)

        await asyncio.sleep(30)
        await conductor.stop(lights)
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        rule_a: int = 30,
        rule_b: int = 90,
        rule_c: int = 110,
        speed: float = 5.0,
        drift_b: float = 1.31,
        drift_c: float = 1.73,
        theme: list[HSBK] | None = None,
        brightness: float = 0.8,
        kelvin: int = 3500,
        zones_per_bulb: int = 1,
    ) -> None:
        """Initialize Rule Trio cellular automaton effect.

        Args:
            power_on: Power on devices if off (default True)
            rule_a: Wolfram rule for CA A, 0-255 (default 30)
            rule_b: Wolfram rule for CA B, 0-255 (default 90)
            rule_c: Wolfram rule for CA C, 0-255 (default 110)
            speed: Base generations per second, must be > 0 (default 5.0)
            drift_b: Speed multiplier for CA B (default 1.31, irrational)
            drift_c: Speed multiplier for CA C (default 1.73, irrational)
            theme: List of 3+ HSBK colors; first three used as CA primaries.
                When None, uses ThemeLibrary.get("exciting").
            brightness: Alive-cell brightness 0.0-1.0 (default 0.8)
            kelvin: Color temperature 1500-9000 (default 3500)
            zones_per_bulb: Physical zones per logical bulb (default 1)

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        for label, rule in [("rule_a", rule_a), ("rule_b", rule_b), ("rule_c", rule_c)]:
            if not (0 <= rule <= 255):
                raise ValueError(f"{label} must be 0-255, got {rule}")
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if drift_b <= 0:
            raise ValueError(f"drift_b must be positive, got {drift_b}")
        if drift_c <= 0:
            raise ValueError(f"drift_c must be positive, got {drift_c}")
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(f"Kelvin must be {MIN_KELVIN}-{MAX_KELVIN}, got {kelvin}")
        if zones_per_bulb < 1:
            raise ValueError(f"zones_per_bulb must be >= 1, got {zones_per_bulb}")

        super().__init__(power_on=power_on, fps=20.0, duration=None)

        self.rule_a = rule_a
        self.rule_b = rule_b
        self.rule_c = rule_c
        self.speed = speed
        self.drift_b = drift_b
        self.drift_c = drift_c
        self.brightness = brightness
        self.kelvin = kelvin
        self.zones_per_bulb = zones_per_bulb

        # Resolve theme colors: use first three from theme or default.
        if theme is not None:
            if len(theme) < 3:
                raise ValueError(f"Theme must have at least 3 colors, got {len(theme)}")
            self._theme_colors: list[HSBK] = list(theme[:3])
        else:
            default_theme = ThemeLibrary.get("exciting")
            self._theme_colors = list(default_theme.colors[:3])

        # Three independent CA instances.
        self._ca_a = _CA()
        self._ca_b = _CA()
        self._ca_c = _CA()
        self._last_elapsed_s: float = 0.0

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "rule_trio"

    def _resolve_primaries(self) -> tuple[HSBK, HSBK, HSBK]:
        """Return the three primary HSBK colors with configured brightness.

        Each theme color is adjusted to the configured brightness level.

        Returns:
            Three HSBK instances, one per CA primary.
        """
        colors: list[HSBK] = []
        for tc in self._theme_colors:
            colors.append(
                HSBK(
                    hue=tc.hue,
                    saturation=tc.saturation,
                    brightness=self.brightness,
                    kelvin=self.kelvin,
                )
            )
        return colors[0], colors[1], colors[2]

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame by blending three CA outputs.

        Each zone's colour is determined by which CAs have a live cell
        there: 0 alive -> background; 1 alive -> that primary; 2 alive ->
        Oklab midpoint; 3 alive -> Oklab centroid of all three.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        # Compute logical bulb count.
        bulb_count = max(ctx.pixel_count // self.zones_per_bulb, 1)

        # Lazy initialization: seed state on first call, if bulb count changed,
        # or if elapsed time reset (effect restarted).
        needs_reseed = (
            len(self._ca_a.state) != bulb_count or ctx.elapsed_s < self._last_elapsed_s
        )
        if needs_reseed:
            self._ca_a.seed(bulb_count, self.rule_a)
            self._ca_b.seed(bulb_count, self.rule_b)
            self._ca_c.seed(bulb_count, self.rule_c)

        self._last_elapsed_s = ctx.elapsed_s

        # Advance each CA to its target generation.
        base = self.speed
        self._ca_a.advance_to(int(ctx.elapsed_s * base), self.rule_a)
        self._ca_b.advance_to(int(ctx.elapsed_s * base * self.drift_b), self.rule_b)
        self._ca_c.advance_to(int(ctx.elapsed_s * base * self.drift_c), self.rule_c)

        # Resolve the three primaries.
        color_a, color_b, color_c = self._resolve_primaries()

        # Background: achromatic at zero brightness.
        dead = HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=self.kelvin)

        bulb_colors: list[HSBK] = []

        for i in range(bulb_count):
            alive_a = bool(self._ca_a.state[i])
            alive_b = bool(self._ca_b.state[i])
            alive_c = bool(self._ca_c.state[i])
            alive_count = alive_a + alive_b + alive_c

            if alive_count == 0:
                bulb_colors.append(dead)
            elif alive_count == 1:
                if alive_a:
                    bulb_colors.append(color_a)
                elif alive_b:
                    bulb_colors.append(color_b)
                else:
                    bulb_colors.append(color_c)
            elif alive_count == 2:
                if alive_a and alive_b:
                    bulb_colors.append(color_a.lerp_oklab(color_b, _BLEND_HALF))
                elif alive_a and alive_c:
                    bulb_colors.append(color_a.lerp_oklab(color_c, _BLEND_HALF))
                else:
                    bulb_colors.append(color_b.lerp_oklab(color_c, _BLEND_HALF))
            else:
                # All three alive: equal thirds via nested lerp.
                mid = color_a.lerp_oklab(color_b, _BLEND_HALF)
                bulb_colors.append(mid.lerp_oklab(color_c, _BLEND_THIRD))

        # Expand logical bulbs to physical zones.
        if self.zones_per_bulb == 1:
            colors = bulb_colors
        else:
            colors = []
            for color in bulb_colors:
                colors.extend([color] * self.zones_per_bulb)

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
            First theme color at zero brightness for smooth fade-in
        """
        tc = self._theme_colors[0]
        return HSBK(
            hue=tc.hue,
            saturation=tc.saturation,
            brightness=0.0,
            kelvin=self.kelvin,
        )

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with Rule Trio effect.

        Rule Trio requires multizone capability (strips/beams). Single lights
        are not supported; matrix devices are not supported.

        Args:
            light: The light device to check

        Returns:
            True if light has multizone support, False otherwise
        """
        if light.capabilities is None:
            await light.ensure_capabilities()
        return light.capabilities.has_multizone if light.capabilities else False

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Rule Trio can inherit prestate from another Rule Trio effect.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectRuleTrio, False otherwise
        """
        return isinstance(other, EffectRuleTrio)

    def __repr__(self) -> str:
        """String representation of Rule Trio effect."""
        return (
            f"EffectRuleTrio(speed={self.speed}, "
            f"rule_a={self.rule_a}, rule_b={self.rule_b}, rule_c={self.rule_c}, "
            f"drift_b={self.drift_b}, drift_c={self.drift_c}, "
            f"brightness={self.brightness}, kelvin={self.kelvin}, "
            f"zones_per_bulb={self.zones_per_bulb}, power_on={self.power_on})"
        )
