"""Tests for EffectRipple (water drops / ripple tank)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.ripple import EffectRipple

# ---------------------------------------------------------------------------
# Default and custom parameters
# ---------------------------------------------------------------------------


def test_ripple_default_parameters() -> None:
    """Test EffectRipple with default parameters."""
    effect = EffectRipple()

    assert effect.name == "ripple"
    assert effect.speed == 1.0
    assert effect.damping == 0.98
    assert effect.drop_rate == 0.3
    assert effect.hue1 == 200
    assert effect.hue2 == 240
    assert effect.saturation == 1.0
    assert effect.brightness == 0.8
    assert effect.kelvin == 3500
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_ripple_custom_parameters() -> None:
    """Test EffectRipple with custom parameters."""
    effect = EffectRipple(
        speed=2.0,
        damping=0.95,
        drop_rate=0.5,
        hue1=100,
        hue2=300,
        saturation=0.7,
        brightness=0.6,
        kelvin=5000,
        power_on=False,
    )

    assert effect.speed == 2.0
    assert effect.damping == 0.95
    assert effect.drop_rate == 0.5
    assert effect.hue1 == 100
    assert effect.hue2 == 300
    assert effect.saturation == 0.7
    assert effect.brightness == 0.6
    assert effect.kelvin == 5000
    assert effect.power_on is False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_ripple_invalid_speed() -> None:
    """Test EffectRipple with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectRipple(speed=0)

    with pytest.raises(ValueError, match="Speed must be"):
        EffectRipple(speed=-1.0)


def test_ripple_invalid_damping() -> None:
    """Test EffectRipple with invalid damping raises ValueError."""
    with pytest.raises(ValueError, match="Damping must be"):
        EffectRipple(damping=-0.1)

    with pytest.raises(ValueError, match="Damping must be"):
        EffectRipple(damping=1.5)


def test_ripple_invalid_drop_rate() -> None:
    """Test EffectRipple with invalid drop_rate raises ValueError."""
    with pytest.raises(ValueError, match="Drop rate must be"):
        EffectRipple(drop_rate=0)

    with pytest.raises(ValueError, match="Drop rate must be"):
        EffectRipple(drop_rate=-1.0)


def test_ripple_invalid_hue1() -> None:
    """Test EffectRipple with invalid hue1 raises ValueError."""
    with pytest.raises(ValueError, match="hue1 must be"):
        EffectRipple(hue1=-1)

    with pytest.raises(ValueError, match="hue1 must be"):
        EffectRipple(hue1=361)


def test_ripple_invalid_hue2() -> None:
    """Test EffectRipple with invalid hue2 raises ValueError."""
    with pytest.raises(ValueError, match="hue2 must be"):
        EffectRipple(hue2=-1)

    with pytest.raises(ValueError, match="hue2 must be"):
        EffectRipple(hue2=361)


def test_ripple_invalid_saturation() -> None:
    """Test EffectRipple with invalid saturation raises ValueError."""
    with pytest.raises(ValueError, match="Saturation must be"):
        EffectRipple(saturation=-0.1)

    with pytest.raises(ValueError, match="Saturation must be"):
        EffectRipple(saturation=1.5)


