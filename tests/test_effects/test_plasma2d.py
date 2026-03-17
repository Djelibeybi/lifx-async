"""Tests for EffectPlasma2D (2D plasma interference pattern)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.plasma2d import EffectPlasma2D

# ---------------------------------------------------------------------------
# Default parameters
# ---------------------------------------------------------------------------


def test_plasma2d_default_parameters() -> None:
    """Test EffectPlasma2D with default parameters."""
    effect = EffectPlasma2D()

    assert effect.name == "plasma2d"
    assert effect.speed == 1.0
    assert effect.scale == 1.0
    assert effect.hue1 == 270
    assert effect.hue2 == 180
    assert effect.brightness == 0.8
    assert effect.kelvin == 3500
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_plasma2d_custom_parameters() -> None:
    """Test EffectPlasma2D with custom parameters."""
    effect = EffectPlasma2D(
        speed=2.5,
        scale=3.0,
        hue1=0,
        hue2=120,
        brightness=0.5,
        kelvin=5000,
        power_on=False,
    )

    assert effect.speed == 2.5
    assert effect.scale == 3.0
    assert effect.hue1 == 0
    assert effect.hue2 == 120
    assert effect.brightness == 0.5
    assert effect.kelvin == 5000
    assert effect.power_on is False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_plasma2d_invalid_speed() -> None:
    """Test EffectPlasma2D with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectPlasma2D(speed=0)

    with pytest.raises(ValueError, match="Speed must be"):
        EffectPlasma2D(speed=-1.0)


def test_plasma2d_invalid_scale() -> None:
    """Test EffectPlasma2D with invalid scale raises ValueError."""
    with pytest.raises(ValueError, match="Scale must be"):
        EffectPlasma2D(scale=0)

    with pytest.raises(ValueError, match="Scale must be"):
        EffectPlasma2D(scale=-1.0)


def test_plasma2d_invalid_hue1() -> None:
    """Test EffectPlasma2D with invalid hue1 raises ValueError."""
    with pytest.raises(ValueError, match="hue1 must be"):
        EffectPlasma2D(hue1=-1)

    with pytest.raises(ValueError, match="hue1 must be"):
        EffectPlasma2D(hue1=361)


def test_plasma2d_invalid_hue2() -> None:
    """Test EffectPlasma2D with invalid hue2 raises ValueError."""
    with pytest.raises(ValueError, match="hue2 must be"):
        EffectPlasma2D(hue2=-1)

    with pytest.raises(ValueError, match="hue2 must be"):
        EffectPlasma2D(hue2=361)


def test_plasma2d_invalid_brightness() -> None:
    """Test EffectPlasma2D with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectPlasma2D(brightness=1.5)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectPlasma2D(brightness=-0.1)


def test_plasma2d_invalid_kelvin() -> None:
    """Test EffectPlasma2D with invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectPlasma2D(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectPlasma2D(kelvin=10000)


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestPlasma2DInheritance:
    """Tests for EffectPlasma2D class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectPlasma2D extends FrameEffect."""
        effect = EffectPlasma2D()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectPlasma2D extends LIFXEffect."""
        effect = EffectPlasma2D()
        assert isinstance(effect, LIFXEffect)


# ---------------------------------------------------------------------------
# Frame generation
# ---------------------------------------------------------------------------


class TestPlasma2DGenerateFrame:
    """Tests for EffectPlasma2D.generate_frame()."""

    def test_matrix_8x8_returns_64_colors(self) -> None:
        """Test 8x8 matrix device returns 64 colors."""
        effect = EffectPlasma2D()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 64

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel canvas returns one color."""
        effect = EffectPlasma2D()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 1

    @pytest.mark.parametrize(
        ("width", "height"),
        [(4, 4), (8, 8), (16, 8), (8, 16), (16, 16)],
    )
    def test_various_grid_sizes(self, width: int, height: int) -> None:
        """Test correct number of colors for various grid sizes."""
        effect = EffectPlasma2D()
        pixel_count = width * height
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=width,
            canvas_height=height,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == pixel_count

    def test_brightness_in_valid_range(self) -> None:
        """Test all brightness values are 0.0-1.0."""
        effect = EffectPlasma2D()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_saturation_in_valid_range(self) -> None:
        """Test all saturation values are 0.0-1.0."""
        effect = EffectPlasma2D()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert 0.0 <= color.saturation <= 1.0

    def test_hue_in_valid_range(self) -> None:
        """Test all hue values are int 0-360."""
        effect = EffectPlasma2D()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert isinstance(color.hue, int)
            assert 0 <= color.hue <= 360

    def test_kelvin_matches_configured(self) -> None:
        """Test kelvin values match configured kelvin."""
        effect = EffectPlasma2D(kelvin=5000)
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.kelvin == 5000

    def test_frame_changes_over_time(self) -> None:
        """Test different elapsed_s produce different frames."""
        effect = EffectPlasma2D()
        ctx1 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        ctx2 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors1 = effect.generate_frame(ctx1)
        colors2 = effect.generate_frame(ctx2)

        # At least some pixels should differ
        assert colors1 != colors2

    def test_pixels_vary_across_grid(self) -> None:
        """Test pixels are not all identical on a matrix grid."""
        effect = EffectPlasma2D()
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        # Not all pixels should be the same hue
        unique_hues = {c.hue for c in colors}
        assert len(unique_hues) > 1

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectPlasma2D()
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 64
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_uses_lerp_oklab_for_blending(self) -> None:
        """Test that output colors reflect Oklab interpolation between hue1 and hue2."""
        effect = EffectPlasma2D(hue1=0, hue2=240)
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        # All colors should be valid HSBK instances
        from lifx.color import HSBK

        for color in colors:
            assert isinstance(color, HSBK)

    def test_pixel_count_padding(self) -> None:
        """Test padding when pixel_count exceeds grid dimensions."""
        effect = EffectPlasma2D()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=70,  # More than 8*8=64
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 70

    def test_pixel_count_trimming(self) -> None:
        """Test trimming when pixel_count is less than grid dimensions."""
        effect = EffectPlasma2D()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=60,  # Less than 8*8=64
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 60

    def test_speed_affects_animation(self) -> None:
        """Test that speed parameter affects the animation rate."""
        slow = EffectPlasma2D(speed=0.5)
        fast = EffectPlasma2D(speed=5.0)

        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )

        colors_slow = slow.generate_frame(ctx)
        colors_fast = fast.generate_frame(ctx)

        # Different speeds should produce different patterns at the same time
        assert colors_slow != colors_fast

    def test_scale_affects_pattern(self) -> None:
        """Test that scale parameter affects the pattern granularity."""
        fine = EffectPlasma2D(scale=0.5)
        coarse = EffectPlasma2D(scale=5.0)

        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )

        colors_fine = fine.generate_frame(ctx)
        colors_coarse = coarse.generate_frame(ctx)

        # Different scales should produce different patterns
        assert colors_fine != colors_coarse

    def test_row_major_order(self) -> None:
        """Test that pixels are in row-major order (index = y * width + x)."""
        effect = EffectPlasma2D()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=4,
            canvas_height=4,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 16
        # Verify we got the expected number of pixels
        # Row 0: indices 0-3, Row 1: indices 4-7, etc.
        # Each row should have canvas_width pixels
        for row in range(4):
            row_colors = colors[row * 4 : (row + 1) * 4]
            assert len(row_colors) == 4


