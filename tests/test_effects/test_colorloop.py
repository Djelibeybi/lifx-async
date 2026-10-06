"""Tests for EffectColorloop."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from lifx.animation.animator import AnimatorStats, AnimatorWriter
from lifx.color import HSBK
from lifx.const import KELVIN_NEUTRAL
from lifx.devices.base import Connectivity
from lifx.effects.base import LIFXEffect
from lifx.effects.colorloop import EffectColorloop
from lifx.effects.frame_effect import (
    FrameContext,
    FrameEffect,
    drop_participant,
    replace_writer,
)
from lifx.exceptions import LifxTimeoutError
from lifx.protocol.protocol_types import LightHsbk


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
    """Test EffectColorloop rejects a change that is 0, or 180 or more."""
    for change in (0, 180, 400):
        with pytest.raises(ValueError, match="more than 0 and less than 180"):
            EffectColorloop(change=change)


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


def _loop(**kwargs: Any) -> EffectColorloop:
    """A colour loop whose steps are 10 degrees and one second long."""
    effect = EffectColorloop(period=36, change=10, **kwargs)
    effect._initial_colors = [
        HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    ]
    effect._direction = 1
    return effect


def _ctx(elapsed: float) -> FrameContext:
    return FrameContext(
        elapsed_s=elapsed,
        device_index=0,
        pixel_count=1,
        canvas_width=1,
        canvas_height=1,
    )


def _light() -> MagicMock:
    light = MagicMock()
    light.serial = "d073d5000001"
    light.set_color = AsyncMock()
    return light


def _hue_at(elapsed: float) -> tuple[int, int, int, int]:
    """The protocol colour _loop() shows at a moment."""
    return HSBK(
        hue=round(120 + elapsed * 10) % 360, saturation=0.9, brightness=0.8, kelvin=3500
    ).as_tuple()


def _slot_writer(
    *,
    shared: bool = False,
    fade: float = 0.0,
    version: int = 0,
    gated: bool = False,
    tile: object = None,
) -> MagicMock:
    writer = MagicMock(spec=AnimatorWriter)
    writer.draws_slot = True
    writer.animator = tile if tile is not None else object()
    writer.tile_shared.return_value = shared
    writer.slot_deadline.return_value = None
    writer.hold_remaining = fade
    writer.hold_version = version
    writer.send_frame.return_value = AnimatorStats(
        packets_sent=1, total_time_ms=0.0, gated=gated
    )
    return writer


class TestColorloopWholeLight:
    """A whole light gets one colour write per step."""

    async def test_a_light_gets_one_write_per_step(self) -> None:
        effect = _loop()
        light = _light()
        effect.participants = [light]
        writer = MagicMock()

        for elapsed in (0.0, 0.05, 0.5, 0.95):
            effect._deliver(0, writer, [_hue_at(elapsed)], _ctx(elapsed), False)
        await asyncio.sleep(0)

        light.set_color.assert_awaited_once()
        color = light.set_color.call_args.args[0]
        assert color.hue == 130
        assert light.set_color.call_args.kwargs["duration"] == 1.0
        writer.send_frame.assert_not_called()

        effect._deliver(0, writer, [_hue_at(1.25)], _ctx(1.25), False)
        await asyncio.sleep(0)

        assert light.set_color.await_count == 2
        assert light.set_color.call_args.args[0].hue == 140
        assert light.set_color.call_args.kwargs["duration"] == pytest.approx(0.75)

    async def test_a_transition_replaces_the_steps_length(self) -> None:
        effect = _loop(transition=0.25)
        light = _light()
        effect.participants = [light]

        effect._deliver(0, MagicMock(), [_hue_at(0.4)], _ctx(0.4), False)
        await asyncio.sleep(0)

        assert light.set_color.call_args.args[0].hue == 130
        assert light.set_color.call_args.kwargs["duration"] == 0.25

    async def test_a_new_step_cancels_a_write_still_in_flight(self) -> None:
        effect = _loop()
        light = _light()
        hang = asyncio.Event()

        async def slow(_color: HSBK, duration: float) -> None:
            await hang.wait()

        light.set_color = AsyncMock(side_effect=slow)
        effect.participants = [light]
        writer = MagicMock()

        effect._deliver(0, writer, [_hue_at(0.0)], _ctx(0.0), False)
        (first,) = effect._writes.values()
        await asyncio.sleep(0)
        effect._deliver(0, writer, [_hue_at(1.0)], _ctx(1.0), False)
        await asyncio.sleep(0)

        assert first.cancelled()
        assert light.set_color.await_count == 2
        hang.set()
        await asyncio.gather(*effect._writes.values())

    async def test_a_failed_write_is_logged_and_the_loop_carries_on(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        effect = _loop()
        light = _light()
        light.set_color = AsyncMock(side_effect=LifxTimeoutError("no reply"))
        effect.participants = [light]

        effect._deliver(0, MagicMock(), [_hue_at(0.0)], _ctx(0.0), False)
        await asyncio.gather(*effect._writes.values())

        assert "no reply" in caplog.text

    async def test_stopping_cancels_writes_in_flight(self) -> None:
        effect = _loop()
        light = _light()
        hang = asyncio.Event()

        async def slow(_color: HSBK, duration: float) -> None:
            await hang.wait()

        light.set_color = AsyncMock(side_effect=slow)
        effect.participants = [light]
        writer = MagicMock()
        writer.pixel_count = 1
        writer.canvas_width = 1
        writer.canvas_height = 1
        writer.wraps = False
        effect._animators = [writer]

        play = asyncio.create_task(effect.async_play())
        while not effect._writes:
            await asyncio.sleep(0.01)
        (write,) = effect._writes.values()
        effect.stop()
        await asyncio.wait_for(play, timeout=1.0)

        assert write.cancelled()
        assert effect._writes == {}
        writer.send_frame.assert_not_called()


class TestColorloopComponent:
    """A light component's tile is written once per step unless it is shared."""

    def test_an_idle_tile_is_sent_once_per_step(self) -> None:
        effect = _loop()
        writer = _slot_writer()

        effect._deliver(0, writer, [_hue_at(0.0)], _ctx(0.0), False)
        effect._deliver(0, writer, [_hue_at(0.5)], _ctx(0.5), False)

        writer.send_frame.assert_called_once_with(
            [_hue_at(1.0)], duration_ms=1000, settled=True
        )
        assert writer.stage.call_args_list == [
            call([_hue_at(0.0)]),
            call([_hue_at(0.5)]),
        ]

    def test_a_shared_tile_only_keeps_its_slot_then_writes_once_alone(self) -> None:
        effect = _loop()
        writer = _slot_writer(shared=True)

        effect._deliver(0, writer, [_hue_at(0.0)], _ctx(0.0), False)

        writer.stage.assert_called_once_with([_hue_at(0.0)])
        writer.send_frame.assert_not_called()

        writer.tile_shared.return_value = False
        effect._deliver(0, writer, [_hue_at(0.3)], _ctx(0.3), False)

        writer.send_frame.assert_called_once_with(
            [_hue_at(1.0)], duration_ms=700, settled=True
        )

    def test_a_held_fade_on_wifi_is_streamed(self) -> None:
        effect = _loop()
        light = _light()
        light._evidenced_connectivity.return_value = Connectivity.WIFI
        effect.participants = [light]
        writer = _slot_writer(fade=2.0)

        effect._deliver(0, writer, [_hue_at(0.0)], _ctx(0.0), False)

        writer.send_frame.assert_called_once_with([_hue_at(0.0)])

    @pytest.mark.parametrize("fade", [18.0, 20.0, 36.0])
    @pytest.mark.parametrize("direction", [1, -1])
    def test_a_long_held_fade_on_thread_is_followed_a_step_at_a_time(
        self, fade: float, direction: int
    ) -> None:
        """No write turns the hue further than one step, however long the fade.

        Half a period (18 s) and more would reverse the loop if one write
        covered the fade, since the firmware fades hue the short way round.
        """
        effect = _loop()
        effect._direction = direction
        light = _light()
        light._evidenced_connectivity.return_value = Connectivity.THREAD
        effect.participants = [light]
        writer = _slot_writer(fade=fade)

        for step in range(6):
            writer.hold_remaining = max(0.0, fade - step)
            effect._deliver(0, writer, [_hue_at(step)], _ctx(float(step)), False)

        sends = writer.send_frame.call_args_list
        assert [c.kwargs for c in sends] == [{"duration_ms": 1000, "settled": True}] * 6
        hues = [HSBK.from_protocol(LightHsbk(*c.args[0][0])).hue for c in sends]
        turns = [round((b - a) % 360) for a, b in zip(hues, hues[1:])]
        assert turns == [10 if direction == 1 else 350] * 5

    def test_a_held_fade_shorter_than_the_step_keeps_the_step(self) -> None:
        effect = _loop()
        light = _light()
        light._evidenced_connectivity.return_value = Connectivity.THREAD
        effect.participants = [light]
        writer = _slot_writer(fade=0.25)

        effect._deliver(0, writer, [_hue_at(0.0)], _ctx(0.0), False)

        writer.send_frame.assert_called_once_with(
            [_hue_at(1.0)], duration_ms=1000, settled=True
        )

    def test_a_change_to_the_held_colours_is_sent_at_once(self) -> None:
        effect = _loop()
        writer = _slot_writer()

        effect._deliver(0, writer, [_hue_at(0.0)], _ctx(0.0), False)
        writer.hold_version = 1
        effect._deliver(0, writer, [_hue_at(0.4)], _ctx(0.4), False)

        assert writer.send_frame.call_count == 2
        assert writer.send_frame.call_args.kwargs == {
            "duration_ms": 600,
            "settled": True,
        }

    def test_a_write_ends_no_later_than_another_slots_fade(self) -> None:
        effect = _loop()
        writer = _slot_writer()
        writer.slot_deadline.return_value = 0.25

        effect._deliver(0, writer, [_hue_at(0.0)], _ctx(0.0), False)
        writer.slot_deadline.return_value = None
        effect._deliver(0, writer, [_hue_at(0.2)], _ctx(0.2), False)
        effect._deliver(0, writer, [_hue_at(0.25)], _ctx(0.25), False)

        assert writer.send_frame.call_args_list == [
            call([_hue_at(0.25)], duration_ms=250, settled=True),
            call([_hue_at(1.0)], duration_ms=750, settled=True),
        ]

    def test_a_fade_ending_within_a_frame_does_not_shorten_a_write(self) -> None:
        effect = _loop()
        writer = _slot_writer()
        writer.slot_deadline.return_value = 0.01

        effect._deliver(0, writer, [_hue_at(0.0)], _ctx(0.0), False)

        writer.send_frame.assert_called_once_with(
            [_hue_at(1.0)], duration_ms=1000, settled=True
        )

    def test_a_shortened_write_keeps_a_shorter_transition(self) -> None:
        for transition, expected in ((0.1, 100), (2.0, 250)):
            effect = _loop(transition=transition)
            writer = _slot_writer()
            writer.slot_deadline.return_value = 0.25

            effect._deliver(0, writer, [_hue_at(0.0)], _ctx(0.0), False)

            writer.send_frame.assert_called_once_with(
                [_hue_at(0.25)], duration_ms=expected, settled=True
            )

    def test_a_gated_send_is_tried_again_next_frame(self) -> None:
        effect = _loop()
        writer = _slot_writer(gated=True)

        effect._deliver(0, writer, [_hue_at(0.0)], _ctx(0.0), False)
        writer.send_frame.return_value = AnimatorStats(
            packets_sent=1, total_time_ms=0.0
        )
        effect._deliver(0, writer, [_hue_at(0.05)], _ctx(0.05), False)
        effect._deliver(0, writer, [_hue_at(0.1)], _ctx(0.1), False)

        assert writer.send_frame.call_count == 2
        assert writer.stage.call_args_list == [
            call([_hue_at(0.0)]),
            call([_hue_at(0.05)]),
            call([_hue_at(0.1)]),
        ]

    def test_two_writers_on_one_tile_send_it_once_per_step(self) -> None:
        effect = _loop()
        tile = object()
        first = _slot_writer(tile=tile)
        second = _slot_writer(tile=tile)

        for elapsed in (0.0, 0.5):
            effect._deliver(0, first, [_hue_at(elapsed)], _ctx(elapsed), True)
            effect._deliver(1, second, [_hue_at(elapsed)], _ctx(elapsed), False)

        assert first.stage.call_args_list == [
            call([_hue_at(0.0)]),
            call([_hue_at(1.0)], settled=True, duration_ms=1000),
            call([_hue_at(0.5)]),
        ]
        second.send_frame.assert_called_once_with(
            [_hue_at(1.0)], duration_ms=1000, settled=True
        )


