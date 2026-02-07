"""Integration tests for effects system."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.effects import Conductor, EffectColorloop, EffectPulse
from lifx.effects.frame_effect import FrameContext, FrameEffect


async def wait_for_mock_called(
    mock: MagicMock, timeout: float = 1.0, poll_interval: float = 0.01
) -> None:
    """Wait for a mock to be called, with timeout.

    This is more reliable than fixed sleeps on slow CI systems (especially Windows).

    Args:
        mock: The mock object to check
        timeout: Maximum time to wait in seconds
        poll_interval: Time between checks in seconds

    Raises:
        AssertionError: If mock was not called within timeout
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if mock.call_count > 0:
            return
        await asyncio.sleep(poll_interval)
    raise AssertionError(f"Expected mock to be called within {timeout}s")


async def wait_for_effect_complete(
    conductor: Conductor,
    light: MagicMock,
    timeout: float = 2.0,
    poll_interval: float = 0.05,
) -> None:
    """Wait for an effect to complete and be removed from registry.

    This is more reliable than fixed sleeps on slow CI systems (especially Windows).

    Args:
        conductor: The Conductor instance
        light: The light to check
        timeout: Maximum time to wait in seconds
        poll_interval: Time between checks in seconds

    Raises:
        AssertionError: If effect was not removed within timeout
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if conductor.effect(light) is None:
            return
        await asyncio.sleep(poll_interval)
    raise AssertionError(f"Expected effect to complete within {timeout}s")


@pytest.fixture
def conductor() -> Conductor:
    """Create a Conductor instance."""
    return Conductor()


@pytest.fixture
def mock_light() -> MagicMock:
    """Create a mock light device."""
    light = MagicMock()
    light.serial = "d073d5123456"
    light.capabilities = MagicMock()
    light.capabilities.has_color = True

    # Setup common mock responses
    light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    light.color = (color, 100)
    light.get_color = AsyncMock(return_value=(color, 100, 200))
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()
    light.set_waveform = AsyncMock()

    return light


@pytest.fixture
def mock_white_light():
    """Create a mock white light (no color support)."""
    light = MagicMock()
    light.serial = "d073d5abcdef"
    light.capabilities = MagicMock()
    light.capabilities.has_color = False

    # Setup common mock responses
    light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=0, saturation=0, brightness=0.8, kelvin=3500)
    light.color = (color, 100)
    light.get_color = AsyncMock(return_value=(color, 100, 200))
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()
    light.set_waveform = AsyncMock()

    return light


@pytest.mark.asyncio
async def test_conductor_start_stop_pulse(conductor, mock_light) -> None:
    """Test starting and stopping a pulse effect."""
    effect = EffectPulse(mode="blink", cycles=1, period=0.1)

    # Start effect
    await conductor.start(effect, [mock_light])

    # Verify effect is running
    running = conductor.effect(mock_light)
    assert running is not None
    assert isinstance(running, EffectPulse)

    # Stop effect
    await conductor.stop([mock_light])

    # Verify effect is no longer running
    assert conductor.effect(mock_light) is None


@pytest.mark.asyncio
async def test_pulse_effect_execution(conductor, mock_light) -> None:
    """Test pulse effect executes and calls set_waveform."""
    effect = EffectPulse(mode="blink", cycles=1, period=0.1)

    # Start effect and let it run briefly
    await conductor.start(effect, [mock_light])
    await asyncio.sleep(0.05)  # Let effect start

    # Verify waveform was called
    mock_light.set_waveform.assert_called()

    # Stop effect
    await conductor.stop([mock_light])


@pytest.mark.asyncio
async def test_pulse_effect_with_color(conductor, mock_light) -> None:
    """Test pulse effect with explicit color."""
    custom_color = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=4000)
    effect = EffectPulse(mode="blink", cycles=1, period=0.1, color=custom_color)

    await conductor.start(effect, [mock_light])
    await asyncio.sleep(0.05)

    # Verify waveform was called with custom color
    mock_light.set_waveform.assert_called()
    call_kwargs = mock_light.set_waveform.call_args.kwargs
    assert call_kwargs["color"] == custom_color

    await conductor.stop([mock_light])


@pytest.mark.asyncio
async def test_pulse_effect_strobe_mode(conductor, mock_light) -> None:
    """Test pulse effect in strobe mode."""
    effect = EffectPulse(mode="strobe", cycles=2, period=0.05)

    await conductor.start(effect, [mock_light])

    # Use polling instead of fixed sleep - more reliable on slow CI systems
    await wait_for_mock_called(mock_light.set_waveform, timeout=1.0)

    await conductor.stop([mock_light])


@pytest.mark.asyncio
async def test_pulse_effect_breathe_mode(conductor, mock_light) -> None:
    """Test pulse effect in breathe mode."""
    effect = EffectPulse(mode="breathe", cycles=1, period=0.1)

    await conductor.start(effect, [mock_light])
    await asyncio.sleep(0.05)

    # Verify waveform called with sine waveform
    mock_light.set_waveform.assert_called()

    await conductor.stop([mock_light])


@pytest.mark.asyncio
async def test_colorloop_effect_execution(conductor, mock_light) -> None:
    """Test colorloop effect executes and sends frames via animator."""
    effect = EffectColorloop(period=0.2, change=30)

    mock_animator = MagicMock()
    mock_animator.pixel_count = 1
    mock_animator.canvas_width = 1
    mock_animator.canvas_height = 1
    mock_animator.send_frame = MagicMock()
    mock_animator.close = MagicMock()

    with patch(
        "lifx.effects.conductor.Conductor._create_animators",
        return_value=[mock_animator],
    ):
        # Start effect and let it run briefly
        await conductor.start(effect, [mock_light])
        await asyncio.sleep(0.05)  # Let effect iterate once

        # Verify frames were sent via animator
        assert mock_animator.send_frame.call_count > 0

        # Stop effect
        await conductor.stop([mock_light])


@pytest.mark.asyncio
async def test_colorloop_synchronized_mode(conductor, mock_light) -> None:
    """Test colorloop in synchronized mode sends frames for all lights."""
    # Create two mock lights
    light1 = mock_light
    light2 = MagicMock()
    light2.serial = "d073d5fedcba"
    light2.capabilities = MagicMock()
    light2.capabilities.has_color = True
    light2.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=180, saturation=1.0, brightness=0.8, kelvin=3500)
    light2.color = (color, 100)
    light2.get_color = AsyncMock(return_value=(color, 100, 200))
    light2.set_color = AsyncMock()
    light2.set_power = AsyncMock()

    effect = EffectColorloop(period=0.2, change=30, synchronized=True)

    mock_animator1 = MagicMock()
    mock_animator1.pixel_count = 1
    mock_animator1.canvas_width = 1
    mock_animator1.canvas_height = 1
    mock_animator1.send_frame = MagicMock()
    mock_animator1.close = MagicMock()

    mock_animator2 = MagicMock()
    mock_animator2.pixel_count = 1
    mock_animator2.canvas_width = 1
    mock_animator2.canvas_height = 1
    mock_animator2.send_frame = MagicMock()
    mock_animator2.close = MagicMock()

    with patch(
        "lifx.effects.conductor.Conductor._create_animators",
        return_value=[mock_animator1, mock_animator2],
    ):
        # Start effect
        await conductor.start(effect, [light1, light2])
        await asyncio.sleep(0.05)

        # Both animators should have send_frame called
        assert mock_animator1.send_frame.called
        assert mock_animator2.send_frame.called

        await conductor.stop([light1, light2])


@pytest.mark.asyncio
async def test_colorloop_with_brightness(conductor, mock_light) -> None:
    """Test colorloop with fixed brightness sends frames."""
    effect = EffectColorloop(period=0.2, change=30, brightness=0.5)

    mock_animator = MagicMock()
    mock_animator.pixel_count = 1
    mock_animator.canvas_width = 1
    mock_animator.canvas_height = 1
    mock_animator.send_frame = MagicMock()
    mock_animator.close = MagicMock()

    with patch(
        "lifx.effects.conductor.Conductor._create_animators",
        return_value=[mock_animator],
    ):
        await conductor.start(effect, [mock_light])
        await asyncio.sleep(0.05)

        # Verify frames were sent
        assert mock_animator.send_frame.called

        await conductor.stop([mock_light])


@pytest.mark.asyncio
async def test_colorloop_filters_white_lights(
    conductor, mock_light, mock_white_light
) -> None:
    """Test colorloop filters out non-color lights."""
    effect = EffectColorloop(period=0.2, change=30)

    mock_animator = MagicMock()
    mock_animator.pixel_count = 1
    mock_animator.canvas_width = 1
    mock_animator.canvas_height = 1
    mock_animator.send_frame = MagicMock()
    mock_animator.close = MagicMock()

    # _create_animators should only be called with the color light (white is filtered)
    with patch(
        "lifx.effects.conductor.Conductor._create_animators",
        return_value=[mock_animator],
    ) as mock_create:
        # Start effect with mixed lights
        await conductor.start(effect, [mock_light, mock_white_light])
        await asyncio.sleep(0.05)

        # Verify _create_animators was called with only the color light
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert len(call_args[0][1]) == 1  # Only one compatible light
        assert call_args[0][1][0] is mock_light

        # White light should not have been sent any colors
        assert not mock_white_light.set_color.called

        await conductor.stop([mock_light, mock_white_light])


@pytest.mark.asyncio
async def test_pulse_does_not_filter_white_lights(
    conductor, mock_light, mock_white_light
):
    """Test pulse effect works on all lights."""
    effect = EffectPulse(mode="blink", cycles=1, period=0.1)

    # Start effect with mixed lights
    await conductor.start(effect, [mock_light, mock_white_light])
    await asyncio.sleep(0.05)

    # Both lights should have waveform called
    assert mock_light.set_waveform.called
    assert mock_white_light.set_waveform.called

    await conductor.stop([mock_light, mock_white_light])


@pytest.mark.asyncio
async def test_effect_with_powered_off_light(conductor, mock_light) -> None:
    """Test effect powers on light that is off."""
    # Light starts powered off
    mock_light.get_power = AsyncMock(return_value=False)

    effect = EffectPulse(mode="blink", cycles=1, period=0.1)

    await conductor.start(effect, [mock_light])
    await asyncio.sleep(0.05)

    # Verify light was powered on
    assert any(call[0][0] is True for call in mock_light.set_power.call_args_list)

    await conductor.stop([mock_light])


@pytest.mark.asyncio
async def test_effect_without_power_on(conductor) -> None:
    """Test effect with power_on=False doesn't power on lights."""
    # Create a fresh mock light that is powered off
    light = MagicMock()
    light.serial = "d073d5test123"
    light.capabilities = MagicMock()
    light.capabilities.has_color = True
    light.get_power = AsyncMock(return_value=False)
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    light.color = (color, 100)
    light.get_color = AsyncMock(return_value=(color, 100, 200))
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()
    light.set_waveform = AsyncMock()

    effect = EffectPulse(mode="blink", cycles=1, period=0.1, power_on=False)

    await conductor.start(effect, [light])
    await asyncio.sleep(0.05)

    # Verify set_power was not called to turn on the light
    assert (
        not any(call[0][0] is True for call in light.set_power.call_args_list)
        if light.set_power.call_args_list
        else True
    )

    await conductor.stop([light])


