"""Tests for EffectRuleTrio (three CAs blended)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.rule_trio import _CA, EffectRuleTrio

# ---------------------------------------------------------------------------
# Default and custom parameters
# ---------------------------------------------------------------------------


def test_rule_trio_default_parameters() -> None:
    """Test EffectRuleTrio with default parameters."""
    effect = EffectRuleTrio()

    assert effect.name == "rule_trio"
    assert effect.rule_a == 30
    assert effect.rule_b == 90
    assert effect.rule_c == 110
    assert effect.speed == 5.0
    assert effect.drift_b == 1.31
    assert effect.drift_c == 1.73
    assert effect.brightness == 0.8
    assert effect.kelvin == 3500
    assert effect.zones_per_bulb == 1
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_rule_trio_custom_parameters() -> None:
    """Test EffectRuleTrio with custom parameters."""
    theme_colors = [
        HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),
        HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500),
        HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500),
    ]
    effect = EffectRuleTrio(
        rule_a=45,
        rule_b=60,
        rule_c=150,
        speed=10.0,
        drift_b=2.0,
        drift_c=3.0,
        theme=theme_colors,
        brightness=0.6,
        kelvin=5000,
        zones_per_bulb=3,
        power_on=False,
    )

    assert effect.rule_a == 45
    assert effect.rule_b == 60
    assert effect.rule_c == 150
    assert effect.speed == 10.0
    assert effect.drift_b == 2.0
    assert effect.drift_c == 3.0
    assert effect.brightness == 0.6
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 3
    assert effect.power_on is False


def test_rule_trio_default_theme_is_exciting() -> None:
    """Test that default theme uses 'exciting' from ThemeLibrary."""
    effect = EffectRuleTrio()
    # The exciting theme starts with hue=0 (red), hue=40, hue=60
    assert len(effect._theme_colors) == 3
    assert effect._theme_colors[0].hue == 0
    assert effect._theme_colors[1].hue == 40
    assert effect._theme_colors[2].hue == 60


def test_rule_trio_custom_theme_uses_first_three() -> None:
    """Test custom theme uses first three colors when more are provided."""
    colors = [
        HSBK(hue=10, saturation=0.5, brightness=0.9, kelvin=3500),
        HSBK(hue=20, saturation=0.6, brightness=0.9, kelvin=3500),
        HSBK(hue=30, saturation=0.7, brightness=0.9, kelvin=3500),
        HSBK(hue=40, saturation=0.8, brightness=0.9, kelvin=3500),
    ]
    effect = EffectRuleTrio(theme=colors)
    assert len(effect._theme_colors) == 3
    assert effect._theme_colors[0].hue == 10
    assert effect._theme_colors[2].hue == 30


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_rule_trio_invalid_rule_a() -> None:
    """Test invalid rule_a raises ValueError."""
    with pytest.raises(ValueError, match="rule_a must be"):
        EffectRuleTrio(rule_a=-1)
    with pytest.raises(ValueError, match="rule_a must be"):
        EffectRuleTrio(rule_a=256)


def test_rule_trio_invalid_rule_b() -> None:
    """Test invalid rule_b raises ValueError."""
    with pytest.raises(ValueError, match="rule_b must be"):
        EffectRuleTrio(rule_b=-1)
    with pytest.raises(ValueError, match="rule_b must be"):
        EffectRuleTrio(rule_b=256)


def test_rule_trio_invalid_rule_c() -> None:
    """Test invalid rule_c raises ValueError."""
    with pytest.raises(ValueError, match="rule_c must be"):
        EffectRuleTrio(rule_c=-1)
    with pytest.raises(ValueError, match="rule_c must be"):
        EffectRuleTrio(rule_c=256)


def test_rule_trio_invalid_speed() -> None:
    """Test invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectRuleTrio(speed=0)
    with pytest.raises(ValueError, match="Speed must be"):
        EffectRuleTrio(speed=-1.0)


def test_rule_trio_invalid_drift_b() -> None:
    """Test invalid drift_b raises ValueError."""
    with pytest.raises(ValueError, match="drift_b must be"):
        EffectRuleTrio(drift_b=0)
    with pytest.raises(ValueError, match="drift_b must be"):
        EffectRuleTrio(drift_b=-0.5)