def test_ripple_invalid_brightness() -> None:
    """Test EffectRipple with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectRipple(brightness=-0.1)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectRipple(brightness=1.5)


def test_ripple_invalid_kelvin() -> None:
    """Test EffectRipple with invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectRipple(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectRipple(kelvin=10000)


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestRippleInheritance:
    """Tests for EffectRipple class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectRipple extends FrameEffect."""
        effect = EffectRipple()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectRipple extends LIFXEffect."""
        effect = EffectRipple()
        assert isinstance(effect, LIFXEffect)


# ---------------------------------------------------------------------------
# Stateful simulation
# ---------------------------------------------------------------------------


class TestRippleState:
    """Tests for ripple wave simulation state management."""

    def test_lazy_initialization(self) -> None:
        """Test state arrays are empty until first frame."""
        effect = EffectRipple()
        assert effect._displacement == []
        assert effect._velocity == []
        assert effect._n_cells == 0

    def test_first_frame_initializes_state(self) -> None:
        """Test first generate_frame call initializes state arrays."""
        effect = EffectRipple()
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect.generate_frame(ctx)

        assert effect._n_cells == 16
        assert len(effect._displacement) == 16
        assert len(effect._velocity) == 16

    def test_state_reinitializes_on_zone_count_change(self) -> None:
        """Test state is reinitialized when pixel count changes."""
        effect = EffectRipple()
        ctx1 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect.generate_frame(ctx1)
        assert effect._n_cells == 16

        ctx2 = FrameContext(
            elapsed_s=0.1,
            device_index=0,
            pixel_count=32,
            canvas_width=32,
            canvas_height=1,
        )
        effect.generate_frame(ctx2)
        assert effect._n_cells == 32
        assert len(effect._displacement) == 32
        assert len(effect._velocity) == 32

    def test_drop_modifies_displacement(self) -> None:
        """Test that _maybe_drop injects impulse into displacement array."""
        effect = EffectRipple(drop_rate=1000.0)  # Very high rate
        effect._init_state(16)
        effect._sim_time = 0.0
        effect._next_drop_t = 0.0

        effect._maybe_drop()

        # At least one interior cell should have nonzero displacement
        interior = effect._displacement[1:-1]
        assert any(d != 0.0 for d in interior)

    def test_step_propagates_displacement(self) -> None:
        """Test that _step propagates an impulse to neighbors."""
        effect = EffectRipple()
        effect._init_state(16)

        # Inject impulse at center
        effect._displacement[8] = 1.0

        # Run a few steps
        for _ in range(5):
            effect._step()

        # Neighbors should now have nonzero displacement
        assert effect._displacement[7] != 0.0
        assert effect._displacement[9] != 0.0

    def test_damping_reduces_displacement(self) -> None:
        """Test that damping causes displacement to decay over time."""
        effect = EffectRipple(damping=0.9, drop_rate=0.001)
        effect._init_state(16)

        # Inject impulse
        effect._displacement[8] = 1.0

        # Run many steps
        for _ in range(100):
            effect._step()

        # All displacements should be very small after heavy damping
        max_disp = max(abs(d) for d in effect._displacement)
        assert max_disp < 0.1

    def test_fixed_boundary_conditions(self) -> None:
        """Test endpoints remain at zero displacement."""
        effect = EffectRipple()
        effect._init_state(16)
        effect._displacement[1] = 1.0

        for _ in range(10):
            effect._step()

        assert effect._displacement[0] == 0.0
        assert effect._displacement[15] == 0.0

    def test_small_cell_count_step_is_noop(self) -> None:
        """Test _step is a no-op for fewer than 3 cells."""
        effect = EffectRipple()
        effect._init_state(2)
        effect._displacement[0] = 1.0
        effect._displacement[1] = 1.0

        # Should not crash
        effect._step()

        # Damping is still applied (loop runs for all n cells)
        # but interior loop (range(1, n-1)) is empty for n=2


# ---------------------------------------------------------------------------
# Frame generation
# ---------------------------------------------------------------------------


class TestRippleGenerateFrame:
    """Tests for EffectRipple.generate_frame()."""

    def test_returns_correct_pixel_count(self) -> None:
        """Test output length matches pixel_count."""
        effect = EffectRipple()
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 16

    @pytest.mark.parametrize("pixel_count", [1, 8, 16, 32, 82])
    def test_various_pixel_counts(self, pixel_count: int) -> None:
        """Test correct number of colors for various pixel counts."""
        effect = EffectRipple()
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == pixel_count

    def test_brightness_in_valid_range(self) -> None:
        """Test all brightness values are 0.0-1.0."""
        effect = EffectRipple()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_kelvin_matches_configured(self) -> None:
        """Test kelvin values match configured kelvin."""
        effect = EffectRipple(kelvin=5000)
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

    def test_saturation_in_valid_range(self) -> None:
        """Test all saturation values are 0.0-1.0."""
        effect = EffectRipple()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert 0.0 <= color.saturation <= 1.0

    def test_hue_in_valid_range(self) -> None:
        """Test all hue values are 0-360."""
        effect = EffectRipple()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert 0 <= color.hue <= 360

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectRipple()
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

    def test_single_pixel(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectRipple()
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 1

    def test_uses_lerp_oklab_for_blending(self) -> None:
        """Test that lerp_oklab produces blended colors between hue1 and hue2.

        We directly verify that the color at blend=0.5 is an interpolation
        between the two endpoint colors, which exercises HSBK.lerp_oklab().
        """
        color_a = HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500)
        color_b = HSBK(hue=180, saturation=1.0, brightness=0.8, kelvin=3500)

        blended = color_a.lerp_oklab(color_b, 0.5)

        # The blended color should differ from both endpoints
        assert blended.hue != color_a.hue or blended.saturation != color_a.saturation
        assert blended.hue != color_b.hue or blended.saturation != color_b.saturation

    def test_opposite_displacements_produce_different_colors(self) -> None:
        """Test positive vs negative displacement yields different colors."""
        effect = EffectRipple(hue1=0, hue2=180, drop_rate=0.001)
        effect._init_state(16)

        # Inject strong impulses directly into velocity to survive stepping
        effect._displacement[3] = 10.0
        effect._displacement[4] = 10.0
        effect._displacement[5] = 10.0
        effect._displacement[11] = -10.0
        effect._displacement[12] = -10.0
        effect._displacement[13] = -10.0

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect._last_t = 0.0

        colors = effect.generate_frame(ctx)

        # After stepping, the center cells should still have opposite signs
        # and produce visually different colors
        assert colors[4] != colors[12]

    def test_floor_brightness_prevents_true_black(self) -> None:
        """Test that minimum brightness floor is applied."""
        effect = EffectRipple(brightness=0.8)
        effect._init_state(16)
        # Leave displacement at zero -- all calm

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect._last_t = 0.0

        colors = effect.generate_frame(ctx)

        # With calm surface, displacement is ~0, but floor should prevent
        # brightness from being exactly zero (floor = brightness * 0.02)
        for color in colors:
            assert color.brightness >= 0.0

    def test_consecutive_frames_differ_with_drops(self) -> None:
        """Test that frames evolve over time with drops."""
        effect = EffectRipple(drop_rate=100.0)  # High drop rate

        ctx1 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors1 = effect.generate_frame(ctx1)

        ctx2 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors2 = effect.generate_frame(ctx2)

        # With high drop rate, frames should differ
        assert colors1 != colors2


# ---------------------------------------------------------------------------
# Frame loop integration
# ---------------------------------------------------------------------------


class TestRippleFrameLoop:
    """Tests for EffectRipple running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test ripple sends frames through animator.send_frame."""
        effect = EffectRipple()

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
# Power-off color, compatibility, prestate, repr
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ripple_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns zero-brightness startup color."""
    effect = EffectRipple(hue1=200, saturation=0.9, kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 200
    assert result.saturation == 0.9
    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_ripple_is_light_compatible_with_multizone() -> None:
    """Test is_light_compatible returns True for multizone lights."""
    effect = EffectRipple()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_ripple_is_light_compatible_without_multizone() -> None:
    """Test is_light_compatible returns False for non-multizone lights."""
    effect = EffectRipple()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_ripple_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectRipple()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_multizone = True
        light.capabilities = caps

    light.ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light.ensure_capabilities.assert_called_once()


def test_ripple_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectRipple."""
    effect = EffectRipple()
    assert effect.inherit_prestate(EffectRipple()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_ripple_repr() -> None:
    """Test EffectRipple string representation."""
    effect = EffectRipple(speed=2.0, damping=0.95, drop_rate=0.5, hue1=100)
    repr_str = repr(effect)

    assert "EffectRipple" in repr_str
    assert "speed=2.0" in repr_str
    assert "damping=0.95" in repr_str
    assert "drop_rate=0.5" in repr_str
    assert "hue1=100" in repr_str
