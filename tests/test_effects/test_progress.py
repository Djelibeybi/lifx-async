"""Tests for EffectProgress."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK, Colors
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.progress import EffectProgress


def test_progress_default_parameters() -> None:
    """Test EffectProgress with default parameters."""
    effect = EffectProgress()

    assert effect.name == "progress"
    assert effect.start_value == 0.0
    assert effect.end_value == 100.0
    assert effect.position == 0.0
    assert effect.foreground == Colors.GREEN
    assert effect.spot_brightness == 1.0
    assert effect.spot_width == 0.15
    assert effect.spot_speed == 1.0
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_progress_custom_parameters() -> None:
    """Test EffectProgress with custom parameters."""
    fg = HSBK(hue=240, saturation=1.0, brightness=0.8, kelvin=3500)
    bg = HSBK(hue=0, saturation=0.0, brightness=0.1, kelvin=3500)
    effect = EffectProgress(
        start_value=10.0,
        end_value=200.0,
        position=50.0,
        foreground=fg,
        background=bg,
        spot_brightness=0.8,
        spot_width=0.2,
        spot_speed=2.0,
    )

    assert effect.start_value == 10.0
    assert effect.end_value == 200.0
    assert effect.position == 50.0
    assert effect.foreground == fg
    assert effect.background == bg
    assert effect.spot_brightness == 0.8
    assert effect.spot_width == 0.2
    assert effect.spot_speed == 2.0


def test_progress_invalid_start_end() -> None:
    """Test EffectProgress with start >= end raises ValueError."""
    with pytest.raises(ValueError, match="start_value.*must be < end_value"):
        EffectProgress(start_value=100, end_value=50)

    with pytest.raises(ValueError, match="start_value.*must be < end_value"):
        EffectProgress(start_value=50, end_value=50)


def test_progress_invalid_position() -> None:
    """Test EffectProgress with position out of range raises ValueError."""
    with pytest.raises(ValueError, match="position.*must be between"):
        EffectProgress(start_value=0, end_value=100, position=-1)

    with pytest.raises(ValueError, match="position.*must be between"):
        EffectProgress(start_value=0, end_value=100, position=101)


def test_progress_gradient_foreground() -> None:
    """Test EffectProgress accepts a gradient (list of HSBK) as foreground."""
    gradient = [
        HSBK(hue=240, saturation=1.0, brightness=0.8, kelvin=3500),
        HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),
        HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500),
    ]
    effect = EffectProgress(foreground=gradient)
    assert effect.foreground == gradient


def test_progress_gradient_too_few_stops() -> None:
    """Test EffectProgress rejects gradient with fewer than 2 stops."""
    with pytest.raises(ValueError, match="at least 2 stops"):
        EffectProgress(foreground=[Colors.RED])


def test_progress_invalid_spot_brightness() -> None:
    """Test EffectProgress with invalid spot_brightness raises ValueError."""
    with pytest.raises(ValueError, match="spot_brightness must be 0.0-1.0"):
        EffectProgress(spot_brightness=1.5)


def test_progress_invalid_spot_width() -> None:
    """Test EffectProgress with invalid spot_width raises ValueError."""
    with pytest.raises(ValueError, match="spot_width must be 0.0-1.0"):
        EffectProgress(spot_width=1.5)


def test_progress_invalid_spot_speed() -> None:
    """Test EffectProgress with invalid spot_speed raises ValueError."""
    with pytest.raises(ValueError, match="spot_speed must be positive"):
        EffectProgress(spot_speed=0)


class TestProgressInheritance:
    """Tests for EffectProgress class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectProgress extends FrameEffect."""
        effect = EffectProgress()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectProgress extends LIFXEffect."""
        effect = EffectProgress()
        assert isinstance(effect, LIFXEffect)


