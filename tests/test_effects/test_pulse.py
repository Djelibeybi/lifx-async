"""Tests for EffectPulse."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.const import KELVIN_COOL
from lifx.effects.pulse import EffectPulse
from lifx.protocol.protocol_types import LightWaveform


def test_pulse_default_mode():
    """Test EffectPulse with default mode (blink)."""
    effect = EffectPulse()

    assert effect.name == "pulse"
    assert effect.mode == "blink"
    assert effect.period == 1.0
    assert effect.cycles == 1
    assert effect.waveform == LightWaveform.PULSE
    assert effect.skew_ratio == 0.5  # 50/50 duty cycle
    assert effect.power_on is True


def test_pulse_strobe_mode():
    """Test EffectPulse with strobe mode."""
    effect = EffectPulse(mode="strobe")

    assert effect.mode == "strobe"
    assert effect.period == 0.1
    assert effect.cycles == 10
    assert effect.waveform == LightWaveform.PULSE


def test_pulse_breathe_mode():
    """Test EffectPulse with breathe mode."""
    effect = EffectPulse(mode="breathe")

    assert effect.mode == "breathe"
    assert effect.period == 1.0
    assert effect.cycles == 1
    assert effect.waveform == LightWaveform.SINE


def test_pulse_ping_mode():
    """Test EffectPulse with ping mode."""
    effect = EffectPulse(mode="ping")

    assert effect.mode == "ping"
    # ping_duration = 5000 - min(2500, 300*1.0) = 4700
    # int_skew = 2^15 - 4700 = 28068
    # float_skew = (28068 + 32767) / 65534 ≈ 0.9283
    assert effect.skew_ratio == pytest.approx(0.9283, rel=1e-4)


def test_pulse_solid_mode():
    """Test EffectPulse with solid mode."""
    effect = EffectPulse(mode="solid")

    assert effect.mode == "solid"
    assert effect.skew_ratio == 0.0  # Minimum skew for minimal variation


def test_pulse_custom_parameters():
    """Test EffectPulse with custom parameters."""
    effect = EffectPulse(mode="blink", period=2.0, cycles=5)

    assert effect.period == 2.0
    assert effect.cycles == 5


def test_pulse_with_color():
    """Test EffectPulse with custom color."""
    color = HSBK.from_rgb(255, 0, 0)
    effect = EffectPulse(mode="blink", color=color)

    assert effect.color == color


def test_pulse_invalid_mode():
    """Test EffectPulse with invalid mode raises ValueError."""
    with pytest.raises(ValueError, match="Invalid mode"):
        EffectPulse(mode="invalid")


def test_pulse_invalid_period():
    """Test EffectPulse with invalid period raises ValueError."""
    with pytest.raises(ValueError, match="Period must be positive"):
        EffectPulse(period=0)


def test_pulse_invalid_cycles():
    """Test EffectPulse with invalid cycles raises ValueError."""
    with pytest.raises(ValueError, match="Cycles must be 1 or higher"):
        EffectPulse(cycles=0)


def test_pulse_repr():
    """Test EffectPulse string representation."""
    effect = EffectPulse(mode="blink", period=1.5, cycles=3)
    repr_str = repr(effect)

    assert "EffectPulse" in repr_str
    assert "mode=blink" in repr_str
    assert "period=1.5" in repr_str
    assert "cycles=3" in repr_str


@pytest.mark.asyncio
async def test_pulse_exception_during_waveform():
    """Test pulse handles exception during set_waveform."""
    effect = EffectPulse(mode="blink", cycles=1, period=0.1)

    # Create mock light that fails on set_waveform
    light = MagicMock()
    light.serial = "d073d5test456"
    light.get_power = AsyncMock(return_value=True)
    color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    light.color = (color, 100)
    light.get_color = AsyncMock(return_value=(color, 100, 200))
    light.set_waveform = AsyncMock(side_effect=Exception("Waveform error"))

    # Set participants
    effect.participants = [light]

    # Should not raise exception, just log error
    await effect.async_play()

    # Verify waveform was attempted
    light.set_waveform.assert_called_once()


@pytest.mark.asyncio
async def test_pulse_from_poweroff_with_custom_color():
    """Test from_poweroff_hsbk with custom color specified."""
    custom_color = HSBK(hue=240, saturation=1.0, brightness=0.8, kelvin=4000)
    effect = EffectPulse(mode="blink", color=custom_color)

    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    # Should return custom color with zero brightness
    assert result.hue == custom_color.hue
    assert result.saturation == custom_color.saturation
    assert result.brightness == 0.0
    assert result.kelvin == custom_color.kelvin


@pytest.mark.asyncio
async def test_pulse_from_poweroff_strobe_mode():
    """Test from_poweroff_hsbk with strobe mode returns cold white."""
    effect = EffectPulse(mode="strobe")

    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    # Strobe starts from cold white
    assert result.hue == 0
    assert result.saturation == 0
    assert result.brightness == 0
    assert result.kelvin == KELVIN_COOL