def test_rule_trio_invalid_drift_c() -> None:
    """Test invalid drift_c raises ValueError."""
    with pytest.raises(ValueError, match="drift_c must be"):
        EffectRuleTrio(drift_c=0)
    with pytest.raises(ValueError, match="drift_c must be"):
        EffectRuleTrio(drift_c=-0.5)


def test_rule_trio_invalid_brightness() -> None:
    """Test invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectRuleTrio(brightness=1.5)
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectRuleTrio(brightness=-0.1)


def test_rule_trio_invalid_kelvin() -> None:
    """Test invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectRuleTrio(kelvin=1000)
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectRuleTrio(kelvin=10000)


def test_rule_trio_invalid_zones_per_bulb() -> None:
    """Test invalid zones_per_bulb raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectRuleTrio(zones_per_bulb=0)
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectRuleTrio(zones_per_bulb=-1)


def test_rule_trio_theme_too_few_colors() -> None:
    """Test theme with fewer than 3 colors raises ValueError."""
    with pytest.raises(ValueError, match="Theme must have at least 3 colors"):
        EffectRuleTrio(
            theme=[
                HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),
                HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500),
            ]
        )


def test_rule_trio_boundary_rule_values() -> None:
    """Test rule boundary values 0 and 255 are accepted."""
    effect = EffectRuleTrio(rule_a=0, rule_b=0, rule_c=255)
    assert effect.rule_a == 0
    assert effect.rule_b == 0
    assert effect.rule_c == 255


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestRuleTrioInheritance:
    """Tests for EffectRuleTrio class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectRuleTrio extends FrameEffect."""
        effect = EffectRuleTrio()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectRuleTrio extends LIFXEffect."""
        effect = EffectRuleTrio()
        assert isinstance(effect, LIFXEffect)


# ---------------------------------------------------------------------------
# Internal _CA helper
# ---------------------------------------------------------------------------


class TestCAHelper:
    """Tests for the _CA internal helper class."""

    def test_seed_creates_random_state(self) -> None:
        """Test seed creates a state array of the correct length."""
        ca = _CA()
        ca.seed(16, 30)
        assert len(ca.state) == 16
        assert ca.generation == 0
        assert all(s in (0, 1) for s in ca.state)

    def test_advance_to_steps_forward(self) -> None:
        """Test advance_to progresses generations."""
        ca = _CA()
        ca.seed(8, 30)
        ca.advance_to(5, 30)
        assert ca.generation == 5

    def test_advance_to_no_overshoot(self) -> None:
        """Test advance_to does not go past target."""
        ca = _CA()
        ca.seed(8, 30)
        ca.advance_to(3, 30)
        assert ca.generation == 3
        # Calling again with same target should not advance further.
        ca.advance_to(3, 30)
        assert ca.generation == 3

    def test_rule_table_rebuilt_on_change(self) -> None:
        """Test rule table is rebuilt when rule number changes."""
        ca = _CA()
        ca.seed(8, 30)
        table_30 = list(ca._rule_table)
        ca._ensure_table(90)
        assert ca._rule_table != table_30

    def test_periodic_boundaries(self) -> None:
        """Test CA wraps around at strip edges."""
        ca = _CA()
        ca.seed(5, 30)
        ca.state = [1, 0, 0, 0, 0]
        ca.generation = 0
        ca.advance_to(1, 30)
        # Cell 4's right neighbor is cell 0 (was 1).
        # Neighborhood for cell 4: L=0, C=0, R=1 -> pattern 001 -> bit 1 of rule 30
        # Rule 30 = 0b00011110, bit 1 = 1
        assert ca.state[4] == 1


# ---------------------------------------------------------------------------
# Three-CA blending logic
# ---------------------------------------------------------------------------


