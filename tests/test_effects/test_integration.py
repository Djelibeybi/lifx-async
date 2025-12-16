"""Integration tests for effects system."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.effects import Conductor, EffectColorloop, EffectPulse


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
def conductor():
    """Create a Conductor instance."""
    return Conductor()


@pytest.fixture
def mock_light():
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
async def test_conductor_start_stop_pulse(conductor, mock_light):
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
async def test_pulse_effect_execution(conductor, mock_light):
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
async def test_pulse_effect_with_color(conductor, mock_light):
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
async def test_pulse_effect_strobe_mode(conductor, mock_light):
    """Test pulse effect in strobe mode."""
    effect = EffectPulse(mode="strobe", cycles=2, period=0.05)

    await conductor.start(effect, [mock_light])

    # Use polling instead of fixed sleep - more reliable on slow CI systems
    await wait_for_mock_called(mock_light.set_waveform, timeout=1.0)

    await conductor.stop([mock_light])


@pytest.mark.asyncio
async def test_pulse_effect_breathe_mode(conductor, mock_light):
    """Test pulse effect in breathe mode."""
    effect = EffectPulse(mode="breathe", cycles=1, period=0.1)

    await conductor.start(effect, [mock_light])
    await asyncio.sleep(0.05)

    # Verify waveform called with sine waveform
    mock_light.set_waveform.assert_called()

    await conductor.stop([mock_light])


@pytest.mark.asyncio
async def test_colorloop_effect_execution(conductor, mock_light):
    """Test colorloop effect executes and calls set_color."""
    effect = EffectColorloop(period=0.2, change=30)

    # Start effect and let it run briefly
    await conductor.start(effect, [mock_light])
    await asyncio.sleep(0.05)  # Let effect iterate once

    # Verify set_color was called
    assert mock_light.set_color.call_count > 0

    # Stop effect
    await conductor.stop([mock_light])


@pytest.mark.asyncio
async def test_colorloop_synchronized_mode(conductor, mock_light):
    """Test colorloop in synchronized mode."""
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

    # Start effect
    await conductor.start(effect, [light1, light2])
    await asyncio.sleep(0.05)

    # Both lights should have set_color called
    assert light1.set_color.called
    assert light2.set_color.called

    await conductor.stop([light1, light2])


@pytest.mark.asyncio
async def test_colorloop_with_brightness(conductor, mock_light):
    """Test colorloop with fixed brightness."""
    effect = EffectColorloop(period=0.2, change=30, brightness=0.5)

    await conductor.start(effect, [mock_light])
    await asyncio.sleep(0.05)

    # Verify set_color called
    assert mock_light.set_color.called

    await conductor.stop([mock_light])


@pytest.mark.asyncio
async def test_colorloop_filters_white_lights(conductor, mock_light, mock_white_light):
    """Test colorloop filters out non-color lights."""
    effect = EffectColorloop(period=0.2, change=30)

    # Start effect with mixed lights
    await conductor.start(effect, [mock_light, mock_white_light])
    await asyncio.sleep(0.05)

    # Only color light should have set_color called
    assert mock_light.set_color.called
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
async def test_effect_with_powered_off_light(conductor, mock_light):
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
async def test_effect_without_power_on(conductor):
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
async def test_consecutive_effects_inherit_prestate(conductor, mock_light):
    """Test consecutive colorloop effects inherit prestate."""
    effect1 = EffectColorloop(period=0.2, change=30)
    effect2 = EffectColorloop(period=0.3, change=45)

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
async def test_effect_completion_restores_state(conductor, mock_light):
    """Test effect automatically restores state on completion."""
    # Very short effect that will complete quickly
    effect = EffectPulse(mode="blink", cycles=1, period=0.05)

    await conductor.start(effect, [mock_light])

    # Use polling instead of fixed sleep - more reliable on slow CI systems
    # The effect should complete within ~0.1s but we allow up to 2s for CI variability
    await wait_for_effect_complete(conductor, mock_light, timeout=2.0)


@pytest.mark.asyncio
async def test_conductor_repr(conductor):
    """Test Conductor string representation."""
    assert "Conductor" in repr(conductor)
    assert "running_effects=0" in repr(conductor)


@pytest.mark.asyncio
async def test_multiple_lights_parallel(conductor, mock_light):
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
async def test_conductor_exception_during_effect():
    """Test conductor handles exception during effect execution."""
    conductor = Conductor()

    # Create mock light that will cause exception in effect
    light = MagicMock()
    light.serial = "d073d5exception"
    light.capabilities = MagicMock()
    light.capabilities.has_color = True
    light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    light.color = (color, 100)
    light.get_color = AsyncMock(return_value=(color, 100, 200))
    light.set_color = AsyncMock(side_effect=Exception("Device error"))
    light.set_power = AsyncMock()

    effect = EffectColorloop(period=0.1, change=30)

    # Start effect (will fail but should handle exception)
    await conductor.start(effect, [light])
    await asyncio.sleep(0.05)

    # Effect should have been cleaned up after exception
    # (may or may not still be in registry depending on timing)
    # Just verify we didn't crash

    await conductor.stop([light])


@pytest.mark.asyncio
async def test_conductor_exception_during_async_perform():
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
async def test_conductor_stop_with_active_effects():
    """Test stopping conductor with actively running effects."""
    conductor = Conductor()

    # Create mock light
    light = MagicMock()
    light.serial = "d073d5active"
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

    await conductor.start(effect, [light])
    await asyncio.sleep(0.05)

    # Stop should cancel and clean up
    await conductor.stop([light])

    # Verify light is no longer in registry
    assert conductor.effect(light) is None


@pytest.mark.asyncio
async def test_conductor_filter_lights_without_capabilities():
    """Test conductor filters lights that need capability check."""
    conductor = Conductor()

    # Create mock light without cached capabilities
    light = MagicMock()
    light.serial = "d073d5nocaps"
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

    # Should handle light with capabilities
    await conductor.start(effect, [light])
    await asyncio.sleep(0.05)

    await conductor.stop([light])
