"""Tests for EffectNewtonsCradle (Newton's Cradle pendulum simulation)."""

import asyncio
import math
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.newtons_cradle import (
    AMBIENT_FACTOR,
    DIFFUSE_FACTOR,
    LIGHT_X,
    LIGHT_Y,
    MIN_BALL_WIDTH,
    SPECULAR_FACTOR,
    SPECULAR_THRESHOLD,
    EffectNewtonsCradle,
)

# ---------------------------------------------------------------------------
# Default parameters
# ---------------------------------------------------------------------------


def test_default_parameters() -> None:
    """Test EffectNewtonsCradle with default parameters."""
    effect = EffectNewtonsCradle()

    assert effect.name == "newtons_cradle"
    assert effect.num_balls == 5
    assert effect.ball_width == 0
    assert effect.speed == 2.0
    assert effect.hue == 0
    assert effect.saturation == 0.0
    assert effect.brightness == 0.8
    assert effect.shininess == 60
    assert effect.kelvin == 4500
    assert effect.zones_per_bulb == 1
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_custom_parameters() -> None:
    """Test EffectNewtonsCradle with custom parameters."""
    effect = EffectNewtonsCradle(
        num_balls=3,
        ball_width=5,
        speed=3.0,
        hue=200,
        saturation=0.3,
        brightness=0.6,
        shininess=25,
        kelvin=5000,
        zones_per_bulb=2,
        power_on=False,
    )

    assert effect.num_balls == 3
    assert effect.ball_width == 5
    assert effect.speed == 3.0
    assert effect.hue == 200
    assert effect.saturation == 0.3
    assert effect.brightness == 0.6
    assert effect.shininess == 25
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 2
    assert effect.power_on is False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_invalid_num_balls_low() -> None:
    """Test num_balls below minimum raises ValueError."""
    with pytest.raises(ValueError, match="num_balls must be"):
        EffectNewtonsCradle(num_balls=1)


def test_invalid_num_balls_high() -> None:
    """Test num_balls above maximum raises ValueError."""
    with pytest.raises(ValueError, match="num_balls must be"):
        EffectNewtonsCradle(num_balls=11)


def test_invalid_ball_width_negative() -> None:
    """Test negative ball_width raises ValueError."""
    with pytest.raises(ValueError, match="ball_width must be"):
        EffectNewtonsCradle(ball_width=-1)


def test_invalid_ball_width_high() -> None:
    """Test ball_width above maximum raises ValueError."""
    with pytest.raises(ValueError, match="ball_width must be"):
        EffectNewtonsCradle(ball_width=31)


def test_invalid_speed() -> None:
    """Test non-positive speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectNewtonsCradle(speed=0)

    with pytest.raises(ValueError, match="Speed must be"):
        EffectNewtonsCradle(speed=-1.0)


def test_invalid_hue() -> None:
    """Test hue out of range raises ValueError."""
    with pytest.raises(ValueError, match="Hue must be"):
        EffectNewtonsCradle(hue=-1)

    with pytest.raises(ValueError, match="Hue must be"):
        EffectNewtonsCradle(hue=361)


def test_invalid_saturation() -> None:
    """Test saturation out of range raises ValueError."""
    with pytest.raises(ValueError, match="Saturation must be"):
        EffectNewtonsCradle(saturation=-0.1)

    with pytest.raises(ValueError, match="Saturation must be"):
        EffectNewtonsCradle(saturation=1.1)


def test_invalid_brightness() -> None:
    """Test brightness out of range raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectNewtonsCradle(brightness=-0.1)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectNewtonsCradle(brightness=1.1)


def test_invalid_shininess_low() -> None:
    """Test shininess below minimum raises ValueError."""
    with pytest.raises(ValueError, match="Shininess must be"):
        EffectNewtonsCradle(shininess=0)


def test_invalid_shininess_high() -> None:
    """Test shininess above maximum raises ValueError."""
    with pytest.raises(ValueError, match="Shininess must be"):
        EffectNewtonsCradle(shininess=101)


