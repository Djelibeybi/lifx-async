"""Tests for FrameEffect and FrameContext."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from lifx.color import HSBK
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect


class ConcreteFrameEffect(FrameEffect):
    """Concrete implementation for testing."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.generate_frame_calls: list[FrameContext] = []
        self.frame_color = HSBK(hue=180, saturation=1.0, brightness=0.8, kelvin=3500)

    @property
    def name(self) -> str:
        return "test_frame_effect"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        self.generate_frame_calls.append(ctx)
        return [self.frame_color] * ctx.pixel_count


class TestFrameContext:
    """Tests for FrameContext dataclass."""

    def test_fields(self) -> None:
        """Test FrameContext has expected fields."""
        ctx = FrameContext(
            elapsed_s=1.5,
            device_index=2,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        assert ctx.elapsed_s == 1.5
        assert ctx.device_index == 2
        assert ctx.pixel_count == 64
        assert ctx.canvas_width == 8
        assert ctx.canvas_height == 8

    def test_frozen(self) -> None:
        """Test FrameContext is immutable."""
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        with pytest.raises(AttributeError):
            ctx.elapsed_s = 2.0  # type: ignore[misc]


class TestFrameEffectValidation:
    """Tests for FrameEffect parameter validation."""

    def test_invalid_fps_zero(self) -> None:
        """Test fps=0 raises ValueError."""
        with pytest.raises(ValueError, match="fps must be positive"):
            ConcreteFrameEffect(fps=0)

    def test_invalid_fps_negative(self) -> None:
        """Test negative fps raises ValueError."""
        with pytest.raises(ValueError, match="fps must be positive"):
            ConcreteFrameEffect(fps=-1.0)

    def test_invalid_duration_zero(self) -> None:
        """Test duration=0 raises ValueError."""
        with pytest.raises(ValueError, match="duration must be positive"):
            ConcreteFrameEffect(duration=0)

    def test_invalid_duration_negative(self) -> None:
        """Test negative duration raises ValueError."""
        with pytest.raises(ValueError, match="duration must be positive"):
            ConcreteFrameEffect(duration=-1.0)

    def test_valid_parameters(self) -> None:
        """Test valid parameters create effect."""
        effect = ConcreteFrameEffect(fps=10.0, duration=5.0, power_on=False)
        assert effect.fps == 10.0
        assert effect.duration == 5.0
        assert effect.power_on is False

    def test_none_duration_infinite(self) -> None:
        """Test duration=None creates infinite effect."""
        effect = ConcreteFrameEffect(duration=None)
        assert effect.duration is None


class TestFrameEffectInheritance:
    """Tests for FrameEffect class hierarchy."""

    def test_is_lifx_effect(self) -> None:
        """Test FrameEffect extends LIFXEffect."""
        effect = ConcreteFrameEffect()
        assert isinstance(effect, LIFXEffect)
        assert isinstance(effect, FrameEffect)

    def test_has_name_property(self) -> None:
        """Test FrameEffect subclass has name property."""
        effect = ConcreteFrameEffect()
        assert effect.name == "test_frame_effect"


class TestFrameEffectLoop:
    """Tests for FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_stops_on_duration(self) -> None:
        """Test frame loop stops when duration expires."""
        effect = ConcreteFrameEffect(fps=30.0, duration=0.1)

        # Create mock animator
        animator = MagicMock()
        animator.pixel_count = 1
        animator.canvas_width = 1
        animator.canvas_height = 1
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        # Run async_play - should stop after ~0.1s
        await asyncio.wait_for(effect.async_play(), timeout=2.0)

        # Should have called send_frame multiple times
        assert animator.send_frame.call_count > 0

    @pytest.mark.asyncio
    async def test_stops_on_stop_event(self) -> None:
        """Test frame loop stops when stop() is called."""
        effect = ConcreteFrameEffect(fps=30.0, duration=None)

        animator = MagicMock()
        animator.pixel_count = 1
        animator.canvas_width = 1
        animator.canvas_height = 1
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        # Start in background
        task = asyncio.create_task(effect.async_play())

        await asyncio.sleep(0.05)
        effect.stop()

        await asyncio.wait_for(task, timeout=2.0)

        assert animator.send_frame.call_count > 0

    @pytest.mark.asyncio
    async def test_calls_generate_frame_with_correct_context(self) -> None:
        """Test generate_frame receives correct FrameContext per device."""
        effect = ConcreteFrameEffect(fps=30.0, duration=0.1)

        # Create two animators
        animator1 = MagicMock()
        animator1.pixel_count = 1
        animator1.canvas_width = 1
        animator1.canvas_height = 1
        animator1.send_frame = MagicMock()

        animator2 = MagicMock()
        animator2.pixel_count = 82
        animator2.canvas_width = 82
        animator2.canvas_height = 1
        animator2.send_frame = MagicMock()

        effect._animators = [animator1, animator2]

        await asyncio.wait_for(effect.async_play(), timeout=2.0)

        # Check that both devices got frames
        assert any(ctx.device_index == 0 for ctx in effect.generate_frame_calls)
        assert any(ctx.device_index == 1 for ctx in effect.generate_frame_calls)

        # Check device 0 (single light) context
        device0_ctxs = [c for c in effect.generate_frame_calls if c.device_index == 0]
        assert device0_ctxs[0].pixel_count == 1
        assert device0_ctxs[0].canvas_width == 1
        assert device0_ctxs[0].canvas_height == 1

        # Check device 1 (multizone) context
        device1_ctxs = [c for c in effect.generate_frame_calls if c.device_index == 1]
        assert device1_ctxs[0].pixel_count == 82
        assert device1_ctxs[0].canvas_width == 82
        assert device1_ctxs[0].canvas_height == 1

    @pytest.mark.asyncio
    async def test_converts_hsbk_to_protocol(self) -> None:
        """Test frame loop converts HSBK.as_tuple() before sending."""
        effect = ConcreteFrameEffect(fps=30.0, duration=0.05)
        effect.frame_color = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=4000)

        animator = MagicMock()
        animator.pixel_count = 1
        animator.canvas_width = 1
        animator.canvas_height = 1
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        await asyncio.wait_for(effect.async_play(), timeout=2.0)

        # Check that send_frame was called with protocol tuples
        call_args = animator.send_frame.call_args_list[0]
        protocol_frame = call_args[0][0]
        assert isinstance(protocol_frame, list)
        assert isinstance(protocol_frame[0], tuple)
        assert len(protocol_frame[0]) == 4
        # Protocol values should be uint16 (not user-friendly floats)
        h, s, b, k = protocol_frame[0]
        assert isinstance(h, int)
        assert isinstance(s, int)
        assert isinstance(b, int)
        assert isinstance(k, int)


class TestFrameEffectAsyncSetup:
    """Tests for FrameEffect async_setup hook."""

    @pytest.mark.asyncio
    async def test_async_setup_called(self) -> None:
        """Test async_setup is a no-op by default."""
        effect = ConcreteFrameEffect()
        # Should not raise
        await effect.async_setup([])


class TestFrameEffectCloseAnimators:
    """Tests for FrameEffect close_animators method."""

    def test_close_animators(self) -> None:
        """Test close_animators closes all and clears list."""
        effect = ConcreteFrameEffect()

        animator1 = MagicMock()
        animator2 = MagicMock()
        effect._animators = [animator1, animator2]

        effect.close_animators()

        animator1.close.assert_called_once()
        animator2.close.assert_called_once()
        assert len(effect._animators) == 0

    def test_close_animators_empty(self) -> None:
        """Test close_animators with no animators is a no-op."""
        effect = ConcreteFrameEffect()
        effect._animators = []

        # Should not raise
        effect.close_animators()

        assert len(effect._animators) == 0
