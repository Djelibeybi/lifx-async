"""Tests for EffectColorloop."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.const import KELVIN_NEUTRAL
from lifx.effects.base import LIFXEffect
from lifx.effects.colorloop import EffectColorloop
from lifx.effects.frame_effect import FrameContext, FrameEffect


def test_colorloop_default_parameters() -> None:
    """Test EffectColorloop with default parameters."""
    effect = EffectColorloop()

    assert effect.name == "colorloop"
    assert effect.period == 60
    assert effect.change == 20
    assert effect.spread == 30
    assert effect.brightness is None
    assert effect.saturation_min == 0.8
    assert effect.saturation_max == 1.0
    assert effect.transition is None
    assert effect.synchronized is False
    assert effect.power_on is True


def test_colorloop_custom_parameters() -> None:
    """Test EffectColorloop with custom parameters."""
    effect = EffectColorloop(
        period=30, change=15, spread=45, brightness=0.7, saturation_min=0.9
    )

    assert effect.period == 30
    assert effect.change == 15
    assert effect.spread == 45
    assert effect.brightness == 0.7
    assert effect.saturation_min == 0.9


def test_colorloop_with_transition() -> None:
    """Test EffectColorloop with custom transition time."""
    effect = EffectColorloop(transition=2.5)

    assert effect.transition == 2.5


def test_colorloop_invalid_period() -> None:
    """Test EffectColorloop with invalid period raises ValueError."""
    with pytest.raises(ValueError, match="Period must be positive"):
        EffectColorloop(period=0)


def test_colorloop_invalid_change() -> None:
    """Test EffectColorloop with invalid change raises ValueError."""
    with pytest.raises(ValueError, match="Change must be 0-360"):
        EffectColorloop(change=400)


def test_colorloop_invalid_spread() -> None:
    """Test EffectColorloop with invalid spread raises ValueError."""
    with pytest.raises(ValueError, match="Spread must be 0-360"):
        EffectColorloop(spread=400)


def test_colorloop_invalid_brightness() -> None:
    """Test EffectColorloop with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be 0.0-1.0"):
        EffectColorloop(brightness=1.5)


def test_colorloop_invalid_saturation_min() -> None:
    """Test EffectColorloop with invalid saturation_min raises ValueError."""
    with pytest.raises(ValueError, match="Saturation_min must be 0.0-1.0"):
        EffectColorloop(saturation_min=1.5)


def test_colorloop_invalid_saturation_max() -> None:
    """Test EffectColorloop with invalid saturation_max raises ValueError."""
    with pytest.raises(ValueError, match="Saturation_max must be 0.0-1.0"):
        EffectColorloop(saturation_max=1.5)


def test_colorloop_saturation_min_greater_than_max() -> None:
    """Test EffectColorloop with saturation_min > saturation_max raises ValueError."""
    with pytest.raises(ValueError, match="Saturation_min .* must be <="):
        EffectColorloop(saturation_min=0.9, saturation_max=0.5)


def test_colorloop_invalid_transition() -> None:
    """Test EffectColorloop with invalid transition raises ValueError."""
    with pytest.raises(ValueError, match="Transition must be non-negative"):
        EffectColorloop(transition=-1.0)


def test_colorloop_synchronized_mode() -> None:
    """Test EffectColorloop with synchronized=True."""
    effect = EffectColorloop(synchronized=True)

    assert effect.synchronized is True
    assert effect.period == 60
    assert effect.change == 20


def test_colorloop_synchronized_with_custom_params() -> None:
    """Test EffectColorloop with synchronized mode and custom parameters."""
    effect = EffectColorloop(
        period=30, change=15, brightness=0.8, synchronized=True, transition=2.0
    )

    assert effect.synchronized is True
    assert effect.period == 30
    assert effect.change == 15
    assert effect.brightness == 0.8
    assert effect.transition == 2.0