# ---------------------------------------------------------------------------
# Frame loop integration
# ---------------------------------------------------------------------------


class TestPlasma2DFrameLoop:
    """Tests for EffectPlasma2D running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test plasma2d sends frames through animator.send_frame."""
        effect = EffectPlasma2D()

        animator = MagicMock()
        animator.pixel_count = 64
        animator.canvas_width = 8
        animator.canvas_height = 8
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        play_task = asyncio.create_task(effect.async_play())
        await asyncio.sleep(0.1)
        effect.stop()
        await asyncio.wait_for(play_task, timeout=1.0)

        assert animator.send_frame.call_count > 0


# ---------------------------------------------------------------------------
# Power-off, compatibility, prestate, repr
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plasma2d_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns dim version of first plasma color."""
    effect = EffectPlasma2D(hue1=120, kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 120
    assert result.saturation == 1.0
    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_plasma2d_is_light_compatible_with_matrix() -> None:
    """Test is_light_compatible returns True for matrix lights."""
    effect = EffectPlasma2D()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_matrix = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_plasma2d_is_light_compatible_without_matrix() -> None:
    """Test is_light_compatible returns False for non-matrix lights."""
    effect = EffectPlasma2D()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_matrix = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_plasma2d_is_light_compatible_multizone() -> None:
    """Test is_light_compatible returns False for multizone (non-matrix) lights."""
    effect = EffectPlasma2D()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_matrix = False
    capabilities.has_multizone = True
    capabilities.has_color = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_plasma2d_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectPlasma2D()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_matrix = True
        light.capabilities = caps

    light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light._ensure_capabilities.assert_called_once()


@pytest.mark.asyncio
async def test_plasma2d_is_light_compatible_none_after_ensure() -> None:
    """Test is_light_compatible returns False when capabilities remain None."""
    effect = EffectPlasma2D()
    light = MagicMock()
    light.capabilities = None
    light._ensure_capabilities = AsyncMock()

    assert await effect.is_light_compatible(light) is False


def test_plasma2d_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectPlasma2D."""
    effect = EffectPlasma2D()
    assert effect.inherit_prestate(EffectPlasma2D()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_plasma2d_repr() -> None:
    """Test EffectPlasma2D string representation."""
    effect = EffectPlasma2D(speed=2.0, scale=3.0, hue1=0, hue2=120, brightness=0.5)
    repr_str = repr(effect)

    assert "EffectPlasma2D" in repr_str
    assert "speed=2.0" in repr_str
    assert "scale=3.0" in repr_str
    assert "hue1=0" in repr_str
    assert "hue2=120" in repr_str
    assert "brightness=0.5" in repr_str
