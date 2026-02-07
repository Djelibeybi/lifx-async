"""Tests for EffectRainbow."""

import asyncio
from unittest.mock import MagicMock

import pytest

from lifx.const import KELVIN_NEUTRAL
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.rainbow import EffectRainbow


def test_rainbow_default_parameters():
    """Test EffectRainbow with default parameters."""
    effect = EffectRainbow()

    assert effect.name == "rainbow"
    assert effect.period == 10.0
    assert effect.brightness == 0.8
    assert effect.saturation == 1.0
    assert effect.spread == 0.0
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_rainbow_custom_parameters():
    """Test EffectRainbow with custom parameters."""
    effect = EffectRainbow(period=5, brightness=0.6, saturation=0.9, spread=45)

    assert effect.period == 5
    assert effect.brightness == 0.6
    assert effect.saturation == 0.9
    assert effect.spread == 45


def test_rainbow_invalid_period():
    """Test EffectRainbow with invalid period raises ValueError."""
    with pytest.raises(ValueError, match="Period must be positive"):
        EffectRainbow(period=0)


def test_rainbow_invalid_brightness():
    """Test EffectRainbow with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be 0.0-1.0"):
        EffectRainbow(brightness=1.5)


def test_rainbow_invalid_saturation():
    """Test EffectRainbow with invalid saturation raises ValueError."""
    with pytest.raises(ValueError, match="Saturation must be 0.0-1.0"):
        EffectRainbow(saturation=-0.1)


def test_rainbow_invalid_spread():
    """Test EffectRainbow with invalid spread raises ValueError."""
    with pytest.raises(ValueError, match="Spread must be 0-360"):
        EffectRainbow(spread=400)


class TestRainbowInheritance:
    """Tests for EffectRainbow class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectRainbow extends FrameEffect."""
        effect = EffectRainbow()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectRainbow still extends LIFXEffect."""
        effect = EffectRainbow()
        assert isinstance(effect, LIFXEffect)


class TestRainbowGenerateFrame:
    """Tests for EffectRainbow.generate_frame()."""

    def test_single_pixel_cycles_hue(self) -> None:
        """Test single-pixel device cycles through hues."""
        effect = EffectRainbow(period=10)

        ctx = FrameContext(
            elapsed_s=2.5,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )

        colors = effect.generate_frame(ctx)
        assert len(colors) == 1
        # At 2.5s / 10s period = 0.25 * 360 = 90 degrees
        assert colors[0].hue == 90

    def test_multi_pixel_spreads_rainbow(self) -> None:
        """Test multi-pixel device gets a rainbow spread across pixels."""
        effect = EffectRainbow(period=10)

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )

        colors = effect.generate_frame(ctx)
        assert len(colors) == 16

        hues = [c.hue for c in colors]
        # First pixel starts at 0 (no time elapsed, no offset)
        assert hues[0] == 0
        # Midpoint pixel near 180 degrees
        assert 170 <= hues[8] <= 190
        # All hues should be unique
        assert len(set(hues)) == 16

    def test_rainbow_scrolls_with_time(self) -> None:
        """Test rainbow pattern scrolls as time passes."""
        effect = EffectRainbow(period=10)

        ctx_t0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        ctx_t5 = FrameContext(
            elapsed_s=5.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )

        colors_t0 = effect.generate_frame(ctx_t0)
        colors_t5 = effect.generate_frame(ctx_t5)

        # At t=0, first pixel is hue=0
        assert colors_t0[0].hue == 0
        # At t=5 (half period), first pixel shifted 180 degrees
        assert colors_t5[0].hue == 180

    def test_device_spread_offset(self) -> None:
        """Test spread parameter offsets rainbow between devices."""
        effect = EffectRainbow(period=10, spread=90)

        ctx0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        ctx1 = FrameContext(
            elapsed_s=0.0,
            device_index=1,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )

        colors0 = effect.generate_frame(ctx0)
        colors1 = effect.generate_frame(ctx1)

        assert colors0[0].hue == 0
        assert colors1[0].hue == 90

    def test_uses_configured_brightness(self) -> None:
        """Test all pixels use the configured brightness."""
        effect = EffectRainbow(brightness=0.6)

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )

        colors = effect.generate_frame(ctx)
        assert all(c.brightness == 0.6 for c in colors)

    def test_uses_configured_saturation(self) -> None:
        """Test all pixels use the configured saturation."""
        effect = EffectRainbow(saturation=0.7)

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )

        colors = effect.generate_frame(ctx)
        assert all(c.saturation == 0.7 for c in colors)

    def test_uses_neutral_kelvin(self) -> None:
        """Test all pixels use neutral kelvin."""
        effect = EffectRainbow()

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=4,
            canvas_width=4,
            canvas_height=1,
        )

        colors = effect.generate_frame(ctx)
        assert all(c.kelvin == KELVIN_NEUTRAL for c in colors)


class TestRainbowFrameLoop:
    """Tests for EffectRainbow running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test rainbow sends frames through animator.send_frame."""
        effect = EffectRainbow(period=1)

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
async def test_rainbow_from_poweroff():
    """Test from_poweroff_hsbk returns configured brightness."""
    effect = EffectRainbow(brightness=0.6, saturation=0.9)

    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 0
    assert result.brightness == 0.6
    assert result.saturation == 0.9
    assert result.kelvin == KELVIN_NEUTRAL


def test_rainbow_repr():
    """Test EffectRainbow string representation."""
    effect = EffectRainbow(period=5, brightness=0.7, spread=45)
    repr_str = repr(effect)

    assert "EffectRainbow" in repr_str
    assert "period=5" in repr_str
    assert "brightness=0.7" in repr_str
    assert "spread=45" in repr_str