@pytest.mark.asyncio
async def test_consecutive_effects_inherit_prestate(conductor, mock_light) -> None:
    """Test consecutive colorloop effects inherit prestate."""
    effect1 = EffectColorloop(period=0.2, change=30)
    effect2 = EffectColorloop(period=0.3, change=45)

    mock_animator = MagicMock()
    mock_animator.pixel_count = 1
    mock_animator.canvas_width = 1
    mock_animator.canvas_height = 1
    mock_animator.send_frame = MagicMock()
    mock_animator.close = MagicMock()

    with patch(
        "lifx.effects.conductor.Conductor._create_animators",
        return_value=[mock_animator],
    ):
        # Start first effect
        await conductor.start(effect1, [mock_light])
        await asyncio.sleep(0.05)

        # Start second effect without stopping first
        await conductor.start(effect2, [mock_light])
        await asyncio.sleep(0.05)

        # Second effect should be running
        running = conductor.effect(mock_light)
        assert isinstance(running, EffectColorloop)

        await conductor.stop([mock_light])


@pytest.mark.asyncio
async def test_effect_completion_restores_state(conductor, mock_light) -> None:
    """Test effect automatically restores state on completion."""
    # Very short effect that will complete quickly
    effect = EffectPulse(mode="blink", cycles=1, period=0.05)

    await conductor.start(effect, [mock_light])

    # Use polling instead of fixed sleep - more reliable on slow CI systems
    # The effect should complete within ~0.1s but we allow up to 2s for CI variability
    await wait_for_effect_complete(conductor, mock_light, timeout=2.0)