class TestRuleTrioBlending:
    """Tests for the three-CA blending in generate_frame."""

    def _make_effect_with_known_states(
        self,
        states_a: list[int],
        states_b: list[int],
        states_c: list[int],
    ) -> EffectRuleTrio:
        """Create an EffectRuleTrio with pre-set CA states."""
        theme = [
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500),
        ]
        effect = EffectRuleTrio(theme=theme, speed=0.1)
        # Force-seed with known states.
        effect._ca_a.state = list(states_a)
        effect._ca_a.generation = 999
        effect._ca_a._ensure_table(effect.rule_a)
        effect._ca_b.state = list(states_b)
        effect._ca_b.generation = 999
        effect._ca_b._ensure_table(effect.rule_b)
        effect._ca_c.state = list(states_c)
        effect._ca_c.generation = 999
        effect._ca_c._ensure_table(effect.rule_c)
        return effect

    def test_no_alive_produces_dead(self) -> None:
        """Test zones with no alive CAs produce background (black)."""
        effect = self._make_effect_with_known_states([0, 0, 0], [0, 0, 0], [0, 0, 0])
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=3,
            canvas_width=3,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for c in colors:
            assert c.brightness == 0.0
            assert c.saturation == 0.0

    def test_single_alive_a(self) -> None:
        """Test zone with only CA A alive shows color A."""
        effect = self._make_effect_with_known_states([1, 0, 0], [0, 0, 0], [0, 0, 0])
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=3,
            canvas_width=3,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        # Zone 0 should be color A (hue=0, red)
        assert colors[0].hue == 0
        assert colors[0].brightness == effect.brightness
        # Zones 1, 2 should be dead
        assert colors[1].brightness == 0.0
        assert colors[2].brightness == 0.0

    def test_single_alive_b(self) -> None:
        """Test zone with only CA B alive shows color B."""
        effect = self._make_effect_with_known_states([0, 0, 0], [1, 0, 0], [0, 0, 0])
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=3,
            canvas_width=3,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert colors[0].hue == 120
        assert colors[0].brightness == effect.brightness

    def test_single_alive_c(self) -> None:
        """Test zone with only CA C alive shows color C."""
        effect = self._make_effect_with_known_states([0, 0, 0], [0, 0, 0], [1, 0, 0])
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=3,
            canvas_width=3,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert colors[0].hue == 240
        assert colors[0].brightness == effect.brightness

    def test_two_alive_produces_blend(self) -> None:
        """Test zone with two CAs alive produces an Oklab blend."""
        effect = self._make_effect_with_known_states([1, 0, 0], [1, 0, 0], [0, 0, 0])
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=3,
            canvas_width=3,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        blended = colors[0]
        # The blend should differ from both primaries.
        color_a, color_b, _ = effect._resolve_primaries()
        assert blended != color_a
        assert blended != color_b
        # Brightness should be > 0 (both alive).
        assert blended.brightness > 0

    def test_two_alive_ab_matches_lerp(self) -> None:
        """Test two-alive blend A+B matches direct lerp_oklab call."""
        effect = self._make_effect_with_known_states([1, 0, 0], [1, 0, 0], [0, 0, 0])
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=3,
            canvas_width=3,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        color_a, color_b, _ = effect._resolve_primaries()
        expected = color_a.lerp_oklab(color_b, 0.5)
        assert colors[0] == expected

    def test_two_alive_ac_matches_lerp(self) -> None:
        """Test two-alive blend A+C matches direct lerp_oklab call."""
        effect = self._make_effect_with_known_states([1, 0, 0], [0, 0, 0], [1, 0, 0])
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=3,
            canvas_width=3,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        color_a, _, color_c = effect._resolve_primaries()
        expected = color_a.lerp_oklab(color_c, 0.5)
        assert colors[0] == expected

    def test_two_alive_bc_matches_lerp(self) -> None:
        """Test two-alive blend B+C matches direct lerp_oklab call."""
        effect = self._make_effect_with_known_states([0, 0, 0], [1, 0, 0], [1, 0, 0])
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=3,
            canvas_width=3,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        _, color_b, color_c = effect._resolve_primaries()
        expected = color_b.lerp_oklab(color_c, 0.5)
        assert colors[0] == expected

    def test_three_alive_produces_triple_blend(self) -> None:
        """Test zone with all three CAs alive produces nested Oklab blend."""
        effect = self._make_effect_with_known_states([1, 0, 0], [1, 0, 0], [1, 0, 0])
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=3,
            canvas_width=3,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        color_a, color_b, color_c = effect._resolve_primaries()
        mid = color_a.lerp_oklab(color_b, 0.5)
        expected = mid.lerp_oklab(color_c, 1.0 / 3.0)
        assert colors[0] == expected

    def test_mixed_alive_dead_across_zones(self) -> None:
        """Test correct blending across zones with varied alive patterns."""
        effect = self._make_effect_with_known_states(
            [1, 0, 1, 0],  # A alive at 0, 2
            [0, 1, 1, 0],  # B alive at 1, 2
            [0, 0, 1, 0],  # C alive at 2
        )
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=4,
            canvas_width=4,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        color_a, color_b, color_c = effect._resolve_primaries()

        # Zone 0: only A alive -> color_a
        assert colors[0] == color_a
        # Zone 1: only B alive -> color_b
        assert colors[1] == color_b
        # Zone 2: all three alive -> triple blend
        mid = color_a.lerp_oklab(color_b, 0.5)
        assert colors[2] == mid.lerp_oklab(color_c, 1.0 / 3.0)
        # Zone 3: none alive -> dead
        assert colors[3].brightness == 0.0