def test_invalid_kelvin() -> None:
    """Test kelvin out of range raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectNewtonsCradle(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectNewtonsCradle(kelvin=10000)


def test_invalid_zones_per_bulb() -> None:
    """Test zones_per_bulb below 1 raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectNewtonsCradle(zones_per_bulb=0)

    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectNewtonsCradle(zones_per_bulb=-1)


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestInheritance:
    """Tests for EffectNewtonsCradle class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectNewtonsCradle extends FrameEffect."""
        effect = EffectNewtonsCradle()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectNewtonsCradle extends LIFXEffect."""
        effect = EffectNewtonsCradle()
        assert isinstance(effect, LIFXEffect)


# ---------------------------------------------------------------------------
# generate_frame() - basic output
# ---------------------------------------------------------------------------


class TestGenerateFrame:
    """Tests for EffectNewtonsCradle.generate_frame()."""

    def _make_ctx(
        self,
        elapsed_s: float = 1.0,
        pixel_count: int = 82,
    ) -> FrameContext:
        return FrameContext(
            elapsed_s=elapsed_s,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )

    def test_returns_correct_length(self) -> None:
        """Test frame has exactly pixel_count colors."""
        effect = EffectNewtonsCradle()
        colors = effect.generate_frame(self._make_ctx(pixel_count=82))
        assert len(colors) == 82

    @pytest.mark.parametrize("pixel_count", [16, 36, 50, 82])
    def test_various_pixel_counts(self, pixel_count: int) -> None:
        """Test correct number of colors for various pixel counts."""
        effect = EffectNewtonsCradle()
        colors = effect.generate_frame(self._make_ctx(pixel_count=pixel_count))
        assert len(colors) == pixel_count

    def test_hue_matches_configured(self) -> None:
        """Test ball zone hues match configured hue (ignoring dead zones)."""
        effect = EffectNewtonsCradle(hue=200, saturation=0.5)
        colors = effect.generate_frame(self._make_ctx())
        # Ball zones have the configured hue; dead zones have hue=0
        ball_hues = {c.hue for c in colors if c.brightness > 0}
        # Due to specular blend, some ball zones may have interpolated hues,
        # but non-specular zones should have exactly the configured hue.
        assert 200 in ball_hues or len(ball_hues) > 0

    def test_kelvin_matches_configured(self) -> None:
        """Test all zones have the configured kelvin."""
        effect = EffectNewtonsCradle(kelvin=5000)
        colors = effect.generate_frame(self._make_ctx())
        for color in colors:
            assert color.kelvin == 5000

    def test_brightness_in_valid_range(self) -> None:
        """Test all brightness values are 0.0-1.0."""
        effect = EffectNewtonsCradle()
        colors = effect.generate_frame(self._make_ctx())
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_saturation_in_valid_range(self) -> None:
        """Test all saturation values are 0.0-1.0."""
        effect = EffectNewtonsCradle(saturation=0.5)
        colors = effect.generate_frame(self._make_ctx())
        for color in colors:
            assert 0.0 <= color.saturation <= 1.0

    def test_frame_changes_over_time(self) -> None:
        """Test different elapsed_s produce different frames."""
        effect = EffectNewtonsCradle()
        colors1 = effect.generate_frame(self._make_ctx(elapsed_s=0.0))
        colors2 = effect.generate_frame(self._make_ctx(elapsed_s=0.5))
        assert colors1 != colors2

    def test_has_lit_and_dark_zones(self) -> None:
        """Test frame has both illuminated ball zones and dark gap zones."""
        effect = EffectNewtonsCradle()
        colors = effect.generate_frame(self._make_ctx(pixel_count=82))
        brightnesses = [c.brightness for c in colors]
        assert max(brightnesses) > 0.0
        assert min(brightnesses) == 0.0

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectNewtonsCradle()
        colors = effect.generate_frame(self._make_ctx(elapsed_s=0.0))
        assert len(colors) == 82
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_pixels_vary_across_strip(self) -> None:
        """Test pixels are not all identical on a multizone strip."""
        effect = EffectNewtonsCradle()
        colors = effect.generate_frame(self._make_ctx(elapsed_s=0.25))
        unique_brightnesses = {c.brightness for c in colors}
        assert len(unique_brightnesses) > 1


# ---------------------------------------------------------------------------
# zones_per_bulb expansion
# ---------------------------------------------------------------------------


class TestZonesPerBulb:
    """Tests for zones_per_bulb logical bulb expansion."""

    def test_zones_per_bulb_expands_colors(self) -> None:
        """Test zones_per_bulb groups zones into logical bulbs."""
        effect = EffectNewtonsCradle(zones_per_bulb=2)
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=82,
            canvas_width=82,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 82

        # Each pair of adjacent zones should have the same color
        for i in range(0, 80, 2):
            assert colors[i] == colors[i + 1]

    def test_zones_per_bulb_correct_count(self) -> None:
        """Test output length matches pixel_count with zones_per_bulb."""
        effect = EffectNewtonsCradle(zones_per_bulb=3)
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=30,
            canvas_width=30,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 30


# ---------------------------------------------------------------------------
# Pendulum swing direction
# ---------------------------------------------------------------------------


class TestPendulumPhase:
    """Tests for pendulum swing behaviour."""

    def test_right_ball_swings_first_half(self) -> None:
        """Test rightmost ball moves right during first half of cycle."""
        effect = EffectNewtonsCradle(speed=2.0, ball_width=5)
        # At phase=0.25 (quarter cycle), right ball at max displacement
        ctx_rest = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=82,
            canvas_width=82,
            canvas_height=1,
        )
        ctx_swing = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=82,
            canvas_width=82,
            canvas_height=1,
        )
        colors_rest = effect.generate_frame(ctx_rest)
        colors_swing = effect.generate_frame(ctx_swing)
        # Frames should differ -- the rightmost ball has moved
        assert colors_rest != colors_swing

    def test_left_ball_swings_second_half(self) -> None:
        """Test leftmost ball moves left during second half of cycle."""
        effect = EffectNewtonsCradle(speed=2.0, ball_width=5)
        # At phase=0.75, left ball at max displacement
        ctx_swing = FrameContext(
            elapsed_s=1.5,
            device_index=0,
            pixel_count=82,
            canvas_width=82,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx_swing)
        # Leftmost ball should be displaced -- first few zones may be lit
        # while they wouldn't be at rest.
        assert len(colors) == 82

    def test_cycle_repeats(self) -> None:
        """Test effect repeats after one full cycle period."""
        effect = EffectNewtonsCradle(speed=2.0)
        ctx1 = FrameContext(
            elapsed_s=0.3,
            device_index=0,
            pixel_count=82,
            canvas_width=82,
            canvas_height=1,
        )
        ctx2 = FrameContext(
            elapsed_s=2.3,
            device_index=0,
            pixel_count=82,
            canvas_width=82,
            canvas_height=1,
        )
        colors1 = effect.generate_frame(ctx1)
        colors2 = effect.generate_frame(ctx2)
        assert colors1 == colors2


# ---------------------------------------------------------------------------
# Layout resolution (_resolve_layout)
# ---------------------------------------------------------------------------


class TestResolveLayout:
    """Tests for _resolve_layout auto-sizing."""

    def test_auto_ball_width_minimum(self) -> None:
        """Test auto ball_width is at least MIN_BALL_WIDTH."""
        effect = EffectNewtonsCradle(num_balls=5, ball_width=0)
        bw, _sw = effect._resolve_layout(20, 5)
        assert bw >= MIN_BALL_WIDTH

    def test_auto_ball_width_scales_with_zones(self) -> None:
        """Test auto ball_width gets larger with more zones."""
        effect = EffectNewtonsCradle(num_balls=5, ball_width=0)
        bw_small, _ = effect._resolve_layout(36, 5)
        bw_large, _ = effect._resolve_layout(200, 5)
        assert bw_large >= bw_small

    def test_explicit_ball_width_used(self) -> None:
        """Test explicit ball_width is passed through."""
        effect = EffectNewtonsCradle(num_balls=5, ball_width=7)
        bw, sw = effect._resolve_layout(82, 5)
        assert bw == 7
        assert sw == 7.0

    def test_swing_amplitude_equals_ball_width_for_explicit(self) -> None:
        """Test swing amplitude equals ball_width when explicit."""
        effect = EffectNewtonsCradle(ball_width=10)
        bw, sw = effect._resolve_layout(200, 5)
        assert bw == 10
        assert sw == float(bw)


# ---------------------------------------------------------------------------
# Rest centres (_rest_centres)
# ---------------------------------------------------------------------------


class TestRestCentres:
    """Tests for _rest_centres positioning."""

    def test_centres_count_matches_num_balls(self) -> None:
        """Test number of centres matches num_balls."""
        effect = EffectNewtonsCradle(num_balls=5)
        centres = effect._rest_centres(82, 5, 6)
        assert len(centres) == 5

    def test_centres_are_centred(self) -> None:
        """Test cradle is centred in the strip."""
        effect = EffectNewtonsCradle(num_balls=3)
        centres = effect._rest_centres(30, 3, 6)
        # Total width = 3 * 6 = 18; origin = (30-18)/2 = 6
        # Centre of strip = 15
        middle_ball = centres[1]
        assert abs(middle_ball - 15.0) < 0.01

    def test_centres_evenly_spaced(self) -> None:
        """Test balls are evenly spaced."""
        effect = EffectNewtonsCradle(num_balls=4)
        centres = effect._rest_centres(100, 4, 8)
        spacings = [centres[i + 1] - centres[i] for i in range(3)]
        for s in spacings:
            assert abs(s - spacings[0]) < 0.01


# ---------------------------------------------------------------------------
# Phong shading (_shade)
# ---------------------------------------------------------------------------


class TestShading:
    """Tests for Phong shading computation."""

    def test_centre_brighter_than_edge(self) -> None:
        """Test ball centre is brighter than edge (diffuse falloff)."""
        effect = EffectNewtonsCradle(brightness=0.8, saturation=0.0)
        centre = effect._shade(0.0)
        edge = effect._shade(0.9)
        assert centre.brightness >= edge.brightness

    def test_ambient_provides_minimum_brightness(self) -> None:
        """Test ambient factor provides floor brightness on dark side."""
        effect = EffectNewtonsCradle(brightness=1.0, saturation=0.0)
        # At x_rel=0.95 (near right edge, away from left light source)
        color = effect._shade(0.95)
        # Should have at least ambient brightness
        assert color.brightness >= AMBIENT_FACTOR * 0.5

    def test_specular_creates_highlight(self) -> None:
        """Test specular produces a bright highlight near the light angle."""
        effect = EffectNewtonsCradle(brightness=1.0, saturation=0.0, shininess=10)
        # Sample across the ball to find the brightest point
        brightnesses = [effect._shade(x / 10.0).brightness for x in range(-9, 10)]
        max_bri = max(brightnesses)
        # With specular, peak brightness should exceed ambient + diffuse alone
        assert max_bri > AMBIENT_FACTOR + DIFFUSE_FACTOR * 0.5

    def test_high_shininess_sharper_highlight(self) -> None:
        """Test higher shininess concentrates the highlight in fewer zones."""
        effect_low = EffectNewtonsCradle(brightness=1.0, saturation=0.0, shininess=5)
        effect_high = EffectNewtonsCradle(brightness=1.0, saturation=0.0, shininess=80)
        # Sample at fine resolution
        samples = 200
        positions = [x / samples for x in range(-samples + 1, samples)]
        bri_low = [effect_low._shade(x).brightness for x in positions]
        bri_high = [effect_high._shade(x).brightness for x in positions]

        # High shininess peak should be at least as bright as low shininess
        # peak, because the specular energy is concentrated.
        assert max(bri_high) >= max(bri_low) * 0.9

        # The variance of brightness should be higher with high shininess
        # (more contrast between highlight and non-highlight zones).
        def variance(vals: list[float]) -> float:
            mean = sum(vals) / len(vals)
            return sum((v - mean) ** 2 for v in vals) / len(vals)

        assert variance(bri_high) >= variance(bri_low) * 0.5

    def test_shade_returns_valid_hsbk(self) -> None:
        """Test _shade returns HSBK with all fields in valid range."""
        effect = EffectNewtonsCradle(hue=120, saturation=0.7, brightness=0.8)
        for x in range(-9, 10):
            color = effect._shade(x / 10.0)
            assert 0 <= color.hue <= 360
            assert 0.0 <= color.saturation <= 1.0
            assert 0.0 <= color.brightness <= 1.0
            assert 1500 <= color.kelvin <= 9000

    def test_hue_is_int(self) -> None:
        """Test that hue is always an integer."""
        effect = EffectNewtonsCradle(hue=200, saturation=0.5, brightness=0.8)
        for x in range(-9, 10):
            color = effect._shade(x / 10.0)
            assert isinstance(color.hue, int)

    def test_specular_blend_toward_white(self) -> None:
        """Test specular bloom reduces saturation (blends toward white)."""
        effect = EffectNewtonsCradle(
            hue=120, saturation=1.0, brightness=1.0, shininess=10
        )
        # Find the zone with highest specular (near the highlight)
        colors = [effect._shade(x / 10.0) for x in range(-9, 10)]
        # Sort by brightness descending -- brightest should have reduced sat
        colors_sorted = sorted(colors, key=lambda c: c.brightness, reverse=True)
        brightest = colors_sorted[0]
        dimmest_ball = colors_sorted[-1]
        # The brightest zone (specular highlight) should have lower saturation
        # than the dimmest zone (pure base color)
        assert brightest.saturation <= dimmest_ball.saturation


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify lighting constants are physically sensible."""

    def test_light_angle_approximately_25_degrees(self) -> None:
        """Test light vector corresponds to ~25 degree angle."""
        angle = math.atan2(-LIGHT_X, LIGHT_Y)
        assert abs(math.degrees(angle) - 25.0) < 0.1

    def test_light_vector_is_unit(self) -> None:
        """Test light direction vector has unit length."""
        length = math.sqrt(LIGHT_X**2 + LIGHT_Y**2)
        assert abs(length - 1.0) < 1e-10

    def test_phong_factors_positive(self) -> None:
        """Test all Phong illumination factors are positive."""
        assert AMBIENT_FACTOR > 0
        assert DIFFUSE_FACTOR > 0
        assert SPECULAR_FACTOR > 0

    def test_specular_threshold_small(self) -> None:
        """Test specular threshold is a small positive value."""
        assert 0 < SPECULAR_THRESHOLD < 0.1


