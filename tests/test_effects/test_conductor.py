"""Tests for Conductor dynamic light management (add_lights/remove_lights)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.effects.base import LIFXEffect
from lifx.effects.conductor import Conductor
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.models import PreState, RunningEffect


def _make_color_light(serial: str, ip: str = "192.168.1.100") -> MagicMock:
    """Create a mock color light."""
    light = MagicMock(spec=Light)
    light.serial = serial
    light.ip = ip
    light.port = 56700

    capabilities = MagicMock()
    capabilities.has_color = True
    capabilities.has_multizone = False
    capabilities.has_matrix = False
    light.capabilities = capabilities
    light._ensure_capabilities = AsyncMock()

    light.get_power = AsyncMock(return_value=True)
    light.get_color = AsyncMock(
        return_value=(
            HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),
            65535,
            "Test Light",
        )
    )
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()

    return light


class _SimpleFrameEffect(FrameEffect):
    """Minimal frame effect for testing."""

    def __init__(self) -> None:
        super().__init__(power_on=True, fps=20.0, duration=None)

    @property
    def name(self) -> str:
        return "test"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        return [
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        ] * ctx.pixel_count

    async def is_light_compatible(self, light: Light) -> bool:
        if light.capabilities is None:
            await light._ensure_capabilities()
        return light.capabilities.has_color if light.capabilities else False


@pytest.fixture
def conductor():
    """Create a Conductor instance."""
    return Conductor()


@pytest.fixture
def light1():
    """Create first mock light."""
    return _make_color_light("d073d5000001", "192.168.1.100")


@pytest.fixture
def light2():
    """Create second mock light."""
    return _make_color_light("d073d5000002", "192.168.1.101")


@pytest.fixture
def light3():
    """Create third mock light."""
    return _make_color_light("d073d5000003", "192.168.1.102")


async def _start_effect_with_mock_animators(
    conductor: Conductor, effect: FrameEffect, lights: list[MagicMock]
) -> None:
    """Start an effect with mock animators to avoid real UDP."""
    with patch.object(conductor, "_create_animators") as mock_create:
        animators = []
        for _ in lights:
            animator = MagicMock()
            animator.pixel_count = 1
            animator.canvas_width = 1
            animator.canvas_height = 1
            animator.send_frame = MagicMock()
            animator.close = MagicMock()
            animators.append(animator)

        mock_create.return_value = animators
        await conductor.start(effect, lights)


async def test_add_lights_to_running_effect(conductor, light1, light2):
    """Test adding a light to a running effect registers it."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        animator1 = MagicMock()
        animator1.pixel_count = 1
        animator1.canvas_width = 1
        animator1.canvas_height = 1
        animator1.send_frame = MagicMock()
        animator1.close = MagicMock()
        mock_create.return_value = [animator1]
        await conductor.start(effect, [light1])

    assert light1.serial in conductor._running
    assert light2.serial not in conductor._running

    # Add light2
    with patch.object(conductor, "_create_animators") as mock_create:
        animator2 = MagicMock()
        animator2.pixel_count = 1
        animator2.canvas_width = 1
        animator2.canvas_height = 1
        animator2.send_frame = MagicMock()
        animator2.close = MagicMock()
        mock_create.return_value = [animator2]
        await conductor.add_lights(effect, [light2])

    assert light2.serial in conductor._running
    assert conductor._running[light2.serial].effect is effect

    await conductor.stop([light1, light2])


async def test_add_lights_captures_prestate(conductor, light1, light2):
    """Test that add_lights captures prestate for the new light."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            )
        ]
        await conductor.start(effect, [light1])

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            )
        ]
        await conductor.add_lights(effect, [light2])

    running = conductor._running[light2.serial]
    assert running.prestate is not None
    assert isinstance(running.prestate, PreState)

    await conductor.stop([light1, light2])


async def test_add_lights_creates_animator(conductor, light1, light2):
    """Test that add_lights creates and appends an animator."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            )
        ]
        await conductor.start(effect, [light1])

    assert len(effect._animators) == 1

    with patch.object(conductor, "_create_animators") as mock_create:
        new_animator = MagicMock(
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
            send_frame=MagicMock(),
            close=MagicMock(),
        )
        mock_create.return_value = [new_animator]
        await conductor.add_lights(effect, [light2])

    assert len(effect._animators) == 2
    assert effect._animators[1] is new_animator

    await conductor.stop([light1, light2])


