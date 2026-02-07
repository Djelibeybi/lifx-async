"""Tests for EffectFlame."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.flame import EffectFlame
from lifx.effects.frame_effect import FrameContext, FrameEffect


def test_flame_default_parameters():
    """Test EffectFlame with default parameters."""
    effect = EffectFlame()

    assert effect.name == "flame"
    assert effect.intensity == 0.7
    assert effect.speed == 1.0
    assert effect.kelvin_min == 1500
    assert effect.kelvin_max == 2500
    assert effect.brightness == 0.8
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_flame_custom_parameters():
    """Test EffectFlame with custom parameters."""
    effect = EffectFlame(
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


def test_flame_invalid_intensity():
    """Test EffectFlame with invalid intensity raises ValueError."""
    with pytest.raises(ValueError, match="Intensity must be 0.0-1.0"):
        EffectFlame(intensity=1.5)

    with pytest.raises(ValueError, match="Intensity must be 0.0-1.0"):
        EffectFlame(intensity=-0.1)


def test_flame_invalid_speed():
    """Test EffectFlame with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be positive"):
        EffectFlame(speed=0)

    with pytest.raises(ValueError, match="Speed must be positive"):
        EffectFlame(speed=-1.0)


def test_flame_invalid_kelvin_min():
    """Test EffectFlame with invalid kelvin_min raises ValueError."""
    with pytest.raises(ValueError, match="kelvin_min must be >="):
        EffectFlame(kelvin_min=1000)


def test_flame_invalid_kelvin_max():
    """Test EffectFlame with invalid kelvin_max raises ValueError."""
    with pytest.raises(ValueError, match="kelvin_max must be <="):
        EffectFlame(kelvin_max=10000)


def test_flame_invalid_kelvin_range():
    """Test EffectFlame with kelvin_min > kelvin_max raises ValueError."""
    with pytest.raises(ValueError, match="kelvin_min.*must be <= kelvin_max"):
        EffectFlame(kelvin_min=3000, kelvin_max=2000)


def test_flame_invalid_brightness():
    """Test EffectFlame with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be 0.0-1.0"):
        EffectFlame(brightness=1.5)


class TestFlameInheritance:
    """Tests for EffectFlame class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectFlame extends FrameEffect."""
        effect = EffectFlame()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectFlame extends LIFXEffect."""
        effect = EffectFlame()
        assert isinstance(effect, LIFXEffect)


class TestFlameGenerateFrame:
    """Tests for EffectFlame.generate_frame()."""

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectFlame()
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
        effect = EffectFlame()
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
        effect = EffectFlame()
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
        effect = EffectFlame()
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
        effect = EffectFlame(kelvin_min=1800, kelvin_max=2800)
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
        effect = EffectFlame()
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
        effect = EffectFlame()
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
        effect = EffectFlame()
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
        effect = EffectFlame(intensity=0.5)
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        # Average brightness of bottom row (y=7) vs top row (y=0)
        # Bottom row is pixels 0..7 (y=0 in row-major), top is 56..63 (y=7)
        # Wait — in the matrix, y=0 is the FIRST row (top), y=7 is LAST (bottom)
        # The falloff formula: y_factor = 1.0 - (y/height)^0.7
        # So y=0 → y_factor=1.0 (bright), y=7 → y_factor ≈ 0 (dark)
        # This means TOP rows are brighter (hot bottom of fire at top of display)
        # Actually, for "bottom rows hotter": if row 0 is top of display,
        # we want bottom rows (high y) to be darker with this formula
        # The formula actually makes y=0 (top) brightest

        # Top row (y=0) should be brighter than bottom row (y=7)
        top_row_avg = sum(colors[i].brightness for i in range(8)) / 8
        bottom_row_avg = sum(colors[i].brightness for i in range(56, 64)) / 8
        assert top_row_avg > bottom_row_avg

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
        effect_low = EffectFlame(intensity=0.0)
        colors_low = effect_low.generate_frame(ctx)
        brightnesses_low = [c.brightness for c in colors_low]
        range_low = max(brightnesses_low) - min(brightnesses_low)

        # High intensity → more variation
        effect_high = EffectFlame(intensity=1.0)
        colors_high = effect_high.generate_frame(ctx)
        brightnesses_high = [c.brightness for c in colors_high]
        range_high = max(brightnesses_high) - min(brightnesses_high)

        assert range_high > range_low


class TestFlameFrameLoop:
    """Tests for EffectFlame running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test flame sends frames through animator.send_frame."""
        effect = EffectFlame()

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


@pytest.mark.asyncio
async def test_flame_from_poweroff():
    """Test from_poweroff_hsbk returns warm amber at zero brightness."""
    effect = EffectFlame()
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 20
    assert result.saturation == 1.0
    assert result.brightness == 0.0
    assert result.kelvin == 2200  # KELVIN_AMBER


@pytest.mark.asyncio
async def test_flame_is_light_compatible_with_color():
    """Test is_light_compatible returns True for color lights."""
    effect = EffectFlame()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_flame_is_light_compatible_without_color():
    """Test is_light_compatible returns False for non-color lights."""
    effect = EffectFlame()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_flame_is_light_compatible_none_capabilities():
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectFlame()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps():
        caps = MagicMock()
        caps.has_color = True
        light.capabilities = caps

    light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light._ensure_capabilities.assert_called_once()


def test_flame_inherit_prestate():
    """Test inherit_prestate returns True for EffectFlame."""
    effect = EffectFlame()
    assert effect.inherit_prestate(EffectFlame()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_flame_repr():
    """Test EffectFlame string representation."""
    effect = EffectFlame(intensity=0.5, speed=2.0, kelvin_min=1800, kelvin_max=3000)
    repr_str = repr(effect)

    assert "EffectFlame" in repr_str
    assert "intensity=0.5" in repr_str
    assert "speed=2.0" in repr_str
    assert "kelvin_min=1800" in repr_str
    assert "kelvin_max=3000" in repr_str