# ---------------------------------------------------------------------------
# Drift and speed
# ---------------------------------------------------------------------------


class TestRuleTrioDrift:
    """Tests for drift-based speed differences between CAs."""

    def test_drift_causes_different_generations(self) -> None:
        """Test that drift_b and drift_c cause CAs to be at different generations."""
        effect = EffectRuleTrio(speed=10.0, drift_b=1.31, drift_c=1.73)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        # Initialize
        effect.generate_frame(ctx)

        ctx1 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect.generate_frame(ctx1)

        # After 1.0s at speed=10.0:
        # CA A: int(1.0 * 10.0) = 10 generations
        # CA B: int(1.0 * 10.0 * 1.31) = 13 generations
        # CA C: int(1.0 * 10.0 * 1.73) = 17 generations
        assert effect._ca_a.generation == 10
        assert effect._ca_b.generation == 13
        assert effect._ca_c.generation == 17

    def test_equal_drift_same_generations(self) -> None:
        """Test equal drift values result in same generation counts."""
        effect = EffectRuleTrio(speed=10.0, drift_b=1.0, drift_c=1.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        effect.generate_frame(ctx)

        ctx1 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        effect.generate_frame(ctx1)
        assert effect._ca_a.generation == effect._ca_b.generation
        assert effect._ca_a.generation == effect._ca_c.generation


# ---------------------------------------------------------------------------
# Frame generation
# ---------------------------------------------------------------------------


class TestRuleTrioGenerateFrame:
    """Tests for EffectRuleTrio.generate_frame()."""

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectRuleTrio()
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 1

    @pytest.mark.parametrize("pixel_count", [1, 8, 16, 82])
    def test_multi_pixel_returns_correct_count(self, pixel_count: int) -> None:
        """Test correct number of colors for various pixel counts."""
        effect = EffectRuleTrio()
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == pixel_count

    def test_kelvin_matches_configured(self) -> None:
        """Test kelvin values match configured kelvin."""
        effect = EffectRuleTrio(kelvin=5000)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.kelvin == 5000

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectRuleTrio()
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 16
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_zones_per_bulb_expands_colors(self) -> None:
        """Test zones_per_bulb groups zones into logical bulbs."""
        effect = EffectRuleTrio(zones_per_bulb=2)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 8
        # Each pair of adjacent zones should have the same color.
        for i in range(0, 8, 2):
            assert colors[i] == colors[i + 1]

    def test_lazy_initialization(self) -> None:
        """Test CAs are lazily initialized on first generate_frame call."""
        effect = EffectRuleTrio()
        assert effect._ca_a.state == []
        assert effect._ca_b.state == []
        assert effect._ca_c.state == []

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect.generate_frame(ctx)
        assert len(effect._ca_a.state) == 16
        assert len(effect._ca_b.state) == 16
        assert len(effect._ca_c.state) == 16

    def test_state_persists_across_frames(self) -> None:
        """Test that state is maintained between generate_frame calls."""
        effect = EffectRuleTrio(speed=10.0)
        ctx0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect.generate_frame(ctx0)
        state_a = list(effect._ca_a.state)
        state_b = list(effect._ca_b.state)
        state_c = list(effect._ca_c.state)

        # Same elapsed time should not change state.
        effect.generate_frame(ctx0)
        assert effect._ca_a.state == state_a
        assert effect._ca_b.state == state_b
        assert effect._ca_c.state == state_c

    def test_state_advances_over_time(self) -> None:
        """Test that CAs advance generations as time increases."""
        effect = EffectRuleTrio(speed=5.0)
        ctx0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors0 = effect.generate_frame(ctx0)

        ctx1 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors1 = effect.generate_frame(ctx1)
        # After multiple generations, pattern should differ.
        assert colors0 != colors1

    def test_reinitializes_on_pixel_count_change(self) -> None:
        """Test state reinitializes if pixel_count changes."""
        effect = EffectRuleTrio(speed=0.1)
        ctx8 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        effect.generate_frame(ctx8)
        assert len(effect._ca_a.state) == 8

        ctx16 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect.generate_frame(ctx16)
        assert len(effect._ca_a.state) == 16


# ---------------------------------------------------------------------------
# Resolve primaries
# ---------------------------------------------------------------------------


class TestResolvePrimaries:
    """Tests for _resolve_primaries brightness application."""

    def test_primaries_use_configured_brightness(self) -> None:
        """Test primaries apply the configured brightness."""
        theme = [
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500),
        ]
        effect = EffectRuleTrio(theme=theme, brightness=0.5)
        a, b, c = effect._resolve_primaries()
        assert a.brightness == 0.5
        assert b.brightness == 0.5
        assert c.brightness == 0.5

    def test_primaries_preserve_hue_and_saturation(self) -> None:
        """Test primaries preserve theme hue and saturation."""
        theme = [
            HSBK(hue=10, saturation=0.8, brightness=1.0, kelvin=3500),
            HSBK(hue=130, saturation=0.6, brightness=1.0, kelvin=3500),
            HSBK(hue=250, saturation=0.4, brightness=1.0, kelvin=3500),
        ]
        effect = EffectRuleTrio(theme=theme, brightness=0.7, kelvin=4000)
        a, b, c = effect._resolve_primaries()
        assert a.hue == 10
        assert a.saturation == 0.8
        assert b.hue == 130
        assert b.saturation == 0.6
        assert c.hue == 250
        assert c.saturation == 0.4

    def test_primaries_use_configured_kelvin(self) -> None:
        """Test primaries use the configured kelvin, not theme kelvin."""
        theme = [
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=2500),
            HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=2500),
            HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=2500),
        ]
        effect = EffectRuleTrio(theme=theme, kelvin=6000)
        a, b, c = effect._resolve_primaries()
        assert a.kelvin == 6000
        assert b.kelvin == 6000
        assert c.kelvin == 6000