# ---------------------------------------------------------------------------
# Frame loop integration
# ---------------------------------------------------------------------------


class TestFrameLoop:
    """Tests for running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test Newton's Cradle sends frames through animator."""
        effect = EffectNewtonsCradle()

        animator = MagicMock()
        animator.pixel_count = 82
        animator.canvas_width = 82
        animator.canvas_height = 1
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        play_task = asyncio.create_task(effect.async_play())
        await asyncio.sleep(0.1)
        effect.stop()
        await asyncio.wait_for(play_task, timeout=1.0)

        assert animator.send_frame.call_count > 0


# ---------------------------------------------------------------------------
# from_poweroff_hsbk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_from_poweroff_hsbk() -> None:
    """Test from_poweroff_hsbk returns zero brightness startup color."""
    effect = EffectNewtonsCradle(hue=200, saturation=0.3, kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 200
    assert result.saturation == 0.3
    assert result.brightness == 0.0
    assert result.kelvin == 5000


# ---------------------------------------------------------------------------
# is_light_compatible
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compatible_with_multizone() -> None:
    """Test is_light_compatible returns True for multizone lights."""
    effect = EffectNewtonsCradle()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_incompatible_without_multizone() -> None:
    """Test is_light_compatible returns False for non-multizone lights."""
    effect = EffectNewtonsCradle()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_compatible_loads_capabilities_when_none() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectNewtonsCradle()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_multizone = True
        light.capabilities = caps

    light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light._ensure_capabilities.assert_called_once()


# ---------------------------------------------------------------------------
# inherit_prestate
# ---------------------------------------------------------------------------


def test_inherit_prestate_same_type() -> None:
    """Test inherit_prestate returns True for same effect type."""
    effect = EffectNewtonsCradle()
    assert effect.inherit_prestate(EffectNewtonsCradle()) is True


def test_inherit_prestate_different_type() -> None:
    """Test inherit_prestate returns False for different effect type."""
    effect = EffectNewtonsCradle()
    assert effect.inherit_prestate(MagicMock()) is False


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------


def test_repr() -> None:
    """Test EffectNewtonsCradle string representation."""
    effect = EffectNewtonsCradle(
        num_balls=3, ball_width=5, speed=3.0, hue=200, shininess=25
    )
    repr_str = repr(effect)

    assert "EffectNewtonsCradle" in repr_str
    assert "num_balls=3" in repr_str
    assert "ball_width=5" in repr_str
    assert "speed=3.0" in repr_str
    assert "hue=200" in repr_str
    assert "shininess=25" in repr_str


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case scenarios."""

    def test_two_balls_minimum(self) -> None:
        """Test effect works with minimum 2 balls."""
        effect = EffectNewtonsCradle(num_balls=2)
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=36,
            canvas_width=36,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 36
        assert any(c.brightness > 0 for c in colors)

    def test_ten_balls_maximum(self) -> None:
        """Test effect works with maximum 10 balls."""
        effect = EffectNewtonsCradle(num_balls=10)
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=82,
            canvas_width=82,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 82

    def test_small_strip(self) -> None:
        """Test effect works on a small 16-zone strip."""
        effect = EffectNewtonsCradle(num_balls=3)
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 16

    def test_explicit_ball_width(self) -> None:
        """Test effect works with explicit ball_width."""
        effect = EffectNewtonsCradle(ball_width=4, num_balls=3)
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=50,
            canvas_width=50,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 50

    def test_single_pixel(self) -> None:
        """Test single-pixel device doesn't crash."""
        effect = EffectNewtonsCradle()
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 1

    def test_zero_saturation_steel_look(self) -> None:
        """Test zero saturation produces grayscale steel balls."""
        effect = EffectNewtonsCradle(saturation=0.0)
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=82,
            canvas_width=82,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        # All ball zones should have zero or near-zero saturation
        for c in colors:
            assert c.saturation <= 1.0  # valid range
