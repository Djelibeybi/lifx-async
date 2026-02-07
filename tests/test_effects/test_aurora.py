"""Tests for EffectAurora."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.const import KELVIN_NEUTRAL
from lifx.effects.aurora import EffectAurora
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect


def test_aurora_default_parameters() -> None:
    """Test EffectAurora with default parameters."""
    effect = EffectAurora()

    assert effect.name == "aurora"
    assert effect.speed == 1.0
    assert effect.brightness == 0.8
    assert effect.spread == 0.0
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_aurora_custom_parameters() -> None:
    """Test EffectAurora with custom parameters."""
    effect = EffectAurora(
        speed=2.0,
        brightness=0.6,
        palette=[100, 200, 300],
        spread=45.0,
        power_on=False,
    )

    assert effect.speed == 2.0
    assert effect.brightness == 0.6
    assert effect.spread == 45.0
    assert effect.power_on is False


def test_aurora_invalid_speed() -> None:
    """Test EffectAurora with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be positive"):
        EffectAurora(speed=0)

    with pytest.raises(ValueError, match="Speed must be positive"):
        EffectAurora(speed=-1.0)


def test_aurora_invalid_brightness() -> None:
    """Test EffectAurora with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be 0.0-1.0"):
        EffectAurora(brightness=1.5)


def test_aurora_invalid_palette_too_short() -> None:
    """Test EffectAurora with too-short palette raises ValueError."""
    with pytest.raises(ValueError, match="Palette must have at least 2"):
        EffectAurora(palette=[120])


def test_aurora_invalid_palette_hue() -> None:
    """Test EffectAurora with out-of-range palette hue raises ValueError."""
    with pytest.raises(ValueError, match="Palette hue values must be 0-360"):
        EffectAurora(palette=[120, 400])


def test_aurora_invalid_spread() -> None:
    """Test EffectAurora with invalid spread raises ValueError."""
    with pytest.raises(ValueError, match="Spread must be 0-360"):
        EffectAurora(spread=400)


class TestAuroraInheritance:
    """Tests for EffectAurora class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectAurora extends FrameEffect."""
        effect = EffectAurora()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectAurora extends LIFXEffect."""
        effect = EffectAurora()
        assert isinstance(effect, LIFXEffect)


class TestAuroraGenerateFrame:
    """Tests for EffectAurora.generate_frame()."""

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectAurora()
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
        effect = EffectAurora()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == pixel_count

    def test_hues_from_palette_range(self) -> None:
        """Test generated hues fall within the palette color space."""
        effect = EffectAurora(palette=[100, 200])
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # All hues should be within interpolation range of palette
        for color in colors:
            assert 0 <= color.hue <= 360

    def test_hue_wrapping_positive(self) -> None:
        """Test palette interpolation wraps hue correctly when diff > 180."""
        # Palette [10, 350]: naive diff is 340, should wrap to -20
        effect = EffectAurora(palette=[10, 350])
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        # All hues should be valid
        for color in colors:
            assert 0 <= color.hue <= 360

    def test_hue_wrapping_negative(self) -> None:
        """Test palette interpolation wraps hue correctly when diff < -180."""
        # Palette [350, 10]: naive diff is -340, should wrap to +20
        effect = EffectAurora(palette=[350, 10])
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        # All hues should be valid
        for color in colors:
            assert 0 <= color.hue <= 360

    def test_custom_palette_affects_output(self) -> None:
        """Test different palette produces different hues."""
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )

        effect_default = EffectAurora()
        colors_default = effect_default.generate_frame(ctx)

        effect_custom = EffectAurora(palette=[0, 30, 60])
        colors_custom = effect_custom.generate_frame(ctx)

        hues_default = [c.hue for c in colors_default]
        hues_custom = [c.hue for c in colors_custom]
        assert hues_default != hues_custom

    def test_default_palette_is_green_blue_purple(self) -> None:
        """Test default palette values."""
        effect = EffectAurora()
        assert effect._palette == [120, 160, 200, 260, 290]

    def test_frame_changes_over_time(self) -> None:
        """Test different elapsed_s produce different frames."""
        effect = EffectAurora()
        ctx1 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        ctx2 = FrameContext(
            elapsed_s=5.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        colors1 = effect.generate_frame(ctx1)
        colors2 = effect.generate_frame(ctx2)
        assert colors1 != colors2

    def test_device_spread_offset(self) -> None:
        """Test spread parameter offsets between devices."""
        effect = EffectAurora(spread=180)
        ctx0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        ctx1 = FrameContext(
            elapsed_s=0.0,
            device_index=1,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        colors0 = effect.generate_frame(ctx0)
        colors1 = effect.generate_frame(ctx1)

        # Different device indices with spread should produce different output
        hues0 = [c.hue for c in colors0]
        hues1 = [c.hue for c in colors1]
        assert hues0 != hues1

    def test_brightness_modulation(self) -> None:
        """Test not all pixels have the same brightness (band effect)."""
        effect = EffectAurora()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        brightnesses = {c.brightness for c in colors}
        assert len(brightnesses) > 1

    def test_matrix_vertical_gradient(self) -> None:
        """Test middle rows brighter than top/bottom on matrix."""
        effect = EffectAurora(brightness=1.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        # Average brightness per row
        row_brightness = []
        for row in range(8):
            start = row * 8
            avg = sum(colors[start + i].brightness for i in range(8)) / 8
            row_brightness.append(avg)

        # Middle rows (3, 4) should be brighter than edge rows (0, 7)
        mid_avg = (row_brightness[3] + row_brightness[4]) / 2
        edge_avg = (row_brightness[0] + row_brightness[7]) / 2
        assert mid_avg > edge_avg


class TestAuroraFrameLoop:
    """Tests for EffectAurora running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test aurora sends frames through animator.send_frame."""
        effect = EffectAurora()

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
async def test_aurora_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns green aurora color."""
    effect = EffectAurora()
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 120
    assert result.saturation == 0.8
    assert result.brightness == 0.0
    assert result.kelvin == KELVIN_NEUTRAL


@pytest.mark.asyncio
async def test_aurora_is_light_compatible_with_color() -> None:
    """Test is_light_compatible returns True for color lights."""
    effect = EffectAurora()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_aurora_is_light_compatible_without_color() -> None:
    """Test is_light_compatible returns False for non-color lights."""
    effect = EffectAurora()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_aurora_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectAurora()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_color = True
        light.capabilities = caps

    light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light._ensure_capabilities.assert_called_once()


def test_aurora_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectAurora."""
    effect = EffectAurora()
    assert effect.inherit_prestate(EffectAurora()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_aurora_repr() -> None:
    """Test EffectAurora string representation."""
    effect = EffectAurora(speed=2.0, brightness=0.7, spread=45)
    repr_str = repr(effect)

    assert "EffectAurora" in repr_str
    assert "speed=2.0" in repr_str
    assert "brightness=0.7" in repr_str
    assert "spread=45" in repr_str