class TestColorloopLeavingWriters:
    """A participant that leaves the run takes its colour write with it."""

    async def test_dropping_a_participant_cancels_its_write(self) -> None:
        effect = _loop()
        effect._initial_colors = effect._initial_colors * 2
        hang = asyncio.Event()

        async def slow(_color: HSBK, duration: float) -> None:
            await hang.wait()

        leaving, staying = _light(), _light()
        leaving.set_color = AsyncMock(side_effect=slow)
        staying.set_color = AsyncMock(side_effect=slow)
        first, second = MagicMock(), MagicMock()
        effect.participants = [leaving, staying]
        effect._animators = [first, second]
        effect._deliver(0, first, [_hue_at(0.0)], _ctx(0.0), False)
        effect._deliver(1, second, [_hue_at(0.0)], _ctx(0.0), False)
        left, stayed = effect._writes[first], effect._writes[second]
        await asyncio.sleep(0)

        drop_participant(effect, 0)
        await asyncio.sleep(0)

        assert left.cancelled()
        assert not stayed.done()
        first.close.assert_called_once_with()
        assert effect.participants == [staying]
        hang.set()
        await stayed

    async def test_a_replaced_writer_cancels_its_write(self) -> None:
        effect = _loop()
        hang = asyncio.Event()

        async def slow(_color: HSBK, duration: float) -> None:
            await hang.wait()

        light = _light()
        light.set_color = AsyncMock(side_effect=slow)
        old = MagicMock()
        effect.participants = [light]
        effect._animators = [old]
        effect._deliver(0, old, [_hue_at(0.0)], _ctx(0.0), False)
        write = effect._writes[old]
        await asyncio.sleep(0)

        replace_writer(effect, 0, _slot_writer())
        await asyncio.sleep(0)

        assert write.cancelled()
        assert effect._writes == {}

    def test_a_writer_with_no_write_leaves_quietly(self) -> None:
        effect = _loop()

        effect._writer_closed(MagicMock())

        assert effect._writes == {}


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
    light.ensure_capabilities = AsyncMock()

    async def set_capabilities():
        light.capabilities = MagicMock()
        light.capabilities.has_color = True

    light.ensure_capabilities.side_effect = set_capabilities

    result = await effect.is_light_compatible(light)

    light.ensure_capabilities.assert_called_once()
    assert result is True


@pytest.mark.asyncio
async def test_colorloop_is_light_compatible_capabilities_still_none() -> None:
    """Test is_light_compatible when capabilities remain None after loading."""
    effect = EffectColorloop()

    light = MagicMock()
    light.capabilities = None
    light.ensure_capabilities = AsyncMock()

    result = await effect.is_light_compatible(light)

    assert result is False


@pytest.mark.asyncio
async def test_colorloop_is_light_compatible_capabilities_already_loaded() -> None:
    """Test is_light_compatible when capabilities are already loaded."""
    effect = EffectColorloop()

    light = MagicMock()
    light.capabilities = MagicMock()
    light.capabilities.has_color = True
    light.ensure_capabilities = AsyncMock()

    result = await effect.is_light_compatible(light)

    light.ensure_capabilities.assert_not_called()
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
