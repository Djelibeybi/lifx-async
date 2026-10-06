"""Tests for EffectFlicker."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.flicker import EffectFlicker
from lifx.effects.frame_effect import FrameContext, FrameEffect


def test_flicker_default_parameters() -> None:
    """Test EffectFlicker with default parameters."""
    effect = EffectFlicker()

    assert effect.name == "flicker"
    assert effect.intensity == 0.7
    assert effect.speed == 1.0
    assert effect.kelvin_min == 1500
    assert effect.kelvin_max == 2500
    assert effect.brightness == 0.8
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_flicker_custom_parameters() -> None:
    """Test EffectFlicker with custom parameters."""
    effect = EffectFlicker(
        intensity=0.5,
        speed=2.0,
        kelvin_min=1800,
        kelvin_max=3000,
        brightness=0.6,
        power_on=False,
    )

    assert effect.intensity == 0.5
    assert effect.speed == 2.0
    assert effect.kelvin_min == 1800
    assert effect.kelvin_max == 3000
    assert effect.brightness == 0.6
    assert effect.power_on is False


def test_flicker_invalid_intensity() -> None:
    """Test EffectFlicker with invalid intensity raises ValueError."""
    with pytest.raises(ValueError, match="Intensity must be 0.0-1.0"):
        EffectFlicker(intensity=1.5)

    with pytest.raises(ValueError, match="Intensity must be 0.0-1.0"):
        EffectFlicker(intensity=-0.1)


def test_flicker_invalid_speed() -> None:
    """Test EffectFlicker with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be positive"):
        EffectFlicker(speed=0)

    with pytest.raises(ValueError, match="Speed must be positive"):
        EffectFlicker(speed=-1.0)


def test_flicker_invalid_kelvin_min() -> None:
    """Test EffectFlicker with invalid kelvin_min raises ValueError."""
    with pytest.raises(ValueError, match="kelvin_min must be >="):
        EffectFlicker(kelvin_min=1000)


def test_flicker_invalid_kelvin_max() -> None:
    """Test EffectFlicker with invalid kelvin_max raises ValueError."""
    with pytest.raises(ValueError, match="kelvin_max must be <="):
        EffectFlicker(kelvin_max=10000)


def test_flicker_invalid_kelvin_range() -> None:
    """Test EffectFlicker with kelvin_min > kelvin_max raises ValueError."""
    with pytest.raises(ValueError, match="kelvin_min.*must be <= kelvin_max"):
        EffectFlicker(kelvin_min=3000, kelvin_max=2000)


def test_flicker_invalid_brightness() -> None:
    """Test EffectFlicker with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be 0.0-1.0"):
        EffectFlicker(brightness=1.5)


class TestFlickerInheritance:
    """Tests for EffectFlicker class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectFlicker extends FrameEffect."""
        effect = EffectFlicker()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectFlicker extends LIFXEffect."""
        effect = EffectFlicker()
        assert isinstance(effect, LIFXEffect)


class TestFlickerGenerateFrame:
    """Tests for EffectFlicker.generate_frame()."""

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectFlicker()
        ctx = FrameContext(
            elapsed_s=1.0,
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
        effect = EffectFlicker()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == pixel_count

    def test_hue_in_warm_range(self) -> None:
        """Test all hues are in warm range 0-40."""
        effect = EffectFlicker()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert 0 <= color.hue <= 40

    def test_saturation_in_range(self) -> None:
        """Test all saturations are in expected range 0.85-1.0."""
        effect = EffectFlicker()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert 0.85 <= color.saturation <= 1.0

    def test_kelvin_in_configured_range(self) -> None:
        """Test kelvin values fall between kelvin_min and kelvin_max."""
        effect = EffectFlicker(kelvin_min=1800, kelvin_max=2800)
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert 1800 <= color.kelvin <= 2800

    def test_brightness_in_valid_range(self) -> None:
        """Test all brightness values are 0.0-1.0."""
        effect = EffectFlicker()
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

    def test_frame_changes_over_time(self) -> None:
        """Test different elapsed_s produce different frames."""
        effect = EffectFlicker()
        ctx1 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        ctx2 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        colors1 = effect.generate_frame(ctx1)
        colors2 = effect.generate_frame(ctx2)

        # At least some pixels should differ
        assert colors1 != colors2

    def test_pixels_vary_across_strip(self) -> None:
        """Test pixels are not all identical on a multizone strip."""
        effect = EffectFlicker()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # Not all pixels should be the same
        unique_brightnesses = {c.brightness for c in colors}
        assert len(unique_brightnesses) > 1

    def test_matrix_bottom_brighter_than_top(self) -> None:
        """Test vertical gradient on 8x8 canvas (bottom hotter)."""
        effect = EffectFlicker(intensity=0.5)
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        # Row-major with row 0 at the top: the top row is pixels 0..7 and
        # the bottom row is pixels 56..63
        top_row_avg = sum(colors[i].brightness for i in range(8)) / 8
        bottom_row_avg = sum(colors[i].brightness for i in range(56, 64)) / 8
        assert bottom_row_avg > top_row_avg

    def test_intensity_affects_variation(self) -> None:
        """Test that higher intensity produces more brightness variation."""
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )

        # Low intensity → less variation
        effect_low = EffectFlicker(intensity=0.0)
        colors_low = effect_low.generate_frame(ctx)
        brightnesses_low = [c.brightness for c in colors_low]
        range_low = max(brightnesses_low) - min(brightnesses_low)

        # High intensity → more variation
        effect_high = EffectFlicker(intensity=1.0)
        colors_high = effect_high.generate_frame(ctx)
        brightnesses_high = [c.brightness for c in colors_high]
        range_high = max(brightnesses_high) - min(brightnesses_high)

        assert range_high > range_low


class TestFlickerFrameLoop:
    """Tests for EffectFlicker running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test flicker sends frames through animator.send_frame."""
        effect = EffectFlicker()

        animator = MagicMock()
        animator.pixel_count = 16
        animator.canvas_width = 16
        animator.canvas_height = 1
        animator.wraps = False
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        play_task = asyncio.create_task(effect.async_play())
        await asyncio.sleep(0.1)
        effect.stop()
        await asyncio.wait_for(play_task, timeout=1.0)

        assert animator.send_frame.call_count > 0


@pytest.mark.asyncio
async def test_flicker_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns warm amber at zero brightness."""
    effect = EffectFlicker()
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 20
    assert result.saturation == 1.0
    assert result.brightness == 0.0
    assert result.kelvin == 2200  # KELVIN_AMBER


@pytest.mark.asyncio
async def test_flicker_is_light_compatible_with_color() -> None:
    """Test is_light_compatible returns True for color lights."""
    effect = EffectFlicker()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_flicker_is_light_compatible_without_color() -> None:
    """Test is_light_compatible returns False for non-color lights."""
    effect = EffectFlicker()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_flicker_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectFlicker()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_color = True
        light.capabilities = caps

    light.ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light.ensure_capabilities.assert_called_once()


def test_flicker_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectFlicker."""
    effect = EffectFlicker()
    assert effect.inherit_prestate(EffectFlicker()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_flicker_repr() -> None:
    """Test EffectFlicker string representation."""
    effect = EffectFlicker(intensity=0.5, speed=2.0, kelvin_min=1800, kelvin_max=3000)
    repr_str = repr(effect)

    assert "EffectFlicker" in repr_str
    assert "intensity=0.5" in repr_str
    assert "speed=2.0" in repr_str
    assert "kelvin_min=1800" in repr_str
    assert "kelvin_max=3000" in repr_str