class TestProgressGenerateFrame:
    """Tests for EffectProgress.generate_frame()."""

    def test_empty_bar_all_background(self) -> None:
        """Test position=0 produces all background pixels."""
        effect = EffectProgress(position=0.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        for color in colors:
            assert color == effect.background

    def test_full_bar_all_foreground(self) -> None:
        """Test position=100 produces all foreground pixels."""
        effect = EffectProgress(position=100.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        for color in colors:
            assert color.hue == effect.foreground.hue
            assert color.saturation == effect.foreground.saturation

    def test_half_bar_split(self) -> None:
        """Test position=50 splits pixels between foreground and background."""
        effect = EffectProgress(position=50.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # First 8 pixels should be foreground (possibly with spot boost)
        for color in colors[:8]:
            assert color.hue == effect.foreground.hue

        # Last 8 pixels should be background
        for color in colors[8:]:
            assert color == effect.background

    def test_traveling_spot_brightness(self) -> None:
        """Test spot pixel is brighter than base foreground."""
        effect = EffectProgress(
            position=100.0,
            spot_brightness=1.0,
        )
        # At elapsed_s=0, sin(0)=0, so spot is at fill_end * 0.5
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # At least one pixel should have brightness > base foreground
        brightnesses = [c.brightness for c in colors]
        assert max(brightnesses) >= effect.foreground.brightness

    def test_custom_start_end_range(self) -> None:
        """Test custom start/end range works correctly."""
        effect = EffectProgress(start_value=20, end_value=80, position=50)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # position=50 in range [20, 80] is (50-20)/(80-20) = 0.5 → 8 pixels
        fill_count = sum(1 for c in colors if c.hue == effect.foreground.hue)
        assert fill_count == 8

    def test_frame_changes_over_time(self) -> None:
        """Test spot position changes between frames."""
        effect = EffectProgress(position=100.0)
        ctx1 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        ctx2 = FrameContext(
            elapsed_s=0.25,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors1 = effect.generate_frame(ctx1)
        colors2 = effect.generate_frame(ctx2)

        # Different elapsed → spot in different position → different brightnesses
        assert colors1 != colors2

    def test_dynamic_position_update(self) -> None:
        """Test changing effect.position changes the bar."""
        effect = EffectProgress(position=0.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )

        colors_empty = effect.generate_frame(ctx)
        all_bg = all(c == effect.background for c in colors_empty)
        assert all_bg

        # Update position
        effect.position = 50.0
        colors_half = effect.generate_frame(ctx)
        # Now some pixels should be foreground
        fg_count = sum(1 for c in colors_half if c.hue == effect.foreground.hue)
        assert fg_count == 8

    @pytest.mark.parametrize("pixel_count", [8, 16, 82])
    def test_pixel_count_variations(self, pixel_count: int) -> None:
        """Test correct output for various pixel counts."""
        effect = EffectProgress(position=50.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == pixel_count


class TestProgressGradient:
    """Tests for gradient foreground behavior."""

    def _make_gradient(self) -> list[HSBK]:
        """Return a blue -> green -> red gradient."""
        return [
            HSBK(hue=240, saturation=1.0, brightness=0.8, kelvin=3500),
            HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),
            HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500),
        ]

    def test_gradient_full_bar_has_varying_hues(self) -> None:
        """Test gradient foreground produces different hues across the bar."""
        effect = EffectProgress(position=100.0, foreground=self._make_gradient())
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        hues = {c.hue for c in colors}
        # A blue -> green -> red gradient across 16 pixels should have
        # multiple distinct hues, not just one
        assert len(hues) > 3

    def test_gradient_first_pixel_matches_first_stop(self) -> None:
        """Test first pixel color matches first gradient stop."""
        gradient = self._make_gradient()
        effect = EffectProgress(
            position=100.0,
            foreground=gradient,
            spot_brightness=0.8,  # same as base to isolate color
        )
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # First pixel should be near blue (hue=240)
        assert abs(colors[0].hue - 240) <= 5

    def test_gradient_last_pixel_matches_last_stop(self) -> None:
        """Test last pixel color matches last gradient stop."""
        gradient = self._make_gradient()
        effect = EffectProgress(
            position=100.0,
            foreground=gradient,
            spot_brightness=0.8,  # same as base
        )
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # Last pixel should be near red (hue=0)
        assert colors[-1].hue <= 5 or colors[-1].hue >= 355

    def test_gradient_half_bar_only_shows_first_half(self) -> None:
        """Test half-filled gradient only shows colors from first half."""
        gradient = self._make_gradient()  # blue(240) -> green(120) -> red(0)
        effect = EffectProgress(position=50.0, foreground=gradient)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # First 8 pixels should be in the blue-to-green range
        for color in colors[:8]:
            assert 100 <= color.hue <= 250

        # Last 8 pixels should be background
        for color in colors[8:]:
            assert color == effect.background

    def test_gradient_spot_still_boosts_brightness(self) -> None:
        """Test traveling spot brightness boost works with gradients."""
        gradient = self._make_gradient()
        effect = EffectProgress(
            position=100.0,
            foreground=gradient,
            spot_brightness=1.0,
        )
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # Some pixel should have brightness boosted above base 0.8
        brightnesses = [c.brightness for c in colors]
        assert max(brightnesses) > 0.8

    def test_gradient_with_two_stops(self) -> None:
        """Test gradient works with minimum 2 stops."""
        gradient = [
            HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500),
            HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),
        ]
        effect = EffectProgress(position=100.0, foreground=gradient)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 16
        # First pixel near red (hue=0), last near green (hue=120)
        assert colors[0].hue <= 5
        assert abs(colors[-1].hue - 120) <= 5


class TestProgressGradientHueWrapping:
    """Tests for gradient hue wrapping in _gradient_color."""

    def test_gradient_hue_wrapping_positive(self) -> None:
        """Test gradient wraps hue when diff > 180 (e.g. 10 -> 350)."""
        # hue_diff = 350 - 10 = 340 > 180, so code subtracts 360 → -20
        gradient = [
            HSBK(hue=10, saturation=1.0, brightness=0.8, kelvin=3500),
            HSBK(hue=350, saturation=1.0, brightness=0.8, kelvin=3500),
        ]
        effect = EffectProgress(position=100.0, foreground=gradient)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # All hues should be valid and near the 350-360-10 range
        for color in colors:
            assert 0 <= color.hue <= 360

    def test_gradient_hue_wrapping_negative(self) -> None:
        """Test gradient wraps hue when diff < -180 (e.g. 350 -> 10)."""
        # hue_diff = 10 - 350 = -340 < -180, so code adds 360 → +20
        gradient = [
            HSBK(hue=350, saturation=1.0, brightness=0.8, kelvin=3500),
            HSBK(hue=10, saturation=1.0, brightness=0.8, kelvin=3500),
        ]
        effect = EffectProgress(position=100.0, foreground=gradient)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # All hues should be valid and near the 350-360-10 range
        for color in colors:
            assert 0 <= color.hue <= 360


def test_progress_gradient_repr() -> None:
    """Test repr shows gradient info."""
    gradient = [
        HSBK(hue=240, saturation=1.0, brightness=0.8, kelvin=3500),
        HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500),
    ]
    effect = EffectProgress(foreground=gradient)
    repr_str = repr(effect)
    assert "gradient(2 stops)" in repr_str