async def test_add_lights_skips_already_running(conductor, light1):
    """Test that adding an already-running light is a no-op."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            )
        ]
        await conductor.start(effect, [light1])

    assert len(effect._animators) == 1

    await conductor.add_lights(effect, [light1])

    # Should still only have 1 animator — no duplicate
    assert len(effect._animators) == 1

    await conductor.stop([light1])


async def test_add_lights_filters_incompatible(conductor, light1):
    """Test that incompatible lights are not added."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            )
        ]
        await conductor.start(effect, [light1])

    # Create a non-color light
    white_light = _make_color_light("d073d5000099")
    white_light.capabilities.has_color = False

    await conductor.add_lights(effect, [white_light])

    assert white_light.serial not in conductor._running

    await conductor.stop([light1])


async def test_remove_lights_restores_state(conductor, light1, light2):
    """Test that remove_lights restores prestate."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        a1 = MagicMock(
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
            send_frame=MagicMock(),
            close=MagicMock(),
        )
        a2 = MagicMock(
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
            send_frame=MagicMock(),
            close=MagicMock(),
        )
        mock_create.return_value = [a1, a2]
        await conductor.start(effect, [light1, light2])

    # Remove light2
    with patch.object(
        conductor._state_manager, "restore_state", new_callable=AsyncMock
    ) as mock_restore:
        await conductor.remove_lights([light2])

    mock_restore.assert_called_once()
    assert light2.serial not in conductor._running

    await conductor.stop([light1])


async def test_remove_lights_closes_animator(conductor, light1, light2):
    """Test that remove_lights closes and removes the animator."""
    effect = _SimpleFrameEffect()

    a1 = MagicMock(
        pixel_count=1,
        canvas_width=1,
        canvas_height=1,
        send_frame=MagicMock(),
        close=MagicMock(),
    )
    a2 = MagicMock(
        pixel_count=1,
        canvas_width=1,
        canvas_height=1,
        send_frame=MagicMock(),
        close=MagicMock(),
    )

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [a1, a2]
        await conductor.start(effect, [light1, light2])

    assert len(effect._animators) == 2

    await conductor.remove_lights([light2])

    # Animator for light2 should have been closed
    a2.close.assert_called_once()
    assert len(effect._animators) == 1
    assert effect._animators[0] is a1

    await conductor.stop([light1])


async def test_remove_lights_no_restore(conductor, light1, light2):
    """Test remove_lights with restore_state=False skips restoration."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            ),
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            ),
        ]
        await conductor.start(effect, [light1, light2])

    with patch.object(
        conductor._state_manager, "restore_state", new_callable=AsyncMock
    ) as mock_restore:
        await conductor.remove_lights([light2], restore_state=False)

    mock_restore.assert_not_called()
    assert light2.serial not in conductor._running

    await conductor.stop([light1])


async def test_remove_last_light_cancels_task(conductor, light1):
    """Test removing the last participant cancels the background task."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            )
        ]
        await conductor.start(effect, [light1])

    task = conductor._running[light1.serial].task

    await conductor.remove_lights([light1])

    # Task should be done (cancelled)
    assert task.done()
    assert light1.serial not in conductor._running


async def test_remove_lights_keeps_other_participants(conductor, light1, light2):
    """Test that removing one light doesn't affect others."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            ),
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            ),
        ]
        await conductor.start(effect, [light1, light2])

    await conductor.remove_lights([light1])

    # light2 should still be running
    assert light2.serial in conductor._running
    assert conductor._running[light2.serial].effect is effect

    # light1 should be gone
    assert light1.serial not in conductor._running

    await conductor.stop([light2])