def test_colorloop_inherit_prestate() -> None:
    """Test EffectColorloop inherit_prestate method."""
    effect1 = EffectColorloop()
    effect2 = EffectColorloop()
    other_effect = object()

    # Should inherit from another EffectColorloop
    assert effect1.inherit_prestate(effect2) is True

    # Should not inherit from other effect types
    assert effect1.inherit_prestate(other_effect) is False  # type: ignore


def test_colorloop_repr() -> None:
    """Test EffectColorloop string representation."""
    effect = EffectColorloop(period=30, change=15, spread=45, brightness=0.7)
    repr_str = repr(effect)

    assert "EffectColorloop" in repr_str
    assert "period=30" in repr_str
    assert "change=15" in repr_str
    assert "spread=45" in repr_str
    assert "brightness=0.7" in repr_str
    assert "synchronized=False" in repr_str


def test_colorloop_repr_synchronized() -> None:
    """Test EffectColorloop string representation with synchronized mode."""
    effect = EffectColorloop(synchronized=True)
    repr_str = repr(effect)

    assert "EffectColorloop" in repr_str
    assert "synchronized=True" in repr_str


class TestColorloopInheritance:
    """Tests for EffectColorloop class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectColorloop extends FrameEffect."""
        effect = EffectColorloop()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectColorloop still extends LIFXEffect."""
        effect = EffectColorloop()
        assert isinstance(effect, LIFXEffect)

    def test_has_fps(self) -> None:
        """Test EffectColorloop has fps property from FrameEffect."""
        effect = EffectColorloop(period=60, change=20)
        assert effect.fps >= 1.0

    def test_has_duration_none(self) -> None:
        """Test EffectColorloop has duration=None (infinite)."""
        effect = EffectColorloop()
        assert effect.duration is None


class TestColorloopFpsCalculation:
    """Tests for FPS calculation from period/change."""

    def test_default_fps_clamped(self) -> None:
        """Test default params produce FPS >= 20.0 (minimum for smooth multizone)."""
        # period=60, change=20 -> (360/20)/60 = 0.3 -> clamped to 20.0
        effect = EffectColorloop(period=60, change=20)
        assert effect.fps == 20.0

    def test_fast_fps(self) -> None:
        """Test fast params produce higher FPS when exceeding minimum."""
        # period=1, change=20 -> (360/20)/1 = 18.0 -> clamped to 20.0
        effect = EffectColorloop(period=1, change=20)
        assert effect.fps == 20.0

        # Very fast: period=0.5, change=5 -> (360/5)/0.5 = 144.0 -> above minimum
        effect = EffectColorloop(period=0.5, change=5)
        assert effect.fps == 144.0

    def test_change_zero_fps(self) -> None:
        """Test change=0 produces 20.0 FPS (minimum)."""
        effect = EffectColorloop(change=0)
        assert effect.fps == 20.0


class TestColorloopGenerateFrame:
    """Tests for EffectColorloop.generate_frame()."""

    def test_synchronized_consistent_hue(self) -> None:
        """Test synchronized mode produces same hue across device indices."""
        effect = EffectColorloop(period=60, change=20, synchronized=True)
        effect._initial_colors = [
            HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),
            HSBK(hue=180, saturation=1.0, brightness=0.8, kelvin=3500),
        ]
        effect._direction = 1

        ctx0 = FrameContext(
            elapsed_s=10.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        ctx1 = FrameContext(
            elapsed_s=10.0,
            device_index=1,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )

        colors0 = effect.generate_frame(ctx0)
        colors1 = effect.generate_frame(ctx1)

        # Synchronized mode: both devices should get same hue
        assert colors0[0].hue == colors1[0].hue

    def test_spread_offset_by_device_index(self) -> None:
        """Test spread mode offsets hue by device_index * spread."""
        effect = EffectColorloop(period=60, change=20, spread=30, synchronized=False)
        effect._initial_colors = [
            HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500),
            HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500),
        ]
        effect._direction = 1

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

        # Device 1 should be offset by spread (30 degrees)
        assert colors0[0].hue == 0
        assert colors1[0].hue == 30

    def test_fills_all_pixels(self) -> None:
        """Test generate_frame returns pixel_count colors."""
        effect = EffectColorloop(period=60, change=20, synchronized=True)
        effect._initial_colors = [
            HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),
        ]
        effect._direction = 1

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=82,
            canvas_width=82,
            canvas_height=1,
        )

        colors = effect.generate_frame(ctx)
        assert len(colors) == 82
        # All pixels should have the same color
        assert all(c.hue == colors[0].hue for c in colors)

    def test_fallback_when_no_initial_colors(self) -> None:
        """Test generate_frame returns fallback when _initial_colors is empty."""
        effect = EffectColorloop()
        # Don't set _initial_colors

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )

        colors = effect.generate_frame(ctx)
        assert len(colors) == 1
        assert colors[0].brightness == 0.8

    def test_synchronized_with_fixed_brightness(self) -> None:
        """Test synchronized mode uses fixed brightness when specified."""
        effect = EffectColorloop(
            period=60, change=20, synchronized=True, brightness=0.5
        )
        effect._initial_colors = [
            HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),
        ]
        effect._direction = 1

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )

        colors = effect.generate_frame(ctx)
        assert colors[0].brightness == 0.5

    def test_spread_with_fixed_brightness(self) -> None:
        """Test spread mode uses fixed brightness when specified."""
        effect = EffectColorloop(
            period=60, change=20, brightness=0.7, synchronized=False
        )
        effect._initial_colors = [
            HSBK(hue=120, saturation=1.0, brightness=0.3, kelvin=3500),
        ]
        effect._direction = 1

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )

        colors = effect.generate_frame(ctx)
        assert colors[0].brightness == 0.7

    def test_spread_with_none_brightness(self) -> None:
        """Test spread mode preserves initial brightness when brightness=None."""
        effect = EffectColorloop(
            period=60, change=20, brightness=None, synchronized=False
        )
        effect._initial_colors = [
            HSBK(hue=120, saturation=1.0, brightness=0.6, kelvin=3500),
        ]
        effect._direction = 1

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )

        colors = effect.generate_frame(ctx)
        assert colors[0].brightness == 0.6

    def test_multi_pixel_all_same_color(self) -> None:
        """Test multi-pixel devices get same color for all pixels."""
        effect = EffectColorloop(period=60, change=20, synchronized=False)
        effect._initial_colors = [
            HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500),
        ]
        effect._direction = 1

        ctx = FrameContext(
            elapsed_s=15.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )

        colors = effect.generate_frame(ctx)
        assert len(colors) == 16
        # All pixels should have the same color (colorloop is single-color)
        assert all(c == colors[0] for c in colors)

    def test_hue_rotates_with_time(self) -> None:
        """Test hue changes as elapsed_s increases."""
        effect = EffectColorloop(period=60, change=20, synchronized=True)
        effect._initial_colors = [
            HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500),
        ]
        effect._direction = 1

        ctx_t0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        ctx_t30 = FrameContext(
            elapsed_s=30.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )

        colors_t0 = effect.generate_frame(ctx_t0)
        colors_t30 = effect.generate_frame(ctx_t30)

        # After 30s (half period), hue should have rotated 180 degrees
        assert colors_t0[0].hue == 0
        assert colors_t30[0].hue == 180


class TestColorloopAsyncSetup:
    """Tests for EffectColorloop.async_setup()."""

    @pytest.mark.asyncio
    async def test_fetches_initial_colors(self) -> None:
        """Test async_setup fetches initial colors from participants."""
        effect = EffectColorloop(period=0.2, change=30)

        light = MagicMock()
        light.serial = "d073d5test789"
        light.get_color = AsyncMock(
            return_value=(
                HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),
                100,
                200,
            )
        )

        effect.participants = [light]
        await effect.async_setup([light])

        assert len(effect._initial_colors) == 1
        assert effect._initial_colors[0].hue == 120

    @pytest.mark.asyncio
    async def test_picks_direction(self) -> None:
        """Test async_setup picks a random direction."""
        effect = EffectColorloop(period=0.2, change=30)

        light = MagicMock()
        light.serial = "d073d5test789"
        light.get_color = AsyncMock(
            return_value=(
                HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),
                100,
                200,
            )
        )

        effect.participants = [light]
        await effect.async_setup([light])

        assert effect._direction in (1, -1)


class TestColorloopFrameLoop:
    """Tests for EffectColorloop running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_stop_method(self) -> None:
        """Test colorloop stop() method via FrameEffect."""
        effect = EffectColorloop(period=0.2, change=30)

        # Set up initial colors and animators
        effect._initial_colors = [
            HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
        ]
        effect._direction = 1

        animator = MagicMock()
        animator.pixel_count = 1
        animator.canvas_width = 1
        animator.canvas_height = 1
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        # Run in background
        play_task = asyncio.create_task(effect.async_play())
        await asyncio.sleep(0.05)

        effect.stop()
        await asyncio.wait_for(play_task, timeout=1.0)

        assert effect._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test colorloop sends frames through animator.send_frame."""
        effect = EffectColorloop(period=0.2, change=30)

        effect._initial_colors = [
            HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
        ]
        effect._direction = 1

        animator = MagicMock()
        animator.pixel_count = 1
        animator.canvas_width = 1
        animator.canvas_height = 1
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        play_task = asyncio.create_task(effect.async_play())
        await asyncio.sleep(0.1)
        effect.stop()
        await asyncio.wait_for(play_task, timeout=1.0)

        # Should have sent frames via animator
        assert animator.send_frame.call_count > 0


@pytest.mark.asyncio
async def test_colorloop_from_poweroff_with_custom_brightness() -> None:
    """Test from_poweroff_hsbk with custom brightness specified."""
    effect = EffectColorloop(brightness=0.6)

    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    # Should return random hue with custom brightness
    assert 0 <= result.hue <= 360
    assert result.brightness == 0.6
    assert result.kelvin == KELVIN_NEUTRAL


@pytest.mark.asyncio
async def test_colorloop_is_light_compatible_with_none_capabilities() -> None:
    """Test is_light_compatible when light.capabilities is None."""
    effect = EffectColorloop()

    light = MagicMock()
    light.capabilities = None
    light._ensure_capabilities = AsyncMock()

    async def set_capabilities():
        light.capabilities = MagicMock()
        light.capabilities.has_color = True

    light._ensure_capabilities.side_effect = set_capabilities

    result = await effect.is_light_compatible(light)

    light._ensure_capabilities.assert_called_once()
    assert result is True


@pytest.mark.asyncio
async def test_colorloop_is_light_compatible_capabilities_still_none() -> None:
    """Test is_light_compatible when capabilities remain None after loading."""
    effect = EffectColorloop()

    light = MagicMock()
    light.capabilities = None
    light._ensure_capabilities = AsyncMock()

    result = await effect.is_light_compatible(light)

    assert result is False


@pytest.mark.asyncio
async def test_colorloop_is_light_compatible_capabilities_already_loaded() -> None:
    """Test is_light_compatible when capabilities are already loaded."""
    effect = EffectColorloop()

    light = MagicMock()
    light.capabilities = MagicMock()
    light.capabilities.has_color = True
    light._ensure_capabilities = AsyncMock()

    result = await effect.is_light_compatible(light)

    light._ensure_capabilities.assert_not_called()
    assert result is True


@pytest.mark.asyncio
async def test_colorloop_is_light_compatible_no_color_support() -> None:
    """Test is_light_compatible when light doesn't support color."""
    effect = EffectColorloop()

    light = MagicMock()
    light.capabilities = MagicMock()
    light.capabilities.has_color = False

    result = await effect.is_light_compatible(light)

    assert result is False