@pytest.mark.asyncio
async def test_conductor_repr(conductor) -> None:
    """Test Conductor string representation."""
    assert "Conductor" in repr(conductor)
    assert "running_effects=0" in repr(conductor)


@pytest.mark.asyncio
async def test_multiple_lights_parallel(conductor, mock_light) -> None:
    """Test effect runs on multiple lights in parallel."""
    # Create multiple mock lights
    lights = []
    for i in range(5):
        light = MagicMock()
        light.serial = f"d073d512345{i}"
        light.capabilities = MagicMock()
        light.capabilities.has_color = True
        light.get_power = AsyncMock(return_value=True)
        color = HSBK(hue=i * 60, saturation=1.0, brightness=0.8, kelvin=3500)
        light.color = (color, 100)
        light.get_color = AsyncMock(return_value=(color, 100, 200))
        light.set_color = AsyncMock()
        light.set_power = AsyncMock()
        light.set_waveform = AsyncMock()
        lights.append(light)

    effect = EffectPulse(mode="blink", cycles=1, period=0.1)

    # Start effect on all lights
    await conductor.start(effect, lights)
    await asyncio.sleep(0.05)

    # All lights should have waveform called
    for light in lights:
        assert light.set_waveform.called

    await conductor.stop(lights)


@pytest.mark.asyncio
async def test_conductor_exception_during_effect() -> None:
    """Test conductor handles exception during effect execution."""
    conductor = Conductor()

    # Create mock light
    light = MagicMock()
    light.serial = "d073d5eece01"
    light.capabilities = MagicMock()
    light.capabilities.has_color = True
    light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    light.color = (color, 100)
    light.get_color = AsyncMock(return_value=(color, 100, 200))
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()

    effect = EffectColorloop(period=0.1, change=30)

    # Mock animator that raises exception on send_frame
    mock_animator = MagicMock()
    mock_animator.pixel_count = 1
    mock_animator.canvas_width = 1
    mock_animator.canvas_height = 1
    mock_animator.send_frame = MagicMock(side_effect=Exception("Device error"))
    mock_animator.close = MagicMock()

    with patch(
        "lifx.effects.conductor.Conductor._create_animators",
        return_value=[mock_animator],
    ):
        # Start effect (will fail but should handle exception)
        await conductor.start(effect, [light])
        await asyncio.sleep(0.1)

        # Effect should have been cleaned up after exception
        # (may or may not still be in registry depending on timing)
        # Just verify we didn't crash

        await conductor.stop([light])