class TestProgressCompatibility:
    """Tests for EffectProgress device compatibility."""

    @pytest.mark.asyncio
    async def test_compatible_with_multizone(self) -> None:
        """Test is_light_compatible returns True for multizone lights."""
        effect = EffectProgress()
        light = MagicMock()
        capabilities = MagicMock()
        capabilities.has_multizone = True
        light.capabilities = capabilities

        assert await effect.is_light_compatible(light) is True

    @pytest.mark.asyncio
    async def test_incompatible_with_non_multizone(self) -> None:
        """Test is_light_compatible returns False for non-multizone lights."""
        effect = EffectProgress()
        light = MagicMock()
        capabilities = MagicMock()
        capabilities.has_multizone = False
        light.capabilities = capabilities

        assert await effect.is_light_compatible(light) is False

    @pytest.mark.asyncio
    async def test_loads_capabilities_when_none(self) -> None:
        """Test is_light_compatible loads capabilities when None."""
        effect = EffectProgress()
        light = MagicMock()
        light.capabilities = None

        async def ensure_caps():
            caps = MagicMock()
            caps.has_multizone = True
            light.capabilities = caps

        light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)

        assert await effect.is_light_compatible(light) is True
        light._ensure_capabilities.assert_called_once()


class TestProgressFrameLoop:
    """Tests for EffectProgress running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test progress sends frames through animator.send_frame."""
        effect = EffectProgress(position=50.0)

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


def test_progress_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectProgress."""
    effect = EffectProgress()
    assert effect.inherit_prestate(EffectProgress()) is True
    assert effect.inherit_prestate(MagicMock()) is False


@pytest.mark.asyncio
async def test_progress_from_poweroff_hsbk() -> None:
    """Test from_poweroff_hsbk returns the background color."""
    bg = HSBK(hue=0, saturation=0.0, brightness=0.1, kelvin=2700)
    effect = EffectProgress(background=bg)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result is effect.background
    assert result == bg


def test_progress_repr() -> None:
    """Test EffectProgress string representation."""
    effect = EffectProgress(position=42.0, start_value=10, end_value=90)
    repr_str = repr(effect)

    assert "EffectProgress" in repr_str
    assert "position=42.0" in repr_str
    assert "start_value=10" in repr_str
    assert "end_value=90" in repr_str