async def test_add_then_remove_roundtrip(conductor, light1, light2):
    """Test adding a light and then removing it leaves clean state."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            )
        ]
        await conductor.start(effect, [light1])

    # Add light2
    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            )
        ]
        await conductor.add_lights(effect, [light2])

    assert light2.serial in conductor._running
    assert len(effect._animators) == 2
    assert len(effect.participants) == 2

    # Remove light2
    await conductor.remove_lights([light2])

    assert light2.serial not in conductor._running
    assert len(effect._animators) == 1
    assert len(effect.participants) == 1

    await conductor.stop([light1])


# --- get_last_frame tests ---


async def test_get_last_frame_no_running_effect(conductor, light1):
    """get_last_frame returns None when no effect is running."""
    assert conductor.get_last_frame(light1) is None


async def test_get_last_frame_returns_stored_frame(conductor, light1):
    """get_last_frame returns the frame stored by the frame loop."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=4,
                canvas_width=4,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            )
        ]
        await conductor.start(effect, [light1])

    # Simulate what async_play does: store a frame in _last_frames
    frame = [HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)] * 4
    effect._last_frames[light1.serial] = frame

    result = conductor.get_last_frame(light1)
    assert result is frame
    assert len(result) == 4

    await conductor.stop([light1])


async def test_get_last_frame_returns_none_before_first_frame(conductor, light1):
    """get_last_frame returns None if no frame has been generated yet."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            )
        ]
        await conductor.start(effect, [light1])

    # No frame generated yet
    assert conductor.get_last_frame(light1) is None

    await conductor.stop([light1])


async def test_get_last_frame_per_device(conductor, light1, light2):
    """get_last_frame returns the correct frame per device."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=2,
                canvas_width=2,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            ),
            MagicMock(
                pixel_count=4,
                canvas_width=4,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            ),
        ]
        await conductor.start(effect, [light1, light2])

    frame1 = [HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)] * 2
    frame2 = [HSBK(hue=120, saturation=0.5, brightness=0.5, kelvin=4000)] * 4
    effect._last_frames[light1.serial] = frame1
    effect._last_frames[light2.serial] = frame2

    result1 = conductor.get_last_frame(light1)
    result2 = conductor.get_last_frame(light2)
    assert result1 is frame1
    assert result2 is frame2
    assert len(result1) == 2
    assert len(result2) == 4

    await conductor.stop([light1, light2])


async def test_get_last_frame_after_stop_returns_none(conductor, light1):
    """get_last_frame returns None after the effect is stopped."""
    effect = _SimpleFrameEffect()

    with patch.object(conductor, "_create_animators") as mock_create:
        mock_create.return_value = [
            MagicMock(
                pixel_count=1,
                canvas_width=1,
                canvas_height=1,
                send_frame=MagicMock(),
                close=MagicMock(),
            )
        ]
        await conductor.start(effect, [light1])

    effect._last_frames[light1.serial] = [
        HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
    ]
    assert conductor.get_last_frame(light1) is not None

    await conductor.stop([light1])

    # After stop, the running entry is removed
    assert conductor.get_last_frame(light1) is None


class _SimpleNonFrameEffect(LIFXEffect):
    """Minimal non-frame effect for testing."""

    def __init__(self) -> None:
        super().__init__(power_on=True)

    @property
    def name(self) -> str:
        return "test_non_frame"

    async def async_play(self) -> None:
        pass

    async def is_light_compatible(self, light: Light) -> bool:
        return True


async def test_get_last_frame_non_frame_effect(conductor, light1):
    """get_last_frame returns None when effect is not a FrameEffect."""
    effect = _SimpleNonFrameEffect()

    # Register a running effect manually (bypassing start to avoid real setup)
    prestate = PreState(
        power=True,
        color=HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500),
    )
    import asyncio

    task = asyncio.create_task(asyncio.sleep(10))
    conductor._running[light1.serial] = RunningEffect(
        effect=effect, prestate=prestate, task=task
    )

    result = conductor.get_last_frame(light1)
    assert result is None

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    del conductor._running[light1.serial]


async def test_add_lights_no_task_found(conductor, light1):
    """add_lights logs warning and returns when effect has no running task."""
    effect = _SimpleFrameEffect()

    # Effect is not running anywhere — no task in _running
    await conductor.add_lights(effect, [light1])

    # Light should NOT have been added
    assert light1.serial not in conductor._running


async def test_remove_lights_not_running(conductor, light1):
    """remove_lights is a no-op for lights that aren't running."""
    # light1 is not in _running
    assert light1.serial not in conductor._running

    # Should not raise — just skips the light
    await conductor.remove_lights([light1])

    assert light1.serial not in conductor._running