@pytest.mark.asyncio
async def test_conductor_exception_during_async_perform() -> None:
    """Test conductor handles exception raised during async_perform."""
    from lifx.effects.base import LIFXEffect

    conductor = Conductor()

    # Create a custom effect that raises exception during async_perform
    class FailingEffect(LIFXEffect):
        @property
        def name(self) -> str:
            """Return the name of the effect."""
            return "failing"

        async def async_play(self):
            raise RuntimeError("Effect failed during execution")

    # Create mock light
    light = MagicMock()
    light.serial = "d073d5failtest"
    light.capabilities = MagicMock()
    light.capabilities.has_color = True
    light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    light.color = (color, 100)
    light.get_color = AsyncMock(return_value=(color, 100, 200))
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()

    effect = FailingEffect()

    # Start effect - should handle exception gracefully
    await conductor.start(effect, [light])

    # Give time for effect to fail
    await asyncio.sleep(0.1)

    # Light should have been removed from registry after exception
    assert light.serial not in conductor._running


@pytest.mark.asyncio
async def test_conductor_stop_with_active_effects() -> None:
    """Test stopping conductor with actively running effects."""
    conductor = Conductor()

    # Create mock light
    light = MagicMock()
    light.serial = "d073d5ac71be"
    light.capabilities = MagicMock()
    light.capabilities.has_color = True
    light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    light.color = (color, 100)
    light.get_color = AsyncMock(return_value=(color, 100, 200))
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()

    # Start a long-running effect
    effect = EffectColorloop(period=10.0, change=30)

    mock_animator = MagicMock()
    mock_animator.pixel_count = 1
    mock_animator.canvas_width = 1
    mock_animator.canvas_height = 1
    mock_animator.send_frame = MagicMock()
    mock_animator.close = MagicMock()

    with patch(
        "lifx.effects.conductor.Conductor._create_animators",
        return_value=[mock_animator],
    ):
        await conductor.start(effect, [light])
        await asyncio.sleep(0.05)

        # Stop should cancel and clean up
        await conductor.stop([light])

        # Verify light is no longer in registry
        assert conductor.effect(light) is None