# ---------------------------------------------------------------------------
# Frame loop integration
# ---------------------------------------------------------------------------


class TestRuleTrioFrameLoop:
    """Tests for EffectRuleTrio running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test rule_trio sends frames through animator.send_frame."""
        effect = EffectRuleTrio()

        animator = MagicMock()
        animator.pixel_count = 16
        animator.canvas_width = 16
        animator.canvas_height = 1
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        play_task = asyncio.create_task(effect.async_play())
        await asyncio.sleep(0.1)
        effect.stop()
        await asyncio.wait_for(play_task, timeout=1.0)

        assert animator.send_frame.call_count > 0


# ---------------------------------------------------------------------------
# Power off and compatibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rule_trio_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns first theme color at zero brightness."""
    theme = [
        HSBK(hue=45, saturation=0.9, brightness=1.0, kelvin=3500),
        HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500),
        HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500),
    ]
    effect = EffectRuleTrio(theme=theme, kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 45
    assert result.saturation == 0.9
    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_rule_trio_is_light_compatible_with_multizone() -> None:
    """Test is_light_compatible returns True for multizone lights."""
    effect = EffectRuleTrio()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_rule_trio_is_light_compatible_without_multizone() -> None:
    """Test is_light_compatible returns False for non-multizone lights."""
    effect = EffectRuleTrio()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_rule_trio_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectRuleTrio()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_multizone = True
        light.capabilities = caps

    light.ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light.ensure_capabilities.assert_called_once()


# ---------------------------------------------------------------------------
# Prestate and repr
# ---------------------------------------------------------------------------


def test_rule_trio_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectRuleTrio."""
    effect = EffectRuleTrio()
    assert effect.inherit_prestate(EffectRuleTrio()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_rule_trio_repr() -> None:
    """Test EffectRuleTrio string representation."""
    effect = EffectRuleTrio(
        speed=10.0,
        rule_a=45,
        rule_b=60,
        rule_c=150,
        drift_b=2.0,
        drift_c=3.0,
        brightness=0.6,
    )
    repr_str = repr(effect)

    assert "EffectRuleTrio" in repr_str
    assert "speed=10.0" in repr_str
    assert "rule_a=45" in repr_str
    assert "rule_b=60" in repr_str
    assert "rule_c=150" in repr_str
    assert "drift_b=2.0" in repr_str
    assert "drift_c=3.0" in repr_str
    assert "brightness=0.6" in repr_str