@pytest.mark.asyncio
async def test_conductor_filter_lights_without_capabilities() -> None:
    """Test conductor filters lights that need capability check."""
    conductor = Conductor()

    # Create mock light with color capabilities
    light = MagicMock()
    light.serial = "d073d500ca95"
    light.capabilities = MagicMock()
    light.capabilities.has_color = True  # Set color capability
    light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    light.color = (color, 100)
    light.get_color = AsyncMock(return_value=(color, 100, 200))
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()

    # Colorloop requires color capability
    effect = EffectColorloop(period=0.2, change=30)

    mock_animator = MagicMock()
    mock_animator.pixel_count = 1
    mock_animator.canvas_width = 1
    mock_animator.canvas_height = 1
    mock_animator.send_frame = MagicMock()
    mock_animator.close = MagicMock()

    with patch(
        "lifx.effects.conductor.Conductor._create_animators",
        return_value=[mock_animator],
    ):
        # Should handle light with capabilities
        await conductor.start(effect, [light])
        await asyncio.sleep(0.05)

        await conductor.stop([light])


# --- FrameEffect + Conductor integration tests ---


class ConcreteFrameEffectForIntegration(FrameEffect):
    """Concrete FrameEffect for integration testing."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.frame_count = 0

    @property
    def name(self) -> str:
        return "test_integration_frame"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        self.frame_count += 1
        return [
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        ] * ctx.pixel_count


class FailingFrameEffect(FrameEffect):
    """FrameEffect that raises during async_play."""

    @property
    def name(self) -> str:
        return "failing_frame"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        return [
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        ] * ctx.pixel_count

    async def async_play(self) -> None:
        raise RuntimeError("Frame effect failed")


@pytest.mark.asyncio
async def test_conductor_creates_animators_for_frame_effect(
    conductor, mock_light
) -> None:
    """Test Conductor creates animators for FrameEffect."""
    effect = ConcreteFrameEffectForIntegration(fps=30.0, duration=0.1)

    with patch("lifx.effects.conductor.Conductor._create_animators") as mock_create:
        mock_animator = MagicMock()
        mock_animator.pixel_count = 1
        mock_animator.canvas_width = 1
        mock_animator.canvas_height = 1
        mock_animator.send_frame = MagicMock()
        mock_animator.close = MagicMock()
        mock_create.return_value = [mock_animator]

        await conductor.start(effect, [mock_light])

        # Verify _create_animators was called
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] is effect
        assert call_args[0][1] == [mock_light]

        await conductor.stop([mock_light])


@pytest.mark.asyncio
async def test_conductor_closes_animators_on_stop(conductor, mock_light) -> None:
    """Test Conductor closes animators when stopping a FrameEffect."""
    effect = ConcreteFrameEffectForIntegration(fps=30.0, duration=None)

    # Manually set up animator mocks
    mock_animator = MagicMock()
    mock_animator.pixel_count = 1
    mock_animator.canvas_width = 1
    mock_animator.canvas_height = 1
    mock_animator.send_frame = MagicMock()
    mock_animator.close = MagicMock()

    with patch(
        "lifx.effects.conductor.Conductor._create_animators",
        return_value=[mock_animator],
    ):
        await conductor.start(effect, [mock_light])
        await asyncio.sleep(0.05)  # Let effect start

        await conductor.stop([mock_light])

        # Verify animators were closed
        mock_animator.close.assert_called_once()


@pytest.mark.asyncio
async def test_conductor_closes_animators_on_completion(conductor, mock_light) -> None:
    """Test Conductor closes animators when FrameEffect completes naturally."""
    effect = ConcreteFrameEffectForIntegration(fps=30.0, duration=0.05)

    mock_animator = MagicMock()
    mock_animator.pixel_count = 1
    mock_animator.canvas_width = 1
    mock_animator.canvas_height = 1
    mock_animator.send_frame = MagicMock()
    mock_animator.close = MagicMock()

    with patch(
        "lifx.effects.conductor.Conductor._create_animators",
        return_value=[mock_animator],
    ):
        await conductor.start(effect, [mock_light])

        # Wait for effect to complete naturally
        await wait_for_effect_complete(conductor, mock_light, timeout=2.0)

        # Verify animators were closed
        mock_animator.close.assert_called_once()


@pytest.mark.asyncio
async def test_conductor_closes_animators_on_error(conductor, mock_light) -> None:
    """Test Conductor closes animators when FrameEffect raises an error."""
    effect = FailingFrameEffect(fps=30.0, duration=None)

    mock_animator = MagicMock()
    mock_animator.pixel_count = 1
    mock_animator.canvas_width = 1
    mock_animator.canvas_height = 1
    mock_animator.send_frame = MagicMock()
    mock_animator.close = MagicMock()

    with patch(
        "lifx.effects.conductor.Conductor._create_animators",
        return_value=[mock_animator],
    ):
        await conductor.start(effect, [mock_light])

        # Wait for effect to fail and be cleaned up
        await asyncio.sleep(0.2)

        # Verify animators were closed
        mock_animator.close.assert_called_once()

        # Light should be removed from registry
        assert conductor.effect(mock_light) is None


@pytest.mark.asyncio
async def test_conductor_frame_effect_with_multiple_device_types() -> None:
    """Test Conductor creates appropriate animators for different device types."""
    from lifx.animation.animator import Animator
    from lifx.devices.matrix import MatrixLight
    from lifx.devices.multizone import MultiZoneLight

    conductor = Conductor()

    # Create mock devices of different types
    light = MagicMock(spec=Light)
    light.serial = "d073d5light01"
    light.ip = "192.168.1.1"
    light.capabilities = MagicMock()
    light.capabilities.has_color = True
    light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    light.color = (color, 100)
    light.get_color = AsyncMock(return_value=(color, 100, 200))
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()

    multizone = MagicMock(spec=MultiZoneLight)
    multizone.serial = "d073d5multi01"
    multizone.ip = "192.168.1.2"
    multizone.capabilities = MagicMock()
    multizone.capabilities.has_color = True
    multizone.capabilities.has_extended_multizone = True
    multizone.get_power = AsyncMock(return_value=True)
    multizone.color = (color, 100)
    multizone.get_color = AsyncMock(return_value=(color, 100, 200))
    multizone.set_color = AsyncMock()
    multizone.set_power = AsyncMock()
    multizone.get_zone_count = AsyncMock(return_value=16)

    matrix = MagicMock(spec=MatrixLight)
    matrix.serial = "d073d5tile01"
    matrix.ip = "192.168.1.3"
    matrix.capabilities = MagicMock()
    matrix.capabilities.has_color = True
    matrix.capabilities.has_chain = False
    matrix.get_power = AsyncMock(return_value=True)
    matrix.color = (color, 100)
    matrix.get_color = AsyncMock(return_value=(color, 100, 200))
    matrix.set_color = AsyncMock()
    matrix.set_power = AsyncMock()

    tile = MagicMock()
    tile.width = 8
    tile.height = 8
    tile.user_x = 0.0
    tile.user_y = 0.0
    tile.nearest_orientation = "Upright"
    matrix.device_chain = [tile]
    matrix.get_device_chain = AsyncMock(return_value=[tile])

    effect = ConcreteFrameEffectForIntegration(fps=10.0, duration=0.05)

    # Mock the Animator factory methods to avoid actual UDP sockets
    mock_light_animator = MagicMock()
    mock_light_animator.pixel_count = 1
    mock_light_animator.canvas_width = 1
    mock_light_animator.canvas_height = 1
    mock_light_animator.send_frame = MagicMock()
    mock_light_animator.close = MagicMock()

    mock_mz_animator = MagicMock()
    mock_mz_animator.pixel_count = 16
    mock_mz_animator.canvas_width = 16
    mock_mz_animator.canvas_height = 1
    mock_mz_animator.send_frame = MagicMock()
    mock_mz_animator.close = MagicMock()

    mock_matrix_animator = MagicMock()
    mock_matrix_animator.pixel_count = 64
    mock_matrix_animator.canvas_width = 8
    mock_matrix_animator.canvas_height = 8
    mock_matrix_animator.send_frame = MagicMock()
    mock_matrix_animator.close = MagicMock()

    with (
        patch.object(Animator, "for_light", return_value=mock_light_animator),
        patch.object(
            Animator,
            "for_multizone",
            new_callable=AsyncMock,
            return_value=mock_mz_animator,
        ),
        patch.object(
            Animator,
            "for_matrix",
            new_callable=AsyncMock,
            return_value=mock_matrix_animator,
        ),
    ):
        await conductor.start(effect, [light, multizone, matrix])

        # Wait for effect to complete
        await asyncio.sleep(0.3)

        # All three factory methods should have been called
        # duration_ms = int(1500 / fps) where fps=10 -> 150ms (1.5x frame interval)
        Animator.for_light.assert_called_once_with(light, duration_ms=150)
        Animator.for_multizone.assert_called_once_with(multizone, duration_ms=150)
        Animator.for_matrix.assert_called_once_with(matrix, duration_ms=150)

        await conductor.stop([light, multizone, matrix])


@pytest.mark.asyncio
async def test_conductor_frame_effect_coexists_with_lifx_effect(
    conductor, mock_light
) -> None:
    """Test FrameEffect and LIFXEffect can coexist on different lights."""
    # Light 1 runs a FrameEffect
    light1 = mock_light

    # Light 2 runs a regular LIFXEffect (pulse)
    light2 = MagicMock()
    light2.serial = "d073d5pulse01"
    light2.capabilities = MagicMock()
    light2.capabilities.has_color = True
    light2.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=180, saturation=1.0, brightness=0.8, kelvin=3500)
    light2.color = (color, 100)
    light2.get_color = AsyncMock(return_value=(color, 100, 200))
    light2.set_color = AsyncMock()
    light2.set_power = AsyncMock()
    light2.set_waveform = AsyncMock()

    frame_effect = ConcreteFrameEffectForIntegration(fps=30.0, duration=None)
    pulse_effect = EffectPulse(mode="blink", cycles=1, period=0.1)

    mock_animator = MagicMock()
    mock_animator.pixel_count = 1
    mock_animator.canvas_width = 1
    mock_animator.canvas_height = 1
    mock_animator.send_frame = MagicMock()
    mock_animator.close = MagicMock()

    with patch(
        "lifx.effects.conductor.Conductor._create_animators",
        return_value=[mock_animator],
    ):
        await conductor.start(frame_effect, [light1])
        await conductor.start(pulse_effect, [light2])
        await asyncio.sleep(0.05)

        # Both effects should be running
        assert conductor.effect(light1) is frame_effect
        assert conductor.effect(light2) is pulse_effect

        # Stop both
        await conductor.stop([light1, light2])
